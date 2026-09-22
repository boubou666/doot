"""Le studio macabre, les horaires, packs et defis."""

from __future__ import annotations

import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from doot import (
    challenges, cli, composer, contagion, content, evenements, history, packs,
    profiles, schedule,
)


class Horaires(unittest.TestCase):
    def test_plage_de_nuit(self):
        self.assertTrue(schedule.contains("22:00-07:00", datetime(2026, 9, 22, 23, 0)))
        self.assertTrue(schedule.contains("22:00-07:00", datetime(2026, 9, 22, 6, 0)))
        self.assertFalse(schedule.contains("22:00-07:00", datetime(2026, 9, 22, 12, 0)))

    def test_profils_planifies(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profiles.json"
            profiles.save(path, "bureau", {"quiet_hours": "09:00-17:00"})
            profiles.schedule_profile(path, "bureau", "09:00-17:00", "lun,mar")
            self.assertEqual(profiles.scheduled(path, datetime(2026, 9, 22, 10, 0)), "bureau")
            self.assertIsNone(profiles.scheduled(path, datetime(2026, 9, 23, 10, 0)))

    def test_le_daemon_peut_revenir_a_sa_configuration_de_base(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profiles.json"
            profiles.save(path, "bureau", {"volume": 0.1})
            args = cli.build_parser().parse_args(["--volume", "0.8"])
            base = profiles.from_namespace(args)
            with mock.patch.object(cli, "profiles_path", return_value=path), \
                    mock.patch.object(profiles, "scheduled", side_effect=["bureau", None]):
                cli._apply_profile_schedule(args, base)
                self.assertEqual(args.volume, 0.1)
                cli._apply_profile_schedule(args, base)
                self.assertEqual(args.volume, 0.8)


class Preferences(unittest.TestCase):
    def test_zero_masque_et_trois_favorise(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "content.json"
            content.set_weight(path, "events", "mimic", 0)
            content.set_weight(path, "events", "parade", 3)
            document = content.read(path)
            self.assertEqual(content.weight(document, "events", "mimic"), 0)
            self.assertEqual(content.weight(document, "events", "parade"), 3)


class Studio(unittest.TestCase):
    def test_partition_multivoix_et_durees(self):
        score = composer.empty_score(2)
        score[0][0], score[1][0] = "c", "e"
        composer.set_duration(score[0], 0, 4)
        text = composer.rtttl_score("duo", 120, 5, score)
        self.assertEqual(len(text.strip().splitlines()), 2)
        self.assertIn("4c", text)

    def test_partition_sauvee_se_recharge_et_une_voix_se_copie(self):
        with tempfile.TemporaryDirectory() as directory:
            score = composer.empty_score(2)
            score[0][0], score[1][3] = "c#", "g"
            path = composer.write_score(Path(directory) / "duo.rtttl", "duo", 98, 4, score)
            title, tempo, octave, loaded = composer.load_score(path)
            self.assertEqual((title, tempo, octave), ("duo", 98, 4))
            self.assertEqual(loaded, score)
            self.assertEqual(composer.copy_voice(loaded[0]), loaded[0])

    def test_source_multivoix_rejoint_la_grille(self):
        score = composer.empty_score(2)
        score[0][0], score[1][4] = ("c", 4), "g"
        source = composer.rtttl_score("duo", 110, 5, score)
        self.assertEqual(composer.parse_score(source)[3], score)

    def test_rencontre_personnelle_rechargeable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = evenements.save(root, "bal", "Le bal", "Danse", formation="wave",
                                    count=6, delay=.1, duration=2.8)
            self.assertTrue(path.is_file())
            self.assertEqual(evenements.find("bal", root).quantite, 6)


class MemoireEtDefis(unittest.TestCase):
    def test_historique_borne_l_affichage(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "history.jsonl"
            history.append(path, "doots", count=2)
            history.append(path, "melody", name="rickroll")
            self.assertEqual([item["kind"] for item in history.read(path, 1)], ["melody"])

    def test_defi_deterministe_et_completion(self):
        day = date(2026, 9, 22)
        self.assertEqual(challenges.daily(day), challenges.daily(day))
        challenge = challenges.daily(day)
        state = {}
        now = datetime(2026, 9, 22, 12, 0)
        if challenge.kind == "formation":
            completed = challenges.record(state, "formation", formation=challenge.formation, now=now)
        else:
            completed = challenges.record(state, challenge.kind, amount=challenge.target, now=now)
        self.assertTrue(completed)


class Packs(unittest.TestCase):
    def test_aller_retour_sans_ecrasement(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            source, target = base / "source", base / "target"
            (source / "melodies").mkdir(parents=True)
            (source / "melodies" / "os.rtttl").write_text("os:d=4,o=5,b=120:c", encoding="utf-8")
            archive = packs.export(source, base, "Nuit")
            name, installed = packs.install(archive, target)
            self.assertEqual(name, "Nuit")
            self.assertEqual([path.name for path in installed], ["os.rtttl"])
            _name, installed_again = packs.install(archive, target)
            self.assertEqual(installed_again[0].name, "os-2.rtttl")


class ParadeDeFlotte(unittest.TestCase):
    def test_parade_horodatee_sans_casser_les_anciens_signaux(self):
        now = datetime(2026, 9, 22, 12, 0, tzinfo=timezone.utc)
        ordinary = contagion.creer("fixe", now=now, token="simple")
        self.assertEqual(set(ordinary), {"id", "source", "emis"})
        parade = contagion.creer(
            "fixe", now=now, token="parade", kind="parade", name="rickroll",
            execute_at=now + timedelta(seconds=35),
        )
        self.assertTrue(contagion.valide(parade, now))
        self.assertEqual((parade["kind"], parade["name"]), ("parade", "rickroll"))


if __name__ == "__main__":
    unittest.main()
