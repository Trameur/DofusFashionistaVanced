# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The language flags, read as a crawler reads them.

These live outside tests.py because tests.py is long and because the thing
under test is one small contract: the flag that knows where the same page
lives in another language must be a link, and the flag that does not must
stay a focusable button.
"""
import re

from django.test import TestCase

LANGUAGES = ('fr', 'es', 'pt', 'de')

#: Pages whose url names their language, so the view can say where the same
#: page lives in each of the others.
PAGES_WITH_ALTERNATES = (
    '/',
    '/encyclopedia/',
    '/guides/',
    '/encyclopedia/sets/',
    '/encyclopedia/monsters/',
    '/encyclopedia/item/equipment/44-twiggy-sword/',
)

#: Pages that have no localised address to offer. A flag there cannot carry an
#: href, and an <a> without one is neither a link nor reachable by keyboard.
PAGES_WITHOUT_ALTERNATES = ('/setup/', '/support/', '/privacy/')

_ANCHOR = re.compile(r'<a\b[^>]*id="flag-([a-z]{2})"[^>]*>')
_BUTTON = re.compile(r'<button\b[^>]*id="flag-([a-z]{2})"[^>]*>')
_HREF = re.compile(r'href="([^"]*)"')


class LanguageFlagsAreCrawlableLinksTests(TestCase):
    """Every flag was a button that javascript turned into a language switch.

    A button is not a link, so a crawler followed none of them and /fr/, /es/,
    /pt/ and /de/ received no internal link from anywhere on the site. Three of
    the four are submitted in a sitemap of their own; German is left out on
    purpose, for want of an audience, which left hreflang as the only thing
    naming it. The click still posts the form -- the cookie is what makes the
    choice stick -- so the href is there for the crawler and for a reader
    without javascript.
    """

    def _page(self, url):
        response = self.client.get(url, HTTP_ACCEPT_LANGUAGE='en')
        self.assertEqual(response.status_code, 200,
                         '%s answered %s' % (url, response.status_code))
        return response.content.decode('utf-8', 'replace')

    def test_a_page_that_knows_its_alternates_links_to_all_of_them(self):
        for url in PAGES_WITH_ALTERNATES:
            html = self._page(url)
            linked = set(_ANCHOR.findall(html))
            self.assertEqual(
                linked, set(LANGUAGES),
                '%s offers %s as links; the flags that are still buttons are '
                '%s' % (url, sorted(linked), sorted(_BUTTON.findall(html))))

    def test_every_flag_link_answers(self):
        # A crawlable link that 404s is worse than no link: it spends the
        # budget and reports a fault.
        #
        # Counting what was examined is the point of the last assertion here.
        # Without it this test passes on a page with no links at all, which is
        # exactly the state it exists to prevent: it would have been green
        # against the buttons it replaced.
        checked = 0
        broken = []
        for url in PAGES_WITH_ALTERNATES:
            html = self._page(url)
            for tag in re.findall(r'<a\b[^>]*id="flag-[a-z]{2}"[^>]*>', html):
                href = _HREF.search(tag)
                language = re.search(r'id="flag-([a-z]{2})"', tag).group(1)
                if href is None or not href.group(1):
                    broken.append((url, language, '(no href)', '-'))
                    continue
                target = href.group(1)
                checked += 1
                status = self.client.get(target).status_code
                if status != 200:
                    broken.append((url, language, target, status))
        self.assertFalse(broken, 'these flag links do not answer 200: %s'
                         % broken[:6])
        self.assertEqual(
            checked, len(PAGES_WITH_ALTERNATES) * len(LANGUAGES),
            'examined %d flag links over %d pages; expected %d, so some page '
            'is offering fewer flags than it should'
            % (checked, len(PAGES_WITH_ALTERNATES),
               len(PAGES_WITH_ALTERNATES) * len(LANGUAGES)))

    def test_a_page_without_alternates_keeps_a_focusable_button(self):
        # The point of the flags being buttons in the first place was that a
        # keyboard could reach them. An <a> with no href reaches nothing.
        for url in PAGES_WITHOUT_ALTERNATES:
            html = self._page(url)
            self.assertEqual(
                set(_BUTTON.findall(html)), set(LANGUAGES),
                '%s should keep four buttons, it has %s'
                % (url, sorted(_BUTTON.findall(html))))
            self.assertFalse(
                _ANCHOR.findall(html),
                '%s has no alternate url to offer, so a flag there cannot be '
                'a link: %s' % (url, sorted(_ANCHOR.findall(html))))

    def test_german_is_named_by_a_link_because_no_sitemap_carries_it(self):
        # fr, es and pt each have a sitemap; de deliberately has none, so this
        # link is the only thing on the site that names a German page. If the
        # day comes that 'de' joins _SITEMAP_LANGUAGES this test is still true,
        # it just stops being the only path.
        html = self._page('/encyclopedia/item/equipment/44-twiggy-sword/')
        german = [tag for tag in
                  re.findall(r'<a\b[^>]*id="flag-de"[^>]*>', html)]
        self.assertEqual(len(german), 1,
                         'expected one German flag link, found %d' % len(german))
        target = _HREF.search(german[0]).group(1)
        self.assertTrue(target, 'the German flag carries no href')
        self.assertEqual(self.client.get(target).status_code, 200,
                         '%s does not answer' % target)
