"""Progression locale, robuste et deterministe des succes."""

from __future__ import annotations

import copy
import unittest
from datetime import datetime, timedelta

from doot import png, succes


class Enregistrement(unittest.TestCase):
    def setUp(self):
        self.etat = {}
        self.maintenant = datetime(2026, 9, 17, 20, 30)

    def ids(self, nouveaux):
        return {item.identifiant for item in nouveaux}

    def test_premier_doot_debloque_le_premier_succes(self):
        nouveaux = succes.enregistrer(
            self.etat, "doots", self.maintenant, quantite=1,
            formation="random", spin=False, bord=None,
        )
        self.assertIn("premier_doot", self.ids(nouveaux))
        self.assertEqual(succes.total(self.etat, "doots"), 1)
        self.assertEqual(succes.score(self.etat), 5)

    def test_un_succes_n_est_annonce_qu_une_fois(self):
        premier = succes.enregistrer(self.etat, "doots", self.maintenant, quantite=1)
        second = succes.enregistrer(self.etat, "doots", self.maintenant, quantite=1)
        self.assertIn("premier_doot", self.ids(premier))
        self.assertNotIn("premier_doot", self.ids(second))

    def test_salve_canon(self):
        nouveaux = succes.enregistrer(
            self.etat, "doots", self.maintenant, quantite=4, formation="canon"
        )
        self.assertIn("trio_infernal", self.ids(nouveaux))
        self.assertIn("canon_a_os", self.ids(nouveaux))
        self.assertEqual(self.etat["stats"]["plus_grande_salve"], 4)

    def test_les_quatre_formations_debloquent_le_choregraphe(self):
        for formation in ("canon", "wave", "rain", "vortex"):
            nouveaux = succes.enregistrer(
                self.etat, "doots", self.maintenant,
                quantite=4, formation=formation,
            )
        self.assertIn("choregraphe", self.ids(nouveaux))

    def test_les_evenements_rares_se_collectionnent(self):
        for rencontre in ("parade", "pluie", "vortex"):
            nouveaux = succes.enregistrer(
                self.etat, "doots", self.maintenant,
                quantite=5, rencontre=rencontre,
            )
        ids = self.ids(nouveaux)
        self.assertIn("collection_evenements", ids)
        self.assertIn("premier_evenement", succes.debloques(self.etat))

    def test_activer_un_profil_a_son_succes(self):
        nouveaux = succes.enregistrer(
            self.etat, "profil", self.maintenant, nom="chaos"
        )
        self.assertIn("profil_actif", self.ids(nouveaux))

    def test_les_quatre_bords_s_accumulent(self):
        for bord in ("left", "right", "top", "bottom"):
            nouveaux = succes.enregistrer(
                self.etat, "doots", self.maintenant, quantite=1, bord=bord
            )
        self.assertIn("quatre_coins", self.ids(nouveaux))

    def test_melodie_fournie_polyphonique_et_rickroll(self):
        nouveaux = succes.enregistrer(
            self.etat,
            "melodie",
            self.maintenant,
            nom="rickroll",
            fournie=True,
            voix=2,
        )
        ids = self.ids(nouveaux)
        self.assertIn("maestro", ids)
        self.assertIn("orchestre", ids)
        self.assertIn("rickroll", ids)
        self.assertNotIn("melodie_perso", ids)

    def test_cinq_melodies_fournies_differentes(self):
        for index in range(5):
            nouveaux = succes.enregistrer(
                self.etat, "melodie", self.maintenant,
                nom=f"morceau-{index}", fournie=True, voix=1,
            )
        self.assertIn("jukebox_macabre", self.ids(nouveaux))

    def test_melodie_perso(self):
        nouveaux = succes.enregistrer(
            self.etat, "melodie", self.maintenant,
            nom="ma-composition", fournie=False, voix=1,
        )
        self.assertIn("melodie_perso", self.ids(nouveaux))

    def test_sept_jours_distincts(self):
        for index in range(7):
            nouveaux = succes.enregistrer(
                self.etat, "doots", self.maintenant + timedelta(days=index), quantite=1
            )
        self.assertIn("sept_jours", self.ids(nouveaux))

    def test_etat_abime_est_repare(self):
        etat = {"stats": [], "succes": "beaucoup"}
        succes.enregistrer(etat, "doots", self.maintenant, quantite=1)
        self.assertIsInstance(etat["stats"], dict)
        self.assertIsInstance(etat["succes"], dict)

    def test_valeurs_invalides_ne_fabriquent_pas_de_score(self):
        etat = {"stats": {"doots": True, "melodies": -10}}
        nouveaux = succes.enregistrer(etat, "doots", self.maintenant, quantite="plein")
        self.assertEqual(nouveaux, [])
        self.assertEqual(succes.score(etat), 0)


class Badges(unittest.TestCase):
    def test_chaque_succes_a_un_png_fourni(self):
        for definition in succes.CATALOGUE:
            with self.subTest(succes=definition.identifiant):
                chemin = succes.badge(definition)
                self.assertIsNotNone(chemin)
                self.assertEqual(png.size(chemin), (256, 256))

    def test_succes_inconnu_n_augmente_ni_le_total_ni_le_score(self):
        etat = {"succes": {"invente": "demain"}}
        self.assertEqual(succes.debloques(etat), {})
        self.assertEqual(succes.score(etat), 0)


class EspecesDeStatistiques(unittest.TestCase):
    """Chaque statistique ecrite doit dire comment elle se fusionne.

    Le garde-fou vaut pour les statistiques a venir : une clef ajoutee a
    `enregistrer` sans etre classee ferait une fusion muette et fausse.
    """

    def toutes_les_statistiques(self) -> set:
        """Les clefs que `enregistrer` produit vraiment, tous evenements confondus."""
        etat = {}
        succes.enregistrer(etat, "doots", quantite=4, formation="canon",
                           spin=True, bord="left", rencontre="lune")
        succes.enregistrer(etat, "doots", quantite=4, formation="wave")
        succes.enregistrer(etat, "melodie", nom="rickroll", voix=2, fournie=True)
        succes.enregistrer(etat, "melodie", nom="maison", voix=1, fournie=False)
        succes.enregistrer(etat, "profil", nom="nuit")
        succes.enregistrer(etat, "defi", serie=7)
        succes.enregistrer(etat, "rencontre_perso")
        succes.enregistrer(etat, "pack")
        succes.enregistrer(etat, "parade_flotte")
        succes.enregistrer(etat, "boss", defeated=True)
        succes.enregistrer(etat, "campagne", completed=True)
        succes.enregistrer(etat, "invasion")
        succes.enregistrer(etat, "replay")
        succes.enregistrer(etat, "studio_live")
        succes.enregistrer(etat, "musee", year=2025)
        succes.enregistrer(etat, "enigme", nom="douzieme_coup")
        succes.enregistrer(etat, "expedition", completed=True)
        succes.enregistrer(etat, "familiar", level=2)
        succes.enregistrer(etat, "contract", completed=True)
        succes.enregistrer(etat, "dj", imported=True)
        succes.enregistrer(etat, "code_hunt", completed=True)
        succes.enregistrer(etat, "new_game_plus", level=1)
        succes.enregistrer(etat, "coop", score=4)
        succes.enregistrer(etat, "nuit_infinie", completed=True)
        succes.enregistrer(etat, "city", level=1)
        succes.enregistrer(etat, "relic_build", equipped=1)
        succes.enregistrer(etat, "faction", reputation=2)
        succes.enregistrer(etat, "nemesis", defeated=True)
        succes.enregistrer(etat, "investigation", solved=True)
        succes.enregistrer(etat, "ghost_race", won=True)
        succes.enregistrer(etat, "adaptive_score", intensity=.7)
        succes.enregistrer(etat, "director", exported=True)
        succes.enregistrer(etat, "workshop", valid=True)
        succes.enregistrer(etat, "mirror_boss", generated=True)
        succes.enregistrer(etat, "glyphs", completed=True)
        succes.enregistrer(etat, "catacomb_victory", won=True)
        succes.enregistrer(etat, "time_loop", broken=True)
        succes.enregistrer(etat, "familiar_skill", unlocked=True)
        succes.enregistrer(etat, "bestiary", found=3)
        succes.enregistrer(etat, "necroforge", crafted=True)
        succes.enregistrer(etat, "paranormal_weather", witnessed=True)
        succes.enregistrer(etat, "collective_ritual", completed=True)
        succes.enregistrer(etat, "nemesis_invasion", repelled=True)
        succes.enregistrer(etat, "tribunal", verdict=True)
        succes.enregistrer(etat, "legacy", chosen=True)
        succes.enregistrer(etat, "campaign_validate", valid=True)
        succes.enregistrer(etat, "personal_museum", exported=True)
        succes.enregistrer(etat, "seven_seals", completed=True)
        succes.enregistrer(etat, "ghost_train", arrived=True, fresh=True, routes=3)
        succes.enregistrer(etat, "spectral_crew", complete=True)
        succes.enregistrer(etat, "rail_case", solved=True)
        succes.enregistrer(etat, "archaeology", restored=True, fragments=9)
        succes.enregistrer(etat, "black_market", detected=True)
        succes.enregistrer(etat, "prophecy", completed=True)
        succes.enregistrer(etat, "crypt_gazette", exported=True)
        succes.enregistrer(etat, "musical_battle", won=True)
        succes.enregistrer(etat, "funeral_house", reputation=3)
        succes.enregistrer(etat, "mod_capsule", valid=True)
        succes.enregistrer(etat, "train_replay", exported=True)
        succes.enregistrer(etat, "thirteenth_bell", rung=True)
        succes.enregistrer(etat, "lost_station", visited=True)
        succes.enregistrer(etat, "grand_retour", completed=True, loyal=True, endings=3)
        succes.enregistrer(etat, "grand_retour_secret", solved=True)
        return set(etat["stats"])

    def test_la_table_couvre_ce_qui_est_ecrit(self):
        classees = set(succes.TOTAUX) | set(succes.MAXIMA) | set(succes.ENSEMBLES)
        self.assertEqual(self.toutes_les_statistiques() - classees, set(),
                         "statistique ecrite mais non classee")

    def test_la_table_ne_declare_rien_qui_n_existe_pas(self):
        classees = set(succes.TOTAUX) | set(succes.MAXIMA) | set(succes.ENSEMBLES)
        self.assertEqual(classees - self.toutes_les_statistiques(), set(),
                         "statistique classee mais jamais ecrite")

    def test_aucune_statistique_n_est_de_deux_especes(self):
        especes = (succes.TOTAUX, succes.MAXIMA, succes.ENSEMBLES)
        for gauche in range(len(especes)):
            for droite in range(gauche + 1, len(especes)):
                self.assertEqual(set(especes[gauche]) & set(especes[droite]), set())

    def test_chaque_espece_a_la_forme_que_sa_fusion_attend(self):
        """Un total est range en parts par machine, sans quoi la fusion double."""
        etat = {}
        succes.enregistrer(etat, "doots", quantite=4, formation="canon",
                           spin=True, bord="left", rencontre="lune")
        succes.enregistrer(etat, "melodie", nom="rickroll", voix=2, fournie=True)
        stats = etat["stats"]
        for cle in succes.TOTAUX:
            if cle in stats:
                self.assertIsInstance(stats[cle], dict, cle)
                for part in stats[cle].values():
                    self.assertIsInstance(part, int, cle)
        for cle in succes.MAXIMA:
            if cle in stats:
                self.assertIsInstance(stats[cle], int, cle)
        for cle in succes.ENSEMBLES:
            if cle in stats:
                self.assertIsInstance(stats[cle], list, cle)


class Fusion(unittest.TestCase):
    """Deux machines qui se rejoignent, sans serveur ni horloge partagee."""

    def poste(self, nom, doots=0, **details):
        etat = {"machine": nom}
        for _ in range(doots):
            succes.enregistrer(etat, "doots", datetime(2026, 9, 17, 12, 0),
                               quantite=1, **details)
        return etat

    def test_les_totaux_s_additionnent(self):
        local = self.poste("portable", 60)
        succes.fusionner(local, self.poste("fixe", 60))
        self.assertEqual(succes.total(local, "doots"), 120)

    def test_refaire_la_fusion_ne_change_rien(self):
        """C'est ce que les parts par machine achetent, et tout le reste en depend."""
        local = self.poste("portable", 60)
        distant = self.poste("fixe", 60)
        for _ in range(3):
            succes.fusionner(local, distant)
        self.assertEqual(succes.total(local, "doots"), 120)

    def test_le_sens_de_la_fusion_ne_change_rien(self):
        portable = self.poste("portable", 60, bord="left")
        fixe = self.poste("fixe", 40, bord="right")

        ici = copy.deepcopy(portable)
        succes.fusionner(ici, fixe)
        la_bas = copy.deepcopy(fixe)
        succes.fusionner(la_bas, portable)

        self.assertEqual(succes.total(ici, "doots"), succes.total(la_bas, "doots"))
        self.assertEqual(ici["stats"]["bords_imposes"], la_bas["stats"]["bords_imposes"])

    def test_les_maxima_se_comparent(self):
        local = {"machine": "portable"}
        succes.enregistrer(local, "doots", quantite=3)
        distant = {"machine": "fixe"}
        succes.enregistrer(distant, "doots", quantite=7)
        succes.fusionner(local, distant)
        self.assertEqual(local["stats"]["plus_grande_salve"], 7)

    def test_les_ensembles_s_unissent(self):
        local = self.poste("portable", 1, bord="left")
        succes.fusionner(local, self.poste("fixe", 1, bord="right"))
        self.assertEqual(local["stats"]["bords_imposes"], ["left", "right"])

    def test_la_reunion_debloque_ce_qu_aucune_n_avait(self):
        local = self.poste("portable", 60)
        nouveaux = succes.fusionner(local, self.poste("fixe", 60))
        self.assertIn("cent_doots", {item.identifiant for item in nouveaux})

    def test_la_date_de_deblocage_la_plus_ancienne_gagne(self):
        local = {"machine": "portable", "succes": {"premier_doot": "2026-09-17T12:00:00"}}
        distant = {"machine": "fixe", "succes": {"premier_doot": "2026-09-01T08:00:00"}}
        succes.fusionner(local, distant)
        self.assertEqual(local["succes"]["premier_doot"], "2026-09-01T08:00:00")

    def test_un_entier_d_avant_les_parts_se_fusionne_sans_doubler(self):
        """Les etats deja sur les disques n'ont pas de parts : ils appartiennent
        a la machine qui les a accumules."""
        local = self.poste("portable", 60)
        vieux = {"machine": "ancien", "stats": {"doots": 40}}
        succes.fusionner(local, vieux)
        succes.fusionner(local, vieux)
        self.assertEqual(succes.total(local, "doots"), 100)

    def test_un_etat_sans_machine_est_refuse(self):
        """Sans identifiant stable, chaque fusion lui en inventerait un neuf et
        rajouterait ses totaux."""
        with self.assertRaises(ValueError):
            succes.fusionner(self.poste("portable", 1), {"stats": {"doots": 5}})

    def test_machine_ne_fait_que_lire(self):
        """L'identite appartient au poste, pas au module : `partage` la pose."""
        self.assertEqual(succes.machine({}), "")
        self.assertEqual(succes.machine({"machine": 42}), "")
        self.assertEqual(succes.machine({"machine": "abc"}), "abc")


if __name__ == "__main__":
    unittest.main()
