# -*- coding: utf-8 -*-
"""Invisible characters and look-alike handles do not let an account show another's name."""
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase

from chardata.login_view import _username_key
from chardata.models import UserAlias, public_handle
from chardata.profile_view import _resolve_user
from chardata.public_name import clean_public_name, has_unsafe_character, public_name_is_taken

INVISIBLE = ('\u00ad', '\u034f', '\u200b', '\u200d', '\u202e', '\u2028', '\u2060', '\u2065',
             '\u2800', '\u3164', '\ufe0f', '\ufeff', '\ufff0', '\U000e0080', '\U000e0100',
             '\U000e0fff')


class TheCharacters(TestCase):

    def test_invisible_characters_are_removed(self):
        for character in INVISIBLE:
            self.assertEqual(clean_public_name('Bo%sb' % character, 50), 'Bob', repr(character))

    def test_invisible_characters_are_refused(self):
        for character in INVISIBLE:
            self.assertTrue(has_unsafe_character('Bo%sb' % character), repr(character))

    def test_a_name_of_nothing_but_invisible_characters_is_empty(self):
        self.assertEqual(clean_public_name('\u3164\u200b', 50), '')

    def test_accents_and_styled_letters_are_kept(self):
        for name in ('B\u00f3b', '\uff22\uff4f\uff42', '\U0001d56f\U0001d586', '\u0416\u0430\u043d', 'Bob Smith'):
            self.assertEqual(clean_public_name(name, 50), name)
            self.assertFalse(has_unsafe_character(name), name)

    def test_a_decomposed_accent_is_composed(self):
        self.assertEqual(clean_public_name('Bo\u0301b', 50), 'B\u00f3b')

    def test_a_slash_and_control_characters_stay_out(self):
        self.assertEqual(clean_public_name('a/b\x07c\x85d', 50), 'abcd')


class TheDoors(TestCase):

    def setUp(self):
        self.bob = User.objects.create_user('Bob', 'bob@test.local', 'pw-42-solid')
        UserAlias.objects.create(user=self.bob, alias='Bob')

    def test_a_decomposed_spelling_of_a_stored_name_is_taken(self):
        other = User.objects.create_user('other', 'other@test.local', 'pw-42-solid')
        UserAlias.objects.create(user=other, alias='B\u00f3b')
        self.assertTrue(public_name_is_taken('Bo\u0301b'))

    def test_signing_up_stores_the_composed_spelling(self):
        with mock.patch('chardata.login_view.recaptcha_ok', return_value=True):
            self.client.post('/register/', {
                'username': 'Zo\u0301e', 'password': 'pw-42-solid', 'email': 'x@test.local'})
        self.assertEqual(User.objects.get(email='x@test.local').username, 'Z\u00f3e')

    def test_signing_up_with_an_invisible_character_is_refused(self):
        with mock.patch('chardata.login_view.recaptcha_ok', return_value=True):
            response = self.client.post('/register/', {
                'username': 'Bob\u200d', 'password': 'pw-42-solid', 'email': 'x@test.local'})
        self.assertEqual(response.status_code, 403)
        self.assertFalse(User.objects.filter(email='x@test.local').exists())

    def test_the_sign_up_form_is_told(self):
        response = self.client.post('/check_username/', {'username': 'Bob\u200d'})
        self.assertEqual(response.content.decode(), 'username-error')

    def test_the_sign_up_form_ignores_a_stray_space(self):
        response = self.client.post('/check_username/', {'username': ' Bob '})
        self.assertEqual(response.content.decode(), 'username-error')

    def test_the_account_page_cannot_take_a_name_with_an_invisible_character(self):
        other = User.objects.create_user('other', 'other@test.local', 'pw-42-solid')
        self.client.force_login(other)
        answer = self.client.post('/saveaccount/', {'alias': 'Bob\u200d'}).json()
        self.assertNotEqual(answer['alias'], 'Bob')
        self.assertTrue(answer['alias_notice'])

    def test_a_login_counter_ignores_invisible_characters(self):
        self.assertEqual(_username_key('Bob\u200d'), _username_key('bob'))
        self.assertEqual(_username_key('B\u00f3b'), _username_key('bob'))


class TheHandles(TestCase):

    def test_look_alike_handles_are_taken(self):
        for name in ('Player2', 'PLAYER2', 'Pl\u00e0yer2', '\uff30\uff4c\uff41\uff59\uff45\uff52\uff12', 'Player\uff12'):
            self.assertTrue(public_name_is_taken(name), name)

    def test_an_account_keeps_its_own_handle(self):
        user = User.objects.create_user('plain', 'p@test.local', 'pw-42-solid')
        self.assertFalse(public_name_is_taken(public_handle(user.pk), user))
        self.assertTrue(public_name_is_taken(public_handle(user.pk + 1), user))

    def test_a_name_that_only_starts_like_a_handle_is_free(self):
        self.assertFalse(public_name_is_taken('Player2Fan'))


class TheProfileDoor(TestCase):

    def test_the_exact_spelling_wins_over_the_first_look_alike(self):
        first = User.objects.create_user('first', 'first@test.local', 'pw-42-solid')
        second = User.objects.create_user('second', 'second@test.local', 'pw-42-solid')
        UserAlias.objects.create(user=first, alias='nick')
        UserAlias.objects.create(user=second, alias='NICK')
        self.assertEqual(_resolve_user('nick'), first)
        self.assertEqual(_resolve_user('NICK'), second)

    def test_a_folded_match_still_finds_the_account(self):
        first = User.objects.create_user('first', 'first@test.local', 'pw-42-solid')
        UserAlias.objects.create(user=first, alias='nick')
        self.assertEqual(_resolve_user('Nick'), first)
