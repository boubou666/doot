"""Vague 4 : une metagame persistante, creative et entierement locale.

Les fonctions transforment un dictionnaire d'etat ou produisent des exports
autonomes. Aucune ne contacte un service distant : courses fantomes, atelier,
telecommande et outils de creation restent utilisables hors ligne.
"""

from __future__ import annotations

import hashlib
import html
import json
import os
import random
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import zipfile
from datetime import date, datetime
from pathlib import Path, PurePosixPath
from urllib.parse import parse_qs, urlparse

from . import png


def _root(state: dict) -> dict:
    value = state.get("wave4")
    if not isinstance(value, dict):
        value = {}
        state["wave4"] = value
    return value


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


# ---------------------------------------------------------- cite / reliques --

BUILDINGS = {
    "crypte": ("Crypte centrale", "augmente la reserve d'os"),
    "scene": ("Scene des revenants", "renforce les combos"),
    "atelier": ("Atelier interdit", "ameliore les reliques"),
    "musee": ("Musee des nuits", "revele les constellations"),
    "radio": ("Tour Radio-Crypte", "amplifie la musique adaptative"),
}


def city_status(state: dict) -> dict:
    city = _root(state).get("city")
    if not isinstance(city, dict):
        city = {"name": "La Cite des Os", "bones": 12, "buildings": {}}
        _root(state)["city"] = city
    levels = city.get("buildings") if isinstance(city.get("buildings"), dict) else {}
    city["buildings"] = {key: max(0, min(5, int(levels.get(key, 0)))) for key in BUILDINGS}
    city["bones"] = max(0, int(city.get("bones", 0)))
    return {
        "name": city.get("name", "La Cite des Os"),
        "bones": city["bones"],
        "level": sum(city["buildings"].values()),
        "buildings": [
            {"id": key, "name": value[0], "effect": value[1],
             "level": city["buildings"][key], "cost": city["buildings"][key] + 2}
            for key, value in BUILDINGS.items()
        ],
    }


def develop_city(state: dict, building: str) -> dict:
    building = str(building).casefold().strip()
    if building not in BUILDINGS:
        raise ValueError("batiment inconnu : " + building)
    status = city_status(state)
    city = _root(state)["city"]
    current = city["buildings"][building]
    if current >= 5:
        raise ValueError("ce batiment est deja au niveau maximal")
    cost = current + 2
    if city["bones"] < cost:
        raise ValueError(f"il faut {cost} os, la cite n'en possede que {city['bones']}")
    city["bones"] -= cost
    city["buildings"][building] = current + 1
    return city_status(state)


RELICS = {
    "metronome_fendu": ("Metronome fendu", "combo", 2),
    "tibia_dore": ("Tibia dore", "bones", 3),
    "souffle_en_bocal": ("Souffle en bocal", "music", 2),
    "miroir_de_poche": ("Miroir de poche", "dodge", 1),
    "antenne_spectrale": ("Antenne spectrale", "radio", 2),
    "clef_de_suie": ("Clef de suie", "secrets", 1),
}


def reliquary(state: dict) -> dict:
    data = _root(state).get("relics")
    if not isinstance(data, dict):
        data = {"owned": ["metronome_fendu", "tibia_dore"], "equipped": []}
        _root(state)["relics"] = data
    owned = [key for key in dict.fromkeys(data.get("owned", [])) if key in RELICS]
    equipped = [key for key in dict.fromkeys(data.get("equipped", [])) if key in owned][:3]
    data.update({"owned": owned, "equipped": equipped})
    return {
        "slots": 3, "equipped": equipped,
        "items": [{"id": key, "name": RELICS[key][0], "effect": RELICS[key][1],
                   "power": RELICS[key][2], "owned": key in owned,
                   "equipped": key in equipped} for key in RELICS],
        "build": {RELICS[key][1]: RELICS[key][2] for key in equipped},
    }


def equip_relic(state: dict, relic: str) -> dict:
    status = reliquary(state)
    relic = str(relic).casefold().strip()
    if relic not in RELICS:
        raise ValueError("relique inconnue : " + relic)
    data = _root(state)["relics"]
    if relic not in data["owned"]:
        raise ValueError("cette relique n'a pas encore ete trouvee")
    equipped = list(data["equipped"])
    if relic in equipped:
        equipped.remove(relic)
    else:
        if len(equipped) >= status["slots"]:
            equipped.pop(0)
        equipped.append(relic)
    data["equipped"] = equipped
    return reliquary(state)


# ------------------------------------------------------ factions / nemesis --

FACTIONS = {
    "airain": ("Fanfare d'Airain", "La puissance et les cuivres impossibles."),
    "silence": ("Ordre du Silence", "Le rythme cache entre deux notes."),
    "cranes": ("Ligue des Cranes", "L'entraide, les jeux et les tres mauvais calembours."),
}


def faction_status(state: dict) -> dict:
    data = _root(state).get("factions")
    if not isinstance(data, dict):
        data = {"pledge": "", "reputation": {key: 0 for key in FACTIONS}, "missions": 0}
        _root(state)["factions"] = data
    reputation = data.get("reputation") if isinstance(data.get("reputation"), dict) else {}
    data["reputation"] = {key: max(0, int(reputation.get(key, 0))) for key in FACTIONS}
    if data.get("pledge") not in FACTIONS:
        data["pledge"] = ""
    return {"pledge": data["pledge"], "missions": max(0, int(data.get("missions", 0))),
            "factions": [{"id": key, "name": value[0], "motto": value[1],
                           "reputation": data["reputation"][key]}
                          for key, value in FACTIONS.items()]}


def pledge_faction(state: dict, faction: str) -> dict:
    faction = str(faction).casefold().strip()
    if faction not in FACTIONS:
        raise ValueError("faction inconnue : " + faction)
    faction_status(state)
    _root(state)["factions"]["pledge"] = faction
    return faction_status(state)


def faction_mission(state: dict, seed: str = "") -> dict:
    status = faction_status(state)
    faction = status["pledge"]
    if not faction:
        raise ValueError("prete d'abord serment a une faction")
    data = _root(state)["factions"]
    index = int(data.get("missions", 0))
    rng = random.Random(f"{faction}:{seed or date.today().isoformat()}:{index}")
    verbs = ("escorter", "accorder", "retrouver", "defier", "ecouter")
    places = ("le clocher inverse", "le bal immobile", "la nef sans echo", "l'ossuaire bleu")
    gain = rng.randint(2, 5)
    data["missions"] = index + 1
    data["reputation"][faction] += gain
    city_status(state)
    _root(state)["city"]["bones"] += gain
    return {"faction": faction, "title": f"{rng.choice(verbs).title()} {rng.choice(places)}",
            "gain": gain, "reputation": data["reputation"][faction]}


NEMESIS_NAMES = ("Baron Fracas", "Maestro Sans-Visage", "Dame Contretemps", "Le Grand Radius")
WEAKNESSES = ("canon", "wave", "vortex", "duel")


def nemesis_status(state: dict, seed: str = "") -> dict:
    data = _root(state).get("nemesis")
    if not isinstance(data, dict):
        rng = random.Random(seed or "premiere-rancune")
        maximum = rng.randint(18, 26)
        data = {"name": rng.choice(NEMESIS_NAMES), "weakness": rng.choice(WEAKNESSES),
                "hp": maximum, "max_hp": maximum, "grudge": 0, "scars": [], "defeated": False}
        _root(state)["nemesis"] = data
    return dict(data)


def confront_nemesis(state: dict, formation: str) -> dict:
    formation = str(formation).casefold().strip()
    if formation not in WEAKNESSES:
        raise ValueError("formation attendue : " + ", ".join(WEAKNESSES))
    data = _root(state).setdefault("nemesis", nemesis_status(state))
    if data.get("defeated"):
        data["grudge"] = int(data.get("grudge", 0)) + 1
        data["max_hp"] = int(data.get("max_hp", 20)) + 6
        data["hp"] = data["max_hp"]
        data["weakness"] = WEAKNESSES[(WEAKNESSES.index(data["weakness"]) + 1) % len(WEAKNESSES)]
        data["defeated"] = False
    damage = 7 if formation == data["weakness"] else 2
    data["hp"] = max(0, int(data["hp"]) - damage)
    if data["hp"] == 0:
        data["defeated"] = True
        scar = f"fissure-{formation}"
        if scar not in data["scars"]:
            data["scars"].append(scar)
    result = dict(data)
    result.update({"damage": damage, "counter": formation == data["weakness"]})
    return result


# ------------------------------------------------ investigations / fantomes --

CASES = (
    ("La Loge aux treize miroirs", "le chef d'orchestre", ("suie", "contretemps", "reflet")),
    ("Le Tramway sans terminus", "la controleuse spectrale", ("ticket", "givre", "cloche")),
    ("L'Opera aux fauteuils vides", "la cantatrice muette", ("velours", "souffle", "clef")),
)


def start_investigation(state: dict, seed: str = "") -> dict:
    rng = random.Random(seed or date.today().isoformat())
    title, culprit, clues = rng.choice(CASES)
    suspects = [culprit, "le fossoyeur", "l'enfant au masque"]
    rng.shuffle(suspects)
    data = {"seed": seed or date.today().isoformat(), "title": title, "culprit": culprit,
            "clues": list(clues), "found": [], "suspects": suspects, "solved": False,
            "attempts": 0}
    _root(state)["investigation"] = data
    return investigation_status(state)


def investigation_status(state: dict) -> dict:
    data = _root(state).get("investigation")
    if not isinstance(data, dict):
        return {"active": False}
    result = {key: value for key, value in data.items() if key != "culprit"}
    result["active"] = not bool(data.get("solved"))
    result["remaining"] = len(data.get("clues", [])) - len(data.get("found", []))
    return result


def investigate(state: dict, action: str) -> dict:
    data = _root(state).get("investigation")
    if not isinstance(data, dict):
        raise ValueError("aucune enquete active")
    action = str(action).strip().casefold()
    if action.startswith("accuser:"):
        suspect = action.split(":", 1)[1].strip()
        data["attempts"] += 1
        data["solved"] = suspect == str(data["culprit"]).casefold()
    elif action == "chercher":
        found = data["found"]
        if len(found) < len(data["clues"]):
            found.append(data["clues"][len(found)])
    else:
        raise ValueError("action attendue : chercher ou accuser:NOM")
    return investigation_status(state)


def _ghost_payload(run: dict) -> dict:
    return {"format": "doot-ghost-v1", "seed": str(run.get("seed", ""))[:80],
            "time_ms": max(1, int(run.get("time_ms", 1))),
            "decisions": [str(x)[:24] for x in run.get("decisions", [])][:64]}


def export_ghost(run: dict, destination: Path) -> Path:
    payload = _ghost_payload(run)
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    envelope = {"payload": payload, "sha256": hashlib.sha256(canonical.encode()).hexdigest()}
    destination = Path(destination)
    if destination.suffix.casefold() != ".dootghost":
        destination = destination / "course.dootghost"
    return _atomic_text(destination, json.dumps(envelope, ensure_ascii=False, indent=2))


def race_ghost(state: dict, source: Path, player_time_ms: int) -> dict:
    try:
        envelope = json.loads(Path(source).read_text(encoding="utf-8"))
        payload = envelope["payload"]
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        if envelope.get("sha256") != hashlib.sha256(canonical.encode()).hexdigest():
            raise ValueError("empreinte incorrecte")
        ghost = _ghost_payload(payload)
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("fantome de course invalide") from exc
    player = max(1, int(player_time_ms))
    won = player < ghost["time_ms"]
    data = _root(state).setdefault("ghost_races", {"races": 0, "wins": 0})
    data["races"] = int(data.get("races", 0)) + 1
    data["wins"] = int(data.get("wins", 0)) + int(won)
    return {"won": won, "player_time_ms": player, "ghost_time_ms": ghost["time_ms"],
            "delta_ms": abs(player - ghost["time_ms"]), **data}


# ------------------------------------------------------ musique / creation --

def adaptive_score(state: dict, danger: int = 0, combo: int = 0, boss: bool = False) -> dict:
    danger = max(0, min(10, int(danger)))
    combo = max(0, min(99, int(combo)))
    intensity = min(1.0, .08 * danger + .025 * combo + (.25 if boss else 0))
    stems = {"pulse": round(.25 + intensity * .75, 2),
             "bones": round(max(0, intensity - .18), 2),
             "choir": round(max(0, intensity - .48), 2),
             "brass": round(.2 + (.8 if boss else intensity * .4), 2)}
    result = {"intensity": round(intensity, 2), "tempo": 72 + round(intensity * 76),
              "key": "d-mineur" if danger < 7 else "triton", "stems": stems}
    _root(state)["adaptive_score"] = result
    return result


def director_studio(destination: Path) -> Path:
    destination = Path(destination)
    if destination.suffix.casefold() != ".html":
        destination = destination / "doot-director.html"
    source = """<!doctype html><meta charset=utf-8><title>Doot — Realisateur</title>
<style>body{margin:0;background:#08050d;color:#f4ecff;font:15px system-ui}main{max-width:980px;margin:auto;padding:28px}h1{color:#e9c46a}.grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}.card{background:#171022;border:1px solid #74508f;border-radius:14px;padding:14px}input,select,textarea{width:100%;box-sizing:border-box;background:#0d0913;color:white;border:1px solid #67487e;border-radius:7px;padding:8px;margin:5px 0}button{background:#9b5de5;color:white;border:0;border-radius:8px;padding:10px 14px;margin:5px}#stage{height:240px;background:radial-gradient(circle,#43305b,#09060e);display:grid;place-items:center;font-size:70px;border-radius:16px}</style>
<main><h1>☠ Mode Realisateur</h1><div class=grid><section class=card><label>Camera<select id=camera><option>travelling</option><option>fixe</option><option>contre-plongee</option></select></label><label>Lumieres<input id=lights value="violet, or, lune"></label><label>Dialogue<textarea id=line>Le silence a rate son entree.</textarea></label><button onclick=add()>Ajouter le plan</button><button onclick=play()>Jouer</button><button onclick=save()>Exporter le mini-film HTML</button></section><section id=stage>💀🎺</section></div><ol id=shots></ol></main>
<script>const data=[];function add(){data.push({camera:camera.value,lights:lights.value,line:line.value});draw()}function draw(){shots.innerHTML=data.map((x,i)=>`<li>Plan ${i+1} — ${x.camera} — ${x.lights}<br>${x.line}</li>`).join('')}function play(){let i=0;if(!data.length)return;stage.textContent=data[0].line;const t=setInterval(()=>{i++;if(i>=data.length){clearInterval(t);stage.textContent='💀🎺';return}stage.textContent=data[i].line},1600)}function save(){const payload=JSON.stringify(data).replaceAll('<','\\u003c');const film=`<!doctype html><meta charset=utf-8><title>Mini-film Doot</title><style>body{margin:0;background:#08050d;color:#f4ecff;display:grid;place-items:center;height:100vh;font:28px Georgia}#s{padding:10vw;text-align:center;text-shadow:0 0 18px #9b5de5}</style><div id=s>💀🎺</div><script>const d=${payload};let i=0;function n(){if(!d.length)return;s.textContent=d[i].line;s.style.color=i%2?'#e9c46a':'#d8b4fe';i=(i+1)%d.length}n();setInterval(n,1800)<\\/script>`;const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([film],{type:'text/html'}));a.download='mini-film-doot.html';a.click()}</script>"""
    return _atomic_text(destination, source)


def photo_booth(state: dict, destination: Path, pose: str = "doot") -> Path:
    """Fabrique un portrait pixel-art local sans capture du bureau."""
    width = height = 256
    bg = (18, 9, 28, 255)
    gold = (88, 192, 233, 255)  # BGRA
    bone = (237, 235, 219, 255)
    dark = (35, 20, 47, 255)
    pixels = bytearray(bg * (width * height))

    def fill(x0, y0, x1, y1, color):
        for y in range(max(0, y0), min(height, y1)):
            for x in range(max(0, x0), min(width, x1)):
                p = (y * width + x) * 4
                pixels[p:p + 4] = bytes(color)

    # Cadre, crane, yeux, corps et trompette volontairement francs en pixel art.
    fill(12, 12, 244, 20, gold); fill(12, 236, 244, 244, gold)
    fill(12, 20, 20, 236, gold); fill(236, 20, 244, 236, gold)
    fill(76, 45, 180, 125, bone); fill(90, 115, 166, 145, bone)
    fill(96, 73, 117, 94, dark); fill(139, 73, 160, 94, dark)
    fill(119, 94, 137, 112, dark); fill(112, 126, 144, 136, dark)
    fill(120, 145, 136, 216, bone); fill(80, 158, 176, 170, bone)
    fill(161, 150, 224, 161, gold); fill(211, 138, 230, 173, gold)
    pose_mark = sum(str(pose).encode("utf-8")) % 50
    fill(28 + pose_mark, 214, 58 + pose_mark, 222, gold)
    destination = Path(destination)
    if destination.suffix.casefold() != ".png":
        destination = destination / "doot-photo-booth.png"
    destination.parent.mkdir(parents=True, exist_ok=True)
    png.write_png(destination, png.Frame(width, height, bytes(pixels)))
    _root(state)["last_photo"] = {"path": str(destination), "pose": str(pose)[:40]}
    return destination


# ------------------------------------------------ telecommande / atelier --

def _gf_mul(x: int, y: int) -> int:
    result = 0
    for _ in range(8):
        if y & 1:
            result ^= x
        y >>= 1
        x = (x << 1) ^ (0x11D if x & 0x80 else 0)
    return result


def _reed_solomon(data: list[int], degree: int) -> list[int]:
    generator = [1]
    root = 1
    for _ in range(degree):
        nxt = [0] * (len(generator) + 1)
        for index, value in enumerate(generator):
            nxt[index] ^= value
            nxt[index + 1] ^= _gf_mul(value, root)
        generator = nxt
        root = _gf_mul(root, 2)
    result = list(data) + [0] * degree
    for index in range(len(data)):
        factor = result[index]
        if factor:
            for offset, value in enumerate(generator):
                result[index + offset] ^= _gf_mul(value, factor)
    return result[-degree:]


def _qr_matrix(text: str) -> list[list[bool]]:
    """Encode un QR version 5-L (octets), suffisant pour une URL locale."""
    raw = text.encode("utf-8")
    if len(raw) > 106:
        raise ValueError("adresse trop longue pour la carte d'appairage")
    bits = [0, 1, 0, 0] + [(len(raw) >> bit) & 1 for bit in range(7, -1, -1)]
    for byte in raw:
        bits.extend((byte >> bit) & 1 for bit in range(7, -1, -1))
    bits.extend([0] * min(4, 108 * 8 - len(bits)))
    bits.extend([0] * ((8 - len(bits) % 8) % 8))
    codewords = [sum(bits[i + j] << (7 - j) for j in range(8)) for i in range(0, len(bits), 8)]
    pads = (0xEC, 0x11)
    while len(codewords) < 108:
        codewords.append(pads[(len(codewords) - (len(bits) // 8)) % 2])
    codewords += _reed_solomon(codewords, 26)
    stream = [((byte >> bit) & 1) for byte in codewords for bit in range(7, -1, -1)]
    size = 37
    modules = [[False] * size for _ in range(size)]
    function = [[False] * size for _ in range(size)]

    def setm(row, col, value):
        if 0 <= row < size and 0 <= col < size:
            modules[row][col] = bool(value); function[row][col] = True

    def finder(top, left):
        for r in range(-1, 8):
            for c in range(-1, 8):
                inside = 0 <= r <= 6 and 0 <= c <= 6
                value = inside and (r in (0, 6) or c in (0, 6) or (2 <= r <= 4 and 2 <= c <= 4))
                setm(top + r, left + c, value)

    finder(0, 0); finder(0, size - 7); finder(size - 7, 0)
    for i in range(8, size - 8):
        setm(6, i, i % 2 == 0); setm(i, 6, i % 2 == 0)
    for r in range(-2, 3):
        for c in range(-2, 3):
            setm(30 + r, 30 + c, max(abs(r), abs(c)) != 1)
    for i in range(9):
        setm(8, i, False); setm(i, 8, False)
        setm(8, size - 1 - i, False); setm(size - 1 - i, 8, False)
    setm(size - 8, 8, True)
    index = 0
    upward = True
    col = size - 1
    while col > 0:
        if col == 6:
            col -= 1
        rows = range(size - 1, -1, -1) if upward else range(size)
        for row in rows:
            for current in (col, col - 1):
                if not function[row][current]:
                    value = stream[index] if index < len(stream) else 0
                    modules[row][current] = bool(value ^ ((row + current) % 2 == 0))
                    index += 1
        upward = not upward
        col -= 2
    fmt = 0x77C4
    for i in range(6): setm(i, 8, (fmt >> i) & 1)
    setm(7, 8, (fmt >> 6) & 1); setm(8, 8, (fmt >> 7) & 1); setm(8, 7, (fmt >> 8) & 1)
    for i in range(9, 15): setm(8, 14 - i, (fmt >> i) & 1)
    for i in range(8): setm(8, size - 1 - i, (fmt >> i) & 1)
    for i in range(8, 15): setm(size - 15 + i, 8, (fmt >> i) & 1)
    setm(size - 8, 8, True)
    return modules


def remote_card(host: str, port: int, destination: Path, token: str = "") -> dict:
    host = str(host).strip() or "127.0.0.1"
    port = max(1, min(65535, int(port)))
    token = token or secrets.token_urlsafe(9)
    url = f"http://{host}:{port}/?token={token}"
    matrix = _qr_matrix(url)
    cells = "".join(f'<rect x="{x + 4}" y="{y + 4}" width="1" height="1"/>'
                    for y, row in enumerate(matrix) for x, value in enumerate(row) if value)
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 45 45" shape-rendering="crispEdges">'
           f'<rect width="45" height="45" fill="white"/><g fill="#09050d">{cells}</g></svg>')
    page = f"""<!doctype html><meta charset=utf-8><title>Telecommande Doot</title>
<style>body{{background:#09050d;color:#f6edff;font:18px system-ui;text-align:center;padding:30px}}svg{{width:min(70vw,360px);border:12px solid white}}code{{color:#e9c46a}}</style>
<h1>☠ Telecommande locale</h1>{svg}<p>Scanne depuis le meme reseau.</p><code>{html.escape(url)}</code><p>Le jeton expire quand le serveur s'arrete.</p>"""
    destination = Path(destination)
    if destination.suffix.casefold() != ".html":
        destination = destination / "doot-remote.html"
    _atomic_text(destination, page)
    return {"path": destination, "url": url, "token": token}


REMOTE_ACTIONS = ("doot", "pause", "resume", "stop")


def serve_remote(host: str, port: int, token: str, on_action) -> None:
    """Sert une telecommande locale protegee par un jeton ephemere."""

    expected = str(token)

    class Handler(BaseHTTPRequestHandler):
        def _reply(self, status: int, body: str) -> None:
            encoded = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'")
            self.end_headers()
            self.wfile.write(encoded)

        def _authorized(self) -> bool:
            query = parse_qs(urlparse(self.path).query)
            return secrets.compare_digest(query.get("token", [""])[0], expected)

        def do_GET(self):
            if not self._authorized():
                self._reply(403, "Acces refuse.")
                return
            buttons = "".join(
                f'<form method=post action="/action?token={html.escape(expected)}"><button name=action value="{action}">{action}</button></form>'
                for action in REMOTE_ACTIONS
            )
            self._reply(200, "<!doctype html><meta name=viewport content='width=device-width'><style>body{background:#09050d;color:white;font:22px system-ui;text-align:center;padding:8vh}button{width:80%;padding:18px;margin:8px;background:#7145a8;color:white;border:0;border-radius:14px}</style><h1>☠ Doot</h1>" + buttons)

        def do_POST(self):
            if not self._authorized() or urlparse(self.path).path != "/action":
                self._reply(403, "Acces refuse.")
                return
            length = min(1024, max(0, int(self.headers.get("Content-Length", "0"))))
            form = parse_qs(self.rfile.read(length).decode("utf-8", "replace"))
            action = form.get("action", [""])[0]
            if action not in REMOTE_ACTIONS:
                self._reply(400, "Action inconnue.")
                return
            on_action(action)
            self._reply(200, f"<p>Commande envoyee : {html.escape(action)}</p><p><a href='/?token={html.escape(expected)}'>retour</a></p>")

        def log_message(self, _format, *_args):
            return

    server = ThreadingHTTPServer((str(host), int(port)), Handler)
    try:
        server.serve_forever(poll_interval=.25)
    finally:
        server.server_close()


def validate_workshop(source: Path) -> dict:
    source = Path(source)
    if not source.is_file() or source.stat().st_size > 25 * 1024 * 1024:
        raise ValueError("pack absent ou superieur a 25 Mio")
    issues = []
    files = []
    try:
        with zipfile.ZipFile(source) as archive:
            for info in archive.infolist():
                pure = PurePosixPath(info.filename)
                if pure.is_absolute() or ".." in pure.parts or info.file_size > 8 * 1024 * 1024:
                    issues.append(f"chemin refuse : {info.filename}")
                    continue
                files.append(info.filename)
            if "manifest.json" not in files:
                issues.append("manifest.json manque")
            else:
                manifest = json.loads(archive.read("manifest.json"))
                if not str(manifest.get("format", "")).startswith("doot-"):
                    issues.append("format de manifeste inconnu")
    except (OSError, zipfile.BadZipFile, json.JSONDecodeError, KeyError) as exc:
        raise ValueError("pack d'atelier illisible") from exc
    return {"valid": not issues, "files": len(files), "issues": issues,
            "sha256": hashlib.sha256(source.read_bytes()).hexdigest()}


# ------------------------------------------------ calendrier / glyphes / fin --

MODIFIERS = (
    ("lune_rouge", "Lune rouge", "les boss gagnent une phase"),
    ("silence", "Voeu de silence", "les contres visuels valent double"),
    ("pluie_os", "Pluie d'os", "les reliques sont plus frequentes"),
    ("bal", "Grand bal", "la coop rapporte davantage"),
    ("miroirs", "Nuit des miroirs", "le boss copie ton style"),
)


def seasonal_calendar(day: date | None = None, days: int = 7) -> list[dict]:
    day = day or date.today()
    result = []
    for offset in range(max(1, min(31, int(days)))):
        current = date.fromordinal(day.toordinal() + offset)
        item = random.Random("doot-night:" + current.isoformat()).choice(MODIFIERS)
        result.append({"date": current.isoformat(), "id": item[0], "name": item[1], "rule": item[2]})
    return result


GLYPHS = {"𐌃": "doot", "☽": "lune", "△": "souffle", "⟐": "miroir", "⌁": "echo"}


def glyph_status(state: dict) -> dict:
    found = _root(state).get("glyphs")
    if not isinstance(found, list):
        found = []
        _root(state)["glyphs"] = found
    clues = {"𐌃": "medailles", "☽": "calendrier", "△": "musique",
             "⟐": "miroirs", "⌁": "dialogues"}
    return {"found": [key for key in GLYPHS if key in found], "total": len(GLYPHS),
            "clues": clues,
            "complete": all(key in found for key in GLYPHS)}


def decipher_glyph(state: dict, glyph: str, word: str) -> dict:
    glyph = str(glyph).strip()
    if glyph not in GLYPHS or str(word).casefold().strip() != GLYPHS[glyph]:
        raise ValueError("le glyphe demeure muet")
    status = glyph_status(state)
    found = _root(state)["glyphs"]
    fresh = glyph not in found
    if fresh:
        found.append(glyph)
    result = glyph_status(state)
    result.update({"glyph": glyph, "word": GLYPHS[glyph], "fresh": fresh})
    return result


def narrative_constellation(state: dict, destination: Path) -> Path:
    city = city_status(state)
    factions = faction_status(state)
    nemesis = nemesis_status(state)
    glyphs = glyph_status(state)
    nodes = [
        {"title": city["name"], "text": f"Niveau {city['level']} — {city['bones']} os"},
        {"title": "Serment", "text": factions["pledge"] or "Aucune faction"},
        {"title": "Rancune", "text": f"{nemesis['name']} — {nemesis['grudge']} retour(s)"},
        {"title": "Langue ancienne", "text": f"{len(glyphs['found'])}/{glyphs['total']} glyphes"},
    ]
    payload = json.dumps(nodes, ensure_ascii=False).replace("</", "<\\/")
    destination = Path(destination)
    if destination.suffix.casefold() != ".html":
        destination = destination / "doot-story-stars.html"
    source = f"""<!doctype html><meta charset=utf-8><title>Legende de la Cite des Os</title>
<style>body{{margin:0;background:radial-gradient(circle,#291841,#050208);color:white;font:16px system-ui}}main{{min-height:100vh;display:grid;place-items:center}}#sky{{position:relative;width:min(92vw,900px);height:70vh}}button{{position:absolute;border:0;background:none;color:#f6d365;font-size:38px;filter:drop-shadow(0 0 12px #9b5de5)}}#card{{position:fixed;bottom:25px;left:25px;right:25px;text-align:center;background:#130b20dd;padding:16px;border-radius:14px}}</style>
<main><div id=sky></div></main><div id=card>Chaque action ecrit la constellation.</div><script>const n={payload};n.forEach((x,i)=>{{let b=document.createElement('button');b.textContent='✦';b.style.left=(12+i*24)+'%';b.style.top=(18+(i%2)*38)+'%';b.onclick=()=>card.textContent=x.title+' — '+x.text;sky.append(b)}})</script>"""
    return _atomic_text(destination, source)


def mirror_boss(state: dict) -> dict:
    stats = state.get("stats") if isinstance(state.get("stats"), dict) else {}

    def total(key):
        value = stats.get(key, 0)
        return sum(x for x in value.values() if isinstance(x, int) and not isinstance(x, bool)) if isinstance(value, dict) else (value if isinstance(value, int) and not isinstance(value, bool) else 0)

    styles = {"virtuose": total("melodies"), "horde": total("doots"),
              "metteur_en_scene": total("evenements"), "explorateur": total("expeditions_terminees") * 10}
    style = max(styles, key=styles.get)
    power = max(12, min(99, 12 + sum(styles.values()) // 10))
    boss = {"name": "Le Reflet " + style.replace("_", " ").title(), "style": style,
            "power": power, "attack": {"virtuose": "accord vole", "horde": "double salve",
                                      "metteur_en_scene": "faux rappel", "explorateur": "porte inverse"}[style],
            "weakness": {"virtuose": "silence", "horde": "duel", "metteur_en_scene": "improvisation",
                                        "explorateur": "prudence"}[style]}
    _root(state)["mirror_boss"] = boss
    return boss
