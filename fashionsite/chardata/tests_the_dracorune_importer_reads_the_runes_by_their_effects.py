# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The importer finds the runes by their effect actions and names the element
the client gives each one."""

import contextlib
import io
import json
import os
import sys
import tempfile

from django.test import SimpleTestCase

from chardata.tests import itemscraper_module
from fashionistapulp.dracorunes import eligible, load_runes, variants


def _effect(rid, action, dice_side=0, value=None):
    data = {'actionId': action, 'diceSide': dice_side}
    if value is not None:
        data['value'] = value
    return {'rid': rid, 'type': {'class': 'EffectInstanceDice'}, 'data': data}


def _item(rid, effect_rids):
    return {'rid': rid, 'type': {'class': 'ItemData'},
            'data': {'possibleEffects': {'Array': [{'rid': r} for r in effect_rids]}}}


def _dump(folder, items):
    """items: {item id: [(action, diceSide[, value])]} in the Unity export
    layout."""
    refs = []
    values = []
    rid = 1000
    for item_id, effects in items.items():
        effect_rids = []
        for action, side, *value in effects:
            rid += 1
            refs.append(_effect(rid, action, side, *value))
            effect_rids.append(rid)
        rid += 1
        refs.append(_item(rid, effect_rids))
        values.append({'rid': rid})
    data = {'references': {'RefIds': refs},
            'objectsById': {'m_keys': {'Array': list(items)},
                            'm_values': {'Array': values}}}
    with open(os.path.join(folder, 'items.json'), 'w', encoding='utf-8') as out:
        json.dump(data, out)


RUNE_ITEMS = {
    10: [(4081, 4), (4180, 0)],
    11: [(4081, 2), (4180, 0)],
    12: [(4081, 3), (4180, 0)],
    13: [(4081, 1), (4180, 0)],
    14: [(4082, 0), (4180, 0)],
    15: [(4083, 0, 60), (4180, 0)],
    20: [(118, 0)],
    21: [(4180, 0)],
}


class TheDracoruneImporterReadsTheRunesByTheirEffectsTests(SimpleTestCase):

    def setUp(self):
        self.store = itemscraper_module('store_dracorunes')
        self.raw = tempfile.TemporaryDirectory()
        self.out = tempfile.TemporaryDirectory()
        self.addCleanup(self.raw.cleanup)
        self.addCleanup(self.out.cleanup)

    def _written(self, items, tag='9.9.9.9'):
        _dump(self.raw.name, items)
        path = self.store.write(self.raw.name, tag, 'beta', self.out.name)
        return path

    def test_a_rune_is_an_item_with_one_of_the_three_actions(self):
        self._written(RUNE_ITEMS)
        runes = self.store.read_runes(self.raw.name)
        self.assertEqual([10, 11, 12, 13, 14, 15],
                         [rune['item_id'] for rune in runes])

    def test_each_element_code_gives_its_characteristic(self):
        self._written(RUNE_ITEMS)
        runes = load_runes('beta', self.out.name)['runes']
        targets = {rune['item_id']: rune.get('target') for rune in runes}
        self.assertEqual(
            {10: 'agi', 11: 'int', 12: 'cha', 13: 'str', 14: None, 15: None},
            targets)

    def test_the_kinds_follow_the_actions(self):
        self._written(RUNE_ITEMS)
        runes = load_runes('beta', self.out.name)['runes']
        self.assertEqual(
            ['element'] * 4 + ['resistance', 'power'],
            [rune['kind'] for rune in runes])

    def test_the_table_flags_what_the_client_does_not_state(self):
        self._written(RUNE_ITEMS, tag='3.8.1.2')
        table = load_runes('beta', self.out.name)
        self.assertEqual('3.8.1.2', table['source_tag'])
        self.assertEqual('floor', table['rounding'])
        self.assertFalse(table['power_takes_neutral'])
        self.assertEqual(0.6, table['runes'][-1]['keep'])
        self.assertEqual(['rounding', 'power_takes_neutral'],
                         table['unverified'])
        self.assertEqual('devblog 1772495', table['unverified_source'])

    def test_the_stored_table_draconizes_a_line_of_agility_and_air_damage(self):
        self._written(RUNE_ITEMS)
        table = load_runes('beta', self.out.name)
        self.assertTrue(eligible('Hat', table))
        self.assertFalse(eligible('Dofus', table))
        found = {key: dict(lines) for key, lines in variants(
            [('agi', 30), ('airdam', 4), ('vit', 5)], table)}
        self.assertEqual({'str': 30, 'earthdam': 4, 'vit': 5},
                         found['element:agi>str'])
        self.assertEqual({'int': 30, 'firedam': 4, 'vit': 5},
                         found['element:agi>int'])
        self.assertEqual({'vit': 5, 'pow': 18, 'dam': 2}, found['power'])

    def _quiet(self, call):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            result = call()
        return result, buffer.getvalue()

    def _main(self, *arguments):
        old = sys.argv
        sys.argv = ['store_dracorunes.py', *arguments]
        try:
            return self._quiet(self.store.main)
        finally:
            sys.argv = old

    def test_no_rune_writes_no_file(self):
        path, _ = self._quiet(lambda: self._written(
            {20: [(118, 0)], 21: [(4180, 0)]}))
        self.assertIsNone(path)
        self.assertEqual([], os.listdir(self.out.name))
        self.assertIsNone(load_runes('beta', self.out.name))

    def test_no_rune_removes_the_stale_file_of_that_version_only(self):
        self._written(RUNE_ITEMS)
        other = os.path.join(self.out.name, 'other.json')
        with open(other, 'w', encoding='utf-8') as handle:
            handle.write('{}')
        path, output = self._quiet(lambda: self._written({20: [(118, 0)]}))
        self.assertIsNone(path)
        self.assertEqual(['other.json'], os.listdir(self.out.name))
        self.assertIn('warning', output)
        self.assertIn('removed', output)

    def test_no_rune_keeps_a_version_file_that_is_not_a_rune_table(self):
        path = os.path.join(self.out.name, 'beta.json')
        with open(path, 'w', encoding='utf-8') as handle:
            json.dump({'weapons': []}, handle)
        _, output = self._quiet(lambda: self._written({20: [(118, 0)]}))
        self.assertEqual(['beta.json'], os.listdir(self.out.name))
        self.assertIn('warning', output)
        self.assertIn('kept', output)

    def test_a_version_with_a_path_is_refused(self):
        _dump(self.raw.name, {20: [(118, 0)]})
        for version in ('../beta', 'a/b', '..', ''):
            with self.assertRaises(ValueError):
                self.store.write(self.raw.name, '1', version, self.out.name)

    def test_a_rune_filed_under_effect_id_is_read(self):
        _dump(self.raw.name, RUNE_ITEMS)
        path = os.path.join(self.raw.name, 'items.json')
        with open(path, encoding='utf-8') as handle:
            text = handle.read()
        with open(path, 'w', encoding='utf-8') as handle:
            handle.write(text.replace('"actionId"', '"effectId"'))
        runes = self.store.read_runes(self.raw.name)
        self.assertEqual([10, 11, 12, 13, 14, 15],
                         [rune['item_id'] for rune in runes])

    def test_no_rune_and_no_file_prints_no_warning(self):
        _, output = self._quiet(lambda: self._written({20: [(118, 0)]}))
        self.assertNotIn('warning', output)

    def test_an_unknown_element_code_is_skipped_with_a_warning(self):
        items = dict(RUNE_ITEMS)
        items[16] = [(4081, 99)]
        _, output = self._quiet(lambda: self._written(items))
        runes = load_runes('beta', self.out.name)['runes']
        self.assertNotIn(16, [rune['item_id'] for rune in runes])
        self.assertIn('warning: rune 16 has unknown element code 99, skipped',
                      output)

    def test_a_power_rune_without_a_rate_is_skipped_with_a_warning(self):
        items = dict(RUNE_ITEMS)
        items[15] = [(4083, 0, 0)]
        _, output = self._quiet(lambda: self._written(items))
        runes = load_runes('beta', self.out.name)['runes']
        self.assertNotIn(15, [rune['item_id'] for rune in runes])
        self.assertIn('warning', output)

    def test_the_source_tag_of_a_raw_folder_is_its_version_number(self):
        parent = tempfile.TemporaryDirectory()
        self.addCleanup(parent.cleanup)
        raw = os.path.join(parent.name, 'raw_3.8.1.2')
        os.mkdir(raw)
        _dump(raw, RUNE_ITEMS)
        self._main(raw, '--output-folder', self.out.name)
        self.assertEqual('3.8.1.2',
                         load_runes('beta', self.out.name)['source_tag'])

    def test_the_command_line_exits_zero_without_a_rune(self):
        _dump(self.raw.name, {20: [(118, 0)]})
        code, _ = self._main(self.raw.name, '--output-folder', self.out.name)
        self.assertEqual(0, code)
        self.assertEqual([], os.listdir(self.out.name))
