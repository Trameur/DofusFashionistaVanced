# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.

"""The Wakfu legacy list in lock_forbid is the legacy tier of the Wakfu data."""
import os

from django.test import SimpleTestCase

from chardata.lock_forbid import DEFAULT_EXCLUSION_ANKAMA_IDS_BY_VERSION


class TheWakfuLegacyListMatchesTheDataTests(SimpleTestCase):
    def setUp(self):
        from fashionistapulp.fashionista_config import get_items_db_path
        from fashionistapulp.structure import get_structure
        if not os.path.exists(get_items_db_path('wakfu')):
            self.skipTest('no Wakfu database built; run update_data_wakfu.py')
        self.structure = get_structure('wakfu')
        self.listed = DEFAULT_EXCLUSION_ANKAMA_IDS_BY_VERSION.get('wakfu', [])

    def test_the_list_is_not_empty_and_has_no_duplicate(self):
        print('legacy ids listed:', len(self.listed))
        self.assertGreater(len(self.listed), 0)
        self.assertEqual(len(self.listed), len(set(self.listed)))

    def test_every_listed_id_is_an_item_of_the_data(self):
        missing = [i for i in self.listed if self.structure.get_item_by_ankama_id(i) is None]
        self.assertEqual([], missing)

    def test_the_listed_items_are_the_legacy_tier(self):
        from fashionistapulp.wakfu_exclusions import default_exclusions
        resolved = [self.structure.get_item_by_ankama_id(i) for i in self.listed]
        self.assertEqual(sorted(item.id for item in resolved if item is not None),
                         default_exclusions(self.structure))
