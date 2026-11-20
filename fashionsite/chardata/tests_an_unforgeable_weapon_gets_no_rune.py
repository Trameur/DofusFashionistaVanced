# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A weapon outside the smithmagic weapon types or on the unforgeable list gets no rune variant."""

from fashionistapulp import dracorune_terms, weapon_forge
from fashionistapulp.exo_options import FORGEABLE_WEAPON_TYPES
from fashionistapulp.model import Model
from fashionistapulp.structure import set_current_game_version

from chardata.dracorune_fixtures import VERSION, BetaModelTestCase, runes


class AnUnforgeableWeaponGetsNoRuneTests(BetaModelTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        set_current_game_version(VERSION)
        try:
            cls.model = Model()
        finally:
            set_current_game_version('dofus3')
        found = cls.model.structure
        cls.weapons = [item for item in cls.model.items_list
                       if found.get_type_name_by_id(item.type) == 'Weapon']
        cls.would_draconize = {item.id for item in cls.weapons
                               if dracorune_terms.item_variants(item, runes(), found)}

    def group(self, rule):
        return [item for item in self.weapons if rule(item) and item.id in self.would_draconize]

    def test_a_weapon_type_smithmagic_never_reaches_has_no_variant(self):
        others = self.group(lambda item: item.weapon_key not in FORGEABLE_WEAPON_TYPES)
        self.assertTrue(others)
        self.assertEqual([], [item.id for item in others
                              if item.id in self.model.dracorune_candidates])

    def test_a_weapon_on_the_unforgeable_list_has_no_variant(self):
        listed = self.group(lambda item: item.weapon_key in FORGEABLE_WEAPON_TYPES
                            and not weapon_forge.can_forge(VERSION, item.ankama_id))
        self.assertTrue(listed)
        self.assertEqual([], [item.id for item in listed
                              if item.id in self.model.dracorune_candidates])

    def test_a_forgeable_weapon_with_lines_to_move_has_variants(self):
        forgeable = self.group(lambda item: item.weapon_key in FORGEABLE_WEAPON_TYPES
                               and weapon_forge.can_forge(VERSION, item.ankama_id))
        self.assertTrue(forgeable)
        self.assertEqual([], [item.id for item in forgeable
                              if item.id not in self.model.dracorune_candidates])
