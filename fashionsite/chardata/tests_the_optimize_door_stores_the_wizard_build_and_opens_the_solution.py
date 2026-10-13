# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The Optimize now door stores the very build the wizard door stores and redirects to the solution page, as Quick Start does."""
import re
from urllib.parse import urlparse

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase
from django.urls import resolve

from chardata import solution_view
from chardata import tests_every_preset_keeps_its_weights_and_minimums as golden
from chardata.char_blobs import read_char_blob
from chardata.coaching_view import coaching
from chardata.create_project_view import create_project
from chardata.models import Char
from chardata.tests_every_preset_keeps_its_weights_and_minimums import VERSIONS, _version_path
from chardata.tests_the_setup_creation_doors_support import door_fields
from chardata.tests_the_setup_preview_matches_the_build_the_door_creates import classes_of
from chardata.tests_the_hand_door_saves_no_minimum_as_the_setup_panel_says import one_element_box
from fashionistapulp.structure import set_current_game_version

IGNORED = frozenset(('id', 'created_time', 'modified_time', 'stuff_time', 'solved_time'))


def stored_build(char):
    """Every column of the build but its id and its clocks, the blobs read back."""
    values = {}
    for field in Char._meta.concrete_fields:
        if field.name in IGNORED:
            continue
        value = getattr(char, field.attname)
        if field.get_internal_type() == 'BinaryField':
            value = read_char_blob(bytes(value), None, field.name)
        values[field.name] = value
    return values


class TheOptimizeDoorTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user('optimize-door', 'optimize@test.local',
                                             'pw-optimize-door-17')

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')

    def press(self, version, door, level=200, char_class=None, touched=()):
        set_current_game_version(version)
        char_class = char_class or sorted(classes_of(version))[0]
        fields = door_fields(door, char_class, level, one_element_box(version), touched)
        request = RequestFactory().post('/', dict(fields))
        request.user = self.owner
        request.game_version = version
        response = create_project(request)
        self.assertEqual(302, response.status_code)
        return Char.objects.order_by('-id').first(), response

    def test_it_stores_the_build_the_wizard_door_stores_in_every_version(self):
        for version in VERSIONS:
            for level in (50, 200):
                with self.subTest(version=version, level=level):
                    wizard, _ = self.press(version, 'wizard', level)
                    optimize, _ = self.press(version, 'optimize', level)
                    self.assertNotEqual(wizard.pk, optimize.pk)
                    self.assertEqual(stored_build(wizard), stored_build(optimize))

    def test_it_stores_the_minimums_the_hand_door_leaves_out(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                optimize, _ = self.press(version, 'optimize')
                byhand, _ = self.press(version, 'byhand')
                self.assertNotEqual(stored_build(byhand)['minimum_stats'],
                                    stored_build(optimize)['minimum_stats'])
                self.assertEqual(stored_build(byhand)['stats_weight'],
                                 stored_build(optimize)['stats_weight'])

    def test_it_stores_the_touched_fields_the_wizard_door_stores(self):
        touched = [('weight_ap', '321'), ('min_mp', '5')]
        for version in VERSIONS:
            with self.subTest(version=version):
                wizard, _ = self.press(version, 'wizard', touched=touched)
                optimize, _ = self.press(version, 'optimize', touched=touched)
                self.assertEqual(stored_build(wizard), stored_build(optimize))

    def test_it_redirects_to_the_solution_page_of_the_new_build_in_every_version(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                char, response = self.press(version, 'optimize')
                self.assertEqual(_version_path(version, '/solution/%d/' % char.pk), response.url)
                match = resolve(response.url)
                self.assertEqual('solution_2', match.url_name)
                self.assertIs(solution_view.solution, match.func)
                self.assertEqual(str(char.pk), match.kwargs['char_id'])

    def test_it_lands_on_the_page_quick_start_lands_on(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                _char, response = self.press(version, 'optimize')
                set_current_game_version(version)
                char_class = sorted(classes_of(version))[0]
                style = golden._offered_styles(version)[0][0]
                request = RequestFactory().post('/', {
                    'char_class': char_class, 'char_level': '200', 'play_style': style,
                    'element': golden._class_element(style, char_class, version, 200)})
                request.user = self.owner
                request.game_version = version
                quick = coaching(request)
                self.assertEqual(302, quick.status_code)
                self.assertEqual(re.sub(r'\d+/$', 'ID/', urlparse(quick.url).path),
                                 re.sub(r'\d+/$', 'ID/', urlparse(response.url).path))

    def test_the_other_doors_still_go_where_they_went(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                char, wizard = self.press(version, 'wizard')
                self.assertEqual('wizard', resolve(wizard.url).url_name)
                self.assertEqual(str(char.pk), str(resolve(wizard.url).kwargs['char_id']))
                char, byhand = self.press(version, 'byhand')
                self.assertEqual('solution', resolve(byhand.url).url_name)
                self.assertEqual(str(char.pk), str(resolve(byhand.url).kwargs['char_id']))

    def test_a_form_that_posts_two_buttons_keeps_the_old_order_of_the_doors(self):
        version = 'dofus3'
        set_current_game_version(version)
        fields = door_fields('byhand', 'Iop', 200, one_element_box(version)) + [
            ('optimize', 'optimize')]
        request = RequestFactory().post('/', dict(fields))
        request.user = self.owner
        request.game_version = version
        response = create_project(request)
        self.assertEqual('solution', resolve(response.url).url_name)
