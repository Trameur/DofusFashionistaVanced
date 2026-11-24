# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The monster page links to the newest build of the viewer, never to a newer build of another user."""
import re

from django.contrib.auth.models import User
from django.test import TestCase

from chardata.models import Char
from chardata.targets import _monster_index
from chardata.tests_the_target_picker_belongs_to_dofus3_and_beta import _make_build


class TheMonsterPageLinkOwnerTests(TestCase):

    def _links(self):
        monster_id = _monster_index('dofus3')[0][0][0]
        page = self.client.get('/encyclopedia/monster/%d-x/' % monster_id, follow=True)
        self.assertEqual(200, page.status_code)
        return re.findall(r'class="monster-try-build" href="([^"]+)"', page.content.decode('utf-8'))

    def test_another_users_newer_build_is_never_offered(self):
        viewer = User.objects.create_user('own1', 'own1@test.local', 'pw-42-solid')
        other = User.objects.create_user('own2', 'own2@test.local', 'pw-42-solid')
        mine = _make_build(viewer, 'dofus3', 'mine')
        theirs = _make_build(other, 'dofus3', 'theirs')
        Char.objects.filter(pk=mine.pk).update(modified_time='2020-01-01T00:00:00Z')
        Char.objects.filter(pk=theirs.pk).update(modified_time='2030-01-01T00:00:00Z')
        self.client.force_login(viewer)
        links = self._links()
        self.assertTrue(links)
        for link in links:
            self.assertTrue(link.startswith('/spells/%d/' % mine.pk), link)

    def test_a_viewer_without_a_build_gets_no_link_though_others_have_one(self):
        viewer = User.objects.create_user('own3', 'own3@test.local', 'pw-42-solid')
        other = User.objects.create_user('own4', 'own4@test.local', 'pw-42-solid')
        _make_build(other, 'dofus3', 'theirs')
        self.client.force_login(viewer)
        self.assertEqual([], self._links())
