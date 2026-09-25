# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A fashionista-build sent by link or form lands on the import page as a preview; only the player's confirm creates the build."""

import base64
import html
import html.parser
import json
import re

from django.core.cache import cache
from django.test import Client, TestCase

from chardata import fashionista_build
from chardata.char_blobs import read_char_blob
from chardata.management.commands import check_actions
from chardata.models import Char, CharBaseStats, ImportSourceHit
from fashionistapulp.game_versions import version_keys
from fashionistapulp.structure import get_structure

BROWSER = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
           '(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36')

UNKNOWN_ID = 987654321


def _prefix(game):
    return '' if game == 'dofus3' else '/' + game


def _data(payload):
    return fashionista_build.encode_link_data(payload)


def _names(payload, language='en'):
    structure = get_structure(payload['game'])
    names = []
    for entry in payload['items']:
        ankama = entry['id'] if isinstance(entry, dict) else entry
        item = structure.get_item_by_ankama_id(ankama)
        names.append(structure.get_item_name_in_language(item, language))
    return names


def _only_in_retro():
    """An Ankama id Dofus Retro knows and Dofus 3 does not."""
    retro, dofus3 = get_structure('retro'), get_structure('dofus3')
    return next(item.ankama_id for item in retro.get_items_list()
                if item.ankama_id and item.id < 10_000_000
                and dofus3.get_item_by_ankama_id(item.ankama_id) is None
                and not any(get_structure(other).get_item_by_ankama_id(item.ankama_id)
                            for other in ('beta', 'dofus2', 'touch')))


class _Tags(html.parser.HTMLParser):

    def __init__(self):
        super().__init__()
        self.tags = []

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


def _tags(page, tag):
    parser = _Tags()
    parser.feed(page.content.decode('utf-8'))
    return [attrs for name, attrs in parser.tags if name == tag]


def _hidden(page, name):
    return [attrs.get('value') for attrs in _tags(page, 'input')
            if attrs.get('type') == 'hidden' and attrs.get('name') == name]


def _contains_name(page, name):
    body = page.content.decode('utf-8')
    return name in body or html.escape(name) in body


def _hop_form(page):
    """(action, hidden fields) of the page that posts a build again from our origin, or None."""
    forms = [attrs for attrs in _tags(page, 'form') if attrs.get('id') == 'sent-build']
    if not forms:
        return None
    fields = {attrs.get('name'): attrs.get('value') or '' for attrs in _tags(page, 'input')
              if attrs.get('type') == 'hidden'}
    return forms[0].get('action'), fields


def _follow_hop(client, page, **extra):
    """The page a browser ends on once that page has posted the build again."""
    hop = _hop_form(page) if page.status_code == 200 else None
    if hop is None:
        return page
    action, fields = hop
    return client.post(action, fields, **dict(extra, HTTP_SEC_FETCH_SITE='same-origin'))


class _SentBuild(TestCase):

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    def _link(self, payload, prefix=None, **extra):
        prefix = _prefix(payload['game']) if prefix is None else prefix
        return self.client.get('%s/import/build/' % prefix,
                               {'data': _data(payload)}, **extra)

    def _post(self, payload, prefix=None, **extra):
        prefix = _prefix(payload['game']) if prefix is None else prefix
        text = payload if isinstance(payload, str) else json.dumps(payload)
        page = self.client.post('%s/import/build/' % prefix,
                                dict(extra.pop('fields', {}), data=text), **extra)
        return _follow_hop(self.client, page, **extra)

    def _confirm(self, preview, char_class='Iop', level='200', client=None):
        form = next(attrs for attrs in _tags(preview, 'form')
                    if attrs.get('action', '').endswith('/import/text/'))
        fields = {'text': _hidden(preview, 'text')[-1], 'confirm': '1',
                  'char_class': char_class, 'level': level}
        token = _hidden(preview, 'count_token')
        if token:
            fields['count_token'] = token[0]
        return (client or self.client).post(form['action'], fields, HTTP_USER_AGENT=BROWSER)


class TheLinkAndTheFormLandOnAPreviewInEveryVersionTests(_SentBuild):

    def _assert_preview(self, page, payload):
        self.assertEqual(200, page.status_code)
        self.assertContains(page, 'id="import-sent-read"')
        self.assertContains(page, 'Build received: Example build')
        for name in _names(payload):
            self.assertTrue(_contains_name(page, name), name)
        forms = [attrs.get('action') for attrs in _tags(page, 'form')
                 if 'import-form' in (attrs.get('class') or '')]
        self.assertEqual(['%s/import/text/' % _prefix(payload['game'])] * 2, forms)
        self.assertEqual(payload, json.loads(_hidden(page, 'text')[-1]))
        selected = [attrs.get('value') for attrs in _tags(page, 'option')
                    if 'selected' in attrs]
        self.assertIn(payload['class'] if isinstance(payload['class'], str) else 'Cra',
                      selected)

    def test_a_link_opens_a_prefilled_preview_for_each_version(self):
        for game in version_keys():
            with self.subTest(game=game):
                payload = fashionista_build.example_payload(game)
                self._assert_preview(self._link(payload, HTTP_ACCEPT_LANGUAGE='en'),
                                     payload)
        self.assertEqual(0, Char.objects.count())

    def test_a_form_post_opens_a_prefilled_preview_for_each_version(self):
        for game in version_keys():
            with self.subTest(game=game):
                payload = fashionista_build.example_payload(game)
                self._assert_preview(self._post(payload, HTTP_ACCEPT_LANGUAGE='en'),
                                     payload)
        self.assertEqual(0, Char.objects.count())

    def test_a_landing_page_is_kept_out_of_search_engines_and_the_import_page_is_not(self):
        payload = fashionista_build.example_payload('dofus3')
        robots = [attrs.get('content') for attrs in _tags(self._link(payload), 'meta')
                  if attrs.get('name') == 'robots']
        self.assertEqual(['noindex, follow'], robots)
        refused = self.client.get('/import/build/', {'data': '!!'})
        self.assertIn('noindex, follow', [attrs.get('content') for attrs in _tags(refused, 'meta')
                                          if attrs.get('name') == 'robots'])
        plain = [attrs.get('content') for attrs in _tags(self.client.get('/import/text/'), 'meta')
                 if attrs.get('name') == 'robots']
        self.assertEqual(['index, follow'], plain)

    def test_the_textarea_stays_empty_and_the_json_rides_in_the_confirm_form(self):
        payload = fashionista_build.example_payload('dofus3')
        page = self._link(payload, HTTP_ACCEPT_LANGUAGE='en')
        area = re.search(r'<textarea[^>]*name="?text"?[^>]*>(.*?)</textarea>',
                         page.content.decode('utf-8'), re.S)
        self.assertEqual('', area.group(1).strip())
        self.assertEqual(payload, json.loads(_hidden(page, 'text')[-1]))

    def test_a_build_for_another_game_is_sent_on_to_that_game(self):
        payload = fashionista_build.example_payload('retro')
        moved = self._link(payload, prefix='')
        self.assertEqual(302, moved.status_code)
        self.assertTrue(moved['Location'].startswith('/retro/import/build/?data='),
                        moved['Location'])
        moved = self._link(payload, prefix='/fr')
        self.assertTrue(moved['Location'].startswith('/fr/retro/import/build/?data='),
                        moved['Location'])
        posted = self._post(payload, prefix='/touch')
        self.assertEqual(307, posted.status_code)
        self.assertEqual('/retro/import/build/', posted['Location'])
        landed = self._post(payload, prefix='/touch', follow=True,
                            HTTP_ACCEPT_LANGUAGE='en')
        self.assertContains(landed, 'Build received: Example build')

    def test_the_page_speaks_the_language_of_its_address_and_of_the_reader(self):
        payload = fashionista_build.example_payload('dofus3')
        page = self._link(payload, prefix='/fr')
        self.assertContains(page, 'lang="fr"')
        self.assertContains(page, 'Build reçu : Example build')
        for name in _names(payload, 'fr'):
            self.assertTrue(_contains_name(page, name), name)
        page = self._link(payload, HTTP_ACCEPT_LANGUAGE='es')
        self.assertContains(page, 'Build recibido: Example build')
        forms = {attrs.get('action') for attrs in _tags(page, 'form')
                 if 'import-form' in (attrs.get('class') or '')}
        self.assertEqual({'/es/import/text/'}, forms)


class NothingIsCreatedBeforeThePlayerConfirmsTests(_SentBuild):

    def test_confirm_fields_forged_into_the_sent_form_create_nothing(self):
        payload = fashionista_build.example_payload('dofus3')
        fields = {'confirm': '1', 'char_class': 'Iop', 'level': '200',
                  'text': json.dumps(payload)}
        page = self._post(payload, fields=fields, HTTP_USER_AGENT=BROWSER)
        self.assertEqual(200, page.status_code)
        page = self._post(payload, fields=dict(fields, hop='1'), HTTP_USER_AGENT=BROWSER,
                          HTTP_SEC_FETCH_SITE='same-origin')
        self.assertContains(page, 'Build received')
        self._link(payload, HTTP_USER_AGENT=BROWSER)
        self.assertEqual(0, Char.objects.count())
        self.assertEqual(0, CharBaseStats.objects.count())

    def test_the_sent_door_takes_no_csrf_token_and_the_confirm_step_still_needs_one(self):
        strict = Client(enforce_csrf_checks=True)
        payload = fashionista_build.example_payload('dofus3')
        page = _follow_hop(strict, strict.post('/import/build/', {'data': json.dumps(payload)},
                                               HTTP_ACCEPT_LANGUAGE='en'),
                           HTTP_ACCEPT_LANGUAGE='en')
        self.assertContains(page, 'Build received')
        refused = strict.post('/import/text/', {
            'text': _hidden(page, 'text')[-1], 'confirm': '1',
            'char_class': 'Iop', 'level': '200'})
        self.assertEqual(403, refused.status_code)
        self.assertEqual(0, Char.objects.count())

    def test_the_confirm_creates_exactly_the_build_that_was_sent(self):
        from chardata.lock_forbid import get_stat_overrides
        from chardata.options import get_options
        payload = fashionista_build.example_payload('dofus3')
        payload['exos'] = {'ap': False, 'mp': True, 'range': False}
        payload['scrolls']['wisdom'] = 40
        preview = self._link(payload, HTTP_ACCEPT_LANGUAGE='en')
        self.assertEqual(0, Char.objects.count())
        done = self._confirm(preview)
        self.assertEqual(302, done.status_code)
        self.assertEqual(1, Char.objects.count())
        char = Char.objects.get()
        self.assertEqual(('dofus3', 'Iop', 200, 'Example build'),
                         (char.game_version, char.char_class, char.level, char.name))
        structure = get_structure('dofus3')
        expected = sorted(structure.get_item_by_ankama_id(
            entry['id'] if isinstance(entry, dict) else entry).id
            for entry in payload['items'])
        worn = read_char_blob(char.minimal_solution, None, 'minimal_solution',
                              char).item_per_slot
        self.assertEqual(expected, sorted(i for i in worn.values() if i))
        stats = {row.stat: (row.total_value - row.scrolled_value, row.scrolled_value)
                 for row in CharBaseStats.objects.filter(char=char)}
        for field, name in fashionista_build.CHARACTERISTICS:
            self.assertEqual((payload['characteristics'][field],
                              payload['scrolls'][field]), stats[name], name)
        hat = structure.get_item_by_ankama_id(payload['items'][0]['id'])
        line = payload['items'][0]['stats'][0]
        self.assertEqual({structure.get_stat_by_key(line['key']).id: line['value']},
                         get_stat_overrides(char)[hat.id])
        options = get_options(char)
        self.assertEqual((False, True, False),
                         (options['ap_exo'], options['mp_exo'], options['range_exo']))

    def test_a_level_200_build_sent_without_exos_comes_in_with_none(self):
        from chardata.options import get_options
        payload = fashionista_build.example_payload('dofus3')
        del payload['exos']
        self.assertEqual(200, payload['level'])
        preview = self._link(payload, HTTP_ACCEPT_LANGUAGE='en')
        self.assertEqual(302, self._confirm(preview).status_code)
        options = get_options(Char.objects.get())
        self.assertEqual((False, False, False),
                         (options['ap_exo'], options['mp_exo'], options['range_exo']))

    def test_a_retro_class_sent_as_its_breed_id_comes_in_as_that_class(self):
        payload = fashionista_build.example_payload('retro')
        preview = self._link(payload, HTTP_ACCEPT_LANGUAGE='en')
        done = self._confirm(preview, char_class='Cra', level='100')
        self.assertEqual(302, done.status_code)
        char = Char.objects.get()
        self.assertEqual(('retro', 'Cra', 100), (char.game_version, char.char_class, char.level))


class UnknownAndWrongGameIdsAreNamedTests(_SentBuild):

    def test_the_preview_names_an_unknown_id_and_an_id_from_another_game(self):
        retro_only = _only_in_retro()
        payload = fashionista_build.example_payload('dofus3')
        payload['items'] += [UNKNOWN_ID, retro_only]
        page = self._link(payload, HTTP_ACCEPT_LANGUAGE='en')
        self.assertContains(page, 'id="import-link-missing"')
        self.assertContains(page, '#%d' % UNKNOWN_ID)
        self.assertContains(page, 'id="import-sent-wrong-game"')
        self.assertContains(page, '#%d (Retro)' % retro_only)

    def test_a_build_of_only_another_games_ids_is_refused_with_the_reason(self):
        payload = fashionista_build.example_payload('dofus3')
        payload['items'] = [_only_in_retro()]
        page = self._link(payload, HTTP_ACCEPT_LANGUAGE='en')
        self.assertContains(page, 'These items belong to another version of the game. '
                                  'Check the game field.')
        self.assertNotContains(page, 'id="import-sent-read"')

    def test_a_piece_with_no_free_slot_is_named_and_left_out(self):
        payload = fashionista_build.example_payload('dofus3')
        rings = [entry for entry in payload['items'] if not isinstance(entry, dict)][2:4]
        structure = get_structure('dofus3')
        third = next(item.ankama_id for item in structure.get_items_list()
                     if structure.get_type_name_by_id(item.type) == 'Ring'
                     and item.ankama_id not in rings and not item.removed
                     and structure.get_item_by_ankama_id(item.ankama_id) is item)
        payload['items'].append(third)
        page = self._link(payload, HTTP_ACCEPT_LANGUAGE='en')
        self.assertContains(page, 'id="import-sent-left-out"')
        name = structure.get_item_name_in_language(
            structure.get_item_by_ankama_id(third), 'en')
        self.assertTrue(_contains_name(page, name))


class ABadPayloadGetsATranslatedMessageTests(_SentBuild):

    CASES = (
        ('too_large', 'This build is too large to be read.',
         'Ce build est trop volumineux pour être lu.'),
        ('bad_encoding', 'The data in the link is not valid base64url.',
         'Les données du lien ne sont pas du base64url valide.'),
        ('not_json', 'This build is not valid JSON.',
         'Ce build n’est pas du JSON valide.'),
        ('not_an_object', 'This build must be a JSON object.',
         'Ce build doit être un objet JSON.'),
        ('wrong_format', 'The format field must say fashionista-build.',
         'Le champ format doit valoir fashionista-build.'),
        ('unsupported_version', 'Only version 1 of the format can be read.',
         'Seule la version 1 du format peut être lue.'),
        ('unknown_game', 'The game field must be dofus3, beta, dofus2, touch or retro.',
         'Le champ game doit valoir dofus3, beta, dofus2, touch ou retro.'),
    )

    def _links(self):
        good = fashionista_build.example_payload('dofus3')
        return {
            'too_large': 'A' * (fashionista_build.MAX_LINK_DATA + 1),
            'bad_encoding': '!!not*base64!!',
            'not_json': base64.urlsafe_b64encode(b'{nope').decode().rstrip('='),
            'not_an_object': _data([1, 2]),
            'wrong_format': _data(dict(good, format='dofusbook')),
            'unsupported_version': _data(dict(good, version=2)),
            'unknown_game': _data(dict(good, game='wakfu')),
        }

    def test_each_bad_link_says_why_in_english_and_in_french(self):
        for code, sentence, french_sentence in self.CASES:
            data = self._links()[code]
            with self.subTest(code=code):
                page = self.client.get('/import/build/', {'data': data},
                                       HTTP_ACCEPT_LANGUAGE='en')
                self.assertEqual(200, page.status_code)
                self.assertContains(page, html.escape(sentence))
                french = self.client.get('/fr/import/build/', {'data': data})
                self.assertEqual(200, french.status_code)
                self.assertContains(french, html.escape(french_sentence))
        self.assertEqual(0, Char.objects.count())

    def test_an_oversized_form_is_refused_before_it_is_read(self):
        page = self._post('x' * (fashionista_build.MAX_JSON + 1), prefix='',
                          HTTP_ACCEPT_LANGUAGE='en')
        self.assertContains(page, 'This build is too large to be read.')
        huge = self.client.generic('POST', '/import/build/', b'data=x',
                                   content_type='application/x-www-form-urlencoded',
                                   CONTENT_LENGTH=str(10 ** 9),
                                   HTTP_ACCEPT_LANGUAGE='en')
        self.assertEqual({'hop': '1', 'data': '', 'refused': 'too_large'},
                         _hop_form(huge)[1])
        self.assertContains(_follow_hop(self.client, huge, HTTP_ACCEPT_LANGUAGE='en'),
                            'This build is too large to be read.')
        same_origin = self.client.generic('POST', '/import/build/', b'data=x',
                                          content_type='application/x-www-form-urlencoded',
                                          CONTENT_LENGTH=str(10 ** 9),
                                          HTTP_ACCEPT_LANGUAGE='en',
                                          HTTP_SEC_FETCH_SITE='same-origin')
        self.assertContains(same_origin, 'This build is too large to be read.')

    def test_every_hostile_body_the_crawler_sends_answers_below_500(self):
        for raw in check_actions.SENT_BUILDS:
            with self.subTest(raw=raw[:40]):
                page = self.client.post('/import/build/', {'data': raw})
                self.assertLess(page.status_code, 500)
                self.assertLess(_follow_hop(self.client, page).status_code, 500)
                page = self.client.post('/import/text/', {'text': raw})
                self.assertLess(page.status_code, 500)
                page = self.client.get('/retro/import/build/', {'data': raw[:7000]})
                self.assertLess(page.status_code, 500)
                answer = self.client.post('/api/v1/import/validate/', raw,
                                          content_type='application/json')
                self.assertLess(answer.status_code, 500)
                self.assertFalse(answer.json()['valid'])
        self.assertEqual(0, Char.objects.count())

    def test_the_crawler_feeds_both_new_post_routes(self):
        command = check_actions.Command()
        paths = {entry[0] for entry in command._payloads('dofus3', 0)}
        self.assertIn('/import/build/', paths)
        self.assertIn('/api/v1/import/validate/', paths)
        retro_paths = {entry[0] for entry in command._payloads('retro', 0)}
        self.assertIn('/import/build/', retro_paths)
        self.assertNotIn('/api/v1/import/validate/', retro_paths)

    def test_a_bare_address_goes_to_the_import_page(self):
        page = self.client.get('/fr/touch/import/build/')
        self.assertEqual(302, page.status_code)
        self.assertEqual('/fr/touch/import/text/', page['Location'])


class TheCounterNamesTheSenderTests(_SentBuild):

    def _rows(self):
        return sorted((row.source, row.host, row.game_version, row.attempts, row.imported)
                      for row in ImportSourceHit.objects.all())

    def test_a_preview_counts_an_attempt_and_the_confirm_an_import_under_the_source(self):
        payload = fashionista_build.example_payload('retro')
        preview = self._link(payload, HTTP_USER_AGENT=BROWSER, HTTP_ACCEPT_LANGUAGE='en')
        self.assertEqual([('api', 'example.org', 'retro', 1, 0)], self._rows())
        self._confirm(preview, char_class='Cra', level='100')
        self.assertEqual([('api', 'example.org', 'retro', 1, 1)], self._rows())

    def test_two_first_time_visitors_of_one_link_count_as_two_attempts_and_two_imports(self):
        payload = fashionista_build.example_payload('retro')
        for _visitor in range(2):
            visitor = Client()
            preview = visitor.get('/retro/import/build/', {'data': _data(payload)},
                                  HTTP_USER_AGENT=BROWSER, HTTP_ACCEPT_LANGUAGE='en')
            again = visitor.get('/retro/import/build/', {'data': _data(payload)},
                                HTTP_USER_AGENT=BROWSER, HTTP_ACCEPT_LANGUAGE='en')
            self.assertContains(again, 'Build received')
            self._confirm(preview, char_class='Cra', level='100', client=visitor)
        self.assertEqual(2, Char.objects.count())
        self.assertEqual([('api', 'example.org', 'retro', 2, 2)], self._rows())

    def test_a_source_that_is_no_domain_counts_under_no_host(self):
        payload = dict(fashionista_build.example_payload('dofus3'), source='localhost')
        self._post(payload, HTTP_USER_AGENT=BROWSER)
        payload = dict(payload, source='https://WWW.Example.COM/some/path')
        self._post(payload, HTTP_USER_AGENT=BROWSER)
        self.assertEqual([('api', '', 'dofus3', 1, 0), ('api', 'example.com', 'dofus3', 1, 0)],
                         self._rows())

    def test_a_link_that_cannot_be_decoded_counts_under_no_host(self):
        self.client.get('/import/build/', {'data': '!!'}, HTTP_USER_AGENT=BROWSER)
        self.assertEqual([('api', '', 'dofus3', 1, 0)], self._rows())

    def test_a_crawler_counts_nothing(self):
        payload = fashionista_build.example_payload('dofus3')
        self._link(payload, HTTP_USER_AGENT='Googlebot/2.1')
        self._link(payload)
        self.assertEqual([], self._rows())

    def test_the_admin_import_tab_lists_the_sending_sites_apart_from_the_pastes(self):
        from django.contrib.auth.models import User
        from django.utils import timezone
        from chardata import admin_stats
        today = timezone.localdate()
        for source, host, attempts, imported in (('api', 'example.org', 4, 1),
                                                  ('api', '', 2, 0),
                                                  ('text', '', 5, 5)):
            ImportSourceHit.objects.create(day=today, source=source, host=host,
                                           game_version='dofus3', attempts=attempts,
                                           imported=imported)
        data = admin_stats.imports(admin_stats.resolve_period('30d'), 'dofus3')
        self.assertEqual([('example.org', 4, 1, 25.0), ('No source named', 2, 0, 0.0)],
                         [(r['label'], r['attempts'], r['imported'], r['rate'])
                          for r in data['sent']])
        self.assertEqual(5, data['total'])
        boss = User.objects.create_user('boss', 'boss@test.local', 'pw-42-solid')
        boss.is_superuser = True
        boss.save()
        self.client.force_login(boss)
        page = self.client.get('/admin-tools/', {'period': '30d', 'version': 'dofus3'})
        self.assertContains(page, 'id="admin-imports-sent"')
        self.assertContains(page, 'Builds other sites send')
        self.assertContains(page, '<td>example.org</td>')


class TheBackLinkIsHttpsAndEscapedTests(_SentBuild):

    def _back_links(self, page):
        return [attrs for attrs in _tags(page, 'a')
                if attrs.get('referrerpolicy') == 'origin'
                and attrs.get('href', '').startswith('https://example.org/')]

    def test_an_https_back_url_is_shown_as_imported_from_its_site(self):
        payload = fashionista_build.example_payload('dofus3')
        page = self._link(payload, HTTP_ACCEPT_LANGUAGE='en')
        self.assertContains(page, 'Imported from example.org')
        links = self._back_links(page)
        self.assertEqual(1, len(links))
        self.assertEqual('https://example.org/builds/42', links[0]['href'])
        self.assertEqual('_blank', links[0].get('target'))
        self.assertIn('noopener', links[0].get('rel', '').split())

    def test_any_other_address_is_never_shown(self):
        for address in ('http://example.org/builds/42', 'javascript:alert(1)',
                        'https://user:pw@example.org/', 'https://localhost/x',
                        'https://example.org:8443/x', 'ftp://example.org/', 12):
            with self.subTest(address=address):
                payload = dict(fashionista_build.example_payload('dofus3'),
                               back_url=address)
                page = self._link(payload, HTTP_ACCEPT_LANGUAGE='en')
                self.assertContains(page, 'Build received')
                self.assertNotContains(page, 'id="import-back"')
                self.assertNotContains(page, 'Imported from')

    def test_markup_inside_the_address_reaches_the_page_escaped(self):
        address = 'https://example.org/b?q="><script>alert(1)</script>'
        payload = dict(fashionista_build.example_payload('dofus3'), back_url=address)
        page = self._link(payload, HTTP_ACCEPT_LANGUAGE='en')
        self.assertNotContains(page, '<script>alert(1)</script>')
        self.assertEqual(address, self._back_links(page)[0]['href'])


class AFormFromAnotherSiteKeepsTheReadersCookiesTests(_SentBuild):

    def test_a_cross_site_post_sets_no_cookie_and_posts_the_build_again_from_our_origin(self):
        text = json.dumps(fashionista_build.example_payload('dofus3'))
        page = Client().post('/fr/import/build/', {'data': text},
                             HTTP_SEC_FETCH_SITE='cross-site')
        self.assertEqual(200, page.status_code)
        self.assertEqual([], sorted(page.cookies))
        self.assertEqual(('/fr/import/build/', {'data': text, 'hop': '1'}), _hop_form(page))
        self.assertEqual('fr', _tags(page, 'html')[0].get('lang'))
        self.assertEqual('noindex', page['X-Robots-Tag'])
        self.assertEqual(0, ImportSourceHit.objects.count())

    def test_a_guest_with_a_build_is_warned_before_a_sent_build_replaces_it(self):
        structure = get_structure('dofus3')
        hat = next(i for i in structure.types[200]['Hat'] if not i.removed)
        self.client.post('/import/text/', {
            'text': structure.get_item_name_in_language(hat, 'en'),
            'confirm': '1', 'char_class': 'Iop', 'level': '200'})
        self.assertEqual(1, Char.objects.count())
        payload = fashionista_build.example_payload('dofus3')
        from_partner = Client().post('/import/build/', {'data': json.dumps(payload)},
                                     HTTP_SEC_FETCH_SITE='cross-site',
                                     HTTP_ACCEPT_LANGUAGE='en')
        page = _follow_hop(self.client, from_partner, HTTP_ACCEPT_LANGUAGE='en')
        self.assertContains(page, 'Build received: Example build')
        self.assertContains(page, 'You already have a build on')

    def test_a_post_from_our_own_page_opens_the_preview_at_once(self):
        payload = fashionista_build.example_payload('dofus3')
        page = self.client.post('/import/build/', {'data': json.dumps(payload)},
                                HTTP_SEC_FETCH_SITE='same-origin', HTTP_ACCEPT_LANGUAGE='en')
        self.assertIsNone(_hop_form(page))
        self.assertContains(page, 'Build received: Example build')

    def test_a_browser_without_fetch_metadata_is_sent_on_once_and_not_twice(self):
        payload = fashionista_build.example_payload('dofus3')
        first = self.client.post('/import/build/', {'data': json.dumps(payload)})
        action, fields = _hop_form(first)
        second = self.client.post(action, fields, HTTP_ACCEPT_LANGUAGE='en')
        self.assertIsNone(_hop_form(second))
        self.assertContains(second, 'Build received: Example build')


class AClassIntCannotReadOrALoneSurrogateAnswersBelow500Tests(_SentBuild):

    CLASSES = (chr(0xb2), chr(0x2460), '9' * 5000)

    def test_a_class_int_cannot_read_is_an_unknown_class_on_every_door(self):
        for value in self.CLASSES:
            payload = dict(fashionista_build.example_payload('dofus3'), **{'class': value})
            text = json.dumps(payload)
            with self.subTest(value=value[:5]):
                answer = self.client.post('/api/v1/import/validate/', text,
                                          content_type='application/json')
                self.assertEqual(200, answer.status_code)
                self.assertIn('unknown_class',
                              [warning['code'] for warning in answer.json()['warnings']])
                self.assertLess(self.client.get('/import/build/', {'data': text}).status_code,
                                500)
                self.assertContains(self._post(payload, HTTP_ACCEPT_LANGUAGE='en'),
                                    'Build received')
                self.assertContains(self.client.post('/import/text/', {'text': text},
                                                     HTTP_ACCEPT_LANGUAGE='en'),
                                    'Build received')

    def test_a_lone_surrogate_is_refused_as_unreadable_json_on_every_door(self):
        escape = chr(92) + 'ud800'
        good = json.dumps(fashionista_build.example_payload('dofus3'))
        bodies = {
            'name': good.replace('"Example build"', '"abc%s"' % escape),
            'back_url': good.replace('"https://example.org/builds/42"',
                                     '"https://example.org/%s"' % escape),
            'stat key': good.replace('"key": "', '"key": "%s' % escape, 1),
            'field name': good.replace('{"format"', '{"%s": 1, "format"' % escape, 1),
        }
        for where, body in bodies.items():
            self.assertIn(escape, body)
            with self.subTest(where=where):
                answer = self.client.post('/api/v1/import/validate/', body,
                                          content_type='application/json')
                self.assertEqual(400, answer.status_code)
                self.assertEqual(['not_json'], [e['code'] for e in answer.json()['errors']])
                for page in (self.client.get('/import/build/', {'data': body},
                                             HTTP_ACCEPT_LANGUAGE='en'),
                             self._post(body, prefix='', HTTP_ACCEPT_LANGUAGE='en'),
                             self.client.post('/import/text/', {'text': body},
                                              HTTP_ACCEPT_LANGUAGE='en')):
                    self.assertContains(page, 'This build is not valid JSON.')
        self.assertEqual(0, Char.objects.count())


class ThePlayerIsSpokenToAsAPlayerTests(_SentBuild):

    def test_a_refused_build_speaks_to_the_player_first_and_gives_the_reason_after(self):
        page = self.client.get('/import/build/', {'data': '!!'}, HTTP_ACCEPT_LANGUAGE='en')
        body = page.content.decode('utf-8')
        lead = body.index('The site that sent this build sent something we cannot read.')
        detail = body.index('id="import-error-detail"')
        self.assertLess(lead, detail)
        self.assertLess(detail, body.index('The data in the link is not valid base64url.'))
        french = self.client.get('/fr/import/build/', {'data': '!!'})
        self.assertContains(french, 'Le site qui a envoyé ce build nous a transmis '
                                    'quelque chose d’illisible.')

    def test_a_sent_builds_exos_are_named_without_speaking_of_a_link(self):
        payload = fashionista_build.example_payload('dofus3')
        page = self._link(payload, HTTP_ACCEPT_LANGUAGE='en')
        self.assertContains(page, 'The exos of the build become its exo options: AP.')
        self.assertNotContains(page, 'The exos from the link')

    def test_a_piece_sent_again_where_the_game_forbids_it_is_named_and_left_out(self):
        payload = fashionista_build.example_payload('dofus3')
        amulet = payload['items'][2]
        payload['items'].append(amulet)
        page = self._link(payload, HTTP_ACCEPT_LANGUAGE='en')
        self.assertContains(page, 'id="import-sent-worn-twice"')
        structure = get_structure('dofus3')
        self.assertTrue(_contains_name(page, structure.get_item_name_in_language(
            structure.get_item_by_ankama_id(amulet), 'en')))

    def test_a_landing_page_names_the_import_page_as_canonical_and_publishes_no_hreflang(self):
        payload = fashionista_build.example_payload('retro')
        page = self._link(payload, prefix='/fr/retro')
        self.assertEqual(200, page.status_code)
        links = _tags(page, 'link')
        self.assertEqual(['https://dofusfashionista.gg/fr/retro/import/text/'],
                         [link.get('href') for link in links if link.get('rel') == 'canonical'])
        self.assertEqual([], [link for link in links if link.get('hreflang')])
