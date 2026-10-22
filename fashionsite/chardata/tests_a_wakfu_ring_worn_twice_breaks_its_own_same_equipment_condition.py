from fashionistapulp import wakfu_legality
from chardata.tests_wakfu_solve_obeys_every_rule_on_invented_items import (
    CATALOGUE, LEVEL, RING, InventedItemsCase, item)

UNIQUE_RING, PLAIN_RING = 5001, 5002

UNIQUE_ITEMS = [
    item(UNIQUE_RING, RING, 'Unique Ring', criteria='not HasAnotherSameEquipment()', hp=10),
    item(PLAIN_RING, RING, 'Plain Ring', hp=10),
]


class AWakfuRingWornTwiceBreaksItsOwnSameEquipmentConditionTests(InventedItemsCase):
    @classmethod
    def catalogue(cls):
        return CATALOGUE + UNIQUE_ITEMS

    def conditions(self, left, right):
        worn = {'LEFT_HAND': self.by_id(left), 'RIGHT_HAND': self.by_id(right)}
        found = wakfu_legality.violations(self.structure, LEVEL, worn)
        return [text for rule, text in found if 'fails' in text and rule == wakfu_legality.SAME_ITEM]

    def test_the_same_ring_in_both_hands_fails_its_own_condition_text(self):
        found = self.conditions(UNIQUE_RING, UNIQUE_RING)
        self.assertEqual(2, len(found), found)
        self.assertTrue(all('not HasAnotherSameEquipment()' in text for text in found), found)

    def test_a_unique_ring_beside_another_ring_fails_nothing(self):
        self.assertEqual([], self.conditions(UNIQUE_RING, PLAIN_RING))
