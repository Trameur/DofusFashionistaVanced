# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Un build neuf est public des qu'il porte quelque chose.

Thibaud, le 11 septembre 2026, capture de DofusBook a l'appui: <<de base les
stuffs sont publics dans dofus book et deviennent confidentiel que si on
choisit l'option ... je pense que ca serait tres benefique pour dofus
fashionista de rendre les builds publics par defaut ?>>, puis <<oui pour tes
questions sur le build par defaut>> sur le dessin ecrit.

Ce qui est garde ici est d'abord ce qui ne doit PAS arriver: aucun build qui
existait avant ce jour-la ne devient visible, aucun build fait sans compte
non plus, et un build rendu prive le reste a travers tous les calculs
suivants. Un defaut qui publie est irreversible du point de vue du lecteur:
ce qui a ete vu a ete vu.
"""

import io
import os
import pickle

from django.conf import settings
from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase

from chardata.models import Char
from chardata.solution import set_minimal_solution, wears_something


class _Solution(object):
    """Ce que le solveur range dans `minimal_solution`, reduit a ce que la
    publication regarde: la galerie dessine un build depuis `item_per_slot`,
    donc c'est ce champ qui dit si le personnage porte quelque chose."""

    def __init__(self, item_per_slot=None):
        self.item_per_slot = item_per_slot or {}


class OnlyADressedNewBuildIsPublishedTests(TestCase):

    def _char(self, **champs):
        defauts = {'name': 'Essai', 'char_name': 'Essai', 'char_class': 'Iop',
                   'char_build': '', 'level': 200, 'link_shared': False,
                   'minimum_stats': pickle.dumps({}),
                   'minimum_crits': pickle.dumps({}),
                   'stats_weight': pickle.dumps({}),
                   'options': pickle.dumps({}),
                   'inclusions': pickle.dumps({}),
                   'exclusions': pickle.dumps({}),
                   'game_version': 'dofus3'}
        defauts.update(champs)
        return Char.objects.create(**defauts)

    def test_a_new_build_goes_public_the_first_time_it_is_dressed(self):
        char = self._char(auto_publish=True)
        set_minimal_solution(char, _Solution({'Hat': 14063}))
        self.assertTrue(Char.objects.get(pk=char.pk).link_shared)

    def test_an_empty_solution_publishes_nothing(self):
        """La galerie n'est pas une liste de brouillons vides. Un build dont
        le solveur n'a rien tire, ou qu'on vient d'ouvrir, ne doit pas y
        entrer: il s'y afficherait comme un cadre vide."""
        char = self._char(auto_publish=True)
        set_minimal_solution(char, _Solution({}))
        self.assertFalse(Char.objects.get(pk=char.pk).link_shared)
        set_minimal_solution(char, _Solution({'Hat': None, 'Cloak': None}))
        self.assertFalse(Char.objects.get(pk=char.pk).link_shared)
        self.assertFalse(wears_something(_Solution({'Hat': None})))
        self.assertTrue(wears_something(_Solution({'Hat': 1})))

    def test_a_build_that_existed_before_is_never_published(self):
        """La garde qui compte. Toutes les lignes ecrites avant le 11
        septembre 2026 portent `auto_publish` a False par la migration, donc
        un simple recalcul ne peut pas rendre public un build que son auteur
        avait garde pour lui il y a des annees."""
        char = self._char(auto_publish=False)
        for _ in range(3):
            set_minimal_solution(char, _Solution({'Hat': 14063}))
        self.assertFalse(Char.objects.get(pk=char.pk).link_shared)

    def test_a_build_made_private_stays_private_through_every_solve(self):
        """Le choix de l'auteur gagne sur le defaut, pour toujours: c'est
        `hide_sharing_link` qui eteint `auto_publish`, pas seulement
        `link_shared`."""
        proprietaire = User.objects.create_user('auteur', password='x')
        char = self._char(auto_publish=True, owner=proprietaire)
        self.client.force_login(proprietaire)
        self.client.get('/hidesharinglink/%d/' % char.pk)
        char.refresh_from_db()
        self.assertFalse(char.auto_publish)
        set_minimal_solution(char, _Solution({'Hat': 14063}))
        self.assertFalse(Char.objects.get(pk=char.pk).link_shared)

    def test_sharing_by_hand_also_settles_the_question(self):
        proprietaire = User.objects.create_user('auteur2', password='x')
        char = self._char(auto_publish=True, owner=proprietaire)
        self.client.force_login(proprietaire)
        self.client.get('/getsharinglink/%d/' % char.pk)
        char.refresh_from_db()
        self.assertTrue(char.link_shared)
        self.assertFalse(char.auto_publish)

    def test_a_build_already_public_is_not_touched_again(self):
        char = self._char(auto_publish=True, link_shared=True)
        set_minimal_solution(char, _Solution({'Hat': 14063}))
        apres = Char.objects.get(pk=char.pk)
        self.assertTrue(apres.link_shared)
        self.assertTrue(apres.auto_publish)


class TheChoiceIsMadeWhenTheBuildIsCreatedTests(TestCase):

    def _cree(self, **extra):
        donnees = {'project': 'Mon build', 'charname': 'Moi', 'level': '200',
                   'class': 'Iop', 'byhand': 'x'}
        donnees.update(extra)
        self.client.post('/createproject/', donnees)
        return Char.objects.order_by('-id').first()

    def test_a_logged_in_author_gets_the_default(self):
        self.client.force_login(User.objects.create_user('a', password='x'))
        char = self._cree()
        self.assertTrue(char.auto_publish)
        # Rien n'est publie a la creation: le build ne porte encore rien.
        self.assertFalse(char.link_shared)

    def test_unticking_the_box_turns_it_off(self):
        """Une case decochee n'envoie RIEN, donc le formulaire est poste ici
        comme un navigateur le poste: le champ cache seul. Lire la case avec
        un defaut a <<coche>> rendait le fait de decocher sans effet, ce qui
        est la facon la plus silencieuse de publier quelqu'un contre son
        gre."""
        self.client.force_login(User.objects.create_user('b', password='x'))
        self.assertFalse(self._cree(publish_choice='1').auto_publish)

    def test_leaving_the_box_ticked_posts_it_the_way_a_browser_does(self):
        self.client.force_login(User.objects.create_user('b2', password='x'))
        self.assertTrue(self._cree(publish_choice='1',
                                   publish='on').auto_publish)

    def test_a_guest_build_is_never_published_on_its_own(self):
        """Un visiteur sans compte n'a pas de page ou retrouver son build ni
        de compte pour le rendre prive ensuite: publier par defaut lui
        prendrait quelque chose qu'il ne peut pas reprendre."""
        char = self._cree()
        self.assertIsNone(char.owner)
        self.assertFalse(char.auto_publish)

    def test_the_quick_start_path_follows_the_same_rule(self):
        """La creation rapide et l'import d'un build passent par
        `coaching_view.create_build`, qui n'a pas de formulaire a lui."""
        from chardata.coaching_view import create_build

        class _Requete(object):
            def __init__(self, user):
                self.user = user
                self.POST = {}
                self.session = {}
                self.game_version = 'dofus3'

        invite = _Requete(User.objects.create_user('c', password='x'))
        char = create_build(invite, 'Iop', 200, set(), 'dofus3')
        self.assertTrue(Char.objects.get(pk=char.pk).auto_publish)


class TheOrdinaryJourneyEndsPublicTests(TestCase):
    """Le trajet que fait vraiment un lecteur: il cree un build, il ouvre sa
    page, le solveur l'habille. Les tests plus haut prennent le point de
    publication par le col; celui-ci prend la porte d'entree, et c'est lui
    qui a fait tomber deux gardes de securite le jour ou le defaut a change,
    parce que leur build de test devenait public sous leurs pieds."""

    def _cree(self, **extra):
        donnees = {'project': 'Mon build', 'charname': 'Moi', 'level': '150',
                   'class': 'Iop', 'where_to_go': 'wizard'}
        donnees.update(extra)
        self.client.post('/createproject/', donnees)
        return Char.objects.order_by('-id').first()

    def test_creating_then_opening_the_build_publishes_it(self):
        self.client.force_login(User.objects.create_user('f', password='x'))
        char = self._cree()
        self.assertFalse(char.link_shared)
        self.client.get('/solution/%d/' % char.pk, follow=True)
        char.refresh_from_db()
        self.assertTrue(char.link_shared, 'the ordinary journey stayed private')
        self.assertTrue(char.minimal_solution)

    def test_the_same_journey_with_the_box_unticked_stays_private(self):
        """Poste comme un navigateur poste une case decochee."""
        self.client.force_login(User.objects.create_user('g', password='x'))
        char = self._cree(publish_choice='1')
        self.client.get('/solution/%d/' % char.pk, follow=True)
        char.refresh_from_db()
        self.assertFalse(char.link_shared)
        self.assertTrue(char.minimal_solution, 'the build was never solved')


class ThePagesSayWhatIsPublishedTests(TestCase):
    """Un defaut qui publie doit s'annoncer avant, pas se decouvrir apres."""

    def test_the_creation_page_shows_the_switch_to_an_author(self):
        self.client.force_login(User.objects.create_user('d', password='x'))
        page = self.client.get('/setup/', HTTP_ACCEPT_LANGUAGE='en'
                               ).content.decode('utf-8')
        self.assertIn('publish-cb', page)
        self.assertIn('Show this build in the gallery', page)
        # Le minifieur trie les attributs, donc on ne compte pas sur l'ordre.
        self.assertRegex(page, r'<input[^>]*checked[^>]*name="?publish"?[^>]*>'
                               r'|<input[^>]*name="?publish"?[^>]*checked[^>]*>')

    def test_a_guest_is_not_shown_a_switch_that_does_nothing(self):
        page = self.client.get('/setup/', HTTP_ACCEPT_LANGUAGE='en'
                               ).content.decode('utf-8')
        self.assertNotIn('publish-cb', page)

    def test_the_creation_page_says_it_in_french_too(self):
        self.client.force_login(User.objects.create_user('e', password='x'))
        page = self.client.get('/setup/', HTTP_ACCEPT_LANGUAGE='fr'
                               ).content.decode('utf-8')
        self.assertIn('dans la galerie', page)


class ThePrivacyPolicySaysWhatIsPublishedTests(SimpleTestCase):
    """Publier des builds d'utilisateurs par defaut est exactement ce qu'une
    politique de confidentialite doit nommer, et dans les cinq langues."""

    PARAGRAPHE = (
        'A build you create while logged in is published the first time it '
        'has gear: it then appears in the build gallery, on the pages of the '
        'items it wears, and under your display name on your profile, and '
        'anyone holding its link can open it. You can turn that off for a '
        'build at any time from the build page, and you can untick the box on '
        'the creation page before you start. Builds made without an account '
        'are never published on their own, and builds created before 11 '
        'September 2026 keep the visibility they already had.')

    def test_the_paragraph_is_in_the_policy(self):
        chemin = os.path.join(settings.BASE_DIR, 'chardata', 'templates',
                              'chardata', 'privacy.html')
        texte = io.open(chemin, encoding='utf-8').read()
        self.assertIn('Builds you publish', texte)
        self.assertIn(self.PARAGRAPHE[:60], texte)

    def test_it_is_translated_everywhere(self):
        from django.utils.translation import gettext, override
        muettes = []
        for langue in ('fr', 'es', 'pt', 'de'):
            with override(langue):
                for chaine in (self.PARAGRAPHE, 'Builds you publish',
                               'Private: only you can open this build.',
                               'Visible to everyone: this build is in the '
                               'gallery and anyone with the link can open it.',
                               'Show this build in the gallery once it has gear',
                               'You can change this at any time from the '
                               'build page.'):
                    if gettext(chaine) == chaine:
                        muettes.append((langue, chaine[:40]))
        self.assertEqual([], muettes)
