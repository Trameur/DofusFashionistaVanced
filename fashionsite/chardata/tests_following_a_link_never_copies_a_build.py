# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A GET or a HEAD on the copy link only shows the build; a POST with its token copies it, and a guest's copies are capped."""
import datetime
import pickle
from html.parser import HTMLParser

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.utils import timezone, translation
from django.utils.translation import gettext

from chardata.encoded_char_id import encode_char_id
from chardata.models import Char, CharBaseStats, RateCounter
from chardata.projects_view import (GUEST_COPIES_ALL, GUEST_COPIES_PER_IP,
                                    GUEST_COPY_WINDOW)
from chardata.rate_limit import hits
from fashionistapulp.modelresult import ModelResultMinimal

COPY_LIMIT_MESSAGE = ('You have copied too many builds for now. '
                      'Please try again later or log in.')
LANGUAGES = ('de', 'en', 'es', 'fr', 'pt')


def _the_prefix(version):
    return '' if version == 'dofus3' else '/' + version


def _a_build(owner, version='dofus3', shared=True, deleted=False,
             name='Following'):
    input_ = {'options': {'ap_exo': False, 'mp_exo': False},
              'origin': 'generated', 'char_level': 200,
              'base_stats_by_attr': {}, 'locked_equips': {}}
    char = Char.objects.create(
        name=name, char_name=name, char_class='Iop', char_build='build',
        level=200, minimum_stats=b'', minimum_crits=b'', stats_weight=b'',
        options=b'', inclusions=b'', exclusions=b'',
        minimal_solution=pickle.dumps(ModelResultMinimal({}, input_, {})),
        owner=owner, link_shared=shared, deleted=deleted, game_version=version)
    CharBaseStats.objects.create(char=char, stat='Vitality',
                                 total_value=120, scrolled_value=100)
    CharBaseStats.objects.create(char=char, stat='Wisdom',
                                 total_value=30, scrolled_value=0)
    return char


class _Page(HTMLParser):
    """The forms, buttons and links of a page, each form knowing whether it sits inside another."""

    def __init__(self, html):
        super().__init__()
        self.forms = []
        self.buttons = []
        self.links = []
        self._open_forms = []
        self._open_button = None
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'form':
            form = {'attrs': attrs, 'nested': bool(self._open_forms),
                    'inputs': {}, 'buttons': []}
            self.forms.append(form)
            self._open_forms.append(form)
        elif tag == 'input' and self._open_forms:
            self._open_forms[-1]['inputs'][attrs.get('name')] = attrs.get('value')
        elif tag == 'button':
            self._open_button = {'attrs': attrs, 'text': '',
                                 'form': (self._open_forms[-1]
                                          if self._open_forms else None)}
            self.buttons.append(self._open_button)
            if self._open_forms:
                self._open_forms[-1]['buttons'].append(self._open_button)
        elif tag == 'a':
            self.links.append(attrs)

    def handle_endtag(self, tag):
        if tag == 'form' and self._open_forms:
            self._open_forms.pop()
        elif tag == 'button':
            self._open_button = None

    def handle_data(self, data):
        if self._open_button is not None:
            self._open_button['text'] += data

    def copy_forms(self):
        return [form for form in self.forms
                if 'duplicatesomeonesproject' in form['attrs'].get('action', '')]


class _Copies(TestCase):

    def setUp(self):
        self.owner = User.objects.create_user('copyowner', 'co@x.test', 'pw-42-solid')
        self.char = _a_build(self.owner)
        self.encoded = encode_char_id(self.char.id)

    def _copy_path(self, char=None, version='dofus3'):
        char = char or self.char
        return '%s/duplicatesomeonesproject/%s/' % (_the_prefix(version),
                                                    encode_char_id(char.id))

    def _written(self):
        return (Char.objects.count(), CharBaseStats.objects.count(),
                RateCounter.objects.count())

    def _shared_page(self, client):
        return client.get('/s/following/%s/' % self.encoded,
                          HTTP_ACCEPT_LANGUAGE='en')

    def _seed(self, key, count, age=0):
        RateCounter.objects.update_or_create(
            key=key, defaults={'count': count,
                               'window_start': timezone.now()
                               - datetime.timedelta(seconds=age)})


class AGetOrAHeadOnTheCopyLinkWritesNothingTests(_Copies):

    def test_a_guest_get_redirects_to_the_shared_page_and_writes_nothing(self):
        before = self._written()
        response = self.client.get(self._copy_path())
        self.assertEqual(302, response.status_code)
        self.assertRegex(response['Location'], r'^/s/[^/]+/%s/$' % self.encoded)
        self.assertEqual(before, self._written())
        self.assertEqual(200, self.client.get(response['Location']).status_code)

    def test_a_head_redirects_to_the_shared_page_and_writes_nothing(self):
        before = self._written()
        response = self.client.head(self._copy_path())
        self.assertEqual(302, response.status_code)
        self.assertRegex(response['Location'], r'^/s/[^/]+/%s/$' % self.encoded)
        self.assertEqual(before, self._written())

    def test_a_signed_in_get_writes_nothing_either(self):
        self.client.force_login(User.objects.create_user('reader', 'r@x.test', 'pw-42-solid'))
        before = self._written()
        response = self.client.get(self._copy_path())
        self.assertEqual(302, response.status_code)
        self.assertRegex(response['Location'], r'^/s/[^/]+/%s/$' % self.encoded)
        self.assertEqual(before, self._written())

    def test_a_get_on_a_prefixed_version_stays_on_its_prefix(self):
        build = _a_build(self.owner, 'dofus2', name='Older')
        before = self._written()
        for method in (self.client.get, self.client.head):
            response = method(self._copy_path(build, 'dofus2'))
            self.assertEqual(302, response.status_code)
            self.assertRegex(response['Location'],
                             r'^/dofus2/s/[^/]+/%s/$' % encode_char_id(build.id))
        self.assertEqual(before, self._written())

    def test_a_get_counts_nothing_against_the_guest_cap(self):
        for _ in range(GUEST_COPIES_PER_IP + 5):
            self.client.get(self._copy_path(), REMOTE_ADDR='203.0.113.40')
            self.client.head(self._copy_path(), REMOTE_ADDR='203.0.113.40')
        self.assertEqual(0, RateCounter.objects.count())
        response = self.client.post(self._copy_path(), REMOTE_ADDR='203.0.113.40')
        self.assertEqual('/loadprojects/', response['Location'])

    def test_a_get_on_an_unshared_deleted_or_made_up_build_is_refused(self):
        unshared = _a_build(self.owner, shared=False, name='Private')
        deleted = _a_build(self.owner, deleted=True, name='Gone')
        before = self._written()
        for path in (self._copy_path(unshared), self._copy_path(deleted),
                     '/duplicatesomeonesproject/not-a-real-id/'):
            for method in (self.client.get, self.client.head):
                self.assertEqual(403, method(path).status_code, path)
        self.assertEqual(before, self._written())


class OnlyAPostWithItsTokenCopiesTests(_Copies):

    def setUp(self):
        super().setUp()
        self.guest = Client(enforce_csrf_checks=True)

    def _the_copy_form_of_the_shared_page(self, client):
        page = _Page(self._shared_page(client).content.decode('utf-8'))
        forms = page.copy_forms()
        self.assertTrue(forms, 'the shared page has no copy form')
        return forms[0]

    def test_a_post_with_the_token_of_the_shared_page_makes_exactly_one_copy(self):
        form = self._the_copy_form_of_the_shared_page(self.guest)
        before = self._written()
        copies_before = Char.objects.count()
        response = self.guest.post(
            form['attrs']['action'],
            {'csrfmiddlewaretoken': form['inputs']['csrfmiddlewaretoken']})
        self.assertEqual(302, response.status_code)
        self.assertEqual('/loadprojects/', response['Location'])
        self.assertEqual(copies_before + 1, Char.objects.count())
        copy = Char.objects.order_by('-id').first()
        self.assertNotEqual(self.char.id, copy.id)
        self.assertIsNone(copy.owner)
        self.assertEqual('Following copy', copy.name)
        self.assertFalse(copy.link_shared)
        self.assertEqual(
            sorted(CharBaseStats.objects.filter(char=self.char).values_list(
                'stat', 'total_value', 'scrolled_value')),
            sorted(CharBaseStats.objects.filter(char=copy).values_list(
                'stat', 'total_value', 'scrolled_value')))
        self.assertEqual(before[1] + 2, CharBaseStats.objects.count())
        self.char.refresh_from_db()
        self.assertTrue(self.char.link_shared)
        self.assertEqual(self.owner, self.char.owner)

    def test_a_post_on_a_prefixed_version_copies_into_that_version(self):
        build = _a_build(self.owner, 'dofus2', name='Older')
        before = Char.objects.count()
        response = self.client.post(self._copy_path(build, 'dofus2'))
        self.assertEqual('/dofus2/loadprojects/', response['Location'])
        self.assertEqual(before + 1, Char.objects.count())
        self.assertEqual('dofus2', Char.objects.order_by('-id').first().game_version)

    def test_a_post_without_the_token_is_refused_and_writes_nothing(self):
        self._shared_page(self.guest)
        before = self._written()
        for data in ({}, {'csrfmiddlewaretoken': 'not-the-token'}):
            response = self.guest.post(self._copy_path(), data)
            self.assertEqual(403, response.status_code)
        self.assertEqual(before, self._written())

    def test_a_signed_in_post_without_the_token_is_refused_too(self):
        self.guest.force_login(User.objects.create_user('reader', 'r@x.test', 'pw-42-solid'))
        before = self._written()
        self.assertEqual(403, self.guest.post(self._copy_path()).status_code)
        self.assertEqual(before, self._written())

    def test_a_signed_in_post_with_the_token_copies_into_the_readers_workspace(self):
        reader = User.objects.create_user('reader', 'r@x.test', 'pw-42-solid')
        self.guest.force_login(reader)
        form = self._the_copy_form_of_the_shared_page(self.guest)
        response = self.guest.post(
            form['attrs']['action'],
            {'csrfmiddlewaretoken': form['inputs']['csrfmiddlewaretoken']})
        self.assertEqual('/loadprojects/', response['Location'])
        copy = Char.objects.order_by('-id').first()
        self.assertEqual(reader, copy.owner)
        self.assertEqual(2, Char.objects.count())

    def test_other_methods_are_refused(self):
        before = self._written()
        for method in (self.client.put, self.client.patch, self.client.delete,
                       self.client.options):
            self.assertEqual(405, method(self._copy_path()).status_code)
        self.assertEqual(before, self._written())

    def test_a_deleted_or_unshared_original_is_refused_on_a_post(self):
        unshared = _a_build(self.owner, shared=False, name='Private')
        deleted = _a_build(self.owner, deleted=True, name='Gone')
        before = self._written()
        for path in (self._copy_path(unshared), self._copy_path(deleted),
                     '/duplicatesomeonesproject/not-a-real-id/'):
            self.assertEqual(403, self.client.post(path).status_code, path)
        self.assertEqual(before, self._written())


class AGuestCannotCopyWithoutEndTests(_Copies):
    ADDRESS = '203.0.113.9'

    def _post(self, address=None, client=None):
        return (client or self.client).post(self._copy_path(),
                                            REMOTE_ADDR=address or self.ADDRESS)

    def test_the_eleventh_copy_from_one_address_within_the_hour_writes_nothing(self):
        for _ in range(GUEST_COPIES_PER_IP):
            self.assertEqual('/loadprojects/', self._post()['Location'])
        before = self._written()
        response = self._post()
        self.assertEqual(302, response.status_code)
        self.assertEqual('/loadprojectserror/copy_limit/', response['Location'])
        self.assertEqual(before, self._written())

    def test_another_address_is_not_held_by_the_first_ones_cap(self):
        for _ in range(GUEST_COPIES_PER_IP):
            self._post()
        self.assertEqual('/loadprojects/',
                         self._post('203.0.113.10', Client())['Location'])

    def test_a_forged_forwarded_for_header_does_not_open_a_fresh_bucket(self):
        for number in range(GUEST_COPIES_PER_IP):
            response = self.client.post(self._copy_path(), REMOTE_ADDR=self.ADDRESS,
                                        HTTP_X_FORWARDED_FOR='198.51.100.%d' % number)
            self.assertEqual('/loadprojects/', response['Location'])
        before = self._written()
        response = self.client.post(self._copy_path(), REMOTE_ADDR=self.ADDRESS,
                                    HTTP_X_FORWARDED_FOR='198.51.100.200')
        self.assertEqual('/loadprojectserror/copy_limit/', response['Location'])
        self.assertEqual(before, self._written())

    def test_the_address_cloudflare_vouches_for_is_the_one_counted(self):
        proxy = '172.18.0.3'
        for number in range(GUEST_COPIES_PER_IP):
            response = self.client.post(self._copy_path(), REMOTE_ADDR=proxy,
                                        HTTP_CF_CONNECTING_IP=self.ADDRESS,
                                        HTTP_X_FORWARDED_FOR='198.51.100.%d' % number)
            self.assertEqual('/loadprojects/', response['Location'])
        response = self.client.post(self._copy_path(), REMOTE_ADDR=proxy,
                                    HTTP_CF_CONNECTING_IP=self.ADDRESS,
                                    HTTP_X_FORWARDED_FOR='198.51.100.200')
        self.assertEqual('/loadprojectserror/copy_limit/', response['Location'])
        other = self.client.post(self._copy_path(), REMOTE_ADDR=proxy,
                                 HTTP_CF_CONNECTING_IP='203.0.113.77')
        self.assertEqual('/loadprojects/', other['Location'])

    def test_the_cap_is_a_ceiling_on_copies_made_not_on_tries(self):
        self._seed('guest-copy-ip:%s' % self.ADDRESS, GUEST_COPIES_PER_IP)
        for _ in range(3):
            self.assertEqual('/loadprojectserror/copy_limit/', self._post()['Location'])
        self.assertEqual(GUEST_COPIES_PER_IP,
                         hits('guest-copy-ip:%s' % self.ADDRESS, GUEST_COPY_WINDOW))
        self.assertEqual(0, hits('guest-copy-all', GUEST_COPY_WINDOW))

    def test_a_copy_counts_for_its_address_and_for_everyone(self):
        self._post()
        self.assertEqual(1, hits('guest-copy-ip:%s' % self.ADDRESS, GUEST_COPY_WINDOW))
        self.assertEqual(1, hits('guest-copy-all', GUEST_COPY_WINDOW))

    def test_the_cap_across_all_addresses_stops_a_fresh_address(self):
        self._seed('guest-copy-all', GUEST_COPIES_ALL - 1)
        self.assertEqual('/loadprojects/', self._post('203.0.113.20', Client())['Location'])
        before = self._written()
        response = self._post('203.0.113.21', Client())
        self.assertEqual('/loadprojectserror/copy_limit/', response['Location'])
        self.assertEqual(before, self._written())

    def test_a_window_that_has_run_out_starts_again(self):
        self._seed('guest-copy-ip:%s' % self.ADDRESS, GUEST_COPIES_PER_IP,
                   age=GUEST_COPY_WINDOW + 5)
        self.assertEqual('/loadprojects/', self._post()['Location'])
        self.assertEqual(1, hits('guest-copy-ip:%s' % self.ADDRESS, GUEST_COPY_WINDOW))

    def test_a_signed_in_user_is_not_stopped_by_the_guest_caps(self):
        self._seed('guest-copy-ip:%s' % self.ADDRESS, GUEST_COPIES_PER_IP)
        self._seed('guest-copy-all', GUEST_COPIES_ALL)
        reader = User.objects.create_user('reader', 'r@x.test', 'pw-42-solid')
        self.client.force_login(reader)
        response = self._post()
        self.assertEqual('/loadprojects/', response['Location'])
        self.assertEqual(reader, Char.objects.order_by('-id').first().owner)
        self.assertEqual(GUEST_COPIES_PER_IP,
                         hits('guest-copy-ip:%s' % self.ADDRESS, GUEST_COPY_WINDOW))
        self.assertEqual(GUEST_COPIES_ALL, hits('guest-copy-all', GUEST_COPY_WINDOW))

    def test_the_limit_page_speaks_every_language(self):
        english = None
        for language in LANGUAGES:
            with translation.override(language):
                message = gettext(COPY_LIMIT_MESSAGE)
            prefix = '' if language == 'en' else '/' + language
            page = self.client.get('%s/loadprojectserror/copy_limit/' % prefix,
                                   HTTP_ACCEPT_LANGUAGE=language)
            self.assertEqual(200, page.status_code, language)
            self.assertContains(page, message, msg_prefix=language)
            if language == 'en':
                english = message
                self.assertEqual(COPY_LIMIT_MESSAGE, message)
        for language in LANGUAGES:
            if language == 'en':
                continue
            with translation.override(language):
                self.assertNotEqual(english, gettext(COPY_LIMIT_MESSAGE), language)

    def test_the_limit_message_shows_only_on_its_own_code(self):
        for path in ('/loadprojects/', '/loadprojectserror/too_many/'):
            page = self.client.get(path, HTTP_ACCEPT_LANGUAGE='en')
            self.assertNotContains(page, COPY_LIMIT_MESSAGE)


class TheSharedPageCopiesWithAPostTests(_Copies):

    def _pages(self):
        reader = User.objects.create_user('reader', 'r@x.test', 'pw-42-solid')
        signed_in = Client()
        signed_in.force_login(reader)
        for label, client in (('guest', Client()), ('signed in', signed_in)):
            yield label, _Page(self._shared_page(client).content.decode('utf-8'))

    def test_the_copy_control_is_a_post_form_carrying_a_token(self):
        for label, page in self._pages():
            forms = page.copy_forms()
            self.assertTrue(forms, label)
            for form in forms:
                self.assertEqual('post', form['attrs'].get('method', '').lower(), label)
                self.assertTrue(form['inputs'].get('csrfmiddlewaretoken'), label)
                self.assertFalse(form['nested'], label)
                self.assertTrue(form['attrs']['action'].endswith(
                    '/duplicatesomeonesproject/%s/' % self.encoded), label)

    def test_no_link_to_the_copy_route_is_left(self):
        for label, page in self._pages():
            self.assertEqual(
                [], [link for link in page.links
                     if 'duplicatesomeonesproject' in (link.get('href') or '')],
                label)

    def test_the_header_button_sits_inside_its_form(self):
        for label, page in self._pages():
            inside = [button for form in page.copy_forms()
                      for button in form['buttons']]
            self.assertTrue(inside, label)
            for button in inside:
                self.assertEqual('submit', button['attrs'].get('type'), label)
                self.assertEqual('Copy this build', button['text'].strip(), label)

    def test_the_sentence_button_submits_the_hidden_form_by_its_id(self):
        for label, page in self._pages():
            outside = [form for form in page.copy_forms() if not form['buttons']]
            self.assertEqual(1, len(outside), label)
            form_id = outside[0]['attrs'].get('id')
            self.assertTrue(form_id, label)
            pointing = [button for button in page.buttons
                        if button['attrs'].get('form') == form_id]
            self.assertEqual(1, len(pointing), label)
            self.assertEqual('submit', pointing[0]['attrs'].get('type'), label)
            self.assertIsNone(pointing[0]['form'], 'the button sits inside a form')

    def test_each_form_of_the_page_copies_once_when_posted(self):
        forms = _Page(self._shared_page(Client()).content.decode('utf-8')).copy_forms()
        for index in range(len(forms)):
            guest = Client(enforce_csrf_checks=True)
            page = _Page(self._shared_page(guest).content.decode('utf-8'))
            form = page.copy_forms()[index]
            before = Char.objects.count()
            response = guest.post(
                form['attrs']['action'],
                {'csrfmiddlewaretoken': form['inputs']['csrfmiddlewaretoken']})
            self.assertEqual('/loadprojects/', response['Location'], index)
            self.assertEqual(before + 1, Char.objects.count(), index)

class AGuestCopyToAnotherVersionIsCappedTooTests(_Copies):
    ADDRESS = '203.0.113.40'

    def _post(self, client=None):
        return (client or Client()).post(
            '/copysharedtoversion/%s/' % self.encoded, {'version': 'beta'},
            REMOTE_ADDR=self.ADDRESS)

    def test_a_guest_at_the_cap_lands_on_the_limit_page_of_the_target_version(self):
        self._seed('guest-copy-ip:%s' % self.ADDRESS, GUEST_COPIES_PER_IP)
        before = self._written()
        response = self._post()
        self.assertEqual(302, response.status_code)
        self.assertEqual('/beta/loadprojectserror/copy_limit/', response['Location'])
        self.assertEqual(before, self._written())

    def test_a_guest_copy_to_another_version_counts_against_the_caps(self):
        response = self._post()
        self.assertTrue(response['Location'].startswith('/beta/loadproject/'),
                        response['Location'])
        self.assertEqual(1, Char.objects.filter(game_version='beta').count())
        self.assertEqual(1, hits('guest-copy-ip:%s' % self.ADDRESS, GUEST_COPY_WINDOW))
        self.assertEqual(1, hits('guest-copy-all', GUEST_COPY_WINDOW))

    def test_a_signed_in_user_copying_to_another_version_is_not_capped(self):
        self._seed('guest-copy-ip:%s' % self.ADDRESS, GUEST_COPIES_PER_IP)
        self._seed('guest-copy-all', GUEST_COPIES_ALL)
        reader = User.objects.create_user('versionreader', 'vr@x.test', 'pw-42-solid')
        client = Client()
        client.force_login(reader)
        response = self._post(client)
        self.assertTrue(response['Location'].startswith('/beta/loadproject/'),
                        response['Location'])
        self.assertEqual(1, Char.objects.filter(game_version='beta',
                                                owner=reader).count())
