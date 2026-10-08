# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The wizard offers the weights page's rows and saves every weight and minimum they post, as the page does."""
import pickle

from django.test import TestCase

from chardata.min_stats import get_min_stats, get_min_stats_by_key
from chardata.presets import default_build_weights
from chardata.stats_weights import get_stats_weights, set_stats_weights
from chardata.tests_the_weights_and_minimums_page_offers_what_each_version_reaches import (
    _PageMixin, _parse)
from chardata.weights_minimums import minimum_keys


class _WizardMixin(_PageMixin):

    def wizard_post(self, data):
        response = self.client.post(self.url('wizardpost'), data)
        self.assertEqual(302, response.status_code)
        self.char.refresh_from_db()

    def store(self, weights=None, minimums=None):
        if weights:
            stored = get_stats_weights(self.char)
            stored.update(weights)
            set_stats_weights(self.char, stored)
        if minimums is not None:
            self.char.minimum_stats = pickle.dumps(dict(minimums, adv_mins={}))
            self.char.save()


class TheWizardOffersTheRowsOfTheWeightsPageTests(_WizardMixin, TestCase):

    def test_every_box_of_the_weights_page_is_on_the_wizard(self):
        wizard = self.inputs(self.page('wizard'))
        weights = self.inputs(self.page('stats'))
        self.assertEqual(sorted(weights), sorted(wizard))
        for key in minimum_keys(self.version):
            self.assertIn('min_%s' % key, wizard)
        for field, attrs in weights.items():
            self.assertEqual(attrs.get('name'), wizard[field].get('name'))
            self.assertEqual(attrs.get('max'), wizard[field].get('max'))

    def test_the_boxes_sit_in_the_form_the_tailor_button_submits(self):
        html = self.page('wizard')
        tags = _parse(html).tags
        form_ids = [attrs.get('id') for tag, attrs in tags if tag == 'form']
        self.assertIn('wizard-form', form_ids)
        self.assertNotIn('main_form', form_ids)
        ids = {attrs.get('id') for _tag, attrs in tags}
        for needed in ('weights_reset', 'wm-col-weight', 'wm-col-min', 'wm-state',
                       'wm-defaults', 'button-reset-weights', 'section-apmprange'):
            self.assertIn(needed, ids)
        for gone in ('min_AP', 'button-reset-sliders', 'button-save', 'button-discard-changes'):
            self.assertNotIn(gone, ids)

    def test_the_boxes_start_where_the_build_is(self):
        self.store(minimums={'AP': 11, 'Wisdom': 300})
        html = self.page('wizard')
        state = [body for attrs, body in _parse(html).scripts if attrs.get('id') == 'wm-state']
        self.assertEqual(1, len(state))
        self.assertIn('"wis": 300', state[0])
        self.assertIn('"ap": 11', state[0])


class TouchWizardOffersTheRowsOfTheWeightsPageTests(TheWizardOffersTheRowsOfTheWeightsPageTests):
    version = 'touch'


class RetroWizardOffersTheRowsOfTheWeightsPageTests(TheWizardOffersTheRowsOfTheWeightsPageTests):
    version = 'retro'


class TheWizardSavesWhatItPostsTests(_WizardMixin, TestCase):

    def test_a_weight_and_a_minimum_beyond_ap_mp_and_range_are_saved(self):
        self.wizard_post({'weight_cha': '41', 'min_vit': '1700', 'min_ap': '10'})
        self.assertEqual(41, get_stats_weights(self.char)['cha'])
        minimums = get_min_stats_by_key(self.char)
        self.assertEqual(1700, minimums['vit'])
        self.assertEqual(10, minimums['ap'])

    def test_an_emptied_minimum_is_removed(self):
        self.store(minimums={'Vitality': 900, 'Wisdom': 300})
        self.wizard_post({'min_vit': '', 'min_wis': '300'})
        minimums = get_min_stats_by_key(self.char)
        self.assertNotIn('vit', minimums)
        self.assertEqual(300, minimums['wis'])

    def test_a_reset_restores_the_default_weights_under_what_was_typed(self):
        self.store(weights={'vit': 999, 'str': 1})
        self.wizard_post({'weights_reset': '1', 'weight_str': '55'})
        stored = get_stats_weights(self.char)
        self.assertEqual(int(default_build_weights(self.char)['vit']), stored['vit'])
        self.assertEqual(55, stored['str'])

    def test_a_form_that_does_not_reset_keeps_the_weights_it_shows(self):
        self.store(weights={'vit': 999})
        self.wizard_post({'weights_reset': '0', 'weight_vit': '999', 'weight_str': '55'})
        stored = get_stats_weights(self.char)
        self.assertEqual(999, stored['vit'])
        self.assertEqual(55, stored['str'])

    def test_the_old_slider_and_minimum_fields_still_work(self):
        self.store(minimums={})
        self.wizard_post({'slider_vit': '77', 'min_AP': '9', 'min_MP': '', 'min_Range': '3'})
        self.assertEqual(77, get_stats_weights(self.char)['vit'])
        minimums = get_min_stats(self.char)
        self.assertEqual(9, minimums['AP'])
        self.assertEqual(0, minimums['MP'])
        self.assertEqual(3, minimums['Range'])

    def test_a_post_with_no_weight_and_no_minimum_changes_neither(self):
        self.store(weights={'vit': 61, 'cha': 17},
                   minimums={'AP': 11, 'Wisdom': 300, 'Vitality': 900})
        weights = get_stats_weights(self.char)
        minimums = get_min_stats(self.char)
        self.wizard_post({'ap_exo': 'no', 'mp_exo': 'no'})
        self.assertEqual(weights, get_stats_weights(self.char))
        self.assertEqual(minimums, get_min_stats(self.char))

    def test_a_post_of_only_the_old_minimums_leaves_the_weights_alone(self):
        self.store(weights={'vit': 61})
        weights = get_stats_weights(self.char)
        self.wizard_post({'min_AP': '8'})
        self.assertEqual(weights, get_stats_weights(self.char))
        self.assertEqual(8, get_min_stats(self.char)['AP'])


class ALowLevelBuildSavesWhatTheWizardPostsTests(TheWizardSavesWhatItPostsTests):
    level = 20
