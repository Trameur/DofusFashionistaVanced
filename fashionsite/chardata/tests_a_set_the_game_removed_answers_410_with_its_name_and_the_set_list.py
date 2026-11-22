# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A set the game removed answers 410 with its name and a link to the version's set list."""

import json
import re
from unittest import mock

from django.test import TestCase
from django.utils.html import escape

from chardata import encyclopedia_view
from chardata import retired_sets as retired_sets_module
from chardata.official_site import get_set_link
from chardata.retired_sets import retired_set_name, retired_sets
from fashionistapulp.structure import get_structure

LANGUAGES = ('fr', 'en', 'es', 'pt', 'de')


def _first():
    return min(retired_sets('retro'))


class RetiredSetPageTests(TestCase):

    def _get(self, url, language='en'):
        return self.client.get(url, HTTP_ACCEPT_LANGUAGE=language)

    def test_retro_records_the_sets_the_game_removed(self):
        self.assertTrue(retired_sets('retro'))

    def test_no_recorded_set_is_live_in_retro(self):
        structure = get_structure('retro')
        live = set(structure.sets_dict) | set(structure.dt_sets_dict)
        self.assertFalse(set(retired_sets('retro')) & live)

    def test_a_removed_set_answers_410_with_its_name_in_the_page_language(self):
        set_id = _first()
        for language in LANGUAGES:
            with self.subTest(language=language):
                resp = self._get('/retro/encyclopedia/set/%d/' % set_id, language)
                self.assertEqual(resp.status_code, 410)
                title = encyclopedia_view.LOCALIZED_UI[language]['missing_retired_set_title']
                self.assertContains(resp, escape(title), status_code=410)
                name = retired_set_name('retro', set_id, language)
                self.assertContains(resp, escape(name), status_code=410)

    def test_the_slug_changes_nothing(self):
        set_id = _first()
        names = retired_sets('retro')[set_id]
        urls = ['/retro/encyclopedia/set/%d/' % set_id,
                '/retro/encyclopedia/set/%d-zzz/' % set_id]
        for lang in ('fr', 'en'):
            if lang in names:
                urls.append(get_set_link(set_id, names[lang], 'retro'))
        spanish = escape(retired_set_name('retro', set_id, 'es'))
        for url in urls:
            with self.subTest(url=url):
                resp = self._get(url, 'es')
                self.assertEqual(resp.status_code, 410)
                self.assertContains(resp, spanish, status_code=410)

    def test_every_recorded_set_answers_410(self):
        for set_id in retired_sets('retro'):
            with self.subTest(set_id=set_id):
                self.assertEqual(
                    self._get('/retro/encyclopedia/set/%d/' % set_id).status_code, 410)

    def test_the_page_links_to_the_version_set_list_and_encyclopedia(self):
        resp = self._get('/retro/encyclopedia/set/%d/' % _first())
        self.assertContains(resp, 'href="/retro/encyclopedia/sets/"', status_code=410)
        self.assertContains(resp, 'href="/retro/encyclopedia/"', status_code=410)

    def test_the_page_is_noindex_and_its_breadcrumb_has_no_leaf(self):
        resp = self._get('/retro/encyclopedia/set/%d/' % _first())
        self.assertContains(resp, 'noindex, follow', status_code=410)
        body = resp.content.decode('utf-8')
        blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', body, re.S)
        crumbs = [json.loads(b) for b in blocks if '"BreadcrumbList"' in b]
        self.assertEqual(len(crumbs), 1)
        items = crumbs[0]['itemListElement']
        self.assertEqual(len(items), 2)
        self.assertTrue(json.dumps(items[-1]).count('/retro/encyclopedia/') >= 1)
        self.assertIn(items[-1]['item'] if isinstance(items[-1].get('item'), str)
                      else items[-1]['item']['@id'], ['https://dofusfashionista.gg/retro/encyclopedia/'])

    def test_a_name_missing_in_the_page_language_falls_back_to_english(self):
        with mock.patch.dict(retired_sets_module._retired_by_version,
                             {'retro': {1: {'en': 'Only English'}}}):
            self.assertEqual(retired_set_name('retro', 1, 'fr'), 'Only English')
            self.assertIsNone(retired_set_name('retro', 2, 'fr'))

    def test_a_live_retro_set_still_answers_200(self):
        structure = get_structure('retro')
        item_set = next(s for s in structure.sets_dict.values() if getattr(s, 'items', None))
        name = item_set.localized_names.get('en') or item_set.name
        resp = self._get(get_set_link(item_set.ankama_id, name, 'retro'), 'en')
        self.assertEqual(resp.status_code, 200)

    def test_an_unknown_retro_set_still_answers_404(self):
        resp = self._get('/retro/encyclopedia/set/99999999/')
        self.assertContains(
            resp, escape(encyclopedia_view.LOCALIZED_UI['en']['missing_set_title']),
            status_code=404)

    def test_the_same_id_in_another_version_answers_what_that_version_holds(self):
        set_id = _first()
        title = escape(encyclopedia_view.LOCALIZED_UI['en']['missing_retired_set_title'])
        for version in ('dofus3', 'beta', 'dofus2', 'touch'):
            with self.subTest(version=version):
                prefix = '' if version == 'dofus3' else '/%s' % version
                resp = self._get('%s/encyclopedia/set/%d/' % (prefix, set_id))
                structure = get_structure(version)
                live = set_id in structure.sets_dict or set_id in structure.dt_sets_dict
                if set_id in retired_sets(version):
                    self.assertEqual(resp.status_code, 410)
                elif live:
                    self.assertIn(resp.status_code, (200, 301, 302))
                else:
                    self.assertEqual(resp.status_code, 404)
                if resp.status_code != 410:
                    self.assertNotContains(resp, title, status_code=resp.status_code)

    def test_every_language_has_the_retired_set_texts(self):
        for language in LANGUAGES:
            with self.subTest(language=language):
                texts = encyclopedia_view.LOCALIZED_UI[language]
                for key in ('missing_retired_set_title', 'missing_retired_set_message',
                            'missing_sets_link'):
                    self.assertTrue(texts[key])
                    self.assertNotIn('\u2013', texts[key])
                    self.assertNotIn('\u2014', texts[key])
                self.assertIn('%(name)s', texts['missing_retired_set_message'])
                self.assertIn('%(game)s', texts['missing_retired_set_message'])
                self.assertIn('%(game)s', texts['missing_sets_link'])
