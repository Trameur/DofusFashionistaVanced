#!/usr/bin/env python3
"""Write fashionistapulp/fashionistapulp/wakfu_special_items.py: the states of the
sublimations and gear, and the class passives, read from the decoded Wakfu client.

    python itemscraper/generate_wakfu_special_items.py
    python itemscraper/generate_wakfu_special_items.py --counts
    python itemscraper/generate_wakfu_special_items.py --show 5073
    python itemscraper/generate_wakfu_special_items.py --show 6989 --passive

The generator walks the roots of every state (table 67) through the effect groups (29) and
the states they apply (action 304), carrying the triggers (table 68's seven arrays) and the
criteria met on the way. A leaf is an effect that names a characteristic, or a non stat
action. Each leaf belongs to one family and a state to the first family present in
PRIMARY_ORDER:

    A  a fixed stat at the start of combat, no criterion
    B  a stat at the start of combat under a criterion about the build only
    C  a conversion of one stat into others at the start of combat
    D  a criterion about the turn, at the start of combat or on a turn trigger
    E  everything the fight settles, damage lines, subtrees the client recomputes
    F  healing, G armor and resistance, H action points under a trigger or a criterion
    I  an action that is not a stat   J  a state that has no leaf at all

Only A, B and C are counted by the solver; every other leaf is listed with its reason.
The block is Ankama data, so it is ignored by git and never edited by hand. A failure
leaves the previous block in place.

The state changes of the 1.92 and 1.93 update notes were read from
    https://www.wakfu.com/en/mmorpg/news/patch-notes/1770254-haven-paddocks/details
    https://www.wakfu.com/en/mmorpg/news/patch-notes/1771828-update-1-93/details
"""

from __future__ import annotations

import argparse
import collections
import io
import json
import os
import pprint
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'fashionistapulp'))
from fashionistapulp import wakfu_aptitudes, wakfu_criteria  # noqa: E402
from fashionistapulp.wakfu_stats import WAKFU_STATS  # noqa: E402

BLOCK = ROOT / 'fashionistapulp' / 'fashionistapulp' / 'wakfu_special_items.py'
CLIENT_DIR = ROOT / 'itemscraper' / 'wakfu_client'
RAW_DIR = ROOT / 'itemscraper' / 'wakfu_raw'

SUBLIMATION_TYPE = 812
APPLY_STATE = 304
CONVERSION = 913
CONVERSION_SOURCE_PARAM = 12
# The breed the client gives the passives every class can take
GENERIC_BREED = -2
# A source kept, a share of it added to a target, up to a share of the level: the child
# (source, target and share in percent) and the cap, as the parent effect's percent of level
RECOMPUTED = 999
ADD_SHARE = 1038
# A recomputed effect whose plain children each take a share of the character level: the
# share is param 14 plus param 15 times the state level, in percent, and a child's second
# value is its factor
LEVEL_SHARE_BASE_PARAM = 14
LEVEL_SHARE_PER_PARAM = 15
# The trigger the client gives the recomputed effect of a share added to another stat
RECOMPUTE_TRIGGER = ('V', 1001)
ADD_SHARE_SOURCE, ADD_SHARE_TARGET, ADD_SHARE_PERCENT = 0, 2, 6
ADD_SHARE_CAP_PARAM = 14
# Param 4 of the child is 0 in the shape read here; any other value is another shape
ADD_SHARE_KEPT_PARAM = 4
# 913 params that shape the converted amount (an offset, a factor and more); a plain
# conversion leaves them at 0 and takes its share from the child values
CONVERSION_SHAPE_PARAMS = (17, 19, 20, 21)
FAMILIES = 'ABCDEFGHIJ'
PRIMARY_ORDER = 'EHGFDCBAIJ'
COUNTED = 'ABC'
KINDS = ('normal', 'relic', 'epic', 'gear', 'passives')

# Trigger arrays of table 68, in field order (ints_esQ to ints_esW)
TRIGGER_LETTERS = 'QRSTUVW'
TURN_LETTERS = 'QRST'
START_OF_COMBAT = ('V', 1028)
# The client's texts read V1003 as the start of the fight too, and V1001 as the start of each
# turn, which comes after both. Only action points and shares of the level are read on V1003.
FIGHT_START = frozenset((START_OF_COMBAT, ('V', 1003)))
TURN_START = ('V', 1001)
FIRST_TURN_CALL = 'GetFightCurrentTableTurn'
LATE_FUNCTION = 'GetCharacLate'

# Calls a criterion can hold, by what they say. Anything else makes the leaf E. A stat call
# names the build whatever its target argument says: at the start of combat the effect target
# is the state bearer (the text of state 7256 reads its "target" masteries as the bearer's).
BUILD_CALLS = frozenset(wakfu_criteria.STAT_FUNCTIONS) | frozenset(
    wakfu_criteria.LEVEL_FUNCTIONS) | {'GetLevel', 'IsBreed', 'HasWeaponType'}
TURN_CALLS = frozenset((
    'IsTriggeredByMeleeEffect', 'IsTriggeredByIndirectEffect', 'IsTriggeredByZoneEffect',
    'IsActivatedByElement', 'IsActivatedBySpell', 'IsBackstabbed', 'IsFacestabbed',
    'IsSidestabbed', 'GetDistanceBetweenCasterAndTarget', 'IsTriggeringEffectCritical',
    'IsInDiagonal', 'HasLineOfSight', 'IsTriggeredByEffectWithREP'))
# A negated test of these holds: it guards the effect against a second application
WEAPON_CALL = 'HasWeaponType'
STATE_TESTS = frozenset(('HasState', 'HasStateFromLevel', 'HasStateFromUser'))

# Reviewed arbitrations. The generator counts the leaves each one decided (ARBITRATIONS).
ACTION_POINT_KEYS = frozenset(('AP', 'MP', 'WP'))
HEAL_KEYS = frozenset(('FINAL_HEAL_IN_PERCENT', 'HEAL_IN_PERCENT'))
GUARD_KEYS = frozenset((
    'ARMOR', 'ARMOR_GIVEN', 'ARMOR_RECEIVED', 'ARMOR_GIVEN_PERCENT',
    'ARMOR_RECEIVED_PERCENT', 'BLOCK', 'RES_IN_PERCENT', 'CRITICAL_RES', 'RES_BACKSTAB',
    'RES_FIRE_PERCENT', 'RES_WATER_PERCENT', 'RES_EARTH_PERCENT', 'RES_AIR_PERCENT'))
HEAL_ACTIONS = (24, 25)
ARMOR_ACTIONS = (1011, 1013)
DAMAGE_ACTIONS = (1, 1083)
STRUCTURE_ACTIONS = (330, 400, 304, 430, 1093)

# The caps the descriptions of a sublimation item give
CAP_PATTERNS = (
    ('en', 'en', re.compile(r'stack up to level (\d+)')),
    ('fr', 'fr', re.compile(r'un niveau de (\d+)')),
    ('max_stacking', 'en', re.compile(r'Max Stacking: (\d+)')),
)

# States the official 1.92 and 1.93 notes change, by the title of their sublimation
NOTE_192 = 'https://www.wakfu.com/en/mmorpg/news/patch-notes/1770254-haven-paddocks/details'
NOTE_193 = 'https://www.wakfu.com/en/mmorpg/news/patch-notes/1771828-update-1-93/details'
NOTED_SUBLIMATIONS = (
    ('AP Return', '1.93', NOTE_193), ('AP Rupture', '1.93', NOTE_193),
    ('Dimensionality II', '1.92', NOTE_192), ('Recklessness', '1.92', NOTE_192),
    ('Secondary Burn', '1.92', NOTE_192), ('About-Turn', '1.92', NOTE_192))
# Activations per turn the 1.93 notes give AP Return and AP Rupture by sublimation level
NOTE_ACTIVATIONS = {2: 1, 4: 2, 6: 3}
CONCORDANT = 'CONCORDANT'
NOT_READ = 'NOT_READ'
ACTIVATION_TEST = re.compile(
    r'GetStateLevel\((\d+)\)\s*>\s*\(GetStateLevel\((\d+)\)\s*\*\s*(\d+)\)')


class GeneratorError(ValueError):
    pass


class Leaf:
    """One effect of a walk that names a characteristic or a non stat action."""

    def __init__(self, effect, action, key, p0, p1, triggers, criteria, source, levels,
                 shaped=False):
        self.effect = effect
        self.action = action
        self.key = key
        self.p0 = p0
        self.p1 = p1
        self.triggers = triggers
        self.criteria = criteria
        self.source = source
        self.levels = levels
        self.shaped = shaped
        self.family = None
        self.reason = ''
        self.atoms = ()
        self.added = False
        self.cap = None
        self.share = False
        self.late = False


def number(value):
    return int(value) if value == int(value) else value


def alias(name):
    return wakfu_aptitudes.TEMPLATE_ALIASES.get(name, name)


def lower_key(name):
    """The stats table's spelling of a characteristic name."""
    return alias(name).lower()


class Naming:
    """Names the characteristic of an effect with the aptitude walker's own rules."""

    def __init__(self, action_texts, characteristics):
        self.texts = {int(action): text for action, text in action_texts.items()}
        self.by_id = {ident: name for name, ident in characteristics.items()}

    def characteristic(self, ident):
        name = self.by_id.get(int(ident))
        return None if name is None else alias(name)

    def leaf_key(self, effect):
        """(key, sign) for an effect that names a characteristic, else (None, reason)."""
        action = effect['action_id']
        sign = wakfu_aptitudes.CHARACTERISTIC_IN_PARAM.get(action)
        if sign is not None:
            named = int(effect['params'][4]) if len(effect['params']) > 4 else None
            key = self.characteristic(named) if named is not None else None
            if key is None:
                return None, 'characteristic %s is not in the client code' % named
            return key, sign
        shim = type('Structure', (), {'aptitude_action_texts': self.texts})()
        stand_in = type('Effect', (), {
            'action': action, 'params': effect['params'], 'id': effect['id']})()
        try:
            return wakfu_aptitudes._characteristic(shim, stand_in)
        except ValueError:
            return None, 'no characteristic'


def trigger_pairs(effect):
    return tuple((TRIGGER_LETTERS[index], int(code))
                 for index, codes in enumerate(effect.get('triggers') or ())
                 for code in codes)


class Analysis:
    """What a conjunction of criteria says: calls met, whether an `or` is in it, and the
    comparisons (function, key, operator, value) it holds."""

    def __init__(self):
        self.names = set()
        self.has_or = False
        self.atoms = []
        self.parsed = True


def _atom_key(call):
    if call.name in wakfu_criteria.STAT_FUNCTIONS and call.args:
        return str(call.args[0]).lower()
    return None


def _walk_tree(node, analysis):
    tree = wakfu_criteria
    if isinstance(node, tree.And):
        for child in node.children:
            _walk_tree(child, analysis)
    elif isinstance(node, tree.Or):
        analysis.has_or = True
        for child in node.children:
            _walk_tree(child, analysis)
    elif isinstance(node, tree.Hidden):
        _walk_tree(node.child, analysis)
    elif isinstance(node, tree.Not):
        inner = node.child
        call = inner.call if isinstance(inner, tree.Compare) else inner
        if isinstance(call, tree.Call) and call.name in STATE_TESTS:
            return
        if isinstance(call, tree.Call) and call.name == WEAPON_CALL and call.args:
            analysis.names.add(call.name)
            analysis.atoms.append((call.name, None, '!=', tuple(call.args)))
            return
        analysis.names.add('not %s' % (call.name if isinstance(call, tree.Call) else '?'))
    elif isinstance(node, tree.Compare):
        if node.call.name == FIRST_TURN_CALL and node.op == '==' and node.value == 1:
            return
        analysis.names.add(node.call.name)
        analysis.atoms.append((node.call.name, _atom_key(node.call), node.op, node.value))
    elif isinstance(node, tree.Call):
        analysis.names.add(node.name)
        if node.name == WEAPON_CALL and node.args:
            analysis.atoms.append((node.name, None, '==', tuple(node.args)))
            return
        argument = node.args[0] if node.args else None
        analysis.atoms.append((node.name, None if argument is None else str(argument),
                               '==', 1))
    elif isinstance(node, tree.Const):
        if not node.value:
            analysis.names.add('False')


_CALL = re.compile(r'([A-Za-z_][A-Za-z0-9_]*)\s*\(([^()]*)\)')
_OR = re.compile(r'\|\||\bor\b')
_NEGATED = re.compile(r'^\s*(?:not\s+|!)\s*[A-Za-z_]')


def analyse(texts):
    """The Analysis of criteria that all hold (a conjunction of the texts)."""
    analysis = Analysis()
    for text in texts:
        try:
            tree = wakfu_criteria.parse(text)
        except wakfu_criteria.CriteriaError:
            tree = None
        if tree is not None:
            _walk_tree(tree, analysis)
            continue
        analysis.parsed = False
        found = _CALL.findall(text)
        names = {name for name, _args in found}
        if _OR.search(text):
            analysis.has_or = True
        if names and names <= STATE_TESTS and _NEGATED.match(text):
            continue
        analysis.names.update(names)
        analysis.atoms.append(('text', ' '.join(text.split()), '', 0))
        if not found:
            analysis.names.add('unreadable')
    return analysis


def is_late(triggers, analysis):
    """True for a leaf of each turn's start that holds while some stat totals are not above
    zero ("the secondary masteries are 0 or less"): the first turn reads them once the start
    of the fight has been applied."""
    others = {pair for pair in triggers if pair != START_OF_COMBAT}
    return (others == {TURN_START} and not analysis.has_or and analysis.names <= BUILD_CALLS
            and any(atom[0] == 'GetCharac' for atom in analysis.atoms)
            and all(atom[0] not in wakfu_criteria.STAT_FUNCTIONS
                    or atom[:1] + atom[2:] == ('GetCharac', '<=', 0) for atom in analysis.atoms))


def keyed_family(key, triggers, analysis, convert, share=False):
    """(family, reason) of a leaf that names a characteristic; the match order is the
    design's: C, H, A, B, D, F, G, E."""
    late = is_late(triggers, analysis)
    start = FIGHT_START if share or key.upper() in ACTION_POINT_KEYS else {START_OF_COMBAT}
    others = set() if late else {pair for pair in triggers if pair not in start}
    names = analysis.names
    build_only = names <= BUILD_CALLS
    if analysis.has_or and not others:
        return 'E', 'an or criterion'
    if convert and not others and build_only:
        return 'C', 'conversion at the start of combat'
    upper = key.upper()
    if upper in ACTION_POINT_KEYS and (others or not build_only):
        return 'H', '%s under a trigger or a criterion' % upper
    if not others:
        if not names:
            return 'A', 'fixed at the start of combat'
        if build_only:
            return 'B', 'a criterion about the build'
        if names <= BUILD_CALLS | TURN_CALLS:
            return 'D', 'a criterion about the turn'
        return 'E', 'a criterion the fight settles'
    if upper in HEAL_KEYS:
        return 'F', '%s under a trigger' % upper
    if upper in GUARD_KEYS:
        return 'G', '%s under a trigger' % upper
    if names and names <= BUILD_CALLS | TURN_CALLS \
            and all(letter in TURN_LETTERS for letter, _code in others):
        return 'D', 'a turn trigger with a criterion about the turn'
    return 'E', '%s under a trigger' % upper


def share_family(leaf, analysis):
    """(family, reason) of a share of a stat added to another, the source kept."""
    others = {pair for pair in leaf.triggers
              if pair not in (START_OF_COMBAT, RECOMPUTE_TRIGGER)}
    if others or analysis.has_or or not analysis.names <= BUILD_CALLS:
        return 'E', 'a share of a stat added to another under a trigger or a criterion'
    return 'C', 'a share of a stat added to another, recomputed in the fight'


def ranged_family(leaf):
    """(family, reason) of a counted leaf that holds for some effect levels only."""
    reason = 'the effect holds for levels %s to %s only' % leaf.levels
    return ('H' if (leaf.key or '').upper() in ACTION_POINT_KEYS else 'E'), reason


def action_family(action, triggers, analysis):
    """(family, reason) of a leaf that names no characteristic."""
    if action in wakfu_aptitudes.SUBTREE_DROPPED:
        return 'E', 'the client recomputes the subtree in the fight'
    if action in HEAL_ACTIONS:
        return 'F', 'heal action %d' % action
    if action in ARMOR_ACTIONS:
        return 'G', 'armor action %d' % action
    if action in DAMAGE_ACTIONS:
        return 'E', 'damage action %d' % action
    return 'I', 'action %d is not a stat' % action


class Tables:
    """The decoded client tables a walk reads."""

    def __init__(self, tables, texts, code):
        self.effects = {record['id']: record for record in tables['effects']}
        self.groups = {record['id']: record['effect_ids'] for record in tables['groups']}
        self.states = {record['id']: record for record in tables['states']}
        self.spells = {record['id']: record for record in tables['spells']}
        families = texts['texts']
        self.state_names = families['state_names']['en']
        self.state_texts = families['state_descriptions']['en']
        self.spell_names = families['spell_names']['en']
        self.effect_texts = families['effect_texts']['en']
        self.naming = Naming(families['action_texts']['en'], code['characteristics'])
        self.ranged = collections.Counter()
        self.dropped = collections.Counter()
        if not self.effects or 'triggers' not in next(iter(self.effects.values())):
            raise GeneratorError('tables.json has no trigger arrays: decode the client again')

    def share_children(self, effect):
        """[(source, target, share, cap)] of a recomputed effect whose children each add a
        share of one characteristic to another, the source kept; None for any other shape.

        cap is the parent's limit as a share of the level, None when it names none."""
        children = [self.effects.get(member) for member in self.groups.get(effect['id'], ())]
        if not children or any(child is None or child['action_id'] != ADD_SHARE
                               or len(child['params']) <= ADD_SHARE_PERCENT
                               or (child.get('criterion') or '').strip()
                               or any(child.get('triggers') or ())
                               or (len(child['params']) > ADD_SHARE_KEPT_PARAM
                                   and child['params'][ADD_SHARE_KEPT_PARAM])
                               for child in children):
            return None
        params = effect['params']
        cap = params[ADD_SHARE_CAP_PARAM] / 100 if len(params) > ADD_SHARE_CAP_PARAM else 0
        found = []
        for child in children:
            values = child['params']
            source = self.naming.characteristic(values[ADD_SHARE_SOURCE])
            target = self.naming.characteristic(values[ADD_SHARE_TARGET])
            if source is None or target is None or not values[ADD_SHARE_PERCENT]:
                return None
            found.append((lower_key(source), lower_key(target),
                          number(round(values[ADD_SHARE_PERCENT] / 100, 6)),
                          number(cap) if cap else None))
        return found

    def level_shares(self, effect):
        """[(key, base, per level)] of a recomputed effect whose plain children each take a
        share of the character level, in percent; None for any other shape."""
        params = effect['params']
        if len(params) <= LEVEL_SHARE_PER_PARAM:
            return None
        base, per = params[LEVEL_SHARE_BASE_PARAM], params[LEVEL_SHARE_PER_PARAM]
        children = [self.effects.get(member) for member in self.groups.get(effect['id'], ())]
        if not (base or per) or not children:
            return None
        found = []
        for child in children:
            if (child is None or (child.get('criterion') or '').strip()
                    or any(child.get('triggers') or ()) or self.groups.get(child['id'])
                    or child['action_id'] in STRUCTURE_ACTIONS + (CONVERSION, RECOMPUTED)
                    or len(child['params']) < 2 or child['params'][0] or not child['params'][1]):
                return None
            key, sign = self.naming.leaf_key(child)
            if not key or not isinstance(sign, int):
                return None
            factor = sign * child['params'][1]
            found.append((lower_key(key), number(round(base * factor, 6)),
                          number(round(per * factor, 6))))
        return found

    def walk(self, roots, seen):
        """[Leaf] under the effect ids `roots`, in walk order."""
        leaves = []

        def visit(effect_id, triggers, criteria, convert, states, path, shaped=False):
            effect = self.effects.get(effect_id)
            if effect is None or effect_id in path:
                return
            text = (effect.get('criterion') or '').strip()
            if text == 'False':
                self.dropped['False'] += 1
                return
            if 'False' in analyse((text,)).names:
                self.dropped['and False'] += 1
                return
            triggers = triggers + trigger_pairs(effect)
            criteria = criteria + ((text,) if text else ())
            action = effect['action_id']
            levels = (effect.get('min_level'), effect.get('max_level'))
            shares = self.share_children(effect) if action == RECOMPUTED else None
            if shares:
                for source, target, share, cap in shares:
                    leaves.append(Leaf(effect_id, action, target, share, 0, triggers,
                                       criteria, source, levels, shaped))
                    leaves[-1].added = True
                    leaves[-1].cap = cap
                return
            level_shares = self.level_shares(effect) \
                if action == RECOMPUTED and convert is None else None
            if level_shares:
                for key, base, per in level_shares:
                    leaves.append(Leaf(effect_id, action, key, base, per, triggers, criteria,
                                       convert, levels, shaped))
                    leaves[-1].share = True
                return
            if action in wakfu_aptitudes.SUBTREE_DROPPED:
                leaves.append(Leaf(effect_id, action, None, 0, 0, triggers, criteria, convert,
                                   levels, shaped))
                return
            if action == CONVERSION:
                params = effect['params']
                named = (self.naming.characteristic(params[CONVERSION_SOURCE_PARAM])
                         if len(params) > CONVERSION_SOURCE_PARAM else None)
                convert = lower_key(named) if named else '?'
                shaped = any(len(params) > index and params[index]
                             for index in CONVERSION_SHAPE_PARAMS)
            elif action == APPLY_STATE:
                inner = int(effect['params'][0])
                if inner in self.states and inner not in states:
                    for root in self.states[inner]['effect_ids']:
                        visit(root, triggers, criteria, convert, states | {inner}, path, shaped)
            elif action not in STRUCTURE_ACTIONS:
                key, sign = self.naming.leaf_key(effect)
                params = effect['params']
                first = params[0] if params else 0
                second = params[1] if len(params) > 1 else 0
                if isinstance(sign, int):
                    leaves.append(Leaf(effect_id, action, lower_key(key), number(sign * first),
                                       number(sign * second), triggers, criteria, convert,
                                       levels, shaped))
                elif sign.startswith('characteristic'):
                    leaves.append(Leaf(effect_id, action, '', 0, 0, triggers, criteria,
                                       convert, levels, shaped))
                    leaves[-1].reason = sign
                else:
                    leaves.append(Leaf(effect_id, action, None, number(first), number(second),
                                       triggers, criteria, convert, levels, shaped))
            for member in self.groups.get(effect_id, ()):
                visit(member, triggers, criteria, convert, states, path | {effect_id}, shaped)

        for root in roots:
            visit(root, (), (), None, frozenset(seen), frozenset())
        return leaves

    def classify(self, leaf):
        """Set the family, the reason and the comparisons of a leaf."""
        analysis = analyse(leaf.criteria)
        leaf.atoms = analysis.atoms
        if leaf.added:
            leaf.family, leaf.reason = share_family(leaf, analysis)
        elif leaf.key == '':
            leaf.family = 'E'
        elif leaf.key is None:
            leaf.family, leaf.reason = action_family(leaf.action, leaf.triggers, analysis)
        else:
            leaf.family, leaf.reason = keyed_family(
                leaf.key, leaf.triggers, analysis, leaf.source, leaf.share)
        if leaf.family in COUNTED and not leaf.added and is_late(leaf.triggers, analysis):
            leaf.late = True
            analysis.atoms = [(LATE_FUNCTION,) + atom[1:] if atom[0] == 'GetCharac' else atom
                              for atom in analysis.atoms]
            leaf.atoms = analysis.atoms
        if leaf.levels not in ((0, 32767), (None, None), (0, None)):
            self.ranged[leaf.family] += 1
            if leaf.family in COUNTED:
                leaf.family, leaf.reason = ranged_family(leaf)
        if leaf.family == 'C' and leaf.shaped:
            leaf.family = 'E'
            leaf.reason = 'a conversion with an offset or a factor the model does not carry'
        return analysis

    def entry(self, roots, seen):
        """The block entry of an effect tree: family, lines, conditions, conversions and
        uncounted leaves, plus the Leaf list for display."""
        leaves = self.walk(roots, seen)
        analyses = [self.classify(leaf) for leaf in leaves]
        conditions = []
        lines, shares, conversions, uncounted = [], [], [], []
        for leaf, analysis in zip(leaves, analyses):
            if leaf.family in 'AB':
                guards = guard_indexes(conditions, analysis)
                (shares if leaf.share else lines).append(
                    (leaf.family, leaf.key, leaf.p0, leaf.p1, guards))
            elif leaf.family == 'C':
                guards = guard_indexes(conditions, analysis)
                sign = -1 if (leaf.p0 < 0 or leaf.p1 < 0) else 1
                conversions.append((leaf.source, leaf.key, abs(leaf.p0), abs(leaf.p1), sign,
                                    guards) + (() if leaf.cap is None else (leaf.cap,)))
            else:
                uncounted.append((leaf.family, leaf.action,
                                  '%s: %s' % (leaf.key or 'a%d' % leaf.action, leaf.reason)))
        present = {leaf.family for leaf in leaves}
        family = next((one for one in PRIMARY_ORDER if one in present), 'J')
        return {'family': family, 'lines': lines, 'shares': shares, 'conditions': conditions,
                'conversions': conversions, 'uncounted': uncounted}, leaves


def guard_indexes(conditions, analysis):
    """Indexes into the state's condition list of the comparisons a leaf needs."""
    found = []
    for atom in analysis.atoms:
        if atom not in conditions:
            conditions.append(atom)
        found.append(conditions.index(atom))
    return tuple(found)


def find_client(client_dir, game_version=None):
    """The folder of the newest decoded client (or that of `game_version`)."""
    found = []
    for path in sorted(Path(client_dir).glob('*/client_code.json')):
        payload = json.loads(path.read_text(encoding='utf-8'))
        if game_version is None or payload.get('game_version') == game_version:
            found.append((path.parent, payload))
    if not found:
        raise GeneratorError('no decoded client with client_code.json under %s' % client_dir)
    return found[-1]


def find_raw(raw_dir, game_version):
    """The data folder whose version starts with `game_version`, exactly one."""
    found = [path for path in sorted(Path(raw_dir).iterdir())
             if path.is_dir() and path.name.startswith(game_version + '.')
             and (path / 'items.json').exists()]
    if len(found) != 1:
        raise GeneratorError('%d data folders for game version %s under %s'
                             % (len(found), game_version, raw_dir))
    return found[0]


def load_inputs(client_dir, raw_dir):
    folder, code = find_client(client_dir)
    tables = json.loads((folder / 'tables.json').read_text(encoding='utf-8'))
    texts = json.loads((folder / 'texts.json').read_text(encoding='utf-8'))
    decoded = json.loads((folder / 'decoded.json').read_text(encoding='utf-8'))
    raw = find_raw(raw_dir, code['game_version'])
    items = json.loads((raw / 'items.json').read_text(encoding='utf-8'))
    positions = {record['definition']['id']: record['definition'].get('equipmentPositions') or []
                 for record in json.loads(
                     (raw / 'equipmentItemTypes.json').read_text(encoding='utf-8'))}
    return {'code': code, 'tables': tables, 'texts': texts, 'items': items,
            'positions': positions, 'breeds': {row['id'] for row in decoded['breeds']},
            'data_version': raw.name}


def item_state_lines(items, positions):
    """[(item, kind, state, level, title)]: sublimations (normal, relic, epic) and gear."""
    lines = []
    for record in items:
        definition = record['definition']
        item = definition['item']
        type_id = item['baseParameters']['itemTypeId']
        for effect in definition.get('equipEffects') or ():
            detail = effect['effect']['definition']
            if detail['actionId'] != APPLY_STATE:
                continue
            params = detail['params']
            if type_id == SUBLIMATION_TYPE:
                flags = item['sublimationParameters']
                kind = 'epic' if flags['isEpic'] else 'relic' if flags['isRelic'] else 'normal'
            elif positions.get(type_id):
                kind = 'gear'
            else:
                continue
            lines.append((item['id'], kind, int(params[0]), int(params[2]),
                          record['title'].get('en') or ''))
    return lines


def read_caps(items, state_of_item):
    """{state: {source: lowest cap read}} from the descriptions of the sublimation items,
    each state's items together."""
    caps = collections.defaultdict(dict)
    for record in items:
        item = record['definition']['item']
        state = state_of_item.get(item['id'])
        if state is None or item['baseParameters']['itemTypeId'] != SUBLIMATION_TYPE:
            continue
        for source, language, pattern in CAP_PATTERNS:
            found = pattern.search((record.get('description') or {}).get(language) or '')
            if found:
                caps[state][source] = min(int(found.group(1)),
                                          caps[state].get(source, int(found.group(1))))
    return caps


def activations(tables, state, level):
    """How many times the counter test of a state's tree passes at `level`, or None when the
    tree holds no such test."""
    for effect in tables.effects.values():
        found = ACTIVATION_TEST.search(effect.get('criterion') or '')
        if found and int(found.group(1)) == state:
            factor = int(found.group(3))
            return sum(1 for counter in range(level + 1) if level > factor * counter)
    return None


def changed_by_notes(data, tables, sublimations):
    """{state: (note, status, source)} for the sublimations the 1.92 and 1.93 notes change.

    A state is CONCORDANT only where the client's own tree gives the numbers of the notes."""
    by_title = collections.defaultdict(set)
    for item, (state, _level, _kind, _pattern) in sublimations.items():
        by_title[data['titles'][item]].add(state)
    changed = {}
    for title, note, source in NOTED_SUBLIMATIONS:
        states = set()
        for name, found in by_title.items():
            if name == title or re.fullmatch(re.escape(title) + r' [IVX]+', name):
                states |= found
        for state in sorted(states):
            status = NOT_READ
            if title in ('AP Return', 'AP Rupture'):
                read = {level: activations(tables, state, level) for level in NOTE_ACTIVATIONS}
                if read == NOTE_ACTIVATIONS:
                    status = CONCORDANT
            changed[state] = (note, status, source)
    return changed


def build(inputs):
    """The whole block as a dict of constants."""
    tables = Tables(inputs['tables'], inputs['texts'], inputs['code'])
    code = inputs['code']
    lines = item_state_lines(inputs['items'], inputs['positions'])
    titles = {item: title for item, _kind, _state, _level, title in lines}
    kind_of_state = {}
    for _item, kind, state, _level, _title in lines:
        if kind_of_state.setdefault(state, kind) != kind:
            raise GeneratorError('state %d is on items of two kinds' % state)
    state_of_item = {item: state for item, kind, state, _level, _title in lines
                     if kind != 'gear'}
    caps = read_caps(inputs['items'], state_of_item)
    items_of_state = collections.defaultdict(list)
    for item, _kind, state, _level, _title in lines:
        items_of_state[state].append(item)

    states = {}
    leaves_of = {}
    for state in sorted(kind_of_state):
        record = tables.states.get(state)
        roots = record['effect_ids'] if record else []
        entry, leaves = tables.entry(roots, {state})
        kind = kind_of_state[state]
        read = dict(caps.get(state, {}))
        if record and record['max_level']:
            read['table'] = record['max_level']
        if kind == 'normal' and not read:
            raise GeneratorError('normal sublimation state %d has no stack cap' % state)
        if any(len(conversion) > 6 for conversion in entry['conversions']):
            raise GeneratorError('state %d has a capped conversion, but the cap is a share of '
                                 'the character level and a state is read at its own' % state)
        name = tables.state_names.get(str(state)) or titles[items_of_state[state][0]]
        states[state] = dict(
            name=name, family=entry['family'], kind=kind,
            cap=min(read.values()) if kind == 'normal' else None,
            caps=read if kind == 'normal' else {}, lines=entry['lines'],
            shares=entry['shares'],
            conditions=entry['conditions'], conversions=entry['conversions'],
            uncounted=entry['uncounted'])
        leaves_of[('state', state)] = leaves

    sublimations, gear = {}, collections.defaultdict(list)
    for item, kind, state, level, title in lines:
        if kind == 'gear':
            gear[item].append((state, level))
        else:
            definition = next_definition(inputs, item)
            pattern = tuple(int(colour) for colour in
                            definition['sublimationParameters']['slotColorPattern'])
            sublimations[item] = (state, level, kind, pattern)
    data = dict(titles=titles)
    notes = changed_by_notes(data, tables, sublimations)

    passive_kinds = {value for name, value in code['spell_kinds'].items() if name != 'ACTIVE'}
    passives = {}
    for spell, record in sorted(tables.spells.items()):
        if record['kind'] not in passive_kinds or (
                record['breed'] not in inputs['breeds'] and record['breed'] != GENERIC_BREED):
            continue
        entry, leaves = tables.entry(record['effect_ids'], set())
        passives[spell] = dict(
            name=tables.spell_names.get(str(spell)) or '', breed=record['breed'],
            unlock=record['unlock_level'], family=entry['family'], lines=entry['lines'],
            shares=entry['shares'], conditions=entry['conditions'], conversions=entry['conversions'],
            uncounted=entry['uncounted'])
        leaves_of[('passive', spell)] = leaves

    arbitrations = collections.defaultdict(collections.Counter)
    for leaves in leaves_of.values():
        for leaf in leaves:
            for group, actions in (('heal', HEAL_ACTIONS), ('armor', ARMOR_ACTIONS),
                                   ('damage', DAMAGE_ACTIONS),
                                   ('untagged', tuple(wakfu_aptitudes.REVIEWED_UNTAGGED))):
                if leaf.action in actions:
                    arbitrations[group][leaf.action] += 1
    counts = family_counts(states, passives)
    return {
        'GAME_VERSION': code['game_version'], 'CLIENT_VERSION': code['client_version'],
        'DATA_VERSION': inputs['data_version'],
        'RARITY_RELIC': code['rarities']['RELIC'], 'RARITY_EPIC': code['rarities']['RELIC2'],
        'PASSIVE_KIND_ACTIVE': code['spell_kinds']['ACTIVE'], 'GENERIC_BREED': GENERIC_BREED,
        'PASSIVE_SLOT_LEVELS': tuple(code['passive_slot_levels']),
        'STATES': {state: {key: value for key, value in entry.items() if key != 'kind'}
                   for state, entry in states.items()},
        'SUBLIMATIONS': sublimations,
        'GEAR_STATES': {item: tuple(pairs) for item, pairs in sorted(gear.items())},
        'PASSIVES': passives, 'CHANGED_BY_NOTES': notes, 'COUNTS': counts,
        'ARBITRATIONS': {group: dict(sorted(found.items()))
                         for group, found in sorted(arbitrations.items())},
    }, tables, states, leaves_of


def next_definition(inputs, item):
    index = inputs.get('_index')
    if index is None:
        index = inputs['_index'] = {
            record['definition']['item']['id']: record['definition']['item']
            for record in inputs['items']}
    return index[item]


def family_counts(states, passives):
    """{kind: {'states': n, family: n, 'with_counted_leaf': n}} as the --counts table."""
    counts = {kind: collections.Counter() for kind in KINDS}
    for entry in list(states.values()) + list(passives.values()):
        kind = entry.get('kind', 'passives')
        counts[kind]['states'] += 1
        counts[kind][entry['family']] += 1
        if entry['lines'] or entry['shares'] or entry['conversions']:
            counts[kind]['with_counted_leaf'] += 1
    return {kind: {name: found[name] for name in
                   ('states',) + tuple(FAMILIES) + ('with_counted_leaf',)}
            for kind, found in counts.items()}


HEADER = '''# Generated by itemscraper/generate_wakfu_special_items.py
# from client {client} and data {data}; edit the generator, never this file.
#
# STATES {{state: {{'name', 'family', 'cap', 'caps', 'lines', 'shares', 'conditions',
#   'conversions', 'uncounted'}}}}. A line is (family, key, p0, p1, guards) and a conversion
#   (source key, target key, p0, p1, sign, guards[, cap]); the value at state level L is
#   p0 + p1 * L (a conversion's, the share of the source). A share has a line's shape and
#   reads p0 + p1 * L as a percent of the character's level. A conversion may end with a cap,
#   the most it moves as a share of the character's level. guards index the state's own
#   'conditions', each (function, key, operator, value); GetCharacLate reads the totals once
#   the start of the fight has been applied.
# SUBLIMATIONS {{item: (state, level, kind, slot colour pattern)}}.
# GEAR_STATES {{item: ((state, level), ...)}}.
# PASSIVES {{spell: {{'name', 'breed', 'unlock', 'family', 'lines', 'shares', 'conditions',
#   'conversions', 'uncounted'}}}}; the breed of a passive any class can take is GENERIC_BREED.
# CHANGED_BY_NOTES {{state: (note, status, source)}}; COUNTS {{kind: {{family: n}}}}.
'''

BLOCK_NAMES = ('GAME_VERSION', 'CLIENT_VERSION', 'DATA_VERSION', 'RARITY_RELIC', 'RARITY_EPIC',
               'PASSIVE_KIND_ACTIVE', 'GENERIC_BREED', 'PASSIVE_SLOT_LEVELS', 'STATES',
               'SUBLIMATIONS', 'GEAR_STATES', 'PASSIVES', 'CHANGED_BY_NOTES', 'COUNTS',
               'ARBITRATIONS')


def render(constants):
    """The text of the block."""
    out = [HEADER.format(client=constants['CLIENT_VERSION'], data=constants['DATA_VERSION'])]
    for name in BLOCK_NAMES:
        text = pprint.pformat(constants[name], width=98, sort_dicts=False)
        out.append('\n%s = %s\n' % (name, text))
    return ''.join(out).encode('ascii', 'backslashreplace').decode('ascii')


def write_block(constants, path):
    """Write the block beside its place and swap it in, so a failure keeps the old one."""
    text = render(constants)
    compile(text, str(path), 'exec')
    temp = Path(str(path) + '.tmp.%d' % os.getpid())
    try:
        with io.open(temp, 'w', encoding='ascii', newline='\r\n') as handle:
            handle.write(text)
        os.replace(str(temp), str(path))
    finally:
        if temp.exists():
            temp.unlink()


def counts_report(constants, tables, states, inputs):
    """The lines --counts prints."""
    lines = ['%-9s %6s %s  with a counted leaf' % (
        'kind', 'states', ' '.join('%4s' % family for family in FAMILIES))]
    for kind in KINDS:
        row = constants['COUNTS'][kind]
        lines.append('%-9s %6d %s  %d' % (
            kind, row['states'], ' '.join('%4d' % row[family] for family in FAMILIES),
            row['with_counted_leaf']))
    gear = {state for state, entry in states.items() if entry['kind'] == 'gear'}
    sublimation = {state for state, entry in states.items() if entry['kind'] != 'gear'}
    lines.append('gear states sharing a state with a sublimation: %d'
                 % len(gear & sublimation))
    return lines


def audit_report(constants, tables, states, leaves_of):
    """The lines --audit prints: cap conflicts, epic B and C, or criteria, stats keys."""
    out = []
    for state, entry in sorted(states.items()):
        if entry['kind'] == 'normal' and len(set(entry['caps'].values())) > 1:
            out.append('cap conflict %d %s: %s -> %d' % (
                state, entry['name'], entry['caps'], entry['cap']))
    for family in 'BC':
        found = [state for state, entry in sorted(states.items())
                 if entry['kind'] == 'epic' and entry['family'] == family]
        out.append('epic %s: %s' % (family, ' '.join(map(str, found))))
        leaves = [state for state, entry in sorted(states.items())
                  if entry['kind'] == 'epic' and entry['family'] != family
                  and any(leaf.family == family for leaf in leaves_of[('state', state)])]
        out.append('epic %s leaves under another primary family: %s' % (
            family, ' '.join(map(str, leaves))))
    wanted = turned = 0
    for leaves in leaves_of.values():
        for leaf in leaves:
            found = analyse(leaf.criteria)
            if leaf.key and found.has_or:
                wanted += 1
                if set(leaf.triggers) <= {START_OF_COMBAT} and found.names <= BUILD_CALLS:
                    turned += 1
    out.append('keyed leaves with an or criterion: %d, of which %d would be A to C '
               'without the or rule' % (wanted, turned))
    stats = {name.lower() for name in WAKFU_STATS}
    for kind in KINDS:
        entries = (constants['PASSIVES'].values() if kind == 'passives'
                   else [entry for entry in states.values() if entry['kind'] == kind])
        found = 0
        for entry in entries:
            keys = {line[1] for line in entry['lines']} | {
                conv[1] for conv in entry['conversions']} | {
                conv[0] for conv in entry['conversions']}
            if keys & stats:
                found += 1
        out.append('%-9s states with a counted leaf on a stats table key: %d' % (kind, found))
    return out


def tree_lines(tables, effect_id, indent, path=()):
    effect = tables.effects.get(effect_id)
    if effect is None or effect_id in path:
        return []
    key, sign = tables.naming.leaf_key(effect) \
        if effect['action_id'] not in STRUCTURE_ACTIONS + (CONVERSION,) else (None, '')
    named = key if isinstance(sign, int) else None
    triggers = ' '.join('%s%d' % pair for pair in trigger_pairs(effect))
    text = ' '.join((effect.get('criterion') or '').split())
    label = '%s%d a%d %s %s%s%s' % (
        ' ' * indent, effect_id, effect['action_id'], named or '',
        [number(value) for value in effect['params'][:2]],
        (' trig[%s]' % triggers) if triggers else '', (' if %s' % text) if text else '')
    lines = [label]
    if effect['action_id'] == APPLY_STATE and effect['params']:
        inner = int(effect['params'][0])
        lines[0] += ' -> state %d' % inner
        for root in tables.states.get(inner, {}).get('effect_ids', ()):
            lines.extend(tree_lines(tables, root, indent + 2, path + (effect_id,)))
    for member in tables.groups.get(effect_id, ()):
        lines.extend(tree_lines(tables, member, indent + 2, path + (effect_id,)))
    return lines


def show(constants, tables, ident, passive):
    """The lines --show prints for one state or passive."""
    table = constants['PASSIVES'] if passive else constants['STATES']
    if ident not in table:
        raise GeneratorError('%d is not a %s of the block' % (ident, 'passive' if passive
                                                              else 'state'))
    entry = table[ident]
    out = ['%s %d %s: family %s' % ('passive' if passive else 'state', ident, entry['name'],
                                    entry['family'])]
    if passive:
        out.append('breed %d unlock %d' % (entry['breed'], entry['unlock']))
    else:
        out.append('cap %s from %s' % (entry['cap'], entry['caps']))
        text = tables.state_texts.get(str(ident))
        if text:
            out.append('text: %s' % ' '.join(text.split())[:200])
    roots = (tables.spells[ident]['effect_ids'] if passive
             else tables.states.get(ident, {}).get('effect_ids', ()))
    out.append('tree:')
    for root in roots:
        out.extend(tree_lines(tables, root, 2))
    out.append('lines: %s' % (entry['lines'],))
    out.append('conditions: %s' % (entry['conditions'],))
    out.append('conversions: %s' % (entry['conversions'],))
    out.append('uncounted: %s' % (entry['uncounted'],))
    if not passive:
        for item, (state, level, kind, pattern) in constants['SUBLIMATIONS'].items():
            if state == ident:
                out.append('sublimation item %d level %d %s %s' % (item, level, kind, pattern))
        for item, pairs in constants['GEAR_STATES'].items():
            for state, level in pairs:
                if state == ident:
                    out.append('gear item %d level %d' % (item, level))
        if ident in constants['CHANGED_BY_NOTES']:
            out.append('changed by notes: %s' % (constants['CHANGED_BY_NOTES'][ident],))
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--client', default=str(CLIENT_DIR))
    parser.add_argument('--raw', default=str(RAW_DIR))
    parser.add_argument('--out', default=str(BLOCK))
    parser.add_argument('--show', type=int, metavar='ID',
                        help='print the tree, family, cap and text of a state')
    parser.add_argument('--passive', action='store_true', help='--show reads a passive spell')
    parser.add_argument('--audit', action='store_true', help='print the review lists')
    parser.add_argument('--counts', action='store_true', help='print the family table')
    args = parser.parse_args(argv)
    try:
        inputs = load_inputs(args.client, args.raw)
        constants, tables, states, _leaves = build(inputs)
        if args.show is not None:
            print('\n'.join(show(constants, tables, args.show, args.passive)))
            return 0
        if args.audit:
            print(chr(10).join(audit_report(constants, tables, states, _leaves)))
            return 0
        if args.counts:
            print('\n'.join(counts_report(constants, tables, states, inputs)))
            return 0
        write_block(constants, Path(args.out))
    except (GeneratorError, OSError, ValueError, KeyError) as error:
        print('the special items block could not be written: %s' % error)
        return 1
    print('wrote %s' % args.out)
    for kind in KINDS:
        row = constants['COUNTS'][kind]
        print('   %-9s %4d' % (kind, row['states']))
    return 0


if __name__ == '__main__':
    sys.exit(main())
