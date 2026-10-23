import io
import re

from django.core.management import call_command
from django.test import SimpleTestCase

from chardata.tests_wakfu_build_solves_on_the_damage_model import wakfu_structure

SOCKET_LINE = re.compile(
    r'^  (\d) (red|green|blue|white) (.+) (\d+) tier (\d+) \+(\d+) (\w+)( \(doubled\))?, '
    r'(\d+) shards$')


class TheWakfuBuildCommandPrintsEveryRuneSocketTests(SimpleTestCase):
    def setUp(self):
        self.structure = wakfu_structure(self)

    def run_command(self, *args):
        out = io.StringIO()
        call_command('wakfu_build', *args, stdout=out, no_color=True)
        return out.getvalue().splitlines()

    def sockets(self, lines):
        return [SOCKET_LINE.match(line) for line in lines if SOCKET_LINE.match(line)]

    def test_the_rune_list_prints_each_tier_from_the_value_function(self):
        from fashionistapulp import wakfu_runes
        lines = self.run_command('--list-runes')
        rune = self.structure.shards[27097]
        at = lines.index(next(line for line in lines if line.startswith('27097 Melee Mastery')))
        self.assertEqual('27097 Melee Mastery red melee_dmg, doubled on BACK, HEAD', lines[at])
        for tier in range(1, len(rune.costs) + 1):
            self.assertEqual(
                '  tier %-2d item level %-3d  +%d single  +%d doubled  %d shards' % (
                    tier, rune.requirements[tier - 1], wakfu_runes.value(rune, tier, False),
                    wakfu_runes.value(rune, tier, True), wakfu_runes.shards_at(rune, tier)),
                lines[at + tier])
        self.assertIn('  tier 10 item level 186  +30 single  +60 doubled  3199 shards', lines)

    def test_the_two_runes_that_give_nothing_say_so(self):
        lines = self.run_command('--list-runes')
        self.assertIn('27095 Single-Target Mastery red: gives nothing', lines)
        self.assertIn('27096 Area Mastery red: gives nothing', lines)

    def test_every_socket_prints_its_colour_rune_tier_value_and_shards(self):
        lines = self.run_command('--level', '50', '--weights', 'melee_dmg=1', '--seconds', '60')
        sockets = self.sockets(lines)
        self.assertTrue(sockets, lines)
        total = 0
        for found in sockets:
            _index, colour, name, ident, tier, number, key, doubled, shards = found.groups()
            rune = self.structure.shards[int(ident)]
            self.assertEqual(rune.names['en'], name)
            self.assertEqual('melee_dmg', key)
            self.assertEqual(2, int(tier))
            self.assertEqual(self.structure.shards[int(ident)].costs[0] + rune.costs[1],
                             int(shards))
            total += int(shards)
        self.assertIn('  total shards: %d' % total, lines)

    def test_a_doubled_socket_says_so_and_gives_twice_the_single_value(self):
        lines = self.run_command('--level', '50', '--weights', 'melee_dmg=1', '--seconds', '60')
        values = {found.group(8): int(found.group(6)) for found in self.sockets(lines)}
        self.assertEqual({' (doubled)': 6, None: 3}, values)

    def test_the_rune_tier_caps_every_socket(self):
        lines = self.run_command('--level', '50', '--weights', 'melee_dmg=1', '--seconds', '60',
                                 '--rune-tier', '1')
        sockets = self.sockets(lines)
        self.assertTrue(sockets, lines)
        self.assertEqual({'1'}, {found.group(5) for found in sockets})
        self.assertIn('  runes (optimistic, at most tier 1)', lines)

    def test_the_none_mode_prints_no_socket_and_the_left_out_line_says_why(self):
        lines = self.run_command('--level', '20', '--elements', 'fire', '--reach', 'distance',
                                 '--runes', 'none')
        self.assertEqual([], self.sockets(lines))
        self.assertFalse([line for line in lines if line.startswith('  runes (')])
        left_out = [line for line in lines
                    if line.startswith('  systems the model leaves out: ')][0]
        self.assertTrue(left_out.endswith('runes (left out by the mode)'), left_out)
