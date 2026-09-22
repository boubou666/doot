"""La campagne des sept nuits et ses liens avec les modes precedents."""

from __future__ import annotations

import copy
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from doot import cli, grand_retour, succes


class GrandRetour(unittest.TestCase):
    def play(self, state, choices):
        grand_retour.start(state)
        item = None
        for choice in choices:
            item = grand_retour.choose(state, choice)
        return item

    def test_seven_nights_and_resume_are_persistent(self):
        state = {}
        first = grand_retour.start(state)
        self.assertEqual(first["night"], 1)
        grand_retour.choose(state, "proteger")
        restored = copy.deepcopy(state)
        self.assertEqual(grand_retour.start(restored)["night"], 2)
        item = self.play(restored, ["ecouter", "accueillir", "partager",
                                    "pardonner", "harmoniser", "ouvrir"])
        self.assertTrue(item["completed"])
        self.assertEqual(item["ending"], "aube")
        self.assertEqual(item["companion"], "fidele")
        self.assertEqual(len(item["history"]), 7)
        self.assertEqual(len(item["clues"]), 7)

    def test_three_endings_survive_replays(self):
        state = {}
        for choice, ending in (("ouvrir", "aube"), ("garder", "veille"),
                               ("briser", "cendres")):
            grand_retour.start(state, restart=bool(state.get("grand_retour")))
            item = self.play(state, ["proteger", "ecouter", "accueillir",
                                     "partager", "pardonner", "harmoniser", choice])
            self.assertEqual(item["ending"], ending)
        self.assertEqual(item["endings"], ["aube", "cendres", "veille"])
        with self.assertRaisesRegex(ValueError, "terminee"):
            grand_retour.choose(state, "ouvrir")

    def test_cross_system_choices_need_real_progress(self):
        state = {}
        grand_retour.start(state)
        before = copy.deepcopy(state)
        with self.assertRaisesRegex(ValueError, "train"):
            grand_retour.choose(state, "guider")
        self.assertEqual(state, before)
        state["wave6"] = {"completed_routes": ["lune"], "crew": ["controleuse", "chef"],
                          "house": {"id": "airain", "reputation": 1},
                          "battle": {"won": True}}
        state["wave4"] = {"city": {"buildings": {"crypte": 1}},
                          "nemesis": {"scars": ["fissure-canon"]}}
        for choice in ("guider", "confier", "mobiliser", "invoquer",
                       "nommer", "repondre", "ouvrir"):
            item = grand_retour.choose(state, choice)
        self.assertEqual(item["ending"], "aube")
        self.assertEqual(len(item["clues"]), 7)

    def test_betrayal_changes_scene_and_end(self):
        state = {}
        grand_retour.start(state)
        grand_retour.choose(state, "forcer")
        grand_retour.choose(state, "ordonner")
        item = grand_retour.status(state)
        self.assertEqual(item["companion"], "en rupture")
        self.assertIn("quitter", item["scene"])
        for choice in ("barricader", "marchander", "frapper", "couvrir", "ouvrir"):
            item = grand_retour.choose(state, choice)
        self.assertEqual(item["ending"], "cendres")
        self.assertTrue(item["betrayed"])
        self.assertEqual(item["companion"], "traitre")

    def test_secret_requires_all_clues_loyalty_and_answer(self):
        state = {}
        self.play(state, ["proteger", "ecouter", "accueillir", "partager",
                          "pardonner", "harmoniser", "ouvrir"])
        self.assertTrue(grand_retour.secret_status(state)["ready"])
        with self.assertRaisesRegex(ValueError, "reponse"):
            grand_retour.solve_secret(state, "minuit")
        item = grand_retour.solve_secret(state, "aube")
        self.assertTrue(item["solved"])
        self.assertIn("sans conducteur", item["epilogue"])
        self.assertIn("FIN SECRETE", "\n".join(grand_retour.journal_lines(state)))
        grand_retour.start(state, restart=True)
        self.assertTrue(grand_retour.secret_status(state)["solved"])
        self.assertFalse(grand_retour.status(state)["secret_this_run"])

    def test_journal_export_escapes_state_and_has_no_remote_assets(self):
        state = {}
        grand_retour.start(state)
        state["grand_retour"]["run"]["history"] = [
            {"night": 1, "text": "<script>alert(1)</script>"}
        ]
        before = copy.deepcopy(state)
        with tempfile.TemporaryDirectory() as root:
            output = grand_retour.export_journal(state, Path(root) / "journal.html")
            content = output.read_text(encoding="utf-8")
        self.assertIn("&lt;script&gt;", content)
        self.assertNotIn("<script>", content)
        self.assertIn("prefers-reduced-motion", content)
        self.assertNotIn("https://", content)
        self.assertEqual(state, before)

    def test_partial_saved_state_recovers_without_losing_the_campaign(self):
        state = {}
        grand_retour.start(state)
        state["grand_retour"]["run"]["history"] = "ancienne valeur"
        state["grand_retour"]["run"]["clues"] = None
        state["grand_retour"]["endings"] = "anciennes fins"
        item = grand_retour.choose(state, "proteger")
        self.assertEqual(item["night"], 2)
        self.assertEqual(len(item["history"]), 1)
        self.assertEqual(item["clues"], [1])

    def test_four_achievements_have_distinct_images(self):
        names = {"veilleur_sept_nuits", "lien_indefectible",
                 "trois_destins", "aube_cachee"}
        catalog = {item.identifiant: item for item in succes.CATALOGUE}
        self.assertTrue(names.issubset(catalog))
        self.assertEqual(len({succes.badge(catalog[name]) for name in names}), 4)
        for name in names:
            self.assertTrue(succes.badge(catalog[name]).is_file(), name)
        state = {}
        unlocked = succes.enregistrer(state, "grand_retour", completed=True,
                                     loyal=True, endings=3)
        unlocked += succes.enregistrer(state, "grand_retour_secret", solved=True)
        self.assertTrue(names.issubset({item.identifiant for item in unlocked}))

    def test_cli_starts_and_advances_the_same_saved_state(self):
        state = {}
        with patch.object(cli, "read_state", return_value=state), \
             patch.object(cli, "write_state") as save, \
             patch.object(cli.profiles, "active", return_value=None), \
             redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(["--grand-retour"]), 0)
            self.assertEqual(cli.main(["--grand-retour-choose", "proteger"]), 0)
        self.assertEqual(grand_retour.status(state)["night"], 2)
        self.assertEqual(save.call_count, 2)


if __name__ == "__main__":
    unittest.main()
