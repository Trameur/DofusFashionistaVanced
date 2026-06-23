# Copyright (C) 2020 The Dofus Fashionista
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

"""Smoke + regression tests for the chardata app.

Run with:
    PYTHONPATH="$PWD;$PWD/fashionistapulp" python fashionsite/manage.py test chardata

Intentionally lightweight: they guard the regressions that have actually bitten
this project (soft-404s served as 200, broken/untranslated UI strings) without
coupling to exact page copy.
"""

from django.test import SimpleTestCase, TestCase, override_settings
import re

from django.utils import translation
from django.utils.translation import gettext


class TranslationRegressionTests(SimpleTestCase):
    """Guards the i18n fixes (fuzzy/empty strings) across fr/es/pt/de.

    A fuzzy or empty .po entry is ignored by Django and silently falls back to
    English, so these assert the *translated* output is actually served.
    """

    def test_charged_n_times_fr(self):
        # Were fuzzy ("Chargée deux fois") for every count -> fixed to "N fois".
        with translation.override('fr'):
            self.assertEqual(gettext('Charged 3 times'), 'Chargée 3 fois')
            self.assertEqual(gettext('Charged 12 times'), 'Chargée 12 fois')

    def test_german_mp_is_bp_not_member_of_parliament(self):
        # Regression: DE "MP" had been mistranslated as "Abgeordneter" (= a
        # member of parliament). Movement Points must read "BP".
        with translation.override('de'):
            self.assertEqual(gettext('MP'), 'BP')

    def test_steals_mp_translated_per_language(self):
        expected = {'fr': 'Vole 3 PM', 'es': 'Roba 3 PM',
                    'pt': 'Rouba 3 PM', 'de': 'Stiehlt 3 BP'}
        for lang, exp in expected.items():
            with translation.override(lang):
                self.assertEqual(gettext('Steals %(mp)d MP') % {'mp': 3}, exp,
                                 msg='Steals MP wrong for %s' % lang)

    def test_previously_untranslated_ui_strings(self):
        expected = {
            'Hunting Weapon': {'fr': 'Arme de chasse', 'es': 'Arma de caza',
                               'pt': 'Arma de caça', 'de': 'Jagdwaffe'},
            'Linked to the character': {'fr': 'Lié au personnage',
                                        'es': 'Vinculado al personaje',
                                        'pt': 'Vinculado ao personagem',
                                        'de': 'Mit dem Charakter verknüpft'},
        }
        for msgid, per_lang in expected.items():
            for lang, exp in per_lang.items():
                with translation.override(lang):
                    self.assertEqual(gettext(msgid), exp,
                                     msg='%r wrong for %s' % (msgid, lang))


# Use the plain (non-manifest) static storage so template {% static %} calls do
# not require a collectstatic manifest during tests (settings uses the manifest
# storage when DEBUG is False, which the test runner forces).
@override_settings(
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    }
)
class PublicRouteSmokeTests(TestCase):
    """Key public routes resolve and return the expected status codes."""

    def test_public_pages_ok(self):
        for path in ['/', '/about/', '/faq/', '/privacy/', '/support/',
                     '/license/', '/encyclopedia/', '/sharedbuilds/',
                     '/quickstart/', '/smartbuild/', '/forgemagie/',
                     '/offline/', '/robots.txt', '/manifest.webmanifest',
                     '/sw.js', '/ads.txt']:
            with self.subTest(path=path):
                resp = self.client.get(path)
                self.assertEqual(resp.status_code, 200,
                                 msg='%s -> %s' % (path, resp.status_code))

    def test_unknown_url_returns_real_404(self):
        # AdSense "low value content" regression: unknown URLs must be 404,
        # not a soft-200 error page.
        resp = self.client.get('/this-page-does-not-exist-xyz123/')
        self.assertEqual(resp.status_code, 404)

    def test_sitemap_is_well_formed_xml(self):
        resp = self.client.get('/sitemap.xml')
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode('utf-8', 'replace')
        self.assertIn('<?xml', body)
        self.assertIn('<urlset', body)
        self.assertIn('/privacy/', body)


@override_settings(
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    }
)
class CanonicalUrlTests(TestCase):
    """Version-prefixed info pages (/retro/about/ …) are duplicates of the global
    pages, so they must canonicalize to the global URL; version-specific pages keep
    a self-referential canonical."""

    def _canonical(self, path):
        resp = self.client.get(path)
        self.assertEqual(resp.status_code, 200, msg='%s -> %s' % (path, resp.status_code))
        html = resp.content.decode('utf-8', 'replace')
        # Tolerant of HTML minification (htmlmin strips attribute quotes when DEBUG=False)
        # and of attribute ordering within the <link> tag.
        tag = re.search(r'<link[^>]*\brel=["\']?canonical["\']?[^>]*>', html)
        self.assertIsNotNone(tag, msg='no canonical tag on %s' % path)
        href = re.search(r'\bhref=["\']?([^"\'\s>]+)', tag.group(0))
        self.assertIsNotNone(href, msg='no href in canonical tag on %s' % path)
        return href.group(1)

    def test_global_info_page_is_self_canonical(self):
        self.assertEqual(self._canonical('/about/'),
                         'https://dofusfashionista.gg/about/')

    def test_version_prefixed_info_pages_canonical_to_global(self):
        self.assertEqual(self._canonical('/retro/about/'),
                         'https://dofusfashionista.gg/about/')
        self.assertEqual(self._canonical('/beta/faq/'),
                         'https://dofusfashionista.gg/faq/')
        self.assertEqual(self._canonical('/dofus2/privacy/'),
                         'https://dofusfashionista.gg/privacy/')

    def test_version_specific_page_keeps_self_canonical(self):
        # The version IS meaningful content here, so canonical stays self-referential.
        self.assertEqual(self._canonical('/retro/'),
                         'https://dofusfashionista.gg/retro/')


class RegistrationTests(TestCase):
    """Username uniqueness must be case-insensitive (MySQL's unique index is), so a
    case-only variant is detected as taken instead of 500ing later in create_user."""

    def test_check_username_is_case_insensitive(self):
        from django.contrib.auth.models import User
        User.objects.create_user('Egabesta', 'egabesta@example.com', 'x')
        taken = self.client.post('/check_username/', {'username': 'egabesta'})
        self.assertContains(taken, 'username-error')
        free = self.client.post('/check_username/', {'username': 'totally-new-name'})
        self.assertContains(free, 'ok')


class SocialAuthCancelTests(TestCase):
    """Cancelling the Google OAuth consent (AuthCanceled) must redirect to login,
    not raise a 500 + admin error email."""

    def test_auth_canceled_redirects_to_login(self):
        from django.test import RequestFactory
        from social_core.exceptions import AuthCanceled
        from chardata.SocialAuthExceptionMiddleware import SocialAuthExceptionMiddleware
        mw = SocialAuthExceptionMiddleware(lambda r: None)
        resp = mw.process_exception(
            RequestFactory().get('/complete/google-oauth2/'),
            AuthCanceled('google-oauth2'))
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/login', resp['Location'])


class PasswordResetTests(TestCase):
    """Completing a password reset must also activate the account, so a user who
    never confirmed their email isn't locked out forever (reset works but login
    rejects inactive accounts)."""

    def test_reset_activates_inactive_account(self):
        from django.contrib.auth.models import User
        from chardata.login_view import _generate_token_for_password_reset
        u = User.objects.create_user('vida', 'vida@example.com', 'oldhash')
        u.is_active = False
        u.save()
        token = _generate_token_for_password_reset('vida', u.password)
        self.client.post('/do_recover_password/vida/%s/' % token,
                         {'new_password': 'newpass', 'confirm_password': 'newpass'})
        u.refresh_from_db()
        self.assertTrue(u.is_active)


class ProjectActionRobustnessTests(TestCase):
    """POST-only project endpoints must not 500 when hit by a bare GET (bots/crawlers).
    Regression: /deleteprojects/ did json.loads(None) -> TypeError -> 500."""

    def test_delete_projects_get_does_not_500(self):
        resp = self.client.get('/deleteprojects/')
        self.assertNotEqual(resp.status_code, 500)

    def test_duplicate_project_get_does_not_500(self):
        resp = self.client.get('/duplicateproject/')
        self.assertNotEqual(resp.status_code, 500)
