"""Ligne de commande et boucle de fond de doot."""

from __future__ import annotations

import argparse
import copy
import ctypes
import json
import os
import random
import sys
import time
from datetime import datetime
from pathlib import Path

from . import (
    __version__, art, carte, coffre, codex, contagion, image, notification,
    partage, profiles, registre, season, sound, succes,
)

DEFAULT_MIN_SECONDS = 600     # 10 min
DEFAULT_MAX_SECONDS = 3600    # 1 h
DEFAULT_DURATION = 2.8
DEFAULT_VOLUME = 0.55
DEFAULT_SPIN_CHANCE = 0.25
DEFAULT_SPIN_MS = 700
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
        "wav": root / "doot.wav",
        "log": root / "doot.log",
        "pid": root / "doot.pid",
        "state": root / "state.json",
        "profiles": root / "profiles.json",
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

def resolve_media(args) -> tuple:
    """(son, image, duree) pour le prochain doot.

    Relu a chaque doot : tu peux deposer un son ou une image pendant que le
    daemon tourne, il les prendra sans redemarrage.
    """
    p = paths()

    wav = None
    if not args.no_sound:
        try:
            wav = sound.pick_sound(p["wav"], p["sound"], args.volume)
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


def display_options(args, step: dict | None = None) -> dict:
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
            wav, picture, duration = resolve_media(args)
            window.show(wav_path=wav, duration=duration, image_path=picture,
                        **display_options(args, plan[index - 1]))
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
    return rng.choice(pool)


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
    return rng.choice(evenements.tirables())


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
    evenement = evenements.find(wanted)
    if evenement is None:
        print(f"doot : evenement inconnu '{wanted}' (doot --events pour la liste)")
        return 2
    emit_evenement(args, evenement, journal=True)
    return 0


def do_events(args) -> int:
    from . import evenements

    print("Evenements rares :")
    for evenement in evenements.CATALOGUE:
        print(f"  {evenement.identifiant:<10} {evenement.titre} - {evenement.description}")
    print("\nEssayer : doot --event NOM --ignore-season")
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


def emit_contagion(args, signal: dict, journal: bool = True) -> bool:
    """Fait surgir ici ce qu'une autre machine vient de jouer chez elle.

    Ce qui traverse reste une contagion aux yeux du Codex, meme quand c'est une
    parade ou un rickroll : la rencontre rare a ete vue la-bas, et la compter
    ici une seconde fois ferait d'une flotte un moyen de les collectionner.

    Les refus du poste l'emportent sur ce que le signal demande. Un poste qui a
    coupe les melodies ou les rencontres recoit le doot, pas le reste.
    """
    from . import evenements

    genre, nom = contagion.charge(signal)
    source = signal.get("source", "une autre machine")

    if genre == "evenement" and not args.no_event:
        evenement = evenements.find(nom)
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
        if definition.identifiant in acquis:
            marque = "[x]"
            detail = f"debloque le {acquis[definition.identifiant]}"
        else:
            marque = "[ ]"
            detail = f"progression {courant}/{objectif}"
        print(f"  {marque} {definition.titre} (+{definition.points})")
        print(f"      {definition.description}  {detail}")
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

    try:
        while True:
            if not args.ignore_season and not season.in_season():
                wait = min(OUT_OF_SEASON_POLL, max(60.0, season.seconds_until_next_season()))
                log(season.describe(), quiet=args.quiet)
                time.sleep(wait)
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
    args._profile_loaded = selected
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if args.gui:
        from . import gui

        return gui.main()

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

    p = paths()
    p["data"].mkdir(parents=True, exist_ok=True)
    p["sound"].mkdir(parents=True, exist_ok=True)
    p["image"].mkdir(parents=True, exist_ok=True)
    p["melodies"].mkdir(parents=True, exist_ok=True)

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
