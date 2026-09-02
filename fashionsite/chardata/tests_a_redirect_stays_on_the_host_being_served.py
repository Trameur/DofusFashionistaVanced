# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

"""A visitor sent to another language must stay on the host serving them.

The hreflang alternates are absolute and name the production host, because
that is what hreflang requires. The language redirect reused them as its
Location, so a signed-in visitor whose account language differed from the page
was thrown at dofusfashionista.gg whatever host they were on: clicking an item
on a development server left the development server, and the same would happen
on any preview host. The alternates must stay absolute; the redirect must not.
"""

from django.conf import settings
from django.shortcuts import redirect
from django.test import RequestFactory, TestCase

from chardata.url_language import (SITE_URL, redirect_target_for_user,
                                   site_relative)

# Item 44 in two languages, the same pair the neighbouring test file uses.
ALTERNATES = {
    'en': SITE_URL + '/encyclopedia/item/equipment/44-twiggy-sword/',
    'fr': SITE_URL + '/encyclopedia/item/equipment/44-epee-de-boisaille/',
    'es': SITE_URL + '/encyclopedia/item/equipment/44-espada-de-maderucha/',
}


class _SignedInUser(object):
    is_authenticated = True


class _AnonymousUser(object):
    is_authenticated = False


class _Alias(object):
    def __init__(self, language):
        self.language = language


class RedirectStaysOnTheHostBeingServed(TestCase):

    def setUp(self):
        self.factory = RequestFactory()

    def _request(self, path, signed_in_language=None):
        request = self.factory.get(path)
        if signed_in_language is None:
            request.user = _AnonymousUser()
            return request
        request.user = _SignedInUser()
        request.COOKIES[settings.SESSION_COOKIE_NAME] = 'x'
        self._patch_alias(signed_in_language)
        return request

    def _patch_alias(self, language):
        from chardata import url_language

        def fake(request):
            return language
        self._saved = url_language.explicit_user_language
        url_language.explicit_user_language = fake
        self.addCleanup(setattr, url_language, 'explicit_user_language',
                        self._saved)

    def test_the_target_is_a_path_not_an_address_on_another_host(self):
        request = self._request(
            '/encyclopedia/item/equipment/44-espada-de-maderucha/',
            signed_in_language='fr')
        target = redirect_target_for_user(request, 'es', ALTERNATES)
        self.assertIsNotNone(target, msg='this visitor must be redirected, '
                                         'otherwise the test proves nothing')
        self.assertTrue(target.startswith('/'), msg=target)
        self.assertNotIn('://', target)
        self.assertEqual('/encyclopedia/item/equipment/44-epee-de-boisaille/',
                         target)

    def test_the_location_header_carries_no_host(self):
        # What the caller actually sends: the same value handed to redirect().
        request = self._request(
            '/encyclopedia/item/equipment/44-espada-de-maderucha/',
            signed_in_language='fr')
        target = redirect_target_for_user(request, 'es', ALTERNATES)
        location = redirect(target)['Location']
        self.assertNotIn('dofusfashionista.gg', location)
        self.assertTrue(location.startswith('/'), msg=location)

    def test_an_anonymous_visitor_is_still_never_redirected(self):
        # Control: without it, a function returning None for everyone would
        # pass the two tests above by never being exercised.
        request = self._request(
            '/encyclopedia/item/equipment/44-espada-de-maderucha/')
        self.assertIsNone(redirect_target_for_user(request, 'es', ALTERNATES))

    def test_the_alternates_themselves_stay_absolute(self):
        # Control on the other side: hreflang needs the host, and a fix that
        # stripped it there would break indexing instead.
        for lang, url in ALTERNATES.items():
            with self.subTest(lang=lang):
                self.assertTrue(url.startswith('https://'), msg=url)

    def test_site_relative_only_touches_our_own_addresses(self):
        self.assertEqual('/guides/', site_relative(SITE_URL + '/guides/'))
        self.assertEqual('/', site_relative(SITE_URL))
        self.assertEqual('/already/a/path/', site_relative('/already/a/path/'))
        # An address elsewhere is left whole: stripping a host we do not own
        # would turn an outgoing link into an internal one.
        self.assertEqual('https://www.dofus.com/x',
                         site_relative('https://www.dofus.com/x'))
