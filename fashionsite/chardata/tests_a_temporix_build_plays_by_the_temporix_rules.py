# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A TemporiX build follows the TemporiX server rules."""
from django.test import SimpleTestCase

from fashionistapulp import temporix
from fashionistapulp.dofus_constants import get_stat_maximum
from fashionistapulp.model import Model, ModelInput
from fashionistapulp.modelresult import ModelResult
from fashionistapulp.structure import get_structure, set_current_game_version

_BASE = {'Vitality': 0, 'Wisdom': 0, 'Strength': 0, 'Intelligence': 0,
         'Chance': 0, 'Agility': 0}
_POIDS = {'vit': 1, 'wis': 1, 'str': 1, 'int': 1, 'cha': 1, 'agi': 1,
          'pow': 1, 'ap': 100, 'mp': 100, 'range': 10, 'summon': 1}
_OPTIONS = {'ap_exo': False, 'mp_exo': False, 'range_exo': False,
            'dofus': True, 'trophies': True, 'dragoturkey': True,
            'seemyool': True, 'rhineetle': True, 'prysmaradite': False,
            'dofuses': {}, 'dofusnotforchar': set()}
_TEMPORIX_OPTIONS = dict(_OPTIONS, temporix=temporix.RULE_VERSION)

_VULBIS = 6980
_GELANO_SANS_EXO = 'Gelano (#2)'


def _stat_of(structure, item, stat_name):
    stat_id = structure.get_stat_by_name(stat_name).id
    return sum(value for sid, value in item.stats if sid == stat_id)


class _Touch(SimpleTestCase):

    def setUp(self):
        # Thread local, and setUpClass runs in another thread
        set_current_game_version('touch')
        self.structure = get_structure('touch')

    def tearDown(self):
        set_current_game_version('dofus3')


class TheShinyRuleIsAnkamasTests(_Touch):

    def test_one_and_a_half_times_rounded_up_maluses_included(self):
        self.assertEqual(2, temporix.shiny_value(1))
        self.assertEqual(11, temporix.shiny_value(7))
        self.assertEqual(90, temporix.shiny_value(60))
        self.assertEqual(-30, temporix.shiny_value(-20))
        self.assertEqual(-8, temporix.shiny_value(-5))
        self.assertEqual(0, temporix.shiny_value(0))

    def test_the_devblog_examples_on_the_real_catalogue(self):
        shiny = temporix.shiny_items_by_id(self.structure)
        vulbis = self.structure.get_item_by_ankama_id(_VULBIS)
        gelano = self.structure.get_item_by_name(_GELANO_SANS_EXO)
        self.assertEqual(1, _stat_of(self.structure, vulbis, 'MP'))
        self.assertEqual(2, _stat_of(self.structure, shiny[vulbis.id], 'MP'))
        self.assertEqual(1, _stat_of(self.structure, gelano, 'AP'))
        self.assertEqual(2, _stat_of(self.structure, shiny[gelano.id], 'AP'))

    def test_what_ankama_never_drops_shiny_stays_as_it_is(self):
        shiny = temporix.shiny_items_by_id(self.structure)
        s = self.structure
        by_type = {}
        for item in s.get_items_list():
            by_type.setdefault(s.get_type_name_by_id(item.type), item)
        for type_name in ('Weapon', 'Shield', 'Pet'):
            with self.subTest(type=type_name):
                self.assertNotIn(by_type[type_name].id, shiny)
        trophy = next(i for i in s.get_items_list() if 'Trophy' in i.flags)
        self.assertNotIn(trophy.id, shiny)
        ivory = s.get_item_by_ankama_id(23851)
        self.assertIn('Linked to the character', ivory.flags)
        self.assertNotIn(ivory.id, shiny)
        exo_gelano = s.get_item_by_name('Gelano (#1)')
        if exo_gelano is not None:
            self.assertNotIn(exo_gelano.id, shiny)

    def test_the_catalogue_rows_are_left_alone(self):
        vulbis = self.structure.get_item_by_ankama_id(_VULBIS)
        before = list(vulbis.stats)
        copy = temporix.shiny_items_by_id(self.structure)[vulbis.id]
        self.assertIsNot(vulbis, copy)
        self.assertEqual(before, list(vulbis.stats))
        self.assertIs(vulbis,
                      self.structure.get_item_by_ankama_id(_VULBIS))


class TheTemporixOnlyPiecesTests(_Touch):

    def test_they_are_the_three_named_and_only_on_touch(self):
        ids = temporix.temporix_only_item_ids(self.structure)
        self.assertEqual(set(temporix.TEMPORIX_ONLY_ANKAMA_IDS.values()),
                         {self.structure.get_item_by_id(i).name for i in ids})
        self.assertEqual(set(), temporix.temporix_only_item_ids(
            get_structure('dofus3')))

    def test_the_shield_of_infinity_is_read_at_rank_1000(self):
        shield = self.structure.get_item_by_ankama_id(23841)
        self.assertEqual(7500, _stat_of(self.structure, shield, 'Vitality'))
        self.assertEqual(2000, _stat_of(self.structure, shield, 'Power'))
        self.assertEqual(200, _stat_of(self.structure, shield, 'Prospecting'))


class TheCapsTests(SimpleTestCase):

    def test_temporix_drops_ap_mp_range_and_summons_and_keeps_resists(self):
        classic = get_stat_maximum('touch')
        uncapped = get_stat_maximum('touch', temporix=True)
        for stat_name in ('AP', 'MP', 'Range', 'Summon'):
            with self.subTest(stat=stat_name):
                self.assertIn(stat_name, classic)
                self.assertNotIn(stat_name, uncapped)
        for resist in ('% Neutral Resist', '% Air Resist', '% Fire Resist',
                       '% Water Resist', '% Earth Resist'):
            self.assertEqual(classic[resist], uncapped[resist])

    def test_the_switch_means_nothing_off_touch(self):
        self.assertTrue(temporix.is_on({'temporix': 1}, 'touch'))
        self.assertFalse(temporix.is_on({'temporix': 1}, 'dofus3'))
        self.assertFalse(temporix.is_on({'temporix': False}, 'touch'))
        self.assertFalse(temporix.is_on(None, 'touch'))


class TheSolverOffersEachBuildItsOwnPiecesTests(_Touch):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        set_current_game_version('touch')
        cls.classic = Model()
        cls.temporix = Model(temporix=True)
        set_current_game_version('dofus3')

    def _entree(self, options):
        return ModelInput(200, dict(_BASE), {}, {}, set(), dict(_POIDS),
                          dict(options), 'Iop', 0)

    def test_a_classic_build_is_never_offered_the_temporix_pieces(self):
        self.classic.setup(self._entree(_OPTIONS))
        classic = self.classic.get_candidate_pool()
        self.temporix.setup(self._entree(_TEMPORIX_OPTIONS))
        offered = self.temporix.get_candidate_pool()
        # The Shield of Infinity; The Real Ivory Dofus and the Cocoa Dofus.
        self.assertEqual(1, offered['Shield'] - classic['Shield'])
        self.assertEqual(2, offered['Dofus'] - classic['Dofus'])

    def test_the_temporix_model_reads_shiny_values_and_no_ap_cap(self):
        vulbis_id = self.structure.get_item_by_ankama_id(_VULBIS).id
        worn = {item.id: item for item in self.temporix.items_list}
        plain = {item.id: item for item in self.classic.items_list}
        self.assertEqual(2, _stat_of(self.structure, worn[vulbis_id], 'MP'))
        self.assertEqual(1, _stat_of(self.structure, plain[vulbis_id], 'MP'))
        self.assertNotIn('AP', self.temporix.stat_maximum)
        self.assertIn('AP', self.classic.stat_maximum)


class ThePageShowsWhatTheSolverCountedTests(_Touch):

    def _result(self, options):
        return ModelResult({'options': dict(options),
                            'base_stats_by_attr': dict(_BASE),
                            'char_level': 200})

    def test_a_temporix_result_wears_the_piece_shiny(self):
        vulbis = self.structure.get_item_by_ankama_id(_VULBIS)
        shiny = self._result(_TEMPORIX_OPTIONS)
        shiny.add_item_at_slot(vulbis, 'dofus1')
        plain = self._result(_OPTIONS)
        plain.add_item_at_slot(vulbis, 'dofus1')
        self.assertEqual(2, shiny.item_list[0].stats['mp'])
        self.assertEqual(1, plain.item_list[0].stats['mp'])

    def test_a_recorded_roll_is_a_forgemaged_piece_and_stays_as_recorded(self):
        vulbis = self.structure.get_item_by_ankama_id(_VULBIS)
        mp = self.structure.get_stat_by_name('MP').id
        result = self._result(_TEMPORIX_OPTIONS)
        result.add_item_at_slot(vulbis, 'dofus1', {vulbis.id: {mp: 1}})
        self.assertEqual(1, result.item_list[0].stats['mp'])

    def test_a_shiny_piece_carries_the_mark_the_game_draws_as_a_golden_slot(self):
        vulbis = self.structure.get_item_by_ankama_id(_VULBIS)
        shiny = self._result(_TEMPORIX_OPTIONS)
        shiny.add_item_at_slot(vulbis, 'dofus1')
        plain = self._result(_OPTIONS)
        plain.add_item_at_slot(vulbis, 'dofus1')
        self.assertTrue(shiny.item_list[0].shiny)
        self.assertEqual(plain.item_list[0].name, shiny.item_list[0].name)
        self.assertFalse(plain.item_list[0].shiny)

    def test_a_piece_with_recorded_rolls_is_not_marked_shiny(self):
        vulbis = self.structure.get_item_by_ankama_id(_VULBIS)
        mp = self.structure.get_stat_by_name('MP').id
        result = self._result(_TEMPORIX_OPTIONS)
        result.add_item_at_slot(vulbis, 'dofus1', {vulbis.id: {mp: 1}})
        self.assertFalse(result.item_list[0].shiny)

    def test_another_pieces_record_leaves_this_one_shiny(self):
        vulbis = self.structure.get_item_by_ankama_id(_VULBIS)
        mp = self.structure.get_stat_by_name('MP').id
        result = self._result(_TEMPORIX_OPTIONS)
        result.add_item_at_slot(vulbis, 'dofus1', {vulbis.id + 1: {mp: 1}})
        self.assertEqual(2, result.item_list[0].stats['mp'])


class TheReviewOfTheModeTests(_Touch):

    def test_only_a_piece_some_monster_drops_can_be_shiny(self):
        shiny = temporix.shiny_items_by_id(self.structure)
        dropped = temporix.droppable_item_ids(self.structure)
        never_dropped = [item.id for item in self.structure.get_items_list()
                         if item.id not in dropped
                         and self.structure.get_type_name_by_id(item.type) in temporix.SHINY_TYPES]
        self.assertGreater(len(never_dropped), 100)
        self.assertEqual([], [item_id for item_id in never_dropped if item_id in shiny])
        vulbis = self.structure.get_item_by_ankama_id(_VULBIS)
        self.assertIn(vulbis.id, dropped)
        self.assertIn(vulbis.id, shiny)
        self.assertTrue(set(shiny) <= dropped)

    def test_a_classic_touch_solve_gets_a_key_of_its_own(self):
        from chardata.fashion_action import temporix_model_option
        self.assertEqual({}, temporix_model_option({'temporix': True}, 'dofus3'))
        self.assertEqual({'temporix': False},
                         temporix_model_option({}, 'touch'))
        self.assertEqual({'temporix': temporix.RULE_VERSION},
                         temporix_model_option({'temporix': True}, 'touch'))

    def test_the_picker_hides_the_temporix_pieces_from_a_classic_build(self):
        from chardata.item_exchange import _without_temporix_only
        shield = self.structure.get_item_by_ankama_id(23841)
        other = next(i for i in self.structure.get_items_list()
                     if self.structure.get_type_name_by_id(i.type) == 'Shield'
                     and i.id != shield.id)

        class _Char:
            game_version = 'touch'

        classic, solved_temporix = _Char(), _Char()
        classic._picker_temporix = False
        solved_temporix._picker_temporix = True
        self.assertEqual([other], _without_temporix_only(
            classic, self.structure, [shield, other]))
        self.assertEqual([shield, other], _without_temporix_only(
            solved_temporix, self.structure, [shield, other]))


class APieceThePlayerLockedIsNotBannedTests(_Touch):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        set_current_game_version('touch')
        cls.model = Model()
        set_current_game_version('dofus3')

    def _rhs(self, item_id):
        return -self.model.restrictions.forbidden_items_constraints[
            item_id].constant

    def test_the_lock_wins_over_the_ban(self):
        ivory = self.structure.get_item_by_ankama_id(23851)
        self.model.setup(ModelInput(200, dict(_BASE), {}, {}, set(),
                                    dict(_POIDS), dict(_OPTIONS), 'Iop', 0))
        self.assertEqual(0, self._rhs(ivory.id))
        self.model.setup(ModelInput(200, dict(_BASE), {},
                                    {'dofus1': ivory.id}, set(),
                                    dict(_POIDS), dict(_OPTIONS), 'Iop', 0))
        self.assertEqual(1, self._rhs(ivory.id))
