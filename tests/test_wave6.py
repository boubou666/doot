"""Le Dernier Train et les systemes locaux de la vague 6."""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from doot import succes, wave6


class LastTrain(unittest.TestCase):
    def finish_route(self, state, route):
        item = wave6.start_ghost_train(state, "essai-" + route, route)
        while item["active"]:
            item = wave6.choose_ghost_train(state, item["current"]["counter"])
        self.assertTrue(item["arrived"])
        return item

    def test_train_is_deterministic_and_reaches_a_terminus(self):
        first = wave6.start_ghost_train({}, "minuit", "cendre")
        second = wave6.start_ghost_train({}, "minuit", "cendre")
        self.assertEqual(first["stations"], second["stations"])
        state = {}
        item = self.finish_route(state, "cendre")
        self.assertEqual(item["completed_routes"], ["cendre"])

    def test_three_lines_complete_the_network(self):
        state = {}
        for route in wave6.TRAIN_ROUTES:
            item = self.finish_route(state, route)
        self.assertEqual(len(item["completed_routes"]), 3)

    def test_four_recruits_complete_the_crew(self):
        state = {}
        for member in tuple(wave6.SPECTRAL_CREW)[:4]:
            item = wave6.recruit_spectral_crew(state, member)
        self.assertTrue(item["complete"])


class MysteriesAndRelics(unittest.TestCase):
    def test_rail_case_needs_clues_and_can_be_solved(self):
        state = {}
        wave6.start_rail_case(state, "siege")
        truth = state["wave6"]["rail_case"]["truth"]
        with self.assertRaisesRegex(ValueError, "deux indices"):
            wave6.investigate_rail_case(state, "accuser:" + truth)
        wave6.investigate_rail_case(state, "chercher")
        wave6.investigate_rail_case(state, "chercher")
        item = wave6.investigate_rail_case(state, "accuser:" + truth)
        self.assertTrue(item["solved"])

    def test_archaeology_restores_an_artifact_and_collects_nine_fragments(self):
        state = {}
        for site in wave6.ARCHAEOLOGY_SITES:
            for _ in range(3):
                wave6.dig_archaeology(state, site)
            restored = wave6.restore_artifact(state, site)
            self.assertTrue(restored["fresh"])
        item = wave6.archaeology_status(state)
        self.assertEqual(len(item["fragments"]), 9)
        self.assertEqual(len(item["restored"]), 3)

    def test_black_market_hides_then_reveals_authenticity(self):
        state = {}
        item = wave6.black_market_status(state, "marche-test")
        self.assertTrue(all("verdict" not in offer for offer in item["offers"]))
        detected = False
        for offer in item["offers"]:
            result = wave6.black_market_action(state, "inspecter:" + offer["id"])
            detected = detected or result["detected"]
        expected = any(not offer["authentic"] for offer in state["wave6"]["market"]["offers"])
        self.assertEqual(detected, expected)

    def test_every_market_contains_a_counterfeit_to_find(self):
        for index in range(20):
            state = {}
            wave6.black_market_status(state, f"marche-{index}")
            self.assertTrue(any(not offer["authentic"]
                                for offer in state["wave6"]["market"]["offers"]))

    def test_auction_is_resolved_against_a_named_rival(self):
        state = {}
        market = wave6.black_market_status(state, "enchere")
        lot = market["offers"][0]
        result = wave6.black_market_action(state, "encherir:" + lot["id"], "enchere")
        updated = next(offer for offer in result["offers"] if offer["id"] == lot["id"])
        self.assertEqual(updated["bids"], 1)
        self.assertIn(updated["rival"], ("Dame Suie", "Baron Minuit", "Comte Echo"))
        self.assertTrue(result["outbid"] or updated["bought"])


class PropheciesAndHouses(unittest.TestCase):
    def test_prophecy_uses_existing_progress(self):
        state = {}
        day = date(2026, 9, 7)
        prophecy = wave6.prophecy_status(state, day)
        self.assertEqual(prophecy["objective"], "train")
        LastTrain().finish_route(state, "cendre")
        item = wave6.resolve_prophecy(state, "accomplir", day)
        self.assertTrue(item["completed"])

    def test_three_distinct_failures_reveal_the_lost_station(self):
        state = {}
        day = date(2026, 9, 7)
        for index, reason in enumerate(wave6.PROPHECY_FAILURES):
            current = day + timedelta(days=index * 7)
            wave6.prophecy_status(state, current)
            item = wave6.resolve_prophecy(state, "echouer:" + reason, current)
        self.assertTrue(item["lost_station"])
        station = wave6.visit_lost_station(state, "monter")
        self.assertTrue(station["visited"])

    def test_house_reputation_uses_rotating_ceremonies(self):
        state = {}
        wave6.pledge_funeral_house(state, "airain")
        for _ in range(3):
            status = wave6.funeral_house_status(state)
            item = wave6.funeral_house_mission(state, status["mission"])
        self.assertEqual(item["reputation"], 3)


class MusicCreationAndSafety(unittest.TestCase):
    def test_musical_battle_can_be_countered_measure_by_measure(self):
        state = {}
        item = wave6.start_musical_battle(state, "solo")
        while item["active"]:
            item = wave6.musical_battle_action(state, item["cue"])
        self.assertTrue(item["won"])

    def test_mod_capsule_roundtrip_and_tamper_rejection(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = wave6.create_mod_capsule(Path(tmp), "Express des ombres", "train")
            item = wave6.validate_mod_capsule(path)
            self.assertTrue(item["valid"])
            envelope = json.loads(path.read_text(encoding="utf-8"))
            envelope["payload"]["manifest"]["entrypoints"] = ["evil.py"]
            path.write_text(json.dumps(envelope), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "invalide"):
                wave6.validate_mod_capsule(path)

    def test_exports_are_self_contained_html(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = {}
            wave6.recruit_spectral_crew(state, "controleuse")
            gazette = wave6.export_crypt_gazette(state, Path(tmp))
            replay = wave6.export_scene_replay(state, Path(tmp))
            for path in (gazette, replay):
                content = path.read_text(encoding="utf-8")
                self.assertIn("<!doctype html>", content)
                self.assertNotIn("https://", content)


class GreatSecret(unittest.TestCase):
    def complete_all_clues(self, state):
        LastTrain().finish_route(state, "cendre")
        for member in tuple(wave6.SPECTRAL_CREW)[:4]:
            wave6.recruit_spectral_crew(state, member)
        wave6.start_rail_case(state, "cloche")
        truth = state["wave6"]["rail_case"]["truth"]
        wave6.investigate_rail_case(state, "chercher")
        wave6.investigate_rail_case(state, "chercher")
        wave6.investigate_rail_case(state, "accuser:" + truth)
        for _ in range(3):
            wave6.dig_archaeology(state, "necropole")
        wave6.restore_artifact(state, "necropole")
        battle = wave6.start_musical_battle(state, "cloche")
        while battle["active"]:
            battle = wave6.musical_battle_action(state, battle["cue"])
        wave6.pledge_funeral_house(state, "airain")
        for _ in range(3):
            house = wave6.funeral_house_status(state)
            wave6.funeral_house_mission(state, house["mission"])

    def test_thirteenth_bell_requires_all_six_echoes(self):
        state = {}
        with self.assertRaisesRegex(ValueError, "echos"):
            wave6.ring_thirteenth_bell(state, "treize")
        self.complete_all_clues(state)
        item = wave6.ring_thirteenth_bell(state, "13")
        self.assertTrue(item["rung"])
        self.assertIn("wagon", item["epilogue"])


class Achievements(unittest.TestCase):
    IDENTIFIERS = {
        "conducteur_outre_tombe", "equipage_eternel", "limier_du_rail",
        "archeologue_interdit", "commissaire_reliques", "oracle_cendres",
        "gazettier_crypte", "virtuose_funebre", "heritier_funeraire",
        "moddeur_maudit", "cineaste_spectral", "treizieme_cloche",
        "gare_inexistante", "collectionneur_fragments", "roi_dernier_train",
    }

    def test_wave6_declares_fifteen_achievements(self):
        catalogue = {item.identifiant for item in succes.CATALOGUE}
        self.assertEqual(len(self.IDENTIFIERS), 15)
        self.assertTrue(self.IDENTIFIERS.issubset(catalogue))

    def test_events_unlock_every_wave6_achievement(self):
        cases = (
            ("ghost_train", {"arrived": True, "fresh": True, "routes": 1}, "conducteur_outre_tombe"),
            ("ghost_train", {"arrived": True, "fresh": True, "routes": 3}, "roi_dernier_train"),
            ("spectral_crew", {"complete": True}, "equipage_eternel"),
            ("rail_case", {"solved": True}, "limier_du_rail"),
            ("archaeology", {"restored": True, "fragments": 1}, "archeologue_interdit"),
            ("archaeology", {"restored": False, "fragments": 9}, "collectionneur_fragments"),
            ("black_market", {"detected": True}, "commissaire_reliques"),
            ("prophecy", {"completed": True}, "oracle_cendres"),
            ("crypt_gazette", {"exported": True}, "gazettier_crypte"),
            ("musical_battle", {"won": True}, "virtuose_funebre"),
            ("funeral_house", {"reputation": 3}, "heritier_funeraire"),
            ("mod_capsule", {"valid": True}, "moddeur_maudit"),
            ("train_replay", {"exported": True}, "cineaste_spectral"),
            ("thirteenth_bell", {"rung": True}, "treizieme_cloche"),
            ("lost_station", {"visited": True}, "gare_inexistante"),
        )
        for event, details, achievement in cases:
            with self.subTest(event=event, achievement=achievement):
                unlocked = succes.enregistrer({}, event, **details)
                self.assertIn(achievement, {item.identifiant for item in unlocked})


if __name__ == "__main__":
    unittest.main()
