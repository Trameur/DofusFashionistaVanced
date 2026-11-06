# -*- coding: utf-8 -*-
"""A name stored by one account breaks neither the pages nor the people reading them."""
import json
import pickle
from unittest import mock

from django.contrib.auth.models import User
from django.template import Context, Template
from django.test import TestCase

from chardata.models import Char, UserAlias
from chardata.public_name import clean_public_name, public_name_is_taken
from chardata.util import json_for_script

ESCAPING_NAME = '</script><script>window.owned=1</script>'


def a_build(owner, name, shared=False):
    return Char.objects.create(
        name=name, char_name=name, char_class='Iop', char_build='', level=200,
        minimum_stats=b'', minimum_crits=b'', stats_weight=pickle.dumps({'vit': 1}),
        options=b'', inclusions=b'', exclusions=b'', owner=owner, game_version='dofus3',
        link_shared=shared, deleted=False, minimal_solution=pickle.dumps({}))


class ScriptEscaping(TestCase):

    def test_the_helper_cannot_close_a_script_and_reads_back_the_same(self):
        written = json_for_script({'name': ESCAPING_NAME})
        self.assertNotIn('<', written)
        self.assertEqual(json.loads(written), {'name': ESCAPING_NAME})

    def test_an_alias_cannot_leave_the_script_of_the_account_page(self):
        user = User.objects.create_user('someone', 's@test.local', 'pw-42-solid')
        UserAlias.objects.create(user=user, alias=ESCAPING_NAME)
        self.client.force_login(user)
        page = self.client.get('/manageaccount/').content.decode()
        self.assertNotIn(ESCAPING_NAME, page)

    def test_a_full_name_cannot_leave_the_script_of_the_account_page(self):
        user = User.objects.create_user('someone', 's@test.local', 'pw-42-solid',
                                        first_name=ESCAPING_NAME[:30])
        self.client.force_login(user)
        page = self.client.get('/manageaccount/').content.decode()
        self.assertNotIn(ESCAPING_NAME[:30], page)

    def test_a_build_name_cannot_leave_the_script_of_the_setup_page(self):
        user = User.objects.create_user('someone', 's@test.local', 'pw-42-solid')
        build = a_build(user, ESCAPING_NAME[:50])
        self.client.force_login(user)
        page = self.client.get('/project/%d/' % build.pk).content.decode()
        self.assertIn('var initialState', page)
        self.assertNotIn(ESCAPING_NAME[:30], page)


class TheAliasOnTheAccountPage(TestCase):

    def setUp(self):
        self.user = User.objects.create_user('someone', 's@test.local', 'pw-42-solid')
        self.client.force_login(self.user)

    def save(self, alias):
        response = self.client.post('/saveaccount/', {'alias': alias})
        self.assertEqual(response.status_code, 200)
        return response.json()

    def stored(self):
        return UserAlias.objects.get(user=self.user).alias

    def test_a_slash_is_removed(self):
        self.assertEqual(self.save('a/b')['alias'], 'ab')

    def test_a_line_break_is_removed(self):
        self.save('a\nb\tc')
        self.assertEqual(self.stored(), 'abc')

    def test_only_unsafe_characters_means_the_default_name(self):
        self.assertEqual(self.save('///')['alias'], 'someone')

    def test_blank_means_the_default_name(self):
        self.save('nick')
        self.assertEqual(self.save('   ')['alias'], 'someone')

    def test_the_alias_of_someone_else_is_refused_and_the_page_is_told(self):
        other = User.objects.create_user('other', 'o@test.local', 'pw-42-solid')
        UserAlias.objects.create(user=other, alias='Taken')
        self.save('nick')
        answer = self.save('TAKEN')
        self.assertEqual(answer['alias'], 'nick')
        self.assertTrue(answer['alias_notice'])
        self.assertEqual(self.stored(), 'nick')

    def test_the_username_of_someone_else_is_refused(self):
        User.objects.create_user('TheirName', 'o@test.local', 'pw-42-solid')
        self.assertTrue(self.save('theirname')['alias_notice'])

    def test_someone_elses_handle_is_refused(self):
        self.assertTrue(self.save('Player999999')['alias_notice'])

    def test_keeping_a_name_someone_else_also_holds_is_allowed(self):
        other = User.objects.create_user('other', 'o@test.local', 'pw-42-solid')
        UserAlias.objects.create(user=other, alias='Twin')
        UserAlias.objects.filter(user=self.user).update(alias='Twin')
        answer = self.save('Twin')
        self.assertEqual(answer['alias_notice'], '')
        self.assertEqual(self.stored(), 'Twin')

    def test_a_free_alias_has_no_notice(self):
        answer = self.save('FreeName')
        self.assertEqual(answer['alias'], 'FreeName')
        self.assertEqual(answer['alias_notice'], '')

    def test_the_page_has_the_place_for_the_notice(self):
        self.assertContains(self.client.get('/manageaccount/'), 'id="alias-notice"')


class TheNameChecks(TestCase):

    def test_the_cleaned_name_never_exceeds_the_column(self):
        self.assertEqual(clean_public_name('a' * 60, 50), 'a' * 50)
        self.assertEqual(clean_public_name('a' * 49 + ' b', 50), 'a' * 49)

    def test_ones_own_username_is_never_taken(self):
        user = User.objects.create_user('Player12', 's@test.local', 'pw-42-solid')
        self.assertFalse(public_name_is_taken('Player12', user))

    def test_a_handle_is_taken_for_someone_signing_up(self):
        self.assertTrue(public_name_is_taken('player12'))


class SigningUp(TestCase):

    def setUp(self):
        patch = mock.patch('chardata.login_view.recaptcha_ok', return_value=True)
        patch.start()
        self.addCleanup(patch.stop)

    def register(self, username):
        return self.client.post('/register/', {'username': username, 'password': 'pw-42-solid',
                                               'email': 'new@test.local'})

    def test_a_slash_in_the_username_is_refused(self):
        self.assertEqual(self.register('a/b').status_code, 403)
        self.assertFalse(User.objects.filter(email='new@test.local').exists())

    def test_a_line_break_in_the_username_is_refused(self):
        self.assertEqual(self.register('a\nb').status_code, 403)

    def test_the_alias_of_someone_else_is_refused(self):
        other = User.objects.create_user('other', 'o@test.local', 'pw-42-solid')
        UserAlias.objects.create(user=other, alias='Taken')
        self.assertEqual(self.register('taken').status_code, 403)
        self.assertEqual(self.client.post('/check_username/', {'username': 'TAKEN'}).content,
                         b'username-error')

    def test_a_handle_is_refused(self):
        self.assertEqual(self.register('Player5').status_code, 403)
        self.assertEqual(self.client.post('/check_username/', {'username': 'player5'}).content,
                         b'username-error')

    def test_a_free_username_still_registers(self):
        self.assertEqual(self.register('freename').status_code, 302)
        self.assertEqual(self.client.post('/check_username/', {'username': 'other-free'}).content,
                         b'ok')


class ABuildName(TestCase):

    def test_control_characters_become_spaces_when_saved(self):
        user = User.objects.create_user('someone', 's@test.local', 'pw-42-solid')
        build = a_build(user, 'one\ntwo\x7f')
        build.refresh_from_db()
        self.assertEqual(build.name, 'one two ')
        self.assertEqual(build.char_name, 'one two ')


class AnUnroutableStoredName(TestCase):

    def render(self, name):
        template = Template('{% load version_url %}{% profile_url name as url %}[{{ url }}]')
        return template.render(Context({'name': name}))

    def test_a_routable_name_gets_its_link(self):
        self.assertEqual(self.render('someone'), '[/user/someone/]')

    def test_a_name_with_a_slash_gets_no_link_instead_of_an_error(self):
        self.assertEqual(self.render('a/b'), '[]')

    def test_the_gallery_survives_a_stored_slash(self):
        owner = User.objects.create_user('owner', 'o@test.local', 'pw-42-solid')
        UserAlias.objects.create(user=owner, alias='a/b')
        a_build(owner, 'shown', shared=True)
        page = self.client.get('/sharedbuilds/')
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'a/b')
