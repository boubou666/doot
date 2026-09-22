"""Ligne de commande et boucle de fond de doot."""

from __future__ import annotations

import argparse
import copy
import ctypes
import json
import os
import random
import shutil
import subprocess
import sys
import time
import zipfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from . import (
    __version__, adventure, art, carte, challenges, choreography, coffre, codex,
    contagion, content, duel, history, image, notification, packs, partage,
    procedural, profiles, registre, replay, rituals, schedule, season, sound, succes,
    wave3, wave4, wave5, wave6,
)

DEFAULT_MIN_SECONDS = 600     # 10 min
DEFAULT_MAX_SECONDS = 3600    # 1 h
DEFAULT_DURATION = 2.8
DEFAULT_VOLUME = 0.55
DEFAULT_SPIN_CHANCE = 0.25
DEFAULT_SPIN_MS = 700
DEFAULT_REVERSE_CHANCE = 0.03
DEFAULT_BURST_DELAY = 0.6
DEFAULT_EVENT_CHANCE = 0.02
DEFAULT_EVENT_PITY = 100
DEFAULT_CONTAGION_CHANCE = 0.12
CONTAGION_POLL_SECONDS = 30
OUT_OF_SEASON_POLL = 3600     # on reverifie la date toutes les heures
FORMATION_SIDES = ("left", "top", "right", "bottom")
FORMATIONS = ("random", "canon", "wave", "rain", "vortex", "duel")


# --------------------------------------------------------------- chemins -----

def data_dir() -> Path:
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local")
        return Path(base) / "doot"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "doot"
    base = os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share")
    return Path(base) / "doot"


def paths() -> dict[str, Path]:
    root = data_dir()
    return {
        "data": root,
        "sound": root / "sound",
        "image": root / "image",
        "melodies": root / "melodies",
        "events": root / "events",
        "wav": root / "doot.wav",
        "log": root / "doot.log",
        "pid": root / "doot.pid",
        "state": root / "state.json",
        "profiles": root / "profiles.json",
        "content": root / "content.json",
        "history": root / "history.jsonl",
        "rituals": root / "rituals.json",
        "choreographies": root / "choreographies",
        "packs": root / "packs",
        "replays": root / "replays",
        "dj": root / "dj",
        "characters": root / "characters",
    }


def log(message: str, quiet: bool = False) -> None:
    line = f"{datetime.now():%Y-%m-%d %H:%M:%S}  {message}"
    try:
        path = paths()["log"]
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except Exception:
        pass
    if not quiet:
        print(line, flush=True)


def profiles_path() -> Path:
    """Chemin des profils, avec repli pour les integrations qui remplacent paths()."""

    p = paths()
    return p.get("profiles", p["data"] / "profiles.json")


def data_path(key: str, fallback: str) -> Path:
    """Chemin ajoute recemment, compatible avec les integrations qui remplacent paths()."""

    p = paths()
    return p.get(key, p["data"] / fallback)


# ------------------------------------------------------- instance unique -----

def _kernel32():
    """Isole l'acces a kernel32 : les tests le remplacent par un faux."""
    return ctypes.windll.kernel32


def _win_process_alive(pid: int) -> bool:
    """Le processus `pid` tourne-t-il encore, sous Windows ?

    Un `OpenProcess` qui reussit ne prouve rien : l'objet noyau du processus
    survit a sa mort tant qu'un handle traine quelque part, et la fonction
    repond alors oui pour un processus termine depuis longtemps. Il faut
    interroger l'objet lui-meme : il est signale des que le processus est
    mort, donc seule l'attente qui expire (WAIT_TIMEOUT) prouve qu'il tourne.
    """
    SYNCHRONIZE = 0x00100000
    WAIT_TIMEOUT = 0x00000102

    kernel32 = _kernel32()
    # Un HANDLE fait 64 bits sur x64 ; sans ces declarations ctypes le
    # ramenerait a un int et le rendrait a CloseHandle deja tronque.
    kernel32.OpenProcess.restype = ctypes.c_void_p
    kernel32.OpenProcess.argtypes = (ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32)
    kernel32.WaitForSingleObject.argtypes = (ctypes.c_void_p, ctypes.c_uint32)
    kernel32.CloseHandle.argtypes = (ctypes.c_void_p,)

    handle = kernel32.OpenProcess(SYNCHRONIZE, False, pid)
    if not handle:
        return False
    try:
        return kernel32.WaitForSingleObject(handle, 0) == WAIT_TIMEOUT
    finally:
        kernel32.CloseHandle(handle)


def _process_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform == "win32":
        return _win_process_alive(pid)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def running_pid() -> int | None:
    pid_file = paths()["pid"]
    try:
        pid = int(pid_file.read_text().strip())
    except Exception:
        return None
    if _process_alive(pid):
        return pid
    return None


def claim_pid_file() -> bool:
    existing = running_pid()
    if existing and existing != os.getpid():
        return False
    pid_file = paths()["pid"]
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    pid_file.write_text(str(os.getpid()))
    return True


def release_pid_file() -> None:
    try:
        paths()["pid"].unlink()
    except Exception:
        pass


# ------------------------------------------------------------- actions -------

def resolve_media(args, reverse: bool = False) -> tuple:
    """(son, image, duree) pour le prochain doot.

    Relu a chaque doot : tu peux deposer un son ou une image pendant que le
    daemon tourne, il les prendra sans redemarrage.
    """
    p = paths()

    wav = None
    if not args.no_sound:
        try:
            wav = sound.pick_sound(p["wav"], p["sound"], args.volume)
            if reverse:
                # La stdlib ne decode pas les MP3 et autres formats compresses.
                # Dans ce cas le doot inverse garde sa promesse avec le jingle
                # synthetise, toujours disponible en WAV.
                source = wav
                if source.suffix.lower() != ".wav":
                    source = sound.ensure_wav(p["wav"], args.volume)
                inverse = sound.reverse_wav(source, p["data"] / "doot-reverse.wav")
                if inverse is not None:
                    wav = inverse
        except Exception as exc:
            log(f"son indisponible : {exc}", quiet=args.quiet)

    picture = None
    if not args.no_image:
        try:
            picture = image.pick_image(p["image"], args.image)
        except Exception as exc:
            log(f"image indisponible : {exc}", quiet=args.quiet)

    # Sans --duration explicite, on reste affiche le temps du son.
    duration = args.duration
    if duration is None:
        duration = DEFAULT_DURATION
        if wav is not None:
            length = sound.probe_duration(wav)
            if length:
                duration = max(DEFAULT_DURATION, length + 0.4)
    return wav, picture, duration


def display_options(args, step: dict | None = None, reverse: bool = False) -> dict:
    """Les reglages d'affichage, tels que `window.show` les attend.

    Un seul endroit ou traduire les options, hors de la boucle de la salve :
    treize reglages recopies au milieu d'un `for` cachent ce que la boucle
    fait vraiment, et l'arbitrage entre les facons d'arriver a besoin d'un nom.

    `--spin` impose le tour complet, comme `--side` impose l'entree par un
    bord : il vaut donc tous les doots, et sur place, sinon la demande
    resterait sans effet la plupart du temps.
    """
    options = {
        "font_size": args.font_size,
        "center": args.center,
        "opacity": args.opacity,
        "scale": args.scale,
        "screen": args.screen,
        "spatialise": not args.no_pan,
        "slide": not args.no_slide and not args.spin,
        "side": args.side,
        "slide_ms": args.slide_ms,
        "slide_chance": args.slide_chance,
        "spin": not args.no_spin,
        "spin_chance": 1.0 if args.spin else args.spin_chance,
        "spin_ms": args.spin_ms,
        "glitch": getattr(args, "mise_en_scene", "") == "faux-bug",
        "reverse": reverse,
    }

    # Une formation ne remplace que les choix laisses au hasard par
    # l'utilisateur. Les options explicites (`--screen`, `--side` et
    # `--no-slide`) restent donc souveraines.
    if step is not None:
        if step["screen"] is not None:
            options["screen"] = step["screen"]
        if step["side"] is not None:
            options["side"] = step["side"]
            if options["slide"]:
                options["slide_chance"] = 1.0
        if step.get("force_spin"):
            options["slide"] = False
            options["side"] = None
            if options["spin"]:
                options["spin_chance"] = 1.0
    return options


def formation_plan(args, total: int) -> list[dict | None]:
    """Prepare les destinations d'une salve avant de l'afficher.

    La formation `random` conserve exactement le tirage historique. `canon`
    tourne autour des quatre bords, `wave` alterne gauche et droite, `rain`
    tombe toujours du haut et `vortex` impose les tours sur place. Les ecrans
    sont parcourus dans l'ordre, ou en aller-retour pour la vague.

    Un choix explicite de l'utilisateur reste fixe ; cela permet par exemple
    une pluie sur un seul ecran. Les refus explicites de glisser ou tourner
    restent eux aussi souverains.
    """
    formation = getattr(args, "formation", "random")
    if formation == "random":
        return [None] * total

    from . import window

    try:
        screen_count = len(window.active_monitors())
    except Exception:
        # La fenetre saura elle-meme se rabattre sur son ecran de secours.
        screen_count = 1
    screen_count = max(1, screen_count)

    screen_locked = args.screen not in (None, "", "random")
    side_locked = args.side not in (None, "", "random")
    can_slide = not args.no_slide and not args.spin
    plan = []
    for index in range(total):
        if formation == "wave" and screen_count > 1:
            period = screen_count * 2 - 2
            offset = index % period
            screen_index = offset if offset < screen_count else period - offset
        else:
            screen_index = index % screen_count

        if side_locked or not can_slide:
            side = args.side
        elif formation == "wave":
            side = ("left", "right")[index % 2]
        elif formation == "rain":
            side = "top"
        elif formation == "duel":
            side = ("left", "right")[index % 2]
        elif formation == "vortex":
            side = None
        else:
            side = FORMATION_SIDES[index % len(FORMATION_SIDES)]

        plan.append({
            "screen": args.screen if screen_locked else str(screen_index),
            "side": side,
            "force_spin": formation == "vortex" and not side_locked,
        })
    return plan


def burst_size(args, rng=random) -> int:
    """Combien de doots ce declenchement enchaine-t-il."""
    bas = max(1, args.burst_min)
    haut = max(bas, args.burst_max)
    return rng.randint(bas, haut)


def should_reverse(args, rng=random) -> bool:
    """Un seul tirage gouverne ensemble l'image et le son de ce doot."""
    if args.no_reverse:
        return False
    chance = 1.0 if args.reverse else args.reverse_chance
    return rng.random() < max(0.0, min(1.0, chance))


def emit_doots(args, journal: bool = False, evenement: str | None = None) -> int:
    """Joue la salve de ce declenchement ; renvoie le nombre de doots affiches.

    Chaque doot de la salve repasse par `resolve_media` et `window.show` : il
    retire donc son son, son image, son ecran, son bord d'entree. Deux
    squelettes d'affilee n'arrivent jamais pareil, ce qui est tout l'interet
    d'en enchainer plusieurs.

    Une salve dure : la pause plus la duree d'affichage, autant de fois qu'il y
    a de doots. La saison peut donc se fermer en plein milieu, comme elle peut
    se fermer pendant l'attente du daemon. On la reverifie avant chaque doot
    sauf le premier, que l'appelant vient de valider.
    """
    from . import window

    total = burst_size(args)
    plan = formation_plan(args, total)
    joues = 0
    try:
        for index in range(1, total + 1):
            if index > 1:
                if args.burst_delay > 0:
                    time.sleep(args.burst_delay)
                if not args.ignore_season and not season.in_season():
                    if journal:
                        log("la saison s'est fermee pendant la salve.", quiet=args.quiet)
                    break
            reverse = should_reverse(args)
            wav, picture, duration = resolve_media(args, reverse=reverse)
            visual_text = (
                "D O O T"
                if (sound.visual_fallback_needed(args.no_sound, args.volume, wav)
                    or getattr(args, "high_contrast", False))
                else None
            )
            window.show(wav_path=wav, duration=duration, image_path=picture,
                        visual_text=visual_text,
                        **display_options(args, plan[index - 1], reverse=reverse))
            joues += 1
            if journal:
                log("doot !" if total == 1 else f"doot {index}/{total} !", quiet=args.quiet)
    finally:
        if joues:
            note_succes(
                args,
                "doots",
                quantite=joues,
                formation=args.formation,
                spin=args.spin,
                bord=args.side,
                rencontre=evenement,
                reverse=args.reverse,
            )
    return joues


def do_once(args) -> int:
    if not args.ignore_season and not season.in_season():
        print(f"doot : {season.describe()}")
        print(f"Saison : {season.SEASON_LABEL}. (--ignore-season pour forcer un test.)")
        return 3

    emit_doots(args)
    return 0


def do_play(args, wanted: str) -> int:
    """Une melodie en doots, sur place : `--play NOM|FICHIER` et `--rickroll`.

    Meme regle de saison que `--once` : hors saison le squelette range sa
    trompette, quel que soit le morceau. Le WAV est rendu a chaque fois, en
    une fraction de seconde, dans le dossier de donnees : pas de cache a
    invalider.
    """
    if not args.ignore_season and not season.in_season():
        print(f"doot : {season.describe()}")
        print(f"Saison : {season.SEASON_LABEL}. (--ignore-season pour forcer un test.)")
        return 3

    from . import melodie, window

    p = paths()
    fichier = melodie.find(wanted, p["melodies"])
    if fichier is None:
        print(f"doot : aucune melodie '{wanted}' (doot --melodies pour la liste, "
              f"ou depose un .rtttl dans {p['melodies']})")
        return 2
    try:
        morceau = melodie.load(fichier)
    except melodie.MelodieError as exc:
        print(f"doot : melodie illisible, {exc}")
        return 2

    emit_melodie(args, morceau)
    note_melodie_jouee(args, fichier, morceau)
    return 0


def read_state() -> dict:
    """L'etat garde entre deux lancements. Vide si illisible pour ne jamais bloquer.

    Un JSON syntaxiquement valide n'est pas un etat valide : le fichier se
    modifie a la main, et une racine qui n'est pas un objet ferait echouer
    chaque reveil du daemon sans que rien ne la repare.
    """
    try:
        etat = json.loads(paths()["state"].read_text(encoding="utf-8"))
    except Exception:
        etat = {}
    if not isinstance(etat, dict):
        etat = {}
    # L'identite de replique vient du poste et jamais du fichier : un
    # state.json copie ou restaure ne doit pas faire croire a deux
    # installations qu'elles n'en sont qu'une.
    etat["machine"] = partage.identite(paths()["data"])
    return etat


def state_compteur(etat: dict, cle: str) -> int:
    """Un compteur de l'etat, ramene a un entier positif.

    Tout le reste, du texte a l'absent en passant par un nombre negatif,
    repart de zero : perdre un cycle de pitie vaut mieux que perdre tous les
    declenchements suivants.
    """
    return succes.entier(etat.get(cle, 0))


def write_state(state: dict) -> None:
    temporaire = None
    try:
        chemin = paths()["state"]
        chemin.parent.mkdir(parents=True, exist_ok=True)
        temporaire = chemin.with_name(f".{chemin.name}.{os.getpid()}.tmp")
        temporaire.write_text(json.dumps(state, indent=2), encoding="utf-8")
        os.replace(temporaire, chemin)
    except Exception:
        pass
    finally:
        if temporaire is not None:
            try:
                temporaire.unlink()
            except FileNotFoundError:
                pass
            except OSError:
                pass


def note_succes(args, evenement: str, **details) -> None:
    """Persiste un evenement et annonce seulement les nouveaux succes."""

    etat = read_state()
    nouveaux = succes.enregistrer(etat, evenement, **details)
    adventure.record_combo(etat, evenement)
    for secret in adventure.observe_riddles(etat, evenement, **details):
        nouveaux.extend(succes.enregistrer(etat, "enigme", nom=secret))
    challenge_done = False
    if evenement == "doots":
        challenge_done |= challenges.record(
            etat, "doots", amount=max(0, int(details.get("quantite", 0))),
        )
        if int(details.get("quantite", 0)) >= 4:
            challenge_done |= challenges.record(
                etat, "formation", formation=str(details.get("formation", "")),
            )
        if details.get("rencontre"):
            challenge_done |= challenges.record(etat, "event")
        history.append(
            data_path("history", "history.jsonl"), "doots", count=int(details.get("quantite", 0)),
            formation=str(details.get("formation", "random")),
            special=str(details.get("rencontre", "")),
        )
    elif evenement == "melodie":
        challenge_done |= challenges.record(etat, "melodie")
        history.append(
            data_path("history", "history.jsonl"), "melody", name=str(details.get("nom", "")),
            voices=int(details.get("voix", 1)),
        )
    elif evenement == "pack":
        history.append(data_path("history", "history.jsonl"), "pack", pack=str(details.get("nom", "")))
    elif evenement == "rencontre_perso":
        history.append(data_path("history", "history.jsonl"), "custom-event", name=str(details.get("nom", "")))
    elif evenement == "parade_flotte":
        history.append(data_path("history", "history.jsonl"), "fleet-parade", name=str(details.get("nom", "")))
    if challenge_done:
        nouveaux.extend(succes.enregistrer(
            etat, "defi", serie=int(etat.get("challenge_streak", 0)),
        ))
        history.append(
            data_path("history", "history.jsonl"), "challenge", challenge=challenges.daily().identifiant,
        )
    write_state(etat)
    annoncer_succes(args, nouveaux)


def annoncer_succes(args, nouveaux) -> None:
    """Journalise chaque succes tombe, et n'en montre qu'une carte.

    Un seul chemin pour le jeu et pour la fusion : un succes gagne en reunissant
    deux machines vaut le sien, il n'y a pas de raison qu'il se contente d'une
    ligne de texte.
    """
    if not nouveaux:
        return

    for definition in nouveaux:
        log(
            f"SUCCES DEBLOQUE : {definition.titre} (+{definition.points} points) - "
            f"{definition.description}",
            quiet=args.quiet,
        )

    wav = notification_sound(args)
    try:
        if len(nouveaux) == 1:
            seul = nouveaux[0]
            notification.show(
                seul.titre, seul.description, seul.points,
                badge_path=succes.badge(seul), wav_path=wav,
            )
        else:
            notification.show_lot(
                [definition.titre for definition in nouveaux],
                sum(definition.points for definition in nouveaux),
                badge_path=succes.badge(nouveaux[0]), wav_path=wav,
            )
    except Exception as exc:
        log(f"notification de succes indisponible : {exc}", quiet=args.quiet)


def notification_sound(args) -> Path | None:
    """Micro-fanfare RTTTL, muette avec --no-sound et repliee sur le doot."""

    if args.no_sound:
        return None
    try:
        return notification.render_victory(paths()["data"] / "victory-parade.wav")
    except Exception as exc:
        log(f"fanfare de succes indisponible ({exc}), repli sur le doot.", quiet=args.quiet)
        try:
            p = paths()
            return sound.pick_sound(p["wav"], p["sound"], args.volume)
        except Exception:
            return None


def note_melodie_jouee(args, fichier: Path, morceau) -> None:
    """Enregistre une melodie seulement apres son affichage reussi."""

    from . import melodie

    try:
        fournie = fichier.resolve().parent == melodie.MELODIES_DIR.resolve()
    except OSError:
        fournie = False
    note_succes(
        args,
        "melodie",
        nom=fichier.stem,
        fournie=fournie,
        voix=len(morceau.voices),
    )


def melody_due(depuis: int, chance: float, pity: int, rng=random) -> bool:
    """Ce declenchement joue-t-il une melodie ?

    `depuis` compte les declenchements passes depuis la derniere. Le compteur
    de pitie borne les series noires : avec 40, le quarantieme declenchement
    sans melodie en joue une a coup sur.
    """
    if pity > 0 and depuis >= pity - 1:
        return True
    return rng.random() < chance


def melody_pool(p: dict) -> list:
    """Les melodies tirables : celles deposees par l'utilisateur, puis celles fournies."""
    from . import melodie

    return melodie.custom(p["melodies"]) + melodie.bundled()


def melody_roll(args, rng=random):
    """La melodie de ce declenchement, ou None pour des doots ordinaires.

    Ne touche pas au compteur : tant qu'aucune melodie n'a joue, la garantie
    reste due. C'est `note_melodie` qui tranche, une fois le sort connu.
    """
    if args.no_melody:
        return None

    pool = melody_pool(paths())
    if not pool:
        return None

    depuis = state_compteur(read_state(), "depuis_melodie")
    if not melody_due(depuis, args.melody_chance, args.melody_pity, rng):
        return None
    return content.choose(
        pool, content.read(data_path("content", "content.json")), "melodies", lambda path: path.stem, rng,
    )


def event_due(depuis: int, chance: float, pity: int, rng=random) -> bool:
    """Ce declenchement est-il une rencontre rare ?"""

    if pity > 0 and depuis >= pity - 1:
        return True
    return rng.random() < chance


def event_roll(args, rng=random):
    """Tire une rencontre rare, sans consommer son compteur avant affichage."""

    if args.no_event:
        return None
    from . import evenements

    depuis = state_compteur(read_state(), "depuis_evenement")
    if not event_due(depuis, args.event_chance, args.event_pity, rng):
        return None
    pool = tuple(
        event for event in evenements.all_events(data_path("events", "events"))
        if event.tirable
    )
    return content.choose(
        pool, content.read(data_path("content", "content.json")), "events",
        lambda event: event.identifiant, rng,
    )


def rite_du_soir(args):
    """La rencontre finale, si ce soir ferme la saison et qu'elle n'a pas eu lieu.

    Le rite ne depend pas du tirage : c'est la date qui l'appelle. Il ne consulte
    que l'etat, donc un daemon relance dans la soiree ne le rejoue pas.
    """
    from . import evenements

    if args.no_event or not season.is_last_night():
        return None
    if state_compteur(read_state(), "rite_saison") == season.last_season_year():
        return None
    return evenements.find("finale")


def clore_la_saison(args, annee: int):
    """Note le rite comme accompli, puis laisse la carte de la saison.

    Dans cet ordre : la carte doit compter les doots de la finale elle-meme.
    Une carte qui echoue ne rejoue pas le rite pour autant - la crypte a bien
    ferme, seule l'image manque, et une douzaine de squelettes par minute
    jusqu'a minuit serait une facon rude de le signaler.
    """
    etat = read_state()
    etat["rite_saison"] = annee
    write_state(etat)
    try:
        chemin = carte.ecrire(paths()["data"], read_state(), annee)
    except Exception as exc:
        log(f"carte de la saison indisponible : {exc}", quiet=args.quiet)
        return None
    log(f"LA CRYPTE SE REFERME - carte de la saison {annee} : {chemin}",
        quiet=args.quiet)
    return chemin


def jouer_le_rite(args, evenement) -> bool:
    """Joue la finale, et referme la saison meme si l'affichage casse en route.

    `emit_doots` compte dans son `finally` les squelettes deja montres. Si une
    fenetre casse au milieu des douze, la ceremonie a bien eu lieu pour qui
    regardait : ne pas la clore ferait rejouer la finale entiere au
    declenchement suivant, puis a chacun de ceux d'apres jusqu'a minuit.

    Aucun doot affiche n'est pas une ceremonie, en revanche. La saison reste
    alors ouverte et le declenchement suivant retentera, ce qui est le bon sens
    d'un ecran indisponible une minute.
    """
    annee = season.last_season_year()
    avant = succes.total(read_state(), "doots")
    try:
        return emit_evenement(args, evenement, journal=True)
    finally:
        if succes.total(read_state(), "doots") > avant:
            clore_la_saison(args, annee)


def do_carte(args, destination: str) -> int:
    """Ecrit la carte d'une saison, sans attendre qu'elle se ferme."""

    annee = season.last_season_year()
    cible = Path(destination).expanduser() if destination else paths()["data"]
    try:
        chemin = carte.ecrire(cible, read_state(), annee)
    except (OSError, ValueError) as exc:
        print(f"doot : carte impossible a ecrire : {exc}")
        return 2
    print(f"doot : carte de la saison {annee} -> {chemin}")
    return 0


def note_evenement(joue: bool) -> None:
    """Persiste la pitie des rencontres rares apres le resultat du tirage."""

    etat = read_state()
    depuis = state_compteur(etat, "depuis_evenement")
    etat["depuis_evenement"] = 0 if joue else depuis + 1
    write_state(etat)


def emit_evenement(args, evenement, journal: bool = False) -> bool:
    """Joue une rencontre precomposee et l'enregistre comme telle."""

    from . import evenements

    if journal:
        log(f"EVENEMENT RARE : {evenement.titre} - {evenement.description}", quiet=args.quiet)
    configured = evenements.configure(args, evenement)
    if evenement.mise_en_scene == "mimic":
        try:
            notification.show_mimic()
        except Exception as exc:
            log(f"mimic indisponible : {exc}", quiet=args.quiet)
    return emit_doots(
        configured,
        journal=journal,
        evenement=evenement.identifiant,
    ) > 0


def do_event(args, wanted: str) -> int:
    """Force une rencontre par son nom, principalement pour la decouvrir."""

    from . import evenements

    if not args.ignore_season and not season.in_season():
        print(f"doot : {season.describe()}")
        print(f"Saison : {season.SEASON_LABEL}. (--ignore-season pour forcer un test.)")
        return 3
    evenement = evenements.find(wanted, data_path("events", "events"))
    if evenement is None:
        print(f"doot : evenement inconnu '{wanted}' (doot --events pour la liste)")
        return 2
    emit_evenement(args, evenement, journal=True)
    return 0


def do_events(args) -> int:
    from . import evenements

    print("Evenements rares :")
    for evenement in evenements.all_events(data_path("events", "events")):
        print(f"  {evenement.identifiant:<10} {evenement.titre} - {evenement.description}")
    print("\nEssayer : doot --event NOM --ignore-season")
    return 0


def do_save_event(args, name: str) -> int:
    from . import evenements

    try:
        path = evenements.save(
            data_path("events", "events"), name, args.event_title or name,
            args.event_description or "Rencontre composee dans le Studio macabre.",
            formation=args.formation, count=args.burst_max,
            delay=args.burst_delay, duration=args.duration or DEFAULT_DURATION,
        )
    except (OSError, ValueError) as exc:
        print(f"doot : rencontre impossible : {exc}")
        return 2
    note_succes(args, "rencontre_perso", nom=path.stem)
    print(f"doot : rencontre sauvegardee -> {path}")
    print(f"Essayer : doot --event {path.stem} --ignore-season")
    return 0


def do_content(args) -> int:
    document = content.read(data_path("content", "content.json"))
    print("Preferences de contenu (1 = normal, 0 = desactive) :")
    for kind in content.KINDS:
        print(f"  {kind}:")
        values = document[kind]
        if not values:
            print("    toutes au poids normal")
        for name, weight in sorted(values.items()):
            print(f"    {name:<28} {weight:g}")
    return 0


def do_set_content(args, kind: str, name: str, weight: float) -> int:
    try:
        value = content.set_weight(data_path("content", "content.json"), kind, name, weight)
    except (OSError, ValueError) as exc:
        print(f"doot : preference impossible : {exc}")
        return 2
    label = "desactive" if value == 0 else "normal" if value == 1 else f"favorise x{value:g}"
    print(f"doot : {name} -> {label}")
    return 0


def do_history(args) -> int:
    entries = history.read(data_path("history", "history.jsonl"), args.history)
    print(f"Historique des apparitions ({len(entries)} derniere(s)) :")
    if not entries:
        print("  aucune apparition enregistree")
        return 0
    for entry in entries:
        details = [f"{key}={value}" for key, value in entry.items()
                   if key not in ("at", "kind") and value not in ("", None)]
        suffix = " - " + ", ".join(details) if details else ""
        print(f"  {entry.get('at', '?')}  {entry['kind']}{suffix}")
    return 0


def do_challenge(args) -> int:
    etat = read_state()
    state = challenges.status(etat)
    write_state(etat)
    challenge = challenges.daily()
    marker = "TERMINE" if state["completed"] else f"{state['progress']}/{challenge.target}"
    print(f"Defi du jour : {challenge.title}")
    print(f"  progression : {marker}")
    print(f"  serie       : {int(etat.get('challenge_streak', 0))} jour(s)")
    return 0


def do_pack_export(args, name: str, destination: str) -> int:
    try:
        path = packs.export(
            paths()["data"], Path(destination).expanduser(), name,
            author=args.pack_author, description=args.pack_description,
            pack_version=args.pack_version,
        )
    except (OSError, ValueError) as exc:
        print(f"doot : export du pack impossible : {exc}")
        return 2
    print(f"doot : pack exporte -> {path}")
    return 0


def do_pack_import(args, source: str) -> int:
    try:
        name, installed = packs.install(Path(source).expanduser(), paths()["data"])
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        print(f"doot : import du pack impossible : {exc}")
        return 2
    note_succes(args, "pack", nom=name)
    try:
        library = data_path("packs", "packs")
        library.mkdir(parents=True, exist_ok=True)
        target = library / Path(source).name
        if not target.exists():
            shutil.copy2(Path(source).expanduser(), target)
    except OSError:
        pass
    print(f"doot : pack '{name}' importe ({len(installed)} fichier(s)).")
    return 0


def do_pack_library(args) -> int:
    entries = packs.library(data_path("packs", "packs"))
    print(f"Bibliotheque de packs ({len(entries)}) :")
    if not entries:
        print("  aucun pack archive ; les imports futurs seront conserves ici")
    for path, metadata in entries:
        author = f" par {metadata['author']}" if metadata["author"] else ""
        trust = "verifie" if metadata["verified"] else "ancien format"
        print(f"  {metadata['name']} {metadata['pack_version']}{author} — {trust} — {path.name}")
        if metadata["description"]:
            print(f"    {metadata['description']}")
    return 0


def do_campaign(args) -> int:
    state = read_state()
    status = adventure.campaign_status(state)
    write_state(state)
    print(f"Campagne de la crypte — {status['index']}/{status['total']} chapitre(s)")
    if status["completed"]:
        print("  FIN — la clef d'ossuaire repose dans ton musee.")
        return 0
    chapter = status["chapter"]
    print(f"\n{chapter.titre}\n  {chapter.texte}")
    for key, label in chapter.choix:
        print(f"  - {key:<10} {label}")
    print("\nChoisir : doot --campaign-choose MOT")
    return 0


def do_campaign_choose(args, choice: str) -> int:
    state = read_state()
    try:
        status = adventure.choose(state, choice)
    except ValueError as exc:
        print(f"doot : {exc}")
        return 2
    write_state(state)
    note_succes(args, "campagne", completed=status["completed"])
    print("doot : choix grave dans l'os.")
    return do_campaign(args)


def do_boss(args) -> int:
    state = read_state()
    boss = adventure.seasonal_boss(state)
    write_state(state)
    bar = "#" * round(20 * (boss["max_hp"] - boss["hp"]) / boss["max_hp"])
    phase = wave3.boss_phase(boss)
    print(f"Boss saisonnier : {boss['name']}")
    print(f"  [{bar:<20}] {boss['hp']}/{boss['max_hp']} PV")
    print(f"  phase {phase['number']} — {phase['name']}")
    print(f"  attaque annoncee : {phase['attack']} — contre rythmique : {phase['counter']}")
    print("  doot --boss-hit N --formation CONTRE pour doubler les degats")
    return 0


def do_boss_hit(args, damage: int) -> int:
    state = read_state()
    before = adventure.seasonal_boss(state)
    phase_before = wave3.boss_phase(before)
    countered = args.formation == phase_before["counter"]
    dealt = damage * 2 if countered else damage
    try:
        boss = adventure.hit_boss(state, dealt)
    except ValueError as exc:
        print(f"doot : {exc}")
        return 2
    write_state(state)
    if boss["defeated"] and not before["defeated"]:
        note_succes(args, "boss", defeated=True)
        print(f"DOOT FINAL ! {boss['name']} est vaincu.")
    else:
        counter = " — CONTRE PARFAIT x2" if countered else ""
        phase_after = wave3.boss_phase(boss)
        change = (f" — transformation : {phase_after['name']}"
                  if phase_after["number"] != phase_before["number"] else "")
        print(f"doot : {min(50, dealt)} degats{counter}{change} — "
              f"{boss['hp']}/{boss['max_hp']} PV")
    return 0


def do_combo(args) -> int:
    combo = adventure.combo_status(read_state())
    if not combo:
        print("Combo : aucune action. Enchaine deux commandes en moins de 8 secondes.")
    else:
        print(f"Combo : x{combo.get('count', 0)} — multiplicateur x{combo.get('multiplier', 1)} "
              f"— record {combo.get('best', 0)}")
    return 0


def do_invasion(args, waves: int) -> int:
    if not args.ignore_season and not season.in_season():
        print(f"doot : {season.describe()}")
        return 3
    waves = max(1, min(10, int(waves)))
    print(f"Invasion : {waves} vague(s) approchent.")
    for index in range(1, waves + 1):
        wave_args = copy.copy(args)
        wave_args.burst_min = wave_args.burst_max = min(12, index + 1)
        wave_args.formation = ("wave", "rain", "canon", "vortex", "duel")[(index - 1) % 5]
        print(f"  vague {index}/{waves} — {wave_args.formation}")
        emit_doots(wave_args, journal=True, evenement="invasion")
    note_succes(args, "invasion", waves=waves)
    print("doot : invasion repoussee.")
    return 0


def do_generate_melody(args, style: str) -> int:
    try:
        path = procedural.save(paths()["melodies"], style, args.melody_seed, args.melody_name)
    except (OSError, ValueError) as exc:
        print(f"doot : generation impossible : {exc}")
        return 2
    print(f"doot : melodie procedurale -> {path}")
    print(f"Jouer : doot --play {path.stem}")
    return 0


def do_replay_export(args, destination: str) -> int:
    entries = history.read(data_path("history", "history.jsonl"), 50)
    try:
        path = replay.export(entries, Path(destination).expanduser())
    except OSError as exc:
        print(f"doot : replay impossible : {exc}")
        return 2
    note_succes(args, "replay", path=str(path))
    print(f"doot : replay partageable -> {path}")
    return 0


def do_choreography_save(args, name: str) -> int:
    try:
        path = choreography.save(
            data_path("choreographies", "choreographies"), name,
            [{"at": 0, "count": max(1, args.burst_min), "formation": args.formation}],
        )
    except (OSError, ValueError) as exc:
        print(f"doot : choregraphie impossible : {exc}")
        return 2
    print(f"doot : choregraphie sauvee -> {path}")
    return 0


def _choreography_path(name: str) -> Path:
    candidate = Path(name).expanduser()
    if candidate.is_file():
        return candidate
    return data_path("choreographies", "choreographies") / f"{choreography.safe_name(name)}.json"


def do_choreography_play(args, name: str) -> int:
    if not args.ignore_season and not season.in_season():
        print(f"doot : {season.describe()}")
        return 3
    try:
        title, cues = choreography.load(_choreography_path(name))
    except (OSError, ValueError) as exc:
        print(f"doot : choregraphie illisible : {exc}")
        return 2
    print(f"Choregraphie : {title} ({len(cues)} repere(s))")
    started = time.monotonic()
    for cue in cues:
        time.sleep(max(0, cue.at - (time.monotonic() - started)))
        cue_args = copy.copy(args)
        cue_args.burst_min = cue_args.burst_max = cue.count
        cue_args.formation = cue.formation
        if cue.melody:
            result = do_play(cue_args, cue.melody)
            if result:
                return result
        else:
            emit_doots(cue_args, journal=True)
    return 0


def do_choreographies(args) -> int:
    files = choreography.list_all(data_path("choreographies", "choreographies"))
    print(f"Choregraphies ({len(files)}) :")
    for path in files:
        try:
            name, cues = choreography.load(path)
            print(f"  {path.stem:<24} {len(cues)} repere(s) — {name}")
        except ValueError:
            print(f"  {path.name:<24} illisible")
    return 0


def do_rituals(args) -> int:
    entries = rituals.read(data_path("rituals", "rituals.json"))
    print(f"Rituels quotidiens ({len(entries)}) :")
    for item in entries:
        detail = f" {item['value']}" if item["value"] else ""
        print(f"  {item['at']}  {item['name']} — {item['action']}{detail}")
    return 0


def do_ritual_add(args, name: str) -> int:
    if not args.ritual_at:
        print("doot : --ritual-at HH:MM est requis")
        return 2
    try:
        item = rituals.add(data_path("rituals", "rituals.json"), name, args.ritual_at,
                           args.ritual_action, args.ritual_value)
    except (OSError, ValueError) as exc:
        print(f"doot : rituel impossible : {exc}")
        return 2
    print(f"doot : rituel '{item['name']}' planifie a {item['at']}.")
    return 0


def do_ritual_delete(args, name: str) -> int:
    if not rituals.delete(data_path("rituals", "rituals.json"), name):
        print(f"doot : rituel inconnu : {name}")
        return 2
    print(f"doot : rituel '{name}' supprime.")
    return 0


def run_due_rituals(args) -> int:
    due = rituals.due(data_path("rituals", "rituals.json"))
    for item in due:
        log(f"rituel : {item['name']}", quiet=args.quiet)
        if item["action"] == "melody" and item["value"]:
            do_play(args, item["value"])
        else:
            emit_doots(args, journal=True, evenement="rituel")
    return len(due)


def do_museum(args) -> int:
    state = read_state()
    display = adventure.museum(state)
    archived = [year for year in display["seasons"] if year < datetime.now().year]
    if archived:
        note_succes(args, "musee", year=max(archived))
        state = read_state()
        display = adventure.museum(state)
    print("Musee des saisons")
    print(f"  saisons archivees : {', '.join(map(str, display['seasons'])) or 'aucune activite datee'}")
    print(f"  rencontres        : {len(display['events'])}")
    print(f"  boss vaincus      : {len(display['bosses'])}")
    print(f"  enigmes resolues  : {display['riddles']}/{len(adventure.RIDDLES)}")
    print(f"  campagne          : {'terminee' if display['campaign_completed'] else 'en cours'}")
    return 0


def do_skeletons(args) -> int:
    active = adventure.active_personality(read_state()).identifiant
    print("Personnalites de squelettes :")
    for item in adventure.PERSONALITIES:
        marker = "*" if item.identifiant == active else " "
        print(f" {marker} {item.identifiant:<10} {item.nom} — {item.replique}")
    return 0


def do_skeleton(args, wanted: str) -> int:
    state = read_state()
    try:
        item = adventure.set_personality(state, wanted)
    except ValueError as exc:
        print(f"doot : {exc}")
        return 2
    write_state(state)
    print(f"doot : {item.nom} prend la trompette — « {item.replique} »")
    return 0


def do_music_duel(args, motif: str) -> int:
    state = read_state()
    try:
        item = adventure.create_music_duel(state, motif, args.duel_opponent)
    except ValueError as exc:
        print(f"doot : duel musical impossible : {exc}")
        return 2
    write_state(state)
    print(f"doot : {item['id']} lance a {item['opponent']} — {item['motif']}")
    return 0


def do_music_duels(args) -> int:
    entries = adventure.music_duels(read_state())
    print(f"Duels musicaux ({len(entries)}) :")
    for item in entries:
        print(f"  {item['id']} vs {item['opponent']}: {item['motif']} [{item['status']}]")
    return 0


def do_riddles(args) -> int:
    entries = adventure.riddle_status(read_state())
    print(f"Succes secrets a enigmes ({sum(item['solved'] for item in entries)}/{len(entries)}) :")
    for item in entries:
        marker = "RESOLU" if item["solved"] else f"INDICE {item['hint_level']}/3"
        print(f"  [{marker}] {item['title']}\n    {item['hint']}")
    return 0


def do_accessibility(args) -> int:
    print("Accessibilite active :")
    print(f"  mouvements reduits : {'oui' if args.reduce_motion else 'non'}")
    print(f"  flashs reduits     : {'oui' if args.no_flash else 'non'}")
    print(f"  contraste renforce : {'oui' if args.high_contrast else 'non'}")
    print(f"  limite sonore      : {args.sound_limit:.0%}")
    return 0


# --------------------------------------------------------------- vague 3 -----

def _print_expedition(status: dict) -> None:
    if not status.get("active") and "seed" not in status:
        print("Expedition : aucune route active. Lance : doot --expedition GRAINE")
        return
    print(f"Expedition {status['seed']} — salle {min(status['room'] + 1, len(status['rooms']))}/"
          f"{len(status['rooms'])} — {status['hp']} PV — {len(status['relics'])} relique(s)")
    if status.get("completed"):
        print("  VICTOIRE — la clef astrale est a toi." if status.get("won")
              else "  DEFAITE — la crypte referme la route.")
        return
    room = status["current"]
    print(f"\n{room['title']}  [danger {room['danger']}]\n  {room['text']}")
    print("  doot --expedition-choose prudence|audace")


def do_expedition(args, seed: str) -> int:
    state = read_state()
    current = wave3.expedition_status(state)
    if seed or not current.get("active"):
        current = wave3.start_expedition(state, seed)
        write_state(state)
    _print_expedition(current)
    return 0


def do_expedition_choose(args, choice: str) -> int:
    state = read_state()
    before = wave3.expedition_status(state)
    try:
        status = wave3.choose_expedition(state, choice)
    except ValueError as exc:
        print(f"doot : {exc}")
        return 2
    write_state(state)
    if status.get("won") and not before.get("won"):
        note_succes(args, "expedition", completed=True)
    _print_expedition(status)
    return 0


def do_campaign_editor(args, destination: str) -> int:
    try:
        path = wave3.campaign_editor(Path(destination).expanduser())
    except OSError as exc:
        print(f"doot : editeur impossible : {exc}")
        return 2
    print(f"doot : editeur visuel de campagne -> {path}")
    return 0


def do_campaign_pack(args, source: str, destination: str) -> int:
    try:
        path = wave3.campaign_pack(Path(source).expanduser(), Path(destination).expanduser())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"doot : pack de campagne impossible : {exc}")
        return 2
    print(f"doot : campagne emballee -> {path}")
    return 0


def do_constellation(args, destination: str) -> int:
    try:
        path = wave3.constellation(read_state(), succes.CATALOGUE,
                                   Path(destination).expanduser())
    except OSError as exc:
        print(f"doot : constellation impossible : {exc}")
        return 2
    print(f"doot : constellation interactive -> {path}")
    return 0


def do_familiars(args) -> int:
    state = read_state()
    current = wave3.familiar_status(state)
    write_state(state)
    print("Familiers spectraux :")
    for item in wave3.FAMILIARS:
        marker = "*" if item.identifiant == current["id"] else " "
        print(f" {marker} {item.identifiant:<16} {item.name} — {item.talent}")
    print(f"Lien actuel : niveau {current['level']} ({current['bond']} activite(s))")
    return 0


def do_familiar(args, wanted: str) -> int:
    state = read_state()
    try:
        item = wave3.set_familiar(state, wanted)
    except ValueError as exc:
        print(f"doot : {exc}")
        return 2
    write_state(state)
    print(f"doot : {item['name']} t'accompagne — {item['talent']}.")
    return 0


def do_familiar_bond(args, activity: str) -> int:
    state = read_state()
    before = wave3.familiar_status(state)
    try:
        item = wave3.bond_familiar(state, activity)
    except ValueError as exc:
        print(f"doot : {exc}")
        return 2
    write_state(state)
    if item["level"] >= 2 and before["level"] < 2:
        note_succes(args, "familiar", level=item["level"])
    print(f"doot : lien avec {item['name']} — niveau {item['level']} ({item['bond']}).")
    return 0


def _print_contract(item: dict) -> None:
    print(f"Contrat de flotte : {item['title']}")
    print(f"  progression : {item['progress']}/{item['target']} — "
          f"{len(item['contributors'])} contributeur(s)")
    print("  TERMINE — pacte honore." if item["completed"] else
          "  Partage : --contract-share FICHIER, puis --contract-join FICHIER")


def do_contract(args) -> int:
    state = read_state()
    item = wave3.contract_status(state)
    write_state(state)
    _print_contract(item)
    return 0


def do_contract_add(args, amount: int) -> int:
    state = read_state()
    before = wave3.contract_status(state)
    try:
        item = wave3.add_contract_progress(state, amount, partage.identite(paths()["data"]))
    except ValueError as exc:
        print(f"doot : {exc}")
        return 2
    write_state(state)
    if item["completed"] and not before["completed"]:
        note_succes(args, "contract", completed=True)
    _print_contract(item)
    return 0


def do_contract_share(args, destination: str) -> int:
    try:
        path = wave3.contract_capsule(read_state(), Path(destination).expanduser())
    except (OSError, ValueError) as exc:
        print(f"doot : partage du contrat impossible : {exc}")
        return 2
    print(f"doot : capsule de contrat chiffree -> {path}")
    return 0


def do_contract_join(args, source: str) -> int:
    state = read_state()
    before = wave3.contract_status(state)
    try:
        item = wave3.join_contract(state, Path(source).expanduser())
    except (OSError, ValueError) as exc:
        print(f"doot : capsule illisible : {exc}")
        return 2
    write_state(state)
    if item["completed"] and not before["completed"]:
        note_succes(args, "contract", completed=True)
    _print_contract(item)
    return 0


def do_dj_import(args, source: str) -> int:
    try:
        path = wave3.dj_import(Path(source).expanduser(), data_path("dj", "dj"), args.dj_slices)
    except (OSError, ValueError) as exc:
        print(f"doot : import DJ impossible : {exc}")
        return 2
    note_succes(args, "dj", imported=True)
    print(f"doot : sample decoupe en {args.dj_slices} pads -> {path}")
    return 0


def do_ambient_mode(args, preset: str) -> int:
    state = read_state()
    try:
        item = wave3.ambience(state, None if preset == "status" else preset)
    except ValueError as exc:
        print(f"doot : {exc}")
        return 2
    write_state(state)
    print(f"Ambiance de crypte : {item['preset']} — brume {item['fog']:.0%}, "
          f"pluie {item['rain']:.0%}, lune {item['moon']:.0%}, "
          f"silhouettes {item['silhouettes']}, OLED {'oui' if item['oled'] else 'non'}")
    return 0


def do_replay_gif(args, destination: str) -> int:
    entries = history.read(data_path("history", "history.jsonl"), 50)
    try:
        path = wave3.replay_gif(entries, Path(destination).expanduser())
    except OSError as exc:
        print(f"doot : GIF impossible : {exc}")
        return 2
    print(f"doot : replay GIF -> {path}")
    return 0


def do_code_hunt(args) -> int:
    entries = wave3.hunt_status(read_state())
    print(f"Chasse aux codes ({sum(item['found'] for item in entries)}/{len(entries)}) :")
    for item in entries:
        print(f"  [{'TROUVE' if item['found'] else '....'}] {item['code']} — {item['hint']}")
    return 0


def do_code_submit(args, code: str) -> int:
    state = read_state()
    try:
        result = wave3.submit_code(state, code)
    except ValueError as exc:
        print(f"doot : {exc}")
        return 2
    write_state(state)
    if result["completed"] and result["fresh"]:
        note_succes(args, "code_hunt", completed=True)
    print(f"doot : code {result['code']} {'decouvert' if result['fresh'] else 'deja grave'}.")
    return 0


def do_new_game_plus(args) -> int:
    state = read_state()
    try:
        level = wave3.new_game_plus(state)
    except ValueError as exc:
        print(f"doot : {exc}")
        return 2
    write_state(state)
    note_succes(args, "new_game_plus", level=level)
    print(f"doot : Nouvelle Partie +{level}. La crypte se souvient de tout, sauf du chemin.")
    return 0


def _character_path(wanted: str) -> Path:
    candidate = Path(wanted).expanduser()
    if candidate.is_file():
        return candidate
    entries = wave3.characters(data_path("characters", "characters"))
    found = next((item for item in entries if item.get("name", "").casefold() == wanted.casefold()), None)
    return Path(found["path"]) if found else candidate


def do_character(args, name: str) -> int:
    try:
        path = wave3.save_character(data_path("characters", "characters"), name,
                                    args.character_skull, args.character_costume,
                                    args.character_instrument, args.character_voice,
                                    args.character_line)
    except (OSError, ValueError) as exc:
        print(f"doot : personnage impossible : {exc}")
        return 2
    print(f"doot : personnage cree -> {path}")
    return 0


def do_characters(args) -> int:
    entries = wave3.characters(data_path("characters", "characters"))
    print(f"Studio de personnages ({len(entries)}) :")
    for item in entries:
        print(f"  {item['name']} — {item['costume']}, {item['instrument']}, voix {item['voice']}")
        print(f"    « {item['line']} »")
    return 0


def do_character_pack(args, wanted: str, destination: str) -> int:
    try:
        path = wave3.character_pack(_character_path(wanted), Path(destination).expanduser())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"doot : pack de personnage impossible : {exc}")
        return 2
    print(f"doot : personnage exporte -> {path}")
    return 0


def do_radio(args, seed: str) -> int:
    print("Radio Crypte — programmation automatique")
    for show in wave3.radio_schedule(seed):
        print(f"  {show['at']}  {show['title']} — {show['style']}")
    return 0


def do_coop(args, action: str) -> int:
    state = read_state()
    try:
        item = wave3.coop_action(state, action)
    except ValueError as exc:
        print(f"doot : {exc}")
        return 2
    write_state(state)
    if item["score"] == 4:
        note_succes(args, "coop", score=item["score"])
    print(f"Coop locale — score {item['score']}, serie {item['streak']}, au joueur {item['turn']}.")
    return 0


def do_night_infinite(args, seed: str) -> int:
    state = read_state()
    item = wave3.endless_night(state, seed)
    write_state(state)
    if item["completed"]:
        note_succes(args, "nuit_infinie", completed=True)
    print(f"Nuit infinie — acte {item['act']}/6 — energie {item['energy']}")
    print("  AUBE IMPOSSIBLE — finale debloquee." if item["completed"] else
          "  Relance --night-infinite pour avancer d'un acte.")
    return 0


# --------------------------------------------------------------- vague 4 -----

def do_city(args, building: str) -> int:
    state = read_state()
    try:
        item = wave4.develop_city(state, building) if building else wave4.city_status(state)
    except ValueError as exc:
        print(f"doot : {exc}")
        return 2
    write_state(state)
    if building:
        note_succes(args, "city", level=item["level"])
    print(f"{item['name']} — niveau {item['level']} — {item['bones']} os")
    for place in item["buildings"]:
        print(f"  {place['id']:<10} niv. {place['level']}  prochain cout {place['cost']} — {place['effect']}")
    return 0


def do_relics(args, wanted: str) -> int:
    state = read_state()
    try:
        item = wave4.equip_relic(state, wanted) if wanted else wave4.reliquary(state)
    except ValueError as exc:
        print(f"doot : {exc}")
        return 2
    write_state(state)
    if wanted:
        note_succes(args, "relic_build", equipped=len(item["equipped"]))
    print(f"Reliquaire — {len(item['equipped'])}/{item['slots']} emplacement(s)")
    for relic in item["items"]:
        marker = "*" if relic["equipped"] else ("+" if relic["owned"] else "?")
        print(f"  {marker} {relic['id']:<20} {relic['name']} — {relic['effect']} +{relic['power']}")
    return 0


def do_factions(args, wanted: str) -> int:
    state = read_state()
    try:
        item = wave4.pledge_faction(state, wanted) if wanted else wave4.faction_status(state)
    except ValueError as exc:
        print(f"doot : {exc}")
        return 2
    write_state(state)
    print("Factions de la Cite des Os :")
    for faction in item["factions"]:
        marker = "*" if faction["id"] == item["pledge"] else " "
        print(f" {marker} {faction['id']:<8} {faction['name']} — reputation {faction['reputation']}")
        print(f"    {faction['motto']}")
    return 0


def do_faction_mission(args, seed: str) -> int:
    state = read_state()
    try:
        item = wave4.faction_mission(state, seed)
    except ValueError as exc:
        print(f"doot : {exc}")
        return 2
    write_state(state)
    note_succes(args, "faction", reputation=item["reputation"])
    print(f"Mission : {item['title']} — +{item['gain']} reputation ({item['reputation']}).")
    return 0


def do_nemesis(args, formation: str) -> int:
    state = read_state()
    try:
        item = wave4.confront_nemesis(state, formation) if formation else wave4.nemesis_status(state)
    except ValueError as exc:
        print(f"doot : {exc}")
        return 2
    write_state(state)
    if formation and item["defeated"]:
        note_succes(args, "nemesis", defeated=True)
    print(f"Nemesis : {item['name']} — {item['hp']}/{item['max_hp']} PV — rancune {item['grudge']}")
    print(f"  faiblesse : {item['weakness']} — cicatrices : {', '.join(item['scars']) or 'aucune'}")
    if formation:
        print(f"  {item['damage']} degats{' — CONTRE PARFAIT' if item['counter'] else ''}")
    return 0


def do_investigation(args, seed: str) -> int:
    state = read_state()
    current = wave4.investigation_status(state)
    item = wave4.start_investigation(state, seed) if seed or not current.get("active") else current
    write_state(state)
    print(f"Enquete : {item['title']} — {len(item['found'])} indice(s), {item['remaining']} restant(s)")
    print("  suspects : " + ", ".join(item["suspects"]))
    print("  indices : " + (", ".join(item["found"]) or "aucun"))
    return 0


def do_investigate(args, action: str) -> int:
    state = read_state()
    try:
        item = wave4.investigate(state, action)
    except ValueError as exc:
        print(f"doot : {exc}")
        return 2
    write_state(state)
    if item.get("solved"):
        note_succes(args, "investigation", solved=True)
    print(f"Enquete {item['title']} — {'RESOLUE' if item.get('solved') else str(item['remaining']) + ' indice(s) restant(s)' }.")
    print("  trouves : " + (", ".join(item["found"]) or "aucun"))
    return 0


def do_ghost_export(args, destination: str) -> int:
    expedition = wave3.expedition_status(read_state())
    decisions = [entry.get("choice", "") for entry in expedition.get("decisions", [])]
    run = {"seed": expedition.get("seed", date.today().isoformat()),
           "time_ms": args.ghost_time, "decisions": decisions}
    try:
        path = wave4.export_ghost(run, Path(destination).expanduser())
    except (OSError, ValueError) as exc:
        print(f"doot : export fantome impossible : {exc}")
        return 2
    print(f"doot : fantome de course -> {path}")
    return 0


def do_ghost_race(args, source: str, elapsed: str) -> int:
    state = read_state()
    try:
        item = wave4.race_ghost(state, Path(source).expanduser(), int(elapsed))
    except (OSError, ValueError) as exc:
        print(f"doot : course fantome impossible : {exc}")
        return 2
    write_state(state)
    if item["won"]:
        note_succes(args, "ghost_race", won=True)
    result = "VICTOIRE" if item["won"] else "DEFAITE"
    print(f"Course fantome : {result} — toi {item['player_time_ms']} ms, spectre {item['ghost_time_ms']} ms.")
    return 0


def do_adaptive_score(args) -> int:
    state = read_state()
    item = wave4.adaptive_score(state, args.score_danger, args.score_combo, args.score_boss)
    write_state(state)
    if item["intensity"] >= .5:
        note_succes(args, "adaptive_score", intensity=item["intensity"])
    print(f"Partition adaptative — intensite {item['intensity']:.0%}, {item['tempo']} BPM, {item['key']}")
    print("  " + ", ".join(f"{key} {value:.0%}" for key, value in item["stems"].items()))
    return 0


def do_director(args, destination: str) -> int:
    try:
        path = wave4.director_studio(Path(destination).expanduser())
    except OSError as exc:
        print(f"doot : studio realisateur impossible : {exc}")
        return 2
    note_succes(args, "director", exported=True)
    print(f"doot : mode realisateur -> {path}")
    return 0


def do_photo_booth(args, destination: str) -> int:
    state = read_state()
    try:
        path = wave4.photo_booth(state, Path(destination).expanduser(), args.photo_pose)
    except OSError as exc:
        print(f"doot : photomaton impossible : {exc}")
        return 2
    write_state(state)
    note_succes(args, "director", exported=True)
    print(f"doot : portrait du photomaton -> {path}")
    return 0


def do_remote(args, destination: str) -> int:
    try:
        item = wave4.remote_card(args.remote_host, args.remote_port,
                                 Path(destination).expanduser())
    except (OSError, ValueError) as exc:
        print(f"doot : appairage impossible : {exc}")
        return 2
    print(f"doot : carte QR de telecommande -> {item['path']}")
    print(f"  adresse locale : {item['url']}")
    return 0


def do_remote_serve(args, destination: str) -> int:
    try:
        item = wave4.remote_card(args.remote_host, args.remote_port,
                                 Path(destination).expanduser())
    except (OSError, ValueError) as exc:
        print(f"doot : appairage impossible : {exc}")
        return 2

    commands = {"doot": ("--once", "--ignore-season"), "pause": ("--snooze", "30m"),
                "resume": ("--resume",), "stop": ("--stop",)}

    def launch(action: str) -> None:
        kwargs = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL,
                  "stderr": subprocess.DEVNULL}
        if os.name == "nt":
            kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        else:
            kwargs["start_new_session"] = True
        subprocess.Popen([sys.executable, "-m", "doot", *commands[action]], **kwargs)

    print(f"Telecommande locale : {item['url']}")
    print(f"  QR : {item['path']} — Ctrl+C pour fermer et invalider le jeton.")
    try:
        wave4.serve_remote(args.remote_host, args.remote_port, item["token"], launch)
    except (OSError, KeyboardInterrupt) as exc:
        if isinstance(exc, KeyboardInterrupt):
            print("\ndoot : telecommande fermee.")
            return 0
        print(f"doot : serveur local impossible : {exc}")
        return 2
    return 0


def do_workshop_validate(args, source: str) -> int:
    try:
        item = wave4.validate_workshop(Path(source).expanduser())
    except ValueError as exc:
        print(f"doot : atelier : {exc}")
        return 2
    if item["valid"]:
        note_succes(args, "workshop", valid=True)
    print(f"Atelier communautaire : {'VALIDE' if item['valid'] else 'REFUSE'} — {item['files']} fichier(s)")
    print(f"  sha256 {item['sha256']}")
    for issue in item["issues"]:
        print(f"  ! {issue}")
    return 0 if item["valid"] else 2


def do_night_calendar(args, days: int) -> int:
    print("Calendrier vivant de la crypte :")
    for item in wave4.seasonal_calendar(days=days):
        print(f"  {item['date']}  {item['name']} — {item['rule']}")
    return 0


def do_glyphs(args) -> int:
    item = wave4.glyph_status(read_state())
    print(f"Langue ancienne — {len(item['found'])}/{item['total']} glyphes dechiffres")
    for glyph in wave4.GLYPHS:
        print(f"  {glyph}  {wave4.GLYPHS[glyph] if glyph in item['found'] else '???'}")
    return 0


def do_glyph_decode(args, glyph: str, word: str) -> int:
    state = read_state()
    try:
        item = wave4.decipher_glyph(state, glyph, word)
    except ValueError as exc:
        print(f"doot : {exc}")
        return 2
    write_state(state)
    if item["complete"] and item["fresh"]:
        note_succes(args, "glyphs", completed=True)
    print(f"doot : {item['glyph']} signifie {item['word']} — {len(item['found'])}/{item['total']}.")
    return 0


def do_story_constellation(args, destination: str) -> int:
    try:
        path = wave4.narrative_constellation(read_state(), Path(destination).expanduser())
    except OSError as exc:
        print(f"doot : constellation narrative impossible : {exc}")
        return 2
    print(f"doot : constellation narrative -> {path}")
    return 0


def do_mirror_boss(args) -> int:
    state = read_state()
    item = wave4.mirror_boss(state)
    write_state(state)
    note_succes(args, "mirror_boss", generated=True)
    print(f"Boss miroir : {item['name']} — puissance {item['power']}")
    print(f"  attaque : {item['attack']} — faiblesse : {item['weakness']}")
    return 0


# --------------------------------------------------------------- vague 5 -----

def _print_catacomb(item: dict) -> None:
    if not item.get("active") and "seed" not in item:
        print("Catacombes : aucune descente active. Lance : doot --catacombs GRAINE")
        return
    print(f"Catacombes {item['seed']} — salle {min(item['room'] + 1, len(item['rooms']))}/"
          f"{len(item['rooms'])} — {item['hp']} PV — torche {item['torch']}")
    if item.get("completed"):
        print("  VICTOIRE — le Geometre rend la carte." if item.get("won") else
              "  DEFAITE — le chemin s'est referme.")
        return
    room = item["current"]
    print(f"  {room['title']} [danger {room['danger']}] — {room['text']}")
    print(f"  gauche : {room['left']} | droite : {room['right']}")


def do_catacombs(args, seed: str) -> int:
    state = read_state()
    item = wave5.catacomb_status(state)
    if seed or not item.get("active"):
        item = wave5.start_catacomb(state, seed)
        write_state(state)
    _print_catacomb(item)
    return 0


def do_catacomb_choose(args, choice: str) -> int:
    state = read_state()
    before = wave5.catacomb_status(state)
    try:
        item = wave5.choose_catacomb(state, choice)
    except ValueError as exc:
        print(f"doot : {exc}")
        return 2
    write_state(state)
    if item.get("won") and not before.get("won"):
        note_succes(args, "catacomb_victory", won=True)
    if len(wave5.bestiary_status(state)["found"]) >= 3:
        note_succes(args, "bestiary", found=len(wave5.bestiary_status(state)["found"]))
    _print_catacomb(item)
    return 0


def do_time_loop(args, action: str) -> int:
    state = read_state()
    before = wave5.time_loop_status(state)
    try:
        item = wave5.advance_time_loop(state, action) if action else before
    except ValueError as exc:
        print(f"doot : {exc}")
        return 2
    write_state(state)
    if item["broken"] and not before["broken"]:
        note_succes(args, "time_loop", broken=True)
    print(f"Boucle temporelle — nuit {item['iteration']} — fissure {item['progress']}/3")
    print("  BRISEE — le matin se souvient de toi." if item["broken"] else f"  indice : {item['hint']}")
    return 0


def do_familiar_skill(args, skill: str) -> int:
    state = read_state()
    before = wave5.familiar_skill_status(state)
    try:
        item = wave5.unlock_familiar_skill(state, skill) if skill else before
    except ValueError as exc:
        print(f"doot : {exc}")
        return 2
    write_state(state)
    if len(item["unlocked"]) > len(before["unlocked"]):
        note_succes(args, "familiar_skill", unlocked=True)
    print(f"Talents de {item['id']} — niveau {item['level']}")
    for talent in item["available"]:
        print(f"  {'*' if talent in item['unlocked'] else '-'} {talent}")
    return 0


def do_bestiary(args, creature: str) -> int:
    state = read_state()
    try:
        item = wave5.observe_creature(state, creature) if creature else wave5.bestiary_status(state)
    except ValueError as exc:
        print(f"doot : {exc}")
        return 2
    write_state(state)
    if len(item["found"]) >= 3:
        note_succes(args, "bestiary", found=len(item["found"]))
    print(f"Bestiaire anime — {len(item['found'])}/{item['total']}")
    for entry in item["entries"]:
        print(f"  {'*' if entry['known'] else '?'} {entry['name'] if entry['known'] else 'Entree inconnue'}"
              + (f" — {entry['lore']}" if entry["known"] else ""))
    return 0


def do_necroforge(args, left: str, right: str) -> int:
    state = read_state()
    try:
        item = wave5.forge_relic(state, left, right)
    except ValueError as exc:
        print(f"doot : {exc}")
        return 2
    write_state(state)
    note_succes(args, "necroforge", crafted=True)
    print(f"Forge necromantique : {item['name']} (puissance {item['power']})")
    print(f"  faveur : {item['boon']} | malediction : {item['curse']}")
    return 0


def do_paranormal_weather(args, days: int) -> int:
    state = read_state()
    current = wave5.witness_weather(state)
    write_state(state)
    note_succes(args, "paranormal_weather", witnessed=True)
    print(f"Meteo paranormale — {current['name']} : {current['effect']}")
    for item in wave5.paranormal_weather(days=days)[1:]:
        print(f"  {item['date']} — {item['name']} : {item['effect']}")
    return 0


def _print_ritual(item: dict) -> None:
    print(f"Grand rituel {item['id']} — {len(item['fragments'])}/{item['target']} fragments — "
          f"{len(item['contributors'])} voix")
    if item["completed"]:
        print("  ACCOMPLI — quelque chose repond sous la cite.")


def do_collective_ritual(args, seed: str) -> int:
    state = read_state()
    item = wave5.ritual_status(state, seed)
    write_state(state)
    _print_ritual(item)
    return 0


def do_ritual_offer(args, fragment: str) -> int:
    state = read_state()
    before = wave5.ritual_status(state)
    try:
        item = wave5.offer_ritual_fragment(state, fragment, partage.identite(paths()["data"]))
    except ValueError as exc:
        print(f"doot : {exc}")
        return 2
    write_state(state)
    if item["completed"] and not before["completed"]:
        note_succes(args, "collective_ritual", completed=True)
    print(f"doot : fragment signe {item['signature']}")
    _print_ritual(item)
    return 0


def do_ritual_export(args, destination: str) -> int:
    try:
        path = wave5.export_ritual(read_state(), Path(destination).expanduser())
    except (OSError, ValueError) as exc:
        print(f"doot : export rituel impossible : {exc}")
        return 2
    print(f"doot : capsule rituelle -> {path}")
    return 0


def do_ritual_import(args, source: str) -> int:
    state = read_state()
    before = wave5.ritual_status(state)
    try:
        item = wave5.import_ritual(state, Path(source).expanduser())
    except (OSError, ValueError) as exc:
        print(f"doot : import rituel impossible : {exc}")
        return 2
    write_state(state)
    if item["completed"] and not before["completed"]:
        note_succes(args, "collective_ritual", completed=True)
    _print_ritual(item)
    return 0


def do_nemesis_invasion(args, seed: str) -> int:
    state = read_state()
    item = wave5.nemesis_invasion_status(state, seed)
    write_state(state)
    print(f"Siege de la Nemesis — phase {item['phase']}/3 — cite {item['city_hp']} PV")
    print("  Repousse !" if item.get("repelled") else "  Choisis : fortifier, contre-attaque ou ruse.")
    return 0


def do_invasion_defend(args, action: str) -> int:
    state = read_state()
    before = wave5.nemesis_invasion_status(state)
    try:
        item = wave5.defend_nemesis_invasion(state, action)
    except ValueError as exc:
        print(f"doot : {exc}")
        return 2
    write_state(state)
    if item.get("repelled") and not before.get("repelled"):
        note_succes(args, "nemesis_invasion", repelled=True)
    print(f"Siege — phase {item['phase']}/3 — cite {item['city_hp']} PV — "
          f"{'repousse' if item.get('repelled') else 'combat en cours'}")
    return 0


def do_tribunal(args, seed: str) -> int:
    state = read_state()
    item = wave5.tribunal_status(state)
    if seed or not item.get("active"):
        item = wave5.start_tribunal(state, seed)
    write_state(state)
    print(f"Tribunal des morts — {item['title']} — accuse : {item['accused']}")
    print(f"  indices {len(item['found'])}/{len(item['found']) + item['remaining']}")
    return 0


def do_tribunal_action(args, action: str) -> int:
    state = read_state()
    try:
        item = wave5.tribunal_action(state, action)
    except ValueError as exc:
        print(f"doot : {exc}")
        return 2
    write_state(state)
    if item["verdict"]:
        note_succes(args, "tribunal", verdict=True)
        print(f"Verdict : {item['verdict']} — {'JUSTE' if item['just'] else 'la crypte conteste'}")
    else:
        print(f"Indice : {item['found'][-1] if item['found'] else 'aucun'}")
    return 0


def do_legacy(args, choice: str) -> int:
    state = read_state()
    try:
        item = wave5.choose_legacy(state, choice)
    except ValueError as exc:
        print(f"doot : {exc}")
        return 2
    write_state(state)
    note_succes(args, "legacy", chosen=True)
    print(f"Heritage NG+{item['level']} — {item['choice']} : {item['effect']}")
    print(f"  « {item['dialogue']} »")
    return 0


def do_campaign_lab(args, destination: str) -> int:
    try:
        path = wave5.campaign_lab(Path(destination).expanduser())
    except OSError as exc:
        print(f"doot : laboratoire impossible : {exc}")
        return 2
    print(f"doot : laboratoire de campagne -> {path}")
    return 0


def do_campaign_check(args, source: str) -> int:
    try:
        item = wave5.validate_campaign(Path(source).expanduser())
    except ValueError as exc:
        print(f"doot : {exc}")
        return 2
    if item["valid"]:
        note_succes(args, "campaign_validate", valid=True)
        print(f"doot : campagne valide — {item['chapters']} chapitre(s) — {item['sha256'][:12]}")
        return 0
    print("doot : campagne invalide — " + "; ".join(item["issues"]))
    return 2


def do_personal_museum(args, destination: str) -> int:
    try:
        path = wave5.museum_gallery(read_state(), succes.CATALOGUE,
                                    Path(destination).expanduser())
    except OSError as exc:
        print(f"doot : musee impossible : {exc}")
        return 2
    note_succes(args, "personal_museum", exported=True)
    print(f"doot : musee personnel -> {path}")
    return 0


def do_seals(args) -> int:
    item = wave5.seal_status(read_state())
    print(f"Les Sept Sceaux — {len(item['found'])}/{item['total']}")
    for entry in item["entries"]:
        print(f"  [{'OUVERT' if entry['found'] else 'FERME '}] {entry['title']} — "
              f"{entry['hint']} [{entry['source']}]")
    return 0


def do_seal_submit(args, seal: str, answer: str) -> int:
    state = read_state()
    try:
        item = wave5.submit_seal(state, seal, answer)
    except ValueError as exc:
        print(f"doot : {exc}")
        return 2
    write_state(state)
    if item["complete"]:
        note_succes(args, "seven_seals", completed=True)
    print(f"doot : sceau {item['seal']} {'ouvert' if item['fresh'] else 'deja ouvert'} — "
          f"{len(item['found'])}/{item['total']}")
    if item["epilogue"]:
        print("  " + item["epilogue"])
    return 0


# --------------------------------------------------------------- vague 6 -----

def _print_ghost_train(item: dict) -> None:
    if not item.get("active") and "route" not in item:
        print("Dernier Train : aucun voyage actif. Lance : doot --ghost-train GRAINE")
        return
    print(f"Dernier Train — ligne {item['route']} — "
          f"gare {min(item['station'] + 1, len(item['stations']))}/{len(item['stations'])} — "
          f"integrite {item['integrity']} — charbon {item['coal']}")
    if item.get("completed"):
        print("  TERMINUS ATTEINT." if item.get("arrived") else "  LE TRAIN S'EST PERDU.")
        print("  lignes achevees : " + (", ".join(item["completed_routes"]) or "aucune"))
        return
    station = item["current"]
    print(f"  {station['name']} [danger {station['danger']}] — {station['signal']}")
    print("  actions : explorer, negocier, accelerer")


def do_ghost_train(args, seed: str) -> int:
    state = read_state()
    item = wave6.ghost_train_status(state)
    try:
        if seed or args.train_route or not item.get("active"):
            item = wave6.start_ghost_train(state, seed, args.train_route)
            write_state(state)
    except ValueError as exc:
        print(f"doot : {exc}")
        return 2
    _print_ghost_train(item)
    return 0


def do_train_choose(args, action: str) -> int:
    state = read_state()
    before_routes = set(wave6.completed_train_routes(state))
    try:
        item = wave6.choose_ghost_train(state, action)
    except ValueError as exc:
        print(f"doot : {exc}")
        return 2
    write_state(state)
    fresh = bool(item.get("arrived") and item.get("route") not in before_routes)
    if fresh:
        note_succes(args, "ghost_train", arrived=True, fresh=True,
                    routes=len(item["completed_routes"]))
    _print_ghost_train(item)
    return 0


def do_spectral_crew(args, member: str) -> int:
    state = read_state()
    before = wave6.spectral_crew_status(state)
    try:
        item = wave6.recruit_spectral_crew(state, member) if member else before
    except ValueError as exc:
        print(f"doot : {exc}")
        return 2
    write_state(state)
    if item["complete"] and not before["complete"]:
        note_succes(args, "spectral_crew", complete=True)
    print(f"Equipage spectral — {len(item['recruited'])}/{item['total']}")
    for crew in item["members"]:
        print(f"  {'*' if crew['recruited'] else '-'} {crew['name']} — {crew['role']} : {crew['gift']}")
    return 0


def do_rail_case(args, seed: str) -> int:
    state = read_state()
    item = wave6.rail_case_status(state)
    if seed or not item.get("active"):
        item = wave6.start_rail_case(state, seed)
        write_state(state)
    print(f"Affaire du rail — {item['title']}")
    print(f"  indices {len(item['found'])}/{len(item['found']) + item['remaining']} — "
          f"suspects : {', '.join(item['suspects'])}")
    return 0


def do_rail_investigate(args, action: str) -> int:
    state = read_state()
    before = wave6.rail_case_status(state)
    try:
        item = wave6.investigate_rail_case(state, action)
    except ValueError as exc:
        print(f"doot : {exc}")
        return 2
    write_state(state)
    if item["solved"] and not before.get("solved"):
        note_succes(args, "rail_case", solved=True)
    if item["verdict"]:
        print(f"Affaire classee — accuse : {item['verdict']} — "
              f"{'RESOLUE' if item['solved'] else 'fausse piste'}")
    else:
        print(f"Affaire du rail — {len(item['found'])} indice(s), "
              f"{len(item['questioned'])} interrogatoire(s)")
    return 0


def do_archaeology(args, site: str) -> int:
    state = read_state()
    try:
        item = wave6.dig_archaeology(state, site) if site else wave6.archaeology_status(state)
    except ValueError as exc:
        print(f"doot : {exc}")
        return 2
    write_state(state)
    if len(item["fragments"]) >= item["fragment_total"]:
        note_succes(args, "archaeology", restored=False, fragments=len(item["fragments"]))
    print(f"Archeologie interdite — {len(item['fragments'])}/{item['fragment_total']} fragments — "
          f"{len(item['restored'])} artefact(s) restaure(s)")
    if site:
        print(f"  {item['site']} : {item['fragment']} {'(nouveau)' if item['fresh'] else '(deja connu)'}")
    for entry in item["sites"]:
        print(f"  {entry['id']} — {entry['found']}/{entry['total']} — {entry['artifact']}")
    return 0


def do_restore_artifact(args, site: str) -> int:
    state = read_state()
    try:
        item = wave6.restore_artifact(state, site)
    except ValueError as exc:
        print(f"doot : {exc}")
        return 2
    write_state(state)
    if item["fresh"]:
        note_succes(args, "archaeology", restored=True, fragments=len(item["fragments"]))
    print(f"doot : artefact restaure — {item['artifact']}")
    return 0


def do_black_market(args, action: str) -> int:
    state = read_state()
    try:
        item = (wave6.black_market_action(state, action, args.market_seed) if action else
                wave6.black_market_status(state, args.market_seed))
    except ValueError as exc:
        print(f"doot : {exc}")
        return 2
    write_state(state)
    if item.get("detected"):
        note_succes(args, "black_market", detected=True)
    print(f"Marche noir {item['id']} — {item['tickets']} billets")
    for offer in item["offers"]:
        verdict = f" — {offer['verdict']}" if offer.get("verdict") else ""
        sold = " — vendu" if offer.get("bought") else ""
        print(f"  {offer['id']} — {offer['name']} — {offer['price']} billets — "
              f"rival {offer['rival']}{verdict}{sold}")
    return 0


def do_prophecy(args, action: str) -> int:
    state = read_state()
    before = wave6.prophecy_status(state)
    try:
        item = wave6.resolve_prophecy(state, action) if action else before
    except ValueError as exc:
        print(f"doot : {exc}")
        return 2
    write_state(state)
    if item["completed"] and not before["completed"]:
        note_succes(args, "prophecy", completed=True)
    print(f"Prophetie {item['id']} — {item['text']}")
    print("  accomplie" if item["completed"] else
          f"  echouee ({item['reason']})" if item["failed"] else "  en attente")
    if item["lost_station"]:
        print("  Une gare absente vient d'apparaitre sur la carte.")
    return 0


def do_crypt_gazette(args, destination: str) -> int:
    state = read_state()
    try:
        path = wave6.export_crypt_gazette(state, Path(destination).expanduser())
    except OSError as exc:
        print(f"doot : gazette impossible : {exc}")
        return 2
    write_state(state)
    note_succes(args, "crypt_gazette", exported=True)
    print(f"doot : Gazette de la Crypte -> {path}")
    return 0


def do_musical_battle(args, seed: str) -> int:
    state = read_state()
    item = wave6.musical_battle_status(state)
    if seed or not item.get("active"):
        item = wave6.start_musical_battle(state, seed)
        write_state(state)
    print(f"Combat musical — mesure {item['round'] + 1}/{len(item['score'])} — "
          f"toi {item['player_hp']} PV / spectre {item['boss_hp']} PV")
    print(f"  signal : {item['cue']}" if item.get("active") else
          "  VICTOIRE" if item.get("won") else "  silence fatal")
    return 0


def do_battle_note(args, note: str) -> int:
    state = read_state()
    before = wave6.musical_battle_status(state)
    try:
        item = wave6.musical_battle_action(state, note)
    except ValueError as exc:
        print(f"doot : {exc}")
        return 2
    write_state(state)
    if item.get("won") and not before.get("won"):
        note_succes(args, "musical_battle", won=True)
    print(f"Combat musical — toi {item['player_hp']} PV / spectre {item['boss_hp']} PV")
    print(f"  signal suivant : {item['cue']}" if item.get("active") else
          "  VICTOIRE" if item.get("won") else "  DEFAITE")
    return 0


def do_funeral_house(args, house: str) -> int:
    state = read_state()
    try:
        item = wave6.pledge_funeral_house(state, house) if house else wave6.funeral_house_status(state)
    except ValueError as exc:
        print(f"doot : {exc}")
        return 2
    write_state(state)
    print(f"Maisons funeraires — serment : {item.get('name') or 'aucun'} — "
          f"reputation {item['reputation']}")
    for entry in item["houses"]:
        print(f"  {entry['id']} — {entry['name']} : {entry['motto']}")
    if item.get("pledged"):
        print(f"  prochaine ceremonie : {item['mission']}")
    return 0


def do_house_mission(args, strategy: str) -> int:
    state = read_state()
    before = wave6.funeral_house_status(state)
    try:
        item = wave6.funeral_house_mission(state, strategy)
    except ValueError as exc:
        print(f"doot : {exc}")
        return 2
    write_state(state)
    if item["reputation"] >= 3 and before["reputation"] < 3:
        note_succes(args, "funeral_house", reputation=item["reputation"])
    print(f"Mission de maison — {'reussie' if item['success'] else 'ratee'} — "
          f"reputation {item['reputation']} — prochaine : {item['mission']}")
    return 0


def do_mod_forge(args, destination: str, name: str, theme: str) -> int:
    try:
        path = wave6.create_mod_capsule(Path(destination).expanduser(), name, theme)
        item = wave6.validate_mod_capsule(path)
    except (OSError, ValueError) as exc:
        print(f"doot : creation du mod impossible : {exc}")
        return 2
    note_succes(args, "mod_capsule", valid=True)
    print(f"doot : mod {item['name']} ({item['theme']}) -> {path}")
    return 0


def do_mod_validate(args, source: str) -> int:
    try:
        item = wave6.validate_mod_capsule(Path(source).expanduser())
    except ValueError as exc:
        print(f"doot : {exc}")
        return 2
    note_succes(args, "mod_capsule", valid=True)
    print(f"doot : capsule valide — {item['name']} — {item['sha256'][:12]}")
    return 0


def do_train_replay(args, destination: str) -> int:
    state = read_state()
    try:
        path = wave6.export_scene_replay(state, Path(destination).expanduser())
    except OSError as exc:
        print(f"doot : replay impossible : {exc}")
        return 2
    write_state(state)
    note_succes(args, "train_replay", exported=True)
    print(f"doot : replay du Dernier Train -> {path}")
    return 0


def do_lost_station(args, action: str) -> int:
    state = read_state()
    before = wave6.lost_station_status(state)
    try:
        item = wave6.visit_lost_station(state, action) if action else before
    except ValueError as exc:
        print(f"doot : {exc}")
        return 2
    write_state(state)
    if item["visited"] and not before["visited"]:
        note_succes(args, "lost_station", visited=True)
    print(f"Gare Zero — {'VISIBLE' if item['unlocked'] else 'absente'} — "
          f"{'visitee' if item['visited'] else item['hint']}")
    return 0


def do_thirteenth_bell(args, answer: str) -> int:
    state = read_state()
    before = wave6.thirteenth_bell_status(state)
    try:
        item = wave6.ring_thirteenth_bell(state, answer) if answer else before
    except ValueError as exc:
        print(f"doot : {exc}")
        return 2
    write_state(state)
    if item["rung"] and not before["rung"]:
        note_succes(args, "thirteenth_bell", rung=True)
    print(f"Treizieme Cloche — {item['found']}/{item['total']} echos")
    for clue in item["clues"]:
        print(f"  [{'*' if clue['found'] else ' '}] {clue['hint']}")
    if item["epilogue"]:
        print("  " + item["epilogue"])
    return 0


def do_snooze(args, value: str) -> int:
    try:
        until = schedule.duration(value)
    except ValueError as exc:
        print(f"doot : {exc}")
        return 2
    etat = read_state()
    etat["snooze_until"] = until.isoformat(timespec="seconds")
    write_state(etat)
    print(f"doot : la crypte dort jusqu'au {until:%d/%m/%Y a %H:%M}.")
    return 0


def do_resume(args) -> int:
    etat = read_state()
    etat.pop("snooze_until", None)
    write_state(etat)
    print("doot : la crypte est reveillee.")
    return 0


def do_schedule_profile(args, name: str) -> int:
    try:
        profiles.schedule_profile(
            profiles_path(), name, args.schedule_window, args.schedule_days,
        )
    except profiles.ProfileError as exc:
        print(f"doot : {exc}")
        return 2
    print(f"doot : profil '{name}' planifie {args.schedule_window} ({args.schedule_days}).")
    return 0


def do_unschedule_profile(args, name: str) -> int:
    try:
        profiles.unschedule_profile(profiles_path(), name)
    except profiles.ProfileError as exc:
        print(f"doot : {exc}")
        return 2
    print(f"doot : planification de '{name}' retiree.")
    return 0


def do_codex(args) -> int:
    """Montre les apparitions decouvertes et garde les autres dans l'ombre."""

    etat = read_state()
    decouverts = codex.vus(etat)
    courant, total = codex.progression(etat)
    print(f"Codex des apparitions : {courant}/{total} decouvertes")
    for apparition in codex.CATALOGUE:
        if apparition.identifiant in decouverts:
            print(f"\n  [VU] {apparition.titre}")
            print(f"       {apparition.description}")
        else:
            print("\n  [???] Apparition inconnue")
            print(f"        Indice : {apparition.indice}")
    print("\nLes rencontres locales se forcent avec doot --event NOM ; "
          "la contagion doit venir d'une autre machine.")
    return 0


def do_duel_name(args, wanted: str) -> int:
    """Donne un nom lisible a cette replique dans le classement partage."""
    etat = read_state()
    try:
        name = duel.set_name(etat, wanted)
    except ValueError as exc:
        print(f"doot : {exc}")
        return 2
    write_state(etat)
    print(f"doot : combattant nomme {name}")
    return 0


def do_duel_board(args) -> int:
    """Actualise si possible, puis affiche le classement de la saison."""
    sync_tour(args)
    etat = read_state()
    year = duel.season_year()
    rows = duel.standings(etat, year)
    print(f"Duel de doot - saison {year}")
    if not rows:
        print("  aucun doot compte pour le moment")
        print("\nChoisir son nom : doot --duel-name NOM")
        return 0
    for rank, row in enumerate(rows, 1):
        marker = " <- toi" if row.machine == succes.machine(etat) else ""
        print(
            f"  {rank:>2}. {row.name:<32} {row.doots:>6} doots  "
            f"{row.specials:>3} speciaux{marker}"
        )
    return 0


def note_melodie(jouee: bool) -> None:
    """Enregistre ce que ce declenchement a donne.

    Le compteur vit dans le fichier d'etat et pas en memoire : le daemon
    repart a chaque ouverture de session, et une pitie remise a zero aussi
    souvent ne bornerait plus rien.
    """
    etat = read_state()
    depuis = state_compteur(etat, "depuis_melodie")
    etat["depuis_melodie"] = 0 if jouee else depuis + 1
    write_state(etat)


def emit_melodie_tiree(args, fichier, journal: bool = False, repli=None) -> bool:
    """Joue la melodie tiree au sort ; faux si elle etait illisible.

    Le repli sur des doots ne vaut pas melodie jouee : rendre faux laisse la
    garantie due au declenchement suivant, au lieu de la repousser d'autant.

    `repli` donne les reglages de ce repli quand ils ne sont pas ceux du
    declenchement. La contagion s'en sert : sa melodie est breve et vient
    d'ailleurs, donc son echec doit rendre un doot bref et non la salve que le
    daemon jouerait de lui-meme.
    """
    from . import melodie

    try:
        morceau = melodie.load(fichier)
    except melodie.MelodieError as exc:
        log(f"melodie illisible ({fichier.name}) : {exc}", quiet=args.quiet)
        emit_doots(repli if repli is not None else args, journal=journal)
        return False

    emit_melodie(args, morceau)
    note_melodie_jouee(args, fichier, morceau)
    if journal:
        log(f"melodie : {morceau.name or fichier.stem} !", quiet=args.quiet)
    return True


def emit_melodie(args, morceau) -> None:
    """Affiche le squelette jouant `morceau`, son et hochements compris."""
    from . import melodie, window

    p = paths()

    wav = None
    if not args.no_sound:
        try:
            wav = melodie.render(p["data"] / "melodie.wav", morceau, args.transpose)
        except Exception as exc:
            log(f"melodie indisponible : {exc}", quiet=args.quiet)

    picture = None
    if not args.no_image:
        try:
            picture = image.pick_image(p["image"], args.image)
        except Exception as exc:
            log(f"image indisponible : {exc}", quiet=args.quiet)

    voice_beats = [
        melodie.onsets(morceau, args.transpose, voice=index)
        for index in range(len(morceau.voices))
    ]
    animation = {"beats": voice_beats[0]}
    if len(voice_beats) > 1:
        animation["voices"] = voice_beats
    window.show(
        wav_path=wav,
        duration=melodie.duration(morceau),
        image_path=picture,
        **animation,
        **display_options(args),
    )


def do_melodies(args) -> int:
    """Liste les melodies jouables : les tiennes, puis celles fournies."""
    from . import melodie

    p = paths()
    groupes = (("perso", melodie.custom(p["melodies"])), ("fournies", melodie.bundled()))
    for titre, fichiers in groupes:
        print(f"{titre} ({p['melodies'] if titre == 'perso' else melodie.MELODIES_DIR})")
        if not fichiers:
            print("  (aucune)")
        for fichier in fichiers:
            try:
                morceau = melodie.load(fichier)
                voix = "" if len(morceau.voices) == 1 else f", {len(morceau.voices)} voix"
                detail = (f"{morceau.name} - {len(morceau.pitches())} notes{voix}, "
                          f"{morceau.tempo:.0f} BPM, {melodie.duration(morceau):.0f} s")
            except melodie.MelodieError as exc:
                detail = f"illisible : {exc}"
            print(f"  {fichier.stem:<28} {detail}")
    print("\nJouer : doot --play NOM   (ou un chemin vers un .rtttl)")
    return 0


def sync_tour(args) -> list[dict]:
    """Un tour complet, annonces et signaux contagieux compris."""
    if not partage.reglage(paths()["data"]).get("cle"):
        return []
    etat = read_state()
    nouveaux = partage.cycle(etat, paths()["data"])
    signaux = contagion.vider(etat)
    write_state(etat)
    annoncer_succes(args, nouveaux)
    return signaux


def propager_contagion(args, charge=None, rng=random) -> bool:
    """Publie parfois dans la crypte partagee ce qui vient d'etre joue ici.

    La charge decrit le declenchement qui vient d'aboutir. Sans elle, le signal
    reste le doot ordinaire d'avant : un declenchement rate n'a rien a faire
    voyager.
    """

    if args.no_contagion or not partage.reglage(paths()["data"]).get("cle"):
        return False
    if rng.random() >= args.contagion_chance:
        return False
    genre, nom = charge or ("doot", "")
    etat = read_state()
    etat["contagion_sortante"] = contagion.creer(
        succes.machine(etat), genre=genre, nom=nom,
    )
    write_state(etat)
    return True


def melodie_locale(nom: str):
    """La melodie que ce poste connait sous ce nom, ou rien.

    Une egalite sur le catalogue d'ici, jamais une recherche par chemin :
    `melodie.find` ouvrirait le fichier designe des que le nom finit en .rtttl,
    et ce nom-la vient d'une autre machine.
    """
    from . import melodie

    if not nom:
        return None
    dossier = paths()["melodies"]
    for candidat in melodie.custom(dossier) + melodie.bundled():
        if candidat.stem.casefold() == nom:
            return candidat
    return None


def contagion_configuree(args, signal: dict):
    """Les reglages du doot bref : court, sur place, entrant par un bord."""

    configured = copy.copy(args)
    configured.burst_min = configured.burst_max = 1
    configured.duration = 2.8
    configured.formation = "random"
    configured.mise_en_scene = "salve"
    source_key = str(signal.get("source", ""))
    configured.side = "left" if sum(map(ord, source_key)) % 2 else "right"
    configured.no_slide = False
    configured.spin = False
    return configured


def emit_parade_contagieuse(args, signal: dict, journal: bool = True) -> bool:
    """Attend l'heure commune puis joue la melodie ou la parade de repli."""

    try:
        instant = datetime.fromisoformat(signal["execute_at"].replace("Z", "+00:00"))
        delay = (instant.astimezone(timezone.utc) - _utc_now()).total_seconds()
        if delay > 0:
            time.sleep(min(CONTAGION_POLL_SECONDS + 10.0, delay))
    except (KeyError, AttributeError, TypeError, ValueError):
        pass

    if journal:
        log(f"PARADE DE FLOTTE : signal recu de {signal.get('source', '?')}.",
            quiet=args.quiet)
    name = str(signal.get("name", ""))
    if name and not args.no_melody:
        path = melodie_locale(name)
        if path is not None:
            return emit_melodie_tiree(args, path, journal=journal)

    if args.no_event:
        return emit_doots(contagion_configuree(args, signal), journal=journal,
                          evenement="contagion") > 0
    from . import evenements

    event = evenements.find("parade", data_path("events", "events"))
    return bool(event and emit_evenement(args, event, journal=journal))


def emit_contagion(args, signal: dict, journal: bool = True) -> bool:
    """Fait surgir ici ce qu'une autre machine vient de jouer chez elle.

    Ce qui traverse reste une contagion aux yeux du Codex, meme quand c'est une
    parade ou un rickroll : la rencontre rare a ete vue la-bas, et la compter
    ici une seconde fois ferait d'une flotte un moyen de les collectionner.

    Les refus du poste l'emportent sur ce que le signal demande. Un poste qui a
    coupe les melodies ou les rencontres recoit le doot, pas le reste.
    """
    from . import evenements

    if signal.get("kind") == "parade":
        return emit_parade_contagieuse(args, signal, journal=journal)

    genre, nom = contagion.charge(signal)
    source = signal.get("source", "une autre machine")

    if genre == "evenement" and not args.no_event:
        evenement = evenements.find(nom, data_path("events", "events"))
        if evenement is not None:
            if journal:
                log(f"DOOT CONTAGIEUX : {source} a vu {evenement.titre}.",
                    quiet=args.quiet)
            configured = evenements.configure(copy.copy(args), evenement)
            return emit_doots(configured, journal=journal, evenement="contagion") > 0

    if genre == "melodie" and not args.no_melody:
        fichier = melodie_locale(nom)
        if fichier is not None:
            if journal:
                log(f"DOOT CONTAGIEUX : {source} joue {fichier.stem}.",
                    quiet=args.quiet)
            joue = emit_melodie_tiree(
                args, fichier, journal=journal,
                repli=contagion_configuree(args, signal),
            )
            note_succes(args, "apparition", nom="contagion")
            return joue

    if journal:
        log(f"DOOT CONTAGIEUX : signal recu de {source}.", quiet=args.quiet)
    return emit_doots(contagion_configuree(args, signal), journal=journal,
                      evenement="contagion") > 0


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def do_fleet_parade(args, name: str) -> int:
    """Publie une apparition horodatee puis la joue localement au meme instant."""

    if not args.ignore_season and not season.in_season():
        print(f"doot : {season.describe()}")
        return 3
    if not partage.reglage(paths()["data"]).get("cle"):
        print("doot : ouvre d'abord un partage avec --sync-init.")
        return 2
    now = _utc_now()
    # Le daemon distant relit la crypte toutes les trente secondes : cinq
    # secondes de marge apres ce tour garantissent qu'il voie le signal avant
    # le depart, au lieu de jouer une parade simplement "a peu pres" ensemble.
    execute_at = now + timedelta(seconds=CONTAGION_POLL_SECONDS + 5)
    etat = read_state()
    signal = contagion.creer(
        succes.machine(etat), now=now, kind="parade", name=name,
        execute_at=execute_at,
    )
    etat["contagion_sortante"] = signal
    write_state(etat)
    sync_tour(args)
    note_succes(args, "parade_flotte", nom=name or "parade")
    print(f"doot : parade publiee, depart synchronise a {execute_at.astimezone():%H:%M:%S}.")
    delay = (execute_at - _utc_now()).total_seconds()
    if delay > 0:
        time.sleep(delay)
    return 0 if emit_contagion(args, signal, journal=True) else 1


def jouer_contagions(args, signaux: list[dict]) -> int:
    """Joue les signaux recus sans jamais en faire repartir un autre."""

    joues = 0
    for signal in signaux:
        if not args.ignore_season and not season.in_season():
            break
        joues += int(emit_contagion(args, signal))
    return joues


def attendre_avec_contagion(args, delay: float) -> None:
    """Attend le prochain tirage tout en ecoutant doucement la crypte partagee."""

    if (args.no_contagion or
            not partage.reglage(paths()["data"]).get("cle")):
        time.sleep(delay)
        return

    fin = time.monotonic() + delay
    while True:
        restant = fin - time.monotonic()
        if restant <= 0:
            return
        time.sleep(min(CONTAGION_POLL_SECONDS, restant))
        if fin - time.monotonic() <= 0:
            return
        jouer_contagions(args, sync_tour(args))


def lire_secret(valeur: str) -> str:
    """Le secret tel qu'il a ete donne, ou lu ailleurs si c'est `-`.

    Un secret passe en argument se lit dans `ps` et reste dans l'historique du
    shell. `-` le prend sur l'entree standard : saisie invisible quand il y a
    un terminal, une ligne lue sinon, ce qui laisse `... | doot --sync-secret -`
    utilisable dans un script.
    """
    if valeur != "-":
        return valeur
    if sys.stdin.isatty():
        import getpass
        return getpass.getpass("Secret Access Key : ").strip()
    return sys.stdin.readline().strip()


def do_sync_init(args, cible: str) -> int:
    """Frappe une cle et retient ou publier. `off` coupe tout."""
    p = paths()
    if cible in ("", "off", "-"):
        partage.poser_reglage(p["data"], None)
        etat = read_state()
        etat.pop("sync_note", None)
        write_state(etat)
        print("doot : synchronisation coupee.")
        return 0

    fiche = dict(partage.reglage(p["data"]))
    if cible.startswith("s3://"):
        reste = cible[5:]
        seau, _, prefixe = reste.partition("/")
        fiche.update({"seau": seau, "prefixe": prefixe,
                      "endpoint": args.sync_endpoint or fiche.get("endpoint", ""),
                      "region": args.sync_region or fiche.get("region", "auto"),
                      "cle_acces": args.sync_key_id or fiche.get("cle_acces", ""),
                      "secret": lire_secret(args.sync_secret) or fiche.get("secret", "")})
        fiche.pop("dossier", None)
        for champ in ("cle_acces", "secret"):
            if not fiche[champ]:
                fiche.pop(champ)   # laisse l'environnement repondre
        if not fiche["endpoint"]:
            print("doot : un seau demande --sync-endpoint https://...")
            return 2
    else:
        # La cle survit au changement de depot : la refrapper orphelinerait la
        # flotte, chaque autre poste continuant a publier sous l'ancienne. Le
        # reste de la fiche decrivait un seau et ne decrit plus rien.
        gardees = {champ: fiche[champ]
                   for champ in ("cle", "cles_quittees", "cle_precedente")
                   if fiche.get(champ)}
        fiche = {"dossier": str(Path(cible).expanduser()), **gardees}

    if not fiche.get("cle") or args.sync_force:
        fiche = partage.poser_cle(p["data"], fiche, coffre.en_texte(coffre.creer()))
    else:
        partage.poser_reglage(p["data"], fiche)
    etat = read_state()
    nouveaux = partage.cycle(etat, p["data"])
    write_state(etat)

    note = etat.get("sync_note", {})
    if note.get("erreur"):
        print(f"doot : depot inutilisable, {note['erreur']}")
        return 2

    print(f"doot : partage par {note.get('depot', cible)}")
    print(f"  {note.get('pairs', 0)} autre(s) machine(s) deja presente(s)")
    print("  le daemon publiera et relira a chaque doot")
    print(f"\n  Sur les autres postes :  doot --sync-join {fiche['cle']}")
    print("  Cette cle ouvre toute la flotte. Elle ne se revoque pas :")
    print("  une machine perdue lit tout jusqu'a ce que les autres soient rechiffrees.")
    annoncer_succes(args, nouveaux)
    return 0


def do_sync_join(args, texte: str) -> int:
    """Rejoint une flotte avec la cle recopiee depuis le premier poste."""
    p = paths()
    try:
        coffre.depuis_texte(texte)
    except coffre.CoffreError as exc:
        print(f"doot : {exc}")
        return 2

    fiche = dict(partage.reglage(p["data"]))
    if not fiche.get("dossier") and not fiche.get("seau"):
        print("doot : dis d'abord ou publier (doot --sync-init CHEMIN)")
        return 2

    # L'objet publie sous l'ancienne cle ne serait plus lisible par personne :
    # `poser_cle` retient lesquelles, et le cycle les retire une fois la part
    # republiee sous la neuve.
    fiche = partage.poser_cle(p["data"], fiche, texte.strip())
    etat = read_state()
    nouveaux = partage.cycle(etat, p["data"])
    write_state(etat)

    note = etat.get("sync_note", {})
    if note.get("erreur"):
        print(f"doot : depot inutilisable, {note['erreur']}")
        return 2

    print(f"doot : flotte rejointe, {note.get('pairs', 0)} autre(s) machine(s)")
    annoncer_succes(args, nouveaux)
    return 0


def do_exporter(args, cible: str) -> int:
    """Ecrit de quoi rejoindre cette machine depuis une autre."""
    etat = read_state()
    write_state(etat)

    if cible == "-":
        print(json.dumps(partage.part_exportable(etat), indent=2, ensure_ascii=False))
        return 0

    try:
        chemin = partage.ecrire_part(etat, Path(cible).expanduser())
    except OSError as exc:
        print(f"doot : ecriture impossible, {exc}")
        return 2
    print(f"doot : etat exporte dans {chemin}")
    return 0


def do_fusionner(args, sources) -> int:
    """Fait entrer les succes d'autres machines dans celle-ci."""
    etat = read_state()
    avant_doots = succes.total(etat, "doots")
    avant_score = succes.score(etat)

    lectures = partage.lire_parts(etat, partage.fichiers_de(sources))
    for lecture in lectures:
        detail = f"machine {lecture.machine}" if lecture.fusionnee else lecture.refus
        print(f"  {lecture.nom} : {detail}")
    lus = sum(1 for lecture in lectures if lecture.fusionnee)
    nouveaux = [item for lecture in lectures for item in lecture.debloques]

    if not lus:
        print("doot : rien a fusionner.")
        return 2

    write_state(etat)
    print(f"\n{lus} machine(s) fusionnee(s).")
    print(f"  doots : {avant_doots} -> {succes.total(etat, 'doots')}")
    print(f"  score : {avant_score} -> {succes.score(etat)} points")
    annoncer_succes(args, nouveaux)
    return 0


def do_succes(args) -> int:
    """Affiche le catalogue local, le score et la progression courante."""

    etat = read_state()
    acquis = succes.debloques(etat)
    print(
        f"Succes : {len(acquis)}/{len(succes.CATALOGUE)} debloques - "
        f"{succes.score(etat)} points"
    )
    for definition in succes.CATALOGUE:
        courant, objectif = succes.progression(etat, definition)
        titre, description = succes.visible(etat, definition)
        if definition.identifiant in acquis:
            marque = "[x]"
            detail = f"debloque le {acquis[definition.identifiant]}"
        else:
            marque = "[ ]"
            detail = f"progression {courant}/{objectif}"
        points = f" (+{definition.points})" if not definition.secret or definition.identifiant in acquis else ""
        print(f"  {marque} {titre}{points}")
        print(f"      {description}  {detail}")
    print(f"\nProgression locale : {paths()['state']}")
    fiche = partage.reglage(paths()["data"])
    if not fiche.get("cle"):
        print("Partage             : aucun (doot --sync-init DEPOT)")
    else:
        note = etat.get("sync_note") or {}
        detail = (f"erreur, {note['erreur']}" if note.get("erreur")
                  else f"{note.get('pairs', 0)} autre(s) machine(s)")
        depot = note.get("depot") or fiche.get("dossier") or fiche.get("seau", "?")
        print(f"Partage             : {depot}  ({detail}, "
              f"dernier tour {note.get('quand', 'jamais')})")
    return 0


CASE_ACTIVE = "#"
CASE_VIDE = "."
CASE_HORS = " "


def grille_texte(saison) -> list:
    """La saison en grille : une colonne par semaine, un caractere par soir.

    Les mois s'inscrivent au-dessus de la semaine qui les ouvre, jamais deux
    fois, et la premiere colonne peut deja porter des cases hors saison : la
    saison ne commence pas un lundi toutes les annees.
    """
    marge = max(len(nom) for nom in registre.JOURS) + 4
    entete = " " * marge
    etiquetes = set()
    for index, colonne in enumerate(saison.semaines):
        for jour in colonne:
            if jour is None or jour.month in etiquetes:
                continue
            etiquetes.add(jour.month)
            position = marge + index * 2
            if position >= len(entete):
                entete += " " * (position - len(entete)) + registre.MOIS[jour.month][:3]
            break

    lignes = [entete.rstrip()]
    for rang, nom in enumerate(registre.JOURS):
        cases = []
        for colonne in saison.semaines:
            jour = colonne[rang]
            if jour is None:
                cases.append(CASE_HORS)
            else:
                cases.append(CASE_ACTIVE if jour in saison.actifs else CASE_VIDE)
        lignes.append(f"  {nom}".ljust(marge) + " ".join(cases).rstrip())
    return lignes


def do_stats(args) -> int:
    """Le registre de la crypte : le detail que l'etat garde depuis toujours."""

    etat = read_state()
    bilan = registre.resume(etat)
    ici = succes.machine(etat)

    print("Registre de la crypte")
    print(f"  succes      : {bilan.succes}/{bilan.succes_total}, {bilan.points} points")
    print(f"  codex       : {bilan.codex}/{bilan.codex_total} apparitions")
    print(f"  soirs       : {bilan.jours} depuis la premiere apparition")

    print("\nTotaux")
    lignes = registre.totaux(etat)
    if not lignes:
        print("  (rien encore : doot --once pour ouvrir le registre)")
    for libelle, valeur in lignes:
        print(f"  {libelle:<26}{valeur:>7}")

    print("\nRecords")
    for libelle, valeur in registre.records(etat):
        print(f"  {libelle:<26}{valeur:>7}")

    postes = registre.postes(etat)
    if postes:
        print("\nMachines")
        for poste in postes:
            marque = " (ici)" if poste.machine == ici else ""
            print(f"  {poste.machine + marque:<20}"
                  f"{poste.doots:>7} doots  {poste.declenchements:>6} declenchements  "
                  f"{poste.melodies:>4} melodies  {poste.evenements:>4} rencontres")
        if len(postes) > 1:
            print("  (parts fusionnees ; une machine re-clee compte pour deux)")

    print("\nCollections")
    for libelle, valeurs in registre.collections(etat):
        print(f"  {libelle:<26}{', '.join(valeurs) if valeurs else '(aucune)'}")

    annee = season.last_season_year()
    courante = registre.saison(etat, annee)
    print(f"\nSoirs de doot - saison {annee} : "
          f"{len(courante.actifs)} sur {courante.duree}")
    for ligne in grille_texte(courante):
        print(ligne)
    print(f"  {CASE_ACTIVE} un doot au moins  "
          f"{CASE_VIDE} rien ce soir-la  (la grille ne compte pas, elle constate)")

    autres = [an for an in registre.saisons(etat) if an != annee]
    if autres:
        print("\nSaisons precedentes")
        for an in autres:
            passee = registre.saison(etat, an)
            print(f"  {an} : {len(passee.actifs)} soir(s) sur {passee.duree}")

    print(f"\nProgression locale : {paths()['state']}")
    return 0


def do_profiles(args) -> int:
    """Liste les profils, leur activation et leurs principaux reglages."""

    path = profiles_path()
    document = profiles.read(path)
    print(f"Profils : {path}")
    if not document["profiles"]:
        print("  (aucun)")
        print("\nCreer : doot --save-profile NOM [OPTIONS]")
        return 0
    for name in sorted(document["profiles"], key=str.casefold):
        values = document["profiles"][name]
        marker = "*" if document["active"] == name else " "
        details = []
        if "formation" in values:
            details.append(f"formation={values['formation']}")
        if "burst_min" in values and "burst_max" in values:
            details.append(f"salve={values['burst_min']}-{values['burst_max']}")
        if "min" in values and "max" in values:
            details.append(f"intervalle={values['min']}-{values['max']}s")
        if "event_chance" in values:
            details.append(f"evenements={values['event_chance']:.1%}")
        schedules = [item for item in document.get("schedules", [])
                     if item.get("profile") == name]
        if schedules:
            details.append("horaire=" + ",".join(item["window"] for item in schedules))
        suffix = f"  ({', '.join(details)})" if details else ""
        print(f" {marker} {name}{suffix}")
    print("\n* profil actif, charge automatiquement par le daemon")
    return 0


def do_save_profile(args, name: str) -> int:
    try:
        profiles.save(profiles_path(), name, profiles.from_namespace(args))
    except profiles.ProfileError as exc:
        print(f"doot : {exc}")
        return 2
    print(f"doot : profil '{name}' enregistre -> {profiles_path()}")
    return 0


def do_activate_profile(args, name: str) -> int:
    try:
        profiles.activate(profiles_path(), name)
    except profiles.ProfileError as exc:
        print(f"doot : {exc}")
        return 2
    print(f"doot : profil '{name}' actif par defaut.")
    note_succes(args, "profil", nom=name)
    return 0


def do_deactivate_profile(args) -> int:
    profiles.activate(profiles_path(), None)
    print("doot : aucun profil actif par defaut.")
    return 0


def do_delete_profile(args, name: str) -> int:
    try:
        profiles.delete(profiles_path(), name)
    except profiles.ProfileError as exc:
        print(f"doot : {exc}")
        return 2
    print(f"doot : profil '{name}' supprime.")
    return 0


def sans_affichage() -> bool:
    """Aucun serveur graphique joignable : ni X11, ni Wayland.

    macOS et Windows dessinent sans passer par ces variables, la question ne
    s'y pose pas.
    """
    if sys.platform in ("win32", "darwin"):
        return False
    return not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def _apply_profile_schedule(args, base: dict) -> str | None:
    """Applique le profil de l'horaire courant, ou restaure la configuration de base."""

    selected = profiles.scheduled(profiles_path())
    for key, value in base.items():
        setattr(args, key, value)
    if selected:
        for key, value in profiles.load(profiles_path(), selected).items():
            setattr(args, key, value)
    args._scheduled_profile = selected
    return selected


def do_daemon(args) -> int:
    from . import window

    # L'environnement d'un processus ne change plus une fois qu'il tourne :
    # demarre avant que la session ne publie DISPLAY, le daemon ne le verrait
    # jamais apparaitre et echouerait a chaque doot jusqu'a la deconnexion.
    # Sortir en erreur laisse le superviseur relancer plus tard, avec
    # l'environnement complet.
    if sans_affichage():
        log(
            "aucun affichage joignable : ni DISPLAY ni WAYLAND_DISPLAY. "
            "Sortie en 5, pour etre relance quand la session les aura publies.",
            quiet=args.quiet,
        )
        return 5

    if not claim_pid_file():
        log(f"une instance tourne deja (pid {running_pid()}), sortie.", quiet=args.quiet)
        return 1

    salve = "" if args.burst_max <= 1 else f" - salve {args.burst_min}-{args.burst_max} doots"
    formation = "" if args.formation == "random" else f" - formation {args.formation}"
    profil = f" - profil {args._profile_loaded}" if args._profile_loaded else ""
    rencontres = " - evenements coupes" if args.no_event else \
        f" - evenements {args.event_chance:.1%} (pitie {args.event_pity or 'non'})"
    log(
        f"demarrage (pid {os.getpid()}) - intervalle {args.min}-{args.max}s"
        f"{salve}{formation}{profil}{rencontres} - "
        f"saison {season.SEASON_LABEL}",
        quiet=args.quiet,
    )
    log("pour tout arreter : doot --stop  (desinstaller : voir le README)", quiet=args.quiet)

    base_settings = profiles.from_namespace(args)
    announced_pause = None
    try:
        while True:
            scheduled_profile = _apply_profile_schedule(args, base_settings)
            etat = read_state()
            paused_reason = None
            if schedule.snoozed(etat):
                paused_reason = f"snooze jusqu'a {etat.get('snooze_until')}"
            elif schedule.contains(getattr(args, "quiet_hours", "")):
                paused_reason = f"heures silencieuses {args.quiet_hours}"
            if paused_reason:
                if announced_pause != paused_reason:
                    extra = f" (profil {scheduled_profile})" if scheduled_profile else ""
                    log(f"crypte en pause : {paused_reason}{extra}.", quiet=args.quiet)
                    announced_pause = paused_reason
                time.sleep(60)
                continue
            announced_pause = None
            if not args.ignore_season and not season.in_season():
                wait = min(OUT_OF_SEASON_POLL, max(60.0, season.seconds_until_next_season()))
                log(season.describe(), quiet=args.quiet)
                time.sleep(wait)
                continue

            if run_due_rituals(args):
                continue

            delay = random.randint(args.min, args.max)
            log(f"prochain doot dans {delay}s", quiet=args.quiet)
            attendre_avec_contagion(args, delay)

            if not args.ignore_season and not season.in_season():
                continue  # la saison s'est fermee pendant l'attente

            try:
                charge = None
                rite = rite_du_soir(args)
                evenement = rite or event_roll(args)
                if evenement is not None:
                    evenement_joue = (
                        jouer_le_rite(args, evenement) if rite is not None
                        else emit_evenement(args, evenement, journal=True)
                    )
                    melodie_jouee = False
                    if evenement_joue:
                        charge = ("evenement", evenement.identifiant)
                else:
                    evenement_joue = False
                    fichier = melody_roll(args)
                    if fichier is None:
                        emit_doots(args, journal=True)
                        melodie_jouee = False
                    else:
                        melodie_jouee = emit_melodie_tiree(args, fichier, journal=True)
                        if melodie_jouee:
                            charge = ("melodie", fichier.stem)
                if not args.no_event:
                    note_evenement(evenement_joue)
                note_melodie(melodie_jouee)
                propager_contagion(args, charge)
                jouer_contagions(args, sync_tour(args))
            except window.TkinterMissing as exc:
                log(str(exc), quiet=args.quiet)
                return 4
            except Exception as exc:
                log(f"echec de l'affichage : {exc}", quiet=args.quiet)
    except KeyboardInterrupt:
        log("arret demande.", quiet=args.quiet)
    finally:
        release_pid_file()
        log("arret.", quiet=args.quiet)
    return 0


def do_status(args) -> int:
    p = paths()
    pid = running_pid()
    print(f"doot {__version__}")
    print(f"  saison      : {season.SEASON_LABEL}")
    print(f"  etat        : {season.describe()}")
    print(f"  daemon      : {'actif (pid ' + str(pid) + ')' if pid else 'arrete'}")
    print(f"  donnees     : {p['data']}")
    print(f"  profil      : {args._profile_loaded or 'aucun'}"
          f" (actif : {profiles.active(profiles_path()) or 'aucun'})")
    etat = read_state()
    print(f"  succes      : {len(succes.debloques(etat))}/{len(succes.CATALOGUE)}, "
          f"{succes.score(etat)} points")
    codex_vus, codex_total = codex.progression(etat)
    print(f"  codex       : {codex_vus}/{codex_total} apparitions decouvertes")
    challenge = challenges.daily()
    challenge_state = challenges.status(etat)
    challenge_progress = "termine" if challenge_state["completed"] else \
        f"{challenge_state['progress']}/{challenge.target}"
    print(f"  defi        : {challenge.title} ({challenge_progress})")
    if schedule.snoozed(etat):
        print(f"  sommeil     : jusqu'a {etat.get('snooze_until')}")
    elif args.quiet_hours:
        active = " (actif)" if schedule.contains(args.quiet_hours) else ""
        print(f"  silence     : {args.quiet_hours}{active}")

    sounds = sound.custom_sounds(p["sound"])
    if sounds:
        extra = f" (+{len(sounds) - 1} autre(s), tirage au hasard)" if len(sounds) > 1 else ""
        print(f"  son         : {sounds[0].name}{extra}")
    else:
        chosen = sound.pick_sound(p["wav"], p["sound"])
        origin = "fourni" if chosen == sound.BUNDLED_SOUND else "jingle synthetise"
        print(f"  son         : {chosen.name} ({origin})")
    print(f"  sons perso  : {p['sound']}  ({len(sounds)} fichier(s))")

    pictures = image.custom_images(p["image"])
    if pictures:
        extra = f" (+{len(pictures) - 1} autre(s), tirage au hasard)" if len(pictures) > 1 else ""
        print(f"  image       : {pictures[0].name}{extra}")
    elif image.bundled_image():
        print(f"  image       : {image.BUNDLED_IMAGE.name} (fournie)")
    else:
        print("  image       : ASCII art (depose un PNG/GIF dans le dossier ci-dessous)")
    print(f"  images      : {p['image']}  ({len(pictures)} fichier(s))")

    from . import melodie

    print(f"  melodies    : {len(melodie.bundled())} fournie(s), "
          f"{len(melodie.custom(p['melodies']))} perso dans {p['melodies']}")

    from . import screens, window

    found = window.active_monitors()
    target = "au hasard" if args.screen in (None, "", "random") else f"--screen {args.screen}"
    print(f"  ecrans      : {screens.describe(found)} -> apparition {target}")
    if args.burst_max > 1:
        print(f"  salve       : {args.burst_min} a {args.burst_max} doots par "
              f"declenchement, {args.burst_delay}s entre chacun")
    if args.formation != "random":
        print(f"  formation   : {args.formation}")
    if args.no_event:
        print("  evenements  : coupes")
    else:
        garantie = str(args.event_pity) if args.event_pity else "aucune"
        print(f"  evenements  : chance {args.event_chance:.1%}, garantie {garantie}")
    if partage.reglage(p["data"]).get("cle"):
        contagieux = "coupe" if args.no_contagion else f"chance {args.contagion_chance:.1%}"
        print(f"  contagion   : {contagieux}")

    print(f"  journal     : {p['log']}")
    if sys.platform == "win32":
        print("  lecteur     : winsound + MCI (integres)")
    else:
        player = sound.find_player()
        print(f"  lecteur     : {player[0] if player else 'AUCUN (installe mpv/ffmpeg/pipewire/alsa-utils)'}"
              f"  (formats compresses)")
        from . import audio

        native = next((s.nom for s in audio._SORTIES
                       if s.bibliotheque() is not None), None)
        print(f"  sortie wav  : {native + ' (natif, sans lecteur)' if native else 'via le lecteur'}")
    try:
        from . import window  # noqa: F401

        import tkinter  # noqa: F401

        print("  affichage   : tkinter OK")
    except Exception:
        print("  affichage   : tkinter MANQUANT (voir README)")
    return 0


def do_update(args) -> int:
    from . import update

    print(f"doot {__version__} - mise a jour")
    return update.update()


def do_check_update(args) -> int:
    from . import update

    print(f"doot {__version__}")
    return update.check()


def do_screens(args) -> int:
    from . import screens, window

    found = window.active_monitors()
    print(f"doot : {len(found)} ecran(s) detecte(s)")
    for index, monitor in enumerate(found):
        tag = "  (principal)" if monitor.primary else ""
        print(f"  {index}  {monitor.name:<16} {monitor.width}x{monitor.height} "
              f"a +{monitor.x}+{monitor.y}{tag}")
    print("\nPar defaut le squelette surgit sur un ecran au hasard.")
    print("Le fixer :  doot --screen 0   |   doot --screen primary")
    return 0


def do_paths(args) -> int:
    for key, value in paths().items():
        print(f"{key:6} {value}")
    return 0


def do_stop(args) -> int:
    pid = running_pid()
    if not pid:
        print("doot : aucun daemon en cours.")
        return 1
    try:
        if sys.platform == "win32":
            os.system(f"taskkill /PID {pid} /F >NUL 2>&1")
        else:
            import signal

            os.kill(pid, signal.SIGTERM)
        print(f"doot : daemon {pid} arrete.")
        release_pid_file()
        return 0
    except Exception as exc:
        print(f"doot : impossible d'arreter {pid} : {exc}")
        return 1


def do_art(args) -> int:
    print(art.frame(len(art.DOOT_FRAMES) - 1))
    return 0


# ---------------------------------------------------------------- parse ------

def build_parser(profile_defaults: dict | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="doot",
        description="Un squelette trompettiste surgit au hasard sur ton ecran, "
        f"uniquement du {season.SEASON_LABEL}.",
    )
    parser.add_argument("--version", action="version", version=f"doot {__version__}")
    parser.add_argument("--gui", action="store_true",
                        help="ouvre le grimoire graphique de toutes les commandes")
    parser.add_argument("--composer", action="store_true",
                        help="ouvre la page autonome de composition et d'edition RTTTL")
    parser.add_argument("--choreographer", action="store_true",
                        help="ouvre l'editeur visuel de choregraphies")
    parser.add_argument("--studio-live", action="store_true",
                        help="ouvre le studio de capture et quantification au clavier")
    parser.add_argument("--control", action="store_true",
                        help="ouvre le panneau compact de controle rapide")
    parser.add_argument("--tray", action="store_true",
                        help="place le controle rapide dans la zone de notification")

    parser.add_argument("--once", action="store_true", help="affiche un doot tout de suite puis quitte")
    parser.add_argument("--play", default=None, metavar="MELODIE",
                        help="le squelette joue une melodie en doots, puis quitte : "
                             "un nom (voir --melodies) ou un fichier .rtttl")
    parser.add_argument("--rickroll", action="store_true",
                        help="raccourci de --play rickroll")
    parser.add_argument("--melodies", action="store_true", help="liste les melodies jouables")
    parser.add_argument("--sync-init", dest="sync_init", default=None, metavar="DEPOT",
                        help="partage les succes par ce dossier, ou par un seau "
                             "`s3://seau/prefixe` ; frappe une cle et publie tout "
                             "de suite (`off` pour arreter)")
    parser.add_argument("--sync-join", dest="sync_join", default=None, metavar="CLE",
                        help="rejoint la flotte avec la cle donnee par --sync-init")
    parser.add_argument("--sync-endpoint", dest="sync_endpoint", default="", metavar="URL",
                        help="point d'acces du seau (R2, MinIO, B2, S3)")
    parser.add_argument("--sync-region", dest="sync_region", default="", metavar="REGION",
                        help="region du seau (defaut auto)")
    parser.add_argument("--sync-key-id", dest="sync_key_id", default="", metavar="ID",
                        help="identifiant d'acces au seau ; sans lui, "
                             "DOOT_S3_KEY_ID puis AWS_ACCESS_KEY_ID")
    parser.add_argument("--sync-secret", dest="sync_secret", default="", metavar="SECRET",
                        help="secret d'acces au seau ; `-` le lit sur l'entree "
                             "standard plutot que de le laisser dans `ps`")
    parser.add_argument("--sync-force", dest="sync_force", action="store_true",
                        help="frappe une cle neuve meme s'il y en avait une")
    parser.add_argument("--export", "--exporter", dest="exporter", default=None,
                        metavar="CHEMIN",
                        help="ecrit les succes de cette machine dans un fichier "
                             "(un dossier recoit doot-<machine>.json, `-` ecrit "
                             "sur la sortie standard)")
    parser.add_argument("--merge", "--fusionner", dest="fusionner", default=None,
                        nargs="+", metavar="CHEMIN",
                        help="fait entrer les succes d'autres machines dans "
                             "celle-ci ; un dossier apporte tous ses .json")
    parser.add_argument("--achievements", "--succes", dest="succes", action="store_true",
                        help="liste les succes locaux, leur score et leur progression")
    parser.add_argument("--carte", nargs="?", const="", default=None,
                        metavar="FICHIER",
                        help="ecrit la carte de la saison (dossier de donnees par defaut)")
    parser.add_argument("--stats", action="store_true",
                        help="ouvre le registre de la crypte (totaux, machines, saison)")
    parser.add_argument("--codex", action="store_true",
                        help="ouvre le Codex des apparitions deja decouvertes")
    parser.add_argument("--events", action="store_true",
                        help="liste les rencontres rares et leur commande d'essai")
    parser.add_argument("--event", default=None, metavar="NOM",
                        help="force une rencontre rare (voir --events), puis quitte")
    parser.add_argument("--event-save", default=None, metavar="NOM",
                        help="sauvegarde les reglages de salve comme rencontre personnelle")
    parser.add_argument("--event-title", default="", metavar="TITRE",
                        help="titre de la rencontre enregistree par --event-save")
    parser.add_argument("--event-description", default="", metavar="TEXTE",
                        help="description de la rencontre enregistree par --event-save")
    parser.add_argument("--history", nargs="?", const=20, type=int, default=None, metavar="N",
                        help="affiche les N dernieres apparitions (defaut 20)")
    parser.add_argument("--challenge", action="store_true",
                        help="affiche le defi quotidien et sa progression")
    parser.add_argument("--content", action="store_true",
                        help="affiche les melodies et rencontres favorisees ou masquees")
    parser.add_argument("--favor-melody", default=None, metavar="NOM")
    parser.add_argument("--disable-melody", default=None, metavar="NOM")
    parser.add_argument("--enable-melody", default=None, metavar="NOM")
    parser.add_argument("--favor-event", default=None, metavar="NOM")
    parser.add_argument("--disable-event", default=None, metavar="NOM")
    parser.add_argument("--enable-event", default=None, metavar="NOM")
    parser.add_argument("--pack-export", nargs=2, default=None, metavar=("NOM", "DESTINATION"),
                        help="exporte les contenus personnels dans un pack ZIP")
    parser.add_argument("--pack-import", default=None, metavar="FICHIER",
                        help="importe un pack doot sans ecraser les contenus existants")
    parser.add_argument("--pack-author", default="", metavar="NOM",
                        help="auteur inscrit dans les metadonnees du pack exporte")
    parser.add_argument("--pack-description", default="", metavar="TEXTE",
                        help="description inscrite dans le pack exporte")
    parser.add_argument("--pack-version", default="1.0", metavar="VERSION",
                        help="version de contenu inscrite dans le pack exporte")
    parser.add_argument("--pack-library", action="store_true",
                        help="liste les packs archives et verifie leurs signatures")
    parser.add_argument("--campaign", action="store_true",
                        help="affiche le chapitre courant de la campagne")
    parser.add_argument("--campaign-choose", default=None, metavar="MOT",
                        help="grave un choix dans le chapitre courant")
    parser.add_argument("--boss", action="store_true", help="affiche le boss saisonnier")
    parser.add_argument("--boss-hit", type=int, default=None, metavar="DEGATS",
                        help="inflige de 1 a 50 degats au boss saisonnier")
    parser.add_argument("--combo", action="store_true", help="affiche le combo et son record")
    parser.add_argument("--invasion", nargs="?", const=3, type=int, default=None,
                        metavar="VAGUES", help="lance de 1 a 10 vagues progressives")
    parser.add_argument("--generate-melody", default=None,
                        choices=tuple(procedural.STYLES), metavar="STYLE",
                        help="genere une melodie macabre, epique, jazz, chiptune ou chaos")
    parser.add_argument("--melody-seed", default="doot", metavar="GRAINE")
    parser.add_argument("--melody-name", default="", metavar="NOM")
    parser.add_argument("--replay-export", default=None, metavar="DESTINATION",
                        help="exporte les 50 dernieres actions en replay HTML partageable")
    parser.add_argument("--choreographies", action="store_true",
                        help="liste les choregraphies sauvegardees")
    parser.add_argument("--choreography-save", default=None, metavar="NOM",
                        help="sauvegarde la salve courante comme choregraphie")
    parser.add_argument("--choreography-play", default=None, metavar="NOM",
                        help="joue une choregraphie sauvegardee")
    parser.add_argument("--rituals", action="store_true", help="liste les rituels quotidiens")
    parser.add_argument("--ritual-add", default=None, metavar="NOM",
                        help="ajoute ou remplace un rituel quotidien")
    parser.add_argument("--ritual-at", default="", metavar="HH:MM")
    parser.add_argument("--ritual-action", choices=("doot", "melody"), default="doot")
    parser.add_argument("--ritual-value", default="", metavar="VALEUR")
    parser.add_argument("--ritual-delete", default=None, metavar="NOM")
    parser.add_argument("--museum", action="store_true", help="ouvre le musee des saisons")
    parser.add_argument("--skeletons", action="store_true",
                        help="liste les personnalites de squelettes")
    parser.add_argument("--skeleton", default=None, metavar="NOM",
                        help="choisit la personnalite active")
    parser.add_argument("--music-duel", default=None, metavar="MOTIF",
                        help="lance un duel musical avec un motif c,d,e,g")
    parser.add_argument("--music-duels", action="store_true", help="liste les duels musicaux")
    parser.add_argument("--duel-opponent", default="la crypte", metavar="NOM")
    parser.add_argument("--riddles", action="store_true",
                        help="affiche les indices des succes secrets")
    parser.add_argument("--expedition", nargs="?", const="", default=None, metavar="GRAINE",
                        help="lance ou reprend une expedition roguelite de sept salles")
    parser.add_argument("--expedition-choose", default=None, metavar="CHOIX",
                        help="avance avec prudence ou audace dans l'expedition")
    parser.add_argument("--campaign-editor", default=None, metavar="DESTINATION",
                        help="exporte l'editeur visuel autonome de campagnes")
    parser.add_argument("--campaign-pack", nargs=2, default=None,
                        metavar=("CAMPAGNE_JSON", "DESTINATION"))
    parser.add_argument("--constellation", default=None, metavar="DESTINATION",
                        help="exporte la carte interactive des succes")
    parser.add_argument("--familiars", action="store_true", help="liste les familiers spectraux")
    parser.add_argument("--familiar", default=None, metavar="NOM")
    parser.add_argument("--familiar-bond", default=None, metavar="ACTIVITE")
    parser.add_argument("--contract", action="store_true", help="affiche le contrat de flotte")
    parser.add_argument("--contract-add", type=int, default=None, metavar="N")
    parser.add_argument("--contract-share", default=None, metavar="DESTINATION")
    parser.add_argument("--contract-join", default=None, metavar="FICHIER")
    parser.add_argument("--dj-import", default=None, metavar="WAV")
    parser.add_argument("--dj-slices", type=int, default=8, metavar="N")
    parser.add_argument("--ambient-mode", nargs="?", const="status", default=None,
                        metavar="PRESET", help="ambiance : bougies, orage, lune ou oled")
    parser.add_argument("--replay-gif", default=None, metavar="DESTINATION")
    parser.add_argument("--code-hunt", action="store_true")
    parser.add_argument("--code-submit", default=None, metavar="CODE")
    parser.add_argument("--new-game-plus", action="store_true")
    parser.add_argument("--character", default=None, metavar="NOM")
    parser.add_argument("--characters", action="store_true")
    parser.add_argument("--character-skull", default="classique", metavar="STYLE")
    parser.add_argument("--character-costume", default="cape", metavar="COSTUME")
    parser.add_argument("--character-instrument", default="trompette", metavar="INSTRUMENT")
    parser.add_argument("--character-voice", default="doot", metavar="VOIX")
    parser.add_argument("--character-line", default="En mesure, les vivants !", metavar="REPLIQUE")
    parser.add_argument("--character-pack", nargs=2, default=None,
                        metavar=("PERSONNAGE", "DESTINATION"))
    parser.add_argument("--radio", nargs="?", const="", default=None, metavar="GRAINE")
    parser.add_argument("--coop", nargs="?", const="start", default=None, metavar="ACTION")
    parser.add_argument("--night-infinite", nargs="?", const="", default=None,
                        metavar="GRAINE")
    parser.add_argument("--city", nargs="?", const="", default=None, metavar="BATIMENT",
                        help="affiche la Cite des Os ou developpe un batiment")
    parser.add_argument("--relics", nargs="?", const="", default=None, metavar="RELIQUE",
                        help="affiche le reliquaire ou equipe/retire une relique")
    parser.add_argument("--factions", nargs="?", const="", default=None, metavar="FACTION",
                        help="affiche les factions ou prete serment")
    parser.add_argument("--faction-mission", nargs="?", const="", default=None, metavar="GRAINE",
                        help="accomplit une mission pour la faction active")
    parser.add_argument("--nemesis", nargs="?", const="", default=None, metavar="FORMATION",
                        help="affiche ou affronte la Nemesis persistante")
    parser.add_argument("--investigation", nargs="?", const="", default=None, metavar="GRAINE",
                        help="lance ou reprend une enquete paranormale")
    parser.add_argument("--investigate", default=None, metavar="ACTION",
                        help="cherche un indice ou accuse avec accuser:NOM")
    parser.add_argument("--ghost-export", default=None, metavar="DESTINATION")
    parser.add_argument("--ghost-time", type=int, default=60000, metavar="MS")
    parser.add_argument("--ghost-race", nargs=2, default=None, metavar=("FANTOME", "MS"))
    parser.add_argument("--adaptive-score", action="store_true")
    parser.add_argument("--score-danger", type=int, default=0, metavar="0-10")
    parser.add_argument("--score-combo", type=int, default=0, metavar="N")
    parser.add_argument("--score-boss", action="store_true")
    parser.add_argument("--director", default=None, metavar="DESTINATION")
    parser.add_argument("--photo-booth", default=None, metavar="DESTINATION")
    parser.add_argument("--photo-pose", default="doot", metavar="POSE")
    parser.add_argument("--remote", default=None, metavar="DESTINATION")
    parser.add_argument("--remote-serve", default=None, metavar="DESTINATION",
                        help="sert la telecommande locale jusqu'a Ctrl+C")
    parser.add_argument("--remote-host", default="127.0.0.1", metavar="ADRESSE")
    parser.add_argument("--remote-port", type=int, default=8765, metavar="PORT")
    parser.add_argument("--workshop-validate", default=None, metavar="PACK")
    parser.add_argument("--night-calendar", nargs="?", const=7, type=int, default=None, metavar="JOURS")
    parser.add_argument("--glyphs", action="store_true")
    parser.add_argument("--glyph-decode", nargs=2, default=None, metavar=("GLYPHE", "MOT"))
    parser.add_argument("--story-constellation", default=None, metavar="DESTINATION")
    parser.add_argument("--mirror-boss", action="store_true")
    parser.add_argument("--catacombs", nargs="?", const="", default=None, metavar="GRAINE",
                        help="lance ou reprend une descente roguelite ramifiee")
    parser.add_argument("--catacomb-choose", default=None, metavar="GAUCHE|DROITE")
    parser.add_argument("--time-loop", nargs="?", const="", default=None, metavar="ACTION")
    parser.add_argument("--familiar-skill", nargs="?", const="", default=None, metavar="TALENT")
    parser.add_argument("--bestiary", nargs="?", const="", default=None, metavar="CREATURE")
    parser.add_argument("--necroforge", nargs=2, default=None, metavar=("MATIERE", "MATIERE"))
    parser.add_argument("--paranormal-weather", nargs="?", const=7, type=int, default=None,
                        metavar="JOURS")
    parser.add_argument("--collective-ritual", nargs="?", const="", default=None, metavar="GRAINE")
    parser.add_argument("--ritual-offer", default=None, metavar="FRAGMENT")
    parser.add_argument("--ritual-export", default=None, metavar="DESTINATION")
    parser.add_argument("--ritual-import", default=None, metavar="CAPSULE")
    parser.add_argument("--nemesis-invasion", nargs="?", const="", default=None, metavar="GRAINE")
    parser.add_argument("--invasion-defend", default=None, metavar="ACTION")
    parser.add_argument("--tribunal", nargs="?", const="", default=None, metavar="GRAINE")
    parser.add_argument("--tribunal-action", default=None, metavar="ACTION")
    parser.add_argument("--legacy", default=None, metavar="HERITAGE")
    parser.add_argument("--campaign-lab", default=None, metavar="DESTINATION")
    parser.add_argument("--campaign-check", default=None, metavar="CAMPAGNE")
    parser.add_argument("--personal-museum", default=None, metavar="DESTINATION")
    parser.add_argument("--seals", action="store_true")
    parser.add_argument("--seal-submit", nargs=2, default=None, metavar=("SCEAU", "REPONSE"))
    parser.add_argument("--ghost-train", nargs="?", const="", default=None, metavar="GRAINE",
                        help="lance ou reprend une ligne du Dernier Train")
    parser.add_argument("--train-route", default="", choices=tuple(wave6.TRAIN_ROUTES),
                        metavar="LIGNE", help="force la ligne cendre, lune ou ossuaire")
    parser.add_argument("--train-choose", default=None, metavar="ACTION")
    parser.add_argument("--spectral-crew", nargs="?", const="", default=None, metavar="MEMBRE")
    parser.add_argument("--rail-case", nargs="?", const="", default=None, metavar="GRAINE")
    parser.add_argument("--rail-investigate", default=None, metavar="ACTION")
    parser.add_argument("--archaeology", nargs="?", const="", default=None, metavar="SITE")
    parser.add_argument("--restore-artifact", default=None, metavar="SITE")
    parser.add_argument("--black-market", nargs="?", const="", default=None, metavar="ACTION")
    parser.add_argument("--market-seed", default="", metavar="GRAINE")
    parser.add_argument("--prophecy", nargs="?", const="", default=None, metavar="ACTION")
    parser.add_argument("--crypt-gazette", default=None, metavar="DESTINATION")
    parser.add_argument("--musical-battle", nargs="?", const="", default=None, metavar="GRAINE")
    parser.add_argument("--battle-note", default=None, metavar="NOTE")
    parser.add_argument("--funeral-house", nargs="?", const="", default=None, metavar="MAISON")
    parser.add_argument("--house-mission", default=None, metavar="STRATEGIE")
    parser.add_argument("--mod-forge", nargs=3, default=None,
                        metavar=("DESTINATION", "NOM", "THEME"))
    parser.add_argument("--mod-validate", default=None, metavar="CAPSULE")
    parser.add_argument("--train-replay", default=None, metavar="DESTINATION")
    parser.add_argument("--lost-station", nargs="?", const="", default=None, metavar="ACTION")
    parser.add_argument("--thirteenth-bell", nargs="?", const="", default=None, metavar="REPONSE")
    parser.add_argument("--accessibility", action="store_true",
                        help="affiche les reglages d'accessibilite actifs")
    parser.add_argument("--fleet-parade", nargs="?", const="", default=None,
                        metavar="MELODIE",
                        help="lance une parade horodatee sur toute la flotte partagee")
    parser.add_argument("--snooze", default=None, metavar="DUREE",
                        help="endort le daemon pour 30m, 2h ou 1d")
    parser.add_argument("--resume", action="store_true",
                        help="annule la mise en sommeil du daemon")
    parser.add_argument("--duel-board", action="store_true",
                        help="actualise et affiche le classement saisonnier partage")
    parser.add_argument("--duel-name", default=None, metavar="NOM",
                        help="nom de cette machine dans le classement de duel")
    parser.add_argument("--transpose", type=int, default=0, metavar="DEMI-TONS",
                        help="decale la melodie de N demi-tons, en plus du recentrage "
                             "automatique sur la hauteur du doot (defaut 0)")
    parser.add_argument("--status", action="store_true", help="affiche l'etat (saison, daemon, audio)")
    parser.add_argument("--stop", action="store_true", help="arrete le daemon en cours")
    parser.add_argument("--paths", action="store_true", help="affiche les chemins utilises")
    parser.add_argument("--art", action="store_true", help="imprime le squelette dans le terminal")
    parser.add_argument("--update", action="store_true",
                        help="met a jour doot depuis GitHub et rejoue l'installeur")
    parser.add_argument("--check-update", action="store_true",
                        help="dit si une version plus recente existe, sans rien installer")

    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--profile", default=None, metavar="NOM",
                           help="charge un profil pour ce lancement")
    selection.add_argument("--no-profile", action="store_true",
                           help="ignore le profil actif pour ce lancement")
    parser.add_argument("--profiles", action="store_true",
                        help="liste les profils persistants ; * indique le profil actif")
    gestion = parser.add_mutually_exclusive_group()
    gestion.add_argument("--save-profile", default=None, metavar="NOM",
                         help="enregistre les reglages courants dans un profil, puis quitte")
    gestion.add_argument("--activate-profile", default=None, metavar="NOM",
                         help="charge automatiquement ce profil aux prochains lancements")
    gestion.add_argument("--deactivate-profile", action="store_true",
                         help="ne charge plus de profil automatiquement")
    gestion.add_argument("--delete-profile", default=None, metavar="NOM",
                         help="supprime un profil persistant")
    gestion.add_argument("--schedule-profile", default=None, metavar="NOM",
                         help="active un profil sur une plage horaire")
    gestion.add_argument("--unschedule-profile", default=None, metavar="NOM",
                         help="retire la planification d'un profil")
    parser.add_argument("--schedule-window", default="", metavar="HH:MM-HH:MM",
                        help="plage de --schedule-profile")
    parser.add_argument("--schedule-days", default="*", metavar="JOURS",
                        help="jours de --schedule-profile : lun,mar,... ou *")

    parser.add_argument("--min", type=int, default=DEFAULT_MIN_SECONDS,
                        help=f"delai minimum entre deux doot, en secondes (defaut {DEFAULT_MIN_SECONDS})")
    parser.add_argument("--max", type=int, default=DEFAULT_MAX_SECONDS,
                        help=f"delai maximum entre deux doot, en secondes (defaut {DEFAULT_MAX_SECONDS})")
    parser.add_argument("--burst-min", type=int, default=1, metavar="N",
                        help="nombre minimum de doots enchaines a chaque declenchement (defaut 1)")
    parser.add_argument("--burst-max", type=int, default=1, metavar="N",
                        help="nombre maximum de doots enchaines a chaque declenchement "
                             "(defaut 1) ; le nombre est tire entre les deux bornes et "
                             "chaque doot de la salve retire son animation")
    parser.add_argument("--burst-delay", type=float, default=DEFAULT_BURST_DELAY,
                        metavar="SECONDES",
                        help=f"pause entre deux doots d'une meme salve (defaut {DEFAULT_BURST_DELAY})")
    parser.add_argument("--formation", choices=FORMATIONS, default="random",
                        help="formation d'une salve : random, canon, wave, rain, vortex ou duel")
    parser.add_argument("--duration", type=float, default=None,
                        help=f"duree d'affichage en secondes (defaut : la duree du son, au moins {DEFAULT_DURATION})")
    parser.add_argument("--image", default=None, metavar="FICHIER",
                        help="PNG ou GIF a afficher au lieu de l'ASCII art")
    parser.add_argument("--no-image", action="store_true",
                        help="force l'ASCII art meme si une image est disponible")
    parser.add_argument("--scale", type=float, default=None,
                        help="echelle de l'image (defaut : ajustee a l'ecran)")
    parser.add_argument("--volume", type=float, default=DEFAULT_VOLUME,
                        help="volume du jingle synthetise, 0.0 a 1.0")
    parser.add_argument("--opacity", type=float, default=1.0, help="opacite maximale, 0.0 a 1.0")
    parser.add_argument("--reduce-motion", action="store_true",
                        help="coupe glissades, rotations et mouvements rapides")
    parser.add_argument("--no-flash", action="store_true",
                        help="coupe les effets brusques et limite l'opacite")
    parser.add_argument("--high-contrast", action="store_true",
                        help="force une opacite pleine et le texte visuel de secours")
    parser.add_argument("--sound-limit", type=float, default=1.0, metavar="PART",
                        help="plafond sonore global de 0.0 a 1.0")
    parser.add_argument("--font-size", type=int, default=15, help="taille de la police (defaut 15)")
    parser.add_argument("--center", action="store_true", help="toujours au centre au lieu du hasard")
    parser.add_argument("--no-slide", action="store_true",
                        help="apparait toujours sur place, sans jamais entrer par un bord")
    parser.add_argument("--no-melody", action="store_true",
                        help="jamais de melodie a la place d'un doot")
    parser.add_argument("--melody-chance", type=float, default=0.05, metavar="PART",
                        help="part des declenchements qui jouent une melodie au lieu "
                             "d'un doot (defaut 0.05, une fois sur vingt ; 0 pour ne "
                             "garder que la garantie de --melody-pity)")
    parser.add_argument("--melody-pity", type=int, default=40, metavar="N",
                        help="le N-ieme declenchement sans melodie en joue une a coup "
                             "sur (defaut 40, 0 pour ne rien garantir)")
    parser.add_argument("--no-event", action="store_true",
                        help="desactive toutes les rencontres rares automatiques")
    parser.add_argument("--event-chance", type=float, default=DEFAULT_EVENT_CHANCE,
                        metavar="PART",
                        help="part des declenchements qui deviennent un evenement rare "
                             f"(defaut {DEFAULT_EVENT_CHANCE})")
    parser.add_argument("--event-pity", type=int, default=DEFAULT_EVENT_PITY, metavar="N",
                        help="le N-ieme declenchement sans evenement en force un "
                             f"(defaut {DEFAULT_EVENT_PITY}, 0 pour aucune garantie)")
    parser.add_argument("--no-contagion", action="store_true",
                        help="ne publie ni ne joue les doots venus des autres machines")
    parser.add_argument("--contagion-chance", type=float,
                        default=DEFAULT_CONTAGION_CHANCE, metavar="PART",
                        help="chance qu'un doot local traverse le partage chiffre "
                             f"(defaut {DEFAULT_CONTAGION_CHANCE})")
    parser.add_argument("--slide-chance", type=float, default=0.5, metavar="PART",
                        help="proportion de doots qui entrent par un bord ; le reste "
                             "surgit sur place (defaut 0.5, soit un sur deux)")
    # --side impose l'entree par un bord, --spin l'apparition sur place : les
    # demander ensemble n'a pas de sens, et l'un mangerait l'autre en silence.
    arrivee = parser.add_mutually_exclusive_group()
    arrivee.add_argument("--side", default=None,
                         choices=("left", "right", "top", "bottom", "random"),
                         help="bord par lequel le squelette entre (defaut : au hasard). "
                              "Le bas de l'image se pose contre ce bord.")
    parser.add_argument("--slide-ms", type=int, default=420,
                        help="duree de l'entree en millisecondes (defaut 420)")
    arrivee.add_argument("--spin", action="store_true",
                         help="ce doot fait un tour complet sur lui-meme ; impose "
                              "l'apparition sur place, et demande une image PNG")
    parser.add_argument("--no-spin", action="store_true",
                        help="jamais de tour complet, le squelette reste droit")
    parser.add_argument("--spin-chance", type=float, default=DEFAULT_SPIN_CHANCE,
                        metavar="PART",
                        help="proportion des apparitions sur place qui font un "
                             f"tour complet (defaut {DEFAULT_SPIN_CHANCE})")
    parser.add_argument("--spin-ms", type=int, default=DEFAULT_SPIN_MS,
                        help=f"duree du tour complet en millisecondes (defaut {DEFAULT_SPIN_MS})")
    parser.add_argument("--reverse", action="store_true",
                        help="retourne ce doot et joue son WAV a l'envers")
    parser.add_argument("--no-reverse", action="store_true",
                        help="desactive les apparitions inversees")
    parser.add_argument("--reverse-chance", type=float, default=DEFAULT_REVERSE_CHANCE,
                        metavar="PART",
                        help="proportion de doots retournes avec leur son inverse "
                             f"(defaut {DEFAULT_REVERSE_CHANCE})")
    parser.add_argument("--screen", default=None, metavar="CHOIX",
                        help="ecran d'apparition : 'random' (defaut), 'primary', "
                             "ou un index (0, 1, 2...). Voir 'doot --screens'.")
    parser.add_argument("--screens", action="store_true", help="liste les ecrans detectes")
    parser.add_argument("--no-sound", action="store_true", help="mode muet")
    parser.add_argument("--no-pan", action="store_true",
                        help="son au centre, au lieu de suivre la position du squelette")
    parser.add_argument("--regen-sound", action="store_true", help="regenere le jingle synthetise")
    parser.add_argument("--ignore-season", action="store_true",
                        help="ignore la fenetre 1er sept - 31 oct (tests uniquement)")
    parser.add_argument("--quiet", action="store_true", help="n'ecrit que dans le journal")
    parser.add_argument("--quiet-hours", default="", metavar="HH:MM-HH:MM",
                        help="suspend les apparitions pendant cette plage, y compris la nuit")
    if profile_defaults:
        parser.set_defaults(**profile_defaults)
    return parser


def parse_args(argv: list[str] | None = None):
    """Charge le profil avant le vrai parsing, pour laisser la CLI le remplacer."""

    raw = list(sys.argv[1:] if argv is None else argv)
    probe = argparse.ArgumentParser(add_help=False)
    selection = probe.add_mutually_exclusive_group()
    selection.add_argument("--profile")
    selection.add_argument("--no-profile", action="store_true")
    known, _unknown = probe.parse_known_args(raw)

    # Les horaires sont appliques dynamiquement par la boucle du daemon. Les
    # charger ici ferait du profil planifie la "base" et empecherait de revenir
    # au profil actif quand sa plage se termine.
    selected = None if known.no_profile else (known.profile or profiles.active(profiles_path()))
    defaults = None
    if selected:
        try:
            defaults = profiles.load(profiles_path(), selected)
        except profiles.ProfileError as exc:
            build_parser().error(str(exc))

    args = build_parser(defaults).parse_args(raw)
    # Les valeurs par defaut d'un groupe mutuellement exclusif ne comptent pas
    # comme une option argparse. Une demande explicite doit pourtant battre le
    # profil charge dans les deux sens.
    explicit_side = any(
        option == "--side" or option.startswith("--side=") for option in raw
    )
    if explicit_side:
        args.spin = False
        if "--no-slide" not in raw:
            args.no_slide = False
    if "--spin" in raw:
        args.side = None
        if "--no-spin" not in raw:
            args.no_spin = False
    if "--no-spin" in raw:
        args.spin = False
    if "--reverse" in raw and "--no-reverse" not in raw:
        args.no_reverse = False
    if "--no-reverse" in raw:
        args.reverse = False
    args._profile_loaded = selected
    args._raw_options = tuple(raw)
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if args.gui:
        from . import gui

        return gui.main()
    if args.composer:
        from . import composer_gui

        return composer_gui.main()
    if args.choreographer:
        from . import choreography_gui

        return choreography_gui.main()
    if args.studio_live:
        from . import live_gui

        return live_gui.main()
    if args.control:
        from . import gui

        return gui.main(compact=True)
    if args.tray:
        from . import tray

        return tray.main()

    if args.min < 1:
        args.min = 1
    if args.max < args.min:
        args.max = args.min
    if args.burst_min < 1:
        args.burst_min = 1
    if args.burst_max < args.burst_min:
        args.burst_max = args.burst_min
    if args.burst_delay < 0:
        args.burst_delay = 0.0
    args.event_chance = max(0.0, min(1.0, args.event_chance))
    args.event_pity = max(0, args.event_pity)
    args.contagion_chance = max(0.0, min(1.0, args.contagion_chance))
    args.reverse_chance = max(0.0, min(1.0, args.reverse_chance))
    args.sound_limit = max(0.0, min(1.0, args.sound_limit))
    args.volume = min(max(0.0, args.volume), args.sound_limit)
    if args.reduce_motion:
        args.no_slide = True
        args.no_spin = True
        args.slide_chance = 0.0
        args.spin_chance = 0.0
    if args.no_flash:
        args.no_spin = True
        args.spin_chance = 0.0
        args.opacity = min(args.opacity, 0.82)
    if args.high_contrast:
        args.opacity = 1.0
    if not args._profile_loaded:
        personality = adventure.selected_personality(read_state())
        if personality is not None:
            if not any(option == "--formation" or option.startswith("--formation=")
                       for option in args._raw_options):
                args.formation = personality.formation
            if not any(option == "--transpose" or option.startswith("--transpose=")
                       for option in args._raw_options):
                args.transpose = personality.transpose
    if args.quiet_hours:
        try:
            schedule.window(args.quiet_hours)
        except ValueError as exc:
            print(f"doot : {exc}")
            return 2

    p = paths()
    p["data"].mkdir(parents=True, exist_ok=True)
    p["sound"].mkdir(parents=True, exist_ok=True)
    p["image"].mkdir(parents=True, exist_ok=True)
    p["melodies"].mkdir(parents=True, exist_ok=True)
    p.get("events", p["data"] / "events").mkdir(parents=True, exist_ok=True)
    p.get("choreographies", p["data"] / "choreographies").mkdir(parents=True, exist_ok=True)
    p.get("packs", p["data"] / "packs").mkdir(parents=True, exist_ok=True)
    p.get("replays", p["data"] / "replays").mkdir(parents=True, exist_ok=True)
    p.get("dj", p["data"] / "dj").mkdir(parents=True, exist_ok=True)
    p.get("characters", p["data"] / "characters").mkdir(parents=True, exist_ok=True)

    if args.profiles:
        return do_profiles(args)
    if args.save_profile:
        return do_save_profile(args, args.save_profile)
    if args.activate_profile:
        return do_activate_profile(args, args.activate_profile)
    if args.deactivate_profile:
        return do_deactivate_profile(args)
    if args.delete_profile:
        return do_delete_profile(args, args.delete_profile)
    if args.schedule_profile:
        if not args.schedule_window:
            print("doot : --schedule-window est requis avec --schedule-profile")
            return 2
        return do_schedule_profile(args, args.schedule_profile)
    if args.unschedule_profile:
        return do_unschedule_profile(args, args.unschedule_profile)

    if args.regen_sound:
        sound.ensure_wav(p["wav"], args.volume, force=True)
        print(f"doot : jingle regenere -> {p['wav']}")

    if args.check_update:
        return do_check_update(args)
    if args.update:
        return do_update(args)
    if args.screens:
        return do_screens(args)
    if args.status:
        return do_status(args)
    if args.paths:
        return do_paths(args)
    if args.stop:
        return do_stop(args)
    if args.art:
        return do_art(args)
    if args.snooze is not None:
        return do_snooze(args, args.snooze)
    if args.resume:
        return do_resume(args)
    if args.history is not None:
        return do_history(args)
    if args.challenge:
        return do_challenge(args)
    if args.content:
        return do_content(args)
    if args.favor_melody:
        return do_set_content(args, "melodies", args.favor_melody, 3)
    if args.disable_melody:
        return do_set_content(args, "melodies", args.disable_melody, 0)
    if args.enable_melody:
        return do_set_content(args, "melodies", args.enable_melody, 1)
    if args.favor_event:
        return do_set_content(args, "events", args.favor_event, 3)
    if args.disable_event:
        return do_set_content(args, "events", args.disable_event, 0)
    if args.enable_event:
        return do_set_content(args, "events", args.enable_event, 1)
    if args.pack_export:
        return do_pack_export(args, args.pack_export[0], args.pack_export[1])
    if args.pack_import:
        return do_pack_import(args, args.pack_import)
    if args.pack_library:
        return do_pack_library(args)
    if args.campaign_choose:
        return do_campaign_choose(args, args.campaign_choose)
    if args.campaign:
        return do_campaign(args)
    if args.boss_hit is not None:
        return do_boss_hit(args, args.boss_hit)
    if args.boss:
        return do_boss(args)
    if args.combo:
        return do_combo(args)
    if args.invasion is not None:
        return do_invasion(args, args.invasion)
    if args.generate_melody:
        return do_generate_melody(args, args.generate_melody)
    if args.replay_export:
        return do_replay_export(args, args.replay_export)
    if args.choreography_save:
        return do_choreography_save(args, args.choreography_save)
    if args.choreography_play:
        return do_choreography_play(args, args.choreography_play)
    if args.choreographies:
        return do_choreographies(args)
    if args.ritual_add:
        return do_ritual_add(args, args.ritual_add)
    if args.ritual_delete:
        return do_ritual_delete(args, args.ritual_delete)
    if args.rituals:
        return do_rituals(args)
    if args.museum:
        return do_museum(args)
    if args.skeleton:
        return do_skeleton(args, args.skeleton)
    if args.skeletons:
        return do_skeletons(args)
    if args.music_duel:
        return do_music_duel(args, args.music_duel)
    if args.music_duels:
        return do_music_duels(args)
    if args.riddles:
        return do_riddles(args)
    if args.expedition_choose:
        return do_expedition_choose(args, args.expedition_choose)
    if args.expedition is not None:
        return do_expedition(args, args.expedition)
    if args.campaign_editor:
        return do_campaign_editor(args, args.campaign_editor)
    if args.campaign_pack:
        return do_campaign_pack(args, args.campaign_pack[0], args.campaign_pack[1])
    if args.constellation:
        return do_constellation(args, args.constellation)
    if args.familiar_bond:
        return do_familiar_bond(args, args.familiar_bond)
    if args.familiar:
        return do_familiar(args, args.familiar)
    if args.familiars:
        return do_familiars(args)
    if args.contract_add is not None:
        return do_contract_add(args, args.contract_add)
    if args.contract_share:
        return do_contract_share(args, args.contract_share)
    if args.contract_join:
        return do_contract_join(args, args.contract_join)
    if args.contract:
        return do_contract(args)
    if args.dj_import:
        return do_dj_import(args, args.dj_import)
    if args.ambient_mode is not None:
        return do_ambient_mode(args, args.ambient_mode)
    if args.replay_gif:
        return do_replay_gif(args, args.replay_gif)
    if args.code_submit:
        return do_code_submit(args, args.code_submit)
    if args.code_hunt:
        return do_code_hunt(args)
    if args.new_game_plus:
        return do_new_game_plus(args)
    if args.character_pack:
        return do_character_pack(args, args.character_pack[0], args.character_pack[1])
    if args.character:
        return do_character(args, args.character)
    if args.characters:
        return do_characters(args)
    if args.radio is not None:
        return do_radio(args, args.radio)
    if args.coop is not None:
        return do_coop(args, args.coop)
    if args.night_infinite is not None:
        return do_night_infinite(args, args.night_infinite)
    if args.city is not None:
        return do_city(args, args.city)
    if args.relics is not None:
        return do_relics(args, args.relics)
    if args.faction_mission is not None:
        return do_faction_mission(args, args.faction_mission)
    if args.factions is not None:
        return do_factions(args, args.factions)
    if args.nemesis is not None:
        return do_nemesis(args, args.nemesis)
    if args.investigate:
        return do_investigate(args, args.investigate)
    if args.investigation is not None:
        return do_investigation(args, args.investigation)
    if args.ghost_export:
        return do_ghost_export(args, args.ghost_export)
    if args.ghost_race:
        return do_ghost_race(args, args.ghost_race[0], args.ghost_race[1])
    if args.adaptive_score:
        return do_adaptive_score(args)
    if args.director:
        return do_director(args, args.director)
    if args.photo_booth:
        return do_photo_booth(args, args.photo_booth)
    if args.remote:
        return do_remote(args, args.remote)
    if args.remote_serve:
        return do_remote_serve(args, args.remote_serve)
    if args.workshop_validate:
        return do_workshop_validate(args, args.workshop_validate)
    if args.night_calendar is not None:
        return do_night_calendar(args, args.night_calendar)
    if args.glyph_decode:
        return do_glyph_decode(args, args.glyph_decode[0], args.glyph_decode[1])
    if args.glyphs:
        return do_glyphs(args)
    if args.story_constellation:
        return do_story_constellation(args, args.story_constellation)
    if args.mirror_boss:
        return do_mirror_boss(args)
    if args.catacomb_choose:
        return do_catacomb_choose(args, args.catacomb_choose)
    if args.catacombs is not None:
        return do_catacombs(args, args.catacombs)
    if args.time_loop is not None:
        return do_time_loop(args, args.time_loop)
    if args.familiar_skill is not None:
        return do_familiar_skill(args, args.familiar_skill)
    if args.bestiary is not None:
        return do_bestiary(args, args.bestiary)
    if args.necroforge:
        return do_necroforge(args, args.necroforge[0], args.necroforge[1])
    if args.paranormal_weather is not None:
        return do_paranormal_weather(args, args.paranormal_weather)
    if args.ritual_offer:
        return do_ritual_offer(args, args.ritual_offer)
    if args.ritual_export:
        return do_ritual_export(args, args.ritual_export)
    if args.ritual_import:
        return do_ritual_import(args, args.ritual_import)
    if args.collective_ritual is not None:
        return do_collective_ritual(args, args.collective_ritual)
    if args.invasion_defend:
        return do_invasion_defend(args, args.invasion_defend)
    if args.nemesis_invasion is not None:
        return do_nemesis_invasion(args, args.nemesis_invasion)
    if args.tribunal_action:
        return do_tribunal_action(args, args.tribunal_action)
    if args.tribunal is not None:
        return do_tribunal(args, args.tribunal)
    if args.legacy:
        return do_legacy(args, args.legacy)
    if args.campaign_lab:
        return do_campaign_lab(args, args.campaign_lab)
    if args.campaign_check:
        return do_campaign_check(args, args.campaign_check)
    if args.personal_museum:
        return do_personal_museum(args, args.personal_museum)
    if args.seal_submit:
        return do_seal_submit(args, args.seal_submit[0], args.seal_submit[1])
    if args.seals:
        return do_seals(args)
    if args.train_choose:
        return do_train_choose(args, args.train_choose)
    if args.ghost_train is not None:
        return do_ghost_train(args, args.ghost_train)
    if args.spectral_crew is not None:
        return do_spectral_crew(args, args.spectral_crew)
    if args.rail_investigate:
        return do_rail_investigate(args, args.rail_investigate)
    if args.rail_case is not None:
        return do_rail_case(args, args.rail_case)
    if args.restore_artifact:
        return do_restore_artifact(args, args.restore_artifact)
    if args.archaeology is not None:
        return do_archaeology(args, args.archaeology)
    if args.black_market is not None:
        return do_black_market(args, args.black_market)
    if args.prophecy is not None:
        return do_prophecy(args, args.prophecy)
    if args.crypt_gazette:
        return do_crypt_gazette(args, args.crypt_gazette)
    if args.battle_note:
        return do_battle_note(args, args.battle_note)
    if args.musical_battle is not None:
        return do_musical_battle(args, args.musical_battle)
    if args.house_mission:
        return do_house_mission(args, args.house_mission)
    if args.funeral_house is not None:
        return do_funeral_house(args, args.funeral_house)
    if args.mod_forge:
        return do_mod_forge(args, args.mod_forge[0], args.mod_forge[1], args.mod_forge[2])
    if args.mod_validate:
        return do_mod_validate(args, args.mod_validate)
    if args.train_replay:
        return do_train_replay(args, args.train_replay)
    if args.lost_station is not None:
        return do_lost_station(args, args.lost_station)
    if args.thirteenth_bell is not None:
        return do_thirteenth_bell(args, args.thirteenth_bell)
    if args.accessibility:
        return do_accessibility(args)
    if args.melodies:
        return do_melodies(args)
    if args.succes:
        return do_succes(args)
    if args.codex:
        return do_codex(args)
    if args.stats:
        return do_stats(args)
    if args.carte is not None:
        return do_carte(args, args.carte)
    if args.duel_name is not None:
        return do_duel_name(args, args.duel_name)
    if args.duel_board:
        return do_duel_board(args)
    if args.sync_init is not None:
        return do_sync_init(args, args.sync_init)
    if args.sync_join is not None:
        return do_sync_join(args, args.sync_join)
    if args.exporter is not None:
        return do_exporter(args, args.exporter)
    if args.fusionner:
        return do_fusionner(args, args.fusionner)
    if args.events:
        return do_events(args)
    if args.event_save:
        return do_save_event(args, args.event_save)
    if args.fleet_parade is not None:
        return do_fleet_parade(args, args.fleet_parade)

    try:
        if args.event:
            return do_event(args, args.event)
        if args.play or args.rickroll:
            return do_play(args, args.play or "rickroll")
        if args.once:
            return do_once(args)
        return do_daemon(args)
    except Exception as exc:
        from .window import TkinterMissing

        if isinstance(exc, TkinterMissing):
            print(str(exc), file=sys.stderr)
            return 4
        raise


if __name__ == "__main__":
    raise SystemExit(main())
