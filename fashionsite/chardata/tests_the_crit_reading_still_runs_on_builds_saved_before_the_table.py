# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A build saved before the weight table, or after it, still counts as untouched for the crit reading."""
import pickle
from types import SimpleNamespace
from unittest import mock

from django.contrib.auth.models import User
from django.test import RequestFactory, SimpleTestCase, TestCase

from chardata import presets
from chardata.coaching_view import create_build
from chardata.crit_curve import _engine_weighs
from chardata.stats_weights import get_stats_weights, set_stats_weights
from chardata.weight_table import TABLE_STATS, cell_table, engine_weights, override_weight_table, unit_of

VERSION = 'dofus3'
BOXES = {'str'}
SCENARIO_OF = {'balanced': 'plain', 'damage': 'glasscannon'}
FACTOR = 1.5


def _cell(scenario, factor=FACTOR, only=None, only_factor=None):
    """The shipped cell of Iop on earth whose ratios are a multiple of the engine's."""
    engine = engine_weights('Iop', ('str',), scenario, VERSION)
    unit = unit_of(('str',), scenario)
    ratios = {stat: (only_factor if only and stat in only else factor) * engine[stat] / unit for stat in TABLE_STATS}
    return cell_table('Iop', ('str',), scenario, ratios)['cells']['Iop']['str'][scenario]


def _table(**glasscannon):
    return {'cells': {'Iop': {'str': {'plain': _cell('plain'), 'glasscannon': _cell('glasscannon', **glasscannon)}}}}


class TheCritReadingTests(SimpleTestCase):
    """Whichever variant of the engine weights a build holds, the crit reading finds its crit weights untouched."""

    ENGINE = {True: {'ch': 100, 'cridam': 200}, False: {'ch': 111, 'cridam': 222}}

    def _engine_weighs(self, stored):
        char = SimpleNamespace(char_class='Iop', level=200, game_version=VERSION)
        with mock.patch('chardata.crit_curve.get_stats_weights', return_value=stored), \
                mock.patch('chardata.crit_curve.get_standard_weights',
                           side_effect=lambda build, table=True: dict(self.ENGINE[table])):
            return _engine_weighs(char, {'str'})

    def test_the_weights_of_either_variant_count_as_the_engines(self):
        for table in (True, False):
            with self.subTest(table=table):
                self.assertEqual((True, True), self._engine_weighs(dict(self.ENGINE[table])))

    def test_a_crit_weight_of_one_variant_beside_the_critical_damage_of_the_other_still_counts(self):
        self.assertEqual((True, True), self._engine_weighs({'ch': 100, 'cridam': 222}))

    def test_an_edited_critical_damage_weight_is_not_the_engines(self):
        self.assertEqual((True, False), self._engine_weighs({'ch': 111, 'cridam': 5}))

    def test_an_edited_crit_weight_is_not_the_engines_and_nor_is_the_critical_damage_beside_it(self):
        self.assertEqual((False, False), self._engine_weighs({'ch': 7, 'cridam': 222}))

    def test_a_stored_floor_mark_keeps_the_crit_weight_as_the_engines(self):
        self.assertEqual((True, False), self._engine_weighs({'ch': 7, 'ch_before_floor': 100, 'cridam': 5}))

    def test_a_crit_priority_box_weighs_neither(self):
        char = SimpleNamespace(char_class='Iop', level=200, game_version=VERSION)
        for box in ('crit', 'noncrit'):
            with self.subTest(box=box):
                self.assertEqual((False, False), _engine_weighs(char, {'str', box}))


class _Builds(TestCase):

    def setUp(self):
        self.owner = User.objects.create_user('crit', 'crit@test.local', 'pw-42-solid')

    def build(self, table, priority='balanced'):
        request = RequestFactory().post('/')
        request.user = self.owner
        with override_weight_table(VERSION, table):
            char = create_build(request, 'Iop', 200, set(BOXES), VERSION)
            presets.apply_setup_choices(char, set(BOXES), priority=priority, set_minimums=False)
        char.refresh_from_db()
        return char

    def stored(self, char):
        return get_stats_weights(char, persist=False)

    def edit(self, char, **changes):
        weights = dict(self.stored(char), **changes)
        set_stats_weights(char, weights)
        char.refresh_from_db()
        return char


class TheStoredWeightsOfEachGenerationTests(_Builds):

    def test_a_build_saved_after_the_table_holds_the_weights_of_the_table(self):
        for priority, scenario in SCENARIO_OF.items():
            char = self.build(_table(), priority)
            engine = engine_weights('Iop', ('str',), scenario, VERSION)
            with self.subTest(priority=priority):
                self.assertEqual(round(FACTOR * engine['pow']), self.stored(char)['pow'])
                self.assertEqual(engine['ch'], self.stored(char)['ch'])

    def test_a_build_saved_before_the_table_holds_the_engine_weights(self):
        for priority, scenario in SCENARIO_OF.items():
            char = self.build(None, priority)
            engine = engine_weights('Iop', ('str',), scenario, VERSION)
            with self.subTest(priority=priority):
                self.assertEqual(engine['pow'], self.stored(char)['pow'])


class TheCritReadingOfSavedBuildsTests(_Builds):

    def test_a_build_of_either_generation_has_its_crit_weights_counted_as_the_engines(self):
        for saved_with in (None, _table()):
            char = self.build(saved_with)
            for read_with in (None, _table()):
                with self.subTest(saved=saved_with is not None, read=read_with is not None):
                    with override_weight_table(VERSION, read_with):
                        self.assertEqual((True, True), _engine_weighs(char, BOXES))

    def test_an_edited_crit_weight_is_seen_on_a_build_of_either_generation(self):
        for saved_with in (None, _table()):
            char = self.edit(self.build(saved_with), ch=500)
            with self.subTest(saved=saved_with is not None):
                with override_weight_table(VERSION, _table()):
                    self.assertEqual((False, False), _engine_weighs(char, BOXES))

    def test_an_edited_critical_damage_weight_is_seen_on_a_build_of_either_generation(self):
        for saved_with in (None, _table()):
            char = self.edit(self.build(saved_with), cridam=1)
            with self.subTest(saved=saved_with is not None):
                with override_weight_table(VERSION, _table()):
                    self.assertEqual((True, False), _engine_weighs(char, BOXES))


class TheBalancedWeightsOfSavedBuildsTests(_Builds):

    def _plain(self, char, table):
        with override_weight_table(VERSION, table):
            return presets._standard_weights(char, BOXES, table=table is not None)

    def test_an_untouched_priority_build_gives_back_the_balanced_weights_of_its_own_generation(self):
        for saved_with, readers in ((None, (None, _table())), (_table(), (_table(),))):
            char = self.build(saved_with, 'damage')
            expected = self._plain(char, saved_with)
            for read_with in readers:
                with self.subTest(saved=saved_with is not None, read=read_with is not None):
                    with override_weight_table(VERSION, read_with):
                        self.assertEqual(expected, presets.balanced_weights(char, self.stored(char)))

    def test_a_change_of_the_player_is_kept_on_a_build_of_either_generation(self):
        for saved_with in (None, _table()):
            char = self.build(saved_with, 'damage')
            expected = dict(self._plain(char, saved_with))
            expected['vit'] += 7
            edited = self.edit(char, vit=self.stored(char)['vit'] + 7)
            with self.subTest(saved=saved_with is not None):
                with override_weight_table(VERSION, _table()):
                    self.assertEqual(expected, presets.balanced_weights(edited, self.stored(edited)))

    def test_a_build_without_a_priority_gives_its_weights_back(self):
        for saved_with in (None, _table()):
            char = self.build(saved_with)
            with self.subTest(saved=saved_with is not None):
                with override_weight_table(VERSION, _table()):
                    self.assertEqual(self.stored(char), presets.balanced_weights(char, self.stored(char)))


class TheSafeguardDoesNotReadTheTableTests(_Builds):

    def _guarded(self, char, table):
        with override_weight_table(VERSION, table):
            balanced = presets._standard_weights(char, BOXES, table=False)
            return presets.guarded_stats(char, balanced)

    def test_the_guarded_stats_are_the_same_with_and_without_a_table(self):
        char = self.build(None, 'damage')
        without = self._guarded(char, None)
        self.assertIn('ap', without)
        self.assertEqual(without, self._guarded(char, _table()))

    def test_a_stat_the_table_raises_with_the_priority_stays_guarded(self):
        char = self.build(None, 'damage')
        raised = _table(only=('hp', 'vit'), only_factor=3.0)
        self.assertIn('hp', self._guarded(char, None))
        self.assertIn('hp', self._guarded(char, raised))
        self.assertEqual(self._guarded(char, None), self._guarded(char, raised))
