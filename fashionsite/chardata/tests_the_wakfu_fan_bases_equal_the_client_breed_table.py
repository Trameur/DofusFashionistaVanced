import os

from django.test import SimpleTestCase


class TheWakfuFanBasesEqualTheClientBreedTableTests(SimpleTestCase):
    def setUp(self):
        from fashionistapulp.fashionista_config import get_items_db_path
        from fashionistapulp.structure import get_structure
        if not os.path.exists(get_items_db_path('wakfu')):
            self.skipTest('no Wakfu database built; run update_data_wakfu.py')
        self.bases = get_structure('wakfu').get_breed_base_values()
        if not self.bases:
            self.skipTest('the Wakfu database holds no breed table')

    def rule(self, name):
        from fashionistapulp.wakfu_value_rules import FAN, RULES
        rule = RULES[name]
        self.assertEqual(FAN, rule.status)
        self.assertIn('WakForge', rule.source)
        return rule.value

    def test_the_fan_life_base_equals_every_breed_hp(self):
        self.assertGreaterEqual(len(self.bases), 18)
        self.assertEqual({self.rule('base_life')}, {table['hp'] for table in self.bases.values()})

    def test_the_fan_critical_hit_base_equals_every_breed_ferocity(self):
        self.assertEqual({self.rule('base_critical_hit_percent')},
                         {table['ferocity'] for table in self.bases.values()})
