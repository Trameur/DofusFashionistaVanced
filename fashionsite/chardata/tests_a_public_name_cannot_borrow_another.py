# -*- coding: utf-8 -*-
"""Invisible characters and look-alike handles do not let an account show another's name."""
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase

from chardata.login_view import _username_key
from chardata.models import UserAlias, public_handle
from chardata.profile_view import _resolve_user
from chardata.public_name import clean_public_name, has_unsafe_character, public_name_is_taken

INVISIBLE = ('­', '͏', '​', '‍', '‮', ' ', '⁠', '⠀',
             'ㅤ', '️', '﻿', '\U000e0100')


class TheCharacters(TestCase):

    def test_invisible_characters_are_removed(self):
        for character in INVISIBLE:
            self.assertEqual(clean_public_name('Bo%sb' % character, 50), 'Bob', repr(character))

    def test_invisible_characters_are_refused(self):
        for character in INVISIBLE:
            self.assertTrue(has_unsafe_character('Bo%sb' % character), repr(character))

    def test_a_name_of_nothing_but_invisible_characters_is_empty(self):
        self.assertEqual(clean_public_name('ㅤ​', 50), '')

    def test_accents_and_styled_letters_are_kept(self):
        for name in ('Bób', 'Ｂｏｂ', '\U0001d56f\U0001d586', 'Жан', 'Bob Smith'):
            self.assertEqual(clean_public_name(name, 50), name)
            self.assertFalse(has_unsafe_character(name), name)

    def test_a_slash_and_control_characters_stay_out(self):
        self.assertEqual(clean_public_name('a/b\x07c\x85d', 50), 'abcd')


class TheDoors(TestCase):

    def setUp(self):
        self.bob = User.objects.create_user('Bob', 'bob@test.local', 'pw-42-solid')
        UserAlias.objects.create(user=self.bob, alias='Bob')

    def test_signing_up_with_an_invisible_character_is_refused(self):
        with mock.patch('chardata.login_view.recaptcha_ok', return_value=True):
            response = self.client.post('/register/', {
                'username': 'Bob‍', 'password': 'pw-42-solid', 'email': 'x@test.local'})
        self.assertEqual(response.status_code, 403)
        self.assertFalse(User.objects.filter(email='x@test.local').exists())

    def test_the_sign_up_form_is_told(self):
        response = self.client.post('/check_username/', {'username': 'Bob‍'})
        self.assertEqual(response.content.decode(), 'username-error')

    def test_the_sign_up_form_ignores_a_stray_space(self):
        response = self.client.post('/check_username/', {'username': ' Bob '})
        self.assertEqual(response.content.decode(), 'username-error')

    def test_the_account_page_cannot_take_a_name_with_an_invisible_character(self):
        other = User.objects.create_user('other', 'other@test.local', 'pw-42-solid')
        self.client.force_login(other)
        answer = self.client.post('/saveaccount/', {'alias': 'Bob‍'}).json()
        self.assertNotEqual(answer['alias'], 'Bob')
        self.assertTrue(answer['alias_notice'])

    def test_a_login_counter_ignores_invisible_characters(self):
        self.assertEqual(_username_key('Bob‍'), _username_key('bob'))
        self.assertEqual(_username_key('Bób'), _username_key('bob'))


class TheHandles(TestCase):

    def test_look_alike_handles_are_taken(self):
        for name in ('Player2', 'PLAYER2', 'Plàyer2', 'Ｐｌａｙｅｒ２', 'Player２'):
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
