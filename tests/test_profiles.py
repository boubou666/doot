"""Stockage robuste et strict des profils persistants."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from doot import profiles


class Profils(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "profiles.json"

    def tearDown(self):
        self.temp.cleanup()

    def test_cycle_de_vie(self):
        profiles.save(self.path, "chaos", {"formation": "vortex", "burst_min": 4})
        self.assertEqual(profiles.load(self.path, "chaos")["formation"], "vortex")
        profiles.activate(self.path, "chaos")
        self.assertEqual(profiles.active(self.path), "chaos")
        profiles.delete(self.path, "chaos")
        self.assertEqual(profiles.names(self.path), [])
        self.assertIsNone(profiles.active(self.path))

    def test_les_commandes_ponctuelles_ne_sont_jamais_sauvees(self):
        profiles.save(
            self.path,
            "sur",
            {"formation": "rain", "update": True, "stop": True, "once": True},
        )
        self.assertEqual(profiles.load(self.path, "sur"), {"formation": "rain"})

    def test_un_fichier_abime_n_empeche_pas_le_demarrage(self):
        self.path.write_text("pas du json", encoding="utf-8")
        self.assertEqual(profiles.read(self.path), profiles.empty())

    def test_les_valeurs_invalides_sont_ignorees(self):
        self.path.write_text(json.dumps({
            "active": "bizarre",
            "profiles": {"bizarre": {
                "formation": "triangle", "burst_min": True, "volume": "fort",
                "no_sound": "oui", "min": 12,
            }},
        }), encoding="utf-8")
        self.assertEqual(profiles.load(self.path, "bizarre"), {"min": 12})

    def test_les_bornes_de_taille_sont_persistees(self):
        profiles.save(self.path, "geants", {"size_min": 1, "size_max": 1.8})
        self.assertEqual(profiles.load(self.path, "geants"),
                         {"size_min": 1.0, "size_max": 1.8})

    def test_nom_invalide_refuse(self):
        with self.assertRaises(profiles.ProfileError):
            profiles.save(self.path, "deux mots", {"formation": "rain"})


if __name__ == "__main__":
    unittest.main()
