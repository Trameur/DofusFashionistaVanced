"""Invented items, structure and block, so the sublimation rules run without the database.

Not a test module: the tests import it. use_block() swaps the generated block for the
invented one in wakfu_sublimations, the only place that reads it.
"""

import collections
import types
from unittest import mock

from fashionistapulp import wakfu_runes, wakfu_sublimations

RED, GREEN, BLUE, WHITE = 1, 2, 3, 4

RELIC_RARITY, EPIC_RARITY = 5, 7

Stat = collections.namedtuple('Stat', 'id key')

STATS = {1: Stat(1, 'ap'), 2: Stat(2, 'dmg_in_percent'), 3: Stat(3, 'hp'),
         4: Stat(4, 'critical_bonus'), 5: Stat(5, 'ferocity'),
         6: Stat(6, 'final_dmg_in_percent')}

TYPES = {1: 'HEAD', 2: 'NECK', 3: 'CHEST', 4: 'BACK', 5: 'LEGS'}


class Piece:
    def __init__(self, ident, kind, sockets=4, rarity=1, stats=(), level=100, flags=()):
        self.id = ident
        self.name = 'Piece %d' % ident
        self.type = kind
        self.level = level
        self.removed = False
        self.flags = list(flags)
        self.localized_names = None
        self.criteria = None
        self.shard_slots = (0, sockets)
        self.rarity = rarity
        self.stats = list(stats)


class Structure:
    """What wakfu_legality.violations reads of a catalogue."""

    def __init__(self, pieces, bases=None):
        self.pieces = {piece.id: piece for piece in pieces}
        self.shards = {}
        self.bases = bases if bases is not None else {1: {'ap': 6, 'ferocity': 0}}

    def get_type_positions(self):
        return list(TYPES.items())

    def get_item_by_id(self, ident):
        return self.pieces.get(ident)

    def get_stat_by_key(self, key):
        return next((stat for stat in STATS.values() if stat.key == key), None)

    def get_stat_by_id(self, ident):
        return STATS.get(ident)

    def get_breed_base_values(self):
        return {breed: dict(values) for breed, values in self.bases.items()}

    def get_breed_names(self):
        return {breed: 'Breed %d' % breed for breed in self.bases}


def socket_row(*colours):
    """Sockets of a piece with no rune, in the colours given."""
    return [wakfu_runes.Socket(at, colour, None, 0, 0, False, 0)
            for at, colour in enumerate(colours)]


def block(states=None, sublimations=None, gear=None, passives=None, generic=None):
    return types.SimpleNamespace(
        STATES=states or {}, SUBLIMATIONS=sublimations or {}, GEAR_STATES=gear or {},
        PASSIVES=passives or {}, RARITY_RELIC=RELIC_RARITY, RARITY_EPIC=EPIC_RARITY,
        PASSIVE_SLOT_LEVELS=(10, 30, 50, 100, 150, 200), GENERIC_BREED=generic)


def state(lines=(), conditions=(), conversions=(), cap=None, family='A', shares=()):
    return {'name': 'State', 'family': family, 'cap': cap, 'caps': {}, 'lines': list(lines),
            'shares': list(shares), 'conditions': list(conditions),
            'conversions': list(conversions), 'uncounted': []}


def use_block(case, found):
    """Make wakfu_sublimations read `found` for the length of one test of `case`."""
    patcher = mock.patch.object(wakfu_sublimations, 'load', return_value=found)
    patcher.start()
    case.addCleanup(patcher.stop)
    return found
