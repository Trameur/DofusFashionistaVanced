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

    def test_touch_set_bonus_condition_shows_lt_2(self):
        # Touch trophies cap at 1 set bonus, so their condition line must read
        # "< 2"; dofus3/beta stay "< 3". Guards both the cap logic and the i18n.
        from chardata.solution_result import LightSetConditionLine
        with translation.override('fr'):
            self.assertEqual(LightSetConditionLine(None, 1).text, 'Bonus de panoplies < 2')
            self.assertEqual(LightSetConditionLine(None, 2).text, 'Bonus de panoplies < 3')

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

    def test_removes_ap_translated_per_language(self):
        # Weapon "removes N AP" hit line (e.g. Worn Koulosse Staff on Touch).
        expected = {'fr': 'Retire 3 PA', 'es': 'Quita 3 PA',
                    'pt': 'Remove 3 PA', 'de': 'Entzieht 3 AP'}
        for lang, exp in expected.items():
            with translation.override(lang):
                self.assertEqual(gettext('Removes %(ap)d AP') % {'ap': 3}, exp,
                                 msg='Removes AP wrong for %s' % lang)

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


class StructureSetResolutionTests(SimpleTestCase):
    """get_set_by_id must return the real (bonus-bearing) set, not a synthetic touch
    set sharing its id. id 1 is the dofus3 "Gobball Set" (sets_dict, has bonuses) and
    also the touch "Jellix Set" (dt_sets_dict, no bonuses); checking dt first showed
    Gobball builds as "Jellix Set" with no set bonus."""

    def test_get_set_by_id_prefers_real_bonus_set(self):
        from fashionistapulp.structure import get_structure
        s = get_structure()
        got = s.get_set_by_id(1)
        self.assertIs(got, s.sets_dict.get(1))
        self.assertTrue(got.bonus, 'set 1 should expose its bonuses')


class BreadcrumbJsonLdTests(SimpleTestCase):
    """The breadcrumb JSON-LD is embedded in a <script> via |safe, so it must escape
    characters that could break out of the tag (defense-in-depth)."""

    def test_escapes_script_breakout(self):
        import json
        from chardata.encyclopedia_view import _breadcrumb_jsonld
        out = _breadcrumb_jsonld([('a</script><img src=x>', 'https://x/')])
        self.assertNotIn('</script>', out)
        self.assertNotIn('<img', out)
        self.assertIn('\\u003c', out)
        self.assertEqual(json.loads(out)['itemListElement'][0]['name'],
                         'a</script><img src=x>')


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

    def test_compare_cart_injected_in_base(self):
        # The comparison cart (add a build from anywhere, compare in one click)
        # is injected site-wide: header cart container, i18n config, script.
        resp = self.client.get('/encyclopedia/')
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertIn('id="compare-cart"', html)
        self.assertIn('id="compare-cart-panel"', html)
        self.assertIn('COMPARE_TRAY_CONFIG', html)
        self.assertIn('compare_tray.js', html)

    def test_non_retro_item_hides_pet_feeding_section(self):
        # Regression: a belt (e.g. Belteen) carries a second entry at id
        # 100M + ankama_id; the Retro pet-feeding logic mislabelled its stats as
        # "Possible bonuses (when fed)". That section must not show outside Retro.
        from fashionistapulp.structure import get_structure
        structure = get_structure()
        target = next((it for it in structure.get_concatenated_items_lists()
                       if it.id >= 100000000 and it.ankama_id and it.ankama_type),
                      None)
        if target is None:
            self.skipTest('no high-id duplicate variant in current data')
        resp = self.client.get('/encyclopedia/item/%s/%s-x/'
                               % (target.ankama_type, target.ankama_id))
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('when fed', resp.content.decode())

    def test_unknown_url_returns_real_404(self):
        # AdSense "low value content" regression: unknown URLs must be 404,
        # not a soft-200 error page.
        resp = self.client.get('/this-page-does-not-exist-xyz123/')
        self.assertEqual(resp.status_code, 404)

    def test_encyclopedia_item_shows_set_bonuses(self):
        # The item page now surfaces the panoply's per-piece bonuses (the set_bonus
        # data was loaded but only the set NAME was shown before).
        from fashionistapulp.structure import get_structure
        s = get_structure()
        target = None
        for iset in s.sets_dict.values():
            if getattr(iset, 'bonus', None) and getattr(iset, 'items', None):
                for iid in iset.items:
                    it = s.get_item_by_id(iid)
                    # The view resolves the set from the item's own .set (sets_dict
                    # first), so only items whose .set lands on a bonus set qualify.
                    if (it and getattr(it, 'ankama_type', None)
                            and getattr(it, 'ankama_id', None)
                            and getattr(it, 'set', None) is not None
                            and getattr(s.sets_dict.get(it.set), 'bonus', None)):
                        target = it
                        break
            if target:
                break
        self.assertIsNotNone(target, 'no set item found in the structure')
        resp = self.client.get('/encyclopedia/item/%s/%s-x/'
                               % (target.ankama_type, target.ankama_id))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Set bonuses')

    def test_gobball_set_item_shows_dofus3_set_name_not_touch(self):
        # Regression: set id 1 is the dofus3 "Gobball Set" (with bonuses) AND, in
        # dt_sets_dict, the touch "Jellix Set". get_set_by_id() checks dt first, so
        # Gobball items wrongly showed "Jellix Set" and no bonuses.
        from fashionistapulp.structure import get_structure
        s = get_structure()
        gob = next((v for v in s.sets_dict.values()
                    if v.localized_names.get('en') == 'Gobball Set'
                    and getattr(v, 'bonus', None) and getattr(v, 'items', None)), None)
        if not gob:
            self.skipTest('Gobball Set not present in the structure')
        it = None
        for iid in gob.items:
            cand = s.get_item_by_id(iid)
            if cand and getattr(cand, 'set', None) is not None and s.sets_dict.get(cand.set) is gob:
                it = cand
                break
        if not it:
            self.skipTest('no Gobball item with a consistent back-link')
        resp = self.client.get('/encyclopedia/item/%s/%s-x/' % (it.ankama_type, it.ankama_id))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Gobball Set')
        self.assertNotContains(resp, 'Jellix Set')
        self.assertContains(resp, 'property="og:image"')  # item-specific social preview

    def test_encyclopedia_sets_list_page_ok(self):
        resp = self.client.get('/encyclopedia/sets/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Sets')

    def test_encyclopedia_set_detail_shows_items_and_bonuses(self):
        from fashionistapulp.structure import get_structure
        s = get_structure()
        target_id = None
        for sid, iset in s.sets_dict.items():
            if (getattr(iset, 'bonus', None) and getattr(iset, 'items', None)
                    and any(s.get_item_by_id(i) and getattr(s.get_item_by_id(i), 'ankama_id', None)
                            for i in iset.items)):
                target_id = sid
                break
        self.assertIsNotNone(target_id, 'no bonus set with items found')
        resp = self.client.get('/encyclopedia/set/%s/' % target_id)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Set bonuses')
        self.assertContains(resp, '/encyclopedia/item/')  # at least one item links out
        self.assertContains(resp, 'property="og:image"')  # set-specific social preview
        self.assertContains(resp, 'BreadcrumbList')  # breadcrumb structured data

    def test_encyclopedia_item_has_valid_breadcrumb_jsonld(self):
        import json
        from fashionistapulp.structure import get_structure
        s = get_structure()
        it = None
        for iset in s.sets_dict.values():
            if getattr(iset, 'bonus', None) and getattr(iset, 'items', None):
                for iid in iset.items:
                    cand = s.get_item_by_id(iid)
                    if (cand and getattr(cand, 'ankama_id', None)
                            and getattr(cand, 'ankama_type', None)):
                        it = cand
                        break
            if it:
                break
        self.assertIsNotNone(it, 'no renderable set item found')
        resp = self.client.get('/encyclopedia/item/%s/%s-x/' % (it.ankama_type, it.ankama_id))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode('utf-8', 'replace')
        m = re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
        self.assertIsNotNone(m, 'no ld+json script on the item page')
        data = json.loads(m.group(1))  # raises if the JSON-LD is malformed
        self.assertEqual(data['@type'], 'BreadcrumbList')
        self.assertGreaterEqual(len(data['itemListElement']), 2)

    def test_encyclopedia_unknown_set_redirects_to_encyclopedia(self):
        resp = self.client.get('/encyclopedia/set/99999999/')
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/encyclopedia', resp['Location'])

    def test_encyclopedia_list_card_links_to_set(self):
        # Items in a panoply now expose a link to their set page from the list card.
        resp = self.client.get('/encyclopedia/?q=gobball')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '/encyclopedia/set/')

    def test_sitemap_is_well_formed_xml(self):
        resp = self.client.get('/sitemap.xml')
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode('utf-8', 'replace')
        self.assertIn('<?xml', body)
        self.assertIn('<urlset', body)
        self.assertIn('/privacy/', body)
        # Global encyclopedia is listed; version-prefixed encyclopedia URLs are not
        # (they canonicalize to the global one). Version-specific pages still are.
        self.assertIn('https://dofusfashionista.gg/encyclopedia/', body)
        self.assertNotIn('/retro/encyclopedia/', body)
        self.assertIn('/retro/forgemagie/', body)

    def test_manifest_has_pwa_install_icons(self):
        import json
        resp = self.client.get('/manifest.webmanifest')
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content.decode('utf-8'))
        sizes = {icon.get('sizes') for icon in data.get('icons', [])}
        self.assertIn('192x192', sizes)  # Chrome needs a >=192px PNG for the install prompt
        self.assertIn('512x512', sizes)
        self.assertTrue(all(icon.get('type') == 'image/png' for icon in data['icons']))

    def test_apple_touch_icon_present(self):
        # iOS "add to home screen" uses apple-touch-icon (not the manifest).
        resp = self.client.get('/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'apple-touch-icon')


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

    def test_version_prefixed_encyclopedia_pages_canonical_to_global(self):
        # The encyclopedia is dofus3 data under every prefix, so /retro/encyclopedia/...
        # etc. are duplicates and must canonicalize to the global URL.
        self.assertEqual(self._canonical('/retro/encyclopedia/'),
                         'https://dofusfashionista.gg/encyclopedia/')
        self.assertEqual(self._canonical('/beta/encyclopedia/sets/'),
                         'https://dofusfashionista.gg/encyclopedia/sets/')
        self.assertEqual(self._canonical('/touch/encyclopedia/set/1/'),
                         'https://dofusfashionista.gg/encyclopedia/set/1/')
        # Item pages canonicalize to the global dofus3 item URL (prefix dropped).
        from fashionistapulp.structure import get_structure
        s = get_structure()
        it = None
        for iset in s.sets_dict.values():
            if getattr(iset, 'bonus', None) and getattr(iset, 'items', None):
                for iid in iset.items:
                    cand = s.get_item_by_id(iid)
                    if (cand and getattr(cand, 'ankama_id', None)
                            and getattr(cand, 'ankama_type', None)):
                        it = cand
                        break
            if it:
                break
        self.assertIsNotNone(it, 'no renderable set item found')
        canon = self._canonical('/dofus2/encyclopedia/item/%s/%s-x/'
                                % (it.ankama_type, it.ankama_id))
        self.assertTrue(canon.startswith('https://dofusfashionista.gg/encyclopedia/item/'),
                        msg=canon)
        self.assertNotIn('/dofus2/', canon)


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

    def test_auth_missing_parameter_redirects_to_login(self):
        # Bots/stale redirects hit /complete/ without the state param -> AuthMissingParameter.
        # Must redirect to login, not 500 + email admins.
        from django.test import RequestFactory
        from social_core.exceptions import AuthMissingParameter
        from chardata.SocialAuthExceptionMiddleware import SocialAuthExceptionMiddleware
        mw = SocialAuthExceptionMiddleware(lambda r: None)
        resp = mw.process_exception(
            RequestFactory().get('/complete/google-oauth2/'),
            AuthMissingParameter('google-oauth2', 'state'))
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

    def test_choose_compare_sets_post_get_does_not_500(self):
        resp = self.client.get('/choose_compare_sets_post/')
        self.assertNotEqual(resp.status_code, 500)

    def test_wizard_post_get_does_not_500(self):
        # Regression: /wizardpost/<id>/ did safe_int('') -> None -> min(12, None)
        # -> TypeError -> 500 on a bare GET.
        resp = self.client.get('/wizardpost/1/')
        self.assertNotEqual(resp.status_code, 500)

    def test_set_min_stats_tolerates_none_caps(self):
        # Regression (prod /wizardpost/): a char whose *stored* AP/MP/Range min is
        # None reaches set_min_stats -> min(12, None) -> TypeError. The earlier
        # safe_int guard only covered POSTed fields, not the char's stored mins.
        import pickle
        from chardata.min_stats import set_min_stats

        class _FakeChar:
            def save(self):
                pass

        char = _FakeChar()
        set_min_stats(char, {'AP': None, 'MP': None, 'Range': None, 'Vitality': 50})
        self.assertEqual(pickle.loads(char.minimum_stats)['Vitality'], 50)

        capped = _FakeChar()
        set_min_stats(capped, {'AP': 99, 'MP': 99, 'Range': 99})
        stored = pickle.loads(capped.minimum_stats)
        self.assertEqual((stored['AP'], stored['MP'], stored['Range']), (12, 6, 6))

    def test_compare_sets_skips_missing_builds(self):
        # Regression: a build removed after being added to the comparison cart
        # made the whole /compare_sets/ page raise. Stale ids are now skipped;
        # with fewer than two left it's a clean 404, never a 500.
        resp = self.client.get('/compare_sets/99999999/88888888/')
        self.assertEqual(resp.status_code, 404)


class SharedBuildCompareIdTests(TestCase):
    """Regression: a *shared* build added to the comparison cart must carry the
    's' prefix on its encoded id. Commit 496a717e shipped it without the prefix,
    so the cart stored the bare encoded blob and /compare_sets/ then did
    int('<base64>') -> ValueError. The templates that emit the cart id for
    shared builds rely on the contract guarded here:
      - solution.html      data-build-id="s{{ encoded_char_id }}"
      - shared_builds.html data-build-id="s{{ build.encoded_id }}"
    i.e. 's' + encode_char_id(id) must round-trip back to the shared char, and
    the bare encoded form must not be accepted as a build id.
    """

    def _make_shared_char(self, link_shared=True):
        from chardata.models import Char
        return Char.objects.create(
            name='Shared build', char_name='hero', char_class='Iop',
            char_build='build', level=200,
            minimum_stats=b'', minimum_crits=b'', stats_weight=b'',
            options=b'', inclusions=b'', exclusions=b'',
            link_shared=link_shared, game_version='dofus3')

    def test_s_prefixed_encoded_id_round_trips_to_char(self):
        from chardata.encoded_char_id import encode_char_id
        from chardata.util import get_char_id_possibly_encoded
        char = self._make_shared_char()
        char_id, was_encoded = get_char_id_possibly_encoded('s' + encode_char_id(char.id))
        self.assertEqual(char_id, char.id)
        self.assertTrue(was_encoded)

    def test_bare_encoded_id_is_rejected_as_int(self):
        # The exact symptom of the missing-prefix bug: without 's', the encoded
        # blob is handed to int() -> ValueError. The 's' prefix is mandatory.
        from chardata.encoded_char_id import encode_char_id
        from chardata.util import get_char_id_possibly_encoded
        char = self._make_shared_char()
        with self.assertRaises(ValueError):
            get_char_id_possibly_encoded(encode_char_id(char.id))

    def test_get_char_possibly_encoded_returns_shared_char(self):
        from django.contrib.auth.models import AnonymousUser
        from django.test import RequestFactory
        from chardata.encoded_char_id import encode_char_id
        from chardata.util import get_char_possibly_encoded_or_raise
        char = self._make_shared_char()
        req = RequestFactory().get('/')
        req.user = AnonymousUser()
        resolved = get_char_possibly_encoded_or_raise(req, 's' + encode_char_id(char.id))
        self.assertEqual(resolved.pk, char.pk)

    def test_unshared_char_via_share_link_is_denied(self):
        # A build that isn't shared must not be reachable through the 's' link.
        from django.contrib.auth.models import AnonymousUser
        from django.core.exceptions import PermissionDenied
        from django.test import RequestFactory
        from chardata.encoded_char_id import encode_char_id
        from chardata.util import get_char_possibly_encoded_or_raise
        char = self._make_shared_char(link_shared=False)
        req = RequestFactory().get('/')
        req.user = AnonymousUser()
        with self.assertRaises(PermissionDenied):
            get_char_possibly_encoded_or_raise(req, 's' + encode_char_id(char.id))


class StaticStorageRegressionTests(SimpleTestCase):
    """Guards the encyclopedia 500: under the production ManifestStaticFilesStorage
    a {% static %} reference to an asset that wasn't collected (a single missing
    item icon -- 'Mister Penguin Chain') raised ValueError and 500'd the whole
    listing. The lenient storage must degrade a missing asset to a URL, not raise.
    """

    @override_settings(STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'fashionsite.storage.LenientManifestStaticFilesStorage'},
    })
    def test_missing_asset_degrades_to_url(self):
        from django.contrib.staticfiles.storage import staticfiles_storage
        # Not in the manifest and not on disk: must return a (unhashed) URL
        # instead of raising ValueError.
        url = staticfiles_storage.url('chardata/definitely-missing-xyz.png')
        self.assertIn('definitely-missing-xyz.png', url)


class RateLimitedErrorFilterTests(SimpleTestCase):
    """The mail_admins rate-limiter must dedupe duplicate errors but never
    suppress an email because of its own failure -- a cache hiccup must not make
    us blind to production errors (prod went 3 days without a single error mail).
    """

    def test_dedupes_same_signature_once_per_window(self):
        import logging
        from unittest import mock
        from chardata.log_filters import RateLimitedErrorFilter
        rec = logging.makeLogRecord({'msg': 'boom'})
        store = {}
        with mock.patch('chardata.log_filters.cache.get', side_effect=store.get), \
             mock.patch('chardata.log_filters.cache.set',
                        side_effect=lambda k, v, t: store.__setitem__(k, v)):
            f = RateLimitedErrorFilter()
            self.assertTrue(f.filter(rec))    # first occurrence -> send
            self.assertFalse(f.filter(rec))   # duplicate within window -> suppressed

    def test_fails_open_on_cache_error(self):
        import logging
        from unittest import mock
        from chardata.log_filters import RateLimitedErrorFilter
        rec = logging.makeLogRecord({'msg': 'boom'})
        with mock.patch('chardata.log_filters.cache.get',
                        side_effect=Exception('cache down')):
            self.assertTrue(RateLimitedErrorFilter().filter(rec))
