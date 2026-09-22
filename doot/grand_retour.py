"""La Nuit du Grand Retour : sept scenes, consequences et epilogue local.

Le journal reste dans state.json. Lire son etat ne lance aucune scene et ne
modifie aucun autre mode de jeu ; les acquis voisins ouvrent seulement des
options supplementaires au moment du choix.
"""

from __future__ import annotations

import html
import os
from pathlib import Path


NIGHTS = (
    {
        "title": "Le quai des derniers",
        "scene": "Le Dernier Train ramene une foule qui n'a jamais eu de billet.",
        "source": "train",
        "options": {
            "proteger": ("Abriter les passagers", 1, 1, 0, True, ""),
            "forcer": ("Forcer le depart", -1, 0, 2, False, ""),
            "guider": ("Guider la foule par une ligne connue", 1, 2, 0, True, "train"),
        },
    },
    {
        "title": "Le wagon des voix",
        "scene": "L'equipage entend une voix familiere derriere une porte condamnee.",
        "source": "crew",
        "options": {
            "ecouter": ("Ecouter la voix", 2, 1, 0, True, ""),
            "ordonner": ("Ordonner le silence", -2, 0, 2, False, ""),
            "confier": ("Confier la clef a l'equipage", 2, 1, 0, True, "crew"),
        },
    },
    {
        "title": "La cite ouverte",
        "scene": "La Cite des Os doit choisir qui franchira ses portes.",
        "source": "city",
        "options": {
            "accueillir": ("Accueillir les inconnus", 1, 1, 0, True, ""),
            "barricader": ("Barricader la cite", -1, -1, 2, False, ""),
            "mobiliser": ("Mobiliser les batiments de la cite", 1, 1, 1, True, "city"),
        },
    },
    {
        "title": "Le banquet des maisons",
        "scene": "Les maisons funeraires demandent a qui appartient la nuit.",
        "source": "house",
        "options": {
            "partager": ("Partager le banquet", 1, 1, 0, True, ""),
            "marchander": ("Marchander les noms", -1, 0, 2, False, ""),
            "invoquer": ("Invoquer le serment d'une maison", 1, 2, 0, True, "house"),
        },
    },
    {
        "title": "Le visage de la Nemesis",
        "scene": "La Nemesis montre la cicatrice d'une bataille oubliee.",
        "source": "nemesis",
        "options": {
            "pardonner": ("Laisser parler le rival", 1, 1, 0, True, ""),
            "frapper": ("Frapper avant la confession", -1, -1, 2, False, ""),
            "nommer": ("Nommer sa cicatrice", 1, 1, 1, True, "nemesis"),
        },
    },
    {
        "title": "Le contrechant",
        "scene": "Une note fausse se glisse entre deux mesures du monde.",
        "source": "music",
        "options": {
            "harmoniser": ("Accorder les voix", 1, 1, 0, True, ""),
            "couvrir": ("Couvrir la note fausse", -1, 0, 2, False, ""),
            "repondre": ("Reprendre le motif d'un duel gagne", 1, 2, 0, True, "music"),
        },
    },
    {
        "title": "La porte du retour",
        "scene": "La foule attend. L'equipage sait enfin ce que couterait l'aube.",
        "source": "finale",
        "options": {
            "ouvrir": ("Ouvrir la porte", 1, 1, 0, True, ""),
            "garder": ("Garder la veille", 0, 0, 1, False, ""),
            "briser": ("Briser la porte", -2, -1, 2, False, ""),
        },
    },
)

CLUES = (
    "La lanterne brille avant que le train ne s'arrete.",
    "La voix de l'equipage ne prononce aucun nom.",
    "La cite ouvre ses portes vers l'est.",
    "Une maison sert le pain avant le soleil.",
    "La cicatrice de la Nemesis dessine un horizon.",
    "La derniere note se tient entre nuit et jour.",
    "La porte laisse passer la lumiere sans laisser entrer le soleil.",
)

ENDINGS = {
    "aube": "La foule retrouve une aube. L'equipage reste a tes cotes.",
    "veille": "Tu gardes la porte. La ville dort encore une nuit.",
    "cendres": "La porte cede. Des cendres tombent sur la ville.",
}
SECRET_EPILOGUE = (
    "Derriere l'aube visible, une seconde porte s'ouvre. Les disparus "
    "choisissent leurs propres noms et le train repart sans conducteur."
)


def _root(state: dict) -> dict:
    value = state.get("grand_retour")
    if not isinstance(value, dict):
        value = {}
        state["grand_retour"] = value
    return value


def _read_root(state: dict) -> dict:
    value = state.get("grand_retour")
    return value if isinstance(value, dict) else {}


def _int(value, default: int = 0) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else default


def _signals(state: dict) -> dict:
    fourth = state.get("wave4")
    fourth = fourth if isinstance(fourth, dict) else {}
    sixth = state.get("wave6")
    sixth = sixth if isinstance(sixth, dict) else {}
    routes = sixth.get("completed_routes")
    crew = sixth.get("crew")
    city = fourth.get("city")
    house = sixth.get("house")
    nemesis = fourth.get("nemesis")
    buildings = city.get("buildings") if isinstance(city, dict) else {}
    return {
        "train": isinstance(routes, list) and bool(routes),
        "crew": isinstance(crew, list) and len(crew) >= 2,
        "city": isinstance(buildings, dict) and any(
            _int(level) >= 1 for level in buildings.values()
        ),
        "house": isinstance(house, dict) and bool(house.get("id"))
                 and _int(house.get("reputation")) >= 1,
        "nemesis": isinstance(nemesis, dict) and bool(nemesis.get("scars")),
        "music": isinstance(sixth.get("battle"), dict)
                 and bool(sixth["battle"].get("won")),
    }


def _current(root: dict) -> dict | None:
    run = root.get("run")
    return run if isinstance(run, dict) else None


def status(state: dict) -> dict:
    root = _read_root(state)
    run = _current(root)
    endings = root.get("endings")
    endings = [name for name in endings if name in ENDINGS] if isinstance(endings, list) else []
    if run is None:
        return {"started": False, "completed": False, "night": 0, "total": 7,
                "endings": sorted(set(endings)), "secret": bool(root.get("secret")),
                "secret_this_run": False}
    night = max(1, min(7, _int(run.get("night"), 1)))
    completed = bool(run.get("completed"))
    scene = NIGHTS[night - 1]
    signals = _signals(state)
    history = run.get("history")
    history = history if isinstance(history, list) else []
    scene_text = scene["scene"]
    if history and not completed:
        trust = _int(run.get("trust"))
        hope = _int(run.get("hope"))
        scene_text += (
            " L'equipage te suit sans hesiter." if trust >= 4 else
            " L'equipage murmure qu'il pourrait te quitter." if trust <= -2 else
            " L'equipage attend ton prochain geste."
        )
        scene_text += (" La foule apercoit deja la lumiere." if hope >= 3 else
                       " La foule avance encore dans l'ombre.")
        if run.get("betrayed"):
            scene_text += " Un membre de l'equipage a livre la clef a la Nemesis."
    options = [
        {"id": key, "text": spec[0], "available": not spec[5] or signals[spec[5]],
         "requires": spec[5]}
        for key, spec in scene["options"].items()
    ] if not completed else []
    clues = run.get("clues")
    clues = sorted({clue for clue in clues if isinstance(clue, int) and 1 <= clue <= 7}) if isinstance(clues, list) else []
    return {
        "started": True, "completed": completed, "night": night, "total": 7,
        "title": scene["title"], "scene": scene_text, "options": options,
        "trust": _int(run.get("trust")), "hope": _int(run.get("hope")),
        "resolve": _int(run.get("resolve")), "companion": run.get("companion", "incertain"),
        "betrayed": bool(run.get("betrayed")),
        "history": [
            {"night": _int(entry.get("night")), "text": str(entry.get("text", ""))[:160]}
            for entry in history if isinstance(entry, dict)
        ][:7],
        "clues": clues, "ending": run.get("ending", "") if completed else "",
        "endings": sorted(set(endings)), "secret": bool(root.get("secret")),
        "secret_this_run": bool(run.get("secret_epilogue")),
    }


def start(state: dict, *, restart: bool = False) -> dict:
    root = _root(state)
    run = _current(root)
    if run is not None and not run.get("completed") and not restart:
        return status(state)
    if run is not None and run.get("completed") and not restart:
        return status(state)
    if restart and run is not None and not run.get("completed"):
        raise ValueError("termine d'abord les sept nuits avant de recommencer")
    root["run"] = {
        "night": 1, "trust": 0, "hope": 0, "resolve": 0,
        "companion": "incertain", "history": [], "clues": [],
        "completed": False, "ending": "", "betrayed": False,
        "secret_epilogue": False,
    }
    return status(state)


def choose(state: dict, action: str) -> dict:
    run = _current(_read_root(state))
    if run is None:
        raise ValueError("commence la campagne avec --grand-retour")
    if run.get("completed"):
        raise ValueError("la campagne est terminee ; utilise --grand-retour-restart")
    night = _int(run.get("night"), 1)
    if not 1 <= night <= 7:
        raise ValueError("la nuit courante est illisible")
    scene = NIGHTS[night - 1]
    key = str(action).strip().casefold()
    if key not in scene["options"]:
        raise ValueError("choix attendu : " + ", ".join(scene["options"]))
    text, trust, hope, resolve, clue, requirement = scene["options"][key]
    if requirement and not _signals(state)[requirement]:
        raise ValueError("ce choix demande un acquis dans : " + requirement)
    run["trust"] = max(-7, min(14, _int(run.get("trust")) + trust))
    run["hope"] = max(-7, min(14, _int(run.get("hope")) + hope))
    run["resolve"] = max(0, min(14, _int(run.get("resolve")) + resolve))
    run["companion"] = ("fidele" if run["trust"] >= 4 else
                        "en rupture" if run["trust"] <= -2 else "incertain")
    if night >= 5 and run["trust"] <= -2:
        run["betrayed"] = True
    if run.get("betrayed"):
        run["companion"] = "traitre"
    if not isinstance(run.get("history"), list):
        run["history"] = []
    run["history"].append({
        "night": night, "title": scene["title"], "choice": key,
        "text": text, "echo": "L'equipage se souvient de ce geste.",
    })
    if clue:
        clues = run.get("clues")
        if not isinstance(clues, list):
            clues = []
            run["clues"] = clues
        if night not in clues:
            clues.append(night)
    if night < 7:
        run["night"] = night + 1
    else:
        if key == "garder":
            ending = "veille"
        elif (key == "ouvrir" and not run["betrayed"]
              and run["hope"] >= 4 and run["trust"] >= 3):
            ending = "aube"
        else:
            ending = "cendres"
        run["completed"] = True
        run["ending"] = ending
        endings = _root(state).get("endings")
        if not isinstance(endings, list):
            endings = []
            _root(state)["endings"] = endings
        if ending not in endings:
            endings.append(ending)
    return status(state)


def secret_status(state: dict) -> dict:
    current = status(state)
    clues = current.get("clues", [])
    ready = (current.get("completed") and current.get("ending") == "aube"
             and current.get("companion") == "fidele" and len(clues) == 7)
    return {
        "clues": [{"night": index, "found": index in clues,
                   "hint": CLUES[index - 1] if index in clues else "Un souvenir manque."}
                  for index in range(1, 8)],
        "ready": bool(ready), "solved": current["secret"],
        "riddle": ("Je nais quand la nuit recule, avant que le soleil n'arrive. "
                   "Qui suis-je ?") if ready else "",
        "epilogue": SECRET_EPILOGUE if current["secret"] else "",
    }


def solve_secret(state: dict, answer: str) -> dict:
    current = secret_status(state)
    if current["solved"]:
        return current
    if not current["ready"]:
        raise ValueError("reunis les sept souvenirs, une aube et un equipage fidele")
    if str(answer).strip().casefold() not in ("aube", "l'aube"):
        raise ValueError("la porte ne reconnait pas cette reponse")
    _root(state)["secret"] = True
    _root(state)["run"]["secret_epilogue"] = True
    return secret_status(state)


def journal_lines(state: dict) -> list[str]:
    item = status(state)
    if not item["started"]:
        return ["La Nuit du Grand Retour n'a pas commence.",
                "Lance : doot --grand-retour"]
    lines = [f"NUIT {item['night']}/7 — {item['title']}",
             item["scene"],
             f"Confiance {item['trust']} · Espoir {item['hope']} · Volonte {item['resolve']}",
             f"Equipage : {item['companion']}"]
    if item["betrayed"]:
        lines.append("Trahison : une clef a ete livree a la Nemesis.")
    if item["completed"]:
        lines.extend([f"FIN : {item['ending'].upper()}",
                      ENDINGS.get(item["ending"], ""),
                      "Fins decouvertes : " + ", ".join(item["endings"]),
                      "Rejouer : doot --grand-retour-restart"])
        if item["secret_this_run"]:
            lines.append("FIN SECRETE — L'AUBE INVISIBLE")
            lines.append(SECRET_EPILOGUE)
    else:
        lines.append("CHOIX")
        for option in item["options"]:
            suffix = f" [demande {option['requires']}]" if not option["available"] else ""
            lines.append(f"  {option['id']} : {option['text']}{suffix}")
        lines.append("Choisir : doot --grand-retour-choose MOT")
    lines.append("JOURNAL")
    for entry in item["history"]:
        lines.append(f"  Nuit {entry['night']} : {entry['text']}")
    lines.append(f"Souvenirs secrets : {len(item['clues'])}/7")
    return lines


def export_journal(state: dict, destination: Path) -> Path:
    path = Path(destination)
    lines = journal_lines(state)
    body = "".join("<p>" + html.escape(line) + "</p>" for line in lines)
    page = (
        "<!doctype html><html lang='fr'><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>Le Grand Retour</title><style>"
        "body{max-width:52rem;margin:2rem auto;padding:0 1rem;background:#100c18;"
        "color:#f0e8db;font:1.1rem/1.6 Georgia,serif}"
        "p{padding:.2rem .6rem;border-left:2px solid #a88b56}"
        "@media(prefers-reduced-motion:reduce){*,*:before,*:after{"
        "animation-duration:.01ms!important;transition-duration:.01ms!important}}"
        "</style><h1>La Nuit du Grand Retour</h1>" + body + "</html>"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(page, encoding="utf-8")
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except OSError:
            pass
    return path
