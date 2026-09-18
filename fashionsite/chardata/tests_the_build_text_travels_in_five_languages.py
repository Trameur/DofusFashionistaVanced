# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The build text is written in the reader's language and read back in all five."""

import html
import re

from django.test import TestCase
from django.utils.translation import override

LANGUES = ('en', 'fr', 'es', 'pt', 'de')

TEXTE = re.compile(
    r'<textarea[^>]*\bid=[\'"]?build_share_text[\'"]?[^>]*>(.*?)</textarea>',
    re.S)
BALISE_APERCU = re.compile(r'<meta[^>]*og:description[^>]*>')
CONTENU = re.compile(r'\bcontent="([^"]*)"')


class _AvecUnBuild(TestCase):

    def _build(self, char_class='Cra'):
        from chardata.models import Char
        from fashionistapulp.structure import (get_structure,
                                               set_current_game_version)
        set_current_game_version('dofus3')
        structure = get_structure('dofus3')
        noms = []
        for type_name in ('Hat', 'Cloak', 'Belt'):
            item = next(i for i in structure.types[200][type_name]
                        if not i.removed and i.ankama_id)
            noms.append(structure.get_item_name_in_language(item, 'en'))
        self.client.post('/import/text/', {
            'text': '\n'.join(noms), 'confirm': '1',
            'char_class': char_class, 'level': '200'})
        char = Char.objects.order_by('-id').first()
        char.link_shared = True
        char.save()
        return char

    def _texte_partage(self, char, langue):
        from chardata.encoded_char_id import encode_char_id
        adresse = '/s/%s/%s/' % (char.char_name or 'shared',
                                 encode_char_id(char.id))
        reponse = self.client.get(adresse, HTTP_ACCEPT_LANGUAGE=langue,
                                  follow=True)
        page = reponse.content.decode('utf-8')
        trouve = TEXTE.search(page)
        self.assertIsNotNone(
            trouve, 'pas de texte a copier en %s (adresse %s, code %s, %d octets)'
            % (langue, adresse, reponse.status_code, len(page)))
        return html.unescape(trouve.group(1)), page


class TheTextIsWrittenInTheReaderLanguageTests(_AvecUnBuild):

    def test_the_head_line_names_the_class_and_the_level_in_each_language(self):
        from chardata.translation_util import LOCALIZED_CHARACTER_CLASSES
        char = self._build()
        for langue in LANGUES:
            with self.subTest(langue=langue):
                texte, _page = self._texte_partage(char, langue)
                entete = texte.splitlines()[0]
                with override(langue):
                    from django.utils.translation import gettext
                    self.assertIn(gettext('lvl'), entete)
                    self.assertIn(
                        str(LOCALIZED_CHARACTER_CLASSES['Cra']), entete)

    def test_the_copied_text_and_the_link_preview_say_the_same_thing(self):
        from chardata.translation_util import LOCALIZED_CHARACTER_CLASSES
        char = self._build()
        for langue in LANGUES:
            with self.subTest(langue=langue):
                texte, page = self._texte_partage(char, langue)
                balise = BALISE_APERCU.search(page)
                self.assertIsNotNone(balise, langue)
                contenu = CONTENU.search(balise.group(0))
                self.assertIsNotNone(contenu, langue)
                apercu = html.unescape(contenu.group(1))
                with override(langue):
                    from django.utils.translation import gettext
                    mot = gettext('lvl')
                    classe = str(LOCALIZED_CHARACTER_CLASSES['Cra'])
                for morceau in (mot, classe):
                    self.assertIn(morceau, texte.splitlines()[0], langue)
                    self.assertIn(morceau, apercu, langue)


class TheSiteReadsItsOwnTextBackTests(_AvecUnBuild):

    def test_the_round_trip_gives_the_same_build_in_five_languages(self):
        from chardata.text_build_import import read_items
        char = self._build()
        attendu = None
        for langue in LANGUES:
            with self.subTest(langue=langue):
                texte, _page = self._texte_partage(char, langue)
                with override(langue):
                    lu = read_items(texte, 'dofus3', langue)
                resume = (lu['char_class'], lu['char_level'],
                          len(lu['matched']))
                self.assertEqual('Cra', lu['char_class'])
                self.assertEqual(200, lu['char_level'])
                self.assertTrue(lu['matched'])
                if attendu is None:
                    attendu = resume
                else:
                    self.assertEqual(attendu, resume)

    def test_a_text_exported_before_this_change_still_reads(self):
        from chardata.text_build_import import read_items
        for langue in LANGUES:
            with self.subTest(langue=langue):
                with override(langue):
                    lu = read_items('Mon build - Cra lvl 200 - Dofus 3',
                                    'dofus3', langue)
                self.assertEqual('Cra', lu['char_class'])
                self.assertEqual(200, lu['char_level'])

    def test_a_header_from_another_language_reads_too(self):
        from chardata.text_build_import import read_items
        with override('fr'):
            lu = read_items('X - Yopuka nvl 150 - Dofus 3', 'dofus3', 'fr')
        self.assertEqual('Iop', lu['char_class'])
        self.assertEqual(150, lu['char_level'])

    def test_the_tables_are_read_from_the_catalogues(self):
        from chardata.text_build_import import _CLASSE_PAR_NOM, _mots_de_niveau
        mots = _mots_de_niveau()
        self.assertIn('lvl', mots)
        for langue in LANGUES:
            with override(langue):
                from django.utils.translation import gettext
                self.assertIn(gettext('lvl'), mots)
        self.assertEqual('Iop', _CLASSE_PAR_NOM.get('yopuka'))
        self.assertEqual('Cra', _CLASSE_PAR_NOM.get('cra'))
