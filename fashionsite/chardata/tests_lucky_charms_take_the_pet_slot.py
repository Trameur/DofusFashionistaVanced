import os

from django.test import SimpleTestCase

CHARM_TYPE = 849
PET_TYPE = 582
LEVEL = 125


class LuckyCharmsTakeThePetSlotTests(SimpleTestCase):
    """The shipped Wakfu database; skipped when it is absent."""

    def setUp(self):
        from fashionistapulp.fashionista_config import get_items_db_path
        from fashionistapulp.structure import get_structure
        if not os.path.exists(get_items_db_path('wakfu')):
            self.skipTest('no Wakfu database built; run update_data_wakfu.py')
        self.structure = get_structure('wakfu')
        if not any(type_id == CHARM_TYPE for type_id, _p in self.structure.get_type_positions()):
            self.skipTest('the Wakfu database has no lucky charms')

    def of_type(self, type_id):
        return [item for item in self.structure.get_items_list() if item.type == type_id]

    def a_charm_and_a_pet(self):
        charm = min((item for item in self.of_type(CHARM_TYPE) if item.level <= LEVEL),
                    key=lambda item: item.id)
        pet = min((item for item in self.of_type(PET_TYPE) if item.level <= LEVEL),
                  key=lambda item: item.id)
        return charm, pet

    def test_the_42_lucky_charms_are_worn_in_pet(self):
        self.assertEqual(['PET'], sorted(position for type_id, position
                                         in self.structure.get_type_positions()
                                         if type_id == CHARM_TYPE))
        self.assertEqual(42, len(self.of_type(CHARM_TYPE)))

    def test_a_charm_fills_pet_when_every_pet_is_forbidden(self):
        from fashionistapulp.wakfu_model import WakfuBuild
        forbidden = {item.id for item in self.of_type(PET_TYPE)}
        build = WakfuBuild(self.structure, LEVEL, {'hp': 1}, forbidden)
        worn = build.build().solve()
        self.assertIsNotNone(worn)
        self.assertEqual(CHARM_TYPE, worn['PET'].type)

    def test_a_lock_on_a_charm_and_a_pet_is_refused(self):
        from fashionistapulp.wakfu_model import WakfuBuild
        charm, pet = self.a_charm_and_a_pet()
        with self.assertRaisesRegex(ValueError, 'need the same slot'):
            WakfuBuild(self.structure, LEVEL, {'hp': 1}, locked=[(charm.id, None),
                                                                 (pet.id, None)])

    def test_a_charm_and_a_pet_worn_together_break_the_slot_count(self):
        from fashionistapulp import wakfu_legality
        charm, pet = self.a_charm_and_a_pet()
        found = wakfu_legality.violations(self.structure, LEVEL, {'PET': [charm, pet]})
        self.assertIn(wakfu_legality.SLOT_COUNT, {rule for rule, _text in found})

    def test_a_level_given_for_a_charm_is_refused(self):
        from fashionistapulp import wakfu_companions, wakfu_legality
        charm, _pet = self.a_charm_and_a_pet()
        with self.assertRaises(ValueError) as caught:
            wakfu_companions.read_levels(self.structure, items={charm.id: 5})
        self.assertIn(charm.name, str(caught.exception))
        found = wakfu_legality.violations(self.structure, LEVEL, {'PET': charm},
                                          levels={charm.id: 5})
        self.assertEqual([wakfu_legality.COMPANION_LEVEL],
                         [rule for rule, _text in found])
