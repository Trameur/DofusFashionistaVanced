# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A spell whose damage grows after each cast lands its next Stack group on each cast of the turn."""

import copy
from unittest import mock

from django.test import SimpleTestCase
from django.utils import translation

from chardata import spell_combo
from chardata.spell_buffs import get_damage_spells_for_version
from chardata.spell_combo import (Castable, apply_spell_modifiers, best_turn,
                                  cast_label, recast_alternatives)
from chardata.spell_modifiers import SpellModifier
from chardata.spell_reference import get_spell_reference

FROZEN_ARROW = 32435
IMMOBILISING_ARROW = 32436
FIRE_LANCE = 23263
GROWING = (FROZEN_ARROW, IMMOBILISING_ARROW, FIRE_LANCE)
VERSIONS = ('dofus3', 'beta')
LANGUAGES = ('en', 'fr', 'es', 'pt', 'de')

SAYS_IT_GROWS = {'en': 'increased after each casting',
                 'fr': 'augmentés après chaque lancer',
                 'es': 'después de cada lanzamiento',
                 'pt': 'aumentam após cada lançamento',
                 'de': 'jedem wirken'}

SECOND_CAST_NOTE = {'en': 'counted on Stack 1',
                    'fr': 'compté sur Cumul 1',
                    'es': 'contado en Acumulación 1',
                    'pt': 'contado em Acúmulo 1',
                    'de': 'mit Stapel 1 gewertet'}

_STATS = {'str': 100, 'int': 100, 'cha': 800, 'agi': 100, 'pow': 0, 'dam': 0,
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
    """The spell as if its first cast landed the Stack group `stack`."""
    alone = copy.copy(spell)
    alone.aggregates = spell.aggregates[stack:]
    alone.stacks_on_recast = False
    alone.digest = None
    return _cast(alone)


def _turn(version, casts, ap):
    return best_turn(dict(_STATS), casts, ap, game_version=version, caster_level=200)


def _card(version, spell_id, language):
    for entries in get_spell_reference(version).values():
        for entry in entries:
            if entry.get('id') == spell_id:
                return ((entry.get('description') or {}).get(language) or '').lower()
    return ''


class EachCastLandsTheNextStackTests(SimpleTestCase):

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

    def test_two_casts_deal_more_than_twice_the_first(self):
        for version in VERSIONS:
            _in_version(self, version)
            for spell_id in GROWING:
                cast = _cast(_spell(version, spell_id))
                one = _turn(version, [cast], cast.cost)[0]
                two = _turn(version, [cast], 2 * cast.cost)[0]
                with self.subTest(version=version, spell=cast.name):
                    self.assertGreater(two, 2 * one)

    def test_the_exhaustive_search_agrees_with_the_bounded_one(self):
        for version in VERSIONS:
            _in_version(self, version)
            casts = [_cast(_spell(version, spell_id)) for spell_id in GROWING]
            for ap in range(2, 13):
                bounded = spell_combo._search_best_turn(dict(_STATS), casts, ap,
                                                        game_version=version)
                with mock.patch.object(spell_combo, 'CEILING_SCORES', -1):
                    exhaustive = spell_combo._search_best_turn(dict(_STATS), casts, ap,
                                                               game_version=version)
                with self.subTest(version=version, ap=ap):
                    self.assertAlmostEqual(bounded[0], exhaustive[0])

    def test_the_bound_keeps_the_best_turn_of_a_full_class_at_each_level(self):
        for version in VERSIONS:
            _in_version(self, version)
            for level in (50, 100, 200):
                spells = spell_combo.castable_spells('Cra', level, version)
                for ap in (7, 9, 11):
                    stats = dict(_STATS, ap=ap)
                    args = (stats, spells, ap)
                    bounded = spell_combo._search_best_turn(*args, game_version=version,
                                                            caster_level=level)
                    with mock.patch.object(spell_combo, 'CEILING_SCORES', -1):
                        exhaustive = spell_combo._search_best_turn(*args, game_version=version,
                                                                   caster_level=level)
                    with self.subTest(version=version, level=level, ap=ap):
                        self.assertAlmostEqual(bounded[0], exhaustive[0])

    def test_a_cast_past_the_last_stack_stays_on_it(self):
        cast = _cast(_spell('dofus3', FROZEN_ARROW))
        self.assertIsNone(recast_alternatives(cast, 0))
        self.assertIs(recast_alternatives(cast, 9), recast_alternatives(cast, 2))
        self.assertIs(recast_alternatives(cast, 1), cast.recasts[0])
        self.assertIs(recast_alternatives(cast, 2), cast.recasts[1])
        self.assertEqual([cast_label(cast, count) for count in range(4)],
                         ['Stack 0', 'Stack 1', 'Stack 2', 'Stack 2'])

    def test_a_spell_that_does_not_grow_lands_its_first_group_every_cast(self):
        spell = copy.copy(_spell('dofus3', FROZEN_ARROW))
        spell.stacks_on_recast = False
        spell.digest = None
        cast = _cast(spell)
        _total, order = _turn('dofus3', [cast], 2 * cast.cost)
        self.assertAlmostEqual(order[0][1], order[1][1])
        self.assertIsNone(recast_alternatives(cast, 1))

    def test_a_worn_base_damage_bonus_raises_every_stack(self):
        cast = _cast(_spell('dofus3', FIRE_LANCE))
        rows = [plain[0][0].max_dam for plain, _critical in cast.recasts]
        apply_spell_modifiers(cast, [SpellModifier('base_damage', 7, 'ring')])
        raised = [plain[0][0].max_dam for plain, _critical in cast.recasts]
        self.assertEqual(raised, [value + 7 for value in rows])

    def test_the_panel_notes_each_cast_on_its_stack_in_every_language(self):
        from chardata.spells_view import _cast_note
        cast = _cast(_spell('dofus3', FROZEN_ARROW))
        for language in LANGUAGES:
            with translation.override(language):
                with self.subTest(language=language):
                    self.assertEqual(_cast_note(cast, cast.name, {}, 400, 'dofus3', 1),
                                     SECOND_CAST_NOTE[language])

    def test_the_panel_counts_the_first_cast_on_stack_0_and_the_second_on_stack_1(self):
        from chardata import spells_view
        _in_version(self, 'dofus3')
        cast = _cast(_spell('dofus3', FROZEN_ARROW))
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

    def test_the_card_says_the_damage_grows_after_each_cast_in_every_language(self):
        for version in VERSIONS:
            for spell_id in GROWING:
                for language in LANGUAGES:
                    with self.subTest(version=version, spell=spell_id, language=language):
                        self.assertIn(SAYS_IT_GROWS[language],
                                      _card(version, spell_id, language))


class TheGeneratorMarksTheGrowingSpellsTests(SimpleTestCase):

    def test_the_generated_tables_mark_exactly_the_listed_spells(self):
        gen = _generator()
        for version in VERSIONS + ('dofus2',):
            marked = {spell.spell_id for spells in get_damage_spells_for_version(version).values()
                      for spell in spells if getattr(spell, 'stacks_on_recast', False)}
            with self.subTest(version=version):
                self.assertEqual(marked, set(gen.RECAST_STACKS_BY_VERSION[version]))

    def test_each_listed_quote_is_in_the_french_card(self):
        gen = _generator()
        for version in VERSIONS:
            for spell_id, quote in gen.RECAST_STACKS_BY_VERSION[version].items():
                with self.subTest(version=version, spell=spell_id):
                    self.assertIn(quote, _card(version, spell_id, 'fr'))

    def test_rows_that_are_not_one_stack_group_per_cast_stop_the_run(self):
        gen = _generator()
        spell = {'ankama_id': FROZEN_ARROW,
                 'description_fr': 'Les dommages du sort sont augmentés après chaque lancer.'}
        with mock.patch.object(gen, 'RECAST_STACKS', gen.RECAST_STACKS_BY_VERSION['dofus3']):
            self.assertTrue(gen._stacks_on_recast(
                spell, [('Stack 0', [0]), ('Stack 1', [1])], {}, None))
            for aggregates, conditional, delayed in (
                    ([('Stack 0', [0]), ('Stack 2', [1])], {}, None),
                    ([('Stack 0', [0, 1]), ('Stack 1', [2])], {}, None),
                    ([('Stack 0', [0])], {}, None),
                    ([('Stack 0', [0]), ('Stack 1', [1])], {1: 'pushback'}, None),
                    ([('Stack 0', [0]), ('Stack 1', [1])], {}, {1: 'turn_end'})):
                with self.subTest(aggregates=aggregates, conditional=conditional,
                                  delayed=delayed):
                    with self.assertRaises(SystemExit):
                        gen._stacks_on_recast(spell, aggregates, conditional, delayed)
            with self.assertRaises(SystemExit):
                gen._stacks_on_recast(dict(spell, description_fr='Occasionne des dommages Eau.'),
                                      [('Stack 0', [0]), ('Stack 1', [1])], {}, None)

    def test_a_spell_off_the_list_is_not_marked(self):
        gen = _generator()
        with mock.patch.object(gen, 'RECAST_STACKS', gen.RECAST_STACKS_BY_VERSION['dofus3']):
            self.assertFalse(gen._stacks_on_recast(
                {'ankama_id': 1, 'description_fr': ''},
                [('Stack 0', [0]), ('Stack 1', [1])], {}, None))
