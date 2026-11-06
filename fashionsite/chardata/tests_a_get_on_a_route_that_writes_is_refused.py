# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The route that duplicates my build answers a GET with 405 and writes only on a POST."""
import pickle
import re

from django.contrib.auth.models import User
from django.test import TestCase

from chardata.models import Char
from fashionistapulp.modelresult import ModelResultMinimal


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
