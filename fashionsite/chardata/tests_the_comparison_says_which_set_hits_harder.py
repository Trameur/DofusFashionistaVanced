# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The comparison page says which set hits harder in one turn."""

import re

from django.test import TestCase
from django.utils.translation import gettext, override

LANGUES = ('en', 'fr', 'es', 'pt', 'de')

# The minifier sorts attributes and squeezes spaces: find the line by its class
LIGNE = re.compile(r'<tr[^>]*compare-best-turn-row[^>]*>(.*?)</tr>', re.S)
NOTE = re.compile(r'<td[^>]*compare-best-turn-note[^>]*>(.*?)</td>', re.S)
CELLULE = re.compile(r'<td[^>]*>(.*?)</td>', re.S)


def _texte(html):
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', html)).strip()


class _AvecDeuxSets(TestCase):

    def setUp(self):
        # The comparison opens only builds the reader may see; without a logged-in owner it answers 404
        from django.contrib.auth.models import User
        self.auteur = User.objects.create_user('auteur', 'a@x.test', 'pw')
        self.client.force_login(self.auteur)

    def _build(self, types, char_class='Cra'):
        from chardata.models import Char
        from fashionistapulp.structure import (get_structure,
                                               set_current_game_version)
        set_current_game_version('dofus3')
        structure = get_structure('dofus3')
        noms = []
        for type_name in types:
            item = next(i for i in structure.types[200][type_name]
                        if not i.removed and i.ankama_id)
            noms.append(structure.get_item_name_in_language(item, 'en'))
        self.client.post('/import/text/', {
            'text': '\n'.join(noms), 'confirm': '1',
            'char_class': char_class, 'level': '200'})
        return Char.objects.order_by('-id').first()

    def _deux(self):
        premier = self._build(('Hat', 'Cloak', 'Belt', 'Boots', 'Amulet'))
        second = self._build(('Hat',))
        return premier, second

    def _page(self, premier, second, langue='en'):
        return self.client.get('/compare_sets/%d/%d/' % (premier.id, second.id),
                               HTTP_ACCEPT_LANGUAGE=langue,
                               follow=True).content.decode('utf-8')

    def _cellules(self, page):
        ligne = LIGNE.search(page)
        self.assertIsNotNone(ligne, 'the best-turn row is missing')
        return [_texte(c) for c in CELLULE.findall(ligne.group(1))]


class TheRowIsThereTests(_AvecDeuxSets):

    def test_each_set_gets_its_own_turn(self):
        premier, second = self._deux()
        cellules = self._cellules(self._page(premier, second))
        # icon, name, set 1, set 2, diff
        self.assertEqual(5, len(cellules), cellules)
        self.assertEqual(gettext('Best turn'), cellules[1])
        for valeur in cellules[2:4]:
            self.assertTrue(valeur.isdigit() or valeur == '-', valeur)

    def test_the_richer_set_hits_harder(self):
        premier, second = self._deux()
        cellules = self._cellules(self._page(premier, second))
        self.assertGreater(int(cellules[2]), int(cellules[3]))

    def test_the_diff_is_the_second_set_minus_the_first(self):
        premier, second = self._deux()
        cellules = self._cellules(self._page(premier, second))
        attendu = int(cellules[3]) - int(cellules[2])
        self.assertEqual(attendu, int(cellules[4]))
        self.assertLess(attendu, 0)


class ItSaysWhatItAssumedTests(_AvecDeuxSets):

    def test_the_note_repeats_the_spells_page_word_for_word(self):
        premier, second = self._deux()
        page = self._page(premier, second)
        note = NOTE.search(page)
        self.assertIsNotNone(note)
        texte = _texte(note.group(1))
        self.assertIn(gettext('One turn on a single target: average damage '
                              'and critical hit rate included. Buffs cast in '
                              'the turn count; none is assumed standing '
                              'before it.'), texte)
        self.assertIn(gettext('Spells at the highest level the character '
                              'reaches.'), texte)


class TheLabelSpeaksTheReaderLanguageTests(_AvecDeuxSets):

    def test_the_five_languages_answer(self):
        premier, second = self._deux()
        vus = {}
        for langue in LANGUES:
            with self.subTest(langue=langue):
                vus[langue] = self._cellules(
                    self._page(premier, second, langue))[1]
                self.assertTrue(vus[langue])
                if langue != 'en':
                    self.assertNotEqual(vus['en'], vus[langue])

    def test_the_french_reader_reads_french(self):
        premier, second = self._deux()
        with override('fr'):
            attendu = gettext('Best turn')
        self.assertEqual('Meilleur tour', attendu)
        self.assertEqual(attendu,
                         self._cellules(self._page(premier, second, 'fr'))[1])


class ABrokenSetDoesNotBreakThePageTests(TestCase):

    def test_a_set_whose_turn_fails_shows_a_dash_and_no_diff(self):
        from chardata.compare_sets_view import _best_turn_rows

        class _Casse(object):
            id = 'casse'
            char = None
            solution = None

        valeurs, diff, note = _best_turn_rows([_Casse(), _Casse()], 'dofus3')
        self.assertEqual({'casse': None}, valeurs)
        self.assertIsNone(diff)
        self.assertEqual('', note)
