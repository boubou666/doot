"""Synthese du jingle et choix du son.

Tout ce qui est verifie ici tourne sans carte son ni serveur graphique : on ne
joue rien, on verifie ce qui est produit et ce qui est choisi.
"""

from __future__ import annotations

import subprocess
import tempfile
import unittest
import wave
from pathlib import Path
from unittest import mock

from doot import sound


class SyntheseDuJingle(unittest.TestCase):
    """Le WAV de repli, genere quand aucun autre son n'est disponible."""

    @classmethod
    def setUpClass(cls):
        cls._dir = tempfile.TemporaryDirectory()
        cls.root = Path(cls._dir.name)
        cls.wav = sound.write_wav(cls.root / "jingle.wav", volume=0.55)

    @classmethod
    def tearDownClass(cls):
        cls._dir.cleanup()

    def test_wav_valide(self):
        with wave.open(str(self.wav), "rb") as handle:
            self.assertEqual(handle.getnchannels(), 1)
            self.assertEqual(handle.getsampwidth(), 2)
            self.assertEqual(handle.getframerate(), sound.SAMPLE_RATE)
            self.assertGreater(handle.getnframes(), 0)

    def test_duree_conforme(self):
        with wave.open(str(self.wav), "rb") as handle:
            seconds = handle.getnframes() / handle.getframerate()
        self.assertAlmostEqual(seconds, sound.TOTAL_SECONDS, places=2)

    def test_le_son_n_est_pas_silencieux(self):
        with wave.open(str(self.wav), "rb") as handle:
            frames = handle.readframes(handle.getnframes())
        self.assertTrue(any(frames), "le jingle ne contient que du silence")

    def test_volume_respecte(self):
        """Un volume plus bas doit donner une amplitude plus basse."""
        import struct

        def peak(path):
            with wave.open(str(path), "rb") as handle:
                data = handle.readframes(handle.getnframes())
            values = struct.unpack(f"<{len(data) // 2}h", data)
            return max(abs(v) for v in values)

        fort = sound.write_wav(self.root / "fort.wav", volume=0.9)
        faible = sound.write_wav(self.root / "faible.wav", volume=0.2)
        self.assertGreater(peak(fort), peak(faible))

    def test_pas_de_saturation(self):
        """Le soft clipping doit garder l'echantillon dans les bornes 16 bits."""
        import struct

        with wave.open(str(self.wav), "rb") as handle:
            data = handle.readframes(handle.getnframes())
        values = struct.unpack(f"<{len(data) // 2}h", data)
        self.assertLessEqual(max(abs(v) for v in values), 32767)

    def test_ensure_wav_ne_regenere_pas_sans_raison(self):
        path = self.root / "cache.wav"
        sound.ensure_wav(path, 0.55)
        first = path.stat().st_mtime_ns
        sound.ensure_wav(path, 0.55)
        self.assertEqual(path.stat().st_mtime_ns, first)

    def test_ensure_wav_force_regenere(self):
        path = self.root / "force.wav"
        sound.ensure_wav(path, 0.55)
        path.write_bytes(b"")  # fichier vide : doit etre refait
        sound.ensure_wav(path, 0.55)
        self.assertGreater(path.stat().st_size, 0)


class ChoixDuSon(unittest.TestCase):
    """L'ordre de priorite : perso, puis fourni, puis synthetise."""

    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.root = Path(self._dir.name)
        self.customs = self.root / "sound"
        self.customs.mkdir()
        self.cache = self.root / "doot.wav"

    def tearDown(self):
        self._dir.cleanup()

    def test_renvoie_toujours_un_fichier_existant(self):
        chosen = sound.pick_sound(self.cache, self.customs, 0.55)
        self.assertTrue(chosen.is_file(), chosen)

    def test_le_son_perso_est_prioritaire(self):
        mine = self.customs / "a_moi.wav"
        sound.write_wav(mine, 0.5)
        self.assertEqual(sound.pick_sound(self.cache, self.customs, 0.55), mine)

    def test_les_extensions_inconnues_sont_ignorees(self):
        (self.customs / "notes.txt").write_text("pas un son")
        (self.customs / "image.png").write_bytes(b"\x89PNG")
        self.assertEqual(sound.custom_sounds(self.customs), [])

    def test_formats_compresses_reconnus(self):
        for name in ("a.mp3", "b.ogg", "c.flac", "d.m4a", "e.opus"):
            (self.customs / name).write_bytes(b"factice")
        found = {p.name for p in sound.custom_sounds(self.customs)}
        self.assertEqual(len(found), 5)

    def test_dossier_absent(self):
        self.assertEqual(sound.custom_sounds(self.root / "nexiste_pas"), [])

    def test_repli_synthetise_si_rien_d_autre(self):
        """Sans son perso ni son fourni lisible, on doit obtenir le WAV genere."""
        chosen = sound.pick_sound(self.cache, self.customs, 0.55)
        bundled = sound.bundled_sound()
        self.assertIn(chosen, [p for p in (bundled, self.cache) if p is not None])


class SonInverse(unittest.TestCase):
    def test_inverse_des_trames_entieres(self):
        with tempfile.TemporaryDirectory() as dossier:
            source = Path(dossier) / "source.wav"
            destination = Path(dossier) / "inverse.wav"
            with wave.open(str(source), "wb") as handle:
                handle.setnchannels(2)
                handle.setsampwidth(2)
                handle.setframerate(8000)
                handle.writeframes(b"aaaabbbbcccc")

            self.assertEqual(sound.reverse_wav(source, destination), destination)
            with wave.open(str(destination), "rb") as handle:
                self.assertEqual(handle.readframes(3), b"ccccbbbbaaaa")

    def test_refuse_un_fichier_non_wav(self):
        with tempfile.TemporaryDirectory() as dossier:
            source = Path(dossier) / "source.mp3"
            source.write_bytes(b"pas un wav")
            self.assertIsNone(sound.reverse_wav(source, Path(dossier) / "inverse.wav"))


class DootVisuel(unittest.TestCase):
    def test_parse_les_outils_des_trois_plateformes(self):
        self.assertEqual(sound._parse_output_level("Volume: 0.42"), 0.42)
        self.assertEqual(sound._parse_output_level("Volume: 0.42 [MUTED]"), 0.0)
        self.assertEqual(sound._parse_output_level("Volume: front-left: 30%"), 0.30)
        self.assertEqual(
            sound._parse_output_level("output volume:77, input volume:50, output muted:false"),
            0.77,
        )

    def test_mode_muet_et_volume_bas_forcent_le_texte(self):
        path = Path("doot.wav")
        self.assertTrue(sound.visual_fallback_needed(True, 1.0, path))
        self.assertTrue(sound.visual_fallback_needed(False, 0.01, path))

    def test_un_systeme_audible_ne_force_pas_le_texte(self):
        with mock.patch.object(sound, "system_output_level", return_value=0.8):
            self.assertFalse(sound.visual_fallback_needed(False, 0.5, Path("doot.wav")))


class Duree(unittest.TestCase):
    """`probe_duration` cale la duree d'affichage sur celle du son."""

    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.root = Path(self._dir.name)

    def tearDown(self):
        self._dir.cleanup()

    def test_duree_d_un_wav(self):
        path = sound.write_wav(self.root / "j.wav", 0.55)
        self.assertAlmostEqual(sound.probe_duration(path), sound.TOTAL_SECONDS, places=2)

    def test_fichier_illisible_renvoie_none(self):
        path = self.root / "casse.wav"
        path.write_bytes(b"pas un wav")
        self.assertIsNone(sound.probe_duration(path))

    def test_son_fourni_plausible_ou_inconnu(self):
        """Selon la plateforme on sait lire un mp3 ou non ; jamais d'exception."""
        bundled = sound.bundled_sound()
        if bundled is None:
            self.skipTest("aucun son fourni dans le paquet")
        length = sound.probe_duration(bundled)
        if length is not None:
            self.assertGreater(length, 0.1)
            self.assertLess(length, 60)


class Spatialisation(unittest.TestCase):
    """Gains stereo et fabrication de la copie panoramisee."""

    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.root = Path(self._dir.name)
        self.source = sound.write_wav(self.root / "mono.wav", volume=0.8)

    def tearDown(self):
        self._dir.cleanup()

    # ------------------------------------------------------------ gains ------

    def test_centre_equilibre_et_a_plein_volume(self):
        """Au centre, le son doit etre celui d'origine, pas 3 dB en dessous.

        L'egalite est exigee stricte : cos(pi/4) et sin(pi/4) ne tombent pas
        sur le meme dernier bit d'une libm a l'autre, et cet ecart infime
        suffisait a desequilibrer les canaux d'une unite sur Linux.
        """
        gauche, droite = sound.stereo_gains(0.0)
        self.assertEqual(gauche, droite, "canaux desequilibres au centre exact")
        self.assertEqual(gauche, 1.0)

    def test_extremes(self):
        gauche, droite = sound.stereo_gains(-1.0)
        self.assertAlmostEqual(gauche, 1.0)
        self.assertAlmostEqual(droite, 0.0)

        gauche, droite = sound.stereo_gains(1.0)
        self.assertAlmostEqual(gauche, 0.0)
        self.assertAlmostEqual(droite, 1.0)

    def test_le_canal_dominant_reste_a_plein_volume(self):
        """Sans quoi le doot serait plus faible qu'avant la spatialisation."""
        for pan in (-1.0, -0.5, -0.2, 0.0, 0.3, 0.75, 1.0):
            gauche, droite = sound.stereo_gains(pan)
            self.assertAlmostEqual(max(gauche, droite), 1.0, places=6, msg=f"pan={pan}")

    def test_pas_de_saut_audible_au_seuil(self):
        """Franchir le seuil ne doit pas s'entendre.

        C'est le defaut que la mesure avait revele : a puissance constante, le
        centre valait 0,71 et le moindre depassement du seuil faisait chuter le
        son de 3 dB d'un coup. On borne l'ecart a 1 dB, en dessous duquel une
        variation de niveau ne se remarque pas.
        """
        import math

        sous_le_seuil = sound.stereo_gains(0.0)
        juste_au_dessus = sound.stereo_gains(sound.SEUIL_PAN * 1.5)
        for avant, apres in zip(sous_le_seuil, juste_au_dessus):
            ecart_db = abs(20 * math.log10(max(apres, 1e-9) / max(avant, 1e-9)))
            self.assertLess(ecart_db, 1.0, f"saut de {ecart_db:.2f} dB au seuil")

    def test_rapport_des_gains_en_quart_de_cercle(self):
        """La forme de la courbe reste celle du cos/sin, seule l'echelle change."""
        import math

        for pan in (-0.8, -0.3, 0.0, 0.45, 0.9):
            gauche, droite = sound.stereo_gains(pan)
            angle = (pan + 1.0) * (math.pi / 4.0)
            attendu = math.cos(angle), math.sin(angle)
            self.assertAlmostEqual(droite / gauche, attendu[1] / attendu[0], places=6)

    def test_symetrie(self):
        for pan in (0.25, 0.5, 0.9):
            gauche, droite = sound.stereo_gains(pan)
            droite_miroir, gauche_miroir = sound.stereo_gains(-pan)
            self.assertAlmostEqual(gauche, gauche_miroir)
            self.assertAlmostEqual(droite, droite_miroir)

    def test_valeurs_hors_bornes_bornees(self):
        self.assertEqual(sound.stereo_gains(-5.0), sound.stereo_gains(-1.0))
        self.assertEqual(sound.stereo_gains(5.0), sound.stereo_gains(1.0))

    # -------------------------------------------------------- copie wav ------

    def pics(self, path):
        """Amplitude maximale de chaque canal d'un WAV stereo 16 bits."""
        import struct

        with wave.open(str(path), "rb") as handle:
            self.assertEqual(handle.getnchannels(), 2)
            data = handle.readframes(handle.getnframes())
        valeurs = struct.unpack(f"<{len(data) // 2}h", data)
        return max(abs(v) for v in valeurs[0::2]), max(abs(v) for v in valeurs[1::2])

    def test_mono_devient_stereo(self):
        sortie = sound.pan_wav(self.source, self.root / "p.wav", 0.0)
        self.assertIsNotNone(sortie)
        with wave.open(str(sortie), "rb") as handle:
            self.assertEqual(handle.getnchannels(), 2)

    def test_duree_et_frequence_inchangees(self):
        sortie = sound.pan_wav(self.source, self.root / "p.wav", 0.6)
        with wave.open(str(self.source), "rb") as avant, wave.open(str(sortie), "rb") as apres:
            self.assertEqual(avant.getframerate(), apres.getframerate())
            self.assertEqual(avant.getnframes(), apres.getnframes())

    def test_a_gauche_le_canal_droit_se_tait(self):
        sortie = sound.pan_wav(self.source, self.root / "g.wav", -1.0)
        gauche, droite = self.pics(sortie)
        self.assertGreater(gauche, 0)
        self.assertLessEqual(droite, 1, "le canal droit devrait etre muet")

    def test_a_droite_le_canal_gauche_se_tait(self):
        sortie = sound.pan_wav(self.source, self.root / "d.wav", 1.0)
        gauche, droite = self.pics(sortie)
        self.assertGreater(droite, 0)
        self.assertLessEqual(gauche, 1, "le canal gauche devrait etre muet")

    def test_au_centre_les_deux_canaux_sont_egaux(self):
        sortie = sound.pan_wav(self.source, self.root / "c.wav", 0.0)
        gauche, droite = self.pics(sortie)
        self.assertEqual(gauche, droite)

    def test_panoramique_intermediaire(self):
        """A mi-chemin a droite, la droite domine sans que la gauche disparaisse."""
        sortie = sound.pan_wav(self.source, self.root / "m.wav", 0.5)
        gauche, droite = self.pics(sortie)
        self.assertGreater(droite, gauche)
        self.assertGreater(gauche, 0, "un panoramique partiel ne coupe pas un canal")

    def test_les_gains_se_retrouvent_dans_les_echantillons(self):
        """Le rapport des pics doit suivre le rapport des gains theoriques."""
        pan = 0.4
        attendu_g, attendu_d = sound.stereo_gains(pan)
        sortie = sound.pan_wav(self.source, self.root / "r.wav", pan)
        gauche, droite = self.pics(sortie)
        self.assertAlmostEqual(droite / gauche, attendu_d / attendu_g, places=2)

    def test_source_stereo_acceptee(self):
        """Une source deja stereo doit ressortir stereo, panoramisee."""
        etape = sound.pan_wav(self.source, self.root / "st.wav", 0.0)
        sortie = sound.pan_wav(etape, self.root / "st2.wav", -1.0)
        self.assertIsNotNone(sortie)
        gauche, droite = self.pics(sortie)
        self.assertGreater(gauche, 0)
        self.assertLessEqual(droite, 1)

    def test_fichier_illisible_renvoie_none(self):
        casse = self.root / "casse.wav"
        casse.write_bytes(b"pas un wav")
        self.assertIsNone(sound.pan_wav(casse, self.root / "x.wav", 0.5))

    def test_la_source_n_est_pas_modifiee(self):
        avant = self.source.read_bytes()
        sound.pan_wav(self.source, self.root / "p.wav", 1.0)
        self.assertEqual(self.source.read_bytes(), avant)


class Panoramique(unittest.TestCase):
    """La syntaxe du filtre, propre a chaque lecteur, et le graphe commun."""

    def test_mpv_passe_par_lavfi(self):
        """`--af=pan=...` ne demarre pas : l'analyseur d'options bute sur les
        barres, et le doot spatialise devient muet."""
        commande = sound._pan_filter(["mpv", "--no-video"], -0.9)
        self.assertTrue(commande[-1].startswith("--af=lavfi=["), commande)
        self.assertTrue(commande[-1].endswith("]"), commande)
        self.assertEqual(commande[-1][len("--af=lavfi=["):-1],
                         sound._pan_graph(-0.9))

    def test_ffplay_garde_la_syntaxe_ffmpeg(self):
        commande = sound._pan_filter(["ffplay", "-nodisp"], 0.9)
        self.assertEqual(commande[-2], "-af")
        self.assertEqual(commande[-1], sound._pan_graph(0.9))

    def test_chaque_canal_garde_le_sien(self):
        """`c1=Rg*c0` construirait les deux sorties depuis le canal gauche : une
        source stereo y perdrait son canal droit, alors que `pan_wav` le garde.
        """
        for commande in (sound._pan_filter(["mpv"], -0.9),
                         sound._pan_filter(["ffplay"], -0.9)):
            self.assertIn("c1=0.0787*c1", commande[-1], commande)
            self.assertNotIn("c1=0.0787*c0", commande[-1], commande)

    def test_le_mono_est_monte_en_stereo_d_abord(self):
        """Pour que `c1` existe quelle que soit la source.

        mpv s'en passerait, son pipeline montant deja en stereo avant les
        filtres, mais le graphe ne doit pas dependre de ce detail de lecteur.
        """
        for commande in (sound._pan_filter(["mpv"], -0.9),
                         sound._pan_filter(["ffplay"], -0.9)):
            self.assertIn("aformat=channel_layouts=stereo,", commande[-1])
        graphe = sound._pan_graph(-0.9)
        self.assertLess(graphe.index("aformat="), graphe.index("pan="))

    def test_le_centre_ne_touche_a_rien(self):
        """Le graphe doit etre l'identite au centre exact.

        Le filtre n'y est pas applique — `SEUIL_PAN` s'y oppose — mais la
        continuite en depend : de part et d'autre du seuil, le son doit valoir
        celui d'origine, sans marche.
        """
        self.assertIn("c0=1.0000*c0", sound._pan_graph(0.0))
        self.assertIn("c1=1.0000*c1", sound._pan_graph(0.0))

    def test_lecteur_inconnu(self):
        self.assertIsNone(sound._pan_filter(["paplay"], -0.9))

    def test_les_gains_suivent_le_cote(self):
        gauche = sound._pan_graph(-1.0)
        droite = sound._pan_graph(1.0)
        self.assertIn("c0=1.0000*c0", gauche)
        self.assertIn("c1=1.0000*c1", droite)


class RepliSansPan(unittest.TestCase):
    """Un lecteur qui refuse le filtre ne doit pas rendre le doot muet."""

    class FauxProcessus:
        def __init__(self, code):
            self.code = code

        def wait(self, timeout=None):
            if self.code is None:
                raise subprocess.TimeoutExpired("lecteur", timeout)
            return self.code

    def setUp(self):
        self.lances = []
        self.addCleanup(setattr, sound, "_lance", sound._lance)

        def faux_lance(command, path):
            self.lances.append(command)
            return "processus de repli"

        sound._lance = faux_lance

    def _joue(self, code):
        lecture = sound.Lecture(self.FauxProcessus(code))
        sound._repli_sans_pan(lecture, ["mpv"], Path("doot.mp3"), delai=0.01).join(2)
        return lecture

    def test_un_refus_est_rejoue_sans_filtre(self):
        lecture = self._joue(1)
        self.assertEqual(self.lances, [["mpv"]])

    def test_le_lecteur_de_repli_reste_joignable(self):
        """Sinon `play_async` rend le processus mort et celui qui joue est
        perdu, ce qui mordra le jour ou `release` coupera vraiment le son."""
        lecture = self._joue(1)
        self.assertEqual(lecture.proc, "processus de repli")

    def test_une_lecture_qui_dure_n_est_pas_doublee(self):
        self._joue(None)
        self.assertEqual(self.lances, [])

    def test_une_fin_normale_n_est_pas_doublee(self):
        self._joue(0)
        self.assertEqual(self.lances, [])


if __name__ == "__main__":
    unittest.main()
