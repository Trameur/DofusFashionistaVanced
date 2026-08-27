# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""What a paginated list says it is.

Two views answer this with two implementations -- the encyclopedia hubs through
_paginated_canonical, the shared builds through _canonical_url -- and the rule
they must agree on is short: a page of a list is canonical at its own page
number, a filtered view of that list points back at the plain one, and neither
tracking noise nor an empty field counts as a filter.

One file exercising both, so the day one of them drifts the difference is what
fails rather than whichever family happens to have a test.
"""
import re
from unittest import mock

from django.test import RequestFactory, TestCase

SITE = 'https://dofusfashionista.gg'


class _Paginator(object):
    def __init__(self, num_pages):
        self.num_pages = num_pages


class _Page(object):
    """Enough of a Paginator page for a canonical to be built from it.

    The test database holds no shared builds, so asking the real view for
    page 40 gets a one-page list and a canonical that is right for that list
    and says nothing about the rule. The rule is checked here on its own.
    """

    def __init__(self, number, num_pages=83):
        self.number = number
        self.paginator = _Paginator(num_pages)


class TheSharedBuildsCanonicalTests(TestCase):
    """Every page of /sharedbuilds/ named /sharedbuilds/ as its canonical.

    The template published none of its own, and the fallback in base.html is
    built from request.path, which carries no query string. So 82 of the 83
    pages asked to be indexed and declared themselves duplicates of the first
    in the same breath -- and the builds that appear only on those pages are
    reached through them.
    """

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
        # A link shared on Reddit arrives with utm_source. Counting it would
        # make the shared page declare itself a duplicate of the first one,
        # which is exactly the page the visitor was not sent to.
        for query in ('?page=40&utm_source=reddit', '?page=40&fbclid=abc123',
                      '?page=40&gclid=x'):
            with self.subTest(query=query):
                self.assertEqual(self._canonical(query),
                                 '/sharedbuilds/?page=40')

    def test_an_empty_field_filters_nothing(self):
        # The filters are a GET form: submitting it untouched produces
        # ?search= and the same builds in the same order.
        for query in ('?page=40&search=', '?page=40&char_class=',
                      '?page=40&tag=%20'):
            with self.subTest(query=query):
                self.assertEqual(self._canonical(query),
                                 '/sharedbuilds/?page=40')

    def test_the_game_version_stays_in_the_address(self):
        """The list is published once per game version and all five are
        submitted. Writing /sharedbuilds/ down instead of reading the path made
        /retro/, /beta/, /dofus2/ and /touch/ name the default version as their
        canonical -- four submitted pages disowning themselves. Caught by
        EverySubmittedPageIsItsOwnCanonicalTest, kept here as well so the rule
        fails where it is written and not only where it is observed.
        """
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
        # The rule being right proves nothing about the page: the template has
        # to print it. A sentinel is the only way to tell the new block apart
        # from the fallback base.html would have produced anyway.
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
    """The same rule, on the family that already had it.

    These run against the real views because the item catalogue is a file and
    is there in a test run, unlike the shared builds, which live in the
    database.
    """

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
            # The minifier sorts attributes, so href can come before rel:
            # matching the whole tag and then its href survives that.
            tag = re.search(r'<link[^>]*canonical[^>]*>', html)
            self.assertIsNotNone(tag, '%s declares no canonical' % url)
            got = re.search(r'href="([^"]*)"', tag.group(0)).group(1)
            if got != SITE + expected:
                wrong.append((url, got.replace(SITE, ''), expected))
        self.assertFalse(
            wrong, 'wrong canonical (address, got, expected): %s' % wrong[:6])
