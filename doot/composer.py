"""Petit sequencer a pas qui produit du RTTTL valide pour la GUI."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

from . import melodie


STEPS = 16
PITCHES = (
    ("SI", "b"), ("LA#", "a#"), ("LA", "a"), ("SOL#", "g#"),
    ("SOL", "g"), ("FA#", "f#"), ("FA", "f"), ("MI", "e"),
    ("RE#", "d#"), ("RE", "d"), ("DO#", "c#"), ("DO", "c"),
)
PITCH_NAMES = frozenset(note for _label, note in PITCHES)
_GRID_NOTE = re.compile(r"^(\d+)?([a-hp])(#?)([1-8])?$")


class ComposerError(ValueError):
    """La partition ne peut pas encore etre jouee ou sauvee."""


@dataclass(frozen=True)
class Draft:
    """Une sonnerie simple que la grille de seize pas sait representer."""

    title: str
    tempo: int
    octave: int
    pattern: tuple[str | None, ...]


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


def validate_source(source: str):
    """Valide du RTTTL libre, polyphonique compris, sans le simplifier."""
    try:
        return melodie.parse(source)
    except melodie.MelodieError as exc:
        raise ComposerError(str(exc)) from exc


def import_grid(source: str) -> Draft:
    """Traduit une sonnerie simple vers la grille, ou explique sa limite.

    Le mode source de la page accepte tout ce que le moteur RTTTL sait jouer.
    La grille, elle, represente exactement seize doubles-croches, une octave et
    une seule voix. Refuser le reste evite de raccourcir ou d'aplatir un import
    en silence.
    """
    morceau = validate_source(source)
    lines = [
        line.strip() for line in source.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    if len(lines) != 1 or len(morceau.voices) != 1:
        raise ComposerError("la grille accepte une seule voix ; utilise le mode source")

    parts = lines[0].split(":")
    if len(parts) != 3:
        raise ComposerError("RTTTL incompatible avec la grille")
    title, settings, notes = (part.strip() for part in parts)
    defaults = {"d": 4, "o": 5, "b": 63}
    for item in filter(None, (value.strip() for value in settings.split(","))):
        key, separator, value = item.partition("=")
        if separator and key.strip().lower() in defaults and value.strip().isdigit():
            defaults[key.strip().lower()] = int(value.strip())

    tokens = [token.strip().lower() for token in notes.split(",") if token.strip()]
    if len(tokens) != STEPS:
        raise ComposerError(f"la grille demande exactement {STEPS} pas")

    pattern = []
    octave = defaults["o"]
    for token in tokens:
        match = _GRID_NOTE.fullmatch(token)
        if not match:
            raise ComposerError(
                "la grille accepte seulement des doubles-croches non pointees"
            )
        duration, note, sharp, explicit_octave = match.groups()
        duration = int(duration) if duration else defaults["d"]
        if duration != 16:
            raise ComposerError("la grille accepte seulement des doubles-croches")
        if explicit_octave is not None and int(explicit_octave) != octave:
            raise ComposerError("la grille accepte une seule octave")
        if note == "p":
            pattern.append(None)
            continue
        note = "b" if note == "h" else note
        pitch = note + sharp
        if pitch not in PITCH_NAMES:
            raise ComposerError(f"note incompatible avec la grille : {pitch}")
        pattern.append(pitch)

    return Draft(
        title=title or morceau.name or "melodie",
        tempo=int(morceau.tempo),
        octave=octave,
        pattern=tuple(pattern),
    )


def write_source(path: Path, source: str) -> Path:
    """Valide puis ecrit atomiquement une source RTTTL sans la reformater."""
    validate_source(source)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(source.rstrip() + "\n", encoding="utf-8")
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except OSError:
            pass
    return path


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
