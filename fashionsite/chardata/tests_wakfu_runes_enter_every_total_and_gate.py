import contextlib
import io
import json

from chardata.tests_wakfu_solve_obeys_every_rule_on_invented_items import (
    AMULET, BOOTS, BREEDS, CATALOGUE, CHEST, EMBLEM, GREAT, HELMET, LEVEL, SHIELD,
    InventedItemsCase, builder, ids, item)
from chardata.tests_wakfu_effect_groups_resolve_to_known_effects import effect

RED, GREEN, BLUE = 1, 2, 3
HEAD, NECK, BACK, LEFT_HAND, RIGHT_HAND = 0, 4, 13, 7, 8
VERSION = '1.0'

MELEE, DODGE, TACKLE, NOTHING, INIT, RANGED = 900, 901, 902, 903, 904, 905
RUNES = (MELEE, DODGE, TACKLE, NOTHING, INIT, RANGED)

# Each tier of the four has exactly one line: (first tier, last tier, base, per level)
MELEE_LINES = ((0, 0, 1.0, 0.0), (1, 2, 0.0, 1.5), (3, 4, -3.0, 4.5))
FLAT_LINES = ((0, 0, 1.0, 0.0), (1, 4, 0.0, 3.0))
SLOPE_TWO = ((0, 0, 1.0, 0.0), (1, 4, 0.0, 2.0))
# Melee Mastery at tiers 1 to 4, single and doubled; Dodge and Tackle
MELEE_SINGLE = (1, 3, 10, 15)
MELEE_DOUBLED = (2, 6, 20, 30)
FLAT_SINGLE = (3, 6, 9, 12)
CURVE = [1, 2, 4, 8]
REQUIREMENT = [0, 36, 51, 66]

LOW_AMULET, HIGH_CHEST, NARROW_BOOTS = 1401, 1402, 1403
SOCKETS = {NARROW_BOOTS: 2}


LINES_OF = {}


def rune(ident, name, colour, action, stat, doubles, lines):
    LINES_OF[ident] = lines
    fields = {'color': colour, 'double_positions': doubles, 'curve': CURVE,
              'requirement': REQUIREMENT}
    made = []
    for number, (_low, _high, base, slope) in enumerate(lines):
        line = {'action': action, 'effect': ident * 10 + number, 'params': [base, slope],
                'value': base}
        if stat:
            line['stat'] = stat
        made.append(line)
    return {
        'id': ident, 'name': {'en': name, 'fr': name + ' fr'}, 'level': 0, 'type_id': 811,
        'type_name': {'en': 'Rune'}, 'positions': [], 'disables': [], 'rarity': 1,
        'set_id': None, 'gfx_id': 0, 'two_handed': False, 'exclusive': None,
        'shard_slots': [0, 0], 'shard': fields, 'lines': made}


RUNE_ITEMS = [
    rune(MELEE, 'Melee Mastery', RED, 1052, 'MELEE_DMG', [HEAD, BACK], MELEE_LINES),
    rune(DODGE, 'Dodge', GREEN, 175, 'DODGE', [LEFT_HAND, RIGHT_HAND], FLAT_LINES),
    rune(TACKLE, 'Lock', BLUE, 173, 'TACKLE', [LEFT_HAND, RIGHT_HAND], FLAT_LINES),
    rune(NOTHING, 'Single-Target', RED, 400, None, [NECK, HEAD], FLAT_LINES),
    rune(INIT, 'Initiative', GREEN, 171, 'INIT', [NECK, BACK], SLOPE_TWO),
    rune(RANGED, 'Distance Mastery', RED, 1053, 'RANGED_DMG', [BACK], MELEE_LINES),
]
# Pieces whose level allows another tier than the 50 of the rest
EXTRA = [item(LOW_AMULET, AMULET, 'Low Amulet', level=30, hp=500),
         item(HIGH_CHEST, CHEST, 'High Chest', level=70, hp=500),
         item(NARROW_BOOTS, BOOTS, 'Narrow Boots', level=70, hp=500)]


def socketed(piece):
    """The invented piece with the sockets of a real one; a second hand and an emblem have none."""
    made = dict(piece)
    none = made['type_id'] in (SHIELD, EMBLEM)
    made['shard_slots'] = [0, 0] if none else [1, SOCKETS.get(made['id'], 4)]
    return made


def client_effects(runes):
    return [dict(effect(line['effect'], line['action'], 'ITEM_EQUIP', made['id']),
                 min_level=low, max_level=high, params=line['params'])
            for made in runes
            for line, (low, high, _base, _slope) in zip(made['lines'], LINES_OF[made['id']])]


def write_inputs(directory, items):
    """The open data dump and the decoded client of a build; their paths."""
    dump = directory / 'transformed_wakfu.json'
    dump.write_text(json.dumps({'version': VERSION, 'equipment': items, 'breeds': BREEDS,
                                'labels': {}, 'nations': {}}), encoding='utf-8')
    client = directory / 'client' / 'x'
    client.mkdir(parents=True, exist_ok=True)
    (client / 'tables.json').write_text(json.dumps({
        'game_version': VERSION, 'item_ids': [one['id'] for one in items],
        'effects': client_effects([one for one in items if 'shard' in one]), 'groups': [],
        'states': [], 'sets': [], 'abilities': [], 'ability_categories': []}),
        encoding='utf-8')
    return dump, directory / 'client'


class ARuneCase(InventedItemsCase):
    """The invented items with four sockets on every piece but a second hand and an emblem."""

    @classmethod
    def catalogue(cls):
        return [socketed(one) for one in CATALOGUE] + RUNE_ITEMS

    @classmethod
    def build_db(cls, directory, items):
        dump, client = write_inputs(directory, items)
        with contextlib.redirect_stdout(io.StringIO()):
            builder.main(['--dump', str(dump), '--db', str(cls.db),
                          '--out', str(directory / 'raw'), '--client', str(client)])

    def build(self, weights, runes='optimistic', rune_tier=None, **options):
        from fashionistapulp.wakfu_model import WakfuBuild
        return WakfuBuild(self.structure, LEVEL, weights, runes=runes, rune_tier=rune_tier,
                          **options)

    def solve_runes(self, weights, runes='optimistic', rune_tier=None, **options):
        """(build, set) of a solve with the rune mode given."""
        build = self.build(weights, runes, rune_tier, **options)
        return build, build.build().solve()

    def rune_columns(self, build):
        return [name for name in build.problem.variable_names() if name.startswith('rn_')]

    def violations(self, worn, **options):
        from fashionistapulp import wakfu_legality
        return wakfu_legality.violations(self.structure, LEVEL, worn, runes=worn.runes,
                                         rune_tier=worn.rune_tier, **options)

    def socket_values(self, worn, positions=None):
        """Counter-free list of every filled Socket of the set, positions limited if given."""
        return [socket for position, sockets in sorted(worn.runes.items())
                if positions is None or position in positions
                for socket in sockets if socket.rune is not None]


GATE_OPEN, GATE_CLOSED, GATE_TACKLE = 1410, 1411, 1412
# The most Dodge the runes give outside HEAD at tier 2: seven positions of four sockets at 6
# and two rings of four at the doubled 12; HEAD holds four more at 6
DODGE_OUTSIDE_HEAD = 7 * 4 * 6 + 2 * 4 * 12
DODGE_WITH_HEAD = DODGE_OUTSIDE_HEAD + 4 * 6


class ARuneGateCase(ARuneCase):
    """Three helmets worth far more than any other, each behind a condition on a rune stat."""

    BOUNDS = {GATE_OPEN: 'GetCharac("DODGE") >= %d' % DODGE_OUTSIDE_HEAD,
              GATE_CLOSED: 'GetCharac("DODGE") >= %d' % (DODGE_OUTSIDE_HEAD + 1),
              GATE_TACKLE: 'GetCharac("TACKLE") <= 100'}
    WANTED = (GATE_OPEN, GATE_CLOSED, GATE_TACKLE)

    @classmethod
    def catalogue(cls):
        gates = [socketed(item(ident, HELMET, 'Gate %d' % ident, criteria=cls.BOUNDS[ident],
                               hp=1000)) for ident in cls.WANTED]
        return super().catalogue() + gates


class TheRunesFillTheSocketsOfTheWornPiecesTests(ARuneCase):
    def test_every_socketed_piece_gets_its_four_sockets_and_a_second_hand_none(self):
        _build, worn = self.solve_runes({'melee_dmg': 1, 'hp': 1}, forbidden=[GREAT])
        self.assertIn('SECOND_WEAPON', worn)
        self.assertNotIn('SECOND_WEAPON', worn.runes)
        self.assertEqual({'HEAD', 'NECK', 'CHEST', 'SHOULDERS', 'BACK', 'BELT', 'LEGS',
                          'LEFT_HAND', 'RIGHT_HAND', 'FIRST_WEAPON'}, set(worn.runes))
        for position, sockets in worn.runes.items():
            self.assertEqual([0, 1, 2, 3], [socket.index for socket in sockets], position)
        self.assertEqual('optimistic', worn.rune_mode)
        self.assertIsNone(worn.rune_tier)

    def test_the_filled_sockets_come_first_and_an_empty_one_has_no_colour_rune_or_tier(self):
        _build, worn = self.solve_runes({'melee_dmg': 1})
        _build, empty = self.solve_runes({'hp': 1})
        for sockets in empty.runes.values():
            for socket in sockets:
                self.assertEqual((None, None, None, 0, False, 0),
                                 socket[1:], 'an empty socket')
        for sockets in worn.runes.values():
            filled = [socket.rune is not None for socket in sockets]
            self.assertEqual(sorted(filled, reverse=True), filled)

    def test_the_stat_totals_of_a_set_hold_the_values_of_its_sockets(self):
        build, worn = self.solve_runes({'melee_dmg': 1})
        self.assertEqual(sum(socket.value for socket in self.socket_values(worn)),
                         build.totals(worn)['melee_dmg'])
        self.assertEqual([], self.violations(worn))


def dodge_outside(worn, position='HEAD'):
    return sum(socket.value for place, sockets in worn.runes.items() if place != position
               for socket in sockets if socket.rune == DODGE)


class ARuneOpensAGatedPieceTests(ARuneGateCase):
    def only(self, ident):
        return [one for one in self.WANTED if one != ident]

    def test_a_minimum_gate_is_opened_by_runes_in_the_sockets_of_the_other_pieces(self):
        self.assertEqual(264, DODGE_OUTSIDE_HEAD)
        build, worn = self.solve_runes({'hp': 1}, forbidden=self.only(GATE_OPEN))
        self.assertEqual(GATE_OPEN, worn['HEAD'].id)
        self.assertEqual(DODGE_OUTSIDE_HEAD, dodge_outside(worn))
        self.assertGreaterEqual(build.totals(worn)['dodge'], DODGE_OUTSIDE_HEAD)
        self.assertEqual([], self.violations(worn))

    def test_without_runes_the_same_gate_keeps_its_piece_out(self):
        _build, worn = self.solve_runes({'hp': 1}, runes='none', forbidden=self.only(GATE_OPEN))
        self.assertNotEqual(GATE_OPEN, worn['HEAD'].id)
        locked = self.build({'hp': 1}, runes='none', forbidden=self.only(GATE_OPEN),
                            locked=[(GATE_OPEN, None)])
        self.assertIsNone(locked.build().solve())
        self.assertEqual('infeasible', locked.reason)

    def test_a_piece_whose_own_runes_would_lift_it_over_its_own_minimum_is_not_worn(self):
        self.assertEqual(DODGE_OUTSIDE_HEAD + 24, DODGE_WITH_HEAD)
        build, worn = self.solve_runes({'hp': 1}, forbidden=self.only(GATE_CLOSED))
        self.assertNotEqual(GATE_CLOSED, worn['HEAD'].id)
        locked = self.build({'hp': 1}, forbidden=self.only(GATE_CLOSED),
                            locked=[(GATE_CLOSED, None)])
        self.assertIsNone(locked.build().solve())
        self.assertEqual('infeasible', locked.reason)

    def test_the_checker_reads_a_piece_without_its_own_runes(self):
        from fashionistapulp import wakfu_legality
        _build, worn = self.solve_runes({'hp': 1}, forbidden=self.only(GATE_OPEN))
        runes = {position: [(socket.colour, socket.rune, socket.tier) for socket in sockets
                            if socket.rune is not None]
                 for position, sockets in worn.runes.items()}
        head = [(GREEN, DODGE, 2)] * 4
        outside = dodge_outside(worn)
        self.assertEqual(DODGE_OUTSIDE_HEAD, outside)
        runes['HEAD'] = head
        self.assertEqual([], wakfu_legality.violations(self.structure, LEVEL, worn, runes=runes))
        # One socket short outside HEAD: with the four of HEAD the total still reaches the
        # bound, without them it does not
        runes['NECK'] = runes['NECK'][:-1]
        found = wakfu_legality.violations(self.structure, LEVEL, worn, runes=runes)
        self.assertEqual(1, len(found), found)
        self.assertIn('Gate %d' % GATE_OPEN, found[0][1])
        self.assertIn('DODGE', found[0][1].upper())

    def test_a_maximum_gate_on_a_stat_the_runes_give_is_respected_with_every_rune_counted(self):
        weights = {'hp': 1, 'tackle': 1}
        build, worn = self.solve_runes(weights, forbidden=self.only(GATE_TACKLE))
        self.assertEqual(GATE_TACKLE, worn['HEAD'].id)
        total = build.totals(worn)['tackle']
        self.assertGreater(total, 90)
        self.assertLessEqual(total, 100)
        self.assertEqual(total, sum(socket.value for socket in self.socket_values(worn)
                                    if socket.rune == TACKLE))
        self.assertEqual([], self.violations(worn))
        _build, bare = self.solve_runes(weights, runes='none', forbidden=self.only(GATE_TACKLE))
        self.assertEqual(GATE_TACKLE, bare['HEAD'].id)

    def test_the_checker_flags_a_maximum_gate_the_runes_break(self):
        _build, worn = self.solve_runes({'hp': 1, 'tackle': 1},
                                        forbidden=self.only(GATE_TACKLE))
        runes = {position: [(socket.colour, socket.rune, socket.tier) for socket in sockets
                            if socket.rune is not None]
                 for position, sockets in worn.runes.items()}
        runes['SHOULDERS'] = [(BLUE, TACKLE, 2)] * 4
        runes['NECK'] = [(BLUE, TACKLE, 2)] * 4
        from fashionistapulp import wakfu_legality
        found = wakfu_legality.violations(self.structure, LEVEL, worn, runes=runes)
        self.assertTrue(found and 'Gate %d' % GATE_TACKLE in found[0][1], found)


class AMinimumOnlyRunesReachTests(ARuneCase):
    @classmethod
    def catalogue(cls):
        return super().catalogue() + [socketed(item(1420, BOOTS, 'Dodge Boots', hp=1, dodge=20))]

    def test_runes_reach_a_minimum_the_gear_cannot(self):
        from fashionistapulp import wakfu_legality
        minimums = {'dodge': 100}
        bare = self.build({'hp': 1}, runes='none', minimums=minimums)
        self.assertIsNone(bare.build().solve())
        self.assertEqual('infeasible', bare.reason)
        build, worn = self.solve_runes({'hp': 1}, minimums=minimums)
        self.assertGreaterEqual(build.totals(worn)['dodge'], 100)
        self.assertEqual([], self.violations(worn, minimums=minimums))

    def test_a_rune_line_is_a_term_of_its_stat_total_and_no_other(self):
        build = self.build({'hp': 1}, minimums={'dodge': 100})
        build.build()
        self.assertTrue(any(category == 'rn' for _c, category, _n
                            in build.stat_total_expr('dodge').terms))
        self.assertFalse(any(category == 'rn' for _c, category, _n
                             in build.stat_total_expr('hp').terms))
        self.assertTrue(build.stat_total_expr('dodge').highest >= 100)

    def test_the_checker_counts_the_runes_in_a_minimum(self):
        minimums = {'dodge': 100}
        _build, worn = self.solve_runes({'hp': 1}, minimums=minimums)
        self.assertEqual([], self.violations(worn, minimums=minimums))
        found = self.violations(worn, minimums={'dodge': 10000})
        self.assertEqual(['minimum'], [rule for rule, _text in found])
