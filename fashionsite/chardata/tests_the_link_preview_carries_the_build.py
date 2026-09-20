# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A shared link's preview carries the build and the solver's verdict."""

import re
from types import SimpleNamespace

from django.test import SimpleTestCase, TestCase

from chardata.solution_view import (_OG_PIECES_MAX_CHARS,
                                    _build_og_description,
                                    shared_build_path)
from chardata.tests_the_gallery_shows_the_proof import (_build_partage,
                                                        _pose_le_fait)

PROUVE = 'Proven optimum.'
LIMITE = 'Best found at the time limit, not a proof.'
PHRASE_DU_SITE = 'Like it, comment it, copy it.'


def _description(page):
    balises = re.findall(r'<meta[^>]*og:description[^>]*>', page)
    assert len(balises) == 1, balises
    return re.search(r'content="([^"]*)"', balises[0]).group(1)


class ThePreviewNamesTheBuildTests(TestCase):

    def _page(self, char, langue='en'):
        reponse = self.client.get(shared_build_path(char),
                                  HTTP_ACCEPT_LANGUAGE=langue, follow=True)
        self.assertEqual(200, reponse.status_code)
        return reponse.content.decode('utf-8')

    def _chapeau(self, langue):
        from fashionistapulp.structure import get_structure
        structure = get_structure('dofus3')
        item = next(i for i in structure.types[200]['Hat'] if not i.removed)
        return structure.get_item_name_in_language(item, langue)

    def test_a_proven_build_says_so_with_its_pieces(self):
        char = _build_partage('ApercuProuve')
        _pose_le_fait(char, True)
        description = _description(self._page(char))
        self.assertIn('Cra lvl 200, Dofus 3: ', description)
        self.assertIn(self._chapeau('en'), description)
        self.assertTrue(description.endswith(PROUVE), description)
        self.assertNotIn(PHRASE_DU_SITE, description)
        self.assertNotIn('\n', description)
        self.assertNotIn('<', description)
        self.assertLess(len(description), 320)

    def test_a_timeout_is_not_sold_as_a_proof(self):
        char = _build_partage('ApercuLimite')
        _pose_le_fait(char, False)
        description = _description(self._page(char))
        self.assertTrue(description.endswith(LIMITE), description)
        self.assertNotIn(PROUVE, description)

    def test_a_build_from_before_the_fact_keeps_quiet(self):
        char = _build_partage('ApercuAncien')
        _pose_le_fait(char, None)
        description = _description(self._page(char))
        self.assertIn(self._chapeau('en'), description)
        self.assertNotIn(PROUVE, description)
        self.assertNotIn(LIMITE, description)

    def test_the_preview_speaks_the_language_of_the_page(self):
        char = _build_partage('ApercuFrancais')
        _pose_le_fait(char, True)
        description = _description(self._page(char, 'fr'))
        # The class is translated too: the expected name comes from the page's table, in its language
        from django.utils import translation
        from chardata.translation_util import LOCALIZED_CHARACTER_CLASSES
        with translation.override('fr'):
            classe = str(LOCALIZED_CHARACTER_CLASSES['Cra'])
        self.assertNotEqual('Cra', classe)
        self.assertIn('%s niv. 200, Dofus 3: ' % classe, description)
        self.assertIn(self._chapeau('fr'), description)
        self.assertTrue(description.endswith('Optimum démontré.'), description)

    def test_the_title_still_names_the_build(self):
        char = _build_partage('ApercuTitre')
        page = self._page(char)
        titre = re.findall(r'<meta[^>]*og:title[^>]*>', page)
        self.assertEqual(1, len(titre), titre)
        self.assertIn('ApercuTitre', titre[0])


class TheListIsCutAtANameNotInsideOneTests(SimpleTestCase):

    def _solution(self, noms):
        pieces = [SimpleNamespace(name='interne%d' % i, localized_name=nom,
                                  item_added=True)
                  for i, nom in enumerate(noms)]
        return SimpleNamespace(items={'Hat': pieces})

    def _char(self):
        return SimpleNamespace(char_class='Cra', level=200,
                               game_version='dofus3')

    def test_a_long_build_is_cut_between_two_names_with_the_count(self):
        noms = ['Piece numero %02d du build' % i for i in range(20)]
        description = _build_og_description(self._char(),
                                            self._solution(noms), True)
        self.assertIn('and ', description)
        self.assertRegex(description, r', and \d+ more\. Proven optimum\.$')
        garde = description.split(': ', 1)[1].split(', and ')[0]
        for morceau in garde.split(', '):
            self.assertIn(morceau, noms, morceau)
        self.assertLessEqual(len(garde), _OG_PIECES_MAX_CHARS)
        combien = int(re.search(r'and (\d+) more', description).group(1))
        self.assertEqual(20, len(garde.split(', ')) + combien)

    def test_a_short_build_lists_everything_and_counts_nothing(self):
        noms = ['Coiffe', 'Cape', 'Amulette']
        description = _build_og_description(self._char(),
                                            self._solution(noms), False)
        self.assertEqual('Cra lvl 200, Dofus 3: Coiffe, Cape, Amulette. '
                         + LIMITE, description)

    def test_an_empty_build_has_no_colon_and_no_list(self):
        description = _build_og_description(self._char(),
                                            self._solution([]), None)
        self.assertEqual('Cra lvl 200, Dofus 3.', description)

    def test_a_piece_not_added_is_not_listed(self):
        piece = SimpleNamespace(name='NoItem', localized_name='rien',
                                item_added=False)
        description = _build_og_description(
            self._char(), SimpleNamespace(items={'Hat': [piece]}), None)
        self.assertEqual('Cra lvl 200, Dofus 3.', description)


class TheCountIsTranslatedTests(SimpleTestCase):

    def test_the_count_sentence_exists_in_the_four_catalogues(self):
        import gettext
        import os
        from django.conf import settings
        for langue in ('fr', 'es', 'pt', 'de'):
            t = gettext.translation('django',
                                    os.path.join(settings.BASE_DIR, 'locale'),
                                    languages=[langue])
            phrase = t.gettext('and %(count)d more')
            self.assertNotEqual('and %(count)d more', phrase, langue)
            self.assertIn('%(count)d', phrase, langue)
