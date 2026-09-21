"""Succes locaux et statistiques de progression de doot.

Le module est volontairement pur : il transforme le dictionnaire de ``state.json``
sans connaitre les chemins ni la ligne de commande. Le client local reste ainsi la
source de verite, et une eventuelle synchronisation en ligne pourra reutiliser les
memes identifiants de succes sans changer le format du fichier.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable


Progression = Callable[[dict], int]
BADGES_DIR = Path(__file__).resolve().parent / "assets" / "success"

# Comment se fusionne chaque statistique quand deux machines se rejoignent. Un
# total s'additionne, un maximum se compare, un ensemble s'unit. Le fichier ne
# portait pas cette distinction, et rien ne dit d'un entier lequel il est :
# sans cette table, une fusion fausse les chiffres sans rien signaler.
TOTAUX = (
    "doots", "declenchements", "canons", "tours_imposes", "evenements",
    "melodies", "melodies_perso", "rickrolls",
)
MAXIMA = ("plus_grande_salve", "voix_max")
ENSEMBLES = (
    "formations", "bords_imposes", "evenements_vus", "melodies_fournies",
    "jours_actifs", "profils_actifs",
)


@dataclass(frozen=True)
class Succes:
    """Un succes, son score et la statistique qui le fait progresser."""

    identifiant: str
    titre: str
    description: str
    points: int
    objectif: int
    progression: Progression


def entier(valeur) -> int:
    """Un entier positif, quoi qu'on lui donne : le reste repart de zero."""
    if isinstance(valeur, bool) or not isinstance(valeur, int):
        return 0
    return max(0, valeur)


def machine(etat: dict) -> str:
    """L'identifiant de la replique. C'est `partage` qui le pose dans l'etat."""
    valeur = etat.get("machine")
    return valeur if isinstance(valeur, str) else ""


def _normaliser(etat: dict) -> dict:
    """Range les totaux en parts, une fois, pour que les lecteurs l'ignorent.

    Un entier d'avant les parts revient a la machine qui l'a accumule. Faire ce
    rangement ici evite de trainer l'origine dans chaque lecture.
    """
    stats = _stats(etat)
    origine = machine(etat) or "inconnue"
    for cle in TOTAUX:
        valeur = stats.get(cle)
        if valeur is not None and not isinstance(valeur, dict):
            valeur = entier(valeur)
            stats[cle] = {origine: valeur} if valeur else {}
    return stats


def _parts(stats: dict, cle: str) -> dict:
    """Les parts d'un total, par machine."""
    valeur = stats.get(cle)
    if not isinstance(valeur, dict):
        return {}
    return {str(nom): entier(part) for nom, part in valeur.items()}


def _compteur(stats: dict, cle: str) -> int:
    valeur = stats.get(cle, 0)
    if isinstance(valeur, dict):
        return sum(entier(part) for part in valeur.values())
    return entier(valeur)


def _liste(stats: dict, cle: str) -> list[str]:
    valeur = stats.get(cle, [])
    if not isinstance(valeur, list):
        return []
    return sorted({item for item in valeur if isinstance(item, str)})


def _nombre_dans_liste(cle: str) -> Progression:
    return lambda stats: len(_liste(stats, cle))


def _valeur(cle: str) -> Progression:
    return lambda stats: _compteur(stats, cle)


CATALOGUE = (
    Succes("premier_doot", "Premier souffle", "Faire apparaitre son premier squelette.",
           5, 1, _valeur("doots")),
    Succes("dix_doots", "Dix sur dix", "Faire apparaitre 10 squelettes.",
           10, 10, _valeur("doots")),
    Succes("cent_doots", "Cent-os", "Faire apparaitre 100 squelettes.",
           25, 100, _valeur("doots")),
    Succes("mille_doots", "Doot mille", "Faire apparaitre 1 000 squelettes.",
           100, 1000, _valeur("doots")),
    Succes("trio_infernal", "Trio infernal", "Jouer une salve d'au moins 3 doots.",
           15, 3, _valeur("plus_grande_salve")),
    Succes("canon_a_os", "Canon a os", "Jouer une formation canon d'au moins 4 doots.",
           20, 1, _valeur("canons")),
    Succes("choregraphe", "Choregraphe des cryptes",
           "Jouer canon, wave, rain et vortex avec au moins 4 doots.",
           35, 4, _nombre_dans_liste("formations")),
    Succes("ca_tourne", "Ca tourne", "Imposer un tour complet avec --spin.",
           10, 1, _valeur("tours_imposes")),
    Succes("quatre_coins", "Aux quatre coins",
           "Imposer chacun des quatre bords avec --side.",
           25, 4, _nombre_dans_liste("bords_imposes")),
    Succes("maestro", "Maestro macabre", "Jouer une premiere melodie.",
           10, 1, _valeur("melodies")),
    Succes("jukebox_macabre", "Jukebox macabre",
           "Jouer 5 melodies fournies differentes.",
           50, 5, _nombre_dans_liste("melodies_fournies")),
    Succes("orchestre", "Orchestre d'outre-tombe",
           "Jouer une melodie avec au moins 2 voix.",
           20, 2, _valeur("voix_max")),
    Succes("rickroll", "Never gonna give you up", "Jouer rickroll en doots. Evidemment.",
           15, 1, _valeur("rickrolls")),
    Succes("melodie_perso", "Luthier d'outre-tombe",
           "Jouer une melodie RTTTL personnelle.",
           30, 1, _valeur("melodies_perso")),
    Succes("sept_jours", "Sept nuits de doot",
           "Jouer au moins une fois pendant 7 jours differents.",
           40, 7, _nombre_dans_liste("jours_actifs")),
    Succes("premier_evenement", "Quelque chose cloche",
           "Assister a un premier evenement rare.",
           15, 1, _valeur("evenements")),
    Succes("collection_evenements", "Cabinet de curiosites",
           "Assister aux trois evenements rares differents.",
           40, 3, _nombre_dans_liste("evenements_vus")),
    Succes("profil_actif", "Costume sur mesure",
           "Activer un profil persistant.",
           10, 1, _nombre_dans_liste("profils_actifs")),
)


def _stats(etat: dict) -> dict:
    """Les statistiques, creees si elles manquent. Pour ecrire, donc."""
    stats = etat.get("stats")
    if not isinstance(stats, dict):
        stats = {}
        etat["stats"] = stats
    return stats


def _lu(etat: dict) -> dict:
    """Les statistiques telles qu'elles sont, sans poser ce qui manque.

    `_stats` ecrit un dictionnaire vide quand la clef est absente, ce qu'il
    faut pour enregistrer et jamais pour lire. Un lecteur qui passait par lui
    transformait `{}` en `{"stats": {}}` : lire la progression la modifiait,
    sur le fichier meme que le README invite a sauvegarder et a recopier.
    """
    stats = etat.get("stats")
    return stats if isinstance(stats, dict) else {}


def _ajoute(stats: dict, cle: str, origine: str, quantite: int = 1) -> None:
    quantite = max(0, quantite)
    if not quantite:
        return
    parts = _parts(stats, cle)
    parts[origine] = entier(parts.get(origine)) + quantite
    stats[cle] = parts


def _ajoute_unique(stats: dict, cle: str, valeur: str) -> None:
    valeurs = _liste(stats, cle)
    if valeur and valeur not in valeurs:
        valeurs.append(valeur)
    stats[cle] = sorted(valeurs)


def _jour_actif(stats: dict, maintenant: datetime) -> None:
    _ajoute_unique(stats, "jours_actifs", maintenant.date().isoformat())


def enregistrer(etat: dict, evenement: str, maintenant: datetime | None = None,
                **details) -> list[Succes]:
    """Enregistre un evenement reel et renvoie les succes nouvellement debloques."""

    maintenant = maintenant or datetime.now()
    stats = _normaliser(etat)
    origine = machine(etat) or "inconnue"

    if evenement == "doots":
        quantite = details.get("quantite", 0)
        if isinstance(quantite, bool) or not isinstance(quantite, int):
            quantite = 0
        quantite = max(0, quantite)
        if quantite:
            _ajoute(stats, "doots", origine, quantite)
            _ajoute(stats, "declenchements", origine)
            stats["plus_grande_salve"] = max(
                _compteur(stats, "plus_grande_salve"), quantite
            )
            if details.get("formation") == "canon" and quantite >= 4:
                _ajoute(stats, "canons", origine)
            formation = details.get("formation")
            if formation in ("canon", "wave", "rain", "vortex") and quantite >= 4:
                _ajoute_unique(stats, "formations", formation)
            if details.get("spin") is True:
                _ajoute(stats, "tours_imposes", origine)
            bord = details.get("bord")
            if bord in ("left", "right", "top", "bottom"):
                _ajoute_unique(stats, "bords_imposes", bord)
            rencontre = details.get("rencontre")
            if isinstance(rencontre, str) and rencontre:
                _ajoute(stats, "evenements", origine)
                _ajoute_unique(stats, "evenements_vus", rencontre)
            _jour_actif(stats, maintenant)

    elif evenement == "melodie":
        nom = details.get("nom")
        if not isinstance(nom, str):
            nom = ""
        voix = details.get("voix", 1)
        if isinstance(voix, bool) or not isinstance(voix, int):
            voix = 1
        _ajoute(stats, "melodies", origine)
        _ajoute(stats, "declenchements", origine)
        stats["voix_max"] = max(_compteur(stats, "voix_max"), max(1, voix))
        if details.get("fournie") is True:
            _ajoute_unique(stats, "melodies_fournies", nom)
        else:
            _ajoute(stats, "melodies_perso", origine)
        if nom.casefold() == "rickroll":
            _ajoute(stats, "rickrolls", origine)
        _jour_actif(stats, maintenant)

    elif evenement == "apparition":
        # Une rencontre vue sans salve a elle : ce qui l'a portee - une melodie
        # venue d'une autre machine - compte deja ses propres doots, et les
        # recompter ici les ferait tomber deux fois.
        nom = details.get("nom")
        if isinstance(nom, str) and nom:
            _ajoute(stats, "evenements", origine)
            _ajoute_unique(stats, "evenements_vus", nom)
            _jour_actif(stats, maintenant)

    elif evenement == "profil":
        nom = details.get("nom")
        if isinstance(nom, str):
            _ajoute_unique(stats, "profils_actifs", nom)

    return _debloquer(etat, maintenant)


def _debloquer(etat: dict, maintenant: datetime) -> list[Succes]:
    """Les succes que l'etat courant vient d'atteindre."""
    stats = _stats(etat)
    acquis = etat.get("succes")
    if not isinstance(acquis, dict):
        acquis = {}
        etat["succes"] = acquis

    nouveaux = []
    for definition in CATALOGUE:
        if definition.identifiant in acquis:
            continue
        if definition.progression(stats) >= definition.objectif:
            acquis[definition.identifiant] = maintenant.isoformat(timespec="seconds")
            nouveaux.append(definition)
    return nouveaux


def _fondre_parts(ici: dict, la_bas: dict, cle: str) -> dict:
    """Maximum part par part : refaire la fusion ne rajoute rien."""
    parts = dict(_parts(ici, cle))
    for nom, part in _parts(la_bas, cle).items():
        parts[nom] = max(entier(parts.get(nom)), part)
    return parts


def _fondre_maximum(ici: dict, la_bas: dict, cle: str) -> int:
    return max(_compteur(ici, cle), _compteur(la_bas, cle))


def _fondre_union(ici: dict, la_bas: dict, cle: str) -> list:
    return sorted(set(_liste(ici, cle)) | set(_liste(la_bas, cle)))


# La table dit desormais comment chaque statistique se fusionne, et non plus
# seulement de quelle espece elle est : une clef ajoutee apporte sa regle avec
# elle, au lieu de la laisser dans une boucle a part.
FUSION = {
    **{cle: _fondre_parts for cle in TOTAUX},
    **{cle: _fondre_maximum for cle in MAXIMA},
    **{cle: _fondre_union for cle in ENSEMBLES},
}


def _dates_les_plus_anciennes(local: dict, distant: dict) -> None:
    """Un succes garde la date ou il a ete gagne en premier."""
    acquis = local.get("succes")
    if not isinstance(acquis, dict):
        acquis = {}
        local["succes"] = acquis
    autres = distant.get("succes")
    if not isinstance(autres, dict):
        return
    for identifiant, date in autres.items():
        if not isinstance(date, str):
            continue
        ancienne = acquis.get(identifiant)
        if not isinstance(ancienne, str) or date < ancienne:
            acquis[identifiant] = date


def fusionner(local: dict, distant: dict, maintenant: datetime | None = None) -> list[Succes]:
    """Fait entrer l'etat d'une autre machine dans celui-ci.

    Idempotente et commutative : refaire la fusion, ou la faire dans l'autre
    sens, donne le meme etat. C'est ce que les parts par machine achetent, un
    total simple s'additionnerait a chaque passage.

    Renvoie les succes que la reunion des deux debloque, qu'aucune des deux
    machines n'avait forcement atteints seule.
    """
    maintenant = maintenant or datetime.now()
    if not machine(distant):
        raise ValueError("l'etat a fusionner ne dit pas de quelle machine il vient")

    ici = _normaliser(local)
    la_bas = _normaliser(distant)
    for cle, fondre in FUSION.items():
        valeur = fondre(ici, la_bas, cle)
        if valeur:
            ici[cle] = valeur

    _dates_les_plus_anciennes(local, distant)
    return _debloquer(local, maintenant)


def debloques(etat: dict) -> dict:
    valeur = etat.get("succes", {})
    if not isinstance(valeur, dict):
        return {}
    connus = {item.identifiant for item in CATALOGUE}
    return {identifiant: date for identifiant, date in valeur.items()
            if identifiant in connus}


def total(etat: dict, cle: str) -> int:
    """La valeur d'une statistique, parts de toutes les machines reunies.

    Passer par ici plutot que par le dictionnaire : un total est stocke en
    parts, un maximum en entier, et la forme n'a pas a sortir du module.
    """
    return _compteur(_lu(etat), cle)


def parts(etat: dict, cle: str) -> dict:
    """Le detail d'un total, machine par machine, les parts vides retirees.

    Un etat d'avant les parts porte un entier : il revient a la machine qui
    l'a accumule, comme le fait le rangement interne, mais sans rien ecrire.
    Un lecteur n'a pas a normaliser le fichier pour le regarder.
    """
    stats = _lu(etat)
    valeur = stats.get(cle)
    if isinstance(valeur, dict):
        detail = {str(nom): entier(part) for nom, part in valeur.items()}
        return {nom: part for nom, part in detail.items() if part}
    valeur = entier(valeur)
    return {machine(etat) or "inconnue": valeur} if valeur else {}


def collection(etat: dict, cle: str) -> list:
    """Les valeurs d'un ensemble, triees, sans les entrees illisibles."""
    return _liste(_lu(etat), cle)


def score(etat: dict) -> int:
    acquis = debloques(etat)
    return sum(item.points for item in CATALOGUE if item.identifiant in acquis)


def badge(definition: Succes) -> Path | None:
    """Illustration fournie avec le succes, absente seulement si le paquet est incomplet."""

    chemin = BADGES_DIR / f"{definition.identifiant}.png"
    return chemin if chemin.is_file() else None


def progression(etat: dict, definition: Succes) -> tuple[int, int]:
    courant = min(definition.objectif, definition.progression(_lu(etat)))
    return courant, definition.objectif
