# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The forbid page of a build in each of the five versions carries the resource row, the Forbidden resources cell and the picker JSON, and a resource name holding markup cannot break out of the page."""
import json
import os
import pickle
import re
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase

from chardata import resource_ban
from chardata.models import Char
from fashionistapulp.game_versions import GAME_VERSIONS
from fashionistapulp.structure import set_current_game_version

VERSIONS = ('dofus3', 'beta', 'dofus2', 'touch', 'retro')
HOSTILE = '</script><b>injected</b>'
TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        'templates', 'chardata', 'exclusions.html')


def _json_script(page, element_id):
    match = re.search(r'<script id="%s" type="application/json">(.*?)</script>' % element_id,
                      page, re.S)
    return json.loads(match.group(1))


class _AForbidPage(TestCase):

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')
        self.owner = User.objects.create_user('banpage', 'bp@test.local', 'pw-ban-page-1')
        self.client.force_login(self.owner)

    def build(self, version, keys):
        set_current_game_version(version)
        return Char.objects.create(
            name='Page', char_name='page', char_class='Iop', char_build='build',
            level=200, minimum_stats=b'', minimum_crits=b'', stats_weight=b'',
            options=pickle.dumps({resource_ban.OPTION_KEY: list(keys)}),
            inclusions=b'', exclusions=b'', owner=self.owner,
            link_shared=False, game_version=version)

    def get(self, version, char):
        prefix = GAME_VERSIONS[version].prefix
        return self.client.get('%s/exclusions/%d/' % ('/' + prefix if prefix else '', char.pk))


class TheResourceRowIsDrawnInEveryVersionTests(_AForbidPage):

    def test_each_version_embeds_the_row_the_cell_and_the_picker(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                known = resource_ban._items_by_resource(version)
                key = next(key for key in sorted(known)
                           if resource_ban._has_icon(version, key))
                char = self.build(version, [key])

                response = self.get(version, char)
                page = response.content.decode('utf-8')

                self.assertEqual(200, response.status_code)
                self.assertIn('id="input-resource-to-forbid"', page)
                self.assertIn('id="div-forbidden-resources"', page)
                self.assertIn('id="table-forbidden-resources"', page)
                state = _json_script(page, 'exclusions-state')
                self.assertEqual([key], [row['key'] for row in state['resources']])
                self.assertTrue(state['resources'][0]['image_url'])
                self.assertTrue(state['total_text'])
                picker = _json_script(page, 'resource-picker')
                self.assertIn(key, [entry[0] for entry in picker.values()])
                self.assertTrue(_json_script(page, 'resource-icon-base'))

    def test_a_build_without_a_ban_has_an_empty_cell_and_no_total(self):
        char = self.build('dofus3', [])

        page = self.get('dofus3', char).content.decode('utf-8')

        state = _json_script(page, 'exclusions-state')
        self.assertEqual([], state['resources'])
        self.assertEqual('', state['total_text'])
        self.assertTrue(_json_script(page, 'resource-picker'))


class AResourceNameCannotInjectMarkupTests(_AForbidPage):

    def test_a_hostile_name_stays_inside_the_json_blocks(self):
        key = '12737:resources'
        char = self.build('dofus3', [key])

        with mock.patch.object(resource_ban, '_resource_labels',
                               return_value={key: HOSTILE}):
            page = self.get('dofus3', char).content.decode('utf-8')

        self.assertNotIn(HOSTILE, page)
        self.assertNotIn('<b>injected', page)
        self.assertIn('\\u003C/script\\u003E\\u003Cb\\u003Einjected', page)
        self.assertEqual(HOSTILE, _json_script(page, 'exclusions-state')['resources'][0]['name'])
        self.assertEqual([HOSTILE], list(_json_script(page, 'resource-picker')))

    def test_the_page_script_never_writes_a_name_as_html(self):
        with open(TEMPLATE, encoding='utf-8') as handle:
            source = handle.read()
        start = source.index('function createForbiddenResourceEntry')
        body = source[start:source.index('function updateResourceContainer')]

        self.assertIn('.text(resource.name)', body)
        self.assertNotIn('resource.name +', body)
        self.assertNotIn('.html(', body)
