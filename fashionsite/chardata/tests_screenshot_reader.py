# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Le lecteur de captures, maintenant sur deux pages.

L'inventaire lit une infobulle, l'import de texte en lit un build entier,
mais c'est le meme lecteur dessous. Deux copies d'un reglage se separent en
silence, et une separation ici ne casse rien: elle enleve simplement une
langue, ou une empreinte, a une des deux pages.
"""

import os
import re

from django.test import SimpleTestCase, TestCase

from chardata.screenshot_reader import OCR_LANGUAGES, language_options

GABARITS = ('inventory.html', 'text_build.html')

_SRC = re.compile(r'\.src\s*=\s*\'(https?://[^\']+)\'')
_INTEGRITY = re.compile(r'\.integrity\s*=\s*\'([^\']+)\'')


def _gabarit(nom):
    chemin = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          'templates', 'chardata', nom)
    with open(chemin, encoding='utf-8') as f:
        return f.read()


class BothPagesPinTheSameReaderTests(SimpleTestCase):
    """L'adresse et l'empreinte sont ecrites en toutes lettres dans chaque
    gabarit, et c'est voulu: `tests_third_party_integrity` cherche un
    `element.src = "https://..."` litteral, donc les tirer d'une variable de
    contexte sortirait les deux pages de cet audit. Le prix de ce choix est
    une copie, et ce test est ce qui la tient."""

    def test_the_two_pages_load_the_same_script(self):
        adresses = {}
        for nom in GABARITS:
            trouves = _SRC.findall(_gabarit(nom))
            tesseract = [u for u in trouves if 'tesseract' in u]
            self.assertEqual(
                1, len(tesseract),
                '%s should load tesseract.js exactly once, found %d'
                % (nom, len(tesseract)))
            adresses[nom] = tesseract[0]
        self.assertEqual(1, len(set(adresses.values())),
                         'the two pages load different builds of the '
                         'screenshot reader: %s' % adresses)

    def test_the_two_pages_pin_the_same_fingerprint(self):
        """Une empreinte qui diverge ne rougit nulle part: la page qui garde
        l'ancienne refuse simplement de charger, chez tout le monde, en
        silence."""
        empreintes = {nom: _INTEGRITY.findall(_gabarit(nom))
                      for nom in GABARITS}
        for nom, trouvees in empreintes.items():
            self.assertEqual(1, len(trouvees),
                             '%s should pin exactly one fingerprint' % nom)
            self.assertTrue(trouvees[0].startswith('sha384-'), trouvees[0])
        self.assertEqual(
            1, len(set(v[0] for v in empreintes.values())),
            'the two pages pin different fingerprints for the same file: %s'
            % empreintes)

    def test_the_version_in_the_address_is_exact(self):
        """Une etiquette flottante comme @5 ne peut pas etre epinglee du
        tout: ses octets changent a chaque publication et le navigateur
        refuserait une mise a jour legitime."""
        adresse = [u for u in _SRC.findall(_gabarit('inventory.html'))
                   if 'tesseract' in u][0]
        self.assertRegex(adresse, r'tesseract\.js@\d+\.\d+\.\d+/')


class TheReaderSpeaksTheSameFiveLanguagesTests(SimpleTestCase):

    def test_the_list_is_the_five_the_site_speaks(self):
        from django.conf import settings
        codes = [code for code, _tess in OCR_LANGUAGES]
        self.assertEqual(sorted(codes), sorted(dict(settings.LANGUAGES)))

    def test_the_readers_language_is_the_one_preselected(self):
        for code, _tesseract in OCR_LANGUAGES:
            choisis = [o['code'] for o in language_options(code)
                       if o['selected']]
            self.assertEqual([code], choisis)

    def test_a_language_the_reader_does_not_speak_selects_nothing(self):
        """Plutot que d'en preselectionner une au hasard: un modele qui n'est
        pas celui du jeu rend du texte plausible et faux."""
        self.assertEqual([], [o['code'] for o in language_options('it')
                              if o['selected']])

    def test_both_pages_offer_the_same_models(self):
        for nom in GABARITS:
            corps = _gabarit(nom)
            self.assertIn('data-tesseract="{{ lang.tesseract }}"', corps,
                          '%s no longer renders the model list' % nom)


class TheImageNeverLeavesTheBrowserTests(TestCase):
    """La page le promet en toutes lettres. Ce qui rend la promesse vraie
    n'est pas le texte, c'est que rien ne peut envoyer le fichier: le champ
    est hors du formulaire ET sans `name`, donc meme deplace dedans un jour,
    le navigateur ne le posterait pas."""

    def _page(self):
        return self.client.get('/import/text/').content.decode('utf-8')

    def test_the_file_field_carries_no_name(self):
        corps = _gabarit('text_build.html')
        champ = re.search(r'<input type="file"[^>]*>', corps)
        self.assertIsNotNone(champ)
        self.assertNotIn('name=', champ.group(0))

    def test_the_file_field_is_outside_the_form(self):
        corps = _gabarit('text_build.html')
        debut = corps.index('<input type="file"')
        formulaire = corps.index('<form method="post"')
        self.assertLess(debut, formulaire,
                        'the file field moved inside the posting form')

    def test_the_page_posts_no_multipart_form(self):
        corps = _gabarit('text_build.html')
        self.assertNotIn('multipart/form-data', corps)


class TheTextImportOffersTheReaderTests(TestCase):

    def test_the_first_screen_offers_it(self):
        page = self.client.get('/import/text/').content.decode('utf-8')
        self.assertIn('shot-toggle', page)
        self.assertIn('multiple', page)
        for _code, tesseract in OCR_LANGUAGES:
            self.assertIn('data-tesseract="%s"' % tesseract, page)

    def test_it_survives_a_refusal(self):
        """Les quatre etats de la page montrent la meme zone de texte, donc
        les quatre doivent montrer la meme facon de la remplir. La liste des
        langues n'etant posee qu'a un seul endroit, un refus la perdait."""
        page = self.client.post('/import/text/', {
            'text': 'Nothing here matches any item at all'
        }).content.decode('utf-8')
        self.assertIn('shot-toggle', page)
        self.assertIn('data-tesseract="fra"', page)

    def test_the_reader_is_translated_everywhere(self):
        from django.utils.translation import gettext, override
        chaines = (
            'Read tooltip screenshots',
            'One screenshot per piece, tooltip visible. They are read inside '
            'your browser: no image leaves your machine.',
            'Choose images',
            'Game language',
            'Reading',
            'Screenshots read. Check the text below, then read it.',
            'That image could not be read.',
        )
        muettes = []
        for langue in ('fr', 'es', 'pt', 'de'):
            with override(langue):
                for chaine in chaines:
                    if gettext(chaine) == chaine:
                        muettes.append((langue, chaine))
        self.assertEqual([], muettes)
