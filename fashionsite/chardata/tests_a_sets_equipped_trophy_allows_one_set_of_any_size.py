# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A trophy asking "Sets equipped < 2" allows one set of any size; one asking "Set bonus < N" still counts bonuses."""

import html
import pickle

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase
from django.utils import translation

from chardata.item_exchange import check_if_violates
from chardata.models import Char
from chardata.official_site import get_item_link
from chardata.solution import get_solution
from chardata.tests import itemscraper_module
from fashionistapulp.dofus_constants import STATS_NAMES
from fashionistapulp.model import Model, ModelInput
from fashionistapulp.modelresult import ModelResultMinimal, sets_equipped_text
from fashionistapulp.structure import get_structure, set_current_game_version

MINOR_OBSTRUCTOR = 16182
TOUCH_MINOR_BLOODTHIRST = 19317
CRIMSON_DAWN = 499
KWISMAS = 214
PINK = 255
OPTIONS = {'ap_exo': False, 'mp_exo': False, 'range_exo': False,
           'dofus': True, 'trophies': True, 'dragoturkey': True,
           'seemyool': True, 'rhineetle': True, 'prysmaradite': False,
           'shields': True}
LABELS = {'en': 'Number of sets equipped < 2',
          'fr': 'Nombre de panoplies équipées < 2',
          'es': 'Número de sets equipados < 2',
          'pt': 'Número de conjuntos equipados < 2',
          'de': 'Anzahl der ausgerüsteten Sets < 2'}


def _pieces(structure, *set_ids):
    """{slot: item id} of every piece of the sets."""
    slots = {}
    for set_id in set_ids:
        for item_id in structure.get_set_by_id(set_id).items:
            item = structure.get_item_by_id(item_id)
            slot = structure.get_type_name_by_id(item.type).lower()
            if slot == 'ring':
                slot = 'ring2' if 'ring1' in slots else 'ring1'
            slots[slot] = item_id
    return slots


def _trophy(structure):
    return structure.get_item_by_ankama_id(MINOR_OBSTRUCTOR)


class TheCriteriaAreReadByTheirCodeTests(SimpleTestCase):

    def test_lowercase_pk_is_a_sets_equipped_cap_and_uppercase_a_set_bonus_cap(self):
        criteria = itemscraper_module('item_criteria')
        lower, upper = criteria.parse('pk<2'), criteria.parse('Pk<3')
        self.assertEqual(['Sets equipped < 2'], criteria.sets_equipped_caps(lower))
        self.assertEqual([], criteria.set_bonus_caps(lower))
        self.assertEqual(['Set bonus < 3'], criteria.set_bonus_caps(upper))
        self.assertEqual([], criteria.sets_equipped_caps(upper))

    def test_dofus3_and_the_beta_know_both_codes_dofus2_and_touch_only_their_own(self):
        criteria = itemscraper_module('item_criteria')
        for version in ('dofus3', 'beta'):
            with self.subTest(version=version):
                self.assertEqual(criteria.SETS_EQUIPPED,
                                 criteria.KINDS[version][('pk', '<')])
                self.assertEqual(criteria.SET_BONUS,
                                 criteria.KINDS[version][('Pk', '<')])
        for version in ('dofus2', 'touch'):
            with self.subTest(version=version):
                self.assertNotIn(('pk', '<'), criteria.KINDS[version])
                self.assertEqual(criteria.SET_BONUS,
                                 criteria.KINDS[version][('Pk', '<')])

    def test_each_version_reads_its_own_trophy_condition(self):
        expected = (('beta', MINOR_OBSTRUCTOR, 1, False),
                    ('dofus3', MINOR_OBSTRUCTOR, None, 2),
                    ('dofus2', MINOR_OBSTRUCTOR, None, 1),
                    ('touch', TOUCH_MINOR_BLOODTHIRST, None, 1))
        for version, ankama_id, sets_equipped, light_set in expected:
            with self.subTest(version=version):
                weird = get_structure(version).get_item_by_ankama_id(
                    ankama_id).weird_conditions
                self.assertEqual(sets_equipped, weird.get('sets_equipped'))
                self.assertEqual(light_set, weird['light_set'])

    def test_only_beta_trophies_carry_a_sets_equipped_condition(self):
        for version in ('dofus3', 'dofus2', 'touch', 'retro'):
            with self.subTest(version=version):
                self.assertEqual([], [
                    item.id for item in get_structure(version).get_items_list()
                    if item.weird_conditions.get('sets_equipped')])
        beta = [item for item in get_structure('beta').get_items_list()
                if item.weird_conditions.get('sets_equipped')]
        self.assertTrue(beta)
        self.assertEqual([], [item.id for item in beta if 'Trophy' not in item.flags])


class _Solves(SimpleTestCase):

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')

    def _solve(self, version, locked):
        set_current_game_version(version)
        base = {name: 0 for name, _key in STATS_NAMES}
        base.update({'AP': 7, 'MP': 3, 'Summon': 1, 'Prospecting': 100,
                     'Pods': 1000})
        model = Model()
        model.setup(ModelInput(200, base, {}, locked, [],
                               {'vit': 1, 'str': 3, 'ap': 400, 'mp': 300},
                               dict(OPTIONS), 'Iop', 995))
        model.run()
        return model


class TheBetaSolverCountsEquippedSetsTests(_Solves):

    def test_a_capped_trophy_and_the_full_crimson_dawn_relics_are_solved(self):
        structure = get_structure('beta')
        locked = dict(_pieces(structure, CRIMSON_DAWN),
                      dofus1=_trophy(structure).id)
        self.assertEqual(6, len(locked) - 1)
        model = self._solve('beta', locked)
        self.assertIn('ysets_1', model.problem.pulp_vars)
        self.assertEqual('Optimal', model.get_solved_status())
        worn = model.get_result_minimal().item_per_slot
        for slot, item_id in locked.items():
            with self.subTest(slot=slot):
                self.assertEqual(item_id, worn[slot])

    def test_a_capped_trophy_and_two_sets_of_two_pieces_are_refused(self):
        structure = get_structure('beta')
        locked = dict(_pieces(structure, KWISMAS, PINK),
                      dofus1=_trophy(structure).id)
        self.assertEqual(4, len(locked) - 1)
        self.assertEqual('Infeasible',
                         self._solve('beta', locked).get_solved_status())

    def test_a_capped_trophy_one_set_and_a_lone_piece_of_another_are_solved(self):
        structure = get_structure('beta')
        locked = dict(_pieces(structure, KWISMAS),
                      belt=_pieces(structure, PINK)['belt'],
                      dofus1=_trophy(structure).id)
        model = self._solve('beta', locked)
        self.assertEqual('Optimal', model.get_solved_status())
        worn = model.get_result_minimal().item_per_slot
        for slot, item_id in locked.items():
            with self.subTest(slot=slot):
                self.assertEqual(item_id, worn[slot])

    def test_the_same_two_sets_without_the_trophy_are_solved(self):
        structure = get_structure('beta')
        locked = _pieces(structure, KWISMAS, PINK)
        self.assertEqual('Optimal',
                         self._solve('beta', locked).get_solved_status())


class TheDofus3SolverStillCountsSetBonusesTests(_Solves):

    def test_a_capped_trophy_and_two_sets_of_two_pieces_are_solved(self):
        structure = get_structure('dofus3')
        locked = dict(_pieces(structure, KWISMAS, PINK),
                      dofus1=_trophy(structure).id)
        model = self._solve('dofus3', locked)
        self.assertNotIn('ysets_1', model.problem.pulp_vars)
        self.assertEqual('Optimal', model.get_solved_status())

    def test_a_capped_trophy_and_four_pieces_of_one_set_are_refused(self):
        structure = get_structure('dofus3')
        crimson = _pieces(structure, CRIMSON_DAWN)
        locked = {slot: crimson[slot] for slot in ('ring1', 'ring2', 'amulet', 'hat')}
        locked['dofus1'] = _trophy(structure).id
        self.assertEqual('Infeasible',
                         self._solve('dofus3', locked).get_solved_status())


class _StoredBuilds(TestCase):

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.addCleanup(set_current_game_version, 'dofus3')
        self.owner = User.objects.create_user('trophy', 'trophy@test.local',
                                              'pw-42-solid')
        self.client.force_login(self.owner)

    def _char(self, version, *set_ids):
        return self._char_wearing(version, _pieces(get_structure(version), *set_ids))

    def _char_wearing(self, version, slots):
        set_current_game_version(version)
        worn = [_trophy(get_structure(version)).id] + list(slots.values())
        model_input = {'char_class': 'Iop', 'char_level': 200,
                       'origin': 'generated', 'options': dict(OPTIONS),
                       'base_stats_by_attr': {name: 0 for name, _key in STATS_NAMES},
                       'locked_equips': {}}
        minimal = ModelResultMinimal.from_item_id_list(worn, model_input, {})
        return Char.objects.create(
            name='Trophy', char_name='', char_class='Iop', char_build='',
            level=200, minimum_stats=b'', minimum_crits=b'',
            stats_weight=pickle.dumps({}), options=pickle.dumps(dict(OPTIONS)),
            inclusions=b'', exclusions=b'', owner=self.owner, link_shared=False,
            game_version=version, minimal_solution=pickle.dumps(minimal))

    def _page(self, url, language='en'):
        self.client.cookies['django_language'] = language
        page = self.client.get(url, follow=True)
        self.assertEqual(200, page.status_code)
        return html.unescape(page.content.decode('utf-8'))


class TheResultCheckReadsTheRuleTests(_StoredBuilds):

    def _trophy_violations(self, version, *set_ids):
        char = self._char(version, *set_ids)
        set_current_game_version(version)
        solution = get_solution(char)
        trophy = next(item for item in solution.item_list
                      if getattr(item, 'item_added', False)
                      and item.id == _trophy(get_structure(version)).id)
        return [violation.stat_name
                for violation in solution.get_violations_on_item(trophy)]

    def test_one_full_set_is_no_violation(self):
        self.assertEqual([], self._trophy_violations('beta', CRIMSON_DAWN))

    def test_two_sets_of_two_pieces_violate_the_beta_trophy(self):
        self.assertEqual(['Number of sets equipped < 2'],
                         self._trophy_violations('beta', KWISMAS, PINK))

    def test_the_same_two_sets_do_not_violate_the_dofus3_trophy(self):
        self.assertEqual([], self._trophy_violations('dofus3', KWISMAS, PINK))

    def test_one_set_and_a_lone_piece_of_another_is_no_violation(self):
        structure = get_structure('beta')
        char = self._char_wearing('beta', dict(
            _pieces(structure, KWISMAS), belt=_pieces(structure, PINK)['belt']))
        set_current_game_version('beta')
        solution = get_solution(char)
        trophy = next(item for item in solution.item_list
                      if getattr(item, 'item_added', False)
                      and item.id == _trophy(structure).id)
        self.assertEqual([], solution.get_violations_on_item(trophy))


class TheWholeBuildCheckReadsTheRuleTests(_StoredBuilds):

    def _labels_after_adding_the_pink_slippers(self, version):
        structure = get_structure(version)
        pink = _pieces(structure, PINK)
        char = self._char_wearing(version, dict(_pieces(structure, KWISMAS),
                                                belt=pink['belt']))
        set_current_game_version(version)
        before = get_solution(char).get_all_project_violations(
            structure.get_type_id_by_name('Dofus'), {})
        after = check_if_violates(structure.get_item_by_id(pink['boots']),
                                  'boots', char)
        return ([violation.stat_name for violation in before],
                [violation.stat_name for violation in after])

    def test_a_second_set_swapped_into_a_beta_build_breaks_the_trophy(self):
        before, after = self._labels_after_adding_the_pink_slippers('beta')
        self.assertNotIn(LABELS['en'], before)
        self.assertIn(LABELS['en'], after)

    def test_the_same_swap_keeps_the_dofus3_trophy(self):
        before, after = self._labels_after_adding_the_pink_slippers('dofus3')
        for labels in (before, after):
            self.assertNotIn(LABELS['en'], labels)
            self.assertNotIn('Set bonus < 3', labels)


class ThePagesPrintTheGameLabelTests(_StoredBuilds):

    def test_the_label_is_the_game_s_own_in_every_language(self):
        for language, label in LABELS.items():
            with self.subTest(language=language), translation.override(language):
                self.assertEqual(label, sets_equipped_text(1))

    def test_the_beta_item_page_prints_the_new_line_in_every_language(self):
        self.client.logout()
        structure = get_structure('beta')
        trophy = _trophy(structure)
        for language, label in LABELS.items():
            with self.subTest(language=language), translation.override(language):
                url = get_item_link(trophy.ankama_type, trophy.ankama_id,
                                    structure.get_item_name_in_language(trophy, language),
                                    'beta')
                page = self._page(url, language)
                self.assertIn(label, page)

    def test_the_dofus3_item_page_keeps_the_set_bonus_line(self):
        page = self._page('/encyclopedia/item/equipment/%d-x/' % MINOR_OBSTRUCTOR)
        self.assertIn('Set bonus < 3', page)
        self.assertNotIn(LABELS['en'], page)

    def test_the_beta_solution_page_prints_the_new_line(self):
        page = self._page('/beta/solution/%d/' % self._char('beta', CRIMSON_DAWN).id)
        self.assertIn(LABELS['en'], page)
        self.assertNotIn('Set bonus <', page)

    def test_the_dofus3_solution_page_keeps_the_set_bonus_line(self):
        page = self._page('/solution/%d/' % self._char('dofus3', CRIMSON_DAWN).id)
        self.assertIn('Set bonus < 3', page)
        self.assertNotIn(LABELS['en'], page)
