# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Aucune route liee a un build ne repond a quelqu'un qui n'en est pas le
proprietaire.

`/setup/7/` repondait 403 a un inconnu et `/infeasible/7/` repondait 200 : la
meme donnee, deux reponses. La deuxieme appelait `get_object_or_404` au lieu de
`get_char_or_raise`, donc elle ne posait jamais la question de la propriete. Le
gabarit de la page ne montre pas grand-chose, mais l'en-tete commun de
`base.html` affiche `{{ char.name }}`, et `over_cap` nomme les minimums du
personnage. Verifie en production le 28 aout 2026 : cinq identifiants tires au
hasard, cinq fois 403 sur /setup/ et cinq fois 200 sur /infeasible/.

**Ce module enumere au lieu de choisir.** Un test ecrit a la main garde le trou
que je viens de voir ; il ne garde pas le prochain. La liste des routes vient
donc de `check_pages.BUILD_PATHS`, que le projet tient deja a jour pour son
parcours de diagnostic : une route ajoutee la se retrouve gardee ici sans que
personne y pense.

Deux exceptions nommees, et leur raison :
  * `/solution/<id>/` et `/spells/<id>/` servent volontairement un build
    PARTAGE a un inconnu -- c'est la fonction meme du partage. Le test ne les
    regarde donc que sur un personnage NON partage.
"""
from django.contrib.auth.models import User
from django.test import TestCase

from chardata.management.commands.check_pages import BUILD_PATHS
from chardata.models import Char

#: Ce que le site sert legitimement a un inconnu quand le build est partage.
#: On teste sur un build non partage, donc meme celles-ci doivent refuser.
_PARTAGEABLES = ('/solution/%s/', '/spells/%s/')


class NoBuildRouteAnswersAStrangerTests(TestCase):

    def setUp(self):
        self.proprio = User.objects.create_user(
            username='proprio', email='p@test.local', password='pw-42-solid')
        self.inconnu = User.objects.create_user(
            username='inconnu', email='i@test.local', password='pw-42-solid')
        self.char = Char.objects.create(
            name='projet prive', char_name='perso', char_class='Iop',
            char_build='build', level=200, minimum_stats=b'',
            minimum_crits=b'', stats_weight=b'', options=b'', inclusions=b'',
            exclusions=b'', owner=self.proprio, game_version='dofus3',
            link_shared=False, deleted=False, minimal_solution=b'')

    def _codes_pour(self, client):
        """(route, code) pour chaque route de build, avec ce client."""
        out = []
        for route in BUILD_PATHS:
            chemin = route % self.char.id
            try:
                code = client.get(chemin).status_code
            except Exception as erreur:            # noqa: BLE001
                # Une exception non geree est pire qu'un 200 : elle dit que la
                # route n'a jamais envisage ce cas du tout.
                code = '%s: %s' % (type(erreur).__name__, str(erreur)[:60])
            out.append((chemin, code))
        return out

    def test_the_route_list_is_not_empty(self):
        """Le plancher du temoin.

        Si `BUILD_PATHS` est renomme ou vide, tous les tests de ce module
        deviennent verts en n'examinant rien. C'est arrive assez souvent sur ce
        projet pour meriter sa propre assertion.
        """
        self.assertGreaterEqual(
            len(BUILD_PATHS), 20,
            'only %d build routes to walk; this module would be guarding '
            'almost nothing' % len(BUILD_PATHS))

    def test_an_anonymous_stranger_gets_no_page(self):
        codes = self._codes_pour(self.client)
        servies = [(c, k) for c, k in codes if k == 200]
        self.assertFalse(
            servies,
            'these serve an unowned build to an anonymous visitor: %s'
            % servies[:6])

    def test_a_logged_in_stranger_gets_no_page(self):
        """Le cas que l'anonyme ne couvre pas.

        Une vue peut refuser l'anonyme par `login_required` et servir ensuite
        n'importe quel compte connecte -- c'est l'erreur classique, et elle
        passe le test precedent sans broncher.
        """
        self.client.force_login(self.inconnu)
        codes = self._codes_pour(self.client)
        servies = [(c, k) for c, k in codes if k == 200]
        self.assertFalse(
            servies,
            'these serve an unowned build to any logged-in account: %s'
            % servies[:6])

    def test_the_owner_is_not_locked_out(self):
        """Le controle positif.

        Sans lui, une vue qui repondrait 500 a tout le monde passerait les deux
        tests precedents : plus personne n'aurait de 200, et le garde
        applaudirait une panne totale.
        """
        self.client.force_login(self.proprio)
        codes = self._codes_pour(self.client)
        ouvertes = [c for c, k in codes if k == 200]
        self.assertGreaterEqual(
            len(ouvertes), 3,
            'the owner gets 200 on only %d of the %d build routes, so the two '
            'tests above may be passing on a site that is simply broken: %s'
            % (len(ouvertes), len(BUILD_PATHS), codes[:8]))

    def test_no_build_route_raises_on_a_stranger(self):
        """Une exception n'est pas un refus.

        Une vue qui explose sur un visiteur non proprietaire rend une 500, ce
        qui n'est ni un refus propre ni une trace exploitable ; et `handler500`
        peut fuir plus que la page elle-meme.
        """
        codes = self._codes_pour(self.client)
        casses = [(c, k) for c, k in codes if not isinstance(k, int)]
        self.assertFalse(casses, 'these raise for a stranger: %s' % casses[:4])
