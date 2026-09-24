# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
from unittest import mock

from django.test import TestCase

from chardata.tests_other_build_sites_wait_for_their_creators import _OwnedBuild

BOX = {
    'en': ('you can buy me a coffee\u00a0:)', 'Buy me a coffee on Ko-fi'),
    'fr': ("tu peux m'offrir un café\u00a0:)", 'Offrir un café sur Ko-fi'),
    'es': ('puedes invitarme a un café\u00a0:)', 'Invítame a un café en Ko-fi'),
    'pt': ('você pode me pagar um cafezinho\u00a0:)', 'Pagar um café no Ko-fi'),
    'de': ('kannst du mir gern einen Kaffee spendieren\u00a0:)',
           'Kaffee auf Ko-fi spendieren'),
}


class TheSupportBoxOffersACoffeeInEveryLanguageTests(_OwnedBuild, TestCase):

    def _box(self, char, language):
        prefix = '' if language == 'en' else '/%s' % language
        with mock.patch('chardata.context_processors.ad_config',
                        return_value={'enabled': False, 'client': '',
                                      'slots': {}, 'auto': False}):
            page = self.client.get('%s/solution/%d/' % (prefix, char.id),
                                   HTTP_ACCEPT_LANGUAGE=language)
        html = page.content.decode('utf-8')
        start = html.index('solution-support')
        return html[start:html.index('</aside>', start)]

    def test_each_language_offers_a_coffee_with_one_smiley(self):
        char = self._owned_build()
        for language, (sentence, button) in BOX.items():
            with self.subTest(language=language):
                box = self._box(char, language)
                self.assertIn(sentence, box)
                self.assertIn(button, box)
                self.assertEqual(1, box.count(':)'))
                self.assertNotIn('chip in', box)
                self.assertNotIn('\u2014', box)
                self.assertNotIn('\u2013', box)
