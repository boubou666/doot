"""Defi quotidien deterministe et progression locale."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, datetime, timedelta


@dataclass(frozen=True)
class Challenge:
    identifiant: str
    title: str
    kind: str
    target: int
    formation: str = ""


def daily(day: date | None = None) -> Challenge:
    day = day or date.today()
    seed = int(hashlib.sha256(day.isoformat().encode("ascii")).hexdigest()[:8], 16)
    choices = (
        Challenge("souffle-5", "Faire surgir 5 squelettes", "doots", 5),
        Challenge("melodie-1", "Jouer une melodie", "melodie", 1),
        Challenge("rencontre-1", "Assister a une rencontre rare", "event", 1),
        Challenge("canon-4", "Jouer 4 doots en canon", "formation", 1, "canon"),
        Challenge("pluie-4", "Faire pleuvoir au moins 4 doots", "formation", 1, "rain"),
        Challenge("vortex-4", "Faire tournoyer au moins 4 doots", "formation", 1, "vortex"),
    )
    return choices[seed % len(choices)]


def status(state: dict, now: datetime | None = None) -> dict:
    now = now or datetime.now()
    challenge = daily(now.date())
    root = state.setdefault("daily_challenge", {})
    if root.get("day") != now.date().isoformat() or root.get("id") != challenge.identifiant:
        root.clear()
        root.update({"day": now.date().isoformat(), "id": challenge.identifiant,
                     "progress": 0, "completed": False})
    return root


def record(state: dict, kind: str, amount: int = 1, formation: str = "",
           now: datetime | None = None) -> bool:
    now = now or datetime.now()
    challenge = daily(now.date())
    root = status(state, now)
    if root.get("completed"):
        return False
    matches = challenge.kind == kind
    if challenge.kind == "formation":
        matches = kind == "formation" and formation == challenge.formation
    if not matches:
        return False
    root["progress"] = min(challenge.target, int(root.get("progress", 0)) + max(0, amount))
    if root["progress"] < challenge.target:
        return False
    root["completed"] = True
    days = state.setdefault("challenge_days", [])
    today = now.date().isoformat()
    if today not in days:
        days.append(today)
        days.sort()
    state["challenge_streak"] = streak(days, now.date())
    return True


def streak(days, today: date | None = None) -> int:
    valid = set()
    for value in days if isinstance(days, list) else []:
        try:
            valid.add(date.fromisoformat(value))
        except (TypeError, ValueError):
            pass
    cursor = today or date.today()
    total = 0
    while cursor in valid:
        total += 1
        cursor -= timedelta(days=1)
    return total
