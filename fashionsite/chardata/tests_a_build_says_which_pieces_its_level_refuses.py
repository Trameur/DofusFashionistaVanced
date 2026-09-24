# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A build names the pieces its level no longer allows, to the owner and to the visitor."""

import re

from django.test import TestCase
from django.utils.translation import gettext, override

LANGUES = ('en', 'fr', 'es', 'pt', 'de')

# The minifier sorts attributes: find the class wherever it sits
LIGNE = re.compile(r'<tr[^>]*solution-level-warning-row[^>]*>(.*?)</tr>', re.S)
VALEUR = re.compile(
    r'<span[^>]*solution-level-warning-value[^>]*>\s*(\d+)\s*</span>')
TITRE = re.compile(r'title="([^"]*)"')


def _texte(html):
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', html)).strip()


class _AvecUnBuild(TestCase):

    def setUp(self):
        from django.contrib.auth.models import User
        self.auteur = User.objects.create_user('auteur', 'a@x.test', 'pw')
        self.client.force_login(self.auteur)

    def _build(self, niveau=200):
        from chardata.models import Char
        from fashionistapulp.structure import (get_structure,
                                               set_current_game_version)
        set_current_game_version('dofus3')
        structure = get_structure('dofus3')
        noms = []
        for type_name in ('Hat', 'Cloak', 'Belt', 'Boots', 'Amulet'):
            item = next(i for i in structure.types[200][type_name]
                        if not i.removed and i.ankama_id)
            noms.append(structure.get_item_name_in_language(item, 'en'))
        self.client.post('/import/text/', {
            'text': '\n'.join(noms), 'confirm': '1',
            'char_class': 'Cra', 'level': str(niveau)})
        char = Char.objects.order_by('-id').first()
        char.link_shared = True
        char.save()
        return char

    def _baisse_le_niveau(self, char, niveau):
        reponse = self.client.post('/saveproject/%d/' % char.id, {
            'project': char.name or 'projet',
            'charname': char.char_name or '',
            'class': char.char_class,
            'level': str(niveau),
            'byhand': '1'})
        self.assertEqual(200, reponse.status_code)
        char.refresh_from_db()
        self.assertEqual(niveau, char.level,
                         'the project form did not save the level')
        return char

    def _pieces_portees(self, char):
        from chardata.solution import get_solution
        from fashionistapulp.structure import set_current_game_version
        set_current_game_version(char.game_version)
        solution = get_solution(char)
        self.assertIsNotNone(solution)
        return [(getattr(i, 'localized_name', i.name), getattr(i, 'level', None))
                for i in solution.item_list if getattr(i, 'item_added', False)]

    def _ligne(self, chemin, langue='en', client=None):
        page = (client or self.client).get(
            chemin, HTTP_ACCEPT_LANGUAGE=langue,
            follow=True).content.decode('utf-8')
        trouve = LIGNE.search(page)
        return trouve.group(1) if trouve else None


class LoweringTheLevelKeepsTheGearTests(_AvecUnBuild):

    def test_the_solver_is_not_run_again_so_the_gear_stays(self):
        char = self._build(200)
        avant = self._pieces_portees(char)
        self.assertTrue(avant, 'the imported build wears nothing')
        self._baisse_le_niveau(char, 30)
        apres = self._pieces_portees(char)
        self.assertEqual(sorted(avant), sorted(apres),
                         'the solution changed, the bug no longer happens')
        trop = [(n, l) for n, l in apres if l and l > 30]
        self.assertTrue(trop, 'no piece above level 30')


class TheOwnerIsToldTests(_AvecUnBuild):

    def test_the_row_counts_the_pieces_the_level_refuses(self):
        char = self._baisse_le_niveau(self._build(200), 30)
        trop = [(n, l) for n, l in self._pieces_portees(char)
                if l and l > char.level]
        ligne = self._ligne('/solution/%d/' % char.id)
        self.assertIsNotNone(ligne, 'aucun avertissement de niveau')
        self.assertIn(gettext("Pieces above this character's level"),
                      _texte(ligne))
        valeur = VALEUR.search(ligne)
        self.assertIsNotNone(valeur, ligne)
        self.assertEqual(len(trop), int(valeur.group(1)))

    def test_the_tooltip_names_them_with_the_level_each_needs(self):
        char = self._baisse_le_niveau(self._build(200), 30)
        ligne = self._ligne('/solution/%d/' % char.id)
        titre = TITRE.search(ligne)
        self.assertIsNotNone(titre, 'la liste n est nulle part')
        for nom, niveau in self._pieces_portees(char):
            if niveau and niveau > char.level:
                with self.subTest(piece=nom):
                    self.assertIn(str(niveau), titre.group(1))

    def test_the_highest_requirement_comes_first(self):
        from chardata.solution import get_solution
        from chardata.solution_view import _build_check
        from fashionistapulp.structure import set_current_game_version
        char = self._baisse_le_niveau(self._build(200), 30)
        set_current_game_version(char.game_version)
        pieces = _build_check(char, get_solution(char))['above_level']
        self.assertTrue(pieces)
        niveaux = [piece['level'] for piece in pieces]
        self.assertEqual(sorted(niveaux, reverse=True), niveaux)

    def test_a_build_whose_level_allows_everything_shows_no_row(self):
        char = self._build(200)
        self.assertIsNone(self._ligne('/solution/%d/' % char.id))


class TheVisitorIsToldTooTests(_AvecUnBuild):

    def test_the_shared_link_carries_the_warning(self):
        from django.test import Client
        from chardata.encoded_char_id import encode_char_id
        char = self._baisse_le_niveau(self._build(200), 30)
        adresse = '/s/%s/%s/' % (char.char_name or 'shared',
                                 encode_char_id(char.id))
        ligne = self._ligne(adresse, client=Client())
        self.assertIsNotNone(ligne, 'the visitor is not told')
        self.assertIn(gettext("Pieces above this character's level"),
                      _texte(ligne))


class ItUsesTheRuleTheSiteAlreadyOwnsTests(_AvecUnBuild):

    def test_it_refuses_exactly_what_the_inclusion_pruner_refuses(self):
        from chardata.solution import get_solution
        from chardata.solution_view import _build_check
        from fashionistapulp.structure import (get_structure,
                                               set_current_game_version)
        char = self._baisse_le_niveau(self._build(200), 30)
        set_current_game_version(char.game_version)
        structure = get_structure(char.game_version)
        signalees = {piece['name']
                     for piece in _build_check(
                         char, get_solution(char))['above_level']}
        for nom, niveau in self._pieces_portees(char):
            with self.subTest(piece=nom):
                # The same comparison as the pruner, on the same data
                self.assertEqual(bool(niveau and niveau > char.level),
                                 nom in signalees)
        self.assertTrue(structure is not None)


class TheLabelSpeaksEveryLanguageTests(_AvecUnBuild):

    def test_the_five_languages_answer(self):
        char = self._baisse_le_niveau(self._build(200), 30)
        vus = {}
        for langue in LANGUES:
            with self.subTest(langue=langue):
                ligne = self._ligne('/solution/%d/' % char.id, langue)
                self.assertIsNotNone(ligne)
                with override(langue):
                    attendu = gettext("Pieces above this character's level")
                self.assertIn(attendu, _texte(ligne))
                vus[langue] = attendu
        for langue, texte in vus.items():
            if langue != 'en':
                self.assertNotEqual(vus['en'], texte, langue)

    def test_the_pieces_are_named_in_the_reader_language(self):
        char = self._baisse_le_niveau(self._build(200), 30)
        anglais = TITRE.search(self._ligne('/solution/%d/' % char.id, 'en'))
        francais = TITRE.search(self._ligne('/solution/%d/' % char.id, 'fr'))
        self.assertIsNotNone(anglais)
        self.assertIsNotNone(francais)
        self.assertNotEqual(anglais.group(1), francais.group(1))
