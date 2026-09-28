# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The quick start and the Smart Build ask for the element, preselect none and build nothing without one."""
import re

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase

from chardata import presets
from chardata.char_blobs import read_char_blob
from chardata.models import Char
from chardata.smart_build import mule_stats
from fashionistapulp.dofus_constants import NON_STAT_WEIGHT_KEYS
from fashionistapulp.structure import get_structure, set_current_game_version

VERSIONS = ('dofus3', 'beta', 'dofus2', 'touch', 'retro')
CHOICES = ['str', 'int', 'cha', 'agi', 'omni', 'none']
REFUSAL = 'Pick an element for this build.'


def _path(version, path):
    return path if version == 'dofus3' else '/%s%s' % (version, path)


def _select(page, name):
    """(opening tag, [(value, selected, disabled)]) of the page's select, (None, []) without one."""
    match = re.search(r'(<select[^>]*name="?%s"?[^>]*>)(.*?)</select>' % name, page, re.S)
    if match is None:
        return None, []
    return match.group(1), [(re.search(r'value="?([\w-]*)"?', tag).group(1),
                             ' selected' in tag, ' disabled' in tag)
                            for tag in re.findall(r'<option[^>]*>', match.group(2))]


def _selected(page, name):
    return [value for value, selected, _disabled in _select(page, name)[1] if selected]


class AnElementChoiceIsOneOfTheListTests(SimpleTestCase):

    def test_each_choice_ticks_its_box_and_none_ticks_nothing(self):
        for element in CHOICES:
            with self.subTest(element=element):
                self.assertEqual(set() if element == 'none' else {element},
                                 presets.element_aspects(element))
        self.assertEqual(set(), presets.element_aspects(None))

    def test_anything_else_is_refused_not_ticked(self):
        for element in ('Iop', 'fire', '', 'wis', 'glasscannon'):
            with self.subTest(element=element):
                self.assertIsNone(presets.offered_element(element))
                with self.assertRaises(ValueError):
                    presets.element_aspects(element)
                with self.assertRaises(ValueError):
                    presets.style_aspects('solo_pvm', element)


class _DoorMixin(object):

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')
        owner = User.objects.create_user('element-choice', 'element@test.local',
                                         'pw-element-choice-4')
        self.client.force_login(owner)

    def post(self, version, path, data, expected=302):
        set_current_game_version(version)
        before = Char.objects.count()
        response = self.client.post(_path(version, path), data, HTTP_ACCEPT_LANGUAGE='en')
        self.assertEqual(expected, response.status_code)
        if expected != 302:
            self.assertEqual(before, Char.objects.count())
        return response

    def last_build(self):
        char = Char.objects.order_by('-id').first()
        return {field: read_char_blob(getattr(char, field), default, field, char)
                for field, default in (('aspects', set()), ('stats_weight', {}),
                                       ('minimum_stats', {}))}


class TheQuickStartAsksForTheElementTests(_DoorMixin, TestCase):

    def quick_start(self, element, style='solo_pvm', version='dofus3', expected=302, **extra):
        data = dict({'char_class': 'Sram', 'char_level': '150', 'play_style': style}, **extra)
        if element is not None:
            data['element'] = element
        return self.post(version, '/quickstart/', data, expected)

    def test_the_page_lists_every_element_and_none_and_preselects_nothing(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                set_current_game_version(version)
                page = self.client.get(_path(version, '/quickstart/')).content.decode('utf-8')
                tag, options = _select(page, 'element')
                self.assertIn(' required', tag)
                self.assertEqual(('', True, True), options[0])
                self.assertEqual(CHOICES, [value for value, _s, _d in options[1:]])
                self.assertEqual([''], _selected(page, 'element'))

    def test_a_post_without_an_element_builds_nothing_and_says_why(self):
        for element in (None, '', 'fire', 'str,int'):
            with self.subTest(element=element):
                page = self.quick_start(element, 'pvp', expected=400).content.decode('utf-8')
                self.assertIn(REFUSAL, page)
                self.assertEqual(['Sram'], _selected(page, 'char_class'))
                self.assertEqual(['150'], _selected(page, 'char_level'))
                self.assertEqual(['pvp'], _selected(page, 'play_style'))
                self.assertEqual([''], _selected(page, 'element'))

    def test_a_refused_post_keeps_the_item_it_was_started_for(self):
        structure = get_structure('dofus3')
        hat = next(item for item in structure.types[100]['Hat'] if not item.removed)
        page = self.quick_start(None, expected=400, item=str(hat.id)).content.decode('utf-8')
        self.assertIn('id="coaching-included-item"', page)
        self.assertRegex(page, r'<input[^>]*name="?item"?[^>]*value="?%d"?' % hat.id)

    def test_the_build_gets_the_element_picked_and_the_style_boxes(self):
        for element in CHOICES:
            with self.subTest(element=element):
                self.quick_start(element)
                expected = {'glasscannon'} | ({element} if element != 'none' else set())
                self.assertEqual(expected, self.last_build()['aspects'])

    def test_none_goes_through_on_every_style(self):
        for version in VERSIONS:
            for style, _label in presets.play_styles(version):
                with self.subTest(version=version, style=style):
                    self.quick_start('none', style, version)
                    self.assertEqual(set(presets.STYLE_BY_KEY[style].aspects),
                                     self.last_build()['aspects'])

    def test_farm_without_an_element_is_the_two_stat_mule(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                self.quick_start('none', 'farm', version)
                build = self.last_build()
                self.assertEqual({'wis', 'pp'}, mule_stats(build['aspects']))
                weighed = {key for key, value in build['stats_weight'].items()
                           if value and key not in NON_STAT_WEIGHT_KEYS}
                self.assertEqual({'wis', 'pp'}, weighed - {'cha'})
                self.assertEqual((0, 0, 0), tuple(build['minimum_stats'][key]
                                                  for key in ('AP', 'MP', 'Range')))

    def test_farm_with_an_element_still_fights(self):
        self.quick_start('cha', 'farm')
        build = self.last_build()
        self.assertEqual({'wis', 'pp', 'cha'}, build['aspects'])
        self.assertEqual(set(), mule_stats(build['aspects']))
        self.assertGreater(build['stats_weight']['ap'], 0)
        self.assertGreater(build['stats_weight']['wis'], 0)
        self.assertGreater(build['minimum_stats']['AP'], 0)


class TheSmartBuildAsksForAMissingElementTests(_DoorMixin, TestCase):

    def smart_build(self, text, element=None, confirm=True, expected=302):
        data = {'q': text}
        if confirm:
            data['confirm'] = '1'
        if element is not None:
            data['element'] = element
        return self.post('dofus3', '/smartbuild/', data, expected)

    def test_a_phrase_without_an_element_asks_for_one(self):
        page = self.smart_build('Pandawa 200', confirm=False, expected=200).content.decode('utf-8')
        tag, options = _select(page, 'element')
        self.assertIn(' required', tag)
        self.assertEqual(('', True, True), options[0])
        self.assertEqual(CHOICES, [value for value, _s, _d in options[1:]])
        chips = re.search(r'<div class="smart-chips">(.*?)</div>', page, re.S).group(1)
        for label in ('Strength', 'Intelligence', 'Chance', 'Agility'):
            self.assertNotIn(label, chips)
        self.assertNotIn(REFUSAL, page)

    def test_a_phrase_with_an_element_asks_nothing_and_keeps_it(self):
        page = self.smart_build('Iop 200 earth PvM', confirm=False,
                                expected=200).content.decode('utf-8')
        self.assertEqual((None, []), _select(page, 'element'))
        self.smart_build('Iop 200 earth PvM', 'none')
        self.assertEqual({'glasscannon', 'str'}, self.last_build()['aspects'])

    def test_confirming_without_an_element_builds_nothing_and_asks_again(self):
        for element in (None, '', 'water'):
            with self.subTest(element=element):
                page = self.smart_build('Pandawa 200', element,
                                        expected=400).content.decode('utf-8')
                self.assertIn(REFUSAL, page)
                self.assertEqual([''], _selected(page, 'element'))

    def test_the_build_gets_the_element_picked(self):
        for element in CHOICES:
            with self.subTest(element=element):
                self.smart_build('Pandawa 200', element)
                expected = {'glasscannon'} | ({element} if element != 'none' else set())
                self.assertEqual(expected, self.last_build()['aspects'])

    def test_a_farm_phrase_with_none_is_the_two_stat_mule(self):
        self.smart_build('Enutrof farm 100', 'none')
        build = self.last_build()
        self.assertEqual({'wis', 'pp'}, build['aspects'])
        self.assertEqual(0, build['minimum_stats']['AP'])
