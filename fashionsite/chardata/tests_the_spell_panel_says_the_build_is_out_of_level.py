# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The spell panel says when the build outgrows the character's level."""

import re

from django.test import TestCase
from django.utils.translation import gettext, override

LANGUES = ('en', 'fr', 'es', 'pt', 'de')

# the minifier sorts attributes; match the class anywhere in the tag
BLOC = re.compile(
    r'<div[^>]*best-combo-level-warning[^>]*>(.*?)</div>\s*</div>', re.S)
VALEUR = re.compile(
    r'<span[^>]*best-combo-level-warning-value[^>]*>\s*(\d+)\s*</span>')
LIGNE_DU_BUILD = re.compile(
    r'<span[^>]*solution-level-warning-value[^>]*>\s*(\d+)\s*</span>')


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
        self.assertEqual(niveau, char.level)
        return char

    def _page(self, chemin, langue='en'):
        return self.client.get(chemin, HTTP_ACCEPT_LANGUAGE=langue,
                               follow=True).content.decode('utf-8')

    def _compte_sur_le_panneau(self, char, langue='en'):
        trouve = VALEUR.search(self._page('/spells/%d/' % char.id, langue))
        return int(trouve.group(1)) if trouve else None

    def _compte_sur_le_build(self, char, langue='en'):
        trouve = LIGNE_DU_BUILD.search(
            self._page('/solution/%d/' % char.id, langue))
        return int(trouve.group(1)) if trouve else None

    def _pieces_hors_niveau(self, char):
        from chardata.solution import get_solution
        from chardata.solution_view import pieces_above_the_character_level
        from fashionistapulp.structure import set_current_game_version
        set_current_game_version(char.game_version)
        return pieces_above_the_character_level(char, get_solution(char))


class ThePanelSaysItTests(_AvecUnBuild):

    def test_a_build_lowered_below_its_gear_really_keeps_it(self):
        char = self._baisse_le_niveau(self._build(200), 30)
        trop = self._pieces_hors_niveau(char)
        self.assertTrue(trop, 'no piece above level 30')
        self.assertTrue(all(piece['level'] > 30 for piece in trop))

    def test_the_panel_counts_them(self):
        char = self._baisse_le_niveau(self._build(200), 30)
        attendu = len(self._pieces_hors_niveau(char))
        self.assertEqual(attendu, self._compte_sur_le_panneau(char))

    def test_the_panel_and_the_build_page_say_the_same_number(self):
        """One rule, one place: both pages call the same function."""
        char = self._baisse_le_niveau(self._build(200), 30)
        self.assertEqual(self._compte_sur_le_build(char),
                         self._compte_sur_le_panneau(char))

    def test_a_build_within_its_level_says_nothing(self):
        char = self._build(200)
        self.assertEqual([], self._pieces_hors_niveau(char))
        self.assertIsNone(self._compte_sur_le_panneau(char))

    def test_the_panel_names_the_pieces_it_counts(self):
        char = self._baisse_le_niveau(self._build(200), 30)
        page = self._page('/spells/%d/' % char.id)
        bloc = BLOC.search(page)
        self.assertIsNotNone(bloc)
        for piece in self._pieces_hors_niveau(char):
            self.assertIn(piece['name'], page)


class TheLabelIsTheOneTheBuildPageUsesTests(_AvecUnBuild):
    """Reuses the build page's label; already translated."""

    ETIQUETTE = "Pieces above this character's level"

    def test_the_five_languages_have_it(self):
        for langue in LANGUES:
            with self.subTest(langue=langue):
                with override(langue):
                    traduite = gettext(self.ETIQUETTE)
                self.assertTrue(traduite)
                if langue != 'en':
                    self.assertNotEqual(self.ETIQUETTE, traduite,
                                        'pas traduite en %s' % langue)

    def test_the_panel_shows_it_in_the_readers_language(self):
        char = self._baisse_le_niveau(self._build(200), 30)
        for langue in LANGUES:
            with self.subTest(langue=langue):
                with override(langue):
                    attendue = gettext(self.ETIQUETTE)
                self.assertIn(attendue,
                              self._page('/spells/%d/' % char.id, langue))


class TheRuleLivesInOnePlaceTests(TestCase):

    def test_the_build_page_calls_the_same_function(self):
        import io
        import os
        chemin = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              'solution_view.py')
        with io.open(chemin, encoding='utf-8') as fichier:
            source = fichier.read()
        self.assertEqual(1, source.count('def pieces_above_the_character_level'))
        self.assertIn('above_level = pieces_above_the_character_level(',
                      source)

    def test_the_panel_pays_only_for_this_rule(self):
        """_build_check also scores every candidate slot, which is expensive; the panel must not call it for a number comparison."""
        import io
        import os
        chemin = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              'spells_view.py')
        with io.open(chemin, encoding='utf-8') as fichier:
            source = fichier.read()
        self.assertIn('pieces_above_the_character_level', source)
        self.assertNotIn('_build_check', source)
