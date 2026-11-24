# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A Touch row only a target in a state takes waits apart from the plain hit, and a steal beside its hit lands with it."""
from django.test import SimpleTestCase

from chardata.spell_buffs import get_damage_spells_for_version
from chardata.spell_combo import BOOSTED_COPIES

VERSIONS = ('touch', 'touchbeta')
PROBE = 4242
NEEDLE, DEADLY_ATTACK, SWORD_OF_JUDGMENT, ASSAULT = 7379, 76, 8079, 5893


def _reader():
    from chardata.tests import itemscraper_module
    return itemscraper_module('get_spells_touch')


def _row(effect_id, low, high, mask='a,A', **extra):
    row = {'effectId': effect_id, 'diceNum': low, 'diceSide': high, 'value': 0, 'targetMask': mask,
           'triggers': 'I', 'delay': 0, 'duration': 0, 'random': 0, 'rawZone': 'P', 'isPreview': False}
    row.update(extra)
    return row


def _decode(effects, critical=None):
    level = {'minPlayerLevel': 1, 'apCost': 3, 'maxCastPerTurn': 2, 'maxStack': 0,
             'criticalHitProbability': 15, 'effects': effects,
             'criticalEffect': effects if critical is None else critical}
    spell = {'id': PROBE, 'nameId': 'Probe', 'descriptionId': 'Occasionne des dommages Terre.',
             'spellLevels': [PROBE * 10]}
    return _reader().decode_spell(spell, {str(PROBE * 10): level}, {str(PROBE): spell})


def _spell(version, spell_id):
    return next(spell for spells in get_damage_spells_for_version(version).values()
                for spell in spells if spell.spell_id == spell_id)


class TheTouchReaderHoldsTheLineOfATargetInAStateTests(SimpleTestCase):

    def test_a_stronger_line_on_a_target_in_a_state_is_a_held_copy_beside_the_plain_hit(self):
        entry = _decode([_row(97, 10, 14), _row(97, 20, 24, mask='a,A,E580')])
        self.assertEqual(entry['non_crit_ranges'], [['10-14'], ['20-24']])
        self.assertEqual(entry['elements'], ['earth', 'earth'])
        self.assertEqual(entry['conditional'], {1: 'target_in_a_state'})

    def test_the_plain_line_is_the_hit_whatever_the_row_order(self):
        entry = _decode([_row(97, 20, 24, mask='a,A,E580'), _row(97, 10, 14)])
        self.assertEqual(entry['non_crit_ranges'], [['10-14'], ['20-24']])

    def test_a_weaker_line_on_a_target_in_a_state_is_dropped(self):
        entry = _decode([_row(97, 10, 14), _row(97, 6, 8, mask='a,A,E580')])
        self.assertEqual(entry['non_crit_ranges'], [['10-14']])
        self.assertFalse(entry.get('conditional'))

    def test_a_line_only_a_target_in_a_state_takes_with_no_plain_line_is_the_hit(self):
        entry = _decode([_row(97, 20, 24, mask='a,A,E580')])
        self.assertEqual(entry['non_crit_ranges'], [['20-24']])
        self.assertFalse(entry.get('conditional'))

    def test_a_line_the_caster_state_gates_is_not_a_target_state(self):
        entry = _decode([_row(97, 10, 14), _row(97, 20, 24, mask='a,A,*E99')])
        self.assertEqual(entry['non_crit_ranges'], [['20-24']])
        self.assertFalse(entry.get('conditional'))

    def test_a_buff_only_a_target_in_a_state_gives_is_left_out(self):
        gated = _decode([_row(97, 10, 14), _row(118, 40, 0, mask='A,E580')])
        plain = _decode([_row(97, 10, 14), _row(118, 40, 0, mask='A')])
        self.assertEqual(gated['elements'], ['earth'])
        self.assertIn('buff_str', plain['elements'])

    def test_a_state_line_on_one_kind_of_hit_only_stops_the_reader(self):
        with self.assertRaises(SystemExit):
            _decode([_row(97, 10, 14), _row(97, 20, 24, mask='a,A,E580')], critical=[_row(97, 12, 16)])

    def test_a_state_line_that_lands_later_stops_the_reader(self):
        with self.assertRaises(SystemExit):
            _decode([_row(97, 10, 14), _row(97, 20, 24, mask='a,A,E580', triggers='TB')])

    def test_a_state_line_beside_an_ally_only_hit_stops_the_reader(self):
        with self.assertRaises(SystemExit):
            _decode([_row(97, 10, 14, mask='A'), _row(97, 5, 6, mask='a'),
                     _row(97, 20, 24, mask='A,E580')])

    def test_the_held_copy_is_priced_as_a_boost_of_the_hit(self):
        self.assertIn(_reader().TARGET_STATE_COPY, BOOSTED_COPIES)


class TheTouchReaderLandsAStealBesideItsHitTests(SimpleTestCase):

    def test_a_steal_beside_a_hit_of_its_element_is_its_own_row(self):
        entry = _decode([_row(98, 10, 14), _row(93, 6, 8)])
        self.assertEqual(entry['non_crit_ranges'], [['10-14'], ['6-8']])
        self.assertEqual(entry['elements'], ['air', 'steal_air'])

    def test_a_steal_on_another_mask_still_keeps_the_strongest_line(self):
        entry = _decode([_row(98, 10, 14), _row(93, 6, 8, mask='a,A,E580')])
        self.assertEqual(entry['non_crit_ranges'], [['10-14']])

    def test_a_steal_alone_is_the_hit(self):
        entry = _decode([_row(93, 6, 8)])
        self.assertEqual(entry['elements'], ['air'])

    def test_a_steal_token_writes_its_element(self):
        self.assertEqual(_reader().ELEMENT_TOKEN_TO_CONST['steal_air'], 'AIR')


class TheTouchTablesCarryTheStateCopiesAndStealsTests(SimpleTestCase):

    def test_the_needle_and_deadly_attack_hold_their_line_on_a_target_in_a_state(self):
        for version in VERSIONS:
            for spell_id in (NEEDLE, DEADLY_ATTACK):
                spell = _spell(version, spell_id)
                rank = spell.get_effects_digest().non_crit_dams[-1]
                with self.subTest(version=version, spell=spell_id):
                    self.assertEqual(spell.conditional, {1: 'target_in_a_state'})
                    self.assertLess(rank[0].min_dam + rank[0].max_dam, rank[1].min_dam + rank[1].max_dam)

    def test_a_steal_and_its_hit_both_land(self):
        for version in VERSIONS:
            for spell_id, steals in ((SWORD_OF_JUDGMENT, [False, True]), (ASSAULT, [True, False])):
                rank = _spell(version, spell_id).get_effects_digest().non_crit_dams[-1]
                with self.subTest(version=version, spell=spell_id):
                    self.assertEqual([row.steals for row in rank], steals)
