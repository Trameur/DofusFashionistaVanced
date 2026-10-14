# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A build its owner deleted after sharing it answers 404 on every door that reads a shared build by its encoded id, and shows on no list."""
import json
import pickle
from unittest import mock

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase

from chardata.encoded_char_id import encode_char_id
from chardata.models import Char, UserFollow
from fashionistapulp.modelresult import ModelResultMinimal

A_READER = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
            '(KHTML, like Gecko) Chrome/126.0 Safari/537.36')


def _a_build(owner, name, shared=True, deleted=False):
    input_ = {'options': {'ap_exo': False, 'mp_exo': False},
              'origin': 'generated', 'char_level': 200,
              'base_stats_by_attr': {}, 'locked_equips': {}}
    return Char.objects.create(
        name=name, char_name=name.lower(), char_class='Iop', char_build='build',
        level=200, minimum_stats=b'', minimum_crits=b'', stats_weight=b'',
        options=b'', inclusions=b'', exclusions=b'',
        minimal_solution=pickle.dumps(ModelResultMinimal({}, input_, {})),
        owner=owner, link_shared=shared, deleted=deleted, game_version='dofus3')


class _Doors(TestCase):

    def setUp(self):
        cache.clear()
        self.owner = User.objects.create_user('sharer', 's@x.test', 'pw-42-solid')
        self.stranger = User.objects.create_user('reader', 'r@x.test', 'pw-42-solid')
        self.live = _a_build(self.owner, 'Livebuild')
        self.other_live = _a_build(self.owner, 'Otherlive')
        self.gone = _a_build(self.owner, 'Gonebuild', deleted=True)
        self.live_code = encode_char_id(self.live.pk)
        self.other_code = encode_char_id(self.other_live.pk)
        self.gone_code = encode_char_id(self.gone.pk)


class ThePublicPageOfADeletedBuildIsGoneTests(_Doors):

    def test_a_live_shared_build_is_served(self):
        response = self.client.get('/s/livebuild/%s/' % self.live_code,
                                   HTTP_USER_AGENT=A_READER)
        self.assertEqual(200, response.status_code)

    def test_the_shared_page_of_a_deleted_build_is_not_found(self):
        response = self.client.get('/s/gonebuild/%s/' % self.gone_code,
                                   HTTP_USER_AGENT=A_READER)
        self.assertEqual(404, response.status_code)

    def test_the_shared_page_of_a_deleted_build_counts_no_view(self):
        self.client.get('/s/gonebuild/%s/' % self.gone_code,
                        HTTP_USER_AGENT=A_READER)
        self.assertEqual(0, Char.objects.get(pk=self.gone.pk).view_count)

    def test_a_deleted_build_that_was_never_shared_is_not_found_either(self):
        Char.objects.filter(pk=self.gone.pk).update(link_shared=False)
        response = self.client.get('/s/gonebuild/%s/' % self.gone_code,
                                   HTTP_USER_AGENT=A_READER)
        self.assertEqual(404, response.status_code)

    def test_a_live_build_that_was_never_shared_is_still_refused(self):
        Char.objects.filter(pk=self.live.pk).update(link_shared=False)
        response = self.client.get('/s/livebuild/%s/' % self.live_code,
                                   HTTP_USER_AGENT=A_READER)
        self.assertEqual(403, response.status_code)


class TheSharedSpellsOfADeletedBuildAreGoneTests(_Doors):

    def test_the_spells_of_a_live_shared_build_are_served(self):
        response = self.client.get('/spells_linked/livebuild/%s/' % self.live_code)
        self.assertEqual(200, response.status_code)

    def test_the_spells_of_a_deleted_shared_build_are_not_found(self):
        response = self.client.get('/spells_linked/gonebuild/%s/' % self.gone_code)
        self.assertEqual(404, response.status_code)

    def test_the_best_combo_of_a_live_shared_build_is_served(self):
        response = self.client.post('/best_combo_linked/%s/' % self.live_code)
        self.assertEqual(200, response.status_code)

    def test_the_best_combo_of_a_deleted_shared_build_is_not_found(self):
        response = self.client.post('/best_combo_linked/%s/' % self.gone_code)
        self.assertEqual(404, response.status_code)


class TheCompareDoorsRefuseADeletedBuildTests(_Doors):

    def _compare(self, *codes):
        return self.client.get('/compare_sets/%s/' % '/'.join('s' + c for c in codes))

    def _choose(self, *codes):
        links = ['https://dofusfashionista.gg/s/build/%s/' % code for code in codes]
        return self.client.post('/choose_compare_sets_post/',
                                {'links': json.dumps(links)})

    def _share(self, *codes):
        return self.client.post('/get_compare_sharing_link/%s/'
                                % '/'.join('s' + c for c in codes))

    def test_two_live_shared_builds_compare(self):
        self.assertEqual(200, self._compare(self.live_code, self.other_code).status_code)

    def test_a_shared_deleted_build_cannot_be_compared(self):
        self.assertEqual(404, self._compare(self.live_code, self.gone_code).status_code)

    def test_two_live_shared_links_are_accepted_by_the_picker(self):
        answer = self._choose(self.live_code, self.other_code).content.decode('utf-8')
        self.assertIn('/compare_sets/', answer)

    def test_the_picker_refuses_the_link_of_a_deleted_build(self):
        answer = self._choose(self.live_code, self.gone_code).content.decode('utf-8')
        self.assertTrue(answer.startswith('Error:'), answer)

    def test_two_live_shared_builds_get_a_compare_link(self):
        answer = self._share(self.live_code, self.other_code)
        self.assertEqual(200, answer.status_code)
        self.assertIn('/compare_sets/', answer.content.decode('utf-8'))

    def test_a_compare_link_is_not_made_for_a_deleted_build(self):
        answer = self._share(self.live_code, self.gone_code)
        self.assertEqual(404, answer.status_code)


class TheWorkshopDoesNotReadADeletedSharedBuildTests(_Doors):

    def setUp(self):
        super().setUp()
        self.client.force_login(self.stranger)

    def test_a_live_shared_build_is_readable_by_a_stranger(self):
        for path in ('/workshop/solutioningredients/%d/' % self.live.pk,):
            self.assertNotEqual(404, self.client.get(path).status_code, path)
        self.assertNotEqual(
            404, self.client.post('/workshop/addsolution/%d/' % self.live.pk).status_code)

    def test_the_ingredients_of_a_deleted_shared_build_are_not_found(self):
        response = self.client.get('/workshop/solutioningredients/%d/' % self.gone.pk)
        self.assertEqual(404, response.status_code)

    def test_a_deleted_shared_build_cannot_be_added_to_the_workshop(self):
        response = self.client.post('/workshop/addsolution/%d/' % self.gone.pk)
        self.assertEqual(404, response.status_code)

    def test_an_owner_cannot_read_their_own_deleted_shared_build_either(self):
        self.client.force_login(self.owner)
        response = self.client.get('/workshop/solutioningredients/%d/' % self.gone.pk)
        self.assertEqual(404, response.status_code)


class TheDoorsThatAlreadyRefuseADeletedBuildStillDoTests(_Doors):
    """Pins the doors found correct, so a later edit cannot reopen them."""

    def test_the_api_detail_does_not_know_it(self):
        self.assertEqual(
            404, self.client.get('/api/v1/shared-builds/%s/' % self.gone_code).status_code)

    def test_the_api_export_does_not_know_it(self):
        self.assertEqual(
            404, self.client.get(
                '/api/v1/shared-builds/%s/fashionista-build/' % self.gone_code).status_code)

    def test_the_api_list_does_not_hold_it(self):
        body = self.client.get('/api/v1/shared-builds/').content.decode('utf-8')
        self.assertIn(self.live_code, body)
        self.assertNotIn(self.gone_code, body)

    def test_the_gallery_does_not_hold_it(self):
        html = self.client.get('/sharedbuilds/', HTTP_USER_AGENT=A_READER
                               ).content.decode('utf-8')
        self.assertIn(self.live_code, html)
        self.assertNotIn(self.gone_code, html)

    def test_the_owners_profile_does_not_hold_it(self):
        html = self.client.get('/user/sharer/', HTTP_USER_AGENT=A_READER
                               ).content.decode('utf-8')
        self.assertIn(self.live_code, html)
        self.assertNotIn(self.gone_code, html)

    def test_the_feed_of_a_follower_does_not_hold_it(self):
        UserFollow.objects.create(follower=self.stranger, followed=self.owner)
        self.client.force_login(self.stranger)
        html = self.client.get('/feed/').content.decode('utf-8')
        self.assertIn(self.live_code, html)
        self.assertNotIn(self.gone_code, html)

    def test_the_sitemap_does_not_hold_it(self):
        xml = self.client.get('/sitemap-pages.xml').content.decode('utf-8')
        self.assertIn(self.live_code, xml)
        self.assertNotIn(self.gone_code, xml)

    def test_the_random_door_never_lands_on_it(self):
        Char.objects.filter(pk=self.live.pk).update(deleted=True)
        Char.objects.filter(pk=self.other_live.pk).update(deleted=True)
        for _ in range(5):
            response = self.client.get('/random/')
            self.assertNotIn(self.gone_code, response['Location'])

    def test_a_vote_on_it_is_refused(self):
        self.client.force_login(self.stranger)
        response = self.client.post('/votebuild/%d/' % self.gone.pk,
                                    {'vote_type': 'like', 'action': 'add'})
        self.assertEqual(404, response.status_code)

    def test_a_comment_on_it_is_refused(self):
        self.client.force_login(self.stranger)
        response = self.client.post('/postcomment/%d/' % self.gone.pk,
                                    {'content': 'a perfectly polite comment'})
        self.assertEqual(404, response.status_code)

    def test_copying_it_is_refused(self):
        self.client.force_login(self.stranger)
        before = Char.objects.count()
        for path in ('/duplicatesomeonesproject/%s/' % self.gone_code,
                     '/copysharedtoversion/%s/' % self.gone_code):
            response = self.client.post(path, {'version': 'beta'})
            self.assertEqual(403, response.status_code, path)
        self.assertEqual(before, Char.objects.count())


def _a_featured_row(build):
    return {'name': build.name, 'char_class': 'Iop', 'level': 200,
            'creator': 'sharer', 'like_count': 0, 'favorite_count': 0,
            'view_count': 0, 'char_name': build.char_name,
            'encoded_char_id': encode_char_id(build.pk),
            'avatar': '/static/avatar.png',
            'patch': {'patch': None, 'current_patch': None, 'older': False}}


class TheHomeFeaturedBuildsDropABuildThatIsNoLongerPublicTests(_Doors):

    def _home(self, scored):
        with mock.patch('chardata.home_view._score_featured_builds',
                        return_value=scored) as scoring:
            html = self.client.get('/', HTTP_USER_AGENT=A_READER).content.decode('utf-8')
        return html, scoring

    def _cache_both_rows(self):
        rows = [_a_featured_row(self.live), _a_featured_row(self.other_live)]
        html, scoring = self._home(rows)
        self.assertIn(self.live_code, html)
        self.assertIn(self.other_code, html)
        self.assertEqual(1, scoring.call_count)
        return rows

    def test_a_build_deleted_after_its_row_was_cached_leaves_the_home_page(self):
        rows = self._cache_both_rows()
        Char.objects.filter(pk=self.other_live.pk).update(deleted=True)
        html, scoring = self._home(rows)
        self.assertEqual(0, scoring.call_count)
        self.assertIn(self.live_code, html)
        self.assertNotIn(self.other_code, html)

    def test_a_build_unshared_after_its_row_was_cached_leaves_the_home_page(self):
        rows = self._cache_both_rows()
        Char.objects.filter(pk=self.other_live.pk).update(link_shared=False)
        html, scoring = self._home(rows)
        self.assertEqual(0, scoring.call_count)
        self.assertIn(self.live_code, html)
        self.assertNotIn(self.other_code, html)
