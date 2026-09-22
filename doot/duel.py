"""Classement saisonnier convergent des duels de doot."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


MAX_NAME = 32


@dataclass(frozen=True)
class Standing:
    machine: str
    name: str
    doots: int
    specials: int


def season_year(now: datetime | None = None) -> int:
    """Saison courante ou prochaine : apres octobre, celle de l'an prochain."""
    now = now or datetime.now()
    return now.year + 1 if now.month > 10 else now.year


def _clean_count(value) -> int:
    return max(0, value) if isinstance(value, int) and not isinstance(value, bool) else 0


def _clean_name(value) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.strip().split())[:MAX_NAME]


def _root(state: dict) -> dict:
    value = state.get("duel")
    if not isinstance(value, dict):
        value = {}
        state["duel"] = value
    return value


def set_name(state: dict, name: str) -> str:
    clean = _clean_name(name)
    if not clean:
        raise ValueError("le nom de duel ne peut pas etre vide")
    machine = state.get("machine")
    if not isinstance(machine, str) or not machine:
        raise ValueError("cette machine n'a pas encore d'identite")
    names = _root(state).get("names")
    names = dict(names) if isinstance(names, dict) else {}
    names[machine] = clean
    _root(state)["names"] = names
    return clean


def record(state: dict, doots: int, special: bool = False,
           now: datetime | None = None) -> None:
    machine = state.get("machine")
    if not isinstance(machine, str) or not machine:
        return
    doots = _clean_count(doots)
    if not doots:
        return
    year = str(season_year(now))
    root = _root(state)
    seasons = root.get("seasons")
    seasons = dict(seasons) if isinstance(seasons, dict) else {}
    board = seasons.get(year)
    board = dict(board) if isinstance(board, dict) else {}
    entry = board.get(machine)
    entry = dict(entry) if isinstance(entry, dict) else {}
    entry["doots"] = _clean_count(entry.get("doots")) + doots
    entry["specials"] = _clean_count(entry.get("specials")) + int(bool(special))
    board[machine] = entry
    seasons[year] = board
    root["seasons"] = seasons


def export(state: dict) -> dict:
    """Copie assainie partageable, sans objets ni valeurs hors bornes."""
    source = state.get("duel")
    if not isinstance(source, dict):
        return {}
    names = source.get("names")
    clean_names = {
        str(machine): _clean_name(name)
        for machine, name in (names.items() if isinstance(names, dict) else ())
        if _clean_name(name)
    }
    clean_seasons = {}
    seasons = source.get("seasons")
    for year, board in (seasons.items() if isinstance(seasons, dict) else ()):
        if not str(year).isdigit() or not isinstance(board, dict):
            continue
        clean_board = {}
        for machine, entry in board.items():
            if not isinstance(entry, dict):
                continue
            clean_board[str(machine)] = {
                "doots": _clean_count(entry.get("doots")),
                "specials": _clean_count(entry.get("specials")),
            }
        if clean_board:
            clean_seasons[str(year)] = clean_board
    result = {}
    if clean_names:
        result["names"] = clean_names
    if clean_seasons:
        result["seasons"] = clean_seasons
    return result


def merge(local: dict, remote: dict) -> None:
    """Maximum par compteur : rejouer une synchronisation ne double rien."""
    other = export(remote)
    if not other:
        return
    here = export(local)
    names = dict(here.get("names", {}))
    names.update(other.get("names", {}))
    seasons = dict(here.get("seasons", {}))
    for year, board in other.get("seasons", {}).items():
        combined = dict(seasons.get(year, {}))
        for machine, entry in board.items():
            current = combined.get(machine, {})
            combined[machine] = {
                "doots": max(_clean_count(current.get("doots")), entry["doots"]),
                "specials": max(
                    _clean_count(current.get("specials")), entry["specials"]
                ),
            }
        seasons[year] = combined
    local["duel"] = {"names": names, "seasons": seasons}


def standings(state: dict, year: int | None = None) -> list[Standing]:
    clean = export(state)
    year = season_year() if year is None else int(year)
    board = clean.get("seasons", {}).get(str(year), {})
    names = clean.get("names", {})
    result = [
        Standing(
            machine=machine,
            name=names.get(machine) or f"skelly-{machine[:6]}",
            doots=entry["doots"],
            specials=entry["specials"],
        )
        for machine, entry in board.items()
    ]
    return sorted(result, key=lambda item: (-item.doots, -item.specials, item.name.casefold()))
