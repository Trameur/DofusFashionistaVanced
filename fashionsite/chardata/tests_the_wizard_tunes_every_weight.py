# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The wizard offers a slider for every weight the version's gear can steer.

Until 2026-09-18 it showed a hand-picked subset: no AP, MP or Range, which
TemporiX makes worth tuning since it lifts their caps, no % damage or resist by
attack type, no single element. Only the Characteristics Weights page had them.
Retro also lost its damage weight on every wizard save: its gear carries plain
damage only, and the save rebuilt that weight as the sum of the elemental ones,
which are zero there.
"""
from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase

from chardata.coaching_view import create_build
from chardata.stats_weights import get_stats_weights, set_stats_weights
from chardata.wizard_sliders import get_wizard_sliders, set_wizard_sliders
from fashionistapulp.structure import set_current_game_version

VERSIONS = ('dofus3', 'beta', 'dofus2', 'retro', 'touch')


class TheWizardTunesEveryWeightTests(TestCase):

    def _char(self, version, char_class='Iop', aspects=None):
        set_current_game_version(version)
        self.addCleanup(set_current_game_version, 'dofus3')
        owner, _ = User.objects.get_or_create(
            username='wizall', defaults={'email': 'wa@test.local'})
        request = RequestFactory().post('/')
        request.user = owner
        return create_build(request, char_class, 200, aspects or {'agi'}, version)

    def _sliders(self, char):
        return {sub.key: sub for section in get_wizard_sliders(char)
                for sub in section.subsliders}

    def _posted(self, char, **moved):
        """What the page posts: every slider where it started, but `moved`."""
        posted = {'slider_%s' % key: str(int(slider.abs_value + 0.5))
                  for key, slider in self._sliders(char).items()}
        posted.update({'slider_%s' % key: str(value)
                       for key, value in moved.items()})
        return posted

    def test_ap_mp_and_range_have_their_sliders_on_every_version(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                sections = get_wizard_sliders(self._char(version))
                self.assertEqual('apmprange', sections[0].key)
                self.assertEqual(['ap', 'mp', 'range'],
                                 [sub.key for sub in sections[0].subsliders])

    def test_every_weight_the_gear_can_carry_has_a_slider(self):
        from chardata.stat_availability import stats_with_no_source
        from fashionistapulp.structure import get_structure
        for version in VERSIONS:
            with self.subTest(version=version):
                char = self._char(version)
                keys = set(self._sliders(char))
                members = set()
                for slider in self._sliders(char).values():
                    members.update(slider.members or ())
                # Damage is the sum of the elemental damages where gear
                # carries them, so it has a slider on Retro only.
                expected = {stat.key for stat in get_structure().get_stats_list()
                            } - set(stats_with_no_source(version))
                if version != 'retro':
                    expected.discard('dam')
                self.assertEqual(set(), expected - keys - members)

    def test_a_stat_no_gear_carries_gets_no_slider(self):
        keys = set(self._sliders(self._char('retro')))
        for dead in ('cridam', 'lock', 'permedam', 'earthdam'):
            self.assertNotIn(dead, keys)
        self.assertNotIn('trapdam', set(self._sliders(self._char('touch'))))
        self.assertNotIn('hp', set(self._sliders(self._char('dofus3'))))

    def test_moving_the_ap_slider_sets_the_ap_weight(self):
        char = self._char('touch')
        set_wizard_sliders(char, self._posted(char, ap=5000))
        self.assertEqual(5000, get_stats_weights(char)['ap'])

    def test_a_retro_save_keeps_the_damage_weight(self):
        char = self._char('retro', 'Iop', {'str'})
        before = get_stats_weights(char)['dam']
        self.assertGreater(before, 0)
        self.assertIn('dam', self._sliders(char))
        set_wizard_sliders(char, self._posted(char))
        self.assertEqual(before, get_stats_weights(char)['dam'])

    def test_elemental_damage_still_adds_up_to_damage_elsewhere(self):
        char = self._char('dofus3')
        self.assertNotIn('dam', self._sliders(char))
        set_wizard_sliders(char, self._posted(char, earthdam=100))
        weights = get_stats_weights(char)
        self.assertEqual(sum(weights['%sdam' % element] for element in
                             ('neut', 'earth', 'fire', 'water', 'air')),
                         weights['dam'])

    def test_an_untouched_aggregate_keeps_each_resist(self):
        char = self._char('dofus3')
        weights = get_stats_weights(char)
        weights.update(neutresper=100, earthresper=300)
        set_stats_weights(char, weights)
        set_wizard_sliders(char, self._posted(char))
        weights = get_stats_weights(char)
        self.assertEqual((100, 300), (weights['neutresper'], weights['earthresper']))

    def test_a_moved_aggregate_sets_each_resist_and_a_single_one_wins(self):
        char = self._char('dofus3')
        set_wizard_sliders(char, self._posted(char, perres=200, fireresper=50))
        weights = get_stats_weights(char)
        self.assertEqual(200, weights['neutresper'])
        self.assertEqual(200, weights['airresper'])
        self.assertEqual(50, weights['fireresper'])

    def test_a_weight_beyond_the_usual_range_survives_a_save(self):
        char = self._char('dofus3')
        weights = get_stats_weights(char)
        weights['lock'] = 5000
        set_stats_weights(char, weights)
        slider = self._sliders(char)['lock']
        self.assertGreaterEqual(slider.max_value, 5000)
        set_wizard_sliders(char, self._posted(char))
        self.assertEqual(5000, get_stats_weights(char)['lock'])
