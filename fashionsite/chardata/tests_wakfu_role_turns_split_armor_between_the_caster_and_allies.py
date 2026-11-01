import os
from unittest import mock

from django.test import SimpleTestCase

from fashionistapulp import (wakfu_family, wakfu_presets, wakfu_recipient, wakfu_turn,
                             wakfu_value)
from fashionistapulp.wakfu_stats import OUT_OF_COMBAT_CAPS
from fashionistapulp.wakfu_value_rules import RULES

BASE = {'ap': (6, 6), 'mp': (3, 3), 'wp': (6, 6)}
ROLE = wakfu_value.Role(wakfu_value.ELEMENTS, 'distance')
MELEE = wakfu_value.Role(wakfu_value.ELEMENTS, 'melee')
FECA, IOP, PANDAWA, MASQUERADER = 1, 8, 12, 14
LEVEL = 245
CASTER_ONLY = frozenset({'caster'})
ALLIES_ONLY = frozenset({'allies'})
BOTH = frozenset({'caster', 'allies'})
MAYBE = frozenset({'allies', 'possibly_caster'})


def totals():
    return wakfu_value.bare_totals(BASE)


def ceiling():
    return {name.lower(): cap for name, cap in OUT_OF_COMBAT_CAPS.items()}


def spell_of(*rows, skipped=()):
    return wakfu_family.FamilySpell(1, 'spell', FECA, None, 3, 0, 0, 1, 5, 1, LEVEL,
                                    tuple(rows), tuple(skipped))


def armor(row_id, base, recipients):
    return wakfu_family.FamilyRow(row_id, 1013, 'armor', base, None, 'none',
                                  recipients=recipients)


def model_of(spell, recipient=None):
    return wakfu_turn.TurnModel([spell], ROLE, 'armor', casts_per_spell=1, recipient=recipient)


class ArmorRowsAreSplitBetweenTheCasterAndAlliesTests(SimpleTestCase):
    def setUp(self):
        self.spell = spell_of(armor(1, 100, CASTER_ONLY), armor(2, 50, ALLIES_ONLY),
                              armor(3, 30, BOTH))

    def test_the_life_side_counts_only_armor_that_reaches_the_caster(self):
        self.assertEqual(130, model_of(self.spell, 'caster').damage(totals()))

    def test_the_support_side_counts_only_armor_that_reaches_an_ally(self):
        self.assertEqual(80, model_of(self.spell, 'allies').damage(totals()))

    def test_a_turn_model_without_a_recipient_counts_every_landing_row(self):
        self.assertEqual(180, model_of(self.spell).damage(totals()))
        unread = spell_of(armor(1, 100, None), armor(2, 50, ALLIES_ONLY))
        self.assertEqual(150, model_of(unread).damage(totals()))

    def test_a_recipient_other_than_caster_or_allies_is_refused(self):
        with self.assertRaises(ValueError):
            model_of(self.spell, 'enemies').damage(totals())

    def test_a_row_that_may_reach_the_caster_counts_for_the_life_side_only_when_the_rule_says_so(self):
        spell = spell_of(armor(1, 100, MAYBE))
        self.assertEqual(0, model_of(spell, 'caster').damage(totals()))
        self.assertEqual(100, model_of(spell, 'allies').damage(totals()))
        rule = RULES['possibly_caster_rows_count_on_the_life_side']._replace(value=True)
        with mock.patch.dict(RULES, {'possibly_caster_rows_count_on_the_life_side': rule}):
            self.assertEqual(100, model_of(spell, 'caster').damage(totals()))


class ArmorOfTheClassSpellsIsSplitTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from fashionistapulp.fashionista_config import get_items_db_path
        cls.path = get_items_db_path('wakfu')

    def setUp(self):
        if not os.path.exists(self.path):
            self.skipTest('no Wakfu database built; run update_data_wakfu.py')
        self.book = wakfu_turn.SpellBook(self.path)
        self.addCleanup(self.book.close)

    def model(self, spells, recipient, role=ROLE):
        return wakfu_turn.TurnModel(spells, role, 'armor', recipient=recipient)

    def test_armor_that_possibly_reaches_the_caster_is_a_life_note_and_counts_on_the_support_side(self):
        spells = [spell for spell in self.book.family_spells(MASQUERADER, LEVEL, 'armor')
                  if any('possibly_caster' in row.recipients for row in spell.rows)]
        self.assertTrue(spells)
        life = self.model(spells, 'caster', MELEE).best(ceiling())
        support = self.model(spells, 'allies', MELEE).best(ceiling())
        self.assertEqual(0, life.damage)
        self.assertGreater(support.damage, 0)
        self.assertIn(wakfu_turn.MAY_REACH_CASTER, [note[2].split(', ', 1)[1]
                                                   for note in life.unmodelled])
        self.assertNotIn(wakfu_turn.MAY_REACH_CASTER, [note[2].split(', ', 1)[1]
                                                       for note in support.unmodelled])

    def test_an_armor_row_with_an_unknown_recipient_is_a_note_and_never_in_the_value(self):
        wave = [spell for spell in self.book.family_spells(FECA, LEVEL, 'armor') if spell.rows]
        self.assertTrue(wave)
        spell_id = wave[0].id
        ids = {row.id for row in wave[0].rows}
        real = self.book.recipients(spell_id)
        unknown = wakfu_recipient.Recipient(
            wakfu_recipient.UNKNOWN, frozenset({'unknown'}), wakfu_recipient.REASON_PARTY)
        book = wakfu_turn.SpellBook(self.path)
        self.addCleanup(book.close)
        book._recipients[spell_id] = {effect: unknown for effect in real}
        spell = [one for one in book.family_spells(FECA, LEVEL, 'armor') if one.id == spell_id][0]
        self.assertEqual((), spell.rows)
        reasons = [why for row_id, why, _functions in spell.skipped
                   if wakfu_recipient.REASON_PARTY in why]
        self.assertTrue(set(ids) <= {row_id for row_id, _why, _functions in spell.skipped})
        self.assertGreaterEqual(len(reasons), len(ids))
        for recipient in (None, 'caster', 'allies'):
            turn = self.model([spell], recipient).best(ceiling())
            self.assertEqual(0, turn.damage)
            self.assertEqual(len(reasons), len([note for note in turn.unmodelled
                                            if wakfu_recipient.REASON_PARTY in note[2]]))
        rule = RULES['unknown_recipient_rows_count']._replace(value=True)
        with mock.patch.dict(RULES, {'unknown_recipient_rows_count': rule}):
            counted = [one for one in book.family_spells(FECA, LEVEL, 'armor')
                       if one.id == spell_id][0]
        self.assertTrue(counted.rows)
        self.assertTrue(all(row.recipients == BOTH for row in counted.rows))

    def test_a_copy_of_a_figure_that_reaches_other_sides_adds_them_to_the_row_that_stands(self):
        rows = [(mock.Mock(action=1013, criteria=(), params=(1.0, 2.0)), armor(1, 100, CASTER_ONLY)),
                (mock.Mock(action=1013, criteria=('x',), params=(1.0, 2.0)),
                 armor(2, 100, ALLIES_ONLY))]
        kept, dropped = wakfu_turn._brackets(rows)
        self.assertEqual(1, len(kept))
        self.assertEqual(BOTH, kept[0][1].recipients)
        self.assertEqual(1, len(dropped))

    def test_the_role_turns_hold_the_self_armor_for_a_life_share_and_the_ally_armor_for_an_armor_share(self):
        for class_id, life, support in ((FECA, 0, 1), (IOP, 1, 1), (PANDAWA, 1, 0)):
            with self.subTest(class_id=class_id):
                built = wakfu_presets.role(class_id, 'support', ('earth',), LEVEL, path=self.path)
                turns = wakfu_presets.build_turns(self.book, class_id, LEVEL, built, self.path)
                self.assertEqual('armor' in built.shares, 'armor' in turns.models)
                self.assertIn('self_armor', turns.models)
                self.assertEqual(
                    bool(life), turns.models['self_armor'].damage(ceiling()) > 0)
                if 'armor' in turns.models:
                    self.assertEqual(
                        bool(support), turns.models['armor'].damage(ceiling()) > 0)
