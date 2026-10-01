# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Each version's default_elements table gives every class, at each Quick Start level, the element of its best turn; no door applies it."""
import pickle
from unittest import mock

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase

from chardata import default_elements, presets
from chardata.char_blobs import read_char_blob
from chardata.management.commands import store_default_elements as generator
from chardata.models import Char
from chardata.nl_parser import parse_build_request
from chardata.smart_build import get_standard_weights
from chardata.spell_combo import HpShare, castable_spells
from chardata.version_compat import filter_classes_for_version
from fashionistapulp.dofus_constants import CHARACTER_CLASSES
from fashionistapulp.game_versions import dofus_versions
from fashionistapulp.structure import set_current_game_version

SINGLE_ELEMENTS = set(presets.ELEMENT_DAMAGE)
REBUILT_WHOLE = ('touch', 'retro')
SAMPLED = (('dofus3', 'Xelor'), ('beta', 'Cra'), ('dofus2', 'Ecaflip'), ('dofus3', 'Sacrier'),
           ('dofus2', 'Masqueraider'))
TURN_TOLERANCE = 0.5
REGENERATE = 'py fashionsite/manage.py store_default_elements'


def _table(version):
    return default_elements.default_elements_table(version)


def _entries(version):
    """[(class, level, entry)] of the version's table."""
    return [(char_class, int(level), entry)
            for char_class, by_level in sorted((_table(version).get('classes') or {}).items())
            for level, entry in sorted(by_level.items(), key=lambda item: int(item[0]))]


def _exempt(entry):
    return entry.get('kept_for_heals') or entry.get('held_by')


def _path(version, path):
    return path if version == 'dofus3' else '/%s%s' % (version, path)


class EveryVersionTablePicksTheBestTurnTests(SimpleTestCase):

    def test_every_class_has_one_single_element_at_each_quick_start_level(self):
        for version in dofus_versions():
            with self.subTest(version=version):
                table = _table(version)
                self.assertEqual(version, table.get('game_version'))
                self.assertEqual(list(generator.LEVELS), table.get('levels'))
                classes = table.get('classes') or {}
                self.assertEqual(set(filter_classes_for_version(CHARACTER_CLASSES, version)),
                                 set(classes))
                for char_class, by_level in classes.items():
                    self.assertEqual({str(level) for level in generator.LEVELS}, set(by_level),
                                     char_class)
                    for entry in by_level.values():
                        self.assertIn(entry['element'], SINGLE_ELEMENTS, char_class)

    def test_every_element_is_within_two_percent_of_the_best_turn(self):
        checked = 0
        for version in dofus_versions():
            for char_class, level, entry in _entries(version):
                if _exempt(entry):
                    continue
                turns = entry['turns']
                best = max(turns.values())
                with self.subTest(version=version, char_class=char_class, level=level):
                    if best <= 0:
                        self.assertEqual(presets.CLASS_DEFAULT_ELEMENT[char_class],
                                         entry['element'])
                        continue
                    self.assertGreaterEqual(turns[entry['element']],
                                            (1 - generator.TIE_SHARE) * best)
                    checked += 1
        self.assertGreater(checked, 400)

    def test_the_best_turn_wins_unless_the_element_a_class_has_is_within_two_percent(self):
        turns = {'str': 100.0, 'int': 98.5, 'cha': 90.0, 'agi': 50.0}
        self.assertEqual('int', generator.pick(turns, 'int'))
        self.assertEqual('str', generator.pick(turns, 'cha'))
        self.assertEqual('agi', generator.pick(dict.fromkeys(turns, 0.0), 'agi'))

    def test_a_summary_line_names_the_leader_of_a_class_kept_on_a_tie(self):
        turns = {'str': 100.0, 'int': 98.5, 'cha': 90.0, 'agi': 50.0}
        table = {'game_version': 'retro', 'classes': {'Iop': {
            '100': {'element': 'int', 'turns': turns},
            '150': {'element': 'str', 'turns': turns},
            '180': {'element': 'agi', 'turns': dict.fromkeys(turns, 0.0)},
            '200': {'element': 'str', 'turns': turns}}}}
        stored = {'classes': {'Iop': {'100': {'element': 'int'}, '150': {'element': 'str'},
                                      '180': {'element': 'agi'}, '200': {'element': 'cha'}}}}
        name = generator.element_name
        self.assertEqual(
            ['retro Iop 100: %s, kept on a tie, %s leads' % (name('int'), name('str')),
             'retro Iop 150: %s' % name('str'),
             'retro Iop 180: %s' % name('agi'),
             'retro Iop 200: %s, was %s' % (name('str'), name('cha'))],
            [line.split(' | ')[0] for line in generator.summary_lines(table, stored)])

    def test_the_element_a_class_has_is_the_stored_one_at_that_level(self):
        stored = {'classes': {'Iop': {'100': {'element': 'agi'}}}}
        self.assertEqual('agi', generator.today_element('Iop', stored, 100))
        self.assertEqual(presets.CLASS_DEFAULT_ELEMENT['Iop'],
                         generator.today_element('Iop', stored, 200))
        self.assertEqual(presets.CLASS_DEFAULT_ELEMENT['Iop'],
                         generator.today_element('Iop', {}, 100))
        gear = _table('retro')['gear'][str(generator.TOP_LEVEL)]
        turns = {'str': 100.0, 'int': 98.5, 'cha': 50.0, 'agi': 50.0}
        for today, expected in (('int', 'int'), ('cha', 'str')):
            with self.subTest(today=today):
                self.assertEqual((expected, {}), generator.choose(
                    'retro', 'Iop', generator.TOP_LEVEL, gear, turns, {}, today))


class AHealerKeepsTheCharacteristicOfItsHealsTests(SimpleTestCase):

    def test_the_weights_raise_intelligence_alone_for_heals(self):
        for version in dofus_versions():
            with self.subTest(version=version):
                def weights(aspects):
                    return get_standard_weights(Char(char_class='Eniripsa', level=200,
                                                     game_version=version,
                                                     aspects=pickle.dumps(aspects)))
                plain, healing = weights({'vit'}), weights({'vit', 'heal'})
                self.assertEqual({generator.HEAL_CHARACTERISTIC},
                                 {characteristic for characteristic in presets.ELEMENT_DAMAGE
                                  if healing.get(characteristic, 0)
                                  > plain.get(characteristic, 0)})

    def test_a_class_its_version_weighs_as_a_healer_keeps_intelligence_at_every_level(self):
        healers = 0
        for version in dofus_versions():
            for char_class, level, entry in _entries(version):
                healer = (generator.heal_share(version, char_class)
                          >= generator.HEALER_SHARE)
                with self.subTest(version=version, char_class=char_class, level=level):
                    self.assertEqual(healer, bool(entry.get('kept_for_heals')))
                    if healer:
                        self.assertEqual(generator.HEAL_CHARACTERISTIC, entry['element'])
                        healers += 1
        self.assertGreater(healers, 0)


class NoElementRestsOnRowsTheTurnMisreadsTests(SimpleTestCase):

    def test_every_listed_spell_still_reads_as_listed(self):
        for version in dofus_versions():
            with self.subTest(version=version):
                self.assertEqual([], generator.bad_row_problems(version))

    def test_a_listed_spell_whose_rows_read_right_or_that_nobody_casts_is_reported(self):
        with mock.patch.dict(generator.KNOWN_BAD_ROWS,
                             {'dofus2': {12846: ('a misread', lambda spell: False),
                                         999999999: ('nothing', lambda spell: True)}}):
            problems = generator.bad_row_problems('dofus2')
        self.assertEqual(2, len(problems))
        self.assertIn('Topkaj', problems[0])
        self.assertIn('999999999', problems[1])

    def test_a_held_element_is_kept_off_a_listed_spell_the_best_turn_casts(self):
        held = 0
        for version in dofus_versions():
            for char_class, level, entry in _entries(version):
                if not entry.get('held_by'):
                    continue
                listed = generator.bad_row_reasons(
                    version, castable_spells(char_class, level, version))
                with self.subTest(version=version, char_class=char_class, level=level):
                    self.assertTrue(set(entry['held_by']) <= set(listed))
                    self.assertNotEqual(max(entry['turns'], key=entry['turns'].get),
                                        entry['element'])
                    held += 1
        self.assertEqual(any(generator.KNOWN_BAD_ROWS.values()), held > 0)


class EveryVersionTableIsBuiltOnTodaysInputsTests(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.rebuilt = {version: generator.build(version) for version in REBUILT_WHOLE}
        level = str(generator.TOP_LEVEL)
        cls.sampled = {(version, char_class): generator.level_entry(
            version, char_class, generator.TOP_LEVEL, _table(version)['gear'][level])
            for version, char_class in SAMPLED}

    def test_what_every_turn_reads_is_what_it_was_built_on(self):
        stale = []
        for version in dofus_versions():
            gear = _table(version)['gear']
            for char_class, level, entry in _entries(version):
                if generator.inputs_fingerprint(version, char_class, level,
                                                gear[str(level)]) != entry['inputs']:
                    stale.append('%s %s %d' % (version, char_class, level))
        self.assertEqual([], stale, 'stale default elements, run %s' % REGENERATE)

    def test_the_gear_lines_are_the_ones_the_catalogue_gives(self):
        for version in dofus_versions():
            for level in generator.LEVELS:
                with self.subTest(version=version, level=level):
                    self.assertEqual(generator.gear_line(version, level),
                                     _table(version)['gear'][str(level)],
                                     'stale default elements, run %s' % REGENERATE)

    def _assert_same(self, stored, rebuilt):
        self.assertEqual({key: value for key, value in stored.items() if key != 'turns'},
                         {key: value for key, value in rebuilt.items() if key != 'turns'})
        for element, turn in rebuilt['turns'].items():
            self.assertAlmostEqual(stored['turns'][element], turn, delta=TURN_TOLERANCE,
                                   msg='stale default elements, run %s' % REGENERATE)

    def test_the_turns_are_the_ones_the_evaluator_gives(self):
        for version in REBUILT_WHOLE:
            classes = _table(version)['classes']
            for char_class, by_level in self.rebuilt[version][0]['classes'].items():
                for level, entry in by_level.items():
                    with self.subTest(version=version, char_class=char_class, level=level):
                        self._assert_same(classes[char_class][level], entry)
        for version, char_class in SAMPLED:
            level = str(generator.TOP_LEVEL)
            with self.subTest(version=version, char_class=char_class):
                self._assert_same(_table(version)['classes'][char_class][level],
                                  self.sampled[(version, char_class)][0])

    def test_a_sampled_turn_casts_a_share_of_the_casters_hp(self):
        cast = []
        for (version, char_class), (entry, by_element) in self.sampled.items():
            shares = {spell.name for spell in castable_spells(char_class, generator.TOP_LEVEL,
                                                              version)
                      if any(isinstance(row, HpShare) for alternative in spell.plain_alternatives
                             for row in alternative)}
            cast.extend(name for name in generator.cast_names(by_element[entry['element']])
                        if name in shares)
        self.assertTrue(cast)

    def test_a_pivot_is_cast_by_the_chosen_turn_and_its_removal_raises_no_turn(self):
        table, orders = self.rebuilt['retro']
        pivots = generator._Pivots(table, orders)
        level = str(generator.TOP_LEVEL)
        for char_class, by_level in table['classes'].items():
            entry = by_level[level]
            cast = set(generator.cast_names(
                orders[char_class][generator.TOP_LEVEL][entry['element']]))
            for name, winner, turns in pivots(char_class):
                with self.subTest(char_class=char_class, spell=name):
                    self.assertIn(name, cast)
                    self.assertNotEqual(entry['element'], winner)
                    for element, turn in turns.items():
                        self.assertLessEqual(turn, entry['turns'][element] + TURN_TOLERANCE)

    def test_the_change_lines_name_every_class_level_off_the_shared_element(self):
        for version in REBUILT_WHOLE:
            table, orders = self.rebuilt[version]
            headers = {tuple(line.split(':')[0].split()[1:3])
                       for line in generator.change_lines(table,
                                                          generator._Pivots(table, orders))
                       if not line.startswith(' ')}
            expected = {(char_class, level)
                        for char_class, by_level in table['classes'].items()
                        for level, entry in by_level.items()
                        if entry['element'] != presets.CLASS_DEFAULT_ELEMENT[char_class]
                        or (entry.get('kept_for_heals') and entry['element']
                            != max(entry['turns'], key=entry['turns'].get))
                        or entry.get('held_by')}
            with self.subTest(version=version):
                self.assertTrue(expected)
                self.assertEqual(expected, headers)


class TheTableReaderGivesTheVersionElementTests(SimpleTestCase):

    def test_the_reader_gives_every_class_its_version_element_at_each_level(self):
        for version in dofus_versions():
            for char_class, level, entry in _entries(version):
                with self.subTest(version=version, char_class=char_class, level=level):
                    self.assertEqual(entry['element'],
                                     presets.default_element(char_class, version, level))

    def test_a_level_reads_the_nearest_reference_level_and_the_lower_on_a_tie(self):
        table = {'classes': {'Iop': {'100': {'element': 'agi'}, '150': {'element': 'int'}}}}
        with mock.patch.object(default_elements, 'default_elements_table',
                               lambda version: table):
            for level, expected in ((1, 'agi'), (124, 'agi'), (125, 'agi'), (126, 'int'),
                                    (230, 'int'), (None, 'int')):
                with self.subTest(level=level):
                    self.assertEqual(expected, presets.default_element('Iop', 'retro', level))

    def test_without_a_version_the_shared_element_stays(self):
        for char_class in CHARACTER_CLASSES:
            with self.subTest(char_class=char_class):
                self.assertEqual(presets.CLASS_DEFAULT_ELEMENT[char_class],
                                 presets.default_element(char_class))

    def test_a_class_its_version_table_lacks_takes_the_shared_element(self):
        self.assertEqual(presets.CLASS_DEFAULT_ELEMENT['Forgelance'],
                         presets.default_element('Forgelance', 'dofus2', 200))
        self.assertEqual(presets.CLASS_DEFAULT_ELEMENT['Iop'],
                         presets.default_element('Iop', 'wakfu', 200))

    def test_the_parser_adds_no_table_element_at_any_level(self):
        for version in dofus_versions():
            for char_class, level, entry in _entries(version):
                with self.subTest(version=version, char_class=char_class, level=level):
                    parsed = parse_build_request('%s %d' % (char_class, level), version)
                    self.assertEqual((char_class, level), (parsed['char_class'],
                                                           parsed['level']))
                    self.assertEqual({'glasscannon'}, parsed['aspects'])


def _tables(overrides):
    real = default_elements.default_elements_table
    return lambda version: overrides.get(version) or real(version)


def _patched(version, elements):
    return {'game_version': version,
            'classes': {char_class: {level: {'element': element}
                                     for level, element in by_level.items()}
                        for char_class, by_level in elements.items()}}


class TheDoorsApplyNoVersionTableTests(TestCase):

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')
        owner = User.objects.create_user('default-elements', 'elements@test.local',
                                         'pw-default-elements-3')
        self.client.force_login(owner)

    def _last_build(self):
        return Char.objects.order_by('-id').first()

    def _aspects_of_the_last_build(self):
        char = self._last_build()
        return set(read_char_blob(char.aspects, set(), 'aspects', char))

    def _post(self, version, path, data, expected):
        set_current_game_version(version)
        before = Char.objects.count()
        response = self.client.post(_path(version, path),
                                    {key: value for key, value in data.items()
                                     if value is not None})
        self.assertEqual(expected, response.status_code)
        if expected != 302:
            self.assertEqual(before, Char.objects.count())
            return None
        return self._aspects_of_the_last_build()

    def _quick_start(self, version, char_class, level=200, style='solo_pvm', element='none',
                     expected=302):
        return self._post(version, '/quickstart/', {
            'char_class': char_class, 'char_level': str(level), 'play_style': style,
            'element': element}, expected)

    def _smart_build(self, version, text, element='none', expected=302):
        return self._post(version, '/smartbuild/', {'q': text, 'confirm': '1',
                                                    'element': element}, expected)

    def test_no_door_reads_the_version_table(self):
        def unread(version):
            raise AssertionError('a door read the %s default_elements table' % version)
        with mock.patch.object(default_elements, 'default_elements_table', unread):
            for version in ('retro', 'dofus3'):
                with self.subTest(version=version):
                    self.assertEqual({'glasscannon'}, self._quick_start(version, 'Iop'))
                    self.assertEqual({'glasscannon'}, self._smart_build(version, 'Iop'))
                    self.assertEqual({'glasscannon'},
                                     parse_build_request('Sram 100', version)['aspects'])

    def test_a_patched_table_changes_no_build(self):
        other = {'Iop': 'agi', 'Sram': 'int'}
        for version in ('retro', 'dofus3'):
            patched = _patched(version, {char_class: {'200': element}
                                         for char_class, element in other.items()})
            with mock.patch.object(default_elements, 'default_elements_table',
                                   _tables({version: patched})):
                for char_class in other:
                    with self.subTest(version=version, char_class=char_class):
                        self.assertEqual({'glasscannon', 'cha'},
                                         self._quick_start(version, char_class, element='cha'))
                        self.assertEqual({'glasscannon', 'cha'},
                                         self._smart_build(version, char_class, 'cha'))

    def test_a_post_without_an_element_is_refused(self):
        for version in ('retro', 'dofus3'):
            with self.subTest(version=version):
                self._quick_start(version, 'Iop', element=None, expected=400)
                self._quick_start(version, 'Iop', element='fire', expected=400)
                self._smart_build(version, 'Iop 150', None, expected=400)

    def test_a_class_its_version_lacks_is_built_without_an_element(self):
        built = presets.version_class('Rogue', 'retro')
        self.assertNotEqual('Rogue', built)
        self.assertEqual({'glasscannon'}, self._quick_start('retro', 'Rogue'))
        self.assertEqual(built, self._last_build().char_class)
        self.assertEqual({'glasscannon'}, self._smart_build('retro', 'Roublard'))
        self.assertEqual(built, self._last_build().char_class)

    def test_a_quick_start_healer_on_intelligence_values_its_heals(self):
        for level in generator.LEVELS:
            with self.subTest(level=level):
                self._quick_start('retro', 'Eniripsa', level, 'group_pvm',
                                  generator.HEAL_CHARACTERISTIC)
                char = self._last_build()
                weights = read_char_blob(char.stats_weight, {}, 'stats_weight', char)
                self.assertGreater(weights.get('heals', 0), 0)
                self.assertGreater(weights.get(generator.HEAL_CHARACTERISTIC, 0), 0)

    def test_the_setup_page_adds_no_element_to_the_boxes_ticked(self):
        for version in dofus_versions():
            with self.subTest(version=version):
                set_current_game_version(version)
                response = self.client.post(_path(version, '/createproject/'), {
                    'project': 'p', 'charname': '', 'class': 'Iop', 'level': '200',
                    'wizard': 'wizard', 'check_vit': 'on'})
                self.assertEqual(302, response.status_code)
                self.assertEqual({'vit'}, self._aspects_of_the_last_build())
