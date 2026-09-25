# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""POST workshop/stock/ answers 400 to non-finite numbers and deep nesting."""

from django.contrib.auth.models import User
from django.test import TestCase

from chardata.models import WorkshopStock


class TheStockEndpointRefusesNumbersJsonCannotHoldTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user('stock-finite', 'sf@test.local', 'pw-4242xy')
        self.client.force_login(self.user)
        WorkshopStock.objects.create(
            user=self.user, game_version='dofus3', ingredient_ankama_id=7,
            ingredient_subtype='resources', owned=3)

    def _post(self, body):
        return self.client.post('/workshop/stock/', data=body,
                                content_type='application/json')

    def _assert_refused_and_unchanged(self, body):
        resp = self._post(body)
        self.assertEqual(400, resp.status_code)
        rows = list(WorkshopStock.objects.filter(user=self.user)
                    .values_list('ingredient_ankama_id', 'owned'))
        self.assertEqual([(7, 3)], rows)

    def test_infinity_as_owned_is_refused(self):
        self._assert_refused_and_unchanged(
            '{"updates": [{"ingredient_ankama_id": 7, "subtype": "resources", '
            '"owned": Infinity}]}')

    def test_infinity_as_ingredient_id_is_refused(self):
        self._assert_refused_and_unchanged(
            '{"updates": [{"ingredient_ankama_id": -Infinity, '
            '"subtype": "resources", "owned": 1}]}')

    def test_an_overflowing_float_as_owned_is_refused(self):
        self._assert_refused_and_unchanged(
            '{"updates": [{"ingredient_ankama_id": 7, "subtype": "resources", '
            '"owned": 1e400}]}')

    def test_an_overflowing_float_as_ingredient_id_is_refused(self):
        self._assert_refused_and_unchanged(
            '{"updates": [{"ingredient_ankama_id": 1e400, '
            '"subtype": "resources", "owned": 1}]}')

    def test_nan_as_owned_is_refused(self):
        self._assert_refused_and_unchanged(
            '{"updates": [{"ingredient_ankama_id": 7, "subtype": "resources", '
            '"owned": NaN}]}')

    def test_a_deeply_nested_body_is_refused(self):
        self._assert_refused_and_unchanged('[' * 200000 + ']' * 200000)

    def test_a_finite_float_still_sets_the_stock(self):
        resp = self._post(
            '{"updates": [{"ingredient_ankama_id": 7, "subtype": "resources", '
            '"owned": 5.0}]}')
        self.assertEqual(200, resp.status_code)
        self.assertEqual(5, WorkshopStock.objects.get(user=self.user).owned)
