"""Historique local borne des apparitions, au format JSON Lines."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


MAX_ENTRIES = 5000
ALLOWED = {
    "kind", "name", "count", "formation", "screen", "special", "voices",
    "source", "challenge", "pack",
}


def append(path: Path, kind: str, now: datetime | None = None, **details) -> dict:
    entry = {"at": (now or datetime.now()).isoformat(timespec="seconds"), "kind": str(kind)}
    for key, value in details.items():
        if key in ALLOWED and isinstance(value, (str, int, float, bool)):
            entry[key] = value
    path = Path(path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
        _trim(path)
    except OSError:
        pass
    return entry


def _trim(path: Path) -> None:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    if len(lines) <= MAX_ENTRIES:
        return
    path.write_text("\n".join(lines[-MAX_ENTRIES:]) + "\n", encoding="utf-8")


def read(path: Path, limit: int = 50) -> list[dict]:
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    entries = []
    for line in lines[-max(0, int(limit)):]:
        try:
            entry = json.loads(line)
        except (TypeError, ValueError):
            continue
        if isinstance(entry, dict) and isinstance(entry.get("kind"), str):
            entries.append(entry)
    return entries
