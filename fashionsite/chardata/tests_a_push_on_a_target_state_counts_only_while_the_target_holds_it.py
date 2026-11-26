# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A push that needs the target in a state counts for the casts that follow one that puts it there, or for a target that starts in it."""
import copy
import itertools
from unittest import mock

from django.test import SimpleTestCase

import chardata.spell_combo as spell_combo
from chardata.pushback import pushback_damage
from chardata.spell_combo import best_turn, castable_spells, conditional_extras
from chardata.spell_reference import (get_spell_reference, lasting_target_states,
                                      target_state_moves, target_state_push)
from chardata.tests import itemscraper_module
from fashionistapulp.structure import get_structure, set_current_game_version

PAINT, PREY, EARTH, BLOWN = 4244, 516, 292, 807


def _gated(version):
    found = {}
    for char_class, entries in get_spell_reference(version).items():
        for entry in entries or []:
            if 'push_by_target_state' in entry:
                found[(char_class, entry['id'])] = [
                    (rank['state'], rank['with'], rank['without']) if rank else None
                    for rank in entry['push_by_target_state']]
    return found


def _stats(version, **more):
    stats = {stat.key: 0 for stat in get_structure(version).get_stats_list()}
    stats.update({'str': 1000, 'pow': 200, 'pshdam': 200, 'ap': 12})
    stats.update(more)
    return stats


class ThePushesThatNeedATargetStateTests(SimpleTestCase):

    def test_each_version_names_the_state_and_cells_of_its_gated_pushes(self):
        expected = {
            'dofus2': {('Eniripsa', 25863): [(PAINT, 4, 0)] * 3,
                       ('Ouginak', 13795): [(PREY, 4, 2)],
                       ('Huppermage', 13696): [(EARTH, 3, 0)] * 3},
            'dofus3': {('Huppermage', 13696): [(EARTH, 2, 0), (EARTH, 3, 0)]},
            'beta': {('Huppermage', 13696): [(EARTH, 2, 0), (EARTH, 3, 0)]},
            'touch': {('Iop', 8105): [(BLOWN, 3, 2)] * 6},
            'touchbeta': {('Iop', 8105): [(BLOWN, 3, 2)] * 6},
            'retro': {},
            'retrobeta': {},
        }
        for version, entries in expected.items():
            with self.subTest(version=version):
                self.assertEqual(entries, _gated(version))

    def test_a_gated_push_reads_its_own_rank(self):
        self.assertEqual({'state': EARTH, 'with': 2, 'without': 0},
                         target_state_push('dofus3', 13696, 0))
        self.assertEqual({'state': EARTH, 'with': 3, 'without': 0},
                         target_state_push('dofus3', 13696))
        self.assertIsNone(target_state_push('dofus3', 25863))

    def test_the_store_reads_a_state_given_through_a_cast_child_spell_at_its_grade(self):
        store = itemscraper_module('store_spell_reference')
        at_enemy = 'a,A'
        children = {99: [{'grade': 1, 'effects': []},
                         {'grade': 2, 'effects': [{'effect_id': 950, 'value': 7,
                                                   'target_mask': at_enemy}]}]}
        cast = {'effect_id': 1160, 'dice': {'min': 99, 'max': 2}, 'target_mask': at_enemy}
        given, taken, lasting = store._target_state_moves([cast], {7}, children.get)
        self.assertEqual(({7}, set(), set()), (given, taken, lasting))
        first = dict(cast, dice={'min': 99, 'max': 1})
        self.assertEqual((set(), set(), set()),
                         store._target_state_moves([first], {7}, children.get))

    def test_the_store_keeps_a_state_applied_for_the_fight_apart_from_a_timed_one(self):
        store = itemscraper_module('store_spell_reference')
        effect = {'effect_id': 950, 'value': 7, 'target_mask': 'a,A', 'duration': -1}
        timed = dict(effect, duration=2)
        self.assertEqual(({7}, set(), {7}), store._target_state_moves([effect], {7}, {}.get))
        self.assertEqual(({7}, set(), set()), store._target_state_moves([timed], {7}, {}.get))

    def test_the_store_refuses_a_push_on_two_target_states(self):
        store = itemscraper_module('store_spell_reference')
        levels = [{'effects': [
            {'effect_id': 5, 'dice': {'min': 2}, 'target_mask': 'a,A,E7'},
            {'effect_id': 5, 'dice': {'min': 3}, 'target_mask': 'a,A,E8'}]}]
        with self.assertRaises(ValueError):
            store._push_by_target_state_per_rank(levels)

    def test_the_store_refuses_a_push_that_moves_less_on_its_state(self):
        store = itemscraper_module('store_spell_reference')
        levels = [{'effects': [
            {'effect_id': 5, 'dice': {'min': 1}, 'target_mask': 'a,A,E7'},
            {'effect_id': 5, 'dice': {'min': 3}, 'target_mask': 'a,A,e7'}]}]
        with self.assertRaises(ValueError):
            store._push_by_target_state_per_rank(levels)

    def test_the_store_leaves_a_caster_state_gate_to_the_existing_push_reader(self):
        store = itemscraper_module('store_spell_reference')
        levels = [{'effects': [{'effect_id': 5, 'dice': {'min': 2}, 'target_mask': 'a,A,*E7'}]}]
        self.assertIsNone(store._push_by_target_state_per_rank(levels))


class TheCastsThatMoveATargetStateTests(SimpleTestCase):

    def test_paint_comes_from_tribal_paintbrush_and_warpaint_through_their_child_spell(self):
        for spell_id in (25866, 25868):
            for rank in range(3):
                with self.subTest(spell_id=spell_id, rank=rank):
                    self.assertEqual((frozenset({PAINT}), frozenset()),
                                     target_state_moves('dofus2', spell_id, rank))

    def test_prey_lasts_the_fight_from_prey_and_three_turns_from_venison(self):
        prey = next(entry for entries in get_spell_reference('dofus2').values()
                    for entry in entries if entry.get('id') == 13748)
        venison = next(entry for entries in get_spell_reference('dofus2').values()
                       for entry in entries if entry.get('id') == 13786)
        self.assertEqual({PREY}, set(prey['target_states'][-1]['lasting']))
        self.assertEqual([], venison['target_states'][-1]['lasting'])
        self.assertEqual((frozenset({PREY}), frozenset()),
                         target_state_moves('dofus2', 13786))
        self.assertEqual({PREY}, lasting_target_states('dofus2', 'Ouginak'))
        self.assertEqual(set(), lasting_target_states('dofus2', 'Eniripsa'))

    def test_polarity_takes_the_earth_state_it_pushes_on(self):
        for version in ('dofus2', 'dofus3', 'beta'):
            with self.subTest(version=version):
                self.assertEqual((frozenset(), frozenset({EARTH})),
                                 target_state_moves(version, 13696))

    def test_breath_gives_blown_for_two_turns(self):
        for version in ('touch', 'touchbeta'):
            with self.subTest(version=version):
                self.assertEqual((frozenset({BLOWN}), frozenset()),
                                 target_state_moves(version, 8115))
                self.assertEqual(set(), lasting_target_states(version, 'Iop'))


class ATurnOnATargetStateTests(SimpleTestCase):

    def _spells(self, version, char_class):
        self.addCleanup(set_current_game_version, 'dofus3')
        set_current_game_version(version)
        return {spell.spell_id: spell for spell in castable_spells(char_class, 200, version)}

    def _turn(self, version, spells, ap, states, **more):
        return best_turn(_stats(version), spells, ap, game_version=version, pushback=True,
                         caster_level=200, target_states=frozenset(states), **more)

    def test_war_cry_alone_pushes_only_a_painted_target(self):
        spells = self._spells('dofus2', 'Eniripsa')
        war_cry = spells[25863]
        off, _order = best_turn(_stats('dofus2'), [war_cry], war_cry.cost, game_version='dofus2',
                                pushback=False, caster_level=200)
        unchecked = self._turn('dofus2', [war_cry], war_cry.cost, ())[0]
        checked = self._turn('dofus2', [war_cry], war_cry.cost, {PAINT})[0]
        self.assertEqual(off, unchecked)
        self.assertAlmostEqual(
            pushback_damage(200, 200, 4, game_version='dofus2') / 2, checked - unchecked)

    def test_warpaint_cast_first_lets_war_cry_push_in_the_same_turn(self):
        spells = self._spells('dofus2', 'Eniripsa')
        pair = [spells[25863], spells[25868]]
        ap = sum(spell.cost for spell in pair)
        total, order = self._turn('dofus2', pair, ap, ())
        self.assertEqual([spells[25868].name, spells[25863].name], [name for name, _ in order])
        self.assertAlmostEqual(
            self._turn('dofus2', [pair[0]], pair[0].cost, {PAINT})[0], order[1][1])
        self.assertAlmostEqual(self._turn('dofus2', pair, ap, {PAINT})[0], total)
        dry = copy.copy(pair[1])
        dry.gives_target_states = frozenset()
        self.assertAlmostEqual(
            pushback_damage(200, 200, 4, game_version='dofus2') / 2,
            total - self._turn('dofus2', [pair[0], dry], ap, ())[0])

    def test_a_cast_that_takes_the_state_stops_the_next_push(self):
        spells = self._spells('dofus2', 'Eniripsa')
        twice = copy.copy(spells[25863])
        twice.limit = 2
        kept = self._turn('dofus2', [twice], twice.cost * 2, {PAINT})[0]
        removing = copy.copy(twice)
        removing.takes_target_states = frozenset({PAINT})
        self.assertAlmostEqual(
            pushback_damage(200, 200, 4, game_version='dofus2') / 2,
            kept - self._turn('dofus2', [removing], removing.cost * 2, {PAINT})[0])

    def test_pursuit_pushes_a_blown_target_one_cell_further(self):
        for version in ('touch', 'touchbeta'):
            spells = self._spells(version, 'Iop')
            pursuit = spells[8105]
            with self.subTest(version=version):
                self.assertAlmostEqual(
                    (pushback_damage(200, 200, 3, game_version=version)
                     - pushback_damage(200, 200, 2, game_version=version)) / 2,
                    self._turn(version, [pursuit], pursuit.cost, {BLOWN})[0]
                    - self._turn(version, [pursuit], pursuit.cost, ())[0])

    def test_the_bounded_search_and_the_full_search_agree_on_a_target_state_turn(self):
        for version, char_class, state in (('dofus2', 'Eniripsa', PAINT),
                                           ('dofus2', 'Ouginak', PREY),
                                           ('touch', 'Iop', BLOWN)):
            spells = list(self._spells(version, char_class).values())
            for ap, states in itertools.product((6, 9, 12), ((), (state,))):
                with self.subTest(version=version, char_class=char_class, ap=ap, states=states):
                    bounded = spell_combo._search_best_turn(
                        _stats(version), spells, ap, game_version=version, pushback=True,
                        caster_level=200, target_states=frozenset(states))
                    with mock.patch.object(spell_combo, 'CEILING_SCORES', -1):
                        full = spell_combo._search_best_turn(
                            _stats(version), spells, ap, game_version=version, pushback=True,
                            caster_level=200, target_states=frozenset(states))
                    self.assertAlmostEqual(full[0], bounded[0])

    def test_two_orders_that_reach_the_same_counts_keep_their_own_target_state(self):
        spells = self._spells('dofus2', 'Eniripsa')
        warpaint, war_cry = spells[25868], spells[25863]
        wiping = copy.copy(spells[25745])
        wiping.takes_target_states = frozenset({PAINT})
        turn = [warpaint, wiping, war_cry]
        ap = sum(spell.cost for spell in turn)
        for ceiling in (spell_combo.CEILING_SCORES, -1):
            with self.subTest(ceiling=ceiling), mock.patch.object(
                    spell_combo, 'CEILING_SCORES', ceiling):
                total, order = spell_combo._search_best_turn(
                    _stats('dofus2'), turn, ap, game_version='dofus2', pushback=True,
                    caster_level=200, target_states=frozenset())
                self.assertEqual([wiping.name, warpaint.name, war_cry.name],
                                 [name for name, _ in order])

    def test_a_class_without_a_target_state_push_keeps_its_turn(self):
        everything = frozenset({PAINT, PREY, EARTH, BLOWN})
        for version, char_class in (('dofus3', 'Cra'), ('dofus3', 'Huppermage'),
                                    ('dofus2', 'Iop'), ('touch', 'Cra'), ('retro', 'Iop')):
            spells = list(self._spells(version, char_class).values())
            with self.subTest(version=version, char_class=char_class):
                self.assertFalse([spell for spell in spells if spell.push_target_state])
                kwargs = dict(game_version=version, pushback=True, caster_level=200)
                self.assertEqual(best_turn(_stats(version), spells, 12, **kwargs),
                                 best_turn(_stats(version), spells, 12, target_states=everything,
                                           **kwargs))

    def test_without_pushback_war_cry_lists_its_push_only_on_a_painted_target(self):
        spells_by_id = self._spells('dofus2', 'Eniripsa')
        spells = list(spells_by_id.values())
        war_cry, warpaint = spells_by_id[25863], spells_by_id[25868]
        kwargs = dict(game_version='dofus2', caster_level=200)
        dealt = pushback_damage(200, 200, 4, game_version='dofus2')
        self.assertEqual([], conditional_extras(_stats('dofus2'), spells, [(war_cry.name, 0.0)],
                                                target_states=frozenset(), **kwargs))
        self.assertEqual([(war_cry.name, 'pushback into an obstacle', dealt)],
                         conditional_extras(_stats('dofus2'), spells, [(war_cry.name, 0.0)],
                                            target_states=frozenset({PAINT}), **kwargs))
        order = [(warpaint.name, 0.0), (war_cry.name, 0.0)]
        extras = conditional_extras(_stats('dofus2'), spells, order,
                                    target_states=frozenset(), **kwargs)
        stripped = warpaint.strips_pushback_resist
        dealt = pushback_damage(200, 200, 4, target_resistance=-stripped, game_version='dofus2')
        self.assertEqual([(war_cry.name, 'pushback into an obstacle', dealt)],
                         [line for line in extras if line[0] == war_cry.name])

    def test_without_pushback_a_cast_that_takes_the_state_ends_the_listed_push(self):
        spells_by_id = self._spells('dofus2', 'Eniripsa')
        removing = copy.copy(spells_by_id[25863])
        removing.takes_target_states = frozenset({PAINT})
        extras = conditional_extras(_stats('dofus2'), [removing],
                                    [(removing.name, 0.0)] * 2, game_version='dofus2',
                                    caster_level=200, target_states=frozenset({PAINT}))
        self.assertEqual([(removing.name, 'pushback into an obstacle',
                           pushback_damage(200, 200, 4, game_version='dofus2'))], extras)
