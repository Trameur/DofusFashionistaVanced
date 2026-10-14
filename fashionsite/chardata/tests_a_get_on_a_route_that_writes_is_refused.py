# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The owner's save routes answer a GET with 405 and write only on a POST."""
import json
import pickle
import re

from django.contrib.auth.models import User
from django.test import TestCase

from chardata.models import Char, CharBaseStats
from fashionistapulp.modelresult import ModelResultMinimal

ABBREVIATIONS = ('vit', 'wis', 'str', 'int', 'cha', 'agi')


def _a_build(owner, version='dofus3', shared=False, name='Saved'):
    input_ = {'options': {'ap_exo': False, 'mp_exo': False},
              'origin': 'generated', 'char_level': 200,
              'base_stats_by_attr': {}, 'locked_equips': {}}
    return Char.objects.create(
        name=name, char_name=name, char_class='Iop', char_build='build',
        level=200, minimum_stats=b'', minimum_crits=b'', stats_weight=b'',
        options=b'', inclusions=b'', exclusions=b'',
        minimal_solution=pickle.dumps(ModelResultMinimal({}, input_, {})),
        owner=owner, link_shared=shared, game_version=version)


def _the_stats_of_a_form(scrolled, points):
    form = {}
    for abbreviation in ABBREVIATIONS:
        form['scrolled_%s' % abbreviation] = str(scrolled)
        form['points_%s' % abbreviation] = str(points)
    return form


class TheBaseStatsRoutesWriteOnlyOnAPostTests(TestCase):

    def setUp(self):
        self.owner = User.objects.create_user('saver', 'sv@x.test', 'pw-42-solid')
        self.client.force_login(self.owner)
        self.char = _a_build(self.owner)

    def _stored(self, char=None):
        char = char or self.char
        return sorted(CharBaseStats.objects.filter(char=char).values_list(
            'stat', 'total_value', 'scrolled_value'))

    def test_a_get_on_save_char_is_refused_and_stores_nothing(self):
        for method in (self.client.get, self.client.head):
            response = method(
                '/save_char/%d/?scrolled_vit=9&points_vit=9' % self.char.pk)
            self.assertEqual(405, response.status_code)
        self.assertEqual([], self._stored())

    def test_a_get_on_save_char_is_refused_under_a_version_prefix(self):
        older = _a_build(self.owner, 'dofus2', name='Older')
        self.assertEqual(405, self.client.get('/dofus2/save_char/%d/' % older.pk).status_code)
        self.assertEqual([], self._stored(older))

    def test_a_post_on_save_char_stores_the_stats_and_answers_them(self):
        response = self.client.post('/save_char/%d/' % self.char.pk,
                                    _the_stats_of_a_form(scrolled=10, points=20))
        self.assertEqual(200, response.status_code)
        self.assertIn('distrib', json.loads(response.content.decode('utf-8')))
        stored = {stat: (total, scrolled) for stat, total, scrolled in self._stored()}
        self.assertEqual(6, len(stored))
        self.assertEqual((30, 10), stored['Vitality'])

    def test_a_get_on_initbasestatspost_is_refused_and_stores_nothing(self):
        for method in (self.client.get, self.client.head):
            self.assertEqual(
                405, method('/initbasestatspost/%d/' % self.char.pk).status_code)
        self.assertEqual([], self._stored())

    def test_a_post_on_initbasestatspost_stores_the_stats_and_goes_to_the_wizard(self):
        response = self.client.post('/initbasestatspost/%d/' % self.char.pk,
                                    _the_stats_of_a_form(scrolled=5, points=15))
        self.assertEqual(302, response.status_code)
        self.assertEqual('/wizard/%d/' % self.char.pk, response['Location'])
        stored = {stat: (total, scrolled) for stat, total, scrolled in self._stored()}
        self.assertEqual((20, 5), stored['Vitality'])


class TheCompareSharingLinkPublishesOnlyOnAPostTests(TestCase):

    def setUp(self):
        self.owner = User.objects.create_user('comparer', 'cp@x.test', 'pw-42-solid')
        self.client.force_login(self.owner)
        self.first = _a_build(self.owner, name='CompareOne')
        self.second = _a_build(self.owner, name='CompareTwo')
        self.path = '/get_compare_sharing_link/%d/%d/' % (self.first.pk, self.second.pk)

    def _shared(self):
        return [Char.objects.get(pk=char.pk).link_shared
                for char in (self.first, self.second)]

    def test_a_get_is_refused_and_publishes_nothing(self):
        for method in (self.client.get, self.client.head):
            self.assertEqual(405, method(self.path).status_code)
        self.assertEqual([False, False], self._shared())

    def test_a_post_publishes_both_builds_and_answers_the_compare_link(self):
        response = self.client.post(self.path)
        self.assertEqual(200, response.status_code)
        self.assertIn('/compare_sets/', response.content.decode('utf-8'))
        self.assertEqual([True, True], self._shared())

    def test_the_compare_page_asks_for_its_link_with_a_post(self):
        page = self.client.get('/compare_sets/%d/%d/' % (self.first.pk, self.second.pk))
        self.assertEqual(200, page.status_code)
        html = page.content.decode('utf-8')
        self.assertIn("$.post('/get_compare_sharing_link/", html)
        self.assertNotIn("$.get('/get_compare_sharing_link/", html)


class DuplicatingMyBuildWritesOnlyOnAPostTests(TestCase):

    def setUp(self):
        self.owner = User.objects.create_user('duplicator', 'dp@x.test', 'pw-42-solid')
        self.client.force_login(self.owner)
        self.char = _a_build(self.owner)

    def test_a_get_is_refused_and_copies_nothing(self):
        before = Char.objects.count()
        response = self.client.get('/duplicatemyproject/%d/' % self.char.id)
        self.assertEqual(405, response.status_code)
        self.assertEqual(before, Char.objects.count())

    def test_a_post_copies_the_build_into_the_owners_workspace(self):
        response = self.client.post('/duplicatemyproject/%d/' % self.char.id)
        self.assertEqual(302, response.status_code)
        self.assertEqual(2, Char.objects.filter(owner=self.owner).count())

    def test_the_header_duplicates_with_a_post_form(self):
        page = self.client.get('/solution/%d/' % self.char.id).content.decode('utf-8')
        self.assertNotIn('href="/duplicatemyproject/', page)
        form = re.search(r'<form[^>]*action="/duplicatemyproject/%d/"[^>]*>'
                         % self.char.id, page)
        self.assertIsNotNone(form)
        self.assertIn('method="post"', form.group(0))
