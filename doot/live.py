"""Capture et quantification des frappes du Studio Live."""

from __future__ import annotations

from dataclasses import dataclass


KEY_NOTES = {"a": "c", "z": "d", "e": "e", "r": "f", "t": "g", "y": "a", "u": "b"}


@dataclass(frozen=True)
class Hit:
    at: float
    note: str


def quantize(hits: list[Hit], tempo: int = 120, steps: int = 16) -> list[str | None]:
    if not 40 <= int(tempo) <= 300:
        raise ValueError("tempo attendu entre 40 et 300 BPM")
    pattern: list[str | None] = [None] * steps
    step_seconds = 60.0 / int(tempo) / 4.0
    for hit in hits:
        index = round(max(0.0, float(hit.at)) / step_seconds)
        if 0 <= index < steps and hit.note in KEY_NOTES.values():
            pattern[index] = hit.note
    return pattern
