"""Comportement de la CLI, et surtout le refus hors saison.

C'est la promesse du projet : hors du 1er septembre - 31 octobre, aucun doot ne
doit s'afficher. Le test remplace `window.show` pour compter les apparitions
sans jamais ouvrir de fenetre, ce qui le rend valable sur un serveur sans
affichage.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

from doot import cli, season, window


class CliTestCase(unittest.TestCase):
    """Isole les donnees et neutralise l'affichage."""

    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        root = Path(self._dir.name)
        self.paths = {
            "data": root,
            "sound": root / "sound",
            "image": root / "image",
            "wav": root / "doot.wav",
            "log": root / "doot.log",
            "pid": root / "doot.pid",
        }
        self.shown = []

        patches = [
            mock.patch.object(cli, "paths", lambda: self.paths),
            mock.patch.object(window, "show", lambda **kwargs: self.shown.append(kwargs)),
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

    def test_stop_sans_daemon(self):
        self.assertEqual(self.run_cli("--stop"), 1)


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


if __name__ == "__main__":
    unittest.main()
