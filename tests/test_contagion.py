"""Le Codex, les signaux de flotte et les nouvelles anomalies."""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from doot import cli, codex, contagion, evenements, notification, partage, window


class Signaux(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)

    def test_un_signal_frais_est_recu_une_seule_fois(self):
        signal = contagion.creer("portable", self.now, token="abc")
        etat = {"machine": "fixe"}
        self.assertTrue(contagion.recevoir(etat, signal, self.now))
        self.assertFalse(contagion.recevoir(etat, signal, self.now))
        self.assertEqual(contagion.vider(etat, self.now), [signal])
        self.assertEqual(contagion.vider(etat, self.now), [])

    def test_un_signal_perime_ou_local_est_ignore(self):
        vieux = contagion.creer(
            "portable", self.now - timedelta(seconds=contagion.TTL_SECONDS + 1),
            token="vieux",
        )
        self.assertFalse(contagion.valide(vieux, self.now))
        local = contagion.creer("fixe", self.now, token="local")
        self.assertFalse(contagion.recevoir({"machine": "fixe"}, local, self.now))

    def test_le_signal_ne_part_que_dans_le_partage_automatique(self):
        signal = contagion.creer("fixe", token="partage")
        etat = {"machine": "fixe", "contagion_sortante": signal}
        self.assertNotIn("contagion", partage.part_exportable(etat))
        self.assertEqual(
            partage.part_exportable(etat, avec_contagion=True)["contagion"], signal,
        )


class ChargeDuSignal(unittest.TestCase):
    """Ce qu'un signal porte, et ce qu'il n'a pas le droit de porter."""

    def test_un_doot_reste_l_objet_d_avant_la_charge(self):
        """Une machine restee en arriere doit le lire sans voir de format neuf."""

        signal = contagion.creer("portable", token="nu")
        self.assertEqual(set(signal), {"id", "source", "emis"})
        self.assertEqual(contagion.charge(signal), ("doot", ""))

    def test_une_melodie_voyage_avec_son_nom(self):
        signal = contagion.creer("portable", token="m", genre="melodie", nom="Rickroll")
        self.assertEqual(contagion.charge(signal), ("melodie", "rickroll"))

    def test_une_rencontre_voyage_avec_son_identifiant(self):
        signal = contagion.creer("portable", token="e", genre="evenement", nom="pluie")
        self.assertEqual(contagion.charge(signal), ("evenement", "pluie"))

    def test_un_genre_inconnu_ne_s_ecrit_pas(self):
        signal = contagion.creer("portable", token="x", genre="rm", nom="tout")
        self.assertNotIn("genre", signal)
        self.assertEqual(contagion.charge(signal), ("doot", ""))

    def test_un_nom_qui_est_un_chemin_est_refuse(self):
        """`melodie.find` ouvrirait le fichier designe : rien de tel n'entre."""

        for mauvais in ("../../secret.rtttl", "/etc/passwd.rtttl",
                        "dossier/melodie.rtttl", "..", ".cache", "a" * 60,
                        "", "melodie\\perso.rtttl"):
            with self.subTest(nom=mauvais):
                self.assertEqual(contagion.nom_sur(mauvais), "")
                signal = contagion.creer("portable", token="t",
                                         genre="melodie", nom=mauvais)
                self.assertNotIn("nom", signal)
                self.assertEqual(contagion.charge(signal), ("doot", ""))

    def test_une_charge_abimee_vaut_un_doot_et_non_un_refus(self):
        """Un nom casse ne doit pas couter l'apparition elle-meme."""

        signal = contagion.creer("portable", self.now, token="ok")
        signal["genre"] = "melodie"
        signal["nom"] = "../x.rtttl"
        self.assertTrue(contagion.valide(signal, self.now))
        self.assertEqual(contagion.charge(signal), ("doot", ""))

    def test_une_charge_survit_au_passage_par_l_etat(self):
        signal = contagion.creer("portable", self.now, token="p",
                                 genre="evenement", nom="vortex")
        etat = {"machine": "fixe"}
        self.assertTrue(contagion.recevoir(etat, signal, self.now))
        self.assertEqual(contagion.charge(contagion.vider(etat, self.now)[0]),
                         ("evenement", "vortex"))

    def setUp(self):
        self.now = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)


class ContagionRecue(unittest.TestCase):
    """Ce qu'un poste fait de ce qu'une autre machine lui envoie."""

    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.addCleanup(self.dossier.cleanup)
        racine = Path(self.dossier.name)
        chemins = {
            "data": racine, "state": racine / "state.json",
            "melodies": racine / "melodies", "sound": racine / "sons",
            "image": racine / "images", "wav": racine / "doot.wav",
            "log": racine / "doot.log",
        }
        chemins["melodies"].mkdir(parents=True)
        self.chemins = chemins
        patch = mock.patch.object(cli, "paths", return_value=chemins)
        patch.start()
        self.addCleanup(patch.stop)
        # La medaille d'un premier succes ouvre une fenetre et rend sa fanfare :
        # quatre secondes par test, sur un runner qui n'a pas d'affichage.
        for nom in ("show", "show_lot"):
            muet = mock.patch.object(cli.notification, nom, lambda *a, **k: None)
            muet.start()
            self.addCleanup(muet.stop)
        self.args = cli.parse_args(["--ignore-season", "--quiet"])

    def joue(self, signal):
        """Renvoie (nombre de squelettes, nom de la melodie jouee ou None)."""

        vus = []
        melodies = []
        with mock.patch.object(window, "show", side_effect=lambda **_: vus.append(1)), \
             mock.patch.object(cli, "resolve_media", return_value=(None, None, 0.0)), \
             mock.patch.object(cli, "emit_melodie",
                               side_effect=lambda _a, morceau: melodies.append(morceau)):
            cli.emit_contagion(self.args, signal, journal=False)
        return len(vus), melodies[0].name if melodies else None

    def test_un_signal_nu_reste_un_doot_bref(self):
        squelettes, melodie = self.joue(contagion.creer("pair", token="1"))
        self.assertEqual(squelettes, 1)
        self.assertIsNone(melodie)

    def test_une_rencontre_arrive_avec_sa_choregraphie(self):
        signal = contagion.creer("pair", token="2", genre="evenement", nom="pluie")
        squelettes, _ = self.joue(signal)
        self.assertEqual(squelettes, evenements.find("pluie").quantite)

    def test_une_melodie_connue_se_joue_vraiment(self):
        signal = contagion.creer("pair", token="3", genre="melodie", nom="rickroll")
        squelettes, melodie = self.joue(signal)
        self.assertIsNotNone(melodie)
        self.assertEqual(squelettes, 0)

    def test_une_melodie_inconnue_ici_retombe_en_doot(self):
        """Deux postes ne portent pas forcement les memes melodies perso."""

        signal = contagion.creer("pair", token="4", genre="melodie",
                                 nom="celle-du-voisin")
        squelettes, melodie = self.joue(signal)
        self.assertEqual(squelettes, 1)
        self.assertIsNone(melodie)

    def test_ce_qui_traverse_reste_une_contagion_au_codex(self):
        """Sinon une flotte suffirait a collectionner les rencontres rares."""

        signal = contagion.creer("pair", token="5", genre="evenement", nom="pluie")
        self.joue(signal)
        self.assertEqual(cli.read_state()["stats"]["evenements_vus"], ["contagion"])

    def test_une_melodie_contagieuse_compte_aussi_la_contagion(self):
        signal = contagion.creer("pair", token="6", genre="melodie", nom="rickroll")
        self.joue(signal)
        stats = cli.read_state()["stats"]
        self.assertEqual(stats["evenements_vus"], ["contagion"])
        self.assertEqual(sum(stats["melodies"].values()), 1)
        self.assertNotIn("doots", stats)

    def test_une_melodie_illisible_retombe_sur_le_doot_bref(self):
        """Le repli d'erreur employait les reglages du daemon.

        Un poste configure en salve de quatre repondait a une melodie
        contagieuse illisible par quatre doots, la ou la contagion n'en promet
        qu'un seul et bref.
        """
        (self.chemins["melodies"] / "cassee.rtttl").write_text(
            "ceci n'est pas du RTTTL", encoding="utf-8")
        self.args = cli.parse_args([
            "--ignore-season", "--quiet", "--burst-min", "4", "--burst-max", "4",
        ])
        signal = contagion.creer("pair", token="9", genre="melodie", nom="cassee")
        squelettes, melodie = self.joue(signal)
        self.assertEqual(squelettes, 1)
        self.assertIsNone(melodie)

    def test_le_tirage_ordinaire_garde_la_salve_du_daemon(self):
        """L'autre moitie du correctif : seul le repli de la contagion change."""

        fichier = self.chemins["melodies"] / "cassee.rtttl"
        fichier.write_text("ceci n'est pas du RTTTL", encoding="utf-8")
        args = cli.parse_args([
            "--ignore-season", "--quiet", "--burst-min", "4", "--burst-max", "4",
        ])
        vus = []
        with mock.patch.object(window, "show", side_effect=lambda **_: vus.append(1)), \
             mock.patch.object(cli, "resolve_media", return_value=(None, None, 0.0)):
            self.assertFalse(cli.emit_melodie_tiree(args, fichier))
        self.assertEqual(len(vus), 4)

    def test_un_poste_muet_sur_les_melodies_recoit_le_doot(self):
        self.args = cli.parse_args(["--ignore-season", "--quiet", "--no-melody"])
        signal = contagion.creer("pair", token="7", genre="melodie", nom="rickroll")
        squelettes, melodie = self.joue(signal)
        self.assertEqual(squelettes, 1)
        self.assertIsNone(melodie)

    def test_un_poste_muet_sur_les_rencontres_recoit_le_doot(self):
        self.args = cli.parse_args(["--ignore-season", "--quiet", "--no-event"])
        signal = contagion.creer("pair", token="8", genre="evenement", nom="pluie")
        squelettes, _ = self.joue(signal)
        self.assertEqual(squelettes, 1)


class ContagionEmise(unittest.TestCase):
    """Ce qu'un poste fait voyager de ce qu'il vient de jouer."""

    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.addCleanup(self.dossier.cleanup)
        racine = Path(self.dossier.name)
        patch = mock.patch.object(cli, "paths", return_value={
            "data": racine, "state": racine / "state.json", "log": racine / "doot.log",
        })
        patch.start()
        self.addCleanup(patch.stop)
        reglage = mock.patch.object(partage, "reglage", return_value={"cle": "x"})
        reglage.start()
        self.addCleanup(reglage.stop)
        self.args = cli.parse_args(["--ignore-season", "--quiet"])

    def sortant(self, charge):
        toujours = mock.Mock(random=mock.Mock(return_value=0.0))
        cli.propager_contagion(self.args, charge, rng=toujours)
        return cli.read_state().get("contagion_sortante", {})

    def test_sans_charge_le_signal_reste_un_doot(self):
        self.assertEqual(contagion.charge(self.sortant(None)), ("doot", ""))

    def test_la_melodie_jouee_ici_part_avec_son_nom(self):
        signal = self.sortant(("melodie", "megalovania"))
        self.assertEqual(contagion.charge(signal), ("melodie", "megalovania"))

    def test_la_rencontre_jouee_ici_part_avec_son_identifiant(self):
        signal = self.sortant(("evenement", "vortex"))
        self.assertEqual(contagion.charge(signal), ("evenement", "vortex"))

    def test_la_finale_part_comme_les_autres_rencontres(self):
        """Le rite du 31 octobre voyage, et chaque poste garde le sien.

        La finale n'est pas tirable au sort, mais une fois jouee c'est une
        rencontre comme une autre : rien ne justifie qu'elle seule reste a la
        maison. Le pair qui la recoit la joue sans refermer sa propre saison,
        `emit_contagion` ne passant jamais par `jouer_le_rite`.
        """
        signal = self.sortant(("evenement", "finale"))
        self.assertEqual(contagion.charge(signal), ("evenement", "finale"))

    def test_rien_ne_part_quand_le_tirage_ne_tombe_pas(self):
        jamais = mock.Mock(random=mock.Mock(return_value=1.0))
        self.assertFalse(cli.propager_contagion(self.args, ("melodie", "x"), rng=jamais))


class LivreDesRencontres(unittest.TestCase):
    def test_le_codex_cache_ce_qui_n_a_pas_ete_vu(self):
        etat = {"stats": {"evenements_vus": ["duel", "mimic"]}}
        self.assertEqual(codex.vus(etat), {"duel", "mimic"})
        self.assertEqual(codex.progression(etat), (2, len(codex.CATALOGUE)))

    def test_les_trois_nouvelles_rencontres_sont_forceables(self):
        self.assertEqual(evenements.find("duel").formation, "duel")
        self.assertEqual(evenements.find("mimic").mise_en_scene, "mimic")
        self.assertEqual(evenements.find("faux-bug").mise_en_scene, "faux-bug")

    def test_le_duel_alterne_les_deux_bords(self):
        args = cli.build_parser().parse_args(["--formation", "duel"])
        with mock.patch.object(window, "active_monitors", return_value=[object()]):
            plan = cli.formation_plan(args, 6)
        self.assertEqual(
            [etape["side"] for etape in plan],
            ["left", "right", "left", "right", "left", "right"],
        )


class MiseEnScene(unittest.TestCase):
    def test_le_faux_bug_tremble_puis_tombe(self):
        avant = window.glitch_position(500, 4000, 100, 200, 1080, 120)
        fin = window.glitch_position(4000, 4000, 100, 200, 1080, 120)
        self.assertLessEqual(abs(avant[0] - 100), 4)
        self.assertGreater(fin[1], 1080)

    def test_le_mimic_a_plusieurs_mensonges(self):
        self.assertGreaterEqual(len(notification.MIMIC_MESSAGES), 3)

    def test_le_mimic_affiche_son_mensonge_avant_le_doot(self):
        args = cli.build_parser().parse_args(["--quiet"])
        evenement = evenements.find("mimic")
        ordre = []
        with mock.patch.object(
            notification, "show_mimic", side_effect=lambda: ordre.append("mimic"),
        ), mock.patch.object(
            cli, "emit_doots", side_effect=lambda *_args, **_kwargs: ordre.append("doot") or 1,
        ):
            self.assertTrue(cli.emit_evenement(args, evenement))
        self.assertEqual(ordre, ["mimic", "doot"])


if __name__ == "__main__":
    unittest.main()
