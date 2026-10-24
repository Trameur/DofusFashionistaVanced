# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.

"""A Wakfu page links the Wakfu site, the shared site pages and each game's home, no Dofus page."""
from html.parser import HTMLParser

from django.test import TestCase
from django.conf import settings
from django.urls import Resolver404, resolve
from django.utils import translation

from chardata import game_urls, wakfu_urls
from chardata.wakfu_flag_for_tests import wakfu_flag

LANDINGS = ('/wakfu/', '/fr/wakfu/', '/es/wakfu/', '/pt/wakfu/', '/de/wakfu/')


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
    """The local addresses a page points at."""

    ATTRIBUTE = {'a': 'href', 'link': 'href', 'form': 'action'}

    def __init__(self, html):
        super().__init__()
        self.targets = set()
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        target = dict(attrs).get(self.ATTRIBUTE.get(tag, ''))
        if target and target.startswith('/') and not target.startswith(('//', '/static/')):
            self.targets.add(target.split('#')[0].split('?')[0])


class WakfuPagesLinkNoDofusGamePageTests(TestCase):
    def test_every_local_link_of_a_landing_is_a_wakfu_or_a_site_page(self):
        game_names = {pattern.name for pattern in game_urls.urlpatterns
                      if getattr(pattern, 'name', None)}
        with wakfu_flag(True):
            for landing in LANDINGS:
                targets = _Targets(self.client.get(landing).content.decode('utf-8')).targets
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
