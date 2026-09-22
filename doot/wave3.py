"""Systemes de la vague 3 : aventures courtes, creation et jeu social local.

Tout l'etat de jeu vit dans ``state.json``.  Les exports (HTML, GIF, packs et
capsules chiffrees) restent autonomes afin que Doot ne depende d'aucun serveur.
"""

from __future__ import annotations

import json
import os
import random
import shutil
import struct
import wave
import zipfile
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path


def _root(state: dict) -> dict:
    value = state.get("wave3")
    if not isinstance(value, dict):
        value = {}
        state["wave3"] = value
    return value


# ------------------------------------------------------------- expeditions --

ROOM_KINDS = (
    ("ossuaire", "L'ossuaire mouvant", "Des os recomposent le chemin."),
    ("orgue", "L'orgue sans poumons", "Une note tient depuis trois siecles."),
    ("miroir", "La galerie des reflets", "Ton squelette prend une mesure d'avance."),
    ("crypte", "La crypte inondee", "Des bulles battent la noire mesure."),
    ("bal", "Le bal immobile", "Les danseurs attendent le contretemps."),
    ("cloche", "Le clocher enterre", "Chaque marche sonne faux, sauf une."),
    ("titan", "L'antichambre du titan", "Un enorme tibia barre la sortie."),
)


def expedition_rooms(seed: str, count: int = 7) -> list[dict]:
    """Construit une route reproductible, partageable par sa graine."""

    wanted = max(1, min(12, int(count)))
    rng = random.Random(str(seed))
    rooms = []
    for index in range(wanted):
        kind, title, text = rng.choice(ROOM_KINDS)
        rooms.append({
            "index": index,
            "kind": kind,
            "title": title,
            "text": text,
            "danger": rng.randint(1, 4) + (1 if index == wanted - 1 else 0),
            "reward": rng.choice(("echo", "os grave", "souffle", "relique")),
        })
    rooms[-1] = dict(rooms[-1], kind="boss", title="Le Gardien du dernier temps",
                     text="Sept salles de musique se taisent d'un coup.", danger=5,
                     reward="clef astrale")
    return rooms


def start_expedition(state: dict, seed: str = "") -> dict:
    seed = str(seed).strip() or date.today().isoformat()
    run = {
        "seed": seed, "rooms": expedition_rooms(seed), "room": 0, "hp": 12,
        "relics": [], "decisions": [], "completed": False, "won": False,
        "started_at": datetime.now().isoformat(timespec="seconds"),
    }
    _root(state)["expedition"] = run
    return expedition_status(state)


def expedition_status(state: dict) -> dict:
    run = _root(state).get("expedition")
    if not isinstance(run, dict):
        return {"active": False}
    result = dict(run)
    rooms = run.get("rooms", [])
    index = run.get("room", 0)
    result["active"] = not bool(run.get("completed"))
    result["current"] = rooms[index] if (isinstance(index, int) and
                                          isinstance(rooms, list) and
                                          0 <= index < len(rooms)) else None
    return result


def choose_expedition(state: dict, choice: str) -> dict:
    run = _root(state).get("expedition")
    if not isinstance(run, dict) or run.get("completed"):
        raise ValueError("aucune expedition active")
    choice = str(choice).strip().casefold()
    if choice not in ("prudence", "audace"):
        raise ValueError("choisis prudence ou audace")
    rooms = run.get("rooms")
    index = run.get("room")
    if not isinstance(rooms, list) or not isinstance(index, int) or index >= len(rooms):
        raise ValueError("l'expedition est illisible")
    room = rooms[index]
    danger = max(1, int(room.get("danger", 1)))
    # Le resultat ne depend pas de l'horloge : une route peut etre rejouee.
    roll = random.Random(f"{run.get('seed')}:{index}:{choice}").random()
    damage = 0
    if choice == "audace" and roll < min(.85, .22 + danger * .10):
        damage = max(1, danger - 1)
    elif choice == "prudence" and roll < .18:
        damage = 1
    run["hp"] = max(0, int(run.get("hp", 0)) - damage)
    decisions = run.get("decisions") if isinstance(run.get("decisions"), list) else []
    decisions.append({"room": index, "choice": choice, "damage": damage})
    run["decisions"] = decisions
    relics = run.get("relics") if isinstance(run.get("relics"), list) else []
    if choice == "audace" or damage == 0:
        relics.append(str(room.get("reward", "echo")))
    run["relics"] = relics
    run["room"] = index + 1
    if run["hp"] <= 0 or run["room"] >= len(rooms):
        run["completed"] = True
        run["won"] = run["hp"] > 0 and run["room"] >= len(rooms)
        run["completed_at"] = datetime.now().isoformat(timespec="seconds")
    return expedition_status(state)


# ---------------------------------------------------------- creator tools --

def _atomic_text(path: Path, content: str) -> Path:
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


def campaign_editor(destination: Path) -> Path:
    """Exporte un petit editeur visuel autonome qui telecharge son JSON."""

    destination = Path(destination)
    if destination.suffix.casefold() != ".html":
        destination = destination / "doot-campaign-editor.html"
    source = """<!doctype html><meta charset=utf-8><title>Doot — Editeur de campagne</title>
<style>body{margin:0;background:#090710;color:#f5efff;font:16px system-ui}main{max-width:980px;margin:auto;padding:32px}
h1{color:#d8b4fe}.node{background:#171124;border:1px solid #8b5cf6;border-radius:16px;padding:16px;margin:12px 0}
input,textarea{box-sizing:border-box;width:100%;margin:5px 0;padding:9px;background:#0c0912;color:white;border:1px solid #5b4777;border-radius:8px}
button{padding:10px 14px;margin:6px;border:0;border-radius:9px;background:#8b5cf6;color:white;font-weight:700}</style>
<main><h1>💀 Editeur de campagne</h1><p>Chapitres, dialogues, choix et fins multiples. Tout reste dans ce fichier.</p>
<div id=nodes></div><button onclick=add()>+ chapitre</button><button onclick=save()>Exporter le pack JSON</button></main>
<script>let data=[{id:'appel',title:"L'appel",text:'Une note vient de la dalle.',choices:'ecouter:procession,frapper:fin'}];
function draw(){nodes.innerHTML='';data.forEach((x,i)=>{let n=document.createElement('section');n.className='node';n.innerHTML=`<b>Chapitre ${i+1}</b><input value="${x.id}" data-k=id><input value="${x.title}" data-k=title><textarea data-k=text>${x.text}</textarea><input value="${x.choices}" data-k=choices placeholder="choix:cible, choix:cible"><button data-del>Retirer</button>`;n.querySelectorAll('[data-k]').forEach(e=>e.oninput=()=>x[e.dataset.k]=e.value);n.querySelector('[data-del]').onclick=()=>{data.splice(i,1);draw()};nodes.append(n)})}
function add(){data.push({id:'chapitre-'+(data.length+1),title:'Nouveau chapitre',text:'',choices:'continuer:fin'});draw()}
function save(){let out={format:'doot-campaign-v1',chapters:data.map(x=>({...x,choices:x.choices.split(',').map(v=>v.trim()).filter(Boolean)}))};let a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(out,null,2)],{type:'application/json'}));a.download='campagne-doot.json';a.click()}draw()</script>"""
    return _atomic_text(destination, source)


def campaign_pack(source: Path, destination: Path) -> Path:
    payload = json.loads(Path(source).read_text(encoding="utf-8"))
    if payload.get("format") != "doot-campaign-v1" or not isinstance(payload.get("chapters"), list):
        raise ValueError("format de campagne inconnu")
    destination = Path(destination)
    if destination.suffix.casefold() != ".dootpack":
        destination = destination / "campaign.dootpack"
    destination.parent.mkdir(parents=True, exist_ok=True)
    manifest = {"format": "doot-pack-v2", "kind": "campaign", "chapters": len(payload["chapters"])}
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, indent=2))
        archive.writestr("campaign.json", json.dumps(payload, ensure_ascii=False, indent=2))
    return destination


def boss_phase(boss: dict) -> dict:
    maximum = max(1, int(boss.get("max_hp", 1)))
    hp = max(0, int(boss.get("hp", maximum)))
    ratio = hp / maximum
    if ratio > .66:
        number, name, attack, counter = 1, "Marche des tibias", "pluie d'os", "wave"
    elif ratio > .33:
        number, name, attack, counter = 2, "Fanfare fracturee", "canon inverse", "duel"
    elif hp:
        number, name, attack, counter = 3, "Dernier souffle", "silence total", "vortex"
    else:
        number, name, attack, counter = 4, "Vaincu", "aucune", "aucun"
    return {"number": number, "name": name, "attack": attack, "counter": counter}


def constellation(state: dict, catalogue, destination: Path) -> Path:
    destination = Path(destination)
    if destination.suffix.casefold() != ".html":
        destination = destination / "doot-constellation.html"
    unlocked = state.get("succes", {})
    unlocked = unlocked if isinstance(unlocked, dict) else {}
    stars = []
    for index, item in enumerate(catalogue):
        known = item.identifiant in unlocked
        title = item.titre if (known or not item.secret) else "Etoile inconnue"
        stars.append({"id": item.identifiant, "title": title, "known": known,
                      "secret": item.secret, "points": item.points if known else 0,
                      "x": 8 + (index * 31) % 84, "y": 10 + (index * 47) % 80})
    payload = json.dumps(stars, ensure_ascii=False).replace("</", "<\\/")
    source = f"""<!doctype html><meta charset=utf-8><title>Constellation Doot</title>
<style>body{{margin:0;background:radial-gradient(circle,#20133a,#050309);color:white;font:15px system-ui;overflow:hidden}}
#sky{{height:100vh;position:relative}}.s{{position:absolute;transform:translate(-50%,-50%);font-size:26px;filter:drop-shadow(0 0 8px #c4b5fd);cursor:pointer}}
.off{{opacity:.24;filter:none}}#card{{position:fixed;left:20px;bottom:20px;background:#110b1ddd;border:1px solid #8b5cf6;padding:16px;border-radius:14px}}</style>
<div id=sky></div><div id=card>Choisis une etoile.</div><script>const stars={payload};for(const x of stars){{let e=document.createElement('button');e.className='s '+(x.known?'':'off');e.style.left=x.x+'%';e.style.top=x.y+'%';e.textContent=x.secret?'✦':'★';e.title=x.title;e.onclick=()=>card.textContent=x.title+(x.known?' — '+x.points+' points':' — verrouille');sky.append(e)}}</script>"""
    return _atomic_text(destination, source)


# -------------------------------------------------------- familiars/contracts --

@dataclass(frozen=True)
class Familiar:
    identifiant: str
    name: str
    talent: str


FAMILIARS = (
    Familiar("chauve_souris", "Mina la Chauve-souris", "repere les salles sures"),
    Familiar("corbeau", "Croasse-Mort", "double les echos trouves"),
    Familiar("crane", "Petit Cranium", "absorbe un point de degat"),
    Familiar("trompettiste", "Doot Junior", "prolonge les combos"),
)


def familiar_status(state: dict) -> dict:
    data = _root(state).get("familiar")
    if not isinstance(data, dict):
        data = {"id": FAMILIARS[0].identifiant, "bond": 0, "level": 1}
        _root(state)["familiar"] = data
    item = next((x for x in FAMILIARS if x.identifiant == data.get("id")), FAMILIARS[0])
    bond = max(0, int(data.get("bond", 0)))
    return {"id": item.identifiant, "name": item.name, "talent": item.talent,
            "bond": bond, "level": 1 + min(4, bond // 5)}


def set_familiar(state: dict, wanted: str) -> dict:
    item = next((x for x in FAMILIARS if x.identifiant == str(wanted).casefold()), None)
    if item is None:
        raise ValueError("familier inconnu")
    current = familiar_status(state)
    _root(state)["familiar"] = {"id": item.identifiant, "bond": current["bond"]}
    return familiar_status(state)


def bond_familiar(state: dict, activity: str) -> dict:
    if str(activity).casefold() not in ("doot", "melodie", "expedition", "rituel"):
        raise ValueError("activite attendue : doot, melodie, expedition ou rituel")
    familiar_status(state)
    data = _root(state)["familiar"]
    data["bond"] = max(0, int(data.get("bond", 0))) + 1
    data["last_activity"] = str(activity).casefold()
    return familiar_status(state)


def daily_contract(day: date | None = None) -> dict:
    day = day or date.today()
    rng = random.Random(f"doot-contract:{day.isoformat()}")
    kind, unit = rng.choice((("doots", "doots"), ("melodies", "melodies"),
                             ("rooms", "salles"), ("combos", "combos")))
    target = rng.choice((12, 16, 20, 24))
    return {"id": day.isoformat(), "kind": kind, "unit": unit, "target": target,
            "title": f"Pacte spectral : {target} {unit}"}


def contract_status(state: dict, day: date | None = None) -> dict:
    contract = daily_contract(day)
    data = _root(state).get("contract")
    if not isinstance(data, dict) or data.get("id") != contract["id"]:
        data = {"id": contract["id"], "progress": 0, "contributors": []}
        _root(state)["contract"] = data
    result = dict(contract)
    result.update({"progress": min(contract["target"], max(0, int(data.get("progress", 0)))),
                   "contributors": list(data.get("contributors", []))})
    result["completed"] = result["progress"] >= result["target"]
    return result


def add_contract_progress(state: dict, amount: int, contributor: str = "local") -> dict:
    if isinstance(amount, bool) or int(amount) < 1:
        raise ValueError("la contribution doit etre positive")
    contract_status(state)
    data = _root(state)["contract"]
    data["progress"] = int(data.get("progress", 0)) + min(1000, int(amount))
    people = data.get("contributors") if isinstance(data.get("contributors"), list) else []
    if contributor and contributor not in people:
        people.append(str(contributor)[:40])
    data["contributors"] = people
    return contract_status(state)


def contract_capsule(state: dict, destination: Path) -> Path:
    """Exporte le pacte en capsule Fernet authentifiee avec sa cle de transport."""

    from cryptography.fernet import Fernet

    key = Fernet.generate_key()
    payload = json.dumps(contract_status(state), ensure_ascii=False).encode("utf-8")
    capsule = {"format": "doot-contract-v1", "key": key.decode("ascii"),
               "token": Fernet(key).encrypt(payload).decode("ascii")}
    destination = Path(destination)
    if destination.suffix.casefold() != ".dootcontract":
        destination = destination / f"contract-{daily_contract()['id']}.dootcontract"
    return _atomic_text(destination, json.dumps(capsule, indent=2))


def join_contract(state: dict, source: Path) -> dict:
    from cryptography.fernet import Fernet, InvalidToken

    try:
        capsule = json.loads(Path(source).read_text(encoding="utf-8"))
        if capsule.get("format") != "doot-contract-v1":
            raise ValueError("capsule inconnue")
        remote = json.loads(Fernet(capsule["key"].encode("ascii")).decrypt(
            capsule["token"].encode("ascii")).decode("utf-8"))
    except (KeyError, TypeError, json.JSONDecodeError, InvalidToken) as exc:
        raise ValueError("capsule de contrat invalide") from exc
    local = contract_status(state)
    if remote.get("id") != local["id"]:
        raise ValueError("ce contrat appartient a un autre jour")
    data = _root(state)["contract"]
    data["progress"] = max(int(data.get("progress", 0)), int(remote.get("progress", 0)))
    data["contributors"] = sorted(set(data.get("contributors", [])) |
                                      set(remote.get("contributors", [])))
    return contract_status(state)


# --------------------------------------------------------------- DJ/ambience --

def dj_import(source: Path, destination: Path, slices: int = 8) -> Path:
    source = Path(source)
    if source.suffix.casefold() != ".wav" or not source.is_file():
        raise ValueError("Doot DJ accepte un fichier WAV")
    slices = max(2, min(32, int(slices)))
    try:
        with wave.open(str(source), "rb") as opened:
            duration = opened.getnframes() / max(1, opened.getframerate())
            channels = opened.getnchannels()
            rate = opened.getframerate()
    except (wave.Error, OSError) as exc:
        raise ValueError("WAV illisible") from exc
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / source.name
    if source.resolve() != target.resolve():
        shutil.copy2(source, target)
    metadata = {
        "format": "doot-dj-v1", "sample": target.name, "duration": duration,
        "channels": channels, "rate": rate,
        "slices": [round(duration * index / slices, 6) for index in range(slices)],
        "keys": list("azertyuqsdfghjkl")[:slices],
    }
    return _atomic_text(target.with_suffix(".dootdj.json"),
                        json.dumps(metadata, indent=2))


AMBIENCES = {
    "bougies": {"fog": .2, "rain": 0, "moon": .5, "silhouettes": 1, "oled": False},
    "orage": {"fog": .7, "rain": 1, "moon": .1, "silhouettes": 3, "oled": False},
    "lune": {"fog": .35, "rain": .1, "moon": 1, "silhouettes": 2, "oled": False},
    "oled": {"fog": 0, "rain": 0, "moon": .25, "silhouettes": 1, "oled": True},
}


def ambience(state: dict, preset: str | None = None) -> dict:
    if preset:
        preset = str(preset).casefold()
        if preset not in AMBIENCES:
            raise ValueError("ambiance inconnue : " + preset)
        _root(state)["ambience"] = {"preset": preset, **AMBIENCES[preset]}
    current = _root(state).get("ambience")
    if not isinstance(current, dict):
        current = {"preset": "bougies", **AMBIENCES["bougies"]}
    return dict(current)


# --------------------------------------------------------- replay GIF/hunt --

def _packed_codes(codes: list[int], width: int = 3) -> bytes:
    value = 0
    bits = 0
    output = bytearray()
    for code in codes:
        value |= int(code) << bits
        bits += width
        while bits >= 8:
            output.append(value & 255)
            value >>= 8
            bits -= 8
    if bits:
        output.append(value & 255)
    return bytes(output)


def _gif_frame(width: int, height: int, phase: int) -> bytes:
    pixels = []
    for y in range(height):
        for x in range(width):
            horn = abs((x - phase * 4) - (y // 3 + 38)) < 3 and 28 < y < 66
            skull = (x - 38) ** 2 + (y - 40) ** 2 < 18 ** 2
            eyes = ((x - 32) ** 2 + (y - 38) ** 2 < 12 or
                    (x - 44) ** 2 + (y - 38) ** 2 < 12)
            pixel = 3 if horn else (1 if skull and not eyes else (2 if eyes else 0))
            pixels.append(pixel)
    # Un clear code entre chaque pixel garde la largeur a trois bits.
    compressed = _packed_codes([code for pixel in pixels for code in (4, pixel)] + [5])
    blocks = b"".join(bytes((len(compressed[i:i + 255]),)) + compressed[i:i + 255]
                      for i in range(0, len(compressed), 255)) + b"\x00"
    descriptor = b"\x2c" + struct.pack("<HHHHB", 0, 0, width, height, 0)
    return b"\x21\xf9\x04\x04\x0c\x00\x00\x00" + descriptor + b"\x02" + blocks


def replay_gif(entries: list[dict], destination: Path) -> Path:
    destination = Path(destination)
    if destination.suffix.casefold() != ".gif":
        destination = destination / "doot-replay.gif"
    destination.parent.mkdir(parents=True, exist_ok=True)
    width = height = 96
    palette = bytes((5, 3, 9, 239, 231, 255, 75, 53, 92, 248, 190, 72)) + bytes(756)
    header = b"GIF89a" + struct.pack("<HHBBB", width, height, 0xF7, 0, 0) + palette
    loop = b"\x21\xff\x0bNETSCAPE2.0\x03\x01\x00\x00\x00"
    count = max(2, min(8, len(entries) or 3))
    body = b"".join(_gif_frame(width, height, index) for index in range(count))
    destination.write_bytes(header + loop + body + b"\x3b")
    return destination


HUNT_CODES = (
    ("ECHO", "La premiere relique d'une expedition te le souffle."),
    ("DOUZE", "Le cadran secret compte un coup de plus."),
    ("MIROIR", "Un duel inverse sait le lire."),
    ("ASTRE", "La constellation cache son nom dans les etoiles."),
    ("FINALE", "La Nuit infinie n'est pas vraiment sans fin."),
)


def hunt_status(state: dict) -> list[dict]:
    found = _root(state).get("hunt_codes")
    found = found if isinstance(found, list) else []
    return [{"found": code in found, "code": code if code in found else "????",
             "hint": hint} for code, hint in HUNT_CODES]


def submit_code(state: dict, code: str) -> dict:
    code = str(code).strip().upper()
    known = {item[0] for item in HUNT_CODES}
    if code not in known:
        raise ValueError("ce symbole ne repond pas")
    found = _root(state).get("hunt_codes")
    if not isinstance(found, list):
        found = []
    fresh = code not in found
    if fresh:
        found.append(code)
    _root(state)["hunt_codes"] = found
    return {"code": code, "fresh": fresh, "completed": len(set(found) & known) == len(known)}


def new_game_plus(state: dict) -> int:
    adventure = state.get("adventure")
    if not isinstance(adventure, dict) or not adventure.get("completed_at"):
        raise ValueError("termine d'abord la campagne")
    count = max(0, int(_root(state).get("new_game_plus", 0))) + 1
    # On preserve les boss, duels, personnalites et le musee ; seule l'histoire repart.
    adventure.pop("chapter", None)
    adventure.pop("path", None)
    adventure.pop("completed_at", None)
    _root(state)["new_game_plus"] = count
    return count


# ------------------------------------------------------- character/radio/coop --

def save_character(directory: Path, name: str, skull: str = "classique",
                   costume: str = "cape", instrument: str = "trompette",
                   voice: str = "doot", line: str = "En mesure, les vivants !") -> Path:
    name = str(name).strip()
    if not name or len(name) > 40:
        raise ValueError("nom de personnage attendu (40 caracteres maximum)")
    safe = "".join(ch.casefold() if ch.isalnum() else "-" for ch in name).strip("-") or "squelette"
    payload = {"format": "doot-character-v1", "name": name, "skull": str(skull)[:30],
               "costume": str(costume)[:30], "instrument": str(instrument)[:30],
               "voice": str(voice)[:30], "line": str(line)[:120]}
    return _atomic_text(Path(directory) / f"{safe}.json",
                        json.dumps(payload, ensure_ascii=False, indent=2))


def characters(directory: Path) -> list[dict]:
    output = []
    for path in sorted(Path(directory).glob("*.json")) if Path(directory).is_dir() else []:
        try:
            item = json.loads(path.read_text(encoding="utf-8"))
            if item.get("format") == "doot-character-v1":
                item["path"] = str(path)
                output.append(item)
        except (OSError, json.JSONDecodeError):
            pass
    return output


def character_pack(character_path: Path, destination: Path) -> Path:
    item = json.loads(Path(character_path).read_text(encoding="utf-8"))
    if item.get("format") != "doot-character-v1":
        raise ValueError("personnage illisible")
    destination = Path(destination)
    if destination.suffix.casefold() != ".dootpack":
        destination = destination / (Path(character_path).stem + ".dootpack")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps({"format": "doot-pack-v2", "kind": "character",
                                                       "name": item["name"]}, indent=2))
        archive.writestr("character.json", json.dumps(item, ensure_ascii=False, indent=2))
    return destination


def radio_schedule(seed: str = "", day: date | None = None) -> list[dict]:
    day = day or date.today()
    seed = str(seed).strip() or day.isoformat()
    rng = random.Random("crypt-radio:" + seed)
    shows = [
        ("00:00", "Les douze coups", "macabre"),
        ("07:06", "Matinale des morts", "chiptune"),
        ("13:13", "Jazz de l'ossuaire", "jazz"),
        ("18:00", "Expedition en direct", "epique"),
        ("23:00", "Nuit infinie", "chaos"),
    ]
    rng.shuffle(shows)
    return [{"at": at, "title": title, "style": style} for at, title, style in
            sorted(shows, key=lambda item: item[0])]


def coop_action(state: dict, action: str) -> dict:
    action = str(action).strip().casefold()
    data = _root(state).get("coop")
    if action == "start" or not isinstance(data, dict):
        data = {"turn": "musique", "score": 0, "streak": 0, "actions": []}
        _root(state)["coop"] = data
        if action == "start":
            return dict(data)
    expected = data.get("turn", "musique")
    if action not in ("musique", "scene"):
        raise ValueError("action coop attendue : start, musique ou scene")
    if action == expected:
        data["score"] = int(data.get("score", 0)) + 1
        data["streak"] = int(data.get("streak", 0)) + 1
        data["turn"] = "scene" if expected == "musique" else "musique"
    else:
        data["streak"] = 0
    actions = data.get("actions") if isinstance(data.get("actions"), list) else []
    actions.append(action)
    data["actions"] = actions[-20:]
    return dict(data)


def endless_night(state: dict, seed: str = "") -> dict:
    """Lance ou avance le grand mode qui relie les systemes de la vague 3."""

    root = _root(state)
    data = root.get("endless_night")
    if not isinstance(data, dict) or data.get("completed"):
        seed = str(seed).strip() or date.today().isoformat()
        data = {"seed": seed, "act": 1, "energy": 6, "completed": False,
                "started_at": datetime.now().isoformat(timespec="seconds")}
        root["endless_night"] = data
        ambience(state, "orage")
        start_expedition(state, "nuit:" + seed)
        return dict(data)
    data["act"] = int(data.get("act", 1)) + 1
    data["energy"] = max(0, int(data.get("energy", 0)) - 1)
    if data["act"] >= 6:
        data["completed"] = True
        data["completed_at"] = datetime.now().isoformat(timespec="seconds")
    return dict(data)
