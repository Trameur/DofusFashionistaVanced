# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A minimum too large for the solver is not stored through the weights page, the wizard's save or any /setup/ door, and the solution page of the build answers."""
import io
import os
import re

from django.test import TestCase

from chardata.min_stats import get_min_stats_digested
from chardata.models import Char
from chardata.setup_edits import touched_fields
from chardata.tests_every_preset_keeps_its_weights_and_minimums import VERSIONS, _version_path
from chardata.tests_the_hand_door_saves_no_minimum_as_the_setup_panel_says import one_element_box
from chardata.tests_the_setup_creation_doors_support import (
    DOORS, TouchedDoors, door_fields, panel_rows)
from chardata.weights_minimums import MINIMUM_LIMIT, _caps, merge_minimum_fields
from fashionistapulp.structure import set_current_game_version

HERE = os.path.dirname(os.path.abspath(__file__))
ROW = os.path.join(HERE, 'templates', 'chardata', 'weights_minimums_row.html')
MOST_HOPS = 4
TOO_LARGE = ('9' * 400, '9' * 300, '1e300', str(MINIMUM_LIMIT + 1), str(-MINIMUM_LIMIT - 1))


class TheLimitIsTheOneTheMinimumBoxesDeclareTests(TestCase):

    def test_every_minimum_box_declares_the_lower_bound_the_server_enforces(self):
        source = io.open(ROW, encoding='utf-8').read()
        declared = re.findall(r'wm-min-input" step="1" min="(-?\d+)"', source)
        self.assertEqual(2, len(declared))
        self.assertEqual({str(-MINIMUM_LIMIT)}, set(declared))


class AMinimumOutsideTheLimitIsNotStoredTests(TouchedDoors, TestCase):

    def free_key(self, version, char):
        set_current_game_version(version)
        capped = set(_caps(char))
        return [key for key in panel_rows(version)[1] if key not in capped][0]

    def test_the_weights_page_keeps_the_stored_minimum_and_takes_the_ones_at_the_limit(self):
        for version in VERSIONS:
            char = self.build(version, 'wizard')
            key = self.free_key(version, char)
            before = self.state(version, char)['minimums'][key]
            for posted in TOO_LARGE:
                with self.subTest(version=version, posted=posted[:12]):
                    answered = self.weights_page(version, char, {'min_%s' % key: posted})
                    self.assertEqual(before, answered['minimums'][key])
            for posted in (MINIMUM_LIMIT, -MINIMUM_LIMIT):
                with self.subTest(version=version, posted=posted):
                    answered = self.weights_page(version, char, {'min_%s' % key: str(posted)})
                    self.assertEqual(posted, answered['minimums'][key])

    def test_merging_the_fields_directly_stores_the_same_values_every_caller_shares(self):
        for version in VERSIONS:
            char = self.build(version, 'wizard')
            key = self.free_key(version, char)
            for posted, kept in (('9' * 400, False), (str(MINIMUM_LIMIT + 1), False),
                                 (str(MINIMUM_LIMIT), True), ('7', True)):
                with self.subTest(version=version, posted=posted[:12]):
                    set_current_game_version(version)
                    char = Char.objects.get(pk=char.pk)
                    merge_minimum_fields(char, {'min_%s' % key: '-3'})
                    merge_minimum_fields(char, {'min_%s' % key: posted})
                    char = Char.objects.get(pk=char.pk)
                    stored = self.state(version, char)['minimums'][key]
                    self.assertEqual(int(posted) if kept else -3, stored)

    def test_a_value_outside_the_limit_does_not_count_as_touched_on_the_setup_form(self):
        for version in VERSIONS:
            char = self.build(version, 'wizard')
            key = self.free_key(version, char)
            set_current_game_version(version)
            for posted in TOO_LARGE:
                with self.subTest(version=version, posted=posted[:12]):
                    self.assertEqual(({}, {}), touched_fields(char, {'min_%s' % key: posted}))
            self.assertEqual({'min_%s' % key: str(MINIMUM_LIMIT)},
                             touched_fields(char, {'min_%s' % key: str(MINIMUM_LIMIT)})[1])

    def test_every_door_stores_the_build_as_it_was_without_the_value(self):
        for version in VERSIONS:
            key = self.free_key(version, self.build(version, 'wizard'))
            for door in DOORS:
                before = self.state(version, self.build(version, door))
                for posted in TOO_LARGE[:2] + TOO_LARGE[3:4]:
                    with self.subTest(version=version, door=door, posted=posted[:12]):
                        stored = self.state(version,
                                            self.build(version, door, [('min_%s' % key, posted)]))
                        self.assertEqual(before['minimums'][key], stored['minimums'][key])


class TheSolutionPageAnswersAfterAnOversizedMinimumTests(TestCase):

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')

    def post(self, door, minimum=None):
        set_current_game_version('dofus3')
        touched = [] if minimum is None else [('min_vit', minimum)]
        fields = door_fields(door, 'Iop', 50, one_element_box('dofus3'), touched)
        return self.client.post(_version_path('dofus3', '/createproject/'), dict(fields))

    def follow(self, response):
        hops = 0
        while response.status_code == 302 and hops < MOST_HOPS:
            hops += 1
            response = self.client.get(response['Location'])
        return response

    def test_the_optimize_door_solves_and_shows_the_build_without_the_minimum(self):
        self.post('optimize')
        before = get_min_stats_digested(Char.objects.order_by('-id').first()).get('Vitality')
        for posted in ('9' * 400, str(MINIMUM_LIMIT + 1)):
            with self.subTest(posted=posted[:12]):
                response = self.post('optimize', posted)
                char = Char.objects.order_by('-id').first()
                self.assertEqual(302, response.status_code)
                self.assertEqual(before, get_min_stats_digested(char).get('Vitality'))
                page = self.follow(response)
                self.assertEqual(200, page.status_code)
                self.assertIn('chardata/solution.html', [template.name for template in page.templates])

    def test_a_minimum_at_the_limit_still_reaches_the_solver_and_the_page_answers(self):
        response = self.post('optimize', str(MINIMUM_LIMIT))
        char = Char.objects.order_by('-id').first()
        self.assertEqual(MINIMUM_LIMIT, get_min_stats_digested(char)['Vitality'])
        page = self.follow(response)
        self.assertEqual(200, page.status_code)
