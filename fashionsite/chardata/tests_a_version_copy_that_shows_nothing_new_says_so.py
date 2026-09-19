# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A version-prefixed copy that shows nothing new is canonical to the global page."""
import re

from django.test import TestCase

SITE = 'https://dofusfashionista.gg'
VERSIONS = ('dofus3', 'beta', 'dofus2', 'touch', 'retro')
PREFIX = {'dofus3': '', 'beta': '/beta', 'dofus2': '/dofus2',
          'touch': '/touch', 'retro': '/retro'}

# Public pages only, logged-in ones are noindex
FAMILIES = ('/about/', '/faq/', '/license/', '/support/', '/contact/',
            '/login_page/', '/smartbuild/', '/quickstart/')

# Body without the header and footer, both name the version
_BODY = re.compile(r'id="main-content"(.*?)class="footer"', re.S)
_TAG = re.compile(r'<[^>]+>')
_LINK = re.compile(r'<link\b[^>]*>', re.I)
_ATTR = {name: re.compile(r'\b%s="([^"]*)"' % name, re.I)
         for name in ('rel', 'href')}

# CSRF token, new on every request
_CSRF = re.compile(r'\b[A-Za-z0-9]{64}\b')


def _attr(tag, name):
    found = _ATTR[name].search(tag)
    return found.group(1) if found else None


def _canonical_of(html):
    for tag in _LINK.findall(html):
        if _attr(tag, 'rel') == 'canonical':
            return _attr(tag, 'href')
    return None


def _read_body(html):
    found = _BODY.search(html)
    return ' '.join(_TAG.sub(' ', found.group(1) if found else html).split())


def _body_of(html):
    return _CSRF.sub('<csrf>', _read_body(html))


class AVersionCopySaysWhetherItShowsAnythingNewTests(TestCase):

    def _page(self, path):
        answer = self.client.get(path, HTTP_ACCEPT_LANGUAGE='en')
        self.assertEqual(answer.status_code, 200, path)
        return answer.content.decode('utf-8', 'replace')

    def _read(self, family):
        bodies, canonicals = {}, {}
        for version in VERSIONS:
            html = self._page(PREFIX[version] + family)
            bodies[version] = _body_of(html)
            canonicals[version] = _canonical_of(html)
        return bodies, canonicals

    def test_the_two_cuts_are_what_make_a_copy_comparable(self):
        """Footer and CSRF token are cut before comparing."""
        page = self._page('/retro/about/')
        self.assertIn('Items up to', page,
                      'the footer no longer names the game version')
        self.assertNotIn('Items up to', _body_of(page),
                         'the footer is still inside the body')
        self.assertGreater(len(_body_of(page)), 400)

        raw = [_read_body(self._page(path))
               for path in ('/login_page/', '/retro/login_page/')]
        self.assertNotEqual(raw[0], raw[1],
                            'the csrf token no longer varies per request')
        self.assertEqual(_CSRF.sub('<csrf>', raw[0]),
                         _CSRF.sub('<csrf>', raw[1]))

    def test_each_family_answers_the_question_it_is_asked(self):
        identical, different = [], []
        for family in FAMILIES:
            bodies, canonicals = self._read(family)
            same = all(bodies[version] == bodies['dofus3']
                       for version in VERSIONS)
            (identical if same else different).append(family)
            for version in VERSIONS[1:]:
                own = SITE + PREFIX[version] + family
                free = SITE + family
                with self.subTest(family=family, version=version):
                    if same:
                        self.assertEqual(
                            free, canonicals[version],
                            '%s%s shows nothing the global page does not, so '
                            'it must not claim to be its own page'
                            % (PREFIX[version], family))
                    else:
                        self.assertEqual(
                            own, canonicals[version],
                            '%s%s shows something else, so it is its own page'
                            % (PREFIX[version], family))
        self.assertGreaterEqual(len(identical), 5, identical)
        self.assertGreaterEqual(len(different), 1, different)

    def test_quickstart_is_the_family_that_shows_something_else(self):
        bodies, canonicals = self._read('/quickstart/')
        self.assertNotEqual(bodies['dofus3'], bodies['retro'])
        missing = [name for name in ('Eliotrope', 'Foggernaut', 'Forgelance',
                                     'Huppermage', 'Masqueraider', 'Ouginak',
                                     'Rogue')
                   if name in bodies['dofus3'] and name not in bodies['retro']]
        self.assertEqual(7, len(missing), missing)
        self.assertEqual(SITE + '/retro/quickstart/', canonicals['retro'])

    def test_a_copy_that_disclaims_itself_publishes_no_hreflang(self):
        """A page canonical elsewhere is in no hreflang group."""
        html = self._page('/retro/contact/')
        self.assertEqual(SITE + '/contact/', _canonical_of(html))
        self.assertNotIn('hreflang=', html)
        global_page = self._page('/contact/')
        self.assertIn('hreflang=', global_page)
