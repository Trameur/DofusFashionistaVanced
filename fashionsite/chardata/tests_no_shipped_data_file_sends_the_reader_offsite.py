# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Un fichier de donnees ne doit pas envoyer le navigateur du lecteur ailleurs.

Le site a deja deux gardes sur les tiers, et **aucun des deux ne pouvait voir
celui-la**. `tests_outbound_third_parties` lit ce que le SERVEUR appelle;
`tests_third_party_integrity` lit les adresses ecrites en toutes lettres dans
les gabarits. Ici l'adresse n'etait ecrite nulle part dans le code: elle
arrivait d'un fichier de donnees, et le gabarit ne portait que
`img.src = r.img`.

**Mesure du 12 septembre 2026, faite dans le navigateur.** La page de
forgemagie posait les icones des runes de transcendance sur
`https://api.dofusdb.fr/img/items/<id>.png`. En parcourant les 36 stats de la
liste, le navigateur du lecteur allait chercher **81 images chez DofusDB**,
128 ms par requete, sur une origine que la politique de confidentialite ne
nommait pas, alors qu'elle nomme chacune des six autres.

Et c'etait le seul endroit du site a le faire. Les illustrations de monstres
de DofusDB, elles, sont **deja** copiees chez nous
(`chardata/monsters/96/*.webp`, 5047 fichiers): le miroir des runes avait meme
ete ecrit dans le scraper, sous une option `--images`, et n'avait jamais ete ni
lance ni branche. Le lot le branche: 81 fichiers webp de 96 pixels, 297 ko au
lieu de 1017 en PNG de 128, la taille que ce site donne deja a ses
illustrations copiees.

Ce que ces tests gardent n'est donc pas <<declarer DofusDB dans la
politique>>, mais la regle plus forte que le site respectait partout ailleurs:
**aucun fichier de donnees livre ne donne au lecteur une adresse hors de chez
nous**. Une regle qui ne peut pas vieillir, contrairement a une liste de
tiers a tenir a jour.
"""

import io
import json
import os
import re

from django.test import SimpleTestCase, TestCase

LANGUES = ('en', 'fr', 'es', 'pt', 'de')

#: Un fichier de donnees a le droit de porter une adresse hors de chez nous
#: seulement s'il figure ici, avec la raison. Aujourd'hui aucun n'en a besoin:
#: le dictionnaire est vide, et c'est ce vide qui est la regle. Une entree
#: ajoutee un jour sera une DECISION, lisible, et pas un oubli.
_ADRESSES_TOLEREES = {}

_URL = re.compile(r'https?://([A-Za-z0-9.-]+)')

#: Le bloc de configuration que la page de forgemagie remet a son JavaScript.
#: Sans ordre impose sur les attributs: le HTML de production est minifie et
#: le minifieur les trie par ordre alphabetique, dans les tests aussi.
_CONFIG = re.compile(
    r'<script[^>]*\bid="fm-config"[^>]*>(.*?)</script>', re.S)

#: Les versions dont le client connait les runes de transcendance. Touch a
#: bifurque avant elles et Retro ne les a jamais eues.
_VERSIONS_AVEC_RUNES = ('dofus3', 'beta', 'dofus2')
_VERSIONS_SANS_RUNES = ('touch', 'retro')


def _dossier_chardata():
    return os.path.dirname(os.path.abspath(__file__))


def _fichiers_de_donnees():
    """(chemin relatif, contenu) pour chaque fichier de donnees livre."""
    racine = _dossier_chardata()
    trouve = []
    for dossier, sous, fichiers in os.walk(racine):
        sous[:] = [d for d in sous if d not in ('__pycache__', 'node_modules')]
        for nom in fichiers:
            if not nom.endswith('.json'):
                continue
            chemin = os.path.join(dossier, nom)
            with io.open(chemin, encoding='utf-8', errors='replace') as f:
                trouve.append((os.path.relpath(chemin, racine), f.read()))
    return trouve


def _catalogue_brut():
    """Le fichier tel qu'il est livre, sans passer par le chargeur."""
    chemin = os.path.join(_dossier_chardata(), 'forgemagie_transcendance.json')
    with io.open(chemin, encoding='utf-8') as f:
        return json.load(f)


def _source_du_scraper():
    chemin = os.path.join(
        os.path.dirname(os.path.dirname(_dossier_chardata())),
        'scripts', 'scrape_transcendance_runes.py')
    with io.open(chemin, encoding='utf-8') as f:
        return f.read()


class TheShippedDataNamesNoForeignHostTests(SimpleTestCase):

    def test_the_scan_actually_reads_the_shipped_data_files(self):
        """Le plancher du temoin.

        Un balayage qui ne trouverait plus rien rendrait zero faute et un vert
        parfait qui ne garde rien. Il exige donc de voir le fichier qui
        portait reellement l'adresse, et pas seulement un nombre: un nombre se
        contente de n'importe quels temoins.
        """
        vus = dict(_fichiers_de_donnees())
        self.assertIn(
            'forgemagie_transcendance.json', vus,
            'the scan no longer sees the file that carried the address, so it '
            'guards nothing')
        self.assertGreaterEqual(
            len(vus), 12,
            'only %d data files found, down from the 14 measured on '
            '2026-09-12; the scan has narrowed' % len(vus))

    def test_no_shipped_data_file_carries_an_address_off_our_domain(self):
        fautifs = []
        for chemin, contenu in _fichiers_de_donnees():
            for hote in sorted(set(_URL.findall(contenu))):
                if hote not in _ADRESSES_TOLEREES:
                    fautifs.append((chemin, hote))
        self.assertFalse(
            fautifs,
            'these shipped data files hand the reader an address nobody '
            'decided about; anything the page puts in a src fetches from it: '
            '%s' % fautifs[:4])


class TheRuneIconsAreMirroredLocallyTests(SimpleTestCase):

    def test_every_rune_in_the_catalogue_has_its_icon_on_disk(self):
        """Une icone qui manque laisse un trou dans la page, sans erreur."""
        runes = _catalogue_brut()['runes']
        self.assertEqual(81, len(runes), 'the catalogue changed size')
        dossier = os.path.join(_dossier_chardata(), 'static', 'chardata',
                               'runes_transcendance')
        manquantes = [r['icon_id'] for r in runes
                      if not os.path.exists(
                          os.path.join(dossier, '%d.webp' % r['icon_id']))]
        self.assertFalse(
            manquantes,
            'these runes are listed but their icon was never mirrored, so the '
            'page shows a hole: %s' % manquantes[:6])

    def test_the_catalogue_records_an_icon_id_and_no_address(self):
        """L'adresse est reconstruite par le chargeur, pas stockee.

        Stockee, elle repart telle quelle vers le navigateur: c'est
        exactement ce qui s'est passe.
        """
        runes = _catalogue_brut()['runes']
        sans_id = [r['id'] for r in runes if not isinstance(
            r.get('icon_id'), int)]
        self.assertFalse(sans_id, 'runes with no usable icon_id: %s'
                         % sans_id[:6])
        avec_adresse = [r['id'] for r in runes if 'img' in r]
        self.assertFalse(
            avec_adresse,
            'the catalogue stores an address again instead of an id: %s'
            % avec_adresse[:6])

    def test_the_loader_builds_the_address_under_our_static_files(self):
        from chardata.forgemagie_transcendance import icon_url
        adresse = icon_url(78179)
        self.assertIn('chardata/runes_transcendance/78179.webp', adresse)
        self.assertNotIn('dofusdb', adresse.lower())


class TheForgemagiePageHandsOutOnlyOurOwnAddressesTests(TestCase):

    def _config(self, game_version):
        prefixe = '' if game_version == 'dofus3' else game_version + '/'
        reponse = self.client.get('/%sforgemagie/' % prefixe, follow=True)
        self.assertEqual(200, reponse.status_code, game_version)
        corps = reponse.content.decode('utf-8')
        bloc = _CONFIG.search(corps)
        self.assertIsNotNone(bloc, 'no fm-config block on %s' % game_version)
        return corps, json.loads(bloc.group(1))

    def test_the_page_points_every_rune_icon_at_our_own_files(self):
        for version in _VERSIONS_AVEC_RUNES:
            with self.subTest(version=version):
                _corps, config = self._config(version)
                runes = [r for entree in config['transcendence'].values()
                         for r in entree['runes']]
                self.assertEqual(81, len(runes), version)
                for rune in runes:
                    self.assertTrue(
                        rune['img'].endswith(
                            'chardata/runes_transcendance/%d.webp'
                            % rune['icon_id']),
                        'rune %s points at %s' % (rune['id'], rune['img']))

    def test_the_page_sends_the_reader_to_dofusdb_nowhere(self):
        """La mesure qui comptait: 81 images allaient y etre cherchees."""
        for version in _VERSIONS_AVEC_RUNES + _VERSIONS_SANS_RUNES:
            with self.subTest(version=version):
                corps, _config = self._config(version)
                self.assertNotIn('dofusdb', corps.lower())

    def test_the_two_versions_without_the_mechanic_are_offered_none(self):
        """Sans ce plancher, un chargeur casse rendrait zero rune partout et
        les assertions ci-dessus seraient vertes sur du vide."""
        for version in _VERSIONS_SANS_RUNES:
            with self.subTest(version=version):
                _corps, config = self._config(version)
                self.assertFalse(config.get('transcendence'))


class TheScraperCannotPutTheAddressBackTests(SimpleTestCase):
    """Le fichier est regenere; corriger le fichier seul ne tient pas.

    Le prochain passage du scraper reecrirait l'adresse, et les tests
    ci-dessus tomberaient sans rien dire de la cause.
    """

    def test_the_scraper_writes_no_address_into_the_catalogue(self):
        source = _source_du_scraper()
        self.assertIn('"icon_id": icon,', source)
        self.assertNotIn('"img":', source)

    def test_the_scraper_always_mirrors_the_icons(self):
        """Le miroir existait deja, derriere une option jamais utilisee.

        On cherche la DECLARATION de l'option, pas le mot: le fichier le cite
        encore dans un commentaire, pour que l'ancienne invocation echoue au
        lieu d'avoir l'air acceptee.
        """
        source = _source_du_scraper()
        self.assertIn('    download_images(runes)', source)
        self.assertNotIn('add_argument("--images"', source)
        self.assertNotIn("add_argument('--images'", source)
        self.assertIn('.webp', source)


class TheCreditsSayWhatTheSiteTakesFromDofusDBTests(TestCase):
    """Le credit disait <<monstres>> pendant que le site prenait aussi les
    runes. Une ligne de credit exacte le jour ou elle est ecrite ne vaut que
    jusqu'a la prochaine donnee prise a la meme source."""

    #: Un temoin par langue, choisi dans la traduction et non dans le nom
    #: propre: <<DofusDB>> prouverait seulement que la marque a survecu.
    TEMOINS = {
        'en': 'transcendence runes with their icons',
        'fr': 'runes de transcendance avec leurs icônes',
        'es': 'runas de trascendencia con sus iconos',
        'pt': 'runas de transcendência com os seus ícones',
        'de': 'Transzendenzrunen mit ihren Symbolen',
    }

    def test_the_about_page_credits_the_runes_in_five_languages(self):
        manquants = []
        for langue in LANGUES:
            reponse = self.client.get('/about/',
                                      headers={'accept-language': langue})
            self.assertEqual(200, reponse.status_code, langue)
            corps = reponse.content.decode('utf-8')
            self.assertIn('dofusdb.fr', corps, langue)
            if self.TEMOINS[langue] not in corps:
                manquants.append(langue)
        self.assertFalse(
            manquants,
            'the credit never reached the page in these languages, so it '
            'still names only the monsters: %s' % manquants)

    def test_the_five_languages_do_not_all_answer_in_english(self):
        """Une entree fuzzy est ignoree sans un mot et la page repasse en
        anglais pendant que le catalogue a l'air complet."""
        self.assertEqual(5, len(set(self.TEMOINS.values())))
