# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A set that counts transcendence runes says so on its page and names the minimums it would fail without them."""

import os
import pickle
from copy import deepcopy
from types import SimpleNamespace
from unittest import mock

from django.template import Context, Template
from django.utils.translation import override

from chardata import solution as solution_module
from chardata import solution_view
from chardata.dracorune_fixtures import BetaModelTestCase
from chardata.presets import effective_hp
from chardata.transcendence_card_fixtures import minimal_with, plain_pieces, rune_of_stat
from chardata.transcendence_result import theoretical_build
from fashionistapulp.dofus_constants import STATS_NAMES
from fashionistapulp.modelresult import model_result_from_minimal

TEMPLATE = os.path.join(os.path.dirname(__file__), 'templates', 'chardata', 'solution.html')


def _banner_template():
    """The banner block of the build page, cut from the template itself."""
    with open(TEMPLATE, encoding='utf-8') as handle:
        text = handle.read()
    start = text.index('{% if theoretical_build %}')
    end = text.index('{% endif %}\n', text.index('</div>', start)) + len('{% endif %}')
    return Template('{% load i18n %}' + text[start:end])


class TheBannerNamesTheMinimumsTheRunesMeetTests(BetaModelTestCase):

    def setUp(self):
        super().setUp()
        self.char = SimpleNamespace(id=1, game_version='beta')
        self.rune = rune_of_stat('vit')
        self.hat, self.other_hat = plain_pieces('Hat', 'beta', 2, self.rune)
        self.rings = plain_pieces('Ring', 'beta', 2, rune_of_stat('init'))
        self.minimums = {}
        for target, replacement in (
                ('chardata.closest_set.get_min_stats_digested', lambda char: dict(self.minimums)),
                ('chardata.transcendence_result.get_solution_from_minimal',
                 lambda char, minimal, refresh_base_stats=True: model_result_from_minimal(minimal))):
            patcher = mock.patch(target, replacement)
            patcher.start()
            self.addCleanup(patcher.stop)

    def minimal(self, with_rune=True, guard=None):
        saved = {'hat': (self.hat.id, self.rune['id'])} if with_rune else None
        minimal = minimal_with({'hat': self.hat.id}, saved)
        if guard is not None:
            minimal.guard = guard
        return minimal

    def banner(self, minimal):
        solution = model_result_from_minimal(minimal)
        return theoretical_build(self.char, minimal, solution)

    def totals(self, with_rune):
        return model_result_from_minimal(self.minimal(with_rune)).get_stats_total()

    def render(self, facts, language='en'):
        with override(language):
            return _banner_template().render(Context({'theoretical_build': facts}))

    def guarded(self, floor):
        return self.minimal(guard={'kind': 'stat_floors', 'percent': 0, 'balanced': 0,
                                   'fallback': False, 'floors': {'vit': floor}})

    def test_the_banner_counts_the_runes_of_the_set(self):
        saved = {'hat': (self.hat.id, self.rune['id']),
                 'ring1': (self.rings[0].id, rune_of_stat('init')['id'])}
        minimal = minimal_with({'hat': self.hat.id, 'ring1': self.rings[0].id}, saved)
        facts = theoretical_build(self.char, minimal, model_result_from_minimal(minimal))
        self.assertEqual(2, facts['count'])
        self.assertIn('Theoretical build: this set counts 2 transcendence runes.', self.render(facts))
        one = self.banner(self.minimal())
        self.assertEqual(1, one['count'])
        page = self.render(one)
        self.assertIn('Theoretical build: this set counts 1 transcendence rune.', page)
        self.assertIn('class="solution-acquisition-summary"', page)
        self.assertNotIn('Minimums met only with', page)

    def test_a_minimum_met_only_with_the_runes_is_named(self):
        self.minimums = {'Vitality': self.totals(False)['vit'] + 1}
        facts = self.banner(self.minimal())
        self.assertEqual(['Vitality'], facts['minimums'])
        self.assertIn('Minimums met only with this rune: Vitality', self.render(facts))

    def test_the_minimums_line_agrees_with_the_number_of_runes(self):
        for language, one, many in (
                ('en', 'Minimums met only with this rune: Vitality',
                 'Minimums met only with these runes: Vitality'),
                ('fr', 'Minimums tenus seulement grâce à cette rune : Vitality',
                 'Minimums tenus seulement grâce à ces runes : Vitality')):
            with self.subTest(language=language):
                self.assertIn(one, self.render({'count': 1, 'minimums': ['Vitality']}, language))
                self.assertIn(many, self.render({'count': 2, 'minimums': ['Vitality']}, language))

    def test_a_minimum_met_either_way_is_not_named(self):
        self.minimums = {'Vitality': self.totals(False)['vit'], 'Wisdom': 99999}
        self.assertEqual([], self.banner(self.minimal())['minimums'])

    def test_an_effective_hp_floor_met_only_with_the_runes_is_named(self):
        with_rune, bare = effective_hp(self.totals(True)), effective_hp(self.totals(False))
        self.assertGreater(with_rune, bare)
        floor = (with_rune + bare) / 2
        guard = {'kind': 'effective_hp', 'percent': 10, 'balanced': floor / 0.9,
                 'fallback': False, 'floors': {}}
        facts = self.banner(self.minimal(guard=guard))
        self.assertEqual(['Effective HP'], facts['minimums'])
        guard['balanced'] = bare / 0.9 * 0.5
        self.assertEqual([], self.banner(self.minimal(guard=guard))['minimums'])
        guard.update(balanced=floor / 0.9, fallback=True)
        self.assertEqual([], self.banner(self.minimal(guard=guard))['minimums'])

    def test_a_stat_floor_held_only_with_the_runes_is_named(self):
        bare = self.totals(False)['vit']
        self.assertEqual(['Vitality'], self.banner(self.guarded(bare + 1))['minimums'])

    def test_a_stat_floor_held_either_way_is_not_named(self):
        self.assertEqual([], self.banner(self.guarded(self.totals(False)['vit']))['minimums'])

    def test_a_stat_floor_the_set_fails_even_with_its_runes_is_not_named(self):
        self.assertEqual([], self.banner(self.guarded(self.totals(True)['vit'] + 1))['minimums'])

    def test_a_set_without_runes_shows_no_banner(self):
        minimal = self.minimal(with_rune=False)
        self.assertIsNone(self.banner(minimal))
        self.assertEqual('', self.render(None).strip())

    def test_a_rebuild_that_fails_keeps_the_count_and_names_nothing(self):
        with mock.patch('chardata.transcendence_result.get_solution_from_minimal',
                        side_effect=ValueError('boom')):
            with self.assertLogs('chardata.transcendence_result', level='ERROR'):
                facts = self.banner(self.minimal())
        self.assertEqual({'count': 1, 'minimums': []}, facts)
        self.assertIn('Theoretical build: this set counts 1 transcendence rune.', self.render(facts))

    def test_a_saved_rune_the_piece_can_no_longer_take_is_not_counted(self):
        saved = {'hat': (self.hat.id, self.rune['id']), 'ring1': 'junk'}
        minimal = minimal_with({'hat': self.hat.id, 'ring1': self.rings[0].id}, saved)
        with self.assertLogs('fashionistapulp.modelresult', level='WARNING'):
            solution = model_result_from_minimal(minimal)
        self.assertEqual(2, len(minimal.transcendences))
        self.assertEqual(1, theoretical_build(self.char, minimal, solution)['count'])


class TheBareSetReadsTheBaseStatsAsThePageSetDoesTests(BetaModelTestCase):

    def setUp(self):
        super().setUp()
        self.char = SimpleNamespace(id=1, game_version='beta', level=200, char_class='Iop',
                                    weapon_forge='')
        rune = rune_of_stat('vit')
        hat = plain_pieces('Hat', 'beta', 1, rune)[0]
        minimal = minimal_with({'hat': hat.id}, {'hat': (hat.id, rune['id'])})
        minimal.stats = {key: 0 for _name, key in STATS_NAMES}
        self.saved = minimal
        self.blob = pickle.dumps(minimal)
        self.minimums = {}
        spent = {name: 0 for name, _key in STATS_NAMES}
        spent['Vitality'] = 200
        scrolled = {name: 0 for name, _key in STATS_NAMES}
        for owner, name, replacement in (
                (solution_module, 'get_stats_and_scrolled', lambda char: (spent, scrolled)),
                (solution_module, 'get_effective_stat_overrides', lambda char: None),
                (solution_module.Wearer, 'of', lambda char: None)):
            patcher = mock.patch.object(owner, name, replacement)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = mock.patch('chardata.closest_set.get_min_stats_digested',
                             lambda char: dict(self.minimums))
        patcher.start()
        self.addCleanup(patcher.stop)

    def page_and_bare_vitality(self, refresh):
        page = solution_module.get_solution_from_blob(self.char, self.blob, refresh)
        bare = deepcopy(self.saved)
        bare.transcendences = None
        bare_page = solution_module.get_solution_from_blob(self.char, pickle.dumps(bare), refresh)
        return page, bare_page.get_stats_total()['vit']

    def test_base_stats_edited_since_the_solve_are_not_a_rune_effect(self):
        for refresh in (True, False):
            page, bare_vit = self.page_and_bare_vitality(refresh)
            self.assertGreater(page.get_stats_total()['vit'], bare_vit)
            self.minimums = {'Vitality': int(bare_vit)}
            facts = theoretical_build(self.char, deepcopy(self.saved), page, refresh)
            self.assertEqual([], facts['minimums'], refresh)

    def test_a_minimum_the_runes_carry_is_named_on_either_base_stats(self):
        for refresh in (True, False):
            page, bare_vit = self.page_and_bare_vitality(refresh)
            self.minimums = {'Vitality': int(bare_vit) + 1}
            facts = theoretical_build(self.char, deepcopy(self.saved), page, refresh)
            self.assertEqual(['Vitality'], facts['minimums'], refresh)


class TheViewHandsTheBannerToTheBuildPageTests(BetaModelTestCase):

    def test_a_build_without_saved_runes_has_no_banner(self):
        blob = pickle.dumps(minimal_with({}, None))
        with mock.patch.object(solution_view, 'theoretical_build') as banner:
            self.assertIsNone(solution_view._theoretical_build(SimpleNamespace(id=1), blob, object()))
        banner.assert_not_called()

    def test_a_build_with_saved_runes_gets_the_facts_and_the_base_stats_choice(self):
        rune = rune_of_stat('vit')
        hat = plain_pieces('Hat', 'beta', 1, rune)[0]
        blob = pickle.dumps(minimal_with({'hat': hat.id}, {'hat': (hat.id, rune['id'])}))
        solution = object()
        with mock.patch.object(solution_view, 'theoretical_build', return_value='facts') as banner:
            self.assertEqual('facts', solution_view._theoretical_build(
                SimpleNamespace(id=1, game_version='beta'), blob, solution, False))
        self.assertIs(False, banner.call_args[0][3])
        self.assertIs(solution, banner.call_args[0][2])

    def test_the_shared_page_carries_the_banner_of_its_own_set(self):
        char = SimpleNamespace(id=1, minimal_solution=b'blob', char_class='Iop', gender=0, char_name='')
        solution = object()
        with mock.patch.object(solution_view.cache, 'get', return_value=None), \
                mock.patch.object(solution_view.cache, 'set'), \
                mock.patch.object(solution_view, '_get_shared_solution_cache_key', return_value='k'), \
                mock.patch.object(solution_view, 'get_all_inclusions_en_names', return_value=[]), \
                mock.patch.object(solution_view, 'get_all_exclusions_en_names', return_value=[]), \
                mock.patch.object(solution_view, 'get_stats_weights', return_value={}), \
                mock.patch.object(solution_view, 'get_solution', return_value=solution), \
                mock.patch.object(solution_view, 'SolutionResult') as result, \
                mock.patch.object(solution_view, '_theoretical_build', return_value='facts') as banner:
            result.return_value.get_params.return_value = {}
            params = solution_view._get_shared_solution_params(char)
        self.assertEqual('facts', params['theoretical_build'])
        banner.assert_called_once_with(char, b'blob', solution)
