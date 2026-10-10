"""Le glitch anime son rendu et transforme vraiment le son, sans l'amplifier."""

from __future__ import annotations

import itertools
import math
import tempfile
import unittest
import wave
from pathlib import Path
from unittest import mock

from doot import cli, glitch, gui, melodie, overlay, png, profiles, sound, window


class Images(unittest.TestCase):
    def source(self):
        return png.Frame(32, 24, bytes(
            channel for y in range(24) for x in range(32)
            for channel in ((100, 150, 200, 220) if 6 < x < 25 else (0, 0, 0, 0))
        ))

    def test_animation_distincte_transparente_et_de_taille_stable(self):
        source = self.source()
        frames = glitch.frames(source)
        self.assertGreater(len({frame.data for frame in frames}), 3)
        self.assertTrue(all((f.width, f.height) == (32, 24) for f in frames))
        self.assertEqual(frames[0], source)
        self.assertEqual(frames[-1], source)
        self.assertTrue(any(alpha == 0 for alpha in frames[2].data[3::4]))
        for frame in frames:
            for pos in range(0, len(frame.data), 4):
                b, g, r, a = frame.data[pos:pos + 4]
                self.assertLessEqual(max(b, g, r), a)
        self.assertEqual(source.data, self.source().data)

    def test_ascii_et_texte_muet_changent_sans_changer_de_dimensions(self):
        for source in ("D O O T", "  /00\\\n   ||\n _/  \\_"):
            frames = [glitch.text(source, step) for step in range(glitch.STEPS)]
            self.assertGreater(len(set(frames)), 1)
            dimensions = {(len(f.splitlines()), max(map(len, f.splitlines()))) for f in frames}
            self.assertEqual(len(dimensions), 1)

    def test_le_rendu_argb_continue_a_changer_pendant_le_plateau(self):
        class Surface:
            def __init__(self):
                self.pixels = []
                self.closed = False

            def map(self):
                pass

            def draw(self, pixels):
                self.pixels.append(pixels)

            def close(self):
                self.closed = True

        surface = Surface()
        clock = itertools.count(0, 0.04)
        with mock.patch.object(overlay.time, "monotonic", side_effect=lambda: next(clock)), \
             mock.patch.object(overlay.time, "sleep"):
            overlay.run(surface, self.source(), 0, 0, 2, glitch_effect=True)
        self.assertTrue(surface.closed)
        self.assertGreater(len(set(surface.pixels[8:18])), 3)

    def test_le_backend_natif_recoit_le_glitch(self):
        monitor = window.screens.Monitor(0, 0, 800, 600)
        backend = mock.Mock()
        backend.available.return_value = True
        with mock.patch.object(window.png, "size", return_value=(32, 24)), \
             mock.patch.object(window.png, "frame", return_value=self.source()):
            result = window._tente_overlay(
                backend, lambda: [monitor], None, 1, True, 1,
                Path("squelette.png"), 1, None, False, False, None,
                420, False, 700, glitch_effect=True,
            )
        self.assertTrue(result)
        self.assertTrue(backend.play.call_args.kwargs["glitch_effect"])

    def test_preparation_en_echec_ferme_la_surface_avant_de_replier(self):
        surface = mock.Mock()
        with mock.patch.object(glitch, "frames", side_effect=ValueError("image invalide")):
            with self.assertRaises(ValueError):
                overlay.run(surface, self.source(), 0, 0, 1, glitch_effect=True)
        surface.map.assert_not_called()
        surface.close.assert_called_once()

    def test_glitch_multivoix_anime_le_montage_sans_recalculer_les_parasites(self):
        source = self.source()
        bobs = [source, source, source]
        group = png.montage([source, source], 2)
        surface = mock.Mock()
        clock = itertools.count(0, 0.04)
        with mock.patch.object(overlay.time, "monotonic", side_effect=lambda: next(clock)), \
             mock.patch.object(overlay.time, "sleep"), \
             mock.patch.object(glitch, "frames", wraps=glitch.frames) as prepare:
            overlay.run(surface, group, 0, 0, 2, bobs=bobs,
                        voices=[[0, 0.5], [0.2, 0.8]], columns=2, glitch_effect=True)
        pixels = [call.args[0] for call in surface.draw.call_args_list]
        self.assertGreater(len(set(pixels[8:18])), 3)
        self.assertTrue(all(len(data) == len(group.data) for data in pixels))
        self.assertEqual(prepare.call_count, 3)


class Audio(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def write_source(self, width=2, channels=2, silence=False):
        rate, count = 8000, 8000
        raw = bytearray()
        for index in range(count):
            value = 0 if silence else int(math.sin(index / 9) * ((1 << (width * 8 - 1)) - 1) * 0.8)
            for channel in range(channels):
                sample = value if channel == 0 else 0
                raw += (sample + (128 if width == 1 else 0)).to_bytes(width, "little", signed=width != 1)
        source = self.root / "source.wav"
        with wave.open(str(source), "wb") as handle:
            handle.setparams((channels, width, rate, 0, "NONE", "not compressed"))
            handle.writeframes(raw)
        return source, bytes(raw)

    def test_formats_pcm_duree_canaux_source_et_pic_conserves(self):
        for width in (1, 2, 3, 4):
            with self.subTest(width=width):
                source, original = self.write_source(width)
                destination = self.root / "glitch.wav"
                self.assertEqual(sound.glitch_wav(source, destination), destination)
                with wave.open(str(source), "rb") as before, wave.open(str(destination), "rb") as after:
                    self.assertEqual(before.getparams(), after.getparams())
                    raw = after.readframes(after.getnframes())
                    self.assertNotEqual(raw, original)
                    self.assertEqual(before.readframes(before.getnframes()), original)
                midpoint = 128 if width == 1 else 0
                def peak(data):
                    return max(abs(int.from_bytes(data[i:i + width], "little", signed=width != 1) - midpoint)
                               for i in range(0, len(data), width))
                self.assertLessEqual(peak(raw), peak(original))
                stride = width * 2
                for pos in range(width, len(raw), stride):
                    self.assertEqual(raw[pos:pos + width], original[pos:pos + width])

    def test_silence_reste_silencieux_meme_en_pcm_unsigned(self):
        for width in (1, 2):
            source, original = self.write_source(width, silence=True)
            dest = sound.glitch_wav(source, self.root / "glitch.wav")
            with wave.open(str(dest), "rb") as handle:
                self.assertEqual(handle.readframes(handle.getnframes()), original)

    def test_fichier_casse_ne_produit_pas_de_faux_succes(self):
        source = self.root / "casse.wav"
        source.write_bytes(b"not wave")
        self.assertIsNone(sound.glitch_wav(source, self.root / "glitch.wav"))


class Integration(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.paths = {"data": self.root, "wav": self.root / "doot.wav",
                      "sound": self.root / "sound", "image": self.root / "image",
                      "state": self.root / "state.json", "melodies": self.root / "melodies"}
        patch = mock.patch.object(cli, "paths", return_value=self.paths)
        patch.start()
        self.addCleanup(patch.stop)

    def test_le_son_et_le_visuel_sont_actives_ensemble(self):
        args = cli.build_parser().parse_args(["--once", "--glitch", "--no-reverse"])
        with mock.patch.object(window, "show") as show, mock.patch.object(cli, "note_succes"):
            cli.emit_doots(args)
        call = show.call_args.kwargs
        self.assertTrue(call["glitch_effect"])
        self.assertEqual(call["wav_path"].name, "doot-glitch.wav")
        self.assertTrue(call["wav_path"].is_file())

    def test_son_personnel_wav_est_bien_la_source(self):
        args = cli.build_parser().parse_args(["--glitch"])
        source = sound.write_wav(self.root / "custom.wav", 0.2)
        with mock.patch.object(sound, "pick_sound", return_value=source), \
             mock.patch.object(sound, "glitch_wav", wraps=sound.glitch_wav) as effect:
            cli.resolve_media(args)
        self.assertEqual(effect.call_args.args[0], source)

    def test_son_fourni_utilise_le_wav_original_decode(self):
        args = cli.build_parser().parse_args(["--glitch"])
        with mock.patch.object(sound, "pick_sound", return_value=sound.BUNDLED_SOUND), \
             mock.patch.object(sound, "glitch_wav", wraps=sound.glitch_wav) as effect:
            wav, _picture, _duration = cli.resolve_media(args)
        self.assertEqual(effect.call_args.args[0], sound.BUNDLED_WAV)
        self.assertAlmostEqual(sound.probe_duration(wav), sound.probe_duration(sound.BUNDLED_WAV))

    def test_taille_accorde_le_son_avant_le_glitch(self):
        args = cli.build_parser().parse_args(["--glitch"])
        with mock.patch.object(sound, "pick_sound", return_value=sound.BUNDLED_SOUND), \
             mock.patch.object(sound, "glitch_wav", wraps=sound.glitch_wav) as effect:
            wav, _picture, _duration = cli.resolve_media(args, taille=1.4)
        self.assertEqual(effect.call_args.args[0].name, "doot-taille.wav")
        self.assertAlmostEqual(sound.probe_duration(wav), sound.probe_duration(sound.BUNDLED_WAV) * 1.4, places=3)

    def test_mouvements_reduits_et_no_flash_restent_prioritaires(self):
        for flag in ("--reduce-motion", "--no-flash"):
            args = cli.parse_args(["--no-profile", "--glitch", flag])
            self.assertFalse(cli.glitch_enabled(args))
            self.assertFalse(cli.display_options(args)["glitch_effect"])

    def test_mode_muet_ne_genere_ni_ne_lit_de_son(self):
        args = cli.build_parser().parse_args(["--glitch", "--no-sound"])
        with mock.patch.object(sound, "glitch_wav") as effect, \
             mock.patch.object(window, "show") as show, mock.patch.object(cli, "note_succes"):
            cli.emit_doots(args)
        effect.assert_not_called()
        self.assertIsNone(show.call_args.kwargs["wav_path"])
        self.assertEqual(show.call_args.kwargs["visual_text"], "D O O T")
        self.assertTrue(show.call_args.kwargs["glitch_effect"])

    def test_no_glitch_gagne_sur_glitch(self):
        args = cli.parse_args(["--no-profile", "--glitch", "--no-glitch"])
        self.assertFalse(cli.glitch_enabled(args))

    def test_profils_sauvegardent_le_glitch_et_la_cli_le_remplace(self):
        path = self.root / "profiles.json"
        profiles.save(path, "digital", {"glitch": True})
        profiles.save(path, "clean", {"no_glitch": True})
        with mock.patch.object(cli, "profiles_path", return_value=path):
            self.assertTrue(cli.glitch_enabled(cli.parse_args(["--profile", "digital"])))
            self.assertFalse(cli.glitch_enabled(cli.parse_args(["--profile", "digital", "--no-glitch"])))
            self.assertTrue(cli.glitch_enabled(cli.parse_args(["--profile", "clean", "--glitch"])))

    def test_gui_propose_le_reglage_et_produit_la_commande(self):
        settings = gui.option_specs()
        self.assertIn("--glitch", {spec.option for spec in settings})
        command = next(command for command in gui.COMMANDS if command.key == "once")
        argv = gui.build_command_argv(command, {}, {"glitch": True}, settings)
        self.assertEqual(argv, ["--once", "--glitch"])

    def test_melodie_glitchee_conserve_sa_duree_et_ses_voix(self):
        args = cli.build_parser().parse_args(["--glitch"])
        piece = melodie.parse("Tiny:d=8,o=5,b=120:c,d,e")
        with mock.patch.object(window, "show") as show:
            cli.emit_melodie(args, piece)
        call = show.call_args.kwargs
        self.assertTrue(call["glitch_effect"])
        self.assertEqual(call["wav_path"].name, "melodie-glitch.wav")
        self.assertAlmostEqual(sound.probe_duration(call["wav_path"]), melodie.duration(piece), places=2)
        self.assertTrue(call["beats"])
