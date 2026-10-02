# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A stored Range minimum of 0 is no minimum on the weights page, as the next save would make it."""
import json
import pickle

from django.test import TestCase

from chardata.min_stats import get_min_stats
from chardata.tests_the_weights_and_minimums_page_offers_what_each_version_reaches import (
    _PageMixin, _parse)
from chardata.weights_minimums import edit_sections


class ARangeMinimumOfZeroShowsAsNoneTests(_PageMixin, TestCase):
    level = 20

    def store(self, minimums):
        self.char.minimum_stats = pickle.dumps(dict(minimums, adv_mins={}))
        self.char.save()

    def shown(self):
        scripts = _parse(self.page()).scripts
        return [json.loads(body) for attrs, body in scripts
                if attrs.get('id') == 'wm-state'][0]['minimums']

    def counted(self):
        return [section['count'] for section in edit_sections(self.char)
                if section['key'] == 'apmprange'][0]

    def test_a_range_of_zero_is_shown_empty_and_not_counted(self):
        self.store({'AP': 6, 'MP': 3, 'Range': 0})
        minimums = self.shown()
        self.assertEqual('', minimums['range'])
        self.assertEqual(6, minimums['ap'])
        self.assertEqual(2, self.counted())

    def test_a_save_of_another_box_leaves_what_the_page_showed(self):
        self.store({'AP': 6, 'MP': 3, 'Range': 0})
        before = self.shown()
        state = self.post({'weight_cha': '2'})
        self.assertEqual(before['range'], state['minimums']['range'])
        self.assertNotIn('Range', get_min_stats(self.char))

    def test_a_range_above_zero_is_shown_and_counted(self):
        self.store({'AP': 6, 'MP': 3, 'Range': 2})
        self.assertEqual(2, self.shown()['range'])
        self.assertEqual(3, self.counted())


class AMaxLevelBuildShowsARangeOfZeroAsNoneTests(ARangeMinimumOfZeroShowsAsNoneTests):
    level = 200
