# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A row that heals adds nothing to a turn on a target, as it adds nothing to the raw turn."""
from django.test import SimpleTestCase

from chardata.spell_combo import castable_spells, final_multiplier, row_value
from chardata.targets import Target
from fashionistapulp.dofus_constants import calculate_damage
from fashionistapulp.structure import get_structure, set_current_game_version

STATS = {'str': 450, 'agi': 480, 'int': 470, 'cha': 460, 'pow': 90, 'dam': 30, 'heals': 60}


class AHealOnATargetTests(SimpleTestCase):

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')

    def test_a_healing_row_is_worth_nothing_to_a_target_as_to_none(self):
        found = 0
        for version in ('dofus3', 'beta', 'dofus2', 'touch', 'retro'):
            set_current_game_version(version)
            stats = {stat.key: 0 for stat in get_structure(version).get_stats_list()}
            stats.update({key: value for key, value in STATS.items() if key in stats})
            multiplier = final_multiplier(stats)
            target = Target(version=version, kind='monster', ref=('m', 1, 1), level=200,
                            hp=10000, percent=(0,) * 5, is_player=False, label='a monster')
            for castable in (castable_spells('Sadida', 200, version)
                             + castable_spells('Ecaflip', 200, version)):
                for rows in castable.plain_alternatives or []:
                    for row in rows:
                        damages = calculate_damage([row], stats, False, castable.is_spell)
                        if not damages or not damages[0].heals:
                            continue
                        found += 1
                        with self.subTest(version=version, spell=castable.name):
                            self.assertEqual(0, row_value([row], stats, False,
                                                          castable.is_spell, multiplier))
                            self.assertEqual(0, row_value([row], stats, False,
                                                          castable.is_spell, multiplier,
                                                          target))
        self.assertGreater(found, 0)
