# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""L'inventaire renvoie vers le lecteur de build entier.

Le lecteur de captures de l'inventaire lit UN objet et l'ajoute a un
dossier. Depuis la section 9.10 du plan, la page d'import de texte lit un
build entier depuis une capture par piece, avec les jets, les exos, la
classe et le niveau. Rien sur l'inventaire ne le disait: un lecteur qui
voulait tout son stuff y passait piece par piece.
"""

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase

from chardata.inventory_view import LOCALIZED_UI


class TheInventoryNamesTheWholeBuildReaderTests(TestCase):
    """La boite de capture n'existe que sur un dossier selectionne. Sans
    dossier, la page porte quand meme un lien vers l'import de texte, dans le
    menu: un test qui cherchait ce lien-la sur la page nue etait vert sans
    avoir vu la boite. Les deux tests ci-dessous lisent le lien A L'INTERIEUR
    de la boite, par son identifiant."""

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
        # L'ancre entiere autour de l'identifiant, sans presumer de l'ordre
        # des attributs: le minifieur les trie.
        ouvre = page.rfind('<a', 0, debut)
        ferme = page.find('</a>', debut)
        return page[ouvre:ferme]

    def test_the_screenshot_box_links_to_the_text_import(self):
        ancre = self._boite('dofus3', '')
        self.assertIn('href="/import/text/"', ancre)
        self.assertIn(LOCALIZED_UI['en']['ocr_whole_build'], ancre)

    def test_the_link_follows_the_version_prefix(self):
        """Un build Touch se lit sous /touch/: le lien d'une page Touch doit
        y mener, pas vers le catalogue Dofus 3."""
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
        """La lecture d'un panneau d'equipement entier en une capture reste
        non livree (section 9.10): la phrase ne doit pas la promettre."""
        for langue, textes in LOCALIZED_UI.items():
            bas = textes['ocr_whole_build'].lower()
            self.assertFalse(
                any(mot in bas for mot in ('panel', 'panneau', 'panel de',
                                           'painel', 'ausrüstungsfenster')),
                (langue, bas))
