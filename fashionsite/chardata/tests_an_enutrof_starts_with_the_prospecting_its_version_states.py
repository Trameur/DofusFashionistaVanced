# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A character starts with the AP, MP and prospecting its own version's client states."""

import contextlib
import io
import json
import os
import tempfile
from unittest import mock

from django.test import SimpleTestCase, TestCase

from chardata.models import Char
from chardata.solution import _repair_character_base
from chardata.starting_stats import (HAND_LEVEL_AP, HAND_STATS,
                                     starting_stats_table)
from chardata.tests import itemscraper_module
from chardata.util import base_stats_by_attr_for
from fashionistapulp.modelresult import ModelResultMinimal

VERSIONS = ('dofus3', 'beta', 'dofus2', 'touch', 'retro')

# {version: {stat: (value, texts stating it)}}
STATED = {
    'dofus3': {'level_ap': ({'level': 100, 'AP': 1}, ['fr.json 1119992'])},
    'beta': {'level_ap': ({'level': 100, 'AP': 1}, ['fr.json 1119992'])},
    'dofus2': {'level_ap': ({'level': 100, 'AP': 1}, ['fr.json 880605'])},
    'touch': {
        'all/AP': (6, ['Documents_fr.json 133']),
        'all/MP': (3, ['Documents_fr.json 133']),
        'all/Prospecting': (100, ['Documents_fr.json 133']),
    },
    'retro': {
        'all/AP': (6, ['kb_fr.json KBA 16']),
        'all/MP': (3, ['kb_fr.json KBA 15']),
        'all/Prospecting': (100, ['kb_fr.json KBA 14']),
        'classes/Enutrof/Prospecting': (120, ['kb_fr.json KBA 14']),
    },
}

ENUTROF_PROSPECTING = {'dofus3': 100, 'beta': 100, 'dofus2': 100,
                       'touch': 100, 'retro': 120}


def _extractor():
    return itemscraper_module('store_starting_stats')


def _flat(table, prefix=''):
    out = {}
    for key, value in table.items():
        if isinstance(value, dict) and key != 'level_ap':
            out.update(_flat(value, prefix + key + '/'))
        else:
            out[prefix + key] = value
    return out


def _char(char_class, game_version, level=200):
    return Char.objects.create(
        name='p', char_name='p', char_class=char_class, char_build='b',
        level=level, minimum_stats=b'', minimum_crits=b'', stats_weight=b'',
        options=b'', inclusions=b'', exclusions=b'', link_shared=False,
        game_version=game_version)


class TheVersionTablesTests(SimpleTestCase):

    def test_each_version_holds_what_its_client_states_and_where(self):
        for version in VERSIONS:
            table = starting_stats_table(version)
            sources = _flat(table.get('sources') or {})
            values = _flat({key: value for key, value in table.items()
                            if key != 'sources'})
            with self.subTest(version=version):
                self.assertEqual(
                    {stat: value for stat, (value, _where)
                     in STATED[version].items()}, values)
                self.assertEqual(
                    {stat: where for stat, (_value, where)
                     in STATED[version].items()}, sources)

    def test_the_pipeline_reads_the_same_from_the_client_files(self):
        extractor = _extractor()
        read = 0
        for version in VERSIONS:
            if not os.path.exists(extractor.source_path(version)):
                continue
            read += 1
            table, notes = extractor.extract(version)
            with self.subTest(version=version):
                self.assertEqual([], notes)
                self.assertEqual(starting_stats_table(version), table)
        if not read:
            self.skipTest('no client file on this machine')

    def test_no_modern_text_gives_a_class_its_own_start(self):
        for version in ('dofus3', 'beta', 'dofus2'):
            with self.subTest(version=version):
                self.assertNotIn('classes', starting_stats_table(version))


class TheExtractorTests(SimpleTestCase):

    def _extract(self, texts, names=None):
        extractor = _extractor()
        with mock.patch.object(extractor, 'texts', return_value=texts), \
                mock.patch.object(extractor, 'class_names',
                                  return_value=names or {}):
            return extractor.extract('retro')

    def test_a_plural_class_name_reaches_the_site_class(self):
        table, notes = self._extract(
            [('kb 1', 'Tu possèdes 100 points de Prospection quand tu '
                      'débutes (120 pour les Enutrofs)')],
            {'enutrof': 'Enutrof'})
        self.assertEqual([], notes)
        self.assertEqual({'Enutrof': {'Prospecting': 120}}, table['classes'])
        self.assertEqual({'Prospecting': 100}, table['all'])

    def test_client_markup_is_read_through(self):
        table, _notes = self._extract([(
            'fr.json 1', 'Au niveau 100, votre personnage obtient <b><color='
                         '"white">1 {{featureDescription,49::PA}}</color></b> '
                         'supplémentaire.')])
        self.assertEqual({'level': 100, 'AP': 1}, table['level_ap'])

    def test_texts_that_disagree_leave_the_stat_to_the_site(self):
        table, notes = self._extract([
            ('kb 1', 'Fixés à 6 PA pour tous les combattants'),
            ('kb 2', 'Fixés à 7 PA pour tous les combattants'),
        ])
        self.assertNotIn('all', table)
        self.assertEqual(1, len(notes))

    def test_a_class_the_version_does_not_have_is_reported(self):
        table, notes = self._extract(
            [('kb 1', '100 points de Prospection quand tu débutes '
                      '(120 pour les Inconnus)')])
        self.assertNotIn('classes', table)
        self.assertEqual(1, len(notes))

    def test_a_stat_that_changes_prints_a_warning(self):
        extractor = _extractor()
        with tempfile.TemporaryDirectory() as folder:
            with open(os.path.join(folder, 'retro.json'), 'w',
                      encoding='utf-8') as handle:
                json.dump({'classes': {'Enutrof': {'Prospecting': 120}}},
                          handle)
            output = io.StringIO()
            with mock.patch.object(extractor, 'OUTPUT_DIR', folder), \
                    mock.patch.object(extractor, 'source_path',
                                      return_value=folder), \
                    mock.patch.object(extractor, 'extract',
                                      return_value=({}, [])), \
                    contextlib.redirect_stdout(output):
                extractor.main(['--game-version', 'retro'])
            with open(os.path.join(folder, 'retro.json'),
                      encoding='utf-8') as handle:
                written = json.load(handle)
        self.assertIn('warning: retro classes/Enutrof/Prospecting changed: '
                      '120 -> None', output.getvalue())
        self.assertEqual({}, written)


class TheCharacterSheetTests(TestCase):

    def test_an_enutrof_starts_with_the_prospecting_of_its_version(self):
        for version, prospecting in ENUTROF_PROSPECTING.items():
            with self.subTest(version=version):
                base = base_stats_by_attr_for(_char('Enutrof', version))
                self.assertEqual(prospecting, base['Prospecting'])

    def test_other_classes_start_with_100_on_every_version(self):
        for version in VERSIONS:
            for char_class in ('Iop', 'Sacrier', 'Feca'):
                with self.subTest(version=version, char_class=char_class):
                    base = base_stats_by_attr_for(_char(char_class, version))
                    self.assertEqual(100, base['Prospecting'])

    def test_the_extra_ap_comes_at_level_100_on_every_version(self):
        for version in VERSIONS:
            for level, ap in ((1, 6), (99, 6), (100, 7), (200, 7)):
                with self.subTest(version=version, level=level):
                    base = base_stats_by_attr_for(
                        _char('Iop', version, level))
                    self.assertEqual(ap, base['AP'])

    def test_what_no_client_text_states_takes_the_hand_value(self):
        for version in VERSIONS:
            stated = {stat.split('/')[-1] for stat in STATED[version]
                      if stat.startswith('all/')}
            base = base_stats_by_attr_for(_char('Iop', version, 1))
            for stat, value in HAND_STATS.items():
                if stat in stated:
                    continue
                with self.subTest(version=version, stat=stat):
                    self.assertEqual(value, base[stat])
        self.assertEqual({'level': 100, 'AP': 1}, HAND_LEVEL_AP)

    def test_a_legacy_solution_without_a_base_gets_its_version_start(self):
        for version, prospecting in ENUTROF_PROSPECTING.items():
            minimal = ModelResultMinimal({}, {'char_level': 200}, {})
            _repair_character_base(_char('Enutrof', version), minimal)
            with self.subTest(version=version):
                base = minimal.input['base_stats_by_attr']
                self.assertEqual(prospecting, base['Prospecting'])
                self.assertEqual(7, base['AP'])

    def test_a_stored_base_keeps_the_prospecting_it_was_solved_with(self):
        for version in VERSIONS:
            stored = {'AP': 7, 'Prospecting': 120}
            minimal = ModelResultMinimal(
                {}, {'base_stats_by_attr': dict(stored)}, {})
            _repair_character_base(_char('Enutrof', version), minimal)
            with self.subTest(version=version):
                self.assertEqual(stored, minimal.input['base_stats_by_attr'])
