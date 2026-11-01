import os

from django.test import SimpleTestCase

from fashionistapulp import (wakfu_client_spells, wakfu_criteria, wakfu_defense,
                             wakfu_family, wakfu_turn, wakfu_value)
from fashionistapulp.wakfu_value_rules import RULES, STATUSES

BASE = {'ap': (6, 6), 'mp': (3, 3), 'wp': (6, 6)}
ROLE = wakfu_value.DamageDealer(wakfu_value.ELEMENTS, 'distance')
MELEE = wakfu_value.DamageDealer(wakfu_value.ELEMENTS, 'melee')
LEVEL = 245

#: Rows of the client's class spells by family, and how many the policy reads (build 1.93.1.62)
READABLE = {'heal': (164, 96), 'armor': (142, 83), 'push': (116, 58), 'teleport': (104, 21),
            'removal': (82, 47), 'damage': (701, 495)}
NEW_RULES = ('critical_mastery_heals', 'berserk_mastery_heals', 'self_heal_uses_melee_mastery',
             'removal_share_at_equal_willpower', 'target_willpower', 'teleport_cells',
             'unknown_recipient_rows_count', 'possibly_caster_rows_count_on_the_life_side')


def totals(**stats):
    out = wakfu_value.bare_totals(BASE)
    out.update(stats)
    return out


def holds(criterion, aim='ally', distance=1, states=None, deck=(), breed=7, high=4):
    """Whether one criterion holds in a context, through the policy."""
    tree, unread = wakfu_family.prepare(criterion)
    if unread:
        raise AssertionError('unread %s' % sorted(unread))
    row = wakfu_family.FamilyRow(1, 258, 'water', 1, 1, 'client', (tree,))
    spell = wakfu_family.FamilySpell(1, 'x', breed, None, 3, 0, 0, 1, high, 1, LEVEL, (row,), ())
    context = wakfu_family.Context(aim, distance, states or {}, frozenset(deck), breed)
    return wakfu_family.row_holds(row, spell, context)


class PolicyTests(SimpleTestCase):
    def test_enemy_sight_and_a_free_cell_are_true_where_the_family_is_aimed_at_enemies(self):
        for text in ('IsEnemy("target")', 'IsEnnemy()', 'HasLineOfSight("target")',
                     'IsTargetCellFree()'):
            self.assertTrue(holds(text, aim='enemy'), text)

    def test_a_heal_aimed_at_allies_does_not_hold_under_the_enemy_function(self):
        self.assertFalse(holds('IsEnnemy()', aim='ally'))
        self.assertTrue(holds('not IsEnnemy()', aim='ally'))

    def test_the_team_comparison_holds_for_the_team_the_family_is_aimed_at(self):
        same = 'GetTeamId("caster") == GetTeamId("target")'
        other = 'GetTeamId("caster") != GetTeamId("target")'
        self.assertTrue(holds(same, aim='ally'))
        self.assertFalse(holds(same, aim='enemy'))
        self.assertTrue(holds(other, aim='enemy'))
        self.assertFalse(holds(other, aim='ally'))

    def test_the_distance_is_the_one_the_role_reaches(self):
        self.assertTrue(holds('GetDistanceBetweenCasterAndTarget() >= 3', distance=4))
        self.assertFalse(holds('GetDistanceBetweenCasterAndTarget() >= 3', distance=1))
        self.assertEqual(1, wakfu_family.distance(self.spell(1, 4), 'melee'))
        self.assertEqual(4, wakfu_family.distance(self.spell(1, 4), 'distance'))
        self.assertEqual(0, wakfu_family.distance(self.spell(0, 0), 'distance'))

    @staticmethod
    def spell(low, high):
        return wakfu_family.FamilySpell(1, 'x', 7, None, 3, 0, 0, low, high, 1, LEVEL, (), ())

    def test_a_passive_counts_when_it_is_in_the_chosen_deck(self):
        self.assertFalse(holds('IsSpellInDeck(2062, "caster")'))
        self.assertTrue(holds('IsSpellInDeck(2062, "caster")', deck=(2062,)))
        self.assertTrue(holds('not IsSpellInDeck(2062, "caster")'))

    def test_a_state_holds_only_when_the_class_options_hold_it_and_a_negation_is_honoured(self):
        self.assertFalse(holds('HasState(702)'))
        self.assertTrue(holds('not HasState(702)'))
        self.assertTrue(holds('HasState(702)', states={702: 1}))
        self.assertTrue(holds('HasStateFromUser(702, "target")', states={702: 1}))
        self.assertTrue(holds('GetStateLevel(702) >= 2', states={702: 3}))
        self.assertFalse(holds('GetStateLevel(702) >= 2', states={702: 1}))
        self.assertFalse(holds('not HasState(702) and HasState(5)', states={5: 1, 702: 1}))

    def test_summons_and_carrying_are_false(self):
        for text in ('IsOwnSummon(5577, "target")', 'IsSummon("target")', 'IsCarried("target")',
                     'IsCarrying("target")'):
            self.assertFalse(holds(text), text)
            self.assertTrue(holds('not ' + text), text)

    def test_the_breed_is_the_casters(self):
        self.assertTrue(holds('IsBreedId(7)', breed=7))
        self.assertFalse(holds('IsBreedId(4)', breed=7))

    def test_a_function_outside_the_table_is_unread_and_named(self):
        tree, unread = wakfu_family.prepare('HasFightProperty("target", 1) and IsEnnemy()')
        self.assertEqual({'HasFightProperty'}, unread)
        _tree, unread = wakfu_family.prepare('GetCharac("MP") < 6 or GetTotalHpInPercent() > 50')
        self.assertEqual({'GetCharac', 'GetTotalHpInPercent'}, unread)

    def test_an_expression_the_parser_cannot_read_is_unread(self):
        tree, unread = wakfu_family.prepare('(GetStateLevel(6759, "caster") % 2) == 0')
        self.assertIsNone(tree)
        self.assertEqual({wakfu_family.UNPARSED}, unread)

    def test_every_function_of_the_table_is_one_the_client_texts_use(self):
        self.assertEqual(16, len(wakfu_family.POLICY))
        self.assertTrue(all(isinstance(name, str) for name in wakfu_family.POLICY))
        for name in ('IsEnemy', 'IsEnnemy', 'HasLineOfSight', 'IsTargetCellFree',
                     'GetDistanceBetweenCasterAndTarget', 'IsSpellInDeck', 'HasState',
                     'HasStateFromUser', 'GetStateLevel', 'HasStateFromLevel', 'IsOwnSummon',
                     'IsSummon', 'IsCarried', 'IsCarrying', 'IsBreedId', 'GetTeamId'):
            self.assertIn(name, wakfu_family.POLICY)

    def test_the_policy_resolves_a_tree_through_the_criteria_evaluator(self):
        tree, _ = wakfu_family.prepare('IsEnnemy() or not HasState(1)')
        self.assertIsInstance(tree, wakfu_criteria.Or)


class NewRulesTests(SimpleTestCase):
    def test_each_new_rule_has_a_status_and_a_source(self):
        for name in NEW_RULES:
            rule = RULES[name]
            self.assertIn(rule.status, STATUSES, name)
            self.assertTrue(rule.source.strip(), name)

    def test_the_values_are_the_designs(self):
        self.assertIs(True, RULES['critical_mastery_heals'].value)
        self.assertIs(False, RULES['berserk_mastery_heals'].value)
        self.assertIs(True, RULES['self_heal_uses_melee_mastery'].value)
        self.assertEqual({'at_equal': 0.5, 'per_point': 1 / 200},
                         RULES['removal_share_at_equal_willpower'].value)
        self.assertEqual(0, RULES['target_willpower'].value)
        self.assertEqual(2, RULES['teleport_cells'].value)
        self.assertIs(False, RULES['unknown_recipient_rows_count'].value)
        self.assertIs(False, RULES['possibly_caster_rows_count_on_the_life_side'].value)


class SyntheticTurnTests(SimpleTestCase):
    @staticmethod
    def spell(*rows, skipped=()):
        return wakfu_family.FamilySpell(
            1, 'x', 7, None, 3, 0, 0, 1, 5, 1, LEVEL, tuple(rows), tuple(skipped))

    def test_a_skipped_row_is_in_the_notes_and_never_in_the_value(self):
        row = wakfu_family.FamilyRow(1, 258, 'water', 100, 100, 'client')
        skipped = ((2, 'a criterion with HasFightProperty', ('HasFightProperty',)),)
        turn = wakfu_turn.TurnModel([self.spell(row, skipped=skipped)], ROLE, 'heal',
                                    casts_per_spell=1).best(totals())
        self.assertEqual(100, turn.damage)
        self.assertEqual([((1,), wakfu_turn.UNREAD, 'row 2, HasFightProperty')],
                         list(turn.unmodelled))

    def test_a_spell_whose_rows_are_all_skipped_adds_nothing(self):
        skipped = ((2, 'a criterion with IsOffPlay', ('IsOffPlay',)),)
        turn = wakfu_turn.TurnModel([self.spell(skipped=skipped)], ROLE, 'heal').best(totals())
        self.assertEqual(0.0, turn.damage)
        self.assertEqual((), turn.casts)
        self.assertEqual(1, len(turn.unmodelled))

    def test_a_row_under_a_state_the_class_does_not_hold_stays_out_until_it_holds_it(self):
        tree, _ = wakfu_family.prepare('HasState(702)')
        row = wakfu_family.FamilyRow(1, 258, 'water', 100, 100, 'client', (tree,))
        model = wakfu_turn.TurnModel([self.spell(row)], ROLE, 'heal', casts_per_spell=1)
        self.assertEqual(0.0, model.damage(totals()))
        held = wakfu_turn.TurnModel([self.spell(row)], ROLE, 'heal', casts_per_spell=1,
                                    states={702: 1})
        self.assertEqual(100, held.damage(totals()))

    def test_placement_counts_cells_and_a_teleport_counts_the_choice(self):
        push = wakfu_family.FamilyRow(1, 300, 'push', 3, None, 'none')
        pull = wakfu_family.FamilyRow(2, 301, 'push', 2, None, 'none')
        tele = wakfu_family.FamilyRow(3, 302, 'teleport', RULES['teleport_cells'].value,
                                      None, 'none')
        turn = wakfu_turn.TurnModel([self.spell(push, pull, tele)], ROLE, 'placement',
                                    casts_per_spell=1).best(totals())
        self.assertEqual(3 + 2 + 2, turn.damage)

    def test_armor_adds_the_rows_that_land(self):
        one = wakfu_family.FamilyRow(1, 1013, 'armor', 20, None, 'none')
        two = wakfu_family.FamilyRow(2, 1013, 'armor', 30, None, 'none')
        turn = wakfu_turn.TurnModel([self.spell(one, two)], ROLE, 'armor',
                                    casts_per_spell=1).best(totals())
        self.assertEqual(50, turn.damage)

    def test_a_family_that_does_not_exist_is_refused(self):
        with self.assertRaises(ValueError):
            wakfu_turn.TurnModel([], ROLE, 'tank')

    def test_the_damage_family_is_the_default_and_its_turn_is_unchanged(self):
        self.assertEqual('damage', wakfu_turn.TurnModel([], ROLE).family)

    def test_no_readable_self_armor_gives_an_armor_turn_of_zero_and_a_note(self):
        empty = wakfu_turn.TurnModel([], ROLE, 'armor').best(totals())
        value, notes = wakfu_defense.class_armor_turn(empty)
        self.assertEqual(0.0, value)
        self.assertEqual((wakfu_defense.NO_SELF_ARMOR,), notes)
        self.assertEqual((0.0, (wakfu_defense.NO_SELF_ARMOR,)),
                         wakfu_defense.class_armor_turn(None))

    def test_a_readable_armor_turn_is_the_class_armor_turn(self):
        row = wakfu_family.FamilyRow(1, 1013, 'armor', 40, None, 'none')
        turn = wakfu_turn.TurnModel([self.spell(row)], ROLE, 'armor',
                                    casts_per_spell=1).best(totals())
        self.assertEqual((40.0, ()), wakfu_defense.class_armor_turn(turn))

    def test_the_armor_turn_feeds_the_effective_life(self):
        row = wakfu_family.FamilyRow(1, 1013, 'armor', 400, None, 'none')
        turn = wakfu_turn.TurnModel([self.spell(row)], ROLE, 'armor',
                                    casts_per_spell=1).best(totals())
        armor_turn, _ = wakfu_defense.class_armor_turn(turn)
        plain = wakfu_defense.effective_life(LEVEL, totals())
        self.assertGreater(wakfu_defense.effective_life(LEVEL, totals(), 'pvm', armor_turn),
                           plain)


class ClientFamilyRowsTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from fashionistapulp.fashionista_config import get_items_db_path
        path = get_items_db_path('wakfu')
        cls.book = None
        if os.path.exists(path):
            book = wakfu_turn.SpellBook(path)
            if book.client() is None:
                book.close()
            else:
                cls.book = book

    @classmethod
    def tearDownClass(cls):
        if cls.book is not None:
            cls.book.close()
        super().tearDownClass()

    def setUp(self):
        if self.book is None:
            self.skipTest('no Wakfu database with the client spell table')

    def test_the_policy_reads_the_rows_of_the_designs_count(self):
        client = self.book.client()
        found = {family: [0, 0] for family in READABLE}
        for breed in client.breeds():
            for own in client.class_spells(breed):
                for row in own.rows:
                    if row.branch != wakfu_client_spells.NORMAL or row.family not in found:
                        continue
                    found[row.family][0] += 1
                    unread = {name for criterion in row.criteria
                              for name in wakfu_family.CALL_NAME.findall(criterion)
                              if name not in wakfu_family.POLICY}
                    found[row.family][1] += not unread
        self.assertEqual(READABLE, {family: tuple(pair) for family, pair in found.items()})

    def test_no_row_of_any_family_holds_a_function_outside_the_table(self):
        for family in wakfu_family.FAMILIES:
            for breed in self.book.client().breeds():
                for found in self.book.family_spells(breed, LEVEL, family):
                    for row in found.rows:
                        for tree in row.trees:
                            self.assertEqual(
                                set(), wakfu_criteria.functions(tree) - wakfu_family.READ)

    def test_a_spell_skipped_for_a_function_has_the_function_in_the_notes_and_not_in_the_value(self):
        spells = self.book.family_spells(7, LEVEL, 'heal')
        by_id = {found.id: found for found in spells}
        revitalisation = by_id[780]
        self.assertEqual((), revitalisation.rows)
        self.assertEqual({('GetTotalHpInPercent',)},
                         {functions for _id, _why, functions in revitalisation.skipped})
        model = wakfu_turn.TurnModel([revitalisation], ROLE, 'heal')
        turn = model.best(totals(dmg_fire_percent=500))
        self.assertEqual(0.0, turn.damage)
        self.assertTrue(all(note[1] == wakfu_turn.UNREAD for note in turn.unmodelled))
        self.assertEqual(2, len(turn.unmodelled))

    def test_every_skipped_row_names_its_reason(self):
        for family in wakfu_family.FAMILIES:
            for breed in self.book.client().breeds():
                for found in self.book.family_spells(breed, LEVEL, family):
                    for _id, why, functions in found.skipped:
                        self.assertTrue(why)
                        if functions:
                            self.assertTrue(set(functions).isdisjoint(wakfu_family.READ))

    def test_a_row_inside_another_mechanism_is_skipped_not_read(self):
        for breed in self.book.client().breeds():
            for found in self.book.family_spells(breed, LEVEL, 'armor'):
                own = self.book.client().spell(found.id)
                for row in own.rows_of('armor'):
                    inside = [action for action, _c, _i in row.signature[:-1]
                              if action != wakfu_family.GROUP_ACTION]
                    if inside:
                        self.assertNotIn(row.effect, [one.id for one in found.rows])

    def test_the_armor_turn_of_an_iop_is_read_and_a_class_with_none_gets_zero(self):
        iop = wakfu_turn.TurnModel(self.book.family_spells(8, LEVEL, 'armor'), MELEE, 'armor')
        value, notes = wakfu_defense.class_armor_turn(iop.best(totals()))
        self.assertGreater(value, 0)
        self.assertEqual((), notes)
        xelor = wakfu_turn.TurnModel(self.book.family_spells(5, LEVEL, 'armor'), MELEE, 'armor')
        value, notes = wakfu_defense.class_armor_turn(xelor.best(totals()))
        self.assertEqual(0.0, value)
        self.assertEqual((wakfu_defense.NO_SELF_ARMOR,), notes)

    def test_below_the_unlock_level_a_spell_is_not_in_a_family(self):
        high = {found.id for found in self.book.family_spells(7, LEVEL, 'heal')}
        low = {found.id for found in self.book.family_spells(7, 5, 'heal')}
        self.assertLess(low, high)
        for found in self.book.family_spells(7, 5, 'heal'):
            self.assertLessEqual(found.unlock, 5)
