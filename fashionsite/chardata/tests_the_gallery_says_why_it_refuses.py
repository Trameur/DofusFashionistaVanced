# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Un build publie que la galerie n'affiche pas le dit a son auteur.

Compte du 11 septembre 2026 sur la copie de production: **1476 des 1980
builds partages qui ont une solution sont ecartes de la galerie, soit
74,5 %**. Les raisons se cumulent: emplacements perimes 1382, objets absents
du catalogue 1083, conditions non tenues 1050. Une cause de fond est l'age:
368 des 3519 objets que la migration de novembre 2025 connaissait ont depuis
disparu du catalogue.

Rien de tout cela n'etait dit. L'auteur publiait, ne voyait son build nulle
part, et depuis que les builds sont publics par defaut (section 37) sa propre
page lui affirmait meme <<Dans la galerie>>. C'etait faux trois fois sur
quatre, et c'est exactement ce qu'une regle de la boucle interdit: une phrase
du site qui n'est pas vraie.

Ce lot ne change pas la regle de la galerie, il la rend visible.
"""

import pickle

from django.contrib.auth.models import User
from django.test import TestCase

from chardata.gallery_visibility import refusal_reason, refusal_sentence
from chardata.models import Char


class TheReasonIsReadOffTheBuildTests(TestCase):

    def _char(self, **champs):
        defauts = {'name': 'Essai', 'char_name': '', 'char_class': 'Cra',
                   'char_build': '', 'level': 200, 'link_shared': True,
                   'minimal_solution': b'', 'minimum_stats': pickle.dumps({}),
                   'minimum_crits': pickle.dumps({}),
                   'stats_weight': pickle.dumps({}),
                   'options': pickle.dumps({}),
                   'inclusions': pickle.dumps({}),
                   'exclusions': pickle.dumps({}),
                   'game_version': 'dofus3'}
        defauts.update(champs)
        return Char.objects.create(**defauts)

    def test_a_private_build_is_never_asked(self):
        """La question ne se pose pas: la page dit deja qu'il est prive."""
        self.assertIsNone(refusal_reason(self._char(link_shared=False)))

    def test_a_deleted_build_is_never_asked(self):
        self.assertIsNone(refusal_reason(self._char(deleted=True)))

    def test_a_published_build_with_no_gear_says_so(self):
        """La galerie et le sitemap l'ecartent deja, et sa page /s/ repond
        404: le lecteur merite de savoir pourquoi son lien est mort."""
        self.assertEqual('no_solution', refusal_reason(self._char()))

    def test_each_reason_has_a_sentence_that_says_what_to_do(self):
        """Une raison sans suite laisse l'auteur devant un fait accompli."""
        for cle in ('missing_items', 'outdated_slots', 'conditions',
                    'no_solution'):
            with self.subTest(cle=cle):
                phrase = refusal_sentence(cle)
                self.assertIn('Not shown in the gallery', phrase)
                self.assertGreater(len(phrase), 40, phrase)
        self.assertEqual('', refusal_sentence(None))

    def test_the_sentences_speak_four_more_languages(self):
        from django.utils.translation import gettext, override
        muettes = []
        for langue in ('fr', 'es', 'pt', 'de'):
            with override(langue):
                for cle in ('missing_items', 'outdated_slots', 'conditions',
                            'no_solution'):
                    with override('en'):
                        anglais = refusal_sentence(cle)
                    if gettext(anglais) == anglais:
                        muettes.append((langue, cle))
        self.assertEqual([], muettes)


class TheAuthorSeesItOnHisOwnPagesTests(TestCase):

    def setUp(self):
        self.auteur = User.objects.create_user('auteur', 'a@x.test', 'pw')
        self.client.force_login(self.auteur)

    def _publie_sans_stuff(self):
        from chardata.models import Char
        self.client.post('/createproject/', {
            'project': 'Mon build', 'charname': 'Moi', 'level': '200',
            'class': 'Cra', 'byhand': 'x'})
        char = Char.objects.order_by('-id').first()
        char.owner = self.auteur
        char.link_shared = True
        char.minimal_solution = b''
        char.save()
        return char

    def test_the_projects_list_replaces_the_promise_with_the_reason(self):
        """<<Dans la galerie>> etait faux: la raison prend sa place."""
        self._publie_sans_stuff()
        page = self.client.get('/loadprojects/', HTTP_ACCEPT_LANGUAGE='en'
                               ).content.decode('utf-8')
        self.assertIn('Not shown in the gallery', page)
        self.assertNotIn('>In the gallery<', page)

    def _publie_avec_un_objet_retire(self):
        """Le vrai cas de production: un objet que le jeu a retire.

        1083 builds partages en portent au moins un. On le reproduit en
        posant dans un emplacement un identifiant que le catalogue n'a pas,
        ce qui est exactement ce que devient un objet supprime.
        """
        from chardata.char_blobs import read_char_blob
        from fashionistapulp.structure import (get_structure,
                                               set_current_game_version)
        import pickle as _pickle
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
        mini.item_per_slot['hat'] = 999999999
        char.minimal_solution = _pickle.dumps(mini)
        char.owner = self.auteur
        char.link_shared = True
        char.save()
        return char

    def test_the_build_page_says_it_too(self):
        char = self._publie_avec_un_objet_retire()
        page = self.client.get('/solution/%d/' % char.id,
                               HTTP_ACCEPT_LANGUAGE='en'
                               ).content.decode('utf-8')
        self.assertIn('gallery_refusal', page)
        self.assertIn('Not shown in the gallery', page)

    def test_a_build_the_gallery_accepts_keeps_its_promise(self):
        """Le cas contraire, sans lequel une page qui refuserait tout
        passerait les deux tests ci-dessus."""
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
        char.owner = self.auteur
        char.link_shared = True
        char.save()
        self.assertIsNone(refusal_reason(char))
        page = self.client.get('/loadprojects/', HTTP_ACCEPT_LANGUAGE='en'
                               ).content.decode('utf-8')
        self.assertIn('In the gallery', page)
        self.assertNotIn('Not shown in the gallery', page)

    def test_the_reason_is_in_the_reader_language(self):
        self._publie_sans_stuff()
        page = self.client.get('/loadprojects/', HTTP_ACCEPT_LANGUAGE='fr'
                               ).content.decode('utf-8')
        self.assertIn('Pas montr', page)
        self.assertIn('galerie', page)
