"""Le registre lit l'etat sans jamais l'ecrire, ni inventer ce qu'il n'y a pas."""

from __future__ import annotations

import copy
import unittest
from datetime import date, datetime

from doot import cli, gui, registre, season, succes


def etat_type() -> dict:
    """Une flotte de deux machines, deux saisons, et une date abimee."""

    return {
        "machine": "aaaa11112222",
        "stats": {
            "doots": {"aaaa11112222": 40, "bbbb33334444": 60},
            "declenchements": {"aaaa11112222": 30},
            "melodies": {"bbbb33334444": 7},
            "evenements": {},
            "melodies_perso": {"aaaa11112222": 2},
            "plus_grande_salve": 5,
            "voix_max": 2,
            "formations": ["canon", "wave"],
            "bords_imposes": ["left"],
            "jours_actifs": [
                "2026-09-01", "2026-09-30", "2026-10-31",
                "2025-10-02", "pas-une-date",
            ],
        },
        "succes": {"premier_doot": "2026-09-01T21:00:00"},
    }


class LecteursDeLEtat(unittest.TestCase):
    """`parts` et `collection` ouvrent le detail sans toucher au fichier."""

    def test_les_parts_rendent_le_detail_par_machine(self):
        etat = etat_type()
        self.assertEqual(
            succes.parts(etat, "doots"),
            {"aaaa11112222": 40, "bbbb33334444": 60},
        )

    def test_un_total_d_avant_les_parts_revient_a_sa_machine(self):
        etat = {"machine": "aaaa11112222", "stats": {"doots": 12}}
        self.assertEqual(succes.parts(etat, "doots"), {"aaaa11112222": 12})

    def test_un_total_sans_machine_connue_reste_attribue(self):
        self.assertEqual(succes.parts({"stats": {"doots": 3}}, "doots"),
                         {"inconnue": 3})

    def test_lire_les_parts_n_ecrit_rien(self):
        """Un affichage ne doit pas ranger le fichier en le regardant."""

        etat = {"machine": "aaaa11112222", "stats": {"doots": 12}}
        avant = copy.deepcopy(etat)
        succes.parts(etat, "doots")
        succes.collection(etat, "formations")
        self.assertEqual(etat["stats"]["doots"], avant["stats"]["doots"])

    def test_lire_un_etat_sans_statistiques_ne_lui_en_pose_pas(self):
        """Le cas que la premiere version du test ne pouvait pas voir.

        Il partait d'un etat portant deja ses statistiques, la seule forme ou
        `_stats` n'ecrit rien. Sur `{}` les quatre lecteurs y posaient
        `{"stats": {}}`, donc regarder le registre modifiait le fichier.
        """
        lectures = (
            ("total", lambda etat: succes.total(etat, "doots")),
            ("parts", lambda etat: succes.parts(etat, "doots")),
            ("collection", lambda etat: succes.collection(etat, "formations")),
            ("progression",
             lambda etat: succes.progression(etat, succes.CATALOGUE[0])),
            ("resume", registre.resume),
            ("postes", registre.postes),
            ("totaux", registre.totaux),
            ("saison", lambda etat: registre.saison(etat, 2026)),
        )
        for nom, lire in lectures:
            with self.subTest(lecture=nom):
                etat = {}
                lire(etat)
                self.assertEqual(etat, {})

    def test_un_etat_neuf_se_lit_sans_rien_inventer(self):
        bilan = registre.resume({})
        self.assertEqual(bilan.doots, 0)
        self.assertEqual(bilan.jours, 0)
        self.assertEqual(registre.postes({}), [])
        self.assertEqual(registre.saisons({}), [])

    def test_les_parts_vides_ne_font_pas_de_ligne(self):
        etat = {"stats": {"doots": {"aaaa": 0, "bbbb": 4}}}
        self.assertEqual(succes.parts(etat, "doots"), {"bbbb": 4})

    def test_une_statistique_absente_ne_rend_aucune_part(self):
        self.assertEqual(succes.parts({}, "doots"), {})


class DerniereSaison(unittest.TestCase):
    def test_en_pleine_saison_c_est_l_annee_courante(self):
        self.assertEqual(season.last_season_year(datetime(2026, 10, 12)), 2026)

    def test_apres_la_fermeture_c_est_encore_l_annee_courante(self):
        self.assertEqual(season.last_season_year(datetime(2026, 12, 25)), 2026)

    def test_avant_l_ouverture_c_est_la_saison_precedente(self):
        """En janvier, l'annee courante designerait une crypte jamais ouverte."""

        self.assertEqual(season.last_season_year(datetime(2026, 1, 3)), 2025)
        self.assertEqual(season.last_season_year(datetime(2026, 8, 31)), 2025)

    def test_le_premier_jour_bascule(self):
        self.assertEqual(season.last_season_year(datetime(2026, 9, 1)), 2026)


class Grille(unittest.TestCase):
    def test_la_grille_est_rectangulaire(self):
        colonnes = registre.semaines(date(2026, 9, 1), date(2026, 10, 31))
        self.assertTrue(colonnes)
        for colonne in colonnes:
            self.assertEqual(len(colonne), registre.SEMAINE)

    def test_le_premier_jour_tombe_sur_son_jour_de_semaine(self):
        """Le 1er septembre 2026 est un mardi : la case du lundi reste vide."""

        colonnes = registre.semaines(date(2026, 9, 1), date(2026, 10, 31))
        self.assertIsNone(colonnes[0][0])
        self.assertEqual(colonnes[0][1], date(2026, 9, 1))

    def test_les_cases_hors_saison_sont_vides_des_deux_cotes(self):
        colonnes = registre.semaines(date(2026, 9, 1), date(2026, 10, 31))
        jours = [jour for colonne in colonnes for jour in colonne if jour]
        self.assertEqual(min(jours), date(2026, 9, 1))
        self.assertEqual(max(jours), date(2026, 10, 31))
        self.assertEqual(len(jours), 61)

    def test_la_saison_se_suit_sans_trou_ni_doublon(self):
        colonnes = registre.semaines(date(2026, 9, 1), date(2026, 10, 31))
        jours = [jour for colonne in colonnes for jour in colonne if jour]
        self.assertEqual(jours, sorted(jours))
        self.assertEqual(len(set(jours)), len(jours))

    def test_une_saison_a_l_envers_ne_rend_rien(self):
        self.assertEqual(registre.semaines(date(2026, 10, 31), date(2026, 9, 1)), [])

    def test_une_saison_d_un_seul_jour_tient_dans_une_colonne(self):
        colonnes = registre.semaines(date(2026, 9, 1), date(2026, 9, 1))
        self.assertEqual(len(colonnes), 1)
        self.assertEqual([jour for jour in colonnes[0] if jour], [date(2026, 9, 1)])


class Saison(unittest.TestCase):
    def test_seuls_les_soirs_de_la_saison_demandee_sont_retenus(self):
        saison = registre.saison(etat_type(), 2026)
        self.assertEqual(
            sorted(saison.actifs),
            [date(2026, 9, 1), date(2026, 9, 30), date(2026, 10, 31)],
        )

    def test_la_duree_couvre_septembre_et_octobre(self):
        self.assertEqual(registre.saison(etat_type(), 2026).duree, 61)

    def test_une_date_illisible_est_ecartee(self):
        """Un state.json retouche a la main ne doit pas casser l'affichage."""

        jours = registre.jours_actifs(etat_type())
        self.assertNotIn(None, jours)
        self.assertEqual(len(jours), 4)

    def test_les_saisons_vues_vont_de_la_plus_recente_a_la_plus_ancienne(self):
        self.assertEqual(registre.saisons(etat_type()), [2026, 2025])

    def test_un_soir_hors_saison_n_inscrit_pas_sa_saison(self):
        """`--ignore-season` fait dooter un 3 janvier, que nulle crypte n'a ouvert.

        Retenir son annee annoncait une saison a zero soir sur soixante et un :
        la liste des saisons disait le contraire de la grille.
        """
        etat = {"stats": {"jours_actifs": [
            "2025-01-03", "2025-08-31", "2025-11-01", "2026-09-15",
        ]}}
        self.assertEqual(registre.saisons(etat), [2026])
        self.assertEqual(registre.saison(etat, 2025).actifs, frozenset())

    def test_les_bornes_de_la_saison_comptent_pour_la_liste(self):
        etat = {"stats": {"jours_actifs": ["2025-09-01", "2024-10-31"]}}
        self.assertEqual(registre.saisons(etat), [2025, 2024])


class Postes(unittest.TestCase):
    def test_la_machine_la_plus_bruyante_passe_devant(self):
        postes = registre.postes(etat_type())
        self.assertEqual([poste.machine for poste in postes],
                         ["bbbb33334444", "aaaa11112222"])
        self.assertEqual(postes[0].doots, 60)
        self.assertEqual(postes[0].melodies, 7)

    def test_une_machine_absente_d_une_colonne_y_compte_zero(self):
        postes = registre.postes(etat_type())
        self.assertEqual(postes[0].declenchements, 0)
        self.assertEqual(postes[1].melodies, 0)

    def test_une_flotte_vide_ne_fait_aucune_ligne(self):
        self.assertEqual(registre.postes({}), [])


class Totaux(unittest.TestCase):
    def test_les_compteurs_a_zero_ne_sont_pas_montres(self):
        libelles = [libelle for libelle, _ in registre.totaux(etat_type())]
        self.assertIn("Doots", libelles)
        self.assertNotIn("Rickrolls", libelles)

    def test_le_total_reunit_les_parts_de_toutes_les_machines(self):
        valeurs = dict(registre.totaux(etat_type()))
        self.assertEqual(valeurs["Doots"], 100)

    def test_le_resume_compte_les_soirs_lisibles(self):
        bilan = registre.resume(etat_type())
        self.assertEqual(bilan.jours, 4)
        self.assertEqual(bilan.doots, 100)
        self.assertEqual(bilan.succes_total, len(succes.CATALOGUE))


class GrilleTexte(unittest.TestCase):
    def lignes(self):
        return cli.grille_texte(registre.saison(etat_type(), 2026))

    def test_une_ligne_d_entete_puis_une_par_jour_de_semaine(self):
        self.assertEqual(len(self.lignes()), registre.SEMAINE + 1)

    def test_les_deux_mois_sont_etiquetes(self):
        """Ecrit en entier, "septembre" mordait sur la colonne d'octobre et
        l'etiquette disparaissait sans bruit : la grille perdait son calendrier."""

        entete = self.lignes()[0]
        self.assertIn("sep", entete)
        self.assertIn("oct", entete)
        self.assertLess(entete.index("sep"), entete.index("oct"))

    def test_un_soir_actif_se_distingue_d_un_soir_vide(self):
        corps = "".join(self.lignes()[1:])
        self.assertEqual(corps.count(cli.CASE_ACTIVE), 3)
        self.assertEqual(corps.count(cli.CASE_VIDE), 61 - 3)


class OngletsDeLEtat(unittest.TestCase):
    """Une action qui promet d'ouvrir un onglet doit l'ouvrir."""

    def test_le_registre_a_son_onglet_comme_les_succes(self):
        self.assertEqual(
            set(gui.ONGLETS_ETAT),
            {"achievements", "stats", "history", "challenge", "grand-retour",
             "carnet", "carnet-secrets", "after-dawn", "crew-missions", "eighth-door"},
        )

    def test_chaque_action_nomme_une_methode_et_un_onglet_qui_existent(self):
        """La table se lit sans Tkinter ; c'est ce qui la rend verifiable ici."""

        for cle, (rafraichir, onglet) in gui.ONGLETS_ETAT.items():
            with self.subTest(action=cle):
                self.assertTrue(callable(getattr(gui.DootApp, rafraichir, None)))
                self.assertIn(cle, {command.key for command in gui.COMMANDS})
                self.assertTrue(onglet.endswith("_tab"))


class VueGraphique(unittest.TestCase):
    def test_la_vue_se_compose_sans_tkinter(self):
        vue = gui.registre_vue(etat_type(), 2026)
        self.assertEqual(vue.saison.annee, 2026)
        self.assertEqual(vue.ici, "aaaa11112222")
        self.assertEqual(vue.resume.doots, 100)

    def test_la_saison_montree_ne_figure_pas_dans_les_precedentes(self):
        vue = gui.registre_vue(etat_type(), 2026)
        self.assertEqual(vue.precedentes, [(2025, 1, 61)])

    def test_sans_annee_la_vue_prend_la_derniere_saison(self):
        vue = gui.registre_vue(etat_type())
        self.assertEqual(vue.saison.annee, season.last_season_year())


if __name__ == "__main__":
    unittest.main()
