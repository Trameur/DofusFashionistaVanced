# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Every Dofus 2 set cap the solver reads names the stat the game's "Max." row caps."""
import json
import os

from django.test import SimpleTestCase

from chardata.tests import itemscraper_module


def _transformed_sets():
    repo_root = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    path = os.path.join(repo_root, 'itemscraper', 'dofus2', 'transformed_sets.json')
    with open(path, encoding='utf-8') as handle:
        return json.load(handle)


class EveryDofus2SetCapLandsOnItsStatTests(SimpleTestCase):

    def test_the_stored_caps_are_the_ones_the_game_rows_give(self):
        from fashionistapulp.structure import get_structure
        max_effects = itemscraper_module('max_effects')
        stat_by_id, keyword_by_id = max_effects.load_cap_stats(None)
        structure = get_structure('dofus2')

        expected, stored = {}, {}
        for set_data in _transformed_sets():
            for effect_data in set_data.get('stats_list') or []:
                for stat_name, max_value in max_effects.max_caps(
                        effect_data['effects'], stat_by_id, keyword_by_id):
                    expected.setdefault(set_data['ankama_id'], set()).add(
                        (int(effect_data['effect_key']), stat_name, max_value))
        for item_set in structure.sets_dict.values():
            for num_items, stat_id, max_value in item_set.max_caps:
                stored.setdefault(item_set.ankama_id, set()).add(
                    (num_items, structure.get_stat_by_id(stat_id).name, max_value))

        self.assertTrue(expected, 'no Dofus 2 set carries a "Max." row')
        self.assertEqual(expected, stored)
