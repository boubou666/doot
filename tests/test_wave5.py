"""La vague 5 relie les systemes avances sans reseau."""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from doot import succes, wave4, wave5


class CatacombsAndMemory(unittest.TestCase):
    def test_catacomb_map_is_reproducible_and_records_path(self):
        self.assertEqual(wave5.catacomb_map("route"), wave5.catacomb_map("route"))
        state = {}
        wave5.start_catacomb(state, "route")
        item = wave5.choose_catacomb(state, "gauche")
        self.assertEqual(item["room"], 1)
        self.assertEqual(item["path"][0]["choice"], "gauche")
        self.assertEqual(len(wave5.bestiary_status(state)["found"]), 1)

    def test_time_loop_requires_the_three_actions_in_order(self):
        state = {}
        wave5.advance_time_loop(state, "courir")
        self.assertEqual(wave5.time_loop_status(state)["iteration"], 2)
        for action in wave5.LOOP_SEQUENCE:
            item = wave5.advance_time_loop(state, action)
        self.assertTrue(item["broken"])


class CompanionsAndCollection(unittest.TestCase):
    def test_familiar_unlock_uses_existing_bond(self):
        state = {"wave3": {"familiar": {"id": "corbeau", "bond": 5}}}
        item = wave5.unlock_familiar_skill(state, "oeil des reliques")
        self.assertIn("oeil des reliques", item["unlocked"])

    def test_bestiary_and_forge_are_persistent(self):
        state = {}
        for creature in ("veilleur", "cantatrice", "mange-lune"):
            wave5.observe_creature(state, creature)
        self.assertEqual(len(wave5.bestiary_status(state)["found"]), 3)
        first = wave5.forge_relic(state, "cendre", "tibia")
        second = wave5.forge_relic(state, "tibia", "cendre")
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(second["total"], 1)

    def test_weather_is_reproducible(self):
        day = date(2026, 10, 31)
        self.assertEqual(wave5.paranormal_weather(day, 7),
                         wave5.paranormal_weather(day, 7))
        state = {}
        item = wave5.witness_weather(state, day)
        self.assertEqual(item["unique"], 1)

    def test_weather_changes_existing_music_and_forge_systems(self):
        storm = {"wave5": {"active_weather": {"id": "orage_silencieux"}}}
        self.assertEqual(wave4.adaptive_score(storm, 6, 8)["stems"]["bones"], 0)
        rain = {"wave5": {"active_weather": {"id": "pluie_os"}}}
        normal = wave5.forge_relic({}, "cendre", "tibia")
        boosted = wave5.forge_relic(rain, "cendre", "tibia")
        self.assertEqual(boosted["power"], normal["power"] + 1)


class SocialAndNarrative(unittest.TestCase):
    def test_ritual_capsule_merges_and_rejects_tampering(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = {}
            for index in range(3):
                wave5.offer_ritual_fragment(state, f"fragment-{index}", "a")
            path = wave5.export_ritual(state, Path(tmp))
            remote = {}
            item = wave5.import_ritual(remote, path)
            self.assertEqual(len(item["fragments"]), 3)
            envelope = json.loads(path.read_text(encoding="utf-8"))
            envelope["payload"]["fragments"].append("fraude")
            path.write_text(json.dumps(envelope), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "invalide"):
                wave5.import_ritual({}, path)

    def test_nemesis_invasion_reaches_a_persistent_outcome(self):
        state = {}
        wave5.nemesis_invasion_status(state, "siege")
        for action in wave5.INVASION_ACTIONS:
            item = wave5.defend_nemesis_invasion(state, action)
        self.assertTrue(item["completed"])
        self.assertTrue(item["repelled"])

    def test_tribunal_reveals_clues_and_records_verdict(self):
        state = {}
        wave5.start_tribunal(state, "affaire")
        item = wave5.tribunal_action(state, "examiner")
        self.assertEqual(len(item["found"]), 1)
        truth = state["wave5"]["tribunal"]["truth"]
        item = wave5.tribunal_action(state, "juger:" + truth)
        self.assertTrue(item["just"])
        self.assertIn("justice", item["consequence"])
        self.assertEqual(wave4.city_status(state)["bones"], 14)

    def test_ng_plus_legacy_requires_and_remembers_a_choice(self):
        with self.assertRaisesRegex(ValueError, "Nouvelle Partie"):
            wave5.choose_legacy({}, "memoire")
        state = {"wave3": {"new_game_plus": 2}}
        item = wave5.choose_legacy(state, "memoire")
        self.assertEqual(item["level"], 2)
        self.assertIn("memoire", item["choices"])


class CreationAndSecrets(unittest.TestCase):
    def test_campaign_validator_checks_graph_targets(self):
        with tempfile.TemporaryDirectory() as tmp:
            good = Path(tmp) / "good.json"
            good.write_text(json.dumps({"format": "doot-campaign-v1", "chapters": [
                {"id": "appel", "choices": ["ouvrir:fin"]},
            ]}), encoding="utf-8")
            self.assertTrue(wave5.validate_campaign(good)["valid"])
            bad = Path(tmp) / "bad.json"
            bad.write_text(json.dumps({"format": "doot-campaign-v1", "chapters": [
                {"id": "appel", "choices": ["ouvrir:absent"]},
            ]}), encoding="utf-8")
            self.assertFalse(wave5.validate_campaign(bad)["valid"])

    def test_studios_export_self_contained_html(self):
        with tempfile.TemporaryDirectory() as tmp:
            lab = wave5.campaign_lab(Path(tmp))
            museum = wave5.museum_gallery({}, succes.CATALOGUE, Path(tmp))
            for path in (lab, museum):
                content = path.read_text(encoding="utf-8")
                self.assertIn("<!doctype html>", content)
                self.assertNotIn("https://", content)

    def test_all_seals_open_the_secret_epilogue(self):
        state = {}
        for seal, definition in wave5.SEALS.items():
            item = wave5.submit_seal(state, seal, definition[2])
        self.assertTrue(item["complete"])
        self.assertIn("huitieme porte", item["epilogue"])

    def test_each_wave5_achievement_declares_a_unique_badge(self):
        identifiers = {
            "cartographe_abime", "horloger_maudit", "compagnon_ascendant",
            "naturaliste_outre_tombe", "forgeron_maudit", "meteorologue_occulte",
            "ritualiste_collectif", "assiegeur_nemesis", "juge_des_morts",
            "memoire_eternelle", "dramaturge_interdit", "conservateur_ombres",
            "septieme_sceau",
        }
        self.assertTrue(identifiers.issubset({item.identifiant for item in succes.CATALOGUE}))
        self.assertEqual(len(identifiers), 13)


class AchievementEvents(unittest.TestCase):
    def test_wave5_events_unlock_their_achievements(self):
        cases = (
            ("catacomb_victory", {"won": True}, "cartographe_abime"),
            ("time_loop", {"broken": True}, "horloger_maudit"),
            ("familiar_skill", {"unlocked": True}, "compagnon_ascendant"),
            ("bestiary", {"found": 3}, "naturaliste_outre_tombe"),
            ("necroforge", {"crafted": True}, "forgeron_maudit"),
            ("paranormal_weather", {"witnessed": True}, "meteorologue_occulte"),
            ("collective_ritual", {"completed": True}, "ritualiste_collectif"),
            ("nemesis_invasion", {"repelled": True}, "assiegeur_nemesis"),
            ("tribunal", {"verdict": True}, "juge_des_morts"),
            ("legacy", {"chosen": True}, "memoire_eternelle"),
            ("campaign_validate", {"valid": True}, "dramaturge_interdit"),
            ("personal_museum", {"exported": True}, "conservateur_ombres"),
            ("seven_seals", {"completed": True}, "septieme_sceau"),
        )
        for event, details, achievement in cases:
            with self.subTest(event=event):
                state = {}
                unlocked = succes.enregistrer(state, event, **details)
                self.assertIn(achievement, {item.identifiant for item in unlocked})


if __name__ == "__main__":
    unittest.main()
