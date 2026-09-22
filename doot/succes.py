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

from . import duel


Progression = Callable[[dict], int]
BADGES_DIR = Path(__file__).resolve().parent / "assets" / "success"

# Comment se fusionne chaque statistique quand deux machines se rejoignent. Un
# total s'additionne, un maximum se compare, un ensemble s'unit. Le fichier ne
# portait pas cette distinction, et rien ne dit d'un entier lequel il est :
# sans cette table, une fusion fausse les chiffres sans rien signaler.
TOTAUX = (
    "doots", "declenchements", "canons", "tours_imposes", "evenements",
    "melodies", "melodies_perso", "rickrolls", "defis_termines",
    "packs_importes", "rencontres_creees", "parades_flotte", "boss_vaincus",
    "campagnes_terminees", "invasions_terminees", "replays_exportes", "takes_live",
    "expeditions_terminees", "familiers_evolues", "contrats_termines", "samples_dj",
    "chasses_codes", "new_game_plus", "sessions_coop", "nuits_infinies",
    "batiments_construits", "builds_reliques", "missions_faction", "nemesis_vaincues",
    "enquetes_resolues", "courses_fantomes", "partitions_adaptatives", "films_realises",
    "packs_atelier_valides", "boss_miroirs", "langues_dechiffrees",
    "catacombes_maitrisees", "boucles_brisees", "talents_familiers",
    "entrees_bestiaire", "reliques_forgees", "meteos_observees",
    "rituels_accomplis", "sieges_repousses", "verdicts_rendus",
    "heritages_choisis", "campagnes_validees", "musees_exportes",
    "sept_sceaux_ouverts", "trains_arrives", "equipages_complets",
    "affaires_rail_resolues", "artefacts_restaures", "contrefacons_detectees",
    "propheties_accomplies", "gazettes_exportees", "duels_musicaux_gagnes",
    "maisons_honorees", "mods_valides", "replays_train_exportes",
    "treizieme_cloche_sonnee", "gare_zero_visitee",
    "collections_archeologiques", "reseaux_ferroviaires_maitrises",
)
MAXIMA = ("plus_grande_salve", "voix_max", "serie_defis")
ENSEMBLES = (
    "formations", "bords_imposes", "evenements_vus", "melodies_fournies",
    "jours_actifs", "profils_actifs", "enigmes_resolues", "saisons_archivees",
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
    secret: bool = False
    indices: tuple[str, ...] = ()


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


def _contient(cle: str, valeur: str) -> Progression:
    return lambda stats: 1 if valeur in _liste(stats, cle) else 0


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
           "Assister a trois evenements rares differents.",
           40, 3, _nombre_dans_liste("evenements_vus")),
    Succes("profil_actif", "Costume sur mesure",
           "Activer un profil persistant.",
           10, 1, _nombre_dans_liste("profils_actifs")),
    Succes("defi_du_jour", "Contrat d'outre-tombe",
           "Terminer un premier defi quotidien.",
           20, 1, _valeur("defis_termines")),
    Succes("serie_macabre", "Sept jours sous terre",
           "Terminer un defi quotidien sept jours de suite.",
           50, 7, _valeur("serie_defis")),
    Succes("metteur_en_scene", "Metteur en os",
           "Creer une rencontre personnalisee.",
           25, 1, _valeur("rencontres_creees")),
    Succes("couturier", "Haute couture funeraire",
           "Importer un pack de contenu doot.",
           20, 1, _valeur("packs_importes")),
    Succes("chef_de_flotte", "Chef de flotte",
           "Lancer une parade synchronisee entre les machines.",
           30, 1, _valeur("parades_flotte")),
    Succes("chasseur_boss", "Chasseur de titan",
           "Vaincre le boss saisonnier.", 50, 1, _valeur("boss_vaincus")),
    Succes("conteur_crypte", "Conteur de la crypte",
           "Terminer la campagne narrative.", 40, 1, _valeur("campagnes_terminees")),
    Succes("maitre_invasion", "Maitre de l'invasion",
           "Survivre a une invasion complete.", 35, 1, _valeur("invasions_terminees")),
    Succes("archiviste_saisons", "Archiviste des saisons",
           "Ouvrir le musee apres avoir archive une saison.", 25, 1,
           _nombre_dans_liste("saisons_archivees")),
    Succes("chef_orchestre_live", "Chef d'orchestre live",
           "Exporter un replay ou enregistrer un take live.", 25, 1,
           lambda stats: _compteur(stats, "replays_exportes") + _compteur(stats, "takes_live")),
    Succes("douzieme_coup", "Le douzieme coup",
           "Faire resonner le doot quand le cadran recommence.", 35, 1,
           _contient("enigmes_resolues", "douzieme_coup"), True,
           ("Le cadran doit perdre ses deux aiguilles.", "Cherche le debut d'une nuit.")),
    Succes("miroir_funebre", "Le miroir funebre",
           "Faire combattre deux reflets qui remontent le temps.", 35, 1,
           _contient("enigmes_resolues", "miroir_funebre"), True,
           ("Deux adversaires se ressemblent.", "Le duel doit remonter le temps.")),
    Succes("clef_ossuaire", "La clef d'ossuaire",
           "Trouver le chemin secret de la campagne.", 40, 1,
           _contient("enigmes_resolues", "clef_ossuaire"), True,
           ("La crypte se souvient de trois verbes.", "Ecoute, joue, puis franchis.")),
    Succes("huitieme_voix", "La huitieme voix",
           "Completer le choeur impossible.", 40, 1,
           _contient("enigmes_resolues", "huitieme_voix"), True,
           ("Un choeur garde une place vide.", "Compte les pattes de l'araignee.")),
    Succes("explorateur_astral", "Explorateur astral",
           "Terminer une expedition de sept salles.", 35, 1,
           _valeur("expeditions_terminees")),
    Succes("ami_spectral", "Ami spectral",
           "Faire evoluer un familier au niveau 2.", 20, 1,
           _valeur("familiers_evolues")),
    Succes("pacte_flotte", "Le pacte de la flotte",
           "Achever un contrat communautaire.", 30, 1,
           _valeur("contrats_termines")),
    Succes("doot_dj", "Doot DJ",
           "Decouper un sample dans le studio DJ.", 20, 1,
           _valeur("samples_dj")),
    Succes("cryptographe", "Cryptographe de l'ombre",
           "Retrouver les cinq codes caches dans la crypte.", 50, 1,
           _valeur("chasses_codes"), True,
           ("Cinq mots dorment entre les systemes.", "Ecoute les indices de la chasse.")),
    Succes("retour_crypte", "La crypte se souvient",
           "Commencer une Nouvelle Partie +.", 30, 1,
           _valeur("new_game_plus")),
    Succes("duo_osseux", "Duo osseux",
           "Atteindre quatre accords en coop locale.", 25, 1,
           _valeur("sessions_coop")),
    Succes("nuit_sans_fin", "L'aube impossible",
           "Traverser les six actes de la Nuit infinie.", 50, 1,
           _valeur("nuits_infinies")),
    Succes("architecte_osseux", "Architecte osseux",
           "Elever le premier batiment de la Cite des Os.", 30, 1,
           _valeur("batiments_construits")),
    Succes("maitre_reliquaire", "Maitre du reliquaire",
           "Equiper une relique dans un build roguelite.", 25, 1,
           _valeur("builds_reliques")),
    Succes("ambassadeur_crypte", "Ambassadeur de la crypte",
           "Accomplir une mission pour une faction.", 25, 1,
           _valeur("missions_faction")),
    Succes("rancune_eternelle", "Rancune eternelle",
           "Vaincre sa Nemesis persistante.", 50, 1,
           _valeur("nemesis_vaincues")),
    Succes("enqueteur_paranormal", "Enqueteur paranormal",
           "Resoudre une affaire surnaturelle.", 30, 1,
           _valeur("enquetes_resolues")),
    Succes("ombre_chronometree", "Ombre chronometree",
           "Battre un fantome dans une course asynchrone.", 25, 1,
           _valeur("courses_fantomes")),
    Succes("maestro_adaptatif", "Maestro adaptatif",
           "Porter la partition reactive au-dela de la demi-intensite.", 25, 1,
           _valeur("partitions_adaptatives")),
    Succes("realisateur_outre_tombe", "Realisateur d'outre-tombe",
           "Creer un film ou un portrait au studio.", 25, 1,
           _valeur("films_realises")),
    Succes("gardien_atelier", "Gardien de l'atelier",
           "Valider un pack communautaire fiable.", 20, 1,
           _valeur("packs_atelier_valides")),
    Succes("miroir_noir", "Le miroir noir",
           "Faire naitre le boss qui imite ton style.", 35, 1,
           _valeur("boss_miroirs")),
    Succes("langue_des_morts", "La langue des morts",
           "Dechiffrer les cinq glyphes de la crypte.", 50, 1,
           _valeur("langues_dechiffrees"), True,
           ("Cinq signes parlent sans bouche.", "Leur sens voyage entre les nuits.")),
    Succes("cartographe_abime", "Cartographe de l'abime",
           "Sortir vivant des catacombes ramifiees.", 40, 1,
           _valeur("catacombes_maitrisees")),
    Succes("horloger_maudit", "L'horloger maudit",
           "Briser la nuit qui recommence.", 40, 1,
           _valeur("boucles_brisees"), True,
           ("Le son vient avant le temps.", "Puis l'immobilite, puis un souffle.")),
    Succes("compagnon_ascendant", "Compagnon ascendant",
           "Eveiller un talent avance de familier.", 25, 1,
           _valeur("talents_familiers")),
    Succes("naturaliste_outre_tombe", "Naturaliste d'outre-tombe",
           "Consigner trois creatures dans le bestiaire.", 30, 1,
           _valeur("entrees_bestiaire")),
    Succes("forgeron_maudit", "Forgeron maudit",
           "Fusionner deux matieres dans la forge necromantique.", 30, 1,
           _valeur("reliques_forgees")),
    Succes("meteorologue_occulte", "Meteorologue occulte",
           "Observer une meteo paranormale.", 20, 1,
           _valeur("meteos_observees")),
    Succes("ritualiste_collectif", "Ritualiste collectif",
           "Achever un rituel asynchrone a cinq fragments.", 35, 1,
           _valeur("rituels_accomplis")),
    Succes("assiegeur_nemesis", "Briseur de siege",
           "Repousser une invasion de la Nemesis.", 45, 1,
           _valeur("sieges_repousses")),
    Succes("juge_des_morts", "Juge des morts",
           "Rendre un verdict au tribunal spectral.", 30, 1,
           _valeur("verdicts_rendus")),
    Succes("memoire_eternelle", "Memoire eternelle",
           "Choisir un heritage de Nouvelle Partie +.", 30, 1,
           _valeur("heritages_choisis")),
    Succes("dramaturge_interdit", "Dramaturge interdit",
           "Valider une campagne communautaire coherente.", 25, 1,
           _valeur("campagnes_validees")),
    Succes("conservateur_ombres", "Conservateur des ombres",
           "Ouvrir son musee personnel.", 25, 1,
           _valeur("musees_exportes")),
    Succes("septieme_sceau", "Le septieme sceau",
           "Ouvrir les sept sceaux caches entre les systemes.", 75, 1,
           _valeur("sept_sceaux_ouverts"), True,
           ("Chaque sceau vit dans un systeme different.",
            "Le chemin, l'heure, l'aile, la gueule, la forge, la balance et l'echo.")),
    Succes("conducteur_outre_tombe", "Conducteur d'outre-tombe",
           "Atteindre un terminus du Dernier Train.", 35, 1,
           _valeur("trains_arrives")),
    Succes("equipage_eternel", "Equipage eternel",
           "Recruter quatre membres de l'equipage spectral.", 30, 1,
           _valeur("equipages_complets")),
    Succes("limier_du_rail", "Limier du rail",
           "Resoudre une affaire a bord du train fantome.", 30, 1,
           _valeur("affaires_rail_resolues")),
    Succes("archeologue_interdit", "Archeologue interdit",
           "Restaurer un artefact exhume des lignes mortes.", 30, 1,
           _valeur("artefacts_restaures")),
    Succes("commissaire_reliques", "Commissaire des reliques",
           "Demasquer une contrefacon au marche noir.", 25, 1,
           _valeur("contrefacons_detectees")),
    Succes("oracle_cendres", "Oracle des cendres",
           "Accomplir une prophetie hebdomadaire.", 30, 1,
           _valeur("propheties_accomplies")),
    Succes("gazettier_crypte", "Gazettier de la crypte",
           "Imprimer la Gazette de la Crypte.", 20, 1,
           _valeur("gazettes_exportees")),
    Succes("virtuose_funebre", "Virtuose funebre",
           "Remporter un combat musical du train.", 40, 1,
           _valeur("duels_musicaux_gagnes")),
    Succes("heritier_funeraire", "Heritier funeraire",
           "Gagner trois faveurs d'une maison rivale.", 30, 1,
           _valeur("maisons_honorees")),
    Succes("moddeur_maudit", "Moddeur maudit",
           "Forger et valider une capsule de mod sure.", 25, 1,
           _valeur("mods_valides")),
    Succes("cineaste_spectral", "Cineaste spectral",
           "Monter le replay cinematographique d'un voyage.", 25, 1,
           _valeur("replays_train_exportes")),
    Succes("treizieme_cloche", "La Treizieme Cloche",
           "Faire sonner le coup que le cadran refuse de compter.", 75, 1,
           _valeur("treizieme_cloche_sonnee"), True,
           ("Six echos voyagent dans le Dernier Train.",
            "Le rail, le choeur, la preuve, la relique, l'accord et le serment.")),
    Succes("gare_inexistante", "La gare inexistante",
           "Monter dans le train de la Gare Zero.", 50, 1,
           _valeur("gare_zero_visitee"), True,
           ("Une gare manque a toutes les cartes.",
            "Echoue a trois propheties de trois manieres differentes.")),
    Succes("collectionneur_fragments", "Collectionneur de fragments",
           "Exhumer les neuf fragments archeologiques.", 25, 1,
           _valeur("collections_archeologiques")),
    Succes("roi_dernier_train", "Roi du Dernier Train",
           "Atteindre le terminus des trois lignes fantomes.", 60, 1,
           _valeur("reseaux_ferroviaires_maitrises")),
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
            duel.record(
                etat, quantite, special=isinstance(rencontre, str) and bool(rencontre),
                now=maintenant,
            )
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

    elif evenement == "defi":
        _ajoute(stats, "defis_termines", origine)
        serie = details.get("serie", 0)
        if isinstance(serie, int) and not isinstance(serie, bool):
            stats["serie_defis"] = max(_compteur(stats, "serie_defis"), serie)

    elif evenement == "rencontre_perso":
        _ajoute(stats, "rencontres_creees", origine)

    elif evenement == "pack":
        _ajoute(stats, "packs_importes", origine)

    elif evenement == "parade_flotte":
        _ajoute(stats, "parades_flotte", origine)

    elif evenement == "boss":
        if details.get("defeated") is True:
            _ajoute(stats, "boss_vaincus", origine)

    elif evenement == "campagne":
        if details.get("completed") is True:
            _ajoute(stats, "campagnes_terminees", origine)

    elif evenement == "invasion":
        _ajoute(stats, "invasions_terminees", origine)

    elif evenement == "replay":
        _ajoute(stats, "replays_exportes", origine)

    elif evenement == "studio_live":
        _ajoute(stats, "takes_live", origine)

    elif evenement == "musee":
        year = details.get("year")
        if isinstance(year, int) and not isinstance(year, bool):
            _ajoute_unique(stats, "saisons_archivees", str(year))

    elif evenement == "enigme":
        nom = details.get("nom")
        if isinstance(nom, str):
            _ajoute_unique(stats, "enigmes_resolues", nom)

    elif evenement == "expedition":
        if details.get("completed") is True:
            _ajoute(stats, "expeditions_terminees", origine)

    elif evenement == "familiar":
        if entier(details.get("level")) >= 2:
            _ajoute(stats, "familiers_evolues", origine)

    elif evenement == "contract":
        if details.get("completed") is True:
            _ajoute(stats, "contrats_termines", origine)

    elif evenement == "dj":
        if details.get("imported") is True:
            _ajoute(stats, "samples_dj", origine)

    elif evenement == "code_hunt":
        if details.get("completed") is True:
            _ajoute(stats, "chasses_codes", origine)

    elif evenement == "new_game_plus":
        _ajoute(stats, "new_game_plus", origine)

    elif evenement == "coop":
        if entier(details.get("score")) >= 4:
            _ajoute(stats, "sessions_coop", origine)

    elif evenement == "nuit_infinie":
        if details.get("completed") is True:
            _ajoute(stats, "nuits_infinies", origine)

    elif evenement == "city":
        if entier(details.get("level")) >= 1:
            _ajoute(stats, "batiments_construits", origine)

    elif evenement == "relic_build":
        if entier(details.get("equipped")) >= 1:
            _ajoute(stats, "builds_reliques", origine)

    elif evenement == "faction":
        if entier(details.get("reputation")) >= 1:
            _ajoute(stats, "missions_faction", origine)

    elif evenement == "nemesis":
        if details.get("defeated") is True:
            _ajoute(stats, "nemesis_vaincues", origine)

    elif evenement == "investigation":
        if details.get("solved") is True:
            _ajoute(stats, "enquetes_resolues", origine)

    elif evenement == "ghost_race":
        if details.get("won") is True:
            _ajoute(stats, "courses_fantomes", origine)

    elif evenement == "adaptive_score":
        intensity = details.get("intensity", 0)
        if isinstance(intensity, (int, float)) and not isinstance(intensity, bool) and intensity >= .5:
            _ajoute(stats, "partitions_adaptatives", origine)

    elif evenement == "director":
        if details.get("exported") is True:
            _ajoute(stats, "films_realises", origine)

    elif evenement == "workshop":
        if details.get("valid") is True:
            _ajoute(stats, "packs_atelier_valides", origine)

    elif evenement == "mirror_boss":
        if details.get("generated") is True:
            _ajoute(stats, "boss_miroirs", origine)

    elif evenement == "glyphs":
        if details.get("completed") is True:
            _ajoute(stats, "langues_dechiffrees", origine)

    elif evenement == "catacomb_victory":
        if details.get("won") is True:
            _ajoute(stats, "catacombes_maitrisees", origine)

    elif evenement == "time_loop":
        if details.get("broken") is True:
            _ajoute(stats, "boucles_brisees", origine)

    elif evenement == "familiar_skill":
        if details.get("unlocked") is True:
            _ajoute(stats, "talents_familiers", origine)

    elif evenement == "bestiary":
        if entier(details.get("found")) >= 3:
            _ajoute(stats, "entrees_bestiaire", origine)

    elif evenement == "necroforge":
        if details.get("crafted") is True:
            _ajoute(stats, "reliques_forgees", origine)

    elif evenement == "paranormal_weather":
        if details.get("witnessed") is True:
            _ajoute(stats, "meteos_observees", origine)

    elif evenement == "collective_ritual":
        if details.get("completed") is True:
            _ajoute(stats, "rituels_accomplis", origine)

    elif evenement == "nemesis_invasion":
        if details.get("repelled") is True:
            _ajoute(stats, "sieges_repousses", origine)

    elif evenement == "tribunal":
        if details.get("verdict") is True:
            _ajoute(stats, "verdicts_rendus", origine)

    elif evenement == "legacy":
        if details.get("chosen") is True:
            _ajoute(stats, "heritages_choisis", origine)

    elif evenement == "campaign_validate":
        if details.get("valid") is True:
            _ajoute(stats, "campagnes_validees", origine)

    elif evenement == "personal_museum":
        if details.get("exported") is True:
            _ajoute(stats, "musees_exportes", origine)

    elif evenement == "seven_seals":
        if details.get("completed") is True:
            _ajoute(stats, "sept_sceaux_ouverts", origine)

    elif evenement == "ghost_train":
        if details.get("arrived") is True and details.get("fresh") is True:
            _ajoute(stats, "trains_arrives", origine)
        if entier(details.get("routes")) >= 3:
            _ajoute(stats, "reseaux_ferroviaires_maitrises", origine)

    elif evenement == "spectral_crew":
        if details.get("complete") is True:
            _ajoute(stats, "equipages_complets", origine)

    elif evenement == "rail_case":
        if details.get("solved") is True:
            _ajoute(stats, "affaires_rail_resolues", origine)

    elif evenement == "archaeology":
        if details.get("restored") is True:
            _ajoute(stats, "artefacts_restaures", origine)
        if entier(details.get("fragments")) >= 9:
            _ajoute(stats, "collections_archeologiques", origine)

    elif evenement == "black_market":
        if details.get("detected") is True:
            _ajoute(stats, "contrefacons_detectees", origine)

    elif evenement == "prophecy":
        if details.get("completed") is True:
            _ajoute(stats, "propheties_accomplies", origine)

    elif evenement == "crypt_gazette":
        if details.get("exported") is True:
            _ajoute(stats, "gazettes_exportees", origine)

    elif evenement == "musical_battle":
        if details.get("won") is True:
            _ajoute(stats, "duels_musicaux_gagnes", origine)

    elif evenement == "funeral_house":
        if entier(details.get("reputation")) >= 3:
            _ajoute(stats, "maisons_honorees", origine)

    elif evenement == "mod_capsule":
        if details.get("valid") is True:
            _ajoute(stats, "mods_valides", origine)

    elif evenement == "train_replay":
        if details.get("exported") is True:
            _ajoute(stats, "replays_train_exportes", origine)

    elif evenement == "thirteenth_bell":
        if details.get("rung") is True:
            _ajoute(stats, "treizieme_cloche_sonnee", origine)

    elif evenement == "lost_station":
        if details.get("visited") is True:
            _ajoute(stats, "gare_zero_visitee", origine)

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


def visible(etat: dict, definition: Succes) -> tuple[str, str]:
    """Titre et texte a montrer sans vendre la solution d'un succes secret."""

    if not definition.secret or definition.identifiant in debloques(etat):
        return definition.titre, definition.description
    current, _target = progression(etat, definition)
    if current:
        return definition.titre, definition.indices[-1] if definition.indices else "Indice revele."
    return "Succes secret", definition.indices[0] if definition.indices else "Une enigme reste a resoudre."
