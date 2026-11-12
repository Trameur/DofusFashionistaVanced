# -*- coding: utf-8 -*-
"""Django's stock password pages store what they receive, and this site stores a browser hash."""
from django.contrib.auth.models import User
from django.test import TestCase

STOCK_ROUTES = (
    '/password_change/',
    '/password_change/done/',
    '/password_reset/',
    '/password_reset/done/',
    '/reset/done/',
)


class TheStockRoutesAreGone(TestCase):

    def test_they_answer_not_found_to_a_visitor(self):
        for path in STOCK_ROUTES:
            self.assertEqual(self.client.get(path).status_code, 404, path)

    def test_they_answer_not_found_to_a_signed_in_account(self):
        self.client.force_login(User.objects.create_user('someone', 's@test.local', 'pw-42-solid'))
        for path in STOCK_ROUTES:
            self.assertEqual(self.client.get(path).status_code, 404, path)

    def test_a_post_cannot_store_a_raw_password(self):
        user = User.objects.create_user('someone', 's@test.local', 'pw-42-solid')
        stored = user.password
        self.client.force_login(user)
        response = self.client.post('/password_change/', {
            'old_password': 'pw-42-solid',
            'new_password1': 'another-raw-one-77',
            'new_password2': 'another-raw-one-77',
        })
        self.assertEqual(response.status_code, 404)
        user.refresh_from_db()
        self.assertEqual(user.password, stored)


class OurOwnRoutesRemain(TestCase):

    def test_the_login_page_still_opens(self):
        self.assertEqual(self.client.get('/login/').status_code, 200)

    def test_the_menu_of_a_signed_in_account_still_renders(self):
        self.client.force_login(User.objects.create_user('someone', 's@test.local', 'pw-42-solid'))
        self.assertContains(self.client.get('/manageaccount/'), 'action="/logout/"')
