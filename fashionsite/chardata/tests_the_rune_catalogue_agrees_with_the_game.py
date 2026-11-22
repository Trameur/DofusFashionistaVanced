# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The transcendence rune tables match the Dofus 2.73 client and the game dumps."""

import io
import json
import os
import re

from django.test import SimpleTestCase, TestCase
from django.utils.translation import override

# Runes per rank on Dofus 3 and Dofus 2; the Beta adds two Ta and two Gata
_RANGS_ATTENDUS = {'Ta': 36, 'Pata': 25, 'Rata': 20}
_RANGS_DE_LA_BETA = {'Ta': 38, 'Pata': 25, 'Rata': 20, 'Gata': 2}
_RUNES_PAR_VERSION = {'dofus3': 81, 'beta': 85, 'dofus2': 81}

# Names Touch would carry if it had transcendence
_MARQUEURS = ('Rune Ta ', 'Rune Pata', 'Rune Rata')

# Ankama names each rune differently in every language
LANGUES_JEU = ('fr', 'en', 'es', 'pt', 'de')

_CONFIG = re.compile(
    r'<script[^>]*\bid="fm-config"[^>]*>(.*?)</script>', re.S)


def _racine_depot():
    return os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))


def _table(version):
    chemin = os.path.join(_racine_depot(), 'fashionistapulp',
                          'fashionistapulp', 'transcendence',
                          '%s.json' % version)
    with io.open(chemin, encoding='utf-8') as f:
        return json.load(f)


def _runes(version):
    from fashionistapulp.transcendence import load_runes
    return load_runes(version)


def _rangs_du_catalogue(version):
    rangs = {}
    for rune in _runes(version):
        rangs[rune['rank_label']] = rangs.get(rune['rank_label'], 0) + 1
    return rangs


def _rangs_du_client_dofus2():
    """Runes per rank in the 2.73 client's text table."""
    chemin = os.path.join(_racine_depot(), 'itemscraper', 'raw', '2.73.3.14',
                          'fr.json')
    with io.open(chemin, encoding='utf-8') as f:
        textes = json.load(f)['texts']
    rangs = {}
    for valeur in textes.values():
        if not isinstance(valeur, str) or not valeur.startswith('Rune '):
            continue
        morceaux = valeur.split()
        if len(morceaux) > 1 and morceaux[1] in _RANGS_ATTENDUS:
            rangs[morceaux[1]] = rangs.get(morceaux[1], 0) + 1
    return rangs


class TheCatalogueAgreesWithAnkamasOwnClientTests(SimpleTestCase):

    def test_the_catalogue_splits_the_ranks_the_way_it_was_measured(self):
        for version in ('dofus3', 'dofus2'):
            with self.subTest(version=version):
                self.assertEqual(_RANGS_ATTENDUS, _rangs_du_catalogue(version))
                self.assertEqual(81, len(_runes(version)))
        self.assertEqual(_RANGS_DE_LA_BETA, _rangs_du_catalogue('beta'))
        self.assertEqual(85, len(_runes('beta')))

    def test_ankamas_own_client_names_exactly_the_same_runes(self):
        self.assertEqual(_RANGS_ATTENDUS, _rangs_du_client_dofus2())

    def test_the_two_sources_are_really_two(self):
        """The two tests above must not read the same file."""
        chemin = os.path.join(_racine_depot(), 'itemscraper', 'raw',
                              '2.73.3.14', 'fr.json')
        self.assertTrue(os.path.exists(chemin), 'the 2.73 text table is gone')
        for version in _RUNES_PAR_VERSION:
            donnees = _table(version)
            self.assertEqual(len(donnees['runes']), donnees['count'], version)
            self.assertNotIn('dofusdb', json.dumps(donnees).lower(), version)
        self.assertEqual('2.73.3.14', _table('dofus2')['source_tag'])


class OnlyTheVersionsWithTheMechanicOfferItTests(SimpleTestCase):

    def test_the_touch_client_knows_no_transcendence_rune(self):
        chemin = os.path.join(_racine_depot(), 'itemscraper', 'touch_raw',
                              'Items_fr.json')
        with io.open(chemin, encoding='utf-8', errors='replace') as f:
            texte = f.read()
        self.assertGreater(texte.lower().count('rune'), 100,
                           'this file carries no rune at all, so the zero '
                           'below would prove nothing')
        presents = [m for m in _MARQUEURS if m in texte]
        self.assertFalse(presents,
                         'Touch turns out to name these after all: %s'
                         % presents)

    def test_the_site_offers_them_on_three_versions_and_no_other(self):
        from chardata.forgemagie_transcendance import get_transcendence_runes
        offertes = {}
        for version in ('dofus3', 'beta', 'dofus2', 'touch', 'retro', 'wakfu'):
            offertes[version] = len(get_transcendence_runes(version))
        self.assertEqual({'dofus3': 81, 'beta': 85, 'dofus2': 81,
                          'touch': 0, 'retro': 0, 'wakfu': 0}, offertes)


class TheRunesTakeTheNameTheReadersClientGivesThemTests(SimpleTestCase):

    def _noms_ankama(self):
        """{French name: {language: name}} from the 2.73 client."""
        tables = {}
        for langue in LANGUES_JEU:
            chemin = os.path.join(_racine_depot(), 'itemscraper', 'raw',
                                  '2.73.3.14', '%s.json' % langue)
            with io.open(chemin, encoding='utf-8') as f:
                tables[langue] = json.load(f)['texts']
        sortie = {}
        for identifiant, valeur in tables['fr'].items():
            if not isinstance(valeur, str) or not valeur.startswith('Rune '):
                continue
            morceaux = valeur.split()
            if len(morceaux) > 1 and morceaux[1] in _RANGS_ATTENDUS:
                sortie[valeur] = dict(
                    (l, tables[l].get(identifiant)) for l in LANGUES_JEU)
        return sortie

    def test_the_catalogue_carries_a_name_in_every_language(self):
        vides = [(rune['id'], langue)
                 for version in _RUNES_PAR_VERSION
                 for rune in _runes(version)
                 for langue in LANGUES_JEU
                 if not (rune.get('names') or {}).get(langue)]
        self.assertFalse(vides, 'runes with a missing name: %s' % vides[:6])

    def test_ankamas_own_client_confirms_all_four_hundred_and_five(self):
        ankama = self._noms_ankama()
        self.assertEqual(81, len(ankama))
        desaccords, verifies = [], 0
        for rune in _runes('dofus2'):
            noms = rune['names']
            chez_ankama = ankama.get(noms['fr'])
            self.assertIsNotNone(
                chez_ankama, 'Ankama does not name %s' % noms['fr'])
            for langue in LANGUES_JEU:
                verifies += 1
                if noms[langue] != chez_ankama[langue]:
                    desaccords.append((noms['fr'], langue, noms[langue],
                                       chez_ankama[langue]))
        self.assertEqual(405, verifies)
        self.assertFalse(desaccords,
                         'the catalogue and the game disagree: %s'
                         % desaccords[:4])

    def test_every_rune_is_renamed_by_the_game_in_every_language(self):
        pareils = [rune['names']['fr'] for version in _RUNES_PAR_VERSION
                   for rune in _runes(version)
                   if len(set(rune['names'][l] for l in LANGUES_JEU)) == 1]
        self.assertFalse(
            pareils,
            'these runes carry one name in all five languages, so translating '
            'them changes nothing: %s' % pareils[:4])

    def test_the_rank_is_read_in_french_because_it_is_a_key(self):
        """Spanish ranks are Ta/Buta/Suta."""
        rangs = set(rune['rank_label'] for version in _RUNES_PAR_VERSION
                    for rune in _runes(version))
        self.assertEqual({'Ta', 'Pata', 'Rata', 'Gata'}, rangs)
        espagnols = set()
        for rune in _runes('dofus3'):
            morceaux = rune['names']['es'].split()
            if len(morceaux) > 1:
                espagnols.add(morceaux[1])
        self.assertTrue(
            espagnols - rangs,
            'Spanish now uses the French rank words, so this reason is stale')


class ThePagesNameTheRuneInTheReadersLanguageTests(TestCase):

    def _config(self, langue):
        reponse = self.client.get('/forgemagie/',
                                  headers={'accept-language': langue})
        self.assertEqual(200, reponse.status_code, langue)
        corps = reponse.content.decode('utf-8')
        bloc = _CONFIG.search(corps)
        self.assertIsNotNone(bloc, langue)
        return json.loads(bloc.group(1))

    def test_the_workshop_serves_each_language_its_own_names(self):
        attendus = {}
        for rune in _runes('dofus3'):
            attendus[rune['id']] = rune['names']
        vus = {}
        for langue in LANGUES_JEU:
            config = self._config(langue)
            runes = [r for entree in config['transcendence'].values()
                     for r in entree['runes']]
            self.assertEqual(81, len(runes), langue)
            for rune in runes:
                self.assertEqual(attendus[rune['id']][langue], rune['name'],
                                 '%s, rune %s' % (langue, rune['id']))
            vus[langue] = sorted(r['name'] for r in runes)
        for langue in LANGUES_JEU:
            if langue != 'fr':
                self.assertNotEqual(
                    vus['fr'], vus[langue],
                    'the page still serves the French names to %s' % langue)

    def test_the_chip_says_the_stat_in_the_readers_language_too(self):
        """The tables carry no stat label: the page reads the site's own."""
        vus = {}
        for langue in LANGUES_JEU:
            config = self._config(langue)
            entree = config['transcendence'].get('vit')
            self.assertIsNotNone(entree, langue)
            vus[langue] = entree['label']
        self.assertEqual(
            len(LANGUES_JEU), len(set(vus.values())),
            'the stat label does not follow the reader: %s' % vus)

    def test_the_build_page_names_the_suggested_rune_in_the_readers_language(
            self):
        from chardata.solution_result import attach_transcendence
        from fashionistapulp.structure import set_current_game_version

        class Piece(object):
            item_added = True
            type = 'Amulet'
            stats = {}

        set_current_game_version('dofus3')
        vus = {}
        for langue in LANGUES_JEU:
            piece = Piece()
            with override(langue):
                attach_transcendence(piece, {'int': 10})
            self.assertTrue(piece.transcendence, langue)
            vus[langue] = piece.transcendence
        for langue in LANGUES_JEU:
            if langue != 'fr':
                self.assertNotEqual(
                    vus['fr'], vus[langue],
                    'the build page still says %s to a %s reader'
                    % (vus['fr'], langue))

    def test_an_unknown_language_falls_back_instead_of_showing_nothing(self):
        from chardata.forgemagie_transcendance import rune_name
        rune = _runes('dofus3')[0]
        self.assertEqual(rune['names']['en'], rune_name(rune, 'it'))
        self.assertEqual(rune['names']['fr'], rune_name({'names': {
            'fr': rune['names']['fr']}}, 'it'))
        self.assertEqual('', rune_name({}, 'en'))
