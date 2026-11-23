# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The Smithmagic page keeps a transcendence rune the version offers as the build's suggestion and ignores every other value, leaving the page as it was."""
import json
import re

from django.test import TestCase

from chardata.forgemagie_transcendance import get_transcendence_runes
from chardata.transcendence_card_fixtures import plain_pieces, rune_of_stat
from fashionistapulp.structure import set_current_game_version


def body_of(response):
    return re.sub(rb'[A-Za-z0-9_:-]{40,}', b'TOKEN', response.content)


def config_of(response):
    html = response.content.decode('utf-8')
    return json.loads(re.search(r'id="fm-config" type="application/json">(.*?)</script>',
                                html, re.S).group(1))


class TheForgemagiePageSuggestsTheRuneOfTheLinkTests(TestCase):

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')
        self.rune = rune_of_stat('vit')
        self.hat = plain_pieces('Hat', 'beta', 1, self.rune)[0]
        self.url = '/beta/forgemagie/?item=%d' % self.hat.id

    def page(self, extra='', url=None):
        return self.client.get((url or self.url) + extra)

    def test_an_offered_rune_reaches_the_preload_and_the_page_carries_its_mark(self):
        config = config_of(self.page('&transcendence=%d' % self.rune['id']))
        self.assertEqual(self.rune['id'], config['preload']['transcendence'])
        self.assertEqual('Suggested transcendence rune', config['transSuggested'])

    def test_the_rune_keeps_the_item_preload_next_to_it(self):
        config = config_of(self.page('&transcendence=%d' % self.rune['id']))
        self.assertEqual(self.hat.id, config['preload']['item']['id'])

    def test_every_bad_value_leaves_the_page_byte_identical_to_one_without_the_parameter(self):
        plain = body_of(self.page())
        beta_ids = {rune['id'] for rune in get_transcendence_runes('beta')}
        dofus3_only = [rune['id'] for rune in get_transcendence_runes('dofus3')
                       if rune['id'] not in beta_ids]
        bad = ['', 'abc', '-1', '0', '1.5', '%d;alert(1)' % self.rune['id'], '99999999',
               '"><script>', '%d,%d' % (self.rune['id'], self.rune['id'])]
        bad += [str(rune_id) for rune_id in dofus3_only]
        for value in bad:
            with self.subTest(value=value):
                response = self.page('&transcendence=' + value)
                self.assertEqual(plain, body_of(response))

    def test_a_dofus3_version_without_the_rune_ignores_a_beta_only_id(self):
        beta_ids = {rune['id'] for rune in get_transcendence_runes('beta')}
        dofus3_ids = {rune['id'] for rune in get_transcendence_runes('dofus3')}
        only_beta = sorted(beta_ids - dofus3_ids)
        self.assertTrue(only_beta)
        url = '/forgemagie/?item=%d' % self.hat.id
        plain = body_of(self.page(url=url))
        self.assertEqual(plain, body_of(self.page('&transcendence=%d' % only_beta[0], url=url)))

    def test_a_version_without_runes_ignores_the_parameter(self):
        self.assertEqual([], get_transcendence_runes('retro'))
        item_url = '/retro/forgemagie/?item=%d' % self.hat.id
        response = self.client.get(item_url + '&transcendence=%d' % self.rune['id'])
        self.assertEqual(body_of(response), body_of(self.client.get(item_url)))

    def test_the_parameter_alone_changes_nothing_without_a_valid_item(self):
        url = '/beta/forgemagie/'
        self.assertEqual(body_of(self.client.get(url)),
                         body_of(self.client.get(url + '?transcendence=%d' % self.rune['id'])))

    def test_the_config_without_the_parameter_has_no_suggestion_key(self):
        config = config_of(self.page())
        self.assertNotIn('transcendence', config['preload'])
        self.assertNotIn('transSuggested', config)

    def test_the_value_reaches_the_page_only_as_an_integer_inside_the_json_config(self):
        html = self.page('&transcendence=%d' % self.rune['id']).content.decode('utf-8')
        self.assertEqual(1, len(re.findall(r'"transcendence": ?%d\b' % self.rune['id'], html)))

    def test_the_page_carries_a_line_that_names_the_suggestion_before_the_simulator_starts(self):
        html = self.page('&transcendence=%d' % self.rune['id']).content.decode('utf-8')
        self.assertIn('id="fm-trans-hint"', html)
        self.assertLess(html.index('id="fm-trans-hint"'), html.index('id="fm-sim-panel"'))
        self.assertIn('showTransHint();', html)

    def test_an_applied_rune_dims_every_card_including_the_suggested_one(self):
        html = self.page('&transcendence=%d' % self.rune['id']).content.decode('utf-8')
        self.assertIn("if (!suggested || (session && session.locked)) {", html)
