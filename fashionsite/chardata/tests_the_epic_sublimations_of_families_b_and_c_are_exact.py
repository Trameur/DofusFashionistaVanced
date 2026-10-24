import collections
import json
import re
from pathlib import Path

from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[2]

from chardata.wakfu_invented_sublimations import (
    EPIC_RARITY, Piece, Structure, socket_row)
from fashionistapulp import wakfu_legality, wakfu_sublimations

try:
    from fashionistapulp import wakfu_special_items as live
except ImportError:
    live = None

EPIC_B = {5073: 'Inflexible', 5074: 'Constant', 5075: 'Measure', 5076: 'Precise',
          6706: 'Outrage II', 6707: 'Pillar', 7255: 'Controlling Space II',
          7256: 'Inflexibility II', 7876: 'Constant II', 7880: 'Engagement',
          7881: 'Iron Will', 8384: 'Pillar II', 8385: 'Measure II', 9074: 'Critical Secret'}
EPIC_C = {5077: 'Unraveling', 5449: 'Elemental Concentration', 7882: 'Colossal'}
# The states whose lines the independent walk below finds all of, key included
WALKED_IN_FULL = (5073, 5074, 5075, 6706, 7256, 7880, 7881, 8385, 9074)
# The states whose text numbers all show in the lines and conditions
TEXT_MATCHES = (5073, 5076, 6707, 7255, 8384, 8385)
START_OF_COMBAT = 1028
LEVEL = 200


def client_files():
    folder = ROOT / 'itemscraper' / 'wakfu_client' / live.CLIENT_VERSION
    names = ('tables.json', 'texts.json')
    if not all((folder / name).exists() for name in names):
        return None
    tables, texts = (json.loads((folder / name).read_text(encoding='utf-8')) for name in names)
    return tables, texts['texts']


def epic_item(state):
    return next(item for item, row in live.SUBLIMATIONS.items()
                if row[0] == state and row[2] == 'epic')


class TheLiveEpicBlockCase(SimpleTestCase):
    def setUp(self):
        if live is None:
            self.skipTest('no wakfu_special_items.py; run '
                          'itemscraper/generate_wakfu_special_items.py')

    def fight(self, state, totals, level=LEVEL):
        return wakfu_sublimations.fight_lines(
            [(wakfu_sublimations.SUBLIMATION, epic_item(state))], collections.Counter(totals),
            level, 1)


class TheEpicStatesOfFamiliesBAndCArePinnedTests(TheLiveEpicBlockCase):
    def epics(self, family):
        return {state: entry['name'] for state, entry in live.STATES.items()
                if entry['family'] == family
                and any(row[0] == state and row[2] == 'epic'
                        for row in live.SUBLIMATIONS.values())}

    def test_the_epic_states_of_family_b_are_these_fourteen(self):
        self.assertEqual(EPIC_B, self.epics('B'))

    def test_the_epic_states_of_family_c_are_these_three(self):
        self.assertEqual(EPIC_C, self.epics('C'))

    def test_every_epic_sublimation_names_one_of_its_states_at_level_one(self):
        for state in list(EPIC_B) + list(EPIC_C):
            rows = [row for row in live.SUBLIMATIONS.values()
                    if row[0] == state and row[2] == 'epic']
            self.assertEqual([1], [row[1] for row in rows], state)


class TheEpicRulesEqualAnIndependentWalkOfTheClientTablesTests(TheLiveEpicBlockCase):
    def setUp(self):
        super().setUp()
        found = client_files()
        if found is None:
            self.skipTest('no decoded client tables for %s' % live.CLIENT_VERSION)
        self.tables, self.texts = found
        self.effects = {effect['id']: effect for effect in self.tables['effects']}
        self.groups = {group['id']: group['effect_ids'] for group in self.tables['groups']}
        self.states = {state['id']: state for state in self.tables['states']}

    def leaves(self, ident, chain):
        effect = self.effects[ident]
        chain = chain + ([effect['criterion']] if effect['criterion'] else [])
        if ident in self.groups:
            return [leaf for child in self.groups[ident] for leaf in self.leaves(child, chain)]
        return [(effect, chain)]

    def walked(self, state):
        """Counter {(key, p0, p1, guarded)} of the leaves that name a characteristic."""
        actions = self.texts['action_texts']['en']
        found = collections.Counter()
        every = []
        for root in self.states[state]['effect_ids']:
            if START_OF_COMBAT not in self.effects[root]['triggers'][5]:
                continue
            for effect, chain in self.leaves(root, []):
                if any(re.search(r'\band False\b|^False$', text) for text in chain):
                    continue
                every.append((float(effect['params'][0]), float(effect['params'][1])))
                text = actions.get(str(effect['action_id']), '')
                match = re.search(r'\[#charac (\w+)\]', text)
                if match:
                    sign = -1 if re.search(r'\]\s*-\[', text) else 1
                    found[(match.group(1).lower(), sign * float(effect['params'][0]),
                           sign * float(effect['params'][1]),
                           any(re.search(r'GetCharac|GetLevel', text) for text in chain))] += 1
        return found, every

    def lines(self, state):
        return collections.Counter((key, float(p0), float(p1), bool(guards))
                                   for _family, key, p0, p1, guards in live.STATES[state]['lines'])

    def test_the_lines_of_the_states_the_walk_names_in_full_are_the_walked_ones(self):
        for state in WALKED_IN_FULL:
            with self.subTest(state=state, name=EPIC_B[state]):
                self.assertEqual(self.walked(state)[0], self.lines(state))

    def shapes(self, counter):
        """Counter {(p0, p1, guarded)}: the key is left out, the sign is the action text's."""
        return collections.Counter(
            (p0, p1, guarded) for (_key, p0, p1, guarded), times in counter.items()
            for _ in range(times))

    def test_every_walked_line_of_every_family_b_state_is_in_the_block_with_its_sign(self):
        for state in EPIC_B:
            with self.subTest(state=state, name=EPIC_B[state]):
                missing = self.shapes(self.walked(state)[0]) - self.shapes(self.lines(state))
                self.assertEqual(collections.Counter(), missing)

    def test_every_line_of_the_block_has_a_leaf_with_its_parameters(self):
        for state in list(EPIC_B):
            _found, every = self.walked(state)
            shown = {(abs(p0), abs(p1)) for p0, p1 in every}
            for _family, key, p0, p1, _guards in live.STATES[state]['lines']:
                self.assertIn((abs(float(p0)), abs(float(p1))), shown, (state, key))

    def numbers(self, state):
        text = ' '.join(self.texts['effect_texts']['en'].get(str(root), '')
                        for root in self.states[state]['effect_ids'])
        return {int(one) for one in re.findall(r'\d+', text)}

    def block_numbers(self, state):
        entry = live.STATES[state]
        shown = set()
        for _family, _key, p0, p1, _guards in entry['lines']:
            shown |= {abs(p0), abs(p1)}
        for _function, _key, _operator, value in entry['conditions']:
            if isinstance(value, (int, float)):
                shown.add(value)
        for _source, _target, p0, p1, _sign, _guards in entry['conversions']:
            shown |= {p0, p1, p0 * 100, p1 * 100}
        return shown

    def test_every_number_of_the_root_text_appears_in_the_block_rule(self):
        for state in TEXT_MATCHES + (5077,):
            with self.subTest(state=state):
                self.assertEqual(set(), self.numbers(state) - self.block_numbers(state))

    def test_inflexible_and_unraveling_show_the_numbers_the_text_gives(self):
        self.assertEqual({10, 15, 100}, self.numbers(5073))
        self.assertEqual({100, 40}, self.numbers(5077))

    def test_the_walk_drops_the_branch_the_client_ends_in_false(self):
        branches = [text for root in self.states[7256]['effect_ids']
                    for _effect, chain in self.leaves(root, []) for text in chain]
        self.assertTrue(any(re.search(r'\band False\b', text) for text in branches))
        self.assertEqual(2, sum(self.lines(7256).values()))


class InflexibleCountsOnTheApTheSheetShowsTests(TheLiveEpicBlockCase):
    def test_it_counts_at_ten_action_points_and_not_at_eleven(self):
        lines, reports = self.fight(5073, {'ap': 10})
        self.assertEqual({'final_dmg_in_percent': 15, 'willpower': 10}, lines)
        self.assertTrue(reports[5073].condition)
        lines, reports = self.fight(5073, {'ap': 11})
        self.assertEqual({}, lines)
        self.assertFalse(reports[5073].condition)

    def test_the_willpower_waits_for_level_one_hundred(self):
        self.assertEqual({'final_dmg_in_percent': 15},
                         self.fight(5073, {'ap': 10}, level=99)[0])
        self.assertEqual({'final_dmg_in_percent': 15, 'willpower': 10},
                         self.fight(5073, {'ap': 10}, level=100)[0])

    def test_fewer_action_points_still_count(self):
        self.assertEqual(15, self.fight(5073, {'ap': 6})[0]['final_dmg_in_percent'])


class UnravelingConvertsCriticalMasteryAtFortyFerocityTests(TheLiveEpicBlockCase):
    def test_it_moves_the_critical_mastery_into_elemental_at_forty(self):
        lines, _reports = self.fight(5077, {'critical_bonus': 300, 'ferocity': 40})
        self.assertEqual({'critical_bonus': -300, 'dmg_in_percent': 300}, lines)

    def test_it_does_nothing_at_thirty_nine(self):
        self.assertEqual({}, self.fight(5077, {'critical_bonus': 300, 'ferocity': 39})[0])

    def test_it_does_nothing_below_two_critical_mastery(self):
        self.assertEqual({}, self.fight(5077, {'critical_bonus': 1, 'ferocity': 60})[0])

    def test_a_negative_critical_mastery_converts_nothing(self):
        self.assertEqual({}, self.fight(5077, {'critical_bonus': -50, 'ferocity': 60})[0])

    def test_the_converted_amount_is_the_sheet_total_whatever_the_fight_adds(self):
        lines, _reports = self.fight(5077, {'critical_bonus': 123, 'ferocity': 55})
        self.assertEqual(123, lines['dmg_in_percent'])
        self.assertEqual(-123, lines['critical_bonus'])


class TheCheckerReadsTheStateConditionBothWaysTests(TheLiveEpicBlockCase):
    LINES = {'final_dmg_in_percent': 15, 'willpower': 10}

    def rules(self, ap, lines):
        epic = Piece(10, 1, rarity=EPIC_RARITY, level=100, stats=[(1, ap - 6)])
        structure = Structure([epic], bases={1: {'ap': 6}})
        report = wakfu_sublimations.StateReport(1, None, 1, 'B', True, lines)
        found = wakfu_legality.violations(
            structure, 100, {'HEAD': epic}, class_id=1,
            sublimations={}, specials={'HEAD': epic_item(5073)},
            runes={'HEAD': socket_row()}, states={5073: report})
        return [rule for rule, _text in found]

    def test_a_state_counted_while_its_condition_fails_is_flagged(self):
        self.assertEqual([wakfu_legality.STATE_CONDITION], self.rules(11, self.LINES))

    def test_a_state_not_counted_while_its_condition_holds_is_flagged(self):
        self.assertEqual([wakfu_legality.STATE_CONDITION], self.rules(10, {}))

    def test_a_state_counted_as_its_condition_says_is_legal(self):
        self.assertEqual([], self.rules(10, self.LINES))
        self.assertEqual([], self.rules(11, {}))
