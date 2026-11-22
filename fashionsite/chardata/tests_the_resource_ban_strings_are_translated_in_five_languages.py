# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The resource ban's strings ship a real translation in fr, de, es and pt, and keep the English source text in en."""

import gettext as gettext_module
import os

from django.test import SimpleTestCase
from django.utils import translation
from django.utils.translation import gettext, ngettext

LANGUAGES = ('fr', 'de', 'es', 'pt')
LOCALE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'locale')

DJANGO_MSGIDS = [
    'Forbidden resources',
    'Forbid an item or a set',
    'Forbid by resource',
    'An item is forbidden when its recipe, or the recipe of an item it is crafted from, uses one of these resources. Locked items stay allowed.',
]
TOTAL = ('In all, these resources forbid %(count)s item at your level.',
         'In all, these resources forbid %(count)s items at your level.')
COUNT_JS = ('%(count)s item forbidden', '%(count)s items forbidden')


def _js_catalog(language):
    return gettext_module.translation('djangojs', localedir=LOCALE_DIR,
                                      languages=[language], fallback=False)


class TheDjangoStringsAreTranslatedTests(SimpleTestCase):

    def test_every_plain_string_differs_from_the_english_in_four_languages(self):
        untranslated = []
        for msgid in DJANGO_MSGIDS:
            for language in LANGUAGES:
                with translation.override(language):
                    if gettext(msgid) == msgid:
                        untranslated.append((msgid, language))
        self.assertEqual([], untranslated)

    def test_the_total_line_has_a_translated_singular_and_plural(self):
        for language in LANGUAGES:
            with translation.override(language):
                one = ngettext(TOTAL[0], TOTAL[1], 1)
                many = ngettext(TOTAL[0], TOTAL[1], 5)
            self.assertNotEqual(TOTAL[0], one, language)
            self.assertNotEqual(TOTAL[1], many, language)
            self.assertNotEqual(one, many, language)
            self.assertIn('%(count)s', one, language)
            self.assertIn('%(count)s', many, language)

    def test_english_keeps_the_source_text(self):
        with translation.override('en'):
            for msgid in DJANGO_MSGIDS:
                self.assertEqual(msgid, gettext(msgid))
            self.assertEqual(TOTAL[0], ngettext(TOTAL[0], TOTAL[1], 1))
            self.assertEqual(TOTAL[1], ngettext(TOTAL[0], TOTAL[1], 2))


class TheJavascriptCountIsTranslatedTests(SimpleTestCase):

    def test_the_row_count_has_a_translated_singular_and_plural(self):
        for language in LANGUAGES:
            catalog = _js_catalog(language)
            one = catalog.ngettext(COUNT_JS[0], COUNT_JS[1], 1)
            many = catalog.ngettext(COUNT_JS[0], COUNT_JS[1], 5)
            self.assertNotEqual(COUNT_JS[0], one, language)
            self.assertNotEqual(COUNT_JS[1], many, language)
            self.assertIn('%(count)s', one, language)
            self.assertIn('%(count)s', many, language)

    def test_french_calls_zero_and_one_singular(self):
        catalog = _js_catalog('fr')

        self.assertEqual(catalog.ngettext(COUNT_JS[0], COUNT_JS[1], 1),
                         catalog.ngettext(COUNT_JS[0], COUNT_JS[1], 0))

    def test_english_keeps_the_source_text(self):
        catalog = _js_catalog('en')

        self.assertEqual(COUNT_JS[0], catalog.ngettext(COUNT_JS[0], COUNT_JS[1], 1))
        self.assertEqual(COUNT_JS[1], catalog.ngettext(COUNT_JS[0], COUNT_JS[1], 2))
