# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A shared build's path carries the build's own game version prefix."""
import pickle

from django.contrib.auth.models import User
from django.test import TestCase

from chardata.models import Char
from chardata.util import shared_build_path

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
        """Saved solution from this version's items; without one /s/ answers 404."""
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
        self.assertGreaterEqual(
            len(VERSIONS), 3,
            'only %d game version(s) to walk (%s); the bug this module guards '
            'exists only on the versions that are not dofus3'
            % (len(VERSIONS), list(VERSIONS)))
        self.assertEqual(
            set(VERSIONS), set(self.builds),
            'no shared build could be seeded for %s, so those versions are '
            'walked by nothing' % sorted(set(VERSIONS) - set(self.builds)))

    def test_a_dofus3_build_keeps_the_bare_path(self):
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
        morts = []
        for version, build in self.builds.items():
            chemin = shared_build_path(build)
            code = self.client.get(chemin).status_code
            if code >= 400:
                morts.append((version, chemin, code))
        self.assertFalse(morts, 'these shared build paths do not open: %s'
                         % morts)

    def test_the_paths_are_not_all_the_same(self):
        chemins = {shared_build_path(b) for b in self.builds.values()}
        self.assertEqual(
            len(chemins), len(self.builds),
            'the helper returns %d distinct paths for %d builds'
            % (len(chemins), len(self.builds)))

    def test_the_api_url_carries_the_version_too(self):
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
