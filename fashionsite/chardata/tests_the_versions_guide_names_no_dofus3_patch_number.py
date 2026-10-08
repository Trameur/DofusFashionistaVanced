# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The versions guide describes Dofus 3 without a patch number in any language."""
import re

from django.test import SimpleTestCase

LANGUAGES = ('en', 'fr', 'es', 'pt', 'de')
DOFUS3_PATCH = re.compile(r'\b3\.\d')


class TheVersionsGuideNamesNoPatchTests(SimpleTestCase):

    def test_no_language_names_a_dofus3_patch(self):
        from chardata.guides_content import get_guide
        for language in LANGUAGES:
            guide = get_guide('versions-explained', language)
            text = ' '.join(guide[field] for field in ('title', 'desc', 'lead', 'body'))
            with self.subTest(language=language):
                self.assertIn('Dofus 3', text)
                self.assertIsNone(DOFUS3_PATCH.search(text))
