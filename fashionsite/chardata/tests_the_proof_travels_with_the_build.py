# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The solver's proof travels with the build, in the pasted text and in the API."""

import pickle

from django.test import RequestFactory, TestCase
from django.utils.translation import gettext, override

from fashionistapulp.lpproblem import TIME_LIMIT_SECONDS

PROUVE = ('Proven optimum. The solver checked that no other legal '
          'combination scores higher on your criteria.')
NON_PROUVE = ('Best set found in %(limit)s seconds. The solver ran out of '
              'time before it could prove that nothing beats it, so this is '
              'the best it reached, not a proof.')


def _char_partage():
    from chardata.models import Char
    from django.test import Client
    from fashionistapulp.structure import get_structure, set_current_game_version
    set_current_game_version('dofus3')
    structure = get_structure('dofus3')
    item = next(i for i in structure.types[200]['Hat'] if not i.removed)
    Client().post('/import/text/', {
        'text': structure.get_item_name_in_language(item, 'en'),
        'confirm': '1', 'char_class': 'Cra', 'level': '200'})
    char = Char.objects.order_by('-id').first()
    char.link_shared = True
    char.save()
    return char


def _pose_le_fait(char, proven, seconds=3.2):
    try:
        minimal = pickle.loads(char.minimal_solution)
    except Exception as erreur:
        raise AssertionError(
            'the freshly imported build has no readable solution: %s' % erreur)
    if proven is None:
        for nom in ('proven', 'solve_seconds'):
            if hasattr(minimal, nom):
                delattr(minimal, nom)
    else:
        minimal.proven = proven
        minimal.solve_seconds = seconds
    char.minimal_solution = pickle.dumps(minimal)
    char.save()


class TheShareTextCarriesTheProofTests(TestCase):

    def _texte(self, char):
        from chardata.solution import get_solution
        from chardata.solution_view import _build_share_text
        requete = RequestFactory().get('/')
        requete.game_version = 'dofus3'
        return _build_share_text(requete, char, get_solution(char))

    def test_a_proven_optimum_says_so(self):
        char = _char_partage()
        _pose_le_fait(char, True)
        texte = self._texte(char)
        self.assertIn(PROUVE, texte)
        self.assertNotIn('not a proof', texte)

    def test_a_timeout_says_it_is_not_a_proof(self):
        char = _char_partage()
        _pose_le_fait(char, False)
        texte = self._texte(char)
        self.assertIn(NON_PROUVE % {'limit': TIME_LIMIT_SECONDS}, texte)
        self.assertNotIn('Proven optimum', texte)

    def test_an_old_solution_says_nothing_rather_than_guessing(self):
        char = _char_partage()
        _pose_le_fait(char, None)
        texte = self._texte(char)
        self.assertNotIn('Proven optimum', texte)
        self.assertNotIn('not a proof', texte)

    def test_the_line_comes_before_the_link_and_after_the_gear(self):
        char = _char_partage()
        _pose_le_fait(char, True)
        texte = self._texte(char)
        self.assertLess(texte.index('Hat:'), texte.index(PROUVE))
        self.assertLess(texte.index(PROUVE), texte.index('https://'))

    def test_the_text_uses_the_same_sentences_as_the_panel(self):
        char = _char_partage()
        _pose_le_fait(char, True)
        with override('fr'):
            texte = self._texte(char)
            self.assertIn(gettext(PROUVE), texte)
            self.assertNotEqual(gettext(PROUVE), PROUVE,
                                'the French catalogue lost the panel sentence')

    def test_the_page_offers_the_same_text_to_a_shared_link_visitor(self):
        from chardata.util import shared_build_path
        char = _char_partage()
        _pose_le_fait(char, False)
        page = self.client.get(shared_build_path(char)).content.decode('utf-8')
        self.assertIn('build_share_text', page)
        self.assertIn('not a proof', page)


class TheApiCarriesTheProofTests(TestCase):

    def _detail(self, char):
        from chardata.encoded_char_id import encode_char_id
        return self.client.get(
            '/api/v1/shared-builds/%s/' % encode_char_id(char.id)).json()

    def test_proven_false_and_unknown_are_three_different_answers(self):
        for fait, attendu in ((True, True), (False, False), (None, None)):
            char = _char_partage()
            _pose_le_fait(char, fait)
            solveur = self._detail(char)['solver']
            self.assertIs(solveur['proven'], attendu)

    def test_the_time_limit_is_the_solver_own(self):
        char = _char_partage()
        _pose_le_fait(char, False)
        solveur = self._detail(char)['solver']
        self.assertEqual(TIME_LIMIT_SECONDS, solveur['time_limit_seconds'])
        self.assertEqual(3.2, solveur['seconds'])

    def test_the_list_does_not_pay_for_it(self):
        char = _char_partage()
        _pose_le_fait(char, True)
        lignes = self.client.get('/api/v1/shared-builds/').json()['results']
        self.assertTrue(lignes)
        self.assertNotIn('solver', lignes[0])
