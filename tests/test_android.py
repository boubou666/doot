"""Overlay Android.

Aucun telephone ni televiseur en CI : la plateforme est simulee. On verifie que
hors application hote le backend s'efface, qu'un refus de superposition se
solde par un repli, que la fenetre Java recoit bien ce qu'`overlay.run` lui
envoie, et qu'Android est essaye avant Wayland et X11.
"""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest import mock

from doot import android, audio, window


def plateforme(peut_dessiner=True, application=True):
    fenetre = mock.Mock()
    fenetre.canDraw.return_value = peut_dessiner
    simulee = mock.Mock()
    simulee.jclass.side_effect = lambda nom: fenetre if nom == android.FENETRE else None
    simulee.context.return_value = mock.Mock() if application else None
    return simulee, fenetre


class SansApplicationHote(unittest.TestCase):
    def test_available_est_faux_sur_un_bureau(self):
        self.assertFalse(android.available())

    def test_available_est_faux_sans_desktop_overlay_recent(self):
        with mock.patch.object(android, "plateforme", None):
            self.assertFalse(android.available())


class Fenetre(unittest.TestCase):
    def test_un_refus_de_superposition_empeche_l_affichage(self):
        simulee, fenetre = plateforme(peut_dessiner=False)
        with mock.patch.object(android, "plateforme", simulee):
            with self.assertRaises(android.AndroidUnavailable):
                android._Overlay(10, 10, 0, 0)
        fenetre.assert_not_called()

    def test_sans_application_pas_de_fenetre(self):
        simulee, _ = plateforme(application=False)
        with mock.patch.object(android, "plateforme", simulee):
            with self.assertRaises(android.AndroidUnavailable):
                android._Overlay(10, 10, 0, 0)

    def test_la_fenetre_java_recoit_des_entiers(self):
        simulee, fenetre = plateforme()
        with mock.patch.object(android, "plateforme", simulee):
            surcouche = android._Overlay(120.0, 80.0, 5.6, 7.2)
            surcouche.map()
            surcouche.draw(b"\0" * 4)
            surcouche.move(10.7, 20.2)
            surcouche.close()
        instance = fenetre.return_value
        fenetre.assert_called_once_with(simulee.context.return_value, 120, 80, 5, 7)
        instance.show.assert_called_once_with()
        instance.draw.assert_called_once_with(b"\0" * 4)
        instance.move.assert_called_once_with(10, 20)
        instance.close.assert_called_once_with()


class Lecture(unittest.TestCase):
    def test_la_fenetre_nait_au_point_de_depart_du_glissement(self):
        frame = mock.Mock(width=30, height=40)
        with mock.patch.object(android, "_Overlay") as fenetre, \
                mock.patch.object(android.overlay, "run") as run:
            android.play(frame, 100, 200, 2.0, start=(0, 200), slide_ms=400)
        fenetre.assert_called_once_with(30, 40, 0, 200)
        self.assertIs(run.call_args.args[0], fenetre.return_value)

    def test_sans_glissement_elle_nait_a_sa_place(self):
        frame = mock.Mock(width=30, height=40)
        with mock.patch.object(android, "_Overlay") as fenetre, \
                mock.patch.object(android.overlay, "run"):
            android.play(frame, 100, 200, 2.0, start=(0, 200), slide_ms=0)
        fenetre.assert_called_once_with(30, 40, 100, 200)


class Ordre(unittest.TestCase):
    def test_android_est_essaye_avant_wayland_et_x11(self):
        essayes = []

        def tente(backend, *_args, **_kwargs):
            essayes.append(backend)
            return False

        with mock.patch.object(window, "_tente_overlay", side_effect=tente):
            window._show_argb(None, 2.0, False, 1.0, Path("doot.png"), None,
                              None, True)
        self.assertEqual(essayes, [android, window.wayland, window.x11])


class Son(unittest.TestCase):
    def test_audiotrack_passe_en_premier_quand_il_existe(self):
        if audio._AndroidOutput is None:
            self.skipTest("desktop-overlay sans sortie Android")
        self.assertIs(audio._SORTIES[0], audio._SortieAndroid)
        self.assertEqual(audio._SortieAndroid.nom, "Android AudioTrack")


if __name__ == "__main__":
    unittest.main()
