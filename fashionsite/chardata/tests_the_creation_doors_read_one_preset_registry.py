# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The quick start, the Smart Build and the setup page take their presets from chardata.presets."""
import json
import re
from unittest import mock

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase

from chardata import presets
from chardata.char_blobs import read_char_blob
from chardata.models import Char
from chardata.nl_parser import parse_build_request
from chardata.smart_build import ALL_ASPECTS
from fashionistapulp.dofus_constants import CHARACTER_CLASSES
from fashionistapulp.game_versions import GAME_VERSIONS
from fashionistapulp.structure import set_current_game_version

SINGLE_ELEMENTS = {'str', 'int', 'cha', 'agi'}
EVERY_STYLE = ('solo_pvm', 'group_pvm', 'pvp', 'farm')


def _offered_styles(page):
    block = re.search(r'<select[^>]*name="?play_style"?[^>]*>(.*?)</select>', page, re.S)
    return re.findall(r'<option[^>]*value="?([\w-]+)"?', block.group(1))


def _aspect_layout(page):
    return json.loads(re.search(r'var aspectLayout = (.*?)\.map', page, re.S).group(1))


class EveryPresetNamesWhatTheDoorsKnowTests(SimpleTestCase):

    def test_every_dofus_version_has_its_own_entry(self):
        for key, version in GAME_VERSIONS.items():
            if version.dofus:
                with self.subTest(version=key):
                    self.assertIn(key, presets.VERSION_PRESETS)

    def test_every_style_sets_only_aspects_the_weights_read(self):
        for style in presets.STYLES:
            with self.subTest(style=style.key):
                self.assertLessEqual(set(style.aspects), ALL_ASPECTS)

    def test_every_version_offers_known_styles_and_the_default_one(self):
        for version, entry in presets.VERSION_PRESETS.items():
            with self.subTest(version=version):
                self.assertLessEqual(set(entry['styles']), set(presets.STYLE_BY_KEY))
                self.assertIn(presets.DEFAULT_STYLE, entry['styles'])

    def test_every_class_has_one_single_element_by_default(self):
        for char_class in CHARACTER_CLASSES:
            with self.subTest(char_class=char_class):
                self.assertIn(presets.CLASS_DEFAULT_ELEMENT.get(char_class), SINGLE_ELEMENTS)

    def test_the_setup_page_has_one_box_per_aspect_the_server_reads(self):
        focus = {aspect for column in presets.FOCUS_COLUMNS for aspect in column}
        offered = set()
        for version, entry in presets.VERSION_PRESETS.items():
            with self.subTest(version=version):
                boxes = [aspect for column in presets.setup_columns(version)
                         for aspect in column]
                expected = (list(presets.ELEMENT_BOXES) + list(entry['option_boxes'])
                            + [aspect for column in presets.FOCUS_COLUMNS for aspect in column])
                self.assertEqual(expected, boxes)
                self.assertEqual(len(boxes), len(set(boxes)))
                self.assertLessEqual(set(boxes), ALL_ASPECTS | {'balanced'})
                offered.update(entry['option_boxes'])
        self.assertEqual(ALL_ASPECTS | {'balanced'},
                         set(presets.ELEMENT_BOXES) | offered | focus)


class TheDoorsReadTheRegistryTests(TestCase):

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')
        owner = User.objects.create_user('preset-registry', 'presets@test.local',
                                         'pw-preset-registry-5')
        self.client.force_login(owner)

    def _aspects_of_the_last_build(self):
        char = Char.objects.order_by('-id').first()
        return set(read_char_blob(char.aspects, set(), 'aspects', char))

    def test_the_quick_start_offers_the_styles_of_its_version(self):
        retro = {'styles': ('solo_pvm', 'pvp'), 'option_boxes': ('pvp', 'duel')}
        with mock.patch.dict(presets.VERSION_PRESETS, {'retro': retro}):
            set_current_game_version('retro')
            on_retro = self.client.get('/retro/quickstart/').content.decode('utf-8')
            set_current_game_version('dofus3')
            on_dofus3 = self.client.get('/quickstart/').content.decode('utf-8')
        self.assertEqual(['solo_pvm', 'pvp'], _offered_styles(on_retro))
        self.assertEqual(list(EVERY_STYLE), _offered_styles(on_dofus3))

    def test_a_style_its_version_does_not_offer_falls_back_to_the_default(self):
        retro = {'styles': ('solo_pvm', 'pvp'), 'option_boxes': ('pvp', 'duel')}
        with mock.patch.dict(presets.VERSION_PRESETS, {'retro': retro}):
            set_current_game_version('retro')
            response = self.client.post('/retro/quickstart/', {
                'char_class': 'Iop', 'char_level': '200', 'play_style': 'farm'})
        self.assertEqual(302, response.status_code)
        self.assertEqual({'glasscannon', 'str'}, self._aspects_of_the_last_build())

    def test_the_setup_page_shows_the_option_boxes_of_its_version(self):
        touch = {'styles': EVERY_STYLE, 'option_boxes': ('duel',)}
        with mock.patch.dict(presets.VERSION_PRESETS, {'touch': touch}):
            set_current_game_version('touch')
            page = self.client.get('/touch/setup/').content.decode('utf-8')
        self.assertEqual(['duel'], _aspect_layout(page)[1])
        self.assertEqual(presets.setup_columns('touch')[2:], _aspect_layout(page)[2:])

    def test_the_quick_start_and_the_smart_build_share_the_default_element(self):
        with mock.patch.dict(presets.CLASS_DEFAULT_ELEMENT, {'Iop': 'agi'}):
            self.assertEqual({'glasscannon', 'agi'}, parse_build_request('Iop')['aspects'])
            response = self.client.post('/quickstart/', {
                'char_class': 'Iop', 'char_level': '200', 'play_style': 'solo_pvm'})
        self.assertEqual(302, response.status_code)
        self.assertEqual({'glasscannon', 'agi'}, self._aspects_of_the_last_build())
