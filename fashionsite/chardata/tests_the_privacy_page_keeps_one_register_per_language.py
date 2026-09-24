# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The DofusBook and DofusCreator privacy bullets use one register."""

import re

from django.test import TestCase, override_settings

def _bullet(page, site):
    match = re.search(r'<b>%s\.</b>(.*?)</li>' % site, page, re.DOTALL)
    return match.group(1)


@override_settings(BUILD_SITES_ENABLED=('dofusbook', 'dofuscreator'))
class ThePrivacyPageKeepsOneRegisterPerLanguageTests(TestCase):

    def _bullets(self, langue):
        page = self.client.get('/%s/privacy/' % langue).content.decode('utf-8')
        return _bullet(page, 'DofusBook'), _bullet(page, 'DofusCreator')

    def test_german_uses_sie_in_both_bullets(self):
        dofusbook, dofuscreator = self._bullets('de')
        for segment in (dofusbook, dofuscreator):
            self.assertIn('Sie', segment)
            self.assertIsNone(re.search(r'\bdu\b|\bdein', segment))

    def test_spanish_uses_tu_in_both_bullets(self):
        dofusbook, dofuscreator = self._bullets('es')
        for segment in (dofusbook, dofuscreator):
            self.assertNotIn('usted', segment.lower())
            self.assertIn('tu', segment.lower())

    def test_portuguese_uses_masculine_voce_in_both_bullets(self):
        dofusbook, dofuscreator = self._bullets('pt')
        for segment in (dofusbook, dofuscreator):
            self.assertIn('você', segment)
            self.assertNotIn('o nosso servidor', segment)
            self.assertNotIn('essa build', segment)
