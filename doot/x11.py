"""Overlay X11 a vraie transparence par pixel, sans dependance.

tkinter ne sait pas faire d'alpha par pixel sur X11/XWayland : il cree ses
fenetres sur le visual par defaut, sans canal alpha, et compose donc l'image
sur une couleur de fond opaque (le rectangle sombre de window.py). Il n'existe
pas d'equivalent X11 au `-transparentcolor` de Windows.

On appelle donc libX11 directement avec ctypes, qui est dans la stdlib : une
fenetre de profondeur 32 sur un visual TrueColor ARGB, que le compositeur
compose avec le bureau. libX11 et libXext sont forcement la, tkinter en depend.

Ne marche que sur X11 (XWayland compris) ; ailleurs, `available()` renvoie
False et l'appelant garde le chemin tkinter.
"""

from __future__ import annotations

import contextlib
import ctypes
import os
import sys
from ctypes import POINTER, byref, c_char_p, c_int, c_long, c_uint, c_ulong, c_void_p
from pathlib import Path

from . import overlay, png, screens, sound

TRUE_COLOR = 4
Z_PIXMAP = 2
ALLOC_NONE = 0
INPUT_OUTPUT = 1
PROP_MODE_REPLACE = 0
XA_ATOM = 4
XA_CARDINAL = 6
SHAPE_INPUT = 2
SHAPE_SET = 0

CW_BACK_PIXEL = 1 << 1
CW_BORDER_PIXEL = 1 << 3
CW_OVERRIDE_REDIRECT = 1 << 9
CW_EVENT_MASK = 1 << 11
CW_COLORMAP = 1 << 13

OPAQUE = 0xFFFFFFFF


class X11Unavailable(Exception):
    """Pas d'overlay ARGB possible ici : l'appelant retombe sur tkinter."""


class XVisualInfo(ctypes.Structure):
    _fields_ = [
        ("visual", c_void_p),
        ("visualid", c_ulong),
        ("screen", c_int),
        ("depth", c_int),
        ("class_", c_int),
        ("red_mask", c_ulong),
        ("green_mask", c_ulong),
        ("blue_mask", c_ulong),
        ("colormap_size", c_int),
        ("bits_per_rgb", c_int),
    ]


class XSetWindowAttributes(ctypes.Structure):
    _fields_ = [
        ("background_pixmap", c_ulong),
        ("background_pixel", c_ulong),
        ("border_pixmap", c_ulong),
        ("border_pixel", c_ulong),
        ("bit_gravity", c_int),
        ("win_gravity", c_int),
        ("backing_store", c_int),
        ("backing_planes", c_ulong),
        ("backing_pixel", c_ulong),
        ("save_under", c_int),
        ("event_mask", c_long),
        ("do_not_propagate_mask", c_long),
        ("override_redirect", c_int),
        ("colormap", c_ulong),
        ("cursor", c_ulong),
    ]


class XImage(ctypes.Structure):
    """Champs de tete de XImage ; le reste (table de fonctions) ne nous sert pas."""

    _fields_ = [
        ("width", c_int),
        ("height", c_int),
        ("xoffset", c_int),
        ("format", c_int),
        ("data", c_char_p),
        ("byte_order", c_int),
        ("bitmap_unit", c_int),
        ("bitmap_bit_order", c_int),
        ("bitmap_pad", c_int),
        ("depth", c_int),
        ("bytes_per_line", c_int),
        ("bits_per_pixel", c_int),
        ("red_mask", c_ulong),
        ("green_mask", c_ulong),
        ("blue_mask", c_ulong),
    ]


_ERROR_HANDLER = ctypes.CFUNCTYPE(c_int, c_void_p, c_void_p)
_state: dict = {}


def _swallow_error(_display, _event) -> int:
    # Sans ce garde-fou, le gestionnaire par defaut de Xlib ecrit sur stderr
    # puis tue le processus : le daemon mourrait sur la moindre broutille.
    return 0


def _library():
    """libX11 (+ libXext), prototypes poses une seule fois."""
    if "lib" in _state:
        return _state["lib"]

    x = ctypes.CDLL("libX11.so.6")
    try:
        ext = ctypes.CDLL("libXext.so.6")
    except OSError:
        ext = None

    x.XOpenDisplay.argtypes = [c_char_p]
    x.XOpenDisplay.restype = c_void_p
    x.XCloseDisplay.argtypes = [c_void_p]
    x.XDefaultScreen.argtypes = [c_void_p]
    x.XDefaultScreen.restype = c_int
    x.XRootWindow.argtypes = [c_void_p, c_int]
    x.XRootWindow.restype = c_ulong
    x.XMatchVisualInfo.argtypes = [c_void_p, c_int, c_int, c_int, POINTER(XVisualInfo)]
    x.XMatchVisualInfo.restype = c_int
    x.XCreateColormap.argtypes = [c_void_p, c_ulong, c_void_p, c_int]
    x.XCreateColormap.restype = c_ulong
    x.XFreeColormap.argtypes = [c_void_p, c_ulong]
    x.XCreateWindow.argtypes = [
        c_void_p, c_ulong, c_int, c_int, c_uint, c_uint, c_uint, c_int,
        c_uint, c_void_p, c_ulong, POINTER(XSetWindowAttributes),
    ]
    x.XCreateWindow.restype = c_ulong
    x.XDestroyWindow.argtypes = [c_void_p, c_ulong]
    x.XMoveWindow.argtypes = [c_void_p, c_ulong, c_int, c_int]
    x.XMapRaised.argtypes = [c_void_p, c_ulong]
    x.XUnmapWindow.argtypes = [c_void_p, c_ulong]
    x.XCreateGC.argtypes = [c_void_p, c_ulong, c_ulong, c_void_p]
    x.XCreateGC.restype = c_void_p
    x.XFreeGC.argtypes = [c_void_p, c_void_p]
    x.XCreateImage.argtypes = [
        c_void_p, c_void_p, c_uint, c_int, c_int, c_char_p,
        c_uint, c_uint, c_int, c_int,
    ]
    x.XCreateImage.restype = POINTER(XImage)
    x.XPutImage.argtypes = [
        c_void_p, c_ulong, c_void_p, POINTER(XImage),
        c_int, c_int, c_int, c_int, c_uint, c_uint,
    ]
    x.XInternAtom.argtypes = [c_void_p, c_char_p, c_int]
    x.XInternAtom.restype = c_ulong
    x.XChangeProperty.argtypes = [
        c_void_p, c_ulong, c_ulong, c_ulong, c_int, c_int, c_void_p, c_int,
    ]
    x.XFlush.argtypes = [c_void_p]
    x.XSync.argtypes = [c_void_p, c_int]
    x.XFree.argtypes = [c_void_p]
    x.XSetErrorHandler.argtypes = [c_void_p]
    x.XSetErrorHandler.restype = c_void_p

    if ext is not None:
        ext.XShapeCombineRectangles.argtypes = [
            c_void_p, c_ulong, c_int, c_int, c_int, c_void_p, c_int, c_int, c_int,
        ]

    _state["handler"] = _ERROR_HANDLER(_swallow_error)
    _state["lib"] = (x, ext)
    return _state["lib"]


@contextlib.contextmanager
def _errors_muted():
    """Coupe les erreurs X, et rend la main au gestionnaire precedent apres.

    XSetErrorHandler est global au processus, et tkinter est un client Xlib du
    meme processus : le poser une fois pour toutes ne tient pas, un seul repli
    vers tkinter installerait le gestionnaire de Tk par-dessus pour de bon. On
    l'installe donc autour de chaque overlay, et on repose l'ancien en sortant
    pour ne pas avaler les erreurs de Tk, qui n'a rien demande.
    """
    x, _ = _library()
    previous = x.XSetErrorHandler(_state["handler"])
    try:
        yield
    finally:
        x.XSetErrorHandler(previous)


def available() -> bool:
    """Vrai si un overlay ARGB est jouable ici."""
    if sys.platform in ("win32", "darwin") or not os.environ.get("DISPLAY"):
        return False
    try:
        _library()
    except Exception:
        return False
    return True


class _Overlay:
    """Une fenetre ARGB sans bordure, posee au pixel pres, invisible au clic."""

    def __init__(self, width: int, height: int, x: int, y: int):
        self.x11, self.ext = _library()
        self.width = width
        self.height = height
        self.display = None
        self.window = 0
        self.colormap = 0
        self.gc = None
        self.image = None
        self._payload = None

        display = self.x11.XOpenDisplay(None)
        if not display:
            raise X11Unavailable("connexion au serveur X impossible")
        self.display = display

        screen = self.x11.XDefaultScreen(display)
        root = self.x11.XRootWindow(display, screen)
        visual = XVisualInfo()
        if not self.x11.XMatchVisualInfo(display, screen, 32, TRUE_COLOR, byref(visual)):
            self.close()
            raise X11Unavailable("aucun visual ARGB 32 bits")

        self.colormap = self.x11.XCreateColormap(display, root, visual.visual, ALLOC_NONE)
        attributes = XSetWindowAttributes()
        attributes.background_pixel = 0
        attributes.border_pixel = 0
        attributes.colormap = self.colormap
        attributes.override_redirect = 1
        attributes.event_mask = 0

        self.window = self.x11.XCreateWindow(
            display, root, x, y, width, height, 0, 32, INPUT_OUTPUT, visual.visual,
            CW_BACK_PIXEL | CW_BORDER_PIXEL | CW_COLORMAP | CW_OVERRIDE_REDIRECT | CW_EVENT_MASK,
            byref(attributes),
        )
        if not self.window:
            self.close()
            raise X11Unavailable("creation de la fenetre refusee")

        self.gc = self.x11.XCreateGC(display, self.window, 0, None)
        self.image = self.x11.XCreateImage(
            display, visual.visual, 32, Z_PIXMAP, 0, None, width, height, 32, 0
        )
        if not self.gc or not self.image:
            self.close()
            raise X11Unavailable("contexte graphique indisponible")

        # Xlib calcule le pas de ligne lui-meme ; s'il ne tombait pas sur nos
        # quatre octets par pixel, XPutImage lirait hors du tampon.
        stride = self.image.contents.bytes_per_line
        if stride != width * 4 or self.image.contents.bits_per_pixel != 32:
            self.close()
            raise X11Unavailable(f"format inattendu : {stride} octets par ligne")

        self._declare_notification()
        self._let_clicks_through()

    def _atom(self, name: str) -> int:
        return self.x11.XInternAtom(self.display, name.encode(), 0)

    def _declare_notification(self) -> None:
        value = c_ulong(self._atom("_NET_WM_WINDOW_TYPE_NOTIFICATION"))
        self.x11.XChangeProperty(
            self.display, self.window, self._atom("_NET_WM_WINDOW_TYPE"),
            XA_ATOM, 32, PROP_MODE_REPLACE, byref(value), 1,
        )

    def _let_clicks_through(self) -> None:
        """Region d'entree vide : la souris traverse le squelette."""
        if self.ext is None:
            return
        self.ext.XShapeCombineRectangles(
            self.display, self.window, SHAPE_INPUT, 0, 0, None, 0, SHAPE_SET, 0,
        )

    def draw(self, payload: bytes) -> None:
        self._payload = payload  # garde le tampon en vie tant que X le lit
        self.image.contents.data = payload
        self.x11.XPutImage(
            self.display, self.window, self.gc, self.image,
            0, 0, 0, 0, self.width, self.height,
        )
        self.x11.XFlush(self.display)

    def move(self, x: int, y: int) -> None:
        self.x11.XMoveWindow(self.display, self.window, int(x), int(y))

    def map(self) -> None:
        self.x11.XMapRaised(self.display, self.window)
        self.x11.XSync(self.display, 0)

    def close(self) -> None:
        if self.display is None:
            return
        try:
            if self.image:
                self.image.contents.data = None  # le tampon appartient a Python
                self.x11.XFree(self.image)
            if self.gc:
                self.x11.XFreeGC(self.display, self.gc)
            if self.window:
                self.x11.XUnmapWindow(self.display, self.window)
                self.x11.XDestroyWindow(self.display, self.window)
            if self.colormap:
                self.x11.XFreeColormap(self.display, self.colormap)
            self.x11.XCloseDisplay(self.display)
        finally:
            self.display = None
            self.window = 0
            self.image = None
            self.gc = None


def play(frame: png.Frame, x: int, y: int, duration: float,
         opacity: float = 1.0, wav_path: Path | None = None, pan: float = 0.0,
         start: tuple[int, int] | None = None, slide_ms: int = 0,
         spins: list | None = None, spin_ms: int = 0,
         beats: list | None = None, bobs: list | None = None,
         voices: list[list] | None = None, columns: int = 1,
         gap: int = 0, glitch_effect: bool = False) -> None:
    """Fait surgir l'image puis la laisse s'effacer.

    `pan` place le son de -1 (gauche) a +1 (droite), selon l'endroit du bureau
    ou l'image apparait. `start` et `slide_ms` font entrer l'image en glissant
    depuis ce point jusqu'a (`x`, `y`), sur l'un ou l'autre axe. `spins` et
    `spin_ms` lui font faire un tour complet sur place ; `beats` et `bobs` lui
    font hocher la tete a chaque coup de trompette.

    Leve X11Unavailable tant que rien n'est affiche ; une fois la fenetre a
    l'ecran, on ne remonte plus d'erreur, un doot ecourte valant mieux qu'un
    doot en double par le chemin de repli.
    """
    with _errors_muted():
        _play(frame, x, y, duration, opacity, wav_path, pan, start, slide_ms,
              spins, spin_ms, beats, bobs, voices, columns, gap, glitch_effect)


def _play(frame, x, y, duration, opacity, wav_path, pan=0.0,
          start=None, slide_ms=0, spins=None, spin_ms=0,
          beats=None, bobs=None, voices=None, columns=1, gap=0,
          glitch_effect=False) -> None:
    glisse = slide_ms > 0 and start is not None and tuple(start) != (x, y)
    depart_x, depart_y = start if glisse else (x, y)
    overlay.run(_Overlay(frame.width, frame.height, depart_x, depart_y),
                frame, x, y, duration, opacity, wav_path, pan, start, slide_ms,
                spins, spin_ms, beats, bobs, voices, columns, gap, glitch_effect)
