"""Rituels quotidiens declaratifs, executes une seule fois par jour."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path


_TIME = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")


def read(path: Path) -> list[dict]:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(raw, list):
        return []
    clean = []
    for item in raw:
        if (isinstance(item, dict) and isinstance(item.get("name"), str)
                and _TIME.fullmatch(str(item.get("at", "")))):
            clean.append({
                "name": item["name"][:40], "at": item["at"],
                "action": item.get("action", "doot") if item.get("action") in ("doot", "melody") else "doot",
                "value": str(item.get("value", ""))[:80],
                "last_run": str(item.get("last_run", ""))[:10],
            })
    return sorted(clean, key=lambda item: (item["at"], item["name"].casefold()))


def write(path: Path, entries: list[dict]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except OSError:
            pass


def add(path: Path, name: str, at: str, action: str = "doot", value: str = "") -> dict:
    name = str(name).strip()
    if not name or len(name) > 40:
        raise ValueError("le nom du rituel doit compter de 1 a 40 caracteres")
    if not _TIME.fullmatch(str(at)):
        raise ValueError("heure attendue au format HH:MM")
    if action not in ("doot", "melody"):
        raise ValueError("action attendue : doot ou melody")
    entries = [item for item in read(path) if item["name"].casefold() != name.casefold()]
    entry = {"name": name, "at": at, "action": action, "value": str(value)[:80], "last_run": ""}
    write(path, entries + [entry])
    return entry


def delete(path: Path, name: str) -> bool:
    entries = read(path)
    kept = [item for item in entries if item["name"].casefold() != str(name).casefold()]
    if len(kept) == len(entries):
        return False
    write(path, kept)
    return True


def due(path: Path, now: datetime | None = None) -> list[dict]:
    now = now or datetime.now()
    entries = read(path)
    today, current = now.date().isoformat(), now.strftime("%H:%M")
    result = [item for item in entries if item["at"] <= current and item["last_run"] != today]
    if result:
        names = {item["name"] for item in result}
        for item in entries:
            if item["name"] in names:
                item["last_run"] = today
        write(path, entries)
    return result
