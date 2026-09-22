"""Progression de l'apres-campagne et enigme finale."""

import copy
import unittest

from doot import after_dawn, wave6


def completed_state(ending="cendres", betrayed=True):
    return {
        "grand_retour": {
            "last_ending": ending, "last_betrayed": betrayed,
            "endings": ["aube", "veille", "cendres"],
            "run": {"night": 7, "completed": True, "ending": ending,
                    "betrayed": betrayed, "history": [], "clues": []},
        },
        "wave6": {"crew": list(after_dawn.CREW)},
        "wave4": {"city": {"bones": 3}, "nemesis": {"grudge": 5}},
    }


class AfterDawnTests(unittest.TestCase):
    def test_readers_do_not_mutate_state(self):
        state = {}
        before = copy.deepcopy(state)
        after_dawn.world_status(state)
        after_dawn.crew_status(state)
        after_dawn.door_status(state)
        after_dawn.carnet_lines(state)
        self.assertEqual(state, before)

    def test_world_choices_have_real_effects_once_per_ending(self):
        state = completed_state()
        after_dawn.choose_world(state, "cite", "rebatir")
        self.assertEqual(state["wave4"]["city"]["bones"], 7)
        after_dawn.choose_world(state, "nemesis", "apaiser")
        self.assertEqual(state["wave4"]["nemesis"]["grudge"], 4)
        after_dawn.choose_world(state, "rail", "charbon")
        self.assertEqual(state["after_dawn"]["rail_voucher"], "coal")
        train = wave6.start_ghost_train(state, "test", "lune")
        self.assertEqual(train["coal"], 14)
        self.assertNotIn("rail_voucher", state["after_dawn"])
        with self.assertRaises(ValueError):
            after_dawn.choose_world(state, "cite", "fortifier")
        self.assertEqual(state["wave4"]["city"]["bones"], 7)

    def test_crew_redemption_and_eighth_door(self):
        state = completed_state()
        for front, action in (("apparitions", "accueillir"), ("cite", "rebatir"),
                              ("rail", "blindage"), ("nemesis", "apaiser")):
            after_dawn.choose_world(state, front, action)
        for member in after_dawn.CREW:
            after_dawn.choose_mission(state, member, "soutenir")
        self.assertTrue(after_dawn.crew_status(state)["redeemed"])
        self.assertEqual(after_dawn.door_status(state)["found"], 8)
        with self.assertRaises(ValueError):
            after_dawn.solve_door(state, "soleil")
        self.assertTrue(after_dawn.solve_door(state, "mémoire")["solved"])
        self.assertIn("Le train repart", after_dawn.door_status(state)["epilogue"])

    def test_prerequisites_and_secrets_are_opt_in(self):
        state = completed_state()
        state["wave6"]["crew"] = []
        with self.assertRaises(ValueError):
            after_dawn.choose_mission(state, "chef", "soutenir")
        with self.assertRaises(ValueError):
            after_dawn.solve_door(state, "memoire")
        self.assertNotIn("La reponse", "\n".join(after_dawn.carnet_lines(state)))
        self.assertIn("La reponse", "\n".join(after_dawn.carnet_lines(state, secrets=True)))


if __name__ == "__main__":
    unittest.main()
