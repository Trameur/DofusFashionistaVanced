import math
import os

from django.test import SimpleTestCase

from chardata.tests_wakfu_solve_obeys_every_rule_on_invented_items import (
    ALPHA, AMULET, BOOTS, HELMET, LEVEL, InventedItemsCase, ids, item)
from fashionistapulp import wakfu_presets, wakfu_value

WISE_HELM, LUCKY_HELM, TOUGH_HELM, WISE_AMULET, TOUGH_AMULET, LUCKY_BOOTS = (
    2001, 2002, 2003, 2004, 2005, 2006)


class TheMuleAsksNoElementTests(SimpleTestCase):
    def test_a_role_with_a_damage_share_raises_without_an_element(self):
        for shares in ({'damage': 1}, {'damage': 1, 'life': 0.4},
                       {'damage': 0.5, 'heal': 0.5, 'lock': 0.1}):
            with self.subTest(shares=shares):
                with self.assertRaisesMessage(ValueError, 'elements are'):
                    wakfu_value.Role((), 'distance', shares=shares)
                self.assertTrue(wakfu_value.Role(('fire',), 'distance', shares=shares))

    def test_a_mule_takes_no_element_and_has_no_damage_share(self):
        mule = wakfu_value.Role((), 'distance', shares={'mule': 1})
        self.assertEqual((), mule.elements)
        self.assertNotIn('damage', mule.shares)


class AMuleSolveOnInventedItemsTests(InventedItemsCase):
    @classmethod
    def catalogue(cls):
        return [
            item(WISE_HELM, HELMET, 'Wise Helm', wisdom=3),
            item(LUCKY_HELM, HELMET, 'Lucky Helm', prospection=10),
            item(TOUGH_HELM, HELMET, 'Tough Helm', hp=500),
            item(WISE_AMULET, AMULET, 'Wise Amulet', wisdom=5),
            item(TOUGH_AMULET, AMULET, 'Tough Amulet', hp=400),
            item(LUCKY_BOOTS, BOOTS, 'Lucky Boots', prospection=2, hp=10),
        ]

    def test_the_mule_keeps_the_most_wisdom_and_prospection_without_an_element(self):
        mule = wakfu_value.Role((), 'distance', shares={'mule': 1})
        found = wakfu_value.solve(self.structure, LEVEL, mule, class_id=ALPHA, rounds=3)
        self.assertIsNotNone(found.best)
        self.assertEqual({LUCKY_HELM, WISE_AMULET, LUCKY_BOOTS}, ids(found.best.worn))
        self.assertEqual(5, found.best.totals['wisdom'])
        self.assertEqual(12, found.best.totals['prospection'])
        self.assertAlmostEqual(math.log(1 + 5 + 12),
                               wakfu_value.value(mule, LEVEL, found.best.totals), 12)


class TheRegistryMuleAsksNoElementTests(SimpleTestCase):
    ENUTROF, LEVEL = 3, 245

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from fashionistapulp.fashionista_config import get_items_db_path
        cls.path = get_items_db_path('wakfu')

    def setUp(self):
        if not os.path.exists(self.path):
            self.skipTest('no Wakfu database built; run update_data_wakfu.py')

    def test_the_registry_gives_the_mule_a_role_without_an_element(self):
        built = wakfu_presets.role(self.ENUTROF, 'mule', (), self.LEVEL, path=self.path)
        self.assertEqual((), built.elements)
        self.assertEqual({'mule': 1.0, 'life': 0.5}, built.shares)
        self.assertEqual({'mule': 1.0, 'life': 0.5}, wakfu_presets.shares(
            self.ENUTROF, 'mule', (), 'pvm', self.LEVEL, self.path))

    def test_the_standard_weights_of_the_mule_are_wisdom_prospection_and_life(self):
        found = wakfu_presets.standard_weights(self.ENUTROF, self.LEVEL, 'mule', (),
                                               path=self.path)
        self.assertGreater(found['wisdom'], 0)
        self.assertEqual(found['wisdom'], found['prospection'])
        self.assertGreater(found['hp'], 0)
        self.assertNotIn('dmg_fire_percent', found)

    def test_any_other_preset_still_asks_for_an_element(self):
        for preset in ('tank', 'damage_melee_single', 'support'):
            with self.subTest(preset=preset):
                with self.assertRaisesMessage(ValueError, 'elements are required'):
                    wakfu_presets.role(self.ENUTROF, preset, (), self.LEVEL, path=self.path)
