# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The new "where to get it" and job-summary strings ship a real translation."""

from django.test import SimpleTestCase
from django.utils import translation
from django.utils.translation import gettext

LANGUAGES = ('fr', 'es', 'pt', 'de')

NEW_MSGIDS = [
    'Jobs needed:',
    'Where to get it',
    'No known drop',
]


class NewSourceAndJobStringsAreTranslatedTests(SimpleTestCase):

    def test_every_new_string_has_a_real_translation(self):
        untranslated = []
        for msgid in NEW_MSGIDS:
            for lang in LANGUAGES:
                with translation.override(lang):
                    translated = gettext(msgid)
                if translated == msgid:
                    untranslated.append((msgid, lang))
        self.assertEqual([], untranslated)

    def test_english_keeps_the_source_text(self):
        for msgid in NEW_MSGIDS:
            with translation.override('en'):
                self.assertEqual(msgid, gettext(msgid))
