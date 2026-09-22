"""Generateur deterministe de petites melodies RTTTL."""

from __future__ import annotations

import random
from pathlib import Path

from . import composer


STYLES = {
    "macabre": (("c", "d#", "f#", "g", "a#"), 92),
    "epique": (("c", "d", "e", "g", "a"), 132),
    "jazz": (("c", "d#", "f", "g", "a", "a#"), 118),
    "chiptune": (("c", "d", "e", "f#", "g", "a", "b"), 168),
    "chaos": (("c", "c#", "d#", "e", "f#", "g#", "a#"), 146),
}


def generate(style: str, seed: str | int | None = None, length: int = 16) -> str:
    style = str(style).casefold()
    if style not in STYLES:
        raise ValueError("style inconnu : " + style + " (" + ", ".join(STYLES) + ")")
    if not 4 <= int(length) <= 64:
        raise ValueError("la melodie doit compter entre 4 et 64 pas")
    notes, tempo = STYLES[style]
    rng = random.Random(f"{style}:{seed if seed is not None else 'doot'}")
    tokens = []
    previous = notes[0]
    for index in range(int(length)):
        if index in (0, int(length) - 1):
            note = notes[0]
        elif rng.random() < 0.12:
            note = "p"
        elif rng.random() < 0.55:
            position = notes.index(previous) if previous in notes else 0
            note = notes[max(0, min(len(notes) - 1, position + rng.choice((-1, 1))))]
        else:
            note = rng.choice(notes)
        tokens.append(note)
        if note != "p":
            previous = note
    title = composer.safe_name(f"{style}-{seed if seed is not None else 'doot'}")
    source = f"{title}:d=16,o=5,b={tempo}:" + ",".join(tokens) + "\n"
    composer.validate_source(source)
    return source


def save(directory: Path, style: str, seed: str | int | None = None,
         name: str = "") -> Path:
    source = generate(style, seed)
    stem = composer.safe_name(name or f"{style}-{seed if seed is not None else 'doot'}")
    path = Path(directory) / f"{stem}.rtttl"
    return composer.write_source(path, source)
