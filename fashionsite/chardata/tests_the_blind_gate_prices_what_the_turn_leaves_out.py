# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The blind gate prices what best_turn leaves out: placed spells, spells it cannot cast, summons that hit."""
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from chardata import weight_tuning as tuning

VERSION = 'dofus3'
LEVEL = 200


def _row(low, high=None):
    return SimpleNamespace(min_dam=low, max_dam=low if high is None else high)


def _entry(spell_id, description, **more):
    return dict({'id': spell_id, 'name': {'en': 'spell %s' % spell_id}, 'description': {'en': description}}, **more)


def _castable(spell_id, cost, alternatives=(), waiting=()):
    return SimpleNamespace(spell_id=spell_id, cost=cost, plain_alternatives=[list(a) for a in alternatives],
                           alternatives=[], waiting_plain=list(waiting))


class TheSummonsThatHitTests(SimpleTestCase):

    def test_a_summon_with_no_rows_in_the_damage_data_is_unpriced(self):
        entries = [_entry(1, 'Summons a biddable Chest that can inflict Water damage and lock.')]
        self.assertEqual(entries, tuning._unpriced_summons(entries, set()))

    def test_a_summon_that_steals_health_is_unpriced(self):
        entries = [_entry(1, 'Summons a Sword that can steal HP in the Neutral element.')]
        self.assertEqual(entries, tuning._unpriced_summons(entries, set()))

    def test_a_summon_that_only_helps_is_priced(self):
        entries = [_entry(1, 'Summons a Totem that gives Dodge and heals the allies around it.')]
        self.assertEqual([], tuning._unpriced_summons(entries, set()))

    def test_a_pushing_summon_is_unpriced(self):
        entries = [_entry(1, 'Summons a Doll.', summon_push=True)]
        self.assertEqual(entries, tuning._unpriced_summons(entries, set()))

    def test_a_spell_the_damage_data_holds_is_priced(self):
        entries = [_entry(1, 'Summons a Bomb that can inflict Fire damage.')]
        self.assertEqual([], tuning._unpriced_summons(entries, {1}))

    def test_a_plain_hit_is_not_a_summon(self):
        entries = [_entry(1, 'Inflicts Earth damage on the target.')]
        self.assertEqual([], tuning._unpriced_summons(entries, set()))


class TheShareOfWhatTheTurnSeesTests(SimpleTestCase):

    def _share(self, castables, spells=(), entries=None):
        reference = {'Cls': entries if entries is not None else [_entry(1, 'Inflicts Fire damage.')]}
        with mock.patch('chardata.spell_reference.get_spell_reference', return_value=reference), \
                mock.patch('chardata.spell_buffs.get_damage_spells_for_version', return_value={'Cls': list(spells)}), \
                mock.patch('chardata.spell_combo.castable_spells', return_value=castables), \
                mock.patch('chardata.spell_combo.Castable', side_effect=lambda spell, level, crit: spell.castable), \
                mock.patch('chardata.spell_combo._chosen_level', return_value=0):
            return tuning.visible_damage_share('Cls', LEVEL, VERSION)

    def _spell(self, spell_id, castable):
        return SimpleNamespace(spell_id=spell_id, casting=True, level_req=(1,), castable=castable)

    def test_a_class_the_turn_casts_whole_is_all_seen(self):
        self.assertEqual(1.0, self._share([_castable(1, 3, [[_row(30)]])]))

    def test_a_placed_spell_the_turn_cannot_cast_is_all_waiting(self):
        trap = _castable(2, 2, waiting=[(_row(20), 'trap')])
        share = self._share([_castable(1, 3, [[_row(30)]])], [self._spell(2, trap)])
        self.assertAlmostEqual(10.0 / (10.0 + 10.0), share)

    def test_the_alternatives_of_a_cast_count_once(self):
        four = [[_row(30)], [_row(30)], [_row(30)], [_row(30)]]
        trap = _castable(2, 2, waiting=[(_row(20), 'trap')])
        share = self._share([_castable(1, 3, four)], [self._spell(2, trap)])
        self.assertAlmostEqual(0.5, share)

    def test_the_rows_that_wait_for_one_trigger_count_once(self):
        elements = [(_row(20), 'trap')] * 4
        share = self._share([_castable(1, 3, [[_row(30)]])], [self._spell(2, _castable(2, 2, waiting=elements))])
        self.assertAlmostEqual(0.5, share)

    def test_the_rows_that_wait_for_other_triggers_add_up(self):
        waiting = [(_row(20), 'trap'), (_row(20), 'pushback')]
        share = self._share([_castable(1, 3, [[_row(30)]])], [self._spell(2, _castable(2, 2, waiting=waiting))])
        self.assertAlmostEqual(10.0 / (10.0 + 20.0), share)

    def test_a_row_that_waits_on_a_cast_spell_is_waiting(self):
        both = _castable(1, 2, [[_row(20)]], waiting=[(_row(20), 'initial_enemy')])
        self.assertAlmostEqual(0.5, self._share([both]))

    def test_a_summon_that_hits_leaves_the_share_unknown(self):
        entries = [_entry(1, 'Inflicts Fire damage.'), _entry(2, 'Summons a Golem that can inflict Fire damage.')]
        self.assertIsNone(self._share([_castable(1, 3, [[_row(30)]])], entries=entries))

    def test_a_class_with_no_reference_has_no_share(self):
        self.assertIsNone(self._share([_castable(1, 3, [[_row(30)]])], entries=[]))

    def test_a_class_with_no_damage_has_no_share(self):
        self.assertIsNone(self._share([_castable(1, 3)]))


class TheShareOfRealClassesTests(SimpleTestCase):

    def test_a_plain_caster_passes_the_gate(self):
        for char_class in ('Iop', 'Cra'):
            self.assertGreaterEqual(tuning.visible_damage_share(char_class, LEVEL, VERSION), tuning.BLIND_SHARE,
                                    char_class)

    def test_a_class_that_lives_on_traps_falls_under_the_gate(self):
        self.assertLess(tuning.visible_damage_share('Sram', LEVEL, VERSION), tuning.BLIND_SHARE)

    def test_a_class_that_lives_on_bombs_and_a_summon_has_no_share(self):
        self.assertIsNone(tuning.visible_damage_share('Rogue', LEVEL, VERSION))
