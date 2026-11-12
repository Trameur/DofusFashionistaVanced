"""The reset form refuses a short new password; what is posted is the raw password, never a hash."""
from django.contrib.auth.models import User
from django.test import TestCase

from chardata.login_view import (MIN_PASSWORD_LENGTH,
                                 _generate_token_for_password_reset,
                                 _prehash_password)


class TheResetForm(TestCase):

    def setUp(self):
        self.user = User.objects.create_user('forgetful', 'f@x.test', 'old-hash')
        token = _generate_token_for_password_reset(
            self.user.username, self.user.password, self.user.email)
        self.url = '/do_recover_password/%s/%s/' % (self.user.username, token)

    def reset(self, new):
        return self.client.post(self.url, {'new_password': new,
                                           'confirm_password': new})

    def test_the_minimum_is_eight(self):
        self.assertEqual(8, MIN_PASSWORD_LENGTH)

    def test_a_short_password_is_refused_and_nothing_changes(self):
        before = self.user.password
        response = self.reset('short12')
        self.assertContains(response, 'Your password must have at least %d characters.'
                            % MIN_PASSWORD_LENGTH)
        self.user.refresh_from_db()
        self.assertEqual(before, self.user.password)

    def test_the_form_and_the_register_page_carry_the_same_number(self):
        form = self.client.get(self.url).content.decode('utf-8')
        self.assertIn('minlength="%d"' % MIN_PASSWORD_LENGTH, form)
        register = self.client.get('/login_page/').content.decode('utf-8')
        self.assertIn('data-min-length="%d"' % MIN_PASSWORD_LENGTH, register)

    def test_a_password_of_eight_is_stored_as_the_prehash(self):
        response = self.reset('longenou')
        self.assertTemplateUsed(response, 'chardata/password_was_reset.html')
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(_prehash_password('longenou')))
