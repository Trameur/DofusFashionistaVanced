# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Devouring Arrow steals more on each cast at one enemy, a recast replaces the delayed hit, and the turn counts the last one."""
import copy
from unittest import mock

from django.test import SimpleTestCase
from django.utils import translation

from chardata.spell_buffs import get_damage_spells_for_version
from chardata.spell_combo import (Castable, _late_landed, best_turn, delayed_by_cast,
                                  delayed_damage, late_taken_back)

DEVOURING_ARROW = 32446
VERSIONS = ('dofus3', 'beta')
QUOTE = "le vol de vie est plus important après chaque lancer sur un même ennemi"
SECOND_CAST_NOTE = {'en': 'counted on Stack 1', 'fr': 'compté sur Cumul 1'}
COUNTED = {'en': 'counted in the total', 'fr': 'compté dans le total'}

_STATS = {'str': 100, 'int': 800, 'cha': 100, 'agi': 100, 'pow': 0, 'dam': 0,
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


def _spell(version):
    return next(spell for spells in get_damage_spells_for_version(version).values()
                for spell in spells if spell.spell_id == DEVOURING_ARROW)


def _cast(spell):
    return Castable(spell, len(spell.level_req) - 1, crit=False)


def _turn(version, cast, casts):
    return best_turn(dict(_STATS), [cast], casts * cast.cost, game_version=version,
                     caster_level=200)


def _first_cast_on(spell, label):
    """The spell as if its first cast landed the group named `label`."""
    alone = copy.copy(spell)
    alone.aggregates = [group for group in spell.aggregates
                        if group[0] == label or not group[0]]
    alone.stacks_on_recast = False
    alone.digest = None
    return _cast(alone)


FIRST_GATE = 'A,e573'
SECOND_GATE = 'A,E573'
CAST_ROWS = [{'situation': mask + '|80'}
             for mask in ('g', FIRST_GATE, SECOND_GATE, FIRST_GATE, SECOND_GATE, FIRST_GATE)]


def _with_removal(levels=1, removed=DEVOURING_ARROW, mask='A,e662', state=True,
                  state_mask=FIRST_GATE):
    effects = [{'effect_id': 406, 'value': removed, 'triggers': 'I', 'target_mask': mask}]
    if state:
        effects.append({'effect_id': 950, 'value': 573, 'target_mask': state_mask})
    return [{'effects': effects}] * levels


def _without_late(cast):
    """A copy of the castable with its late rows taken out of every alternative."""
    kept = copy.copy(cast)
    late = cast.late_by_effect
    for name in ('plain_alternatives', 'crit_alternatives'):
        setattr(kept, name, [[row for row in alternative if id(row) not in late]
                             for alternative in getattr(cast, name)])
    kept.alternatives = kept.crit_alternatives if cast.crit else kept.plain_alternatives
    kept.recasts = [tuple([[row for row in alternative if id(row) not in late]
                           for alternative in alternatives] for alternatives in recast)
                    for recast in getattr(cast, 'recasts', None) or []]
    kept.late_by_effect = {}
    return kept


class TheGeneratorLaddersDevouringArrowTests(SimpleTestCase):

    def test_the_four_enemy_groups_are_stacks_and_the_ally_row_is_held(self):
        for version in VERSIONS:
            spell = _spell(version)
            with self.subTest(version=version):
                self.assertTrue(spell.stacks_on_recast)
                self.assertEqual(spell.conditional.get(0), 'on_ally')
                self.assertEqual([(label, list(indices)) for label, indices in spell.aggregates
                                  if label.startswith('Stack')],
                                 [('Stack 0', [1, 5]), ('Stack 1', [2, 7]),
                                  ('Stack 2', [3, 9]), ('Stack 3', [4, 10])])

    def test_the_cast_groups_are_named_in_cast_order_around_the_held_ones(self):
        gen = _generator()
        aggregates = [('', [0]), ('', [1, 5]), ('', [2, 7]), ('', [6]), ('', [3])]
        conditional = {0: 'on_ally', 6: 'initial_enemy'}
        with mock.patch.object(gen, 'RECAST_STACKS', {DEVOURING_ARROW: QUOTE}):
            self.assertEqual(
                gen._label_the_recast_ladder({'ankama_id': DEVOURING_ARROW}, aggregates,
                                             conditional),
                [('', [0]), ('Stack 0', [1, 5]), ('Stack 1', [2, 7]), ('', [6]),
                 ('Stack 2', [3])])
            self.assertEqual(gen._label_the_recast_ladder({'ankama_id': 1}, aggregates,
                                                          conditional), aggregates)

    def test_a_delayed_row_is_a_stack_only_when_each_cast_removes_the_last_one(self):
        gen = _generator()
        spell = {'ankama_id': DEVOURING_ARROW, 'description_fr': QUOTE.capitalize() + '.',
                 'levels': _with_removal(2)}
        ladder = [('', [0]), ('Stack 0', [1, 3]), ('Stack 1', [2, 4])]
        held = {0: 'on_ally'}
        late = {3: 'later_turn', 4: 'later_turn'}
        with mock.patch.object(gen, 'RECAST_STACKS', {DEVOURING_ARROW: QUOTE}):
            self.assertTrue(gen._stacks_on_recast(spell, ladder, held, late, CAST_ROWS))
            crowded = [('', [0]), ('Stack 0', [1, 3, 5]), ('Stack 1', [2, 4])]
            swapped = [CAST_ROWS[0], CAST_ROWS[2], CAST_ROWS[1], CAST_ROWS[4], CAST_ROWS[3]]
            for case, (aggregates, conditional, delayed, levels, rows) in {
                    'no removal': (ladder, held, late, [{'effects': []}] * 2, CAST_ROWS),
                    'one grade without removal': (ladder, held, late,
                                                  _with_removal() + [{'effects': []}],
                                                  CAST_ROWS),
                    'removal of another spell': (ladder, held, late,
                                                 _with_removal(2, removed=DEVOURING_ARROW + 1),
                                                 CAST_ROWS),
                    'removal that spares the enemy': (ladder, held, late,
                                                      _with_removal(2, mask='a'), CAST_ROWS),
                    'delayed row off the ladder': (ladder, held, {**late, 5: 'later_turn'},
                                                   _with_removal(2), CAST_ROWS),
                    'held row inside a cast group': (
                        crowded, {**held, 5: 'initial_enemy'}, {**late, 5: 'later_turn'},
                        _with_removal(2), CAST_ROWS),
                    'two hits on one cast': (crowded, held, late, _with_removal(2),
                                             CAST_ROWS),
                    'two delayed hits on one cast': (crowded, held,
                                                     {**late, 5: 'later_turn'},
                                                     _with_removal(2), CAST_ROWS),
                    'groups out of the order the states chain them': (
                        ladder, held, late, _with_removal(2), swapped),
                    'state handed on by the wrong cast': (
                        ladder, held, late, _with_removal(2, state_mask=SECOND_GATE),
                        CAST_ROWS),
                    'no state handed on to the next cast': (
                        ladder, held, late, _with_removal(2, state=False), CAST_ROWS)}.items():
                with self.subTest(case=case):
                    with self.assertRaises(SystemExit):
                        gen._stacks_on_recast(dict(spell, levels=levels), aggregates,
                                              conditional, delayed, rows)


class EachCastStealsMoreTests(SimpleTestCase):

    def test_the_first_cast_steals_from_the_enemy_not_with_the_ally_row(self):
        for version in VERSIONS:
            _in_version(self, version)
            cast = _cast(_spell(version))
            landed = [id(effect) for alternative in cast.plain_alternatives
                      for effect in alternative]
            with self.subTest(version=version):
                self.assertIn(id(cast.effects[1]), landed)
                self.assertNotIn(id(cast.effects[0]), landed)

    def test_the_second_cast_steals_more_than_the_first(self):
        for version in VERSIONS:
            _in_version(self, version)
            spell = _spell(version)
            cast = _cast(spell)
            _total, order = _turn(version, cast, 2)
            steals = [damage - late for (_name, damage), late in zip(
                order, delayed_by_cast(dict(_STATS), [cast], order, game_version=version))]
            first = _first_cast_on(spell, 'Stack 0')
            second = _first_cast_on(spell, 'Stack 1')
            with self.subTest(version=version):
                self.assertEqual([name for name, _damage in order], [cast.name] * 2)
                self.assertGreater(steals[1], steals[0])
                for steal, alone in zip(steals, (first, second)):
                    _one, solo = _turn(version, _without_late(alone), 1)
                    self.assertAlmostEqual(steal, solo[0][1])

    def test_the_turn_counts_the_steals_and_the_last_delayed_hit(self):
        for version in VERSIONS:
            _in_version(self, version)
            cast = _cast(_spell(version))
            steals = _without_late(cast)
            for casts in (1, 2):
                total, order = _turn(version, cast, casts)
                alone, _order = _turn(version, steals, casts)
                late = delayed_damage(dict(_STATS), [cast], order, game_version=version)[
                    cast.name]
                with self.subTest(version=version, casts=casts):
                    self.assertGreater(late, 0)
                    self.assertAlmostEqual(total, alone + late)

    def test_a_critical_cast_takes_back_the_critical_delayed_hit(self):
        for version in VERSIONS:
            _in_version(self, version)
            spell = _spell(version)
            plain = _cast(spell)
            critical = Castable(spell, len(spell.level_req) - 1, crit=True)
            stats = dict(_STATS)
            taken = {key: late_taken_back(cast, 1, stats, 1.0, crit=True, game_version=version)
                     for key, cast in (('plain', plain), ('critical', critical))}
            with self.subTest(version=version):
                self.assertAlmostEqual(
                    taken['critical'],
                    _late_landed(critical, critical.crit_alternatives, stats, True, 1.0)[1])
                self.assertAlmostEqual(
                    taken['plain'],
                    _late_landed(plain, plain.plain_alternatives, stats, True, 1.0)[1])
                self.assertNotAlmostEqual(taken['critical'], taken['plain'])

    def test_the_delayed_hit_shown_is_the_last_casts_only(self):
        for version in VERSIONS:
            _in_version(self, version)
            spell = _spell(version)
            cast = _cast(spell)
            _total, order = _turn(version, cast, 2)
            second = _first_cast_on(spell, 'Stack 1')
            _one, solo = _turn(version, second, 1)
            with self.subTest(version=version):
                self.assertAlmostEqual(
                    delayed_damage(dict(_STATS), [cast], order, game_version=version)[cast.name],
                    delayed_damage(dict(_STATS), [second], solo, game_version=version)[second.name])

    def test_the_panel_shows_each_cast_its_steal_and_the_last_delayed_hit_beside_it(self):
        from chardata import spells_view
        _in_version(self, 'dofus3')
        cast = _cast(_spell('dofus3'))
        second = _first_cast_on(_spell('dofus3'), 'Stack 1')
        _one, solo = _turn('dofus3', second, 1)
        turn, _order = _turn('dofus3', cast, 2)
        last = delayed_damage(dict(_STATS), [second], solo, game_version='dofus3')[second.name]
        char = mock.Mock(char_class='Cra', level=200)
        solution = mock.Mock(item_list=[])
        solution.get_stats_total.return_value = dict(_STATS, ap=2 * cast.cost)
        with mock.patch('chardata.spell_combo.castable_spells', return_value=[cast]), \
                mock.patch('chardata.spell_combo.buffs_in_force', return_value={}), \
                mock.patch('chardata.spell_combo.stacks_in_force', return_value={}), \
                mock.patch('chardata.temporix_mode.solution_uses_temporix', return_value=False), \
                mock.patch.object(spells_view, 'worn_spell_modifiers', return_value={}), \
                mock.patch.object(spells_view, '_weapon_castable', return_value=None):
            for language in ('en', 'fr'):
                with translation.override(language), self.subTest(language=language):
                    combo = spells_view._best_combo(char, solution, 'dofus3',
                                                    note_without_buffs=False)
                    self.assertEqual([entry['note'] for entry in combo['casts']],
                                     [SECOND_CAST_NOTE[language].replace('1', '0'),
                                      SECOND_CAST_NOTE[language]])
                    self.assertGreater(combo['casts'][1]['damage'],
                                       combo['casts'][0]['damage'])
                    self.assertEqual([entry['late'] for entry in combo['casts']],
                                     [0, int(round(last))])
                    self.assertIn(COUNTED[language], combo['casts'][1]['late_title'])
                    self.assertEqual('', combo['casts'][0]['late_title'])
                    self.assertEqual(sum(entry['damage'] + entry['late']
                                         for entry in combo['casts']), int(round(turn)))
                    self.assertEqual(combo['total'], int(round(turn)))
                    self.assertEqual(combo['total'], spells_view._burst_total(
                        dict(_STATS, ap=2 * cast.cost), [cast], _order, {}, 'dofus3'))
                    self.assertEqual([], combo['later'])
                    self.assertEqual(0, combo['later_total'])


class WhichSpellsCountTheirDelayedHitTests(SimpleTestCase):

    def test_only_devouring_arrow_counts_it_in_every_version(self):
        from chardata.spells_view import _counts_its_late
        for version in VERSIONS:
            with self.subTest(version=version):
                counted = {spell.spell_id
                           for spells in get_damage_spells_for_version(version).values()
                           for spell in spells
                           if _counts_its_late(Castable(spell, len(spell.level_req) - 1, crit=False))
                           and spell.delayed}
                self.assertEqual({DEVOURING_ARROW}, counted)
