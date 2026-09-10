# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""La preuve voyage avec le build.

Le panneau <<Pourquoi ce resultat ?>> dit sur la page si le solveur a
DEMONTRE l'optimum ou rendu le meilleur set atteint a la limite de temps.
C'est la phrase de la section 2.3 du plan, celle qu'aucun systeme generatif
ne peut ecrire sur sa propre sortie. Elle ne quittait pas la page: ni le
texte colle sur un Discord ni l'API publique ne la portaient, et c'est la
que les builds se discutent.
"""

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
    """Ecrit le fait dans le pickle, la ou le solveur l'ecrit lui-meme.

    Le garde `test_no_column_is_unpickled_bare` refuse un `pickle.loads`
    d'une colonne stockee hors d'un try, et il a raison en production. Ici le
    try ne cache rien: un build qui vient d'etre importe et dont la solution
    ne se relit pas est une faute du test, dite en clair.
    """
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
        """None n'est pas False: un pickle d'avant le fait ne sait pas, et
        <<pas prouve>> serait une affirmation, pas une absence."""
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
        """Memes msgids que le panneau, donc la page et le texte colle ne
        peuvent pas se contredire, dans aucune langue."""
        char = _char_partage()
        _pose_le_fait(char, True)
        with override('fr'):
            texte = self._texte(char)
            self.assertIn(gettext(PROUVE), texte)
            self.assertNotEqual(gettext(PROUVE), PROUVE,
                                'the French catalogue lost the panel sentence')

    def test_the_page_offers_the_same_text_to_a_shared_link_visitor(self):
        """Le texte est fait pour celui qui recoit le lien: il doit le voir
        depuis /s/ et pas seulement depuis sa propre page."""
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
        """Une copie du 90 ici promettrait une limite que le solveur
        n'utilise plus le jour ou elle change: la valeur est importee."""
        char = _char_partage()
        _pose_le_fait(char, False)
        solveur = self._detail(char)['solver']
        self.assertEqual(TIME_LIMIT_SECONDS, solveur['time_limit_seconds'])
        self.assertEqual(3.2, solveur['seconds'])

    def test_the_list_does_not_pay_for_it(self):
        """La liste est paginee et cachee; depickler chaque ligne pour un
        champ que personne n'y lit serait payer pour rien."""
        char = _char_partage()
        _pose_le_fait(char, True)
        lignes = self.client.get('/api/v1/shared-builds/').json()['results']
        self.assertTrue(lignes)
        self.assertNotIn('solver', lignes[0])
