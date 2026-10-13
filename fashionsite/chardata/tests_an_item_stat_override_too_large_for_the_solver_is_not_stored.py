# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""An item stat override too large for the solver is refused and not stored, the bound is the build import's, and a build with an override at the bound still solves."""
from django.test import TestCase

from chardata.fashionista_build import MAX_STAT_VALUE
from chardata.lock_forbid import get_stat_overrides
from chardata.tests_the_weights_and_minimums_page_offers_what_each_version_reaches import _PageMixin
from fashionistapulp.structure import get_structure

TOO_LARGE = ('9' * 400, '9' * 300, str(MAX_STAT_VALUE + 1), str(-MAX_STAT_VALUE - 1))
MOST_HOPS = 4


class AnItemStatOverrideTooLargeForTheSolverIsNotStoredTests(_PageMixin, TestCase):

    def setUp(self):
        super().setUp()
        structure = get_structure(self.version)
        self.stat_id = structure.get_stat_by_key('vit').id
        self.item_id = next(item.id for item in structure.get_items_list()
                            if any(stat_id == self.stat_id for stat_id, _value in item.stats))

    def override(self, value):
        response = self.client.post(self.url('setitemstatoverride'),
                                    {'item_id': self.item_id, 'stat_id': self.stat_id, 'value': value})
        self.assertEqual(200, response.status_code)
        self.char.refresh_from_db()
        return response.content.decode('utf-8')

    def stored(self):
        return get_stat_overrides(self.char).get(self.item_id, {}).get(self.stat_id)

    def test_a_value_outside_the_bound_is_refused_and_keeps_the_stored_override(self):
        self.assertEqual('ok', self.override('120'))
        for posted in TOO_LARGE:
            with self.subTest(posted=posted[:12]):
                self.assertEqual('error', self.override(posted))
                self.assertEqual(120, self.stored())

    def test_a_value_at_the_bound_is_stored(self):
        for posted in (MAX_STAT_VALUE, -MAX_STAT_VALUE):
            with self.subTest(posted=posted):
                self.assertEqual('ok', self.override(str(posted)))
                self.assertEqual(posted, self.stored())

    def test_a_build_with_an_override_at_the_bound_still_solves(self):
        self.assertEqual('ok', self.override(str(MAX_STAT_VALUE)))
        response = self.client.get(self.url('fashion'))
        hops = 0
        while response.status_code == 302 and hops < MOST_HOPS:
            hops += 1
            response = self.client.get(response['Location'])
        self.assertEqual(200, response.status_code)
        self.assertIn('chardata/solution.html', [template.name for template in response.templates])
        self.assertContains(response, 'var MAX_STAT_VALUE = %d;' % MAX_STAT_VALUE)

    def test_the_inclusions_page_gives_its_script_the_bound(self):
        response = self.client.get(self.url('inclusions'))
        self.assertContains(response, 'var MAX_STAT_VALUE = %d;' % MAX_STAT_VALUE)


class TouchItemStatOverrideTooLargeForTheSolverIsNotStoredTests(
        AnItemStatOverrideTooLargeForTheSolverIsNotStoredTests):
    version = 'touch'


class RetroItemStatOverrideTooLargeForTheSolverIsNotStoredTests(
        AnItemStatOverrideTooLargeForTheSolverIsNotStoredTests):
    version = 'retro'
