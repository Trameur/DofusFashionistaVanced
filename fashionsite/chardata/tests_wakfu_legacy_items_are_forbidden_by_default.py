import os

from django.test import SimpleTestCase


class WakfuLegacyItemsAreForbiddenByDefaultTests(SimpleTestCase):
    def setUp(self):
        from fashionistapulp.fashionista_config import get_items_db_path
        from fashionistapulp.structure import get_structure
        if not os.path.exists(get_items_db_path('wakfu')):
            self.skipTest('no Wakfu database built; run update_data_wakfu.py')
        self.structure = get_structure('wakfu')

    def ids(self, worn):
        return {item.id for item in worn.values()}

    def test_the_default_exclusions_are_the_legacy_tier(self):
        from fashionistapulp.wakfu_exclusions import default_exclusions
        legacy = sorted(item.id for item in self.structure.get_items_list() if item.rarity == 0)
        self.assertGreater(len(legacy), 100)
        self.assertEqual(legacy, default_exclusions(self.structure))

    def test_a_legacy_item_stays_in_the_catalogue_and_the_solver_pool(self):
        from fashionistapulp.wakfu_exclusions import default_exclusions
        from fashionistapulp.wakfu_model import WakfuBuild
        shipped = {item.id for item in self.structure.get_items_list() if not item.removed}
        legacy = set(default_exclusions(self.structure)) & shipped
        self.assertGreater(len(legacy), 100)
        candidates = {item.id for item, _position in WakfuBuild(self.structure, 245, {'hp': 1})._candidates()}
        self.assertEqual(set(), legacy - candidates)

    def test_a_low_level_set_wears_legacy_items_only_when_they_are_allowed(self):
        from fashionistapulp.wakfu_exclusions import default_exclusions
        from fashionistapulp.wakfu_model import WakfuBuild
        legacy = set(default_exclusions(self.structure))
        allowed = WakfuBuild(self.structure, 5, {'hp': 1}).build().solve()
        self.assertTrue(legacy & self.ids(allowed), 'no legacy item was worth wearing, so nothing was checked')
        default = WakfuBuild(self.structure, 5, {'hp': 1}, legacy).build().solve()
        self.assertIsNotNone(default)
        self.assertEqual(set(), legacy & self.ids(default))
