# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A build imported from text or a link keeps the reader's language prefix.

_solution_path and _url_pour_version used to build the redirect path by hand,
always without a language prefix. reverse() under the build's own version
namespace picks up the language active while the view runs instead.
"""
import os

from django.test import TestCase

from chardata import text_build_view
from fashionistapulp.fashionista_config import get_items_db_path


class ATextOnlyImportKeepsThePrefixTests(TestCase):

    def _url(self, version='dofus3', language=None):
        prefixe = '' if version == 'dofus3' else '/' + version
        return '/%s%s/import/text/' % (language, prefixe) if language \
            else '%s/import/text/' % prefixe

    def _texte(self, version='dofus3'):
        from fashionistapulp.structure import get_structure
        structure = get_structure(version)
        return '\n'.join(
            structure.get_item_name_in_language(
                next(i for i in structure.types[200][t] if not i.removed), 'en')
            for t in ('Hat', 'Cloak', 'Belt'))

    def test_the_solution_redirect_keeps_the_prefix(self):
        page = self.client.post(self._url(language='es'), {
            'text': self._texte(), 'confirm': '1', 'char_class': 'Iop',
            'level': '200'})
        self.assertEqual(302, page.status_code)
        self.assertTrue(page['Location'].startswith('/es/solution/'),
                        page['Location'])

    def test_the_english_redirect_still_carries_no_prefix(self):
        page = self.client.post(self._url(), {
            'text': self._texte(), 'confirm': '1', 'char_class': 'Iop',
            'level': '200'})
        self.assertEqual(302, page.status_code)
        self.assertTrue(page['Location'].startswith('/solution/'),
                        page['Location'])

    def test_a_version_mismatch_link_keeps_the_prefix(self):
        """A pasted header naming another version links back with the prefix."""
        if not os.path.exists(get_items_db_path('retro')):
            self.skipTest('no retro database')
        from chardata.solution_view import _build_share_text
        from chardata.solution import get_solution
        from chardata.models import Char
        from django.test import RequestFactory
        self.client.post('/retro/import/text/', {
            'text': self._texte('retro'), 'confirm': '1', 'char_class': 'Iop',
            'level': '200'})
        char = Char.objects.order_by('-id').first()
        texte_retro = _build_share_text(RequestFactory().get('/'), char,
                                        get_solution(char))
        page = self.client.post(self._url(language='es'), {'text': texte_retro})
        self.assertEqual('/es/retro/import/text/',
                         page.context['other_version_url'])


class ALinkImportKeepsThePrefixTests(TestCase):
    """A pasted link decides the build's own version, not the page's."""

    def setUp(self):
        self.addCleanup(setattr, text_build_view, 'read_build',
                        text_build_view.read_build)

    def _build(self, version):
        from fashionistapulp.structure import get_structure
        structure = get_structure(version)
        ids = [next(item.id for item in structure.types[200][type_name]
                    if not item.removed)
               for type_name in ('Hat', 'Cloak', 'Belt')]
        return {'game_version': version, 'source_host': 'www.dofusbook.net',
                'build_id': '1', 'name': 'Imported', 'level': 200,
                'item_ids': ids, 'missing': [], 'class_is_unknown': True}

    def _patch(self, build):
        def faux(url, opener=None):
            return build
        text_build_view.read_build = faux

    def test_a_touch_link_on_the_dofus3_page_redirects_kept_prefix(self):
        if not os.path.exists(get_items_db_path('touch')):
            self.skipTest('no touch database')
        self._patch(self._build('touch'))
        page = self.client.post('/es/import/text/', {
            'text': 'https://www.dofusbook.net/fr/stuff/123-a',
            'confirm': '1', 'char_class': 'Iop', 'level': '200'})
        self.assertEqual(302, page.status_code)
        self.assertTrue(page['Location'].startswith('/es/touch/solution/'),
                        page['Location'])


class TheLegacyImportAddressKeepsThePrefixTests(TestCase):

    def test_the_old_dofus3_address_redirects_with_the_prefix(self):
        page = self.client.get('/es/import/dofusbook/')
        self.assertEqual(301, page.status_code)
        self.assertEqual('/es/import/text/', page['Location'])

    def test_the_old_prefixed_version_address_redirects_with_the_prefix(self):
        page = self.client.get('/es/touch/import/dofusbook/')
        self.assertEqual(301, page.status_code)
        self.assertEqual('/es/touch/import/text/', page['Location'])
