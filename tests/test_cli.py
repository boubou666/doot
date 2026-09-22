"""Comportement de la CLI, et surtout le refus hors saison.

C'est la promesse du projet : hors du 1er septembre - 31 octobre, aucun doot ne
doit s'afficher. Le test remplace `window.show` pour compter les apparitions
sans jamais ouvrir de fenetre, ce qui le rend valable sur un serveur sans
affichage.
"""

from __future__ import annotations

import io
import json
import os
import random
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

from doot import cli, partage, season, window


class CliTestCase(unittest.TestCase):
    """Isole les donnees et neutralise l'affichage."""

    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        root = Path(self._dir.name)
        self.paths = {
            "data": root,
            "sound": root / "sound",
            "image": root / "image",
            "melodies": root / "melodies",
            "wav": root / "doot.wav",
            "log": root / "doot.log",
            "pid": root / "doot.pid",
            "state": root / "state.json",
        }
        self.shown = []
        self.notifications = []

        partage._connues.clear()
        self.addCleanup(partage._connues.clear)
        patches = [
            mock.patch.object(cli, "paths", lambda: self.paths),
            mock.patch.object(window, "show", lambda **kwargs: self.shown.append(kwargs)),
            mock.patch.object(
                cli.notification,
                "show",
                lambda *args, **kwargs: self.notifications.append({"args": args, **kwargs}),
            ),
            # Sans ce faux, tout test qui debloque plusieurs succes d'un coup
            # ouvre une vraie carte et attend qu'elle s'efface.
            mock.patch.object(
                cli.notification,
                "show_lot",
                lambda *args, **kwargs: self.notifications.append({"lot": args, **kwargs}),
            ),
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)

    def tearDown(self):
        self._dir.cleanup()

    def run_cli(self, *args) -> int:
        return cli.main(list(args))


class RefusHorsSaison(CliTestCase):
    """Le coeur du projet."""

    def hors_saison(self):
        return mock.patch.object(season, "in_season", lambda now=None: False)

    def en_saison(self):
        return mock.patch.object(season, "in_season", lambda now=None: True)

    def test_hors_saison_refuse_et_sort_en_3(self):
        with self.hors_saison():
            code = self.run_cli("--once", "--no-sound")
        self.assertEqual(code, 3)
        self.assertEqual(self.shown, [], "une fenetre a ete ouverte hors saison")

    def test_ignore_season_passe_outre(self):
        with self.hors_saison():
            code = self.run_cli("--once", "--ignore-season", "--no-sound")
        self.assertEqual(code, 0)
        self.assertEqual(len(self.shown), 1)

    def test_en_saison_affiche(self):
        with self.en_saison():
            code = self.run_cli("--once", "--no-sound")
        self.assertEqual(code, 0)
        self.assertEqual(len(self.shown), 1)

    def test_la_vraie_date_decide(self):
        """Sans patch, le comportement doit suivre le calendrier reel."""
        code = self.run_cli("--once", "--no-sound")
        if season.in_season(datetime.now()):
            self.assertEqual(code, 0)
            self.assertEqual(len(self.shown), 1)
        else:
            self.assertEqual(code, 3)
            self.assertEqual(self.shown, [])


class Play(CliTestCase):
    """`--play` et `--rickroll` : un seul passage, sur place, avec la partition."""

    def hors_saison(self):
        return mock.patch.object(season, "in_season", lambda now=None: False)

    def en_saison(self):
        return mock.patch.object(season, "in_season", lambda now=None: True)

    def test_hors_saison_le_squelette_range_sa_trompette(self):
        with self.hors_saison():
            code = self.run_cli("--rickroll", "--no-sound")
        self.assertEqual(code, 3)
        self.assertEqual(self.shown, [])

    def test_rickroll_est_un_raccourci_de_play(self):
        from doot import melodie

        morceau = melodie.load(melodie.MELODIES_DIR / "rickroll.rtttl")
        with self.en_saison():
            code = self.run_cli("--rickroll")
        self.assertEqual(code, 0)
        self.assertEqual(len(self.shown), 1)
        montre = self.shown[0]
        self.assertEqual(montre["beats"], melodie.onsets(morceau))
        self.assertEqual(
            montre["voices"],
            [melodie.onsets(morceau, voice=index) for index in range(2)],
        )
        self.assertEqual(montre["duration"], melodie.duration(morceau))
        self.assertEqual(montre["wav_path"], self.paths["data"] / "melodie.wav")
        self.assertTrue(montre["wav_path"].is_file())

    def test_play_par_nom_fourni(self):
        from doot import melodie

        morceau = melodie.load(melodie.MELODIES_DIR / "spooky-scary-skeletons.rtttl")
        with self.en_saison():
            code = self.run_cli("--play", "spooky-scary-skeletons", "--no-sound")
        self.assertEqual(code, 0)
        self.assertEqual(self.shown[0]["beats"], melodie.onsets(morceau))

    def test_play_par_fichier_perso(self):
        from doot import melodie

        self.paths["melodies"].mkdir()
        mien = self.paths["melodies"] / "gamme.rtttl"
        mien.write_text("Gamme:d=4,o=5,b=120:c,d,e", encoding="utf-8")
        with self.en_saison():
            code = self.run_cli("--play", "gamme", "--no-sound")
        self.assertEqual(code, 0)
        self.assertEqual(self.shown[0]["beats"], melodie.onsets(melodie.load(mien)))

    def test_transpose_suit(self):
        from doot import melodie

        morceau = melodie.load(melodie.MELODIES_DIR / "rickroll.rtttl")
        with self.en_saison():
            self.run_cli("--rickroll", "--no-sound", "--transpose", "-2")
        self.assertEqual(self.shown[0]["beats"], melodie.onsets(morceau, -2))

    def test_melodie_inconnue_sort_en_2_sans_rien_afficher(self):
        with self.en_saison():
            code = self.run_cli("--play", "nope", "--no-sound")
        self.assertEqual(code, 2)
        self.assertEqual(self.shown, [])

    def test_melodie_illisible_sort_en_2(self):
        self.paths["melodies"].mkdir()
        (self.paths["melodies"] / "casse.rtttl").write_text("x::c,?", encoding="utf-8")
        with self.en_saison():
            code = self.run_cli("--play", "casse", "--no-sound")
        self.assertEqual(code, 2)
        self.assertEqual(self.shown, [])

    def test_no_sound_ne_rend_pas_le_wav(self):
        with self.en_saison():
            self.run_cli("--rickroll", "--no-sound")
        self.assertIsNone(self.shown[0]["wav_path"])
        self.assertFalse((self.paths["data"] / "melodie.wav").exists())

    def test_les_reglages_d_affichage_suivent(self):
        with self.en_saison():
            self.run_cli("--rickroll", "--no-sound", "--screen", "primary", "--opacity", "0.5")
        montre = self.shown[0]
        self.assertEqual(montre["screen"], "primary")
        self.assertEqual(montre["opacity"], 0.5)

    def test_melodies_liste_sans_rien_afficher(self):
        with mock.patch("builtins.print") as sortie:
            code = self.run_cli("--melodies")
        self.assertEqual(code, 0)
        self.assertEqual(self.shown, [])
        texte = "\n".join(str(appel.args[0]) for appel in sortie.call_args_list if appel.args)
        self.assertIn("rickroll", texte)
        self.assertIn("spooky-scary-skeletons", texte)
        self.assertIn("megalovania", texte)
        self.assertIn("2 voix", texte)


class PlayPolyphonique(CliTestCase):
    """Une voix RTTTL donne exactement un squelette dans le meme concert."""

    def setUp(self):
        super().setUp()
        patch = mock.patch.object(season, "in_season", lambda now=None: True)
        patch.start()
        self.addCleanup(patch.stop)

    def test_megalovania_transmet_les_deux_voix(self):
        from doot import melodie

        morceau = melodie.load(melodie.MELODIES_DIR / "megalovania.rtttl")
        code = self.run_cli("--play", "megalovania", "--no-sound")
        self.assertEqual(code, 0)
        self.assertEqual(len(self.shown), 1, "le groupe partage une seule fenetre")
        self.assertEqual(
            self.shown[0]["voices"],
            [melodie.onsets(morceau, voice=index) for index in range(2)],
        )
        self.assertEqual(self.shown[0]["beats"], self.shown[0]["voices"][0])

    def test_une_seule_voix_garde_l_api_historique(self):
        self.run_cli("--play", "this-is-halloween", "--no-sound")
        self.assertNotIn("voices", self.shown[0])


class OptionsDAffichage(CliTestCase):
    """Ce qui est transmis a la fenetre."""

    def setUp(self):
        super().setUp()
        patch = mock.patch.object(season, "in_season", lambda now=None: True)
        patch.start()
        self.addCleanup(patch.stop)

    def test_no_image_force_l_ascii(self):
        self.run_cli("--once", "--no-sound", "--no-image")
        self.assertIsNone(self.shown[0]["image_path"])

    def test_image_fournie_par_defaut(self):
        from doot import image

        self.run_cli("--once", "--no-sound")
        if image.bundled_image() is not None:
            self.assertIsNotNone(self.shown[0]["image_path"])

    def test_no_sound_ne_transmet_aucun_son(self):
        self.run_cli("--once", "--no-sound")
        self.assertIsNone(self.shown[0]["wav_path"])

    def test_options_transmises(self):
        self.run_cli("--once", "--no-sound", "--center", "--screen", "1",
                     "--duration", "5", "--opacity", "0.4")
        call = self.shown[0]
        self.assertTrue(call["center"])
        self.assertEqual(call["screen"], "1")
        self.assertEqual(call["duration"], 5.0)
        self.assertEqual(call["opacity"], 0.4)

    def test_duree_suit_la_duree_du_son(self):
        """Sans --duration, l'affichage couvre au moins le son."""
        from doot import sound

        self.paths["sound"].mkdir(parents=True, exist_ok=True)
        sound.write_wav(self.paths["sound"] / "perso.wav", 0.5)

        self.run_cli("--once")
        self.assertGreaterEqual(self.shown[0]["duration"], cli.DEFAULT_DURATION)

    def test_min_et_max_incoherents_sont_rattrapes(self):
        """--max plus petit que --min ne doit pas casser le tirage aleatoire."""
        parser = cli.build_parser()
        args = parser.parse_args(["--min", "500", "--max", "10"])
        self.assertEqual(args.min, 500)
        # main() rattrape avant la boucle
        with mock.patch.object(season, "in_season", lambda now=None: False):
            self.assertEqual(self.run_cli("--min", "500", "--max", "10", "--once"), 3)


class TourCompletEnLigneDeCommande(CliTestCase):
    """`--spin` et ses reglages, tels qu'ils arrivent a la fenetre."""

    def setUp(self):
        super().setUp()
        patch = mock.patch.object(season, "in_season", lambda now=None: True)
        patch.start()
        self.addCleanup(patch.stop)

    def test_reglages_par_defaut(self):
        self.run_cli("--once", "--no-sound")
        call = self.shown[0]
        self.assertTrue(call["spin"])
        self.assertEqual(call["spin_chance"], cli.DEFAULT_SPIN_CHANCE)
        self.assertEqual(call["spin_ms"], cli.DEFAULT_SPIN_MS)

    def test_spin_impose_le_tour_et_l_apparition_sur_place(self):
        """Sans quoi la demande n'aurait d'effet qu'une fois sur quatre."""
        self.run_cli("--once", "--no-sound", "--spin")
        call = self.shown[0]
        self.assertEqual(call["spin_chance"], 1.0)
        self.assertFalse(call["slide"])

    def test_no_spin_coupe_le_tour_sans_toucher_au_reste(self):
        self.run_cli("--once", "--no-sound", "--no-spin")
        call = self.shown[0]
        self.assertFalse(call["spin"])
        self.assertTrue(call["slide"])

    def test_proportion_et_duree_transmises(self):
        self.run_cli("--once", "--no-sound", "--spin-chance", "0.8", "--spin-ms", "1200")
        call = self.shown[0]
        self.assertEqual(call["spin_chance"], 0.8)
        self.assertEqual(call["spin_ms"], 1200)

    def test_spin_et_side_sont_incompatibles(self):
        """L'un impose l'apparition sur place, l'autre l'entree par un bord."""
        parser = cli.build_parser()
        with mock.patch("sys.stderr"):
            with self.assertRaises(SystemExit):
                parser.parse_args(["--spin", "--side", "left"])


class DootInverseEtMuet(CliTestCase):
    def setUp(self):
        super().setUp()
        patch = mock.patch.object(season, "in_season", lambda now=None: True)
        patch.start()
        self.addCleanup(patch.stop)

    def test_reverse_force_image_et_wav_inverses(self):
        self.run_cli("--once", "--reverse")
        call = self.shown[0]
        self.assertTrue(call["reverse"])
        self.assertEqual(call["wav_path"].name, "doot-reverse.wav")
        self.assertTrue(call["wav_path"].is_file())

    def test_no_reverse_gagne_sur_reverse(self):
        args = cli.parse_args(["--reverse", "--no-reverse"])
        self.assertFalse(cli.should_reverse(args))

    def test_chance_reverse_bornee(self):
        class Fixe:
            def __init__(self, value):
                self.value = value

            def random(self):
                return self.value

        args = cli.build_parser().parse_args(["--reverse-chance", "0.3"])
        self.assertTrue(cli.should_reverse(args, Fixe(0.2)))
        self.assertFalse(cli.should_reverse(args, Fixe(0.4)))

    def test_mode_sans_son_affiche_le_doot_geant(self):
        self.run_cli("--once", "--no-sound", "--no-reverse")
        self.assertEqual(self.shown[0]["visual_text"], "D O O T")


class Salves(CliTestCase):
    """Plusieurs doots a la suite pour un seul declenchement."""

    def setUp(self):
        super().setUp()
        patch = mock.patch.object(season, "in_season", lambda now=None: True)
        patch.start()
        self.addCleanup(patch.stop)

    def sans_attente(self):
        """Neutralise les pauses de la salve, et note ce qui a ete demande."""
        pauses = []
        patch = mock.patch.object(cli.time, "sleep", pauses.append)
        patch.start()
        self.addCleanup(patch.stop)
        return pauses

    def test_par_defaut_un_seul_doot(self):
        self.sans_attente()
        self.run_cli("--once", "--no-sound")
        self.assertEqual(len(self.shown), 1)

    def test_salve_fixe(self):
        self.sans_attente()
        self.run_cli("--once", "--no-sound", "--burst-min", "3", "--burst-max", "3")
        self.assertEqual(len(self.shown), 3)

    def test_le_nombre_reste_dans_la_fourchette(self):
        self.sans_attente()
        for _ in range(30):
            self.shown.clear()
            self.run_cli("--once", "--no-sound", "--burst-min", "2", "--burst-max", "5")
            self.assertIn(len(self.shown), range(2, 6))

    def test_bornes_inversees_rattrapees(self):
        self.sans_attente()
        self.run_cli("--once", "--no-sound", "--burst-min", "4", "--burst-max", "1")
        self.assertEqual(len(self.shown), 4)

    def test_zero_devient_un(self):
        self.sans_attente()
        self.run_cli("--once", "--no-sound", "--burst-min", "0", "--burst-max", "0")
        self.assertEqual(len(self.shown), 1)

    def test_delai_entre_les_doots(self):
        """Une pause entre deux doots, donc n-1 pour une salve de n."""
        pauses = self.sans_attente()
        self.run_cli("--once", "--no-sound", "--burst-min", "3", "--burst-max", "3",
                     "--burst-delay", "0.25")
        self.assertEqual(pauses, [0.25, 0.25])

    def test_delai_nul_ne_dort_pas(self):
        pauses = self.sans_attente()
        self.run_cli("--once", "--no-sound", "--burst-min", "3", "--burst-max", "3",
                     "--burst-delay", "0")
        self.assertEqual(pauses, [])

    def test_delai_negatif_rattrape(self):
        pauses = self.sans_attente()
        self.run_cli("--once", "--no-sound", "--burst-min", "2", "--burst-max", "2",
                     "--burst-delay", "-3")
        self.assertEqual(pauses, [])

    def test_chaque_doot_de_la_salve_retire_son_animation(self):
        """Un appel a window.show par doot : c'est lui qui tire l'animation.

        Une salve qui n'appellerait show qu'une fois rejouerait la meme entree
        n fois, ce qui n'aurait aucun interet.
        """
        self.sans_attente()
        self.run_cli("--once", "--no-sound", "--burst-min", "4", "--burst-max", "4",
                     "--slide-chance", "0.5")
        self.assertEqual(len(self.shown), 4)
        for appel in self.shown:
            self.assertTrue(appel["slide"])
            self.assertIsNone(appel["side"])
            self.assertEqual(appel["slide_chance"], 0.5)

    def test_la_saison_qui_se_ferme_coupe_la_salve(self):
        """Une salve dure : la saison peut se fermer en plein milieu.

        Le premier doot a ete valide par l'appelant, les suivants revalident.
        """
        self.sans_attente()
        reponses = iter([True, False, False, False])
        with mock.patch.object(season, "in_season", lambda now=None: next(reponses)):
            self.run_cli("--once", "--no-sound", "--burst-min", "3", "--burst-max", "3",
                         "--burst-delay", "0")
        self.assertEqual(len(self.shown), 1)

    def test_ignore_season_laisse_la_salve_entiere(self):
        self.sans_attente()
        with mock.patch.object(season, "in_season", lambda now=None: False):
            self.run_cli("--once", "--ignore-season", "--no-sound",
                         "--burst-min", "3", "--burst-max", "3", "--burst-delay", "0")
        self.assertEqual(len(self.shown), 3)

    def test_hors_saison_aucune_salve(self):
        self.sans_attente()
        with mock.patch.object(season, "in_season", lambda now=None: False):
            code = self.run_cli("--once", "--no-sound", "--burst-min", "5", "--burst-max", "5")
        self.assertEqual(code, 3)
        self.assertEqual(self.shown, [])

    def test_burst_size_suit_le_tirage(self):
        args = cli.build_parser().parse_args(["--burst-min", "2", "--burst-max", "7"])

        class Fixe:
            def randint(self, bas, haut):
                self.vus = (bas, haut)
                return haut

        rng = Fixe()
        self.assertEqual(cli.burst_size(args, rng), 7)
        self.assertEqual(rng.vus, (2, 7))


class SalvesChoreographiees(CliTestCase):
    """Le mode canon organise les destinations sans changer le mode par defaut."""

    def setUp(self):
        super().setUp()
        patch = mock.patch.object(season, "in_season", lambda now=None: True)
        patch.start()
        self.addCleanup(patch.stop)
        patch = mock.patch.object(window, "active_monitors", return_value=[object(), object()])
        patch.start()
        self.addCleanup(patch.stop)
        patch = mock.patch.object(cli.time, "sleep")
        patch.start()
        self.addCleanup(patch.stop)

    def test_canon_alterne_les_bords_et_les_ecrans(self):
        self.run_cli("--once", "--no-sound", "--burst-min", "4", "--burst-max", "4",
                     "--burst-delay", "0", "--formation", "canon")

        self.assertEqual([call["screen"] for call in self.shown], ["0", "1", "0", "1"])
        self.assertEqual(
            [call["side"] for call in self.shown],
            ["left", "top", "right", "bottom"],
        )
        for call in self.shown:
            self.assertTrue(call["slide"])
            self.assertEqual(call["slide_chance"], 1.0)

    def test_choix_explicit_reste_fixe(self):
        self.run_cli("--once", "--no-sound", "--burst-min", "3", "--burst-max", "3",
                     "--burst-delay", "0", "--formation", "canon",
                     "--screen", "primary", "--side", "right")

        for call in self.shown:
            self.assertEqual(call["screen"], "primary")
            self.assertEqual(call["side"], "right")

    def test_no_slide_garde_la_formation_des_ecrans(self):
        self.run_cli("--once", "--no-sound", "--no-slide", "--side", "left",
                     "--burst-min", "2", "--burst-max", "2", "--burst-delay", "0",
                     "--formation", "canon")

        self.assertEqual([call["screen"] for call in self.shown], ["0", "1"])
        self.assertEqual([call["side"] for call in self.shown], ["left", "left"])
        self.assertEqual([call["slide"] for call in self.shown], [False, False])

    def test_wave_fait_l_aller_retour_et_alterne_les_cotes(self):
        with mock.patch.object(
            window, "active_monitors", return_value=[object(), object(), object()]
        ):
            self.run_cli(
                "--once", "--no-sound", "--burst-min", "5", "--burst-max", "5",
                "--burst-delay", "0", "--formation", "wave",
            )

        self.assertEqual([call["screen"] for call in self.shown], ["0", "1", "2", "1", "0"])
        self.assertEqual(
            [call["side"] for call in self.shown],
            ["left", "right", "left", "right", "left"],
        )

    def test_rain_tombe_du_haut(self):
        self.run_cli(
            "--once", "--no-sound", "--burst-min", "4", "--burst-max", "4",
            "--burst-delay", "0", "--formation", "rain",
        )
        self.assertEqual([call["side"] for call in self.shown], ["top"] * 4)
        self.assertTrue(all(call["slide"] for call in self.shown))

    def test_vortex_tourne_sur_place(self):
        self.run_cli(
            "--once", "--no-sound", "--burst-min", "4", "--burst-max", "4",
            "--burst-delay", "0", "--formation", "vortex",
        )
        self.assertTrue(all(not call["slide"] for call in self.shown))
        self.assertTrue(all(call["spin_chance"] == 1.0 for call in self.shown))

    def test_vortex_considere_side_random_comme_non_verrouille(self):
        self.run_cli(
            "--once", "--no-sound", "--side", "random", "--burst-min", "2",
            "--burst-max", "2", "--burst-delay", "0", "--formation", "vortex",
        )
        self.assertTrue(all(not call["slide"] for call in self.shown))
        self.assertTrue(all(call["spin_chance"] == 1.0 for call in self.shown))

    def test_no_spin_garde_le_vortex_sur_place_mais_droit(self):
        self.run_cli(
            "--once", "--no-sound", "--no-spin", "--burst-min", "2",
            "--burst-max", "2", "--burst-delay", "0", "--formation", "vortex",
        )
        self.assertTrue(all(not call["slide"] for call in self.shown))
        self.assertTrue(all(not call["spin"] for call in self.shown))


class EvenementsRares(CliTestCase):
    def setUp(self):
        super().setUp()
        patch = mock.patch.object(season, "in_season", lambda now=None: True)
        patch.start()
        self.addCleanup(patch.stop)
        patch = mock.patch.object(cli.time, "sleep")
        patch.start()
        self.addCleanup(patch.stop)

    def args(self, *options):
        return cli.build_parser().parse_args(list(options))

    def test_chance_et_pitie(self):
        rng = random.Random(0)
        self.assertFalse(cli.event_due(98, 0.0, 100, rng))
        self.assertTrue(cli.event_due(99, 0.0, 100, rng))
        self.assertTrue(cli.event_due(0, 1.0, 0, rng))

    def test_no_event_coupe_le_tirage(self):
        args = self.args("--no-event", "--event-chance", "1")
        self.assertIsNone(cli.event_roll(args, random.Random(0)))

    def test_un_evenement_force_joue_sa_choregraphie(self):
        code = self.run_cli("--event", "parade", "--no-sound")
        self.assertEqual(code, 0)
        self.assertEqual(len(self.shown), 6)
        self.assertEqual(
            [call["side"] for call in self.shown],
            ["left", "right", "left", "right", "left", "right"],
        )
        self.assertTrue(all(call["duration"] == 1.15 for call in self.shown))

    def test_evenement_inconnu_est_refuse(self):
        self.assertEqual(self.run_cli("--event", "ectoplasme", "--no-sound"), 2)
        self.assertEqual(self.shown, [])

    def test_compteur_d_evenement_survit_dans_l_etat(self):
        cli.note_evenement(False)
        cli.note_evenement(False)
        self.assertEqual(cli.read_state()["depuis_evenement"], 2)
        cli.note_evenement(True)
        self.assertEqual(cli.read_state()["depuis_evenement"], 0)


class ProfilsPersistants(CliTestCase):
    def setUp(self):
        super().setUp()
        patch = mock.patch.object(season, "in_season", lambda now=None: True)
        patch.start()
        self.addCleanup(patch.stop)
        patch = mock.patch.object(cli.time, "sleep")
        patch.start()
        self.addCleanup(patch.stop)

    def test_sauvegarde_activation_et_chargement_automatique(self):
        self.assertEqual(self.run_cli(
            "--save-profile", "chaos", "--formation", "rain",
            "--burst-min", "4", "--burst-max", "4", "--burst-delay", "0",
            "--no-sound",
        ), 0)
        self.assertEqual(self.run_cli("--activate-profile", "chaos", "--no-sound"), 0)

        self.assertEqual(self.run_cli("--once"), 0)
        self.assertEqual(len(self.shown), 4)
        self.assertEqual([call["side"] for call in self.shown], ["top"] * 4)
        self.assertTrue(all(call["wav_path"] is None for call in self.shown))

    def test_cli_remplace_les_valeurs_du_profil(self):
        self.run_cli(
            "--save-profile", "chaos", "--formation", "rain",
            "--burst-min", "4", "--burst-max", "4", "--no-sound",
        )
        self.run_cli("--activate-profile", "chaos", "--no-sound")
        self.run_cli(
            "--once", "--formation", "wave", "--burst-min", "2",
            "--burst-max", "2", "--burst-delay", "0",
        )
        self.assertEqual(len(self.shown), 2)
        self.assertEqual([call["side"] for call in self.shown], ["left", "right"])

    def test_side_avec_syntaxe_egale_remplace_le_spin_du_profil(self):
        self.run_cli("--save-profile", "toupie", "--spin", "--no-sound")
        self.run_cli("--activate-profile", "toupie", "--no-sound")

        args = cli.parse_args(["--once", "--side=left"])

        self.assertEqual(args.side, "left")
        self.assertFalse(args.spin)

    def test_no_spin_remplace_le_spin_du_profil(self):
        self.run_cli("--save-profile", "toupie", "--spin", "--no-sound")
        self.run_cli("--activate-profile", "toupie", "--no-sound")

        args = cli.parse_args(["--once", "--no-spin"])

        self.assertFalse(args.spin)
        self.assertTrue(args.no_spin)

    def test_side_remplace_no_slide_du_profil(self):
        self.run_cli("--save-profile", "statue", "--no-slide", "--no-sound")
        self.run_cli("--activate-profile", "statue", "--no-sound")

        args = cli.parse_args(["--once", "--side", "right"])

        self.assertEqual(args.side, "right")
        self.assertFalse(args.no_slide)

    def test_no_profile_retrouve_les_defauts(self):
        self.run_cli(
            "--save-profile", "chaos", "--burst-min", "4", "--burst-max", "4",
            "--no-sound",
        )
        self.run_cli("--activate-profile", "chaos", "--no-sound")
        self.run_cli("--no-profile", "--once", "--no-sound")
        self.assertEqual(len(self.shown), 1)

    def test_supprimer_le_profil_actif_le_desactive(self):
        self.run_cli("--save-profile", "calme", "--no-sound")
        self.run_cli("--activate-profile", "calme", "--no-sound")
        self.assertEqual(self.run_cli("--delete-profile", "calme", "--no-sound"), 0)
        document = cli.profiles.read(cli.profiles_path())
        self.assertIsNone(document["active"])
        self.assertNotIn("calme", document["profiles"])

    def test_profil_inconnu_est_refuse(self):
        with mock.patch("sys.stderr"), self.assertRaises(SystemExit) as sortie:
            cli.parse_args(["--profile", "inconnu", "--once"])
        self.assertEqual(sortie.exception.code, 2)


class CommandesInformatives(CliTestCase):
    """Elles doivent repondre sans affichage et sans effet de bord."""

    def test_status(self):
        self.assertEqual(self.run_cli("--status"), 0)
        self.assertEqual(self.shown, [])

    def test_paths(self):
        self.assertEqual(self.run_cli("--paths"), 0)

    def test_screens(self):
        self.assertEqual(self.run_cli("--screens"), 0)

    def test_art(self):
        self.assertEqual(self.run_cli("--art"), 0)
        self.assertEqual(self.shown, [])

    def test_succes(self):
        self.assertEqual(self.run_cli("--achievements"), 0)
        self.assertEqual(self.run_cli("--succes"), 0)
        self.assertEqual(self.shown, [])

    def test_nom_et_classement_duel(self):
        from doot import duel

        sortie = io.StringIO()
        with mock.patch("sys.stdout", new=sortie):
            self.assertEqual(self.run_cli("--duel-name", "Doot   Vader"), 0)
        state = cli.read_state()
        duel.record(state, 12, special=True, now=datetime(2026, 9, 22))
        cli.write_state(state)

        sortie = io.StringIO()
        with mock.patch.object(duel, "season_year", lambda now=None: 2026), \
                mock.patch("sys.stdout", new=sortie):
            self.assertEqual(self.run_cli("--duel-board"), 0)
        texte = sortie.getvalue()
        self.assertIn("Doot Vader", texte)
        self.assertIn("12 doots", texte)
        self.assertIn("1 speciaux", texte)
        self.assertIn("<- toi", texte)

    def test_nom_duel_vide_est_refuse(self):
        with mock.patch("sys.stdout", new=io.StringIO()):
            self.assertEqual(self.run_cli("--duel-name", "   "), 2)

    def test_stop_sans_daemon(self):
        self.assertEqual(self.run_cli("--stop"), 1)


class NotificationsDeSucces(CliTestCase):
    """Une medaille illustree suit chaque deblocage, sans jamais casser doot."""

    def setUp(self):
        super().setUp()
        patch = mock.patch.object(season, "in_season", lambda now=None: True)
        patch.start()
        self.addCleanup(patch.stop)

    def test_premier_succes_affiche_son_badge(self):
        self.assertEqual(self.run_cli("--once", "--no-sound"), 0)
        self.assertEqual(len(self.notifications), 1)
        toast = self.notifications[0]
        self.assertEqual(toast["args"][0], "Premier souffle")
        self.assertEqual(toast["args"][2], 5)
        self.assertEqual(toast["badge_path"].name, "premier_doot.png")
        self.assertIsNone(toast["wav_path"])

    def test_un_succes_n_est_pas_remontre(self):
        self.run_cli("--once", "--no-sound")
        self.run_cli("--once", "--no-sound")
        self.assertEqual(len(self.notifications), 1)

    def test_la_fanfare_rtttl_accompagne_le_toast(self):
        rendue = Path(self._dir.name) / "victory-parade.wav"
        with mock.patch.object(cli.notification, "render_victory", return_value=rendue) as render:
            self.run_cli("--once")
        render.assert_called_once_with(self.paths["data"] / "victory-parade.wav")
        self.assertEqual(self.notifications[0]["wav_path"], rendue)

    def test_no_sound_coupe_aussi_la_fanfare(self):
        with mock.patch.object(cli.notification, "render_victory") as render:
            self.run_cli("--once", "--no-sound")
        render.assert_not_called()
        self.assertIsNone(self.notifications[0]["wav_path"])

    def test_un_toast_en_echec_ne_fait_pas_echouer_le_doot(self):
        with mock.patch.object(cli.notification, "show", side_effect=RuntimeError("pas de toast")):
            self.assertEqual(self.run_cli("--once", "--no-sound"), 0)
        self.assertIn("notification de succes indisponible", self.paths["log"].read_text())


class FauxKernel32:
    """Imite les trois appels Win32 utilises par `_win_process_alive`."""

    WAIT_OBJECT_0 = 0x00000000
    WAIT_TIMEOUT = 0x00000102

    def __init__(self, handle=0x1234, attente=WAIT_TIMEOUT):
        self.fermes = []
        self.OpenProcess = mock.Mock(return_value=handle)
        self.WaitForSingleObject = mock.Mock(return_value=attente)
        self.CloseHandle = mock.Mock(side_effect=self.fermes.append)


class ProcessusVivantSousWindows(unittest.TestCase):
    """Un PID perime ne doit jamais passer pour un daemon qui tourne.

    La machine coupee en pleine saison tuait le daemon sans qu'il efface son
    `doot.pid`. `OpenProcess` reussissant encore sur le processus mort, doot
    se croyait deja lance et se retirait a chaque ouverture de session : plus
    aucun doot, jusqu'a effacer le fichier a la main.
    """

    def alive(self, **kwargs):
        faux = FauxKernel32(**kwargs)
        with mock.patch.object(cli, "_kernel32", lambda: faux):
            return cli._win_process_alive(4242), faux

    def test_objet_non_signale_le_processus_tourne(self):
        vivant, faux = self.alive(attente=FauxKernel32.WAIT_TIMEOUT)
        self.assertTrue(vivant)
        faux.OpenProcess.assert_called_once()

    def test_objet_signale_le_processus_est_mort(self):
        vivant, _ = self.alive(attente=FauxKernel32.WAIT_OBJECT_0)
        self.assertFalse(vivant, "un processus termine a ete pris pour vivant")

    def test_open_process_refuse_le_processus_est_mort(self):
        vivant, faux = self.alive(handle=0)
        self.assertFalse(vivant)
        faux.WaitForSingleObject.assert_not_called()
        self.assertEqual(faux.fermes, [], "rien a fermer si rien n'a ete ouvert")

    def test_le_handle_est_toujours_rendu(self):
        for attente in (FauxKernel32.WAIT_TIMEOUT, FauxKernel32.WAIT_OBJECT_0):
            with self.subTest(attente=attente):
                _, faux = self.alive(handle=0x1234, attente=attente)
                self.assertEqual(faux.fermes, [0x1234])


class PidPerime(CliTestCase):
    """Le fichier laisse par un daemon mort ne doit bloquer personne."""

    def mort(self):
        return mock.patch.object(cli, "_process_alive", lambda pid: False)

    def vivant(self):
        return mock.patch.object(cli, "_process_alive", lambda pid: True)

    def test_pid_perime_ne_compte_pas_comme_daemon(self):
        self.paths["pid"].write_text("12220")
        with self.mort():
            self.assertIsNone(cli.running_pid())

    def test_pid_perime_laisse_la_place(self):
        self.paths["pid"].write_text("12220")
        with self.mort():
            self.assertTrue(cli.claim_pid_file(), "le demarrage a ete refuse a tort")
        self.assertEqual(self.paths["pid"].read_text().strip(), str(os.getpid()))

    def test_daemon_vivant_garde_sa_place(self):
        self.paths["pid"].write_text("12220")
        with self.vivant():
            self.assertEqual(cli.running_pid(), 12220)
            self.assertFalse(cli.claim_pid_file())
        self.assertEqual(self.paths["pid"].read_text().strip(), "12220")

    def test_fichier_illisible_ne_bloque_pas(self):
        self.paths["pid"].write_text("pas un nombre")
        self.assertIsNone(cli.running_pid())
        self.assertTrue(cli.claim_pid_file())


class AucunAffichage(CliTestCase):
    """Le daemon sort au lieu de tourner aveugle jusqu'a la deconnexion.

    L'environnement d'un processus ne change plus une fois qu'il tourne :
    demarre avant que la session ne publie DISPLAY, le daemon ne le verrait
    jamais apparaitre. Sortir en erreur laisse le superviseur le relancer avec
    l'environnement complet.
    """

    def environnement(self, **variables):
        return mock.patch.dict(os.environ, variables, clear=False)

    def sans(self, *noms):
        propre = {k: v for k, v in os.environ.items() if k not in noms}
        return mock.patch.dict(os.environ, propre, clear=True)

    def boucle_interdite(self):
        """Fait echouer le test si le daemon atteint sa boucle d'attente.

        Sans ce garde-fou, un correctif retire laisserait le test tourner
        jusqu'au premier `time.sleep` de dix minutes : il se bloquerait au lieu
        d'echouer, ce qui ne previendrait personne.
        """
        def refus(_duree):
            raise AssertionError("le daemon a atteint sa boucle au lieu de sortir")

        return mock.patch.object(cli.time, "sleep", refus)

    def test_ni_x11_ni_wayland(self):
        with mock.patch.object(cli.sys, "platform", "linux"), \
                self.sans("DISPLAY", "WAYLAND_DISPLAY"):
            self.assertTrue(cli.sans_affichage())

    def test_x11_suffit(self):
        with mock.patch.object(cli.sys, "platform", "linux"), \
                self.sans("WAYLAND_DISPLAY"), self.environnement(DISPLAY=":0"):
            self.assertFalse(cli.sans_affichage())

    def test_wayland_suffit(self):
        with mock.patch.object(cli.sys, "platform", "linux"), \
                self.sans("DISPLAY"), self.environnement(WAYLAND_DISPLAY="wayland-0"):
            self.assertFalse(cli.sans_affichage())

    def test_windows_et_macos_dessinent_sans_ces_variables(self):
        for plateforme in ("win32", "darwin"):
            with self.subTest(plateforme=plateforme):
                with mock.patch.object(cli.sys, "platform", plateforme), \
                        self.sans("DISPLAY", "WAYLAND_DISPLAY"):
                    self.assertFalse(cli.sans_affichage())

    def test_le_daemon_sort_en_5(self):
        with mock.patch.object(cli, "sans_affichage", lambda: True), self.boucle_interdite():
            code = self.run_cli("--ignore-season", "--quiet")
        self.assertEqual(code, 5)
        self.assertEqual(self.shown, [], "aucun doot ne doit avoir ete tente")

    def test_le_daemon_ne_laisse_pas_de_fichier_pid(self):
        """Sortir avant de reclamer le pid : sinon la relance se croirait en double."""
        with mock.patch.object(cli, "sans_affichage", lambda: True), self.boucle_interdite():
            self.run_cli("--ignore-season", "--quiet")
        self.assertFalse(self.paths["pid"].exists())

    def test_le_journal_dit_pourquoi_meme_en_quiet(self):
        """L'unite tourne avec --quiet : sans le journal, le refus serait muet."""
        with mock.patch.object(cli, "sans_affichage", lambda: True), self.boucle_interdite():
            self.run_cli("--ignore-season", "--quiet")
        journal = self.paths["log"].read_text(encoding="utf-8")
        self.assertIn("aucun affichage joignable", journal)


class MelodieAuHasard(CliTestCase):
    """Le daemon joue parfois une melodie au lieu de la salve ordinaire.

    Deux reglages independants : une chance par declenchement, et un compteur
    de pitie qui borne les series noires. Le compteur vit dans le fichier
    d'etat, pas en memoire, parce que le daemon repart a chaque ouverture de
    session.
    """

    def args(self, *options):
        return cli.build_parser().parse_args(list(options))

    def declenchement(self, args, rng, jouee=True):
        """Un tour complet : le tirage, puis l'enregistrement de ce qu'il a donne."""
        fichier = cli.melody_roll(args, rng)
        cli.note_melodie(bool(fichier) and jouee)
        return fichier

    def melodie_fournie(self):
        from doot import melodie

        fournies = melodie.bundled()
        self.assertTrue(fournies, "aucune melodie fournie avec le paquet")
        return fournies[0]

    # ------------------------------------------------------------ tirage ----

    def test_la_chance_seule_suit_le_taux(self):
        rng = random.Random(0)
        tirages = 200_000
        touches = sum(cli.melody_due(0, 0.05, 0, rng) for _ in range(tirages))
        self.assertAlmostEqual(touches / tirages, 0.05, delta=0.002)

    def test_la_pitie_garantit_le_quarantieme(self):
        """Trente-neuf declenchements peuvent passer, le quarantieme non."""
        rng = random.Random(0)
        self.assertFalse(cli.melody_due(38, 0.0, 40, rng))
        self.assertTrue(cli.melody_due(39, 0.0, 40, rng))

    def test_pitie_a_zero_ne_garantit_rien(self):
        rng = random.Random(0)
        self.assertFalse(cli.melody_due(10_000, 0.0, 0, rng))

    def test_la_serie_noire_est_bornee(self):
        """Sans la pitie, une chance a 5 % laisse passer des series tres longues."""
        rng = random.Random(1)
        depuis = pire = 0
        for _ in range(200_000):
            if cli.melody_due(depuis, 0.05, 40, rng):
                pire = max(pire, depuis)
                depuis = 0
            else:
                depuis += 1
        self.assertLessEqual(pire, 39)

    # ------------------------------------------------------------- etat -----

    def test_le_compteur_monte_puis_repart_a_zero(self):
        args = self.args("--melody-chance", "0", "--melody-pity", "3")
        rng = random.Random(0)
        vus = [bool(self.declenchement(args, rng)) for _ in range(5)]
        self.assertEqual(vus, [False, False, True, False, False])

    def test_le_compteur_est_relu_du_fichier_a_chaque_fois(self):
        """C'est ce qui le fait survivre au redemarrage du daemon."""
        args = self.args("--melody-chance", "0", "--melody-pity", "10")
        self.declenchement(args, random.Random(0))
        self.declenchement(args, random.Random(0))
        self.assertEqual(json.loads(self.paths["state"].read_text())["depuis_melodie"], 2)

        cli.write_state({"depuis_melodie": 9})
        self.assertIsNotNone(self.declenchement(args, random.Random(0)))

    ETATS_ABIMES = (
        "ceci n'est pas du json",
        "[]",
        "null",
        '"bonjour"',
        "42",
        '{"depuis_melodie": "beaucoup"}',
        '{"depuis_melodie": null}',
        '{"depuis_melodie": true}',
        '{"depuis_melodie": 2.5}',
        '{"depuis_melodie": -5}',
    )

    def test_un_etat_abime_ne_fait_rien_planter(self):
        """Le fichier se modifie a la main, et du JSON valide n'est pas un etat valide.

        Un plantage ici serait rattrape par la boucle du daemon, qui
        n'afficherait alors ni melodie ni doot, et comme rien ne reparerait le
        fichier, tous les declenchements suivants seraient perdus aussi.
        """
        args = self.args("--melody-chance", "0", "--melody-pity", "3")
        for contenu in self.ETATS_ABIMES:
            with self.subTest(etat=contenu):
                self.paths["state"].write_text(contenu, encoding="utf-8")
                self.declenchement(args, random.Random(0))
                repare = json.loads(self.paths["state"].read_text(encoding="utf-8"))
                self.assertEqual(repare["depuis_melodie"], 1, "le compteur repart de zero")

    def test_state_compteur_ramene_a_un_entier_positif(self):
        for valeur, attendu in (({}, 0), ({"n": 3}, 3), ({"n": -5}, 0), ({"n": True}, 0),
                                ({"n": 2.5}, 0), ({"n": "beaucoup"}, 0), ({"n": None}, 0)):
            with self.subTest(valeur=valeur):
                self.assertEqual(cli.state_compteur(valeur, "n"), attendu)

    def test_les_autres_cles_de_l_etat_survivent(self):
        """Le fichier est partage : un compteur ajoute plus tard ne doit pas disparaitre."""
        cli.write_state({"depuis_melodie": 1, "autre_compteur": 7})
        self.declenchement(self.args("--melody-chance", "1"), random.Random(0))
        etat = json.loads(self.paths["state"].read_text(encoding="utf-8"))
        self.assertEqual(etat["autre_compteur"], 7)

    # ------------------------------------------------------------ refus -----

    def test_no_melody_coupe_tout(self):
        args = self.args("--no-melody", "--melody-chance", "1", "--melody-pity", "1")
        self.assertIsNone(cli.melody_roll(args, random.Random(0)))

    def test_sans_melodie_disponible_on_garde_les_doots(self):
        args = self.args("--melody-chance", "1")
        with mock.patch.object(cli, "melody_pool", lambda p: []):
            self.assertIsNone(cli.melody_roll(args, random.Random(0)))

    def test_une_melodie_illisible_ne_consomme_pas_la_pitie(self):
        """Le repli sur des doots ne vaut pas melodie jouee.

        Sinon le quarantieme declenchement joue des doots, remet le compteur a
        zero, et repousse la garantie de quarante tours ; avec un fichier
        casse tire plusieurs fois, la serie reelle n'est plus bornee du tout.
        """
        casse = Path(self._dir.name) / "casse.rtttl"
        casse.write_text("ceci n'est pas une sonnerie", encoding="utf-8")
        args = self.args("--melody-chance", "0", "--melody-pity", "40", "--no-sound")
        cli.write_state({"depuis_melodie": 39})

        with mock.patch.object(cli, "melody_pool", lambda p: [casse]):
            fichier = cli.melody_roll(args, random.Random(0))
            self.assertIsNotNone(fichier, "le quarantieme declenchement est du")
            jouee = cli.emit_melodie_tiree(args, fichier, journal=True)
            cli.note_melodie(jouee)

            self.assertFalse(jouee)
            self.assertEqual(
                json.loads(self.paths["state"].read_text())["depuis_melodie"], 40,
                "la garantie reste due au lieu d'etre consommee",
            )
            self.assertIsNotNone(cli.melody_roll(args, random.Random(0)),
                                 "le declenchement suivant retente")

    def test_la_melodie_jouee_consomme_la_pitie(self):
        args = self.args("--melody-chance", "0", "--melody-pity", "40", "--no-sound")
        cli.write_state({"depuis_melodie": 39})
        fichier = cli.melody_roll(args, random.Random(0))
        self.assertTrue(cli.emit_melodie_tiree(args, fichier))
        cli.note_melodie(True)
        self.assertEqual(json.loads(self.paths["state"].read_text())["depuis_melodie"], 0)

    # ---------------------------------------------------------- affichage ---

    def test_la_melodie_tiree_est_jouee(self):
        args = self.args("--no-sound")
        cli.emit_melodie_tiree(args, self.melodie_fournie(), journal=True)
        self.assertEqual(len(self.shown), 1)
        self.assertTrue(self.shown[0]["beats"], "le squelette doit hocher sur les notes")
        self.assertGreater(self.shown[0]["duration"], 0)
        self.assertIn("melodie :", self.paths["log"].read_text(encoding="utf-8"))

    def test_une_melodie_illisible_retombe_sur_les_doots(self):
        casse = Path(self._dir.name) / "casse.rtttl"
        casse.write_text("ceci n'est pas une sonnerie", encoding="utf-8")
        retombees = []
        with mock.patch.object(cli, "emit_doots",
                               lambda args, journal=False: retombees.append(journal)):
            cli.emit_melodie_tiree(self.args("--no-sound"), casse, journal=True)
        self.assertEqual(retombees, [True], "le declenchement ne doit pas etre perdu")
        self.assertIn("melodie illisible", self.paths["log"].read_text(encoding="utf-8"))

    # ------------------------------------------------------------ daemon ----

    def test_le_daemon_suit_le_tirage(self):
        """Une melodie tiree remplace la salve, elle ne s'y ajoute pas.

        Et le sort du declenchement est enregistre : une melodie jouee remet le
        compteur a zero, des doots le font monter.
        """
        cas = (
            (self.melodie_fournie(), True, "melodie", 0),
            (self.melodie_fournie(), False, "melodie", 6),
            (None, False, "doots", 6),
        )
        for tiree, jouee, attendu, compteur in cas:
            with self.subTest(tirage=attendu, jouee=jouee):
                cli.write_state({"depuis_melodie": 5})
                appels = []
                sommeils = []
                tours = []

                def dors(_duree):
                    sommeils.append(1)
                    if len(sommeils) > 1:
                        raise KeyboardInterrupt

                def joue_melodie(a, f, journal=False):
                    appels.append("melodie")
                    return jouee

                # Le daemon refuse de demarrer sans affichage : sans ce faux, le
                # test dependrait du DISPLAY de la machine qui le lance, et
                # tomberait sur un runner sans ecran.
                with mock.patch.object(cli, "sans_affichage", lambda: False), \
                        mock.patch.object(cli, "event_roll", lambda args, rng=None: None), \
                        mock.patch.object(cli, "melody_roll", lambda args, rng=None: tiree), \
                        mock.patch.object(cli, "emit_doots",
                                          lambda a, journal=False: appels.append("doots")), \
                        mock.patch.object(cli, "emit_melodie_tiree", joue_melodie), \
                        mock.patch.object(cli, "sync_tour",
                                          lambda a: tours.append(True)), \
                        mock.patch.object(cli.time, "sleep", dors):
                    self.run_cli("--ignore-season", "--quiet")

                self.assertEqual(appels, [attendu])
                etat = json.loads(self.paths["state"].read_text(encoding="utf-8"))
                self.assertEqual(etat["depuis_melodie"], compteur)
                self.assertEqual(tours, [True],
                                 "le daemon doit jouer un tour de synchronisation")


class ExportEtFusion(CliTestCase):
    """Les deux commandes qui font converger des postes, sans serveur."""

    def poste(self, nom, doots, **details):
        from doot import succes
        etat = {"machine": nom}
        for _ in range(doots):
            succes.enregistrer(etat, "doots", datetime(2026, 9, 17, 12, 0),
                               quantite=1, **details)
        return etat

    def depose(self, nom, contenu):
        chemin = Path(self._dir.name) / "partage" / nom
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_text(json.dumps(contenu), encoding="utf-8")
        return chemin

    def test_export_vers_un_dossier_nomme_d_apres_la_machine(self):
        from doot import succes
        cible = Path(self._dir.name) / "partage"
        cible.mkdir()
        self.assertEqual(self.run_cli("--export", str(cible)), 0)
        fichiers = list(cible.glob("*.json"))
        self.assertEqual(len(fichiers), 1)
        contenu = json.loads(fichiers[0].read_text(encoding="utf-8"))
        self.assertEqual(fichiers[0].name, f"doot-{contenu['machine']}.json")

    def test_l_export_laisse_les_compteurs_de_pitie_derriere_lui(self):
        """Ils decrivent le rythme d'un poste, pas ce qui y a ete accompli."""
        cli.write_state({"depuis_melodie": 7, "depuis_evenement": 3,
                         "stats": {"doots": {"ici": 4}}})
        cible = Path(self._dir.name) / "part.json"
        self.run_cli("--export", str(cible))
        contenu = json.loads(cible.read_text(encoding="utf-8"))
        self.assertEqual(set(contenu), {"machine", "stats", "succes"})

    def test_l_identifiant_de_machine_survit_a_l_export(self):
        cible = Path(self._dir.name) / "part.json"
        self.run_cli("--export", str(cible))
        premier = json.loads(cible.read_text(encoding="utf-8"))["machine"]
        self.run_cli("--export", str(cible))
        self.assertEqual(json.loads(cible.read_text(encoding="utf-8"))["machine"], premier)

    def test_la_fusion_additionne_et_debloque(self):
        from doot import succes
        cli.write_state(self.poste("ici", 60))
        self.depose("fixe.json", self.poste("fixe", 60))
        self.assertEqual(self.run_cli("--merge", str(Path(self._dir.name) / "partage")), 0)
        etat = cli.read_state()
        self.assertEqual(succes.total(etat, "doots"), 120)
        self.assertIn("cent_doots", etat["succes"])

    def test_refaire_la_fusion_ne_change_rien(self):
        from doot import succes
        cli.write_state(self.poste("ici", 60))
        dossier = str(Path(self._dir.name) / "partage")
        self.depose("fixe.json", self.poste("fixe", 60))
        self.run_cli("--merge", dossier)
        self.run_cli("--merge", dossier)
        self.assertEqual(succes.total(cli.read_state(), "doots"), 120)

    def test_son_propre_fichier_est_reconnu_et_saute(self):
        from doot import succes
        etat = self.poste("ici", 10)
        cli.write_state(etat)
        ici = cli.read_state()["machine"]
        self.depose("moi.json", {"machine": ici, "stats": {"doots": {ici: 999}}})
        self.assertEqual(self.run_cli("--merge", str(Path(self._dir.name) / "partage")), 2)
        self.assertEqual(succes.total(cli.read_state(), "doots"), 10)

    def test_un_etat_sans_machine_est_refuse_sans_rien_casser(self):
        from doot import succes
        cli.write_state(self.poste("ici", 10))
        self.depose("anonyme.json", {"stats": {"doots": 999}})
        self.assertEqual(self.run_cli("--merge", str(Path(self._dir.name) / "partage")), 2)
        self.assertEqual(succes.total(cli.read_state(), "doots"), 10)

    def test_un_fichier_illisible_n_arrete_pas_les_autres(self):
        from doot import succes
        cli.write_state(self.poste("ici", 10))
        dossier = Path(self._dir.name) / "partage"
        dossier.mkdir(parents=True, exist_ok=True)
        (dossier / "casse.json").write_text("ceci n'est pas du json", encoding="utf-8")
        self.depose("fixe.json", self.poste("fixe", 5))
        self.assertEqual(self.run_cli("--merge", str(dossier)), 0)
        self.assertEqual(succes.total(cli.read_state(), "doots"), 15)

    def test_rien_a_fusionner_sort_en_2(self):
        dossier = Path(self._dir.name) / "vide"
        dossier.mkdir()
        self.assertEqual(self.run_cli("--merge", str(dossier)), 2)


class PartageAutomatique(CliTestCase):
    """Le cycle que le daemon joue a chaque doot : reprendre, fusionner, publier."""

    def poste(self, nom, doots):
        from doot import succes
        etat = {"machine": nom}
        for _ in range(doots):
            succes.enregistrer(etat, "doots", datetime(2026, 9, 17, 12, 0), quantite=1)
        return etat

    def depot(self):
        return Path(self._dir.name) / "depot"

    def regle(self, cle=None):
        from doot import coffre
        fiche = {"dossier": str(self.depot()), "cle": cle or coffre.en_texte(coffre.creer())}
        partage.poser_reglage(self.paths["data"], fiche)
        return fiche["cle"]

    def publie_un_pair(self, etat, cle_texte):
        from doot import coffre, transport
        cle = coffre.depuis_texte(cle_texte)
        partage.publier(etat, transport.Dossier(self.depot()), cle)

    def test_sans_cle_le_tour_ne_fait_rien(self):
        cli.write_state(self.poste("ici", 10))
        cli.sync_tour(cli.build_parser().parse_args(["--quiet"]))
        self.assertNotIn("sync_note", cli.read_state())

    def test_le_cycle_reprend_fusionne_et_publie(self):
        from doot import coffre, succes, transport
        cle = self.regle()
        self.publie_un_pair(self.poste("fixe", 60), cle)

        etat = cli.read_state()
        etat.update(self.poste(etat["machine"], 0))
        for _ in range(60):
            succes.enregistrer(etat, "doots", datetime(2026, 9, 17), quantite=1)
        partage.cycle(etat, self.paths["data"])

        self.assertEqual(succes.total(etat, "doots"), 120)
        self.assertEqual(etat["sync_note"]["pairs"], 1)
        noms = [o.nom for o in transport.Dossier(self.depot()).lister()]
        self.assertIn(coffre.nom_objet(coffre.depuis_texte(cle), etat["machine"]), noms)

    def test_ce_qui_est_publie_est_chiffre(self):
        from doot import coffre
        cle = self.regle()
        etat = cli.read_state()
        partage.cycle(etat, self.paths["data"])
        octets = next((self.depot() / "v1").iterdir()).read_bytes()
        self.assertTrue(octets.startswith(coffre.MAGIC))
        self.assertNotIn(b"doots", octets)
        self.assertNotIn(etat["machine"].encode(), octets)

    def test_une_autre_cle_ne_lit_rien(self):
        from doot import coffre
        cle = self.regle()
        self.publie_un_pair(self.poste("fixe", 60), cle)
        self.regle(coffre.en_texte(coffre.creer()))

        etat = cli.read_state()
        partage.cycle(etat, self.paths["data"])
        self.assertEqual(etat["sync_note"]["pairs"], 0)
        self.assertIn("autre cle", " ".join(etat["sync_note"]["ecartes"]))

    def test_un_depot_impossible_ne_leve_jamais(self):
        """Un doot ne doit pas dependre du partage."""
        from doot import coffre, succes
        bloque = Path(self._dir.name) / "bloque"
        bloque.write_text("je ne suis pas un dossier", encoding="utf-8")
        partage.poser_reglage(self.paths["data"],
                              {"dossier": str(bloque / "dedans"),
                               "cle": coffre.en_texte(coffre.creer())})
        etat = self.poste("ici", 10)
        self.assertEqual(partage.cycle(etat, self.paths["data"]), [])
        self.assertIn("erreur", etat["sync_note"])
        self.assertEqual(succes.total(etat, "doots"), 10)

    def test_le_tour_est_idempotent(self):
        from doot import succes
        cle = self.regle()
        self.publie_un_pair(self.poste("fixe", 60), cle)
        etat = cli.read_state()
        for _ in range(60):
            succes.enregistrer(etat, "doots", datetime(2026, 9, 17), quantite=1)
        cli.write_state(etat)
        for _ in range(3):
            cli.sync_tour(cli.build_parser().parse_args(["--quiet"]))
        self.assertEqual(succes.total(cli.read_state(), "doots"), 120)

    def test_sync_init_frappe_une_cle_et_publie(self):
        from doot import coffre
        cli.write_state(self.poste("ici", 10))
        self.assertEqual(self.run_cli("--sync-init", str(self.depot())), 0)
        fiche = partage.reglage(self.paths["data"])
        self.assertTrue(fiche["cle"].startswith(coffre.PREFIXE))
        self.assertTrue(list((self.depot() / "v1").iterdir()))

    def test_sync_init_garde_la_cle_existante(self):
        cle = self.regle()
        self.run_cli("--sync-init", str(self.depot()))
        self.assertEqual(partage.reglage(self.paths["data"])["cle"], cle)

    def test_sync_force_en_frappe_une_neuve(self):
        cle = self.regle()
        self.run_cli("--sync-init", str(self.depot()), "--sync-force")
        self.assertNotEqual(partage.reglage(self.paths["data"])["cle"], cle)

    def test_sync_join_refuse_une_cle_de_travers(self):
        self.regle()
        self.assertEqual(self.run_cli("--sync-join", "pas-une-cle"), 2)

    def test_sync_join_retient_la_cle_donnee(self):
        from doot import coffre
        self.regle()
        autre = coffre.en_texte(coffre.creer())
        self.assertEqual(self.run_cli("--sync-join", autre), 0)
        self.assertEqual(partage.reglage(self.paths["data"])["cle"], autre)

    def test_rejoindre_retire_l_objet_de_l_ancienne_cle(self):
        """Sinon le depot garde un objet que plus personne ne sait ouvrir."""
        from doot import coffre
        self.regle()
        self.run_cli("--sync-init", str(self.depot()))
        avant = {p.name for p in (self.depot() / "v1").iterdir()}
        self.run_cli("--sync-join", coffre.en_texte(coffre.creer()))
        apres = {p.name for p in (self.depot() / "v1").iterdir()}
        self.assertEqual(len(apres), 1, f"reste {apres - avant | avant - apres}")

    def test_la_rotation_retire_l_objet_de_l_ancienne_cle(self):
        """Symetrique de celui de --sync-join : la cle neuve ne laisse pas de dechet."""
        self.run_cli("--sync-init", str(self.depot()))
        self.assertEqual(len(list((self.depot() / "v1").iterdir())), 1)
        self.run_cli("--sync-init", str(self.depot()), "--sync-force")
        restants = list((self.depot() / "v1").iterdir())
        self.assertEqual(len(restants), 1, f"reste {[p.name for p in restants]}")

    def objets(self):
        return {chemin.name for chemin in (self.depot() / "v1").iterdir()}

    def rotation_ratee(self, *commande):
        """Joue une commande qui change de cle pendant que le depot refuse d'ecrire."""
        from doot import transport
        self.run_cli("--sync-init", str(self.depot()))
        avant, cle = self.objets(), partage.reglage(self.paths["data"])["cle"]
        with mock.patch.object(partage, "publier",
                               side_effect=transport.TransportError("disque plein")):
            self.assertEqual(self.run_cli(*commande), 2)
        return cle, avant

    def test_une_rotation_ratee_retient_la_cle_quittee(self):
        """Sans la marque, plus personne ne sait quel objet retirer."""
        cle, avant = self.rotation_ratee("--sync-init", str(self.depot()), "--sync-force")
        fiche = partage.reglage(self.paths["data"])
        self.assertIn(cle, fiche["cles_quittees"])
        self.assertNotEqual(fiche["cle"], cle)
        self.assertEqual(self.objets(), avant)

    def test_le_cycle_suivant_solde_une_rotation_ratee(self):
        _, avant = self.rotation_ratee("--sync-init", str(self.depot()), "--sync-force")
        cli.sync_tour(cli.build_parser().parse_args(["--quiet"]))
        self.assertEqual(len(self.objets()), 1)
        self.assertFalse(self.objets() & avant)
        self.assertNotIn("cles_quittees", partage.reglage(self.paths["data"]))

    def test_rejoindre_apres_une_publication_ratee_solde_aussi(self):
        from doot import coffre
        cle, avant = self.rotation_ratee("--sync-join", coffre.en_texte(coffre.creer()))
        self.assertIn(cle, partage.reglage(self.paths["data"])["cles_quittees"])
        cli.sync_tour(cli.build_parser().parse_args(["--quiet"]))
        self.assertEqual(len(self.objets()), 1)
        self.assertFalse(self.objets() & avant)
        self.assertNotIn("cles_quittees", partage.reglage(self.paths["data"]))

    def test_relancer_sync_init_solde_une_rotation_ratee(self):
        """Refrapper la commande sur le meme depot ne doit pas perdre la marque."""
        _, avant = self.rotation_ratee("--sync-init", str(self.depot()), "--sync-force")
        self.assertEqual(self.run_cli("--sync-init", str(self.depot())), 0)
        self.assertEqual(len(self.objets()), 1)
        self.assertFalse(self.objets() & avant)

    def test_un_retrait_impossible_garde_la_marque(self):
        """Tant que l'objet quitte est la, la marque doit survivre au cycle."""
        from doot import transport
        cle, avant = self.rotation_ratee("--sync-init", str(self.depot()), "--sync-force")
        with mock.patch.object(transport.Dossier, "effacer",
                               side_effect=transport.TransportError("lecture seule")):
            cli.sync_tour(cli.build_parser().parse_args(["--quiet"]))
        self.assertIn(cle, partage.reglage(self.paths["data"])["cles_quittees"])
        cli.sync_tour(cli.build_parser().parse_args(["--quiet"]))
        self.assertEqual(len(self.objets()), 1)
        self.assertFalse(self.objets() & avant)

    def test_refrapper_la_rotation_ratee_n_oublie_pas_la_premiere_cle(self):
        """Le geste naturel apres un echec : rejouer la meme commande.

        La cle de la tentative ratee n'a jamais rien publie ; si elle chassait
        celle d'avant, l'objet de celle-ci resterait la pour toujours.
        """
        _, avant = self.rotation_ratee("--sync-init", str(self.depot()), "--sync-force")
        self.assertEqual(self.run_cli("--sync-init", str(self.depot()), "--sync-force"), 0)
        self.assertEqual(len(self.objets()), 1)
        self.assertFalse(self.objets() & avant)
        self.assertNotIn("cles_quittees", partage.reglage(self.paths["data"]))

    def test_deux_cles_peuvent_attendre_leur_retrait(self):
        """Une rotation dont le retrait echoue, puis une autre : deux objets restent."""
        from doot import transport
        self.run_cli("--sync-init", str(self.depot()))
        avant = self.objets()
        with mock.patch.object(transport.Dossier, "effacer",
                               side_effect=transport.TransportError("lecture seule")):
            self.assertEqual(self.run_cli("--sync-init", str(self.depot()), "--sync-force"), 0)
        self.assertEqual(len(self.objets()), 2)
        avant |= self.objets()

        self.assertEqual(self.run_cli("--sync-init", str(self.depot()), "--sync-force"), 0)
        restants = self.objets()
        self.assertEqual(len(restants), 1, f"reste {restants}")
        self.assertFalse(restants & avant)

    def test_revenir_a_une_cle_quittee_ne_retire_pas_son_objet(self):
        """Elle est redevenue courante : la solder effacerait la part du jour."""
        from doot import coffre
        cle, _ = self.rotation_ratee("--sync-init", str(self.depot()), "--sync-force")
        self.assertEqual(self.run_cli("--sync-join", cle), 0)
        etat = cli.read_state()
        attendu = coffre.nom_objet(coffre.depuis_texte(cle), etat["machine"])
        self.assertEqual(self.objets(), {attendu})

    def test_une_fiche_a_l_ancienne_marque_est_reprise(self):
        """Quand la marque n'en tenait qu'une, elle designait deja un objet."""
        from doot import coffre
        self.run_cli("--sync-init", str(self.depot()))
        avant = self.objets()
        partage.poser_reglage(self.paths["data"],
                              {"dossier": str(self.depot()),
                               "cle": coffre.en_texte(coffre.creer()),
                               "cle_precedente": partage.reglage(self.paths["data"])["cle"]})
        cli.sync_tour(cli.build_parser().parse_args(["--quiet"]))
        self.assertEqual(len(self.objets()), 1)
        self.assertFalse(self.objets() & avant)

    def test_une_publication_ratee_rend_quand_meme_ce_qui_a_fusionne(self):
        """La fusion a eu lieu : un depot muet ne doit pas avaler les succes."""
        from doot import succes, transport
        cle = self.regle()
        self.publie_un_pair(self.poste("fixe", 60), cle)
        etat = cli.read_state()
        for _ in range(60):
            succes.enregistrer(etat, "doots", datetime(2026, 9, 17), quantite=1)
        with mock.patch.object(partage, "publier",
                               side_effect=transport.TransportError("disque plein")):
            nouveaux = partage.cycle(etat, self.paths["data"])
        self.assertIn("cent_doots", [item.identifiant for item in nouveaux])
        self.assertIn("erreur", etat["sync_note"])

    def test_sync_init_off_coupe_tout(self):
        self.regle()
        self.assertEqual(self.run_cli("--sync-init", "off"), 0)
        self.assertEqual(partage.reglage(self.paths["data"]), {})

    def test_le_secret_ne_part_pas_dans_l_etat(self):
        """La cle vit dans replica.json, que l'etat copiable n'emporte pas."""
        self.regle()
        etat = cli.read_state()
        cli.write_state(etat)
        self.assertNotIn("sync", etat)
        self.assertNotIn("cle", json.dumps(etat))


class IdentifiantsDuSeau(CliTestCase):
    """Les identifiants S3 se posent dans la fiche, pas dans l'environnement.

    Une machine qui garde deja des `AWS_*` pour autre chose ne doit pas avoir a
    les partager avec doot, ni a jouer avec l'ordre de chargement de
    `environment.d` pour les separer.
    """

    def sync_init(self, *extra):
        with mock.patch.object(partage, "cycle", return_value=[]):
            return self.run_cli("--sync-init", "s3://seau",
                                "--sync-endpoint", "https://exemple.invalid", *extra)

    def fiche(self):
        return partage.reglage(self.paths["data"])

    def test_les_deux_champs_atterrissent_dans_la_fiche(self):
        self.assertEqual(self.sync_init("--sync-key-id", "abc",
                                        "--sync-secret", "xyz"), 0)
        self.assertEqual((self.fiche()["cle_acces"], self.fiche()["secret"]),
                         ("abc", "xyz"))

    def test_sans_les_drapeaux_la_fiche_ne_porte_rien(self):
        """Un champ vide masquerait l'environnement, qui doit pouvoir repondre."""
        self.assertEqual(self.sync_init(), 0)
        self.assertNotIn("cle_acces", self.fiche())
        self.assertNotIn("secret", self.fiche())

    def test_un_tiret_lit_le_secret_sur_l_entree(self):
        """Pour qu'il ne traine ni dans `ps` ni dans l'historique du shell."""
        with mock.patch("sys.stdin", io.StringIO("depuis-l-entree\n")):
            self.assertEqual(self.sync_init("--sync-key-id", "abc",
                                            "--sync-secret", "-"), 0)
        self.assertEqual(self.fiche()["secret"], "depuis-l-entree")

    def test_une_relance_sans_drapeaux_les_conserve(self):
        self.sync_init("--sync-key-id", "abc", "--sync-secret", "xyz")
        self.assertEqual(self.sync_init(), 0)
        self.assertEqual(self.fiche()["secret"], "xyz")


class AnnoncesGroupees(CliTestCase):
    """Plusieurs succes tombes ensemble tiennent sur une seule carte."""

    def args_quiet(self):
        return cli.build_parser().parse_args(["--quiet"])

    def succes_du_catalogue(self, combien):
        from doot import succes
        return list(succes.CATALOGUE[:combien])

    def test_un_seul_succes_garde_sa_carte(self):
        cli.annoncer_succes(self.args_quiet(), self.succes_du_catalogue(1))
        self.assertEqual(len(self.notifications), 1)
        self.assertIn("args", self.notifications[0], "carte simple attendue")

    def test_plusieurs_succes_ne_font_qu_une_carte(self):
        """Cinq cartes a la suite bloquaient le daemon dix-sept secondes."""
        lot = self.succes_du_catalogue(5)
        cli.annoncer_succes(self.args_quiet(), lot)
        self.assertEqual(len(self.notifications), 1, "une carte, pas cinq")
        carte = self.notifications[0]
        self.assertIn("lot", carte, "carte groupee attendue")
        titres, points = carte["lot"][0], carte["lot"][1]
        self.assertEqual(titres, [item.titre for item in lot])
        self.assertEqual(points, sum(item.points for item in lot))

    def test_chaque_succes_garde_sa_ligne_de_journal(self):
        lot = self.succes_du_catalogue(3)
        cli.annoncer_succes(self.args_quiet(), lot)
        journal = self.paths["log"].read_text(encoding="utf-8")
        for definition in lot:
            self.assertIn(definition.titre, journal)

    def test_aucun_succes_n_annonce_rien(self):
        cli.annoncer_succes(self.args_quiet(), [])
        self.assertEqual(self.notifications, [])


class IdentiteDeReplique(CliTestCase):
    """L'etat charge porte l'identite du poste, jamais celle du fichier."""

    def test_l_etat_charge_prend_l_identite_du_poste(self):
        cli.write_state({"machine": "venue-d-ailleurs", "stats": {"doots": {"x": 5}}})
        etat = cli.read_state()
        self.assertNotEqual(etat["machine"], "venue-d-ailleurs")
        self.assertEqual(etat["machine"], partage.identite(self.paths["data"]))

    def test_les_parts_de_l_etat_copie_ne_sont_pas_perdues(self):
        """Elles restent a la machine qui les a gagnees ; seules les suivantes
        vont a la nouvelle identite."""
        from doot import succes
        cli.write_state({"machine": "venue-d-ailleurs", "stats": {"doots": {"souche": 10}}})
        etat = cli.read_state()
        succes.enregistrer(etat, "doots", datetime(2026, 9, 18), quantite=5)
        self.assertEqual(succes.total(etat, "doots"), 15)
        self.assertEqual(etat["stats"]["doots"]["souche"], 10)


if __name__ == "__main__":
    unittest.main()
