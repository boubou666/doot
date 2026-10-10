"""La boucle d'animation, commune aux overlays qui composent leurs pixels.

`x11.py` et `wayland.py` posent leur surface par des chemins sans rapport, mais
une fois a l'ecran ils font la meme chose : glisser depuis un bord, monter en
fondu, tenir, redescendre. Seul le support change, donc seule la creation de la
surface leur appartient.

Un overlay est n'importe quel objet qui sait `map()`, `draw(pixels)`,
`move(x, y)` en coordonnees globales, et `close()`.
"""

from __future__ import annotations

import time
from pathlib import Path

from . import glitch, png, screens, sound

TICK = 0.04
BOB = 0.18   # duree d'un hochement de tete, en secondes


def bob_step(since: float) -> int:
    """L'etape du hochement `since` secondes apres le coup de trompette.

    0 : droit, 1 : a mi-chemin, 2 : penche. Le squelette se penche vite et
    revient plus lentement, comme le `@keyframes` de la page qui a servi de
    maquette : penche au tiers du mouvement, droit a la fin.
    """
    if since < 0 or since >= BOB:
        return 0
    phase = since / BOB
    if phase < 0.2:
        return 1
    if phase < 0.55:
        return 2
    if phase < 0.8:
        return 1
    return 0


def bob_at(elapsed: float, beats: list) -> int:
    """L'etape du hochement a `elapsed` secondes, `beats` etant les coups."""
    dernier = None
    for coup in beats:
        if coup > elapsed:
            break
        dernier = coup
    return 0 if dernier is None else bob_step(elapsed - dernier)


def run(overlay, frame: png.Frame, x: int, y: int, duration: float,
        opacity: float = 1.0, wav_path: Path | None = None, pan: float = 0.0,
        start: tuple[int, int] | None = None, slide_ms: int = 0,
        spins: list | None = None, spin_ms: int = 0,
        beats: list | None = None, bobs: list | None = None,
        voices: list[list] | None = None, columns: int = 1,
        gap: int = 0, glitch_effect: bool = False) -> None:
    """Joue l'apparition puis rend la main, l'overlay ferme dans tous les cas.

    `spins` sont les quatre etapes d'un tour complet (`png.spin_frames`) :
    l'image les parcourt en `spin_ms` puis reste droite pour le reste du doot.
    Toutes ont la meme taille, celle de `frame`, sinon la surface changerait de
    dimensions en cours de route.

    `beats` sont des instants en secondes et `bobs` les trois etapes du
    hochement (`png.bob_frames`) : a chaque instant le squelette se penche
    puis se redresse. `voices` contient une liste de coups par squelette ; le
    montage en grille est alors reconstruit seulement quand l'un d'eux bouge.
    Meme contrainte de taille, et le tour complet passe avant si les deux sont
    demandes.

    Tant que rien n'est affiche, l'erreur remonte : l'appelant doit pouvoir se
    replier sur un autre backend. Une fois la surface a l'ecran on n'echoue
    plus, un doot ecourte valant mieux qu'un doot en double.
    """
    glisse = slide_ms > 0 and start is not None and tuple(start) != (x, y)
    depart_x, depart_y = start if glisse else (x, y)
    tourne = spin_ms > 0 and spins is not None and len(spins) == 4
    groupe = bool(voices) and bobs is not None and len(bobs) == 3
    hoche = not groupe and bool(beats) and bobs is not None and len(bobs) == 3
    glitch_cache = {}

    try:
        if glitch_effect:
            for image in ([] if groupe else [frame]) + (spins or []) + (bobs or []):
                glitch_cache[id(image)] = glitch.frames(image)
        overlay.map()
    except Exception:
        overlay.close()
        raise

    playback = None
    try:
        playback = sound.play_async(wav_path, pan) if wav_path else None

        total = max(0.4, float(duration))
        fade_in = min(0.22, total / 4)
        fade_out = min(0.5, total / 3)
        ceiling = max(0.0, min(1.0, opacity))
        glissement = slide_ms / 1000.0
        rotation = spin_ms / 1000.0
        debut = time.monotonic()
        montre = None
        quart = 0
        etape = 0
        etapes_groupe = tuple(0 for _ in voices) if groupe else ()
        image_groupe = frame
        last_glitch = None

        while True:
            elapsed = time.monotonic() - debut
            if elapsed >= total:
                break

            # Pendant le glissement, pas de fondu d'apparition : le bord de
            # l'ecran revele deja le squelette.
            if glisse and elapsed <= glissement:
                avance = screens.ease_out(elapsed / glissement)
                overlay.move(depart_x + (x - depart_x) * avance,
                             depart_y + (y - depart_y) * avance)
                factor = 1.0
            elif not glisse and elapsed < fade_in:
                factor = elapsed / fade_in
            elif elapsed > total - fade_out:
                factor = max(0.0, (total - elapsed) / fade_out)
            else:
                factor = 1.0

            # Le tour se joue sur place : les quatre quarts defilent, puis
            # l'image reste droite (quart 0) jusqu'a la fin du doot.
            voulu = int(elapsed / rotation * 4) % 4 if tourne and elapsed < rotation else 0
            penche = bob_at(elapsed, beats) if hoche and not tourne else 0
            glitch_step = glitch.phase(int(elapsed * 1000)) if glitch_effect else None
            groupe_change = False
            if tourne:
                image = spins[voulu]
            elif groupe:
                nouvelles = tuple(bob_at(elapsed, coups) for coups in voices)
                if nouvelles != etapes_groupe or (glitch_effect and glitch_step != last_glitch):
                    etapes_groupe = nouvelles
                    image_groupe = png.montage(
                        [glitch_cache[id(bobs[etape])][glitch_step] if glitch_effect
                         else bobs[etape] for etape in etapes_groupe], columns, gap
                    )
                    groupe_change = True
                image = image_groupe
            elif hoche:
                image = bobs[penche]
            else:
                image = frame

            if glitch_effect and not groupe:
                image = glitch_cache[id(image)][glitch_step]

            level = round(factor * ceiling * 255)
            # Pendant le glissement on redessine a chaque pas : l'opacite ne
            # bouge pas, donc rien ne le declencherait, et le contenu d'une
            # surface qu'on deplace n'est pas garanti d'etre conserve.
            if (level != montre or voulu != quart or penche != etape
                    or groupe_change or glitch_step != last_glitch
                    or (glisse and elapsed <= glissement)):
                overlay.draw(image.faded(level / 255))
                montre = level
                quart = voulu
                etape = penche
                last_glitch = glitch_step
            time.sleep(TICK)
    except Exception:
        pass
    finally:
        sound.release(playback)
        overlay.close()
