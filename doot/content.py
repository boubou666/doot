"""Preferences de tirage des melodies et rencontres.

Le fichier est volontairement declaratif : un poids nul masque un contenu,
un poids superieur a un le favorise, et une absence garde le poids historique.
"""

from __future__ import annotations

import json
import os
from pathlib import Path


VERSION = 1
KINDS = ("melodies", "events")


def empty() -> dict:
    return {"version": VERSION, "melodies": {}, "events": {}}


def _weights(value) -> dict[str, float]:
    if not isinstance(value, dict):
        return {}
    clean = {}
    for name, weight in value.items():
        if not isinstance(name, str) or not name.strip():
            continue
        if isinstance(weight, bool) or not isinstance(weight, (int, float)):
            continue
        clean[name.casefold()] = max(0.0, min(100.0, float(weight)))
    return clean


def read(path: Path) -> dict:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return empty()
    if not isinstance(raw, dict):
        return empty()
    return {
        "version": VERSION,
        "melodies": _weights(raw.get("melodies")),
        "events": _weights(raw.get("events")),
    }


def write(path: Path, document: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(
            json.dumps(document, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except OSError:
            pass


def set_weight(path: Path, kind: str, name: str, weight: float) -> float:
    if kind not in KINDS:
        raise ValueError(f"type de contenu inconnu : {kind}")
    name = str(name).strip().casefold()
    if not name:
        raise ValueError("le nom du contenu est vide")
    weight = max(0.0, min(100.0, float(weight)))
    document = read(path)
    if weight == 1.0:
        document[kind].pop(name, None)
    else:
        document[kind][name] = weight
    write(path, document)
    return weight


def weight(document: dict, kind: str, name: str) -> float:
    return float(document.get(kind, {}).get(name.casefold(), 1.0))


def choose(items, document: dict, kind: str, key, rng):
    """Tire un item avec poids ; renvoie None si tous sont desactives."""

    choices, weights = [], []
    for item in items:
        item_weight = weight(document, kind, key(item))
        if item_weight > 0:
            choices.append(item)
            weights.append(item_weight)
    if not choices:
        return None
    # random.Random et le module random possedent tous deux choices depuis 3.6.
    return rng.choices(choices, weights=weights, k=1)[0]
