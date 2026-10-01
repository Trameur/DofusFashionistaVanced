# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""statspost keeps every weight it is not sent; a field sent blank still writes 0."""
from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase

from chardata.coaching_view import create_build
from chardata.stats_weights import get_stats_weights, set_stats_weights
from fashionistapulp.structure import set_current_game_version

PREFIX = {'dofus3': '', 'touch': '/touch', 'retro': '/retro'}


class _SaveMixin(object):
    version = 'dofus3'
    level = 200

    def setUp(self):
        set_current_game_version(self.version)
        self.owner = User.objects.create_user('weigher', 'w@test.local', 'pw-42-solid')
        self.client.force_login(self.owner)
        request = RequestFactory().post('/')
        request.user = self.owner
        self.char = create_build(request, 'Iop', self.level, {'str'}, self.version)

    def tearDown(self):
        set_current_game_version('dofus3')

    def save(self, data):
        response = self.client.post('%s/statspost/%d/' % (PREFIX[self.version], self.char.pk),
                                    data)
        self.assertEqual(200, response.status_code)
        self.char.refresh_from_db()
        return get_stats_weights(self.char)


class AWeightsSaveKeepsTheRowsItDoesNotPostTests(_SaveMixin, TestCase):

    def test_the_hp_weight_survives_a_save_without_it(self):
        weights = get_stats_weights(self.char)
        weights['hp'] = 33
        set_stats_weights(self.char, weights)
        after = self.save({'weight_str': '10'})
        self.assertEqual(33, after['hp'])
        self.assertEqual(10, after['str'])

    def test_a_field_sent_blank_still_writes_zero(self):
        weights = get_stats_weights(self.char)
        weights['wis'] = 40
        set_stats_weights(self.char, weights)
        self.assertEqual(0, self.save({'weight_wis': ''})['wis'])


class ALowLevelBuildKeepsItsRowsTooTests(AWeightsSaveKeepsTheRowsItDoesNotPostTests):
    level = 20


class TouchKeepsItsPvpWeightsTests(_SaveMixin, TestCase):
    version = 'touch'

    def test_every_pvp_weight_survives_a_save_without_it(self):
        weights = get_stats_weights(self.char)
        pvp = sorted(key for key in weights if key.startswith('pvp'))
        self.assertTrue(pvp)
        for at, key in enumerate(pvp):
            weights[key] = 10 + at
        set_stats_weights(self.char, weights)
        after = self.save({'weight_str': '10'})
        for at, key in enumerate(pvp):
            self.assertEqual(10 + at, after[key], key)
