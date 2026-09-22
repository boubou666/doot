"""Classement de duel partageable et idempotent."""

from __future__ import annotations

import unittest
from datetime import datetime

from doot import duel, partage


class Classement(unittest.TestCase):
    def test_enregistre_doots_et_un_special_par_rencontre(self):
        state = {"machine": "oscar"}
        duel.set_name(state, "Oscar")
        duel.record(state, 6, special=True, now=datetime(2026, 9, 22))
        row = duel.standings(state, 2026)[0]
        self.assertEqual((row.name, row.doots, row.specials), ("Oscar", 6, 1))

    def test_classe_par_doots_puis_speciaux(self):
        state = {
            "duel": {
                "names": {"a": "Alice", "b": "Bob", "c": "Cathy"},
                "seasons": {"2026": {
                    "a": {"doots": 5, "specials": 1},
                    "b": {"doots": 8, "specials": 0},
                    "c": {"doots": 5, "specials": 3},
                }},
            },
        }
        self.assertEqual([row.name for row in duel.standings(state, 2026)],
                         ["Bob", "Cathy", "Alice"])

    def test_fusion_idempotente_prend_les_maxima(self):
        local = {"duel": {"seasons": {"2026": {
            "a": {"doots": 3, "specials": 1},
        }}}}
        remote = {"duel": {"seasons": {"2026": {
            "a": {"doots": 7, "specials": 1},
            "b": {"doots": 4, "specials": 2},
        }}}}
        duel.merge(local, remote)
        duel.merge(local, remote)
        rows = duel.standings(local, 2026)
        self.assertEqual([(row.machine, row.doots) for row in rows], [("a", 7), ("b", 4)])

    def test_apres_octobre_prepare_la_saison_suivante(self):
        self.assertEqual(duel.season_year(datetime(2026, 11, 1)), 2027)

    def test_le_classement_voyage_dans_une_part(self):
        state = {"machine": "oscar"}
        duel.set_name(state, "Oscar")
        duel.record(state, 3, now=datetime(2026, 9, 22))
        part = partage.part_exportable(state)
        self.assertEqual(part["duel"], state["duel"])

        other = {"machine": "victor"}
        duel.merge(other, part)
        self.assertEqual(duel.standings(other, 2026)[0].name, "Oscar")


if __name__ == "__main__":
    unittest.main()
