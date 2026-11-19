# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The Dracorune count is offered on the setup page and the options page of a version with a runes file, and nowhere else."""
import re

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase

from chardata.coaching_view import create_build
from chardata.options import get_available_options
from fashionistapulp import dracorunes
from fashionistapulp.structure import set_current_game_version

OTHER_VERSIONS = ('dofus3', 'dofus2', 'retro', 'touch', 'wakfu')


def prefix(version):
    return '' if version == 'dofus3' else '/%s' % version


def field_of(html):
    return re.findall(r'<input[^>]*name="dracorunes"[^>]*>', html)


class TheDracoruneCountIsOfferedWhereTheVersionHasRunesTests(TestCase):

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')
        self.owner = User.objects.create_user('dracoshow', 'dracoshow@test.local', 'pw-1234')
        self.client.force_login(self.owner)

    def build(self, version):
        set_current_game_version(version)
        request = RequestFactory().post('/')
        request.user = self.owner
        return create_build(request, 'Iop', 200, {'str'}, version)

    def test_the_slot_count_is_the_slots_a_rune_item_type_can_fill(self):
        set_current_game_version('beta')
        slots = get_available_options()['dracorune_slots']
        runes = dracorunes.load_runes('beta')
        self.assertEqual(dracorunes.slot_count('beta', runes), slots)
        self.assertGreater(slots, 0)

    def test_the_beta_setup_page_draws_the_field_from_zero_up_to_the_slot_count(self):
        set_current_game_version('beta')
        slots = get_available_options()['dracorune_slots']
        html = self.client.get('/beta/setup/').content.decode('utf-8')
        found = field_of(html)
        self.assertEqual(1, len(found))
        self.assertIn('min="0"', found[0])
        self.assertIn('max="%d"' % slots, found[0])
        self.assertIn('value="0"', found[0])

    def test_the_beta_options_page_draws_the_field(self):
        char = self.build('beta')
        html = self.client.get('/beta/options/%d/' % char.id).content.decode('utf-8')
        self.assertEqual(1, len(field_of(html)))

    def test_no_other_version_draws_it_on_either_page(self):
        for version in OTHER_VERSIONS:
            with self.subTest(version=version):
                set_current_game_version(version)
                self.assertEqual(0, get_available_options()['dracorune_slots'])
                setup = self.client.get('%s/setup/' % prefix(version)).content.decode('utf-8')
                self.assertEqual([], field_of(setup))
                char = self.build(version)
                options = self.client.get('%s/options/%d/' % (prefix(version), char.id))
                self.assertEqual([], field_of(options.content.decode('utf-8')))
