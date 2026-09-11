# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Les pieces qu'un build porte et que le catalogue n'a plus sont nommees.

La section 42 disait a l'auteur <<certains de ses objets n'existent plus dans
le jeu>>. Il ne pouvait pas savoir LESQUELS, donc il ne pouvait rien y faire.

264 objets du catalogue du 4 novembre 2025 n'ont plus le meme numero chez
nous. **222 d'entre eux sont pourtant toujours la**, sous un autre nombre,
parce que notre fournisseur a renumerote les montures: ceux-la sont RENDUS au
build (section 45) et ne sont pas nommes ici. Ne restent ici que les **42**
sans equivalent, les versions sauvages, que la source ne liste plus.

Cette correction est venue le lendemain de la section 44, qui avait ecrit
trop vite que les 264 avaient quitte notre catalogue. Leurs noms sont lus sur
ce catalogue-la, table `item_names` comprise: les cinq langues du site y sont.

La phrase dit <<notre catalogue>> et non <<le jeu>>: qu'un objet ait quitte
notre catalogue ne prouve pas qu'il ait quitte le jeu
([[absence-in-data-is-not-absence-in-game]]).
"""

import pickle

from django.test import SimpleTestCase, TestCase

from chardata.legacy_missing import missing_names, name_of_missing
from chardata.models import Char


class TheNamesComeFromTheLastCatalogueThatHadThemTests(SimpleTestCase):

    #: Trois montures SAUVAGES, avec leur identifiant Ankama et leur nom
    #: francais, lus sur le catalogue du 4 novembre 2025.
    #:
    #: Sauvages exprès: la verification du lendemain a montre que notre
    #: fournisseur avait RENUMEROTE les montures apprivoisees, que notre
    #: catalogue a donc toujours (section 45). <<Dragodinde Ebene>> etait un
    #: temoin ici le premier jour et n'en est plus un: elle est rendue au
    #: build, pas nommee comme perdue. Seules les sauvages le restent.
    TEMOINS = (
        (1, 'Wild Almond Dragoturkey', 'Dragodinde Amande Sauvage'),
        (6, 'Wild Ginger Dragoturkey', 'Dragodinde Rousse Sauvage'),
        (167, 'Wild Golden Seemyool', 'Muldo Doré Sauvage'),
    )

    def test_a_vanished_pet_still_has_a_name(self):
        for ankama, anglais, francais in self.TEMOINS:
            with self.subTest(ankama=ankama):
                self.assertEqual(anglais,
                                 name_of_missing('dofus3', ankama, 'en'))
                self.assertEqual(francais,
                                 name_of_missing('dofus3', ankama, 'fr'))

    def test_the_five_languages_are_all_there(self):
        for langue in ('en', 'fr', 'es', 'pt', 'de'):
            with self.subTest(langue=langue):
                nom = name_of_missing('dofus3', 1, langue)
                self.assertTrue(nom)
                if langue != 'en':
                    self.assertNotEqual(name_of_missing('dofus3', 1, 'en'), nom)

    def test_a_build_may_store_the_mount_offset_instead(self):
        """Selon le jour ou le build a ete enregistre, la meme monture est
        stockee en ankama nu ou decalee de l'espace des montures. Les deux
        doivent nommer la meme bete."""
        self.assertEqual(name_of_missing('dofus3', 1, 'en'),
                         name_of_missing('dofus3', 1000001, 'en'))

    def test_an_item_the_catalogue_still_has_is_not_named_here(self):
        """La table ne porte que les disparus: y mettre un objet vivant
        ferait dire a la page qu'il manque alors qu'il est la."""
        self.assertIsNone(name_of_missing('dofus3', 44, 'en'))

    def test_another_version_has_no_table(self):
        for version in ('retro', 'touch', 'dofus2', 'beta', ''):
            with self.subTest(version=version):
                self.assertIsNone(name_of_missing(version, 1, 'en'))

    def test_a_nonsense_id_names_nothing(self):
        self.assertIsNone(name_of_missing('dofus3', 999999999, 'en'))
        self.assertIsNone(name_of_missing('dofus3', None, 'en'))


class _Mini(object):
    def __init__(self, par_slot):
        self.item_per_slot = dict(par_slot)


class TheBuildListsWhatItLostTests(TestCase):

    def _char(self):
        return Char.objects.create(
            name='Essai', char_name='', char_class='Cra', char_build='',
            level=200, link_shared=True, minimum_stats=pickle.dumps({}),
            minimum_crits=pickle.dumps({}), stats_weight=pickle.dumps({}),
            options=pickle.dumps({}), inclusions=pickle.dumps({}),
            exclusions=pickle.dumps({}), game_version='dofus3')

    def test_the_pet_that_vanished_is_named(self):
        from fashionistapulp.structure import set_current_game_version
        set_current_game_version('dofus3')
        noms = missing_names(self._char(), _Mini({'pet': 1}), 'fr')
        self.assertEqual(['Dragodinde Amande Sauvage'], noms)

    def test_a_piece_that_is_still_there_is_not_listed(self):
        from fashionistapulp.structure import (get_structure,
                                               set_current_game_version)
        set_current_game_version('dofus3')
        structure = get_structure('dofus3')
        chapeau = next(i for i in structure.types[200]['Hat']
                       if not i.removed and i.ankama_id)
        self.assertEqual([], missing_names(self._char(),
                                           _Mini({'hat': chapeau.id}), 'en'))

    def test_two_slots_holding_the_same_lost_beast_name_it_once(self):
        from fashionistapulp.structure import set_current_game_version
        set_current_game_version('dofus3')
        noms = missing_names(self._char(), _Mini({'pet': 1, 'shield': 1}), 'en')
        self.assertEqual(['Wild Almond Dragoturkey'], noms)


class TheSentenceNamesThemTests(TestCase):

    def _build_avec_familier_disparu(self):
        from chardata.char_blobs import read_char_blob
        from fashionistapulp.structure import (get_structure,
                                               set_current_game_version)
        set_current_game_version('dofus3')
        structure = get_structure('dofus3')
        item = next(i for i in structure.types[200]['Hat']
                    if not i.removed and i.ankama_id)
        self.client.post('/import/text/', {
            'text': structure.get_item_name_in_language(item, 'en'),
            'confirm': '1', 'char_class': 'Cra', 'level': '200'})
        char = Char.objects.order_by('-id').first()
        mini = read_char_blob(char.minimal_solution, None, 'minimal_solution',
                              char)
        mini.item_per_slot['pet'] = 1
        char.minimal_solution = pickle.dumps(mini)
        char.link_shared = True
        char.save()
        return char

    def test_the_sentence_carries_the_name(self):
        from chardata.gallery_visibility import sentence_for
        char = self._build_avec_familier_disparu()
        phrase = sentence_for(char)
        self.assertIn('Wild Almond Dragoturkey', phrase)
        self.assertIn('our catalogue no longer has', phrase)

    def test_it_says_our_catalogue_and_not_the_game(self):
        """Qu'un objet ait quitte notre catalogue ne prouve pas qu'il ait
        quitte le jeu, et la phrase ne doit pas l'affirmer."""
        from chardata.gallery_visibility import sentence_for
        phrase = sentence_for(self._build_avec_familier_disparu())
        self.assertNotIn('no longer in the game', phrase)

    def test_the_french_reader_gets_the_french_name(self):
        from django.utils.translation import override
        from chardata.gallery_visibility import sentence_for
        char = self._build_avec_familier_disparu()
        with override('fr'):
            phrase = sentence_for(char)
        self.assertIn('Dragodinde Amande Sauvage', phrase)
        self.assertIn('notre catalogue', phrase)

    def test_the_projects_list_shows_the_name(self):
        from django.contrib.auth.models import User
        auteur = User.objects.create_user('auteur', 'a@x.test', 'pw')
        char = self._build_avec_familier_disparu()
        char.owner = auteur
        char.save()
        self.client.force_login(auteur)
        page = self.client.get('/loadprojects/', HTTP_ACCEPT_LANGUAGE='en'
                               ).content.decode('utf-8')
        self.assertIn('Wild Almond Dragoturkey', page)
