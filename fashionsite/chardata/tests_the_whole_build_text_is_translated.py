# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Le texte du build est traduit EN ENTIER, et relu en entier.

La section precedente avait traduit l'en-tete et laisse le reste, en disant
pourquoi: les emplacements et les deux lignes de caracteristiques de base
etaient ecrits en anglais interne, et l'import les relisait ainsi. Un lecteur
francais copiait donc:

    witness 0 - Iop niv. 200 - Dofus 3

    Hat: Chapeau de l'Aventurier
    PA 7 / PM 3
    Scrolls: Vitality 0 / Wisdom 0 / Strength 0 / ...

Trois registres dans cinq lignes. Tout est traduit maintenant, et l'import lit
les trois dans les cinq langues.

**La mesure qui dit pourquoi les deux moitiés vont ensemble.** Avec l'export
traduit et l'import laisse en arriere, un texte francais relu rendait **6
pieces sur 16** et plus aucune ligne de points: les dix autres lignes tombaient
dans les ignorees, parce que <<Coiffe: Masque d'Anerice>> etait compare en
entier a un nom d'objet.

Rien n'est recopie: les noms d'emplacements, les noms de stats et les deux
mots de ligne viennent des catalogues, donc une traduction corrigee est suivie.
Seul <<Scrolls>> manquait et a ete traduit dans les cinq langues.

L'anglais reste lu quoi qu'il arrive, pour les textes deja colles sur un
Discord.
"""

import html
import re

from django.test import TestCase
from django.utils.translation import gettext, override

LANGUES = ('en', 'fr', 'es', 'pt', 'de')

#: Le minifieur trie les attributs: on ne s'ancre sur aucun ordre.
TEXTE = re.compile(
    r'<textarea[^>]*\bid=[\'"]?build_share_text[\'"]?[^>]*>(.*?)</textarea>',
    re.S)


class _AvecUnBuild(TestCase):

    def _build(self):
        from chardata.models import Char
        from fashionistapulp.structure import (get_structure,
                                               set_current_game_version)
        set_current_game_version('dofus3')
        structure = get_structure('dofus3')
        noms = []
        for type_name in ('Hat', 'Cloak', 'Belt', 'Boots'):
            item = next(i for i in structure.types[200][type_name]
                        if not i.removed and i.ankama_id)
            noms.append(structure.get_item_name_in_language(item, 'en'))
        self.client.post('/import/text/', {
            'text': '\n'.join(noms), 'confirm': '1',
            'char_class': 'Cra', 'level': '200'})
        char = Char.objects.order_by('-id').first()
        char.link_shared = True
        char.save()
        return char

    def _texte(self, char, langue):
        from chardata.encoded_char_id import encode_char_id
        page = self.client.get(
            '/s/%s/%s/' % (char.char_name or 'shared', encode_char_id(char.id)),
            HTTP_ACCEPT_LANGUAGE=langue, follow=True).content.decode('utf-8')
        trouve = TEXTE.search(page)
        self.assertIsNotNone(trouve, langue)
        return html.unescape(trouve.group(1))


class EverySlotIsNamedInTheReaderLanguageTests(_AvecUnBuild):

    def test_the_slot_label_is_translated(self):
        char = self._build()
        for langue in LANGUES:
            with self.subTest(langue=langue):
                texte = self._texte(char, langue)
                with override(langue):
                    attendu = gettext('Hat')
                self.assertIn('%s:' % attendu, texte)

    def test_the_french_reader_reads_coiffe_and_not_hat(self):
        """Le cas concret, pour qu'un changement de traduction se voie."""
        char = self._build()
        texte = self._texte(char, 'fr')
        self.assertIn('Coiffe:', texte)
        self.assertNotIn('Hat:', texte)


class TheBaseStatLinesAreTranslatedTests(TestCase):

    def _deux_lignes(self, langue):
        from chardata.translation_util import localized_stat_name
        from fashionistapulp.dofus_constants import STATS_NAMES
        from fashionistapulp.structure import set_current_game_version
        set_current_game_version('dofus3')
        with override(langue):
            stats = ' / '.join('%s %d' % (localized_stat_name(nom), 100 + i)
                               for i, (nom, _c) in enumerate(STATS_NAMES))
            return '%s: %s\n%s: %s' % (gettext('Points'), stats,
                                       gettext('Scrolls'), stats)

    def test_both_lines_read_back_in_five_languages(self):
        from chardata.text_build_import import read_items
        from fashionistapulp.dofus_constants import STATS_NAMES
        attendu = {nom: 100 + i for i, (nom, _c) in enumerate(STATS_NAMES)}
        for langue in LANGUES:
            with self.subTest(langue=langue):
                with override(langue):
                    lu = read_items(self._deux_lignes(langue), 'dofus3', langue)
                self.assertEqual(attendu, lu['base_points'])
                self.assertEqual(attendu, lu['base_scrolled'])

    def test_the_word_scrolls_is_translated_everywhere(self):
        """Le seul mot qui manquait aux catalogues."""
        anglais = 'Scrolls'
        for langue in LANGUES:
            with self.subTest(langue=langue):
                with override(langue):
                    mot = gettext(anglais)
                self.assertTrue(mot)
                if langue != 'en':
                    self.assertNotEqual(anglais, mot)


class TheRoundTripSurvivesTests(_AvecUnBuild):

    def test_the_same_build_comes_back_in_the_five_languages(self):
        """Le garde qui tient les deux moities ensemble: traduire l'export
        sans apprendre a l'import rendait 6 pieces sur 16 en francais."""
        from chardata.text_build_import import read_items
        char = self._build()
        attendu = None
        for langue in LANGUES:
            with self.subTest(langue=langue):
                texte = self._texte(char, langue)
                with override(langue):
                    lu = read_items(texte, 'dofus3', langue)
                resume = (lu['char_class'], lu['char_level'],
                          len(lu['matched']))
                self.assertEqual(4, len(lu['matched']),
                                 [e['line'] for e in lu['matched']])
                if attendu is None:
                    attendu = resume
                else:
                    self.assertEqual(attendu, resume)

    def test_an_english_text_still_reads(self):
        """Ceux qui trainent deja sur un Discord portent l'anglais interne."""
        from chardata.text_build_import import read_items
        from fashionistapulp.structure import (get_structure,
                                               set_current_game_version)
        set_current_game_version('dofus3')
        structure = get_structure('dofus3')
        item = next(i for i in structure.types[200]['Hat']
                    if not i.removed and i.ankama_id)
        nom = structure.get_item_name_in_language(item, 'en')
        texte = 'Hat: %s\nPoints: Vitality 50\nScrolls: Vitality 101' % nom
        for langue in LANGUES:
            with self.subTest(langue=langue):
                with override(langue):
                    lu = read_items(texte, 'dofus3', langue)
                self.assertEqual(1, len(lu['matched']))
                self.assertEqual({'Vitality': 50}, lu['base_points'])
                self.assertEqual({'Vitality': 101}, lu['base_scrolled'])


class TheTablesComeFromTheCataloguesTests(TestCase):

    def test_nothing_is_copied_into_the_code(self):
        """Recopier les mots les figerait: une traduction corrigee ne serait
        plus lue."""
        from chardata.text_build_import import (_CARACTERISTIQUE_PAR_NOM,
                                                _mots_traduits)
        from chardata.inventory_view import _ocr_normalize
        from chardata.translation_util import localized_stat_name
        from fashionistapulp.structure import set_current_game_version
        set_current_game_version('dofus3')
        mots = _mots_traduits(['Scrolls'])
        self.assertIn('Scrolls', mots)
        for langue in LANGUES:
            with override(langue):
                self.assertIn(gettext('Scrolls'), mots)
                nom = _ocr_normalize(localized_stat_name('Vitality'))
                self.assertEqual('Vitality',
                                 _CARACTERISTIQUE_PAR_NOM.get(nom), langue)
