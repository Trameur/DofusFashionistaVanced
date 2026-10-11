# -*- coding: utf-8 -*-
"""A build locked on a piece the data no longer holds still gets its result."""
from django.test import SimpleTestCase

from fashionistapulp.modelresult import ModelResultMinimal
from fashionistapulp.structure import get_structure


class ALockedPieceThatLeftTheGameDoesNotStopTheSolve(SimpleTestCase):

    def setUp(self):
        self.structure = get_structure()
        self.hat = next(item for item in self.structure.get_items_list()
                        if self.structure.get_type_name_by_id(item.type) == 'Hat')
        self.gone = max(self.structure.items_dict) + 1000
        self.assertIsNone(self.structure.get_item_by_id(self.gone))

    def test_the_result_keeps_the_pieces_the_solve_chose(self):
        result = ModelResultMinimal.from_item_id_list(
            [self.hat.id], {'locked_equips': {'hat': self.gone}}, {})

        self.assertEqual(result.item_per_slot.get('hat'), self.hat.id)
