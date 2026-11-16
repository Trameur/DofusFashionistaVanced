# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A dracorune moves the item lines the devblog names and nothing else."""

import json
import os
import tempfile

from django.test import SimpleTestCase

from fashionistapulp.dracorunes import eligible, load_runes, variants

RUNES = {
    'source_tag': 'synthetic',
    'runes': [
        {'item_id': 1, 'kind': 'element', 'target': 'agi'},
        {'item_id': 2, 'kind': 'element', 'target': 'str'},
        {'item_id': 3, 'kind': 'resistance'},
        {'item_id': 4, 'kind': 'power', 'keep': 0.7},
    ],
    'item_types': ['Hat', 'Cloak'],
    'rounding': 'floor',
}


def only(kind, target=None, **extra):
    rune = {'item_id': 9, 'kind': kind}
    if target:
        rune['target'] = target
    if 'keep' in extra:
        rune['keep'] = extra.pop('keep')
    return dict(RUNES, runes=[rune], **extra)


def by_key(stats, runes):
    return {key: dict(lines) for key, lines in variants(stats, runes)}


class ADracoruneMovesTheLinesTheDevblogNamesTests(SimpleTestCase):

    def test_the_devblog_power_example(self):
        stats = [('str', 100), ('earthdam', 10), ('cha', 50),
                 ('waterdam', 5), ('vit', 40)]
        result = by_key(stats, only('power', keep=0.7))
        self.assertEqual(result, {'power': {'vit': 40, 'pow': 70, 'dam': 7}})

    def test_an_element_rune_moves_stat_and_damage_together(self):
        result = by_key([('str', 30), ('earthdam', 4), ('vit', 5)],
                        only('element', 'agi'))
        self.assertEqual(result, {
            'element:str>agi': {'agi': 30, 'airdam': 4, 'vit': 5}})

    def test_only_the_stat_or_only_the_damage_moves(self):
        runes = only('element', 'agi')
        self.assertEqual(by_key([('int', 20)], runes),
                         {'element:int>agi': {'agi': 20}})
        self.assertEqual(by_key([('firedam', 6)], runes),
                         {'element:int>agi': {'airdam': 6}})

    def test_the_target_element_already_on_the_item_is_banned(self):
        runes = only('element', 'agi')
        self.assertEqual(by_key([('str', 30), ('agi', 10)], runes), {})
        self.assertEqual(by_key([('str', 30), ('airdam', 3)], runes), {})

    def test_every_other_element_is_a_source(self):
        result = by_key([('str', 30), ('int', 20)], only('element', 'agi'))
        self.assertEqual(set(result), {'element:str>agi', 'element:int>agi'})
        self.assertEqual(result['element:int>agi'], {'str': 30, 'agi': 20})

    def test_a_negative_line_moves_with_an_element_rune(self):
        result = by_key([('str', -15), ('earthdam', -2)],
                        only('element', 'agi'))
        self.assertEqual(result, {
            'element:str>agi': {'agi': -15, 'airdam': -2}})

    def test_the_power_rune_keeps_a_negative_line_as_is(self):
        result = by_key([('str', 40), ('cha', -10), ('waterdam', -3)],
                        only('power', keep=0.7))
        self.assertEqual(result, {'power': {'cha': -10, 'waterdam': -3,
                                            'pow': 28}})

    def test_the_power_rune_needs_something_positive_to_drop(self):
        self.assertEqual(by_key([('cha', -10), ('vit', 5)],
                                only('power', keep=0.7)), {})

    def test_neutral_damage_is_left_unless_the_data_says_so(self):
        stats = [('neutdam', 10), ('str', 10)]
        self.assertEqual(by_key(stats, only('power', keep=0.7)),
                         {'power': {'neutdam': 10, 'pow': 7}})
        runes = only('power', keep=0.7, power_takes_neutral=True)
        self.assertEqual(by_key(stats, runes), {'power': {'pow': 7,
                                                          'dam': 7}})

    def test_resistances_move_fixed_and_percent_together(self):
        stats = [('fireres', 10), ('fireresper', 5), ('crires', 3),
                 ('pshres', 4), ('respermee', 2)]
        result = by_key(stats, only('resistance'))
        self.assertEqual(set(result), {
            'resistance:fire>neutral', 'resistance:fire>earth',
            'resistance:fire>water', 'resistance:fire>air'})
        self.assertEqual(result['resistance:fire>air'], {
            'airres': 10, 'airresper': 5, 'crires': 3, 'pshres': 4,
            'respermee': 2})

    def test_a_resistance_never_moves_to_an_element_already_present(self):
        stats = [('fireres', 10), ('waterresper', 5)]
        result = by_key(stats, only('resistance'))
        self.assertNotIn('resistance:fire>water', result)
        self.assertNotIn('resistance:water>fire', result)
        self.assertEqual(result['resistance:fire>air'], {
            'airres': 10, 'waterresper': 5})
        self.assertIn('resistance:water>earth', result)

    def test_a_percent_only_resistance_moves(self):
        result = by_key([('neutresper', 7)], only('resistance'))
        self.assertEqual(result['resistance:neutral>air'], {'airresper': 7})

    def test_identical_results_are_deduplicated(self):
        runes = dict(RUNES, runes=[
            {'item_id': 1, 'kind': 'element', 'target': 'agi'},
            {'item_id': 2, 'kind': 'element', 'target': 'agi'},
            {'item_id': 3, 'kind': 'power', 'keep': 0.7},
            {'item_id': 4, 'kind': 'power', 'keep': 0.7}])
        keys = [key for key, _ in variants([('str', 10)], runes)]
        self.assertEqual(sorted(keys), ['element:str>agi', 'power'])

    def test_no_variant_equals_the_original(self):
        self.assertEqual(variants([('pow', 7), ('dam', 7)], RUNES), [])
        self.assertEqual(variants([('vit', 5)], RUNES), [])

    def test_the_rounding_comes_from_the_data(self):
        floor = by_key([('str', 5)], only('power', keep=0.7))
        ceil = by_key([('str', 5)], only('power', keep=0.7, rounding='ceil'))
        self.assertEqual(floor['power']['pow'], 3)
        self.assertEqual(ceil['power']['pow'], 4)

    def test_no_runes_gives_no_variants(self):
        self.assertEqual(variants([('str', 5)], None), [])

    def test_load_runes_is_none_without_a_file(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertIsNone(load_runes('dofus3', folder))
        self.assertIsNone(load_runes('dofus3'))

    def test_load_runes_reads_the_version_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, 'dofus3.json')
            with open(path, 'w', encoding='utf-8') as handle:
                json.dump(RUNES, handle)
            runes = load_runes('dofus3', folder)
            self.assertEqual(runes['source_tag'], 'synthetic')
            self.assertIsNone(load_runes('beta', folder))
            self.assertTrue(variants([('str', 100)], runes))

    def test_eligible_reads_item_types(self):
        self.assertTrue(eligible('Hat', RUNES))
        self.assertFalse(eligible('Ring', RUNES))
        self.assertFalse(eligible('Hat', None))
