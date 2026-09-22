"""Lanceur graphique des commandes de doot.

La GUI ne reimplemente aucune action : elle compose une ligne de commande et
lance ``python -m doot``. La CLI reste donc l'unique source de verite, y
compris pour la validation, les profils et les futures evolutions.
"""

from __future__ import annotations

import argparse
import os
import queue
import shlex
import subprocess
import sys
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Mapping, Sequence

from . import composer, registre, season, succes


ASSETS_DIR = Path(__file__).with_name("assets")


@dataclass(frozen=True)
class ParameterSpec:
    """Valeur obligatoire propre a une commande."""

    option: str
    label: str
    hint: str
    multiple: bool = False
    requis: bool = True


@dataclass(frozen=True)
class CommandSpec:
    """Une action proposee dans la colonne de gauche."""

    key: str
    title: str
    description: str
    argv: tuple[str, ...] = ()
    parameters: tuple[ParameterSpec, ...] = ()
    image: str = "logo.png"
    detached: bool = False


@dataclass(frozen=True)
class OptionSpec:
    """Un reglage argparse rendu automatiquement dans la GUI."""

    dest: str
    option: str
    help: str
    kind: str
    choices: tuple[str, ...] = ()
    metavar: str = "VALEUR"
    default: object = None


@dataclass(frozen=True)
class AchievementCard:
    """Donnees pretes a afficher pour une carte de succes."""

    identifiant: str
    titre: str
    description: str
    points: int
    courant: int
    objectif: int
    debloque_le: str | None


def achievement_cards(etat: dict) -> tuple[AchievementCard, ...]:
    """Construit la galerie sans faire dependre les tests de Tkinter."""

    acquis = succes.debloques(etat)
    cards = []
    for definition in succes.CATALOGUE:
        courant, objectif = succes.progression(etat, definition)
        date = acquis.get(definition.identifiant)
        cards.append(AchievementCard(
            identifiant=definition.identifiant,
            titre=definition.titre,
            description=definition.description,
            points=definition.points,
            courant=courant,
            objectif=objectif,
            debloque_le=date if isinstance(date, str) else None,
        ))
    return tuple(cards)


@dataclass(frozen=True)
class RegistreVue:
    """Tout ce que l'onglet du registre montre, compose sans Tkinter."""

    resume: object
    totaux: list
    records: list
    postes: list
    collections: list
    saison: object
    precedentes: list
    ici: str


def registre_vue(etat: dict, annee: int | None = None) -> RegistreVue:
    """Assemble le registre d'une saison, la derniere ouverte par defaut."""

    if annee is None:
        annee = season.last_season_year()
    precedentes = [
        (autre, registre.saison(etat, autre))
        for autre in registre.saisons(etat)
        if autre != annee
    ]
    return RegistreVue(
        resume=registre.resume(etat),
        totaux=registre.totaux(etat),
        records=registre.records(etat),
        postes=registre.postes(etat),
        collections=registre.collections(etat),
        saison=registre.saison(etat, annee),
        precedentes=[(autre, len(passee.actifs), passee.duree)
                     for autre, passee in precedentes],
        ici=succes.machine(etat),
    )


def _achievement_date(value: str) -> str:
    """Rend une date ISO agreable, tout en tolerant les vieux etats manuels."""

    try:
        return datetime.fromisoformat(value).strftime("%d/%m/%Y")
    except (TypeError, ValueError):
        return value


COMMANDS: tuple[CommandSpec, ...] = (
    CommandSpec(
        "daemon", "Lancer le daemon",
        "Reveille doot en arriere-plan avec les reglages choisis. La GUI peut ensuite etre fermee.",
        image="success/ca_tourne.png", detached=True,
    ),
    CommandSpec(
        "once", "Faire un doot maintenant",
        "Affiche une apparition tout de suite, puis quitte.",
        ("--once",), image="success/premier_doot.png",
    ),
    CommandSpec(
        "play", "Jouer une melodie",
        "Joue une melodie fournie ou un fichier RTTTL personnel.",
        parameters=(ParameterSpec("--play", "Melodie", "nom ou chemin du fichier .rtttl"),),
        image="success/maestro.png",
    ),
    CommandSpec(
        "rickroll", "Rickroll macabre",
        "Joue immediatement la melodie rickroll en doots.",
        ("--rickroll",), image="success/rickroll.png",
    ),
    CommandSpec(
        "melodies", "Voir les melodies",
        "Liste les melodies personnelles et celles fournies avec doot.",
        ("--melodies",), image="success/jukebox_macabre.png",
    ),
    CommandSpec(
        "events", "Voir les rencontres",
        "Liste toutes les rencontres rares disponibles et leur commande d'essai.",
        ("--events",), image="success/collection_evenements.png",
    ),
    CommandSpec(
        "codex", "Ouvrir le Codex",
        "Revele les apparitions deja rencontrees et donne un indice pour les autres.",
        ("--codex",), image="success/collection_evenements.png",
    ),
    CommandSpec(
        "event", "Forcer une rencontre",
        "Declenche une rencontre rare precise, puis quitte.",
        parameters=(ParameterSpec(
            "--event", "Rencontre", "parade, pluie, vortex, duel, mimic ou faux-bug",
        ),),
        image="success/choregraphe.png",
    ),
    CommandSpec(
        "achievements", "Voir les succes",
        "Affiche les medailles, le score et la progression locale.",
        ("--achievements",), image="success/cent_doots.png",
    ),
    CommandSpec(
        "carte", "Carte de la saison",
        "Ecrit dans le dossier de donnees l'image qui resume la saison.",
        ("--carte",), image="success/sept_jours.png",
    ),
    CommandSpec(
        "stats", "Ouvrir le registre",
        "Detaille les totaux, les machines de la flotte et les soirs de la saison.",
        ("--stats",), image="success/sept_jours.png",
    ),
    CommandSpec(
        "duel-board", "Classement du duel",
        "Actualise le partage chiffre et classe les combattants par doots et speciaux.",
        ("--duel-board",), image="success/canon_a_os.png",
    ),
    CommandSpec(
        "duel-name", "Choisir mon nom de duel",
        "Affiche un nom lisible a la place de l'identifiant de cette machine.",
        parameters=(ParameterSpec("--duel-name", "Nom", "par exemple : Doot Vader"),),
        image="success/profil_actif.png",
    ),
    CommandSpec(
        "status", "Etat de doot",
        "Montre la saison, le daemon actif, l'audio et l'image utilises.",
        ("--status",), image="success/ca_tourne.png",
    ),
    CommandSpec(
        "stop", "Arreter le daemon",
        "Arrete proprement l'instance de doot qui tourne en arriere-plan.",
        ("--stop",), image="success/premier_doot.png",
    ),
    CommandSpec(
        "screens", "Voir les ecrans",
        "Liste les ecrans detectes et leurs index utilisables avec --screen.",
        ("--screens",), image="success/quatre_coins.png",
    ),
    CommandSpec(
        "profiles", "Voir les profils",
        "Liste les profils persistants et indique celui qui est actif.",
        ("--profiles",), image="success/profil_actif.png",
    ),
    CommandSpec(
        "save-profile", "Enregistrer un profil",
        "Sauvegarde les reglages coches dans un nouveau profil.",
        parameters=(ParameterSpec("--save-profile", "Nom du profil", "par exemple : parade"),),
        image="success/profil_actif.png",
    ),
    CommandSpec(
        "activate-profile", "Activer un profil",
        "Rend un profil automatique pour les prochains lancements.",
        parameters=(ParameterSpec("--activate-profile", "Nom du profil", "profil deja enregistre"),),
        image="success/profil_actif.png",
    ),
    CommandSpec(
        "deactivate-profile", "Desactiver le profil",
        "Revient aux reglages historiques sans supprimer les profils.",
        ("--deactivate-profile",), image="success/profil_actif.png",
    ),
    CommandSpec(
        "delete-profile", "Supprimer un profil",
        "Supprime definitivement un profil persistant.",
        parameters=(ParameterSpec("--delete-profile", "Nom du profil", "profil a supprimer"),),
        image="success/profil_actif.png",
    ),
    CommandSpec(
        "sync-init", "Ouvrir le partage",
        "Partage les succes par un dossier ou un seau S3, et frappe une cle a "
        "recopier sur les autres postes ; utilise 'off' pour l'arreter.",
        parameters=(
            ParameterSpec("--sync-init", "Depot", "dossier, s3://seau/prefixe, ou off"),
            ParameterSpec("--sync-endpoint", "Point d'acces",
                          "https://... pour un seau", requis=False),
            ParameterSpec("--sync-region", "Region",
                          "region du seau, defaut auto", requis=False),
            ParameterSpec("--sync-key-id", "Identifiant",
                          "acces au seau, sinon l'environnement", requis=False),
            ParameterSpec("--sync-secret", "Secret",
                          "acces au seau, sinon l'environnement", requis=False),
        ),
        image="success/canon_a_os.png",
    ),
    CommandSpec(
        "sync-join", "Rejoindre le partage",
        "Rejoint une flotte avec la cle affichee par l'ouverture du partage.",
        parameters=(ParameterSpec("--sync-join", "Cle", "dootsync1..."),),
        image="success/choregraphe.png",
    ),
    CommandSpec(
        "export", "Exporter les succes",
        "Ecrit la progression de cette machine dans un fichier ou un dossier.",
        parameters=(ParameterSpec("--export", "Destination", "fichier, dossier, ou - pour la sortie"),),
        image="success/mille_doots.png",
    ),
    CommandSpec(
        "merge", "Fusionner des succes",
        "Importe sans doublon la progression d'autres machines.",
        parameters=(ParameterSpec(
            "--merge", "Sources", "plusieurs chemins peuvent etre separes par un point-virgule", True,
        ),),
        image="success/collection_evenements.png",
    ),
    CommandSpec(
        "paths", "Voir les chemins",
        "Affiche les dossiers de donnees, sons, images, melodies et journal.",
        ("--paths",), image="success/melodie_perso.png",
    ),
    CommandSpec(
        "regen-sound", "Regenerer le jingle",
        "Recree le jingle synthetise, puis affiche l'etat de doot.",
        ("--regen-sound", "--status"), image="success/orchestre.png",
    ),
    CommandSpec(
        "check-update", "Chercher une mise a jour",
        "Verifie si une version plus recente existe, sans rien installer.",
        ("--check-update",), image="success/sept_jours.png",
    ),
    CommandSpec(
        "update", "Mettre doot a jour",
        "Recupere la derniere version et rejoue l'installeur.",
        ("--update",), image="success/sept_jours.png",
    ),
    CommandSpec(
        "art", "Art terminal",
        "Imprime le squelette en ASCII dans la console integree.",
        ("--art",), image="success/premier_doot.png",
    ),
    CommandSpec(
        "help", "Aide complete",
        "Affiche toutes les options de la ligne de commande.",
        ("--help",), image="logo.png",
    ),
    CommandSpec(
        "version", "Version",
        "Affiche la version installee de doot.",
        ("--version",), image="logo.png",
    ),
)


# Les actions qui ouvrent un onglet de l'etat : ce qu'il faut relire, et ou
# aller. La table dit le couple une fois et se lit sans Tkinter, donc un runner
# sans affichage peut verifier qu'aucune action ne promet un onglet sans l'ouvrir.
ONGLETS_ETAT = {
    "achievements": ("_refresh_achievements", "achievements_tab"),
    "stats": ("_refresh_registre", "registre_tab"),
}


COMMAND_OPTIONS = {
    option
    for command in COMMANDS
    for option in (
        *command.argv,
        *(parameter.option for parameter in command.parameters),
    )
    if option.startswith("--")
}
COMMAND_OPTIONS.update({"--gui", "--help"})


def _long_option(action: argparse.Action) -> str | None:
    """Le nom long canonique d'une action argparse."""

    for option in action.option_strings:
        if option.startswith("--"):
            return option
    return action.option_strings[0] if action.option_strings else None


def option_specs(parser: argparse.ArgumentParser | None = None) -> tuple[OptionSpec, ...]:
    """Extrait tous les reglages non commandes depuis le vrai parser CLI."""

    if parser is None:
        from .cli import build_parser

        parser = build_parser()

    specs = []
    for action in parser._actions:
        option = _long_option(action)
        if not option or set(action.option_strings) & COMMAND_OPTIONS:
            continue
        if isinstance(action, argparse._StoreTrueAction):
            kind = "boolean"
        elif action.choices:
            kind = "choice"
        else:
            kind = "value"
        choices = tuple(str(choice) for choice in (action.choices or ()))
        metavar = action.metavar or action.dest.replace("_", "-").upper()
        specs.append(OptionSpec(
            dest=action.dest,
            option=option,
            help=action.help or "",
            kind=kind,
            choices=choices,
            metavar=str(metavar),
            default=action.default,
        ))
    return tuple(specs)


def build_command_argv(
    command: CommandSpec,
    parameter_values: Mapping[str, object],
    setting_values: Mapping[str, object],
    settings: Sequence[OptionSpec] | None = None,
    *,
    strict: bool = True,
) -> list[str]:
    """Compose argv sans shell, donc sans probleme d'echappement ou d'injection."""

    argv = list(command.argv)
    for parameter in command.parameters:
        raw = str(parameter_values.get(parameter.option, "")).strip()
        if not raw:
            if not parameter.requis:
                continue
            if strict:
                raise ValueError(f"Le champ « {parameter.label} » est obligatoire.")
            argv.extend((parameter.option, f"<{parameter.hint}>"))
            continue
        values = [raw]
        if parameter.multiple:
            values = [value.strip() for value in raw.split(";") if value.strip()]
        argv.append(parameter.option)
        argv.extend(values)

    for spec in settings or option_specs():
        value = setting_values.get(spec.dest)
        if spec.kind == "boolean":
            if value:
                argv.append(spec.option)
        elif value is not None and str(value).strip():
            argv.extend((spec.option, str(value).strip()))
    return argv


def format_command(argv: Sequence[str]) -> str:
    """Representation lisible de la commande exacte qui sera lancee."""

    words = ["doot", *argv]
    if os.name == "nt":
        return subprocess.list2cmdline(words)
    return shlex.join(words)


def wheel_units(delta: int) -> int:
    """Convertit une molette Windows/macOS en un nombre d'unites non nul."""
    if delta == 0:
        return 0
    magnitude = max(1, round(abs(delta) / 120))
    return -magnitude if delta > 0 else magnitude


def widget_is_inside(widget, ancestor) -> bool:
    """Dit si ``widget`` est ``ancestor`` ou l'un de ses descendants Tk."""
    while widget is not None:
        if widget is ancestor:
            return True
        widget = getattr(widget, "master", None)
    return False


class BoneScrollbar:
    """Scrollbar verticale dessinee comme un os, compatible avec ``yview``."""

    def __init__(self, master, tk_module, command, *, background: str,
                 bone: str, outline: str, track: str) -> None:
        self.tk = tk_module
        self.command = command
        self.first = 0.0
        self.last = 1.0
        self.thumb_top = 5.0
        self.thumb_bottom = 45.0
        self.drag_offset: float | None = None
        self.background = background
        self.bone = bone
        self.outline = outline
        self.track = track
        self.canvas = tk_module.Canvas(
            master, width=24, bg=background, bd=0, highlightthickness=0,
            cursor="hand2",
        )
        self.canvas.bind("<Configure>", lambda _event: self._draw())
        self.canvas.bind("<Button-1>", self._press)
        self.canvas.bind("<B1-Motion>", self._drag)
        self.canvas.bind("<ButtonRelease-1>", self._release)

    def pack(self, *args, **kwargs):
        return self.canvas.pack(*args, **kwargs)

    def grid(self, *args, **kwargs):
        return self.canvas.grid(*args, **kwargs)

    def set(self, first, last) -> None:
        self.first = max(0.0, min(1.0, float(first)))
        self.last = max(self.first, min(1.0, float(last)))
        self._draw()

    def _metrics(self) -> tuple[float, float, float]:
        height = max(1.0, float(self.canvas.winfo_height()))
        padding = 7.0
        track_length = max(1.0, height - padding * 2)
        visible = max(0.0, min(1.0, self.last - self.first))
        thumb_length = min(track_length, max(42.0, track_length * visible))
        travel = max(0.0, track_length - thumb_length)
        if visible >= 1.0 or travel == 0.0:
            top = padding
        else:
            top = padding + travel * (self.first / max(0.0001, 1.0 - visible))
        return top, top + thumb_length, travel

    def _draw(self) -> None:
        canvas = self.canvas
        canvas.delete("all")
        width = max(1, canvas.winfo_width())
        height = max(1, canvas.winfo_height())
        middle = width / 2
        canvas.create_line(
            middle, 5, middle, height - 5, fill=self.track, width=2,
        )
        top, bottom, _travel = self._metrics()
        self.thumb_top, self.thumb_bottom = top, bottom

        # Diaphyse : la tige centrale legerement doree de l'os.
        canvas.create_rectangle(
            middle - 3, top + 7, middle + 3, bottom - 7,
            fill=self.bone, outline=self.outline, width=1,
        )
        # Epiphyses : deux lobes a chaque extremite donnent la silhouette d'os.
        for y1, y2 in ((top, top + 11), (bottom - 11, bottom)):
            canvas.create_oval(
                middle - 8, y1, middle, y2,
                fill=self.bone, outline=self.outline, width=1,
            )
            canvas.create_oval(
                middle, y1, middle + 8, y2,
                fill=self.bone, outline=self.outline, width=1,
            )
        canvas.create_oval(
            middle - 4, top + 4, middle + 4, top + 12,
            fill=self.bone, outline=self.outline, width=1,
        )
        canvas.create_oval(
            middle - 4, bottom - 12, middle + 4, bottom - 4,
            fill=self.bone, outline=self.outline, width=1,
        )

    def _press(self, event) -> None:
        if self.thumb_top <= event.y <= self.thumb_bottom:
            self.drag_offset = event.y - self.thumb_top
        else:
            direction = -1 if event.y < self.thumb_top else 1
            self.command("scroll", direction, "pages")

    def _drag(self, event) -> None:
        if self.drag_offset is None:
            return
        top, bottom, travel = self._metrics()
        if travel <= 0:
            return
        padding = 7.0
        fraction = (event.y - self.drag_offset - padding) / travel
        self.command("moveto", max(0.0, min(1.0, fraction)))

    def _release(self, _event) -> None:
        self.drag_offset = None


class DootApp:
    """Fenetre Tkinter : galerie de commandes, reglages et sortie integree."""

    BG = "#0e0b14"
    PANEL = "#171120"
    PANEL_2 = "#20172b"
    CARD = "#261b32"
    CARD_ACTIVE = "#3b2547"
    GOLD = "#d7a84a"
    GOLD_LIGHT = "#f3d486"
    BONE = "#f2e7cf"
    MUTED = "#aa9cb4"
    PURPLE = "#9b6bd1"
    EMBER = "#e76f36"

    def __init__(self, root) -> None:
        import tkinter as tk
        from tkinter import ttk

        self.tk = tk
        self.ttk = ttk
        self.root = root
        self.settings = option_specs()
        self.setting_vars: dict[str, object] = {}
        self.parameter_vars: dict[str, object] = {}
        self.command_buttons: dict[str, object] = {}
        self.images: dict[str, object] = {}
        self.events: queue.Queue = queue.Queue()
        self.processes: list[subprocess.Popen] = []
        self.wheel_canvases: list[object] = []
        self.wheel_bindings_installed = False
        self.composer_pattern = composer.empty_pattern()
        self.composer_cells: dict[tuple[int, str], object] = {}

        root.title("doot — grimoire de commandes")
        root.geometry("1180x860")
        root.minsize(940, 700)
        root.configure(bg=self.BG)
        self._style()
        icon = self._load_image("logo.png", 64)
        if icon is not None:
            root.iconphoto(True, icon)

        self.selected_key = tk.StringVar(value=COMMANDS[0].key)
        self.command_title = tk.StringVar()
        self.command_description = tk.StringVar()
        self.preview = tk.StringVar()

        self._build_header()
        self._build_body()
        self._select_command(COMMANDS[0].key)
        self.root.after(80, self._drain_events)

    def _style(self) -> None:
        style = self.ttk.Style(self.root)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure(".", background=self.BG, foreground=self.BONE,
                        font=("Segoe UI", 10))
        style.configure("TFrame", background=self.BG)
        style.configure("Panel.TFrame", background=self.PANEL)
        style.configure("Card.TFrame", background=self.PANEL_2)
        style.configure("TLabel", background=self.BG, foreground=self.BONE)
        style.configure("Muted.TLabel", foreground=self.MUTED)
        style.configure("Gold.TLabel", foreground=self.GOLD_LIGHT)
        style.configure("Title.TLabel", foreground=self.GOLD_LIGHT,
                        font=("Georgia", 24, "bold"))
        style.configure("CommandTitle.TLabel", foreground=self.GOLD_LIGHT,
                        background=self.PANEL, font=("Georgia", 18, "bold"))
        style.configure("Panel.TLabel", background=self.PANEL)
        style.configure("PanelMuted.TLabel", background=self.PANEL, foreground=self.MUTED)
        style.configure("Option.TLabel", background=self.PANEL_2,
                        foreground=self.GOLD_LIGHT, font=("Consolas", 9, "bold"))
        style.configure("OptionHelp.TLabel", background=self.PANEL_2,
                        foreground=self.MUTED, font=("Segoe UI", 9))
        style.configure("TEntry", fieldbackground="#120e19", foreground=self.BONE,
                        insertcolor=self.BONE, bordercolor="#4a365a", padding=7)
        style.configure("TCombobox", fieldbackground="#120e19", foreground=self.BONE,
                        arrowcolor=self.GOLD, bordercolor="#4a365a", padding=6)
        style.map("TCombobox", fieldbackground=[("readonly", "#120e19")],
                  foreground=[("readonly", self.BONE)])
        style.configure("TCheckbutton", background=self.PANEL_2, foreground=self.BONE,
                        indicatorcolor="#120e19", indicatormargin=5)
        style.map("TCheckbutton", background=[("active", self.PANEL_2)],
                  indicatorcolor=[("selected", self.EMBER)])
        style.configure("Run.TButton", background=self.EMBER, foreground="#fff8e8",
                        borderwidth=0, padding=(18, 11), font=("Segoe UI", 11, "bold"))
        style.map("Run.TButton", background=[("active", "#f28b51"), ("pressed", "#bd4f25")])
        style.configure("Clear.TButton", background="#382745", foreground=self.BONE,
                        borderwidth=0, padding=(12, 8))
        style.map("Clear.TButton", background=[("active", "#4c3560")])
        style.configure("TLabelframe", background=self.PANEL, bordercolor="#4c365a")
        style.configure("TLabelframe.Label", background=self.PANEL,
                        foreground=self.GOLD_LIGHT, font=("Georgia", 11, "bold"))
        style.configure("Vertical.TScrollbar", background="#33223e", troughcolor=self.BG,
                        arrowcolor=self.GOLD, bordercolor=self.BG)
        style.configure("TNotebook", background=self.PANEL, borderwidth=0)
        style.configure("TNotebook.Tab", background="#24192f", foreground=self.MUTED,
                        borderwidth=0, padding=(16, 8))
        style.map("TNotebook.Tab", background=[("selected", self.CARD_ACTIVE)],
                  foreground=[("selected", self.GOLD_LIGHT)])
        style.configure(
            "Achievement.Horizontal.TProgressbar",
            troughcolor="#120e19", background=self.EMBER,
            bordercolor="#120e19", lightcolor=self.EMBER, darkcolor=self.EMBER,
        )

    def _load_image(self, relative: str, target: int = 58):
        key = f"{relative}:{target}"
        if key in self.images:
            return self.images[key]
        try:
            source = self.tk.PhotoImage(file=str(ASSETS_DIR / relative))
            factor = max(1, (max(source.width(), source.height()) + target - 1) // target)
            image = source.subsample(factor)
        except Exception:
            image = None
        self.images[key] = image
        return image

    def _build_header(self) -> None:
        header = self.tk.Frame(self.root, bg=self.BG, height=224)
        header.pack(fill="x", padx=24, pady=(18, 8))
        header.pack_propagate(False)

        copy = self.tk.Frame(header, bg=self.BG)
        copy.pack(side="left", fill="both", expand=True, padx=(14, 10), pady=24)
        self.tk.Label(
            copy, text="LE GRIMOIRE DE DOOT", bg=self.BG, fg=self.GOLD,
            font=("Segoe UI", 10, "bold"), anchor="w",
        ).pack(fill="x")
        self.tk.Label(
            copy, text="Invoque chaque commande\nsans quitter la crypte.",
            bg=self.BG, fg=self.BONE, font=("Georgia", 27, "bold"),
            justify="left", anchor="w",
        ).pack(fill="x", pady=(6, 8))
        self.tk.Label(
            copy,
            text="Choisis une action, ajuste ses runes, puis sonne la trompette.",
            bg=self.BG, fg=self.MUTED, font=("Segoe UI", 11), anchor="w",
        ).pack(fill="x")
        countdown = season.countdown()
        if countdown:
            self.tk.Label(
                copy, text=countdown, bg=self.BG, fg=self.EMBER,
                font=("Consolas", 12, "bold"), anchor="w",
            ).pack(fill="x", pady=(12, 0))

        hero = self._load_image("gui-command-center.png", 210)
        self.tk.Label(header, image=hero, bg=self.BG, bd=0).pack(
            side="right", padx=(8, 24), pady=2,
        )

        self.tk.Frame(self.root, bg=self.GOLD, height=1).pack(fill="x", padx=38)

    def _build_body(self) -> None:
        body = self.tk.PanedWindow(
            self.root, orient="horizontal", bg=self.BG, bd=0,
            sashwidth=7, sashrelief="flat",
        )
        body.pack(fill="both", expand=True, padx=24, pady=(12, 20))

        gallery = self.tk.Frame(body, bg=self.PANEL, width=365)
        details = self.tk.Frame(body, bg=self.PANEL)
        body.add(gallery, minsize=300, width=365)
        body.add(details, minsize=500)
        self._build_gallery(gallery)
        self._build_details(details)

    def _build_gallery(self, parent) -> None:
        self.tk.Label(
            parent, text="COMMANDES", bg=self.PANEL, fg=self.GOLD_LIGHT,
            font=("Georgia", 14, "bold"), anchor="w",
        ).pack(fill="x", padx=18, pady=(17, 10))

        canvas = self.tk.Canvas(parent, bg=self.PANEL, highlightthickness=0, bd=0)
        scrollbar = self._bone_scrollbar(parent, canvas.yview, self.PANEL)
        holder = self.tk.Frame(canvas, bg=self.PANEL)
        window = canvas.create_window((0, 0), window=holder, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y", padx=(0, 3), pady=(0, 12))
        canvas.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=(0, 12))
        holder.bind("<Configure>", lambda _event: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(window, width=event.width))
        self._wheel_scroll(canvas, holder)

        for command in COMMANDS:
            image = self._load_image(command.image)
            button = self.tk.Button(
                holder, text=command.title, image=image, compound="left",
                command=lambda key=command.key: self._select_command(key),
                bg=self.CARD, fg=self.BONE, activebackground=self.CARD_ACTIVE,
                activeforeground=self.GOLD_LIGHT, bd=0, relief="flat",
                anchor="w", justify="left", padx=10, pady=8,
                font=("Segoe UI", 10, "bold"), cursor="hand2",
            )
            button.pack(fill="x", padx=5, pady=3)
            self.command_buttons[command.key] = button

    def _build_details(self, parent) -> None:
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(2, weight=1)

        intro = self.tk.Frame(parent, bg=self.PANEL)
        intro.grid(row=0, column=0, sticky="ew", padx=22, pady=(17, 10))
        self.ttk.Label(intro, textvariable=self.command_title,
                       style="CommandTitle.TLabel").pack(anchor="w")
        self.ttk.Label(
            intro, textvariable=self.command_description, style="PanelMuted.TLabel",
            wraplength=680, justify="left",
        ).pack(fill="x", anchor="w", pady=(5, 0))

        self.parameter_box = self.ttk.LabelFrame(parent, text="  Parametres de la commande  ")
        self.parameter_box.grid(row=1, column=0, sticky="ew", padx=22, pady=(4, 9))

        notebook = self.ttk.Notebook(parent)
        notebook.grid(row=2, column=0, sticky="nsew", padx=22, pady=(0, 10))
        options_tab = self.tk.Frame(notebook, bg=self.PANEL_2)
        composer_tab = self.tk.Frame(notebook, bg=self.PANEL_2)
        achievements_tab = self.tk.Frame(notebook, bg=self.PANEL_2)
        registre_tab = self.tk.Frame(notebook, bg=self.PANEL_2)
        output_tab = self.tk.Frame(notebook, bg="#0b0910")
        notebook.add(options_tab, text="  Reglages  ")
        notebook.add(composer_tab, text="  Compositeur  ")
        notebook.add(achievements_tab, text="  Succes  ")
        notebook.add(registre_tab, text="  Registre  ")
        notebook.add(output_tab, text="  Sortie  ")
        self.notebook = notebook
        self.achievements_tab = achievements_tab
        self.registre_tab = registre_tab
        self.output_tab = output_tab
        self._build_settings(options_tab)
        self._build_composer(composer_tab)
        self._build_achievements(achievements_tab)
        self._build_registre(registre_tab)
        self._build_output(output_tab)

        launch = self.tk.Frame(parent, bg=self.PANEL)
        launch.grid(row=3, column=0, sticky="ew", padx=22, pady=(0, 17))
        preview_label = self.tk.Label(
            launch, textvariable=self.preview, bg="#0b0910", fg=self.PURPLE,
            font=("Consolas", 9), anchor="w", justify="left", padx=12, pady=9,
        )
        preview_label.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.ttk.Button(
            launch, text="SONNER LA TROMPETTE  ›", style="Run.TButton",
            command=self._run_selected,
        ).pack(side="right")

    def _build_settings(self, parent) -> None:
        canvas = self.tk.Canvas(parent, bg=self.PANEL_2, highlightthickness=0, bd=0)
        scrollbar = self._bone_scrollbar(parent, canvas.yview, self.PANEL_2)
        holder = self.tk.Frame(canvas, bg=self.PANEL_2)
        window = canvas.create_window((0, 0), window=holder, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y", padx=(0, 3), pady=4)
        canvas.pack(side="left", fill="both", expand=True)
        holder.bind("<Configure>", lambda _event: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(window, width=event.width))
        self._wheel_scroll(canvas, holder)

        heading = self.tk.Frame(holder, bg=self.PANEL_2)
        heading.pack(fill="x", padx=16, pady=(13, 7))
        self.tk.Label(
            heading, text="Toutes les options de doot", bg=self.PANEL_2,
            fg=self.GOLD_LIGHT, font=("Georgia", 13, "bold"), anchor="w",
        ).pack(side="left")
        self.ttk.Button(
            heading, text="Effacer les reglages", style="Clear.TButton",
            command=self._clear_settings,
        ).pack(side="right")

        for index, spec in enumerate(self.settings):
            row = self.tk.Frame(holder, bg=self.PANEL_2)
            row.pack(fill="x", padx=16, pady=5)
            labels = self.tk.Frame(row, bg=self.PANEL_2)
            labels.pack(side="left", fill="x", expand=True, padx=(0, 12))
            self.ttk.Label(labels, text=spec.option, style="Option.TLabel").pack(anchor="w")
            help_text = spec.help
            if spec.kind != "boolean" and spec.default not in (None, ""):
                help_text += f"  ·  defaut : {spec.default}"
            self.ttk.Label(
                labels, text=help_text, style="OptionHelp.TLabel",
                wraplength=420, justify="left",
            ).pack(fill="x", anchor="w", pady=(1, 0))

            if spec.kind == "boolean":
                variable = self.tk.BooleanVar(value=False)
                widget = self.ttk.Checkbutton(row, text="Activer", variable=variable)
            elif spec.kind == "choice":
                variable = self.tk.StringVar(value="")
                widget = self.ttk.Combobox(
                    row, textvariable=variable, values=("", *spec.choices),
                    state="readonly", width=19,
                )
            else:
                variable = self.tk.StringVar(value="")
                widget = self.ttk.Entry(row, textvariable=variable, width=22)
            widget.pack(side="right", padx=(4, 2))
            variable.trace_add("write", lambda *_args: self._update_preview())
            self.setting_vars[spec.dest] = variable

            self.tk.Frame(holder, bg="#30233c", height=1).pack(
                fill="x", padx=16, pady=(2 if index < len(self.settings) - 1 else 12, 0),
            )

    def _build_composer(self, parent) -> None:
        """Grille a la Mario Paint : une hauteur possible par pas."""
        toolbar = self.tk.Frame(parent, bg=self.PANEL_2)
        toolbar.pack(fill="x", padx=14, pady=(12, 8))

        self.composer_title = self.tk.StringVar(value="ma-melodie")
        self.composer_tempo = self.tk.StringVar(value="120")
        self.composer_octave = self.tk.StringVar(value="5")
        for label, variable, width in (
            ("Nom", self.composer_title, 20),
            ("BPM", self.composer_tempo, 7),
        ):
            self.tk.Label(
                toolbar, text=label, bg=self.PANEL_2, fg=self.GOLD_LIGHT,
                font=("Segoe UI", 9, "bold"),
            ).pack(side="left", padx=(0, 5))
            self.ttk.Entry(toolbar, textvariable=variable, width=width).pack(
                side="left", padx=(0, 12),
            )
        self.tk.Label(
            toolbar, text="Octave", bg=self.PANEL_2, fg=self.GOLD_LIGHT,
            font=("Segoe UI", 9, "bold"),
        ).pack(side="left", padx=(0, 5))
        self.ttk.Combobox(
            toolbar, textvariable=self.composer_octave,
            values=tuple(str(value) for value in range(3, 8)),
            state="readonly", width=4,
        ).pack(side="left")
        self.ttk.Button(
            toolbar, text="Effacer", style="Clear.TButton",
            command=self._composer_clear,
        ).pack(side="right")

        grid = self.tk.Frame(parent, bg=self.PANEL_2)
        grid.pack(fill="both", expand=True, padx=14, pady=(0, 8))
        self.tk.Label(
            grid, text="NOTE", bg=self.PANEL_2, fg=self.MUTED,
            font=("Consolas", 8, "bold"), width=6,
        ).grid(row=0, column=0, padx=(0, 4), pady=(0, 3))
        for step in range(composer.STEPS):
            self.tk.Label(
                grid, text=str(step + 1), bg=self.PANEL_2,
                fg=self.GOLD if step % 4 == 0 else self.MUTED,
                font=("Consolas", 8, "bold"), width=2,
            ).grid(row=0, column=step + 1, padx=1, pady=(0, 3))

        for row, (label, note) in enumerate(composer.PITCHES, 1):
            self.tk.Label(
                grid, text=label, bg=self.PANEL_2, fg=self.BONE,
                font=("Consolas", 8, "bold"), width=6, anchor="e",
            ).grid(row=row, column=0, padx=(0, 5), pady=1, sticky="e")
            for step in range(composer.STEPS):
                cell = self.tk.Button(
                    grid, text="", width=2, height=1, bd=0,
                    bg=self.CARD, activebackground=self.GOLD,
                    fg="#fff8e8", activeforeground="#fff8e8",
                    cursor="hand2",
                    command=lambda s=step, n=note: self._composer_toggle(s, n),
                )
                cell.grid(row=row, column=step + 1, padx=1, pady=1, sticky="nsew")
                self.composer_cells[(step, note)] = cell
        for column in range(1, composer.STEPS + 1):
            grid.grid_columnconfigure(column, weight=1)

        footer = self.tk.Frame(parent, bg=self.PANEL_2)
        footer.pack(fill="x", padx=14, pady=(0, 12))
        self.composer_status = self.tk.StringVar(
            value="Pose des notes sur les 16 pas, puis ecoute ou sauvegarde.",
        )
        self.tk.Label(
            footer, textvariable=self.composer_status, bg=self.PANEL_2,
            fg=self.MUTED, font=("Consolas", 8), anchor="w", justify="left",
            wraplength=390,
        ).pack(side="left", fill="x", expand=True)
        self.ttk.Button(
            footer, text="Sauvegarder", style="Clear.TButton",
            command=self._composer_save,
        ).pack(side="right", padx=(8, 0))
        self.ttk.Button(
            footer, text="ECOUTER  ›", style="Run.TButton",
            command=self._composer_play,
        ).pack(side="right")
        for variable in (
                self.composer_title, self.composer_tempo, self.composer_octave):
            variable.trace_add("write", lambda *_args: self._composer_refresh())

    def _composer_toggle(self, step: int, note: str) -> None:
        composer.toggle(self.composer_pattern, step, note)
        self._composer_refresh()

    def _composer_refresh(self) -> None:
        for (step, note), cell in self.composer_cells.items():
            selected = self.composer_pattern[step] == note
            cell.configure(
                text="♪" if selected else "",
                bg=self.EMBER if selected else self.CARD,
            )
        try:
            text = composer.rtttl(
                self.composer_title.get(), int(self.composer_tempo.get()),
                int(self.composer_octave.get()), self.composer_pattern,
            )
            self.composer_status.set(text.strip())
        except (ValueError, composer.ComposerError) as exc:
            self.composer_status.set(str(exc))

    def _composer_clear(self) -> None:
        self.composer_pattern[:] = composer.empty_pattern()
        self._composer_refresh()

    def _composer_values(self) -> tuple[str, int, int]:
        try:
            return (
                self.composer_title.get(), int(self.composer_tempo.get()),
                int(self.composer_octave.get()),
            )
        except ValueError as exc:
            raise composer.ComposerError("le tempo et l'octave doivent etre des nombres") from exc

    def _composer_save(self) -> None:
        from . import cli

        try:
            title, tempo, octave = self._composer_values()
            path = composer.save(
                cli.paths()["melodies"], title, tempo, octave, self.composer_pattern,
            )
        except (OSError, composer.ComposerError) as exc:
            self.composer_status.set(f"Impossible de sauvegarder : {exc}")
            return
        self.composer_status.set(f"Sauvegardee : {path}")

    def _composer_play(self) -> None:
        from . import cli

        try:
            title, tempo, octave = self._composer_values()
            path = composer.write(
                cli.paths()["data"] / "composer-preview.rtttl",
                title, tempo, octave, self.composer_pattern,
            )
        except (OSError, composer.ComposerError) as exc:
            self.composer_status.set(f"Impossible de jouer : {exc}")
            return
        self._launch_argv(["--play", str(path), "--ignore-season"])

    def _build_achievements(self, parent) -> None:
        toolbar = self.tk.Frame(parent, bg=self.PANEL_2)
        toolbar.pack(fill="x", padx=16, pady=(12, 8))
        heading = self.tk.Frame(toolbar, bg=self.PANEL_2)
        heading.pack(side="left", fill="x", expand=True)
        self.tk.Label(
            heading, text="CABINET DES TROPHEES", bg=self.PANEL_2,
            fg=self.GOLD_LIGHT, font=("Georgia", 13, "bold"), anchor="w",
        ).pack(anchor="w")
        self.achievement_summary = self.tk.StringVar(value="Chargement des succes...")
        self.tk.Label(
            heading, textvariable=self.achievement_summary, bg=self.PANEL_2,
            fg=self.MUTED, font=("Segoe UI", 9), anchor="w",
        ).pack(anchor="w", pady=(2, 0))
        self.ttk.Button(
            toolbar, text="Actualiser", style="Clear.TButton",
            command=self._refresh_achievements,
        ).pack(side="right", padx=(10, 0))

        canvas = self.tk.Canvas(parent, bg=self.PANEL_2, highlightthickness=0, bd=0)
        scrollbar = self._bone_scrollbar(parent, canvas.yview, self.PANEL_2)
        holder = self.tk.Frame(canvas, bg=self.PANEL_2)
        window = canvas.create_window((0, 0), window=holder, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y", padx=(0, 3), pady=(0, 4))
        canvas.pack(side="left", fill="both", expand=True)
        holder.bind(
            "<Configure>",
            lambda _event: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.bind(
            "<Configure>",
            lambda event: self._resize_achievement_gallery(canvas, window, event.width),
        )
        self._wheel_scroll(canvas, holder)
        self.achievement_holder = holder
        self.achievement_widgets: list[object] = []
        self.achievement_columns = 0
        self._refresh_achievements()

    def _refresh_achievements(self) -> None:
        """Relit l'etat et redessine les cartes, succes acquis en premier."""

        from . import cli

        etat = cli.read_state()
        cards = achievement_cards(etat)
        unlocked = sum(card.debloque_le is not None for card in cards)
        total_points = sum(card.points for card in cards)
        self.achievement_summary.set(
            f"{unlocked}/{len(cards)} debloques  ·  "
            f"{succes.score(etat)}/{total_points} points"
        )

        holder = self.achievement_holder
        for child in holder.winfo_children():
            child.destroy()
        ordered = sorted(cards, key=lambda card: card.debloque_le is None)
        self.achievement_widgets = [
            self._build_achievement_card(holder, card) for card in ordered
        ]
        self.achievement_columns = 0
        self._layout_achievement_cards(max(1, holder.winfo_width()))

    def _resize_achievement_gallery(self, canvas, window, width: int) -> None:
        canvas.itemconfigure(window, width=width)
        self._layout_achievement_cards(width)

    def _layout_achievement_cards(self, width: int) -> None:
        """Passe de une a deux colonnes selon la place reellement disponible."""

        columns = 2 if width >= 620 else 1
        if columns == self.achievement_columns:
            return
        self.achievement_columns = columns
        for column in range(2):
            self.achievement_holder.grid_columnconfigure(
                column, weight=1 if column < columns else 0,
                uniform="achievement" if column < columns else "",
            )
        for index, widget in enumerate(self.achievement_widgets):
            widget.grid_forget()
            column = index % columns
            widget.grid(
                row=index // columns, column=column, sticky="nsew",
                padx=(12 if column == 0 else 6, 12 if column == columns - 1 else 6),
                pady=6,
            )

    def _build_achievement_card(self, parent, card: AchievementCard):
        unlocked = card.debloque_le is not None
        background = self.CARD_ACTIVE if unlocked else self.CARD
        border = self.GOLD if unlocked else "#493653"
        frame = self.tk.Frame(
            parent, bg=background, highlightthickness=1,
            highlightbackground=border, padx=10, pady=10,
        )

        image = self._load_image(f"success/{card.identifiant}.png", 72)
        self.tk.Label(frame, image=image, bg=background, bd=0).pack(
            side="left", anchor="n", padx=(0, 10),
        )
        copy = self.tk.Frame(frame, bg=background)
        copy.pack(side="left", fill="both", expand=True)
        title_row = self.tk.Frame(copy, bg=background)
        title_row.pack(fill="x")
        self.tk.Label(
            title_row, text=card.titre, bg=background,
            fg=self.GOLD_LIGHT if unlocked else self.BONE,
            font=("Georgia", 11, "bold"), anchor="w", justify="left",
            wraplength=180,
        ).pack(side="left", fill="x", expand=True)
        self.tk.Label(
            title_row, text=f"+{card.points}", bg=background,
            fg=self.GOLD, font=("Segoe UI", 9, "bold"),
        ).pack(side="right", anchor="n", padx=(5, 0))
        self.tk.Label(
            copy, text=card.description, bg=background, fg=self.MUTED,
            font=("Segoe UI", 8), anchor="w", justify="left", wraplength=205,
        ).pack(fill="x", anchor="w", pady=(4, 7))

        if unlocked:
            status = f"DEBLOQUE LE {_achievement_date(card.debloque_le or '')}"
            status_color = self.GOLD_LIGHT
        else:
            status = f"PROGRESSION  {card.courant}/{card.objectif}"
            status_color = self.MUTED
        self.tk.Label(
            copy, text=status, bg=background, fg=status_color,
            font=("Consolas", 8, "bold"), anchor="w",
        ).pack(fill="x", anchor="w")
        self.ttk.Progressbar(
            copy, style="Achievement.Horizontal.TProgressbar", mode="determinate",
            maximum=max(1, card.objectif), value=card.courant,
        ).pack(fill="x", pady=(5, 0))
        return frame

    CASE = 14
    ECART = 3
    MARGE_GAUCHE = 36
    MARGE_HAUT = 20

    def _build_registre(self, parent) -> None:
        toolbar = self.tk.Frame(parent, bg=self.PANEL_2)
        toolbar.pack(fill="x", padx=16, pady=(12, 8))
        heading = self.tk.Frame(toolbar, bg=self.PANEL_2)
        heading.pack(side="left", fill="x", expand=True)
        self.tk.Label(
            heading, text="REGISTRE DE LA CRYPTE", bg=self.PANEL_2,
            fg=self.GOLD_LIGHT, font=("Georgia", 13, "bold"), anchor="w",
        ).pack(anchor="w")
        self.registre_summary = self.tk.StringVar(value="Lecture de l'etat...")
        self.tk.Label(
            heading, textvariable=self.registre_summary, bg=self.PANEL_2,
            fg=self.MUTED, font=("Segoe UI", 9), anchor="w",
        ).pack(anchor="w", pady=(2, 0))
        self.ttk.Button(
            toolbar, text="Actualiser", style="Clear.TButton",
            command=self._refresh_registre,
        ).pack(side="right", padx=(10, 0))

        canvas = self.tk.Canvas(parent, bg=self.PANEL_2, highlightthickness=0, bd=0)
        scrollbar = self._bone_scrollbar(parent, canvas.yview, self.PANEL_2)
        holder = self.tk.Frame(canvas, bg=self.PANEL_2)
        window = canvas.create_window((0, 0), window=holder, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y", padx=(0, 3), pady=(0, 4))
        canvas.pack(side="left", fill="both", expand=True)
        holder.bind(
            "<Configure>",
            lambda _event: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.bind(
            "<Configure>",
            lambda event: canvas.itemconfigure(window, width=event.width),
        )
        self._wheel_scroll(canvas, holder)
        self.registre_holder = holder
        self._refresh_registre()

    def _refresh_registre(self) -> None:
        """Relit l'etat et redessine le registre entier."""

        from . import cli

        vue = registre_vue(cli.read_state())
        bilan = vue.resume
        self.registre_summary.set(
            f"{bilan.doots} doots  ·  {bilan.jours} soirs  ·  "
            f"{bilan.codex}/{bilan.codex_total} apparitions  ·  {bilan.points} points"
        )

        holder = self.registre_holder
        for child in holder.winfo_children():
            child.destroy()

        saison = vue.saison
        titre = (f"Saison {saison.annee}  -  {len(saison.actifs)} soir(s) "
                 f"sur {saison.duree}")
        section = self._registre_section(holder, titre)
        grille = self.tk.Canvas(
            section, bg=self.PANEL_2, highlightthickness=0, bd=0,
        )
        grille.pack(anchor="w", pady=(4, 2))
        self._dessiner_saison(grille, saison)
        self.tk.Label(
            section, text="une case par soir ; pleine des qu'un doot a eu lieu, "
                          "l'etat ne compte pas les doots par jour",
            bg=self.PANEL_2, fg=self.MUTED, font=("Segoe UI", 8),
            anchor="w", justify="left", wraplength=520,
        ).pack(anchor="w")
        for annee, actifs, duree in vue.precedentes:
            self._registre_ligne(section, f"Saison {annee}", f"{actifs} soir(s) sur {duree}")

        if vue.totaux:
            section = self._registre_section(holder, "Totaux")
            for libelle, valeur in vue.totaux:
                self._registre_ligne(section, libelle, str(valeur))

        section = self._registre_section(holder, "Records")
        for libelle, valeur in vue.records:
            self._registre_ligne(section, libelle, str(valeur))

        if vue.postes:
            section = self._registre_section(holder, "Machines")
            for poste in vue.postes:
                nom = poste.machine + (" (ici)" if poste.machine == vue.ici else "")
                self._registre_ligne(
                    section, nom,
                    f"{poste.doots} doots, {poste.melodies} melodies, "
                    f"{poste.evenements} rencontres",
                )

        section = self._registre_section(holder, "Collections")
        for libelle, valeurs in vue.collections:
            self._registre_ligne(section, libelle, ", ".join(valeurs) or "(aucune)")

    def _registre_section(self, parent, titre: str):
        frame = self.tk.Frame(parent, bg=self.PANEL_2)
        frame.pack(fill="x", padx=16, pady=(6, 10))
        self.tk.Label(
            frame, text=titre, bg=self.PANEL_2, fg=self.GOLD,
            font=("Georgia", 11, "bold"), anchor="w",
        ).pack(anchor="w", pady=(0, 4))
        return frame

    def _registre_ligne(self, parent, libelle: str, valeur: str) -> None:
        row = self.tk.Frame(parent, bg=self.PANEL_2)
        row.pack(fill="x", pady=1)
        self.tk.Label(
            row, text=libelle, bg=self.PANEL_2, fg=self.MUTED,
            font=("Segoe UI", 9), anchor="w", width=26,
        ).pack(side="left")
        self.tk.Label(
            row, text=valeur, bg=self.PANEL_2, fg=self.BONE,
            font=("Segoe UI", 9, "bold"), anchor="w", justify="left",
        ).pack(side="left", fill="x", expand=True)

    def _dessiner_saison(self, canvas, saison) -> None:
        """La saison en cases : une colonne par semaine, du lundi au dimanche."""

        canvas.delete("all")
        pas = self.CASE + self.ECART
        for rang, nom in enumerate(registre.JOURS):
            if rang % 2:
                continue  # une etiquette sur deux : sept lignes de 14 px n'en tiennent pas plus
            canvas.create_text(
                self.MARGE_GAUCHE - 8, self.MARGE_HAUT + rang * pas + self.CASE / 2,
                text=nom, anchor="e", fill=self.MUTED, font=("Segoe UI", 8),
            )

        etiquetes = set()
        for index, colonne in enumerate(saison.semaines):
            for rang, jour in enumerate(colonne):
                if jour is None:
                    continue
                x = self.MARGE_GAUCHE + index * pas
                y = self.MARGE_HAUT + rang * pas
                canvas.create_rectangle(
                    x, y, x + self.CASE, y + self.CASE, width=0,
                    fill=self.GOLD if jour in saison.actifs else self.CARD,
                )
                if jour.month in etiquetes:
                    continue
                if jour.day == 1 or index == 0:
                    etiquetes.add(jour.month)
                    canvas.create_text(
                        x, self.MARGE_HAUT - 9, text=registre.MOIS[jour.month],
                        anchor="w", fill=self.MUTED, font=("Segoe UI", 8),
                    )

        largeur = self.MARGE_GAUCHE + max(1, len(saison.semaines)) * pas
        hauteur = self.MARGE_HAUT + registre.SEMAINE * pas
        canvas.configure(width=largeur, height=hauteur)

    def _build_output(self, parent) -> None:
        toolbar = self.tk.Frame(parent, bg="#0b0910")
        toolbar.pack(fill="x", padx=10, pady=(8, 0))
        self.tk.Label(
            toolbar, text="JOURNAL D'INVOCATION", bg="#0b0910", fg=self.GOLD,
            font=("Consolas", 9, "bold"),
        ).pack(side="left")
        self.ttk.Button(
            toolbar, text="Effacer", style="Clear.TButton", command=self._clear_output,
        ).pack(side="right")
        output_body = self.tk.Frame(parent, bg="#0b0910")
        output_body.pack(fill="both", expand=True)
        self.output = self.tk.Text(
            output_body, bg="#0b0910", fg=self.BONE, insertbackground=self.BONE,
            selectbackground="#523a67", relief="flat", bd=0,
            font=("Consolas", 10), wrap="word", padx=14, pady=12,
        )
        output_scrollbar = self._bone_scrollbar(
            output_body, self.output.yview, "#0b0910",
        )
        self.output.configure(yscrollcommand=output_scrollbar.set)
        output_scrollbar.pack(side="right", fill="y", padx=(0, 3), pady=4)
        self.output.pack(side="left", fill="both", expand=True)
        self.output.configure(state="disabled")
        self.output.tag_configure("command", foreground=self.PURPLE)
        self.output.tag_configure("success", foreground=self.GOLD_LIGHT)
        self.output.tag_configure("error", foreground="#ff7b72")

    def _bone_scrollbar(self, parent, command, background: str) -> BoneScrollbar:
        return BoneScrollbar(
            parent, self.tk, command, background=background,
            bone=self.BONE, outline=self.GOLD, track="#4b3459",
        )

    def _wheel_scroll(self, canvas, _widget) -> None:
        """Enregistre un canevas defilable sans casser les widgets enfants."""
        self.wheel_canvases.append(canvas)
        if self.wheel_bindings_installed:
            return
        self.root.bind_all("<MouseWheel>", self._dispatch_wheel, add="+")
        self.root.bind_all("<Button-4>", self._dispatch_wheel, add="+")
        self.root.bind_all("<Button-5>", self._dispatch_wheel, add="+")
        self.wheel_bindings_installed = True

    def _dispatch_wheel(self, event):
        canvas = next(
            (
                candidate for candidate in self.wheel_canvases
                if widget_is_inside(getattr(event, "widget", None), candidate)
            ),
            None,
        )
        if canvas is None:
            return None

        delta = getattr(event, "delta", 0)
        if delta:
            units = wheel_units(delta)
        else:
            number = getattr(event, "num", 0)
            units = -1 if number == 4 else 1 if number == 5 else 0
        if units:
            canvas.yview_scroll(units, "units")
            return "break"
        return None

    def _selected_command(self) -> CommandSpec:
        key = self.selected_key.get()
        return next(command for command in COMMANDS if command.key == key)

    def _select_command(self, key: str) -> None:
        self.selected_key.set(key)
        command = self._selected_command()
        for command_key, button in self.command_buttons.items():
            selected = command_key == key
            button.configure(
                bg=self.CARD_ACTIVE if selected else self.CARD,
                fg=self.GOLD_LIGHT if selected else self.BONE,
            )
        self.command_title.set(command.title)
        self.command_description.set(command.description)
        for child in self.parameter_box.winfo_children():
            child.destroy()
        self.parameter_vars.clear()

        if not command.parameters:
            self.ttk.Label(
                self.parameter_box, text="Aucun parametre obligatoire.",
                style="PanelMuted.TLabel",
            ).pack(anchor="w", padx=12, pady=10)
        for parameter in command.parameters:
            row = self.tk.Frame(self.parameter_box, bg=self.PANEL)
            row.pack(fill="x", padx=12, pady=9)
            self.tk.Label(
                row, text=parameter.label, bg=self.PANEL, fg=self.GOLD_LIGHT,
                font=("Segoe UI", 9, "bold"), width=18, anchor="w",
            ).pack(side="left")
            variable = self.tk.StringVar(value="")
            variable.trace_add("write", lambda *_args: self._update_preview())
            self.ttk.Entry(row, textvariable=variable).pack(side="left", fill="x", expand=True)
            self.tk.Label(
                row, text=parameter.hint, bg=self.PANEL, fg=self.MUTED,
                font=("Segoe UI", 8), anchor="w",
            ).pack(side="left", padx=(10, 0))
            self.parameter_vars[parameter.option] = variable
        self._update_preview()
        # Une action qui dit ouvrir quelque chose l'ouvre. L'onglet se relit au
        # passage, puisqu'une commande lancee entre-temps a pu changer l'etat.
        rafraichir, onglet = ONGLETS_ETAT.get(key, (None, None))
        if onglet is not None:
            getattr(self, rafraichir)()
            self.notebook.select(getattr(self, onglet))

    def _values(self, variables: Mapping[str, object]) -> dict[str, object]:
        return {name: variable.get() for name, variable in variables.items()}

    def _current_argv(self, *, strict: bool) -> list[str]:
        return build_command_argv(
            self._selected_command(), self._values(self.parameter_vars),
            self._values(self.setting_vars), self.settings, strict=strict,
        )

    def _update_preview(self) -> None:
        if not hasattr(self, "preview"):
            return
        self.preview.set(format_command(self._current_argv(strict=False)))

    def _clear_settings(self) -> None:
        for variable in self.setting_vars.values():
            variable.set(False if isinstance(variable, self.tk.BooleanVar) else "")

    def _append_output(self, text: str, tag: str | None = None) -> None:
        self.output.configure(state="normal")
        self.output.insert("end", text, tag or ())
        self.output.see("end")
        self.output.configure(state="disabled")

    def _clear_output(self) -> None:
        self.output.configure(state="normal")
        self.output.delete("1.0", "end")
        self.output.configure(state="disabled")

    def _run_selected(self) -> None:
        try:
            argv = self._current_argv(strict=True)
        except ValueError as exc:
            self.notebook.select(self.output_tab)
            self._append_output(f"\n{exc}\n", "error")
            return

        self._launch_argv(argv, detached=self._selected_command().detached)

    def _launch_argv(self, argv: list[str], detached: bool = False) -> None:
        """Lance une commande doot et branche sa sortie sur le journal GUI."""
        shown = format_command(argv)
        self.notebook.select(self.output_tab)
        self._append_output(f"\n❯ {shown}\n", "command")
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        popen_args = [sys.executable, "-m", "doot", *argv]
        try:
            if detached:
                kwargs = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL,
                          "stderr": subprocess.DEVNULL, "env": env}
                if os.name == "nt":
                    kwargs["creationflags"] = (
                        getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
                        | getattr(subprocess, "CREATE_NO_WINDOW", 0)
                    )
                else:
                    kwargs["start_new_session"] = True
                process = subprocess.Popen(popen_args, **kwargs)
                self.processes.append(process)
                self._append_output(
                    f"Daemon lance en arriere-plan (pid {process.pid}).\n", "success",
                )
                return

            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
            process = subprocess.Popen(
                popen_args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL, text=True, encoding="utf-8", errors="replace",
                bufsize=1, env=env, creationflags=flags,
            )
            self.processes.append(process)
        except OSError as exc:
            self._append_output(f"Impossible de lancer doot : {exc}\n", "error")
            return

        threading.Thread(target=self._read_process, args=(process,), daemon=True).start()

    def _read_process(self, process: subprocess.Popen) -> None:
        assert process.stdout is not None
        for line in process.stdout:
            self.events.put(("line", line))
        self.events.put(("done", process.wait()))

    def _drain_events(self) -> None:
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == "line":
                    self._append_output(value)
                else:
                    tag = "success" if value == 0 else "error"
                    self._append_output(f"[termine avec le code {value}]\n", tag)
                    self._refresh_achievements()
                    self._refresh_registre()
        except queue.Empty:
            pass
        self.processes[:] = [process for process in self.processes if process.poll() is None]
        self.root.after(80, self._drain_events)


def main() -> int:
    """Ouvre le lanceur ; renvoie 4 quand Tkinter ou l'affichage manque."""

    try:
        import tkinter as tk
    except ImportError:
        print("doot : la GUI demande tkinter (le paquet python3-tk sous Linux).", file=sys.stderr)
        return 4
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        print(f"doot : impossible d'ouvrir la GUI : {exc}", file=sys.stderr)
        return 4
    DootApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
