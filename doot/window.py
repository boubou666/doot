"""Overlay tkinter : le squelette apparait par-dessus tout, puis s'efface.

Deux modes :
  - image   : un PNG ou un GIF (anime) depose dans <data_dir>/image/
  - ASCII   : le squelette dessine en caracteres, quand il n'y a pas d'image

Multiplateforme :
  - Windows : fond reellement transparent (-transparentcolor) + fenetre
    "click-through" et sans vol de focus (styles etendus Win32).
  - macOS   : fenetre sans bordure, sans icone dans le Dock.
  - Linux   : l'overlay layer-shell de wayland.py, sinon l'ARGB de x11.py
              prend la main quand il peut (vraie
    transparence par pixel) ; sinon tkinter, type de fenetre "splash" et fond
    sombre, faute d'alpha par pixel sur le visual par defaut.
"""

from __future__ import annotations

import os
import random
import sys
import tempfile
from fractions import Fraction
from pathlib import Path

from desktop_overlay import window as overlay_window

from . import art, png, screens, sound, wayland, x11

TRANSPARENT_KEY = "#ff00ff"
FALLBACK_BG = "#0b0b12"
FOREGROUND = "#f4f4f8"
GIF_FRAME_MS = 90

FONT_CANDIDATES = {
    "win32": ("Consolas", "Lucida Console", "Courier New"),
    "darwin": ("Menlo", "Monaco", "Courier New"),
}
LINUX_FONTS = ("DejaVu Sans Mono", "Liberation Mono", "Noto Sans Mono", "monospace")


class TkinterMissing(RuntimeError):
    """tkinter absent : paquet systeme a installer."""


def _import_tk():
    try:
        return overlay_window.import_tk()
    except overlay_window.TkinterMissing as exc:
        raise TkinterMissing(
            "tkinter est introuvable. Installe-le :\n"
            "  Arch/Manjaro   : sudo pacman -S tk\n"
            "  Debian/Ubuntu  : sudo apt install python3-tk\n"
            "  Fedora         : sudo dnf install python3-tkinter\n"
            "  macOS (brew)   : brew install python-tk\n"
            "  Windows        : reinstalle Python en cochant 'tcl/tk'"
        ) from exc


def _pick_font(tkfont, size: int):
    families = set(tkfont.families())
    candidates = FONT_CANDIDATES.get(sys.platform, LINUX_FONTS)
    for name in candidates:
        if name in families:
            return (name, size, "bold")
    return ("TkFixedFont", size, "bold")


def _rescale(photo, scale: float):
    """Redimensionne une PhotoImage avec les seuls outils de Tk (zoom/subsample)."""
    if scale == 1.0 or scale <= 0:
        return photo
    ratio = Fraction(scale).limit_denominator(4)
    if ratio.numerator != 1:
        photo = photo.zoom(ratio.numerator)
    if ratio.denominator != 1:
        photo = photo.subsample(ratio.denominator)
    return photo


def _load_frames(tk, path: Path, scale: float) -> list:
    """Charge un PNG (1 image) ou un GIF (toutes ses images)."""
    frames = []
    if path.suffix.lower() == ".gif":
        index = 0
        while True:
            try:
                photo = tk.PhotoImage(file=str(path), format=f"gif -index {index}")
            except Exception:
                break
            frames.append(_rescale(photo, scale))
            index += 1
    if not frames:
        frames = [_rescale(tk.PhotoImage(file=str(path)), scale)]
    return frames


COTES = ("left", "right", "top", "bottom")

# Quarts de tour horaires a appliquer pour que le BAS de l'image se retrouve
# contre le bord par lequel le squelette entre.
TOURS = {"left": 1, "top": 2, "right": 3, "bottom": 0}

_ALIAS = {"gauche": "left", "droite": "right", "haut": "top", "bas": "bottom"}


def decide_slide(slide: bool, side: str | None, chance: float, rng=random) -> bool:
    """Ce doot entre-t-il par un bord, ou surgit-il sur place ?

    Les deux se cotoient : tout faire entrer par un bord priverait doot du bon
    vieux squelette qui apparait en plein milieu. Demander un bord precis
    impose le glissement, sinon la demande n'aurait aucun effet une fois sur
    deux.
    """
    if not slide:
        return False
    if side is not None:
        return True
    return rng.random() < max(0.0, min(1.0, chance))


def decide_spin(spin: bool, chance: float, glisse: bool, rng=random) -> bool:
    """Ce doot fait-il un tour complet sur lui-meme ?

    Seulement s'il surgit sur place. Pendant une entree par un bord l'image est
    deja pivotee pour poser les pieds contre ce bord : la faire tourner en plus
    lui ferait perdre le seul repere de l'arrivee, et les deux mouvements se
    disputeraient les memes premieres millisecondes du doot.
    """
    if not spin or glisse:
        return False
    return rng.random() < max(0.0, min(1.0, chance))


def pick_side(side: str | None, rng=random) -> str:
    """Bord d'entree : 'left', 'right', 'top', 'bottom', ou tire au sort."""
    voulu = _ALIAS.get(side, side)
    if voulu in COTES:
        return voulu
    return rng.choice(COTES)


def _rotated_photo(tk, image_path: Path, scale: float, tours: int):
    """Charge un PNG pivote de `tours` quarts de tour, transparence comprise.

    Tk sait miroiter mais pas pivoter, et n'accepte des pixels avec leur alpha
    que par un fichier : on decode, on pivote, on reecrit un PNG a cote.
    """
    frame = png.frame(image_path, scale).rotated(tours)
    tampon = Path(tempfile.gettempdir()) / f"doot-pivote-{os.getpid()}.png"
    png.write_png(tampon, frame)
    return tk.PhotoImage(file=str(tampon))


def _spin_photos(tk, image_path: Path, scale: float) -> list:
    """Les quatre etapes d'un tour complet, en PhotoImage.

    Meme detour que `_rotated_photo`, et pour la meme raison. Elles partagent
    toutes la taille du carre qui contient l'image : la fenetre n'a donc pas a
    changer de geometrie au milieu du tour.
    """
    dossier = Path(tempfile.gettempdir())
    photos = []
    for quarts, frame in enumerate(png.spin_frames(png.frame(image_path, scale))):
        tampon = dossier / f"doot-tour-{os.getpid()}-{quarts}.png"
        png.write_png(tampon, frame)
        photos.append(tk.PhotoImage(file=str(tampon)))
    return photos


def _auto_scale(width: int, height: int, screen_w: int, screen_h: int) -> float:
    """Reduit l'image si elle mange plus de 40 % de l'ecran."""
    limit_h = screen_h * 0.40
    limit_w = screen_w * 0.40
    if height <= limit_h and width <= limit_w:
        return 1.0
    return min(limit_h / height, limit_w / width)


def active_monitors() -> list:
    """Les ecrans tels que les verra le backend qui affichera reellement.

    `--screens` et `--status` doivent decrire l'espace de coordonnees dans
    lequel le squelette sera pose, pas un autre.
    """
    if wayland.available():
        found = wayland.monitors()
        if found:
            return found
    return screens.monitors()


def _show_argb(wav_path, duration, center, opacity, image_path, scale, screen,
               spatialise, slide=True, side=None, slide_ms=420, spin=False,
               spin_ms=700) -> bool:
    """Tente les overlays sans tkinter ; faux si tkinter doit prendre le relais.

    Wayland passe en premier : layer-shell sait poser la surface sur la sortie
    voulue, ce qu'aucun client XWayland ne peut faire. Chaque backend enumere
    lui-meme ses ecrans, parce que les coordonnees doivent venir du meme espace
    que le rendu.

    Reserve aux PNG : les deux composent leurs pixels eux-memes et png.py ne
    lit pas les GIF animes.
    """
    if image_path is None or image_path.suffix.lower() != ".png":
        return False
    for backend, enumere in ((wayland, wayland.monitors), (x11, screens.monitors)):
        if _tente_overlay(backend, enumere, wav_path, duration, center, opacity,
                          image_path, scale, screen, spatialise, slide, side,
                          slide_ms, spin, spin_ms):
            return True
    return False


def _tente_overlay(backend, enumere, wav_path, duration, center, opacity,
                   image_path, scale, screen, spatialise, slide, side,
                   slide_ms, spin, spin_ms) -> bool:
    if not backend.available():
        return False

    try:
        image_width, image_height = png.size(image_path)
        if spin:
            # Le tour se joue dans le carre qui contient l'image : c'est lui
            # qui doit tenir a l'ecran, et pas seulement l'image droite.
            image_width = image_height = max(image_width, image_height)
        found = enumere()
        monitor = screens.pick(found, screen)
        wanted = scale if scale is not None else _auto_scale(
            image_width, image_height, monitor.width, monitor.height
        )
        frame = png.frame(image_path, wanted)

        entree = pick_side(side) if slide else None
        if entree:
            # Le bas de l'image se pose contre le bord d'entree.
            frame = frame.rotated(TOURS[entree])

        spins = png.spin_frames(frame) if spin else None
        if spins:
            frame = spins[0]  # le carre : toutes les etapes ont sa taille

        if slide:
            depart_x, depart_y, repos_x, repos_y = monitor.entry(
                frame.width, frame.height, entree, random, center=center
            )
        else:
            repos_x, repos_y = monitor.place(frame.width, frame.height, center, random)
            depart_x, depart_y = repos_x, repos_y

        pan = screens.pan_for(repos_x + frame.width / 2, found) if spatialise else 0.0
    except Exception:
        return False

    try:
        backend.play(frame, repos_x, repos_y, duration, opacity, wav_path, pan,
                     start=(depart_x, depart_y), slide_ms=slide_ms if slide else 0,
                     spins=spins, spin_ms=spin_ms if spins else 0)
    except Exception:
        # overlay.run ne laisse remonter qu'avant affichage : arriver ici veut
        # dire que rien n'est a l'ecran, donc le repli ne fera pas de double.
        return False
    return True


def show(
    wav_path: Path | None = None,
    duration: float = 2.8,
    font_size: int = 15,
    center: bool = False,
    opacity: float = 1.0,
    image_path: Path | None = None,
    scale: float | None = None,
    screen: str | int | None = None,
    spatialise: bool = True,
    slide: bool = True,
    side: str | None = None,
    slide_ms: int = 420,
    slide_chance: float = 0.5,
    spin: bool = True,
    spin_chance: float = 0.25,
    spin_ms: int = 700,
) -> None:
    """Affiche un doot et rend la main quand il a disparu.

    `screen` : None/"random" pour un ecran au hasard, "primary" pour l'ecran
    principal, ou l'index d'un ecran precis.

    `spatialise` : place le son a gauche ou a droite selon l'endroit ou le
    squelette apparait sur le bureau.

    `slide` : autorise l'entree en glissant depuis un bord. `slide_chance` dit
    a quelle frequence elle a lieu : le reste du temps le squelette surgit sur
    place, au milieu de l'ecran, droit et sans glisser. `side` force le bord et
    impose le glissement, `slide_ms` en regle la duree.

    `spin` autorise le tour complet sur soi-meme, reserve aux apparitions sur
    place. `spin_chance` dit a quelle frequence il a lieu, `spin_ms` en regle
    la duree. Il demande une image PNG : les GIF animes et l'ASCII art restent
    droits.
    """
    slide = decide_slide(slide, side, slide_chance)
    # Un tour de duree nulle n'est pas un tour : il ne ferait que payer les
    # quatre orientations pour ne rien montrer.
    spin = decide_spin(spin, spin_chance, slide) and spin_ms > 0
    if _show_argb(wav_path, duration, center, opacity, image_path, scale, screen,
                  spatialise, slide, side, slide_ms, spin, spin_ms):
        return

    tk, tkfont = _import_tk()

    root = tk.Tk()
    background = overlay_window.prepare_window(
        root,
        transparent_key=TRANSPARENT_KEY,
        fallback_background=FALLBACK_BG,
    )

    # Ecran d'accueil : tkinter ne sait pas decrire un montage multi-ecrans,
    # on demande au systeme (voir screens.py).
    found = screens.monitors(root.winfo_screenwidth(), root.winfo_screenheight())
    monitor = screens.pick(found, screen)
    screen_w, screen_h = monitor.width, monitor.height

    # Le bord d'entree decide de l'orientation : le bas de l'image doit se
    # poser contre lui. Il se choisit donc avant de charger quoi que ce soit.
    entree = pick_side(side) if slide else None
    tours = TOURS[entree] if entree else 0

    frames: list = []
    spins: list = []
    if image_path is not None:
        try:
            probe = tk.PhotoImage(file=str(image_path)) if image_path.suffix.lower() != ".gif" \
                else tk.PhotoImage(file=str(image_path), format="gif -index 0")
            large, haut = probe.width(), probe.height()
            if tours % 2:
                large, haut = haut, large  # un quart de tour echange les cotes
            if spin:
                # Le tour se joue dans le carre qui contient l'image : c'est lui
                # qui doit tenir a l'ecran, et pas seulement l'image droite.
                large = haut = max(large, haut)
            wanted = scale if scale is not None else _auto_scale(
                large, haut, screen_w, screen_h
            )
            if spin and image_path.suffix.lower() == ".png":
                spins = _spin_photos(tk, image_path, wanted)
                frames = [spins[0]]
            elif tours and image_path.suffix.lower() == ".png":
                frames = [_rotated_photo(tk, image_path, wanted, tours)]
            else:
                # Les GIF animes restent droits : png.py ne les decode pas.
                frames = _load_frames(tk, image_path, wanted)
        except Exception:
            # Image illisible : on retombe sur l'ASCII, qui ne tourne pas.
            frames = []
            spins = []

    widget_kwargs = dict(bg=background, borderwidth=0, highlightthickness=0)
    if frames:
        label = tk.Label(root, image=frames[0], **widget_kwargs)
        # garde une reference, sinon Tk libere les images
        label.image = frames + spins
    else:
        label = tk.Label(
            root,
            text=art.widest_frame(),
            font=_pick_font(tkfont, font_size),
            fg=FOREGROUND,
            justify="left",
            anchor="nw",
            padx=6,
            pady=6,
            **widget_kwargs,
        )
    label.pack()

    # Dimensionne sur l'etat le plus large, puis repart de la premiere image.
    root.update_idletasks()
    width = max(label.winfo_reqwidth(), 1)
    height = max(label.winfo_reqheight(), 1)
    # Le squelette ASCII ne se pivote pas : des glyphes a chasse fixe tournes
    # d'un quart de tour ne veulent plus rien dire. On se contente de le
    # retourner quand il entre par la droite.
    retourne = not frames and entree == "right"
    if not frames:
        label.configure(text=art.frame(0, mirrored=retourne))

    if slide:
        depart_x, depart_y, repos_x, repos_y = monitor.entry(
            width, height, entree, random, center=center
        )
    else:
        repos_x, repos_y = monitor.place(width, height, center, random)
        depart_x, depart_y = repos_x, repos_y

    overlay_window.move_window(
        root, width, height, depart_x, depart_y
    )
    overlay_window.show_window(root)

    # Le son sort de l'endroit ou le squelette se posera.
    pan = screens.pan_for(repos_x + width / 2, found) if spatialise else 0.0
    playback = sound.play_async(wav_path, pan) if wav_path else None

    total_ms = max(400, int(duration * 1000))
    fade_in_ms = min(220, total_ms // 4)
    fade_out_ms = min(500, total_ms // 3)
    tick_ms = 40
    state = {"elapsed": 0, "step": 0, "quart": 0}

    def set_alpha(value: float) -> None:
        try:
            root.wm_attributes("-alpha", max(0.0, min(1.0, value)) * opacity)
        except Exception:
            pass

    def tick() -> None:
        state["elapsed"] += tick_ms
        elapsed = state["elapsed"]

        # Pendant le glissement, pas de fondu d'apparition : le bord de l'ecran
        # revele deja le squelette, et les deux ensemble font bouillie.
        if slide and elapsed <= slide_ms:
            avance = screens.ease_out(elapsed / slide_ms)
            overlay_window.move_window(
                root,
                width,
                height,
                int(depart_x + (repos_x - depart_x) * avance),
                int(depart_y + (repos_y - depart_y) * avance),
            )
            set_alpha(1.0)
        elif not slide and elapsed < fade_in_ms:
            set_alpha(elapsed / fade_in_ms)
        elif elapsed > total_ms - fade_out_ms:
            set_alpha(max(0, total_ms - elapsed) / fade_out_ms)
        else:
            set_alpha(1.0)

        # Le tour se joue sur place : les quatre quarts defilent, puis l'image
        # reste droite (quart 0) jusqu'a la fin du doot.
        if spins:
            quart = int(elapsed / spin_ms * 4) % 4 if elapsed < spin_ms else 0
            if quart != state["quart"]:
                state["quart"] = quart
                label.configure(image=spins[quart])

        if frames:
            if len(frames) > 1:
                wanted = (elapsed // GIF_FRAME_MS) % len(frames)
                if wanted != state["step"]:
                    state["step"] = wanted
                    label.configure(image=frames[wanted])
        else:
            wanted = min(len(art.DOOT_FRAMES) - 1, elapsed // art.FRAME_MS)
            if wanted != state["step"]:
                state["step"] = wanted
                label.configure(text=art.frame(wanted, mirrored=retourne))

        if elapsed >= total_ms:
            root.quit()
            return
        root.after(tick_ms, tick)

    root.after(tick_ms, tick)
    try:
        root.mainloop()
    finally:
        sound.release(playback)
        try:
            root.destroy()
        except Exception:
            pass
