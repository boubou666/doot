"""Choix du bord d'entree et orientation qui en decoule.

Rien ici n'ouvre de fenetre : seules la selection du bord et la table des
rotations sont verifiees, ce qui tourne sur un serveur sans affichage.
"""

from __future__ import annotations

import random
import unittest
from pathlib import Path
from unittest import mock

from doot import window


class ChoixDuBord(unittest.TestCase):
    """`--side` et son tirage au sort."""

    def test_bords_explicites(self):
        for demande in ("left", "right", "top", "bottom"):
            self.assertEqual(window.pick_side(demande), demande)

    def test_noms_francais_acceptes(self):
        self.assertEqual(window.pick_side("gauche"), "left")
        self.assertEqual(window.pick_side("droite"), "right")
        self.assertEqual(window.pick_side("haut"), "top")
        self.assertEqual(window.pick_side("bas"), "bottom")

    def test_valeur_absente_ou_incomprise_tire_au_sort(self):
        for demande in (None, "random", "n'importe quoi"):
            self.assertIn(window.pick_side(demande), window.COTES)

    def test_les_quatre_bords_sortent(self):
        rng = random.Random(4321)
        vus = {window.pick_side(None, rng) for _ in range(400)}
        self.assertEqual(vus, set(window.COTES))


class MelangeDesDeuxModes(unittest.TestCase):
    """Entrer par un bord ou surgir sur place, tire au sort a chaque doot."""

    def part_glissee(self, chance, tirages=4000, side=None, slide=True):
        rng = random.Random(1234)
        return sum(
            1 for _ in range(tirages)
            if window.decide_slide(slide, side, chance, rng)
        ) / tirages

    def test_les_deux_modes_coexistent(self):
        """Ni tout par les bords, ni tout sur place."""
        part = self.part_glissee(0.5)
        self.assertGreater(part, 0.4)
        self.assertLess(part, 0.6)

    def test_la_proportion_est_respectee(self):
        for chance in (0.2, 0.5, 0.8):
            self.assertAlmostEqual(self.part_glissee(chance), chance, delta=0.05)

    def test_zero_reste_toujours_sur_place(self):
        self.assertEqual(self.part_glissee(0.0), 0.0)

    def test_un_entre_toujours_par_un_bord(self):
        self.assertEqual(self.part_glissee(1.0), 1.0)

    def test_valeurs_aberrantes_bornees(self):
        self.assertEqual(self.part_glissee(-3.0), 0.0)
        self.assertEqual(self.part_glissee(12.0), 1.0)

    def test_no_slide_coupe_tout(self):
        self.assertEqual(self.part_glissee(1.0, slide=False), 0.0)

    def test_un_bord_demande_impose_le_glissement(self):
        """Sans quoi --side left n'aurait d'effet qu'une fois sur deux."""
        self.assertEqual(self.part_glissee(0.01, side="left"), 1.0)

    def test_un_bord_demande_ne_force_rien_si_no_slide(self):
        self.assertEqual(self.part_glissee(1.0, side="left", slide=False), 0.0)


class Orientation(unittest.TestCase):
    """La rotation qui pose le bas de l'image contre le bord d'entree."""

    def test_table_complete(self):
        self.assertEqual(set(window.TOURS), set(window.COTES))

    def test_sens_de_rotation(self):
        """Un quart de tour horaire amene le bas a gauche, trois a droite."""
        self.assertEqual(window.TOURS["left"], 1)
        self.assertEqual(window.TOURS["right"], 3)
        self.assertEqual(window.TOURS["top"], 2)
        self.assertEqual(window.TOURS["bottom"], 0)

    def test_gauche_et_droite_sont_opposees(self):
        self.assertEqual((window.TOURS["left"] + window.TOURS["right"]) % 4, 0)

    def test_entrer_par_le_bas_ne_pivote_rien(self):
        """L'image est deja debout : son bas est deja en bas."""
        self.assertEqual(window.TOURS["bottom"] % 4, 0)

    def test_un_quart_echange_les_cotes(self):
        """Utilise pour ajuster l'echelle : la fenetre change de proportions."""
        for cote in ("left", "right"):
            self.assertEqual(window.TOURS[cote] % 2, 1)
        for cote in ("top", "bottom"):
            self.assertEqual(window.TOURS[cote] % 2, 0)

    def test_reverse_ajoute_exactement_un_demi_tour(self):
        self.assertEqual(window.image_turns(None, True), 2)
        for cote in window.COTES:
            self.assertEqual(
                window.image_turns(cote, True),
                (window.image_turns(cote, False) + 2) % 4,
            )


class TourComplet(unittest.TestCase):
    """La rotation complete : le squelette tourne sur lui-meme, sur place."""

    def part_tournee(self, chance, tirages=4000, spin=True, glisse=False):
        rng = random.Random(1234)
        return sum(
            1 for _ in range(tirages)
            if window.decide_spin(spin, chance, glisse, rng)
        ) / tirages

    def test_la_proportion_est_respectee(self):
        for chance in (0.2, 0.25, 0.8):
            self.assertAlmostEqual(self.part_tournee(chance), chance, delta=0.05)

    def test_zero_ne_fait_jamais_tourner(self):
        self.assertEqual(self.part_tournee(0.0), 0.0)

    def test_un_fait_toujours_tourner(self):
        self.assertEqual(self.part_tournee(1.0), 1.0)

    def test_valeurs_aberrantes_bornees(self):
        self.assertEqual(self.part_tournee(-3.0), 0.0)
        self.assertEqual(self.part_tournee(12.0), 1.0)

    def test_no_spin_coupe_tout(self):
        self.assertEqual(self.part_tournee(1.0, spin=False), 0.0)

    def test_jamais_pendant_une_entree_par_un_bord(self):
        """L'image y est deja pivotee pour poser les pieds contre le bord."""
        self.assertEqual(self.part_tournee(1.0, glisse=True), 0.0)

    def test_le_repli_tk_termine_apres_un_tour(self):
        """La boucle d'orchestre ne doit pas masquer le label du tour."""
        class Photo:
            def __init__(self, *_args, **_kwargs):
                pass

            def width(self):
                return 120

            def height(self):
                return 160

        class Racine:
            def __init__(self):
                self.prochain = None
                self.termine = False
                self.detruite = False

            def winfo_screenwidth(self):
                return 800

            def winfo_screenheight(self):
                return 600

            def update_idletasks(self):
                pass

            def withdraw(self):
                pass

            def overrideredirect(self, _value):
                pass

            def wm_attributes(self, *_args):
                pass

            def configure(self, **_kwargs):
                pass

            def geometry(self, _value):
                pass

            def deiconify(self):
                pass

            def after(self, _delay, callback):
                self.prochain = callback

            def mainloop(self):
                for _ in range(20):
                    callback, self.prochain = self.prochain, None
                    if callback is None or self.termine:
                        return
                    callback()
                raise AssertionError("la boucle Tk ne s'est pas terminee")

            def quit(self):
                self.termine = True

            def destroy(self):
                self.detruite = True

        etiquettes = []

        class Etiquette:
            def __init__(self, _parent, **_kwargs):
                self.images = []
                etiquettes.append(self)

            def pack(self):
                pass

            def configure(self, **kwargs):
                if "image" in kwargs:
                    self.images.append(kwargs["image"])

            def winfo_reqwidth(self):
                return 160

            def winfo_reqheight(self):
                return 160

        class FauxTk:
            PhotoImage = Photo
            Label = Etiquette

            def __init__(self, root):
                self.Tk = lambda: root

        root = Racine()
        photos = [Photo() for _ in range(4)]
        tk = FauxTk(root)
        monitor = window.screens.Monitor(0, 0, 800, 600)
        with mock.patch.object(window, "_show_argb", return_value=False), \
             mock.patch.object(window, "_import_tk", return_value=(tk, object())), \
             mock.patch.object(window, "_spin_photos", return_value=photos), \
             mock.patch.object(window.screens, "monitors", return_value=[monitor]):
            window.show(
                duration=0.4,
                image_path=Path("squelette.png"),
                center=True,
                slide=False,
                spin=True,
                spin_chance=1.0,
            )

        self.assertTrue(root.termine)
        self.assertTrue(root.detruite)
        self.assertIn(photos[1], etiquettes[0].images)


class Orchestre(unittest.TestCase):
    """La grille grossit sans plafond et reste dans les bornes de l'ecran."""

    def test_deux_squelettes_verticaux_se_mettent_cote_a_cote(self):
        columns, rows, scale = window.ensemble_layout(2, 100, 200, 1920, 1080)
        self.assertEqual((columns, rows), (2, 1))
        self.assertEqual(scale, 1.0)

    def test_la_grille_contient_toutes_les_voix(self):
        for count in (3, 7, 50, 500):
            columns, rows, scale = window.ensemble_layout(
                count, 320, 480, 1920, 1080
            )
            self.assertGreaterEqual(columns * rows, count)
            self.assertGreater(columns, 0)
            self.assertGreater(rows, 0)
            self.assertGreater(scale, 0)

    def test_un_grand_orchestre_est_reduit_et_tient_a_l_ecran(self):
        columns, rows, scale = window.ensemble_layout(
            500, 320, 480, 1920, 1080
        )
        group_width = 320 * scale * (columns + 0.05 * (columns - 1))
        group_height = 480 * scale * (rows + 0.05 * (rows - 1))
        self.assertLess(scale, 1.0)
        self.assertLessEqual(group_width, 1920 * 0.86 + 1)
        self.assertLessEqual(group_height, 1080 * 0.72 + 1)

    def test_une_voix_conserve_l_echelle_historique(self):
        self.assertEqual(
            window.ensemble_layout(1, 1000, 800, 1920, 1080),
            (1, 1, window._auto_scale(1000, 800, 1920, 1080)),
        )

if __name__ == "__main__":
    unittest.main()
