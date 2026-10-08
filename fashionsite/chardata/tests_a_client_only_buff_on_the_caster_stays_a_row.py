# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A buff the client marks as its own but gives the caster stays the spell's buff row."""
from django.test import SimpleTestCase

from chardata.spell_buffs import get_damage_spells_for_version

LUCKY_SHOVEL = 29755


def _generator():
    from chardata.tests import itemscraper_module
    return itemscraper_module('generate_damage_spells')


def _power(flags):
    return {'effect_id': 138, 'dice': {'min': 40, 'max': 0}, 'target_mask': 'P,h',
            'triggers': 'I', 'duration': 2, 'delay': 0, 'order': 1, 'flags': flags,
            'effect_metadata': {'category': 0, 'characteristic': 25, 'bonus_type': 1,
                                'description': {'en': '#1{{~1~2 to }}#2 Power'}}}


class TheGeneratorKeepsAClientOnlyBuffTests(SimpleTestCase):

    def test_a_client_only_power_on_the_caster_is_a_power_row(self):
        generator = _generator()
        power = _power(95)
        self.assertTrue(generator._client_only(power))
        spell = {'ankama_id': 99000,
                 'levels': [{'effects': [power], 'critical_effects': []}]}
        self.assertEqual([('buff_pow', ['40'])],
                         [(row['token'], row['normal'])
                          for row in generator._extract_stat_buff_rows(spell, 1)])


class TheLuckyShovelKeepsItsPowerTests(SimpleTestCase):

    def test_its_one_row_is_the_power_it_gives_the_caster(self):
        for version in ('dofus3', 'beta'):
            with self.subTest(version=version):
                shovel = next(spell
                              for spell in get_damage_spells_for_version(version)['Enutrof']
                              if spell.spell_id == LUCKY_SHOVEL)
                self.assertEqual(['buff_pow'], shovel.effects.elements)
                self.assertEqual([[(40, 40)]],
                                 [[(rng.min_dam, rng.max_dam) for rng in row]
                                  for row in shovel.effects.non_crit_ranges])
