"""Fenêtres horaires, mise en sommeil et durees humaines."""

from __future__ import annotations

import re
from datetime import datetime, timedelta


_DURATION = re.compile(r"^(\d+)([mhd])$", re.IGNORECASE)


def minute(value: str) -> int:
    try:
        hour, minute_value = (int(part) for part in value.split(":"))
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError("heure attendue au format HH:MM") from exc
    if not 0 <= hour <= 23 or not 0 <= minute_value <= 59:
        raise ValueError("heure attendue au format HH:MM")
    return hour * 60 + minute_value


def window(value: str) -> tuple[int, int]:
    try:
        start, end = value.split("-", 1)
    except (AttributeError, ValueError) as exc:
        raise ValueError("plage attendue au format HH:MM-HH:MM") from exc
    return minute(start), minute(end)


def contains(value: str | None, now: datetime | None = None) -> bool:
    if not value:
        return False
    start, end = window(value)
    current = (now or datetime.now()).hour * 60 + (now or datetime.now()).minute
    if start == end:
        return True
    if start < end:
        return start <= current < end
    return current >= start or current < end


def duration(value: str, now: datetime | None = None) -> datetime:
    match = _DURATION.fullmatch(str(value).strip())
    if not match:
        raise ValueError("duree attendue : 30m, 2h ou 1d")
    amount = int(match.group(1))
    if amount <= 0:
        raise ValueError("la duree doit etre positive")
    unit = match.group(2).casefold()
    seconds = amount * {"m": 60, "h": 3600, "d": 86400}[unit]
    return (now or datetime.now()) + timedelta(seconds=seconds)


def snoozed(state: dict, now: datetime | None = None) -> bool:
    value = state.get("snooze_until")
    if not isinstance(value, str):
        return False
    try:
        until = datetime.fromisoformat(value)
    except ValueError:
        return False
    return (now or datetime.now()) < until
