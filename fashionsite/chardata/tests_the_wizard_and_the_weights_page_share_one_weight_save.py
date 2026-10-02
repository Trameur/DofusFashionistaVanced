# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The wizard's sliders and the weight boxes save through one helper; the build defaults are read without saving."""

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase

from chardata.char_blobs import read_char_blob
from chardata.coaching_view import create_build
from chardata.presets import default_build_weights, reapply_build_weights
from chardata.stats_weights import get_stats_weights, set_stats_weights
from chardata.wizard_sliders import (_raw_sections, _sections, apply_weight_fields,
                                     set_wizard_sliders)
from fashionistapulp.structure import set_current_game_version

VERSIONS = ('dofus3', 'beta', 'dofus2', 'touch', 'retro')


class TheRawSectionsHoldEverySliderTests(TestCase):

    def test_every_offered_slider_comes_from_the_raw_lists_in_order(self):
        raw = {key: keys for key, _label, keys in _raw_sections()}
        for version in VERSIONS:
            for key, _label, keys in _sections(version):
                with self.subTest(version=version, section=key):
                    self.assertEqual(keys, [k for k in raw[key] if k in keys])

    def test_damage_follows_power(self):
        offense = dict((key, keys) for key, _label, keys in _raw_sections())['offense']
        self.assertEqual(offense.index('pow') + 1, offense.index('dam'))


class _BuildMixin(object):
    level = 200

    def build(self, version):
        set_current_game_version(version)
        owner = User.objects.create_user('w-%d' % User.objects.count(),
                                         'x@test.local', 'pw-42-solid')
        request = RequestFactory().post('/')
        request.user = owner
        return create_build(request, 'Iop', self.level, {'str'}, version)

    def tearDown(self):
        set_current_game_version('dofus3')


class OneHelperSavesTheWeightsTests(_BuildMixin, TestCase):

    def test_the_wizard_and_the_weight_boxes_store_the_same_weights(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                first, second = self.build(version), self.build(version)
                set_wizard_sliders(first, {'slider_str': '90', 'slider_perres': '80'})
                apply_weight_fields(second, {'weight_str': '90', 'weight_perres': '80'},
                                    'weight_')
                self.assertEqual(get_stats_weights(first), get_stats_weights(second))

    def test_a_base_replaces_the_stored_weights_under_the_fields(self):
        char = self.build('dofus3')
        weights = get_stats_weights(char)
        weights['vit'] = 999
        set_stats_weights(char, weights)
        base = default_build_weights(char)
        saved = apply_weight_fields(char, {'weight_str': '42'}, 'weight_', base)
        self.assertEqual(42, saved['str'])
        self.assertEqual(int(base['vit']), get_stats_weights(char)['vit'])

    def test_a_base_without_a_posted_stat_reads_it_as_zero(self):
        char = self.build('dofus3')
        base = default_build_weights(char)
        base.pop('trapdam', None)
        base.pop('str', None)
        saved = apply_weight_fields(char, {'weight_trapdam': '0', 'weight_str': '30'},
                                    'weight_', base)
        self.assertEqual(0, saved['trapdam'])
        self.assertEqual(30, saved['str'])

    def test_the_defaults_are_read_without_being_saved(self):
        char = self.build('dofus3')
        weights = get_stats_weights(char)
        weights['vit'] = 999
        set_stats_weights(char, weights)
        before = char.stats_weight
        defaults = default_build_weights(char)
        self.assertEqual(before, char.stats_weight)
        reapply_build_weights(char)
        self.assertEqual(defaults, read_char_blob(char.stats_weight, {}, 'stats_weight', char))


class ALowLevelBuildSavesAlikeTests(OneHelperSavesTheWeightsTests):
    level = 20
