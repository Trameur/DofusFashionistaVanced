# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A page of a list is canonical at its own page number; a filtered view points back at the plain one."""
import re
from unittest import mock

from django.test import RequestFactory, TestCase

SITE = 'https://dofusfashionista.gg'


class _Paginator(object):
    def __init__(self, num_pages):
        self.num_pages = num_pages


class _Page(object):
    """Enough of a Paginator page for a canonical to be built from it, without a real shared build."""

    def __init__(self, number, num_pages=83):
        self.number = number
        self.paginator = _Paginator(num_pages)


class TheSharedBuildsCanonicalTests(TestCase):
    """Every page of /sharedbuilds/ must name its own page, not fall back to the bare address."""

    def setUp(self):
        self.factory = RequestFactory()

    def _canonical(self, query, number=40):
        from chardata.shared_builds_view import _canonical_url
        request = self.factory.get('/sharedbuilds/' + query)
        return _canonical_url(request, _Page(number)).replace(SITE, '')

    def test_a_page_of_the_list_is_itself(self):
        self.assertEqual(self._canonical('?page=40'), '/sharedbuilds/?page=40')

    def test_the_first_page_is_the_plain_address(self):
        self.assertEqual(self._canonical('?page=1', number=1), '/sharedbuilds/')
        self.assertEqual(self._canonical('', number=1), '/sharedbuilds/')

    def test_a_filter_points_back_at_the_plain_list(self):
        for query in ('?page=40&char_class=Iop', '?page=40&check_str=on',
                      '?page=40&order_by=likes', '?page=40&search=gelano',
                      '?page=40&tag=pvp'):
            with self.subTest(query=query):
                self.assertEqual(self._canonical(query), '/sharedbuilds/')

    def test_tracking_noise_is_not_a_filter(self):
        # tracking params like utm_source must not make the page a duplicate of the first
        for query in ('?page=40&utm_source=reddit', '?page=40&fbclid=abc123',
                      '?page=40&gclid=x'):
            with self.subTest(query=query):
                self.assertEqual(self._canonical(query),
                                 '/sharedbuilds/?page=40')

    def test_an_empty_field_filters_nothing(self):
        # the filters are a GET form: submitting it untouched adds an empty field
        for query in ('?page=40&search=', '?page=40&char_class=',
                      '?page=40&tag=%20'):
            with self.subTest(query=query):
                self.assertEqual(self._canonical(query),
                                 '/sharedbuilds/?page=40')

    def test_the_game_version_stays_in_the_address(self):
        """The list is published once per game version; each version's canonical must keep its own prefix."""
        from chardata.shared_builds_view import _canonical_url
        for prefix in ('', '/retro', '/beta', '/dofus2', '/touch'):
            with self.subTest(version=prefix or 'default'):
                request = self.factory.get('%s/sharedbuilds/' % prefix)
                self.assertEqual(_canonical_url(request, _Page(1)),
                                 SITE + prefix + '/sharedbuilds/')
                request = self.factory.get('%s/sharedbuilds/?page=4' % prefix)
                self.assertEqual(_canonical_url(request, _Page(4)),
                                 SITE + prefix + '/sharedbuilds/?page=4')

    def test_the_page_publishes_what_the_view_decided(self):
        # a sentinel value tells the view's canonical apart from base.html's fallback
        sentinel = SITE + '/sharedbuilds/?page=sentinel'
        with mock.patch('chardata.shared_builds_view._canonical_url',
                        return_value=sentinel):
            response = self.client.get('/sharedbuilds/',
                                       HTTP_ACCEPT_LANGUAGE='en')
        self.assertEqual(response.status_code, 200)
        html = response.content.decode('utf-8', 'replace')
        tag = re.search(r'<link[^>]*canonical[^>]*>', html)
        self.assertIsNotNone(tag, 'the page declares no canonical at all')
        self.assertIn(
            'page=sentinel', tag.group(0),
            'the page ignored the view and fell back to request.path: %s'
            % tag.group(0))


class TheEncyclopediaCanonicalTests(TestCase):
    """The same rule, run against the real views since the item catalogue is a file, not the database."""

    NAVIGATEUR = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0'

    CASES = (
        ('/encyclopedia/', '/encyclopedia/'),
        ('/encyclopedia/?page=7', '/encyclopedia/?page=7'),
        ('/encyclopedia/monsters/?page=5', '/encyclopedia/monsters/?page=5'),
        ('/encyclopedia/sets/?page=3', '/encyclopedia/sets/?page=3'),
        ('/encyclopedia/?q=sword&page=2', '/encyclopedia/'),
        ('/encyclopedia/?page=2&utm_source=reddit', '/encyclopedia/?page=2'),
        ('/encyclopedia/?page=2&q=', '/encyclopedia/?page=2'),
    )

    def test_each_address_names_the_expected_canonical(self):
        wrong = []
        for url, expected in self.CASES:
            response = self.client.get(url, HTTP_ACCEPT_LANGUAGE='en',
                                       HTTP_USER_AGENT=self.NAVIGATEUR)
            self.assertEqual(response.status_code, 200, url)
            html = response.content.decode('utf-8', 'replace')
            # the minifier sorts attributes, so href can come before rel
            tag = re.search(r'<link[^>]*canonical[^>]*>', html)
            self.assertIsNotNone(tag, '%s declares no canonical' % url)
            got = re.search(r'href="([^"]*)"', tag.group(0)).group(1)
            if got != SITE + expected:
                wrong.append((url, got.replace(SITE, ''), expected))
        self.assertFalse(
            wrong, 'wrong canonical (address, got, expected): %s' % wrong[:6])
