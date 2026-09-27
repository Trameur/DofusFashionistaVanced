import io
import os

from django.core.management import call_command
from django.test import SimpleTestCase

HANDS = {'LEFT_HAND', 'RIGHT_HAND'}
REASONS = {'no item fits', 'two-handed weapon', 'left empty by the solver'}


class WakfuSolveCase(SimpleTestCase):
    def setUp(self):
        from fashionistapulp.fashionista_config import get_items_db_path
        from fashionistapulp.structure import get_structure
        if not os.path.exists(get_items_db_path('wakfu')):
            self.skipTest('no Wakfu database built; run update_data_wakfu.py')
        self.structure = get_structure('wakfu')

    def worn_in(self, position, level=245):
        types = {type_id for type_id, place in self.structure.get_type_positions() if place == position}
        return [item for item in self.structure.get_available_items_list()
                if item.type in types and item.level <= level]

    def rings(self, level=245, leave_out=()):
        return [item for item in self.worn_in('LEFT_HAND', level) if item.id not in leave_out]

    def life(self, item):
        hp = self.structure.get_stat_by_key('hp').id
        return sum(value for stat_id, value in item.stats if stat_id == hp)


class AWakfuSolveSaysWhenItDroppedTheFullSetTests(WakfuSolveCase):
    def two_rings(self):
        """The two rings with the most HP, each from a different ring."""
        from fashionistapulp.wakfu_model import same_item
        best = {}
        for item in sorted(self.rings(), key=lambda item: (-self.life(item), item.id)):
            best.setdefault(same_item(item), item)
            if len(best) == 2:
                break
        first, second = best.values()
        self.assertGreater(self.life(second), 0)
        return first, second

    def solve(self, allowed, full_set=True):
        from fashionistapulp.wakfu_model import WakfuBuild
        forbidden = {item.id for item in self.structure.get_items_list()} - {item.id for item in allowed}
        build = WakfuBuild(self.structure, 245, {'hp': 1}, forbidden, full_set)
        return build, build.build().solve()

    def test_one_ring_for_two_hands_drops_the_full_set(self):
        from fashionistapulp.wakfu_slots import SLOTS
        first, _second = self.two_rings()
        build, worn = self.solve([first])
        self.assertIsNotNone(worn)
        self.assertTrue(worn.full_set_dropped)
        self.assertEqual('Infeasible', worn.full_set_status)
        self.assertEqual([first.id], [item.id for item in worn.values()])
        self.assertEqual(set(SLOTS) - HANDS, set(worn.no_candidate))
        self.assertTrue(build.solve().full_set_dropped, 'a second solve forgot the dropped full set')

    def test_a_set_that_fills_every_slot_is_not_flagged(self):
        from fashionistapulp.wakfu_slots import SLOTS
        build, worn = self.solve(self.two_rings())
        self.assertTrue(build.full_set)
        self.assertEqual(HANDS, set(worn))
        self.assertFalse(worn.full_set_dropped)
        self.assertIsNone(worn.full_set_status)
        self.assertEqual(set(SLOTS) - HANDS, set(worn.no_candidate))

    def test_a_caller_that_allowed_empty_slots_is_not_told_the_full_set_was_dropped(self):
        first, _second = self.two_rings()
        _build, worn = self.solve([first], full_set=False)
        self.assertEqual([first.id], [item.id for item in worn.values()])
        self.assertFalse(worn.full_set_dropped)


class TheWakfuBuildCommandSaysWhatTheSolverDidTests(WakfuSolveCase):
    def run_command(self, *args):
        out = io.StringIO()
        call_command('wakfu_build', *args, stdout=out, no_color=True)
        return out.getvalue()

    def empty_slots(self, out):
        """{slot: reason} from the command's empty line."""
        lines = [line[len('empty: '):] for line in out.splitlines() if line.startswith('empty: ')]
        self.assertLessEqual(len(lines), 1, out)
        if not lines:
            return {}
        empty = {}
        for part in lines[0].split(', '):
            slot, reason = part.split(' (', 1)
            self.assertTrue(reason.endswith(')'), part)
            empty[slot] = reason[:-1]
        self.assertEqual(set(), set(empty.values()) - REASONS)
        return empty

    def test_a_low_level_set_without_legacy_items_names_its_empty_slots(self):
        from fashionistapulp.wakfu_exclusions import default_exclusions
        from fashionistapulp.wakfu_model import WakfuBuild, same_item
        from fashionistapulp.wakfu_slots import SLOTS
        legacy = default_exclusions(self.structure)
        self.assertEqual(1, len({same_item(item) for item in self.rings(5, set(legacy))}),
                         'level 5 no longer has exactly one ring outside the legacy tier')
        self.assertGreater(len({same_item(item) for item in self.rings(5)}), 1)

        out = self.run_command('--level', '5', '--weights', 'hp=1')
        self.assertIn('leaving out %d legacy items' % len(legacy), out)
        dropped = [line for line in out.splitlines() if 'empty slots were allowed' in line]
        self.assertEqual(1, len(dropped), out)
        self.assertIn('(Infeasible)', dropped[0])
        empty = self.empty_slots(out)
        self.assertEqual(set(), set(empty) - set(SLOTS))
        self.assertTrue(HANDS & set(empty))
        self.assertEqual({'left empty by the solver'}, {empty[hand] for hand in HANDS & set(empty)})
        no_candidate = WakfuBuild(self.structure, 5, {'hp': 1}, legacy).build().solve().no_candidate
        self.assertEqual({slot for slot in empty if empty[slot] == 'no item fits'}, set(no_candidate))

        allowed = self.run_command('--level', '5', '--weights', 'hp=1', '--allow-legacy')
        self.assertNotIn('legacy items', allowed)
        self.assertNotIn('empty slots were allowed', allowed)

    def test_a_slot_no_allowed_item_fits_is_printed_without_the_fallback_warning(self):
        necks = sorted(item.id for item in self.worn_in('NECK', 20))
        self.assertTrue(necks)
        out = self.run_command('--level', '20', '--weights', 'hp=1', '--forbid', ','.join(map(str, necks)))
        self.assertNotIn('empty slots were allowed', out)
        self.assertEqual({'NECK': 'no item fits'}, self.empty_slots(out), out)

    def test_an_off_hand_under_a_two_handed_weapon_says_so(self):
        one_handed = sorted(item.id for item in self.worn_in('FIRST_WEAPON', 20)
                            if 'two_handed' not in (item.flags or ()))
        self.assertTrue(one_handed)
        out = self.run_command('--level', '20', '--weights', 'hp=1', '--forbid', ','.join(map(str, one_handed)))
        self.assertNotIn('empty slots were allowed', out)
        self.assertEqual({'SECOND_WEAPON': 'two-handed weapon'}, self.empty_slots(out), out)

    def test_each_spread_line_is_printed_with_the_elements_it_landed_on(self):
        from fashionistapulp.wakfu_exclusions import default_exclusions
        from fashionistapulp.wakfu_model import WakfuBuild
        out = self.run_command('--level', '110', '--weights', 'dmg_fire_percent=1')
        build = WakfuBuild(self.structure, 110, {'dmg_fire_percent': 1.0}, default_exclusions(self.structure))
        spread = build.spread_lines(build.build().solve())
        self.assertGreater(len(spread), 3)

        lines = out.splitlines()
        start = lines.index('  spread lines and the elements each landed on') + 1
        printed = lines[start:start + len(spread) + 1]
        self.assertEqual('', printed.pop(), 'more spread lines printed than the set carries')
        for (slot, item, key, value, landed), line in zip(spread, printed):
            with self.subTest(slot=slot):
                self.assertEqual(slot, line.split()[0])
                self.assertIn(item.name, line)
                self.assertIn('%+d %s -> ' % (value, key.upper()), line)
                self.assertEqual([name.upper() for name in landed], line.split(' -> ')[1].split(', '))
                if key == 'dmg_in_percent' and value > 0:
                    self.assertIn('DMG_FIRE_PERCENT', line)
