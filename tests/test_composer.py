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

    def test_import_retrouve_une_grille_produite_par_le_compositeur(self):
        pattern = composer.empty_pattern()
        pattern[0], pattern[4], pattern[8], pattern[12] = "c", "e", "g", "b"
        source = composer.rtttl("Os dansants", 135, 6, pattern)
        draft = composer.import_grid(source)
        self.assertEqual((draft.title, draft.tempo, draft.octave),
                         ("Os-dansants", 135, 6))
        self.assertEqual(list(draft.pattern), pattern)

    def test_import_avance_reste_editable_en_source_sans_etre_aplati(self):
        source = (
            "Lead:d=8,o=5,b=120:c,e,g,c6\n"
            "Bass:d=4,o=3,b=120:c,g,c,g\n"
        )
        self.assertEqual(len(composer.validate_source(source).voices), 2)
        with self.assertRaisesRegex(composer.ComposerError, "une seule voix"):
            composer.import_grid(source)

    def test_la_grille_refuse_les_durees_qu_elle_ne_peut_pas_representer(self):
        source = "Longue:d=8,o=5,b=100:" + ",".join(["c"] * 16)
        with self.assertRaisesRegex(composer.ComposerError, "doubles-croches"):
            composer.import_grid(source)


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

    def test_source_importee_est_sauvee_sans_reformatage(self):
        source = "# garde ce commentaire\nDuo:d=8,o=5,b=90:c,e,g,c6\n"
        with tempfile.TemporaryDirectory() as dossier:
            path = composer.write_source(Path(dossier) / "duo.rtttl", source)
            self.assertEqual(path.read_text(encoding="utf-8"), source)

    def test_source_invalide_n_est_pas_ecrite(self):
        with tempfile.TemporaryDirectory() as dossier:
            path = Path(dossier) / "cassee.rtttl"
            with self.assertRaises(composer.ComposerError):
                composer.write_source(path, "pas du rtttl")
            self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
