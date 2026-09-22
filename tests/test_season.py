"""La fenetre saisonniere : du 1er septembre au 31 octobre inclus.

C'est la regle centrale du projet, celle qu'on ne peut pas verifier a l'oeil
puisqu'elle depend de la date du jour. Les bornes sont donc figees ici.
"""

from __future__ import annotations

import unittest
from datetime import datetime

from doot import season


class Bornes(unittest.TestCase):
    """Les limites exactes de la saison."""

    def test_veille_de_l_ouverture(self):
        self.assertFalse(season.in_season(datetime(2026, 8, 31, 23, 59, 59)))

    def test_premiere_seconde(self):
        self.assertTrue(season.in_season(datetime(2026, 9, 1, 0, 0, 0)))

    def test_pleine_saison(self):
        self.assertTrue(season.in_season(datetime(2026, 9, 6, 12, 0)))
        self.assertTrue(season.in_season(datetime(2026, 9, 30, 23, 59)))
        self.assertTrue(season.in_season(datetime(2026, 10, 1, 0, 0)))

    def test_derniere_seconde(self):
        self.assertTrue(season.in_season(datetime(2026, 10, 31, 23, 59, 59)))

    def test_lendemain_de_la_fermeture(self):
        self.assertFalse(season.in_season(datetime(2026, 11, 1, 0, 0, 0)))

    def test_hors_saison(self):
        for when in (
            datetime(2027, 1, 15, 9, 0),
            datetime(2027, 3, 1, 0, 0),
            datetime(2027, 6, 30, 18, 0),
            datetime(2027, 8, 15, 12, 0),
        ):
            self.assertFalse(season.in_season(when), when)

    def test_annee_bissextile(self):
        """Le 29 fevrier ne doit pas perturber le calcul."""
        self.assertFalse(season.in_season(datetime(2028, 2, 29, 12, 0)))
        self.assertTrue(season.in_season(datetime(2028, 9, 1, 0, 0)))


class ProchaineOuverture(unittest.TestCase):
    """`next_season_start` sert au sommeil du daemon hors saison."""

    def test_avant_l_ouverture_c_est_cette_annee(self):
        found = season.next_season_start(datetime(2027, 3, 15))
        self.assertEqual((found.year, found.month, found.day), (2027, 9, 1))

    def test_apres_la_fermeture_c_est_l_an_prochain(self):
        found = season.next_season_start(datetime(2026, 11, 15))
        self.assertEqual((found.year, found.month, found.day), (2027, 9, 1))

    def test_pendant_la_saison_c_est_l_an_prochain(self):
        found = season.next_season_start(datetime(2026, 9, 6))
        self.assertEqual((found.year, found.month, found.day), (2027, 9, 1))

    def test_delai_toujours_positif(self):
        for when in (
            datetime(2026, 9, 6),
            datetime(2026, 11, 1),
            datetime(2027, 8, 31, 23, 59),
        ):
            self.assertGreater(season.seconds_until_next_season(when), 0, when)

    def test_fin_de_saison_exclusive(self):
        """`season_end` est le 1er novembre a 00:00, borne exclusive."""
        end = season.season_end(2026)
        self.assertEqual((end.year, end.month, end.day), (2026, 11, 1))
        self.assertFalse(season.in_season(end))


class Description(unittest.TestCase):
    """Le texte affiche par `doot --status`."""

    def test_en_saison(self):
        self.assertIn("ouverte", season.describe(datetime(2026, 9, 6)))

    def test_hors_saison_annonce_la_date(self):
        text = season.describe(datetime(2026, 12, 25))
        self.assertIn("hors saison", text)
        self.assertIn("01/09/2027", text)


class CalendrierGraphique(unittest.TestCase):
    def test_hors_saison_compte_les_jours_calendaires(self):
        text = season.countdown(datetime(2027, 8, 31, 23, 59))
        self.assertIn("J-1", text)
        self.assertIn("01/09/2027", text)

    def test_pendant_la_saison_le_cartouche_disparait(self):
        self.assertIsNone(season.countdown(datetime(2027, 10, 12, 9, 0)))


if __name__ == "__main__":
    unittest.main()
