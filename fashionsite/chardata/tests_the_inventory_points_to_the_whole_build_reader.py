# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The inventory points to the whole-build reader from its screenshot box."""

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase

from chardata.inventory_view import LOCALIZED_UI


class TheInventoryNamesTheWholeBuildReaderTests(TestCase):

    def _boite(self, version, prefixe):
        from chardata.models import InventoryFolder
        owner = User.objects.create_user('inv-' + version,
                                         'inv-%s@t.local' % version,
                                         'pw-42-solid')
        dossier = InventoryFolder.objects.create(
            user=owner, name='Imagiro', game_version=version)
        self.client.force_login(owner)
        reponse = self.client.get('%s/inventory/' % prefixe,
                                  {'folder': dossier.id})
        self.assertEqual(200, reponse.status_code)
        page = reponse.content.decode('utf-8')
        debut = page.find('inv-ocr-whole-build')
        self.assertNotEqual(-1, debut, 'the whole-build link is not in the '
                                        'screenshot box')
        # The whole anchor around the id, in any attribute order: the minifier sorts them
        ouvre = page.rfind('<a', 0, debut)
        ferme = page.find('</a>', debut)
        return page[ouvre:ferme]

    def test_the_screenshot_box_links_to_the_text_import(self):
        ancre = self._boite('dofus3', '')
        self.assertIn('href="/import/text/"', ancre)
        self.assertIn(LOCALIZED_UI['en']['ocr_whole_build'], ancre)

    def test_the_link_follows_the_version_prefix(self):
        ancre = self._boite('touch', '/touch')
        self.assertIn('href="/touch/import/text/"', ancre)


class TheHintExistsInEveryLanguageTests(SimpleTestCase):

    def test_five_languages_five_different_sentences(self):
        phrases = {}
        for langue, textes in LOCALIZED_UI.items():
            self.assertIn('ocr_whole_build', textes, langue)
            phrases[langue] = textes['ocr_whole_build']
        self.assertEqual(5, len(phrases))
        self.assertEqual(5, len(set(phrases.values())),
                         'two languages share the same sentence: %s' % phrases)

    def test_the_hint_promises_one_screenshot_per_piece_not_a_panel(self):
        for langue, textes in LOCALIZED_UI.items():
            bas = textes['ocr_whole_build'].lower()
            self.assertFalse(
                any(mot in bas for mot in ('panel', 'panneau', 'panel de',
                                           'painel', 'ausrüstungsfenster')),
                (langue, bas))
