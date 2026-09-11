# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Qui rend un build public, et par quelle porte.

Depuis le 11 septembre 2026 un build neuf est publie des qu'il porte un
stuff, donc la visibilite a cesse d'etre un detail de la page d'un build:
c'est une chose que son auteur doit pouvoir lire et changer d'un coup d'oeil
sur la liste de ses projets.

Et c'est aussi une chose que personne d'autre ne doit pouvoir changer.
Mesure du 11 septembre: les deux routes qui publient et depublient un build
repondaient a un GET, sans jeton. Une simple balise image sur n'importe
quelle page (`<img src="https://.../getsharinglink/123/">`) publiait donc le
build prive de tout lecteur connecte qui passait par la, et les
identifiants sont des entiers qui se suivent. Les tests d'ici gardent la
porte fermee dans les deux sens.
"""

import pickle

from django.contrib.auth.models import User
from django.test import Client, TestCase

from chardata.models import Char


def un_build(owner, **champs):
    defauts = {'name': 'Essai', 'char_name': 'Essai', 'char_class': 'Iop',
               'char_build': '', 'level': 200, 'link_shared': False,
               'owner': owner,
               'minimum_stats': pickle.dumps({}),
               'minimum_crits': pickle.dumps({}),
               'stats_weight': pickle.dumps({}),
               'options': pickle.dumps({}),
               'inclusions': pickle.dumps({}),
               'exclusions': pickle.dumps({}),
               'game_version': 'dofus3'}
    defauts.update(champs)
    return Char.objects.create(**defauts)


class NobodyPublishesYourBuildForYouTests(TestCase):

    def setUp(self):
        self.auteur = User.objects.create_user('auteur', 'a@x.test', 'pw')
        self.char = un_build(self.auteur)

    def test_a_get_can_no_longer_publish_a_build(self):
        """Le trou, referme. Un GET ne change plus rien, donc une image
        posee sur une page etrangere ne publie plus rien non plus."""
        self.client.force_login(self.auteur)
        reponse = self.client.get('/getsharinglink/%d/' % self.char.pk)
        self.assertEqual(405, reponse.status_code)
        self.assertFalse(Char.objects.get(pk=self.char.pk).link_shared)

    def test_a_get_can_no_longer_hide_one_either(self):
        """L'autre sens compte autant: depublier le build de quelqu'un le
        fait disparaitre de la galerie et casse les liens qu'il a
        partages."""
        self.char.link_shared = True
        self.char.save()
        self.client.force_login(self.auteur)
        reponse = self.client.get('/hidesharinglink/%d/' % self.char.pk)
        self.assertEqual(405, reponse.status_code)
        self.assertTrue(Char.objects.get(pk=self.char.pk).link_shared)

    def test_a_post_without_the_token_is_refused(self):
        """Le jeton est ce qui distingue un clic du lecteur d'un formulaire
        poste par une page etrangere."""
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.auteur)
        reponse = client.post('/getsharinglink/%d/' % self.char.pk)
        self.assertEqual(403, reponse.status_code)
        self.assertFalse(Char.objects.get(pk=self.char.pk).link_shared)

    def test_the_author_still_publishes_and_hides_with_a_post(self):
        """Le cas contraire, sans lequel une vue qui refuse tout passerait
        tous les tests ci-dessus."""
        self.client.force_login(self.auteur)
        reponse = self.client.post('/getsharinglink/%d/' % self.char.pk)
        self.assertEqual(200, reponse.status_code)
        self.assertIn('http', reponse.content.decode('utf-8'))
        self.assertTrue(Char.objects.get(pk=self.char.pk).link_shared)
        self.client.post('/hidesharinglink/%d/' % self.char.pk)
        self.assertFalse(Char.objects.get(pk=self.char.pk).link_shared)

    def test_a_stranger_is_refused_whatever_the_method(self):
        etranger = User.objects.create_user('etranger', 'e@x.test', 'pw')
        self.client.force_login(etranger)
        reponse = self.client.post('/getsharinglink/%d/' % self.char.pk)
        self.assertIn(reponse.status_code, (403, 404))
        self.assertFalse(Char.objects.get(pk=self.char.pk).link_shared)


class YourProjectsSayWhichOnesArePublicTests(TestCase):

    def setUp(self):
        self.auteur = User.objects.create_user('auteur', 'a@x.test', 'pw')
        self.client.force_login(self.auteur)

    def _page(self, langue='en'):
        return self.client.get('/loadprojects/',
                               HTTP_ACCEPT_LANGUAGE=langue
                               ).content.decode('utf-8')

    def test_a_public_build_says_so(self):
        un_build(self.auteur, name='Publie', link_shared=True)
        page = self._page()
        self.assertIn('In the gallery', page)
        self.assertIn('Make private', page)

    def test_a_build_waiting_for_gear_says_what_will_happen(self):
        """L'etat que le nouveau defaut a cree, et le seul que le lecteur ne
        peut pas deviner: le build n'est pas encore visible, et il le sera.
        Le taire serait publier sans prevenir."""
        un_build(self.auteur, name='En attente', auto_publish=True)
        page = self._page()
        self.assertIn('Public once it has gear', page)
        self.assertIn('Make private', page)

    def test_a_private_build_says_so_and_offers_to_publish(self):
        un_build(self.auteur, name='Prive')
        page = self._page()
        self.assertIn('Private', page)
        self.assertIn('Publish', page)
        # L'etat se lit sur la cellule et non sur le texte de la page: le
        # script porte les quatre libelles pour pouvoir les echanger sans
        # rechargement, donc chercher un libelle prouverait qu'il est dans
        # le script, pas dans une ligne.
        self.assertIn('data-visibility-state="private"', page)
        self.assertNotIn('data-visibility-state="public"', page)

    def test_the_column_is_there_in_french_too(self):
        un_build(self.auteur, name='Publie', link_shared=True)
        page = self._page('fr')
        self.assertIn('Dans la galerie', page)
        self.assertIn('Rendre priv', page)

    def test_each_row_carries_its_own_build(self):
        """Deux lignes, deux etats, deux boutons: un bouton qui agirait sur
        le mauvais build serait pire que pas de bouton du tout."""
        prive = un_build(self.auteur, name='Prive')
        public = un_build(self.auteur, name='Publie', link_shared=True)
        page = self._page()
        for char in (prive, public):
            self.assertIn('data-visibility-build="%d"' % char.pk, page)
        self.assertIn('data-visibility-state="public"', page)
        self.assertIn('data-visibility-state="private"', page)

    def test_a_guest_sees_no_switch(self):
        """L'attribut AVEC sa valeur, parce que le script de la page nomme
        le meme attribut sans valeur pour trouver ses cellules: chercher le
        nom seul aurait trouve le script et rien prouve."""
        self.client.logout()
        page = self._page()
        self.assertNotIn('data-visibility-build="', page)
        self.assertNotIn('>Visibility<', page)


class TheWordsAreTranslatedTests(TestCase):

    CHAINES = ('In the gallery', 'Public once it has gear', 'Private',
               'Make private', 'Publish', 'Visibility')

    def test_every_word_of_the_column_speaks_four_more_languages(self):
        from django.utils.translation import gettext, override
        muettes = []
        for langue in ('fr', 'es', 'pt', 'de'):
            with override(langue):
                for chaine in self.CHAINES:
                    if gettext(chaine) == chaine:
                        muettes.append((langue, chaine))
        self.assertEqual([], muettes)
