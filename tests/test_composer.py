"""Le sequencer graphique produit des fichiers RTTTL jouables."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from doot import composer, melodie


class Partition(unittest.TestCase):
    def test_grille_vide_de_seize_pas(self):
        self.assertEqual(composer.empty_pattern(), [None] * 16)

    def test_un_clic_pose_remplace_et_efface(self):
        pattern = composer.empty_pattern()
        composer.toggle(pattern, 3, "c")
        self.assertEqual(pattern[3], "c")
        composer.toggle(pattern, 3, "d#")
        self.assertEqual(pattern[3], "d#")
        composer.toggle(pattern, 3, "d#")
        self.assertIsNone(pattern[3])

    def test_rtttl_genere_est_lu_par_le_vrai_moteur(self):
        pattern = composer.empty_pattern()
        pattern[0], pattern[4], pattern[8], pattern[12] = "c", "e", "g", "b"
        text = composer.rtttl("Os dansants", 120, 5, pattern)
        morceau = melodie.parse(text)
        self.assertEqual(morceau.tempo, 120)
        self.assertEqual(len(morceau.voices[0]), 16)
        self.assertEqual(sum(note is not None for note, _ in morceau.voices[0]), 4)

    def test_partition_sans_note_refusee(self):
        with self.assertRaisesRegex(composer.ComposerError, "au moins une note"):
            composer.rtttl("silence", 120, 5, composer.empty_pattern())


class Sauvegarde(unittest.TestCase):
    def test_nom_nettoye_et_pas_d_ecrasement(self):
        pattern = composer.empty_pattern()
        pattern[0] = "c"
        with tempfile.TemporaryDirectory() as dossier:
            first = composer.save(Path(dossier), "  Doot / danse  ", 90, 4, pattern)
            second = composer.save(Path(dossier), "  Doot / danse  ", 90, 4, pattern)
            self.assertEqual(first.name, "Doot-danse.rtttl")
            self.assertEqual(second.name, "Doot-danse-2.rtttl")
            self.assertEqual(melodie.load(first).tempo, 90)


if __name__ == "__main__":
    unittest.main()
