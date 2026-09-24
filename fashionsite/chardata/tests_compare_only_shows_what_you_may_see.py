# -*- coding: utf-8 -*-
"""Comparing two builds must not leak a private one, checked on the body as well as the status."""
from django.contrib.auth.models import User
from django.test import TestCase

from chardata.encoded_char_id import encode_char_id
from chardata.models import Char

SECRET = 'Bilbon-le-secret'
OTHER = 'Frodon-le-second'


class CompareOnlyShowsWhatYouMaySee(TestCase):

    def setUp(self):
        self.owner = User.objects.create_user('owner', 'o@x.test', 'pw')
        self.stranger = User.objects.create_user('stranger', 's@x.test', 'pw')
        self.client.force_login(self.owner)
        self.private = self.a_build(SECRET)
        self.second = self.a_build(OTHER)

    def a_build(self, name):
        # posts publish_choice without publish, as an unchecked box; keeps the build private
        self.client.post('/createproject/', {
            'project': name, 'charname': name, 'level': '150',
            'class': 'Iop', 'where_to_go': 'wizard',
            'publish_choice': '1'})
        char = Char.objects.order_by('-id').first()
        self.client.get('/solution/%d/' % char.id, follow=True)
        char.refresh_from_db()
        return char

    def compare(self, *refs):
        return self.client.get('/compare_sets/%s/' % '/'.join(str(r) for r in refs))

    def test_the_owner_can_compare_their_own_two(self):
        """The opposite case: without it, a view that 404s on everything would
        pass every refusal below."""
        response = self.compare(self.private.id, self.second.id)
        self.assertEqual(200, response.status_code)
        body = response.content.decode('utf-8', 'replace')
        self.assertIn(SECRET, body)
        self.assertIn(OTHER, body)

    def test_a_stranger_gets_nothing_from_two_bare_ids(self):
        self.client.force_login(self.stranger)
        response = self.compare(self.private.id, self.second.id)
        self.assertEqual(404, response.status_code)
        self.assertNotIn(SECRET, response.content.decode('utf-8', 'replace'),
                         'the refusal page carries the private name anyway')

    def test_an_anonymous_visitor_gets_nothing_either(self):
        self.client.logout()
        response = self.compare(self.private.id, self.second.id)
        self.assertEqual(404, response.status_code)
        self.assertNotIn(SECRET, response.content.decode('utf-8', 'replace'))

    def test_the_encoded_form_still_needs_the_build_to_be_shared(self):
        """The share link is the other door, and it has its own lock."""
        self.client.force_login(self.stranger)
        refs = ['s%s' % encode_char_id(self.private.id),
                's%s' % encode_char_id(self.second.id)]
        response = self.compare(*refs)
        self.assertEqual(404, response.status_code)
        self.assertNotIn(SECRET, response.content.decode('utf-8', 'replace'))

    def test_two_shared_builds_compare_for_anybody(self):
        for char in (self.private, self.second):
            char.link_shared = True
            char.save()
        self.client.force_login(self.stranger)
        refs = ['s%s' % encode_char_id(self.private.id),
                's%s' % encode_char_id(self.second.id)]
        response = self.compare(*refs)
        self.assertEqual(200, response.status_code,
                         'two shared builds no longer compare')
        self.assertIn(SECRET, response.content.decode('utf-8', 'replace'))

    def test_one_shared_and_one_private_is_not_half_a_comparison(self):
        self.second.link_shared = True
        self.second.save()
        self.client.force_login(self.stranger)
        response = self.compare('s%s' % encode_char_id(self.second.id),
                                self.private.id)
        self.assertEqual(404, response.status_code)
        self.assertNotIn(SECRET, response.content.decode('utf-8', 'replace'))
