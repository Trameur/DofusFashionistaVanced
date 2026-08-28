# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""L'adresse d'un build partage porte le prefixe de SA version de jeu.

Un build vit dans une seule version, et sa page n'existe que sous le prefixe de
cette version. La forme sans prefixe etait ecrite en dur a quatre endroits :
`encyclopedia_view` (le bloc « builds qui utilisent cet objet », public),
`api_view` (le champ `url` des trois points d'entree), `admin_stats` et
`admin_tools_view`.

Mesure en production le 28 aout 2026, sur quatre fiches d'objets Touch : les
**huit** liens de builds affiches rendaient 404, et les huit memes adresses
prefixees rendaient 200. Cote API, les 20 builds partages hors Dofus 3 -- 11
Touch, 4 Retro, 3 Beta, 2 Dofus 2 -- auraient recu un `url` mort des le
deploiement du champ.

Pourquoi pas `version_reverse` : elle prefixe avec la version de la REQUETE.
Une page Dofus 3, ou une reponse d'API, doit pouvoir designer un build Touch.
C'est la version du BUILD qui commande, pas celle du lecteur.

Ce module enumere les versions plutot que de tester celle a laquelle je pense :
le defaut ne se voyait pas parce que Dofus 3 represente 99 % des builds, et
c'est la seule version pour laquelle la forme sans prefixe est juste.
"""
import pickle

from django.contrib.auth.models import User
from django.test import TestCase

from chardata.models import Char
from chardata.util import shared_build_path

#: Les versions que le site sert. Lue depuis la configuration plutot
#: qu'ecrite en dur : une version ajoutee doit entrer dans ce test toute seule.
#: La liste est faite de paires (slug, libelle) -- `admin_stats.py:20` la
#: deballe de la meme facon. Ma premiere version supposait des dictionnaires
#: et fabriquait des cles qui n'etaient pas des chaines.
from chardata.context_processors import ACTIVE_GAME_VERSIONS

VERSIONS = tuple(slug for slug, _libelle in ACTIVE_GAME_VERSIONS)


class ASharedBuildPathCarriesItsVersionTests(TestCase):

    @staticmethod
    def _entree_de_base():
        return {'options': {'ap_exo': False, 'mp_exo': False},
                'origin': 'generated', 'char_level': 200,
                'base_stats_by_attr': {'Vitality': 0, 'Wisdom': 0,
                                       'Strength': 0, 'Intelligence': 0,
                                       'Chance': 0, 'Agility': 0},
                'locked_equips': {}}

    def _solution_pour(self, version):
        """Une solution enregistree, prise dans le catalogue de CETTE version.

        `solution_linked` leve 404 sur deux motifs distincts : la version qui
        ne correspond pas, et la solution absente. Sans cette graine, les cinq
        chemins rendaient 404 pour le SECOND motif -- y compris celui de
        Dofus 3, dont la forme est pourtant juste -- et le test aurait accuse
        le prefixe a la place de sa propre mise en scene.
        """
        from fashionistapulp.modelresult import ModelResultMinimal
        from fashionistapulp.structure import get_structure
        s = get_structure(version)
        chapeaux = [i for i in s.get_items_list()
                    if s.get_type_name_by_id(i.type) == 'Hat'
                    and not getattr(i, 'removed', False)]
        if not chapeaux:
            return None
        return pickle.dumps(ModelResultMinimal({'hat': chapeaux[0].id},
                                               self._entree_de_base(), {}))

    def setUp(self):
        self.proprio = User.objects.create_user(
            username='proprio', email='p@test.local', password='pw-42-solid')
        self.builds = {}
        for version in VERSIONS:
            solution = self._solution_pour(version)
            if solution is None:
                continue
            self.builds[version] = Char.objects.create(
                name='projet %s' % version, char_name='perso%s' % version,
                char_class='Iop', char_build='build', level=200,
                minimum_stats=b'', minimum_crits=b'',
                stats_weight=pickle.dumps({'vit': 1}), options=b'',
                inclusions=b'', exclusions=b'',
                owner=self.proprio, game_version=version,
                link_shared=True, deleted=False, minimal_solution=solution)

    def test_the_version_list_is_not_a_single_entry(self):
        """Le plancher du temoin.

        Avec une seule version, tout ce module devient vrai par construction :
        la forme sans prefixe est correcte pour Dofus 3, et le defaut ne se
        voyait justement que sur les autres.
        """
        self.assertGreaterEqual(
            len(VERSIONS), 3,
            'only %d game version(s) to walk (%s); the bug this module guards '
            'exists only on the versions that are not dofus3'
            % (len(VERSIONS), list(VERSIONS)))
        # Et surtout : combien ont vraiment recu un build. Une version sautee
        # faute de chapeau ne serait gardee par rien, en silence.
        self.assertEqual(
            set(VERSIONS), set(self.builds),
            'no shared build could be seeded for %s, so those versions are '
            'walked by nothing' % sorted(set(VERSIONS) - set(self.builds)))

    def test_a_dofus3_build_keeps_the_bare_path(self):
        """Le controle positif de la paire.

        Sans lui, un helper qui prefixerait TOUT -- y compris Dofus 3 --
        passerait le test suivant, et casserait 99 % des liens du site.
        """
        chemin = shared_build_path(self.builds['dofus3'])
        self.assertTrue(chemin.startswith('/s/'),
                        'a dofus3 build must keep the bare path, got %s'
                        % chemin)

    def test_every_other_version_is_prefixed(self):
        manquants = []
        for version, build in self.builds.items():
            if version == 'dofus3':
                continue
            chemin = shared_build_path(build)
            if not chemin.startswith('/%s/s/' % version):
                manquants.append((version, chemin))
        self.assertFalse(
            manquants,
            'these paths do not carry their own game version, so they answer '
            '404: %s' % manquants)

    def test_every_path_actually_resolves(self):
        """La mesure qui compte : l'adresse repond-elle.

        Un prefixe bien forme mais route nulle part serait exactement aussi
        casse que pas de prefixe du tout.
        """
        morts = []
        for version, build in self.builds.items():
            chemin = shared_build_path(build)
            code = self.client.get(chemin).status_code
            if code >= 400:
                morts.append((version, chemin, code))
        self.assertFalse(morts, 'these shared build paths do not open: %s'
                         % morts)

    def test_the_paths_are_not_all_the_same(self):
        """Un helper qui rendrait une constante passerait tout ce qui precede
        sauf ceci."""
        chemins = {shared_build_path(b) for b in self.builds.values()}
        self.assertEqual(
            len(chemins), len(self.builds),
            'the helper returns %d distinct paths for %d builds'
            % (len(chemins), len(self.builds)))

    def test_the_api_url_carries_the_version_too(self):
        """Le champ `url` de l'API est construit par le meme chemin.

        Il n'existait pas en production au moment ou ce test a ete ecrit : le
        commit qui l'ajoute attendait le deploiement. Le corriger avant qu'il
        parte coutait une ligne ; apres, il aurait fallu le reprendre chez les
        consommateurs qui l'auraient deja lu.
        """
        from chardata.api_view import _build_payload
        for version, build in self.builds.items():
            charge = _build_payload(build, {}, tags_by_char={},
                                    include_tags=False)
            url = charge.get('url') or ''
            attendu = shared_build_path(build)
            self.assertTrue(
                url.endswith(attendu),
                'the api url for a %s build is %r, which does not end with '
                'its own path %r' % (version, url, attendu))
