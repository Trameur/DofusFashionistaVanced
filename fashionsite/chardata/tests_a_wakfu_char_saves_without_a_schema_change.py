# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.

"""A build of Wakfu is an ordinary Char row, found only under its own version."""
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.test import RequestFactory, TestCase

from chardata.data_versions import current_data_version
from chardata.models import Char
from chardata.util import get_char_or_raise


def _wakfu_char(owner=None):
    return Char.objects.create(
        owner=owner, name='wakfu build', char_name='wakfu build', char_class='Iop',
        char_build='build',
        level=245, minimum_stats=b'', minimum_crits=b'', stats_weight=b'', options=b'',
        inclusions=b'', exclusions=b'', minimal_solution=b'', link_shared=True,
        game_version='wakfu')


def _request(version, user=None):
    request = RequestFactory().get('/')
    request.game_version = version
    request.user = user or type(
        'Anonymous', (), {'is_authenticated': False, 'is_anonymous': True})()
    request.session = {}
    return request


class AWakfuCharSavesWithoutASchemaChangeTests(TestCase):
    def test_a_saved_wakfu_char_keeps_its_version_and_the_data_version(self):
        char = _wakfu_char()
        char.refresh_from_db()
        self.assertEqual('wakfu', char.game_version)
        self.assertEqual(current_data_version('wakfu'), char.created_version)

    def test_a_wakfu_char_is_found_under_wakfu_and_refused_under_dofus3(self):
        char = _wakfu_char()
        with self.assertRaises(Http404):
            get_char_or_raise(_request('dofus3'), char.pk)
        try:
            served = get_char_or_raise(_request('wakfu'), char.pk)
        except PermissionDenied:
            served = char
        self.assertEqual(char.pk, served.pk)

    def test_the_owner_of_a_wakfu_char_gets_it_under_wakfu_and_a_404_under_dofus3(self):
        owner = get_user_model().objects.create_user('wakfu_owner', password='x')
        char = _wakfu_char(owner)
        self.assertEqual(char.pk, get_char_or_raise(_request('wakfu', owner), char.pk).pk)
        with self.assertRaises(Http404):
            get_char_or_raise(_request('dofus3', owner), char.pk)
