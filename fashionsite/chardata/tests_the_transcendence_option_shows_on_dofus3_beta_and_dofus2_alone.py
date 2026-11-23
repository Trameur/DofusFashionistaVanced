# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The transcendence rune count is offered on the setup page and the options page of dofus3, beta and dofus2, and nowhere else."""
import re

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase

from chardata.coaching_view import create_build
from chardata.options import get_available_options
from fashionistapulp.structure import set_current_game_version
from fashionistapulp.transcendence_terms import TRANSCENDENCE_VERSIONS, transcendence_slot_count

OFFERED = TRANSCENDENCE_VERSIONS
NOT_OFFERED = ('retro', 'touch', 'wakfu')


def prefix(version):
    return '' if version == 'dofus3' else '/%s' % version


def field_of(html):
    return re.findall(r'<input[^>]*name="transcendence"[^>]*>', html)


class TheTranscendenceCountIsOfferedWhereTheVersionHasRunesTests(TestCase):

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')
        self.owner = User.objects.create_user('transshow', 'transshow@test.local', 'pw-1234')
        self.client.force_login(self.owner)

    def build(self, version):
        set_current_game_version(version)
        request = RequestFactory().post('/')
        request.user = self.owner
        return create_build(request, 'Iop', 200, {'str'}, version)

    def test_the_slot_count_is_the_slots_the_solver_may_put_a_rune_on(self):
        for version in OFFERED:
            with self.subTest(version=version):
                set_current_game_version(version)
                slots = get_available_options()['transcendence_slots']
                self.assertEqual(transcendence_slot_count(version), slots)
                self.assertEqual(7, slots)

    def test_the_setup_page_draws_the_field_from_zero_up_to_the_slot_count(self):
        for version in OFFERED:
            with self.subTest(version=version):
                set_current_game_version(version)
                slots = get_available_options()['transcendence_slots']
                html = self.client.get('%s/setup/' % prefix(version)).content.decode('utf-8')
                found = field_of(html)
                self.assertEqual(1, len(found))
                self.assertIn('min="0"', found[0])
                self.assertIn('max="%d"' % slots, found[0])
                self.assertIn('value="0"', found[0])
                self.assertIn('setup-more-transcendence', html)

    def test_the_options_page_draws_the_field(self):
        for version in OFFERED:
            with self.subTest(version=version):
                char = self.build(version)
                html = self.client.get('%s/options/%d/' % (prefix(version), char.id)).content.decode('utf-8')
                self.assertEqual(1, len(field_of(html)))

    def test_no_other_version_draws_it_on_either_page(self):
        for version in NOT_OFFERED:
            with self.subTest(version=version):
                set_current_game_version(version)
                self.assertEqual(0, get_available_options()['transcendence_slots'])
                setup = self.client.get('%s/setup/' % prefix(version)).content.decode('utf-8')
                self.assertEqual([], field_of(setup))
                char = self.build(version)
                options = self.client.get('%s/options/%d/' % (prefix(version), char.id))
                self.assertEqual([], field_of(options.content.decode('utf-8')))
