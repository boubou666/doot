"""Le squelette sur Android : une fenetre posee par-dessus les autres applis.

Android n'a ni X11 ni Wayland. doot y tourne embarque par Chaquopy dans une
application (`packaging/android`), qui fournit la classe Java
`org.doot.android.OverlayWindow` : une fenetre `TYPE_APPLICATION_OVERLAY` sans
focus ni toucher, dans laquelle on peint les pixels BGRA de `png.Frame`. Tout
le reste, choregraphie comprise, est celui de `overlay.run`.
"""

from __future__ import annotations

from pathlib import Path

from . import overlay, png, screens

try:
    from desktop_overlay import android as plateforme
except ImportError:  # desktop-overlay < 0.3
    plateforme = None

FENETRE = "org.doot.android.OverlayWindow"


class AndroidUnavailable(Exception):
    """Pas d'application hote, ou pas le droit de s'afficher par-dessus."""


def available() -> bool:
    return plateforme is not None and plateforme.jclass(FENETRE) is not None


def monitors() -> list[screens.Monitor]:
    return screens.monitors()


class _Overlay:
    """La fenetre Java, vue comme un overlay de `overlay.run`."""

    def __init__(self, width: int, height: int, x: int, y: int):
        fenetre = plateforme.jclass(FENETRE)
        app = plateforme.context()
        if fenetre is None or app is None:
            raise AndroidUnavailable("aucune application hote")
        if not fenetre.canDraw(app):
            raise AndroidUnavailable("superposition refusee")
        self.fenetre = fenetre(app, int(width), int(height), int(x), int(y))

    def draw(self, payload: bytes) -> None:
        self.fenetre.draw(payload)

    def move(self, x: int, y: int) -> None:
        self.fenetre.move(int(x), int(y))

    def map(self) -> None:
        self.fenetre.show()

    def close(self) -> None:
        self.fenetre.close()


def play(frame: png.Frame, x: int, y: int, duration: float,
         opacity: float = 1.0, wav_path: Path | None = None, pan: float = 0.0,
         start: tuple[int, int] | None = None, slide_ms: int = 0,
         spins: list | None = None, spin_ms: int = 0,
         beats: list | None = None, bobs: list | None = None,
         voices: list[list] | None = None, columns: int = 1,
         gap: int = 0, glitch_effect: bool = False) -> None:
    """Meme contrat que `x11.play` : AndroidUnavailable tant que rien n'est affiche."""
    glisse = slide_ms > 0 and start is not None and tuple(start) != (x, y)
    depart_x, depart_y = start if glisse else (x, y)
    overlay.run(_Overlay(frame.width, frame.height, depart_x, depart_y),
                frame, x, y, duration, opacity, wav_path, pan, start, slide_ms,
                spins, spin_ms, beats, bobs, voices, columns, gap, glitch_effect)
