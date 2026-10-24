import collections
import sys
from pathlib import Path
from unittest import TestCase

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'itemscraper'))

import generate_wakfu_special_items as generator  # noqa: E402

try:
    from fashionistapulp import wakfu_special_items as block
except ImportError:
    block = None

FAMILIES = 'ABCDEFGHIJ'
KINDS = ('normal', 'relic', 'epic', 'gear', 'passives')
TOTALS = {'normal': 157, 'relic': 47, 'epic': 32, 'gear': 54, 'passives': 339}
# States of each kind by family, as the generator counted them on game 1.93.1
FAMILY_COUNTS = {
    'normal': dict(A=18, B=1, C=0, D=0, E=60, F=9, G=9, H=12, I=13, J=35),
    'relic': dict(A=2, B=0, C=0, D=0, E=16, F=3, G=9, H=5, I=5, J=7),
    'epic': dict(A=3, B=14, C=3, D=0, E=7, F=0, G=0, H=1, I=0, J=4),
    'gear': dict(A=0, B=0, C=0, D=0, E=11, F=6, G=5, H=6, I=1, J=25),
    'passives': dict(A=27, B=0, C=2, D=0, E=74, F=5, G=10, H=27, I=24, J=170)}
EPIC_B = [5073, 5074, 5075, 5076, 6706, 6707, 7255, 7256, 7876, 7880, 7881, 8384, 8385,
          9074]
EPIC_C = [5077, 5449, 7882]

CHARACTERISTICS = {'CRITICAL_BONUS': 52, 'DMG_FIRE_PERCENT': 21}
ACTIONS = {'122': '[#charac DMG_FIRE_PERCENT] [#1]% fire damage', '330': 'group'}
START = [[], [], [], [], [], [1028], []]
NO_TRIGGER = [[]] * 7


def effect(ident, action, params=(), criterion='', triggers=NO_TRIGGER, levels=(0, 32767)):
    return {'id': ident, 'action_id': action, 'params': list(params),
            'criterion': criterion, 'triggers': triggers, 'min_level': levels[0],
            'max_level': levels[1]}


def invented():
    """Six invented states: one of each family the solver reads, and three it does not."""
    conversion = [0] * 12 + [52]
    shaped = [0] * 12 + [52, 0, 0, 0, 0, -8, 0, 2]
    effects = [
        effect(10, 330, triggers=START), effect(11, 122, [5, 0]),
        effect(20, 330, criterion='GetLevel("caster") >= 100', triggers=START),
        effect(21, 122, [5, 0]),
        effect(30, 330, triggers=START), effect(31, 913, conversion), effect(32, 122, [0, 1]),
        effect(40, 999, triggers=START),
        effect(50, 330, criterion='GetLevel("caster") >= 1 and False', triggers=START),
        effect(51, 122, [5, 0]),
        effect(60, 1093, triggers=START),
        effect(70, 330, criterion='False', triggers=START), effect(71, 122, [5, 0]),
        effect(80, 330, triggers=START), effect(81, 122, [5, 0], levels=(2, 2)),
        effect(90, 330, triggers=START), effect(91, 913, shaped), effect(92, 122, [0, 1]),
        effect(100, 330, criterion='GetCharac("FEROCITY", "target") <= 0', triggers=START),
        effect(101, 122, [5, 0]),
    ]
    groups = [{'id': 10, 'effect_ids': [11]}, {'id': 20, 'effect_ids': [21]},
              {'id': 30, 'effect_ids': [31]}, {'id': 31, 'effect_ids': [32]},
              {'id': 50, 'effect_ids': [51]}, {'id': 70, 'effect_ids': [71]},
              {'id': 80, 'effect_ids': [81]}, {'id': 90, 'effect_ids': [91]},
              {'id': 91, 'effect_ids': [92]}, {'id': 100, 'effect_ids': [101]}]
    states = [{'id': ident, 'bcw': '', 'effect_ids': [root], 'max_level': 0}
              for ident, root in ((1, 10), (2, 20), (3, 30), (4, 40), (5, 50), (6, 60),
                           (7, 70), (8, 80), (9, 90), (10, 100))]
    texts = {'texts': {'state_names': {'en': {}}, 'state_descriptions': {'en': {}},
                       'spell_names': {'en': {}}, 'effect_texts': {'en': {}},
                       'action_texts': {'en': ACTIONS}}}
    tables = {'effects': effects, 'groups': groups, 'states': states, 'spells': []}
    return generator.Tables(tables, texts, {'characteristics': CHARACTERISTICS})


class TheInventedStatesFallIntoTheirFamiliesTests(TestCase):
    def family(self, tables, state):
        entry, _leaves = tables.entry(tables.states[state]['effect_ids'], {state})
        return entry['family']

    def test_each_invented_state_lands_in_the_family_its_effects_decide(self):
        tables = invented()
        self.assertEqual(
            {1: 'A', 2: 'B', 3: 'C', 4: 'E', 5: 'J', 6: 'J'},
            {state: self.family(tables, state) for state in range(1, 7)})

    def test_a_fixed_stat_is_a_line_the_solver_counts(self):
        tables = invented()
        entry, _leaves = tables.entry(tables.states[1]['effect_ids'], {1})
        self.assertEqual([('A', 'dmg_fire_percent', 5, 0, ())], entry['lines'])

    def test_a_criterion_about_the_build_becomes_a_guard_on_the_line(self):
        tables = invented()
        entry, _leaves = tables.entry(tables.states[2]['effect_ids'], {2})
        self.assertEqual([('B', 'dmg_fire_percent', 5, 0, (0,))], entry['lines'])
        self.assertEqual([('GetLevel', None, '>=', 100)], entry['conditions'])

    def test_a_conversion_names_its_source_and_target(self):
        tables = invented()
        entry, _leaves = tables.entry(tables.states[3]['effect_ids'], {3})
        self.assertEqual([('critical_bonus', 'dmg_fire_percent', 0, 1, 1, ())],
                         entry['conversions'])

    def test_a_branch_ending_in_false_counts_nothing(self):
        tables = invented()
        entry, leaves = tables.entry(tables.states[5]['effect_ids'], {5})
        self.assertEqual(([], []), (leaves, entry['lines']))

    def test_a_group_whose_own_criterion_is_false_drops_its_children(self):
        tables = invented()
        entry, leaves = tables.entry(tables.states[7]['effect_ids'], {7})
        self.assertEqual(([], [], 'J'), (leaves, entry['lines'], entry['family']))

    def test_an_effect_that_holds_for_some_levels_only_is_not_counted(self):
        tables = invented()
        entry, _leaves = tables.entry(tables.states[8]['effect_ids'], {8})
        self.assertEqual(([], 'E'), (entry['lines'], entry['family']))
        self.assertIn('levels 2 to 2', entry['uncounted'][0][2])

    def test_a_conversion_with_an_offset_and_a_factor_is_not_counted(self):
        tables = invented()
        entry, _leaves = tables.entry(tables.states[9]['effect_ids'], {9})
        self.assertEqual(([], [], 'E'),
                         (entry['lines'], entry['conversions'], entry['family']))

    def test_a_stat_test_on_the_target_of_a_start_of_combat_effect_is_about_the_build(self):
        tables = invented()
        entry, _leaves = tables.entry(tables.states[10]['effect_ids'], {10})
        self.assertEqual([('B', 'dmg_fire_percent', 5, 0, (0,))], entry['lines'])

    def test_a_subtree_the_client_recomputes_is_listed_and_not_counted(self):
        tables = invented()
        entry, _leaves = tables.entry(tables.states[4]['effect_ids'], {4})
        self.assertEqual(([], 999), (entry['lines'], entry['uncounted'][0][1]))


class TheLiveWakfuSpecialItemsBlockGivesEveryLineAFamilyTests(TestCase):
    """Guards on the generated block, skipped where it is not written."""

    def setUp(self):
        if block is None:
            self.skipTest('no wakfu_special_items.py; run '
                          'itemscraper/generate_wakfu_special_items.py')

    def entries(self, kind):
        if kind == 'passives':
            return list(block.PASSIVES.values())
        return [entry for state, entry in block.STATES.items()
                if state in self.states_of(kind)]

    def states_of(self, kind):
        if kind == 'gear':
            return {state for pairs in block.GEAR_STATES.values() for state, _ in pairs}
        return {state for state, _level, found, _pattern in block.SUBLIMATIONS.values()
                if found == kind}

    def test_each_kind_holds_the_states_the_game_has(self):
        self.assertEqual(TOTALS, {kind: len(self.entries(kind)) for kind in KINDS})
        self.assertEqual(TOTALS, {kind: block.COUNTS[kind]['states'] for kind in KINDS})

    def test_each_kind_holds_as_many_states_of_each_family_as_the_generator_counted(self):
        for kind in KINDS:
            with self.subTest(kind=kind):
                found = collections.Counter(entry['family'] for entry in self.entries(kind))
                counted = {family: found.get(family, 0) for family in FAMILIES}
                self.assertEqual(FAMILY_COUNTS[kind], counted)
                self.assertEqual(
                    counted, {family: block.COUNTS[kind][family] for family in FAMILIES})

    def test_every_state_and_passive_has_one_known_family(self):
        for kind in KINDS:
            with self.subTest(kind=kind):
                found = [entry['family'] for entry in self.entries(kind)]
                self.assertEqual([], [one for one in found if one not in FAMILIES])
                self.assertEqual(
                    TOTALS[kind], sum(block.COUNTS[kind][family] for family in FAMILIES))

    def test_no_state_is_a_turn_state_since_the_turn_is_not_modelled(self):
        for kind in KINDS:
            self.assertEqual(0, block.COUNTS[kind]['D'], kind)

    def test_the_epic_states_of_the_build_and_the_conversion_families_are_these(self):
        epics = {state: entry for state, entry in block.STATES.items()
                 if state in self.states_of('epic')}
        self.assertEqual(EPIC_B, sorted(s for s, e in epics.items() if e['family'] == 'B'))
        self.assertEqual(EPIC_C, sorted(s for s, e in epics.items() if e['family'] == 'C'))

    def test_a_gear_state_is_never_also_a_sublimation_state(self):
        sublimations = {state for state, _l, _k, _p in block.SUBLIMATIONS.values()}
        self.assertEqual(set(), self.states_of('gear') & sublimations)

    def test_a_line_the_solver_counts_is_in_family_a_or_b_and_names_a_stat(self):
        for state, entry in list(block.STATES.items()) + list(block.PASSIVES.items()):
            for family, key, _p0, _p1, guards in entry['lines']:
                self.assertIn(family, 'AB', state)
                self.assertTrue(key, state)
                self.assertTrue(all(0 <= at < len(entry['conditions']) for at in guards))

    def test_a_normal_sublimation_state_has_a_cap(self):
        normal = self.states_of('normal')
        self.assertEqual([], [state for state in normal if not block.STATES[state]['cap']])

    def test_the_two_notes_that_the_client_confirms_are_marked_concordant(self):
        agreed = sorted(state for state, (_note, status, _url)
                        in block.CHANGED_BY_NOTES.items() if status == 'CONCORDANT')
        self.assertEqual([6001, 8403], agreed)
