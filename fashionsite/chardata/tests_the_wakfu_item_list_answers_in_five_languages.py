# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.

"""The Wakfu item list answers in each site language while the flag is on, and not otherwise."""
import os

from django.core.cache import cache
from django.test import TestCase

from chardata import wakfu_encyclopedia_data as data
from chardata.wakfu_flag_for_tests import wakfu_flag

LANGUAGES = ('en', 'fr', 'es', 'pt', 'de')
ITEM_PAGE = '/fr/wakfu/encyclopedia/item/equipment/2021-x/'


def path_of(language):
    return '/%swakfu/encyclopedia/' % ('' if language == 'en' else language + '/')


class TheWakfuItemListAnswersInFiveLanguagesTests(TestCase):
    def setUp(self):
        cache.clear()
        if not os.path.exists(data.database_path()):
            self.skipTest('no Wakfu database built; run update_data_wakfu.py')

    def test_the_list_answers_200_in_each_language(self):
        with wakfu_flag(True):
            for language in LANGUAGES:
                with self.subTest(language=language):
                    self.assertEqual(200, self.client.get(path_of(language)).status_code)

    def test_the_version_switcher_leads_to_the_list_of_the_other_version(self):
        with wakfu_flag(True):
            html = self.client.get(path_of('fr')).content.decode('utf-8')
            item = self.client.get(ITEM_PAGE, follow=True).content.decode('utf-8')
        self.assertIn('href="/fr/encyclopedia/"', html)
        self.assertIn('href="/fr/encyclopedia/"', item)

    def test_the_menu_of_every_wakfu_page_leads_to_the_list(self):
        with wakfu_flag(True):
            pages = [self.client.get(path, follow=True).content.decode('utf-8')
                     for path in ('/fr/wakfu/', path_of('fr'), ITEM_PAGE)]
        for html in pages:
            self.assertRegex(html, r'<a [^>]*menu_link[^>]*href="?/fr/wakfu/encyclopedia/"?[ >]')
            self.assertRegex(html, r'<form [^>]*action="?/fr/wakfu/encyclopedia/"?[ >]')

    def test_the_landing_links_the_list_in_its_text(self):
        with wakfu_flag(True):
            html = self.client.get('/fr/wakfu/').content.decode('utf-8')
        self.assertRegex(html, r'<p> ?<a href="?/fr/wakfu/encyclopedia/"?>')

    def test_the_list_answers_404_while_the_flag_is_off(self):
        for language in LANGUAGES:
            with self.subTest(language=language):
                self.assertEqual(404, self.client.get(path_of(language)).status_code)

    def test_the_german_list_keeps_its_language_and_marks_the_game_texts(self):
        with wakfu_flag(True):
            html = self.client.get(path_of('de')).content.decode('utf-8')
            english = self.client.get(path_of('en')).content.decode('utf-8')
        self.assertIn('<html lang="de"', html)
        self.assertIn('wakfu-game-text-notice', html)
        self.assertIn('<span lang="en">', html)
        self.assertNotIn('wakfu-game-text-notice', english)
        self.assertNotIn('<span lang="en">', english)

    def test_the_other_languages_keep_theirs(self):
        with wakfu_flag(True):
            for language in ('fr', 'es', 'pt'):
                html = self.client.get(path_of(language)).content.decode('utf-8')
                self.assertIn('<html lang="%s"' % language, html)
                self.assertNotIn('<span lang="en">', html)

    def test_a_language_prefix_never_leaks_into_the_list_links(self):
        with wakfu_flag(True):
            for language in LANGUAGES:
                with self.subTest(language=language):
                    html = self.client.get(path_of(language)).content.decode('utf-8')
                    self.assertIn('href="%s"' % path_of(language), html)
