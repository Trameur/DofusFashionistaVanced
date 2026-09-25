# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The JS catalogue, the changelog body and guide links follow the page's language."""

import os
import re

from django.template import Context, Template
from django.test import TestCase
from django.utils import translation

from chardata.guides_content import slug_for

TEMPLATES = os.path.join(os.path.dirname(__file__), 'templates', 'chardata')
TRANSLATED = ('fr', 'es', 'pt', 'de')


class FetchedTextFollowsThePageLanguageTests(TestCase):

    def _french_page(self):
        response = self.client.get('/fr/faq/', HTTP_ACCEPT_LANGUAGE='en-US')
        self.assertEqual(200, response.status_code)
        return response.content.decode('utf-8')

    def test_the_french_page_catalogue_url_serves_the_french_catalogue(self):
        match = re.search(r'(/jsi18n/\?lang=[a-z]+)', self._french_page())
        self.assertIsNotNone(match)
        self.assertEqual('/jsi18n/?lang=fr', match.group(1))
        response = self.client.get(match.group(1), HTTP_ACCEPT_LANGUAGE='en-US')
        body = response.content.decode('utf-8')
        self.assertIn('Erreur de connexion.', body)
        self.assertEqual('fr', response['Content-Language'])

    def test_the_french_page_changelog_url_serves_the_french_changelog(self):
        match = re.search(r'(/changelog-content/\?lang=[a-z]+)', self._french_page())
        self.assertIsNotNone(match)
        self.assertEqual('/changelog-content/?lang=fr', match.group(1))
        response = self.client.get(match.group(1), HTTP_ACCEPT_LANGUAGE='en-US')
        body = response.content.decode('utf-8')
        self.assertIn('Toutes les versions', body)
        self.assertNotIn('All versions', body)

    def test_an_unknown_lang_falls_back_to_the_browser_language(self):
        response = self.client.get('/changelog-content/?lang=xx',
                                   HTTP_ACCEPT_LANGUAGE='en-US')
        self.assertIn('All versions', response.content.decode('utf-8'))

    def test_the_catalogue_urls_differ_per_language(self):
        english = self.client.get('/jsi18n/?lang=en', HTTP_ACCEPT_LANGUAGE='fr')
        self.assertNotIn('Erreur de connexion.', english.content.decode('utf-8'))


class GuideLinksFollowThePageLanguageTests(TestCase):

    def test_the_faq_links_the_getting_started_guide_in_each_language(self):
        for lang in TRANSLATED:
            with self.subTest(lang=lang):
                body = self.client.get('/%s/faq/' % lang).content.decode('utf-8')
                self.assertIn('/guides/%s/' % slug_for('getting-started', lang), body)

    def test_the_setup_page_links_the_class_guide_in_each_language(self):
        for lang in TRANSLATED:
            with self.subTest(lang=lang):
                body = self.client.get('/%s/setup/' % lang).content.decode('utf-8')
                self.assertIn('/guides/%s/' % slug_for('choosing-your-class', lang), body)
                self.assertNotIn('/guides/choosing-your-class/', body)

    def test_the_guide_url_tag_gives_the_translated_slug_in_each_language(self):
        template = Template("{% load version_url %}{% guide_url key %}")
        for key in ('how-it-works', 'monster-weaknesses'):
            for lang in TRANSLATED:
                with self.subTest(key=key, lang=lang), translation.override(lang):
                    url = template.render(Context({'key': key}))
                    self.assertTrue(url.endswith('/guides/%s/' % slug_for(key, lang)), url)
                    self.assertNotEqual(key, slug_for(key, lang))

    def test_the_guide_url_tag_keeps_the_version_prefix(self):
        template = Template("{% load version_url %}{% guide_url 'how-it-works' %}")
        with translation.override('fr'):
            url = template.render(Context({'current_game_version': 'retro'}))
        self.assertIn('/retro/guides/%s/' % slug_for('how-it-works', 'fr'), url)

    def test_the_solution_and_monster_pages_build_their_guide_link_with_guide_url(self):
        for name, key in (('solution.html', 'how-it-works'),
                          ('encyclopedia_monsters.html', 'monster-weaknesses'),
                          ('faq.html', 'getting-started'),
                          ('projdetails.html', 'choosing-your-class')):
            with self.subTest(template=name):
                with open(os.path.join(TEMPLATES, name), encoding='utf-8') as handle:
                    source = handle.read()
                self.assertIn("{%% guide_url '%s'" % key, source)
                self.assertNotIn("'guide' '%s'" % key, source)
                self.assertNotIn('/guides/%s/' % key, source)
