# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A caster buff given on cast and raised by each hit the caster takes counts its cast value in the turn and its cap fully buffed."""

from django.test import SimpleTestCase

from chardata.spell_buffs import _buff_value, get_damage_spells_for_version
from chardata.spell_combo import Castable

GNAW = 13803


def _generator():
    from chardata.tests import itemscraper_module
    return itemscraper_module('generate_damage_spells')


def _in_version(test, version):
    from fashionistapulp.structure import set_current_game_version
    test.addCleanup(set_current_game_version, 'dofus3')
    set_current_game_version(version)


def _spell(version, spell_id):
    return next(spell for spells in get_damage_spells_for_version(version).values()
                for spell in spells if spell.spell_id == spell_id)


def _row(characteristic, label, value, triggers, mask='C'):
    return {'effect_id': 138, 'triggers': triggers, 'target_mask': mask,
            'dice': {'min': value, 'max': 0},
            'effect_metadata': {'characteristic': characteristic, 'bonus_type': 1,
                                'description': {'en': '#1{~1~2 to }#2 ' + label}}}


def _raw(*rows, max_stack=10):
    return {'ankama_id': 1, 'levels': [{'max_stack': max_stack, 'effects': list(rows)}]}


class TheBuffCountsItsCastValueTests(SimpleTestCase):

    def test_one_cast_of_gnaw_gives_its_cast_value(self):
        _in_version(self, 'dofus2')
        cast = Castable(_spell('dofus2', GNAW), 0, crit=False)
        self.assertEqual(cast.buff_deltas(1), {'pow': 80, 'pshdam': 40})

    def test_gnaw_fully_buffed_adds_ten_hits(self):
        spell = _spell('dofus2', GNAW)
        self.assertEqual(spell.stacks, 11)
        self.assertEqual(_buff_value(spell.buff_scaling, 'pow', spell.stacks, 15), 80 + 10 * 15)
        self.assertEqual(_buff_value(spell.buff_scaling, 'pshdam', spell.stacks, 10),
                         40 + 10 * 10)

    def test_the_generator_pairs_the_cast_row_with_the_hit_row_of_one_stat(self):
        scaling = _generator()._hit_buff_scaling(_raw(_row(25, 'Power', 80, 'I'),
                                                      _row(25, 'Power', 15, 'D')))
        self.assertEqual(scaling, {'type': 'hit_buff', 'stack_offset': 1, 'selection_count': 11,
                                   'stats': {'pow': {'base': 80, 'per_stack': 15,
                                                     'max_effective': 10}}})

    def test_the_generator_leaves_a_buff_without_both_rows(self):
        generator = _generator()
        for rows in ((_row(25, 'Power', 80, 'I'),),
                     (_row(25, 'Power', 15, 'D'),),
                     (_row(25, 'Power', 80, 'I'), _row(25, 'Power', 15, 'D', mask='a'))):
            with self.subTest(rows=len(rows)):
                self.assertIsNone(generator._hit_buff_scaling(_raw(*rows)))

    def test_the_generator_leaves_a_buff_with_no_stack_cap(self):
        rows = (_row(25, 'Power', 80, 'I'), _row(25, 'Power', 15, 'D'))
        self.assertIsNone(_generator()._hit_buff_scaling(_raw(*rows, max_stack=-1)))
