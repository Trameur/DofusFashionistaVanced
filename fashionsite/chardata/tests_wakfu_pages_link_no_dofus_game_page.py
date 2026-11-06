# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.

"""A Wakfu page links the Wakfu site, the shared site pages and each game's home, no Dofus page.

The version switcher is the one way out: it leads to another game's home or item list."""
from html.parser import HTMLParser

from django.test import TestCase
from django.conf import settings
from django.urls import Resolver404, resolve
from django.utils import translation

from chardata import game_urls, wakfu_urls
from chardata.wakfu_flag_for_tests import wakfu_flag

LANDINGS = ('/wakfu/', '/fr/wakfu/', '/es/wakfu/', '/pt/wakfu/', '/de/wakfu/')
LIST_PAGES = tuple('/%swakfu/encyclopedia/' % prefix for prefix in ('', 'fr/', 'es/', 'pt/', 'de/'))
ITEM_PAGES = tuple('/%swakfu/encyclopedia/item/equipment/2021-x/' % prefix
                   for prefix in ('', 'fr/', 'es/', 'pt/', 'de/'))


def _resolve(path):
    """The match of a path under the language its prefix names."""
    for code, _name in settings.LANGUAGES:
        with translation.override(code):
            try:
                return resolve(path)
            except Resolver404:
                continue
    return None


class _Targets(HTMLParser):
    """The local addresses a page points at, those of the version switcher apart."""

    ATTRIBUTE = {'a': 'href', 'link': 'href', 'form': 'action'}

    def __init__(self, html):
        super().__init__()
        self.targets = set()
        self.switcher = set()
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        target = attributes.get(self.ATTRIBUTE.get(tag, ''))
        if target and target.startswith('/') and not target.startswith(('//', '/static/')):
            in_switcher = 'version-link' in (attributes.get('class') or '').split()
            found = self.switcher if in_switcher else self.targets
            found.add(target.split('#')[0].split('?')[0])


class WakfuPagesLinkNoDofusGamePageTests(TestCase):
    def test_every_local_link_of_a_landing_is_a_wakfu_or_a_site_page(self):
        self.assert_pages_link_no_dofus_game_page(LANDINGS)

    def test_every_local_link_of_the_item_list_is_a_wakfu_or_a_site_page(self):
        self.assert_pages_link_no_dofus_game_page(LIST_PAGES)

    def test_every_local_link_of_a_filtered_item_list_is_a_wakfu_or_a_site_page(self):
        self.assert_pages_link_no_dofus_game_page(
            tuple(path + '?q=ring&page=2' for path in LIST_PAGES))

    def test_every_local_link_of_an_item_page_is_a_wakfu_or_a_site_page(self):
        self.assert_pages_link_no_dofus_game_page(ITEM_PAGES)

    def assert_pages_link_no_dofus_game_page(self, landings):
        game_names = {pattern.name for pattern in game_urls.urlpatterns
                      if getattr(pattern, 'name', None)}
        with wakfu_flag(True):
            for landing in landings:
                response = self.client.get(landing, follow=True)
                self.assertEqual(200, response.status_code, landing)
                links = _Targets(response.content.decode('utf-8'))
                self.assertTrue(links.switcher, landing)
                for target in sorted(links.switcher):
                    with self.subTest(landing=landing, switcher=target):
                        match = _resolve(target)
                        self.assertTrue(match.namespace == 'wakfu'
                                        or match.url_name in ('home', 'encyclopedia'),
                                        target)
                targets = links.targets
                self.assertTrue(targets, landing)
                for target in sorted(targets):
                    with self.subTest(landing=landing, target=target):
                        match = _resolve(target)
                        self.assertIsNotNone(match, '%s links %s, which resolves to nothing'
                                             % (landing, target))
                        name = match.url_name
                        self.assertTrue(
                            match.namespace == 'wakfu'
                            or name in wakfu_urls.WAKFU_SITE_ROUTES
                            or name not in game_names
                            or name == 'home',
                            '%s links the Dofus page %s (%s)' % (landing, target, name))
