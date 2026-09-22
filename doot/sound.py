"""Le son du doot : lecture multiplateforme, avec repli synthetise.

Ordre de priorite :
  1. un fichier depose dans <data_dir>/sound/  (`doot --paths` donne le chemin)
  2. le son fourni avec doot (doot/assets/doot.mp3)
  3. un petit motif deux notes synthetise ici meme (harmoniques + vibrato +
     enveloppe ADSR + soft clipping), utilise quand rien ne sait lire le mp3

Formats acceptes : wav, mp3, ogg, opus, flac, m4a, aac.
"""

from __future__ import annotations

import array
import math
import os
import random
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
import wave
from pathlib import Path

from . import audio

SAMPLE_RATE = 44100
TOTAL_SECONDS = 1.30

# "doo - doot" : une note breve puis une note tenue, meme hauteur (sol4).
NOTES = (
    {"start": 0.00, "duration": 0.28, "freq": 392.00},
    {"start": 0.34, "duration": 0.78, "freq": 392.00},
)

# Formats acceptes pour les sons perso.
AUDIO_EXTENSIONS = (".wav", ".mp3", ".ogg", ".oga", ".opus", ".flac", ".m4a", ".aac")

ASSETS_DIR = Path(__file__).resolve().parent / "assets"
BUNDLED_SOUND = ASSETS_DIR / "doot.mp3"

# Lecteurs Linux/BSD, dans l'ordre de preference.
# "any" = gere aussi les formats compresses ; sinon wav (+ ce que lit libsndfile).
LINUX_PLAYERS = (
    ("mpv", ["mpv", "--really-quiet", "--no-video"], "any"),
    ("ffplay", ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet"], "any"),
    ("play", ["play", "-q"], "any"),                  # SoX
    ("cvlc", ["cvlc", "--play-and-exit", "--intf", "dummy"], "any"),
    ("pw-play", ["pw-play"], "wav"),                  # PipeWire
    ("paplay", ["paplay"], "wav"),                    # PulseAudio
    ("aplay", ["aplay", "-q"], "wav"),                # ALSA
)

MCI_ALIAS = "dootsound"
VISUAL_VOLUME_THRESHOLD = 0.05


# ------------------------------------------------------------- synthese ------

def _render_samples(volume: float) -> list[float]:
    count = int(SAMPLE_RATE * TOTAL_SECONDS)
    buffer = [0.0] * count
    two_pi = math.tau

    for note in NOTES:
        offset = int(note["start"] * SAMPLE_RATE)
        length = int(note["duration"] * SAMPLE_RATE)
        attack = int(0.018 * SAMPLE_RATE)
        decay = int(0.070 * SAMPLE_RATE)
        release = int(0.110 * SAMPLE_RATE)
        sustain = 0.78

        for i in range(length):
            t = i / SAMPLE_RATE

            if i < attack:
                envelope = i / attack
            elif i < attack + decay:
                envelope = 1.0 - (1.0 - sustain) * ((i - attack) / decay)
            elif i > length - release:
                envelope = sustain * ((length - i) / release)
            else:
                envelope = sustain

            # petit "scoop" a l'attaque + vibrato leger : ca sonne cuivre
            bend = 1.0 - 0.012 * math.exp(-t * 45.0)
            vibrato = 1.0 + 0.0045 * math.sin(two_pi * 5.4 * t)
            phase = two_pi * note["freq"] * bend * vibrato * t

            value = 0.0
            for harmonic in range(1, 9):
                value += math.sin(phase * harmonic) / harmonic**1.25

            index = offset + i
            if index < count:
                buffer[index] += (value / 2.3) * envelope

    for i in range(count):
        buffer[i] = math.tanh(buffer[i] * 1.35) * volume

    fade = int(0.02 * SAMPLE_RATE)  # evite le clic de fin
    for i in range(fade):
        buffer[count - 1 - i] *= i / fade

    return buffer


def write_wav(path: Path, volume: float = 0.55) -> Path:
    """Ecrit le jingle synthetise en WAV PCM 16 bits mono."""
    path.parent.mkdir(parents=True, exist_ok=True)
    samples = _render_samples(volume)
    frames = b"".join(
        struct.pack("<h", int(max(-1.0, min(1.0, s)) * 32000)) for s in samples
    )
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(SAMPLE_RATE)
        handle.writeframes(frames)
    return path


def ensure_wav(path: Path, volume: float = 0.55, force: bool = False) -> Path:
    if force or not path.exists() or path.stat().st_size == 0:
        write_wav(path, volume)
    return path


def reverse_wav(src: Path, dest: Path) -> Path | None:
    """Inverse les trames d'un WAV sans inverser les octets des echantillons.

    None laisse l'appelant choisir un repli pour les formats compresses ou les
    fichiers abimes. Tous les parametres PCM sont conserves.
    """
    try:
        with wave.open(str(src), "rb") as handle:
            params = handle.getparams()
            frame_size = handle.getnchannels() * handle.getsampwidth()
            raw = handle.readframes(handle.getnframes())
        if frame_size <= 0 or len(raw) % frame_size:
            return None
        reversed_frames = b"".join(
            raw[offset:offset + frame_size]
            for offset in range(len(raw) - frame_size, -1, -frame_size)
        )
        dest.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(dest), "wb") as handle:
            handle.setparams(params)
            handle.writeframes(reversed_frames)
    except Exception:
        return None
    return dest


# ------------------------------------------------------- volume systeme -----

def _parse_output_level(text: str) -> float | None:
    """Lit les sorties usuelles de wpctl, pactl et ``get volume settings``."""
    lowered = text.lower()
    if "[muted]" in lowered or re.search(r"(?:mute|muted)\s*:\s*(?:yes|true|1)", lowered):
        return 0.0

    percent = re.search(r"(?:output volume\s*:\s*)?(\d+(?:[.,]\d+)?)\s*%", lowered)
    if percent:
        return max(0.0, min(1.0, float(percent.group(1).replace(",", ".")) / 100.0))

    mac = re.search(r"output volume\s*:\s*(\d+(?:[.,]\d+)?)", lowered)
    if mac:
        return max(0.0, min(1.0, float(mac.group(1).replace(",", ".")) / 100.0))

    pipewire = re.search(r"volume\s*:\s*(\d+(?:[.,]\d+)?)", lowered)
    if pipewire:
        return max(0.0, min(1.0, float(pipewire.group(1).replace(",", "."))))
    return None


def _volume_command(command: list[str]) -> str | None:
    try:
        result = subprocess.run(
            command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL, text=True, timeout=0.8, check=False,
        )
    except Exception:
        return None
    return result.stdout if result.returncode == 0 else None


def _windows_core_audio_level() -> float | None:
    """Volume et mute du peripherique de rendu Windows via Core Audio COM."""
    import ctypes
    import uuid

    class GUID(ctypes.Structure):
        _fields_ = (
            ("Data1", ctypes.c_uint32),
            ("Data2", ctypes.c_uint16),
            ("Data3", ctypes.c_uint16),
            ("Data4", ctypes.c_ubyte * 8),
        )

    def guid(value: str) -> GUID:
        raw = uuid.UUID(value)
        return GUID(
            raw.time_low, raw.time_mid, raw.time_hi_version,
            (ctypes.c_ubyte * 8).from_buffer_copy(raw.bytes[8:]),
        )

    def method(pointer, index, result, *arguments):
        table = ctypes.cast(
            pointer, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))
        ).contents
        return ctypes.WINFUNCTYPE(result, ctypes.c_void_p, *arguments)(table[index])

    ole32 = ctypes.windll.ole32
    initialized = False
    enumerator = ctypes.c_void_p()
    device = ctypes.c_void_p()
    endpoint = ctypes.c_void_p()
    try:
        initialized = ole32.CoInitialize(None) in (0, 1)
        clsid = guid("BCDE0395-E52F-467C-8E3D-C4579291692E")
        iid_enumerator = guid("A95664D2-9614-4F35-A746-DE8DB63617E6")
        iid_endpoint = guid("5CDF2C82-841E-4546-9722-0CF74078229A")
        ole32.CoCreateInstance.argtypes = (
            ctypes.POINTER(GUID), ctypes.c_void_p, ctypes.c_uint32,
            ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p),
        )
        ole32.CoCreateInstance.restype = ctypes.c_long
        if ole32.CoCreateInstance(
                ctypes.byref(clsid), None, 23, ctypes.byref(iid_enumerator),
                ctypes.byref(enumerator)) < 0:
            return None

        get_default = method(
            enumerator, 4, ctypes.c_long,
            ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_void_p),
        )
        if get_default(enumerator, 0, 1, ctypes.byref(device)) < 0:
            return None

        activate = method(
            device, 3, ctypes.c_long,
            ctypes.POINTER(GUID), ctypes.c_uint32, ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_void_p),
        )
        if activate(
                device, ctypes.byref(iid_endpoint), 23, None,
                ctypes.byref(endpoint)) < 0:
            return None

        level = ctypes.c_float()
        muted = ctypes.c_int()
        if method(endpoint, 9, ctypes.c_long, ctypes.POINTER(ctypes.c_float))(
                endpoint, ctypes.byref(level)) < 0:
            return None
        if method(endpoint, 15, ctypes.c_long, ctypes.POINTER(ctypes.c_int))(
                endpoint, ctypes.byref(muted)) < 0:
            return None
        return 0.0 if muted.value else max(0.0, min(1.0, level.value))
    except Exception:
        return None
    finally:
        for pointer in (endpoint, device, enumerator):
            if pointer.value:
                try:
                    method(pointer, 2, ctypes.c_ulong)(pointer)
                except Exception:
                    pass
        if initialized:
            ole32.CoUninitialize()


def system_output_level() -> float | None:
    """Niveau de sortie global, de 0 a 1, ou None s'il est inconnu.

    C'est volontairement un meilleur-effort sans dependance : WinMM sous
    Windows, ``get volume settings`` sous macOS, puis wpctl/pactl sous Linux.
    """
    if sys.platform == "win32":
        level = _windows_core_audio_level()
        if level is not None:
            return level
        # Vieux pilotes sans Core Audio : WinMM ne dit pas le mute, mais un
        # volume nul reste une information utile.
        try:
            import ctypes

            packed = ctypes.c_uint32()
            mapper = ctypes.c_void_p(-1)
            result = ctypes.windll.winmm.waveOutGetVolume(mapper, ctypes.byref(packed))
            if result != 0:
                return None
            left = packed.value & 0xFFFF
            right = packed.value >> 16
            return max(left, right) / 65535.0
        except Exception:
            return None

    if sys.platform == "darwin":
        if not shutil.which("osascript"):
            return None
        text = _volume_command(["osascript", "-e", "get volume settings"])
        return _parse_output_level(text or "")

    if shutil.which("wpctl"):
        text = _volume_command(["wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@"])
        level = _parse_output_level(text or "")
        if level is not None:
            return level
    if shutil.which("pactl"):
        mute = _volume_command(["pactl", "get-sink-mute", "@DEFAULT_SINK@"]) or ""
        volume = _volume_command(["pactl", "get-sink-volume", "@DEFAULT_SINK@"]) or ""
        return _parse_output_level(f"{mute}\n{volume}")
    return None


def visual_fallback_needed(no_sound: bool, configured_volume: float,
                           path: Path | None) -> bool:
    """Le doot doit-il aussi devenir lisible en tres grandes lettres ?"""
    if no_sound or path is None or configured_volume <= VISUAL_VOLUME_THRESHOLD:
        return True
    level = system_output_level()
    return level is not None and level <= VISUAL_VOLUME_THRESHOLD


def custom_sounds(custom_dir: Path) -> list[Path]:
    """Les fichiers audio deposes par l'utilisateur, tries."""
    if not custom_dir.is_dir():
        return []
    return sorted(
        p for p in custom_dir.iterdir()
        if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS
    )


def bundled_sound() -> Path | None:
    """Le son livre avec doot, ou None si le paquet n'en contient pas."""
    return BUNDLED_SOUND if BUNDLED_SOUND.is_file() else None


def pick_sound(cache_wav: Path, custom_dir: Path, volume: float = 0.55) -> Path:
    """Son a jouer : perso d'abord, puis celui fourni, puis le jingle synthetise.

    Le son fourni est un mp3 : sur les systemes sans lecteur capable de le lire
    (Linux minimal sans mpv/ffmpeg/sox/vlc), on retombe sur le jingle wav.
    """
    customs = custom_sounds(custom_dir)
    if customs:
        return random.choice(customs)

    default = bundled_sound()
    if default is not None and (sys.platform == "win32" or find_player(default)):
        return default

    return ensure_wav(cache_wav, volume)


# ---------------------------------------------------------- spatialisation ---

def stereo_gains(pan: float) -> tuple[float, float]:
    """Gains gauche et droit pour un panoramique de -1 a +1.

    Le rapport entre les deux suit un quart de cercle (cos, sin), plus doux a
    l'oreille qu'une regle de trois. Mais les gains sont ensuite ramenes de
    sorte que le canal dominant reste a plein volume : seul le canal oppose est
    attenue.

    C'est volontaire. A puissance constante, le centre vaudrait 0,71 de chaque
    cote, soit 3 dB de moins qu'un son non panoramise. Le doot serait plus
    discret qu'avant l'arrivee de cette fonction, et surtout il sauterait de
    3 dB en franchissant le seuil sous lequel on ne panoramise pas. Ici le
    centre rend exactement le son d'origine, et la courbe est continue.
    """
    pan = max(-1.0, min(1.0, float(pan)))
    angle = (pan + 1.0) * (math.pi / 4.0)  # -1 -> 0, 0 -> pi/4, +1 -> pi/2

    # Arrondi avant de comparer : cos(pi/4) et sin(pi/4) ne tombent pas sur le
    # meme dernier bit d'une libm a l'autre, et au centre exact cet ecart
    # infime suffirait a desequilibrer les deux canaux d'une unite.
    gauche = round(math.cos(angle), 12)
    droite = round(math.sin(angle), 12)
    fort = max(gauche, droite)
    return gauche / fort, droite / fort


def pan_wav(src: Path, dest: Path, pan: float) -> Path | None:
    """Ecrit une copie stereo panoramisee de `src`. None si le format s'y refuse.

    Fait avec le seul module `wave` : le module audioop, qui aurait fait ca en
    une ligne, a disparu en Python 3.13.
    """
    left_gain, right_gain = stereo_gains(pan)
    try:
        with wave.open(str(src), "rb") as handle:
            channels = handle.getnchannels()
            width = handle.getsampwidth()
            rate = handle.getframerate()
            raw = handle.readframes(handle.getnframes())
    except Exception:
        return None

    if channels not in (1, 2) or width not in (1, 2):
        return None  # 24 ou 32 bits, ou multicanal : on joue sans toucher

    if width == 2:
        samples = array.array("h")
        samples.frombytes(raw[:len(raw) - len(raw) % 2])
        if sys.byteorder == "big":
            samples.byteswap()
        limit = 32767
        centre = 0
    else:
        # WAV 8 bits : non signe, silence a 128
        samples = array.array("h", [b - 128 for b in raw])
        limit = 127
        centre = 128

    frames = len(samples) // channels
    out = array.array("h", bytes(4 * frames))
    for i in range(frames):
        if channels == 1:
            gauche = droite = samples[i]
        else:
            gauche, droite = samples[2 * i], samples[2 * i + 1]
        # arrondi, pas troncature : `int()` tire tout vers zero et ajoute un
        # biais a chaque echantillon
        gauche = int(round(gauche * left_gain))
        droite = int(round(droite * right_gain))
        out[2 * i] = max(-limit - 1, min(limit, gauche))
        out[2 * i + 1] = max(-limit - 1, min(limit, droite))

    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(dest), "wb") as handle:
            handle.setnchannels(2)
            handle.setsampwidth(width)
            handle.setframerate(rate)
            if width == 2:
                if sys.byteorder == "big":
                    out.byteswap()
                handle.writeframes(out.tobytes())
            else:
                handle.writeframes(bytes((v + centre) & 255 for v in out))
    except Exception:
        return None
    return dest


def _panned_path() -> Path:
    """Fichier de travail pour la copie panoramisee, propre a ce processus."""
    return Path(tempfile.gettempdir()) / f"doot-panned-{os.getpid()}.wav"


def _pan_graph(pan: float) -> str:
    """Le graphe libavfilter qui place le son, source mono ou stereo.

    Chaque canal garde le sien : `c0` sort de `c0`, `c1` de `c1`. Tirer les
    deux sorties de `c0`, plus court, jetterait le canal droit d'une source
    stereo — la ou `pan_wav` fait le meme travail sur les WAV en gardant les
    deux. Le meme son changerait alors de rendu en franchissant `SEUIL_PAN`,
    exactement la marche que `stereo_gains` s'applique a eviter par ailleurs.

    Mesure sur une source asymetrique, RMS 13395 a gauche et 2679 a droite,
    panoramisee a -0.9 : `c1=Rg*c0` rend 1054 sur la sortie droite, soit le
    canal gauche attenue ; `c1=Rg*c1` rend 211, soit le droit.

    L'`aformat` en tete monte le mono en stereo avant le `pan`, en dupliquant
    l'unique canal, ce qui laisse une seule expression valable pour les deux
    sources. mpv s'en passerait — son pipeline monte deja en stereo avant les
    filtres — mais autant ne pas dependre de ce detail. Un 5.1 y gagne un vrai
    melange, la ou `c0` seul n'aurait garde que l'avant gauche.
    """
    left_gain, right_gain = stereo_gains(pan)
    return ("aformat=channel_layouts=stereo,"
            f"pan=stereo|c0={left_gain:.4f}*c0|c1={right_gain:.4f}*c1")


def _pan_filter(command: list[str], pan: float) -> list[str] | None:
    """Ajoute un filtre de panoramique a mpv ou ffplay, qui savent le faire."""
    graphe = _pan_graph(pan)
    binary = Path(command[0]).name
    if binary.startswith("mpv"):
        # `pan` vient de libavfilter : mpv ne l'atteint que par `lavfi=[...]`.
        # Ecrit `--af=pan=...`, son analyseur d'options bute sur les barres et
        # refuse de demarrer, ce qui rendait tout doot spatialise muet. Les
        # crochets prennent le graphe tel quel, virgule comprise.
        return command + [f"--af=lavfi=[{graphe}]"]
    if binary.startswith("ffplay"):
        # `-af` recoit le graphe dans un argument a lui, sans analyseur
        # d'options entre les deux : la forme ffmpeg y passe telle quelle.
        return command + ["-af", graphe]
    return None


def _mci_pan(pan: float) -> None:
    """Panoramique cote Windows : MCI regle le volume de chaque canal."""
    left_gain, right_gain = stereo_gains(pan)
    _mci(f"setaudio {MCI_ALIAS} left volume to {int(left_gain * 1000)}")
    _mci(f"setaudio {MCI_ALIAS} right volume to {int(right_gain * 1000)}")


# --------------------------------------------------------------- lecture -----

def _mci(command: str) -> tuple[int, str]:
    """Envoie une commande MCI (Windows). Gere le mp3 et compagnie."""
    import ctypes

    buffer = ctypes.create_unicode_buffer(512)
    code = ctypes.windll.winmm.mciSendStringW(command, buffer, 511, 0)
    return code, buffer.value


def find_player(path: Path | None = None) -> list[str] | None:
    """Commande de lecture adaptee au fichier, ou None.

    Windows n'en a pas besoin (winsound / MCI sont integres).
    """
    if sys.platform == "win32":
        return None
    if sys.platform == "darwin":
        return ["afplay"] if shutil.which("afplay") else None

    compressed = path is not None and path.suffix.lower() not in (".wav",)
    for binary, command, formats in LINUX_PLAYERS:
        if compressed and formats != "any":
            continue
        if shutil.which(binary):
            return command
    return None


SEUIL_PAN = 0.02  # en deca, le panoramique ne s'entend pas : autant ne rien faire


def play_async(path: Path, pan: float = 0.0) -> object | None:
    """Lance le son sans bloquer, place a `pan` (-1 gauche, 0 centre, +1 droite).

    Silencieux si aucun lecteur n'est disponible, et non panoramise plutot que
    muet si la plateforme ne sait pas placer ce format.
    """
    path = Path(path)
    spatialise = abs(pan) > SEUIL_PAN

    # Sortie native d'abord : pas de lecteur externe, pas de fichier temporaire,
    # et le panoramique applique sur les echantillons comme `pan_wav`. Elle rend
    # None hors WAV, aucun decodeur audio n'existant dans la stdlib.
    native = audio.play(path, pan if spatialise else 0.0)
    if native is not None:
        return native

    # Un WAV, on le panoramise nous-memes : ca marche partout, quel que soit
    # le lecteur, et sans rien installer.
    if spatialise and path.suffix.lower() == ".wav":
        panned = pan_wav(path, _panned_path(), pan)
        if panned is not None:
            path = panned
            spatialise = False  # le panoramique est deja dans les echantillons

    if sys.platform == "win32":
        if path.suffix.lower() == ".wav":
            try:
                import winsound

                winsound.PlaySound(
                    str(path),
                    winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT,
                )
                return "winsound"
            except Exception:
                return None
        # mp3, m4a, wma... : MCI sait faire, sans dependance externe, et sait
        # regler le volume de chaque canal separement.
        try:
            _mci(f"close {MCI_ALIAS}")
            code, _ = _mci(f'open "{path}" alias {MCI_ALIAS}')
            if code != 0:
                return None
            if spatialise:
                _mci_pan(pan)
            _mci(f"play {MCI_ALIAS}")
            return "mci"
        except Exception:
            return None

    command = find_player(path)
    if not command:
        return None

    lecture = command
    if spatialise:
        filtre = _pan_filter(command, pan)
        if filtre is not None:
            lecture = filtre
    try:
        en_cours = Lecture(_lance(lecture, path))
    except Exception:
        return None
    if lecture is not command:
        _repli_sans_pan(en_cours, command, path)
    return en_cours


def _lance(command: list[str], path: Path) -> subprocess.Popen:
    return subprocess.Popen(
        command + [str(path)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
    )


class Lecture:
    """Le lecteur en cours.

    Le repli remplace le processus en place, pour que celui qu'on peut joindre
    soit toujours celui qui joue. Sans ca `play_async` rendrait le processus
    mort et le lecteur de repli serait injoignable, ce qui ne se voit pas tant
    que `release` est un no-op mais mordrait le jour ou il coupera le son.
    """

    __slots__ = ("proc",)

    def __init__(self, proc):
        self.proc = proc


def _repli_sans_pan(lecture: "Lecture", command: list[str], path: Path,
                    delai: float = 0.25) -> threading.Thread:
    """Rejoue sans panoramique si le lecteur a refuse le filtre.

    Un lecteur qui n'accepte pas la syntaxe meurt aussitot. Sans ce garde-fou,
    le doot est muet, alors que ce module promet un son non panoramise plutot
    qu'un silence. La veille est dans un fil : le cas nominal ne paie rien.

    Une sortie non nulle venue d'ailleurs (pas de peripherique, fichier
    illisible) declenche une tentative aussi vouee que la premiere. On ne sait
    pas les distinguer sans lire stderr, et un processus de plus qui meurt
    aussitot coute moins qu'un doot muet.
    """
    def veille():
        try:
            if lecture.proc.wait(timeout=delai) != 0:
                lecture.proc = _lance(command, path)
        except subprocess.TimeoutExpired:
            pass
        except Exception:
            pass

    fil = threading.Thread(target=veille, daemon=True)
    fil.start()
    return fil


def release(handle: object | None) -> None:
    """Libere les ressources SANS couper le son en cours.

    Le squelette peut disparaitre avant la fin de la note : on laisse le son
    aller au bout plutot que de le tronquer.
    """
    if handle == "mci":
        # MCI garde le fichier ouvert : on ne ferme qu'a la lecture suivante.
        return
    return


def stop_all() -> None:
    """Coupe net tout son en cours (arret du programme)."""
    audio.stop_all()
    if sys.platform == "win32":
        try:
            import winsound

            winsound.PlaySound(None, winsound.SND_PURGE)
        except Exception:
            pass
        try:
            _mci(f"close {MCI_ALIAS}")
        except Exception:
            pass


# --------------------------------------------------------------- duree -------

def probe_duration(path: Path) -> float | None:
    """Duree du fichier en secondes, ou None si on ne sait pas la lire."""
    path = Path(path)

    if path.suffix.lower() == ".wav":
        try:
            with wave.open(str(path), "rb") as handle:
                rate = handle.getframerate()
                if rate:
                    return handle.getnframes() / float(rate)
        except Exception:
            return None
        return None

    if sys.platform == "win32":
        try:
            alias = MCI_ALIAS + "probe"
            _mci(f"close {alias}")
            code, _ = _mci(f'open "{path}" alias {alias}')
            if code != 0:
                return None
            _mci(f"set {alias} time format milliseconds")
            code, value = _mci(f"status {alias} length")
            _mci(f"close {alias}")
            if code == 0 and value.strip().isdigit():
                return int(value.strip()) / 1000.0
        except Exception:
            return None
        return None

    ffprobe = shutil.which("ffprobe")
    if ffprobe:
        try:
            out = subprocess.run(
                [ffprobe, "-v", "quiet", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
                capture_output=True, text=True, timeout=5,
            )
            return float(out.stdout.strip())
        except Exception:
            return None
    return None
