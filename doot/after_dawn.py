"""Consequences locales du Grand Retour, missions et Huitieme Porte.

Les lectures n'ecrivent jamais dans l'etat. Chaque decision est unique par fin ;
une campagne rejouee conserve les traces des fins precedentes.
"""

from __future__ import annotations

from . import grand_retour


FRONTS = {
    "apparitions": ("Les revenants demandent une place dans la ville.",
                    {"accueillir": "Leur donner un nom et une place.",
                     "eloigner": "Les raccompagner au seuil."}),
    "cite": ("La Cite des Os reconstruit ses murs apres la nuit.",
             {"rebatir": "Rebatir les maisons ouvertes.",
              "fortifier": "Fortifier les anciennes portes."}),
    "rail": ("Le Dernier Train cherche une nouvelle voie.",
             {"charbon": "Charger du charbon bleu.",
              "blindage": "Renforcer ses wagons."}),
    "nemesis": ("La Nemesis porte encore la marque du retour.",
                {"apaiser": "Lui offrir une treve.",
                 "defier": "L'appeler a un nouveau duel."}),
}
SCENES = {
    "aube": "La lumiere revele ce que chacun a perdu et retrouve.",
    "veille": "La ville attend sous une garde qui ne dort jamais.",
    "cendres": "La poussiere rend chaque promesse plus difficile.",
}
FRONT_SCENES = {
    "aube": {
        "apparitions": "Sous le soleil neuf, les revenants demandent un nom civil.",
        "cite": "La Cite ouvre des quartiers aux vivants et aux morts.",
        "rail": "Le Train traverse un horizon qu'aucune carte ne portait.",
        "nemesis": "La Nemesis contemple une cicatrice enfin visible.",
    },
    "veille": {
        "apparitions": "Les revenants attendent devant la porte gardee.",
        "cite": "La Cite doit nourrir ceux qui montent la garde.",
        "rail": "Le Train tourne autour d'une nuit qui refuse de finir.",
        "nemesis": "La Nemesis surveille la meme porte que toi.",
    },
    "cendres": {
        "apparitions": "Des silhouettes sortent de la poussiere de la porte brisee.",
        "cite": "La Cite rebâtit ses murs parmi les cendres.",
        "rail": "Le Train tire ses wagons hors des ruines.",
        "nemesis": "La Nemesis revient sur le terrain du desastre.",
    },
}
CREW = {
    "controleuse": "Mina Sans-Billet", "mecanicien": "Gaston Braise",
    "cantatrice": "Alma Sourdine", "bagagiste": "Porter Cranes",
    "chef": "Octave Minuit",
}
MISSIONS = {
    "controleuse": "Un billet sans nom attend son proprietaire.",
    "mecanicien": "Le foyer du train garde une flamme trop ancienne.",
    "cantatrice": "Une voix disparue repond au contrechant.",
    "bagagiste": "Une malle scellee contient les noms des absents.",
    "chef": "La table du dernier wagon a six couverts.",
}
DOOR_EPILOGUE = (
    "La Huitieme Porte ne ramene personne : elle laisse chacun choisir "
    "ce qu'il emporte. Le train repart, libre de ses trois fins."
)


def _read(state: dict) -> dict:
    value = state.get("after_dawn")
    return value if isinstance(value, dict) else {}


def _root(state: dict) -> dict:
    value = _read(state)
    if not value:
        value = {}
        state["after_dawn"] = value
    return value


def ending(state: dict) -> str:
    root = state.get("grand_retour")
    root = root if isinstance(root, dict) else {}
    value = root.get("last_ending")
    if value in grand_retour.ENDINGS:
        return value
    current = grand_retour.status(state)
    return current.get("ending", "") if current.get("completed") else ""


def _choices(state: dict, finale: str) -> dict:
    worlds = _read(state).get("worlds")
    worlds = worlds if isinstance(worlds, dict) else {}
    result = worlds.get(finale)
    return {key: value for key, value in result.items()
            if key in FRONTS and isinstance(value, str) and
            value in FRONTS[key][1]} if isinstance(result, dict) else {}


def world_status(state: dict) -> dict:
    finale = ending(state)
    choices = _choices(state, finale)
    return {
        "available": bool(finale), "ending": finale,
        "scene": SCENES.get(finale, "Termine le Grand Retour pour voir le monde changer."),
        "fronts": {key: {"scene": FRONT_SCENES.get(finale, {}).get(key, scene),
                         "options": options,
                         "choice": choices.get(key, "")}
                   for key, (scene, options) in FRONTS.items()},
        "completed": sum(choices.get(key) in FRONTS[key][1] for key in FRONTS),
    }


def choose_world(state: dict, front: str, action: str) -> dict:
    finale = ending(state)
    if not finale:
        raise ValueError("termine d'abord le Grand Retour")
    front, action = str(front).strip().casefold(), str(action).strip().casefold()
    if front not in FRONTS:
        raise ValueError("front attendu : " + ", ".join(FRONTS))
    if action not in FRONTS[front][1]:
        raise ValueError("choix attendu : " + ", ".join(FRONTS[front][1]))
    if front in _choices(state, finale):
        raise ValueError("ce front a deja ete decide pour cette fin")
    worlds = _root(state).setdefault("worlds", {})
    worlds.setdefault(finale, {})[front] = action
    if front == "cite":
        fourth = state.setdefault("wave4", {})
        city = fourth.get("city")
        if isinstance(city, dict):
            bones = city.get("bones", 0)
            bones = bones if isinstance(bones, int) and not isinstance(bones, bool) else 0
            reward = {"aube": 8, "veille": 6, "cendres": 4}[finale]
            city["bones"] = max(0, min(9999, bones +
                                       (reward if action == "rebatir" else reward - 2)))
    elif front == "rail":
        _root(state)["rail_voucher"] = "coal" if action == "charbon" else "integrity"
    elif front == "nemesis":
        fourth = state.get("wave4")
        nemesis = fourth.get("nemesis") if isinstance(fourth, dict) else None
        if isinstance(nemesis, dict):
            grudge = nemesis.get("grudge", 0)
            if isinstance(grudge, int):
                influence = {"aube": 3, "veille": 2, "cendres": 1}[finale]
                nemesis["grudge"] = max(0, min(99, grudge +
                                              (-influence if action == "apaiser" else influence)))
    return world_status(state)


def crew_status(state: dict) -> dict:
    sixth = state.get("wave6")
    recruited = sixth.get("crew") if isinstance(sixth, dict) else []
    recruited = {item for item in recruited if isinstance(item, str)} if isinstance(recruited, list) else set()
    missions = _read(state).get("missions")
    missions = missions if isinstance(missions, dict) else {}
    return {
        "members": {key: {"name": name, "scene": MISSIONS[key],
                          "recruited": key in recruited,
                          "choice": missions.get(key, "")}
                    for key, name in CREW.items()},
        "completed": sum(missions.get(key) in ("soutenir", "sacrifier") for key in CREW),
        "loyal": sum(missions.get(key) == "soutenir" for key in CREW),
        "redeemed": bool(_read(state).get("redeemed")),
    }


def choose_mission(state: dict, member: str, action: str) -> dict:
    if not ending(state):
        raise ValueError("termine d'abord le Grand Retour")
    member, action = str(member).strip().casefold(), str(action).strip().casefold()
    if member not in CREW:
        raise ValueError("membre attendu : " + ", ".join(CREW))
    if action not in ("soutenir", "sacrifier"):
        raise ValueError("choix attendu : soutenir, sacrifier")
    current = crew_status(state)
    if not current["members"][member]["recruited"]:
        raise ValueError("recrute d'abord ce membre dans le Dernier Train")
    if current["members"][member]["choice"]:
        raise ValueError("cette mission est deja terminee")
    _root(state).setdefault("missions", {})[member] = action
    result = crew_status(state)
    campaign = grand_retour.status(state)
    campaign_root = state.get("grand_retour")
    betrayed = campaign.get("betrayed") or (isinstance(campaign_root, dict) and
                                            campaign_root.get("last_betrayed"))
    if betrayed and result["loyal"] >= 3:
        _root(state)["redeemed"] = True
    return crew_status(state)


def door_status(state: dict) -> dict:
    campaign = grand_retour.status(state)
    world = world_status(state)
    crew = crew_status(state)
    endings = set(campaign.get("endings", []))
    clues = [name in endings for name in grand_retour.ENDINGS]
    clues.extend(world["fronts"][name]["choice"] in FRONTS[name][1] for name in FRONTS)
    clues.append(crew["completed"] == len(CREW))
    solved = bool(_read(state).get("door_solved"))
    return {"clues": clues, "found": sum(clues), "ready": all(clues),
            "solved": solved,
            "riddle": ("Je garde toutes les fins sans en effacer aucune. Qui suis-je ?"
                       if all(clues) else ""),
            "epilogue": DOOR_EPILOGUE if solved else ""}


def solve_door(state: dict, answer: str) -> dict:
    before = door_status(state)
    if before["solved"]:
        return before
    if not before["ready"]:
        raise ValueError("reunis les trois fins, les quatre fronts et l'equipage")
    if str(answer).strip().casefold() not in ("memoire", "la memoire", "mémoire", "la mémoire"):
        raise ValueError("la porte ne reconnait pas cette reponse")
    _root(state)["door_solved"] = True
    return door_status(state)


def carnet_lines(state: dict, *, secrets: bool = False) -> list[str]:
    campaign = grand_retour.status(state)
    world = world_status(state)
    crew = crew_status(state)
    door = door_status(state)
    lines = ["CARNET DE ROUTE", f"Grand Retour : {len(campaign['endings'])}/3 fins decouvertes"]
    if not world["available"]:
        lines.append("Prochain pas : doot --grand-retour")
    else:
        lines.append(f"Monde apres l'Aube ({world['ending']}) : {world['completed']}/4 fronts")
        for key, item in world["fronts"].items():
            lines.append(f"  [{'x' if item['choice'] else ' '}] {key} : {item['choice'] or item['scene']}")
        lines.append(f"Equipage : {crew['completed']}/5 missions, {crew['loyal']} liens preserves")
        for key, item in crew["members"].items():
            if not item["choice"]:
                lines.append(f"  [{'+' if item['recruited'] else '-'}] {item['name']} : " +
                             ("mission disponible" if item["recruited"] else "a recruter"))
        if not campaign["completed"]:
            lines.append("Prochain pas : terminer la campagne en cours")
        elif world["completed"] < 4:
            lines.append("Prochain pas : doot --after-dawn")
        elif crew["completed"] < 5:
            lines.append("Prochain pas : doot --crew-missions")
        else:
            lines.append("Prochain pas : rejouer pour les autres fins ou examiner la porte")
    lines.append(f"Huitieme Porte : {door['found']}/8 traces")
    if secrets:
        lines.extend(["Indices : trois destins, quatre fronts d'une meme fin, cinq compagnons.",
                      "La reponse est ce qui conserve sans effacer."])
    else:
        lines.append("Indices masques ; utilise --carnet-secrets pour les reveler.")
    return lines
