# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A build made to be optimized waits on the loading screen, which then asks for the search, so its creator never waits on a silent page."""
from unittest import mock

from django.conf import settings
from django.test import Client, SimpleTestCase, TestCase

from chardata.models import Char
from chardata.solution import get_solution
from chardata.tests_every_preset_keeps_its_weights_and_minimums import VERSIONS, _version_path
from chardata.tests_the_hand_door_saves_no_minimum_as_the_setup_panel_says import one_element_box
from chardata.tests_the_setup_stylesheet_support import declared, stylesheet
from chardata.tests_the_setup_creation_doors_support import door_fields
from fashionistapulp.structure import set_current_game_version

QUICKSTART = {'char_class': 'Iop', 'char_level': '200', 'element': 'str'}
SMARTBUILD = {'q': 'Iop 200 earth PvM', 'confirm': '1'}


class ANewBuildWaitsOnTheLoadingScreenTests(TestCase):

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')

    def new_build(self, version):
        set_current_game_version(version)
        fields = door_fields('optimize', 'Iop', 50, one_element_box(version))
        response = self.client.post(_version_path(version, '/createproject/'), dict(fields))
        return Char.objects.order_by('-id').first(), response['Location']

    def test_the_optimize_door_opens_the_loading_screen_in_every_version(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                char, location = self.new_build(version)
                self.assertEqual(_version_path(version, '/tailoring/%d/' % char.pk), location)
                page = self.client.get(location)
                self.assertEqual(200, page.status_code)
                self.assertIn('chardata/tailoring.html', [t.name for t in page.templates])
                self.assertContains(page, 'class="loading"')
                self.assertContains(page, 'loading.js')
                self.assertContains(page, _version_path(version, '/fashion/%d/' % char.pk))
                self.assertContains(page, 'noindex')
                self.assertEqual('no-store', page['Cache-Control'])

    def test_the_quick_start_and_the_phrase_doors_open_it_too(self):
        for path, form in (('/quickstart/', QUICKSTART), ('/smartbuild/', SMARTBUILD)):
            with self.subTest(path=path):
                response = self.client.post(path, form, HTTP_ACCEPT_LANGUAGE='en')
                char = Char.objects.order_by('-id').first()
                self.assertEqual('/tailoring/%d/' % char.pk, response['Location'])

    def test_opening_the_loading_screen_runs_no_search(self):
        char, location = self.new_build('dofus3')
        self.client.get(location)
        self.assertIsNone(get_solution(Char.objects.get(pk=char.pk)))

    def test_the_search_the_loading_screen_asks_for_ends_on_the_solved_build_page(self):
        char, location = self.new_build('dofus3')
        self.client.get(location)
        response = self.client.get('/fashion/%d/' % char.pk)
        self.assertEqual(302, response.status_code)
        self.assertEqual('/solution/%d/' % char.pk, response['Location'])
        self.assertIsNotNone(get_solution(Char.objects.get(pk=char.pk)))
        page = self.client.get(response['Location'])
        self.assertIn('chardata/solution.html', [t.name for t in page.templates])

    def test_the_loading_screen_of_a_solved_build_goes_straight_to_its_page(self):
        char, location = self.new_build('dofus3')
        self.client.get('/fashion/%d/' % char.pk)
        response = self.client.get(location)
        self.assertEqual(302, response.status_code)
        self.assertEqual('/solution/%d/' % char.pk, response['Location'])

    def test_the_solution_page_of_a_build_with_no_set_still_solves_it(self):
        char, _location = self.new_build('dofus3')
        page = self.client.get('/solution/%d/' % char.pk, follow=True)
        self.assertEqual(200, page.status_code)
        self.assertIsNotNone(get_solution(Char.objects.get(pk=char.pk)))
        self.assertNotIn('chardata/tailoring.html', [t.name for t in page.templates])

    def test_a_stranger_is_refused_the_loading_screen_as_the_solution_page(self):
        char, location = self.new_build('dofus3')
        stranger = Client()
        refused = stranger.get('/solution/%d/' % char.pk).status_code
        self.assertNotEqual(200, refused)
        self.assertEqual(refused, stranger.get(location).status_code)

    def test_the_loading_screen_sends_no_page_view(self):
        char, location = self.new_build('dofus3')
        with mock.patch.dict(settings.GEN_CONFIGS, {'google_analytics_id': 'G-PINNED'}):
            self.assertNotContains(self.client.get(location), 'googletagmanager')
            self.assertContains(self.client.get('/setup/%d/' % char.pk), 'googletagmanager')

    def test_the_step_to_the_search_needs_no_jquery_and_shows_its_link_when_the_overlay_fails(self):
        _char, location = self.new_build('dofus3')
        page = self.client.get(location).content.decode('utf-8')
        script = page[page.index("var fallback = document.getElementById('tailor-fallback');"):]
        script = script[:script.index('</script>')]
        self.assertIn('id="tailor-fallback"', page)
        self.assertNotIn('$(', script)
        self.assertIn("fallback.style.display = '';", script)
        self.assertIn('window.location.replace(', script)

    def test_the_hand_door_still_opens_the_empty_solution_page(self):
        set_current_game_version('dofus3')
        fields = door_fields('byhand', 'Iop', 50, one_element_box('dofus3'))
        response = self.client.post('/createproject/', dict(fields))
        page = self.client.get(response['Location'])
        self.assertIn('chardata/solution.html', [t.name for t in page.templates])
        self.assertNotIn('chardata/tailoring.html', [t.name for t in page.templates])


class TheDarkSpinnerTests(SimpleTestCase):

    def test_the_dark_spinner_keeps_only_its_light_spokes_on_the_page(self):
        self.assertEqual('lighten', declared(stylesheet('home_darktheme.css'), '#loadingimg', 'mix-blend-mode')[0])
