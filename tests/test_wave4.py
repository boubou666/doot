"""La vague 4 reste locale, reproductible et portable."""

from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from datetime import date
from pathlib import Path

from doot import png, succes, wave4


class CityAndBuilds(unittest.TestCase):
    def test_city_is_persistent_and_spends_bones(self):
        state = {}
        before = wave4.city_status(state)
        after = wave4.develop_city(state, "crypte")
        self.assertEqual(after["level"], 1)
        self.assertEqual(after["bones"], before["bones"] - 2)

    def test_relics_toggle_and_limit_slots(self):
        state = {}
        first = wave4.equip_relic(state, "metronome_fendu")
        self.assertEqual(first["equipped"], ["metronome_fendu"])
        second = wave4.equip_relic(state, "metronome_fendu")
        self.assertEqual(second["equipped"], [])


class FactionsAndNemesis(unittest.TestCase):
    def test_faction_mission_rewards_city(self):
        state = {}
        wave4.pledge_faction(state, "airain")
        item = wave4.faction_mission(state, "fixe")
        self.assertGreater(item["reputation"], 0)
        self.assertGreater(wave4.city_status(state)["bones"], 12)

    def test_nemesis_can_return_with_more_health(self):
        state = {}
        foe = wave4.nemesis_status(state, "fixe")
        while not foe["defeated"]:
            foe = wave4.confront_nemesis(state, foe["weakness"])
        maximum = foe["max_hp"]
        returned = wave4.confront_nemesis(state, foe["weakness"])
        self.assertEqual(returned["grudge"], 1)
        self.assertEqual(returned["max_hp"], maximum + 6)


class InvestigationsAndGhosts(unittest.TestCase):
    def test_investigation_collects_clues_and_solves(self):
        state = {}
        item = wave4.start_investigation(state, "loge")
        for _ in range(3):
            item = wave4.investigate(state, "chercher")
        culprit = state["wave4"]["investigation"]["culprit"]
        item = wave4.investigate(state, "accuser:" + culprit)
        self.assertTrue(item["solved"])
        self.assertFalse(item["active"])

    def test_ghost_is_verified_and_race_is_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = wave4.export_ghost({"seed": "x", "time_ms": 1000,
                                       "decisions": ["audace"]}, Path(tmp))
            state = {}
            result = wave4.race_ghost(state, path, 900)
            self.assertTrue(result["won"])
            envelope = json.loads(path.read_text(encoding="utf-8"))
            envelope["payload"]["time_ms"] = 5
            path.write_text(json.dumps(envelope), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "invalide"):
                wave4.race_ghost(state, path, 1)


class CreativeTools(unittest.TestCase):
    def test_adaptive_score_reacts(self):
        calm = wave4.adaptive_score({}, 0, 0, False)
        danger = wave4.adaptive_score({}, 10, 20, True)
        self.assertGreater(danger["tempo"], calm["tempo"])
        self.assertGreater(danger["stems"]["choir"], calm["stems"]["choir"])

    def test_html_exports_are_self_contained(self):
        with tempfile.TemporaryDirectory() as tmp:
            director = wave4.director_studio(Path(tmp))
            stars = wave4.narrative_constellation({}, Path(tmp))
            for path in (director, stars):
                content = path.read_text(encoding="utf-8")
                self.assertIn("<!doctype html>", content)
                self.assertNotIn("https://", content)

    def test_photo_booth_writes_real_png(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = {}
            path = wave4.photo_booth(state, Path(tmp), "fanfare")
            self.assertEqual(png.size(path), (256, 256))
            self.assertEqual(state["wave4"]["last_photo"]["pose"], "fanfare")

    def test_remote_card_contains_scannable_qr_and_token(self):
        with tempfile.TemporaryDirectory() as tmp:
            item = wave4.remote_card("192.168.1.7", 8765, Path(tmp), "secret")
            content = item["path"].read_text(encoding="utf-8")
            self.assertIn("<svg", content)
            self.assertIn("192.168.1.7:8765", content)
            self.assertIn("token=secret", item["url"])


class WorkshopAndSecrets(unittest.TestCase):
    def test_workshop_accepts_manifest_and_rejects_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            good = Path(tmp) / "good.zip"
            with zipfile.ZipFile(good, "w") as archive:
                archive.writestr("manifest.json", '{"format":"doot-pack-v2"}')
                archive.writestr("melodies/a.rtttl", "a:d=4,o=5,b=90:c")
            self.assertTrue(wave4.validate_workshop(good)["valid"])
            bad = Path(tmp) / "bad.zip"
            with zipfile.ZipFile(bad, "w") as archive:
                archive.writestr("manifest.json", '{"format":"doot-pack-v2"}')
                archive.writestr("../escape", "boo")
            self.assertFalse(wave4.validate_workshop(bad)["valid"])

    def test_calendar_is_reproducible(self):
        today = date(2026, 10, 13)
        self.assertEqual(wave4.seasonal_calendar(today), wave4.seasonal_calendar(today))

    def test_all_glyphs_unlock_secret(self):
        state = {}
        result = None
        for glyph, word in wave4.GLYPHS.items():
            result = wave4.decipher_glyph(state, glyph, word)
        self.assertTrue(result["complete"])

    def test_mirror_boss_uses_dominant_style(self):
        state = {"stats": {"melodies": {"local": 20}, "doots": {"local": 3}}}
        boss = wave4.mirror_boss(state)
        self.assertEqual(boss["style"], "virtuose")


class Achievements(unittest.TestCase):
    def test_each_wave4_achievement_has_a_badge_name(self):
        identifiers = {
            "architecte_osseux", "maitre_reliquaire", "ambassadeur_crypte",
            "rancune_eternelle", "enqueteur_paranormal", "ombre_chronometree",
            "maestro_adaptatif", "realisateur_outre_tombe", "gardien_atelier",
            "miroir_noir", "langue_des_morts",
        }
        self.assertTrue(identifiers.issubset({item.identifiant for item in succes.CATALOGUE}))

    def test_events_unlock_progress(self):
        events = (
            ("city", {"level": 1}), ("relic_build", {"equipped": 1}),
            ("faction", {"reputation": 2}), ("nemesis", {"defeated": True}),
            ("investigation", {"solved": True}), ("ghost_race", {"won": True}),
            ("adaptive_score", {"intensity": .7}), ("director", {"exported": True}),
            ("workshop", {"valid": True}), ("mirror_boss", {"generated": True}),
            ("glyphs", {"completed": True}),
        )
        state = {}
        unlocked = []
        for event, details in events:
            unlocked.extend(succes.enregistrer(state, event, **details))
        self.assertEqual(len([item for item in unlocked if item.identifiant in {
            "architecte_osseux", "maitre_reliquaire", "ambassadeur_crypte",
            "rancune_eternelle", "enqueteur_paranormal", "ombre_chronometree",
            "maestro_adaptatif", "realisateur_outre_tombe", "gardien_atelier",
            "miroir_noir", "langue_des_morts"}]), 11)


if __name__ == "__main__":
    unittest.main()
