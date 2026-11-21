# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A draconized piece still links to the Smithmagic tool, on the catalogue lines with its own rune selected, and keeps no Customize stats button."""
import json
import pickle
import re
from urllib.parse import quote

from django.template.loader import render_to_string
from django.test import TestCase

from chardata.dracorune_fixtures import (OPTIONS, BetaModelTestCase, eligible_items,
                                         element_key, element_move, runes, structure)
from chardata.solution_result import SolutionResult
from fashionistapulp import dracorunes
from fashionistapulp.dofus_constants import STATS_NAMES
from fashionistapulp.modelresult import ModelResultMinimal, model_result_from_minimal


class TheSmithmagicLinkFollowsTheRuneTests(BetaModelTestCase):

    def setUp(self):
        super().setUp()
        source, target = element_move()
        self.key = element_key(source, target)
        self.hat = next(item for item in eligible_items('Hat')
                        if self.key in dict(dracorunes.variants(
                            [(structure().get_stat_by_id(stat_id).key, value)
                             for stat_id, value in item.stats], runes())))

    def card(self, draconized):
        minimal = ModelResultMinimal(
            {'hat': self.hat.id},
            {'options': dict(OPTIONS), 'char_level': 200,
             'base_stats_by_attr': dict({name: 0 for name, _key in STATS_NAMES}, AP=7, MP=3)},
            None)
        if draconized:
            minimal.dracorunes = {'hat': (self.hat.id, self.key)}
        result = model_result_from_minimal(pickle.loads(pickle.dumps(minimal)))
        params = SolutionResult(result).get_params()
        return next(item for item in params['all_items'] if item.slot == 'hat')

    def link(self, card):
        html = render_to_string('chardata/solution_item.html', {'item': card, 'current_game_version': 'beta'})
        found = re.findall(r'href="[^"]*forgemagie/\?item=%d[^"]*"' % self.hat.id, html)
        return found[0] if found else None

    def test_the_plain_card_links_the_item_with_no_rune_parameter(self):
        card = self.card(False)
        self.assertTrue(card.mageable)
        self.assertFalse(card.dracorune_label)
        link = self.link(card)
        self.assertTrue(link)
        self.assertNotIn('dracorune', link)

    def test_a_draconized_card_links_the_item_with_its_rune_key(self):
        card = self.card(True)
        self.assertTrue(card.dracorune_label)
        self.assertIn('&amp;dracorune=%s"' % quote(self.key, safe=''), self.link(card))

    def test_a_draconized_card_offers_no_customize_stats_button(self):
        button = 'stat-override-btn-sol-hat'
        context = {'current_game_version': 'beta'}
        plain = render_to_string('chardata/solution_item.html', dict(context, item=self.card(False)))
        html = render_to_string('chardata/solution_item.html', dict(context, item=self.card(True)))
        self.assertIn(button, plain)
        self.assertNotIn(button, html)


class TheToolPreselectsTheRuneOfTheLinkTests(TestCase):

    def setUp(self):
        self.hat = TheSmithmagicLinkFollowsTheRuneTests('test_the_plain_card_links_the_item_with_no_rune_parameter')
        self.hat.setUp()
        self.addCleanup(self.hat.doCleanups)

    def test_following_the_link_preloads_the_key(self):
        card = self.hat.card(True)
        href = re.search(r'href="([^"]*)"', self.hat.link(card)).group(1).replace('&amp;', '&')
        html = self.client.get(href).content.decode('utf-8')
        config = json.loads(re.search(r'id="fm-config" type="application/json">(.*?)</script>', html, re.S).group(1))
        self.assertEqual(self.hat.key, config['preload']['dracorune'])
