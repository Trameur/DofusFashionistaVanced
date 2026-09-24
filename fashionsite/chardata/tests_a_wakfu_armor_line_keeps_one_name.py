# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
import importlib.util
import os

from django.test import SimpleTestCase

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), 'itemscraper', 'get_items_wakfu.py')


def _load():
    spec = importlib.util.spec_from_file_location('get_items_wakfu', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AWakfuArmorLineKeepsOneNameTests(SimpleTestCase):

    def test_the_template_form_and_the_parameter_form_give_one_stat(self):
        module = _load()
        by_template = module.characteristic(183, '[#charac ARMOR_GIVEN] [#1]% Armor given', [8])
        by_parameter = module.characteristic(39, '[#1]% [#charac]', [8, 0, 0, 0, 120])
        self.assertEqual(('ARMOR_GIVEN_PERCENT', 8), by_template)
        self.assertEqual(by_template, by_parameter)
        self.assertEqual(('ARMOR_RECEIVED_PERCENT', 4),
                         module.characteristic(185, '[#charac ARMOR_RECEIVED] [#1]% Armor received', [4]))

    def test_every_alias_lands_on_a_stat_the_catalogue_knows(self):
        from fashionistapulp.wakfu_stats import WAKFU_STATS
        module = _load()
        for alias, key in module.TEMPLATE_ALIASES.items():
            with self.subTest(alias=alias):
                self.assertIn(key, WAKFU_STATS)
                self.assertNotIn(alias, WAKFU_STATS)
