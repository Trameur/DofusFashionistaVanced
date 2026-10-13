# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A visitor who posts the /setup/ form with Optimize now is sent to the solution page of the new build and reads the solved build there."""
from django.test import TestCase
from django.urls import resolve

from chardata.models import Char
from chardata.solution import get_solution
from chardata.tests_every_preset_keeps_its_weights_and_minimums import VERSIONS, _version_path
from chardata.tests_the_hand_door_saves_no_minimum_as_the_setup_panel_says import one_element_box
from chardata.tests_the_setup_creation_doors_support import door_fields
from fashionistapulp.structure import set_current_game_version

MOST_HOPS = 4


class ThePostedOptimizeNowEndsOnTheSolutionPageTests(TestCase):

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')

    def post(self, version, door, level=50):
        set_current_game_version(version)
        fields = door_fields(door, 'Iop', level, one_element_box(version))
        return self.client.post(_version_path(version, '/createproject/'), dict(fields))

    def follow(self, response):
        """The hops a browser makes; the test client refuses the solution page redirecting to itself."""
        hops = []
        while response.status_code == 302 and len(hops) < MOST_HOPS:
            hops.append(response['Location'])
            response = self.client.get(response['Location'])
        return hops, response

    def test_the_first_hop_is_the_solution_page_of_the_new_build_in_every_version(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                response = self.post(version, 'optimize')
                char = Char.objects.order_by('-id').first()
                self.assertEqual(302, response.status_code)
                self.assertEqual(_version_path(version, '/solution/%d/' % char.pk),
                                 response['Location'])
                self.assertEqual('solution_2', resolve(response['Location']).url_name)

    def test_the_hand_door_posted_the_same_way_goes_to_the_empty_solution_page(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                response = self.post(version, 'byhand')
                char = Char.objects.order_by('-id').first()
                self.assertEqual(_version_path(version, '/solution/%d/True/' % char.pk),
                                 response['Location'])

    def test_a_visitor_who_follows_the_hops_reads_the_solved_build_page(self):
        response = self.post('dofus3', 'optimize')
        char = Char.objects.get()
        self.assertIsNone(get_solution(char))
        hops, page = self.follow(response)
        self.assertEqual(200, page.status_code)
        self.assertEqual('/solution/%d/' % char.pk, hops[0])
        self.assertLess(len(hops), MOST_HOPS)
        self.assertIn('chardata/solution.html', [template.name for template in page.templates])
        char.refresh_from_db()
        self.assertIsNotNone(get_solution(char))

    def test_the_build_is_the_visitors_own_for_the_whole_trip(self):
        response = self.post('dofus3', 'optimize')
        char = Char.objects.get()
        self.assertIsNone(char.owner)
        _hops, page = self.follow(response)
        self.assertEqual(200, page.status_code)
        again = self.client.get('/solution/%d/' % char.pk)
        self.assertEqual(200, again.status_code)
