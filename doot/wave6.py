"""Vague 6 : le Dernier Train pour l'Au-dela.

Les systemes de cette vague restent locaux, deterministes et partageables par
des capsules bornees. Ils prolongent la progression existante sans reseau et
sans executer de contenu fourni par un pack.
"""

from __future__ import annotations

import hashlib
import html
import json
import os
import random
from datetime import date
from pathlib import Path


def _root(state: dict) -> dict:
    value = state.get("wave6")
    if not isinstance(value, dict):
        value = {}
        state["wave6"] = value
    return value


def _atomic_text(path: Path, content: str) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(content, encoding="utf-8")
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except OSError:
            pass
    return path


def _checksum(payload: dict) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                           separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _chronicle(state: dict, kind: str, text: str) -> None:
    entries = _root(state).get("chronicle")
    if not isinstance(entries, list):
        entries = []
        _root(state)["chronicle"] = entries
    entries.append({"kind": str(kind)[:24], "text": str(text)[:180]})
    del entries[:-80]


# ---------------------------------------------------------- train fantome ---

TRAIN_ROUTES = {
    "cendre": ("Quai des veuves", "Tunnel des soupirs", "Wagon-cendre",
                "Pont sans rive", "Terminus du brasier froid"),
    "lune": ("Quai de cuivre", "Tunnel eclipse", "Wagon des astres",
              "Viaduc renverse", "Terminus de la lune creuse"),
    "ossuaire": ("Quai des tibias", "Tunnel des noms", "Wagon-reliquaire",
                  "Pont des cloches", "Terminus du dernier os"),
}
TRAIN_KINDS = {
    "quai": ("explorer", "Une lanterne montre une porte qui n'etait pas la."),
    "wagon": ("negocier", "Les passagers tendent des billets sans date."),
    "tunnel": ("accelerer", "Quelque chose court a la meme vitesse sur le toit."),
}
TRAIN_ACTIONS = tuple(item[0] for item in TRAIN_KINDS.values())


def _train_stations(seed: str, route: str) -> list[dict]:
    rng = random.Random(f"dernier-train:{route}:{seed}")
    result = []
    for index, name in enumerate(TRAIN_ROUTES[route]):
        kind = rng.choice(tuple(TRAIN_KINDS))
        counter, signal = TRAIN_KINDS[kind]
        result.append({"index": index, "name": name, "kind": kind,
                       "danger": 1 + index // 2, "counter": counter,
                       "signal": signal,
                       "reward": rng.choice(("billet noir", "charbon bleu",
                                             "fragment de rail", "cle de wagon"))})
    return result


def start_ghost_train(state: dict, seed: str = "", route: str = "") -> dict:
    seed = str(seed).strip() or date.today().isoformat()
    route = str(route).strip().casefold()
    if not route:
        route = random.Random("ligne:" + seed).choice(tuple(TRAIN_ROUTES))
    if route not in TRAIN_ROUTES:
        raise ValueError("ligne inconnue : " + ", ".join(TRAIN_ROUTES))
    _root(state)["train"] = {
        "seed": seed, "route": route, "stations": _train_stations(seed, route),
        "station": 0, "integrity": 12, "coal": 11, "cargo": [], "history": [],
        "completed": False, "arrived": False,
    }
    aftermath = state.get("after_dawn")
    if isinstance(aftermath, dict):
        voucher = aftermath.pop("rail_voucher", "")
        if voucher == "coal":
            _root(state)["train"]["coal"] += 3
        elif voucher == "integrity":
            _root(state)["train"]["integrity"] += 3
    _chronicle(state, "train", f"Depart de la ligne {route}.")
    return ghost_train_status(state)


def ghost_train_status(state: dict) -> dict:
    run = _root(state).get("train")
    if not isinstance(run, dict):
        return {"active": False}
    result = dict(run)
    stations = run.get("stations") if isinstance(run.get("stations"), list) else []
    index = run.get("station", 0)
    result["active"] = not bool(run.get("completed"))
    result["current"] = stations[index] if isinstance(index, int) and 0 <= index < len(stations) else None
    result["completed_routes"] = completed_train_routes(state)
    return result


def completed_train_routes(state: dict) -> list[str]:
    routes = _root(state).get("completed_routes")
    if not isinstance(routes, list):
        routes = []
        _root(state)["completed_routes"] = routes
    return sorted({item for item in routes if item in TRAIN_ROUTES})


def choose_ghost_train(state: dict, action: str) -> dict:
    run = _root(state).get("train")
    if not isinstance(run, dict) or run.get("completed"):
        raise ValueError("aucun train fantome en route")
    action = str(action).strip().casefold()
    if action not in TRAIN_ACTIONS:
        raise ValueError("action attendue : " + ", ".join(TRAIN_ACTIONS))
    index = int(run.get("station", 0))
    stations = run.get("stations", [])
    if not (0 <= index < len(stations)):
        raise ValueError("l'itineraire du train est illisible")
    station = stations[index]
    countered = action == station["counter"]
    damage = 0 if countered else int(station["danger"])
    run["integrity"] = max(0, int(run.get("integrity", 0)) - damage)
    run["coal"] = max(0, int(run.get("coal", 0)) - (1 if action != "accelerer" else 2))
    if countered:
        run["cargo"].append(station["reward"])
    run["history"].append({"station": station["name"], "action": action,
                           "countered": countered, "damage": damage})
    run["station"] = index + 1
    if run["integrity"] <= 0 or run["coal"] <= 0 or run["station"] >= len(stations):
        run["completed"] = True
        run["arrived"] = (run["integrity"] > 0 and run["station"] >= len(stations))
        if run["arrived"]:
            routes = completed_train_routes(state)
            if run["route"] not in routes:
                routes.append(run["route"])
                _root(state)["completed_routes"] = sorted(routes)
            _chronicle(state, "train", f"La ligne {run['route']} atteint son terminus.")
    return ghost_train_status(state)


# --------------------------------------------------------- equipage spectral --

SPECTRAL_CREW = {
    "controleuse": ("Mina Sans-Billet", "navigation", "evite un faux terminus"),
    "mecanicien": ("Gaston Braise", "moteur", "rend un point de charbon"),
    "cantatrice": ("Alma Sourdine", "musique", "revele le prochain contretemps"),
    "bagagiste": ("Porter Cranes", "butin", "protege une relique fragile"),
    "chef": ("Octave Minuit", "commandement", "renforce toutes les synergies"),
}


def spectral_crew_status(state: dict) -> dict:
    crew = _root(state).get("crew")
    if not isinstance(crew, list):
        crew = []
        _root(state)["crew"] = crew
    crew = [item for item in crew if item in SPECTRAL_CREW]
    _root(state)["crew"] = crew
    return {"recruited": crew, "total": len(SPECTRAL_CREW), "complete": len(crew) >= 4,
            "members": [{"id": key, "name": value[0], "role": value[1],
                         "gift": value[2], "recruited": key in crew}
                        for key, value in SPECTRAL_CREW.items()]}


def recruit_spectral_crew(state: dict, member: str) -> dict:
    member = str(member).strip().casefold()
    if member not in SPECTRAL_CREW:
        raise ValueError("fantome inconnu : " + ", ".join(SPECTRAL_CREW))
    status = spectral_crew_status(state)
    if member not in status["recruited"]:
        _root(state)["crew"].append(member)
        _chronicle(state, "equipage", f"{SPECTRAL_CREW[member][0]} monte a bord.")
    return spectral_crew_status(state)


# ------------------------------------------------------- enquetes du rail ----

RAIL_CASES = (
    ("Le passager du siege vide", ("controleuse", "cantatrice", "bagagiste"),
     "bagagiste", ("un ticket troue deux fois", "une valise qui respire", "de la suie sous le siege")),
    ("Le vol de la treizieme cloche", ("mecanicien", "chef", "cantatrice"),
     "cantatrice", ("une partition humide", "un marteau sans empreinte", "un echo en retard")),
    ("Le terminus falsifie", ("controleuse", "mecanicien", "chef"),
     "chef", ("un plan retourne", "une montre sans minuit", "un billet encore chaud")),
)


def start_rail_case(state: dict, seed: str = "") -> dict:
    case = random.Random("affaire-rail:" + (seed or date.today().isoformat())).choice(RAIL_CASES)
    _root(state)["rail_case"] = {"title": case[0], "suspects": list(case[1]),
                                  "truth": case[2], "clues": list(case[3]),
                                  "found": [], "questioned": [], "verdict": "",
                                  "solved": False}
    _chronicle(state, "enquete", f"Affaire ouverte : {case[0]}.")
    return rail_case_status(state)


def rail_case_status(state: dict) -> dict:
    data = _root(state).get("rail_case")
    if not isinstance(data, dict):
        return {"active": False}
    return {"active": not bool(data.get("verdict")), "title": data["title"],
            "suspects": list(data.get("suspects", [])), "found": list(data.get("found", [])),
            "questioned": list(data.get("questioned", [])), "verdict": data.get("verdict", ""),
            "solved": bool(data.get("solved")),
            "remaining": max(0, len(data.get("clues", [])) - len(data.get("found", [])))}


def investigate_rail_case(state: dict, action: str) -> dict:
    data = _root(state).get("rail_case")
    if not isinstance(data, dict) or data.get("verdict"):
        raise ValueError("aucune affaire du rail active")
    action = str(action).strip().casefold()
    if action == "chercher":
        if len(data["found"]) < len(data["clues"]):
            data["found"].append(data["clues"][len(data["found"])])
    elif action.startswith("interroger:"):
        suspect = action.partition(":")[2]
        if suspect not in data["suspects"]:
            raise ValueError("suspect inconnu")
        if suspect not in data["questioned"]:
            data["questioned"].append(suspect)
    elif action.startswith("accuser:"):
        suspect = action.partition(":")[2]
        if suspect not in data["suspects"]:
            raise ValueError("suspect inconnu")
        if len(data["found"]) < 2:
            raise ValueError("deux indices sont necessaires avant l'accusation")
        data["verdict"] = suspect
        data["solved"] = suspect == data["truth"]
        _chronicle(state, "enquete", f"Affaire {data['title']} : "
                   f"{'resolue' if data['solved'] else 'classee sans reponse'}.")
    else:
        raise ValueError("action attendue : chercher, interroger:NOM ou accuser:NOM")
    return rail_case_status(state)


# ------------------------------------------------ archeologie interdite -----

ARCHAEOLOGY_SITES = {
    "necropole": ("couronne de basalte", ("arc frontal", "gemme de suie", "serment grave")),
    "gare-ensevelie": ("lanterne du premier train", ("verre lunaire", "anse d'airain", "meche eternelle")),
    "cratere": ("trompette du roi muet", ("pavillon fendu", "piston d'ivoire", "souffle fossilise")),
}


def archaeology_status(state: dict) -> dict:
    found = _root(state).get("fragments")
    if not isinstance(found, list):
        found = []
        _root(state)["fragments"] = found
    restored = _root(state).get("restored_artifacts")
    if not isinstance(restored, list):
        restored = []
        _root(state)["restored_artifacts"] = restored
    valid = {fragment for _, fragments in ARCHAEOLOGY_SITES.values() for fragment in fragments}
    found = sorted({item for item in found if item in valid})
    restored = sorted({item for item in restored if item in {value[0] for value in ARCHAEOLOGY_SITES.values()}})
    _root(state)["fragments"] = found
    _root(state)["restored_artifacts"] = restored
    return {"fragments": found, "fragment_total": len(valid), "restored": restored,
            "sites": [{"id": key, "artifact": value[0],
                       "found": len(set(found) & set(value[1])), "total": len(value[1])}
                      for key, value in ARCHAEOLOGY_SITES.items()]}


def dig_archaeology(state: dict, site: str) -> dict:
    site = str(site).strip().casefold()
    if site not in ARCHAEOLOGY_SITES:
        raise ValueError("site inconnu : " + ", ".join(ARCHAEOLOGY_SITES))
    status = archaeology_status(state)
    fragments = ARCHAEOLOGY_SITES[site][1]
    fragment = next((item for item in fragments if item not in status["fragments"]), fragments[0])
    fresh = fragment not in status["fragments"]
    if fresh:
        _root(state)["fragments"].append(fragment)
        _chronicle(state, "archeologie", f"Fragment exhume : {fragment}.")
    result = archaeology_status(state)
    result.update({"site": site, "fragment": fragment, "fresh": fresh})
    return result


def restore_artifact(state: dict, site: str) -> dict:
    site = str(site).strip().casefold()
    if site not in ARCHAEOLOGY_SITES:
        raise ValueError("site inconnu")
    status = archaeology_status(state)
    artifact, fragments = ARCHAEOLOGY_SITES[site]
    if not set(fragments).issubset(status["fragments"]):
        raise ValueError("les trois fragments du site sont necessaires")
    fresh = artifact not in status["restored"]
    if fresh:
        _root(state)["restored_artifacts"].append(artifact)
        _chronicle(state, "archeologie", f"Artefact restaure : {artifact}.")
    result = archaeology_status(state)
    result.update({"artifact": artifact, "fresh": fresh})
    return result


# ------------------------------------------------ marche noir / propheties --

MARKET_NAMES = ("Compas du nocher", "Masque a deux ombres", "Billet du terminus",
                "Cle du wagon royal", "Sablier de cendre", "Violon sans cordes")


def black_market_status(state: dict, seed: str = "") -> dict:
    market = _root(state).get("market")
    requested = str(seed).strip()
    market_id = requested or date.today().isoformat()
    if not isinstance(market, dict) or (requested and market.get("id") != market_id):
        rng = random.Random("marche-noir:" + market_id)
        names = list(MARKET_NAMES)
        rng.shuffle(names)
        offers = []
        for index, name in enumerate(names[:4]):
            signature = hashlib.sha256(f"{market_id}:{name}".encode()).hexdigest()
            offers.append({"id": f"lot-{index + 1}", "name": name,
                           "price": 4 + int(signature[:2], 16) % 8,
                           "authentic": int(signature[2:4], 16) % 3 != 0,
                           "inspected": False, "bought": False, "bids": 0,
                           "rival": rng.choice(("Dame Suie", "Baron Minuit", "Comte Echo"))})
        if offers and all(offer["authentic"] for offer in offers):
            offers[0]["authentic"] = False
        market = {"id": market_id, "tickets": 24, "offers": offers,
                  "counterfeits": []}
        _root(state)["market"] = market
    visible_offers = []
    for offer in market.get("offers", []):
        visible = {key: value for key, value in offer.items() if key != "authentic"}
        if offer.get("inspected"):
            visible["verdict"] = "authentique" if offer["authentic"] else "contrefacon"
        visible_offers.append(visible)
    return {"id": market["id"], "tickets": int(market.get("tickets", 0)),
            "offers": visible_offers,
            "counterfeits": list(market.get("counterfeits", []))}


def black_market_action(state: dict, action: str, seed: str = "") -> dict:
    black_market_status(state, seed)
    market = _root(state)["market"]
    verb, separator, lot = str(action).strip().casefold().partition(":")
    if not separator or verb not in ("inspecter", "acheter", "encherir"):
        raise ValueError("action attendue : inspecter:LOT, acheter:LOT ou encherir:LOT")
    offer = next((item for item in market["offers"] if item["id"] == lot), None)
    if offer is None:
        raise ValueError("lot inconnu")
    detected = False
    outbid = False
    if verb == "inspecter":
        offer["inspected"] = True
        if not offer["authentic"] and offer["id"] not in market["counterfeits"]:
            market["counterfeits"].append(offer["id"])
            detected = True
            _chronicle(state, "marche", f"Contrefacon demasquee : {offer['name']}.")
    elif verb == "acheter":
        if offer.get("bought"):
            raise ValueError("ce lot a deja ete vendu")
        if int(market.get("tickets", 0)) < int(offer["price"]):
            raise ValueError("pas assez de billets noirs")
        market["tickets"] -= offer["price"]
        offer["bought"] = True
        _chronicle(state, "marche", f"Lot acquis : {offer['name']}.")
    else:
        if offer.get("bought"):
            raise ValueError("ce lot a deja ete vendu")
        if int(market.get("tickets", 0)) < int(offer["price"]):
            raise ValueError("pas assez de billets noirs pour encherir")
        offer["bids"] = int(offer.get("bids", 0)) + 1
        signature = hashlib.sha256(
            f"{market['id']}:{offer['id']}:{offer['bids']}".encode()
        ).hexdigest()
        outbid = int(signature[:2], 16) % 3 == 0
        if outbid:
            offer["price"] += 1 + int(signature[2], 16) % 3
            _chronicle(state, "marche", f"{offer['rival']} surencherit sur {offer['name']}.")
        else:
            market["tickets"] -= offer["price"]
            offer["bought"] = True
            _chronicle(state, "marche", f"Enchere remportee : {offer['name']}.")
    result = black_market_status(state, seed)
    result.update({"action": verb, "lot": lot, "detected": detected, "outbid": outbid})
    return result


PROPHECY_FAILURES = ("retard", "silence", "demi-tour")


def prophecy_status(state: dict, day: date | None = None) -> dict:
    day = day or date.today()
    year, week, _ = day.isocalendar()
    prophecy_id = f"{year}-W{week:02d}"
    data = _root(state).get("prophecy")
    if not isinstance(data, dict) or data.get("id") != prophecy_id:
        progress = archaeology_status(state)
        crew = spectral_crew_status(state)
        routes = completed_train_routes(state)
        if not routes:
            objective, text = "train", "Atteins un terminus du Dernier Train."
        elif len(crew["recruited"]) < 2:
            objective, text = "crew", "Recrute deux voix pour l'equipage."
        elif not progress["restored"]:
            objective, text = "artifact", "Restaure un artefact interdit."
        else:
            objective, text = "case", "Resous une affaire du rail."
        data = {"id": prophecy_id, "objective": objective, "text": text,
                "completed": False, "failed": False, "reason": ""}
        _root(state)["prophecy"] = data
    failures = _root(state).get("prophecy_failures")
    if not isinstance(failures, list):
        failures = []
        _root(state)["prophecy_failures"] = failures
    return {**data, "failures": sorted({item for item in failures if item in PROPHECY_FAILURES}),
            "lost_station": bool(_root(state).get("lost_station_unlocked"))}


def _prophecy_ready(state: dict, objective: str) -> bool:
    if objective == "train":
        return bool(completed_train_routes(state))
    if objective == "crew":
        return len(spectral_crew_status(state)["recruited"]) >= 2
    if objective == "artifact":
        return bool(archaeology_status(state)["restored"])
    case = rail_case_status(state)
    return bool(case.get("solved"))


def resolve_prophecy(state: dict, action: str, day: date | None = None) -> dict:
    status = prophecy_status(state, day)
    data = _root(state)["prophecy"]
    action = str(action).strip().casefold()
    if data.get("completed") or data.get("failed"):
        return status
    if action == "accomplir":
        if not _prophecy_ready(state, data["objective"]):
            raise ValueError("la prophetie n'est pas encore accomplie")
        data["completed"] = True
        _chronicle(state, "prophetie", f"Prophetie {data['id']} accomplie.")
    elif action.startswith("echouer:"):
        reason = action.partition(":")[2]
        if reason not in PROPHECY_FAILURES:
            raise ValueError("echec attendu : " + ", ".join(PROPHECY_FAILURES))
        data["failed"] = True
        data["reason"] = reason
        failures = _root(state)["prophecy_failures"]
        if reason not in failures:
            failures.append(reason)
        if set(PROPHECY_FAILURES).issubset(failures):
            _root(state)["lost_station_unlocked"] = True
    else:
        raise ValueError("action attendue : accomplir ou echouer:RAISON")
    return prophecy_status(state, day)


# ------------------------------------------------ gazette / combat musical --

def export_crypt_gazette(state: dict, destination: Path) -> Path:
    destination = Path(destination)
    if destination.suffix.casefold() not in (".html", ".htm"):
        destination = destination / "gazette-de-la-crypte.html"
    entries = _root(state).get("chronicle")
    entries = entries if isinstance(entries, list) else []
    routes = ", ".join(completed_train_routes(state)) or "aucune"
    crew = ", ".join(item["name"] for item in spectral_crew_status(state)["members"]
                     if item["recruited"]) or "personne"
    stories = "".join(f"<li><b>{html.escape(str(item.get('kind', 'echo')))}</b> — "
                      f"{html.escape(str(item.get('text', '')))}</li>" for item in entries[-20:])
    document = f"""<!doctype html><html lang=\"fr\"><meta charset=\"utf-8\">
<title>La Gazette de la Crypte</title><style>
body{{max-width:780px;margin:3rem auto;background:#130f1d;color:#eee4cf;font:18px Georgia;padding:2rem}}
h1{{color:#e3b55b;border-bottom:2px solid #6f4b87}}li{{margin:.8rem 0;line-height:1.45}}
.mast{{letter-spacing:.18em;text-transform:uppercase;color:#b998cc}}</style>
<p class=\"mast\">Edition du dernier quai</p><h1>La Gazette de la Crypte</h1>
<p><b>Lignes arrivees :</b> {html.escape(routes)}<br><b>Equipage :</b> {html.escape(crew)}</p>
<h2>Les nouvelles d'outre-tombe</h2><ul>{stories or '<li>Le silence attend son premier scoop.</li>'}</ul></html>"""
    path = _atomic_text(destination, document)
    _chronicle(state, "gazette", f"Gazette imprimee : {path.name}.")
    return path


BATTLE_NOTES = ("grave", "aigu", "silence")


def start_musical_battle(state: dict, seed: str = "") -> dict:
    seed = str(seed).strip() or date.today().isoformat()
    rng = random.Random("combat-musical:" + seed)
    _root(state)["battle"] = {"seed": seed, "score": list(BATTLE_NOTES) + [rng.choice(BATTLE_NOTES)],
                               "round": 0, "player_hp": 3, "boss_hp": 4,
                               "history": [], "completed": False, "won": False}
    return musical_battle_status(state)


def musical_battle_status(state: dict) -> dict:
    data = _root(state).get("battle")
    if not isinstance(data, dict):
        return {"active": False}
    result = dict(data)
    index = int(data.get("round", 0))
    score = data.get("score", [])
    result["active"] = not bool(data.get("completed"))
    result["cue"] = score[index] if 0 <= index < len(score) else ""
    return result


def musical_battle_action(state: dict, note: str) -> dict:
    data = _root(state).get("battle")
    if not isinstance(data, dict) or data.get("completed"):
        raise ValueError("aucun combat musical actif")
    note = str(note).strip().casefold()
    if note not in BATTLE_NOTES:
        raise ValueError("note attendue : " + ", ".join(BATTLE_NOTES))
    index = int(data["round"])
    counter = note == data["score"][index]
    if counter:
        data["boss_hp"] = max(0, int(data["boss_hp"]) - 1)
    else:
        data["player_hp"] = max(0, int(data["player_hp"]) - 1)
    data["history"].append({"round": index + 1, "note": note, "counter": counter})
    data["round"] = index + 1
    if data["boss_hp"] <= 0 or data["player_hp"] <= 0 or data["round"] >= len(data["score"]):
        data["completed"] = True
        data["won"] = data["boss_hp"] <= 0 and data["player_hp"] > 0
        _chronicle(state, "musique", "Le duel musical est gagne." if data["won"]
                   else "Le dernier accord se brise.")
    return musical_battle_status(state)


# -------------------------------------------------- maisons funeraires ------

FUNERAL_HOUSES = {
    "airain": ("Maison de l'Airain", "cortege", "les cuivres ouvrent chaque porte"),
    "velours": ("Maison du Velours", "elegie", "le silence rend les serments audibles"),
    "cendre": ("Maison de la Cendre", "festin", "chaque fin nourrit une autre histoire"),
}
HOUSE_STRATEGIES = ("cortege", "elegie", "festin")


def funeral_house_status(state: dict) -> dict:
    data = _root(state).get("house")
    if not isinstance(data, dict):
        return {"pledged": "", "reputation": 0, "mission": "",
                "houses": [{"id": key, "name": value[0], "motto": value[2]}
                           for key, value in FUNERAL_HOUSES.items()]}
    house = data.get("id", "")
    mission = HOUSE_STRATEGIES[int(data.get("missions", 0)) % len(HOUSE_STRATEGIES)]
    return {"pledged": house, "name": FUNERAL_HOUSES.get(house, ("", "", ""))[0],
            "reputation": max(0, int(data.get("reputation", 0))), "mission": mission,
            "missions": max(0, int(data.get("missions", 0))),
            "houses": [{"id": key, "name": value[0], "motto": value[2]}
                       for key, value in FUNERAL_HOUSES.items()]}


def pledge_funeral_house(state: dict, house: str) -> dict:
    house = str(house).strip().casefold()
    if house not in FUNERAL_HOUSES:
        raise ValueError("maison inconnue : " + ", ".join(FUNERAL_HOUSES))
    current = _root(state).get("house")
    if isinstance(current, dict) and current.get("id") not in (None, "", house):
        raise ValueError("une maison a deja recu ton serment")
    if not isinstance(current, dict):
        _root(state)["house"] = {"id": house, "reputation": 0, "missions": 0}
        _chronicle(state, "maison", f"Serment prete a {FUNERAL_HOUSES[house][0]}.")
    return funeral_house_status(state)


def funeral_house_mission(state: dict, strategy: str) -> dict:
    status = funeral_house_status(state)
    if not status["pledged"]:
        raise ValueError("prete d'abord serment a une maison")
    strategy = str(strategy).strip().casefold()
    if strategy not in HOUSE_STRATEGIES:
        raise ValueError("strategie attendue : " + ", ".join(HOUSE_STRATEGIES))
    success = strategy == status["mission"]
    data = _root(state)["house"]
    data["missions"] = int(data.get("missions", 0)) + 1
    if success:
        data["reputation"] = int(data.get("reputation", 0)) + 1
        _chronicle(state, "maison", f"Mission reussie pour {FUNERAL_HOUSES[data['id']][0]}.")
    result = funeral_house_status(state)
    result["success"] = success
    return result


# ----------------------------------------------------- atelier de mods -------

MOD_MODULES = ("campaign", "creature", "relic", "riddle")


def create_mod_capsule(destination: Path, name: str, theme: str) -> Path:
    name = str(name).strip()
    theme = str(theme).strip()
    if not name or len(name) > 64 or not theme or len(theme) > 64:
        raise ValueError("nom et theme doivent compter de 1 a 64 caracteres")
    payload = {"format": "doot-mod-v1", "manifest": {"name": name, "theme": theme,
               "modules": list(MOD_MODULES), "entrypoints": []}}
    envelope = {"payload": payload, "sha256": _checksum(payload)}
    destination = Path(destination)
    if destination.suffix.casefold() != ".dootmod":
        destination = destination / ("-".join(name.casefold().split()) + ".dootmod")
    return _atomic_text(destination, json.dumps(envelope, ensure_ascii=False, indent=2))


def validate_mod_capsule(source: Path) -> dict:
    try:
        source = Path(source)
        if not source.is_file() or source.stat().st_size > 512 * 1024:
            raise ValueError
        envelope = json.loads(source.read_text(encoding="utf-8"))
        payload = envelope["payload"]
        manifest = payload["manifest"]
        if (envelope.get("sha256") != _checksum(payload) or
                payload.get("format") != "doot-mod-v1" or
                not isinstance(manifest, dict) or
                not isinstance(manifest.get("name"), str) or not manifest["name"] or
                len(manifest["name"]) > 64 or
                not isinstance(manifest.get("theme"), str) or not manifest["theme"] or
                len(manifest["theme"]) > 64 or
                manifest.get("modules") != list(MOD_MODULES) or
                manifest.get("entrypoints") != []):
            raise ValueError
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("capsule de mod invalide") from exc
    return {"valid": True, "name": manifest["name"], "theme": manifest["theme"],
            "modules": list(manifest["modules"]), "sha256": envelope["sha256"]}


# ---------------------------------------------------- realisateur / secrets --

def export_scene_replay(state: dict, destination: Path) -> Path:
    destination = Path(destination)
    if destination.suffix.casefold() not in (".html", ".htm"):
        destination = destination / "dernier-train-replay.html"
    entries = _root(state).get("chronicle")
    entries = entries if isinstance(entries, list) else []
    cards = "".join(f"<article><span>{index:02d}</span><h2>{html.escape(str(item.get('kind', 'scene')))}</h2>"
                    f"<p>{html.escape(str(item.get('text', '')))}</p></article>"
                    for index, item in enumerate(entries[-24:], 1))
    document = f"""<!doctype html><html lang=\"fr\"><meta charset=\"utf-8\">
<title>Dernier Train — Replay</title><style>
body{{margin:0;background:#090711;color:#f2e7cf;font:18px Georgia;overflow-x:auto;display:flex;gap:2rem;padding:4rem}}
article{{min-width:320px;max-width:320px;background:linear-gradient(145deg,#24182f,#100d18);border:1px solid #9b7241;padding:2rem;box-shadow:0 20px 50px #0008}}
span{{color:#d9ae60;font-size:3rem}}h2{{color:#c6a3db;text-transform:capitalize}}</style>
{cards or '<article><span>00</span><h2>Silence</h2><p>La camera attend le premier depart.</p></article>'}</html>"""
    path = _atomic_text(destination, document)
    _chronicle(state, "realisateur", f"Replay monte : {path.name}.")
    return path


def lost_station_status(state: dict) -> dict:
    return {"unlocked": bool(_root(state).get("lost_station_unlocked")),
            "visited": bool(_root(state).get("lost_station_visited")),
            "failures": prophecy_status(state)["failures"],
            "hint": "Trois propheties doivent mourir chacune autrement."}


def visit_lost_station(state: dict, action: str) -> dict:
    status = lost_station_status(state)
    if not status["unlocked"]:
        raise ValueError("cette gare n'existe sur aucune carte")
    if str(action).strip().casefold() != "monter":
        raise ValueError("un train sans numero attend : monter")
    fresh = not status["visited"]
    _root(state)["lost_station_visited"] = True
    if fresh:
        _chronicle(state, "secret", "La Gare Zero accepte un passager vivant.")
    result = lost_station_status(state)
    result["fresh"] = fresh
    return result


BELL_CLUES = (
    ("rail", "Un terminus rend le premier coup."),
    ("choeur", "Quatre voix portent le second."),
    ("preuve", "Une affaire close rend le troisieme."),
    ("relique", "Un objet reuni rend le quatrieme."),
    ("accord", "Un duel gagne rend le cinquieme."),
    ("serment", "Trois faveurs d'une maison rendent le sixieme."),
)


def thirteenth_bell_status(state: dict) -> dict:
    case = rail_case_status(state)
    house = funeral_house_status(state)
    checks = {
        "rail": bool(completed_train_routes(state)),
        "choeur": spectral_crew_status(state)["complete"],
        "preuve": bool(case.get("solved")),
        "relique": bool(archaeology_status(state)["restored"]),
        "accord": bool(musical_battle_status(state).get("won")),
        "serment": house.get("reputation", 0) >= 3,
    }
    return {"clues": [{"id": key, "hint": hint, "found": checks[key]}
                      for key, hint in BELL_CLUES],
            "found": sum(1 for value in checks.values() if value), "total": len(checks),
            "rung": bool(_root(state).get("thirteenth_bell")),
            "epilogue": _root(state).get("bell_epilogue", "")}


def ring_thirteenth_bell(state: dict, answer: str) -> dict:
    status = thirteenth_bell_status(state)
    if status["found"] < status["total"]:
        raise ValueError("la cloche refuse : tous ses echos ne sont pas reunis")
    answer = str(answer).strip().casefold()
    if answer not in ("treize", "13"):
        raise ValueError("le marteau retombe sans sonner")
    fresh = not status["rung"]
    _root(state)["thirteenth_bell"] = True
    _root(state)["bell_epilogue"] = (
        "Le treizieme coup ouvre le wagon qui voyageait derriere le temps. "
        "A l'interieur, ton premier doot t'attend encore."
    )
    if fresh:
        _chronicle(state, "secret", "La Treizieme Cloche sonne enfin.")
    result = thirteenth_bell_status(state)
    result["fresh"] = fresh
    return result
