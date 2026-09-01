# -*- coding: utf-8 -*-
"""A page that says noindex must stay fetchable, or it never leaves the index.

/loadprojects/ is empty unless you sign in, and Google showed it 3 962 times
for 4 clicks over ninety days. The remedy already chosen, and live, is a
`noindex, follow` meta tag -- deliberately NOT a robots.txt disallow. The view's
own docstring says why: "the page is already in the index, and a disallow would
stop Google ever reading the instruction to drop it."

That reasoning was easy to miss, and missing it makes the page permanent. This
walks every disallowed word in robots.txt, asks for it as an anonymous visitor,
and refuses the one combination that traps a page: 200, noindex, disallowed.

A page that answers 404 or a redirect is exempt -- /admin-tools/ sets noindex
and is disallowed, and that is fine, because a crawler never receives its body.
"""
import io
import os
import re

from django.test import Client, SimpleTestCase, TestCase

HERE = os.path.dirname(os.path.abspath(__file__))
ROBOTS = os.path.join(HERE, 'templates', 'chardata', 'robots.txt')


#: Words that serve 200 + noindex and are disallowed anyway, accepted on
#: purpose. All three are auth pages: never in a sitemap, never linked from a
#: public page, so nothing put them in the index for the noindex to get out of.
#: The disallow is what keeps a crawler from spending its budget on them.
#:
#: This list is honest about its limit: I could not verify their index status.
#: `site:` with `inurl:` returns nothing for this domain even for the
#: encyclopedia, which is indexed 43 000 times over -- so the operator, not the
#: index, is what is empty. If one of them ever turns up in a search result,
#: the remedy is the one /loadprojects/ uses: drop the disallow, keep noindex.
ACCEPTED_TRAPPED = frozenset(('check_your_email', 'login', 'login_page'))


def _rules():
    out, inside = [], False
    for line in io.open(ROBOTS, encoding='utf-8').read().splitlines():
        line = line.split('#', 1)[0].strip()
        if not line or ':' not in line:
            continue
        key, value = (p.strip() for p in line.split(':', 1))
        key = key.lower()
        if key == 'user-agent':
            inside = (value == '*')
        elif inside and key in ('allow', 'disallow') and value:
            out.append((key, value))
    return out


def _as_pattern(path):
    anchored = path.endswith('$')
    if anchored:
        path = path[:-1]
    body = ''.join('.*' if c == '*' else re.escape(c) for c in path)
    return re.compile('^' + body + ('$' if anchored else ''))


def _allows(rules, path):
    """Google's rule: longest matching pattern wins, ties go to Allow."""
    winner, length = None, -1
    for key, value in rules:
        if _as_pattern(value).match(path):
            n = len(value)
            if n > length or (n == length and key == 'allow'):
                winner, length = key, n
    return winner != 'disallow'


def _says_noindex(html):
    """Read the tag without assuming attribute order: django-htmlmin sorts
    them, so name= does not come before content=."""
    for tag in re.findall(r'<meta\b[^>]*>', html):
        attrs = dict(re.findall(r'([a-zA-Z-]+)="([^"]*)"', tag))
        if attrs.get('name') == 'robots':
            return 'noindex' in attrs.get('content', '')
    return False


class NoindexNeedsToBeReadable(TestCase):

    def setUp(self):
        self.rules = _rules()
        self.client = Client()

    def _words(self):
        return sorted(
            m.group(1) for key, value in self.rules
            for m in [re.fullmatch(r'\*/([A-Za-z0-9_-]+)/', value)]
            if key == 'disallow' and m)

    def test_the_noindex_reader_can_tell_the_two_apart(self):
        """Without this, every assertion below passes on a blind reader."""
        self.assertTrue(_says_noindex(
            '<meta content="noindex, follow" name="robots">'))
        self.assertFalse(_says_noindex(
            '<meta content="index, follow" name="robots">'))
        self.assertFalse(_says_noindex('<title>no meta at all</title>'))

    def test_the_live_case_is_still_the_shape_the_docstring_describes(self):
        page = self.client.get('/loadprojects/')
        self.assertEqual(page.status_code, 200)
        self.assertTrue(_says_noindex(page.content.decode('utf-8')),
                        '/loadprojects/ lost its noindex')
        self.assertTrue(_allows(self.rules, '/loadprojects/'),
                        'robots.txt now blocks a page that carries noindex: '
                        'Google can no longer read the instruction to drop it')

    def test_no_disallowed_word_serves_a_noindex_body(self):
        trapped = []
        for word in self._words():
            if word in ACCEPTED_TRAPPED:
                continue
            path = '/%s/' % word
            if _allows(self.rules, path):
                continue
            try:
                page = self.client.get(path)
            except Exception:
                continue           # a view that needs arguments is not a page
            if page.status_code != 200:
                continue           # never delivered to a crawler
            if _says_noindex(page.content.decode('utf-8', 'replace')):
                trapped.append(word)
        self.assertEqual(trapped, [])

    def test_the_accepted_ones_are_still_in_that_state(self):
        """A named exception that stopped applying is a stale comment."""
        for word in sorted(ACCEPTED_TRAPPED):
            path = '/%s/' % word
            self.assertFalse(_allows(self.rules, path), path)
            page = self.client.get(path)
            self.assertEqual(page.status_code, 200, path)
            self.assertTrue(_says_noindex(page.content.decode('utf-8')), path)


class RobotsMatcherHasTeeth(SimpleTestCase):

    def test_it_can_say_yes_and_no(self):
        rules = _rules()
        self.assertTrue(_allows(rules, '/encyclopedia/item/equipment/44-x/'))
        self.assertTrue(_allows(rules, '/loadprojects/'))
        self.assertFalse(_allows(rules, '/admin-tools/'))
        self.assertFalse(_allows(rules, '/fr/postcomment/'))
