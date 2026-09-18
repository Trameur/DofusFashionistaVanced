# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A Touch spell with no description is explained from its effect rows."""
from django.test import SimpleTestCase

from chardata.tests import itemscraper_module

EFFECTS = {
    '1163': {'descriptionId': 'Dommages subis x#1%'},
    '119': {'descriptionId': '#1{~1~2 à }#2 Agilité'},
    '138': {'descriptionId': '#1{~1~2 à }#2 Puissance'},
    '181': {'descriptionId': 'Invoque : #1'},
    '792': {'descriptionId': '#1'},
    '950': {'descriptionId': 'État #3'},
    '1109': {'descriptionId': 'Soin : #1{~1~2 à }#2% des PV max'},
    '2909': {'descriptionId': 'Augmente les déplacements occasionnés de #3'},
    '2915': {'descriptionId': 'Augmente les déplacements subis de #1'},
}


def _row(effect_id, dice_num=0, dice_side=0, value=0, triggers='I',
         random=0, hidden=False):
    return {'effectId': effect_id, 'diceNum': dice_num, 'diceSide': dice_side,
            'value': value, 'triggers': triggers, 'random': random,
            'hidden': hidden}


def _read(rows, monster_names=None, lang='fr'):
    tooltips = itemscraper_module('store_spell_tooltips')
    spell = {'spellLevels': [1, 2]}
    levels = {'1': {'effects': rows},
              '2': {'effects': [_row(1109, 20)]}}
    return tooltips.touch_spell_effects(spell, levels, EFFECTS,
                                        monster_names or {}, lang)


class AnUndescribedTouchSpellReadsItsEffectsTests(SimpleTestCase):

    def test_the_shield_halves_what_summons_deal(self):
        # DI: damage from summons, per Griffe Cinglante's description
        rows = [_row(1163, 50, 63, triggers='DI')]
        self.assertEqual('Dommages subis x50% de la part des invocations',
                         _read(rows))
        self.assertEqual('Dommages subis x50% from summons',
                         _read(rows, lang='en'))

    def test_a_row_drawn_at_random_says_its_odds(self):
        rows = [_row(119, 30, random=20), _row(138, 20, random=20)]
        self.assertEqual('30 Agilité (20%), 20 Puissance (20%)', _read(rows))

    def test_a_summon_is_named_or_left_out(self):
        rows = [_row(181, 4183, 1)]
        self.assertEqual('Invoque : Boufballe',
                         _read(rows, {4183: 'Boufballe'}))
        self.assertIsNone(_read(rows))

    def test_ids_hidden_rows_and_missing_amounts_are_left_out(self):
        # #3 can hold an id, and #1 is 0 here
        self.assertIsNone(_read([_row(2909, value=1), _row(2915, value=1)]))
        self.assertIsNone(_read([_row(950, value=873), _row(792, 8603, 2)]))
        self.assertIsNone(_read([_row(119, 30, hidden=True)]))

    def test_a_row_on_a_trigger_it_cannot_word_is_left_out(self):
        # TB: recast at turn start, not worded
        self.assertIsNone(_read([_row(119, 30, triggers='TB')]))
