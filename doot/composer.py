"""Petit sequencer a pas qui produit du RTTTL valide pour la GUI."""

from __future__ import annotations

import os
import re
from pathlib import Path


STEPS = 16
PITCHES = (
    ("SI", "b"), ("LA#", "a#"), ("LA", "a"), ("SOL#", "g#"),
    ("SOL", "g"), ("FA#", "f#"), ("FA", "f"), ("MI", "e"),
    ("RE#", "d#"), ("RE", "d"), ("DO#", "c#"), ("DO", "c"),
)
PITCH_NAMES = frozenset(note for _label, note in PITCHES)


class ComposerError(ValueError):
    """La partition ne peut pas encore etre jouee ou sauvee."""


def empty_pattern() -> list[str | None]:
    return [None] * STEPS


def toggle(pattern: list[str | None], step: int, note: str) -> None:
    """Pose une note, la remplace, ou l'efface si on reclique dessus."""
    if not 0 <= step < len(pattern):
        raise ComposerError("pas hors de la grille")
    if note not in PITCH_NAMES:
        raise ComposerError(f"note inconnue : {note}")
    pattern[step] = None if pattern[step] == note else note


def safe_name(title: str) -> str:
    """Nom de fichier court et portable, sans laisser sortir de melodies/."""
    compact = re.sub(r"[^\w-]+", "-", title.strip(), flags=re.UNICODE).strip("-_")
    if not compact:
        raise ComposerError("donne un nom a ta melodie")
    return compact[:64]


def rtttl(title: str, tempo: int, octave: int,
          pattern: list[str | None]) -> str:
    if len(pattern) != STEPS:
        raise ComposerError(f"la grille doit contenir {STEPS} pas")
    if not 1 <= int(tempo) <= 999:
        raise ComposerError("le tempo doit etre compris entre 1 et 999 BPM")
    if not 1 <= int(octave) <= 8:
        raise ComposerError("l'octave doit etre comprise entre 1 et 8")
    unknown = [note for note in pattern if note is not None and note not in PITCH_NAMES]
    if unknown:
        raise ComposerError(f"note inconnue : {unknown[0]}")
    if not any(pattern):
        raise ComposerError("pose au moins une note dans la grille")

    stem = safe_name(title)
    notes = ",".join(note or "p" for note in pattern)
    return f"{stem}:d=16,o={int(octave)},b={int(tempo)}:{notes}\n"


def write(path: Path, title: str, tempo: int, octave: int,
          pattern: list[str | None]) -> Path:
    """Ecriture atomique d'une partition RTTTL."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(rtttl(title, tempo, octave, pattern), encoding="utf-8")
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except OSError:
            pass
    return path


def save(directory: Path, title: str, tempo: int, octave: int,
         pattern: list[str | None]) -> Path:
    """Sauve sans ecraser : les versions suivantes recoivent -2, -3, etc."""
    directory = Path(directory)
    stem = safe_name(title)
    destination = directory / f"{stem}.rtttl"
    suffix = 2
    while destination.exists():
        destination = directory / f"{stem}-{suffix}.rtttl"
        suffix += 1
    return write(destination, title, tempo, octave, pattern)
