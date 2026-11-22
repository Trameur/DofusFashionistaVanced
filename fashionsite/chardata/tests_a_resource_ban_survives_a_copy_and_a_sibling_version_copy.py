# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A resource ban travels with a duplicated project and with a copy to a sibling version, where keys the target lacks are ignored."""
import pickle

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase

from chardata import resource_ban
from chardata.char_blobs import read_char_blob
from chardata.models import Char
from chardata.version_copy import copy_build
from fashionistapulp.structure import set_current_game_version

CRIMSON_PEBBLE = '12737:resources'
BETA_LACKS = '999999999:resources'


class ABanIsCarriedTests(TestCase):

    def setUp(self):
        set_current_game_version('dofus3')
        self.addCleanup(set_current_game_version, 'dofus3')
        self.owner = User.objects.create_user('copyban', 'cb@test.local', 'pw-copy-ban-1')
        self.char = Char.objects.create(
            name='Banned', char_name='banned', char_class='Iop', char_build='build',
            level=200, minimum_stats=pickle.dumps({}), minimum_crits=b'',
            stats_weight=pickle.dumps({'Vitality': 1.0}),
            options=pickle.dumps({resource_ban.OPTION_KEY: [CRIMSON_PEBBLE, BETA_LACKS]}),
            inclusions=pickle.dumps({}), exclusions=pickle.dumps([]),
            owner=self.owner, link_shared=False, game_version='dofus3')

    def stored(self, char):
        options = read_char_blob(Char.objects.get(pk=char.pk).options, {}, 'options')
        return options.get(resource_ban.OPTION_KEY)

    def copy_to_the_beta(self):
        request = RequestFactory().post('/copy/')
        request.user = self.owner
        request.session = self.client.session
        copied, _missing = copy_build(request, Char.objects.get(pk=self.char.pk), 'beta')
        self.assertIsNotNone(copied)
        return Char.objects.get(pk=copied.pk)

    def test_a_duplicated_project_carries_the_ban(self):
        self.client.force_login(self.owner)
        self.client.post('/duplicatemyproject/%d/' % self.char.pk)

        copy = Char.objects.exclude(pk=self.char.pk).get()
        self.assertEqual([CRIMSON_PEBBLE, BETA_LACKS], self.stored(copy))

    def test_a_copy_to_the_beta_carries_the_ban(self):
        copied = self.copy_to_the_beta()

        self.assertEqual('beta', copied.game_version)
        self.assertEqual([CRIMSON_PEBBLE, BETA_LACKS], self.stored(copied))

    def test_the_copy_reads_only_the_keys_its_version_knows(self):
        copied = self.copy_to_the_beta()

        self.assertEqual([CRIMSON_PEBBLE], resource_ban.banned_resource_keys(copied))
