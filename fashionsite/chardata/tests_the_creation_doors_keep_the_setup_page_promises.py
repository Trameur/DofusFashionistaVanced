# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Every door gets the setup page's minimums and damage weights; the server checks the boxes it offers."""
import json
import os
import pickle
import re
import shutil
import subprocess
import tempfile
from collections import namedtuple
from unittest import mock

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase
from django.utils import translation

from chardata import presets
from chardata.char_blobs import read_char_blob
from chardata.coaching_view import included_set_for
from chardata.gallery_visibility import refusal_reason
from chardata.models import Char
from chardata.nl_parser import parse_build_request
from chardata.smart_build import get_standard_weights, level_minimums
from chardata.solution import get_solution
from fashionistapulp.dofus_constants import CHARACTER_CLASSES
from fashionistapulp.structure import get_structure, set_current_game_version

DAMAGE_WEIGHTS = ('pow', 'dam', 'earthdam', 'firedam', 'waterdam', 'airdam', 'neutdam')
OTHER_ELEMENT_STATS = ('int', 'cha', 'agi', 'firedam', 'waterdam', 'airdam')


def _path(version, path):
    return path if version == 'dofus3' else '/%s%s' % (version, path)


def _solver_available():
    try:
        import pulp
        return bool(pulp.listSolvers(onlyAvailable=True))
    except Exception:
        return False


class _DoorMixin(object):

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')
        self.owner = User.objects.create_user('setup-promises', 'promises@test.local',
                                              'pw-setup-promises-9')
        self.client.force_login(self.owner)

    def last_char(self):
        return Char.objects.order_by('-id').first()

    def blob(self, char, field, default):
        return read_char_blob(getattr(char, field), default, field, char)

    def setup_page(self, version, char_class, level, aspects, button='wizard', expected=302):
        set_current_game_version(version)
        data = {'project': 'p', 'charname': '', 'class': char_class, 'level': str(level),
                button: button}
        data.update(('check_%s' % aspect, 'on') for aspect in aspects)
        before = Char.objects.count()
        response = self.client.post(_path(version, '/createproject/'), data)
        self.assertEqual(expected, response.status_code)
        if expected != 302:
            self.assertEqual(before, Char.objects.count())
            return None
        return self.last_char()


class EveryDoorSeedsTheSetupPageMinimumsTests(_DoorMixin, TestCase):

    def test_the_quick_start_stores_what_the_setup_wizard_stores(self):
        for version, char_class, level, style in (('dofus3', 'Iop', 200, 'solo_pvm'),
                                                  ('retro', 'Cra', 100, 'pvp'),
                                                  ('touch', 'Osamodas', 150, 'group_pvm'),
                                                  ('dofus2', 'Enutrof', 200, 'farm')):
            with self.subTest(version=version, style=style):
                set_current_game_version(version)
                self.client.post(_path(version, '/quickstart/'), {
                    'char_class': char_class, 'char_level': str(level), 'play_style': style})
                quick = self.last_char()
                page = self.setup_page(version, char_class, level,
                                       presets.style_aspects(style, char_class))
                self.assertEqual(self.blob(page, 'minimum_stats', {}),
                                 self.blob(quick, 'minimum_stats', {}))
                self.assertTrue(self.blob(quick, 'minimum_stats', {}))

    def test_the_smart_build_stores_the_level_minimums_of_its_aspects(self):
        set_current_game_version('beta')
        self.client.post('/beta/smartbuild/', {'q': 'Sram agi pvp level 150', 'confirm': '1'})
        char = self.last_char()
        aspects = self.blob(char, 'aspects', set())
        self.assertEqual(level_minimums(char, aspects), self.blob(char, 'minimum_stats', {}))
        self.assertEqual({'AP': 9, 'MP': 5}, {key: self.blob(char, 'minimum_stats', {})[key]
                                              for key in ('AP', 'MP')})

    def test_a_farm_build_asks_no_ap_mp_or_range(self):
        self.client.post('/quickstart/', {'char_class': 'Enutrof', 'char_level': '200',
                                          'play_style': 'farm'})
        minimums = self.blob(self.last_char(), 'minimum_stats', {})
        self.assertEqual((0, 0, 0), (minimums['AP'], minimums['MP'], minimums['Range']))


def _lowest_set(version, pieces=6):
    found = []
    for set_id in get_structure(version).sets_dict:
        info = included_set_for(version, str(set_id), 'en')
        if info is not None and len(info['pieces']) >= pieces:
            found.append((info['level'], set_id))
    return min(found)[1]


class AQuickStartAroundGearKeepsItSolvableTests(_DoorMixin, TestCase):

    def quick_start_around_a_set(self, version):
        set_current_game_version(version)
        response = self.client.post(_path(version, '/quickstart/'), {
            'char_class': 'Iop', 'char_level': '200', 'play_style': 'solo_pvm',
            'set': str(_lowest_set(version))})
        self.assertEqual(302, response.status_code)
        return self.last_char()

    def test_a_locked_set_seeds_no_minimum(self):
        for version in ('dofus3', 'retro'):
            with self.subTest(version=version):
                char = self.quick_start_around_a_set(version)
                self.assertGreaterEqual(len(self.blob(char, 'inclusions', {})), 6)
                self.assertEqual({}, self.blob(char, 'minimum_stats', {}))

    def test_a_locked_item_seeds_no_minimum(self):
        structure = get_structure('dofus3')
        hat = next(item for item in structure.types[200]['Hat'] if not item.removed)
        self.client.post('/quickstart/', {'char_class': 'Iop', 'char_level': '200',
                                          'play_style': 'solo_pvm', 'item': str(hat.id)})
        char = self.last_char()
        self.assertEqual(hat.id, self.blob(char, 'inclusions', {}).get('hat'))
        self.assertEqual({}, self.blob(char, 'minimum_stats', {}))

    def test_a_retro_set_locked_at_level_200_still_solves(self):
        if not _solver_available():
            self.skipTest('no pulp solver available')
        char = self.quick_start_around_a_set('retro')
        response = self.client.get('/retro/fashion/%d/' % char.id)
        self.assertNotIn('infeasible', response.get('Location', ''))
        char.refresh_from_db()
        self.assertTrue(char.minimal_solution)


class TheFarmStyleWeighsWisdomTests(_DoorMixin, TestCase):

    def test_farm_weighs_prospecting_and_wisdom_on_every_version(self):
        for version in presets.VERSION_PRESETS:
            with self.subTest(version=version):
                set_current_game_version(version)
                self.client.post(_path(version, '/quickstart/'), {
                    'char_class': 'Enutrof', 'char_level': '200', 'play_style': 'farm'})
                weights = self.blob(self.last_char(), 'stats_weight', {})
                self.assertGreater(weights['wis'], 0)
                self.assertGreater(weights['pp'], 0)

    def test_a_pods_mule_still_ignores_wisdom(self):
        char = self.setup_page('dofus3', 'Iop', 200, {'pods'})
        self.assertEqual(0, self.blob(char, 'stats_weight', {})['wis'])

    def test_a_prospecting_mule_still_ignores_wisdom(self):
        char = self.setup_page('retro', 'Enutrof', 100, {'pp'})
        self.assertEqual(0, self.blob(char, 'stats_weight', {})['wis'])

    def test_the_setup_page_weighs_wisdom_next_to_prospecting_or_pods(self):
        for version in presets.VERSION_PRESETS:
            for boxes, kept in (({'wis', 'pp'}, 'pp'), ({'wis', 'pods'}, 'pod')):
                with self.subTest(version=version, boxes=sorted(boxes)):
                    char = self.setup_page(version, 'Enutrof', 200, boxes)
                    weights = self.blob(char, 'stats_weight', {})
                    self.assertGreater(weights['wis'], 0)
                    self.assertGreater(weights[kept], 0)
                    self.assertEqual([0] * len(DAMAGE_WEIGHTS),
                                     [weights[key] for key in DAMAGE_WEIGHTS])
                    self.assertEqual(0, self.blob(char, 'minimum_stats', {})['AP'])


class TheFocusLimitHoldsOnTheServerTests(_DoorMixin, TestCase):

    def test_creating_with_three_focus_boxes_is_refused(self):
        response_char = self.setup_page('dofus3', 'Iop', 200, {'str', 'vit', 'res', 'dam'},
                                        expected=400)
        self.assertIsNone(response_char)

    def test_two_focus_boxes_and_both_option_boxes_are_accepted(self):
        char = self.setup_page('dofus3', 'Iop', 200, {'str', 'pvp', 'duel', 'vit', 'res'})
        self.assertEqual({'str', 'pvp', 'duel', 'vit', 'res'}, self.blob(char, 'aspects', set()))

    def test_saving_with_three_focus_boxes_changes_nothing(self):
        char = self.setup_page('dofus3', 'Iop', 200, {'str', 'vit'})
        stored = (char.aspects, char.stats_weight, char.minimum_stats, char.level)
        response = self.client.post('/saveproject/%d/' % char.id, {
            'project': 'p', 'charname': '', 'class': 'Iop', 'level': '150',
            'check_str': 'on', 'check_vit': 'on', 'check_res': 'on', 'check_heal': 'on',
            'reapply': 'reapply'})
        self.assertEqual(400, response.status_code)
        char.refresh_from_db()
        self.assertEqual(stored, (char.aspects, char.stats_weight, char.minimum_stats,
                                  char.level))

    def test_saving_without_the_wizard_keeps_the_weights_and_minimums(self):
        char = self.setup_page('dofus3', 'Iop', 200, {'str'})
        stored = (char.stats_weight, char.minimum_stats)
        response = self.client.post('/saveproject/%d/' % char.id, {
            'project': 'p', 'charname': '', 'class': 'Iop', 'level': '200',
            'check_int': 'on'})
        self.assertEqual(200, response.status_code)
        char.refresh_from_db()
        self.assertEqual(stored, (char.stats_weight, char.minimum_stats))

    def test_the_smart_build_keeps_the_first_two_focus_words_typed(self):
        parsed = parse_build_request('Sram heal summon traps')
        self.assertEqual({'heal', 'summon'}, presets.focus_boxes(parsed['aspects']))
        parsed = parse_build_request('Sram traps summon heal')
        self.assertEqual({'trap', 'summon'}, presets.focus_boxes(parsed['aspects']))

    def test_the_smart_build_drops_its_style_boxes_before_the_words_typed(self):
        parsed = parse_build_request('Feca vitality resistance 50')
        self.assertEqual({'int', 'vit', 'res'}, parsed['aspects'])

    def test_every_parsed_request_stays_within_the_limit(self):
        for phrase in ('Eniripsa fire healer summon', 'Xelor crit pvp trap pushback',
                       'Enutrof farm drop pods wisdom', 'Iop'):
            with self.subTest(phrase=phrase):
                self.assertTrue(presets.within_focus_limit(parse_build_request(phrase)['aspects']))


class TheDoorsReadTheBoxesTheirVersionListsTests(_DoorMixin, TestCase):

    def test_an_option_box_the_version_does_not_list_is_ignored(self):
        touch = {'styles': ('solo_pvm', 'group_pvm', 'pvp', 'farm'), 'option_boxes': ('pvp',)}
        with mock.patch.dict(presets.VERSION_PRESETS, {'touch': touch}):
            char = self.setup_page('touch', 'Iop', 200, {'str', 'pvp', 'duel'})
            self.assertEqual({'str', 'pvp'}, self.blob(char, 'aspects', set()))
            self.client.post('/touch/saveproject/%d/' % char.id, {
                'project': 'p', 'charname': '', 'class': 'Iop', 'level': '200',
                'check_int': 'on', 'check_duel': 'on', 'reapply': 'reapply'})
        char.refresh_from_db()
        self.assertEqual({'int'}, self.blob(char, 'aspects', set()))

    def test_the_gallery_lays_out_the_setup_columns(self):
        touch = {'styles': ('solo_pvm',), 'option_boxes': ('duel',)}
        with mock.patch.dict(presets.VERSION_PRESETS, {'touch': touch}):
            set_current_game_version('touch')
            page = self.client.get('/touch/sharedbuilds/').content.decode('utf-8')
            expected = presets.setup_columns('touch')
        layout = json.loads(re.search(r'var aspectLayout = (.*?);', page).group(1))
        self.assertEqual(expected, layout)
        self.assertEqual(['duel'], layout[1])

    def test_the_smart_build_only_uses_a_style_its_version_offers(self):
        retro = {'styles': ('solo_pvm', 'pvp'), 'option_boxes': ('pvp', 'duel')}
        with mock.patch.dict(presets.VERSION_PRESETS, {'retro': retro}):
            set_current_game_version('retro')
            self.client.post('/retro/smartbuild/', {'q': 'Enutrof farm level 100',
                                                    'confirm': '1'})
        self.assertEqual(presets.style_aspects('solo_pvm', 'Enutrof'),
                         self.blob(self.last_char(), 'aspects', set()))


FakeStat = namedtuple('FakeStat', 'id')
FakeItem = namedtuple('FakeItem', 'stats')


class _FakeStructure(object):
    KEYS = ('str', 'int', 'cha', 'agi', 'earthdam', 'firedam', 'waterdam', 'airdam', 'neutdam',
            'vit')

    def __init__(self, items):
        self.stat_dict_key = {key: FakeStat(number) for number, key in enumerate(self.KEYS)}
        self.items = {item_id: FakeItem([(self.stat_dict_key[key].id, value)
                                         for key, value in stats.items()])
                      for item_id, stats in items.items()}

    def get_item_by_id(self, item_id):
        return self.items.get(item_id)


class AnImportWeighsTheElementsItsGearCarriesTests(_DoorMixin, TestCase):

    def elements(self, items, overrides=None):
        structure = _FakeStructure(items)
        return presets.gear_elements(structure, list(items), 'Iop', 200, 'dofus3', overrides)

    def test_a_main_element_with_a_small_second_one_is_mono(self):
        self.assertEqual({'str'}, self.elements({1: {'str': 300}, 2: {'agi': 60, 'vit': 400}}))

    def test_a_second_element_with_half_the_points_counts(self):
        self.assertEqual({'str', 'agi'}, self.elements({1: {'str': 300}, 2: {'agi': 150}}))

    def test_elemental_damage_counts_for_its_element(self):
        self.assertEqual({'int'}, self.elements({1: {'firedam': 30, 'str': 40}}))
        self.assertEqual({'str'}, self.elements({1: {'neutdam': 20}}))

    def test_a_third_element_is_left_out_unless_all_four_count(self):
        self.assertEqual({'str', 'int'},
                         self.elements({1: {'str': 300, 'int': 200}, 2: {'agi': 160}}))

    def test_four_elements_add_the_multi_element_box(self):
        self.assertEqual({'str', 'int', 'cha', 'agi', 'omni'},
                         self.elements({1: {'str': 100, 'int': 90, 'cha': 80, 'agi': 70}}))

    def test_a_roll_replaces_the_catalogue_value(self):
        structure = _FakeStructure({1: {'str': 100}, 2: {'agi': 80}})
        overrides = {1: {structure.stat_dict_key['str'].id: 10}}
        self.assertEqual({'agi'}, presets.gear_elements(structure, [1, 2], 'Iop', 200, 'dofus3',
                                                        overrides))

    def test_gear_without_an_element_gives_none(self):
        self.assertEqual(set(), self.elements({1: {'vit': 400}, 2: {'str': -20}}))
        self.assertEqual(set(), self.elements({}))

    def test_retro_counts_characteristics_only(self):
        for char_class in CHARACTER_CLASSES:
            with self.subTest(char_class=char_class):
                points = presets.element_stat_points(char_class, 200, 'retro')
                self.assertEqual({0}, {rate for stats in points.values()
                                       for stat, rate in stats.items() if stat.endswith('dam')})
                self.assertGreater(presets.element_stat_points(char_class, 200,
                                                               'dofus3')['str']['earthdam'], 0)

    def test_touch_reads_its_own_class_rates(self):
        self.assertTrue(any(presets.element_stat_points(char_class, 200, 'touch')
                            != presets.element_stat_points(char_class, 200, 'dofus3')
                            for char_class in CHARACTER_CLASSES))

    def import_strength_pieces(self, level):
        structure = get_structure('dofus3')
        ids = {structure.stat_dict_key[key].id: key for key in OTHER_ELEMENT_STATS}
        strength = structure.stat_dict_key['str'].id
        names = []
        for type_name in ('Hat', 'Belt'):
            item = next(item for item in structure.types[level][type_name]
                        if not item.removed and item.level <= level
                        and dict(item.stats).get(strength, 0) >= 10
                        and not any(value > 0 and stat in ids for stat, value in item.stats))
            names.append(structure.get_item_name_in_language(item, 'en'))
        set_current_game_version('dofus3')
        with translation.override('en'):
            response = self.client.post('/import/text/', {
                'text': '\n'.join(names), 'confirm': '1', 'char_class': 'Sacrier',
                'level': str(level)})
        self.assertEqual(302, response.status_code)
        return self.last_char()

    def test_an_imported_strength_set_weighs_earth_damage(self):
        char = self.import_strength_pieces(200)
        self.assertEqual({'str'}, self.blob(char, 'aspects', set()))
        weights = self.blob(char, 'stats_weight', {})
        self.assertGreater(weights['earthdam'], 0)
        self.assertEqual(0, weights['firedam'])
        self.assertEqual(get_standard_weights(char), weights)

    def test_an_imported_set_stores_the_level_minimums(self):
        for level in (50, 200):
            with self.subTest(level=level):
                char = self.import_strength_pieces(level)
                self.assertEqual(level_minimums(char, {'str'}),
                                 self.blob(char, 'minimum_stats', {}))

    def test_only_a_solved_set_is_hidden_for_missing_its_minimums(self):
        char = self.import_strength_pieces(200)
        self.assertLess(get_solution(char).get_stats_total()['ap'],
                        self.blob(char, 'minimum_stats', {})['AP'])
        char.owner = self.owner
        char.link_shared = True
        char.save()
        self.assertIsNone(refusal_reason(char))
        solution = self.blob(char, 'minimal_solution', None)
        solution.input['origin'] = 'generated'
        char.minimal_solution = pickle.dumps(solution)
        char.save()
        cache.clear()
        self.assertEqual('conditions', refusal_reason(char))


SOLVED_SETS = (
    ('dofus3', 'Eniripsa', ('str',),
     (33268, 14076, 14077, 14078, 15430, 17997, 17998, 18018, 19983, 20286, 20357, 22024, 694,
      7043, 7115, 7754)),
    ('dofus3', 'Xelor', ('str', 'int'),
     (13465, 14092, 14093, 15432, 15433, 15440, 15442, 18718, 19591, 20286, 22004, 31787, 694,
      6980, 7043, 7754)),
    ('beta', 'Osamodas', ('str',),
     (33268, 13774, 14076, 14077, 14078, 17997, 17998, 18018, 19246, 20286, 20357, 22024, 22429,
      694, 7043, 7115)),
    ('beta', 'Pandawa', ('str', 'int'),
     (13465, 14092, 14093, 15432, 15433, 15440, 15442, 18718, 20286, 22004, 22412, 26066, 31787,
      694, 6980, 7043)),
    ('dofus2', 'Ecaflip', ('str',),
     (11955, 12747, 13344, 13759, 13774, 14076, 14077, 14078, 14168, 20357, 22205, 22209, 24029,
      24031, 7043, 7754)),
    ('dofus2', 'Eniripsa', ('str', 'int'),
     (13465, 12114, 13344, 13774, 13780, 14091, 14092, 14093, 15431, 15432, 18703, 19591, 27644,
      694, 6980, 7043)),
    ('touch', 'Cra', ('str',),
     (12747, 13114, 13115, 13116, 13344, 13774, 14168, 15965, 16226, 16344, 16394, 17808, 19135,
      19137, 7043, 7754)),
    ('touch', 'Osamodas', ('str', 'int'),
     (12114, 13344, 13774, 13780, 14131, 14595, 15740, 15741, 17808, 12177, 21611, 21613, 21615,
      21621, 694, 7043)),
    ('retro', 'Feca', ('str',),
     (12827, 694, 6980, 7114, 739, 7754, 8876, 8877, 8991, 9117, 9140, 9146, 9461, 9464, 972)),
    ('retro', 'Ecaflip', ('str', 'int'),
     (11547, 12827, 694, 6980, 7114, 739, 7680, 7754, 8876, 8877, 8991, 9117, 9146, 9464, 972)),
)


class ASolvedSetReadsBackAsTheElementsItWasBuiltForTests(SimpleTestCase):

    def test_every_set_keeps_its_elements(self):
        for version, char_class, elements, ankama_ids in SOLVED_SETS:
            with self.subTest(version=version, elements=elements):
                structure = get_structure(version)
                items = [structure.get_item_by_ankama_id(ankama_id) for ankama_id in ankama_ids]
                self.assertEqual([], [ankama_id for ankama_id, item in zip(ankama_ids, items)
                                      if item is None])
                self.assertEqual(set(elements), presets.gear_elements(
                    structure, [item.id for item in items], char_class, 200, version))


class TheSetupPageSaysWhatTheWeightsDoTests(_DoorMixin, TestCase):

    def page(self):
        with translation.override('en'):
            return self.client.get('/setup/').content.decode('utf-8')

    def test_every_box_carries_one_name(self):
        body = re.search(r'function createCheckbox\(.*?\n}', self.page(), re.S).group(0)
        self.assertEqual(1, body.count('name='))

    def test_no_tooltip_promises_what_the_weights_do_not_do(self):
        page = self.page()
        for claim in ('Enables shields', 'will hurt the other stats', 'all-around build',
                      'Disables trophies and Dofus'):
            with self.subTest(claim=claim):
                self.assertNotIn(claim, page)

    def test_the_vitality_box_sets_the_same_weight_for_every_class(self):
        for char_class in ('Iop', 'Sacrier', 'Cra'):
            with self.subTest(char_class=char_class):
                char = self.setup_page('retro', char_class, 200, {'str', 'vit'})
                self.assertEqual(30, self.blob(char, 'stats_weight', {})['vit'])

    def test_the_leech_box_keeps_only_the_cawwot_unless_prospecting_without_element(self):
        for aspects, dofus in (({'wis'}, 'cawwot'), ({'str', 'wis'}, 'cawwot'),
                               ({'wis', 'pp'}, True), ({'str', 'wis', 'pp'}, 'cawwot')):
            with self.subTest(aspects=sorted(aspects)):
                char = self.setup_page('dofus3', 'Iop', 200, aspects)
                self.assertEqual(dofus, self.blob(char, 'options', {}).get('dofus', True))

    def test_the_page_warns_before_a_build_without_any_damage(self):
        page = self.page()
        self.assertIn('id="no-element-warning"', page)
        char = self.setup_page('dofus3', 'Iop', 200, {'vit'})
        weights = self.blob(char, 'stats_weight', {})
        self.assertEqual([0] * len(DAMAGE_WEIGHTS), [weights[key] for key in DAMAGE_WEIGHTS])


_SCRIPT_FUNCTIONS = ('flashRed', 'highlightAspectRules', 'lacksElement', 'warnOnceWithoutElement',
                     'forgetNoElementWarning', 'areAspectsValid', 'checkAndSubmit',
                     'saveButtonClicked')

_JQUERY_STUB = r"""
var checked = {}, shown = {};
function $(selector) {
    var id = selector.replace('#', '');
    return {
        prop: function(name, value) {
            if (value === undefined) { return !!checked[id]; }
            checked[id] = value;
            return this;
        },
        show: function() { shown[id] = true; return this; },
        hide: function() { shown[id] = false; return this; },
        addClass: function() { return this; },
        removeClass: function() { return this; },
        serialize: function() { return 'form'; }
    };
}
$.each = function(list, callback) {
    for (var i = 0; i < list.length; i++) { callback(i, list[i]); }
};
function setTimeout() {}
"""


class TheNoElementWarningRunsUnderNodeTests(_DoorMixin, TestCase):

    def run_page_script(self, body):
        node = shutil.which('node')
        if node is None:
            self.skipTest('node is not installed')
        with translation.override('en'):
            page = self.client.get('/setup/').content.decode('utf-8')
        parts = [_JQUERY_STUB,
                 re.search(r'var inertAspects = .*?(?=\nfunction )', page, re.S).group(0),
                 'var noElementWarned = false;']
        for name in _SCRIPT_FUNCTIONS:
            parts.append(re.search(r'function %s\(.*?\n\}' % name, page, re.S).group(0))
        parts.append('console.log(JSON.stringify((function() {%s})()));' % body)
        with tempfile.NamedTemporaryFile('w', suffix='.js', encoding='utf-8',
                                         delete=False) as handle:
            handle.write('\n'.join(parts))
            name = handle.name
        try:
            done = subprocess.run([node, name], capture_output=True, text=True)
        finally:
            os.unlink(name)
        self.assertEqual(0, done.returncode, done.stderr[-800:])
        return json.loads(done.stdout)

    def test_the_first_click_warns_and_the_second_one_submits(self):
        self.assertEqual([False, True, True], self.run_page_script(
            'var first = checkAndSubmit();'
            'return [first, shown["no-element-warning"], checkAndSubmit()];'))

    def test_an_element_or_a_farm_box_submits_at_once(self):
        for box in presets.ELEMENT_BOXES + ('wis', 'pp', 'pods'):
            with self.subTest(box=box):
                self.assertEqual([True, False], self.run_page_script(
                    'checked["check_%s"] = true;'
                    'return [checkAndSubmit(), !!shown["no-element-warning"]];' % box))

    def test_the_focus_limit_is_checked_before_the_warning(self):
        self.assertEqual([False, False], self.run_page_script(
            'checked["check_vit"] = checked["check_res"] = checked["check_dam"] = true;'
            'return [checkAndSubmit(), !!shown["no-element-warning"]];'))

    def test_saving_warns_only_when_the_wizard_restarts(self):
        self.assertEqual(['form', None, 'form'], self.run_page_script(
            'var kept = saveButtonClicked();'
            'checked["reapply-cb"] = true;'
            'return [kept, saveButtonClicked(), saveButtonClicked()];'))

    def test_forgetting_the_warning_hides_it_and_warns_again_next_time(self):
        self.assertEqual([False, False], self.run_page_script(
            'checkAndSubmit();'
            'forgetNoElementWarning();'
            'return [!!shown["no-element-warning"], checkAndSubmit()];'))

    def test_discarding_changes_forgets_the_warning(self):
        with translation.override('en'):
            page = self.client.get('/setup/').content.decode('utf-8')
        handler = re.search(r'#button-discard-changes"\)\.click\(function\(\) \{(.*?)\n    \}\);',
                            page, re.S).group(1)
        self.assertIn('forgetNoElementWarning();', handler)


class TheNewSetupSentencesAreTranslatedTests(SimpleTestCase):

    SENTENCES = (
        'No element checked: the build will not look for any damage. Click again to continue '
        'anyway.',
        'Check at most %(limit)d boxes in the focus column.',
        '1 vs. 1 duelers should check this. Increases importance of initiative a lot.',
        'No focus: every stat keeps its usual importance. Checking another box in this column '
        'unchecks this one.',
        'Support and vitality based characters should check this. Vitality gets the same high '
        'importance for every class, and the other stats keep theirs.',
        'Only leechers should check this. Wisdom becomes very important and, through the '
        'wizard, the Cawwot becomes the only Dofus allowed, with no trophy, unless Prospecting '
        'or Pods is checked without an element. Without an element, the other stats get almost '
        'no importance and there is no AP, MP or Range minimum.',
    )

    def test_every_language_has_its_own_wording(self):
        for language in ('fr', 'es', 'pt', 'de'):
            for sentence in self.SENTENCES:
                with self.subTest(language=language, sentence=sentence[:30]):
                    with translation.override(language):
                        self.assertNotEqual(sentence, translation.gettext(sentence))

    def test_the_limit_is_filled_in_every_language(self):
        for language in ('en', 'fr', 'es', 'pt', 'de'):
            with translation.override(language):
                text = translation.gettext(self.SENTENCES[1]) % {'limit': presets.FOCUS_LIMIT}
            self.assertIn(str(presets.FOCUS_LIMIT), text)
