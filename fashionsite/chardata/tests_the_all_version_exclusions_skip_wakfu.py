# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.

"""The exclusions every Dofus version shares are not applied to Wakfu."""
import os

from django.test import SimpleTestCase

from chardata.lock_forbid import (DEFAULT_EXCLUSION_ANKAMA_IDS,
                                  DEFAULT_EXCLUSION_ANKAMA_IDS_BY_VERSION,
                                  default_exclusion_ankama_ids, get_default_exclusions)
from fashionistapulp.game_versions import GAME_VERSIONS
from fashionistapulp.structure import set_current_game_version

CHECKED_ITEMS = (27278, 27645)


class TheAllVersionExclusionsSkipWakfuTests(SimpleTestCase):
    def test_the_wakfu_list_holds_no_id_of_the_all_version_list(self):
        shared = set(DEFAULT_EXCLUSION_ANKAMA_IDS)
        self.assertEqual(set(), shared & set(default_exclusion_ankama_ids('wakfu')))

    def test_a_dofus_version_gets_the_all_version_list_then_its_own(self):
        dofus_keys = [key for key, known in GAME_VERSIONS.items() if known.dofus]
        self.assertEqual(5, len(dofus_keys))
        for key in dofus_keys:
            self.assertEqual(
                DEFAULT_EXCLUSION_ANKAMA_IDS
                + DEFAULT_EXCLUSION_ANKAMA_IDS_BY_VERSION.get(key, []),
                default_exclusion_ankama_ids(key), key)

    def test_the_default_exclusions_of_a_wakfu_build_skip_the_all_version_items(self):
        from fashionistapulp.fashionista_config import get_items_db_path
        from fashionistapulp.structure import get_structure
        if not os.path.exists(get_items_db_path('wakfu')):
            self.skipTest('no Wakfu database built; run update_data_wakfu.py')
        structure = get_structure('wakfu')
        found = {ankama_id: structure.get_item_by_ankama_id(ankama_id)
                 for ankama_id in CHECKED_ITEMS}
        print('items checked:', {ankama_id: getattr(item, 'id', None)
                                 for ankama_id, item in found.items()})
        for ankama_id, item in found.items():
            self.assertIsNotNone(item, 'item %d is not in the Wakfu data' % ankama_id)
        set_current_game_version('wakfu')
        try:
            excluded = set(get_default_exclusions(None))
        finally:
            set_current_game_version('dofus3')
        for ankama_id, item in found.items():
            self.assertNotIn(item.id, excluded, ankama_id)
