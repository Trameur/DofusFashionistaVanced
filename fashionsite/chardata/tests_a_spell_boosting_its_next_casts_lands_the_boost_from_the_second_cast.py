# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A spell boosting its own next casts once lands the boost on every cast after the first."""
from unittest import mock

from django.test import SimpleTestCase

from chardata.spell_buffs import get_damage_spells_for_version
from chardata.spell_combo import Castable, best_turn

ACCUMULATION = 13138
VERSIONS = ('dofus3', 'beta')
BOOSTS = (20, 24)
QUOTE = 'Sur le lanceur : augmente les dommages du sort.'
LADDER = [('Stack 0', [0]), ('Stack 1', [1])]

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


def _spell(version):
    return next(spell for spells in get_damage_spells_for_version(version).values()
                for spell in spells if spell.spell_id == ACCUMULATION)


def _effect(effect_id, **fields):
    effect = {'effect_id': effect_id, 'triggers': 'I', 'delay': 0, 'duration': 0,
              'target_mask': 'g,A'}
    effect.update(fields)
    return effect


def _effects(low, spell_id, value, boosted=None, boosts=1, delay=0, duration=3, mask='c'):
    hit = _effect(97, dice={'min': low, 'max': low + 3}, effect_metadata={'category': 2})
    boost = _effect(293, value=value, dice={'min': boosted or spell_id, 'max': 0},
                    delay=delay, duration=duration, target_mask=mask)
    return [hit] + [dict(boost) for _count in range(boosts)]


def _raw(spell_id=ACCUMULATION, text=QUOTE, critical=None, max_stack=1, casts=3, per_target=2,
         rows=1, stackable=None, **shape):
    """Accumulation's rows as the scraper hands them, with one part of their shape changed."""
    levels = []
    for grade, (low, value) in enumerate(zip((19, 22), BOOSTS), 1):
        own = dict(shape, value=shape.get('value', value))
        crit = dict(own, **(critical or {}))
        levels.append({'grade': grade, 'max_stack': max_stack, 'max_cast_per_turn': casts,
                       'max_cast_per_target': per_target,
                       'effects': _effects(low, spell_id, **own),
                       'critical_effects': _effects(low + 3, spell_id, **crit)})
    row = {'element': 'EARTH', 'ranges': ['19-22', '22-26'], 'situation': 'g,A|80,1,0',
           'triggers': 'I'}
    crit_row = dict(row, ranges=['22-25', '25-29'])
    return {'ankama_id': spell_id, 'name_en': 'Probe', 'level_requirements': [105, 172],
            'description_fr': 'Occasionne des dommages Terre. ' + text, 'levels': levels,
            'damage_templates': {'normal': [dict(row) for _count in range(rows)],
                                 'critical': [dict(crit_row) for _count in range(rows)],
                                 'stackable_damage': stackable}}


class TheGeneratorLaddersTheOneBoostTests(SimpleTestCase):

    def test_the_one_boost_becomes_a_ladder_whose_second_cast_lands_it(self):
        entry = _generator().convert_spell(_raw())
        self.assertEqual(entry.aggregates, LADDER)
        self.assertTrue(entry.stacks_on_recast)
        self.assertEqual(entry.non_crit_ranges, [['19-22', '22-26'], ['39-42', '46-50']])
        self.assertEqual(entry.crit_ranges, [['22-25', '25-29'], ['42-45', '49-53']])
        self.assertIsNone(entry.boost_problem)

    def test_a_boost_off_its_shape_stops_the_generator(self):
        cases = {
            'card lost the sentence': _raw(text='Occasionne des dommages.'),
            'boost waits a turn': _raw(delay=1),
            'boost lasts no turn': _raw(duration=0),
            'boost stacks twice': _raw(max_stack=2),
            'boost on the allies': _raw(mask='a'),
            'boost of another spell': _raw(boosted=ACCUMULATION + 1),
            'two boosts': _raw(boosts=2),
            'no boost value': _raw(value=0),
            'critical boost differs': _raw(critical={'value': 30}),
            'a stack ladder already': _raw(stackable={'per_stack': [20, 24], 'max_stacks': [2, 2]}),
            'two hits': _raw(rows=2),
        }
        for case, raw in cases.items():
            with self.subTest(case=case):
                with self.assertRaises(SystemExit):
                    _generator().convert_spell(raw)

    def test_an_unlisted_spell_whose_own_boost_lasts_is_flagged_not_laddered(self):
        gen = _generator()
        flagged = gen.convert_spell(_raw(spell_id=1))
        self.assertTrue(flagged.boost_problem)
        self.assertFalse(flagged.stacks_on_recast)
        self.assertIsNone(gen.convert_spell(_raw(spell_id=1, casts=1)).boost_problem)
        self.assertIsNone(gen.convert_spell(_raw(spell_id=1, per_target=1)).boost_problem)
        self.assertIsNone(gen.convert_spell(_raw(spell_id=1, duration=0)).boost_problem)
        unlisted = {spell: quote for spell, quote in gen.RECAST_STACKS.items()
                    if spell != ACCUMULATION}
        with mock.patch.object(gen, 'ONE_BOOST_RECASTS', frozenset()):
            with self.assertRaises(SystemExit):
                gen.convert_spell(_raw())
            with mock.patch.object(gen, 'RECAST_STACKS', unlisted):
                self.assertTrue(gen.convert_spell(_raw()).boost_problem)


class AccumulationLandsItsBoostFromTheSecondCastTests(SimpleTestCase):

    def test_the_entry_is_a_one_stack_recast_ladder_in_each_version(self):
        for version in VERSIONS:
            spell = _spell(version)
            digest = spell.get_effects_digest()
            with self.subTest(version=version):
                self.assertEqual(spell.aggregates, LADDER)
                self.assertTrue(spell.stacks_on_recast)
                for ranks in (digest.non_crit_dams, digest.crit_dams):
                    self.assertEqual([[(row.min_dam + boost, row.max_dam + boost)
                                       for row in rank[:1]]
                                      for rank, boost in zip(ranks, BOOSTS)],
                                     [[(row.min_dam, row.max_dam) for row in rank[1:2]]
                                      for rank in ranks])

    def test_the_second_cast_adds_the_boost_the_first_one_lacks(self):
        scale = 1 + _STATS['str'] / 100.0
        for version in VERSIONS:
            _in_version(self, version)
            spell = _spell(version)
            for grade, boost in enumerate(BOOSTS):
                cast = Castable(spell, grade, crit=False)
                _one, (first,) = best_turn(dict(_STATS), [cast], cast.cost,
                                           game_version=version, caster_level=200)
                total, order = best_turn(dict(_STATS), [cast], 2 * cast.cost,
                                         game_version=version, caster_level=200)
                with self.subTest(version=version, grade=grade):
                    self.assertEqual(len(order), 2)
                    self.assertAlmostEqual(order[0][1], first[1])
                    self.assertAlmostEqual(order[1][1] - order[0][1], scale * boost)
                    self.assertAlmostEqual(total, 2 * first[1] + scale * boost)
