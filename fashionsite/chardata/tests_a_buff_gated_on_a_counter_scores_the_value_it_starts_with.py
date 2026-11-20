# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A buff gated on a caster counter scores the value the counter starts a fight with."""
import os
from pathlib import Path

from django.test import SimpleTestCase

from chardata.spell_buffs import get_damage_spells_for_version
from chardata.spell_combo import Castable

COUNTER = '99001'
OTHER_COUNTER = '99002'


def _scraper(name):
    from chardata.tests import itemscraper_module
    return itemscraper_module(name)


def _power(value, mask, order):
    return {'effect_id': 138, 'dice': {'min': value, 'max': 0}, 'target_mask': mask,
            'triggers': 'I', 'duration': 2, 'delay': 0, 'order': order, 'flags': 79,
            'effect_metadata': {'category': 0, 'characteristic': 25, 'bonus_type': 1,
                                'description': {'en': '#1{{~1~2 to }}#2 Power'}}}


def _counter_spell(counter, start):
    generator = _scraper('generate_damage_spells')
    return {'ankama_id': int(counter), 'levels': [{'effects': [
        {'effect_id': generator.COUNTER_INIT_EFFECT_ID, 'dice': {'min': start, 'max': 1},
         'target_mask': 'C'}]}]}


def _two_gated_powers():
    return {'ankama_id': 99000, 'levels': [{'effects': [
        _power(100, 'C,*Ct%s=3' % COUNTER, 2),
        _power(60, 'C,*Ct%s=2' % COUNTER, 1),
    ], 'critical_effects': []}]}


class TwoGatedEffectsOfOneStatKeepBothGatesTests(SimpleTestCase):

    def test_each_gate_keeps_its_own_value(self):
        generator = _scraper('generate_damage_spells')
        rows = generator._stat_buff_rows_by_gate(_two_gated_powers(), 1)
        self.assertEqual({('buff_pow', ((COUNTER, '=', '2'),)): ['60'],
                          ('buff_pow', ((COUNTER, '=', '3'),)): ['100']},
                         {key: row['normal'] for key, row in rows.items()})

    def test_the_scored_row_is_the_gate_the_counter_starts_in(self):
        generator = _scraper('generate_damage_spells')
        for start, expected in ((2, ['60']), (3, ['100'])):
            with self.subTest(start=start):
                lookup = {int(COUNTER): _counter_spell(COUNTER, start)}
                self.assertEqual(
                    [('buff_pow', expected)],
                    [(row['token'], row['normal']) for row in
                     generator._extract_stat_buff_rows(_two_gated_powers(), 1, lookup)])

    def test_a_counter_without_a_start_value_stops_the_generator(self):
        generator = _scraper('generate_damage_spells')
        lookup = {int(OTHER_COUNTER): _counter_spell(OTHER_COUNTER, 2)}
        with self.assertRaises(SystemExit):
            generator._extract_stat_buff_rows(_two_gated_powers(), 1, lookup)


class InspirationScoresThePowerOfItsStartingBellauraTests(SimpleTestCase):

    def setUp(self):
        import fashionista_version
        from fashionistapulp.fashionista_config import get_fashionista_path
        directory = (Path(get_fashionista_path()) / 'itemscraper' / 'raw'
                     / fashionista_version.FASHIONISTA_BETA_VERSION)
        if not (directory / 'spell_levels.json').exists():
            self.skipTest('no Beta client archive on this machine')
        self.inspiration = next(
            spell for spell in get_damage_spells_for_version('beta')['Bellaphone']
            if spell.name == 'Inspiration')
        self.reader = _scraper('get_spells').SpellTransformer(
            directory, Path(os.devnull), languages=('en',))
        self.generator = _scraper('generate_damage_spells')

    def _levels(self, spell_id):
        return self.reader._spell_levels(self.reader.spells[spell_id])

    def _start_gate_powers(self, levels):
        """The Power each raw grade gives on the counter value its counter spell starts at."""
        powers = []
        for level in levels:
            gated = [(self.generator.CASTER_COUNTER_BRANCH.findall(effect['target_mask']), effect)
                     for effect in level['effects']
                     if self.generator._stat_buff_token(effect) == 'buff_pow']
            self.assertGreater(len(gated), 1)
            starts = {}
            for gates, _effect in gated:
                for counter, _sign, _value in gates:
                    first = self._levels(int(counter))[0]['effects']
                    starts[counter] = next(
                        effect['dice']['min'] for effect in first
                        if effect['effect_id'] == self.generator.COUNTER_INIT_EFFECT_ID)
            held = [effect['dice']['min'] for gates, effect in gated
                    if gates and all(sign == '=' and int(value) == starts[counter]
                                     for counter, sign, value in gates)]
            self.assertEqual(1, len(held))
            powers.append(held[0])
        return powers, starts

    def test_the_generator_reads_the_start_gate_power_from_the_raw_levels(self):
        levels = self._levels(self.inspiration.spell_id)
        powers, starts = self._start_gate_powers(levels)
        lookup = {int(counter): {'levels': self._levels(int(counter))} for counter in starts}
        spell = {'ankama_id': self.inspiration.spell_id, 'levels': levels}
        self.assertEqual(
            [('buff_pow', [str(power) for power in powers])],
            [(row['token'], row['normal']) for row in
             self.generator._extract_stat_buff_rows(spell, len(levels), lookup)])

    def test_the_shipped_row_and_the_combo_score_the_start_gate_power(self):
        powers, _starts = self._start_gate_powers(self._levels(self.inspiration.spell_id))
        effects = self.inspiration.effects
        self.assertEqual(['buff_pow'], effects.elements)
        self.assertEqual([[(power, power) for power in powers]],
                         [[(rng.min_dam, rng.max_dam) for rng in row]
                          for row in effects.non_crit_ranges])
        for index, power in enumerate(powers):
            with self.subTest(grade=index + 1):
                self.assertEqual({'pow': power},
                                 Castable(self.inspiration, index, False).buff_deltas(1))
