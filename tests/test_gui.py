"""Le grimoire graphique compose fidelement des commandes CLI."""

from __future__ import annotations

import unittest
from unittest import mock

from doot import cli, composer_gui, gui


class CatalogueGraphique(unittest.TestCase):
    def test_les_actions_principales_sont_toutes_visibles(self):
        options = gui.COMMAND_OPTIONS
        attendues = {
            "--once", "--play", "--rickroll", "--melodies", "--sync-init",
            "--sync-join", "--sync-endpoint", "--sync-region",
            "--sync-key-id", "--sync-secret",
            "--export", "--merge", "--achievements", "--codex", "--events", "--event",
            "--carte", "--stats", "--status", "--stop", "--paths", "--art", "--update",
            "--check-update", "--profiles", "--save-profile",
            "--activate-profile", "--deactivate-profile", "--delete-profile",
            "--screens", "--regen-sound", "--version", "--help", "--gui",
            "--duel-board", "--duel-name", "--composer",
            "--tray",
            "--control", "--event-save", "--event-title", "--event-description",
            "--history", "--challenge", "--content", "--favor-melody",
            "--disable-melody", "--enable-melody", "--favor-event",
            "--disable-event", "--enable-event",
            "--pack-export", "--pack-import", "--pack-author", "--pack-description",
            "--pack-version", "--fleet-parade", "--snooze",
            "--resume", "--schedule-profile", "--schedule-window",
            "--schedule-days", "--unschedule-profile",
            "--choreographer", "--studio-live", "--pack-library",
            "--campaign", "--campaign-choose", "--boss", "--boss-hit",
            "--combo", "--invasion", "--generate-melody", "--melody-seed",
            "--melody-name", "--replay-export", "--choreographies",
            "--choreography-save", "--choreography-play", "--rituals",
            "--ritual-add", "--ritual-at", "--ritual-action", "--ritual-value",
            "--ritual-delete", "--museum", "--skeletons", "--skeleton",
            "--music-duel", "--music-duels", "--duel-opponent", "--riddles",
            "--expedition", "--expedition-choose", "--campaign-editor",
            "--campaign-pack", "--constellation", "--familiars", "--familiar",
            "--familiar-bond", "--contract", "--contract-add", "--contract-share",
            "--contract-join", "--dj-import", "--dj-slices", "--ambient-mode",
            "--replay-gif", "--code-hunt", "--code-submit", "--new-game-plus",
            "--character", "--characters", "--character-skull",
            "--character-costume", "--character-instrument", "--character-voice",
            "--character-line", "--character-pack", "--radio", "--coop",
            "--night-infinite",
            "--city", "--relics", "--factions", "--faction-mission",
            "--nemesis", "--investigation", "--investigate", "--ghost-export",
            "--ghost-time", "--ghost-race", "--adaptive-score", "--score-danger",
            "--score-combo", "--director", "--photo-booth", "--photo-pose",
            "--remote", "--remote-serve", "--remote-host", "--remote-port", "--workshop-validate",
            "--night-calendar", "--glyphs", "--glyph-decode",
            "--story-constellation", "--mirror-boss",
            "--catacombs", "--catacomb-choose", "--time-loop",
            "--familiar-skill", "--bestiary", "--necroforge",
            "--paranormal-weather", "--collective-ritual", "--ritual-offer",
            "--ritual-export", "--ritual-import", "--nemesis-invasion",
            "--invasion-defend", "--tribunal", "--tribunal-action", "--legacy",
            "--campaign-lab", "--campaign-check", "--personal-museum",
            "--seals", "--seal-submit",
            "--ghost-train", "--train-route", "--train-choose",
            "--spectral-crew", "--rail-case", "--rail-investigate",
            "--archaeology", "--restore-artifact", "--black-market",
            "--market-seed", "--prophecy", "--crypt-gazette",
            "--musical-battle", "--battle-note", "--funeral-house",
            "--house-mission", "--mod-forge", "--mod-validate",
            "--train-replay", "--lost-station", "--thirteenth-bell",
            "--grand-retour", "--grand-retour-restart", "--grand-retour-choose",
            "--grand-retour-secret", "--grand-retour-export",
            "--after-dawn", "--after-dawn-choose", "--crew-missions",
            "--crew-mission", "--carnet", "--carnet-secrets", "--eighth-door",
            "--accessibility",
        }
        self.assertEqual(options, attendues)

    def test_tous_les_autres_drapeaux_deviennent_des_reglages(self):
        parser = cli.build_parser()
        reglages = {spec.option for spec in gui.option_specs(parser)}
        visibles = reglages | gui.COMMAND_OPTIONS
        longs = {
            option
            for action in parser._actions
            for option in action.option_strings
            if option.startswith("--") and option not in {"--exporter", "--fusionner", "--succes"}
        }
        self.assertEqual(visibles, longs)
        self.assertIn("--formation", reglages)
        self.assertIn("--ignore-season", reglages)

    def test_chaque_commande_a_son_illustration_embarquee(self):
        absentes = [
            command.image for command in gui.COMMANDS
            if not (gui.ASSETS_DIR / command.image).is_file()
        ]
        self.assertEqual(absentes, [])

    def test_l_enigme_se_consulte_sans_reponse(self):
        command = next(item for item in gui.COMMANDS if item.key == "grand-retour-secret")
        argv = gui.build_command_argv(command, {}, {}, (), strict=True)
        self.assertEqual(argv, ["--grand-retour-secret"])

    def test_jeu_et_outils_ont_des_sous_menus_distincts(self):
        self.assertEqual(gui.command_section("carnet"), ("game", "Campagnes & carnet"))
        self.assertEqual(gui.command_section("daemon"), ("tools", "Invocation & musique"))
        self.assertEqual({item.key for item in gui.COMMANDS},
                         set(gui.GAME_KEYS) | {item.key for item in gui.COMMANDS
                                               if gui.command_section(item.key)[0] == "tools"})

    def test_choix_du_monde_compose_deux_arguments(self):
        item = next(command for command in gui.COMMANDS if command.key == "after-dawn-choose")
        self.assertEqual(gui.build_command_argv(item, {"--after-dawn-choose": "cite; rebatir"}, {}, ()),
                         ["--after-dawn-choose", "cite", "rebatir"])


class CompositionCommande(unittest.TestCase):
    def setUp(self):
        self.settings = gui.option_specs(cli.build_parser())

    def command(self, key):
        return next(command for command in gui.COMMANDS if command.key == key)

    def test_une_action_et_ses_reglages_forment_argv(self):
        argv = gui.build_command_argv(
            self.command("once"), {},
            {"formation": "wave", "ignore_season": True, "volume": "0.8"},
            self.settings,
        )
        self.assertEqual(
            argv,
            ["--once", "--formation", "wave", "--volume", "0.8", "--ignore-season"],
        )
        parsed = cli.build_parser().parse_args(argv)
        self.assertTrue(parsed.once)
        self.assertEqual(parsed.formation, "wave")

    def test_une_commande_a_deux_arguments_garde_le_second_positionnel(self):
        argv = gui.build_command_argv(
            self.command("campaign-pack"),
            {"--campaign-pack": "campagne.json", "": "packs"}, {}, self.settings,
        )
        self.assertEqual(argv, ["--campaign-pack", "campagne.json", "packs"])

    def test_la_forge_de_mod_garde_ses_trois_arguments(self):
        argv = gui.build_command_argv(
            self.command("mod-forge"),
            {"--mod-forge": "mods; Express des ombres; train"}, {}, self.settings,
        )
        self.assertEqual(argv, ["--mod-forge", "mods", "Express des ombres", "train"])
        parsed = cli.build_parser().parse_args(argv)
        self.assertEqual(parsed.mod_forge, ["mods", "Express des ombres", "train"])

    def test_un_parametre_obligatoire_manquant_est_refuse(self):
        with self.assertRaisesRegex(ValueError, "Melodie"):
            gui.build_command_argv(self.command("play"), {}, {}, self.settings)

    def test_le_compositeur_est_une_page_detachee(self):
        command = self.command("composer")
        self.assertTrue(command.detached)
        self.assertEqual(command.argv, ("--composer",))

    def test_la_fusion_accepte_plusieurs_sources(self):
        argv = gui.build_command_argv(
            self.command("merge"),
            {"--merge": "partage-a ; C:/Mes fichiers/partage-b"}, {}, self.settings,
        )
        self.assertEqual(
            argv,
            ["--merge", "partage-a", "C:/Mes fichiers/partage-b"],
        )

    def test_l_apercu_protege_les_chemins_avec_espaces(self):
        texte = gui.format_command(["--image", "C:/Mes images/doot.png"])
        self.assertIn("C:/Mes images/doot.png", texte)


class GalerieSucces(unittest.TestCase):
    def test_les_cartes_reunissent_badge_progression_et_deblocage(self):
        etat = {
            "stats": {"doots": 7},
            "succes": {"premier_doot": "2026-09-20T12:34:56"},
        }

        cards = gui.achievement_cards(etat)
        premier = next(card for card in cards if card.identifiant == "premier_doot")
        dix = next(card for card in cards if card.identifiant == "dix_doots")

        self.assertEqual(premier.debloque_le, "2026-09-20T12:34:56")
        self.assertEqual((dix.courant, dix.objectif), (7, 10))
        self.assertTrue((gui.ASSETS_DIR / "success" / f"{premier.identifiant}.png").is_file())

    def test_la_date_iso_est_rendue_pour_un_humain(self):
        self.assertEqual(gui._achievement_date("2026-09-20T12:34:56"), "20/09/2026")
        self.assertEqual(gui._achievement_date("date ancienne"), "date ancienne")


class EntreeCli(unittest.TestCase):
    def test_gui_delegue_au_lanceur_sans_preparer_le_daemon(self):
        with mock.patch.object(gui, "main", return_value=27) as lancer:
            self.assertEqual(cli.main(["--gui"]), 27)
        lancer.assert_called_once_with()

    def test_compositeur_delegue_a_sa_page_sans_preparer_le_daemon(self):
        with mock.patch.object(composer_gui, "main", return_value=28) as lancer:
            self.assertEqual(cli.main(["--composer"]), 28)
        lancer.assert_called_once_with()


class DefilementGraphique(unittest.TestCase):
    class Widget:
        def __init__(self, master=None):
            self.master = master

    class Canvas(Widget):
        def __init__(self, master=None):
            super().__init__(master)
            self.scrolls = []

        def yview_scroll(self, amount, units):
            self.scrolls.append((amount, units))

    def test_les_petites_valeurs_de_trackpad_ne_sont_pas_perdues(self):
        self.assertEqual(gui.wheel_units(1), -1)
        self.assertEqual(gui.wheel_units(-1), 1)
        self.assertEqual(gui.wheel_units(240), -2)

    def test_la_molette_sur_un_widget_enfant_fait_defiler_son_canevas(self):
        canvas = self.Canvas()
        enfant = self.Widget(self.Widget(canvas))
        app = gui.DootApp.__new__(gui.DootApp)
        app.wheel_canvases = [canvas]
        event = mock.Mock(widget=enfant, delta=-120, num=0)

        self.assertEqual(app._dispatch_wheel(event), "break")
        self.assertEqual(canvas.scrolls, [(1, "units")])

    def test_la_molette_hors_des_zones_defilables_est_ignoree(self):
        canvas = self.Canvas()
        app = gui.DootApp.__new__(gui.DootApp)
        app.wheel_canvases = [canvas]
        event = mock.Mock(widget=self.Widget(), delta=-120, num=0)

        self.assertIsNone(app._dispatch_wheel(event))
        self.assertEqual(canvas.scrolls, [])


class ParametresFacultatifs(unittest.TestCase):
    """Un dossier local ne doit pas reclamer les reglages d'un seau."""

    def sync_init(self):
        return next(c for c in gui.COMMANDS if c.key == "sync-init")

    def test_un_dossier_local_se_compose_sans_endpoint(self):
        argv = gui.build_command_argv(
            self.sync_init(), {"--sync-init": "/home/moi/Sync"}, {}, strict=True)
        self.assertIn("--sync-init", argv)
        self.assertNotIn("--sync-endpoint", argv)
        self.assertNotIn("--sync-region", argv)

    def test_le_depot_reste_obligatoire(self):
        with self.assertRaises(ValueError):
            gui.build_command_argv(self.sync_init(), {}, {}, strict=True)

    def test_un_seau_transmet_ses_reglages(self):
        argv = gui.build_command_argv(
            self.sync_init(),
            {"--sync-init": "s3://seau/doot", "--sync-endpoint": "https://exemple"},
            {}, strict=True)
        self.assertIn("--sync-endpoint", argv)
        self.assertIn("https://exemple", argv)


if __name__ == "__main__":
    unittest.main()
