# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Nogdra, Domoko and Drosera land one hit in the Bellaphone's best element on Touch Beta."""
from django.test import SimpleTestCase

from chardata.spell_buffs import get_damage_spells_for_version
from chardata.spell_reference import get_spell_reference

VERSION = 'touchbeta'
DOMOKO = 13569
NOGDRA = 13769
DROSERA = 13771
BEST_ELEMENT_HITS = (DOMOKO, NOGDRA, DROSERA)
FACES = [('Hit in best element', [0]), ('', [1]), ('', [2]), ('', [3])]

_STATS = {'str': 0, 'int': 0, 'cha': 0, 'agi': 0, 'pow': 0, 'dam': 0,
          'cridam': 0, 'heals': 0, 'perspedam': 0, 'perweadam': 0,
          'permedam': 0, 'perrandam': 0, 'earthdam': 0, 'firedam': 0,
          'waterdam': 0, 'airdam': 0, 'neutdam': 0, 'ch': 0, 'final': 0,
          'negfinal': 0, 'pshdam': 0, 'ap': 12}


def _touch_reader():
    from chardata.tests import itemscraper_module
    return itemscraper_module('get_spells_touch')


def _in_version(test):
    from fashionistapulp.structure import set_current_game_version
    test.addCleanup(set_current_game_version, 'dofus3')
    set_current_game_version(VERSION)


def _card(spell_id):
    for entries in get_spell_reference(VERSION).values():
        for entry in entries:
            if entry.get('id') == spell_id:
                return entry
    return None


def _castable(spell_id):
    from chardata.spell_combo import castable_spells
    return next(castable for castable in castable_spells('Bellaphone', 200, VERSION)
                if castable.spell_id == spell_id)


def _alone(castable, stats):
    from chardata.spell_combo import best_turn
    return best_turn(dict(_STATS, **stats), [castable], castable.cost,
                     game_version=VERSION, caster_level=200)[0]


class TheTouchReaderReadsTheBellaphoneBestElementHitsTests(SimpleTestCase):

    def test_each_card_says_its_best_element_row_is_the_casters_hit(self):
        reader = _touch_reader()
        for spell_id in BEST_ELEMENT_HITS:
            card = _card(spell_id)
            with self.subTest(spell=spell_id):
                self.assertTrue(reader._best_element_is_the_whole_hit(
                    {'id': spell_id, 'descriptionId': card['description']}))


class TheBellaphoneTurnCountsItsBestElementHitsTests(SimpleTestCase):

    def test_each_hit_is_one_row_per_element_with_the_same_dice(self):
        spells = {spell.spell_id: spell
                  for spell in get_damage_spells_for_version(VERSION).get('Bellaphone', [])}
        for spell_id in BEST_ELEMENT_HITS:
            with self.subTest(spell=spell_id):
                self.assertIn(spell_id, spells)
                spell = spells[spell_id]
                self.assertEqual([list(group) for group in spell.aggregates],
                                 [list(group) for group in FACES])
                rows = spell.get_effects_digest().non_crit_dams[-1]
                self.assertEqual([row.element for row in rows],
                                 ['earth', 'fire', 'water', 'air'])
                self.assertEqual({(row.min_dam, row.max_dam) for row in rows},
                                 {(rows[0].min_dam, rows[0].max_dam)})

    def test_a_chance_build_and_a_strength_build_land_the_same_hit(self):
        _in_version(self)
        for spell_id in BEST_ELEMENT_HITS:
            castable = _castable(spell_id)
            chance = _alone(castable, {'cha': 800})
            strength = _alone(castable, {'str': 800})
            with self.subTest(spell=castable.name):
                self.assertGreater(chance, _alone(castable, {}))
                self.assertAlmostEqual(chance, strength)

    def test_the_hit_follows_the_build_s_best_element(self):
        _in_version(self)
        for spell_id in BEST_ELEMENT_HITS:
            castable = _castable(spell_id)
            mixed = _alone(castable, {'cha': 800, 'str': 200})
            with self.subTest(spell=castable.name):
                self.assertAlmostEqual(mixed, _alone(castable, {'cha': 800}))
