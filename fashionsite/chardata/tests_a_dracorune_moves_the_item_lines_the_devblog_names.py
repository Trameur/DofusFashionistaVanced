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

    def test_a_negative_resistance_line_moves_with_the_resistance_rune(self):
        result = by_key([('earthres', 5), ('earthresper', -3)],
                        only('resistance'))
        self.assertEqual(result['resistance:earth>air'],
                         {'airres': 5, 'airresper': -3})

    def test_the_power_rune_adds_to_an_existing_power_and_damage_line(self):
        stats = [('str', 100), ('pow', 10), ('earthdam', 10), ('dam', 3)]
        result = by_key(stats, only('power', keep=0.7))
        self.assertEqual(result, {'power': {'pow': 80, 'dam': 10}})

    def test_the_power_rune_on_damage_lines_alone_adds_no_power_line(self):
        result = by_key([('firedam', 10)], only('power', keep=0.7))
        self.assertEqual(result, {'power': {'dam': 7}})

    def test_a_negative_line_in_the_target_element_blocks_that_target(self):
        runes = dict(RUNES, runes=[
            {'item_id': 1, 'kind': 'element', 'target': 'agi'},
            {'item_id': 2, 'kind': 'element', 'target': 'str'},
            {'item_id': 3, 'kind': 'element', 'target': 'int'}])
        result = by_key([('agi', -10), ('str', 30)], runes)
        self.assertEqual(set(result), {'element:agi>int', 'element:str>int'})
        self.assertEqual(result['element:agi>int'], {'int': -10, 'str': 30})
        self.assertEqual(result['element:str>int'], {'agi': -10, 'int': 30})

    def test_a_line_stored_at_zero_counts_as_present_and_is_kept(self):
        stats = [('str', 30), ('agi', 0)]
        self.assertEqual(by_key(stats, only('element', 'agi')), {})
        result = by_key(stats, only('element', 'int'))
        self.assertEqual(result, {'element:str>int': {'int': 30, 'agi': 0}})

    def test_moving_a_zero_line_alone_gives_no_variant(self):
        self.assertEqual(variants([('agi', 0), ('vit', 5)],
                                  only('element', 'int')), [])

    def test_a_zero_line_moves_with_its_nonzero_partner(self):
        result = by_key([('agi', 0), ('airdam', 5)], only('element', 'int'))
        self.assertEqual(result, {'element:agi>int': {'int': 0, 'firedam': 5}})

    def test_a_zero_resistance_line_blocks_a_target_and_never_moves_alone(self):
        result = by_key([('fireres', 4), ('airres', 0)], only('resistance'))
        self.assertNotIn('resistance:fire>air', result)
        self.assertFalse([key for key in result
                          if key.startswith('resistance:air>')])

    def test_the_power_rune_keeps_zero_lines_and_drops_a_created_zero(self):
        result = by_key([('str', 1), ('vit', 0)], only('power', keep=0.7))
        self.assertEqual(result, {'power': {'vit': 0}})


    def test_the_same_variant_key_with_two_results_raises(self):
        runes = dict(RUNES, runes=[
            {'item_id': 1, 'kind': 'power', 'keep': 0.7},
            {'item_id': 2, 'kind': 'power', 'keep': 0.5}])
        with self.assertRaises(ValueError):
            variants([('str', 100)], runes)

    def test_a_moved_line_takes_the_place_of_its_source_line(self):
        result = variants([('str', 30), ('ap', 1)], only('element', 'int'))
        self.assertEqual(result, [('element:str>int',
                                   [('int', 30), ('ap', 1)])])

    def test_the_power_lines_take_the_place_of_the_first_dropped_lines(self):
        stats = [('vit', 5), ('str', 10), ('wis', 2), ('cha', 20),
                 ('earthdam', 4), ('sag', 1)]
        result = variants(stats, only('power', keep=0.7))
        self.assertEqual(result, [('power', [
            ('vit', 5), ('pow', 14), ('wis', 2), ('dam', 2), ('sag', 1)])])

    def test_an_existing_power_line_keeps_its_place(self):
        stats = [('pow', 10), ('vit', 5), ('str', 100)]
        result = variants(stats, only('power', keep=0.7))
        self.assertEqual(result, [('power', [('pow', 80), ('vit', 5)])])

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
