# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The crit curve is read on the first set wearing the weapon the weapon terms rank first."""
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from chardata.crit_curve import _set_view, anchor_solution, crit_hinges, read_curve, top_weapon
from chardata.weapon_terms import stat_lines_value
from fashionistapulp.dofus_constants import STAT_KEY_TO_NAME, STATS_NAMES
from fashionistapulp.modelresult import ModelResultMinimal, model_result_from_minimal

MINOTOT_SCEPTRE = 8275
DREGGON_DAGGERS = 8414
SRAMBAD_DAGGERS = 15493
CHAOTIC_SCYTHE = 26011

OWN = {'str': 900, 'int': 700, 'pow': 250, 'ch': 30, 'cridam': 40, 'ap': 12}
WEIGHTS = {'str': 120, 'int': 110, 'cha': 0, 'agi': 30, 'ch': 240, 'cridam': 100}
CHAR = SimpleNamespace(id=1, game_version='dofus3', char_class='Iop', level=200)


def _minimal(weapon_id):
    base = {name: 0 for name, _key in STATS_NAMES}
    base.update({STAT_KEY_TO_NAME[key]: value for key, value in OWN.items()})
    given = {'options': {'ap_exo': False, 'mp_exo': False, 'range_exo': False},
             'base_stats_by_attr': base, 'char_level': 200, 'origin': 'generated'}
    return ModelResultMinimal({'weapon': weapon_id}, given, {})


def _solution(weapon_id):
    return model_result_from_minimal(_minimal(weapon_id))


def _input(**values):
    given = {'objective_values': dict(WEIGHTS), 'forbidden_equips': set(), 'locked_equips': {},
             'empty_slot_types': []}
    given.update(values)
    return SimpleNamespace(**given)


def _structure():
    from fashionistapulp.structure import get_structure
    return get_structure('dofus3')


def _lines(item_id):
    return stat_lines_value(_structure().get_item_by_id(item_id), WEIGHTS, _structure())


def _slopes(reading):
    return None if reading is None else (reading.ch, reading.hinges)


class _DofusThree(SimpleTestCase):

    def setUp(self):
        from fashionistapulp.structure import set_current_game_version
        set_current_game_version('dofus3')
        self.addCleanup(set_current_game_version, 'dofus3')

    def read(self, terms, worn=MINOTOT_SCEPTRE, model_input=None):
        """(the slopes of the reading, the weapons of the sets the reading asked for)."""
        built = []

        def solution_from(char, minimal, refresh_base_stats=True):
            built.append(minimal.item_per_slot.get('weapon'))
            return model_result_from_minimal(minimal)

        with mock.patch('chardata.crit_curve.get_char_aspects', return_value={'str'}), \
                mock.patch('chardata.crit_curve.get_standard_weights', return_value=dict(WEIGHTS)), \
                mock.patch('chardata.crit_curve.get_stats_weights', return_value=dict(WEIGHTS)), \
                mock.patch('chardata.solution.get_solution_from_minimal', side_effect=solution_from):
            return _slopes(crit_hinges(CHAR, _minimal(worn), model_input or _input(), terms)), built


class TheTermsRankTheWeaponsTests(_DofusThree):

    def terms_where_the_daggers_trail_by(self, gap):
        return {MINOTOT_SCEPTRE: 100.0,
                DREGGON_DAGGERS: 100.0 + _lines(MINOTOT_SCEPTRE) - _lines(DREGGON_DAGGERS) - gap}

    def test_a_weapon_is_ranked_by_its_term_and_the_value_of_its_stat_lines(self):
        self.assertNotEqual(_lines(MINOTOT_SCEPTRE), _lines(DREGGON_DAGGERS))
        self.assertEqual(MINOTOT_SCEPTRE, top_weapon(self.terms_where_the_daggers_trail_by(1), _input(),
                                                     'dofus3'))
        self.assertEqual(DREGGON_DAGGERS, top_weapon(self.terms_where_the_daggers_trail_by(-1), _input(),
                                                     'dofus3'))

    def test_the_first_of_equal_values_wins(self):
        terms = self.terms_where_the_daggers_trail_by(0)
        self.assertEqual(MINOTOT_SCEPTRE, top_weapon(terms, _input(), 'dofus3'))
        self.assertEqual(DREGGON_DAGGERS, top_weapon(dict(reversed(list(terms.items()))), _input(),
                                                     'dofus3'))

    def test_a_forbidden_weapon_is_never_the_top(self):
        terms = self.terms_where_the_daggers_trail_by(-1000)
        self.assertEqual(MINOTOT_SCEPTRE, top_weapon(terms, _input(forbidden_equips={DREGGON_DAGGERS}),
                                                     'dofus3'))
        self.assertIsNone(top_weapon(terms, _input(forbidden_equips=set(terms)), 'dofus3'))

    def test_without_terms_no_weapon_is_on_top(self):
        self.assertIsNone(top_weapon({}, _input(), 'dofus3'))


class TheCurveIsReadOnTheTopWeaponTests(_DofusThree):

    TERMS = {CHAOTIC_SCYTHE: 100000.0, MINOTOT_SCEPTRE: 1.0}

    def expected_on(self, weapon_id):
        """The curve called on the first set with `weapon_id` swapped in, at the critical damage of the first set."""
        first = _set_view(CHAR, _solution(MINOTOT_SCEPTRE))
        return _slopes(read_curve(_set_view(CHAR, _solution(weapon_id)), WEIGHTS, first, priced=False))

    def test_the_slope_is_the_one_read_by_calling_the_curve_on_the_swapped_set(self):
        reading, built = self.read(self.TERMS)
        self.assertEqual([MINOTOT_SCEPTRE, CHAOTIC_SCYTHE], built)
        self.assertEqual(self.expected_on(CHAOTIC_SCYTHE), reading)

    def test_the_swap_moves_the_curve(self):
        reading, _built = self.read(self.TERMS)
        worn, _built = self.read({})
        self.assertEqual(self.expected_on(MINOTOT_SCEPTRE), worn)
        self.assertNotEqual(worn, reading)

    def test_the_turn_is_read_at_the_critical_damage_of_the_first_set(self):
        swapped = _solution(CHAOTIC_SCYTHE).get_stats_total()['cridam']
        first = _solution(MINOTOT_SCEPTRE).get_stats_total()['cridam']
        self.assertNotEqual(first, swapped)
        view = _set_view(CHAR, _solution(CHAOTIC_SCYTHE))
        at_first = _slopes(read_curve(view, WEIGHTS, _set_view(CHAR, _solution(MINOTOT_SCEPTRE)), priced=False))
        self.assertNotEqual(at_first, _slopes(read_curve(view, WEIGHTS, priced=False)))
        self.assertEqual(at_first, self.read(self.TERMS)[0])

    def test_the_first_set_stays_when_it_already_wears_the_top_weapon(self):
        reading, built = self.read({MINOTOT_SCEPTRE: 100000.0, CHAOTIC_SCYTHE: 1.0})
        self.assertEqual([MINOTOT_SCEPTRE], built)
        self.assertEqual(self.expected_on(MINOTOT_SCEPTRE), reading)

    def test_without_terms_the_first_set_is_read_as_it_is(self):
        for terms in (None, {}):
            with self.subTest(terms=terms):
                reading, built = self.read(terms)
                self.assertEqual([MINOTOT_SCEPTRE], built)
                self.assertEqual(self.expected_on(MINOTOT_SCEPTRE), reading)

    def test_a_locked_weapon_is_not_swapped(self):
        reading, built = self.read(self.TERMS, model_input=_input(
            locked_equips={'weapon': MINOTOT_SCEPTRE}))
        self.assertEqual([MINOTOT_SCEPTRE], built)
        self.assertEqual(self.expected_on(MINOTOT_SCEPTRE), reading)

    def test_an_emptied_weapon_slot_is_not_swapped(self):
        reading, built = self.read(self.TERMS, model_input=_input(empty_slot_types=['weapon']))
        self.assertEqual([MINOTOT_SCEPTRE], built)
        self.assertEqual(self.expected_on(MINOTOT_SCEPTRE), reading)

    def test_a_forbidden_weapon_is_not_the_anchor_and_the_next_one_is(self):
        terms = {CHAOTIC_SCYTHE: 100000.0, SRAMBAD_DAGGERS: 50000.0, MINOTOT_SCEPTRE: 1.0}
        reading, built = self.read(terms, model_input=_input(forbidden_equips={CHAOTIC_SCYTHE}))
        self.assertEqual([MINOTOT_SCEPTRE, SRAMBAD_DAGGERS], built)
        self.assertEqual(self.expected_on(SRAMBAD_DAGGERS), reading)

    def test_only_forbidden_weapons_leave_the_first_set_as_it_is(self):
        reading, built = self.read(self.TERMS, model_input=_input(forbidden_equips={CHAOTIC_SCYTHE}))
        self.assertEqual([MINOTOT_SCEPTRE], built)
        self.assertEqual(self.expected_on(MINOTOT_SCEPTRE), reading)

    def test_the_stored_set_is_left_alone(self):
        result = _minimal(MINOTOT_SCEPTRE)
        solution = _solution(MINOTOT_SCEPTRE)
        with mock.patch('chardata.solution.get_solution_from_minimal',
                        side_effect=lambda char, minimal, refresh_base_stats=True:
                        model_result_from_minimal(minimal)):
            swapped = anchor_solution(CHAR, result, solution, self.TERMS, _input())
        self.assertIsNot(solution, swapped)
        self.assertEqual(MINOTOT_SCEPTRE, result.item_per_slot['weapon'])
        self.assertEqual(CHAOTIC_SCYTHE, swapped.items['Weapon'][0].id)

    def test_a_swapped_set_that_cannot_be_built_leaves_the_first_set(self):
        result = _minimal(MINOTOT_SCEPTRE)
        solution = _solution(MINOTOT_SCEPTRE)
        with mock.patch('chardata.solution.get_solution_from_minimal', side_effect=ValueError), \
                self.assertLogs('chardata.crit_curve', 'ERROR'):
            self.assertIs(solution, anchor_solution(CHAR, result, solution, self.TERMS, _input()))
