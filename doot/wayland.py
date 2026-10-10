"""Overlay Wayland natif via wlr-layer-shell, sans dependance.

Sous Wayland, un client n'a aucun moyen de se placer : ni le coeur du protocole
ni xdg-shell ne l'autorisent, le compositeur decide. XWayland ne rattrape rien,
il applique aux coordonnees demandees le facteur d'echelle global et pose la
fenetre sur une dalle qui ne suit pas la geometrie annoncee.

`wlr-layer-shell` est la seule voie : la surface se cree sur un `wl_output`
choisi et se positionne par ancrage et marges, en coordonnees logiques. On parle
donc le protocole directement sur la socket, comme screens.py le fait pour X11.
Le descripteur du tampon partage passe par SCM_RIGHTS, tout est dans la stdlib.

Verifie sur Hyprland. Sway, river et KDE implementent aussi layer-shell, mais
le glissement s'appuie sur des marges negatives et rien ne dit qu'ils ne les
bornent pas a zero : le squelette apparaitrait alors pose contre le bord au lieu
d'y entrer. GNOME n'implemente pas layer-shell du tout : `available()` renvoie
False et l'appelant garde le chemin X11 ou tkinter.
"""

from __future__ import annotations

import array
import mmap
import os
import socket
import struct
import sys
from pathlib import Path

from . import overlay, png, screens

ARGB8888 = 0
LAYER_OVERLAY = 3
ANCHOR_TOP, ANCHOR_LEFT = 1, 4

_WL_DISPLAY = 1
_DISPLAY_SYNC, _DISPLAY_GET_REGISTRY = 0, 1
_REGISTRY_BIND = 0
_COMPOSITOR_CREATE_SURFACE, _COMPOSITOR_CREATE_REGION = 0, 1
_SHM_CREATE_POOL = 0
_POOL_CREATE_BUFFER = 0
_SURFACE_ATTACH, _SURFACE_DAMAGE = 1, 2
_SURFACE_SET_INPUT_REGION, _SURFACE_COMMIT = 5, 6
_SHELL_GET_LAYER_SURFACE = 0
_XDG_OUTPUT_GET = 1
_LAYER_SET_SIZE, _LAYER_SET_ANCHOR, _LAYER_SET_EXCLUSIVE = 0, 1, 2
_LAYER_SET_MARGIN, _LAYER_SET_KEYBOARD, _LAYER_ACK = 3, 4, 6


class WaylandUnavailable(Exception):
    """Rien a afficher par ce chemin ; l'appelant se rabat ailleurs."""


def _text(value: str) -> bytes:
    raw = value.encode() + b"\0"
    return struct.pack("=I", len(raw)) + raw + b"\0" * (-len(raw) % 4)


class _Connection:
    """Le minimum du protocole Wayland : objets, requetes, evenements."""

    def __init__(self):
        runtime = os.environ.get("XDG_RUNTIME_DIR")
        display = os.environ.get("WAYLAND_DISPLAY")
        if not runtime or not display:
            raise WaylandUnavailable("pas de session Wayland")
        path = display if display.startswith("/") else os.path.join(runtime, display)
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            self.sock.connect(path)
        except OSError as erreur:
            self.sock.close()
            raise WaylandUnavailable(str(erreur))
        self.sock.settimeout(3)
        self.buf = b""
        self.next_id = 2
        self.globals: dict[str, list[tuple[int, int]]] = {}
        self.handlers: dict[tuple[int, int], object] = {}

    def id(self) -> int:
        value = self.next_id
        self.next_id += 1
        return value

    def send(self, obj: int, opcode: int, payload: bytes = b"", fd: int | None = None):
        size = 8 + len(payload)
        message = struct.pack("=II", obj, (size << 16) | opcode) + payload
        if fd is None:
            self.sock.sendall(message)
        else:
            self.sock.sendmsg([message], [(socket.SOL_SOCKET, socket.SCM_RIGHTS,
                                           array.array("i", [fd]))])

    def pump(self):
        chunk = self.sock.recv(8192)
        if not chunk:
            raise WaylandUnavailable("compositeur deconnecte")
        self.buf += chunk
        while len(self.buf) >= 8:
            obj, word = struct.unpack_from("=II", self.buf)
            size, opcode = word >> 16, word & 0xFFFF
            if size < 8 or len(self.buf) < size:
                break
            body, self.buf = self.buf[8:size], self.buf[size:]
            if obj == _WL_DISPLAY and opcode == 0:
                cible, code = struct.unpack_from("=II", body)
                length, = struct.unpack_from("=I", body, 8)
                raise WaylandUnavailable(
                    "objet %d code %d : %s"
                    % (cible, code, body[12:12 + length - 1].decode("latin-1")))
            handler = self.handlers.get((obj, opcode))
            if handler:
                handler(body)

    def roundtrip(self):
        callback = self.id()
        done = []
        self.handlers[(callback, 0)] = lambda _body: done.append(True)
        self.send(_WL_DISPLAY, _DISPLAY_SYNC, struct.pack("=I", callback))
        while not done:
            self.pump()
        self.handlers.pop((callback, 0), None)

    def _on_global(self, body: bytes):
        name, = struct.unpack_from("=I", body)
        length, = struct.unpack_from("=I", body, 4)
        interface = body[8:8 + length - 1].decode("latin-1")
        offset = 8 + ((length + 3) // 4) * 4
        version, = struct.unpack_from("=I", body, offset)
        self.globals.setdefault(interface, []).append((name, version))

    def connect(self):
        self.registry = self.id()
        self.handlers[(self.registry, 0)] = self._on_global
        self.send(_WL_DISPLAY, _DISPLAY_GET_REGISTRY, struct.pack("=I", self.registry))
        self.roundtrip()

    def bind(self, interface: str, version: int, index: int = 0) -> int:
        entries = self.globals.get(interface)
        if not entries:
            raise WaylandUnavailable("interface absente : " + interface)
        name, annoncee = entries[index]
        new = self.id()
        self.send(self.registry, _REGISTRY_BIND,
                  struct.pack("=I", name) + _text(interface)
                  + struct.pack("=II", min(version, annoncee), new))
        return new

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass


def _collect_outputs(conn: _Connection) -> dict[int, dict]:
    """Chaque `wl_output` avec son nom, sa position et sa taille logique."""
    found: dict[int, dict] = {}
    for index in range(len(conn.globals.get("wl_output", []))):
        oid = conn.bind("wl_output", 4, index)
        found[oid] = {"name": "", "x": 0, "y": 0, "width": 0, "height": 0, "scale": 1}

        def on_geometry(body, oid=oid):
            x, y = struct.unpack_from("=ii", body)
            found[oid]["x"], found[oid]["y"] = x, y

        def on_mode(body, oid=oid):
            flags, width, height, _refresh = struct.unpack_from("=Iiii", body)
            if flags & 1:                      # current
                found[oid]["width"], found[oid]["height"] = width, height

        def on_scale(body, oid=oid):
            found[oid]["scale"], = struct.unpack_from("=i", body)

        def on_name(body, oid=oid):
            length, = struct.unpack_from("=I", body)
            found[oid]["name"] = body[4:4 + length - 1].decode("latin-1")

        conn.handlers[(oid, 0)] = on_geometry
        conn.handlers[(oid, 1)] = on_mode
        conn.handlers[(oid, 2)] = lambda _body: None
        conn.handlers[(oid, 3)] = on_scale
        conn.handlers[(oid, 4)] = on_name
    conn.roundtrip()
    _ask_logical(conn, found)
    return found


def _ask_logical(conn: _Connection, found: dict[int, dict]) -> None:
    """Remplace le calcul `mode / scale` par la geometrie logique exacte.

    `wl_output.scale` est un entier : sous echelle fractionnaire les
    compositeurs laissent `mode` en pixels physiques et arrondissent `scale` au
    superieur, donc la division retreci l'ecran. Une dalle 2560 a l'echelle 1.5
    fait 1707 unites logiques et la division en annonce 1280 : le squelette se
    cantonnerait au quart superieur gauche, et une entree par la droite
    demarrerait au milieu de la dalle au lieu de son bord.

    `zxdg_output_manager_v1` donne la valeur juste. Absent, on garde le calcul.
    """
    if not conn.globals.get("zxdg_output_manager_v1"):
        return
    try:
        manager = conn.bind("zxdg_output_manager_v1", 3)
    except WaylandUnavailable:
        return

    logiques: dict[int, dict] = {}
    par_sortie: dict[int, int] = {}
    for oid in found:
        xid = conn.id()
        logiques[xid] = {}
        par_sortie[oid] = xid
        conn.send(manager, _XDG_OUTPUT_GET, struct.pack("=II", xid, oid))

        def on_position(body, xid=xid):
            x, y = struct.unpack_from("=ii", body)
            logiques[xid]["x"], logiques[xid]["y"] = x, y

        def on_size(body, xid=xid):
            width, height = struct.unpack_from("=ii", body)
            logiques[xid]["width"], logiques[xid]["height"] = width, height

        conn.handlers[(xid, 0)] = on_position
        conn.handlers[(xid, 1)] = on_size
    conn.roundtrip()

    for oid, xid in par_sortie.items():
        mesures = logiques[xid]
        if mesures.get("width") and mesures.get("height"):
            found[oid].update(mesures)
            # La taille est deja logique : plus rien a diviser.
            found[oid]["scale"] = 1


def available() -> bool:
    """Vrai si un overlay layer-shell est jouable ici."""
    if sys.platform in ("win32", "darwin"):
        return False
    conn = None
    try:
        conn = _Connection()
        conn.connect()
        return bool(conn.globals.get("zwlr_layer_shell_v1")
                    and conn.globals.get("wl_compositor")
                    and conn.globals.get("wl_shm"))
    except Exception:
        return False
    finally:
        if conn is not None:
            conn.close()


def monitors() -> list[screens.Monitor]:
    """Les ecrans vus par le compositeur, en coordonnees logiques."""
    conn = None
    try:
        conn = _Connection()
        conn.connect()
        found = []
        for info in _collect_outputs(conn).values():
            echelle = info["scale"] or 1
            if info["width"] and info["height"]:
                found.append(screens.Monitor(
                    info["x"], info["y"],
                    info["width"] // echelle, info["height"] // echelle,
                    name=info["name"]))
        return found
    except Exception:
        return []
    finally:
        if conn is not None:
            conn.close()


class _Overlay:
    """Une surface layer-shell posee au pixel pres, invisible au clic."""

    def __init__(self, width: int, height: int, x: int, y: int,
                 output_at: tuple[int, int] | None = None):
        self.width, self.height = width, height
        self.conn = _Connection()
        self.conn.connect()

        # Les identifiants d'objet valent pour une connexion et une seule : la
        # sortie doit donc etre reliee sur celle-ci, pas sur une autre.
        sorties = _collect_outputs(self.conn)
        ancre = output_at if output_at is not None else (x, y)
        output, _, _ = _locate(ancre[0], ancre[1], sorties)
        self.origin = (sorties[output]["x"], sorties[output]["y"])

        compositor = self.conn.bind("wl_compositor", 4)
        shm = self.conn.bind("wl_shm", 1)
        shell = self.conn.bind("zwlr_layer_shell_v1", 4)

        self.surface = self.conn.id()
        self.conn.send(compositor, _COMPOSITOR_CREATE_SURFACE,
                       struct.pack("=I", self.surface))

        self.layer = self.conn.id()
        self.conn.send(shell, _SHELL_GET_LAYER_SURFACE,
                       struct.pack("=IIII", self.layer, self.surface, output,
                                   LAYER_OVERLAY) + _text("doot"))
        self.conn.send(self.layer, _LAYER_SET_SIZE, struct.pack("=II", width, height))
        self.conn.send(self.layer, _LAYER_SET_ANCHOR,
                       struct.pack("=I", ANCHOR_TOP | ANCHOR_LEFT))
        self.conn.send(self.layer, _LAYER_SET_KEYBOARD, struct.pack("=I", 0))
        self.conn.send(self.layer, _LAYER_SET_EXCLUSIVE, struct.pack("=i", -1))
        self._set_margin(x, y)

        region = self.conn.id()
        self.conn.send(compositor, _COMPOSITOR_CREATE_REGION, struct.pack("=I", region))
        self.conn.send(self.surface, _SURFACE_SET_INPUT_REGION, struct.pack("=I", region))

        self.configured = []
        self.conn.handlers[(self.layer, 0)] = self._on_configure
        self.conn.send(self.surface, _SURFACE_COMMIT)
        while not self.configured:
            self.conn.pump()

        self.stride = width * 4
        self.frame_size = self.stride * height
        self.fd = os.memfd_create("doot", 0)
        os.ftruncate(self.fd, self.frame_size * 2)
        self.pixels = mmap.mmap(self.fd, self.frame_size * 2)
        pool = self.conn.id()
        self.conn.send(shm, _SHM_CREATE_POOL,
                       struct.pack("=Ii", pool, self.frame_size * 2), fd=self.fd)
        self.buffers, self.busy = [], {}
        for index in range(2):
            buf = self.conn.id()
            self.conn.send(pool, _POOL_CREATE_BUFFER,
                           struct.pack("=Iiiiii", buf, index * self.frame_size,
                                       width, height, self.stride, ARGB8888))
            self.buffers.append(buf)
            self.busy[buf] = False
            self.conn.handlers[(buf, 0)] = lambda _body, b=buf: self.busy.__setitem__(b, False)

    def _on_configure(self, body: bytes):
        serial, _width, _height = struct.unpack_from("=III", body)
        self.configured.append(serial)
        self.conn.send(self.layer, _LAYER_ACK, struct.pack("=I", serial))

    def _set_margin(self, x: float, y: float):
        """Les marges sont locales a la sortie ; l'appelant parle en global."""
        self.conn.send(self.layer, _LAYER_SET_MARGIN,
                       struct.pack("=iiii", int(y) - self.origin[1], 0, 0,
                                   int(x) - self.origin[0]))

    def map(self):
        """La surface est deja a l'ecran des la construction."""

    def poll(self):
        """Vide ce qui est arrive sans jamais bloquer."""
        self.conn.sock.setblocking(False)
        try:
            while True:
                try:
                    self.conn.pump()
                except (BlockingIOError, InterruptedError):
                    return
                except OSError:
                    return
        finally:
            self.conn.sock.setblocking(True)
            self.conn.sock.settimeout(3)

    def draw(self, payload: bytes):
        self.poll()
        buf = next((b for b in self.buffers if not self.busy[b]), self.buffers[0])
        offset = self.buffers.index(buf) * self.frame_size
        self.pixels.seek(offset)
        self.pixels.write(payload[:self.frame_size])
        self.busy[buf] = True
        self.conn.send(self.surface, _SURFACE_ATTACH, struct.pack("=Iii", buf, 0, 0))
        self.conn.send(self.surface, _SURFACE_DAMAGE,
                       struct.pack("=iiii", 0, 0, self.width, self.height))
        self.conn.send(self.surface, _SURFACE_COMMIT)

    def move(self, x: float, y: float):
        self._set_margin(int(x), int(y))
        self.conn.send(self.surface, _SURFACE_COMMIT)

    def close(self):
        try:
            self.pixels.close()
            os.close(self.fd)
        except Exception:
            pass
        self.conn.close()


def _locate(x: int, y: int, found: dict[int, dict]) -> tuple[int, int, int]:
    """La sortie qui contient (x, y), et la position locale dedans."""
    best = None
    for oid, info in found.items():
        echelle = info["scale"] or 1
        largeur = info["width"] // echelle
        hauteur = info["height"] // echelle
        dedans = (info["x"] <= x < info["x"] + largeur
                  and info["y"] <= y < info["y"] + hauteur)
        distance = abs(x - info["x"]) + abs(y - info["y"])
        if dedans:
            return oid, x - info["x"], y - info["y"]
        if best is None or distance < best[0]:
            best = (distance, oid, x - info["x"], y - info["y"])
    if best is None:
        raise WaylandUnavailable("aucune sortie")
    return best[1], best[2], best[3]


def play(frame: png.Frame, x: int, y: int, duration: float,
         opacity: float = 1.0, wav_path: Path | None = None, pan: float = 0.0,
         start: tuple[int, int] | None = None, slide_ms: int = 0,
         spins: list | None = None, spin_ms: int = 0,
         beats: list | None = None, bobs: list | None = None,
         voices: list[list] | None = None, columns: int = 1,
         gap: int = 0, glitch_effect: bool = False) -> None:
    """Fait surgir l'image sur la sortie qui contient (x, y), puis l'efface.

    Meme contrat que `x11.play` : leve WaylandUnavailable tant que rien n'est
    affiche, se tait une fois la surface a l'ecran.
    """
    glisse = slide_ms > 0 and start is not None and tuple(start) != (x, y)
    depart_x, depart_y = start if glisse else (x, y)
    surface = _Overlay(frame.width, frame.height, depart_x, depart_y,
                       output_at=(x, y))
    overlay.run(surface, frame, x, y, duration, opacity, wav_path, pan,
                start, slide_ms, spins, spin_ms, beats, bobs,
                voices, columns, gap, glitch_effect)
