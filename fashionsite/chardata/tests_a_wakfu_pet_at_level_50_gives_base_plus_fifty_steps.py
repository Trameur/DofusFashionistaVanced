import collections
import io
import os

from django.core.management import call_command
from django.test import SimpleTestCase

CHACHAGORA = 12127
MOOFLY = 15100
MOUNT = 14422
GEMLIN = 12237
KERUBABY = 20274


class APetGivesItsLinesAtTheLevelItIsWornAtTests(SimpleTestCase):
    """The shipped Wakfu database; skipped when it is absent."""

    def setUp(self):
        from fashionistapulp.fashionista_config import get_items_db_path
        from fashionistapulp.structure import get_structure
        if not os.path.exists(get_items_db_path('wakfu')):
            self.skipTest('no Wakfu database built; run update_data_wakfu.py')
        self.structure = get_structure('wakfu')
        if self.structure.get_item_by_id(CHACHAGORA) is None \
                or not hasattr(self.structure.get_item_by_id(CHACHAGORA), 'level_cap'):
            self.skipTest('the Wakfu database has no level tables')

    def item(self, ident):
        return self.structure.get_item_by_id(ident)

    def at(self, ident, level):
        """{stat key: value} of an item at a level, read through wakfu_companions."""
        from fashionistapulp import wakfu_companions
        return {self.structure.get_stat_by_id(stat_id).key: value
                for stat_id, value in wakfu_companions.lines_at(self.item(ident), level)}

    def test_chachagora_at_level_50_has_90_hp_and_60_initiative(self):
        self.assertEqual({'hp': 90, 'init': 60}, self.at(CHACHAGORA, 50))

    def test_chachagora_at_level_49_floors_88_5_to_88_hp_and_has_59_initiative(self):
        self.assertEqual({'hp': 88, 'init': 59}, self.at(CHACHAGORA, 49))

    def test_chachagora_at_level_0_has_its_base_15_hp_and_10_initiative(self):
        self.assertEqual({'hp': 15, 'init': 10}, self.at(CHACHAGORA, 0))

    def test_moofly_ferocity_is_3_at_50_1_at_17_and_0_at_16(self):
        self.assertEqual(3, self.at(MOOFLY, 50)['ferocity'])
        self.assertEqual(1, self.at(MOOFLY, 17)['ferocity'])
        self.assertNotIn('ferocity', self.at(MOOFLY, 16), 'a zero line is left out')
        self.assertEqual(40, self.at(MOOFLY, 50)['dmg_in_percent'])
        self.assertEqual(16, self.at(MOOFLY, 16)['dmg_in_percent'])

    def test_a_mount_gives_40_elemental_mastery_at_50_and_39_at_49(self):
        self.assertEqual({'dmg_in_percent': 40}, self.at(MOUNT, 50))
        self.assertEqual({'dmg_in_percent': 39}, self.at(MOUNT, 49))
        self.assertEqual('MOUNT', self.item(MOUNT).level_slot)

    def test_a_gemlin_asked_at_50_stays_at_its_cap_25_with_65_hp(self):
        from fashionistapulp import wakfu_companions
        gemlin = self.item(GEMLIN)
        self.assertEqual(25, gemlin.level_cap)
        levels = wakfu_companions.Levels(pet=50)
        level = wakfu_companions.level_of(levels, gemlin)
        self.assertEqual(25, level)
        self.assertEqual({'hp': 65}, self.at(GEMLIN, level))

    def test_kerubaby_has_cap_0_and_gives_30_hp_and_30_mastery(self):
        from fashionistapulp import wakfu_companions
        kerubaby = self.item(KERUBABY)
        self.assertEqual(0, kerubaby.level_cap)
        level = wakfu_companions.level_of(wakfu_companions.Levels(pet=50), kerubaby)
        self.assertEqual(0, level)
        self.assertEqual({'hp': 30, 'dmg_in_percent': 30}, self.at(KERUBABY, level))

    def test_the_stored_lines_of_every_leveled_item_are_its_values_at_the_cap(self):
        from fashionistapulp import wakfu_companions
        leveled = [item for item in self.structure.get_items_list()
                   if getattr(item, 'level_cap', None) is not None]
        self.assertGreater(len(leveled), 150)
        for item in leveled:
            self.assertEqual(
                collections.Counter(item.stats),
                collections.Counter(wakfu_companions.lines_at(item, item.level_cap)),
                '%s (%d)' % (item.name, item.id))

    def test_the_command_prints_the_pet_and_mount_levels_with_their_caps(self):
        out = io.StringIO()
        call_command('wakfu_build', '--weights', 'hp=1', '--level', '50',
                     '--pet-level', '10', '--mount-level', '20', '--seconds', '30',
                     stdout=out)
        lines = {line.split()[0]: line for line in out.getvalue().splitlines()
                 if line.startswith('  ') and line.split()
                 and line.split()[0] in ('PET', 'MOUNT')}
        self.assertIn('mount level 20 of 50', lines['MOUNT'])
        name = lines['PET'][19:57].strip()
        caps = {item.level_cap for item in self.structure.get_items_list()
                if item.name == name and getattr(item, 'level_cap', None) is not None}
        if caps:
            self.assertTrue(any('pet level %d of %d' % (min(10, cap), cap) in lines['PET']
                                for cap in caps), lines['PET'])
        else:
            self.assertNotIn('pet level', lines['PET'])
