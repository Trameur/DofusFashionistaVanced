# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A beta whose label already starts with its game's name shows that name once in the switcher, and a beta whose label does not still shows both."""
import re
from unittest import mock

from django.test import TestCase

from fashionistapulp.game_versions import GAME_VERSIONS, is_beta, main_of


def _links(html):
    found = []
    for attributes, body in re.findall(r'<a ([^>]*)>(.*?)</a>', html, re.S):
        classes = re.search(r'class="([^"]*)"', attributes)
        key = re.search(r'data-version="(\w+)"', attributes)
        if classes and key and classes.group(1).startswith('version-link version-beta'):
            found.append((key.group(1), body))
    return found


class TheSwitcherNamesTheGameOnceTests(TestCase):

    def test_each_readable_beta_reads_as_its_game_and_its_channel_once(self):
        html = self.client.get('/').content.decode('utf-8')
        links = _links(html)
        self.assertTrue(links)
        for key, body in links:
            game, label = GAME_VERSIONS[main_of(key)].label, GAME_VERSIONS[key].label
            text = re.sub(r'<[^>]+>', '', body.replace('&nbsp;', ' ').replace(chr(160), ' '))
            expected = label if game in label else '%s %s' % (game, label)
            self.assertTrue(text.startswith(expected), (key, text))
            self.assertEqual(game in label, 'version-game-name' not in body, key)

    def test_a_beta_that_goes_live_follows_the_same_rule(self):
        for key, version in GAME_VERSIONS.items():
            if not (version.dofus and is_beta(key) and version.experimental):
                continue
            with mock.patch.object(version, 'experimental', False):
                links = dict(_links(self.client.get('/').content.decode('utf-8')))
            self.assertIn(key, links)
            self.assertEqual(GAME_VERSIONS[main_of(key)].label in version.label, 'version-game-name' not in links[key])
