# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Dofus 2 Accumulation, whose rows carry the boost as a digit string, lands it from its second cast."""
from unittest import mock

from django.test import SimpleTestCase

from chardata.spell_buffs import get_damage_spells_for_version
from chardata.spell_combo import Castable, best_turn

ACCUMULATION = 13138
VERSION = 'dofus2'
BOOSTS = (20, 24)
QUOTE = 'Sur le lanceur : augmente les dommages du sort.'
LADDER = [('Stack 0', [0]), ('Stack 1', [1])]
UNCAPPED = {'per_stack': list(BOOSTS), 'max_stacks': [None, None]}

_STATS = {'str': 100, 'int': 0, 'cha': 0, 'agi': 0, 'pow': 0, 'dam': 0, 'cridam': 0,
          'heals': 0, 'perspedam': 0, 'perweadam': 0, 'permedam': 0, 'perrandam': 0,
          'earthdam': 0, 'firedam': 0, 'waterdam': 0, 'airdam': 0, 'neutdam': 0, 'ch': 0,
          'final': 0, 'negfinal': 0, 'pshdam': 0, 'ap': 12}


def _generator():
    from chardata.tests import itemscraper_module
    return itemscraper_module('generate_damage_spells')


def _in_version(test, version):
    from fashionistapulp.structure import set_current_game_version
    test.addCleanup(set_current_game_version, 'dofus3')
    set_current_game_version(version)


def _spell():
    return next(spell for spells in get_damage_spells_for_version(VERSION).values()
                for spell in spells if spell.spell_id == ACCUMULATION)


def _effects(low, value):
    hit = {'effect_id': 97, 'triggers': 'I', 'delay': 0, 'duration': 0, 'target_mask': 'g,A',
           'dice': {'min': low, 'max': low + 3}, 'effect_metadata': {'category': 2}}
    boost = {'effect_id': 293, 'value': value, 'dice': {'min': ACCUMULATION, 'max': 0},
             'triggers': 'I', 'delay': 0, 'duration': 3, 'target_mask': 'c'}
    return [hit, boost]


def _raw(value=str, stackable=UNCAPPED):
    """Accumulation's Dofus 2 rows as the scraper hands them."""
    levels = [{'grade': grade, 'max_stack': 1, 'max_cast_per_turn': 3,
               'max_cast_per_target': 2,
               'effects': _effects(low, value(boost)),
               'critical_effects': _effects(low + 3, value(boost))}
              for grade, (low, boost) in enumerate(zip((19, 22), BOOSTS), 1)]
    row = {'element': 'EARTH', 'ranges': ['19-22', '22-26'], 'situation': 'g,A|80,1,0',
           'triggers': 'I'}
    return {'ankama_id': ACCUMULATION, 'name_en': 'Probe', 'level_requirements': [105, 172],
            'description_fr': 'Occasionne des dommages Terre. ' + QUOTE, 'levels': levels,
            'damage_templates': {'normal': [row], 'critical': [dict(row, ranges=['22-25', '25-29'])],
                                 'stackable_damage': stackable}}


class TheGeneratorLaddersTheDofus2BoostTests(SimpleTestCase):

    def _convert(self, raw):
        gen = _generator()
        with mock.patch.object(gen, 'RECAST_STACKS', gen.RECAST_STACKS_BY_VERSION[VERSION]):
            return gen.convert_spell(raw)

    def test_a_digit_string_boost_with_an_uncapped_template_becomes_the_ladder(self):
        entry = self._convert(_raw())
        self.assertEqual(entry.aggregates, LADDER)
        self.assertTrue(entry.stacks_on_recast)
        self.assertEqual(entry.non_crit_ranges, [['19-22', '22-26'], ['39-42', '46-50']])
        self.assertIsNone(entry.boost_problem)

    def test_a_template_off_the_rows_still_stops_the_generator(self):
        cases = {
            'template of other values': {'per_stack': [18, 24], 'max_stacks': [None, None]},
            'template with a cap': {'per_stack': list(BOOSTS), 'max_stacks': [2, 2]},
        }
        for case, stackable in cases.items():
            with self.subTest(case=case):
                with self.assertRaises(SystemExit):
                    self._convert(_raw(stackable=stackable))

    def test_a_boost_that_is_no_whole_number_stops_the_generator(self):
        for case, value in {'text': lambda boost: 'x%d' % boost,
                            'zero': lambda boost: '0'}.items():
            with self.subTest(case=case):
                with self.assertRaises(SystemExit):
                    self._convert(_raw(value=value))


class Dofus2AccumulationLandsItsBoostFromTheSecondCastTests(SimpleTestCase):

    def test_the_entry_is_a_one_stack_recast_ladder(self):
        spell = _spell()
        digest = spell.get_effects_digest()
        self.assertEqual(spell.aggregates, LADDER)
        self.assertTrue(spell.stacks_on_recast)
        for ranks in (digest.non_crit_dams, digest.crit_dams):
            self.assertEqual([[(row.min_dam + boost, row.max_dam + boost) for row in rank[:1]]
                              for rank, boost in zip(ranks, BOOSTS)],
                             [[(row.min_dam, row.max_dam) for row in rank[1:2]]
                              for rank in ranks])

    def test_the_second_cast_adds_the_boost_the_first_one_lacks(self):
        scale = 1 + _STATS['str'] / 100.0
        _in_version(self, VERSION)
        spell = _spell()
        for grade, boost in enumerate(BOOSTS):
            cast = Castable(spell, grade, crit=False)
            _one, (first,) = best_turn(dict(_STATS), [cast], cast.cost,
                                       game_version=VERSION, caster_level=200)
            total, order = best_turn(dict(_STATS), [cast], 2 * cast.cost,
                                     game_version=VERSION, caster_level=200)
            with self.subTest(grade=grade):
                self.assertEqual(len(order), 2)
                self.assertAlmostEqual(order[1][1] - order[0][1], scale * boost)
                self.assertAlmostEqual(total, 2 * first[1] + scale * boost)
