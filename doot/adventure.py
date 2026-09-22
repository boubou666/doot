"""Campagne, boss, combos et secrets de la seconde vague de Doot.

Le module ne fait ni affichage ni audio.  Il transforme ``state.json`` afin
que la CLI, les interfaces graphiques et une future synchronisation partagent
exactement les memes regles.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Chapter:
    identifiant: str
    titre: str
    texte: str
    choix: tuple[tuple[str, str], ...]


CHAPTERS = (
    Chapter(
        "appel", "I. L'appel sous la dalle",
        "Une trompette repond sous la crypte. Trois symboles brillent dans la poussiere.",
        (("ecouter", "Ecouter la note"), ("frapper", "Frapper la dalle")),
    ),
    Chapter(
        "procession", "II. La procession sans ombre",
        "Des squelettes attendent un chef d'orchestre devant une porte sans serrure.",
        (("dooter", "Donner le doot de depart"), ("danser", "Mener la danse")),
    ),
    Chapter(
        "ossuaire", "III. La clef d'ossuaire",
        "La porte reconnait les choix passes. Derriere elle, quelque chose compte les temps.",
        (("ouvrir", "Tourner la clef invisible"), ("sonner", "Sonner huit coups")),
    ),
)


@dataclass(frozen=True)
class Personality:
    identifiant: str
    nom: str
    replique: str
    formation: str
    transpose: int


PERSONALITIES = (
    Personality("maestro", "Maestro Clavicule", "Une, deux... et DOOT !", "canon", 0),
    Personality("punk", "Johnny Rotule", "Plus fort, les vivants !", "duel", -5),
    Personality("oracle", "Madame Omoplate", "J'entends deja le prochain refrain.", "vortex", 7),
    Personality("jazz", "Miles Dootvis", "Le silence aussi swingue.", "wave", -2),
)


@dataclass(frozen=True)
class Riddle:
    identifiant: str
    titre: str
    indices: tuple[str, ...]


RIDDLES = (
    Riddle("douzieme_coup", "Le douzieme coup", (
        "Le cadran doit perdre ses deux aiguilles.",
        "Cherche le tout debut d'une nouvelle nuit.",
        "Fais un doot entre 00:00 et 00:00:59.",
    )),
    Riddle("miroir_funebre", "Le miroir funebre", (
        "Deux adversaires se ressemblent sans regarder dans le meme sens.",
        "Le duel doit remonter le temps.",
        "Joue au moins deux doots en formation duel avec --reverse.",
    )),
    Riddle("clef_ossuaire", "La clef d'ossuaire", (
        "La crypte se souvient de trois verbes.",
        "Ecoute, joue, puis franchis.",
        "Dans la campagne : ecouter, dooter, ouvrir.",
    )),
    Riddle("huitieme_voix", "La huitieme voix", (
        "Un choeur incomplet garde toujours une place vide.",
        "Le compositeur accepte autant de voix que l'araignee a de pattes.",
        "Joue une melodie RTTTL a huit voix.",
    )),
)


def _adventure(state: dict) -> dict:
    value = state.get("adventure")
    if not isinstance(value, dict):
        value = {}
        state["adventure"] = value
    return value


def campaign_status(state: dict) -> dict:
    data = _adventure(state)
    index = data.get("chapter", 0)
    if isinstance(index, bool) or not isinstance(index, int):
        index = 0
    index = max(0, min(len(CHAPTERS), index))
    path = data.get("path", [])
    if not isinstance(path, list):
        path = []
    return {
        "chapter": CHAPTERS[index] if index < len(CHAPTERS) else None,
        "index": index,
        "total": len(CHAPTERS),
        "path": [item for item in path if isinstance(item, str)],
        "completed": index >= len(CHAPTERS),
    }


def choose(state: dict, choice: str) -> dict:
    status = campaign_status(state)
    chapter = status["chapter"]
    if chapter is None:
        raise ValueError("la campagne est deja terminee")
    choice = str(choice).strip().casefold()
    valid = {key for key, _label in chapter.choix}
    if choice not in valid:
        raise ValueError("choix inconnu : " + choice)
    data = _adventure(state)
    data["path"] = status["path"] + [choice]
    data["chapter"] = status["index"] + 1
    if data["chapter"] >= len(CHAPTERS):
        data["completed_at"] = datetime.now().isoformat(timespec="seconds")
    return campaign_status(state)


def seasonal_boss(state: dict, year: int | None = None) -> dict:
    year = int(year or datetime.now().year)
    data = _adventure(state)
    bosses = data.get("bosses")
    if not isinstance(bosses, dict):
        bosses = {}
        data["bosses"] = bosses
    boss = bosses.get(str(year))
    maximum = 120 + (year % 7) * 10
    if not isinstance(boss, dict):
        boss = {"name": f"Le Tibia-Titan {year}", "hp": maximum, "max_hp": maximum,
                "defeated": False}
        bosses[str(year)] = boss
    hp = boss.get("hp", maximum)
    boss["hp"] = max(0, min(maximum, hp if isinstance(hp, int) else maximum))
    boss["max_hp"] = maximum
    boss["defeated"] = boss["hp"] == 0
    return dict(boss)


def hit_boss(state: dict, damage: int, year: int | None = None) -> dict:
    if isinstance(damage, bool) or not isinstance(damage, int) or damage < 1:
        raise ValueError("les degats doivent etre un entier positif")
    year = int(year or datetime.now().year)
    boss = seasonal_boss(state, year)
    boss["hp"] = max(0, boss["hp"] - min(50, damage))
    boss["defeated"] = boss["hp"] == 0
    _adventure(state)["bosses"][str(year)] = boss
    return dict(boss)


def record_combo(state: dict, event: str, now: datetime | None = None) -> dict:
    """Enchaine les actions faites a moins de huit secondes d'intervalle."""

    now = now or datetime.now()
    data = _adventure(state)
    combo = data.get("combo")
    if not isinstance(combo, dict):
        combo = {}
    previous = combo.get("at")
    try:
        elapsed = (now - datetime.fromisoformat(previous)).total_seconds()
    except (TypeError, ValueError):
        elapsed = 999
    count = int(combo.get("count", 0)) + 1 if 0 <= elapsed <= 8 else 1
    best = max(int(combo.get("best", 0)), count)
    combo = {"count": count, "best": best, "event": str(event),
             "at": now.isoformat(timespec="seconds"), "multiplier": 1 + min(4, count // 3)}
    data["combo"] = combo
    return dict(combo)


def combo_status(state: dict) -> dict:
    combo = _adventure(state).get("combo", {})
    return dict(combo) if isinstance(combo, dict) else {}


def set_personality(state: dict, wanted: str) -> Personality:
    wanted = str(wanted).casefold()
    for item in PERSONALITIES:
        if item.identifiant == wanted:
            _adventure(state)["personality"] = wanted
            return item
    raise ValueError(f"squelette inconnu : {wanted}")


def active_personality(state: dict) -> Personality:
    wanted = _adventure(state).get("personality", PERSONALITIES[0].identifiant)
    return next((item for item in PERSONALITIES if item.identifiant == wanted), PERSONALITIES[0])


def selected_personality(state: dict) -> Personality | None:
    """La personnalite explicitement choisie, sans imposer un defaut au legacy."""

    data = state.get("adventure")
    wanted = data.get("personality") if isinstance(data, dict) else None
    return next((item for item in PERSONALITIES if item.identifiant == wanted), None)


def create_music_duel(state: dict, motif: str, opponent: str = "la crypte") -> dict:
    motif = ",".join(part.strip().casefold() for part in str(motif).split(",") if part.strip())
    if not motif or len(motif) > 160:
        raise ValueError("donne un motif RTTTL court, par exemple c,d,e,g")
    # Validation par le parseur officiel, sans imposer de fichier.
    from . import melodie
    melodie.parse(f"duel:d=8,o=5,b=120:{motif}")
    data = _adventure(state)
    duels = data.get("music_duels")
    if not isinstance(duels, list):
        duels = []
    entry = {
        "id": f"duel-{len(duels) + 1}", "motif": motif,
        "opponent": str(opponent).strip()[:40] or "la crypte",
        "created_at": datetime.now().isoformat(timespec="seconds"), "status": "open",
    }
    data["music_duels"] = (duels + [entry])[-20:]
    return dict(entry)


def music_duels(state: dict) -> list[dict]:
    value = _adventure(state).get("music_duels", [])
    return [dict(item) for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def observe_riddles(state: dict, event: str, now: datetime | None = None, **details) -> list[str]:
    """Renvoie les enigmes nouvellement resolues par une action reelle."""

    now = now or datetime.now()
    solved = state.get("riddles_solved")
    if not isinstance(solved, list):
        solved = []
        state["riddles_solved"] = solved
    candidates = []
    if event == "doots" and now.hour == 0 and now.minute == 0:
        candidates.append("douzieme_coup")
    if (event == "doots" and details.get("formation") == "duel"
            and details.get("reverse") is True and int(details.get("quantite", 0)) >= 2):
        candidates.append("miroir_funebre")
    if event == "campagne" and campaign_status(state)["path"] == ["ecouter", "dooter", "ouvrir"]:
        candidates.append("clef_ossuaire")
    if event == "melodie" and int(details.get("voix", 1)) >= 8:
        candidates.append("huitieme_voix")
    fresh = [item for item in candidates if item not in solved]
    solved.extend(fresh)
    return fresh


def riddle_status(state: dict) -> list[dict]:
    solved = state.get("riddles_solved", [])
    solved = solved if isinstance(solved, list) else []
    attempts = sum((
        int(campaign_status(state)["index"]),
        int(bool(combo_status(state))),
        len(music_duels(state)),
    ))
    level = min(2, attempts // 2)
    return [
        {
            "id": item.identifiant,
            "solved": item.identifiant in solved,
            "title": item.titre if item.identifiant in solved else "Succes secret",
            "hint": item.indices[2 if item.identifiant in solved else level],
            "hint_level": 3 if item.identifiant in solved else level + 1,
        }
        for item in RIDDLES
    ]


def museum(state: dict) -> dict:
    stats = state.get("stats", {})
    events = stats.get("evenements_vus", []) if isinstance(stats, dict) else []
    years = []
    for value in (stats.get("jours_actifs", []) if isinstance(stats, dict) else []):
        try:
            years.append(int(str(value)[:4]))
        except ValueError:
            pass
    bosses = _adventure(state).get("bosses", {})
    defeated = [year for year, item in bosses.items()
                if isinstance(item, dict) and item.get("defeated")] if isinstance(bosses, dict) else []
    return {
        "seasons": sorted(set(years)),
        "events": sorted(item for item in events if isinstance(item, str)),
        "bosses": sorted(defeated),
        "campaign_completed": campaign_status(state)["completed"],
        "riddles": sum(1 for item in riddle_status(state) if item["solved"]),
    }
