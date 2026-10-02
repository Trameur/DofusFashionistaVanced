# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The set page shows its owner a link to the weights and minimums, and a visitor none."""
import pickle
from html.parser import HTMLParser

from django.contrib.auth.models import User
from django.test import TestCase

from chardata.encoded_char_id import encode_char_id
from chardata.models import Char
from fashionistapulp.modelresult import ModelResultMinimal
from fashionistapulp.structure import get_structure, set_current_game_version


class _Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self._href = None

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self._href = dict(attrs).get('href')
            self.links.append([dict(attrs), ''])

    def handle_endtag(self, tag):
        if tag == 'a':
            self._href = None

    def handle_data(self, data):
        if self._href is not None and self.links:
            self.links[-1][1] += data


class TheSetPageLinksItsOwnerToTheWeightsTests(TestCase):
    level = 200

    def setUp(self):
        set_current_game_version('dofus3')
        structure = get_structure('dofus3')
        hat = next(item for item in structure.get_unique_items_by_type_and_level('Hat', 200)
                   if not item.removed and item.ankama_id)
        self.owner = User.objects.create_user('setowner', 'so@test.local', 'pw-42-solid')
        solution = ModelResultMinimal(
            {'hat': hat.id}, {'options': {'ap_exo': False, 'mp_exo': False},
                              'origin': 'generated', 'char_level': self.level,
                              'base_stats_by_attr': {}, 'locked_equips': {}}, {})
        self.char = Char.objects.create(
            name='linked', char_name='linked', char_class='Iop', char_build='build',
            level=self.level, minimum_stats=b'', minimum_crits=b'', stats_weight=b'',
            options=b'', inclusions=b'', exclusions=b'',
            minimal_solution=pickle.dumps(solution), owner=self.owner,
            link_shared=True, game_version='dofus3')

    def links_to_the_weights(self, url):
        response = self.client.get(url)
        self.assertEqual(200, response.status_code)
        parser = _Links()
        parser.feed(response.content.decode('utf-8'))
        return [(attrs, text.strip()) for attrs, text in parser.links
                if attrs.get('href') == '/stats/%d/' % self.char.pk]

    def test_the_owner_gets_the_link_beside_tailor(self):
        self.client.force_login(self.owner)
        links = self.links_to_the_weights('/solution/%d/' % self.char.pk)
        texts = [text for attrs, text in links]
        self.assertIn('Edit weights and minimums', texts)
        button = [attrs for attrs, text in links if text == 'Edit weights and minimums'][0]
        self.assertIn('button-thin', button.get('class', '').split())

    def test_a_visitor_gets_no_link(self):
        links = self.links_to_the_weights(
            '/s/linked/%s/' % encode_char_id(self.char.pk))
        self.assertEqual([], links)


class ALowLevelSetLinksItsOwnerTooTests(TheSetPageLinksItsOwnerToTheWeightsTests):
    level = 20
