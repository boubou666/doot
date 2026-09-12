"""Sortie audio native, sans lecteur externe.

La bibliotheque standard ne sait rien emettre sous Linux ni macOS : `winsound`
est propre a Windows, `ossaudiodev` et `audioop` ont disparu en 3.13, et `wave`
ne fait que lire et ecrire des fichiers. doot passait donc par un lecteur
externe, ce qui l'obligeait a construire une ligne de commande par lecteur et a
lui confier le panoramique, avec une syntaxe de filtre differente chacun.

On appelle donc libpulse-simple en ctypes, comme x11.py appelle libX11, avec
libasound en second recours. PipeWire n'a pas besoin d'un chemin a lui : il sert
l'API PulseAudio (`pactl info` repond « PulseAudio (on PipeWire) ») et son
greffon ALSA sert la seconde. La seconde ne sert donc que sur un ALSA nu.

Ne couvre que le WAV : aucun decodeur audio n'existe dans la stdlib, donc les
formats compresses gardent le lecteur externe. Le panoramique, lui, est
applique sur les echantillons comme `pan_wav` le fait deja, donc les deux
chemins sont enfin d'accord.
"""

from __future__ import annotations

import array
import atexit
import ctypes
import ctypes.util
import sys
import threading
import wave
from pathlib import Path

PA_SAMPLE_S16LE = 3
PA_STREAM_PLAYBACK = 1
SND_PCM_STREAM_PLAYBACK = 0
SND_PCM_FORMAT_S16_LE = 2
SND_PCM_ACCESS_RW_INTERLEAVED = 3
SND_LATENCE_US = 200000
EPIPE = 32          # underrun, rendu negatif par snd_pcm_writei
REPRISES_MAX = 8    # au-dela, le peripherique ne repartira pas
MORCEAU = 4096          # trames par ecriture, pour pouvoir s'arreter en route

_en_cours: set = set()
_verrou = threading.Lock()


class _SampleSpec(ctypes.Structure):
    _fields_ = [("format", ctypes.c_int),
                ("rate", ctypes.c_uint32),
                ("channels", ctypes.c_uint8)]


def _charge(nom: str, soname: str, prepare):
    """Charge une bibliotheque une seule fois, None si elle manque."""
    if nom not in _charge.cache:
        lib = None
        if sys.platform not in ("win32", "darwin"):
            try:
                lib = ctypes.CDLL(ctypes.util.find_library(nom) or soname)
                prepare(lib)
            except Exception:
                lib = None
        _charge.cache[nom] = lib
    return _charge.cache[nom]


_charge.cache = {}


def _prepare_pulse(lib):
    lib.pa_simple_new.restype = ctypes.c_void_p
    lib.pa_simple_new.argtypes = [
        ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p,
        ctypes.c_char_p, ctypes.POINTER(_SampleSpec), ctypes.c_void_p,
        ctypes.c_void_p, ctypes.POINTER(ctypes.c_int)]
    lib.pa_simple_write.restype = ctypes.c_int
    lib.pa_simple_write.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                    ctypes.c_size_t, ctypes.POINTER(ctypes.c_int)]
    lib.pa_simple_drain.restype = ctypes.c_int
    lib.pa_simple_drain.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int)]
    lib.pa_simple_free.argtypes = [ctypes.c_void_p]


def _prepare_alsa(lib):
    lib.snd_pcm_open.argtypes = [ctypes.POINTER(ctypes.c_void_p), ctypes.c_char_p,
                                 ctypes.c_int, ctypes.c_int]
    lib.snd_pcm_set_params.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
                                       ctypes.c_uint, ctypes.c_uint, ctypes.c_int,
                                       ctypes.c_uint]
    lib.snd_pcm_writei.restype = ctypes.c_long
    lib.snd_pcm_writei.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]
    lib.snd_pcm_prepare.argtypes = [ctypes.c_void_p]
    lib.snd_pcm_drain.argtypes = [ctypes.c_void_p]
    lib.snd_pcm_close.argtypes = [ctypes.c_void_p]


class _SortiePulse:
    """PulseAudio, et donc aussi PipeWire qui en sert l'interface."""

    nom = "PulseAudio/PipeWire"

    @staticmethod
    def bibliotheque():
        return _charge("pulse-simple", "libpulse-simple.so.0", _prepare_pulse)

    def __init__(self, rate: int):
        self.lib = self.bibliotheque()
        self.erreur = ctypes.c_int(0)
        spec = _SampleSpec(PA_SAMPLE_S16LE, rate, 2)
        self.flux = self.lib.pa_simple_new(
            None, b"doot", PA_STREAM_PLAYBACK, None, b"doot",
            ctypes.byref(spec), None, None, ctypes.byref(self.erreur))
        if not self.flux:
            raise OSError("pa_simple_new a echoue")

    def write(self, bloc: bytes) -> bool:
        return self.lib.pa_simple_write(self.flux, bloc, len(bloc),
                                        ctypes.byref(self.erreur)) >= 0

    def drain(self):
        self.lib.pa_simple_drain(self.flux, ctypes.byref(self.erreur))

    def close(self):
        self.lib.pa_simple_free(self.flux)


class _SortieAlsa:
    """ALSA nu, quand aucun serveur de son ne tourne."""

    nom = "ALSA"

    @staticmethod
    def bibliotheque():
        return _charge("asound", "libasound.so.2", _prepare_alsa)

    def __init__(self, rate: int):
        self.lib = self.bibliotheque()
        self.pcm = ctypes.c_void_p()
        if self.lib.snd_pcm_open(ctypes.byref(self.pcm), b"default",
                                 SND_PCM_STREAM_PLAYBACK, 0) < 0:
            raise OSError("snd_pcm_open a echoue")
        if self.lib.snd_pcm_set_params(self.pcm, SND_PCM_FORMAT_S16_LE,
                                       SND_PCM_ACCESS_RW_INTERLEAVED, 2, rate,
                                       1, SND_LATENCE_US) < 0:
            self.lib.snd_pcm_close(self.pcm)
            raise OSError("snd_pcm_set_params a echoue")

    def write(self, bloc: bytes) -> bool:
        """Ecrit tout le bloc, en reprenant apres un underrun.

        `snd_pcm_writei` peut rendre moins de trames que demande, et -EPIPE sur
        un underrun demande un `snd_pcm_prepare` pour repartir. Non eprouve sur
        un ALSA nu, faute de machine sans serveur de son : ici le greffon ALSA
        de PipeWire repond a sa place.
        """
        trames = len(bloc) // 4
        pose = 0
        reprises = 0
        while pose < trames:
            rendu = self.lib.snd_pcm_writei(self.pcm, bloc[pose * 4:], trames - pose)
            if rendu > 0:
                pose += rendu
                reprises = 0
                continue
            if rendu < 0 and rendu != -EPIPE:
                return False
            if rendu == -EPIPE:
                self.lib.snd_pcm_prepare(self.pcm)
            # Un underrun perpetuel, ou un zero rendu en boucle, ferait tourner
            # ce fil a vide indefiniment. Mieux vaut un son coupe qu'un cœur
            # brule en silence, d'autant que ce chemin n'a pas ete eprouve.
            reprises += 1
            if reprises > REPRISES_MAX:
                return False
        return True

    def drain(self):
        self.lib.snd_pcm_drain(self.pcm)

    def close(self):
        self.lib.snd_pcm_close(self.pcm)


_SORTIES = (_SortiePulse, _SortieAlsa)


def available() -> bool:
    """Vrai si au moins une sortie native est utilisable ici."""
    return any(sortie.bibliotheque() is not None for sortie in _SORTIES)


def _ouvre(rate: int):
    """La premiere sortie qui accepte, ou None."""
    for sortie in _SORTIES:
        if sortie.bibliotheque() is None:
            continue
        try:
            return sortie(rate)
        except Exception:
            continue
    return None


def _pcm_stereo(path: Path, pan: float) -> tuple[bytes, int] | None:
    """Le WAV lu, monte en stereo et panoramise. None si le format echappe.

    Le mono est duplique avant d'appliquer les gains, pour qu'une source mono et
    une source stereo se comportent pareil : chaque canal de sortie garde son
    canal d'entree, attenue par son propre gain.
    """
    from . import sound

    try:
        with wave.open(str(path), "rb") as handle:
            if handle.getsampwidth() != 2 or handle.getnchannels() not in (1, 2):
                return None
            canaux = handle.getnchannels()
            rate = handle.getframerate()
            brut = handle.readframes(handle.getnframes())
    except Exception:
        return None

    echantillons = array.array("h")
    echantillons.frombytes(brut[:len(brut) - len(brut) % 2])
    if sys.byteorder == "big":
        echantillons.byteswap()

    # `int(round(...))` et non `int(...)` : `pan_wav` arrondit, et tirer vers
    # zero ajouterait un biais par echantillon. Les deux chemins doivent rendre
    # les memes octets, un test les compare l'un a l'autre.
    gauche_gain, droite_gain = sound.stereo_gains(pan)
    sortie = array.array("h", bytes(len(echantillons) * (2 if canaux == 1 else 1) * 2))
    if canaux == 1:
        for i, valeur in enumerate(echantillons):
            sortie[2 * i] = int(round(valeur * gauche_gain))
            sortie[2 * i + 1] = int(round(valeur * droite_gain))
    else:
        for i in range(0, len(echantillons) - 1, 2):
            sortie[i] = int(round(echantillons[i] * gauche_gain))
            sortie[i + 1] = int(round(echantillons[i + 1] * droite_gain))
    if sys.byteorder == "big":
        sortie.byteswap()
    return sortie.tobytes(), rate


class Lecture:
    """Un son en cours, que l'on peut laisser finir ou couper."""

    __slots__ = ("_arret", "_fil")

    def __init__(self):
        self._arret = threading.Event()
        self._fil = None

    def stop(self):
        self._arret.set()

    def join(self, timeout=None):
        if self._fil is not None:
            self._fil.join(timeout)


def play(path: Path, pan: float = 0.0) -> "Lecture | None":
    """Joue un WAV sans bloquer. None si ce chemin ne sait pas le faire.

    Rendre None n'est pas une erreur : l'appelant se rabat sur le lecteur
    externe, seul capable des formats compresses.
    """
    # Avant tout le reste : convertir le PCM pour decouvrir ensuite qu'aucune
    # sortie n'existe, c'est du travail jete a chaque doot sous Windows et macOS.
    if not available():
        return None
    prepare = _pcm_stereo(Path(path), pan)
    if prepare is None:
        return None
    pcm, rate = prepare
    if not pcm:
        return None
    sortie = _ouvre(rate)
    if sortie is None:
        return None

    lecture = Lecture()

    def verse():
        try:
            pas = MORCEAU * 4          # 2 canaux x 2 octets
            for debut in range(0, len(pcm), pas):
                if lecture._arret.is_set():
                    break
                if not sortie.write(pcm[debut:debut + pas]):
                    break
            if not lecture._arret.is_set():
                sortie.drain()
        except Exception:
            pass
        finally:
            try:
                sortie.close()
            except Exception:
                pass
            with _verrou:
                _en_cours.discard(lecture)

    with _verrou:
        _en_cours.add(lecture)
    lecture._fil = threading.Thread(target=verse, daemon=True)
    lecture._fil.start()
    return lecture


def _laisse_finir(delai: float = 5.0) -> None:
    """A la sortie, laisse les sons en cours aller au bout.

    `sound.release` promet de ne pas tronquer une note ; un sous-processus y
    parvenait en survivant a doot. Le fil reste daemon pour qu'un serveur audio
    bloque ne retienne jamais le programme, et cette attente bornee tient la
    promesse dans tous les cas ordinaires.
    """
    # Le cliche sous verrou, l'attente hors verrou. A nu, `list(_en_cours)`
    # court contre le `discard` d'un fil qui finit juste a ce moment-la, et
    # c'est un RuntimeError a la sortie ; en tenant le verrou pendant le join,
    # ce meme fil ne pourrait plus se retirer et l'attente irait au bout du
    # delai a chaque fois.
    with _verrou:
        lectures = list(_en_cours)
    for lecture in lectures:
        lecture.join(delai)


atexit.register(_laisse_finir)


def stop_all() -> None:
    """Coupe net tous les sons natifs en cours."""
    with _verrou:
        for lecture in list(_en_cours):
            lecture.stop()
