# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A Touch build's seals go out and come back through the text, the fashionista-build and DofusBook doors."""

import html.parser
import json
import pickle
from unittest import mock

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import RequestFactory, TestCase
from django.utils import translation

from chardata import fashionista_build
from chardata.char_blobs import read_char_blob
from chardata.models import Char, CharBaseStats
from chardata.solution import get_solution
from chardata.solution_view import _build_share_text
from chardata.tests_a_touch_build_saved_before_the_seals_still_loads import (
    _OPTIONS, sixteen_slot_minimal)
from chardata.text_build_import import read_items
from fashionistapulp.dofus_constants import STATS_NAMES
from fashionistapulp.structure import get_structure, set_current_game_version

LANGUAGES = ('en', 'fr', 'es', 'pt', 'de')

BROWSER = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
           '(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36')


def _stored(char):
    return read_char_blob(char.minimal_solution, None, 'minimal_solution',
                          char).item_per_slot


class _Hidden(html.parser.HTMLParser):

    def __init__(self):
        super().__init__()
        self.hidden = {}
        self.forms = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'input' and attrs.get('type') == 'hidden':
            self.hidden.setdefault(attrs.get('name'), []).append(attrs.get('value'))
        if tag == 'form':
            self.forms.append(attrs)


class _SealedBuild(TestCase):

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.addCleanup(set_current_game_version, 'dofus3')
        set_current_game_version('touch')
        self.structure = get_structure('touch')
        self.power = self.structure.get_item_by_name('Iop Seal: Power')
        self.jump = self.structure.get_item_by_name('Iop Seal: Jump')
        self.heroism = self.structure.get_item_by_name('Feca Seal: Heroism')
        minimal = sixteen_slot_minimal(self.structure)
        minimal.item_per_slot['emblem1'] = self.power.id
        minimal.item_per_slot['emblem2'] = self.jump.id
        self.owner = User.objects.create_user('sealed', 'sealed@test.local',
                                              'pw-42-solid')
        self.client.force_login(self.owner)
        self.char = Char.objects.create(
            name='Sealed', char_name='Sealed', char_class='Iop', char_build='',
            level=200, minimum_stats=b'', minimum_crits=b'',
            stats_weight=pickle.dumps({}), options=pickle.dumps(dict(_OPTIONS)),
            inclusions=b'', exclusions=b'', owner=self.owner, link_shared=True,
            game_version='touch', minimal_solution=pickle.dumps(minimal))
        for name, _key in STATS_NAMES:
            CharBaseStats.objects.create(char=self.char, stat=name,
                                         total_value=100, scrolled_value=100)

    def _share_text(self, language):
        with translation.override(language):
            return _build_share_text(RequestFactory().get('/'), self.char,
                                     get_solution(self.char))

    def _seals_of(self, char):
        stored = _stored(char)
        return sorted(item_id for slot, item_id in stored.items()
                      if slot.startswith('emblem') and item_id)


class TheTextExportCarriesTheSealsTests(_SealedBuild):

    def test_the_text_names_both_seals_in_every_language(self):
        for language in LANGUAGES:
            with self.subTest(language=language):
                text = self._share_text(language)
                for seal in (self.power, self.jump):
                    self.assertIn(seal.localized_names[language], text)

    def test_the_text_import_reads_both_seals_back_in_every_language(self):
        for language in LANGUAGES:
            with self.subTest(language=language), translation.override(language):
                read = read_items(self._share_text(language), 'touch', language)
                self.assertIn(self.power.id, read['item_ids'])
                self.assertIn(self.jump.id, read['item_ids'])

    def test_the_confirmed_text_import_wears_them_in_the_seal_slots(self):
        answer = self.client.post('/touch/import/text/', {
            'text': self._share_text('fr'), 'confirm': '1',
            'char_class': 'Iop', 'level': '200'})
        self.assertEqual(302, answer.status_code)
        copy = Char.objects.order_by('-id').first()
        self.assertNotEqual(self.char.id, copy.id)
        self.assertEqual(sorted([self.power.id, self.jump.id]),
                         self._seals_of(copy))

    def test_an_import_for_another_class_leaves_its_seals_out(self):
        text = '\n'.join((self.heroism.localized_names['en'],
                          self.power.localized_names['en']))
        answer = self.client.post('/touch/import/text/', {
            'text': text, 'confirm': '1', 'char_class': 'Feca',
            'level': '200'})
        self.assertEqual(302, answer.status_code)
        copy = Char.objects.order_by('-id').first()
        self.assertEqual([self.heroism.id], self._seals_of(copy))


class TheFashionistaBuildCarriesTheSealsTests(_SealedBuild):

    def test_the_export_lists_the_seals_and_the_copy_wears_them(self):
        answer = self.client.get('/touch/export/fashionista/%d/' % self.char.id)
        self.assertEqual(200, answer.status_code)
        payload = answer.json()
        sent = [entry['id'] if isinstance(entry, dict) else entry
                for entry in payload['items']]
        self.assertIn(self.power.ankama_id, sent)
        self.assertIn(self.jump.ankama_id, sent)
        report = fashionista_build.report(payload)
        self.assertTrue(report['valid'], report['errors'])
        self.assertEqual([], report['warnings'])

        preview = self.client.get(
            '/touch/import/build/',
            {'data': fashionista_build.encode_link_data(payload)},
            HTTP_ACCEPT_LANGUAGE='en', HTTP_USER_AGENT=BROWSER)
        self.assertEqual(200, preview.status_code)
        parsed = _Hidden()
        parsed.feed(preview.content.decode('utf-8'))
        action = next(form['action'] for form in parsed.forms
                      if form.get('action', '').endswith('/import/text/'))
        done = self.client.post(action, {
            'text': parsed.hidden['text'][-1], 'confirm': '1',
            'char_class': 'Iop', 'level': '200',
            'count_token': (parsed.hidden.get('count_token') or [''])[0]},
            HTTP_USER_AGENT=BROWSER)
        self.assertEqual(302, done.status_code)
        copy = Char.objects.order_by('-id').first()
        self.assertEqual(sorted(i for i in _stored(self.char).values() if i),
                         sorted(i for i in _stored(copy).values() if i))
        self.assertEqual(sorted([self.power.id, self.jump.id]),
                         self._seals_of(copy))


class DofusBookListsTheSealsAsStayingTests(_SealedBuild):

    def test_the_export_page_keeps_the_seals_here(self):
        worn = [item for item in get_solution(self.char).item_list
                if item.item_added and not item.slot.startswith('emblem')]

        class Answer(object):
            def read(self, *args):
                return json.dumps({'data': [{'official': item.ankama_id}
                                            for item in worn]}).encode('utf-8')

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        with mock.patch('chardata.dofusbook_import._urlopen_allowlisted',
                        return_value=Answer()):
            page = self.client.get('/touch/export/dofusbook/%d/' % self.char.id)
        self.assertEqual(200, page.status_code)
        staying = page.context['staying']
        self.assertIn(self.power.name, staying)
        self.assertIn(self.jump.name, staying)
        self.assertNotIn(self.power.name, page.context['going'])
