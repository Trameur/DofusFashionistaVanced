# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Le texte d'un build est ecrit dans la langue du lecteur, et relu dans les cinq.

Le bouton <<copier>> ecrit un resume fait pour etre colle sur un Discord, et la
porte d'import sait relire ce meme texte. Les noms d'objets et les libelles de
stats y sont depuis longtemps dans la langue du lecteur. **Son en-tete, non**:
un lecteur francais copiait <<Cra lvl 200>> pendant que l'apercu de son propre
lien, ecrit dix lignes plus bas dans le meme fichier, annoncait <<Crâ niv.
200>>.

Selon la langue, **6 a 13 des 19 classes portent un autre nom**: six en
francais (Xélor, Sacrieur, Crâ, Roublard, Zobal, Steamer), treize en espagnol,
six en portugais, dix en allemand. Et le mot <<lvl>> est traduit dans les cinq
catalogues depuis toujours: <<niv.>>, <<nvl>>, <<nív.>>, <<Stufe>>.

**Et la moitie qui compte**: traduire l'en-tete sans l'apprendre au lecteur
cassait l'aller-retour. Mesure faite avant de livrer: le texte francais
revenait avec **aucune classe et aucun niveau**, la ligne entiere tombait dans
les lignes ignorees. L'import lit donc maintenant le mot <<niveau>> et le nom
de classe dans les cinq langues, et les deux tables sont construites depuis les
catalogues plutot que recopiees, pour qu'une traduction qui change soit suivie.

L'anglais reste lu quoi qu'il arrive: tous les textes deja colles sur un
Discord portent <<lvl>> et le nom interne de la classe.
"""

import html
import re

from django.test import TestCase
from django.utils.translation import override

LANGUES = ('en', 'fr', 'es', 'pt', 'de')

#: Le minifieur de production trie les attributs et leur enleve leurs
#: guillemets, donc `id` n'est pas forcement le premier ni entoure: on ne
#: s'ancre sur aucun ordre. C'est ce qui a fait echouer la premiere version
#: de ce test alors que la page etait juste.
TEXTE = re.compile(
    r'<textarea[^>]*\bid=[\'"]?build_share_text[\'"]?[^>]*>(.*?)</textarea>',
    re.S)
#: Meme raison: le minifieur trie, et `content` passe AVANT `property`. On
#: trouve d'abord la balise, on y lit le contenu ensuite, sans supposer
#: l'ordre des deux.
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
        """Les deux textes sont ecrits a dix lignes d'ecart dans le meme
        fichier et parlent du meme build: ils ne doivent pas se contredire."""
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
        """Ceux qui trainent deja sur un Discord portent <<lvl>> et le nom
        interne, quelle que soit la langue de celui qui les a exportes."""
        from chardata.text_build_import import read_items
        for langue in LANGUES:
            with self.subTest(langue=langue):
                with override(langue):
                    lu = read_items('Mon build - Cra lvl 200 - Dofus 3',
                                    'dofus3', langue)
                self.assertEqual('Cra', lu['char_class'])
                self.assertEqual(200, lu['char_level'])

    def test_a_header_from_another_language_reads_too(self):
        """Un joueur francais colle le build d'un ami espagnol."""
        from chardata.text_build_import import read_items
        with override('fr'):
            lu = read_items('X - Yopuka nvl 150 - Dofus 3', 'dofus3', 'fr')
        self.assertEqual('Iop', lu['char_class'])
        self.assertEqual(150, lu['char_level'])

    def test_the_tables_are_read_from_the_catalogues(self):
        """Recopier les mots ici les figerait: une traduction corrigee ne
        serait plus lue. Les cinq mots viennent des catalogues."""
        from chardata.text_build_import import _CLASSE_PAR_NOM, _mots_de_niveau
        mots = _mots_de_niveau()
        self.assertIn('lvl', mots)
        for langue in LANGUES:
            with override(langue):
                from django.utils.translation import gettext
                self.assertIn(gettext('lvl'), mots)
        self.assertEqual('Iop', _CLASSE_PAR_NOM.get('yopuka'))
        self.assertEqual('Cra', _CLASSE_PAR_NOM.get('cra'))
