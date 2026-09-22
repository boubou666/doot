"""Profils persistants des reglages de doot.

Le fichier reste du JSON lisible et ne contient que les options de comportement :
jamais une commande ponctuelle comme ``--update`` ou ``--stop``. Le module ne
connait pas argparse afin de rester testable sans lancer la CLI.
"""

from __future__ import annotations

import json
import os
from pathlib import Path


VERSION = 2

# Options dont le sens survit a un autre lancement. L'ordre sert aussi a
# produire une sortie stable avec ``doot --profiles``.
OPTIONS = (
    "min", "max", "burst_min", "burst_max", "burst_delay", "formation",
    "duration", "image", "no_image", "scale", "volume", "opacity",
    "font_size", "center", "no_slide", "no_melody", "melody_chance",
    "melody_pity", "slide_chance", "side", "slide_ms", "spin", "no_spin",
    "spin_chance", "spin_ms", "reverse", "no_reverse", "reverse_chance",
    "screen", "no_sound", "no_pan",
    "event_chance", "event_pity", "no_event", "contagion_chance",
    "no_contagion", "quiet", "quiet_hours", "reduce_motion", "no_flash",
    "high_contrast", "sound_limit",
)

_ENTIERS = {
    "min", "max", "burst_min", "burst_max", "font_size", "melody_pity",
    "slide_ms", "spin_ms", "event_pity",
}
_NOMBRES = {
    "burst_delay", "duration", "scale", "volume", "opacity",
    "melody_chance", "slide_chance", "spin_chance", "reverse_chance", "event_chance",
    "contagion_chance",
    "sound_limit",
}
_BOOLEENS = {
    "no_image", "center", "no_slide", "no_melody", "spin", "no_spin",
    "reverse", "no_reverse",
    "no_sound", "no_pan", "no_event", "no_contagion", "quiet",
    "reduce_motion", "no_flash", "high_contrast",
}
_TEXTES = {"image", "side", "screen", "quiet_hours"}
_FORMATIONS = {"random", "canon", "wave", "rain", "vortex", "duel"}


class ProfileError(ValueError):
    """Une operation explicite vise un profil inutilisable."""


def valid_name(name: str) -> bool:
    """Nom court, affichable et utilisable sans echappement particulier."""

    if not isinstance(name, str) or not 1 <= len(name) <= 40:
        return False
    compact = name.replace("-", "").replace("_", "")
    return bool(compact) and compact.isalnum()


def _clean_values(values) -> dict:
    if not isinstance(values, dict):
        return {}
    clean = {}
    for key in OPTIONS:
        if key not in values:
            continue
        value = values.get(key)
        if key in _ENTIERS and isinstance(value, int) and not isinstance(value, bool):
            clean[key] = value
        elif key in _NOMBRES and isinstance(value, (int, float)) \
                and not isinstance(value, bool):
            clean[key] = float(value) if isinstance(value, int) else value
        elif key in _BOOLEENS and isinstance(value, bool):
            clean[key] = value
        elif key in _TEXTES and (value is None or isinstance(value, str)):
            clean[key] = value
        elif key == "formation" and value in _FORMATIONS:
            clean[key] = value
    return clean


def empty() -> dict:
    return {"version": VERSION, "active": None, "profiles": {}, "schedules": []}


def _clean_schedules(raw, profile_names) -> list[dict]:
    from . import schedule

    clean = []
    if not isinstance(raw, list):
        return clean
    for item in raw:
        if not isinstance(item, dict) or item.get("profile") not in profile_names:
            continue
        value = item.get("window")
        try:
            schedule.window(value)
        except ValueError:
            continue
        days = item.get("days", list(range(7)))
        if not isinstance(days, list):
            continue
        days = sorted({day for day in days if isinstance(day, int) and 0 <= day <= 6})
        if days:
            clean.append({"profile": item["profile"], "window": value, "days": days})
    return clean


def read(path: Path) -> dict:
    """Lit et assainit le document ; un fichier abime n'empeche pas doot de partir."""

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return empty()
    if not isinstance(raw, dict):
        return empty()

    raw_profiles = raw.get("profiles")
    clean_profiles = {}
    if isinstance(raw_profiles, dict):
        for name, values in raw_profiles.items():
            if valid_name(name):
                clean_profiles[name] = _clean_values(values)

    active = raw.get("active")
    if active not in clean_profiles:
        active = None
    return {
        "version": VERSION,
        "active": active,
        "profiles": clean_profiles,
        "schedules": _clean_schedules(raw.get("schedules"), clean_profiles),
    }


def write(path: Path, document: dict) -> None:
    """Remplace atomiquement le fichier pour survivre a une extinction brutale."""

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
        except FileNotFoundError:
            pass


def names(path: Path) -> list[str]:
    return sorted(read(path)["profiles"], key=str.casefold)


def active(path: Path) -> str | None:
    return read(path)["active"]


def load(path: Path, name: str) -> dict:
    document = read(path)
    try:
        return dict(document["profiles"][name])
    except KeyError as exc:
        raise ProfileError(f"profil inconnu : {name}") from exc


def save(path: Path, name: str, values: dict) -> None:
    if not valid_name(name):
        raise ProfileError(
            "nom de profil invalide (1 a 40 lettres, chiffres, '-' ou '_')"
        )
    document = read(path)
    document["profiles"][name] = _clean_values(values)
    write(path, document)


def activate(path: Path, name: str | None) -> None:
    document = read(path)
    if name is not None and name not in document["profiles"]:
        raise ProfileError(f"profil inconnu : {name}")
    document["active"] = name
    write(path, document)


def delete(path: Path, name: str) -> None:
    document = read(path)
    if name not in document["profiles"]:
        raise ProfileError(f"profil inconnu : {name}")
    del document["profiles"][name]
    if document["active"] == name:
        document["active"] = None
    document["schedules"] = [
        item for item in document.get("schedules", []) if item.get("profile") != name
    ]
    write(path, document)


_DAY_NAMES = {
    "lun": 0, "mar": 1, "mer": 2, "jeu": 3, "ven": 4, "sam": 5, "dim": 6,
    "mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6,
}


def parse_days(value: str) -> list[int]:
    if not value or value.strip() in ("*", "tous", "all"):
        return list(range(7))
    days = []
    for token in value.casefold().split(","):
        token = token.strip()
        if token not in _DAY_NAMES:
            raise ProfileError(f"jour inconnu : {token}")
        days.append(_DAY_NAMES[token])
    return sorted(set(days))


def schedule_profile(path: Path, name: str, time_window: str, days: str = "*") -> None:
    from . import schedule

    document = read(path)
    if name not in document["profiles"]:
        raise ProfileError(f"profil inconnu : {name}")
    try:
        schedule.window(time_window)
    except ValueError as exc:
        raise ProfileError(str(exc)) from exc
    entry = {"profile": name, "window": time_window, "days": parse_days(days)}
    document["schedules"] = [
        item for item in document.get("schedules", []) if item.get("profile") != name
    ] + [entry]
    write(path, document)


def unschedule_profile(path: Path, name: str) -> None:
    document = read(path)
    before = len(document.get("schedules", []))
    document["schedules"] = [
        item for item in document.get("schedules", []) if item.get("profile") != name
    ]
    if len(document["schedules"]) == before:
        raise ProfileError(f"profil non planifie : {name}")
    write(path, document)


def scheduled(path: Path, now=None) -> str | None:
    from datetime import datetime
    from . import schedule

    now = now or datetime.now()
    for item in read(path).get("schedules", []):
        if now.weekday() in item["days"] and schedule.contains(item["window"], now):
            return item["profile"]
    return None


def from_namespace(args) -> dict:
    """Extrait seulement les reglages autorises d'un Namespace argparse."""

    return {key: getattr(args, key) for key in OPTIONS if hasattr(args, key)}
