# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A copy is a new build: no views of the original's, the publication default a freshly created build gets, and still the original's items and solution."""
import json
import pickle

from django.contrib.auth.models import User
from django.test import TestCase

from chardata.encoded_char_id import encode_char_id
from chardata.models import Char, CharBaseStats
from fashionistapulp.modelresult import ModelResultMinimal

VIEWS = 57


def _a_build(owner, auto_publish, shared=True, views=VIEWS, name='Original'):
    input_ = {'options': {'ap_exo': False, 'mp_exo': False},
              'origin': 'generated', 'char_level': 200,
              'base_stats_by_attr': {}, 'locked_equips': {}}
    char = Char.objects.create(
        name=name, char_name=name.lower(), char_class='Iop', char_build='build',
        level=200, minimum_stats=pickle.dumps({'Vitality': 100}),
        minimum_crits=b'', stats_weight=pickle.dumps({'Vitality': 1.0}),
        options=pickle.dumps({}), inclusions=pickle.dumps({}),
        exclusions=pickle.dumps([]),
        minimal_solution=pickle.dumps(ModelResultMinimal({}, input_, {})),
        owner=owner, link_shared=shared, auto_publish=auto_publish,
        view_count=views, game_version='dofus3')
    CharBaseStats.objects.create(char=char, stat='Vitality',
                                 total_value=120, scrolled_value=100)
    return char


class _Copies(TestCase):

    def setUp(self):
        self.owner = User.objects.create_user('author', 'a@x.test', 'pw-42-solid')
        self.reader = User.objects.create_user('reader', 'r@x.test', 'pw-42-solid')

    def _the_copy(self, original):
        return Char.objects.exclude(pk=original.pk).get()

    def _stats(self, char):
        return sorted(CharBaseStats.objects.filter(char=char).values_list(
            'stat', 'total_value', 'scrolled_value'))


class ACopyInTheSameVersionStartsAsANewBuildTests(_Copies):

    def _duplicate_mine(self, original):
        self.client.force_login(self.owner)
        return self.client.post('/duplicatemyproject/%d/' % original.pk)

    def test_my_copy_starts_with_no_views(self):
        original = _a_build(self.owner, auto_publish=True)
        self._duplicate_mine(original)
        self.assertEqual(0, self._the_copy(original).view_count)

    def test_my_copy_of_a_build_i_kept_private_stays_private(self):
        original = _a_build(self.owner, auto_publish=False, shared=False)
        self._duplicate_mine(original)
        self.assertFalse(self._the_copy(original).auto_publish)

    def test_my_copy_gets_what_a_build_i_create_gets(self):
        self.client.force_login(self.owner)
        self.client.post('/createproject/', {
            'project': 'Fresh', 'charname': 'Moi', 'level': '200',
            'class': 'Iop', 'byhand': 'x'})
        created = Char.objects.get(name='Fresh')
        original = _a_build(self.owner, auto_publish=True, shared=False)
        self._duplicate_mine(original)
        copy = self._the_copy_among(original, created)
        self.assertTrue(created.auto_publish)
        self.assertEqual(created.auto_publish, copy.auto_publish)
        self.assertEqual(created.link_shared, copy.link_shared)

    def _the_copy_among(self, original, other):
        return Char.objects.exclude(pk__in=[original.pk, other.pk]).get()

    def test_my_copy_is_not_public_until_it_is_dressed(self):
        original = _a_build(self.owner, auto_publish=True, shared=True)
        self._duplicate_mine(original)
        self.assertFalse(self._the_copy(original).link_shared)

    def test_the_project_list_duplicates_by_the_same_rule(self):
        original = _a_build(self.owner, auto_publish=False, shared=False)
        self.client.force_login(self.owner)
        answer = self.client.post('/duplicateproject/',
                                  {'project_id': json.dumps(original.pk)})
        self.assertEqual('ok', answer.content.decode('utf-8'))
        copy = self._the_copy(original)
        self.assertEqual(0, copy.view_count)
        self.assertFalse(copy.auto_publish)

    def test_a_readers_copy_of_a_shared_build_starts_with_no_views(self):
        original = _a_build(self.owner, auto_publish=False)
        self.client.force_login(self.reader)
        self.client.post('/duplicatesomeonesproject/%s/' % encode_char_id(original.pk))
        copy = self._the_copy(original)
        self.assertEqual(self.reader, copy.owner)
        self.assertEqual(0, copy.view_count)

    def test_a_readers_copy_gets_the_readers_choice_not_the_authors(self):
        original = _a_build(self.owner, auto_publish=False)
        self.client.force_login(self.reader)
        self.client.post('/duplicatesomeonesproject/%s/' % encode_char_id(original.pk))
        self.assertTrue(self._the_copy(original).auto_publish)

    def test_a_guests_copy_never_publishes_itself(self):
        original = _a_build(self.owner, auto_publish=True)
        self.client.post('/duplicatesomeonesproject/%s/' % encode_char_id(original.pk))
        copy = self._the_copy(original)
        self.assertIsNone(copy.owner)
        self.assertFalse(copy.auto_publish)
        self.assertEqual(0, copy.view_count)

    def test_the_copy_keeps_the_originals_solution_and_base_stats(self):
        original = _a_build(self.owner, auto_publish=True)
        self._duplicate_mine(original)
        copy = self._the_copy(original)
        self.assertEqual(bytes(original.minimal_solution), bytes(copy.minimal_solution))
        self.assertEqual(bytes(original.minimum_stats), bytes(copy.minimum_stats))
        self.assertEqual(bytes(original.inclusions), bytes(copy.inclusions))
        self.assertEqual(self._stats(original), self._stats(copy))

    def test_the_original_keeps_its_views_and_its_choice(self):
        original = _a_build(self.owner, auto_publish=False)
        self._duplicate_mine(original)
        stored = Char.objects.get(pk=original.pk)
        self.assertEqual(VIEWS, stored.view_count)
        self.assertFalse(stored.auto_publish)
        self.assertTrue(stored.link_shared)


class ACopyToAnotherVersionStartsAsANewBuildTests(_Copies):

    def _copy_mine(self, original):
        self.client.force_login(self.owner)
        return self.client.post('/copytoversion/%d/' % original.pk, {'version': 'beta'})

    def _the_beta_copy(self):
        return Char.objects.get(game_version='beta')

    def test_my_copy_starts_with_no_views(self):
        original = _a_build(self.owner, auto_publish=True)
        self.assertEqual(302, self._copy_mine(original).status_code)
        self.assertEqual(0, self._the_beta_copy().view_count)

    def test_my_copy_of_a_build_i_kept_private_stays_private(self):
        original = _a_build(self.owner, auto_publish=False, shared=False)
        self._copy_mine(original)
        copy = self._the_beta_copy()
        self.assertFalse(copy.auto_publish)
        self.assertFalse(copy.link_shared)

    def test_a_readers_copy_gets_the_readers_choice_not_the_authors(self):
        original = _a_build(self.owner, auto_publish=False)
        self.client.force_login(self.reader)
        self.client.post('/copysharedtoversion/%s/' % encode_char_id(original.pk),
                         {'version': 'beta'})
        copy = self._the_beta_copy()
        self.assertEqual(self.reader, copy.owner)
        self.assertTrue(copy.auto_publish)
        self.assertEqual(0, copy.view_count)

    def test_a_guests_copy_never_publishes_itself(self):
        original = _a_build(self.owner, auto_publish=True)
        self.client.post('/copysharedtoversion/%s/' % encode_char_id(original.pk),
                         {'version': 'beta'})
        copy = self._the_beta_copy()
        self.assertIsNone(copy.owner)
        self.assertFalse(copy.auto_publish)

    def test_the_original_keeps_its_views_and_its_choice(self):
        original = _a_build(self.owner, auto_publish=False)
        self._copy_mine(original)
        stored = Char.objects.get(pk=original.pk)
        self.assertEqual(VIEWS, stored.view_count)
        self.assertFalse(stored.auto_publish)
        self.assertEqual(self._stats(original),
                         self._stats(self._the_beta_copy()))
