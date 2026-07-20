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

When MySQL lacks CREATE-DATABASE rights, use a local (gitignored)
fashionsite/fashionsite/settings_test.py and add --settings=fashionsite.settings_test:

    from fashionsite.settings import *  # noqa: F401,F403
    STORAGES = {
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    }
    DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}}
    # Shell probes with these settings must never email real error reports
    # (the test runner swaps to locmem itself; `manage.py shell` does not).
    EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
    ADMINS = []

Intentionally lightweight: they guard the regressions that have actually bitten
this project (soft-404s served as 200, broken/untranslated UI strings) without
coupling to exact page copy.
"""

from django.test import SimpleTestCase, TestCase, override_settings
import glob
import os
import re
import shutil
import subprocess
import unittest

from django.utils import translation
from django.utils.translation import gettext


class PoFileFormatTests(SimpleTestCase):
    """The docker build runs compilemessages, whose msgfmt --check-format
    rejects e.g. a bare % in a msgstr whose msgid uses %%. That exact mistake
    broke a production deploy; catch it locally instead."""

    @unittest.skipIf(shutil.which('msgfmt') is None, 'msgfmt not installed')
    def test_every_po_passes_msgfmt_check_format(self):
        locale_dir = os.path.join(os.path.dirname(__file__), '..', 'locale')
        po_files = glob.glob(os.path.join(locale_dir, '*', 'LC_MESSAGES', '*.po'))
        self.assertTrue(po_files, msg='no .po files found')
        for po in po_files:
            with self.subTest(po=os.path.relpath(po, locale_dir)):
                proc = subprocess.run(
                    ['msgfmt', '--check-format', '-o', os.devnull, po],
                    capture_output=True, text=True)
                self.assertEqual(proc.returncode, 0, msg=proc.stderr[:2000])


class OfficialSiteUrlTests(SimpleTestCase):
    """Internal encyclopedia URLs should stay readable for localized names."""

    def test_internal_links_transliterate_accented_names(self):
        from chardata.official_site import (
            get_item_link,
            get_monster_link,
            get_resource_link,
            get_set_link,
        )
        self.assertEqual(
            get_item_link('equipment', 999, "Épée d'Âme"),
            '/encyclopedia/item/equipment/999-epee-d-ame/')
        self.assertEqual(
            get_resource_link('resources', 395, 'Trèfle à 5 feuilles', 'retro'),
            '/retro/encyclopedia/resource/resources/395-trefle-a-5-feuilles/')
        self.assertEqual(
            get_monster_link(123, 'Jalató Real', 'retro'),
            '/retro/encyclopedia/monster/123-jalato-real/')
        self.assertEqual(
            get_set_link(321, 'Panoplie du Bouftou Royal', 'retro'),
            '/retro/encyclopedia/set/321-panoplie-du-bouftou-royal/')


class EmailTemplateTranslationTests(SimpleTestCase):
    """Email templates render server-side in the recipient's language and are
    never seen during normal dev, so a blocktrans whose text drifts from its .po
    msgid falls back to English silently (removing a dash from the comment mail
    template without resyncing the catalog did exactly that). Read the committed
    .po, not the compiled .mo, so the drift is caught before a deploy hits it."""

    LANGS = ('fr', 'es', 'pt', 'de')

    @staticmethod
    def _blocktrans_msgids(text):
        # Only the plain {% blocktrans %}...{% endblocktrans %} form (none of the
        # email templates use the with/count/trimmed variants).
        blocks = re.findall(
            r'\{%\s*blocktrans\s*%\}(.*?)\{%\s*endblocktrans\s*%\}', text, re.DOTALL)
        return [re.sub(r'\{\{\s*(\w+)\s*\}\}', r'%(\1)s', b) for b in blocks]

    def test_email_blocktrans_are_translated(self):
        try:
            import polib
        except ImportError:
            self.skipTest('polib not installed')
        email_dir = os.path.join(
            os.path.dirname(__file__), 'templates', 'chardata', 'emails')
        templates = glob.glob(os.path.join(email_dir, '*'))
        self.assertTrue(templates, msg='no email templates found')
        catalogs = {}
        for lang in self.LANGS:
            path = os.path.join(os.path.dirname(__file__), '..', 'locale',
                                lang, 'LC_MESSAGES', 'django.po')
            catalogs[lang] = {e.msgid: e for e in polib.pofile(path)
                              if not e.obsolete}
        for tpl in templates:
            with open(tpl, encoding='utf-8') as fh:
                text = fh.read()
            for msgid in self._blocktrans_msgids(text):
                for lang in self.LANGS:
                    entry = catalogs[lang].get(msgid)
                    self.assertIsNotNone(entry, msg=(
                        '%s: blocktrans has no active %s msgid, so it falls back '
                        'to English. Resync the .po with the template: %r'
                        % (os.path.basename(tpl), lang, msgid[:90])))
                    self.assertTrue(entry.msgstr.strip(), msg=(
                        '%s: %s translation is empty for %r'
                        % (os.path.basename(tpl), lang, msgid[:90])))


class BrandNameCatalogTests(SimpleTestCase):
    """Branding rule: "The Dofus Fashionista" in English only; every other
    language uses "Dofus Fashionista" (no "The"). The title check can't see
    strings like the transactional emails, where the German catalog still
    carried "The Dofus Fashionista"; scan the catalogs directly."""

    NON_ENGLISH = ('fr', 'es', 'pt', 'de')

    def test_no_the_dofus_fashionista_in_non_english_catalogs(self):
        try:
            import polib
        except ImportError:
            self.skipTest('polib not installed')
        locale_dir = os.path.join(os.path.dirname(__file__), '..', 'locale')
        for lang in self.NON_ENGLISH:
            for po_path in glob.glob(os.path.join(
                    locale_dir, lang, 'LC_MESSAGES', '*.po')):
                po = polib.pofile(po_path)
                offenders = [e.msgid[:60] for e in po
                             if not e.obsolete and e.msgstr
                             and 'The Dofus Fashionista' in e.msgstr]
                with self.subTest(po=os.path.relpath(po_path, locale_dir)):
                    self.assertEqual(offenders, [], msg=(
                        '%s: %d msgstr still say "The Dofus Fashionista"; the '
                        'brand must drop "The" outside English. Offenders: %s'
                        % (lang, len(offenders), offenders)))

    def test_brand_fashionista_is_capitalized(self):
        # The brand keeps a capital F everywhere ("Dofus Fashionista"). A French
        # password-reset email had shipped "Dofus fashionista".
        try:
            import polib
        except ImportError:
            self.skipTest('polib not installed')
        locale_dir = os.path.join(os.path.dirname(__file__), '..', 'locale')
        for po_path in glob.glob(os.path.join(
                locale_dir, '*', 'LC_MESSAGES', '*.po')):
            po = polib.pofile(po_path)
            offenders = [e.msgid[:60] for e in po
                         if not e.obsolete and e.msgstr
                         and re.search(r'[Dd]ofus fashionista', e.msgstr)]
            with self.subTest(po=os.path.relpath(po_path, locale_dir)):
                self.assertEqual(offenders, [], msg=(
                    '%s: brand must be "Dofus Fashionista" (capital F). '
                    'Offenders: %s' % (po_path, offenders)))


class TranslationRegressionTests(SimpleTestCase):
    """Guards the i18n fixes (fuzzy/empty strings) across fr/es/pt/de.

    A fuzzy or empty .po entry is ignored by Django and silently falls back to
    English, so these assert the *translated* output is actually served.
    """

    def test_charged_n_times_fr(self):
        # French keeps the digit: "Chargée 3 fois", not a spelled-out count.
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

    def test_setup_links_the_class_guide(self):
        # The class dropdown is where the "which class?" question actually
        # happens: the setup page must link the class guide there, localized.
        resp = self.client.get('/setup/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'href="/guides/choosing-your-class/"')
        with translation.override('fr'):
            expected = translation.gettext(
                'Not sure which class to pick? Read the guide')
        self.assertNotEqual(
            expected, 'Not sure which class to pick? Read the guide',
            'fr catalog entry missing')
        resp = self.client.get('/setup/', HTTP_ACCEPT_LANGUAGE='fr')
        self.assertContains(resp, expected)

    def test_search_finds_resources(self):
        import sqlite3
        from fashionistapulp.fashionista_config import get_items_db_path
        for version, prefix in (('dofus3', ''), ('beta', '/beta'),
                                ('touch', '/touch'), ('retro', '/retro'),
                                ('dofus2', '/dofus2')):
            with self.subTest(version=version):
                conn = sqlite3.connect(get_items_db_path(version))
                row = conn.execute(
                    "SELECT name FROM item_recipe_ingredient_names "
                    "WHERE language = 'en' AND ingredient_subtype = 'resources' "
                    "ORDER BY ingredient_ankama_id LIMIT 1").fetchone()
                conn.close()
                self.assertIsNotNone(row, 'no resource ingredient for ' + version)
                resp = self.client.get('%s/encyclopedia/' % prefix, {'q': row[0]})
                self.assertEqual(resp.status_code, 200)
                self.assertContains(resp, 'encyclopedia-resource-hit')
                self.assertContains(resp, '%s/encyclopedia/resource/' % prefix)

    def test_search_family_nav_links_each_result_family(self):
        # Multi-family searches get an anchored count bar above the results;
        # plain browsing (no query) never shows it.
        resp = self.client.get('/retro/encyclopedia/', {'q': 'bouftou'},
                               HTTP_ACCEPT_LANGUAGE='fr')
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode('utf-8')
        self.assertIn('class="encyclopedia-family-nav"', body)
        for anchor in ('#resources-results', '#monsters-results',
                       '#items-results'):
            self.assertIn('href="%s"' % anchor, body)
        for section_id in ('id="resources-results"', 'id="monsters-results"',
                           'id="items-results"'):
            self.assertIn(section_id, body)
        resp = self.client.get('/encyclopedia/')
        self.assertNotIn('class="encyclopedia-family-nav"',
                         resp.content.decode('utf-8'))

    def test_search_totals_are_real_not_capped(self):
        from chardata import encyclopedia_view as ev

        # A one-letter needle matches far more than the display cap: the
        # total must say so while the page entries stay capped.
        entries, total = ev._search_resources('retro', 'e', 'en')
        self.assertLessEqual(len(entries), 48)
        self.assertGreater(total, 12)
        self.assertGreaterEqual(total, len(entries))

        # Rendered: the section header carries the real total, and the chips
        # beyond the first 12 fold behind a details block.
        needle = ev._normalized_text('bouftou')
        _entries, res_total = ev._search_resources('retro', needle, 'fr')
        resp = self.client.get('/retro/encyclopedia/', {'q': 'bouftou'},
                               HTTP_ACCEPT_LANGUAGE='fr')
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode('utf-8')
        m = re.search(r'id="resources-results">[^<]*?(\d+)<', body)
        self.assertIsNotNone(m, 'resources header missing')
        self.assertEqual(int(m.group(1)), res_total)
        if res_total > 12:
            self.assertIn('class="encyclopedia-hits-more"', body)

    def test_resource_search_reuses_cached_index_per_version(self):
        import sqlite3
        from chardata import encyclopedia_view
        from fashionistapulp.fashionista_config import get_items_db_path

        conn = sqlite3.connect(get_items_db_path('retro'))
        row = conn.execute(
            "SELECT name FROM item_recipe_ingredient_names "
            "WHERE language = 'en' AND ingredient_subtype = 'resources' "
            "ORDER BY ingredient_ankama_id LIMIT 1").fetchone()
        conn.close()
        self.assertIsNotNone(row, 'no resource ingredient for retro')

        encyclopedia_view._resource_search_index_cache.clear()
        try:
            with unittest.mock.patch.object(encyclopedia_view.sqlite3, 'connect',
                                           wraps=sqlite3.connect) as connect_mock:
                needle = encyclopedia_view._normalized_text(row[0])
                self.assertTrue(encyclopedia_view._search_resources('retro', needle, 'en')[0])
                self.assertTrue(encyclopedia_view._search_resources('retro', needle, 'fr')[0])
                self.assertEqual(connect_mock.call_count, 1)
        finally:
            encyclopedia_view._resource_search_index_cache.clear()

    def test_item_light_index_reuses_language_neutral_core(self):
        from chardata import encyclopedia_view
        from fashionistapulp.structure import get_structure

        structure = get_structure('dofus3')
        encyclopedia_view._light_core_cache.clear()
        encyclopedia_view._light_index_cache.clear()
        try:
            first = encyclopedia_view._get_light_index(structure, 'en')
            self.assertTrue(first)
            with unittest.mock.patch.object(
                    encyclopedia_view, '_collect_unique_items',
                    side_effect=AssertionError('rebuilt item core')):
                second = encyclopedia_view._get_light_index(structure, 'fr')
            self.assertEqual(len(first), len(second))
            self.assertEqual(first[0]['search_blob'], second[0]['search_blob'])
        finally:
            encyclopedia_view._light_core_cache.clear()
            encyclopedia_view._light_index_cache.clear()

    def test_item_page_renders_translated_dynamic_stats(self):
        # The runtime-translated data strings (dynamic_translations) must
        # actually render localized: Sulik carries the 'Reflects' stat. The
        # expected text comes from the catalog, never hardcoded.
        from django.utils import translation
        with translation.override('fr'):
            expected = translation.gettext('Reflects')
        self.assertNotEqual(expected, 'Reflects',
                            'the Reflects stat has no fr translation')
        resp = self.client.get('/encyclopedia/item/equipment/6988-x/',
                               headers={'accept-language': 'fr'})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, expected)

    def test_no_items_notice_hidden_when_other_families_match(self):
        import sqlite3
        from fashionistapulp.fashionista_config import get_items_db_path
        from chardata.encyclopedia_view import LOCALIZED_UI
        conn = sqlite3.connect(get_items_db_path('dofus3'))
        row = conn.execute(
            "SELECT name FROM monster_names WHERE language = 'en' "
            "ORDER BY monster_ankama_id LIMIT 1").fetchone()
        resource_row = conn.execute(
            """
            SELECT rn.name
            FROM item_recipe_ingredient_names rn
            WHERE rn.language = 'en'
              AND rn.ingredient_subtype = 'resources'
              AND NOT EXISTS (
                  SELECT 1 FROM item_names i
                  WHERE i.language = 'en'
                    AND (
                        lower(i.name) LIKE '%' || lower(rn.name) || '%'
                        OR lower(rn.name) LIKE '%' || lower(i.name) || '%'
                    )
              )
            ORDER BY rn.ingredient_ankama_id
            LIMIT 1
            """).fetchone()
        conn.close()
        self.assertIsNotNone(row, 'no monster name found')
        self.assertIsNotNone(resource_row, 'no resource-only name found')
        # A monster-only query: chips shown, and the misleading "no items
        # match your filters" notice must stay hidden.
        resp = self.client.get('/encyclopedia/', {'q': row[0]})
        self.assertContains(resp, '/encyclopedia/monster/')
        self.assertNotContains(resp, LOCALIZED_UI['en']['no_results'])
        # Same contract for a resource-only query.
        resp = self.client.get('/encyclopedia/', {'q': resource_row[0]})
        self.assertContains(resp, '/encyclopedia/resource/')
        self.assertNotContains(resp, LOCALIZED_UI['en']['no_results'])
        # A query matching nothing at all keeps the notice.
        resp = self.client.get('/encyclopedia/', {'q': 'zzzznothingmatchesthis'})
        self.assertContains(resp, LOCALIZED_UI['en']['no_results'])

    def test_encyclopedia_hub_does_not_search_other_families_without_query(self):
        resp = self.client.get('/encyclopedia/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['resource_results'], [])
        self.assertEqual(resp.context['monster_results'], [])

    def test_item_page_links_other_versions(self):
        # Twiggy Sword (44) exists on dofus3, dofus2 and retro but not touch:
        # the "Also in" block cross-links only the versions that carry the
        # item (unlike the global version switcher, which links blindly).
        resp = self.client.get('/encyclopedia/item/equipment/44-x/')
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode('utf-8')
        m = re.search(
            r'encyclopedia-other-versions.*?</div>', body, re.S)
        self.assertIsNotNone(m, 'Also in block missing')
        block = m.group(0)
        self.assertIn('/retro/encyclopedia/item/equipment/44-', block)
        self.assertIn('/dofus2/encyclopedia/item/equipment/44-', block)
        self.assertNotIn('/touch/', block)
        # And the retro page links back to dofus3 (unprefixed URL).
        resp = self.client.get('/retro/encyclopedia/item/equipment/44-x/')
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode('utf-8')
        m = re.search(r'encyclopedia-other-versions.*?</div>', body, re.S)
        self.assertIsNotNone(m)
        self.assertIn('"/encyclopedia/item/equipment/44-', m.group(0))

    def test_resource_page_links_other_versions(self):
        # Sesame Seed (resources/287) is a craft ingredient in every version:
        # the "Also in" block must cross-link them all.
        resp = self.client.get('/encyclopedia/resource/resources/287-x/')
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode('utf-8')
        m = re.search(r'encyclopedia-other-versions.*?</div>', body, re.S)
        self.assertIsNotNone(m, 'Also in block missing')
        block = m.group(0)
        for prefix in ('/retro', '/dofus2', '/touch', '/beta'):
            self.assertIn('%s/encyclopedia/resource/resources/287-' % prefix,
                          block)
        # Strawberry (resources/381) is only used by dofus3-era recipes:
        # no touch/retro link even though the global switcher lists them.
        resp = self.client.get('/encyclopedia/resource/resources/381-x/')
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode('utf-8')
        m = re.search(r'encyclopedia-other-versions.*?</div>', body, re.S)
        self.assertIsNotNone(m, 'Also in block missing')
        block = m.group(0)
        self.assertNotIn('/touch/', block)
        self.assertNotIn('/retro/', block)
        # And the retro page links back to dofus3 (unprefixed URL).
        resp = self.client.get('/retro/encyclopedia/resource/resources/287-x/')
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode('utf-8')
        m = re.search(r'encyclopedia-other-versions.*?</div>', body, re.S)
        self.assertIsNotNone(m)
        self.assertIn('"/encyclopedia/resource/resources/287-', m.group(0))

    def test_search_finds_monsters(self):
        import sqlite3
        from fashionistapulp.fashionista_config import get_items_db_path
        for version, prefix in (('dofus3', ''), ('beta', '/beta'),
                                ('touch', '/touch'), ('retro', '/retro'),
                                ('dofus2', '/dofus2')):
            with self.subTest(version=version):
                conn = sqlite3.connect(get_items_db_path(version))
                row = conn.execute(
                    "SELECT name FROM monster_names WHERE language = 'en' "
                    "ORDER BY monster_ankama_id LIMIT 1").fetchone()
                conn.close()
                self.assertIsNotNone(row, 'no monster for ' + version)
                resp = self.client.get('%s/encyclopedia/' % prefix, {'q': row[0]})
                self.assertEqual(resp.status_code, 200)
                self.assertContains(resp, '%s/encyclopedia/monster/' % prefix)

    def test_monster_search_prioritizes_names_across_languages(self):
        from chardata import encyclopedia_view

        with unittest.mock.patch.object(
                encyclopedia_view,
                '_get_monster_index',
                return_value=[
                    {
                        'name': 'Found through a drop',
                        'search_blob': 'blue resource',
                        'name_aliases': ['gobball'],
                        'url': '/drop-match/',
                    },
                    {
                        'name': 'Larve Bleue',
                        'search_blob': 'blue larva larve bleue',
                        'name_aliases': ['blue larva', 'larve bleue'],
                        'url': '/name-match/',
                    },
                ]):
            hits, _total = encyclopedia_view._search_monsters(
                'dofus3', encyclopedia_view._normalized_text('blue'), 'fr', limit=3)

        self.assertEqual([hit['url'] for hit in hits],
                         ['/name-match/', '/drop-match/'])

    def test_resource_page_shows_the_ingredient_icon(self):
        import sqlite3
        from fashionistapulp.fashionista_config import get_items_db_path
        for version, prefix, icon_dir in (
                ('dofus3', '', 'resources/60x60'),
                ('touch', '/touch', 'resources/touch/60x60'),
                ('retro', '/retro', 'resources/retro/60x60'),
                ('dofus2', '/dofus2', 'resources/dofus2/60x60')):
            with self.subTest(version=version):
                conn = sqlite3.connect(get_items_db_path(version))
                row = conn.execute(
                    "SELECT ingredient_ankama_id, ingredient_subtype "
                    "FROM item_recipe_ingredient_names WHERE language = 'en' "
                    "ORDER BY ingredient_ankama_id LIMIT 1").fetchone()
                conn.close()
                self.assertIsNotNone(row, 'no recipe ingredients for ' + version)
                ankama_id, subtype = row
                resp = self.client.get('%s/encyclopedia/resource/%s/%d-x/'
                                       % (prefix, subtype, ankama_id))
                self.assertEqual(resp.status_code, 200)
                self.assertContains(resp, '%s/%d-60-60.png' % (icon_dir, ankama_id))

    def test_encyclopedia_item_icons_use_the_current_version(self):
        import sqlite3
        from chardata import encyclopedia_view
        from fashionistapulp.fashionista_config import get_items_db_path

        real_get_image_url = encyclopedia_view.get_image_url
        seen_versions = []

        def tracking_get_image_url(type_name, item_name, game_version=None):
            seen_versions.append(game_version)
            return real_get_image_url(type_name, item_name, game_version)

        structure = encyclopedia_view.get_structure('retro')
        representative_item = next(
            item for item in structure.get_concatenated_items_lists()
            if getattr(item, 'ankama_id', None) and not getattr(item, 'removed', False))
        representative_set = next(
            item_set for item_set in structure.sets_dict.values()
            if getattr(item_set, 'items', None))

        conn = sqlite3.connect(get_items_db_path('retro'))
        try:
            resource_row = conn.execute(
                "SELECT ingredient_ankama_id, ingredient_subtype "
                "FROM item_recipe_ingredient_names WHERE language = 'en' "
                "ORDER BY ingredient_ankama_id LIMIT 1").fetchone()
            monster_row = conn.execute(
                "SELECT monster_ankama_id FROM item_drops "
                "ORDER BY monster_ankama_id LIMIT 1").fetchone()
        finally:
            conn.close()
        self.assertIsNotNone(resource_row)
        self.assertIsNotNone(monster_row)

        item_url = encyclopedia_view.get_item_link(
            representative_item.ankama_type,
            representative_item.ankama_id,
            representative_item.name,
            game_version='retro')
        resource_url = '/retro/encyclopedia/resource/%s/%d-x/' % (
            resource_row[1], resource_row[0])
        monster_url = '/retro/encyclopedia/monster/%d-x/' % monster_row[0]

        with unittest.mock.patch.object(
                encyclopedia_view, 'get_image_url',
                side_effect=tracking_get_image_url):
            for path in ('/retro/encyclopedia/', item_url, resource_url, monster_url):
                with self.subTest(path=path):
                    resp = self.client.get(path)
                    self.assertEqual(resp.status_code, 200)
            encyclopedia_view._get_set_items(
                structure, representative_set, 'en', 'retro')

        self.assertTrue(seen_versions)
        self.assertEqual(set(seen_versions), {'retro'})

    def test_public_pages_ok(self):
        for path in ['/', '/about/', '/faq/', '/privacy/', '/support/',
                     '/license/', '/encyclopedia/', '/sharedbuilds/',
                     '/quickstart/', '/smartbuild/', '/forgemagie/',
                     '/guides/', '/guides/getting-started/',
                     '/guides/how-it-works/', '/guides/stats-explained/',
                     '/guides/game-modes/', '/guides/reading-an-item/',
                     '/guides/understanding-your-solution/',
                     '/guides/tuning-your-weights/',
                     '/guides/forgemagie-planning/',
                     '/guides/mono-vs-multi-element/', '/guides/gearing-up/',
                     '/guides/crafting-and-professions/',
                     '/guides/comparing-builds/', '/guides/versions-explained/',
                     '/offline/', '/robots.txt', '/manifest.webmanifest',
                     '/sw.js', '/ads.txt']:
            with self.subTest(path=path):
                resp = self.client.get(path)
                self.assertEqual(resp.status_code, 200,
                                 msg='%s -> %s' % (path, resp.status_code))

    def test_brand_name_localized_in_title(self):
        # Branding: "The Dofus Fashionista" in English, "Dofus Fashionista"
        # (no "The") in the other languages.
        cases = {'en': 'The Dofus Fashionista:', 'fr': 'Dofus Fashionista :',
                 'de': 'Dofus Fashionista:'}
        for path in ('/faq/', '/encyclopedia/', '/guides/'):
            for lang in cases:
                with self.subTest(path=path, lang=lang):
                    resp = self.client.get(path, headers={'accept-language': lang})
                    self.assertEqual(resp.status_code, 200)
                    title = re.search(r'<title>([^<]*)</title>',
                                      resp.content.decode('utf-8')).group(1)
                    if lang == 'en':
                        self.assertIn('The Dofus Fashionista', title)
                    else:
                        self.assertNotIn('The Dofus Fashionista', title)
                        self.assertIn('Dofus Fashionista', title)

    def test_smart_build_understands_a_german_query(self):
        # POST a German description (no confirm) -> the view echoes the parsed
        # class, proving the German keywords work end to end (view + template),
        # not just in the parser unit tests. "Halsabschneider" is the German
        # class name for Rogue.
        resp = self.client.post('/smartbuild/', {'q': 'Halsabschneider Stufe 150 Luft'})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Rogue')

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

    def test_service_worker_stays_network_first(self):
        # The sw must keep navigations network-first, otherwise users get stuck
        # on a stale cached site after a deploy.
        resp = self.client.get('/sw.js')
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode('utf-8')
        self.assertIn("req.mode === 'navigate'", body)
        self.assertIn('fetch(req).catch', body)

    def test_js_catalog_serves_translations(self):
        # The popups translate through gettext() from /jsi18n/; guard that the
        # catalog actually carries the chardata djangojs entries.
        resp = self.client.get('/jsi18n/', headers={'accept-language': 'fr'})
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode('utf-8')
        self.assertIn('Fermer', body)

    def test_security_headers_sent(self):
        # SecurityMiddleware has to be installed for nosniff and referrer-policy
        # to actually go out.
        resp = self.client.get('/')
        self.assertEqual(resp.headers.get('X-Content-Type-Options'), 'nosniff')
        self.assertEqual(resp.headers.get('Referrer-Policy'), 'same-origin')

    def test_home_website_jsonld_valid(self):
        # Sitelinks searchbox: the home page carries WebSite+SearchAction
        # JSON-LD pointing at the encyclopedia search.
        import json
        resp = self.client.get('/')
        html = resp.content.decode('utf-8')
        m = re.search(r'<script type="application/ld\+json">\s*(\{.*?"@type":\s*"WebSite".*?\})\s*</script>',
                      html, re.S)
        self.assertIsNotNone(m, 'WebSite JSON-LD missing on home')
        data = json.loads(m.group(1))
        self.assertEqual(data['potentialAction']['@type'], 'SearchAction')
        self.assertIn('/encyclopedia/?q=', data['potentialAction']['target']['urlTemplate'])

    def test_default_og_image_present(self):
        # Links shared on discord/twitter need a preview image; item/set pages
        # have their own, everything else falls back to the wide brand card
        # (1200x630, summary_large_image).
        for path in ['/', '/guides/getting-started/', '/smartbuild/']:
            with self.subTest(path=path):
                resp = self.client.get(path)
                self.assertContains(resp, 'property="og:image"')
                self.assertContains(resp, 'og-card.jpg')
                self.assertContains(resp, 'summary_large_image')
        import os
        card = os.path.join(os.path.dirname(__file__), 'static', 'chardata', 'og-card.jpg')
        self.assertTrue(os.path.exists(card), 'og-card.jpg missing from static')

    def test_404_page_is_translated(self):
        # The error page is user-visible in every language; the fr heading had
        # silently shipped in english. The expected text comes from the
        # catalog so a translation rewording cannot silently break the test
        # (a de rewording once left main red for a whole tick).
        from django.utils import translation
        msgid = '404 - Page Not Found'
        for lang in ('fr', 'es', 'de'):
            with self.subTest(lang=lang):
                with translation.override(lang):
                    needle = translation.gettext(msgid)
                self.assertNotEqual(needle, msgid,
                                    'the 404 heading has no %s translation' % lang)
                resp = self.client.get('/this-page-does-not-exist-xyz123/',
                                       headers={'accept-language': lang})
                self.assertEqual(resp.status_code, 404)
                self.assertIn(needle, resp.content.decode('utf-8'))

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

    def test_encyclopedia_title_carries_brand(self):
        resp = self.client.get('/encyclopedia/')
        title = re.search(r'<title>([^<]*)</title>',
                          resp.content.decode('utf-8')).group(1)
        self.assertIn('Dofus Fashionista', title)

    def test_craft_line_shows_the_profession(self):
        # Twiggy Sword is a Smith recipe.
        resp = self.client.get('/encyclopedia/item/equipment/44-x/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Crafted by')
        self.assertContains(resp, 'Smith')

    def test_base_job_recipes_hide_the_craft_line(self):
        # Musamune is a "Base" (job 1) recipe: a special workbench craft no
        # player profession can learn, so no "Crafted by" line.
        resp = self.client.get('/encyclopedia/item/equipment/23590-x/')
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, 'Crafted by')

    def test_encyclopedia_search_filters_results(self):
        # The WebSite SearchAction points google at /encyclopedia/?q=...; the
        # search must actually filter (a broken filter would surface directly
        # in the sitelinks searchbox). Count result cards via their item links
        # (the changelog modal on every page mentions item names, so plain
        # substring checks are unreliable).
        resp = self.client.get('/encyclopedia/', {'q': 'Gelano'})
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode('utf-8')
        hits = html.count('/encyclopedia/item/')
        self.assertGreater(hits, 0, 'narrow search returned no result cards')
        self.assertLess(hits, 40, 'narrow search rendered the whole catalog')

    def test_encyclopedia_search_matches_item_names_from_other_languages(self):
        from chardata.encyclopedia_view import _normalized_text
        from fashionistapulp.structure import get_structure
        structure = get_structure('dofus3')
        query = None
        for item in structure.get_concatenated_items_lists():
            if not getattr(item, 'ankama_id', None) or getattr(item, 'removed', False):
                continue
            english_name = structure.get_item_name_in_language(item, 'en')
            french_name = structure.get_item_name_in_language(item, 'fr')
            current_blob = _normalized_text('%s %s' % (english_name, item.or_name))
            if french_name and english_name and _normalized_text(french_name) not in current_blob:
                query = french_name
                break
        if query is None:
            self.skipTest('no cross-language item name found in this build')

        resp = self.client.get('/encyclopedia/', {'q': query}, HTTP_ACCEPT_LANGUAGE='en')
        self.assertEqual(resp.status_code, 200)
        hits = resp.content.decode('utf-8').count('/encyclopedia/item/')
        self.assertGreater(hits, 0, 'cross-language item search returned no result cards')

    def test_encyclopedia_search_no_result_is_clean(self):
        resp = self.client.get('/encyclopedia/', {'q': 'zzzznotanitemzzzz'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content.decode('utf-8').count('/encyclopedia/item/'), 0)

    def test_encyclopedia_sets_list_page_ok(self):
        resp = self.client.get('/encyclopedia/sets/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Sets')

    def test_encyclopedia_sets_search_matches_item_names_across_languages(self):
        from chardata.encyclopedia_view import _normalized_text
        from fashionistapulp.structure import get_structure
        s = get_structure('dofus3')
        target = None
        for sid, iset in s.sets_dict.items():
            if not getattr(iset, 'items', None):
                continue
            set_blob = _normalized_text('%s %s' % (
                iset.localized_names.get('en') or iset.name,
                iset.name))
            for item_id in iset.items:
                item = s.get_item_by_id(item_id)
                if item is None:
                    continue
                french_name = s.get_item_name_in_language(item, 'fr')
                if french_name and _normalized_text(french_name) not in set_blob:
                    target = (sid, french_name)
                    break
            if target is not None:
                break
        if target is None:
            self.skipTest('no set item with a distinct French name found')

        set_id, query = target
        resp = self.client.get('/encyclopedia/sets/', {'q': query}, HTTP_ACCEPT_LANGUAGE='en')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Search a set or item')
        self.assertContains(resp, 'Items:')
        self.assertRegex(resp.content.decode('utf-8', 'replace'),
                         r'/encyclopedia/set/%s-[^"]+/' % set_id)

    def test_encyclopedia_set_detail_shows_items_and_bonuses(self):
        from chardata.official_site import get_set_link
        from fashionistapulp.structure import get_structure
        s = get_structure()
        target_id = None
        target_name = None
        for sid, iset in s.sets_dict.items():
            if (getattr(iset, 'bonus', None) and getattr(iset, 'items', None)
                    and any(s.get_item_by_id(i) and getattr(s.get_item_by_id(i), 'ankama_id', None)
                            for i in iset.items)):
                target_id = sid
                target_name = iset.localized_names.get('en') or iset.name
                break
        self.assertIsNotNone(target_id, 'no bonus set with items found')
        set_url = get_set_link(target_id, target_name)
        resp = self.client.get(set_url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Set bonuses')
        self.assertContains(resp, '/encyclopedia/item/')  # at least one item links out
        self.assertContains(resp, 'property="og:image"')  # set-specific social preview
        self.assertContains(resp, 'BreadcrumbList')  # breadcrumb structured data
        legacy_resp = self.client.get('/encyclopedia/set/%s/' % target_id)
        self.assertEqual(legacy_resp.status_code, 200)
        self.assertContains(legacy_resp, 'https://dofusfashionista.gg%s' % set_url)

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

    def test_encyclopedia_pages_show_visible_breadcrumbs(self):
        # The JSON-LD breadcrumb exists for robots; humans get the same trail.
        from fashionistapulp.structure import get_structure
        s = get_structure()
        it = next(i for i in s.get_concatenated_items_lists()
                  if getattr(i, 'ankama_id', None) and getattr(i, 'ankama_type', None))
        set_id = next(sid for sid, iset in s.sets_dict.items() if iset.bonus)
        for url in ('/encyclopedia/item/%s/%s-x/' % (it.ankama_type, it.ankama_id),
                    '/encyclopedia/set/%d/' % set_id,
                    '/encyclopedia/sets/'):
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 200, url)
            self.assertContains(resp, 'encyclopedia-crumbs', msg_prefix=url)
            self.assertContains(resp, 'aria-label="Breadcrumb"', msg_prefix=url)

    def test_encyclopedia_unknown_set_is_a_real_404_with_useful_page(self):
        # Pruned/unknown sets and items must answer 404 (so search engines
        # drop them) while still giving humans a clear way back.
        resp = self.client.get('/encyclopedia/set/99999999/')
        self.assertEqual(resp.status_code, 404)
        self.assertContains(resp, '/encyclopedia/', status_code=404)

        resp = self.client.get('/encyclopedia/item/equipment/99999999-gone/',
                               HTTP_ACCEPT_LANGUAGE='en')
        self.assertEqual(resp.status_code, 404)
        self.assertContains(resp, 'Item unavailable in this version', status_code=404)
        self.assertContains(resp, 'does not exist in the Dofus 3 encyclopedia',
                            status_code=404)
        self.assertContains(resp, '/encyclopedia/', status_code=404)

    def test_missing_versioned_item_has_graceful_localized_404(self):
        from chardata.official_site import get_item_link
        from fashionistapulp.structure import get_structure

        modern = get_structure('dofus3')
        retro = get_structure('retro')
        retro_keys = {
            ((item.ankama_type or '').strip().lower(), item.ankama_id)
            for item in retro.get_concatenated_items_lists()
            if getattr(item, 'ankama_id', None)
        }
        candidate = None
        for item in modern.get_concatenated_items_lists():
            key = ((item.ankama_type or '').strip().lower(), item.ankama_id)
            if (getattr(item, 'ankama_id', None)
                    and getattr(item, 'ankama_type', None)
                    and key not in retro_keys):
                candidate = item
                break
        if candidate is None:
            self.skipTest('no Dofus 3 item missing from Retro data')

        name = modern.get_item_name_in_language(candidate, 'fr') or candidate.name
        url = get_item_link(candidate.ankama_type, candidate.ankama_id, name,
                            game_version='retro')
        resp = self.client.get(url, HTTP_ACCEPT_LANGUAGE='fr')
        self.assertEqual(resp.status_code, 404)
        self.assertContains(resp, name, status_code=404)
        from chardata.encyclopedia_view import LOCALIZED_UI
        fr_fragment = LOCALIZED_UI['fr']['missing_item_message'].split('%(version)s')[0].split('%(name)s')[1]
        self.assertContains(resp, fr_fragment.strip(),
                            status_code=404)
        self.assertContains(resp, '/retro/encyclopedia/', status_code=404)
        self.assertContains(resp, LOCALIZED_UI['fr']['missing_back_to_encyclopedia'],
                            status_code=404)

    def test_encyclopedia_list_card_links_to_set(self):
        # Items in a panoply now expose a link to their set page from the list card.
        resp = self.client.get('/encyclopedia/?q=gobball')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '/encyclopedia/set/')

    def test_encyclopedia_hub_copy_mentions_versioned_monsters_and_drops(self):
        resp = self.client.get('/retro/encyclopedia/', HTTP_ACCEPT_LANGUAGE='fr')
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode('utf-8', 'replace')
        self.assertIn('panoplies, monstres et drops de cette version', body)

    def test_sitemap_has_no_redirecting_urls(self):
        # /random/ always 302s to a random shared build; redirect targets do
        # not belong in a sitemap.
        resp = self.client.get('/sitemap.xml')
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('/random/', resp.content.decode('utf-8'))

    def test_sitemap_is_well_formed_xml(self):
        resp = self.client.get('/sitemap.xml')
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode('utf-8', 'replace')
        self.assertIn('<?xml', body)
        self.assertIn('<urlset', body)
        self.assertIn('/privacy/', body)
        # Global and version-specific encyclopedia hubs are all canonical because
        # each game version has distinct data and calculations.
        self.assertIn('https://dofusfashionista.gg/encyclopedia/', body)
        self.assertIn('https://dofusfashionista.gg/retro/encyclopedia/</loc>', body)
        self.assertIn('https://dofusfashionista.gg/retro/encyclopedia/sets/', body)
        self.assertIn('/retro/forgemagie/', body)
        # Original guide content is listed (hub + at least one article).
        self.assertIn('https://dofusfashionista.gg/guides/', body)
        self.assertIn('/guides/getting-started/', body)

    def test_sitemap_lists_monster_encyclopedia_urls(self):
        body = self.client.get('/sitemap.xml').content.decode('utf-8')
        self.assertIn('https://dofusfashionista.gg/encyclopedia/monsters/', body)
        self.assertIn('https://dofusfashionista.gg/retro/encyclopedia/monsters/', body)
        self.assertIn('https://dofusfashionista.gg/retro/encyclopedia/monster/101-', body)

    def test_sitemap_lists_versioned_resource_urls(self):
        body = self.client.get('/sitemap.xml').content.decode('utf-8')
        self.assertIn('https://dofusfashionista.gg/encyclopedia/resource/resources/', body)
        self.assertIn('https://dofusfashionista.gg/retro/encyclopedia/resource/resources/384-', body)

    def test_sitemap_lists_non_resource_recipe_ingredient_urls(self):
        import sqlite3
        from chardata.official_site import get_resource_link
        from fashionistapulp.fashionista_config import get_items_db_path

        conn = sqlite3.connect(get_items_db_path('dofus3'))
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT r.ingredient_subtype, r.ingredient_ankama_id, n.name
                FROM item_recipes r
                JOIN item_recipe_ingredient_names n
                  ON n.ingredient_ankama_id = r.ingredient_ankama_id
                 AND n.ingredient_subtype = r.ingredient_subtype
                 AND n.language = 'en'
                WHERE r.ingredient_subtype <> 'resources'
                GROUP BY r.ingredient_subtype, r.ingredient_ankama_id, n.name
                HAVING COUNT(*) >= 2
                ORDER BY CASE WHEN r.ingredient_subtype = 'consumables' THEN 0 ELSE 1 END,
                         r.ingredient_subtype, r.ingredient_ankama_id
                LIMIT 1
                """)
            ingredient = cur.fetchone()
        finally:
            conn.close()

        if ingredient is None:
            self.skipTest('no non-resource recipe ingredient in this build')

        subtype, ankama_id, name = ingredient
        link = get_resource_link(subtype, ankama_id, name, game_version='dofus3')
        self.assertTrue(link)
        page_resp = self.client.get(link)
        self.assertEqual(page_resp.status_code, 200)

        body = self.client.get('/sitemap.xml').content.decode('utf-8')
        self.assertIn('https://dofusfashionista.gg%s' % link, body)

    def test_sitemap_lists_versioned_item_urls(self):
        body = self.client.get('/sitemap.xml').content.decode('utf-8')
        self.assertIn('https://dofusfashionista.gg/encyclopedia/item/', body)
        self.assertIn('https://dofusfashionista.gg/retro/encyclopedia/item/equipment/2416-', body)

    def test_sitemap_lists_versioned_set_detail_urls(self):
        from chardata.official_site import get_set_link
        from fashionistapulp.structure import get_structure

        structure = get_structure('retro')
        set_id = None
        set_name = None
        for candidate_id, item_set in structure.sets_dict.items():
            if (getattr(item_set, 'items', None)
                    and (item_set.localized_names.get('en') or item_set.name)):
                set_id = candidate_id
                set_name = item_set.localized_names.get('en') or item_set.name
                break
        if set_id is None:
            self.skipTest('no retro set in this build')

        retro_set_url = get_set_link(set_id, set_name, 'retro')
        body = self.client.get('/sitemap.xml').content.decode('utf-8')
        self.assertIn('https://dofusfashionista.gg/encyclopedia/set/', body)
        self.assertIn('https://dofusfashionista.gg%s' % retro_set_url, body)

    def test_sitemap_lists_shared_builds_with_a_solution_only(self):
        # Shared builds are content pages worth indexing, but a build with no
        # stored solution answers 404 on /s/, so it must stay out of the sitemap.
        import pickle
        from django.contrib.auth.models import User
        from chardata.models import Char
        from chardata.encoded_char_id import encode_char_id
        from fashionistapulp.modelresult import ModelResultMinimal
        owner = User.objects.create_user('mapper', 'm@test.local', 'pw-42-solid')
        input_ = {'options': {'ap_exo': False, 'mp_exo': False}, 'origin': 'generated',
                  'char_level': 200, 'base_stats_by_attr': {}, 'locked_equips': {}}
        with_sol = Char.objects.create(
            name='HasSolution', char_name='hassol', char_class='Iop', char_build='b',
            level=200, minimum_stats=b'', minimum_crits=b'', stats_weight=b'',
            options=b'', inclusions=b'', exclusions=b'',
            minimal_solution=pickle.dumps(ModelResultMinimal({}, input_, {})),
            owner=owner, link_shared=True, game_version='dofus3')
        without_sol = Char.objects.create(
            name='NoSolution', char_name='nosol', char_class='Iop', char_build='b',
            level=200, minimum_stats=b'', minimum_crits=b'', stats_weight=b'',
            options=b'', inclusions=b'', exclusions=b'',
            owner=owner, link_shared=True, game_version='dofus3')
        body = self.client.get('/sitemap.xml').content.decode('utf-8')
        self.assertIn(encode_char_id(with_sol.id), body)
        self.assertNotIn(encode_char_id(without_sol.id), body)

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

    def test_version_prefixed_encyclopedia_pages_keep_self_canonical(self):
        # Encyclopedia data, items, recipes and calculations differ by version.
        self.assertEqual(self._canonical('/retro/encyclopedia/'),
                         'https://dofusfashionista.gg/retro/encyclopedia/')
        self.assertEqual(self._canonical('/beta/encyclopedia/sets/'),
                         'https://dofusfashionista.gg/beta/encyclopedia/sets/')
        from chardata.official_site import get_set_link
        from fashionistapulp.structure import get_structure
        touch = get_structure('touch')
        touch_set = touch.sets_dict.get(1) or touch.dt_sets_dict.get(1)
        self.assertIsNotNone(touch_set, 'touch set 1 missing')
        touch_set_name = touch_set.localized_names.get('en') or touch_set.name
        self.assertEqual(self._canonical('/touch/encyclopedia/set/1/'),
                         'https://dofusfashionista.gg%s'
                         % get_set_link(1, touch_set_name, 'touch'))
        s = get_structure('dofus2')
        it = None
        for cand in s.get_concatenated_items_lists():
            if (cand and not cand.removed and getattr(cand, 'ankama_id', None)
                    and getattr(cand, 'ankama_type', None)):
                it = cand
                break
        self.assertIsNotNone(it, 'no renderable dofus2 item found')
        canon = self._canonical('/dofus2/encyclopedia/item/%s/%s-x/'
                                % (it.ankama_type, it.ankama_id))
        self.assertTrue(canon.startswith('https://dofusfashionista.gg/dofus2/encyclopedia/item/'),
                        msg=canon)
        self.assertIn('/dofus2/', canon)


class VersionSwitcherPathTests(SimpleTestCase):
    """The global version switcher should preserve public encyclopedia pages,
    but not private/user build URLs whose numeric ids are version-specific."""

    def _base_path(self, path, game_version):
        from types import SimpleNamespace
        from chardata.context_processors import game_version as context_game_version
        request = SimpleNamespace(path_info=path, game_version=game_version)
        return context_game_version(request)['version_switch_base_path']

    def test_encyclopedia_monster_path_survives_version_switching(self):
        self.assertEqual(
            self._base_path('/retro/encyclopedia/monster/101-bouftou/', 'retro'),
            '/encyclopedia/monster/101-bouftou/')

    def test_encyclopedia_resource_path_survives_version_switching(self):
        self.assertEqual(
            self._base_path('/dofus2/encyclopedia/resource/resources/384-x/', 'dofus2'),
            '/encyclopedia/resource/resources/384-x/')

    def test_private_numeric_build_path_still_switches_to_home(self):
        self.assertEqual(self._base_path('/retro/solution/123/', 'retro'), '/')

    def test_shared_build_path_still_switches_to_home(self):
        self.assertEqual(self._base_path('/retro/s/name/AbCdEf_/', 'retro'), '/')


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

    def test_reset_email_sent_for_password_account(self):
        from django.contrib.auth.models import User
        from django.core import mail
        User.objects.create_user('withpw', 'withpw@example.com', 'pw-42-solid')
        resp = self.client.post('/recover_password/', {'email': 'withpw@example.com'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('/do_recover_password/', mail.outbox[0].body)

    def test_reset_sends_nothing_for_unknown_email(self):
        # Anti-enumeration: same page, but no mail for an unknown address.
        from django.core import mail
        resp = self.client.post('/recover_password/', {'email': 'nobody@example.com'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)

    def test_reset_sends_nothing_for_google_login_account(self):
        # Google-login accounts have no password to reset, so nothing is sent
        # (this is the usual reason a reset "doesn't arrive").
        from django.contrib.auth.models import User
        from django.core import mail
        from social_django.models import UserSocialAuth
        u = User.objects.create_user('googler', 'googler@example.com', 'unusable')
        UserSocialAuth.objects.create(user=u, provider='google-oauth2', uid='g-123')
        resp = self.client.post('/recover_password/', {'email': 'googler@example.com'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)


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


class SolutionSetTemplateTests(SimpleTestCase):

    def _render_set_link(self, game_version, url=None):
        from types import SimpleNamespace
        from django.template.loader import render_to_string
        set_result = SimpleNamespace(
            id=123,
            localized_name='Bouftou Set',
            number_of_items=1,
            total_number_of_items=8,
            url=url,
            parts={},
            stats_lines=[],
        )
        return render_to_string('chardata/solution_set.html', {
            'current_game_version': game_version,
            'set_result': set_result,
        })

    def test_set_link_uses_current_game_version(self):
        html = self._render_set_link('retro')
        self.assertIn('href="/retro/encyclopedia/set/123/"', html)
        self.assertIn('View this set', html)

    def test_set_link_prefers_readable_url(self):
        html = self._render_set_link(
            'retro', '/retro/encyclopedia/set/123-bouftou-set/')
        self.assertIn('href="/retro/encyclopedia/set/123-bouftou-set/"', html)

    def test_solution_result_sets_readable_set_url(self):
        from chardata.solution_result import SolutionResult
        from fashionistapulp.dofus_constants import SLOT_NAME_TO_TYPE
        from fashionistapulp.modelresult import ModelResultSet
        from fashionistapulp.structure import get_structure, set_current_game_version

        class _FakeResult:
            input = {'options': {}, 'origin': 'generated'}

            def __init__(self, result_set):
                self.items = {
                    slot_type: [] for slot_type in set(SLOT_NAME_TO_TYPE.values())
                }
                self.sets = [result_set]

            def get_violations_on_item(self, result_item):
                return []

            def get_stats_base(self):
                return {}

            def get_stats_gear(self):
                return {}

            def get_stats_total(self):
                return {}

        set_current_game_version('retro')
        try:
            structure = get_structure('retro')
            item_set = next(iset for iset in structure.sets_dict.values()
                            if getattr(iset, 'items', None))
            params = SolutionResult(_FakeResult(ModelResultSet(item_set, 1))).get_params()
            self.assertRegex(params['sets'][0].url,
                             r'^/retro/encyclopedia/set/%d-[^/]+/$' % item_set.id)
        finally:
            set_current_game_version('dofus3')


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


class ChooseCompareSetsPickerTests(TestCase):
    """The comparison chooser should expose saved builds from the current
    version without leaking private ids from other users."""

    @staticmethod
    def _minimal_solution():
        import pickle as _pickle
        from fashionistapulp.modelresult import ModelResultMinimal
        input_ = {
            'options': {'ap_exo': False, 'mp_exo': False},
            'origin': 'generated',
            'char_level': 200,
            'base_stats_by_attr': {
                'Vitality': 0,
                'Wisdom': 0,
                'Strength': 0,
                'Intelligence': 0,
                'Chance': 0,
                'Agility': 0,
            },
            'locked_equips': {},
        }
        return _pickle.dumps(ModelResultMinimal({}, input_, {}))

    def _make_char(self, owner, name, game_version='dofus3',
                   link_shared=False, has_solution=True):
        from chardata.models import Char
        return Char.objects.create(
            name=name, char_name=name.lower().replace(' ', '-'),
            char_class='Iop', char_build='Damage', level=200,
            minimum_stats=b'', minimum_crits=b'', stats_weight=b'',
            options=b'', inclusions=b'', exclusions=b'',
            minimal_solution=(self._minimal_solution() if has_solution else b''),
            owner=owner, link_shared=link_shared, game_version=game_version)

    def test_logged_in_picker_lists_owned_favorite_and_liked_builds_for_current_version(self):
        from django.contrib.auth.models import User
        from chardata.models import BuildVote
        user = User.objects.create_user('comparepicker', 'cp@test.local', 'pw-42-solid')
        other = User.objects.create_user('otherpicker', 'op@test.local', 'pw-42-solid')
        own = self._make_char(user, 'Retro Own', game_version='retro')
        favorite = self._make_char(other, 'Retro Favorite', game_version='retro',
                                   link_shared=True)
        liked = self._make_char(other, 'Retro Like', game_version='retro',
                                link_shared=True)
        self._make_char(user, 'Dofus3 Own', game_version='dofus3')
        self._make_char(user, 'No Solution', game_version='retro', has_solution=False)
        BuildVote.objects.create(user=user, build=favorite, vote_type='favorite')
        BuildVote.objects.create(user=user, build=liked, vote_type='like')
        self.client.force_login(user)

        resp = self.client.get('/retro/choose_compare_sets/')
        self.assertEqual(resp.status_code, 200)
        sections = {
            section['key']: section
            for section in resp.context['compare_picker_sections']
        }

        self.assertEqual([entry['name'] for entry in sections['owned']['builds']],
                         ['Retro Own'])
        self.assertEqual([entry['name'] for entry in sections['favorites']['builds']],
                         ['Retro Favorite'])
        self.assertEqual([entry['name'] for entry in sections['likes']['builds']],
                         ['Retro Like'])
        self.assertEqual(sections['owned']['builds'][0]['link'],
                         '/retro/solution/%d/' % own.pk)
        self.assertIn('/retro/s/retro-favorite/',
                      sections['favorites']['builds'][0]['link'])
        html = resp.content.decode('utf-8')
        self.assertIn('Retro Own', html)
        self.assertNotIn('Dofus3 Own', html)
        self.assertNotIn('No Solution', html)

    def test_anonymous_picker_keeps_manual_flow(self):
        resp = self.client.get('/choose_compare_sets/')
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode('utf-8')
        self.assertIn('Log in to pick from your builds, favorites and likes.', html)
        self.assertIn('Manual links', html)

    def test_post_rejects_too_many_links_with_visible_error(self):
        import json
        links = [
            'http://testserver/solution/%d/' % i
            for i in range(1, 6)
        ]
        resp = self.client.post('/choose_compare_sets_post/',
                                {'links': json.dumps(links)})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content.decode('utf-8'),
                         'Error: Choose at most 4 builds to compare')

    def test_post_errors_keep_ajax_prefix(self):
        import json
        resp = self.client.post('/choose_compare_sets_post/',
                                {'links': json.dumps([])})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.content.decode('utf-8').startswith('Error: '))

    def test_post_rejects_malformed_link_without_500(self):
        import json
        resp = self.client.post('/choose_compare_sets_post/',
                                {'links': json.dumps(['////', '/solution/1/'])})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.content.decode('utf-8').startswith('Error: '))

    def test_name_search_only_returns_current_version_builds(self):
        from django.contrib.auth.models import User
        user = User.objects.create_user('versionsearch', 'vs@test.local', 'pw-42-solid')
        retro = self._make_char(user, 'Own Retro Search', game_version='retro')
        self._make_char(user, 'Own Dofus3 Search', game_version='dofus3')
        self.client.force_login(user)

        resp = self.client.post('/retro/compare_set_search_proj_name/',
                                {'name[term]': 'Own'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [{'label': 'Own Retro Search', 'idx': retro.pk}])


class WorkshopTests(TestCase):
    """The workshop aggregates the items a player wants to craft; cover the
    add endpoint happy path, its error paths and the auth guard."""

    def setUp(self):
        from django.contrib.auth.models import User
        self.user = User.objects.create_user('crafter', 'w@test.local', 'pw-42-solid')
        from fashionistapulp.structure import get_structure
        self.item = next(iter(get_structure('dofus3').get_concatenated_items_lists()))

    def test_add_item_then_add_again_increments(self):
        self.client.force_login(self.user)
        resp = self.client.post('/workshop/add/', {'item_id': self.item.id})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['success'])
        self.assertTrue(resp.json()['created'])
        resp = self.client.post('/workshop/add/', {'item_id': self.item.id})
        self.assertFalse(resp.json()['created'])

    def test_bad_item_ids_rejected(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.post('/workshop/add/', {'item_id': 'abc'}).status_code, 400)
        self.assertEqual(self.client.post('/workshop/add/', {'item_id': 99999999}).status_code, 404)

    def test_anonymous_cannot_add(self):
        resp = self.client.post('/workshop/add/', {'item_id': self.item.id})
        self.assertEqual(resp.status_code, 302)


class GetItemStatsTests(TestCase):
    """/get_item_stats_compare/ powers the compare-page item tooltips. An id
    that isn't in the current structure (stale page, other game version) should
    answer null, not error."""

    def test_valid_item_returns_stats(self):
        from fashionistapulp.structure import get_structure
        item = next(iter(get_structure('dofus3').get_concatenated_items_lists()))
        resp = self.client.post('/get_item_stats_compare/', {'itemId': item.id})
        self.assertEqual(resp.status_code, 200)
        self.assertIn('stats_lines', resp.content.decode('utf-8'))

    def test_unknown_or_malformed_id_answers_null_not_500(self):
        for bad in ('99999999', 'abc', ''):
            resp = self.client.post('/get_item_stats_compare/', {'itemId': bad})
            self.assertEqual(resp.status_code, 200, 'itemId=%r' % bad)
        resp = self.client.post('/get_item_stats_compare/')
        self.assertEqual(resp.status_code, 200)

    def test_versioned_item_stats_use_version_specific_items(self):
        from fashionistapulp.structure import get_structure
        dofus3_ids = {
            item.id for item in get_structure('dofus3').get_concatenated_items_lists()
        }
        retro_item = next(
            (item for item in get_structure('retro').get_concatenated_items_lists()
             if item.id not in dofus3_ids and not item.removed),
            None)
        self.assertIsNotNone(retro_item, 'no retro-only item found')

        resp = self.client.post('/retro/get_item_stats_compare/', {'itemId': retro_item.id})
        self.assertEqual(resp.status_code, 200)
        self.assertIn('"id": %d' % retro_item.id, resp.content.decode('utf-8'))

        default_resp = self.client.post('/get_item_stats_compare/', {'itemId': retro_item.id})
        self.assertEqual(default_resp.status_code, 200)
        self.assertEqual(default_resp.content.decode('utf-8'), 'None')

    def test_item_details_survives_unknown_or_malformed_id(self):
        from fashionistapulp.structure import get_structure
        item = next(iter(get_structure('dofus3').get_concatenated_items_lists()))
        resp = self.client.post('/getitemdetails/', {'item': item.id})
        self.assertEqual(resp.status_code, 200)
        self.assertIn('level', resp.json())
        for bad in ('99999999', 'abc', ''):
            resp = self.client.post('/getitemdetails/', {'item': bad})
            self.assertEqual(resp.status_code, 200, 'item=%r' % bad)
            self.assertEqual(resp.json(), {})

    def test_evolve_no_item_result_does_not_crash(self):
        # A no-item result must survive evolve_result_item (it reads .slot/.file).
        from fashionistapulp.modelresult import ModelResultItem
        from chardata.solution_result import evolve_result_item
        result_item = ModelResultItem(None)
        self.assertIsNone(result_item.slot)
        self.assertIsNone(result_item.file)
        evolve_result_item(result_item)

    def test_switch_item_rejects_unknown_id_instead_of_removing(self):
        from django.contrib.auth.models import User
        from chardata.models import Char
        user = User.objects.create_user('switcher', 's@test.local', 'pw-42-solid')
        char = Char.objects.create(
            name='Switch test', char_name='hero', char_class='Iop',
            char_build='build', level=200,
            minimum_stats=b'', minimum_crits=b'', stats_weight=b'',
            options=b'', inclusions=b'', exclusions=b'',
            owner=user, link_shared=False, game_version='dofus3')
        self.client.force_login(user)
        for bad in ('99999999', 'abc', ''):
            resp = self.client.post('/exchange/%d/' % char.id,
                                    {'itemName': bad, 'slot': 'hat'})
            self.assertEqual(resp.status_code, 400, 'itemName=%r' % bad)


class CommunityFeatureTests(TestCase):
    """Comments and votes on shared builds are the retention features; cover
    the happy paths and the auth guard."""

    def setUp(self):
        from django.contrib.auth.models import User
        from chardata.models import Char
        self.user = User.objects.create_user('communaut', 'c@test.local', 'pw-42-solid')
        self.build = Char.objects.create(
            name='Shared build', char_name='hero', char_class='Iop',
            char_build='build', level=200,
            minimum_stats=b'', minimum_crits=b'', stats_weight=b'',
            options=b'', inclusions=b'', exclusions=b'',
            link_shared=True, game_version='dofus3')

    def test_post_comment(self):
        self.client.force_login(self.user)
        resp = self.client.post('/postcomment/%d/' % self.build.id,
                                {'content': 'Nice build, works great on my server.'})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['success'])
        self.assertIn('Nice build', resp.json()['comment']['content'])

    def test_vote_build_like(self):
        self.client.force_login(self.user)
        resp = self.client.post('/votebuild/%d/' % self.build.id,
                                {'vote_type': 'like', 'action': 'add'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json().get('like_count'), 1)

    def test_anonymous_cannot_comment_or_vote(self):
        for path in ['/postcomment/%d/' % self.build.id,
                     '/votebuild/%d/' % self.build.id]:
            with self.subTest(path=path):
                resp = self.client.post(path, {'content': 'x'})
                self.assertEqual(resp.status_code, 302)


class RegistrationFunnelTests(TestCase):
    """End-to-end signup: register -> inactive user + confirmation email ->
    following the emailed link activates the account. This is the growth
    funnel; it must never silently break."""

    @override_settings(DEBUG=True)  # captcha bypassed in debug
    def test_register_confirm_activates_account(self):
        from django.contrib.auth.models import User
        from django.core import mail
        resp = self.client.post('/register/', {
            'username': 'newplayer', 'password': 'a-solid-password-42',
            'email': 'newplayer@test.local'})
        self.assertEqual(resp.status_code, 302)
        user = User.objects.get(username='newplayer')
        self.assertFalse(user.is_active, 'account must start inactive')
        self.assertEqual(len(mail.outbox), 1)
        m = re.search(r'/confirm_email/[^/\s]+/[^/\s]+/', mail.outbox[0].body)
        self.assertIsNotNone(m, 'confirmation link missing from the email')
        resp = self.client.get(m.group(0))
        user.refresh_from_db()
        self.assertTrue(user.is_active, 'confirmation link must activate')

    @override_settings(DEBUG=True)
    def test_bad_confirmation_token_rejected(self):
        from django.contrib.auth.models import User
        self.client.post('/register/', {
            'username': 'otherplayer', 'password': 'a-solid-password-42',
            'email': 'otherplayer@test.local'})
        resp = self.client.get('/confirm_email/otherplayer/wrongtoken/')
        user = User.objects.get(username='otherplayer')
        self.assertFalse(user.is_active, 'bad token must not activate')

    @override_settings(DEBUG=True)
    def test_welcome_email_follows_request_language(self):
        # A French visitor registering must get the welcome email in French.
        from django.core import mail
        resp = self.client.post('/register/', {
            'username': 'joueurfr', 'password': 'a-solid-password-42',
            'email': 'joueurfr@test.local'},
            headers={'accept-language': 'fr'})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Bienvenue', mail.outbox[0].subject)
        self.assertNotIn('Please click', mail.outbox[0].body)


class ContactFormTests(TestCase):
    """The contact form is the players' support lifeline; a silent breakage
    means lost messages. DEBUG=True (test settings) bypasses the captcha."""

    def test_contact_page_renders(self):
        self.assertEqual(self.client.get('/contact/').status_code, 200)

    @override_settings(DEBUG=True)  # the captcha is bypassed in debug
    def test_send_email_delivers_and_redirects(self):
        from django.core import mail
        resp = self.client.post('/send/', {
            'topic': 'Bug report', 'message': 'The optimizer ate my hat.',
            'email': 'player@test.local', 'name': 'A player'})
        self.assertEqual(resp.status_code, 302)
        self.assertIn('thankyou', resp.url)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Fashionista Form: Bug report', mail.outbox[0].subject)

    def test_send_email_get_redirects_to_contact(self):
        resp = self.client.get('/send/')
        self.assertEqual(resp.status_code, 302)


class AuthenticatedPagesSmokeTests(TestCase):
    """The anonymous smoke tests cover the public site; these cover the pages
    a logged-in player actually lives in."""

    def setUp(self):
        from django.contrib.auth.models import User
        self.user = User.objects.create_user('smoketester', 'smoke@test.local',
                                             'irrelevant-password')
        self.client.force_login(self.user)

    def test_logged_in_pages_ok(self):
        for path in ['/feed/', '/inventory/', '/workshop/', '/loadprojects/']:
            with self.subTest(path=path):
                resp = self.client.get(path)
                self.assertEqual(resp.status_code, 200,
                                 msg='%s -> %s' % (path, resp.status_code))


class ErrorHandlerRenderTests(TestCase):
    """The 500 handler renders a full template (extends base); if that render
    itself breaks, users get a blank page exactly when things already went
    wrong. Guard that the handler produces real, translated html."""

    def test_app_error_renders(self):
        from django.test import RequestFactory
        from django.contrib.auth.models import AnonymousUser
        from django.contrib.sessions.backends.db import SessionStore
        from chardata import views
        request = RequestFactory().get('/')
        request.user = AnonymousUser()
        request.session = SessionStore()
        request.game_version = 'dofus3'
        response = views.app_error(request)
        self.assertEqual(response.status_code, 500)
        body = response.content.decode('utf-8')
        self.assertIn('500', body)
        self.assertIn('noindex', body)


class PrivateProjectAccessTests(TestCase):
    """Private (non-shared) project pages must never render for a third party
    (including crawlers): anonymous access to someone else's char has to be
    denied, so private builds cannot leak or get indexed."""

    def _make_private_char(self):
        from chardata.models import Char
        return Char.objects.create(
            name='Private build', char_name='hero', char_class='Iop',
            char_build='build', level=200,
            minimum_stats=b'', minimum_crits=b'', stats_weight=b'',
            options=b'', inclusions=b'', exclusions=b'',
            link_shared=False, game_version='dofus3')

    def test_anonymous_cannot_open_private_project_pages(self):
        char = self._make_private_char()
        for path in ['/solution/%d/' % char.id, '/wizard/%d/' % char.id,
                     '/setup/%d/' % char.id]:
            with self.subTest(path=path):
                resp = self.client.get(path)
                self.assertIn(resp.status_code, (302, 403, 404),
                              msg='%s leaked with %s' % (path, resp.status_code))


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


@override_settings(
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    }
)
class GuidesContentTests(TestCase):
    """The Guides section is original editorial content (AdSense "low value
    content" remedy). It must render in every language, 404 on unknown slugs,
    and stay self-canonical."""

    def test_hub_lists_every_guide(self):
        from chardata import guides_content
        resp = self.client.get('/guides/')
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode('utf-8', 'replace')
        for slug in guides_content.GUIDES:
            self.assertIn('/guides/%s/' % slug, html)

    def test_order_covers_every_guide(self):
        # The crafting guide shipped published but invisible for a morning:
        # only ORDER feeds the hub and the sitemap, and it was missing there.
        # ordered_slugs() now catches forgotten slugs at runtime; this catches
        # them at test time, where the author actually sees it.
        from chardata import guides_content
        self.assertEqual(set(guides_content.ORDER),
                         set(guides_content.GUIDES),
                         'ORDER and GUIDES must list the same guide slugs')

    def test_unknown_guide_is_404(self):
        self.assertEqual(self.client.get('/guides/not-a-real-guide/').status_code, 404)

    def test_guide_is_self_canonical(self):
        resp = self.client.get('/guides/getting-started/')
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode('utf-8', 'replace')
        tag = re.search(r'<link[^>]*\brel=["\']?canonical["\']?[^>]*>', html)
        self.assertIsNotNone(tag)
        self.assertIn('https://dofusfashionista.gg/guides/getting-started/', tag.group(0))

    def test_hub_has_valid_itemlist_jsonld(self):
        import json
        from chardata import guides_content
        resp = self.client.get('/guides/')
        html = resp.content.decode('utf-8')
        blocks = re.findall(r'<script type="application/ld\+json">\s*(.*?)\s*</script>',
                            html, re.S)
        lists = [json.loads(b) for b in blocks
                 if json.loads(b).get('@type') == 'ItemList']
        self.assertEqual(len(lists), 1, 'ItemList JSON-LD missing on guides hub')
        self.assertEqual(len(lists[0]['itemListElement']), len(guides_content.ORDER))

    def test_guide_has_valid_breadcrumb_jsonld(self):
        import json
        resp = self.client.get('/guides/getting-started/')
        html = resp.content.decode('utf-8')
        blocks = re.findall(r'<script type="application/ld\+json">\s*(.*?)\s*</script>',
                            html, re.S)
        crumbs = [json.loads(b) for b in blocks
                  if json.loads(b).get('@type') == 'BreadcrumbList']
        self.assertEqual(len(crumbs), 1, 'BreadcrumbList JSON-LD missing on guide page')
        items = crumbs[0]['itemListElement']
        self.assertEqual(len(items), 3)
        self.assertTrue(items[2]['name'])

    def test_guide_article_jsonld_has_publish_date(self):
        import json
        from chardata import guides_content
        for slug in guides_content.ORDER:
            self.assertRegex(guides_content.GUIDES[slug]['published'],
                             r'^\d{4}-\d{2}-\d{2}$', slug)
        resp = self.client.get('/guides/getting-started/')
        html = resp.content.decode('utf-8')
        blocks = re.findall(r'<script type="application/ld\+json">\s*(.*?)\s*</script>',
                            html, re.S)
        articles = [json.loads(b) for b in blocks
                    if json.loads(b).get('@type') == 'Article']
        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0]['datePublished'], '2026-06-30')

    def test_guide_body_links_back_into_the_tool(self):
        # Internal links (SEO + UX): the article body points at real tool pages.
        resp = self.client.get('/guides/getting-started/')
        self.assertContains(resp, 'href="/setup/"')

    def test_all_guide_body_links_resolve(self):
        # Every root-relative link in every language's body must keep resolving
        # when site URLs change; a dead link in editorial content is invisible
        # until a reader hits it.
        from chardata import guides_content
        hrefs = set()
        for guide in guides_content.GUIDES.values():
            for block in guide['i18n'].values():
                hrefs.update(re.findall(r'href="(/[^"]*)"', block['body']))
        self.assertTrue(hrefs)
        for href in sorted(hrefs):
            resp = self.client.get(href.split('#')[0])
            self.assertIn(resp.status_code, (200, 301, 302), href)

    def test_content_is_translated_per_language(self):
        # Each language must serve its own hand-written title, not the English one.
        cases = {
            'fr': 'ton premier stuff',
            'es': 'tu primer build',
            'pt': 'seu primeiro build',
            'de': 'dein erstes',
        }
        for lang, needle in cases.items():
            with translation.override(lang):
                resp = self.client.get('/guides/getting-started/',
                                       headers={'accept-language': lang})
            html = resp.content.decode('utf-8', 'replace').lower()
            with self.subTest(lang=lang):
                self.assertIn(needle, html, msg='%s title missing' % lang)


class NlParserTests(SimpleTestCase):
    """The smart-build natural-language parser must understand all five UI
    languages. German was added last; these lock in the German class names,
    elements, styles and aspects (official Ankama names, sourced from the de
    translations) so the feature stays complete."""

    def _parse(self, text):
        from chardata.nl_parser import parse_build_request
        return parse_build_request(text)

    def test_german_class_names(self):
        cases = {
            'Halsabschneider': 'Rogue',
            'Speerschmied': 'Forgelance',
            'Übermagier': 'Huppermage',
            'Maskerador': 'Masqueraider',
            'Steamer': 'Foggernaut',
            'Sacrieur': 'Sacrier',
        }
        for word, expected in cases.items():
            with self.subTest(word=word):
                self.assertEqual(self._parse('%s 200' % word)['char_class'], expected)

    def test_german_elements(self):
        cases = {'Feuer': 'int', 'Erde': 'str', 'Wasser': 'cha', 'Luft': 'agi'}
        for word, expected in cases.items():
            with self.subTest(word=word):
                self.assertEqual(self._parse('Iop %s' % word)['element'], expected)

    def test_german_level_keyword(self):
        self.assertEqual(self._parse('Cra Stufe 150 Luft')['level'], 150)

    def test_german_styles_and_aspects(self):
        r = self._parse('Maskerador Beweglichkeit Verlies Heiler')
        self.assertEqual(r['char_class'], 'Masqueraider')
        self.assertEqual(r['style'], 'group_pvm')
        self.assertIn('heal', r['extra_aspects'])
        self.assertEqual(self._parse('Enutrof Prospektion farmen')['style'], 'farm')
        self.assertIn('trap', self._parse('Sram Falle')['extra_aspects'])

    def test_existing_languages_still_parse(self):
        # Guard against regressions in the FR/EN keyword sets while extending DE.
        self.assertEqual(self._parse('Iop 200 terre PvM')['char_class'], 'Iop')
        self.assertEqual(self._parse('Iop 200 terre PvM')['element'], 'str')
        self.assertEqual(self._parse('Cra agi pvp niveau 150')['style'], 'pvp')

    def test_every_example_chip_parses_to_a_class(self):
        # The example chips are clickable and fill the box, so each one must
        # itself resolve to a class in every language it is offered in.
        from chardata.nl_build_view import EXAMPLE_QUERIES_BY_LANG
        for lang, examples in EXAMPLE_QUERIES_BY_LANG.items():
            for ex in examples:
                with self.subTest(lang=lang, example=ex):
                    self.assertIsNotNone(self._parse(ex)['char_class'],
                                         msg='example %r has no class' % ex)

    def test_build_name_style_is_localized(self):
        # The auto-generated build name must not leak the raw "group_pvm" key;
        # the style word is served in the active language.
        from chardata.nl_build_view import _style_name
        with translation.override('fr'):
            self.assertEqual(_style_name('group_pvm'), 'PvM en groupe')
        with translation.override('de'):
            self.assertEqual(_style_name('solo_pvm'), 'Solo-PvM')


class AspectParserTests(SimpleTestCase):
    """The "understand my build" text field (build_confirmation.html ->
    /understandbuild/) auto-checks aspect boxes from a free-text description.
    It was English-only; these lock in the FR/ES/PT/DE keywords and the accent
    folding so non-English players get their aspects recognized too."""

    def _aspects(self, text):
        from chardata.aspect_parser import parse_aspects
        return parse_aspects(text)

    def test_french_keywords(self):
        self.assertEqual(self._aspects('Iop terre dégâts'), {'str', 'dam'})
        self.assertEqual(self._aspects('Eni feu soigneur'), {'int', 'heal'})
        self.assertIn('trap', self._aspects('Sram piège invocation'))
        self.assertIn('summon', self._aspects('Sram piège invocation'))

    def test_german_keywords(self):
        self.assertEqual(self._aspects('Iop Erde Schaden'), {'str', 'dam'})
        self.assertEqual(self._aspects('Eni Feuer Heiler'), {'int', 'heal'})

    def test_spanish_keywords(self):
        self.assertEqual(self._aspects('Cra agua sanador'), {'cha', 'heal'})

    def test_accent_folding(self):
        # "dégâts" must match the "degats" marker.
        self.assertIn('dam', self._aspects('dégâts'))

    def test_english_still_parses(self):
        self.assertEqual(self._aspects('earth fire healer'), {'str', 'int', 'heal'})
        self.assertIn('pvp', self._aspects('pvp kolo'))


class ItemIconFallbackTests(SimpleTestCase):
    """Variant items produced by the data pipeline ("Nomoon 2") reuse the base
    item's artwork; only the base icon exists on disk. get_image_url must fall
    back to the base icon instead of serving a broken image."""

    def test_variant_falls_back_to_base_icon(self):
        from chardata.image_store import get_image_url
        self.assertEqual(get_image_url('Amulet', 'Nomoon 2', 'dofus3'),
                         'chardata/items/60x60/Nomoon-60-60.png')

    def test_regular_item_keeps_exact_path(self):
        from chardata.image_store import get_image_url
        self.assertEqual(get_image_url('Amulet', 'Nomoon', 'dofus3'),
                         'chardata/items/60x60/Nomoon-60-60.png')

    def test_dofus2_variant_falls_back(self):
        from chardata.image_store import get_image_url
        self.assertEqual(get_image_url('Shield', 'Sponghield 2', 'dofus2'),
                         'chardata/items/60x60/Sponghield-60-60.png')

    def test_windows_illegal_chars_stripped_from_icon_path(self):
        # "Wand Else?" cannot exist as a filename on windows; the icon is
        # stored (and must be looked up) without the question mark.
        from chardata.image_store import get_image_url
        self.assertEqual(get_image_url('Weapon', 'Wand Else?', 'touch'),
                         'chardata/items/touch/60x60/Wand Else-60-60.png')


class LocalizedUiParityTests(SimpleTestCase):
    """The inventory, forgemagie and encyclopedia pages each carry their own
    hand-maintained per-language UI dict. A key present in English but missing
    in another language renders blank (or raises) for those users, so these keep
    the five languages at strict key parity and catch future drift."""

    LANGS = ['en', 'fr', 'es', 'pt', 'de']

    def test_encyclopedia_ui_uses_proper_accents(self):
        # The encyclopedia dict shipped unaccented ("Encyclopedie", "Direcao");
        # pin a few strings so the accents don't regress.
        from chardata.encyclopedia_view import LOCALIZED_UI
        self.assertEqual(LOCALIZED_UI['fr']['title'], 'Encyclopédie')
        self.assertEqual(LOCALIZED_UI['fr']['details_title'], "Détails de l'objet")
        self.assertEqual(LOCALIZED_UI['es']['search_label'], 'Búsqueda')
        self.assertEqual(LOCALIZED_UI['pt']['title'], 'Enciclopédia')
        self.assertEqual(LOCALIZED_UI['de']['title'], 'Enzyklopädie')

    def _assert_parity(self, dictionary, name):
        for lang in self.LANGS:
            self.assertIn(lang, dictionary, msg='%s missing %s' % (name, lang))
        base = set(dictionary['en'].keys())
        for lang in self.LANGS:
            with self.subTest(dict=name, lang=lang):
                self.assertEqual(set(dictionary[lang].keys()), base,
                                 msg='%s[%s] keys differ from en' % (name, lang))

    def test_inventory_ui_parity(self):
        from chardata.inventory_view import LOCALIZED_UI
        self._assert_parity(LOCALIZED_UI, 'inventory')

    def test_forgemagie_ui_parity(self):
        from chardata.forgemagie_view import LOCALIZED_UI, TRANSCENDENCE_UI
        self._assert_parity(LOCALIZED_UI, 'forgemagie')
        self._assert_parity(TRANSCENDENCE_UI, 'forgemagie_transcendence')

    def test_encyclopedia_ui_parity(self):
        from chardata.encyclopedia_view import LOCALIZED_UI
        self._assert_parity(LOCALIZED_UI, 'encyclopedia')


class ApiDocsTests(TestCase):
    """The public API advertises /about/#api as its docs; that section must
    exist, stay translated, and the meta endpoint must keep pointing at it."""

    def test_about_documents_the_api(self):
        resp = self.client.get('/about/')
        self.assertContains(resp, 'id="api"')
        self.assertContains(resp, '/api/v1/shared-builds/')

    def test_about_api_section_is_translated(self):
        cases = {'fr': 'API publique', 'es': 'API p', 'pt': 'API p', 'de': 'ffentliche API'}
        for lang, needle in cases.items():
            resp = self.client.get('/about/', headers={'accept-language': lang})
            self.assertContains(resp, needle, msg_prefix=lang)

    def test_meta_endpoint_points_to_about_anchor(self):
        resp = self.client.get('/api/v1/')
        self.assertEqual(resp.json()['docs'], 'https://dofusfashionista.gg/about/#api')

    def test_api_responses_carry_cache_and_cors_headers(self):
        # Public API contract: open CORS + short client-side cache, so bots
        # and overlays do not hammer the backend.
        for url, max_age in (('/api/v1/', 'max-age=300'),
                             ('/api/v1/shared-builds/', 'max-age=60')):
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 200, url)
            self.assertEqual(resp['Access-Control-Allow-Origin'], '*', url)
            self.assertIn(max_age, resp.get('Cache-Control', ''), url)


class CommentNotificationLanguageTests(TestCase):
    """The build owner gets the new-comment email in the language they last
    picked in the language selector, not hardcoded English."""

    def _make_build(self, owner):
        from chardata.models import Char
        return Char.objects.create(
            name='Mail build', char_name='hero', char_class='Iop',
            char_build='build', level=200,
            minimum_stats=b'', minimum_crits=b'', stats_weight=b'',
            options=b'', inclusions=b'', exclusions=b'',
            owner=owner, link_shared=True, game_version='dofus3')

    def test_setlang_remembers_the_choice(self):
        from django.contrib.auth.models import User
        from chardata.models import UserAlias
        user = User.objects.create_user('polyglot', 'p@test.local', 'pw-42-solid')
        self.client.force_login(user)
        resp = self.client.post('/i18n/setlang/', {'language': 'de'})
        self.assertIn(resp.status_code, (200, 302))
        self.assertEqual(UserAlias.objects.get(user=user).language, 'de')

    def test_login_backfills_language(self):
        # Accounts that never touched the language selector get the language
        # they were browsing in when they logged in.
        from django.contrib.auth.models import User
        from chardata.models import UserAlias
        user = User.objects.create_user('nolang', 'n@test.local', 'pw-42-solid')
        with translation.override('pt'):
            self.client.force_login(user)
        self.assertEqual(UserAlias.objects.get(user=user).language, 'pt')

    def test_login_does_not_overwrite_explicit_choice(self):
        from django.contrib.auth.models import User
        from chardata.models import UserAlias
        user = User.objects.create_user('haslang', 'h@test.local', 'pw-42-solid')
        UserAlias.objects.create(user=user, language='de')
        with translation.override('fr'):
            self.client.force_login(user)
        self.assertEqual(UserAlias.objects.get(user=user).language, 'de')

    def test_account_page_saves_email_language(self):
        from django.contrib.auth.models import User
        from chardata.models import UserAlias
        user = User.objects.create_user('settings-user', 's@test.local', 'pw-42-solid')
        self.client.force_login(user)
        resp = self.client.get('/manageaccount/')
        self.assertContains(resp, 'email_language')
        # Explicit choice saved.
        resp = self.client.post('/saveaccount/', {'alias': 'Testeur', 'email_language': 'es'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['email_language'], 'es')
        self.assertEqual(UserAlias.objects.get(user=user).language, 'es')
        # Bogus value ignored, choice kept.
        self.client.post('/saveaccount/', {'alias': 'Testeur', 'email_language': 'xx'})
        self.assertEqual(UserAlias.objects.get(user=user).language, 'es')
        # Field absent (cached page): choice kept.
        self.client.post('/saveaccount/', {'alias': 'Testeur'})
        self.assertEqual(UserAlias.objects.get(user=user).language, 'es')
        # "Automatic" clears it.
        self.client.post('/saveaccount/', {'alias': 'Testeur', 'email_language': ''})
        self.assertIsNone(UserAlias.objects.get(user=user).language)

    def test_notification_email_uses_owner_language(self):
        from django.contrib.auth.models import User
        from django.core import mail
        from chardata.models import UserAlias
        owner = User.objects.create_user('owner-fr', 'owner@test.local', 'pw-42-solid')
        UserAlias.objects.create(user=owner, language='fr')
        build = self._make_build(owner)
        commenter = User.objects.create_user('lecteur', 'l@test.local', 'pw-42-solid')
        self.client.force_login(commenter)
        resp = self.client.post('/postcomment/%d/' % build.id,
                                {'content': 'Tres joli build, bravo pour le travail.'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        self.assertIn('Nouveau commentaire sur ton build', msg.subject)
        self.assertIn('vient de commenter', msg.body)
        html = msg.alternatives[0][0]
        self.assertIn('lang="fr"', html)


class WizardSlidersRoundTripTests(SimpleTestCase):
    """The tuning page maps sliders to solver weights and back; drift in that
    mapping silently corrupts what players believe they configured."""

    def test_set_then_get_round_trips_for_every_slider(self):
        import collections
        from chardata.wizard_sliders import (SLIDER_RANGES,
                                             get_slider_value_from_weights,
                                             set_weights_from_slider_value)
        weights = collections.defaultdict(int)
        for key, (low, high) in SLIDER_RANGES.items():
            for value in (low, (low + high) // 2, high):
                set_weights_from_slider_value(key, value, weights)
                got = get_slider_value_from_weights(key, weights)
                self.assertEqual(got, value,
                                 'slider %r: set %s, got back %s' % (key, value, got))


class SharedBuildsHideInvalidTests(TestCase):
    """The hide_invalid filter drops builds whose stored solution no longer
    unpickles; it must keep working after the cache-driven scan rewrite."""

    def _make_build(self, name, blob):
        from django.contrib.auth.models import User
        from chardata.models import Char
        owner, _created = User.objects.get_or_create(
            username='sharer', defaults={'email': 'sh@test.local'})
        return Char.objects.create(
            name=name, char_name=name, char_class='Iop',
            char_build='build', level=200,
            minimum_stats=b'', minimum_crits=b'', stats_weight=b'',
            options=b'', inclusions=b'', exclusions=b'',
            minimal_solution=blob,
            owner=owner, link_shared=True, game_version='dofus3')

    def test_hide_invalid_drops_corrupt_builds_only(self):
        self._make_build('ValidementVisible', b'')
        self._make_build('CorrompuCache', b'not-a-pickle')
        resp = self.client.get('/sharedbuilds/?hide_invalid=1')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'ValidementVisible')
        self.assertNotContains(resp, 'CorrompuCache')
        resp = self.client.get('/sharedbuilds/')
        self.assertContains(resp, 'ValidementVisible')
        self.assertContains(resp, 'CorrompuCache')


class SharedBuildMetaVersionTests(TestCase):
    """Shared-build cards must score and preview items from the build's own
    game version, even when called outside a versioned request."""

    @staticmethod
    def _base_input():
        return {
            'options': {'ap_exo': False, 'mp_exo': False},
            'origin': 'generated',
            'char_level': 200,
            'base_stats_by_attr': {
                'Vitality': 0,
                'Wisdom': 0,
                'Strength': 0,
                'Intelligence': 0,
                'Chance': 0,
                'Agility': 0,
            },
            'locked_equips': {},
        }

    def test_meta_uses_build_game_version_for_preview_and_public_score(self):
        import pickle as _pickle
        from django.contrib.auth.models import User
        from django.core.cache import cache
        from chardata.image_store import get_image_url
        from chardata.models import Char
        from chardata.shared_builds_view import _get_shared_build_meta
        from fashionistapulp.modelresult import ModelResultMinimal
        from fashionistapulp.structure import (get_current_game_version,
                                               get_structure,
                                               set_current_game_version)
        from static_s3.templatetags.static_s3 import static

        cache.clear()
        retro = get_structure('retro')
        modern = get_structure('dofus3')
        retro_hat = None
        for candidate in retro.get_unique_items_by_type_and_level('Hat', 200):
            modern_item = modern.get_item_by_id(candidate.id)
            has_public_score = any(
                value > 0 and retro.get_stat_by_id(stat_id) is not None
                for stat_id, value in candidate.stats)
            if (not candidate.removed and candidate.ankama_id and has_public_score
                    and (modern_item is None or modern_item.name != candidate.name)):
                retro_hat = candidate
                break
        self.assertIsNotNone(retro_hat, 'no distinct Retro hat found')

        owner = User.objects.create_user('retrometa', 'retrometa@test.local',
                                         'pw-42-solid')
        char = Char.objects.create(
            name='RetroMeta', char_name='retrometa', char_class='Iop',
            char_build='build', level=200,
            minimum_stats=b'', minimum_crits=b'', stats_weight=b'',
            options=b'', inclusions=b'', exclusions=b'',
            minimal_solution=_pickle.dumps(ModelResultMinimal(
                {'hat': retro_hat.id}, self._base_input(), {})),
            owner=owner, link_shared=True, game_version='retro')

        previous_version = get_current_game_version()
        set_current_game_version('dofus3')
        self.addCleanup(set_current_game_version, previous_version)
        with translation.override('en'):
            meta = _get_shared_build_meta(char)

        self.assertFalse(meta['has_missing_items'])
        self.assertFalse(meta['has_outdated_slots'])
        self.assertGreater(meta['public_score'], 0)
        self.assertEqual(len(meta['preview_items']), 1)
        self.assertEqual(meta['preview_items'][0]['name'],
                         retro.get_item_name_in_language(retro_hat, 'en'))
        expected_image_url = static(get_image_url(
            retro.get_type_name_by_id(retro_hat.type), retro_hat.name, 'retro'))
        self.assertEqual(meta['preview_items'][0]['image_url'], expected_image_url)
        self.assertEqual(get_current_game_version(), 'dofus3')


class SharedLinkWithoutSolutionTests(TestCase):
    """A shared link to a build whose solution was never stored (or was reset)
    404s cleanly, without counting a view."""

    def test_solutionless_shared_link_is_404_not_500(self):
        from django.contrib.auth.models import User
        from chardata.models import Char
        from chardata.encoded_char_id import encode_char_id
        owner = User.objects.create_user('viewed', 'v@test.local', 'pw-42-solid')
        build = Char.objects.create(
            name='Vitrine', char_name='vitrine', char_class='Iop',
            char_build='build', level=200,
            minimum_stats=b'', minimum_crits=b'', stats_weight=b'',
            options=b'', inclusions=b'', exclusions=b'',
            owner=owner, link_shared=True, game_version='dofus3')
        url = '/s/vitrine/%s/' % encode_char_id(build.pk)
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(Char.objects.get(pk=build.pk).view_count, 0)


class SharedSolutionPageTests(TestCase):
    """End-to-end render of a shared solution page from a hand-built minimal
    solution (no solver run), guarding the view-count contract: one view is
    counted and modified_time must not move."""

    def _shared_build(self):
        import pickle as _pickle
        from django.contrib.auth.models import User
        from chardata.models import Char
        from fashionistapulp.modelresult import ModelResultMinimal
        owner = User.objects.create_user('star', 'st@test.local', 'pw-42-solid')
        input_ = {'options': {'ap_exo': False, 'mp_exo': False}, 'origin': 'generated', 'char_level': 200,
                  'base_stats_by_attr': {}, 'locked_equips': {}}
        minimal = ModelResultMinimal({}, input_, {})
        return Char.objects.create(
            name='Etoile', char_name='star', char_class='Iop',
            char_build='build', level=200,
            minimum_stats=b'', minimum_crits=b'', stats_weight=b'',
            options=b'', inclusions=b'', exclusions=b'',
            minimal_solution=_pickle.dumps(minimal),
            owner=owner, link_shared=True, game_version='dofus3')

    def test_shared_page_renders_and_counts_one_view(self):
        from chardata.models import Char
        from chardata.encoded_char_id import encode_char_id
        build = self._shared_build()
        before = Char.objects.get(pk=build.pk).modified_time
        resp = self.client.get('/s/star/%s/' % encode_char_id(build.pk))
        self.assertEqual(resp.status_code, 200)
        after = Char.objects.get(pk=build.pk)
        self.assertEqual(after.view_count, 1)
        self.assertEqual(after.modified_time, before,
                         'a mere view must not touch modified_time')

    def test_shared_page_shows_weighted_build_score_without_saving(self):
        import pickle as _pickle
        from django.contrib.auth.models import User
        from chardata.models import Char
        from chardata.encoded_char_id import encode_char_id
        from chardata.solution import get_solution
        from chardata.solution_scores import calculate_project_build_score
        from fashionistapulp.modelresult import ModelResultMinimal
        from fashionistapulp.structure import get_structure
        owner = User.objects.create_user('scorer', 'score@test.local', 'pw-42-solid')
        structure = get_structure('dofus3')
        hat = None
        scored_stat_key = None
        for candidate in structure.get_unique_items_by_type_and_level('Hat', 200):
            for stat_id, value in candidate.stats:
                stat = structure.get_stat_by_id(stat_id)
                if not candidate.removed and stat is not None and value > 0:
                    hat = candidate
                    scored_stat_key = stat.key
                    break
            if hat is not None:
                break
        self.assertIsNotNone(hat)
        input_ = {'options': {'ap_exo': False, 'mp_exo': False},
                  'origin': 'generated', 'char_level': 200,
                  'base_stats_by_attr': {},
                  'locked_equips': {}}
        build = Char.objects.create(
            name='Score', char_name='score', char_class='Iop',
            char_build='build', level=200,
            minimum_stats=b'', minimum_crits=b'',
            stats_weight=_pickle.dumps({scored_stat_key: 2}),
            options=b'', inclusions=b'', exclusions=b'',
            minimal_solution=_pickle.dumps(ModelResultMinimal({'hat': hat.id}, input_, {})),
            owner=owner, link_shared=True, game_version='dofus3')
        expected_score = calculate_project_build_score(build, get_solution(build))

        before = Char.objects.get(pk=build.pk).modified_time
        resp = self.client.get('/s/score/%s/' % encode_char_id(build.pk))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Build score')
        self.assertContains(resp, str(expected_score))
        self.assertEqual(Char.objects.get(pk=build.pk).modified_time, before,
                         'showing the score must not re-save shared builds')


class BuildScoreTests(SimpleTestCase):

    def test_public_score_weights_major_stats_more_than_elemental_points(self):
        from chardata.solution_scores import (GENERIC_BUILD_WEIGHTS,
                                              calculate_score_from_stats)
        ap_score = calculate_score_from_stats({'ap': 1, 'cha': 0}, GENERIC_BUILD_WEIGHTS)
        chance_score = calculate_score_from_stats({'ap': 0, 'cha': 1}, GENERIC_BUILD_WEIGHTS)
        self.assertGreater(ap_score, chance_score * 50)

    def test_project_score_uses_the_build_game_version(self):
        import pickle as _pickle
        from types import SimpleNamespace

        from chardata.solution_scores import calculate_project_build_score
        from fashionistapulp.structure import (get_current_game_version,
                                               set_current_game_version)

        class VersionAwareSolution:
            seen_game_version = None

            def get_stats_gear(self):
                self.seen_game_version = get_current_game_version()
                return {'ap': 1}

        set_current_game_version('dofus3')
        self.addCleanup(set_current_game_version, 'dofus3')
        solution = VersionAwareSolution()
        char = SimpleNamespace(
            stats_weight=_pickle.dumps({'ap': 1}),
            game_version='retro')

        score = calculate_project_build_score(char, solution)

        self.assertEqual(score, 1)
        self.assertEqual(solution.seen_game_version, 'retro')
        self.assertEqual(get_current_game_version(), 'dofus3')

    def test_public_score_can_be_scoped_to_a_game_version(self):
        from chardata.solution_scores import (GENERIC_BUILD_WEIGHTS,
                                              calculate_public_build_score)
        from fashionistapulp.structure import (get_current_game_version,
                                               set_current_game_version)

        class VersionAwareSolution:
            seen_game_version = None

            def get_stats_gear(self):
                self.seen_game_version = get_current_game_version()
                return {'ap': 1}

        set_current_game_version('dofus3')
        self.addCleanup(set_current_game_version, 'dofus3')
        solution = VersionAwareSolution()

        score = calculate_public_build_score(solution, 'touch')

        self.assertEqual(score, GENERIC_BUILD_WEIGHTS['ap'])
        self.assertEqual(solution.seen_game_version, 'touch')
        self.assertEqual(get_current_game_version(), 'dofus3')


class SolutionGenerationHistoryTests(TestCase):
    """Generated sets should be kept as private, comparable snapshots."""

    @staticmethod
    def _base_input():
        return {
            'options': {'ap_exo': False, 'mp_exo': False},
            'origin': 'generated',
            'char_level': 200,
            'base_stats_by_attr': {
                'Vitality': 0,
                'Wisdom': 0,
                'Strength': 0,
                'Intelligence': 0,
                'Chance': 0,
                'Agility': 0,
            },
            'locked_equips': {},
        }

    def _build_char_with_items(self):
        import pickle as _pickle
        from django.contrib.auth.models import User
        from chardata.models import Char
        from fashionistapulp.modelresult import ModelResultMinimal
        from fashionistapulp.structure import get_structure
        structure = get_structure('dofus3')
        hats = [
            item for item in structure.get_unique_items_by_type_and_level('Hat', 200)
            if not item.removed and item.ankama_id
        ][:12]
        self.assertGreaterEqual(len(hats), 2)
        owner = User.objects.create_user('historyowner', 'hist@test.local', 'pw-42-solid')
        current_minimal = ModelResultMinimal({'hat': hats[0].id}, self._base_input(), {})
        char = Char.objects.create(
            name='HistoryBuild', char_name='history', char_class='Iop',
            char_build='build', level=200,
            minimum_stats=b'', minimum_crits=b'',
            stats_weight=_pickle.dumps({'vit': 1, 'str': 1, 'int': 1, 'cha': 1, 'agi': 1}),
            options=b'', inclusions=b'', exclusions=b'',
            minimal_solution=_pickle.dumps(current_minimal),
            owner=owner, link_shared=True, game_version='dofus3')
        return owner, char, hats

    def test_record_solution_generation_keeps_last_ten(self):
        from chardata.models import SolutionGeneration
        from chardata.solution_history import record_solution_generation
        from fashionistapulp.modelresult import ModelResultMinimal
        owner, char, hats = self._build_char_with_items()

        created_ids = []
        for idx, hat in enumerate(hats):
            generation = record_solution_generation(
                char,
                ModelResultMinimal({'hat': hat.id}, self._base_input(), {'str': idx}))
            created_ids.append(generation.id)

        kept_ids = list(SolutionGeneration.objects
                        .filter(char=char)
                        .order_by('id')
                        .values_list('id', flat=True))
        self.assertEqual(len(kept_ids), 10)
        self.assertEqual(kept_ids, created_ids[-10:])

    def test_solution_page_lists_saved_generations(self):
        from chardata.solution_history import record_solution_generation
        from fashionistapulp.modelresult import ModelResultMinimal
        owner, char, hats = self._build_char_with_items()
        generation = record_solution_generation(
            char,
            ModelResultMinimal({'hat': hats[1].id}, self._base_input(), {}))
        self.client.force_login(owner)

        resp = self.client.get('/solution/%d/' % char.pk)

        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Recent generations')
        self.assertContains(resp, 'g%d' % generation.pk)
        self.assertContains(resp, 'Compare with current')

    def test_solution_history_shows_score_delta_against_current_build(self):
        import pickle as _pickle
        from chardata.solution import get_solution
        from chardata.solution_history import get_generation_solution, record_solution_generation
        from chardata.solution_scores import calculate_project_build_score
        from fashionistapulp.modelresult import ModelResultMinimal

        owner, char, hats = self._build_char_with_items()

        def minimal_for(hat):
            return ModelResultMinimal({'hat': hat.id}, self._base_input(), {})

        generation = None
        expected_delta = None
        for current_hat in hats:
            char.minimal_solution = _pickle.dumps(minimal_for(current_hat))
            char.save()
            current_score = calculate_project_build_score(char, get_solution(char))
            if current_score is None:
                continue
            for saved_hat in hats:
                if current_hat.id == saved_hat.id:
                    continue
                candidate = record_solution_generation(char, minimal_for(saved_hat))
                saved_score = calculate_project_build_score(
                    char, get_generation_solution(char, candidate))
                if saved_score is not None and saved_score != current_score:
                    generation = candidate
                    expected_delta = saved_score - current_score
                    break
            if generation is not None:
                break
        if generation is None:
            self.skipTest('no two test hats with different build scores')

        self.client.force_login(owner)

        resp = self.client.get('/solution/%d/' % char.pk)

        self.assertEqual(resp.status_code, 200)
        history = resp.context['generation_history']
        self.assertEqual(history[0]['id'], generation.id)
        self.assertTrue(history[0]['has_score'])
        self.assertTrue(resp.context['has_build_score'])
        expected_delta = history[0]['score'] - resp.context['build_score']
        expected_text = '+%d' % expected_delta if expected_delta > 0 else str(expected_delta)
        self.assertEqual(history[0]['score_delta'], expected_delta)
        self.assertEqual(history[0]['score_delta_text'], expected_text)
        self.assertContains(resp, expected_text)
        self.assertContains(resp, 'vs current')

    def test_generation_preview_uses_the_generation_game_version(self):
        import pickle as _pickle
        from django.contrib.auth.models import User
        from chardata.image_store import get_image_url
        from chardata.models import Char
        from chardata.solution_history import get_generation_preview_items
        from chardata.solution_history import record_solution_generation
        from fashionistapulp.modelresult import ModelResultMinimal
        from fashionistapulp.structure import get_structure
        from static_s3.templatetags.static_s3 import static

        retro = get_structure('retro')
        modern = get_structure('dofus3')
        retro_hat = None
        for candidate in retro.get_unique_items_by_type_and_level('Hat', 200):
            if candidate.removed:
                continue
            modern_item = modern.get_item_by_id(candidate.id)
            if modern_item is None or modern_item.name != candidate.name:
                retro_hat = candidate
                break
        self.assertIsNotNone(retro_hat)

        owner = User.objects.create_user('retrohistoryowner', 'retrohist@test.local',
                                         'pw-42-solid')
        char = Char.objects.create(
            name='RetroHistoryBuild', char_name='retrohistory', char_class='Iop',
            char_build='build', level=200,
            minimum_stats=b'', minimum_crits=b'',
            stats_weight=_pickle.dumps({'str': 1}),
            options=b'', inclusions=b'', exclusions=b'',
            minimal_solution=_pickle.dumps(
                ModelResultMinimal({'hat': retro_hat.id}, self._base_input(), {})),
            owner=owner, link_shared=True, game_version='retro')
        generation = record_solution_generation(
            char,
            ModelResultMinimal({'hat': retro_hat.id}, self._base_input(), {}))

        with translation.override('en'):
            preview = get_generation_preview_items(generation)

        self.assertEqual(len(preview), 1)
        self.assertEqual(preview[0]['name'],
                         retro.get_item_name_in_language(retro_hat, 'en'))
        expected_image_url = static(get_image_url(
            retro.get_type_name_by_id(retro_hat.type), retro_hat.name, 'retro'))
        self.assertEqual(preview[0]['image_url'], expected_image_url)

    def test_saved_generation_can_be_opened_compared_and_restored(self):
        import pickle as _pickle
        from chardata.solution_history import record_solution_generation
        from fashionistapulp.modelresult import ModelResultMinimal
        owner, char, hats = self._build_char_with_items()
        old_minimal = ModelResultMinimal({'hat': hats[1].id}, self._base_input(), {})
        generation = record_solution_generation(char, old_minimal)
        self.client.force_login(owner)

        snapshot_resp = self.client.get('/solutiongeneration/%d/%d/' % (char.pk, generation.pk))
        self.assertEqual(snapshot_resp.status_code, 200)
        self.assertContains(snapshot_resp, 'Viewing saved generation')
        self.assertContains(snapshot_resp, 'This is a saved generation')

        compare_resp = self.client.get('/compare_sets/%d/g%d/' % (char.pk, generation.pk))
        self.assertEqual(compare_resp.status_code, 200)
        self.assertEqual(compare_resp.context['char_ids'], [char.pk, 'g%d' % generation.pk])
        self.assertContains(compare_resp, 'Saved generation')

        restore_resp = self.client.post('/restoregeneration/%d/%d/' % (char.pk, generation.pk))
        self.assertEqual(restore_resp.status_code, 302)
        char.refresh_from_db()
        restored = _pickle.loads(char.minimal_solution)
        self.assertEqual(restored.item_per_slot.get('hat'), hats[1].id)

    def test_compare_post_accepts_generation_links(self):
        import json
        from chardata.solution_history import record_solution_generation
        from fashionistapulp.modelresult import ModelResultMinimal
        owner, char, hats = self._build_char_with_items()
        generation = record_solution_generation(
            char,
            ModelResultMinimal({'hat': hats[1].id}, self._base_input(), {}))
        self.client.force_login(owner)

        resp = self.client.post('/choose_compare_sets_post/',
                                {'links': json.dumps([
                                    '/solution/%d/' % char.pk,
                                    '/solutiongeneration/%d/%d/' % (char.pk, generation.pk),
                                ])})

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content.decode('utf-8'),
                         '/compare_sets/%d/g%d' % (char.pk, generation.pk))

    def test_generation_endpoints_deny_non_owners(self):
        # Saved generations are private snapshots: another logged-in user must not
        # be able to view them, restore them over the owner's build, or pull them
        # into a comparison, even when the owner's build itself is link-shared.
        import pickle as _pickle
        from django.contrib.auth.models import User
        from chardata.solution_history import record_solution_generation
        from fashionistapulp.modelresult import ModelResultMinimal
        owner, char, hats = self._build_char_with_items()
        generation = record_solution_generation(
            char,
            ModelResultMinimal({'hat': hats[1].id}, self._base_input(), {}))
        blob_before = bytes(char.minimal_solution)

        intruder = User.objects.create_user(
            'historyintruder', 'intruder@test.local', 'pw-42-solid')
        self.client.force_login(intruder)

        view_resp = self.client.get(
            '/solutiongeneration/%d/%d/' % (char.pk, generation.pk))
        self.assertEqual(view_resp.status_code, 403)

        restore_resp = self.client.post(
            '/restoregeneration/%d/%d/' % (char.pk, generation.pk))
        self.assertEqual(restore_resp.status_code, 403)
        char.refresh_from_db()
        self.assertEqual(bytes(char.minimal_solution), blob_before,
                         'a non-owner restore must not touch the stored solution')

        # The whole comparison collapses (<2 accessible builds) instead of leaking.
        compare_resp = self.client.get(
            '/compare_sets/%d/g%d/' % (char.pk, generation.pk))
        self.assertEqual(compare_resp.status_code, 404)


class SharedSolutionPageDeepTests(TestCase):
    """Same fixture as SharedSolutionPageTests but with a real item equipped:
    the page must show the item card, and switching an item on a char that has
    a solution must actually change the stored solution."""

    def _build_with_hat(self, owner):
        import pickle as _pickle
        from chardata.models import Char
        from fashionistapulp.modelresult import ModelResultMinimal
        from fashionistapulp.structure import get_structure
        s = get_structure('dofus3')
        hat = next(i for i in s.get_unique_items_by_type_and_level('Hat', 200)
                   if not i.removed and i.ankama_id)
        input_ = {'options': {'ap_exo': False, 'mp_exo': False},
                  'origin': 'generated', 'char_level': 200,
                  'base_stats_by_attr': {}, 'locked_equips': {}}
        minimal = ModelResultMinimal({'hat': hat.id}, input_, {})
        char = Char.objects.create(
            name='Casque', char_name='casque', char_class='Iop',
            char_build='build', level=200,
            minimum_stats=b'', minimum_crits=b'', stats_weight=b'',
            options=b'', inclusions=b'', exclusions=b'',
            minimal_solution=_pickle.dumps(minimal),
            owner=owner, link_shared=True, game_version='dofus3')
        return char, hat, s

    def test_shared_page_shows_the_equipped_item(self):
        from django.contrib.auth.models import User
        from chardata.encoded_char_id import encode_char_id
        owner = User.objects.create_user('capo', 'c2@test.local', 'pw-42-solid')
        char, hat, s = self._build_with_hat(owner)
        resp = self.client.get('/s/casque/%s/' % encode_char_id(char.pk))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, hat.name.split(' ')[0])

    def test_switch_item_replaces_the_slot(self):
        import pickle as _pickle
        from django.contrib.auth.models import User
        from chardata.models import Char
        owner = User.objects.create_user('switch2', 's2b@test.local', 'pw-42-solid')
        char, hat, s = self._build_with_hat(owner)
        other_hat = next(i for i in s.get_unique_items_by_type_and_level('Hat', 200)
                         if not i.removed and i.ankama_id and i.id != hat.id)
        self.client.force_login(owner)
        resp = self.client.post('/exchange/%d/' % char.pk,
                                {'itemName': other_hat.id, 'slot': 'hat'})
        self.assertEqual(resp.status_code, 200)
        char.refresh_from_db()
        minimal = _pickle.loads(char.minimal_solution)
        self.assertEqual(minimal.item_per_slot.get('hat'), other_hat.id)

    def test_remove_item_empties_the_slot(self):
        import pickle as _pickle
        from django.contrib.auth.models import User
        owner = User.objects.create_user('remover', 'rm@test.local', 'pw-42-solid')
        char, hat, s = self._build_with_hat(owner)
        self.client.force_login(owner)
        resp = self.client.post('/remove/%d/' % char.pk, {'slot': 'hat'})
        self.assertEqual(resp.status_code, 200)
        char.refresh_from_db()
        minimal = _pickle.loads(char.minimal_solution)
        self.assertIsNone(minimal.item_per_slot.get('hat'))


class CompareSetsSpellPreviewTests(TestCase):
    """The set comparison page should expose spell/weapon damage previews."""

    @staticmethod
    def _base_input():
        return {
            'options': {'ap_exo': False, 'mp_exo': False},
            'origin': 'generated',
            'char_level': 200,
            'base_stats_by_attr': {
                'Vitality': 0,
                'Wisdom': 0,
                'Strength': 0,
                'Intelligence': 0,
                'Chance': 0,
                'Agility': 0,
            },
            'locked_equips': {},
        }

    @staticmethod
    def _first_weapon(structure):
        for weapon_item in structure.get_unique_items_by_type_and_level('Weapon', 200):
            weapon = structure.get_weapon_by_name(weapon_item.name)
            if (not weapon_item.removed and weapon_item.ankama_id
                    and weapon is not None and weapon.non_crit_hits):
                return weapon_item
        return None

    @staticmethod
    def _stats(**overrides):
        stats = {'vit': 0, 'wis': 0, 'str': 0, 'int': 0, 'cha': 0, 'agi': 0}
        stats.update(overrides)
        return stats

    def _build(self, owner, name, item_per_slot, stats=None, game_version='dofus3'):
        import pickle as _pickle
        from chardata.models import Char
        from fashionistapulp.modelresult import ModelResultMinimal
        return Char.objects.create(
            name=name, char_name=name.lower(), char_class='Iop',
            char_build='build', level=200,
            minimum_stats=b'', minimum_crits=b'', stats_weight=b'',
            options=b'', inclusions=b'', exclusions=b'',
            minimal_solution=_pickle.dumps(ModelResultMinimal(
                item_per_slot, self._base_input(), stats or {})),
            owner=owner, link_shared=True, game_version=game_version)

    def test_compare_sets_includes_spell_damage_preview_payloads(self):
        from django.contrib.auth.models import User
        from fashionistapulp.structure import get_structure, set_current_game_version
        set_current_game_version('dofus3')
        structure = get_structure('dofus3')
        weapon = self._first_weapon(structure)
        self.assertIsNotNone(weapon, 'no renderable test weapon found')
        owner = User.objects.create_user('damagecompare', 'dc@test.local', 'pw-42-solid')
        first = self._build(owner, 'DamageOne', {'weapon': weapon.id}, self._stats(str=0))
        second = self._build(owner, 'DamageTwo', {'weapon': weapon.id}, self._stats(str=250))
        self.client.force_login(owner)

        resp = self.client.get('/compare_sets/%d/%d/' % (first.pk, second.pk))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode('utf-8', 'replace')
        self.assertIn('Spell damage preview', html)
        self.assertIn('compareSpellDigests', html)
        self.assertIn('compareWeaponDigests', html)
        self.assertIn('compareCharLevels', html)
        self.assertIn('spell_damage_weapon_%d' % first.pk, html)
        self.assertIn('name="spell_class"', html)
        self.assertIn('allCharIds.length > 1 && bestChars.length > 0', html)

    def test_compare_sets_can_choose_spell_preview_class(self):
        from django.contrib.auth.models import User
        owner = User.objects.create_user('spellclasscompare', 'scc@test.local', 'pw-42-solid')
        first = self._build(owner, 'ClassOne', {}, self._stats(str=0))
        second = self._build(owner, 'ClassTwo', {}, self._stats(str=250))
        self.client.force_login(owner)

        resp = self.client.get(
            '/compare_sets/%d/%d/' % (first.pk, second.pk),
            {'spell_class': 'Cra'})
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode('utf-8', 'replace')
        self.assertEqual(resp.context['spell_preview_selected_class'], 'Cra')
        self.assertRegex(
            html,
            r'<option(?=[^>]*\bvalue="Cra")(?=[^>]*\bselected(?:=""|(?=[\s>])))[^>]*>')

    def test_compare_sets_can_choose_single_spell_preview(self):
        from django.contrib.auth.models import User
        from chardata.compare_sets_view import _spell_has_direct_damage
        from chardata.spell_buffs import get_damage_spells_for_version
        cra_spell = next(
            spell for spell in get_damage_spells_for_version('dofus3')['Cra']
            if _spell_has_direct_damage(spell))
        owner = User.objects.create_user('spellpickcompare', 'spc@test.local', 'pw-42-solid')
        first = self._build(owner, 'SpellOne', {}, self._stats(str=0))
        second = self._build(owner, 'SpellTwo', {}, self._stats(str=250))
        self.client.force_login(owner)

        resp = self.client.get(
            '/compare_sets/%d/%d/' % (first.pk, second.pk),
            {'spell_class': 'Cra', 'spell_name': cra_spell.name})

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['spell_preview_selected_spell'], cra_spell.name)
        spell_rows = [
            row for row in resp.context['spell_preview_rows']
            if row['kind'] == 'spell'
        ]
        self.assertEqual(len(spell_rows), 1)
        html = resp.content.decode('utf-8', 'replace')
        self.assertIn('name="spell_name"', html)
        self.assertIn('spell_class=Cra', resp.context['compare_link_shared'])
        self.assertIn('spell_name=', resp.context['compare_link_shared'])

        share_resp = self.client.get(
            '/get_compare_sharing_link/%d/%d/' % (first.pk, second.pk),
            {'spell_class': 'Cra', 'spell_name': cra_spell.name})
        self.assertEqual(share_resp.status_code, 200)
        self.assertIn('spell_class=Cra', share_resp.content.decode('utf-8'))
        self.assertIn('spell_name=', share_resp.content.decode('utf-8'))

    def test_retro_compare_uses_retro_spell_payloads(self):
        from django.contrib.auth.models import User
        from fashionistapulp.structure import set_current_game_version
        set_current_game_version('retro')
        self.addCleanup(set_current_game_version, 'dofus3')
        owner = User.objects.create_user('retrocompare', 'rc@test.local', 'pw-42-solid')
        first = self._build(owner, 'RetroOne', {}, game_version='retro')
        second = self._build(owner, 'RetroTwo', {}, game_version='retro')
        self.client.force_login(owner)

        resp = self.client.get('/retro/compare_sets/%d/%d/' % (first.pk, second.pk))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode('utf-8', 'replace')
        self.assertIn('Spell damage preview', html)
        self.assertIn('chardata/spells/retro/', html)

    def test_retro_compare_item_popup_uses_versioned_stats_endpoint(self):
        from django.contrib.auth.models import User
        from fashionistapulp.structure import set_current_game_version
        set_current_game_version('retro')
        self.addCleanup(set_current_game_version, 'dofus3')
        owner = User.objects.create_user('retropopup', 'rp@test.local', 'pw-42-solid')
        first = self._build(owner, 'RetroPopupOne', {}, game_version='retro')
        second = self._build(owner, 'RetroPopupTwo', {}, game_version='retro')
        self.client.force_login(owner)

        resp = self.client.get('/retro/compare_sets/%d/%d/' % (first.pk, second.pk))

        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode('utf-8', 'replace')
        self.assertIn('var compareItemStatsUrl = "/retro/get_item_stats_compare/";', html)

    def test_retro_compare_hides_dead_stat_rows(self):
        from django.contrib.auth.models import User
        from fashionistapulp.structure import set_current_game_version
        set_current_game_version('retro')
        self.addCleanup(set_current_game_version, 'dofus3')
        owner = User.objects.create_user('retrodeadstats', 'rds@test.local', 'pw-42-solid')
        first = self._build(owner, 'RetroDeadOne', {}, game_version='retro')
        second = self._build(owner, 'RetroDeadTwo', {}, game_version='retro')
        self.client.force_login(owner)

        resp = self.client.get('/retro/compare_sets/%d/%d/' % (first.pk, second.pk))

        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode('utf-8', 'replace')
        self.assertNotIn('stat_value_cridam_', html)
        self.assertNotIn('stat_value_apred_', html)
        self.assertNotIn('stat_value_lock_', html)
        self.assertIn('stat_value_trapdam_', html)

    def test_touch_compare_hides_touch_dead_stat_rows(self):
        from django.contrib.auth.models import User
        from fashionistapulp.structure import set_current_game_version
        set_current_game_version('touch')
        self.addCleanup(set_current_game_version, 'dofus3')
        owner = User.objects.create_user('touchdeadstats', 'tds@test.local', 'pw-42-solid')
        first = self._build(owner, 'TouchDeadOne', {}, game_version='touch')
        second = self._build(owner, 'TouchDeadTwo', {}, game_version='touch')
        self.client.force_login(owner)

        resp = self.client.get('/touch/compare_sets/%d/%d/' % (first.pk, second.pk))

        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode('utf-8', 'replace')
        self.assertNotIn('stat_value_trapdam_', html)
        self.assertNotIn('stat_value_trapdamper_', html)
        self.assertNotIn('stat_value_permedam_', html)
        self.assertIn('stat_value_cridam_', html)

    def test_dofus3_compare_keeps_stat_rows(self):
        from django.contrib.auth.models import User
        owner = User.objects.create_user('modernstats', 'modernstats@test.local',
                                         'pw-42-solid')
        first = self._build(owner, 'ModernOne', {})
        second = self._build(owner, 'ModernTwo', {})
        self.client.force_login(owner)

        resp = self.client.get('/compare_sets/%d/%d/' % (first.pk, second.pk))

        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode('utf-8', 'replace')
        self.assertIn('stat_value_cridam_', html)
        self.assertIn('stat_value_apred_', html)
        self.assertIn('stat_value_lock_', html)
        self.assertIn('stat_value_trapdam_', html)


class InlineScriptSyntaxTests(TestCase):
    """Syntax-check every inline script of the key pages with node. A single
    stray quote in a jQuery string can kill a whole page's JS silently, so this
    catches it before it ships."""

    @unittest.skipIf(shutil.which('node') is None, 'node not installed')
    def test_inline_scripts_parse(self):
        import pickle as _pickle
        import subprocess, tempfile
        from django.contrib.auth.models import User
        from chardata.models import Char
        from chardata.encoded_char_id import encode_char_id
        from fashionistapulp.modelresult import ModelResultMinimal
        from fashionistapulp.structure import get_structure, set_current_game_version
        set_current_game_version('dofus3')
        s = get_structure('dofus3')
        hat = next(i for i in s.get_unique_items_by_type_and_level('Hat', 200)
                   if not i.removed and i.ankama_id)
        input_ = {'options': {'ap_exo': False, 'mp_exo': False},
                  'origin': 'generated', 'char_level': 200,
                  'base_stats_by_attr': {}, 'locked_equips': {}}
        owner = User.objects.create_user('jsowner', 'js@test.local', 'pw-42-solid')
        char = Char.objects.create(
            name='JsCheck', char_name='jscheck', char_class='Iop',
            char_build='build', level=200,
            minimum_stats=b'', minimum_crits=b'', stats_weight=b'',
            options=b'', inclusions=b'', exclusions=b'',
            minimal_solution=_pickle.dumps(ModelResultMinimal({'hat': hat.id}, input_, {})),
            owner=owner, link_shared=True, game_version='dofus3')
        char2 = Char.objects.create(
            name='JsCheckTwo', char_name='jschecktwo', char_class='Iop',
            char_build='build', level=200,
            minimum_stats=b'', minimum_crits=b'', stats_weight=b'',
            options=b'', inclusions=b'', exclusions=b'',
            minimal_solution=_pickle.dumps(ModelResultMinimal(
                {'hat': hat.id}, input_,
                {'vit': 0, 'wis': 0, 'str': 100, 'int': 0, 'cha': 0, 'agi': 0})),
            owner=owner, link_shared=True, game_version='dofus3')
        self.client.force_login(owner)

        pages = ['/', '/encyclopedia/', '/sharedbuilds/',
                 '/s/jscheck/%s/' % encode_char_id(char.pk),
                 '/solution/%d/' % char.pk,
                 '/compare_sets/%d/%d/' % (char.pk, char2.pk),
                 '/wizard/%d/' % char.pk,
                 '/setup/%d/' % char.pk,
                 '/spells/%d/' % char.pk,
                 '/min_stats/%d/' % char.pk,
                 '/inclusions/%d/' % char.pk,
                 '/exclusions/%d/' % char.pk,
                 '/forgemagie/', '/inventory/', '/workshop/',
                 '/choose_compare_sets/', '/manageaccount/']
        # Extract inline scripts with a real HTML tokenizer instead of a regexp: a
        # regexp can never match every script end tag the browser accepts (</script >,
        # </script\t\nbar>, ...), so html.parser is both correct and CodeQL-clean.
        from html.parser import HTMLParser

        class _InlineScripts(HTMLParser):
            def __init__(self):
                super().__init__(convert_charrefs=False)
                self.scripts = []
                self._keep = False

            def handle_starttag(self, tag, attrs):
                if tag == 'script':
                    self._keep = not any(k == 'src' for k, _ in attrs)
                    if self._keep:
                        self.scripts.append('')

            def handle_endtag(self, tag):
                if tag == 'script':
                    self._keep = False

            def handle_data(self, data):
                if self._keep:
                    self.scripts[-1] += data

        for page in pages:
            resp = self.client.get(page)
            self.assertEqual(resp.status_code, 200, page)
            html = resp.content.decode('utf-8', 'replace')
            collector = _InlineScripts()
            collector.feed(html)
            collector.close()
            for idx, script in enumerate(collector.scripts):
                if not script.strip():
                    continue
                # JSON-LD blocks are collected too; they are not JS.
                if script.lstrip().startswith('{'):
                    continue
                with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False,
                                                 encoding='utf-8') as f:
                    f.write(script)
                    path = f.name
                try:
                    proc = subprocess.run(['node', '--check', path],
                                          capture_output=True, text=True)
                    self.assertEqual(
                        proc.returncode, 0,
                        'inline script %d of %s does not parse:\n%s'
                        % (idx, page, proc.stderr[:800]))
                finally:
                    os.unlink(path)

class JqueryStringQuoteLintTests(SimpleTestCase):
    """No empty double-quoted attribute inside a double-quoted jQuery string:
    it closes the string early and kills the inline script. Scans every template,
    including the admin pages the render-based node check can't reach."""

    def test_no_empty_double_quoted_attr_in_jquery_string(self):
        template_dir = os.path.join(os.path.dirname(__file__), 'templates')
        bad_re = re.compile(r'\$\("[^"]*=""')
        offenders = []
        for path in glob.glob(os.path.join(template_dir, '**', '*.html'),
                              recursive=True):
            with open(path, encoding='utf-8') as f:
                for lineno, line in enumerate(f, 1):
                    if bad_re.search(line):
                        offenders.append(
                            '%s:%d' % (os.path.relpath(path, template_dir), lineno))
        self.assertEqual(
            offenders, [],
            'empty double-quoted attribute inside a double-quoted jQuery string '
            'breaks the whole inline script:\n' + '\n'.join(offenders))


class GelanoExoDisplayLintTests(SimpleTestCase):
    """mp_exo can be the string "gelano" (the MP then comes from equipping the
    Gelano ring, not a free exo). The solution page's exo display must test it
    strictly (=== true) or 'gelano' shows a phantom "+1" on MP (reported bug)."""

    def test_solution_exo_display_uses_strict_equality(self):
        path = os.path.join(os.path.dirname(__file__), 'templates',
                            'chardata', 'solution.html')
        with open(path, encoding='utf-8') as f:
            src = f.read()
        self.assertNotIn('options["mp_exo"] ? 1', src)
        self.assertNotIn('baseOptions["mp_exo"] ? ', src)
        self.assertIn('options["mp_exo"] === true', src)


class RetroSoftCapsTests(SimpleTestCase):
    """Retro (1.29) spends characteristic points on class-specific tables; every
    other version keeps the uniform modern table. Costs verified against the
    129dofus wiki 'Soft Cap' page (cross-checked with dofuzion)."""

    _TIER_COST = [0.5, 1, 2, 3, 4, 5]

    def _capital_cost(self, caps, target):
        # Mirror the model's per-tier width computation, then walk the tiers
        # cheapest-first to reach `target` stat points.
        widths = []
        for i in range(6):
            if i >= 1 and caps[i - 1] is not None and caps[i] is not None:
                widths.append(caps[i] - caps[i - 1])
            else:
                widths.append(caps[i])  # None == unlimited
        remaining, cost = target, 0.0
        for i in range(6):
            take = remaining if widths[i] is None else min(remaining, widths[i])
            cost += take * self._TIER_COST[i]
            remaining -= take
            if remaining <= 0:
                break
        return cost

    def test_retro_costs_match_the_wiki(self):
        from fashionistapulp.dofus_constants import get_soft_caps_for
        cases = [
            ('Sacrier', 'vit', 200, 100),   # 1 point for 2 vitality
            ('Iop', 'vit', 100, 100),       # everyone else 1:1
            ('Iop', 'wis', 100, 300),       # wisdom 3:1 for all
            ('Iop', 'str', 100, 100), ('Iop', 'str', 200, 300), ('Iop', 'str', 400, 1000),
            ('Pandawa', 'str', 200, 350), ('Pandawa', 'str', 300, 650),
            ('Sacrier', 'str', 100, 300), ('Sacrier', 'str', 150, 500),
            ('Sadida', 'str', 300, 600), ('Enutrof', 'cha', 230, 440),
            ('Eniripsa', 'str', 50, 100),
        ]
        for char_class, stat, target, expected in cases:
            caps = get_soft_caps_for('retro', char_class)[stat]
            self.assertEqual(self._capital_cost(caps, target), expected,
                             '%s %s to %d' % (char_class, stat, target))

    def test_retro_covers_the_twelve_classes(self):
        from fashionistapulp.dofus_constants import SOFT_CAPS_RETRO
        retro_classes = {'Cra', 'Ecaflip', 'Eniripsa', 'Enutrof', 'Feca', 'Iop',
                         'Osamodas', 'Pandawa', 'Sacrier', 'Sadida', 'Sram', 'Xelor'}
        self.assertEqual(set(SOFT_CAPS_RETRO), retro_classes)
        for caps in SOFT_CAPS_RETRO.values():
            self.assertEqual(set(caps), {'vit', 'wis', 'str', 'int', 'cha', 'agi'})
            for lis in caps.values():
                self.assertEqual(len(lis), 6)

    def test_modern_versions_keep_the_uniform_modern_table(self):
        from fashionistapulp.dofus_constants import get_soft_caps_for, SOFT_CAPS
        for version in ('dofus3', 'beta', 'dofus2'):
            for char_class in ('Iop', 'Sacrier', 'Cra', 'Sram'):
                self.assertEqual(get_soft_caps_for(version, char_class),
                                 SOFT_CAPS[char_class],
                                 '%s / %s should be unchanged' % (version, char_class))


class TouchSoftCapsTests(SimpleTestCase):
    """Dofus Touch keeps its own 2.x-era characteristic costs (from its game
    files touch_raw/Breeds_fr.json): one uniform table for every class where the
    elements and Wisdom scale 1/2/3/4/5 at 100/200/300/400 and Vitality is 1:1.
    Notably Wisdom is distributable and cheap early, unlike modern's flat 3:1."""

    _TIER_COST = [0.5, 1, 2, 3, 4, 5]

    def _capital_cost(self, caps, target):
        widths = []
        for i in range(6):
            if i >= 1 and caps[i - 1] is not None and caps[i] is not None:
                widths.append(caps[i] - caps[i - 1])
            else:
                widths.append(caps[i])
        remaining, cost = target, 0.0
        for i in range(6):
            take = remaining if widths[i] is None else min(remaining, widths[i])
            cost += take * self._TIER_COST[i]
            remaining -= take
            if remaining <= 0:
                break
        return cost

    def test_touch_costs_match_the_game_files(self):
        from fashionistapulp.dofus_constants import get_soft_caps_for
        cases = [
            ('str', 100, 100), ('str', 200, 300), ('str', 400, 1000),
            ('wis', 100, 100), ('wis', 300, 600),   # Touch wisdom is cheap early
            ('vit', 100, 100), ('vit', 500, 500),   # flat 1:1
        ]
        for stat, target, expected in cases:
            caps = get_soft_caps_for('touch', 'Iop')[stat]
            self.assertEqual(self._capital_cost(caps, target), expected,
                             'touch %s to %d' % (stat, target))

    def test_touch_wisdom_is_cheaper_than_modern(self):
        from fashionistapulp.dofus_constants import get_soft_caps_for
        touch = self._capital_cost(get_soft_caps_for('touch', 'Iop')['wis'], 100)
        modern = self._capital_cost(get_soft_caps_for('dofus3', 'Iop')['wis'], 100)
        self.assertEqual(touch, 100)   # 1:1 first tier
        self.assertEqual(modern, 300)  # flat 3:1
        self.assertLess(touch, modern)

    def test_touch_is_uniform_across_classes(self):
        from fashionistapulp.dofus_constants import get_soft_caps_for
        self.assertEqual(get_soft_caps_for('touch', 'Iop'),
                         get_soft_caps_for('touch', 'Sadida'))

    def test_only_sacrier_gets_cheap_vitality_in_retro(self):
        from fashionistapulp.dofus_constants import get_soft_caps_for
        # Sacrier reaches 100 vitality for 50 capital points; everyone else 100.
        self.assertEqual(
            self._capital_cost(get_soft_caps_for('retro', 'Sacrier')['vit'], 100), 50)
        for char_class in ('Iop', 'Cra', 'Feca', 'Pandawa'):
            self.assertEqual(
                self._capital_cost(get_soft_caps_for('retro', char_class)['vit'], 100),
                100, char_class)

    def _capital_for_extra(self, caps, scrolled, extra):
        # Capital cost of adding `extra` points on top of a `scrolled` base.
        from fashionistapulp.dofus_constants import tier_widths_after_scroll
        widths = tier_widths_after_scroll(caps, scrolled)
        remaining, cost = extra, 0.0
        for i in range(6):
            take = remaining if widths[i] is None else min(remaining, widths[i])
            cost += take * self._TIER_COST[i]
            remaining -= take
            if remaining <= 0:
                break
        return cost

    def test_scrolls_push_points_up_the_cost_curve(self):
        # Reported bug: an Iop scrolled to 100 Intelligence was charged 1:1 for the
        # next point. Scrolls are free stat but still climb the curve, so it is 5:1.
        from fashionistapulp.dofus_constants import get_soft_caps_for
        iop_int = get_soft_caps_for('retro', 'Iop')['int']
        self.assertEqual(self._capital_for_extra(iop_int, 0, 1), 1)      # fresh: 1:1
        self.assertEqual(self._capital_for_extra(iop_int, 100, 1), 5)    # scrolled: 5:1
        self.assertEqual(self._capital_for_extra(iop_int, 100, 10), 50)
        # 30 base sits 10 into the 2:1 tier.
        self.assertEqual(self._capital_for_extra(iop_int, 30, 1), 2)
        # Modern is affected too: scrolled to 100 the next Strength point is 2:1.
        modern_str = get_soft_caps_for('dofus3', 'Iop')['str']
        self.assertEqual(self._capital_for_extra(modern_str, 100, 1), 2)
        # 1:1 stats (vitality) never get pricier from scrolling.
        self.assertEqual(self._capital_for_extra(get_soft_caps_for('retro', 'Iop')['vit'], 100, 1), 1)


class UnobtainableItemsTests(SimpleTestCase):
    """Joke/unobtainable items (reported: Le Divhugalch, a +3 AP/+3 MP retro staff)
    are forbidden by default through the standard mechanism, so the solver never
    picks them yet a user can still remove them from the forbidden list."""

    def test_le_divhugalch_forbidden_by_default_but_still_available_in_retro(self):
        from fashionistapulp.structure import get_structure, set_current_game_version
        from chardata.lock_forbid import get_default_exclusions
        set_current_game_version('retro')
        s = get_structure('retro')
        item = s.get_item_by_ankama_id(11761)
        self.assertIsNotNone(item, 'Le Divhugalch missing from retro data')
        # Forbidden by default, so it is never proposed...
        self.assertIn(item.id, get_default_exclusions(char=None))
        # ...but still in the pool, so it can be un-forbidden by hand.
        self.assertIn(item.id, {it.id for it in s.get_available_items_list()})

    def test_gm_items_forbidden_by_default(self):
        # Staff-only items (GM suffix) exist in the scraped data of several
        # versions but no player can obtain them, so the solver must not
        # propose them (reported after the Touch pet pool review).
        from fashionistapulp.structure import get_structure, set_current_game_version
        from chardata.lock_forbid import get_default_exclusions
        gm_ankama_ids = (6894,   # Ultra-powerful Combat Bow Meow (GM)
                        6895,   # Small Combat Bow Meow (GM)
                        7913,   # Animagi (GM)
                        7920)   # Tournament Wand (GM)
        for version in ('touch', 'dofus3'):
            set_current_game_version(version)
            structure = get_structure(version)
            defaults = set(get_default_exclusions(char=None))
            for ankama_id in gm_ankama_ids:
                item = structure.get_item_by_ankama_id(ankama_id)
                if item is None:
                    continue  # not every GM item exists in every version
                self.assertIn(item.id, defaults,
                              '%s (%s) should be forbidden by default on %s'
                              % (item.name, ankama_id, version))


class OfficialNamePunctuationTests(SimpleTestCase):
    """The dofus3/beta transform used to strip Windows-forbidden characters
    from the displayed EN name ("Wand Else" instead of "Wand Else?"); only
    icon filenames need that. Lock the official punctuation so a future
    pipeline run cannot regress it."""

    def test_names_keep_their_official_punctuation(self):
        from fashionistapulp.structure import get_structure
        for version in ('dofus3', 'beta'):
            s = get_structure(version)
            for name in ('Wand Else?', 'Plushy-Ball: Tofu'):
                self.assertIsNotNone(
                    s.get_item_by_name(name),
                    '%r missing on %s: display-name sanitization regressed?'
                    % (name, version))


class VersionItemAvailabilityTests(SimpleTestCase):
    """Items in a version's data that shouldn't be proposed there are forbidden by
    default per version, without touching the versions where they are real
    (reported: the Hispanic shield was offered on Dofus Touch)."""

    def test_hispanic_shield_forbidden_by_default_on_touch_not_on_retro(self):
        from fashionistapulp.structure import get_structure, set_current_game_version
        from chardata.lock_forbid import get_default_exclusions
        set_current_game_version('touch')
        touch = get_structure('touch')
        shield = touch.get_item_by_ankama_id(10076)
        self.assertIsNotNone(shield, 'Hispanic shield missing from Touch data')
        # Forbidden by default on Touch...
        self.assertIn(shield.id, get_default_exclusions(char=None))
        # ...but still in the pool, so it can be un-forbidden by hand.
        self.assertIn(shield.id, {it.id for it in touch.get_available_items_list()})
        # On Retro it is a genuine item: not force-forbidden.
        set_current_game_version('retro')
        retro = get_structure('retro')
        self.assertNotIn(retro.get_item_by_ankama_id(10076).id,
                         get_default_exclusions(char=None))

    def test_sourceless_touch_shields_are_forbidden_by_default(self):
        # Shields in the Touch client data with no obtention source there
        # (no recipe, no drop) are 2.x PC leftovers never distributed on
        # Touch: every one of them must be in the touch defaults. The list
        # is recomputed from the data so a future re-scrape keeps it honest.
        import sqlite3
        from fashionistapulp.fashionista_config import get_items_db_path
        from fashionistapulp.structure import get_structure, set_current_game_version
        from chardata.lock_forbid import get_default_exclusions

        conn = sqlite3.connect(get_items_db_path('touch'))
        try:
            rows = conn.execute("""
                SELECT i.id, i.name FROM items i
                JOIN item_types it ON it.id = i.type
                WHERE it.name = 'Shield'
                  AND NOT EXISTS (SELECT 1 FROM item_recipes r WHERE r.item = i.id)
                  AND NOT EXISTS (SELECT 1 FROM item_drops d WHERE d.item = i.id)
                """).fetchall()
        finally:
            conn.close()
        self.assertTrue(rows, 'expected sourceless shields in the touch data')

        set_current_game_version('touch')
        self.addCleanup(set_current_game_version, 'dofus3')
        structure = get_structure('touch')
        defaults = set(get_default_exclusions(char=None))
        pool = {it.id for it in structure.get_available_items_list()}
        for item_id, name in rows:
            self.assertIn(item_id, defaults,
                          '%s has no Touch obtention source but is proposable' % name)
            # Still in the pool: a player who owns one can un-forbid it.
            self.assertIn(item_id, pool, name)

    def test_ice_dofus_forbidden_by_default_on_retro_not_on_dofus3(self):
        from fashionistapulp.structure import get_structure, set_current_game_version
        from chardata.lock_forbid import get_default_exclusions
        # The Ice Dofus does not exist in 1.29; it was scraped into Retro as a
        # bogus level 1 Dofus, so it is forbidden by default there.
        set_current_game_version('retro')
        retro = get_structure('retro')
        ice = retro.get_item_by_ankama_id(7043)
        self.assertIsNotNone(ice, 'Ice Dofus missing from Retro data')
        self.assertIn(ice.id, get_default_exclusions(char=None))
        # But it is a real Dofus on Dofus 3: not force-forbidden there.
        set_current_game_version('dofus3')
        dofus3 = get_structure('dofus3')
        self.assertNotIn(dofus3.get_item_by_ankama_id(7043).id,
                         get_default_exclusions(char=None))

    def test_grobouclier_forbidden_by_default_on_retro(self):
        from fashionistapulp.structure import get_structure, set_current_game_version
        from chardata.lock_forbid import get_default_exclusions
        # The Grobouclier (Nolifishield) is a Grobe dungeon-key shield players
        # do not build with; hidden by default on Retro but still removable.
        set_current_game_version('retro')
        retro = get_structure('retro')
        shield = retro.get_item_by_ankama_id(13171)
        self.assertIsNotNone(shield, 'Grobouclier missing from Retro data')
        self.assertIn(shield.id, get_default_exclusions(char=None))
        self.assertIn(shield.id, {it.id for it in retro.get_available_items_list()})


class TrophyFlagTests(SimpleTestCase):
    """Trophies share the Dofus slot but carry a 'Trophy' flag (written by the data
    pipeline from the source's Trophy type) so the "no trophies" option can forbid
    them without touching real Dofuses."""

    def test_trophies_flagged_but_not_real_dofuses(self):
        from fashionistapulp.structure import get_structure
        for ver in ('dofus3', 'touch', 'dofus2', 'beta'):
            s = get_structure(ver)
            dofus_type = s.get_type_id_by_name('Dofus')
            in_slot = [it for it in s.get_available_items_list()
                       if it.type == dofus_type]
            flagged = [it for it in in_slot if 'Trophy' in it.flags]
            self.assertGreater(len(flagged), 100,
                               '%s should flag its trophies' % ver)
            emerald = s.get_item_by_name('Emerald Dofus')
            self.assertNotIn('Trophy', emerald.flags,
                             '%s flagged a real Dofus as a trophy' % ver)


class WizardTrophyOptionTests(TestCase):
    """The 'no trophies' toggle must show on the wizard too, not just the options
    page (reported missing on /wizard/). It rides the same options plumbing."""

    def test_wizard_shows_trophies_checkbox(self):
        import pickle
        from django.contrib.auth.models import User
        from chardata.models import Char
        owner = User.objects.create_user('wiztrophy', 'wt@test.local', 'pw-wiz-77')
        char = Char.objects.create(
            name='Wiz', char_name='wiz', char_class='Iop', char_build='build',
            level=200, minimum_stats=b'', minimum_crits=b'', stats_weight=b'',
            options=b'', inclusions=b'', exclusions=b'', aspects=pickle.dumps({'str'}),
            owner=owner, link_shared=False, game_version='dofus3')
        self.client.force_login(owner)
        resp = self.client.get('/wizard/%d/' % char.pk)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'name="trophies"')


class RetroShieldsDefaultTests(TestCase):
    """Retro shields only work in PvP, so a PvM preset forbids them by default;
    the PvP preset (and every non-retro version) keeps them."""

    def _created_options(self, aspects, version):
        import pickle
        from django.test import RequestFactory
        from django.contrib.auth.models import User
        from fashionistapulp.structure import set_current_game_version
        from chardata.coaching_view import create_build
        set_current_game_version(version)
        user = User.objects.create_user(
            'shield_%s_%s' % (version, '_'.join(sorted(aspects))),
            'sh@test.local', 'pw-shield-77')
        req = RequestFactory().post('/')
        req.user = user
        char = create_build(req, 'Iop', 100, set(aspects), version)
        return pickle.loads(char.options)

    def test_retro_pvm_forbids_shields(self):
        self.assertFalse(self._created_options({'res', 'vit', 'str'}, 'retro')['shields'])

    def test_retro_pvp_keeps_shields(self):
        self.assertTrue(self._created_options({'pvp', 'crit', 'str'}, 'retro')['shields'])

    def test_modern_pvm_keeps_shields(self):
        self.assertTrue(self._created_options({'res', 'vit', 'str'}, 'dofus3')['shields'])


class FullScrollRetroTests(TestCase):
    """Scroll caps per version: Touch 150 (Dedale, update 1.73), Retro 101,
    every other version 100. The 'full parcho' button honours the version cap."""

    def _full_scroll_values(self, version):
        from django.test import RequestFactory
        from django.contrib.auth.models import User
        from fashionistapulp.structure import set_current_game_version
        from chardata.coaching_view import create_build
        from chardata.wizard_view import _full_scroll_char
        from chardata.models import CharBaseStats
        set_current_game_version(version)
        user = User.objects.create_user(
            'scroll_%s' % version, 'sc@test.local', 'pw-scroll-77')
        req = RequestFactory().post('/')
        req.user = user
        char = create_build(req, 'Iop', 200, {'str'}, version)
        _full_scroll_char(char)
        return set(b.scrolled_value for b in CharBaseStats.objects.filter(char=char))

    def test_touch_full_scroll_is_150(self):
        self.assertEqual(self._full_scroll_values('touch'), {150})

    def test_retro_full_scroll_is_101(self):
        self.assertEqual(self._full_scroll_values('retro'), {101})

    def test_modern_full_scroll_is_100(self):
        self.assertEqual(self._full_scroll_values('dofus3'), {100})


class VersionWeightTuningTests(SimpleTestCase):
    """Each game version is a different game: the smart-build weights zero the
    stats that version's item pool does not carry, and encode 1.29 mechanics
    (wisdom as the AP/MP defense stat, rarer % resistance gear, stronger
    initiative). The Dofus 3 engine itself must not move."""

    def _weights(self, version, aspects, race='Iop'):
        from types import SimpleNamespace
        from chardata.smart_build import _set_weights
        char = SimpleNamespace(char_class=race, level=200, game_version=version)
        return _set_weights(char, aspects, apply=False)

    def test_dead_stats_are_zeroed_per_version(self):
        for version, dead in (
                ('retro', ('cridam', 'apres', 'mpres', 'apred', 'mpred', 'lock')),
                ('touch', ('permedam', 'perrandam', 'perweadam', 'perspedam',
                           'respermee', 'resperran')),
                ('dofus2', ('ref',))):
            w = self._weights(version, {'str'})
            for key in dead:
                if key in w:
                    self.assertEqual(w[key], 0,
                                     '%s should weigh 0 on %s' % (key, version))

    def test_dofus3_engine_unchanged(self):
        w = self._weights('dofus3', {'str'})
        for key in ('cridam', 'permedam', 'apres', 'earthresper'):
            self.assertGreater(w[key], 0, key)

    def test_retro_mechanics_differ_from_dofus3(self):
        w3 = self._weights('dofus3', {'str'})
        wr = self._weights('retro', {'str'})
        self.assertGreater(wr['wis'], w3['wis'])
        self.assertGreater(wr['init'], w3['init'])
        self.assertLess(wr['earthresper'], w3['earthresper'])

    def test_retro_ap_mp_defense_routes_through_wisdom(self):
        w = self._weights('retro', {'str', 'aprape'})
        self.assertGreaterEqual(w['wis'], 12 * 20)
        self.assertEqual(w['apred'], 0)

    def test_class_profiles_can_be_overridden_per_version(self):
        # Every class x element/preset x version is independently tunable:
        # a retro override must change retro weights only, at the right
        # specificity (element beats 'all', override beats base profile).
        from unittest.mock import patch
        from chardata.smart_build import (RACE_PROFILE_OVERRIDES_BY_VERSION,
                                          param_for_build)
        # Ecaflip has no real retro override, so the injected one is isolated.
        retro_eca = {'all': {'mpred_importance': 0.9},
                     'agi': {'airdam': 3.0}}
        with patch.dict(RACE_PROFILE_OVERRIDES_BY_VERSION['retro'],
                        {'Ecaflip': retro_eca}):
            self.assertEqual(
                param_for_build('Ecaflip', ['agi'], 'airdam', game_version='retro'), 3.0)
            self.assertEqual(
                param_for_build('Ecaflip', ['agi'], 'mpred_importance',
                                game_version='retro'), 0.9)
            # Params the override does not state inherit the base profile.
            self.assertEqual(
                param_for_build('Ecaflip', ['agi'], 'meleeness', game_version='retro'),
                param_for_build('Ecaflip', ['agi'], 'meleeness'))
            # Other versions are untouched.
            self.assertEqual(param_for_build('Ecaflip', ['agi'], 'airdam'), 6.0)
            # And the whole weight vector reacts on retro only.
            wr = self._weights('retro', {'agi'}, race='Ecaflip')
            w3 = self._weights('dofus3', {'agi'}, race='Ecaflip')
            self.assertLess(wr['airdam'], w3['airdam'])
        self.assertEqual(
            param_for_build('Ecaflip', ['agi'], 'airdam', game_version='retro'), 6.0)
        # The real, committed retro tuning is live (Cra 1.29).
        self.assertEqual(
            param_for_build('Cra', ['agi'], 'airdam', game_version='retro'), 5.5)
        self.assertEqual(param_for_build('Cra', ['agi'], 'airdam'), 6.0)


class WizardSlidersPerVersionTests(TestCase):
    """The wizard hides sliders for stats no item of the version carries
    (VERSION_WEIGHT_TUNING zero_stats): a retro build has no Critical Damage
    or AP Reduction gear, a touch build no Trap Damage gear. Dofus 3 keeps
    everything."""

    def _slider_keys(self, version, char_class='Iop', aspects=None):
        from django.test import RequestFactory
        from django.contrib.auth.models import User
        from fashionistapulp.structure import set_current_game_version
        from chardata.coaching_view import create_build
        from chardata.wizard_sliders import get_wizard_sliders
        set_current_game_version(version)
        self.addCleanup(set_current_game_version, 'dofus3')
        owner, _ = User.objects.get_or_create(
            username='wizver', defaults={'email': 'wv@test.local'})
        req = RequestFactory().post('/')
        req.user = owner
        char = create_build(req, char_class, 150, aspects or {'str'}, version)
        keys = set()
        for section in get_wizard_sliders(char):
            for sub in (section.subsliders or []):
                keys.add(sub.key)
        return keys

    def test_retro_hides_dead_stat_sliders(self):
        keys = self._slider_keys('retro', 'Sram', {'str', 'trap'})
        for dead in ('cridam', 'apred', 'mpred', 'lock', 'crires'):
            self.assertNotIn(dead, keys)
        self.assertIn('trapdam', keys)

    def test_touch_hides_trap_damage_sliders(self):
        keys = self._slider_keys('touch', 'Sram', {'str', 'trap'})
        self.assertNotIn('trapdam', keys)
        self.assertNotIn('trapdamper', keys)
        self.assertIn('cridam', keys)

    def test_dofus3_keeps_all_sliders(self):
        keys = self._slider_keys('dofus3', 'Sram', {'str', 'trap'})
        for key in ('cridam', 'trapdam', 'lock', 'crires'):
            self.assertIn(key, keys)


class StatsWeightCapTests(TestCase):
    """A build whose weights exceed the old 5k guard (high-end crit/omni builds
    store weights via _set_weights, which never checks the bound) used to 500 on
    a plain wizard GET, because get_stats_weights re-saves through
    set_stats_weights. Re-saving must clamp, not crash, and keep the value."""

    def _char_with_weight(self, cridam):
        import pickle
        from django.contrib.auth.models import User
        from chardata.models import Char
        # Omit the resper defaults so get_stats_weights fills them -> changed=True
        # -> a re-save through set_stats_weights (the prod crash path).
        weights = {'str': 100, 'dam': 4320, 'cridam': cridam, 'ch': 240}
        owner = User.objects.create_user(
            'wcap%d' % cridam, 'wc@test.local', 'pw-wcap-77')
        char = Char.objects.create(
            name='Wc', char_name='wc', char_class='Iop', char_build='build',
            level=200, minimum_stats=b'', minimum_crits=b'',
            stats_weight=pickle.dumps(weights), options=b'', inclusions=b'',
            exclusions=b'', aspects=pickle.dumps({'str', 'crit', 'dam'}),
            owner=owner, link_shared=False, game_version='dofus3')
        return owner, char

    def test_wizard_get_does_not_crash_on_large_weight(self):
        owner, char = self._char_with_weight(5400)
        self.client.force_login(owner)
        resp = self.client.get('/wizard/%d/' % char.pk)
        self.assertEqual(resp.status_code, 200)

    def test_large_weight_is_preserved(self):
        import pickle
        from chardata.stats_weights import set_stats_weights
        owner, char = self._char_with_weight(5400)
        set_stats_weights(char, {'str': 100, 'cridam': 5400})
        char.refresh_from_db()
        self.assertEqual(pickle.loads(char.stats_weight)['cridam'], 5400)

    def test_runaway_weight_is_clamped(self):
        import pickle
        from chardata.stats_weights import set_stats_weights, MAX_STAT_WEIGHT
        owner, char = self._char_with_weight(5400)
        set_stats_weights(char, {'str': 100, 'cridam': 10 ** 9})
        char.refresh_from_db()
        self.assertEqual(pickle.loads(char.stats_weight)['cridam'], MAX_STAT_WEIGHT)


def _pulp_solver_available():
    try:
        import pulp
        return bool(pulp.listSolvers(onlyAvailable=True))
    except Exception:
        return False


class SolverSmokeTests(TestCase):
    """The optimizer is the product; one real end-to-end solve guards the
    whole chain (weights -> model -> pulp solver -> stored solution)."""

    @unittest.skipUnless(_pulp_solver_available(), 'no pulp solver available')
    def test_full_solve_stores_a_solution_with_items(self):
        import pickle as _pickle
        from django.contrib.auth.models import User
        from chardata.models import Char
        from chardata.smart_build import get_standard_weights
        from chardata.solution import get_solution
        owner = User.objects.create_user('solveur', 'so@test.local', 'pw-42-solid')
        char = Char.objects.create(
            name='Smoke solve', char_name='smoke', char_class='Iop',
            char_build='build', level=50,
            minimum_stats=b'', minimum_crits=b'', stats_weight=b'',
            options=b'', inclusions=b'', exclusions=b'',
            aspects=_pickle.dumps({'str'}),
            owner=owner, link_shared=False, game_version='dofus3')
        char.stats_weight = _pickle.dumps(get_standard_weights(char))
        char.save()
        self.client.force_login(owner)
        resp = self.client.get('/fashion/%d/' % char.pk)
        self.assertIn(resp.status_code, (200, 302))
        char.refresh_from_db()
        solution = get_solution(char)
        self.assertIsNotNone(solution, 'no solution stored after solving')
        equipped = sum(1 for ri in solution.item_list if ri.item_added)
        self.assertGreaterEqual(equipped, 3,
                                'a level 50 strength solve should equip several items')

class TouchPetSolveTests(TestCase):
    """Maxed pet variants (scraped from the official Dofus Touch encyclopedia)
    must reach the solver: at level 50 no mount is equippable (all level 60)
    and no natural pet beats the maxed bonuses, so a strength solve has to put
    a synthesized variant in the Pet slot."""

    VARIANT_ID_BASE = 200000000

    def test_touch_structure_has_maxed_pet_variants(self):
        from fashionistapulp.structure import get_structure
        st = get_structure('touch')
        variant = st.get_item_by_name('Bow Meow (+110 Strength)')
        self.assertIsNotNone(variant,
                             'maxed touch pet variants missing from items_touch.db')
        self.assertGreaterEqual(variant.id, self.VARIANT_ID_BASE)
        self.assertEqual(st.get_type_name_by_id(variant.type), 'Pet')

    @unittest.skipUnless(_pulp_solver_available(), 'no pulp solver available')
    def test_touch_strength_solve_equips_a_maxed_pet_variant(self):
        from django.test import RequestFactory
        from django.contrib.auth.models import User
        from fashionistapulp.structure import set_current_game_version
        from chardata.coaching_view import create_build
        from chardata.solution import get_solution
        set_current_game_version('touch')
        self.addCleanup(set_current_game_version, 'dofus3')
        owner = User.objects.create_user('touchsolve', 'ts@test.local', 'pw-42-solid')
        req = RequestFactory().post('/')
        req.user = owner
        # The real creation path seeds the default exclusions (GM pets...).
        char = create_build(req, 'Iop', 50, {'str'}, 'touch')
        self.client.force_login(owner)
        resp = self.client.get('/touch/fashion/%d/' % char.pk)
        self.assertIn(resp.status_code, (200, 302))
        char.refresh_from_db()
        solution = get_solution(char)
        self.assertIsNotNone(solution, 'no solution stored after solving')
        pet = next((ri for ri in solution.item_list
                    if ri.item_added and ri.type == 'Pet'), None)
        self.assertIsNotNone(pet, 'no pet equipped on a touch strength solve')
        self.assertGreaterEqual(
            pet.id, self.VARIANT_ID_BASE,
            'expected a maxed pet variant in the Pet slot, got %r' % pet.name)

class WeaponTypeDisplayTests(TestCase):
    """Weapons with no standard type (magnifying glass, fishing rod...) show
    their AP line without a placeholder type prefix."""

    def _damage_head(self, item_name):
        from fashionistapulp.structure import get_structure
        from fashionistapulp.modelresult import ModelResultItem
        from chardata.solution_result import evolve_result_item
        item = get_structure('dofus3').get_item_by_name(item_name)
        self.assertIsNotNone(item, 'missing test fixture item %r' % item_name)
        result_item = ModelResultItem(item)
        evolve_result_item(result_item)
        return result_item.damage_text.split('<br>')[0]

    def test_untyped_weapon_has_no_placeholder_prefix(self):
        head = self._damage_head('Magnifying Glass')
        self.assertNotIn('Unknown Weapon Type', head)
        self.assertNotIn('DefaultName', head)
        self.assertTrue(head.startswith('AP:'), head)

    def test_typed_weapon_keeps_its_type_prefix(self):
        from fashionistapulp.structure import get_structure
        st = get_structure('dofus3')
        sword_name = next(
            name for name, w in st.weapons_dict_by_name.items()
            if getattr(st.get_weapon_type_by_id(w.weapon_type), 'name', None) == 'Sword')
        head = self._damage_head(sword_name)
        self.assertIn('(Sword)', head)

class ExclusionsForbidTests(TestCase):
    """Forbidding an item adds an id that's actually in the forbiddable set,
    grouped variants like Gelano included."""

    def _load_forbid_data(self):
        import json
        from django.contrib.auth.models import User
        from chardata.models import Char
        owner = User.objects.create_user('forbidder', 'fb@test.local', 'pw-42-solid')
        char = Char.objects.create(
            name='Forbid', char_name='forbid', char_class='Iop',
            char_build='build', level=200,
            minimum_stats=b'', minimum_crits=b'', stats_weight=b'',
            options=b'', inclusions=b'', exclusions=b'',
            owner=owner, link_shared=False, game_version='dofus3')
        self.client.force_login(owner)
        resp = self.client.get('/exclusions/%d/' % char.pk)
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode('utf-8')
        items = json.loads(re.search(r'var allItems = (\{.*\});', html).group(1))
        names = json.loads(re.search(r'var allItemsNames = (\{.*\});', html).group(1))
        return set(items.keys()), names

    def test_every_forbiddable_name_maps_into_the_item_set(self):
        item_ids, names = self._load_forbid_data()
        bad = {n: i for n, i in names.items()
               if i is not None and str(i) not in item_ids}
        self.assertEqual(bad, {}, 'names point to non-forbiddable ids: %r' % bad)

    def test_gelano_is_forbiddable(self):
        item_ids, names = self._load_forbid_data()
        self.assertIn('Gelano', names)
        self.assertIn(str(names['Gelano']), item_ids)


class RobotsTxtTests(TestCase):
    """robots.txt must keep the public content crawlable while blocking the
    action endpoints and per-project/private pages that were flooding Search
    Console with 403 / soft-404 / noindex 'errors' and wasting crawl budget."""

    def _parser(self):
        import urllib.robotparser as rp
        body = self.client.get('/robots.txt').content.decode('utf-8')
        p = rp.RobotFileParser()
        p.parse(body.splitlines())
        return p, body

    def test_content_pages_stay_crawlable(self):
        p, _ = self._parser()
        for url in ['/', '/guides/getting-started/', '/encyclopedia/',
                    '/encyclopedia/item/equipment/123-foo/', '/sharedbuilds/',
                    '/s/zobal/abc123/', '/user/someone/', '/setup/', '/about/',
                    '/faq/', '/quickstart/', '/forgemagie/', '/workshop/',
                    '/loadprojects/', '/compare_sets/s123/']:
            self.assertTrue(p.can_fetch('Googlebot', url),
                            'robots.txt must not block content page %s' % url)

    def test_action_endpoints_are_blocked(self):
        p, _ = self._parser()
        for url in ['/setup/170414/', '/beta/setup/170414/', '/postcomment/3048/',
                    '/beta/postcomment/3048/', '/touch/saveprojecttouser/',
                    '/addtag/215413/', '/workshop/addsolution/7420/',
                    '/loadproject/223687/', '/solution/123/', '/spells/123/',
                    '/exchange/5/', '/setitemlocked/1/', '/manageaccount/',
                    '/fashion/123/', '/inventory/', '/login/']:
            self.assertFalse(p.can_fetch('Googlebot', url),
                             'robots.txt must block action endpoint %s' % url)

    def test_sitemap_is_declared(self):
        _, body = self._parser()
        self.assertIn('Sitemap: https://dofusfashionista.gg/sitemap.xml', body)



class AdminToolsTests(TestCase):
    """The staff dashboard must be invisible (404) to everyone but admins, and
    let an admin moderate comments (hide / restore / dismiss reports)."""

    def _make_build_and_comment(self):
        from django.contrib.auth.models import User
        from chardata.models import Char, BuildComment
        author = User.objects.create_user('poster', 'p@test.local', 'pw-42-solid')
        build = Char.objects.create(
            name='Shared', char_name='shared', char_class='Iop', char_build='b',
            level=200, minimum_stats=b'', minimum_crits=b'', stats_weight=b'',
            options=b'', inclusions=b'', exclusions=b'',
            owner=author, link_shared=True, game_version='dofus3')
        comment = BuildComment.objects.create(
            user=author, build=build, content='A questionable comment')
        return author, build, comment

    def test_anonymous_and_regular_users_get_404(self):
        from django.contrib.auth.models import User
        self.assertEqual(self.client.get('/admin-tools/').status_code, 404)
        User.objects.create_user('plain', 'pl@test.local', 'pw-42-solid')
        self.client.login(username='plain', password='pw-42-solid')
        self.assertEqual(self.client.get('/admin-tools/').status_code, 404)

    def test_superuser_sees_dashboard_with_reported_comment(self):
        from django.contrib.auth.models import User
        from chardata.models import CommentReport
        author, build, comment = self._make_build_and_comment()
        r1 = User.objects.create_user('rep1', 'r1@test.local', 'pw-42-solid')
        r2 = User.objects.create_user('rep2', 'r2@test.local', 'pw-42-solid')
        CommentReport.objects.create(user=r1, comment=comment, reason='spam')
        CommentReport.objects.create(user=r2, comment=comment, reason='harassment')
        User.objects.create_superuser('boss', 'boss@test.local', 'pw-42-solid')
        self.client.login(username='boss', password='pw-42-solid')
        resp = self.client.get('/admin-tools/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Reported comments')
        self.assertContains(resp, 'A questionable comment')
        self.assertContains(resp, 'noindex')

    def test_admin_can_hide_and_restore_a_comment(self):
        from django.contrib.auth.models import User
        from chardata.models import BuildComment, CommentReport
        author, build, comment = self._make_build_and_comment()
        rep = User.objects.create_user('rep', 'r@test.local', 'pw-42-solid')
        CommentReport.objects.create(user=rep, comment=comment, reason='spam')
        User.objects.create_superuser('boss', 'boss@test.local', 'pw-42-solid')
        self.client.login(username='boss', password='pw-42-solid')

        resp = self.client.post('/admin-comment-action/',
                                {'comment_id': comment.id, 'action': 'delete'})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(BuildComment.objects.get(id=comment.id).deleted)
        # Hiding also processes its open reports.
        self.assertFalse(CommentReport.objects.filter(comment=comment, processed=False).exists())

        resp = self.client.post('/admin-comment-action/',
                                {'comment_id': comment.id, 'action': 'restore'})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(BuildComment.objects.get(id=comment.id).deleted)

    def test_action_endpoint_is_404_for_non_admins(self):
        author, build, comment = self._make_build_and_comment()
        resp = self.client.post('/admin-comment-action/',
                                {'comment_id': comment.id, 'action': 'delete'})
        self.assertEqual(resp.status_code, 404)

    def test_menu_link_only_shows_for_admins(self):
        from django.contrib.auth.models import User
        User.objects.create_user('plain', 'pl@test.local', 'pw-42-solid')
        self.client.login(username='plain', password='pw-42-solid')
        self.assertNotContains(self.client.get('/faq/'), '/admin-tools/')
        self.client.logout()
        User.objects.create_superuser('boss', 'boss@test.local', 'pw-42-solid')
        self.client.login(username='boss', password='pw-42-solid')
        self.assertContains(self.client.get('/faq/'), '/admin-tools/')


class CreateLocalAdminCommandTests(TestCase):
    """create_local_admin makes a superuser whose password works with the
    site's own login form (which pre-hashes in the browser). This is the way
    back in when the only admin is a Google-login account that can't be used
    on a localhost test server."""

    def test_created_admin_logs_in_via_site_form(self):
        import hashlib
        from django.contrib.auth.models import User
        from django.core.management import call_command
        call_command('create_local_admin', username='localadmin',
                     email='la@test.local', password='a-solid-pw-42')
        u = User.objects.get(username='localadmin')
        self.assertTrue(u.is_superuser and u.is_staff and u.is_active)
        prehash = hashlib.sha256(('dofusfashionista' + 'a-solid-pw-42').encode()).hexdigest()
        resp = self.client.post('/local_login/', {'username': 'localadmin', 'password': prehash})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content.decode(), 'ok')
        # And that session can reach the staff dashboard.
        self.assertEqual(self.client.get('/admin-tools/').status_code, 200)


class GelanoExoInventoryTests(TestCase):
    """MP exo "only Gelano" must equip the +1 AP +1 MP Gelano, not the plain
    one. Owning another item with an MP roll above its base used to flip the
    'gelano' choice to a generic "yes", which equipped the plain Gelano."""

    @unittest.skipUnless(_pulp_solver_available(), 'no pulp solver available')
    def test_gelano_exo_keeps_the_mp_gelano_despite_an_owned_mp_roll(self):
        import pickle as _pickle
        from django.test import RequestFactory
        from django.contrib.auth.models import User
        from fashionistapulp.structure import set_current_game_version, get_structure
        from chardata.coaching_view import create_build
        from chardata.options import get_options, set_options
        from chardata.models import InventoryFolder, InventoryItem
        from chardata.solution import get_solution
        set_current_game_version('dofus3')
        structure = get_structure('dofus3')
        gelano2 = structure.get_item_by_name('Gelano (#2)')
        boots = next(it for it in structure.get_concatenated_items_lists()
                     if it.type == structure.get_type_id_by_name('Boots'))
        owner = User.objects.create_user('gelexo', 'ge@test.local', 'pw-gel-77')
        req = RequestFactory().post('/')
        req.user = owner
        char = create_build(req, 'Xelor', 150, {'cha'}, 'dofus3')
        folder = InventoryFolder.objects.create(
            user=owner, name='inv', game_version='dofus3')
        InventoryItem.objects.create(folder=folder, item_id=gelano2.id, custom_stats='')
        # An owned item with an MP roll above its base (the trigger for the bug).
        InventoryItem.objects.create(
            folder=folder, item_id=boots.id, custom_stats='{"mp": 3}')
        options = get_options(char)
        options['mp_exo'] = 'gelano'
        options['inventory_mode'] = 'only'
        options['inventory_folder'] = folder.id
        set_options(char, options)
        self.client.force_login(owner)
        self.client.get('/fashion/%d/' % char.pk)
        char.refresh_from_db()
        solution = get_solution(char)
        gelanos = [ri for ri in solution.item_list
                   if ri.item_added and 'Gelano' in getattr(ri, 'name', '')]
        self.assertEqual(len(gelanos), 1, 'expected a Gelano equipped')
        self.assertEqual(gelanos[0].stats.get('mp'), 1,
                         'gelano exo must equip the +1 MP Gelano, not the plain one')


class RetroPercentDamageStatTests(SimpleTestCase):
    """Retro's "% Dommages" (effect 138) is the game's percent-damage stat; it
    was dropped by the scraper. It now maps to Power, so items like the Feathered
    Belt (15% Dmg) carry it and a retro damage build can stack it."""

    def test_feathered_belt_has_the_percent_damage_stat(self):
        from fashionistapulp.structure import get_structure
        retro = get_structure('retro')
        belt = retro.get_item_by_ankama_id(11545)
        self.assertIsNotNone(belt, 'Feathered Belt missing from Retro data')
        power = retro.get_stat_by_name('Power')
        power_val = dict(belt.stats).get(power.id)
        self.assertEqual(power_val, 15, 'Feathered Belt should carry 15% Dommages')

    def test_many_retro_items_carry_percent_damage(self):
        from fashionistapulp.structure import get_structure
        retro = get_structure('retro')
        power_id = retro.get_stat_by_name('Power').id
        n = sum(1 for it in retro.get_concatenated_items_lists()
                if power_id in dict(it.stats))
        self.assertGreater(n, 100, 'retro items should carry the % damage stat')


class RetroAbsentStatsTests(SimpleTestCase):
    """These stats are Dofus 2.30+ mechanics that do not exist in Retro 1.29.
    No Retro item should carry them, and the solution page hides their rows for
    the retro version (they are not derived either, so they stay at zero)."""

    DOFUS2_ONLY = [
        'Critical Damage', 'Pushback Damage', 'Critical Resist', 'Pushback Resist',
        '% Melee Damage', '% Ranged Damage', '% Weapon Damage', '% Spell Damage',
        '% Melee Resist', '% Ranged Resist', '% Weapon Resist',
    ]

    def test_no_retro_item_carries_a_dofus2_only_stat(self):
        from fashionistapulp.structure import get_structure
        retro = get_structure('retro')
        items = retro.get_concatenated_items_lists()
        for name in self.DOFUS2_ONLY:
            stat = retro.get_stat_by_name(name)
            self.assertIsNotNone(stat, '%s missing from retro stat table' % name)
            offenders = [it.name for it in items if stat.id in dict(it.stats)]
            self.assertEqual(offenders, [],
                             '%s should not appear on any retro item, found: %s'
                             % (name, offenders[:5]))


class TouchAbsentStatsTests(SimpleTestCase):
    """Dofus Touch forked before the Dofus 2.30 percent-final damage/resist stats,
    so it has none of them, but it kept the Dofus 2.x critical/pushback stats and
    the PvP resists. The solution page hides the final damage/resist rows for
    touch while keeping the critical/pushback rows and the PvP resist rows."""

    FINAL_ABSENT = [
        '% Melee Damage', '% Ranged Damage', '% Weapon Damage', '% Spell Damage',
        '% Melee Resist', '% Ranged Resist', '% Weapon Resist',
    ]
    KEPT = ['Critical Damage', 'Pushback Damage', 'Critical Resist', 'Pushback Resist']

    def _items(self):
        from fashionistapulp.structure import get_structure
        touch = get_structure('touch')
        return touch, touch.get_concatenated_items_lists()

    def test_no_touch_item_carries_final_damage_or_resist(self):
        touch, items = self._items()
        for name in self.FINAL_ABSENT:
            stat = touch.get_stat_by_name(name)
            self.assertIsNotNone(stat, '%s missing from touch stat table' % name)
            offenders = [it.name for it in items if stat.id in dict(it.stats)]
            self.assertEqual(offenders, [],
                             '%s should not appear on any touch item, found: %s'
                             % (name, offenders[:5]))

    def test_touch_still_carries_critical_and_pushback_stats(self):
        # The solution page shows character totals including weapons, so check the
        # raw touch item db (weapons are excluded from get_concatenated_items_lists).
        import os, sqlite3, fashionistapulp
        db = os.path.join(os.path.dirname(fashionistapulp.__file__), 'items_touch.db')
        c = sqlite3.connect(db)
        present = set(r[0] for r in c.execute('SELECT DISTINCT stat FROM stats_of_item'))
        by_key = {k: i for i, k in c.execute('SELECT id, key FROM stats')}
        for key in ['cridam', 'pshdam', 'crires', 'pshres']:
            self.assertIn(by_key[key], present,
                          'touch should keep the %s stat on gear' % key)
        c.close()

    def test_touch_carries_pvp_resists(self):
        touch, items = self._items()
        stat = touch.get_stat_by_name('% Air Resist in PVP')
        n = sum(1 for it in items if stat.id in dict(it.stats))
        self.assertGreater(n, 0, 'touch gear should carry PvP resists')


class NoEmDashInGuidesTests(SimpleTestCase):
    """The /guides/ prose is our original, AdSense-facing editorial content; a run of
    em/en dashes reads as machine-generated. Guard every localized guide field so a
    future edit cannot reintroduce one (the 'desc' field also feeds the Google snippet
    and the og:description). See chardata.guides_content.GUIDES."""

    def test_no_guide_field_contains_an_em_or_en_dash(self):
        from chardata.guides_content import GUIDES
        offenders = []
        for slug, guide in GUIDES.items():
            for language, fields in guide.get('i18n', {}).items():
                for field_name, value in fields.items():
                    if isinstance(value, str) and ('—' in value or '–' in value):
                        offenders.append('%s/%s/%s' % (slug, language, field_name))
        self.assertEqual(
            offenders, [],
            'em/en dash found in guide content (use ., :, , or parentheses): %s' % offenders)

    def test_no_dash_in_templates_or_catalogs(self):
        # Same rule for everything else we render: template sources and the
        # translation catalogs. The footer separators and og:titles carried
        # ndash/mdash entities for years; this pins the cleanup.
        import glob
        import io
        import os

        banned = ('—', '–', '&mdash;', '&ndash;')
        here = os.path.dirname(os.path.abspath(__file__))
        scan = glob.glob(os.path.join(here, 'templates', 'chardata', '*'))
        scan += glob.glob(os.path.join(here, '..', 'locale', '*',
                                       'LC_MESSAGES', '*.po'))
        offenders = []
        for path in scan:
            if not os.path.isfile(path):
                continue
            text = io.open(path, encoding='utf-8', errors='replace').read()
            for token in banned:
                if token in text:
                    offenders.append('%s (%s)' % (os.path.basename(path), token))
        self.assertEqual(
            offenders, [],
            'em/en dash in rendered sources (use ., :, &middot; or |): %s' % offenders)


class GuideMetaDescriptionLengthTests(SimpleTestCase):
    """Each guide 'desc' is the <meta name="description">, og:description and JSON-LD
    description. Past ~160 characters Google truncates it in the search snippet, losing
    the tail (call to action, keyword). Guard every localized description so a future
    edit stays within the snippet budget. See chardata.guides_content.GUIDES."""

    MAX_DESC = 160

    def test_guide_descriptions_fit_the_search_snippet(self):
        from chardata.guides_content import GUIDES
        offenders = []
        for slug, guide in GUIDES.items():
            for language, fields in guide.get('i18n', {}).items():
                desc = fields.get('desc', '')
                if len(desc) > self.MAX_DESC:
                    offenders.append('%s/%s (%d)' % (slug, language, len(desc)))
        self.assertEqual(
            offenders, [],
            'guide desc over %d chars (Google truncates the snippet): %s'
            % (self.MAX_DESC, offenders))


class EncyclopediaCacheWarmupTests(SimpleTestCase):
    def test_warm_caches_covers_every_version(self):
        from chardata import encyclopedia_view as ev

        ev.warm_caches()
        for version, _label in ev.ACTIVE_GAME_VERSIONS:
            structure = ev.get_structure(version)
            self.assertIn(id(structure), ev._light_core_cache)
            for language in ev.SUPPORTED_LANGUAGES:
                self.assertIn((id(structure), language), ev._light_index_cache)
                self.assertIn((version, language), ev._monster_index_cache)
            self.assertIn(version, ev._monster_core_by_id_cache)
            subdir = ev._MONSTER_IMAGE_DIRS.get(version)
            if subdir is not None:
                self.assertIn(subdir, ev._monster_image_ids_cache)
            self.assertIn(ev._INGREDIENT_ICON_DIRS[version],
                          ev._ingredient_icon_ids_cache)
            self.assertIn(version, ev._version_item_keys_cache)
            self.assertIn(version, ev._version_resource_keys_cache)
            self.assertIn(version, ev._resource_search_index_cache)
        # After the warmup every cross-version helper must answer without
        # touching sqlite (this is what the wsgi background thread buys us).
        with unittest.mock.patch.object(
                ev.sqlite3, 'connect',
                side_effect=AssertionError('cold db hit after warmup')):
            self.assertTrue(ev._other_versions_with_item(
                'dofus3', 'equipment', 44, 'x'))
            self.assertTrue(ev._other_versions_with_resource(
                'dofus3', 'resources', 287, 'x'))
            self.assertTrue(ev._get_monster_version_links(101, 'retro', 'fr'))
            self.assertTrue(ev._get_light_index(ev.get_structure('retro'), 'fr'))


class EncyclopediaResourcePageTests(TestCase):
    """The resource page is the reverse recipe index: it lists every item a crafting
    ingredient is used in, and item recipes link to it. See
    encyclopedia_view.encyclopedia_resource."""

    def _busiest_resource(self, game_version='dofus3'):
        import sqlite3
        from fashionistapulp.fashionista_config import get_items_db_path
        conn = sqlite3.connect(get_items_db_path(game_version))
        try:
            return conn.cursor().execute(
                """
                SELECT r.ingredient_ankama_id, n.name
                FROM item_recipes r
                JOIN item_recipe_ingredient_names n
                  ON n.ingredient_ankama_id = r.ingredient_ankama_id
                 AND n.ingredient_subtype = r.ingredient_subtype
                 AND n.language = 'en'
                WHERE r.ingredient_subtype = 'resources'
                GROUP BY r.ingredient_ankama_id
                ORDER BY COUNT(DISTINCT r.item) DESC
                LIMIT 1
                """).fetchone()
        finally:
            conn.close()

    def _non_resource_ingredient(self, game_version='dofus3'):
        import sqlite3
        from fashionistapulp.fashionista_config import get_items_db_path
        conn = sqlite3.connect(get_items_db_path(game_version))
        try:
            return conn.cursor().execute(
                """
                SELECT r.ingredient_subtype, r.ingredient_ankama_id, n.name
                FROM item_recipes r
                JOIN item_recipe_ingredient_names n
                  ON n.ingredient_ankama_id = r.ingredient_ankama_id
                 AND n.ingredient_subtype = r.ingredient_subtype
                 AND n.language = 'en'
                WHERE r.ingredient_subtype <> 'resources'
                GROUP BY r.ingredient_subtype, r.ingredient_ankama_id, n.name
                HAVING COUNT(*) >= 2
                ORDER BY CASE WHEN r.ingredient_subtype = 'consumables' THEN 0 ELSE 1 END,
                         r.ingredient_subtype, r.ingredient_ankama_id
                LIMIT 1
                """).fetchone()
        finally:
            conn.close()

    def _retro_equipment_ingredient_used_in(self):
        import sqlite3
        from fashionistapulp.fashionista_config import get_items_db_path
        conn = sqlite3.connect(get_items_db_path('retro'))
        try:
            return conn.cursor().execute(
                """
                SELECT r.ingredient_ankama_id, n.name,
                       (SELECT COALESCE(crafted_name.name, crafted.name)
                        FROM item_recipes r2
                        JOIN items crafted ON crafted.id = r2.item
                        LEFT JOIN item_names crafted_name
                          ON crafted_name.item = crafted.id
                         AND crafted_name.language = 'en'
                        WHERE r2.ingredient_subtype = 'equipment'
                          AND r2.ingredient_ankama_id = r.ingredient_ankama_id
                        ORDER BY crafted.level DESC
                        LIMIT 1)
                FROM item_recipes r
                JOIN item_recipe_ingredient_names n
                  ON n.ingredient_ankama_id = r.ingredient_ankama_id
                 AND n.ingredient_subtype = r.ingredient_subtype
                 AND n.language = 'en'
                WHERE r.ingredient_subtype = 'equipment'
                GROUP BY r.ingredient_ankama_id, n.name
                ORDER BY COUNT(DISTINCT r.item) DESC
                LIMIT 1
                """).fetchone()
        finally:
            conn.close()

    def test_resource_page_lists_the_items_it_crafts(self):
        resource = self._busiest_resource()
        self.assertIsNotNone(resource, 'expected at least one resource with a recipe')
        ankama_id, name = resource
        resp = self.client.get('/encyclopedia/resource/resources/%d-x/' % ankama_id,
                               HTTP_ACCEPT_LANGUAGE='en')
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode('utf-8')
        self.assertIn(name, body)
        self.assertIn('<div class="encyclopedia-item-meta">Resource</div>', body)
        self.assertIn('/encyclopedia/item/', body)

    def test_non_resource_ingredient_page_uses_ingredient_label(self):
        ingredient = self._non_resource_ingredient()
        if ingredient is None:
            self.skipTest('no non-resource recipe ingredient in this build')

        from chardata.official_site import get_resource_link
        subtype, ankama_id, name = ingredient
        url = get_resource_link(subtype, ankama_id, name, game_version='dofus3')
        resp = self.client.get(url, HTTP_ACCEPT_LANGUAGE='en')
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode('utf-8')
        self.assertIn(name, body)
        self.assertIn('<div class="encyclopedia-item-meta">Ingredient</div>', body)
        self.assertIn('uses this ingredient', body)
        self.assertNotIn('uses this resource', body)

    def test_item_page_lists_items_it_is_used_to_craft(self):
        ingredient = self._retro_equipment_ingredient_used_in()
        if ingredient is None:
            self.skipTest('no Retro equipment ingredient in this build')

        from chardata.official_site import get_item_link
        ankama_id, name, crafted_name = ingredient
        url = get_item_link('equipment', ankama_id, name, game_version='retro')
        resp = self.client.get(url, HTTP_ACCEPT_LANGUAGE='en')
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode('utf-8')
        self.assertIn('Used to craft', body)
        self.assertIn(crafted_name, body)

    def test_retro_resource_page_uses_retro_route_and_data(self):
        ankama_id = 2448
        resp = self.client.get(
            '/retro/encyclopedia/resource/resources/%d-cervelle-de-bouftou/' % ankama_id,
            HTTP_ACCEPT_LANGUAGE='fr')
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode('utf-8')
        self.assertIn('Cervelle de Bouftou', body)
        self.assertIn('/retro/encyclopedia/item/', body)
        self.assertIn(
            'https://dofusfashionista.gg/retro/encyclopedia/resource/resources/%d-' % ankama_id,
            body)

    def test_retro_resource_page_localizes_crafted_item_names(self):
        expected_names = {
            'fr': 'Cape du Boufcoul',
            'es': 'Capa del jalatranki',
            'pt': 'Capa do Gobkool',
            'de': 'Fresscool-Mantel',
        }
        expected_resource_names = {
            'fr': 'Laine de Bouftou',
            'es': 'Lana de jalató',
            'pt': 'Lã de Gobball',
            'de': 'Fresssackwolle',
        }
        for language, expected_name in expected_names.items():
            with self.subTest(language=language):
                resp = self.client.get(
                    '/retro/encyclopedia/resource/resources/384-laine-de-bouftou/',
                    HTTP_ACCEPT_LANGUAGE=language)
                self.assertEqual(resp.status_code, 200)
                body = resp.content.decode('utf-8')
                self.assertIn(expected_resource_names[language], body)
                self.assertIn(expected_name, body)
                if language == 'fr':
                    self.assertIn('Cape | Niv.', body)
                self.assertIn('/retro/encyclopedia/item/', body)

    def test_unknown_resource_shows_the_graceful_missing_page(self):
        from chardata.encyclopedia_view import LOCALIZED_UI
        resp = self.client.get('/encyclopedia/resource/resources/999999999-x/')
        self.assertEqual(resp.status_code, 404)
        self.assertContains(resp, LOCALIZED_UI['en']['missing_resource_title'],
                            status_code=404)

    def test_unknown_versioned_resource_shows_versioned_missing_page(self):
        from chardata.encyclopedia_view import LOCALIZED_UI
        resp = self.client.get('/retro/encyclopedia/resource/resources/999999999-x/')
        self.assertEqual(resp.status_code, 404)
        self.assertContains(resp, LOCALIZED_UI['en']['missing_back_to_encyclopedia'],
                            status_code=404)
        self.assertContains(resp, '/retro/encyclopedia/', status_code=404)

    def _resource_with_drops(self):
        import sqlite3
        from fashionistapulp.fashionista_config import get_items_db_path
        conn = sqlite3.connect(get_items_db_path('dofus3'))
        try:
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='resource_drops'")
            if cur.fetchone() is None:
                return None
            return cur.execute(
                """
                SELECT d.resource_ankama_id, n.name
                FROM resource_drops d
                JOIN item_recipe_ingredient_names n
                  ON n.ingredient_ankama_id = d.resource_ankama_id
                 AND n.ingredient_subtype = 'resources' AND n.language = 'en'
                GROUP BY d.resource_ankama_id
                ORDER BY COUNT(*) DESC
                LIMIT 1
                """).fetchone()
        finally:
            conn.close()

    def test_resource_page_shows_the_monsters_that_drop_it(self):
        resource = self._resource_with_drops()
        if resource is None:
            self.skipTest('no resource_drops table/data in this build')
        ankama_id, name = resource
        resp = self.client.get('/encyclopedia/resource/resources/%d-x/' % ankama_id,
                               HTTP_ACCEPT_LANGUAGE='en')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Dropped by', resp.content.decode('utf-8'))


class EncyclopediaMonsterPageTests(TestCase):
    """Monster encyclopedia pages are version-scoped and built from the per-version
    drop tables, so Retro monsters never borrow modern drops or names."""

    def _retro_item_url_with_variant_only_drop(self):
        import sqlite3
        from collections import defaultdict

        from chardata.encyclopedia_view import (
            _get_group_representative,
            _get_item_group_key,
        )
        from chardata.official_site import get_item_link
        from fashionistapulp.fashionista_config import get_items_db_path
        from fashionistapulp.structure import get_structure, set_current_game_version

        set_current_game_version('retro')
        structure = get_structure('retro')
        grouped_items = defaultdict(list)
        for item in structure.get_concatenated_items_lists():
            if not getattr(item, 'ankama_id', None):
                continue
            if (item.ankama_type or '').lower() != 'equipment':
                continue
            grouped_items[_get_item_group_key(item)].append(item)

        conn = sqlite3.connect(get_items_db_path('retro'))
        try:
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='item_drops'")
            if cur.fetchone() is None:
                return None

            cur.execute("SELECT item FROM item_drops")
            dropped_item_ids = {row[0] for row in cur.fetchall()}
            for variants in grouped_items.values():
                representative = _get_group_representative(variants)
                variant_ids = [item.id for item in variants]
                if len(variant_ids) < 2:
                    continue
                if representative.id in dropped_item_ids:
                    continue
                if not any(item_id in dropped_item_ids for item_id in variant_ids):
                    continue

                placeholders = ','.join('?' for _ in variant_ids)
                cur.execute(
                    """
                    SELECT d.monster_ankama_id,
                           COALESCE(
                               (SELECT name FROM monster_names
                                WHERE monster_ankama_id = d.monster_ankama_id
                                  AND language = 'fr'),
                               (SELECT name FROM monster_names
                                WHERE monster_ankama_id = d.monster_ankama_id
                                  AND language = 'en'),
                               '#' || d.monster_ankama_id)
                    FROM item_drops d
                    WHERE d.item IN (%s)
                    ORDER BY d.rate DESC
                    LIMIT 1
                    """ % placeholders,
                    variant_ids)
                row = cur.fetchone()
                item_url = get_item_link(
                    representative.ankama_type,
                    representative.ankama_id,
                    representative.name,
                    'retro')
                if row is not None and item_url:
                    return item_url, row[0], row[1]
        finally:
            conn.close()

        return None

    def test_retro_monsters_list_is_localized_and_version_prefixed(self):
        resp = self.client.get('/retro/encyclopedia/monsters/?q=bouftou',
                               HTTP_ACCEPT_LANGUAGE='fr')
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode('utf-8')
        self.assertIn('Bouftou', body)
        self.assertIn('/retro/encyclopedia/monster/101-', body)
        self.assertIn('https://dofusfashionista.gg/retro/encyclopedia/monsters/', body)

    def test_monsters_list_renders_for_every_supported_version(self):
        for path in (
                '/encyclopedia/monsters/',
                '/dofus2/encyclopedia/monsters/',
                '/retro/encyclopedia/monsters/',
                '/touch/encyclopedia/monsters/',
                '/beta/encyclopedia/monsters/'):
            with self.subTest(path=path):
                resp = self.client.get(path, HTTP_ACCEPT_LANGUAGE='en')
                self.assertEqual(resp.status_code, 200)
                self.assertIn('Monsters', resp.content.decode('utf-8'))

    def test_monsters_search_matches_names_from_other_languages(self):
        resp = self.client.get('/retro/encyclopedia/monsters/?q=bouftou',
                               HTTP_ACCEPT_LANGUAGE='es')
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode('utf-8')
        self.assertIn('/retro/encyclopedia/monster/101-', body)
        self.assertIn('Jalat', body)
        self.assertIn('Botín:', body)

    def test_monsters_search_matches_drop_names(self):
        resp = self.client.get('/retro/encyclopedia/monsters/?q=laine',
                               HTTP_ACCEPT_LANGUAGE='fr')
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode('utf-8')
        self.assertIn('/retro/encyclopedia/monster/101-', body)
        self.assertIn('Bouftou', body)
        self.assertIn('Drops:', body)
        self.assertIn('Laine de Bouftou', body)
        self.assertRegex(
            body,
            r'Laine de Bouftou</a>\s*<span class="drop-rate">[0-9,.]+%</span>')
        self.assertIn('/retro/encyclopedia/resource/resources/384-', body)

    def test_monsters_list_can_filter_and_sort_by_drop_kind(self):
        resp = self.client.get(
            '/retro/encyclopedia/monsters/?drop_kind=items&sort=item_drops',
            HTTP_ACCEPT_LANGUAGE='fr')
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode('utf-8')
        self.assertIn('Type de drop', body)
        self.assertIn('Trier par', body)
        self.assertEqual(resp.context['drop_kind'], 'items')
        self.assertEqual(resp.context['sort_key'], 'item_drops')
        monsters = list(resp.context['monsters_page'].object_list)
        self.assertTrue(monsters)
        self.assertTrue(all(monster['item_count'] > 0 for monster in monsters))
        item_counts = [monster['item_count'] for monster in monsters]
        self.assertEqual(item_counts, sorted(item_counts, reverse=True))

    def test_monsters_pagination_preserves_filters(self):
        resp = self.client.get(
            '/retro/encyclopedia/monsters/?drop_kind=resources&sort=resource_drops',
            HTTP_ACCEPT_LANGUAGE='en')
        self.assertEqual(resp.status_code, 200)
        if not resp.context['monsters_page'].has_next():
            self.skipTest('not enough Retro monsters with resource drops for pagination')
        body = resp.content.decode('utf-8')
        self.assertIn('drop_kind=resources', body)
        self.assertIn('sort=resource_drops', body)
        self.assertIn('page=2', body)

    def test_invalid_monster_filters_fall_back_to_defaults(self):
        resp = self.client.get(
            '/retro/encyclopedia/monsters/?drop_kind=bad&sort=bad',
            HTTP_ACCEPT_LANGUAGE='en')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['drop_kind'], 'all')
        self.assertEqual(resp.context['sort_key'], 'name')

    def test_retro_monster_page_lists_resource_and_item_drops(self):
        resp = self.client.get('/retro/encyclopedia/monster/101-bouftou/',
                               HTTP_ACCEPT_LANGUAGE='fr')
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode('utf-8')
        self.assertIn('Bouftou', body)
        self.assertIn('Laine de Bouftou', body)
        self.assertIn('Marteau du Bouftou', body)
        self.assertIn('Arme | Niv.', body)
        self.assertIn('/retro/encyclopedia/resource/resources/384-', body)
        self.assertIn('/retro/encyclopedia/item/equipment/2416-', body)
        self.assertIn('href="#resource-drops"', body)
        self.assertIn('href="#item-drops"', body)
        self.assertIn('id="resource-drops"', body)
        self.assertIn('id="item-drops"', body)
        self.assertIn('<span class="monster-drop-summary-count">11</span> Ressources droppées',
                      body)
        self.assertIn('<span class="monster-drop-summary-count">3</span> Objets droppés',
                      body)

    def test_monster_page_links_same_monster_in_other_versions(self):
        resp = self.client.get('/retro/encyclopedia/monster/101-bouftou/',
                               HTTP_ACCEPT_LANGUAGE='fr')
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode('utf-8')
        self.assertIn('Autres versions', body)
        self.assertIn('/encyclopedia/monster/101-bouftou/', body)
        self.assertIn('/touch/encyclopedia/monster/101-bouftou/', body)

        version_links = {
            link['game_version']: link
            for link in resp.context['monster_version_links']
        }
        self.assertIn('dofus3', version_links)
        self.assertIn('touch', version_links)
        self.assertNotIn('retro', version_links)
        self.assertEqual(version_links['dofus3']['resource_count'], 3)
        self.assertEqual(version_links['dofus3']['item_count'], 2)
        self.assertEqual(version_links['touch']['resource_count'], 4)
        self.assertEqual(version_links['touch']['item_count'], 1)

    def test_monster_version_links_only_include_versions_with_drops(self):
        resp = self.client.get('/retro/encyclopedia/monster/101-bouftou/',
                               HTTP_ACCEPT_LANGUAGE='fr')
        self.assertEqual(resp.status_code, 200)
        for version in resp.context['monster_version_links']:
            self.assertGreater(
                version['resource_count'] + version['item_count'], 0,
                version['game_version'])

    def test_touch_monster_page_shows_official_grade_stats(self):
        # The stats-per-grade section comes from the Touch backend Monsters
        # table (monster_grades, stored by store_touch_monster_grades.py).
        # Expectations are read back from the db so a re-scrape stays honest.
        import sqlite3
        from fashionistapulp.fashionista_config import get_items_db_path

        conn = sqlite3.connect(get_items_db_path('touch'))
        try:
            rows = conn.execute(
                """SELECT grade, level, life_points FROM monster_grades
                   WHERE monster_ankama_id = 101 ORDER BY grade""").fetchall()
        finally:
            conn.close()
        self.assertTrue(rows, 'no touch grades stored for the Gobball')

        resp = self.client.get('/touch/encyclopedia/monster/101-bouftou/',
                               HTTP_ACCEPT_LANGUAGE='fr')
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode('utf-8')
        self.assertIn('id="monster-stats"', body)
        self.assertIn('Caractéristiques par grade', body)
        for grade, level, hp in rows:
            self.assertIn('<td>%d</td>' % level, body)
            self.assertIn('<td>%d</td>' % hp, body)

        # dofus3 has its OWN grades (DofusDB source): same monster id, its
        # own numbers. The two versions must differ, proving no data sharing.
        conn = sqlite3.connect(get_items_db_path('dofus3'))
        try:
            d3_rows = conn.execute(
                """SELECT grade, level, life_points FROM monster_grades
                   WHERE monster_ankama_id = 101 ORDER BY grade""").fetchall()
        finally:
            conn.close()
        self.assertTrue(d3_rows, 'no dofus3 grades stored for the Gobball')
        self.assertNotEqual(rows, d3_rows,
                            'touch and dofus3 grades must be version-specific')
        resp = self.client.get('/encyclopedia/monster/101-bouftou/')
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode('utf-8')
        self.assertIn('id="monster-stats"', body)
        self.assertIn('<td>%d</td>' % d3_rows[0][1], body)

        # retro has its own 1.29 numbers from the Solomonk bestiary.
        conn = sqlite3.connect(get_items_db_path('retro'))
        try:
            retro_rows = conn.execute(
                """SELECT grade, level, life_points FROM monster_grades
                   WHERE monster_ankama_id = 101 ORDER BY grade""").fetchall()
        finally:
            conn.close()
        self.assertTrue(retro_rows, 'no retro grades stored for the Gobball')
        self.assertNotEqual(retro_rows, d3_rows,
                            'retro and dofus3 grades must be version-specific')
        resp = self.client.get('/retro/encyclopedia/monster/101-bouftou/')
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode('utf-8')
        self.assertIn('id="monster-stats"', body)
        self.assertIn('<td>%d</td>' % retro_rows[0][1], body)

        # Versions without their own source show no stats section at all.
        for prefix in ('/dofus2',):
            resp = self.client.get(
                '%s/encyclopedia/monster/101-bouftou/' % prefix)
            self.assertEqual(resp.status_code, 200, prefix)
            self.assertNotIn('id="monster-stats"',
                             resp.content.decode('utf-8'), prefix)

    def test_monster_hub_shows_level_ranges_per_version(self):
        # The hub cards show the level span across grades, read from each
        # version's own monster_grades table; expectations come from the db.
        import re
        import sqlite3
        from fashionistapulp.fashionista_config import get_items_db_path

        for prefix, version in (('/touch', 'touch'), ('/retro', 'retro'), ('', 'dofus3')):
            conn = sqlite3.connect(get_items_db_path(version))
            try:
                level_min, level_max = conn.execute(
                    """SELECT MIN(level), MAX(level) FROM monster_grades
                       WHERE monster_ankama_id = 101 AND level IS NOT NULL""").fetchone()
            finally:
                conn.close()
            self.assertIsNotNone(level_min, version)
            resp = self.client.get('%s/encyclopedia/monsters/?q=bouftou' % prefix,
                                   HTTP_ACCEPT_LANGUAGE='fr')
            self.assertEqual(resp.status_code, 200, version)
            body = resp.content.decode('utf-8')
            expected = ('Niveau %d-%d' % (level_min, level_max)
                        if level_max != level_min else 'Niveau %d' % level_min)
            self.assertIn(expected, re.sub(r'\s+', ' ', body), version)

        # dofus2 has no grade source: no level line and no level sort option.
        resp = self.client.get('/dofus2/encyclopedia/monsters/?q=bouftou',
                               HTTP_ACCEPT_LANGUAGE='fr')
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode('utf-8')
        self.assertNotIn('encyclopedia-monsters-level', body)
        self.assertNotIn('value="level"', body)

        # Sorting by level orders the touch hub by ascending level span.
        resp = self.client.get('/touch/encyclopedia/monsters/?sort=level',
                               HTTP_ACCEPT_LANGUAGE='fr')
        self.assertEqual(resp.status_code, 200)
        body = re.sub(r'\s+', ' ', resp.content.decode('utf-8'))
        self.assertEqual(resp.context['sort_key'], 'level')
        self.assertIn('value="level"', body)
        mins = [int(m) for m in re.findall(r'Niveau (\d+)', body)]
        self.assertTrue(mins, 'no level lines rendered on the sorted hub')
        self.assertEqual(mins, sorted(mins))

    def test_monster_page_title_carries_the_level_span(self):
        # The title/meta use the version's own grade levels; dofus2 has no
        # grades so its title stays untouched.
        import sqlite3
        from fashionistapulp.fashionista_config import get_items_db_path

        conn = sqlite3.connect(get_items_db_path('touch'))
        try:
            level_min, level_max = conn.execute(
                """SELECT MIN(level), MAX(level) FROM monster_grades
                   WHERE monster_ankama_id = 101 AND level IS NOT NULL""").fetchone()
        finally:
            conn.close()
        self.assertIsNotNone(level_min)
        span = ('%d-%d' % (level_min, level_max)
                if level_max != level_min else '%d' % level_min)

        resp = self.client.get('/touch/encyclopedia/monster/101-bouftou/',
                               HTTP_ACCEPT_LANGUAGE='fr')
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode('utf-8')
        self.assertIn('Niveau %s - Monstre' % span, body)
        # The minifier reorders attributes: match the content only.
        self.assertIn('content="Niveau %s. Drops' % span, body)

        resp = self.client.get('/dofus2/encyclopedia/monster/101-bouftou/',
                               HTTP_ACCEPT_LANGUAGE='fr')
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode('utf-8')
        self.assertNotIn('Niveau', body.split('</title>')[0])

    def test_retro_monster_page_lists_its_subareas(self):
        # "Where to find it" comes from the version's own source (retro:
        # the Solomonk bestiary subarea blocks); expectations are read back
        # from the db. Versions without the table show no section.
        import sqlite3
        from fashionistapulp.fashionista_config import get_items_db_path

        conn = sqlite3.connect(get_items_db_path('retro'))
        try:
            rows = conn.execute(
                """SELECT name FROM monster_subareas
                   WHERE monster_ankama_id = 101 AND language = 'fr'
                   ORDER BY position""").fetchall()
        finally:
            conn.close()
        self.assertTrue(rows, 'no retro subareas stored for the Gobball')

        resp = self.client.get('/retro/encyclopedia/monster/101-bouftou/',
                               HTTP_ACCEPT_LANGUAGE='fr')
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode('utf-8')
        self.assertIn('id="monster-subareas"', body)
        self.assertIn('Où le trouver', body)
        for (name,) in rows[:3]:
            self.assertIn(name, body)

        # Touch has its OWN first-hand locations (the client SubAreas
        # table): same monster id, its own zones, natively localized.
        conn = sqlite3.connect(get_items_db_path('touch'))
        try:
            touch_rows = conn.execute(
                """SELECT name FROM monster_subareas
                   WHERE monster_ankama_id = 101 AND language = 'fr'
                   ORDER BY position""").fetchall()
            touch_de = conn.execute(
                """SELECT COUNT(*) FROM monster_subareas
                   WHERE monster_ankama_id = 101 AND language = 'de'""").fetchone()[0]
        finally:
            conn.close()
        self.assertTrue(touch_rows, 'no touch subareas stored for the Gobball')
        self.assertGreater(touch_de, 0, 'touch subareas must be localized')
        self.assertNotEqual([r[0] for r in touch_rows], [r[0] for r in rows],
                            'touch and retro locations must be version-specific')
        resp = self.client.get('/touch/encyclopedia/monster/101-bouftou/',
                               HTTP_ACCEPT_LANGUAGE='fr')
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode('utf-8')
        self.assertIn('id="monster-subareas"', body)
        for (name,) in touch_rows[:2]:
            self.assertIn(name, body)

        # dofus3 locations come from DofusDB (its own zones, own ids).
        conn = sqlite3.connect(get_items_db_path('dofus3'))
        try:
            d3_rows = conn.execute(
                """SELECT name FROM monster_subareas
                   WHERE monster_ankama_id = 101 AND language = 'fr'
                   ORDER BY position""").fetchall()
        finally:
            conn.close()
        self.assertTrue(d3_rows, 'no dofus3 subareas stored for the Gobball')
        resp = self.client.get('/encyclopedia/monster/101-bouftou/',
                               HTTP_ACCEPT_LANGUAGE='fr')
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode('utf-8')
        self.assertIn('id="monster-subareas"', body)
        self.assertIn(d3_rows[0][0], body)

        # dofus2 has no source for monster locations: no section at all.
        resp = self.client.get('/dofus2/encyclopedia/monster/101-bouftou/')
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('id="monster-subareas"',
                         resp.content.decode('utf-8'))

    def test_monster_page_shows_the_artwork(self):
        # dofus3/beta artwork comes from the DofusDB id -> img mapping (the
        # file name is the gfxId, not the monster id); touch has its own
        # era-accurate art from the official Touch CDN (indexed by monster
        # id); retro has the vectors extracted from the official 1.29 client.
        # Versions without a source (dofus2) must never borrow another's art.
        from chardata import encyclopedia_view as ev

        self.assertTrue(ev._monster_image_url('dofus3', 101))
        self.assertTrue(ev._monster_image_url('beta', 101))
        touch_url = ev._monster_image_url('touch', 101)
        self.assertTrue(touch_url)
        self.assertIn('monsters/touch/96/101.webp', touch_url)
        retro_url = ev._monster_image_url('retro', 101)
        self.assertTrue(retro_url)
        self.assertIn('monsters/retro/96/101.webp', retro_url)
        self.assertIsNone(ev._monster_image_url('dofus2', 101))

        # The touch page serves the touch art, not the modern render.
        resp = self.client.get('/touch/encyclopedia/monster/101-bouftou/')
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode('utf-8')
        self.assertIn('chardata/monsters/touch/96/101.webp', body)
        self.assertNotIn('chardata/monsters/96/101.webp', body)

        resp = self.client.get('/encyclopedia/monster/101-bouftou/')
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode('utf-8')
        self.assertIn('class="monster-portrait"', body)
        self.assertIn('width="48"', body)
        self.assertIn('height="48"', body)
        self.assertIn('decoding="async"', body)
        self.assertIn('chardata/monsters/96/101.webp', body)
        self.assertIn('property="og:image"', body)

        # The retro page serves the 1.29 art, never the modern render.
        resp = self.client.get('/retro/encyclopedia/monster/101-bouftou/')
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode('utf-8')
        self.assertIn('class="monster-portrait"', body)
        self.assertIn('chardata/monsters/retro/96/101.webp', body)
        self.assertNotIn('chardata/monsters/96/101.webp', body)
        self.assertIn('property="og:image"', body)

        # Search chips reuse the same artwork on dofus3.
        resp = self.client.get('/encyclopedia/', {'q': 'bouftou'})
        body = resp.content.decode('utf-8')
        self.assertIn('chardata/monsters/96/', body)
        self.assertIn('width="24"', body)
        self.assertIn('height="24"', body)
        self.assertIn('loading="lazy"', body)
        self.assertIn('decoding="async"', body)

    def test_monsters_hub_shows_thumbnails_from_cached_id_set(self):
        from chardata import encyclopedia_view as ev

        # The hub renders 60 rows per page: availability comes from one
        # cached directory listing, never per-file probing.
        resp = self.client.get('/encyclopedia/monsters/', {'q': 'bouftou'})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'chardata/monsters/96/')
        resp = self.client.get('/retro/encyclopedia/monsters/', {'q': 'bouftou'})
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, 'chardata/monsters/96/')
        self.assertContains(resp, 'chardata/monsters/retro/96/')

        # Warm set answers without listing the disk again.
        self.assertIn(101, ev._monster_image_ids('dofus3'))
        self.assertIn(101, ev._monster_image_ids('retro'))
        with unittest.mock.patch.object(
                ev, 'list_static_dir',
                side_effect=AssertionError('directory listed on a warm cache')):
            self.assertTrue(ev._monster_image_url('dofus3', 101))
            self.assertTrue(ev._monster_image_url('retro', 101))
            self.assertIsNone(ev._monster_image_url('dofus2', 101))

    def test_ingredient_icons_served_from_cached_id_set(self):
        from chardata import encyclopedia_view as ev

        # Sesame Seed (287) has an icon in every version; after the per-dir
        # set is warm, no icon lookup may list the disk again.
        for version in ('dofus3', 'beta', 'touch', 'retro', 'dofus2'):
            self.assertIn(287, ev._ingredient_icon_ids(version), version)
        with unittest.mock.patch.object(
                ev, 'list_static_dir',
                side_effect=AssertionError('directory listed on a warm cache')):
            for version in ('dofus3', 'beta', 'touch', 'retro', 'dofus2'):
                self.assertTrue(ev._ingredient_icon_url(version, 287), version)

    def test_monster_version_links_served_from_cache(self):
        from chardata import encyclopedia_view

        # Warm the per-version caches, then cut sqlite off: the links must
        # come out of memory (one db scan per version per process, not four
        # db opens plus counts on every monster page view).
        first = encyclopedia_view._get_monster_version_links(101, 'retro', 'fr')
        self.assertTrue(first)
        with unittest.mock.patch.object(
                encyclopedia_view.sqlite3, 'connect',
                side_effect=AssertionError('db hit on a warm cache')):
            cached = encyclopedia_view._get_monster_version_links(101, 'retro', 'fr')
        self.assertEqual(first, cached)

    def test_retro_monster_page_localizes_drops_for_supported_languages(self):
        expected_drops = {
            'fr': ('Laine de Bouftou', 'Marteau du Bouftou'),
            'es': ('Lana de jalató', 'Martillo del jalató'),
            'pt': ('Lã de Gobball', 'Martelo do Gobball'),
            'de': ('Fresssackwolle', 'Hammer des Fresssacks'),
        }
        for language, (resource_name, item_name) in expected_drops.items():
            with self.subTest(language=language):
                resp = self.client.get('/retro/encyclopedia/monster/101-bouftou/',
                                       HTTP_ACCEPT_LANGUAGE=language)
                self.assertEqual(resp.status_code, 200)
                body = resp.content.decode('utf-8')
                self.assertIn(resource_name, body)
                self.assertIn(item_name, body)

    def test_retro_monster_page_localizes_section_labels(self):
        expected_labels = {
            'fr': ('Ressources droppées', 'Objets droppés'),
            'de': ('Gedroppte Ressourcen', 'Gedroppte Gegenstände'),
        }
        for language, labels in expected_labels.items():
            with self.subTest(language=language):
                resp = self.client.get('/retro/encyclopedia/monster/101-bouftou/',
                                       HTTP_ACCEPT_LANGUAGE=language)
                self.assertEqual(resp.status_code, 200)
                body = resp.content.decode('utf-8')
                for label in labels:
                    self.assertIn(label, body)

    def test_monsters_empty_result_skips_drop_preview_db(self):
        from chardata import encyclopedia_view

        with unittest.mock.patch.object(
                encyclopedia_view, '_get_monster_index', return_value=[]):
            with unittest.mock.patch.object(
                    encyclopedia_view.sqlite3, 'connect') as connect_mock:
                resp = self.client.get(
                    '/encyclopedia/monsters/',
                    {'q': 'zzzznothingmatchesthis'})

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['monsters_count'], 0)
        connect_mock.assert_not_called()

    def test_missing_versioned_monster_uses_name_from_other_version(self):
        import sqlite3
        from chardata.official_site import get_monster_link
        from fashionistapulp.fashionista_config import get_items_db_path

        def dropped_monster_ids(game_version):
            conn = sqlite3.connect(get_items_db_path(game_version))
            try:
                cur = conn.cursor()
                sources = []
                for table_name in ('resource_drops', 'item_drops'):
                    cur.execute(
                        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                        (table_name,))
                    if cur.fetchone() is not None:
                        sources.append('SELECT monster_ankama_id FROM %s' % table_name)
                if not sources:
                    return set()
                cur.execute(' UNION '.join(sources))
                return {row[0] for row in cur.fetchall()}
            finally:
                conn.close()

        modern_ids = dropped_monster_ids('dofus3')
        retro_ids = dropped_monster_ids('retro')
        missing_ids = sorted(modern_ids - retro_ids)
        if not missing_ids:
            self.skipTest('no Dofus 3 dropped monster missing from Retro data')

        monster_id = missing_ids[0]
        conn = sqlite3.connect(get_items_db_path('dofus3'))
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT COALESCE(
                    (SELECT name FROM monster_names
                     WHERE monster_ankama_id = ? AND language = 'fr'),
                    (SELECT name FROM monster_names
                     WHERE monster_ankama_id = ? AND language = 'en'),
                    '#' || ?)
                """,
                (monster_id, monster_id, monster_id))
            name = cur.fetchone()[0]
        finally:
            conn.close()

        resp = self.client.get(
            get_monster_link(monster_id, name, game_version='retro'),
            HTTP_ACCEPT_LANGUAGE='fr')
        self.assertEqual(resp.status_code, 404)
        self.assertContains(resp, name, status_code=404)
        from chardata.encyclopedia_view import LOCALIZED_UI
        fr_fragment = LOCALIZED_UI['fr']['missing_item_message'].split('%(version)s')[0].split('%(name)s')[1]
        self.assertContains(resp, fr_fragment.strip(),
                            status_code=404)
        self.assertContains(resp, '/retro/encyclopedia/', status_code=404)

    def test_unknown_versioned_monster_has_graceful_localized_404(self):
        resp = self.client.get('/retro/encyclopedia/monster/999999999-gone/',
                               HTTP_ACCEPT_LANGUAGE='fr')
        self.assertEqual(resp.status_code, 404)
        body = resp.content.decode('utf-8')
        self.assertIn('Monstre indisponible dans cette version', body)
        from chardata.encyclopedia_view import LOCALIZED_UI
        monster_fragment = LOCALIZED_UI['fr']['missing_monster_message'].split('%(version)s')[0] % {'name': 'Gone'}
        self.assertIn(monster_fragment.strip(), body)
        self.assertIn('/retro/encyclopedia/', body)
        self.assertIn(LOCALIZED_UI['fr']['missing_back_to_encyclopedia'], body)

    def test_missing_versioned_resource_uses_name_from_other_version(self):
        import sqlite3
        from chardata.official_site import get_resource_link
        from fashionistapulp.fashionista_config import get_items_db_path

        def resource_ids(game_version):
            conn = sqlite3.connect(get_items_db_path(game_version))
            try:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT DISTINCT ingredient_ankama_id
                    FROM item_recipe_ingredient_names
                    WHERE ingredient_subtype = 'resources'
                    """)
                return {row[0] for row in cur.fetchall()}
            finally:
                conn.close()

        modern_ids = resource_ids('dofus3')
        retro_ids = resource_ids('retro')
        missing_ids = sorted(modern_ids - retro_ids)
        if not missing_ids:
            self.skipTest('no Dofus 3 resource missing from Retro data')

        resource_id = missing_ids[0]
        conn = sqlite3.connect(get_items_db_path('dofus3'))
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT COALESCE(
                    (SELECT name FROM item_recipe_ingredient_names
                     WHERE ingredient_ankama_id = ?
                       AND ingredient_subtype = 'resources'
                       AND language = 'fr'),
                    (SELECT name FROM item_recipe_ingredient_names
                     WHERE ingredient_ankama_id = ?
                       AND ingredient_subtype = 'resources'
                       AND language = 'en'),
                    '#' || ?)
                """,
                (resource_id, resource_id, resource_id))
            name = cur.fetchone()[0]
        finally:
            conn.close()

        resp = self.client.get(
            get_resource_link('resources', resource_id, name, game_version='retro'),
            HTTP_ACCEPT_LANGUAGE='fr')
        self.assertEqual(resp.status_code, 404)
        body = resp.content.decode('utf-8')
        self.assertIn(name, body)
        from chardata.encyclopedia_view import LOCALIZED_UI
        resource_fragment = (
            LOCALIZED_UI['fr']['missing_resource_message']
            .split('%(version)s')[0] % {'name': name})
        self.assertIn(resource_fragment.strip(), body)
        self.assertIn('/retro/encyclopedia/', body)
        self.assertIn(LOCALIZED_UI['fr']['missing_back_to_encyclopedia'], body)

    def test_existing_drop_lists_link_to_monster_pages(self):
        resource_resp = self.client.get(
            '/retro/encyclopedia/resource/resources/384-laine-de-bouftou/',
            HTTP_ACCEPT_LANGUAGE='fr')
        self.assertEqual(resource_resp.status_code, 200)
        self.assertIn('/retro/encyclopedia/monster/101-',
                      resource_resp.content.decode('utf-8'))

        item_resp = self.client.get('/retro/encyclopedia/item/equipment/2416-x/',
                                    HTTP_ACCEPT_LANGUAGE='fr')
        self.assertEqual(item_resp.status_code, 200)
        self.assertIn('/retro/encyclopedia/monster/101-',
                      item_resp.content.decode('utf-8'))

    def test_item_page_lists_drops_from_other_variants_in_same_version(self):
        item_case = self._retro_item_url_with_variant_only_drop()
        if item_case is None:
            self.skipTest('no Retro item variant group with variant-only drops')

        item_url, monster_id, monster_name = item_case
        item_resp = self.client.get(item_url, HTTP_ACCEPT_LANGUAGE='fr')
        self.assertEqual(item_resp.status_code, 200)
        body = item_resp.content.decode('utf-8')
        self.assertIn('/retro/encyclopedia/monster/%d-' % monster_id, body)
        self.assertIn(monster_name, body)


class NoMojibakeInTranslationsTests(SimpleTestCase):
    """Guard against encoding corruption in the .po catalogs: a tool writing them
    with the wrong encoding turns accents into literal question marks (seen live:
    'Derni?res g?n?rations', 'Comparer ? l'actuel', '?ffnen'). msgfmt does not
    catch this because the file stays valid. Two detectors:
    - a '?' squeezed between letters never occurs in legitimate copy;
    - a translation should not carry more '?' than its source string (one final
      question mark is tolerated: some languages phrase a statement as a question)."""

    LANGS = ('en', 'fr', 'es', 'pt', 'de')
    CATALOGS = ('django.po', 'djangojs.po')
    MOJIBAKE = re.compile(r'[^\W\d_]\?[^\W\d_]', re.UNICODE)

    @staticmethod
    def _suspicious(msgid, text):
        if NoMojibakeInTranslationsTests.MOJIBAKE.search(text):
            return True
        body = text.rstrip()
        if body.endswith('?'):
            body = body[:-1]
        return body.count('?') > msgid.count('?')

    def test_no_question_mark_mojibake_in_any_msgstr(self):
        try:
            import polib
        except ImportError:
            self.skipTest('polib not installed')
        offenders = []
        for lang in self.LANGS:
            for catalog in self.CATALOGS:
                path = os.path.join(os.path.dirname(__file__), '..', 'locale',
                                    lang, 'LC_MESSAGES', catalog)
                if not os.path.exists(path):
                    continue
                for entry in polib.pofile(path):
                    if entry.obsolete:
                        continue
                    candidates = [entry.msgstr] + list(entry.msgstr_plural.values())
                    for text in candidates:
                        if text and self._suspicious(entry.msgid, text):
                            offenders.append('%s/%s: %s -> %s'
                                             % (lang, catalog, entry.msgid[:40],
                                                text[:60]))
        self.assertEqual(
            offenders, [],
            'mojibake question marks found in translations (broken accents, '
            'rewrite the .po in UTF-8): %s' % offenders)


class NoEmDashInCodeTests(SimpleTestCase):
    """Em/en dashes read machine-generated, so the whole site avoids them (copy,
    comments, CSS, JS). The 2026-07 sweep brought every first-party source to zero;
    this test freezes that state. Allowlisted leftovers:
    - <title>/og:title separator dashes (ranking-sensitive, pending a decision);
    - this test file itself (the guard literals);
    - third-party minified libraries."""

    DASH_RE = re.compile('[—–]')
    EXTENSIONS = ('.py', '.html', '.css', '.js')
    SKIP_DIRS = {'locale', 'staticfiles', 'migrations', '__pycache__', 'admin'}
    SKIP_FILES = {'tests.py', 'mousetrap.min.js', 'sha256.js',
                  'jquery-ui-touch-punch-min.js'}
    LINE_ALLOWLIST = ('og:title', 'block title')

    def test_no_em_dash_in_first_party_sources(self):
        chardata_dir = os.path.dirname(os.path.abspath(__file__))
        fashionsite_root = os.path.dirname(chardata_dir)
        offenders = []
        for dirpath, dirnames, filenames in os.walk(fashionsite_root):
            dirnames[:] = [d for d in dirnames if d not in self.SKIP_DIRS]
            for filename in filenames:
                if not filename.endswith(self.EXTENSIONS):
                    continue
                if filename in self.SKIP_FILES or '.min.' in filename:
                    continue
                path = os.path.join(dirpath, filename)
                with open(path, encoding='utf-8', errors='replace') as fh:
                    for lineno, line in enumerate(fh, 1):
                        if not self.DASH_RE.search(line):
                            continue
                        if any(allow in line for allow in self.LINE_ALLOWLIST):
                            continue
                        rel = os.path.relpath(path, fashionsite_root)
                        offenders.append('%s:%d: %s'
                                         % (rel, lineno, line.strip()[:60]))
        self.assertEqual(
            offenders, [],
            'em/en dash found in first-party sources (use ., :, , or '
            'parentheses): %s' % offenders)
