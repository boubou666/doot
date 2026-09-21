"""Signaux ephemeres du Doot contagieux.

Le signal voyage dans l'objet chiffre deja publie par une machine. Il porte un
identifiant, sa source, son heure de depart, et dit ce qui a ete joue la-bas.
Les signaux trop anciens sont ignores et chaque poste garde une petite liste de
ceux qu'il a deja vus, afin qu'une synchronisation repetee ne rejoue jamais le
meme doot.

La charge est facultative des deux cotes. Un poste plus ancien n'ecrit pas les
deux clefs et en recoit un doot ordinaire ; un poste plus ancien qui en recoit
les ignore et joue le doot. Les deux sens se degradent sans se casser, ce qui
compte pour une flotte qu'on ne met pas a jour d'un coup.

Le nom que porte un signal vient d'une autre machine et servira a chercher une
melodie : il est reduit a un jeton ici, et cherche par egalite la-bas. Jamais
comme un chemin.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone


TTL_SECONDS = 5 * 60
MAX_SEEN = 128
MAX_PENDING = 8

GENRES = ("doot", "melodie", "evenement")

# Un nom de melodie ou de rencontre, et rien d'autre : ni separateur, ni point
# de tete, ni longueur de quoi remplir le depot.
_JETON = re.compile(r"^[a-z0-9][a-z0-9._-]{0,47}$")


def nom_sur(nom) -> str:
    """Le nom porte par un signal, vide s'il ne peut pas etre un nom de melodie.

    `melodie.find` prend son argument pour un chemin des que le nom finit en
    `.rtttl` et qu'un fichier repond. Laisser passer ce qu'une autre machine
    ecrit lui ferait lire un fichier choisi ailleurs, hors du dossier des
    melodies. Le filtre est donc ici, au plus pres de l'entree.
    """
    if not isinstance(nom, str):
        return ""
    reduit = nom.casefold()
    if ".." in reduit or not _JETON.match(reduit):
        return ""
    return reduit


def charge(signal) -> tuple:
    """Ce qu'un signal demande de jouer : le genre et le nom.

    Une charge qu'on ne sait pas lire vaut un doot ordinaire, elle n'annule pas
    le signal : un nom abime ne doit pas valoir une apparition en moins.
    """
    if not isinstance(signal, dict):
        return ("doot", "")
    genre = signal.get("genre")
    if genre not in GENRES or genre == "doot":
        return ("doot", "")
    nom = nom_sur(signal.get("nom"))
    return (genre, nom) if nom else ("doot", "")


def _utc(now: datetime | None = None) -> datetime:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        return now.replace(tzinfo=timezone.utc)
    return now.astimezone(timezone.utc)


def creer(source: str, now: datetime | None = None, token: str | None = None,
          genre: str = "doot", nom: str = "") -> dict:
    """Un signal, et ce qu'il porte quand ce n'est pas un doot ordinaire.

    Les deux clefs ne sont ecrites que si elles disent quelque chose : un doot
    reste exactement l'objet d'avant la charge, donc une machine restee en
    arriere le lit sans savoir qu'un format a bouge.

    Le genre et le nom s'ajoutent derriere `now` et `token`, que des appelants
    passent deja par position.
    """
    maintenant = _utc(now)
    token = token or uuid.uuid4().hex[:12]
    signal = {
        "id": f"{source}:{token}",
        "source": source,
        "emis": maintenant.isoformat(timespec="seconds"),
    }
    nom = nom_sur(nom)
    if genre in GENRES and genre != "doot" and nom:
        signal["genre"] = genre
        signal["nom"] = nom
    return signal


def valide(signal, now: datetime | None = None) -> bool:
    if not isinstance(signal, dict):
        return False
    identifiant = signal.get("id")
    source = signal.get("source")
    emis = signal.get("emis")
    if not all(isinstance(item, str) and item for item in (identifiant, source, emis)):
        return False
    if len(identifiant) > 96 or len(source) > 64:
        return False
    try:
        instant = datetime.fromisoformat(emis.replace("Z", "+00:00"))
        age = (_utc(now) - _utc(instant)).total_seconds()
    except (TypeError, ValueError, OverflowError):
        return False
    return -30 <= age <= TTL_SECONDS


def recevoir(etat: dict, signal, now: datetime | None = None) -> bool:
    """Met un signal neuf en attente. Faux signifie invalide, local ou deja vu."""

    if not valide(signal, now):
        return False
    if signal["source"] == etat.get("machine"):
        return False

    vues = etat.get("contagions_vues", [])
    vues = [item for item in vues if isinstance(item, str)] if isinstance(vues, list) else []
    if signal["id"] in vues:
        return False

    attentes = etat.get("contagions_en_attente", [])
    attentes = [item for item in attentes if isinstance(item, dict)] \
        if isinstance(attentes, list) else []
    attentes.append(dict(signal))
    etat["contagions_en_attente"] = attentes[-MAX_PENDING:]
    etat["contagions_vues"] = (vues + [signal["id"]])[-MAX_SEEN:]
    return True


def vider(etat: dict, now: datetime | None = None) -> list[dict]:
    attentes = etat.pop("contagions_en_attente", [])
    if not isinstance(attentes, list):
        return []
    return [item for item in attentes if valide(item, now)]
