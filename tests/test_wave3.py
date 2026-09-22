"""La vague 3 reste reproductible, portable et jouable sans reseau."""

from __future__ import annotations

import json
import tempfile
import unittest
import wave
from datetime import date
from pathlib import Path

from doot import wave3


class Expeditions(unittest.TestCase):
    def test_route_reproductible_et_boss_final(self):
        first = wave3.expedition_rooms("treize")
        self.assertEqual(first, wave3.expedition_rooms("treize"))
        self.assertEqual(len(first), 7)
        self.assertEqual(first[-1]["kind"], "boss")

    def test_une_route_peut_etre_terminee(self):
        state = {}
        wave3.start_expedition(state, "route-sure")
        status = None
        for _ in range(7):
            status = wave3.choose_expedition(state, "prudence")
            if status["completed"]:
                break
        self.assertTrue(status["completed"])
        self.assertLessEqual(status["room"], 7)

    def test_boss_a_trois_phases_et_un_epilogue(self):
        self.assertEqual(wave3.boss_phase({"hp": 100, "max_hp": 100})["number"], 1)
        self.assertEqual(wave3.boss_phase({"hp": 50, "max_hp": 100})["number"], 2)
        self.assertEqual(wave3.boss_phase({"hp": 10, "max_hp": 100})["number"], 3)
        self.assertEqual(wave3.boss_phase({"hp": 0, "max_hp": 100})["number"], 4)


class CreationEtExports(unittest.TestCase):
    def test_editeur_pack_constellation_et_gif_sont_autonomes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            editor = wave3.campaign_editor(root)
            self.assertIn("Exporter le pack JSON", editor.read_text(encoding="utf-8"))

            campaign = root / "campaign.json"
            campaign.write_text(json.dumps({
                "format": "doot-campaign-v1",
                "chapters": [{"id": "un", "choices": ["fin"]}],
            }), encoding="utf-8")
            self.assertTrue(wave3.campaign_pack(campaign, root / "packs").is_file())

            class Achievement:
                identifiant = "premier"
                titre = "Premier"
                secret = False
                points = 5

            sky = wave3.constellation({"succes": {"premier": "date"}},
                                      [Achievement()], root)
            self.assertIn("Constellation", sky.read_text(encoding="utf-8"))
            gif = wave3.replay_gif([{"kind": "doots"}], root)
            self.assertEqual(gif.read_bytes()[:6], b"GIF89a")
            self.assertEqual(gif.read_bytes()[-1:], b";")

    def test_studio_dj_decoupe_un_wav(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "sample.wav"
            with wave.open(str(source), "wb") as opened:
                opened.setparams((1, 1, 8000, 8000, "NONE", "raw"))
                opened.writeframes(bytes(8000))
            metadata = wave3.dj_import(source, root / "dj", 8)
            payload = json.loads(metadata.read_text(encoding="utf-8"))
            self.assertEqual(len(payload["slices"]), 8)
            self.assertEqual(payload["duration"], 1)


class ProgressionSociale(unittest.TestCase):
    def test_familier_evolue_et_contrat_se_partage_chiffre(self):
        state = {}
        for _ in range(5):
            familiar = wave3.bond_familiar(state, "doot")
        self.assertEqual(familiar["level"], 2)

        target = wave3.daily_contract(date.today())["target"]
        wave3.add_contract_progress(state, target, "crane-a")
        with tempfile.TemporaryDirectory() as directory:
            capsule = wave3.contract_capsule(state, Path(directory))
            other = {}
            result = wave3.join_contract(other, capsule)
        self.assertTrue(result["completed"])
        self.assertIn("crane-a", result["contributors"])

    def test_chasse_new_game_plus_coop_et_nuit(self):
        state = {"adventure": {"completed_at": "2026-09-22T12:00:00", "chapter": 3}}
        for code, _hint in wave3.HUNT_CODES:
            result = wave3.submit_code(state, code.lower())
        self.assertTrue(result["completed"])
        self.assertEqual(wave3.new_game_plus(state), 1)
        self.assertNotIn("chapter", state["adventure"])

        wave3.coop_action(state, "start")
        for action in ("musique", "scene", "musique", "scene"):
            coop = wave3.coop_action(state, action)
        self.assertEqual(coop["score"], 4)

        night = wave3.endless_night(state, "finale")
        for _ in range(5):
            night = wave3.endless_night(state)
        self.assertTrue(night["completed"])

    def test_personnage_pack_radio_et_ambiance(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            character = wave3.save_character(root / "characters", "Lord Femur",
                                              costume="smoking", instrument="saxophone")
            self.assertEqual(wave3.characters(root / "characters")[0]["name"], "Lord Femur")
            self.assertTrue(wave3.character_pack(character, root / "packs").is_file())
        self.assertEqual(len(wave3.radio_schedule("minuit")), 5)
        self.assertTrue(wave3.ambience({}, "oled")["oled"])


if __name__ == "__main__":
    unittest.main()
