# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The option "Remove only trophies that limit sets" removes those trophies and nothing else."""

from django.test import SimpleTestCase

from fashionistapulp.dofus_constants import STATS_NAMES
from fashionistapulp.model import Model, ModelInput
from fashionistapulp.structure import get_structure, set_current_game_version

from chardata.options import get_available_options

OPTIONS = {'ap_exo': False, 'mp_exo': False, 'range_exo': False,
           'dofus': True, 'trophies': True, 'dragoturkey': True,
           'seemyool': True, 'rhineetle': True, 'prysmaradite': False,
           'shields': True}


def _limits_sets(item):
    return bool(item.weird_conditions.get('light_set')
                or item.weird_conditions.get('sets_equipped'))


class TheOptionRemovesOnlyTheTrophiesThatLimitSetsTests(SimpleTestCase):

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')

    def _removed(self, version):
        set_current_game_version(version)
        base = {name: 0 for name, _key in STATS_NAMES}
        base.update({'AP': 7, 'MP': 3, 'Summon': 1, 'Prospecting': 100,
                     'Pods': 1000})
        model = Model()
        model.setup(ModelInput(200, base, {}, {}, [], {'vit': 1, 'str': 3},
                               dict(OPTIONS), 'Iop', 995))
        dofus_type = model.structure.get_type_id_by_name('Dofus')
        pieces = [item for item in model.items_list if item.type == dofus_type]
        removed = []
        for choice in (True, 'lightset'):
            model.modify_forbidden_items_constraints(
                [], dict(OPTIONS, dofus=choice), 'Iop')
            constraints = model.restrictions.forbidden_items_constraints
            removed.append({item.id for item in pieces
                            if -constraints[item.id].constant <= 0})
        return pieces, removed[0], removed[1]

    def test_the_versions_with_such_trophies_lose_exactly_them(self):
        for version in ('dofus3', 'beta', 'dofus2', 'touch'):
            with self.subTest(version=version):
                pieces, with_yes, with_option = self._removed(version)
                added = with_option - with_yes
                self.assertTrue(added)
                self.assertTrue(with_yes <= with_option)
                self.assertEqual(
                    {item.id for item in pieces
                     if _limits_sets(item) and item.id not in with_yes},
                    added)
                self.assertEqual([], [item.id for item in pieces
                                      if item.id in added
                                      and 'Trophy' not in item.flags])

    def test_retro_has_none_and_loses_nothing(self):
        pieces, with_yes, with_option = self._removed('retro')
        self.assertEqual([], [item.id for item in pieces if _limits_sets(item)])
        self.assertEqual(with_yes, with_option)


class TheOptionsPageOffersItOnlyWhereItRemovesSomethingTests(SimpleTestCase):

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')

    def test_each_version_offers_it_when_it_has_such_a_trophy(self):
        for version in ('dofus3', 'beta', 'dofus2', 'touch', 'retro'):
            with self.subTest(version=version):
                set_current_game_version(version)
                structure = get_structure()
                has_one = any(_limits_sets(item)
                              for item in structure.get_items_list())
                self.assertEqual(
                    has_one,
                    get_available_options(structure)['set_limit_trophies'])
                self.assertEqual(version != 'retro', has_one)
