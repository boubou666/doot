"""Placement multi-ecrans.

L'enumeration reelle depend de la machine (Win32, xrandr, CoreGraphics) et ne
peut pas etre reproduite en CI. Ce qui est verifie ici, c'est le contrat que
`window.py` utilise : on obtient toujours au moins un ecran, et une fenetre
posee sur un ecran tombe entierement dedans.
"""

from __future__ import annotations

import random
import unittest
from unittest import mock

from doot import screens


class Enumeration(unittest.TestCase):
    """`monitors()` ne doit jamais laisser l'appelant sans ecran."""

    def test_jamais_vide(self):
        found = screens.monitors()
        self.assertGreaterEqual(len(found), 1)

    def test_dimensions_positives(self):
        for monitor in screens.monitors():
            self.assertGreater(monitor.width, 0, monitor)
            self.assertGreater(monitor.height, 0, monitor)

    def test_repli_sur_les_dimensions_fournies(self):
        """Sur une machine sans serveur graphique, on retombe sur le repli."""
        found = screens.monitors(1280, 800)
        self.assertGreaterEqual(len(found), 1)

    def test_description_lisible(self):
        text = screens.describe(screens.monitors())
        self.assertIn("ecran", text)

class SharedBackend(unittest.TestCase):
    """The application adapter preserves Doot's public monitor type."""

    def test_engine_rectangles_are_adapted(self):
        shared = screens._geometry.Monitor(
            -1920, 20, 1920, 1040, primary=True, name="partage"
        )
        with mock.patch.object(
                screens, "enumerate_monitors", return_value=[shared]) as detect:
            found = screens.monitors(1280, 720)

        detect.assert_called_once_with(1280, 720)
        self.assertIsInstance(found[0], screens.Monitor)
        self.assertEqual(
            (found[0].x, found[0].y, found[0].name),
            (-1920, 20, "partage"),
        )

class Selection(unittest.TestCase):
    """La semantique de --screen."""

    def setUp(self):
        self.mons = [
            screens.Monitor(0, 0, 1920, 1040, primary=True, name="gauche"),
            screens.Monitor(1920, 0, 2560, 1400, primary=False, name="droite"),
            screens.Monitor(-1080, -200, 1080, 1920, primary=False, name="portrait"),
        ]

    def test_index_explicite(self):
        for index, monitor in enumerate(self.mons):
            self.assertIs(screens.pick(self.mons, index), monitor)

    def test_index_en_texte(self):
        self.assertIs(screens.pick(self.mons, "1"), self.mons[1])

    def test_principal(self):
        self.assertIs(screens.pick(self.mons, "primary"), self.mons[0])

    def test_index_hors_bornes_est_borne(self):
        """Un index farfelu doit borner, pas planter."""
        self.assertIs(screens.pick(self.mons, 99), self.mons[-1])
        self.assertIs(screens.pick(self.mons, -5), self.mons[0])

    def test_valeur_incomprehensible_tire_au_hasard(self):
        self.assertIn(screens.pick(self.mons, "n'importe quoi"), self.mons)

    def test_hasard_touche_tous_les_ecrans(self):
        seen = {screens.pick(self.mons, None).name for _ in range(400)}
        self.assertEqual(seen, {"gauche", "droite", "portrait"})

    def test_liste_vide_ne_plante_pas(self):
        self.assertIsNotNone(screens.pick([], None))


class Placement(unittest.TestCase):
    """Une fenetre ne doit jamais deborder de l'ecran choisi."""

    def setUp(self):
        self.mons = [
            screens.Monitor(0, 0, 1920, 1040, primary=True, name="gauche"),
            screens.Monitor(1920, 0, 2560, 1400, primary=False, name="droite"),
            screens.Monitor(-1080, -200, 1080, 1920, primary=False, name="portrait"),
        ]

    def assert_inside(self, monitor, x, y, w, h):
        self.assertGreaterEqual(x, monitor.x, monitor)
        self.assertGreaterEqual(y, monitor.y, monitor)
        self.assertLessEqual(x + w, monitor.x + monitor.width, monitor)
        self.assertLessEqual(y + h, monitor.y + monitor.height, monitor)

    def test_aleatoire_reste_dans_l_ecran(self):
        rng = random.Random(1234)
        for monitor in self.mons:
            for _ in range(300):
                x, y = monitor.place(353, 385, center=False, rng=rng)
                self.assert_inside(monitor, x, y, 353, 385)

    def test_centre_reste_dans_l_ecran(self):
        for monitor in self.mons:
            x, y = monitor.place(353, 385, center=True, rng=random)
            self.assert_inside(monitor, x, y, 353, 385)

    def test_centre_est_bien_centre(self):
        monitor = self.mons[0]
        x, y = monitor.place(400, 200, center=True, rng=random)
        self.assertEqual(x, (1920 - 400) // 2)
        self.assertEqual(y, (1040 - 200) // 2)

    def test_ecran_a_coordonnees_negatives(self):
        """Un ecran a gauche du principal a un x negatif : ca doit suivre."""
        monitor = self.mons[2]
        x, y = monitor.place(200, 200, center=True, rng=random)
        self.assertLess(x, 0)
        self.assert_inside(monitor, x, y, 200, 200)

    def test_fenetre_plus_grande_que_l_ecran(self):
        """Cas degenere : on ne plante pas, on colle au coin de l'ecran."""
        monitor = self.mons[0]
        x, y = monitor.place(4000, 4000, center=False, rng=random)
        self.assertEqual((x, y), (monitor.x, monitor.y))


class Panoramique(unittest.TestCase):
    """Le son suit la position du squelette sur le bureau entier."""

    def setUp(self):
        # deux dalles cote a cote : le bureau va de 0 a 3840
        self.deux = [
            screens.Monitor(0, 0, 1920, 1040, primary=True, name="gauche"),
            screens.Monitor(1920, 0, 1920, 1040, primary=False, name="droite"),
        ]
        self.seul = [screens.Monitor(0, 0, 1920, 1080, primary=True, name="seul")]

    def test_bornes_du_bureau_virtuel(self):
        self.assertEqual(screens.virtual_bounds(self.deux), (0, 3840))
        self.assertEqual(screens.virtual_bounds(self.seul), (0, 1920))

    def test_bornes_avec_ecran_a_gauche(self):
        gauche = [
            screens.Monitor(-1920, 0, 1920, 1080, name="a gauche"),
            screens.Monitor(0, 0, 1920, 1080, primary=True, name="principal"),
        ]
        self.assertEqual(screens.virtual_bounds(gauche), (-1920, 1920))

    def test_extremites_et_centre(self):
        self.assertAlmostEqual(screens.pan_for(0, self.deux), -1.0)
        self.assertAlmostEqual(screens.pan_for(3840, self.deux), 1.0)
        self.assertAlmostEqual(screens.pan_for(1920, self.deux), 0.0)

    def test_un_seul_ecran_utilise_toute_sa_largeur(self):
        self.assertAlmostEqual(screens.pan_for(0, self.seul), -1.0)
        self.assertAlmostEqual(screens.pan_for(960, self.seul), 0.0)
        self.assertAlmostEqual(screens.pan_for(1920, self.seul), 1.0)

    def test_le_bord_droit_de_l_ecran_droit_sonne_a_droite(self):
        """Le vrai interet du calcul sur le bureau entier."""
        bord = screens.pan_for(3800, self.deux)
        self.assertGreater(bord, 0.9, "un doot colle a droite doit sonner a droite")

    def test_centre_de_l_ecran_droit(self):
        """Centre de la dalle de droite = trois quarts du bureau = +0.5."""
        self.assertAlmostEqual(screens.pan_for(2880, self.deux), 0.5)

    def test_toujours_borne(self):
        for x in (-10_000, -1, 3841, 99_999):
            valeur = screens.pan_for(x, self.deux)
            self.assertGreaterEqual(valeur, -1.0)
            self.assertLessEqual(valeur, 1.0)

    def test_progression_monotone(self):
        precedent = -2.0
        for x in range(0, 3841, 120):
            valeur = screens.pan_for(x, self.deux)
            self.assertGreaterEqual(valeur, precedent)
            precedent = valeur

    def test_liste_vide_reste_au_centre(self):
        self.assertEqual(screens.pan_for(500, []), 0.0)


class Acceleration(unittest.TestCase):
    """La courbe du glissement : vive au depart, posee a l'arrivee."""

    def test_bornes(self):
        self.assertAlmostEqual(screens.ease_out(0.0), 0.0)
        self.assertAlmostEqual(screens.ease_out(1.0), 1.0)

    def test_hors_bornes_bornee(self):
        self.assertAlmostEqual(screens.ease_out(-3.0), 0.0)
        self.assertAlmostEqual(screens.ease_out(7.0), 1.0)

    def test_monotone(self):
        precedent = -1.0
        for i in range(0, 101):
            valeur = screens.ease_out(i / 100)
            self.assertGreaterEqual(valeur, precedent)
            precedent = valeur

    def test_vive_au_depart(self):
        """A mi-parcours dans le temps, plus de la moitie du chemin est fait."""
        self.assertGreater(screens.ease_out(0.5), 0.5)
        self.assertGreater(screens.ease_out(0.25), 0.25)


class EntreeParLeCote(unittest.TestCase):
    """Le trajet d'entree : depart hors ecran, repos pres du bord."""

    def setUp(self):
        self.rng = random.Random(20260906)
        self.gauche = screens.Monitor(0, 0, 1920, 1040, primary=True, name="gauche")
        self.droite = screens.Monitor(1920, 0, 1920, 1040, name="droite")
        self.taille = (353, 385)

    def test_depart_entierement_hors_ecran(self):
        largeur, hauteur = self.taille
        ecran = self.gauche
        cas = {
            "left": lambda dx, dy: dx + largeur <= ecran.x,
            "right": lambda dx, dy: dx >= ecran.x + ecran.width,
            "top": lambda dx, dy: dy + hauteur <= ecran.y,
            "bottom": lambda dx, dy: dy >= ecran.y + ecran.height,
        }
        for cote, dehors in cas.items():
            dx, dy, _, _ = ecran.entry(largeur, hauteur, cote, self.rng)
            self.assertTrue(dehors(dx, dy), f"depart visible pour {cote} : +{dx}+{dy}")

    def test_repos_entierement_visible(self):
        largeur, hauteur = self.taille
        for ecran in (self.gauche, self.droite):
            for cote in ("left", "right", "top", "bottom"):
                for _ in range(120):
                    _, _, rx, ry = ecran.entry(largeur, hauteur, cote, self.rng)
                    self.assertGreaterEqual(rx, ecran.x, cote)
                    self.assertLessEqual(rx + largeur, ecran.x + ecran.width, cote)
                    self.assertGreaterEqual(ry, ecran.y, cote)
                    self.assertLessEqual(ry + hauteur, ecran.y + ecran.height, cote)

    def test_s_arrete_contre_le_bord(self):
        """Il se pose au bord, sans s'enfoncer : ce serait une traversee.

        Une marge de 5 % laisse la place au leger hasard qui evite un placement
        toujours identique.
        """
        largeur, hauteur = self.taille
        ecran = self.gauche
        marge_x, marge_y = ecran.width * 0.05, ecran.height * 0.05
        ecarts = {
            "left": lambda rx, ry: rx - ecran.x,
            "right": lambda rx, ry: (ecran.x + ecran.width) - (rx + largeur),
            "top": lambda rx, ry: ry - ecran.y,
            "bottom": lambda rx, ry: (ecran.y + ecran.height) - (ry + hauteur),
        }
        for cote, ecart in ecarts.items():
            marge = marge_x if cote in ("left", "right") else marge_y
            for _ in range(200):
                _, _, rx, ry = ecran.entry(largeur, hauteur, cote, self.rng)
                self.assertLessEqual(ecart(rx, ry), marge,
                                     f"entre par {cote}, il s'enfonce trop")

    def test_le_bord_est_atteint(self):
        """Le tirage doit pouvoir coller le squelette exactement au bord."""
        colles = sum(
            1 for _ in range(300)
            if self.gauche.entry(*self.taille, "left", self.rng)[2] == self.gauche.x
        )
        self.assertGreater(colles, 0, "jamais colle au bord")

    def test_glissement_sur_le_bon_axe(self):
        """Entrer par le cote ne bouge pas en y, et par le haut ne bouge pas en x."""
        largeur, hauteur = self.taille
        for cote in ("left", "right"):
            dx, dy, rx, ry = self.gauche.entry(largeur, hauteur, cote, self.rng)
            self.assertEqual(dy, ry, f"{cote} ne devrait pas glisser verticalement")
            self.assertNotEqual(dx, rx)
        for cote in ("top", "bottom"):
            dx, dy, rx, ry = self.gauche.entry(largeur, hauteur, cote, self.rng)
            self.assertEqual(dx, rx, f"{cote} ne devrait pas glisser horizontalement")
            self.assertNotEqual(dy, ry)

    def test_ecran_secondaire_garde_son_decalage(self):
        dx, _, rx, _ = self.droite.entry(*self.taille, "left", self.rng)
        self.assertLessEqual(dx + self.taille[0], self.droite.x)
        self.assertGreaterEqual(rx, self.droite.x)

    def test_centre_ne_centre_que_l_axe_perpendiculaire(self):
        largeur, hauteur = self.taille
        _, _, rx, ry = self.gauche.entry(largeur, hauteur, "left", self.rng, center=True)
        self.assertEqual(ry, self.gauche.y + (self.gauche.height - hauteur) // 2)
        self.assertLessEqual(rx - self.gauche.x, self.gauche.width * 0.05,
                             "le bord d'entree n'est pas negociable")

    def test_fenetre_plus_grande_que_l_ecran(self):
        """Cas degenere : on ne plante pas."""
        _, _, rx, ry = self.gauche.entry(4000, 4000, "left", self.rng)
        self.assertEqual((rx, ry), (self.gauche.x, self.gauche.y))



if __name__ == "__main__":
    unittest.main()
