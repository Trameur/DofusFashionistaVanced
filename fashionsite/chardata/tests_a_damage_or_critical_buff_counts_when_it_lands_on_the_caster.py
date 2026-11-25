# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A Damage or % Critical row a spell gives its caster is a buff row; one for an ally, the tooltip or a roll is not."""
import re

from django.template.loader import get_template
from django.test import SimpleTestCase

from chardata.spell_buffs import get_damage_spells_for_version
from chardata.spell_combo import Castable, best_turn

MODERN = ('dofus3', 'beta')
DAMAGE = 16
CRITICAL = 18

# {version: {spell id: (token, normal per rank, critical per rank or None)}}
CASTER_BUFFS = {
    'dofus3': {
        32466: ('buff_ch', [10, 12, 15], [12, 14, 17]),
        32469: ('buff_ch', [10, 15], None),
        13110: ('buff_dam', [10, 20, 30], [10, 20, 30]),
        13394: ('buff_dam', [20, 30, 40], [20, 30, 40]),
        31135: ('buff_dam', [10, 15, 20], [10, 15, 20]),
        31111: ('buff_ch', [5, 7, 10], [5, 7, 10]),
        12727: ('buff_ch', [5, 7], [5, 7]),
        14741: ('buff_dam', [20], None),
        24016: ('buff_ch', [5, 10], [5, 10]),
    },
    'dofus2': {
        13073: ('buff_ch', [10, 10], [12, 12]),
        13110: ('buff_dam', [10, 20, 30], [10, 20, 30]),
        13394: ('buff_dam', [20, 30, 40], [20, 30, 40]),
        12727: ('buff_ch', [5, 7], [5, 7]),
        24016: ('buff_ch', [5, 10], [5, 10]),
    },
}
CASTER_BUFFS['beta'] = CASTER_BUFFS['dofus3']

# Roulette, Wheel of Fortune and Short-Circuit buff allies or enemies, Heads or Tails only in
# the tooltip, Yahtzee rolls its value; Piercing Shots, Vendetta, Telluric Blade, Turbine and
# the Dofus 2 Plot give it to the targeted ally
ELSEWHERE = {
    'dofus3': (12840, 12863, 13872, 12841, 29680),
    'dofus2': (12840, 12863, 13872, 12841, 29680, 13066, 23510, 13715, 13874, 14741),
}
ELSEWHERE['beta'] = ELSEWHERE['dofus3']

DIVINE_SWORD = 13110
POWERFUL_SHOTS = 32466

_STATS = {'str': 100, 'int': 0, 'cha': 0, 'agi': 100, 'pow': 0, 'dam': 0, 'cridam': 0,
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


def _spells(version, spell_id):
    return [spell for spells in get_damage_spells_for_version(version).values()
            for spell in spells if spell.spell_id == spell_id]


def _row(characteristic, mask='C', low=10, high=0, flags=79):
    label = '#1{~1~2 to }#2 Damage' if characteristic == DAMAGE else '#1{~1~2 to }#2% Critical'
    return {'effect_id': 112, 'dice': {'min': low, 'max': high}, 'target_mask': mask,
            'triggers': 'I', 'duration': 2, 'delay': 0, 'order': 1, 'flags': flags,
            'effect_metadata': {'category': 0, 'characteristic': characteristic,
                                'bonus_type': 1, 'description': {'en': label}}}


def _buff_rows(*effects):
    spell = {'ankama_id': 99001, 'levels': [{'effects': list(effects), 'critical_effects': []}]}
    return [(row['token'], row['normal'])
            for row in _generator()._extract_stat_buff_rows(spell, 1)]


def _per_rank(ranges, row):
    return [rank.min_dam for rank in ranges[row]]


class TheGeneratorReadsACasterDamageOrCriticalRowTests(SimpleTestCase):

    def test_a_damage_row_on_the_caster_is_a_damage_buff(self):
        self.assertEqual([('buff_dam', ['10'])], _buff_rows(_row(DAMAGE)))
        self.assertEqual([('buff_dam', ['10'])], _buff_rows(_row(DAMAGE, mask='C,a')))

    def test_a_critical_row_on_the_caster_is_a_critical_buff(self):
        self.assertEqual([('buff_ch', ['10'])], _buff_rows(_row(CRITICAL)))
        self.assertEqual([('buff_ch', ['10'])], _buff_rows(_row(CRITICAL, mask='g,C')))

    def test_a_row_for_the_targeted_ally_or_enemy_is_no_buff(self):
        for mask in ('a', 'a,A', 'A', 'a,F5835'):
            with self.subTest(mask=mask):
                self.assertEqual([], _buff_rows(_row(DAMAGE, mask=mask)))
                self.assertEqual([], _buff_rows(_row(CRITICAL, mask=mask)))

    def test_a_row_only_the_tooltip_shows_is_no_buff(self):
        self.assertTrue(_generator()._client_only(_row(CRITICAL, flags=95)))
        self.assertEqual([], _buff_rows(_row(CRITICAL, flags=95)))

    def test_a_value_rolled_at_each_cast_is_no_buff(self):
        self.assertEqual([], _buff_rows(_row(CRITICAL, low=3, high=18)))
        self.assertEqual([], _buff_rows(_row(CRITICAL), _row(CRITICAL, low=3, high=18)))


class TheSpellsCarryTheirCasterBuffTests(SimpleTestCase):

    def test_each_caster_buff_carries_its_value_at_each_rank(self):
        for version, spells in CASTER_BUFFS.items():
            for spell_id, (token, normal, critical) in spells.items():
                found = _spells(version, spell_id)
                with self.subTest(version=version, spell=spell_id):
                    self.assertEqual(1, len(found))
                    effects = found[0].effects
                    self.assertEqual(1, effects.elements.count(token))
                    row = effects.elements.index(token)
                    self.assertEqual(normal, _per_rank(effects.non_crit_ranges, row))
                    if critical is not None:
                        self.assertEqual(critical, _per_rank(effects.crit_ranges, row))

    def test_a_spell_whose_row_goes_elsewhere_keeps_no_such_buff(self):
        for version, spell_ids in ELSEWHERE.items():
            for spell_id in spell_ids:
                for spell in _spells(version, spell_id):
                    with self.subTest(version=version, spell=spell_id):
                        self.assertNotIn('buff_dam', spell.effects.elements)
                        self.assertNotIn('buff_ch', spell.effects.elements)


class TheTurnCountsTheCasterBuffsTests(SimpleTestCase):

    def test_divine_swords_damage_lands_on_its_next_cast(self):
        for version in MODERN + ('dofus2',):
            _in_version(self, version)
            (spell,) = _spells(version, DIVINE_SWORD)
            for grade, gained in enumerate((10, 20, 30)):
                cast = Castable(spell, grade, crit=False)
                _total, order = best_turn(dict(_STATS), [cast], 2 * cast.cost,
                                          game_version=version, caster_level=200)
                with self.subTest(version=version, grade=grade):
                    self.assertEqual(2, len(order))
                    self.assertAlmostEqual(gained, order[1][1] - order[0][1])

    def test_powerful_shots_raises_the_critical_rate_of_the_turn(self):
        for version in MODERN:
            (spell,) = _spells(version, POWERFUL_SHOTS)
            for grade, critical in enumerate((10, 12, 15)):
                with self.subTest(version=version, grade=grade):
                    self.assertEqual(critical,
                                     Castable(spell, grade, crit=False).buff_deltas(1)['ch'])


class TheSpellsPageNamesEveryBuffTests(SimpleTestCase):

    def test_every_buff_row_has_a_label_on_the_spells_page(self):
        source = get_template('chardata/spells.html').template.source
        labelled = set(re.findall(r'element == "(buff_\w+)"', source))
        for version in MODERN + ('dofus2',):
            tokens = {element for spells in get_damage_spells_for_version(version).values()
                      for spell in spells for element in spell.effects.elements
                      if isinstance(element, str) and element.startswith('buff')}
            with self.subTest(version=version):
                self.assertEqual(set(), tokens - labelled)
