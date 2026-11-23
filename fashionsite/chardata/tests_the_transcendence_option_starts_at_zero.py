# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The transcendence rune count is off on every page that draws it and in every new build."""

import re

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase

from chardata.char_blobs import read_char_blob
from chardata.coaching_view import create_build
from chardata.models import Char
from chardata.setup_options import GROUP_FIELD, apply_option_groups
from fashionistapulp.structure import set_current_game_version
from fashionistapulp.transcendence_terms import TRANSCENDENCE_VERSIONS


def prefix(version):
    return '' if version == 'dofus3' else '/%s' % version


def field_of(html):
    return re.findall(r'<input[^>]*name="transcendence"[^>]*>', html)[0]


class TheTranscendenceOptionStartsAtZeroTests(TestCase):

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')
        self.owner = User.objects.create_user('transzero', 'transzero@test.local', 'pw-1234')
        self.client.force_login(self.owner)

    def build(self, version):
        set_current_game_version(version)
        request = RequestFactory().post('/')
        request.user = self.owner
        return create_build(request, 'Iop', 200, {'str'}, version)

    def test_the_setup_page_field_holds_zero(self):
        for version in TRANSCENDENCE_VERSIONS:
            with self.subTest(version=version):
                set_current_game_version(version)
                html = self.client.get('%s/setup/' % prefix(version)).content.decode('utf-8')
                self.assertIn('value="0"', field_of(html))

    def test_the_options_page_field_of_a_new_build_holds_zero(self):
        for version in TRANSCENDENCE_VERSIONS:
            with self.subTest(version=version):
                char = self.build(version)
                html = self.client.get('%s/options/%d/' % (prefix(version), char.id)).content.decode('utf-8')
                self.assertIn('value="0"', field_of(html))

    def test_a_new_build_stores_no_transcendence_key(self):
        for version in TRANSCENDENCE_VERSIONS:
            with self.subTest(version=version):
                char = self.build(version)
                blob = Char.objects.get(id=char.id).options
                self.assertNotIn('transcendence', read_char_blob(blob, {}, 'options'))

    def test_a_setup_post_of_zero_in_its_group_stores_nothing(self):
        char = self.build('dofus3')
        before = Char.objects.get(id=char.id).options
        request = RequestFactory().post('/setup/', {GROUP_FIELD: 'transcendence', 'transcendence': '0'})
        request.user = self.owner
        apply_option_groups(request, char)
        self.assertEqual(before, Char.objects.get(id=char.id).options)

    def test_a_setup_post_above_zero_stores_the_count(self):
        char = self.build('dofus3')
        request = RequestFactory().post('/setup/', {GROUP_FIELD: 'transcendence', 'transcendence': '3'})
        request.user = self.owner
        apply_option_groups(request, char)
        self.assertEqual(3, read_char_blob(Char.objects.get(id=char.id).options, {}, 'options')['transcendence'])
