# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Marrow Bone and Carcass, raised after each cast on the Prey, land their next Stack group on each cast of the turn."""

import copy

from django.test import SimpleTestCase

from chardata.spell_buffs import get_damage_spells_for_version
from chardata.spell_combo import Castable, best_turn

MARROW_BONE = 13762
CARCASS = 13768
GROWING = (MARROW_BONE, CARCASS)
VERSIONS = ('dofus3', 'beta')
SAYS_IT_GROWS = 'les dommages du sort sont augmentés après chaque lancer si la cible est la proie'

_STATS = {'str': 100, 'int': 100, 'cha': 800, 'agi': 800, 'pow': 0, 'dam': 0,
          'cridam': 0, 'heals': 0, 'perspedam': 0, 'perweadam': 0,
          'permedam': 0, 'perrandam': 0, 'earthdam': 0, 'firedam': 0,
          'waterdam': 0, 'airdam': 0, 'neutdam': 0, 'ch': 0, 'final': 0,
          'negfinal': 0, 'pshdam': 0, 'ap': 12}


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


def _cast(spell):
    return Castable(spell, len(spell.level_req) - 1, crit=False)


def _landing_on(spell, stack):
    alone = copy.copy(spell)
    alone.aggregates = spell.aggregates[stack:]
    alone.stacks_on_recast = False
    alone.digest = None
    return _cast(alone)


def _turn(version, casts, ap):
    return best_turn(dict(_STATS), casts, ap, game_version=version, caster_level=200)


class EachCastOnThePreyLandsTheNextStackTests(SimpleTestCase):

    def test_the_second_cast_scores_the_stack_1_row(self):
        for version in VERSIONS:
            _in_version(self, version)
            for spell_id in GROWING:
                spell = _spell(version, spell_id)
                cast = _cast(spell)
                _total, order = _turn(version, [cast], 2 * cast.cost)
                first = _turn(version, [_landing_on(spell, 0)], cast.cost)[0]
                second = _turn(version, [_landing_on(spell, 1)], cast.cost)[0]
                with self.subTest(version=version, spell=spell.name):
                    self.assertEqual([name for name, _damage in order], [spell.name] * 2)
                    self.assertAlmostEqual(order[0][1], first)
                    self.assertAlmostEqual(order[1][1], second)
                    self.assertGreater(second, first)

    def test_both_are_listed_on_the_sentence_their_card_states(self):
        generator = _generator()
        for version in VERSIONS:
            for spell_id in GROWING:
                with self.subTest(version=version, spell=spell_id):
                    self.assertTrue(_spell(version, spell_id).stacks_on_recast)
                    self.assertEqual(generator.RECAST_STACKS_BY_VERSION[version][spell_id],
                                     SAYS_IT_GROWS)

    def test_the_second_cast_note_says_the_target_is_the_prey(self):
        from django.utils import translation
        from chardata.spells_view import _cast_note
        for version in VERSIONS:
            for spell_id in GROWING:
                spell = _spell(version, spell_id)
                self.assertTrue(spell.recast_needs_prey)
                with self.subTest(version=version, spell=spell.name), translation.override('en'):
                    self.assertEqual(
                        'counted on Stack 1, if the target is the Prey',
                        _cast_note(_cast(spell), spell.name, {}, 10, version, 1))
