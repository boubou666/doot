"""Rencontres rares precomposees a partir des formations de doot."""

from __future__ import annotations

import copy
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Evenement:
    identifiant: str
    titre: str
    description: str
    formation: str
    quantite: int
    delai: float
    duree: float
    mise_en_scene: str = "salve"
    # Une rencontre qui appartient a une date ne se tire pas au sort le reste
    # du temps. Le champ vit ici, avec la rencontre, et non dans le tirage.
    tirable: bool = True


CATALOGUE = (
    Evenement(
        "parade",
        "La parade des sans-chair",
        "Six squelettes traversent les ecrans en vague serree.",
        "wave",
        6,
        0.10,
        1.15,
    ),
    Evenement(
        "pluie",
        "Pluie d'os",
        "Sept trompettistes tombent du plafond numerique.",
        "rain",
        7,
        0.08,
        1.0,
    ),
    Evenement(
        "vortex",
        "Vortex infernal",
        "Cinq squelettes tournoient a travers les ecrans.",
        "vortex",
        5,
        0.10,
        1.2,
    ),
    Evenement(
        "duel",
        "Le duel des cuivres",
        "Deux camps se repondent d'un bord a l'autre de l'ecran.",
        "duel",
        6,
        0.16,
        0.85,
    ),
    Evenement(
        "finale",
        "La derniere nuit",
        "La crypte se vide d'un coup : douze trompettistes saluent la fermeture.",
        "vortex",
        12,
        0.07,
        1.5,
        tirable=False,
    ),
    Evenement(
        "mimic",
        "Le Mimic",
        "Une notification presque credible cache un squelette.",
        "random",
        1,
        0.0,
        2.8,
        "mimic",
    ),
    Evenement(
        "faux-bug",
        "Le faux bug",
        "Le squelette se coince au bord, tremble, puis tombe.",
        "random",
        1,
        0.0,
        3.8,
        "faux-bug",
    ),
)


def tirables() -> tuple:
    """Les rencontres que le hasard peut amener de lui-meme.

    La finale n'en est pas : elle appartient au soir du 31 octobre, et un
    tirage qui la sortirait un 12 septembre lui oterait tout son sens.
    """
    return tuple(item for item in CATALOGUE if item.tirable)


def _safe_name(name: str) -> str:
    value = re.sub(r"[^a-z0-9_-]+", "-", name.casefold()).strip("-_")
    if not value:
        raise ValueError("nom de rencontre invalide")
    return value[:64]


def custom(directory: Path) -> tuple[Evenement, ...]:
    """Charge les rencontres declaratives ; un fichier casse est simplement ignore."""

    found = []
    directory = Path(directory)
    if not directory.is_dir():
        return ()
    for path in sorted(directory.glob("*.json")):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            event = Evenement(
                _safe_name(str(raw.get("id") or path.stem)),
                str(raw["title"])[:80], str(raw["description"])[:240],
                str(raw["formation"]), int(raw["count"]), float(raw["delay"]),
                float(raw["duration"]), str(raw.get("staging", "salve")),
            )
        except Exception:
            continue
        if (event.formation in {"random", "canon", "wave", "rain", "vortex", "duel"}
                and event.mise_en_scene == "salve" and 1 <= event.quantite <= 32
                and 0 <= event.delai <= 30 and 0.2 <= event.duree <= 60):
            found.append(event)
    return tuple(found)


def all_events(directory: Path | None = None) -> tuple[Evenement, ...]:
    return CATALOGUE + (custom(directory) if directory is not None else ())


def find(name: str, directory: Path | None = None) -> Evenement | None:
    wanted = name.casefold()
    return next((event for event in all_events(directory) if event.identifiant == wanted), None)


def save(directory: Path, name: str, title: str, description: str, *, formation: str,
         count: int, delay: float, duration: float) -> Path:
    """Enregistre une rencontre sans code executable et sans ecraser l'existant."""

    identifier = _safe_name(name)
    if formation not in {"random", "canon", "wave", "rain", "vortex", "duel"}:
        raise ValueError("formation inconnue")
    if not 1 <= int(count) <= 32:
        raise ValueError("une rencontre contient entre 1 et 32 doots")
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / f"{identifier}.json"
    number = 2
    while destination.exists():
        destination = directory / f"{identifier}-{number}.json"
        number += 1
    document = {
        "format": "doot-event", "version": 1, "id": destination.stem,
        "title": str(title).strip()[:80] or identifier,
        "description": str(description).strip()[:240] or "Rencontre personnalisee.",
        "formation": formation, "count": int(count), "delay": float(delay),
        "duration": float(duration), "staging": "salve",
    }
    temporary = destination.with_name(f".{destination.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n",
                             encoding="utf-8")
        os.replace(temporary, destination)
    finally:
        try:
            temporary.unlink()
        except OSError:
            pass
    return destination


def configure(args, event: Evenement):
    """Copie les options puis applique la choregraphie, sans muter le daemon."""

    configured = copy.copy(args)
    configured.burst_min = event.quantite
    configured.burst_max = event.quantite
    configured.burst_delay = event.delai
    configured.duration = event.duree
    configured.formation = event.formation
    configured.mise_en_scene = event.mise_en_scene
    if event.mise_en_scene == "faux-bug":
        configured.side = "bottom"
        configured.no_slide = False
        configured.spin = False
        configured.slide_ms = 650
    return configured
