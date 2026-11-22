# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""No shipped data file hands the reader's browser an address off our domain."""

import io
import json
import os
import re

from django.test import SimpleTestCase, TestCase

LANGUES = ('en', 'fr', 'es', 'pt', 'de')

# Foreign hosts a data file may carry, with the reason
_ADRESSES_TOLEREES = {}

_URL = re.compile(r'https?://([A-Za-z0-9.-]+)')

# Forgemagie config block, any attribute order: the minifier sorts them
_CONFIG = re.compile(
    r'<script[^>]*\bid="fm-config"[^>]*>(.*?)</script>', re.S)

# Touch forked before transcendence runes, Retro never had them
_VERSIONS_AVEC_RUNES = ('dofus3', 'beta', 'dofus2')
_VERSIONS_SANS_RUNES = ('touch', 'retro')


def _dossier_chardata():
    return os.path.dirname(os.path.abspath(__file__))


def _dossier_des_tables():
    return os.path.join(
        os.path.dirname(os.path.dirname(_dossier_chardata())),
        'fashionistapulp', 'fashionistapulp', 'transcendence')


def _fichiers_de_donnees():
    """(relative path, content) for each shipped .json file, rune tables included."""
    trouve = []
    depot = os.path.dirname(os.path.dirname(_dossier_chardata()))
    for racine in (_dossier_chardata(), _dossier_des_tables()):
        for dossier, sous, fichiers in os.walk(racine):
            sous[:] = [d for d in sous
                       if d not in ('__pycache__', 'node_modules')]
            for nom in fichiers:
                if not nom.endswith('.json'):
                    continue
                chemin = os.path.join(dossier, nom)
                with io.open(chemin, encoding='utf-8', errors='replace') as f:
                    trouve.append((os.path.relpath(chemin, depot), f.read()))
    return trouve


def _catalogue_brut(version='dofus3'):
    """The table as shipped, without the loader."""
    chemin = os.path.join(_dossier_des_tables(), '%s.json' % version)
    with io.open(chemin, encoding='utf-8') as f:
        return json.load(f)


def _source_du_telechargeur():
    chemin = os.path.join(
        os.path.dirname(os.path.dirname(_dossier_chardata())),
        'itemscraper', 'download_transcendence_icons.py')
    with io.open(chemin, encoding='utf-8') as f:
        return f.read()


class TheShippedDataNamesNoForeignHostTests(SimpleTestCase):

    def test_the_scan_actually_reads_the_shipped_data_files(self):
        vus = dict(_fichiers_de_donnees())
        self.assertIn(
            os.path.join('fashionistapulp', 'fashionistapulp', 'transcendence',
                         'beta.json'), vus,
            'the scan no longer sees the rune tables, so it guards nothing')
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
        dossier = os.path.join(_dossier_chardata(), 'static', 'chardata',
                               'runes_transcendance')
        manquantes = []
        for version, taille in (('dofus3', 81), ('beta', 85), ('dofus2', 81)):
            runes = _catalogue_brut(version)['runes']
            self.assertEqual(taille, len(runes), 'the %s table changed size'
                             % version)
            manquantes += [r['icon_id'] for r in runes
                           if not os.path.exists(
                               os.path.join(dossier, '%d.webp' % r['icon_id']))]
        self.assertFalse(
            manquantes,
            'these runes are listed but their icon was never mirrored, so the '
            'page shows a hole: %s' % manquantes[:6])

    def test_the_catalogue_records_an_icon_id_and_no_address(self):
        """The loader builds the address from the id."""
        runes = [r for version in ('dofus3', 'beta', 'dofus2')
                 for r in _catalogue_brut(version)['runes']]
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
                self.assertEqual(85 if version == 'beta' else 81, len(runes),
                                 version)
                for rune in runes:
                    self.assertTrue(
                        rune['img'].endswith(
                            'chardata/runes_transcendance/%d.webp'
                            % rune['icon_id']),
                        'rune %s points at %s' % (rune['id'], rune['img']))

    def test_the_page_sends_the_reader_to_dofusdb_nowhere(self):
        for version in _VERSIONS_AVEC_RUNES + _VERSIONS_SANS_RUNES:
            with self.subTest(version=version):
                corps, _config = self._config(version)
                self.assertNotIn('dofusdb', corps.lower())

    def test_the_two_versions_without_the_mechanic_are_offered_none(self):
        for version in _VERSIONS_SANS_RUNES:
            with self.subTest(version=version):
                _corps, config = self._config(version)
                self.assertFalse(config.get('transcendence'))


class TheIconsComeFromTheGameDataNotFromDofusDBTests(SimpleTestCase):
    """The icons are fetched by itemscraper/download_transcendence_icons.py."""

    def test_the_downloader_reads_the_dofusdude_resource_files_only(self):
        source = _source_du_telechargeur()
        self.assertIn('all_resources_en.json', source)
        self.assertNotIn('dofusdb', source.lower())
        self.assertNotIn('http://', source)
        self.assertNotIn('https://', source)

    def test_the_downloader_can_fetch_the_icons_again_and_writes_webp(self):
        source = _source_du_telechargeur()
        self.assertIn("'--replace'", source)
        self.assertIn("'WEBP'", source)


class TheCreditsSayWhatTheSiteTakesFromDofusDBTests(TestCase):

    # One translated phrase per language, not the brand name
    TEMOINS = {
        'en': 'where monsters are found and their artwork for Dofus 3 and the Beta',
        'fr': 'zones où trouver les monstres et leurs illustrations pour Dofus 3 et la Beta',
        'es': 'zonas donde encontrar los monstruos y sus ilustraciones para Dofus 3 y la Beta',
        'pt': 'zonas onde encontrar os monstros e as suas ilustrações para o Dofus 3 e o Beta',
        'de': 'Fundorte und Illustrationen der Monster für Dofus 3 und die Beta',
    }

    # What the credit used to add, now that the runes come from the game files
    ANCIENS = {
        'en': 'transcendence runes with their icons',
        'fr': 'runes de transcendance avec leurs icônes',
        'es': 'runas de trascendencia con sus iconos',
        'pt': 'runas de transcendência com os seus ícones',
        'de': 'Transzendenzrunen mit ihren Symbolen',
    }

    def test_the_about_page_credits_only_the_monsters_in_five_languages(self):
        manquants, restes = [], []
        for langue in LANGUES:
            reponse = self.client.get('/about/',
                                      headers={'accept-language': langue})
            self.assertEqual(200, reponse.status_code, langue)
            corps = reponse.content.decode('utf-8')
            self.assertIn('dofusdb.fr', corps, langue)
            if self.TEMOINS[langue] not in corps:
                manquants.append(langue)
            if self.ANCIENS[langue] in corps:
                restes.append(langue)
        self.assertFalse(
            manquants,
            'the credit never reached the page in these languages: %s'
            % manquants)
        self.assertFalse(
            restes,
            'the page still credits DofusDB for the runes in: %s' % restes)

    def test_the_five_languages_do_not_all_answer_in_english(self):
        """A fuzzy .po entry silently falls back to English."""
        self.assertEqual(5, len(set(self.TEMOINS.values())))
