"""La vague 2 reste declarative, persistante et testable sans affichage."""

from __future__ import annotations

import tempfile
import unittest
import zipfile
from datetime import datetime
from pathlib import Path

from doot import adventure, choreography, live, packs, procedural, replay, rituals, succes


class CampagneEtBoss(unittest.TestCase):
    def test_la_campagne_garde_le_chemin_et_resout_la_clef(self):
        state = {}
        for choice in ("ecouter", "dooter", "ouvrir"):
            status = adventure.choose(state, choice)
        self.assertTrue(status["completed"])
        self.assertEqual(
            adventure.observe_riddles(state, "campagne"), ["clef_ossuaire"],
        )

    def test_un_boss_vaincu_reste_vaincu(self):
        state = {}
        while not adventure.hit_boss(state, 50, year=2026)["defeated"]:
            pass
        self.assertEqual(adventure.seasonal_boss(state, 2026)["hp"], 0)

    def test_combo_court_et_record(self):
        state = {}
        adventure.record_combo(state, "doots", datetime(2026, 9, 22, 12, 0, 0))
        combo = adventure.record_combo(state, "melodie", datetime(2026, 9, 22, 12, 0, 5))
        self.assertEqual((combo["count"], combo["best"]), (2, 2))
        reset = adventure.record_combo(state, "doots", datetime(2026, 9, 22, 12, 1, 0))
        self.assertEqual((reset["count"], reset["best"]), (1, 2))


class Enigmes(unittest.TestCase):
    def test_minuit_et_huit_voix_sont_deux_secrets_distincts(self):
        state = {}
        midnight = adventure.observe_riddles(
            state, "doots", datetime(2026, 10, 1, 0, 0, 42), quantite=1,
        )
        choir = adventure.observe_riddles(state, "melodie", voix=8)
        self.assertEqual(midnight, ["douzieme_coup"])
        self.assertEqual(choir, ["huitieme_voix"])

    def test_un_succes_secret_cache_son_titre_avant_de_tomber(self):
        definition = next(item for item in succes.CATALOGUE if item.identifiant == "miroir_funebre")
        self.assertEqual(succes.visible({}, definition)[0], "Succes secret")
        state = {"stats": {"enigmes_resolues": ["miroir_funebre"]},
                 "succes": {"miroir_funebre": "2026-09-22T12:00:00"}}
        self.assertEqual(succes.visible(state, definition)[0], "Le miroir funebre")

    def test_chaque_nouveau_succes_a_son_badge(self):
        ids = {
            "chasseur_boss", "conteur_crypte", "maitre_invasion", "archiviste_saisons",
            "chef_orchestre_live", "douzieme_coup", "miroir_funebre", "clef_ossuaire",
            "huitieme_voix",
        }
        for definition in succes.CATALOGUE:
            if definition.identifiant in ids:
                with self.subTest(definition.identifiant):
                    self.assertTrue(succes.badge(definition).is_file())


class Studios(unittest.TestCase):
    def test_melodie_procedurale_reproductible_et_valide(self):
        first = procedural.generate("macabre", "treize")
        self.assertEqual(first, procedural.generate("macabre", "treize"))
        self.assertIn(":d=16,o=5,b=92:", first)

    def test_choregraphie_aller_retour(self):
        with tempfile.TemporaryDirectory() as directory:
            path = choreography.save(Path(directory), "Bal", [
                {"at": 2.5, "count": 4, "formation": "wave"},
                {"at": 0, "count": 1, "formation": "random"},
            ])
            name, cues = choreography.load(path)
            self.assertEqual(name, "Bal")
            self.assertEqual([cue.at for cue in cues], [0, 2.5])

    def test_studio_live_quantifie_au_seizieme(self):
        pattern = live.quantize([live.Hit(0, "c"), live.Hit(.13, "d")], tempo=120)
        self.assertEqual(pattern[:2], ["c", "d"])

    def test_replay_est_un_html_autonome(self):
        with tempfile.TemporaryDirectory() as directory:
            path = replay.export([{"kind": "doots", "count": 3}], Path(directory))
            source = path.read_text(encoding="utf-8")
            self.assertIn("setInterval", source)
            self.assertIn("doots", source)


class PlanificationsEtPacks(unittest.TestCase):
    def test_un_rituel_ne_tombe_qu_une_fois_par_jour(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rituals.json"
            rituals.add(path, "reveil", "08:13")
            now = datetime(2026, 9, 22, 8, 14)
            self.assertEqual(len(rituals.due(path, now)), 1)
            self.assertEqual(rituals.due(path, now), [])

    def test_un_pack_v2_est_signe_et_verifie(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source" / "melodies").mkdir(parents=True)
            (root / "source" / "melodies" / "os.rtttl").write_text(
                "os:d=4,o=5,b=120:c", encoding="utf-8",
            )
            archive = packs.export(root / "source", root, "Nuit", author="Doot")
            metadata = packs.inspect(archive)
            self.assertTrue(metadata["verified"])
            self.assertEqual(metadata["author"], "Doot")

    def test_une_signature_modifiee_est_refusee(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source" / "melodies").mkdir(parents=True)
            source = root / "source" / "melodies" / "os.rtttl"
            source.write_text("os:d=4,o=5,b=120:c", encoding="utf-8")
            archive = packs.export(root / "source", root, "Nuit")
            with zipfile.ZipFile(archive, "a") as opened:
                opened.writestr("melodies/os.rtttl", "truque")
            with self.assertRaisesRegex(ValueError, "empreinte invalide"):
                packs.inspect(archive)


if __name__ == "__main__":
    unittest.main()
