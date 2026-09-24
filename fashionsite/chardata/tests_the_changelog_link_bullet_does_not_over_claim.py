# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The changelog link-import bullet no longer promises rolls and exos it cannot carry."""

from django.test import TestCase, override_settings

WITNESS = {
    'en': 'another build site',
    'fr': "d’un autre site de builds",
    'es': 'de otro sitio de builds',
    'pt': 'de outro site de builds',
    'de': 'einer anderen Build-Seite',
}


@override_settings(BUILD_SITES_ENABLED=('dofusbook', 'dofus-stuffer',
                                        'dofuscreator'))
class TheChangelogLinkBulletDoesNotOverClaimTests(TestCase):

    def test_the_bullet_does_not_promise_rolls_and_exos_for_every_link(self):
        for langue, phrase in WITNESS.items():
            self.client.post('/i18n/setlang/', {'language': langue})
            page = self.client.get(
                '/changelog-content/').content.decode('utf-8')
            with self.subTest(langue=langue):
                self.assertIn(phrase, page)
                self.assertNotIn('Rolls and exos come along.', page)
                self.assertNotIn('Les jets et les exos suivent.', page)
