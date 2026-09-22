"""Vague 5 : catacombes, memoire et grands secrets persistants.

Tous les systemes restent locaux et reproductibles. Les capsules sociales sont
des fichiers verifies, les studios exportent des documents autonomes et aucun
service distant n'est requis.
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
    value = state.get("wave5")
    if not isinstance(value, dict):
        value = {}
        state["wave5"] = value
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


# ---------------------------------------------------------- catacombes 2.0 --

CATACOMB_SCENES = (
    ("vestibule", "Le vestibule des choix", "Une porte respire, l'autre fredonne."),
    ("bibliotheque", "La bibliotheque calcinee", "Les index cherchent encore leurs livres."),
    ("aqueduc", "L'aqueduc de mercure", "Un courant remonte vers sa propre source."),
    ("jardin", "Le jardin des clavicules", "Les fleurs tintent quand on ment."),
    ("clocher", "Le clocher sous la terre", "La cloche attend son treizieme coup."),
    ("trone", "Le trone sans roi", "Une couronne flotte au-dessus d'une ombre."),
)


def catacomb_map(seed: str, rooms: int = 6) -> list[dict]:
    seed = str(seed).strip() or date.today().isoformat()
    rng = random.Random("catacombes:" + seed)
    result = []
    for index in range(max(3, min(9, int(rooms)))):
        kind, title, text = rng.choice(CATACOMB_SCENES)
        result.append({
            "index": index, "kind": kind, "title": title, "text": text,
            "danger": min(6, rng.randint(1, 3) + index // 2),
            "creature": rng.choice(tuple(BESTIARY)),
            "left": rng.choice(("repos", "indice", "os grave")),
            "right": rng.choice(("relique", "clef", "souffle double")),
        })
    result[-1].update({"kind": "boss", "title": "Le Geometre des tombes",
                       "text": "Il replie tous les chemins en un seul.",
                       "creature": "geometre", "danger": 6})
    return result


def start_catacomb(state: dict, seed: str = "") -> dict:
    seed = str(seed).strip() or date.today().isoformat()
    _root(state)["catacomb"] = {
        "seed": seed, "rooms": catacomb_map(seed), "room": 0, "hp": 15,
        "torch": 7, "path": [], "loot": [], "completed": False, "won": False,
    }
    return catacomb_status(state)


def catacomb_status(state: dict) -> dict:
    run = _root(state).get("catacomb")
    if not isinstance(run, dict):
        return {"active": False}
    result = dict(run)
    rooms = run.get("rooms") if isinstance(run.get("rooms"), list) else []
    index = run.get("room", 0)
    result["active"] = not bool(run.get("completed"))
    result["current"] = rooms[index] if isinstance(index, int) and 0 <= index < len(rooms) else None
    return result


def choose_catacomb(state: dict, choice: str) -> dict:
    run = _root(state).get("catacomb")
    if not isinstance(run, dict) or run.get("completed"):
        raise ValueError("aucune descente active")
    choice = str(choice).strip().casefold()
    if choice not in ("gauche", "droite"):
        raise ValueError("choisis gauche ou droite")
    rooms = run.get("rooms")
    index = run.get("room")
    if not isinstance(rooms, list) or not isinstance(index, int) or index >= len(rooms):
        raise ValueError("la carte des catacombes est illisible")
    room = rooms[index]
    roll = random.Random(f"{run['seed']}:{index}:{choice}").random()
    danger = max(1, int(room.get("danger", 1)))
    weather = _root(state).get("active_weather")
    weather_id = weather.get("id") if isinstance(weather, dict) else ""
    damage = max(0, danger - (2 if choice == "gauche" else 0)) if roll < .55 else 0
    if damage and weather_id == "brouillard":
        damage += 1
    reward = room["left" if choice == "gauche" else "right"]
    if choice == "droite" and damage == 0:
        run["loot"].append(reward)
    elif choice == "gauche" or damage == 0:
        run["loot"].append(reward)
    if weather_id == "eclipse" and "glyphe meteorologique" not in run["loot"]:
        run["loot"].append("glyphe meteorologique")
    run["hp"] = max(0, int(run.get("hp", 0)) - damage)
    run["torch"] = max(0, int(run.get("torch", 0)) - 1)
    run["path"].append({"room": index, "choice": choice, "damage": damage})
    observe_creature(state, room["creature"])
    run["room"] = index + 1
    if run["hp"] <= 0 or run["torch"] <= 0 or run["room"] >= len(rooms):
        run["completed"] = True
        run["won"] = run["hp"] > 0 and run["room"] >= len(rooms)
    return catacomb_status(state)


# --------------------------------------------------------- boucle temporelle --

LOOP_SEQUENCE = ("ecouter", "attendre", "doot")


def time_loop_status(state: dict) -> dict:
    data = _root(state).get("time_loop")
    if not isinstance(data, dict):
        data = {"iteration": 1, "progress": 0, "broken": False, "memories": []}
        _root(state)["time_loop"] = data
    progress = max(0, min(len(LOOP_SEQUENCE), int(data.get("progress", 0))))
    return {"iteration": max(1, int(data.get("iteration", 1))), "progress": progress,
            "broken": bool(data.get("broken")), "memories": list(data.get("memories", [])),
            "hint": ("Le son vient avant le temps." if progress == 0 else
                     "L'immobilite laisse une fissure." if progress == 1 else
                     "Un seul souffle peut finir la nuit.")}


def advance_time_loop(state: dict, action: str) -> dict:
    status = time_loop_status(state)
    if status["broken"]:
        return status
    action = str(action).strip().casefold()
    if action not in ("ecouter", "attendre", "doot", "courir", "frapper"):
        raise ValueError("action inconnue dans la boucle")
    data = _root(state)["time_loop"]
    expected = LOOP_SEQUENCE[status["progress"]]
    if action == expected:
        data["progress"] = status["progress"] + 1
        if action not in data["memories"]:
            data["memories"].append(action)
        if data["progress"] == len(LOOP_SEQUENCE):
            data["broken"] = True
    else:
        data["iteration"] = status["iteration"] + 1
        data["progress"] = 0
    return time_loop_status(state)


# ------------------------------------------------------ familiers / bestiaire --

FAMILIAR_SKILLS = {
    "chauve_souris": ("echolocation", "abri nocturne"),
    "corbeau": ("oeil des reliques", "presage dore"),
    "crane": ("armure d'os", "rire de parade"),
    "trompettiste": ("souffle long", "contrechant spectral"),
}


def familiar_skill_status(state: dict) -> dict:
    familiar = state.get("wave3", {}).get("familiar", {})
    familiar = familiar if isinstance(familiar, dict) else {}
    familiar_id = familiar.get("id", "chauve_souris")
    if familiar_id not in FAMILIAR_SKILLS:
        familiar_id = "chauve_souris"
    bond = max(0, int(familiar.get("bond", 0)))
    data = _root(state).get("familiar_skills")
    if not isinstance(data, dict):
        data = {}
        _root(state)["familiar_skills"] = data
    unlocked = [item for item in data.get(familiar_id, []) if item in FAMILIAR_SKILLS[familiar_id]]
    data[familiar_id] = unlocked
    return {"id": familiar_id, "bond": bond, "level": 1 + min(4, bond // 5),
            "available": list(FAMILIAR_SKILLS[familiar_id]), "unlocked": unlocked}


def unlock_familiar_skill(state: dict, skill: str) -> dict:
    status = familiar_skill_status(state)
    skill = str(skill).strip().casefold()
    if status["level"] < 2:
        raise ValueError("le lien doit atteindre le niveau 2")
    wanted = next((item for item in status["available"] if item.casefold() == skill), None)
    if wanted is None:
        raise ValueError("talent inconnu pour ce familier")
    data = _root(state)["familiar_skills"][status["id"]]
    if wanted not in data:
        data.append(wanted)
    return familiar_skill_status(state)


BESTIARY = {
    "veilleur": ("Veilleur de suie", "Il cligne quand personne ne le regarde."),
    "cantatrice": ("Cantatrice sans voix", "Son ombre chante une mesure plus tard."),
    "controleuse": ("Controleuse spectrale", "Elle poinconne les souvenirs."),
    "geometre": ("Geometre des tombes", "Il plie les couloirs comme du papier."),
    "mange-lune": ("Mange-lune", "Une eclipse tient dans sa gueule."),
    "roi-echo": ("Roi Echo", "Il ne prononce que les dernieres paroles."),
}


def bestiary_status(state: dict) -> dict:
    found = _root(state).get("bestiary")
    if not isinstance(found, list):
        found = []
        _root(state)["bestiary"] = found
    return {"found": [key for key in BESTIARY if key in found], "total": len(BESTIARY),
            "entries": [{"id": key, "name": value[0], "lore": value[1], "known": key in found}
                        for key, value in BESTIARY.items()]}


def observe_creature(state: dict, creature: str) -> dict:
    creature = str(creature).strip().casefold()
    if creature not in BESTIARY:
        raise ValueError("creature inconnue")
    bestiary_status(state)
    found = _root(state)["bestiary"]
    fresh = creature not in found
    if fresh:
        found.append(creature)
    result = bestiary_status(state)
    result.update({"creature": creature, "fresh": fresh})
    return result


# ------------------------------------------------------ forge / meteorologie --

FORGE_MATERIALS = ("cendre", "tibia", "souffle", "miroir", "suie", "cloche")
FORGE_BOONS = ("double les os", "protege une salle", "revele un indice", "prolonge un combo")
FORGE_CURSES = ("attire la Nemesis", "eteint une torche", "inverse un choix", "revele ton reflet")


def forge_relic(state: dict, left: str, right: str) -> dict:
    left, right = str(left).casefold().strip(), str(right).casefold().strip()
    if left not in FORGE_MATERIALS or right not in FORGE_MATERIALS or left == right:
        raise ValueError("choisis deux materiaux differents : " + ", ".join(FORGE_MATERIALS))
    pair = sorted((left, right))
    seed = hashlib.sha256(":".join(pair).encode()).hexdigest()
    boon = FORGE_BOONS[int(seed[:2], 16) % len(FORGE_BOONS)]
    curse = FORGE_CURSES[int(seed[2:4], 16) % len(FORGE_CURSES)]
    weather = _root(state).get("active_weather")
    weather_id = weather.get("id") if isinstance(weather, dict) else ""
    item = {"id": "-".join(pair), "name": f"{pair[0].title()} de {pair[1]}",
            "materials": pair, "boon": boon, "curse": curse, "power": 2 + int(seed[4], 16) % 5}
    if weather_id == "pluie_os":
        item["power"] += 1
    item["weather"] = weather_id
    collection = _root(state).get("forged_relics")
    if not isinstance(collection, list):
        collection = []
        _root(state)["forged_relics"] = collection
    if not any(entry.get("id") == item["id"] for entry in collection if isinstance(entry, dict)):
        collection.append(item)
    return {**item, "total": len(collection)}


WEATHER = (
    ("brouillard", "Brouillard pensant", "les choix surs sont voiles"),
    ("lune_rouge", "Lune rouge", "les boss gagnent une riposte"),
    ("pluie_os", "Pluie d'os", "la forge produit une relique plus puissante"),
    ("eclipse", "Eclipse de cuivre", "les familiers parlent en glyphes"),
    ("orage_silencieux", "Orage silencieux", "la musique perd sa percussion"),
)


def paranormal_weather(day: date | None = None, days: int = 1) -> list[dict]:
    day = day or date.today()
    result = []
    for offset in range(max(1, min(31, int(days)))):
        current = date.fromordinal(day.toordinal() + offset)
        weather = random.Random("doot-weather:" + current.isoformat()).choice(WEATHER)
        result.append({"date": current.isoformat(), "id": weather[0],
                       "name": weather[1], "effect": weather[2]})
    return result


def witness_weather(state: dict, day: date | None = None) -> dict:
    item = paranormal_weather(day, 1)[0]
    _root(state)["active_weather"] = dict(item)
    seen = _root(state).get("weather_seen")
    if not isinstance(seen, list):
        seen = []
        _root(state)["weather_seen"] = seen
    if item["id"] not in seen:
        seen.append(item["id"])
    return {**item, "seen": list(seen), "unique": len(seen)}


# ------------------------------------------------- rituel / siege Nemesis --

def ritual_status(state: dict, seed: str = "") -> dict:
    data = _root(state).get("ritual")
    requested = str(seed).strip()
    ritual_id = requested or (str(data.get("id")) if isinstance(data, dict) and data.get("id")
                              else date.today().isoformat())
    if not isinstance(data, dict) or data.get("id") != ritual_id:
        data = {"id": ritual_id, "target": 5, "fragments": [], "contributors": []}
        _root(state)["ritual"] = data
    fragments = sorted({str(item)[:64] for item in data.get("fragments", [])})
    contributors = sorted({str(item)[:40] for item in data.get("contributors", [])})
    data.update({"fragments": fragments, "contributors": contributors})
    return {"id": data["id"], "target": data["target"], "fragments": fragments,
            "contributors": contributors, "completed": len(fragments) >= data["target"]}


def offer_ritual_fragment(state: dict, fragment: str, contributor: str = "local") -> dict:
    fragment = str(fragment).strip()
    if not fragment or len(fragment) > 64:
        raise ValueError("fragment rituel invalide")
    ritual_status(state)
    data = _root(state)["ritual"]
    signature = hashlib.sha256((data["id"] + ":" + fragment).encode()).hexdigest()[:20]
    if signature not in data["fragments"]:
        data["fragments"].append(signature)
    if contributor and contributor not in data["contributors"]:
        data["contributors"].append(str(contributor)[:40])
    result = ritual_status(state, data["id"])
    result["signature"] = signature
    return result


def export_ritual(state: dict, destination: Path) -> Path:
    payload = {"format": "doot-ritual-v1", **ritual_status(state)}
    envelope = {"payload": payload, "sha256": _checksum(payload)}
    destination = Path(destination)
    if destination.suffix.casefold() != ".dootritual":
        destination = destination / f"ritual-{payload['id']}.dootritual"
    return _atomic_text(destination, json.dumps(envelope, ensure_ascii=False, indent=2))


def import_ritual(state: dict, source: Path) -> dict:
    try:
        source = Path(source)
        if not source.is_file() or source.stat().st_size > 1024 * 1024:
            raise ValueError
        envelope = json.loads(source.read_text(encoding="utf-8"))
        payload = envelope["payload"]
        if envelope.get("sha256") != _checksum(payload) or payload.get("format") != "doot-ritual-v1":
            raise ValueError
        fragments = payload.get("fragments")
        contributors = payload.get("contributors")
        if (not isinstance(fragments, list) or len(fragments) > 256 or
                not all(isinstance(item, str) and len(item) == 20 and
                        all(char in "0123456789abcdef" for char in item)
                        for item in fragments) or
                not isinstance(contributors, list) or len(contributors) > 256 or
                not all(isinstance(item, str) and len(item) <= 40 for item in contributors)):
            raise ValueError
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("capsule rituelle invalide") from exc
    local = ritual_status(state, str(payload.get("id", "")))
    data = _root(state)["ritual"]
    data["fragments"] = sorted(set(local["fragments"]) | set(payload.get("fragments", [])))
    data["contributors"] = sorted(set(local["contributors"]) | set(payload.get("contributors", [])))
    return ritual_status(state, data["id"])


INVASION_ACTIONS = ("fortifier", "contre-attaque", "ruse")


def nemesis_invasion_status(state: dict, seed: str = "") -> dict:
    data = _root(state).get("nemesis_invasion")
    if (not isinstance(data, dict) or
            (seed and (data.get("seed") != seed or data.get("completed")))):
        rng = random.Random("siege:" + (seed or date.today().isoformat()))
        data = {"seed": seed or date.today().isoformat(), "phase": 0, "city_hp": 12,
                "weaknesses": [rng.choice(INVASION_ACTIONS) for _ in range(3)],
                "completed": False, "repelled": False, "history": []}
        _root(state)["nemesis_invasion"] = data
    result = dict(data)
    result.pop("weaknesses", None)
    result["active"] = not bool(data.get("completed"))
    return result


def defend_nemesis_invasion(state: dict, action: str) -> dict:
    nemesis_invasion_status(state)
    data = _root(state)["nemesis_invasion"]
    if data.get("completed"):
        raise ValueError("le siege est termine")
    action = str(action).strip().casefold()
    if action not in INVASION_ACTIONS:
        raise ValueError("action attendue : " + ", ".join(INVASION_ACTIONS))
    phase = int(data.get("phase", 0))
    counter = action == data["weaknesses"][phase]
    damage = 0 if counter else 2 + phase
    data["city_hp"] = max(0, int(data["city_hp"]) - damage)
    data["history"].append({"phase": phase + 1, "action": action,
                            "counter": counter, "damage": damage})
    data["phase"] = phase + 1
    if data["city_hp"] <= 0 or data["phase"] >= len(data["weaknesses"]):
        data["completed"] = True
        data["repelled"] = data["city_hp"] > 0 and data["phase"] >= len(data["weaknesses"])
    return nemesis_invasion_status(state)


# ------------------------------------------------ tribunal / heritage NG+ --

TRIBUNAL_CASES = (
    ("Le dernier billet", "controleuse", "innocent", ("ticket intact", "horloge arretee")),
    ("Le concert vole", "cantatrice", "coupable", ("partition brulee", "echo inverse")),
    ("La couronne vide", "roi-echo", "liberer", ("serment ancien", "trone sans ombre")),
)


def start_tribunal(state: dict, seed: str = "") -> dict:
    case = random.Random("tribunal:" + (seed or date.today().isoformat())).choice(TRIBUNAL_CASES)
    _root(state)["tribunal"] = {"title": case[0], "accused": case[1], "truth": case[2],
                                "clues": list(case[3]), "found": [], "verdict": "",
                                "just": False}
    return tribunal_status(state)


def tribunal_status(state: dict) -> dict:
    data = _root(state).get("tribunal")
    if not isinstance(data, dict):
        return {"active": False}
    return {"active": not bool(data.get("verdict")), "title": data["title"],
            "accused": data["accused"], "found": list(data.get("found", [])),
            "remaining": len(data.get("clues", [])) - len(data.get("found", [])),
            "verdict": data.get("verdict", ""), "just": bool(data.get("just")),
            "consequence": data.get("consequence", "")}


def tribunal_action(state: dict, action: str) -> dict:
    data = _root(state).get("tribunal")
    if not isinstance(data, dict) or data.get("verdict"):
        raise ValueError("aucune audience active")
    action = str(action).strip().casefold()
    if action == "examiner":
        if len(data["found"]) < len(data["clues"]):
            data["found"].append(data["clues"][len(data["found"])])
    elif action.startswith("juger:"):
        verdict = action.split(":", 1)[1]
        if verdict not in ("innocent", "coupable", "liberer"):
            raise ValueError("verdict attendu : innocent, coupable ou liberer")
        data["verdict"] = verdict
        data["just"] = verdict == data["truth"]
        from . import wave4
        if data["just"]:
            wave4.city_status(state)
            state["wave4"]["city"]["bones"] += 2
            data["consequence"] = "la Cite des Os recoit deux os de justice"
        else:
            wave4.nemesis_status(state)
            state["wave4"]["nemesis"]["grudge"] += 1
            data["consequence"] = "la Nemesis gagne un rang de rancune"
    else:
        raise ValueError("action attendue : examiner ou juger:VERDICT")
    return tribunal_status(state)


LEGACIES = {
    "clemence": "Les anciens ennemis se souviennent d'avoir ete epargnes.",
    "gloire": "Les boss nomment tes victoires avant le combat.",
    "memoire": "Les dialogues parlent directement des boucles precedentes.",
}

LEGACY_DIALOGUES = {
    "clemence": "Je me souviens de ta main ouverte, dit l'ancien rival.",
    "gloire": "La fanfare joue ton nom avant meme ton entree.",
    "memoire": "Nous avons deja eu cette conversation, murmure la crypte.",
}


def choose_legacy(state: dict, legacy: str) -> dict:
    level = state.get("wave3", {}).get("new_game_plus", 0)
    if not isinstance(level, int) or isinstance(level, bool) or level < 1:
        raise ValueError("commence d'abord une Nouvelle Partie +")
    legacy = str(legacy).strip().casefold()
    if legacy not in LEGACIES:
        raise ValueError("heritage attendu : " + ", ".join(LEGACIES))
    data = _root(state).get("legacy")
    if not isinstance(data, dict):
        data = {"choices": [], "level": level}
        _root(state)["legacy"] = data
    if legacy not in data["choices"]:
        data["choices"].append(legacy)
    data["level"] = level
    return {"level": level, "choice": legacy, "effect": LEGACIES[legacy],
            "dialogue": LEGACY_DIALOGUES[legacy],
            "choices": list(data["choices"])}


# ------------------------------------------------------- campagne / musee --

def validate_campaign(source: Path) -> dict:
    try:
        source = Path(source)
        if not source.is_file() or source.stat().st_size > 2 * 1024 * 1024:
            raise ValueError
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("campagne illisible") from exc
    issues = []
    chapters = payload.get("chapters")
    if payload.get("format") != "doot-campaign-v1" or not isinstance(chapters, list):
        issues.append("format doot-campaign-v1 attendu")
        chapters = []
    ids = [str(item.get("id", "")) for item in chapters if isinstance(item, dict)]
    if not ids or any(not item for item in ids) or len(set(ids)) != len(ids):
        issues.append("identifiants de chapitres absents ou dupliques")
    targets = set(ids) | {"fin"}
    for chapter in chapters:
        if not isinstance(chapter, dict):
            issues.append("chapitre invalide")
            continue
        for choice in chapter.get("choices", []):
            target = str(choice).split(":", 1)[-1].strip()
            if target not in targets:
                issues.append(f"cible inconnue : {target}")
        if "music" in chapter and not isinstance(chapter.get("music"), str):
            issues.append("musique de chapitre invalide")
        if "riddle" in chapter and not isinstance(chapter.get("riddle"), dict):
            issues.append("enigme de chapitre invalide")
        if "achievement" in chapter and not isinstance(chapter.get("achievement"), str):
            issues.append("succes de chapitre invalide")
    return {"valid": not issues, "chapters": len(chapters), "issues": sorted(set(issues)),
            "sha256": hashlib.sha256(Path(source).read_bytes()).hexdigest()}


def campaign_lab(destination: Path) -> Path:
    destination = Path(destination)
    if destination.suffix.casefold() != ".html":
        destination = destination / "doot-campaign-lab.html"
    source = """<!doctype html><meta charset=utf-8><title>Laboratoire de campagne Doot</title>
<style>body{margin:0;background:#09060f;color:#f5efff;font:16px system-ui}main{max-width:1000px;margin:auto;padding:28px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}.card{background:#171022;border:1px solid #76508f;border-radius:14px;padding:14px}textarea,input{box-sizing:border-box;width:100%;background:#0b0711;color:white;border:1px solid #604477;border-radius:7px;padding:8px;margin:5px 0}button{background:#9b5de5;color:white;border:0;border-radius:8px;padding:10px;margin:5px}</style>
<main><h1>Laboratoire de campagne</h1><div class=grid><section class=card><input id=id value=appel><input id=title value="L'appel"><textarea id=text>Une note vient de la dalle.</textarea><input id=choices value="ecouter:fin" placeholder="choix:cible"><input id=music value="spooky-scary-skeletons" placeholder="musique"><input id=riddle placeholder="reponse de l'enigme"><input id=achievement placeholder="succes optionnel"><button onclick=add()>Ajouter</button><button onclick=save()>Exporter</button></section><section class=card><h2>Graphe</h2><ol id=graph></ol><p id=check></p></section></div></main><script>const d=[];function add(){d.push({id:id.value,title:title.value,text:text.value,scene:'crypte',choices:choices.value.split(',').map(x=>x.trim()).filter(Boolean),music:music.value,riddle:riddle.value?{answer:riddle.value}:undefined,achievement:achievement.value});draw()}function draw(){graph.innerHTML=d.map(x=>`<li><b>${x.id}</b> → ${x.choices.join(', ')} · ${x.music}</li>`).join('');const ids=new Set(d.map(x=>x.id));const bad=d.flatMap(x=>x.choices.map(c=>c.split(':').pop())).filter(x=>x!='fin'&&!ids.has(x));check.textContent=bad.length?'Cibles inconnues : '+bad.join(', '):'Graphe coherent.'}function save(){const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify({format:'doot-campaign-v1',chapters:d},null,2)],{type:'application/json'}));a.download='campagne-doot.json';a.click()}</script>"""
    return _atomic_text(destination, source)


def museum_gallery(state: dict, catalogue, destination: Path) -> Path:
    unlocked = state.get("succes") if isinstance(state.get("succes"), dict) else {}
    exhibits = []
    for item in catalogue:
        if item.identifiant in unlocked:
            exhibits.append({"title": item.titre, "points": item.points,
                             "badge": f"success/{item.identifiant}.png"})
    forged = _root(state).get("forged_relics")
    forged = forged if isinstance(forged, list) else []
    wave4 = state.get("wave4") if isinstance(state.get("wave4"), dict) else {}
    curiosities = []
    if isinstance(wave4.get("last_photo"), dict):
        curiosities.append({"name": "Portrait du photomaton", "detail": wave4["last_photo"].get("pose", "doot")})
    if isinstance(wave4.get("mirror_boss"), dict):
        curiosities.append({"name": "Trophee du miroir", "detail": wave4["mirror_boss"].get("name", "Reflet")})
    if isinstance(wave4.get("nemesis"), dict):
        curiosities.append({"name": "Cicatrices de Nemesis", "detail": ", ".join(wave4["nemesis"].get("scars", [])) or "aucune"})
    if isinstance(wave4.get("glyphs"), list):
        curiosities.append({"name": "Tablette des glyphes", "detail": f"{len(wave4['glyphs'])} signes"})
    payload = json.dumps({"achievements": exhibits, "relics": forged,
                          "bestiary": bestiary_status(state)["found"],
                          "curiosities": curiosities}, ensure_ascii=False).replace("</", "<\\/")
    destination = Path(destination)
    if destination.suffix.casefold() != ".html":
        destination = destination / "doot-museum.html"
    source = f"""<!doctype html><meta charset=utf-8><title>Musee personnel Doot</title>
<style>body{{margin:0;background:radial-gradient(circle,#261638,#07040b);color:#f8f1ff;font:16px system-ui}}main{{max-width:1050px;margin:auto;padding:30px}}#rooms{{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:14px}}article{{background:#160e20;border:1px solid #8963a3;border-radius:16px;padding:16px;animation:float 4s ease-in-out infinite alternate}}article:nth-child(2n){{animation-delay:-2s}}h1,h2{{color:#f2d06b}}@keyframes float{{to{{transform:translateY(-6px);box-shadow:0 10px 28px #9b5de544}}}}</style><main><h1>Musee personnel</h1><p id=count></p><div id=rooms></div></main><script>const d={payload};const cards=[...d.achievements.map(x=>({{t:x.title,s:x.points+' points'}})),...d.relics.map(x=>({{t:x.name,s:x.boon+' / '+x.curse}})),...d.bestiary.map(x=>({{t:x,s:'Bestiaire'}})),...d.curiosities.map(x=>({{t:x.name,s:x.detail}}))];count.textContent=cards.length+' pieces exposees';rooms.replaceChildren(...cards.map(x=>{{const a=document.createElement('article'),h=document.createElement('h2'),p=document.createElement('p');h.textContent=x.t;p.textContent=x.s;a.append(h,p);return a}}))</script>"""
    return _atomic_text(destination, source)


# ------------------------------------------------------------ sept sceaux --

SEALS = {
    "chemin": ("Le sceau du chemin", "La route sure alterne avec le risque.", "gauche-droite-gauche", "catacombes"),
    "heure": ("Le sceau de l'heure", "Trois gestes fendent la meme nuit.", "ecouter-attendre-doot", "boucle"),
    "aile": ("Le sceau de l'aile", "L'oiseau garde la relique dans son oeil.", "corbeau", "familier"),
    "gueule": ("Le sceau de la gueule", "Une eclipse tient dans cette creature.", "mange-lune", "bestiaire"),
    "cendre": ("Le sceau de la forge", "Le premier feu survit sous ce nom.", "cendre", "forge"),
    "balance": ("Le sceau de la balance", "Le dernier billet ne condamne personne.", "innocent", "tribunal"),
    "echo": ("Le sceau de l'echo", "Deux souffles, puis laisse parler le vide.", "doot-doot-silence", "musique"),
}


def seal_status(state: dict) -> dict:
    found = _root(state).get("seals")
    if not isinstance(found, list):
        found = []
        _root(state)["seals"] = found
    entries = [{"id": key, "title": value[0], "hint": value[1], "source": value[3],
                "found": key in found} for key, value in SEALS.items()]
    return {"found": [key for key in SEALS if key in found], "total": len(SEALS),
            "complete": all(key in found for key in SEALS), "entries": entries}


def submit_seal(state: dict, seal: str, answer: str) -> dict:
    seal = str(seal).strip().casefold()
    answer = "-".join(str(answer).strip().casefold().split())
    if seal not in SEALS or answer != SEALS[seal][2]:
        raise ValueError("le sceau demeure ferme")
    seal_status(state)
    found = _root(state)["seals"]
    fresh = seal not in found
    if fresh:
        found.append(seal)
    result = seal_status(state)
    result.update({"seal": seal, "fresh": fresh,
                   "epilogue": "La huitieme porte apparait derriere le menu." if result["complete"] else ""})
    return result
