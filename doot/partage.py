"""Ce qu'un poste publie de ses succes, et ce qu'il prend aux autres.

Aucun serveur : chaque machine ecrit un objet que seule elle ecrit, dans un
stockage que la personne a deja, dossier synchronise ou seau compatible S3. Les
objets a un seul ecrivain retirent toute resolution de conflit du dessin, et
chaque partie difficile d'un service de synchronisation disparait avec lui,
hebergement, authentification, disponibilite.

L'objet publie porte aussi ce que le poste a appris des autres. Deux machines
jamais allumees ensemble se rejoignent par l'intermediaire d'une troisieme, ce
que les parts par machine rendent sans danger : fusionner prend le maximum part
par part, jamais une somme.

L'identite de la replique et les reglages vivent dans `replica.json`, jamais
dans `state.json` : ce dernier se sauvegarde et se copie, et ni une identite
partagee ni un secret S3 recopie n'y ont leur place.
"""

from __future__ import annotations

import json
import platform
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from . import coffre, contagion, duel, succes, transport

FICHIER = "replica.json"

_connues: dict[str, str] = {}


def _empreinte(dossier: Path) -> str:
    """De quoi reconnaitre que l'installation n'est plus la meme."""
    return f"{platform.node()}|{dossier}"


def _fiche(dossier: Path) -> dict:
    try:
        note = json.loads((dossier / FICHIER).read_text(encoding="utf-8"))
    except Exception:
        return {}
    return note if isinstance(note, dict) else {}


def _ecrire_fiche(dossier: Path, note: dict) -> None:
    try:
        dossier.mkdir(parents=True, exist_ok=True)
        transport.ecrire_atomiquement(
            dossier / FICHIER,
            (json.dumps(note, indent=2, ensure_ascii=False) + "\n").encode("utf-8"),
            mode=0o600,
        )
    except OSError:
        pass


def identite(dossier: Path) -> str:
    """L'identifiant de cette replique, garde hors de l'etat sauvegardable.

    Une empreinte qui ne correspond plus fait battre une identite neuve : les
    parts deja ecrites restent a la machine qui les a gagnees, les suivantes
    vont a la nouvelle. Comme les parts s'additionnent, se re-cler pour rien ne
    coute qu'une part de plus ; ne pas se re-cler quand il le fallait coute des
    doots.
    """
    empreinte = _empreinte(dossier)
    connue = _connues.get(empreinte)
    if connue:
        return connue

    note = _fiche(dossier)
    if (isinstance(note.get("id"), str) and note["id"]
            and note.get("empreinte") == empreinte):
        _connues[empreinte] = note["id"]
        return note["id"]

    neuve = uuid.uuid4().hex[:12]
    note.update({"id": neuve, "empreinte": empreinte})
    _ecrire_fiche(dossier, note)
    _connues[empreinte] = neuve
    return neuve


def reglage(dossier: Path) -> dict:
    """Ou et avec quelle cle ce poste publie."""
    valeur = _fiche(dossier).get("sync")
    return valeur if isinstance(valeur, dict) else {}


def poser_reglage(dossier: Path, valeur: dict | None) -> None:
    note = _fiche(dossier)
    note.setdefault("id", identite(dossier))
    note.setdefault("empreinte", _empreinte(dossier))
    if valeur is None:
        note.pop("sync", None)
    else:
        note["sync"] = valeur
    _ecrire_fiche(dossier, note)


def _cles_quittees(fiche: dict) -> list:
    """Les cles dont l'objet attend encore d'etre retire, sans doublon.

    `cle_precedente` est le nom que portait la marque quand elle n'en tenait
    qu'une seule ; une fiche ecrite par cette version-la est reprise telle
    quelle plutot que d'abandonner l'objet qu'elle designe.
    """
    brutes = fiche.get("cles_quittees")
    brutes = list(brutes) if isinstance(brutes, list) else []
    heritee = fiche.get("cle_precedente")
    if isinstance(heritee, str) and heritee:
        brutes.append(heritee)

    vues, propres = set(), []
    for texte in brutes:
        if isinstance(texte, str) and texte and texte not in vues:
            vues.add(texte)
            propres.append(texte)
    return propres


def _poser_quittees(fiche: dict, quittees: list) -> dict:
    """Range la liste dans la fiche, ou l'en retire si elle est vide."""
    fiche = dict(fiche)
    fiche.pop("cle_precedente", None)
    if quittees:
        fiche["cles_quittees"] = quittees
    else:
        fiche.pop("cles_quittees", None)
    return fiche


def poser_cle(dossier: Path, fiche: dict, cle_texte: str) -> dict:
    """Pose une cle neuve et retient toutes celles qu'elle a remplacees.

    Le nom d'un objet se calcule depuis la cle qui l'a ferme : oublier une cle
    avant d'avoir retire son objet le laisserait dans le depot pour toujours,
    illisible et que rien ne remplacera.

    Une liste, et non une seule marque, parce que deux objets peuvent attendre
    a la fois : une rotation dont le retrait a echoue laisse le sien derriere
    elle, et la rotation suivante ajoute le sien. Rejouer la commande qui vient
    d'echouer passe aussi par la, la cle jamais publiee s'ajoutant sans chasser
    celle qui l'a precedee.
    """
    quittees = _cles_quittees(fiche)
    ancienne = fiche.get("cle", "")
    if ancienne and ancienne != cle_texte:
        quittees.append(ancienne)
    # Revenir sur ses pas rend la cle courante : son objet ne se retire plus.
    quittees = [texte for texte in quittees if texte != cle_texte]

    fiche = _poser_quittees(fiche, quittees)
    fiche["cle"] = cle_texte
    poser_reglage(dossier, fiche)
    return fiche


def part_exportable(etat: dict, avec_contagion: bool = False) -> dict:
    """Ce qui voyage d'une machine a l'autre.

    Les compteurs de pitie restent : ils decrivent le rythme de ce poste, pas
    ce qui y a ete accompli.
    """
    part = {
        "machine": succes.machine(etat),
        "stats": etat.get("stats", {}),
        "succes": etat.get("succes", {}),
    }
    classement = duel.export(etat)
    if classement:
        part["duel"] = classement
    signal = etat.get("contagion_sortante")
    if avec_contagion and contagion.valide(signal):
        part["contagion"] = signal
    return part


@dataclass(frozen=True)
class Lecture:
    """Le sort d'un objet rencontre : fusionne, ou ecarte et pourquoi."""

    nom: str
    machine: str = ""
    refus: str = ""
    debloques: tuple = ()

    @property
    def fusionnee(self) -> bool:
        return not self.refus


def lire_objets(etat: dict, depot, cle: bytes, objets) -> list[Lecture]:
    """Fait entrer les parts lisibles, et dit ce qu'il est advenu de chacune.

    Rendre le sort de chaque objet plutot que l'imprimer laisse l'appelant
    choisir : la commande en fait des lignes, le cycle du daemon les compte.
    """
    ici = coffre.nom_objet(cle, succes.machine(etat))
    lectures = []
    for objet in objets:
        if objet.nom == ici:
            continue
        try:
            scelle = depot.reprendre(objet)
            if scelle is None:
                continue
            distant = json.loads(coffre.ouvrir(cle, scelle))
        except coffre.CoffreError as exc:
            lectures.append(Lecture(objet.nom, refus=str(exc)))
            continue
        except Exception as exc:
            lectures.append(Lecture(objet.nom, refus=f"illisible, {exc}"))
            continue
        if not isinstance(distant, dict):
            lectures.append(Lecture(objet.nom, refus="ce n'est pas un etat doot"))
            continue
        try:
            nouveaux = succes.fusionner(etat, distant)
        except ValueError as exc:
            lectures.append(Lecture(objet.nom, refus=str(exc)))
            continue
        duel.merge(etat, distant)
        contagion.recevoir(etat, distant.get("contagion"))
        lectures.append(Lecture(objet.nom, machine=str(distant.get("machine")),
                                debloques=tuple(nouveaux)))
    return lectures


def fichiers_de(sources) -> list[Path]:
    """Les fichiers a lire pour un transfert a la main ; un dossier apporte ses .json."""
    fichiers = []
    for source in sources:
        chemin = Path(source).expanduser()
        if chemin.is_dir():
            fichiers.extend(sorted(chemin.glob("*.json")))
        else:
            fichiers.append(chemin)
    return fichiers


def lire_parts(etat: dict, fichiers) -> list[Lecture]:
    """La meme chose que `lire_objets`, sur des fichiers clairs.

    C'est le chemin a la main, `--export` et `--merge` : une cle USB, un
    courriel, un dossier qu'on trimballe. Rien n'y est chiffre puisque la
    personne manipule le fichier elle-meme, la ou le partage automatique
    traverse un stockage qu'elle ne controle pas forcement.
    """
    ici = succes.machine(etat)
    lectures = []
    for chemin in fichiers:
        try:
            distant = json.loads(chemin.read_text(encoding="utf-8"))
        except Exception as exc:
            lectures.append(Lecture(chemin.name, refus=f"illisible, {exc}"))
            continue
        if not isinstance(distant, dict):
            lectures.append(Lecture(chemin.name, refus="ce n'est pas un etat doot"))
            continue
        if distant.get("machine") == ici:
            lectures.append(Lecture(chemin.name, refus="c'est cette machine, ignore"))
            continue
        try:
            nouveaux = succes.fusionner(etat, distant)
        except ValueError as exc:
            lectures.append(Lecture(chemin.name, refus=str(exc)))
            continue
        duel.merge(etat, distant)
        lectures.append(Lecture(chemin.name, machine=str(distant.get("machine")),
                                debloques=tuple(nouveaux)))
    return lectures


def ecrire_part(etat: dict, cible: Path) -> Path:
    """Depose la part en clair ; un dossier recoit doot-<machine>.json."""
    part = part_exportable(etat)
    chemin = cible / f"doot-{part['machine']}.json" if cible.is_dir() else cible
    transport.ecrire_atomiquement(
        chemin, (json.dumps(part, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    return chemin


def publier(etat: dict, depot, cle: bytes) -> str:
    """Depose la part de ce poste, chiffree, sous un nom opaque."""
    nom = coffre.nom_objet(cle, succes.machine(etat))
    part = part_exportable(etat, avec_contagion=True)
    clair = json.dumps(part, ensure_ascii=False).encode("utf-8")
    depot.deposer(nom, coffre.fermer(cle, clair))
    return nom


def solder_cles_quittees(etat: dict, dossier: Path, fiche: dict, depot) -> None:
    """Retire les objets des cles quittees, maintenant que la neuve est publiee.

    Apres `publier` et seulement apres : le depot ne doit a aucun instant se
    retrouver sans objet de cette machine. Une cle n'est rayee que si son
    retrait a abouti, faute de quoi le cycle suivant la reessaie ; un retrait
    qui echoue ne condamne pas les autres et ne fait pas echouer le tour, la
    part ayant deja ete publiee.
    """
    quittees = _cles_quittees(fiche)
    if not quittees:
        return

    restantes = []
    for texte in quittees:
        try:
            cle = coffre.depuis_texte(texte)
        except coffre.CoffreError:
            continue   # marque illisible : elle ne designera jamais d'objet
        try:
            depot.effacer(coffre.nom_objet(cle, succes.machine(etat)))
        except Exception:
            restantes.append(texte)
    poser_reglage(dossier, _poser_quittees(fiche, restantes))


def cycle(etat: dict, dossier: Path) -> list:
    """Prendre ce que les autres ont publie, fusionner, republier.

    Ne leve jamais : un depot injoignable, un disque plein ou un objet a moitie
    ecrit laissent la progression locale intacte et l'ennui dans `sync_note`.
    Un doot ne doit pas dependre de la synchronisation. Ce qui a ete fusionne
    est retenu avant de publier, pour qu'une panne d'ecriture ne fasse pas
    perdre les succes que la lecture venait de debloquer.
    """
    fiche = reglage(dossier)
    if not fiche or not fiche.get("cle"):
        return []

    note = {"quand": datetime.now().isoformat(timespec="seconds")}
    nouveaux = []
    try:
        cle = coffre.depuis_texte(fiche["cle"])
        depot = transport.ouvrir(fiche)
        note["depot"] = depot.decrire()
        lectures = lire_objets(etat, depot, cle, depot.lister())
        note["pairs"] = sum(1 for lecture in lectures if lecture.fusionnee)
        note["ecartes"] = [lecture.refus for lecture in lectures if lecture.refus]
        nouveaux = [item for lecture in lectures for item in lecture.debloques]
        publier(etat, depot, cle)
        solder_cles_quittees(etat, dossier, fiche, depot)
    except Exception as exc:
        note["erreur"] = str(exc)
    etat["sync_note"] = note
    return nouveaux
