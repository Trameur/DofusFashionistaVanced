# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

"""Wakfu equip conditions: read the client's text, derive solver rows, evaluate on a set."""

import collections
import dataclasses
import operator
import re

EVALUATED, HISTORY, STATE, IMPOSSIBLE = 'evaluated', 'history', 'state', 'impossible'

# Every function and literal the client's EQUIP texts use, in exactly one class
FUNCTIONS = {
    'HasAnotherSameEquipment': EVALUATED, 'GetCharac': EVALUATED,
    'GetCharacMax': EVALUATED, 'GetCharacteristicMax': EVALUATED,
    'IsBreed': EVALUATED, 'HasEquipmentId': EVALUATED, 'GetLevel': EVALUATED,
    'GetRealLevel': EVALUATED, 'GetEquipment': EVALUATED, 'True': EVALUATED,
    'GetCraftLevel': HISTORY, 'GetInstanceId': HISTORY, 'IsDay': HISTORY,
    'HasCraft': HISTORY, 'IsAchievementComplete': HISTORY,
    'GetWakfuGauge': STATE, 'GetStasisGauge': STATE, 'GetCrimeScore': STATE,
    'GetCompanyRank': STATE, 'GetNationId': STATE, 'HasPvpRank': STATE,
    'GetGuildLevel': STATE,
    'IsAdmin': IMPOSSIBLE, 'False': IMPOSSIBLE,
}

STAT_FUNCTIONS = ('GetCharac', 'GetCharacMax', 'GetCharacteristicMax')
LEVEL_FUNCTIONS = ('GetLevel', 'GetRealLevel')

# Function -> (label key, label key under not); state functions use STATE_OPTIONS
LABEL_KEYS = {
    'GetCraftLevel': ('critere.craftLevel', None),
    'HasCraft': ('critere.hasCraft', None),
    'GetInstanceId': ('critere.getInstanceId', 'critere.notGetInstanceId'),
    'IsDay': ('critere.isDay', 'critere.notIsDay'),
    'IsAchievementComplete': ('critere.isAchievementComplete', None),
    'False': ('critere.false', None),
}

# What each kind of a client record says about wearing it (client enum fnG)
REVIEWED_KINDS = {
    'EQUIP': 'enforced',
    'USE': 'does not bear on wearing',
    'USE_IN_FIGHT': 'does not bear on wearing',
    'EXCHANGE': 'does not bear on wearing',
    'CRAFT': 'does not bear on wearing',
    'PICK_UP': 'does not bear on wearing',
    'DROP': 'does not bear on wearing',
    'DELETE': 'does not bear on wearing',
}

# Item properties, named by the client enum foe
REVIEWED_PROPERTIES = {
    1: 'TREASURE', 4: 'NO_ENU_DROP', 7: 'SHOP_ITEM', 8: 'EXCLUSIVE_EQUIPMENT_ITEM',
    9: 'CREATE_EVENT_ON_DROP', 12: 'EXCLUSIVE_EQUIPMENT_ITEM_2',
    13: 'NOT_RECYCLABLE', 19: 'EPIC_GEMMABLE', 20: 'RELIC_GEMMABLE',
    23: 'EXCLUDE_FROM_LISTS', 24: 'EXCLUDE_FROM_ENCYCLOPEDIA',
}


class CriteriaError(ValueError):
    pass


Call = collections.namedtuple('Call', 'name args')
Compare = collections.namedtuple('Compare', 'call op value')
Not = collections.namedtuple('Not', 'child')
And = collections.namedtuple('And', 'children')
Or = collections.namedtuple('Or', 'children')
Const = collections.namedtuple('Const', 'value')
Hidden = collections.namedtuple('Hidden', 'child')

_TOKEN = re.compile(
    r'\s*(?:(?P<num>-?\d+)|(?P<str>"[^"]*")|'
    r'(?P<op>==|!=|<=|>=|<|>|&&|\|\||[(),#])|(?P<word>[A-Za-z_][A-Za-z0-9_]*))')

_COMPARE_OPS = ('==', '!=', '<', '>', '<=', '>=')
_FLIP = {'==': '==', '!=': '!=', '<': '>', '>': '<', '<=': '>=', '>=': '<='}
_OPERATORS = {'==': operator.eq, '!=': operator.ne, '<': operator.lt,
              '>': operator.gt, '<=': operator.le, '>=': operator.ge}


def classify(name):
    if name not in FUNCTIONS:
        raise CriteriaError('unknown function %r' % (name,))
    return FUNCTIONS[name]


def _tokens(text):
    out = []
    position = 0
    text = text.strip()
    while position < len(text):
        found = _TOKEN.match(text, position)
        if not found or found.end() == position:
            raise CriteriaError('cannot read %r' % text[position:position + 12])
        position = found.end()
        kind = found.lastgroup
        value = found.group(kind)
        if kind == 'word' and value in ('and', 'or', 'not'):
            kind = 'op'
        out.append((kind, value))
    return out


class _Parser:
    def __init__(self, text):
        self.tokens = _tokens(text)
        self.index = 0

    def peek(self):
        if self.index < len(self.tokens):
            return self.tokens[self.index]
        return None, None

    def take(self, value=None):
        token = self.peek()
        if value is not None and token[1] != value:
            raise CriteriaError('expected %s, found %s' % (value, token[1]))
        if token[0] is None:
            raise CriteriaError('the text ends too early')
        self.index += 1
        return token

    def parse(self):
        node = self.disjunction()
        if self.index != len(self.tokens):
            raise CriteriaError('left over %r' % (self.tokens[self.index:],))
        return node

    def disjunction(self):
        parts = [self.conjunction()]
        while self.peek()[1] in ('or', '||'):
            self.take()
            parts.append(self.conjunction())
        return parts[0] if len(parts) == 1 else Or(tuple(parts))

    def conjunction(self):
        parts = [self.negation()]
        while self.peek()[1] in ('and', '&&'):
            self.take()
            parts.append(self.negation())
        return parts[0] if len(parts) == 1 else And(tuple(parts))

    def negation(self):
        if self.peek() == ('op', 'not'):
            self.take()
            return Not(self.negation())
        return self.comparison()

    def comparison(self):
        left = self.atom()
        if self.peek()[1] in _COMPARE_OPS and self.peek()[0] == 'op':
            op = self.take()[1]
            right = self.atom()
            if isinstance(left, Call) and not isinstance(right, Call):
                return Compare(left, op, self._literal(right))
            if isinstance(right, Call) and not isinstance(left, Call):
                return Compare(right, _FLIP[op], self._literal(left))
            raise CriteriaError('a comparison needs one call and one literal')
        return left

    @staticmethod
    def _literal(node):
        if isinstance(node, (int, str)) and not isinstance(node, bool):
            return node
        raise CriteriaError('a comparison needs a literal, found %r' % (node,))

    def atom(self):
        kind, value = self.peek()
        if value == '(' and kind == 'op':
            self.take()
            node = self.disjunction()
            self.take(')')
            return node
        if value == '#' and kind == 'op':
            self.take()
            node = self.disjunction()
            self.take('#')
            return Hidden(node)
        if kind == 'num':
            self.take()
            return int(value)
        if kind == 'str':
            self.take()
            return value[1:-1]
        if kind == 'word' and value in ('True', 'False', 'true', 'false'):
            self.take()
            return Const(value.lower() == 'true')
        if kind == 'word':
            self.take()
            self.take('(')
            args = []
            if self.peek()[1] != ')':
                args.append(self._argument())
                while self.peek()[1] == ',':
                    self.take()
                    args.append(self._argument())
            self.take(')')
            return Call(value, tuple(args))
        raise CriteriaError('unexpected %r' % (value,))

    def _argument(self):
        node = self.atom()
        if isinstance(node, (int, str)):
            return node
        raise CriteriaError('arguments are literals, found %r' % (node,))


def parse(text):
    """The tree of one client criterion text; CriteriaError on anything else."""
    if text is None or not str(text).strip():
        raise CriteriaError('an empty criterion')
    return _Parser(str(text)).parse()


def _walk(node):
    yield node
    if isinstance(node, (And, Or)):
        for child in node.children:
            yield from _walk(child)
    elif isinstance(node, (Not, Hidden)):
        yield from _walk(node.child)
    elif isinstance(node, Compare):
        yield node.call


def functions(node):
    """Names of every call in a tree, plus True or False for a literal."""
    names = set()
    for one in _walk(node):
        if isinstance(one, Call):
            names.add(one.name)
        elif isinstance(one, Const):
            names.add('True' if one.value else 'False')
    return names


def is_history(node):
    """True when every leaf of the subtree is a history atom."""
    if isinstance(node, Call):
        return classify(node.name) == HISTORY
    if isinstance(node, Compare):
        return classify(node.call.name) == HISTORY
    if isinstance(node, (Not, Hidden)):
        return is_history(node.child)
    if isinstance(node, (And, Or)):
        return all(is_history(child) for child in node.children)
    return False


StateOption = collections.namedtuple(
    'StateOption', 'name functions start low high label_key flag')

STATE_OPTIONS = (
    StateOption('wakfu_gauge', ('GetWakfuGauge',), 0, 0, 100,
                'critere.getWakfuGauge', '--wakfu-gauge'),
    StateOption('stasis_gauge', ('GetStasisGauge',), 0, 0, 100,
                'critere.getStasisGauge', '--stasis-gauge'),
    StateOption('nation', ('GetNationId',), 0, None, None,
                'critere.getNationId', '--nation'),
    StateOption('citizenship', ('GetCrimeScore',), 0, None, None,
                'critere.getCrimeScore', '--citizenship'),
    StateOption('company_rank', ('GetCompanyRank',), 0, 0, None,
                'critere.getCompanyRank', '--company-rank'),
    StateOption('pvp_rank', ('HasPvpRank',), 0, 0, None,
                'critere.hasPvpRank', '--pvp-rank'),
    StateOption('guild_level', ('GetGuildLevel',), 0, 0, None,
                'critere.guildLevel', '--guild-level'),
)

_OPTION_OF_FUNCTION = {name: option for option in STATE_OPTIONS
                       for name in option.functions}
_OPTION_BY_NAME = {option.name: option for option in STATE_OPTIONS}

StateCondition = collections.namedtuple('StateCondition',
                                        'option nation operator value')


@dataclasses.dataclass(frozen=True)
class PlayerState:
    wakfu_gauge: int = 0
    stasis_gauge: int = 0
    nation: int = 0
    citizenship: tuple = ()
    company_rank: int = 0
    pvp_rank: int = 0
    guild_level: int = 0


def start_state():
    return PlayerState(**{option.name: (() if option.name == 'citizenship'
                                        else option.start)
                          for option in STATE_OPTIONS})


def _whole(name, value):
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError('%s must be a whole number, got %r' % (name, value))
    return value


def player_state(structure=None, **given):
    """A PlayerState from named values; ValueError on a bad name or value."""
    state = {}
    for name, value in given.items():
        option = _OPTION_BY_NAME.get(name)
        if option is None:
            raise ValueError('%r is not a player state option, choose from %s' % (
                name, ', '.join(sorted(_OPTION_BY_NAME))))
        if name == 'citizenship':
            pairs = value.items() if hasattr(value, 'items') else value
            points = {}
            for nation, score in pairs:
                _whole('citizenship nation', nation)
                _whole('citizenship points', score)
                if nation == 0:
                    raise ValueError('citizenship is held toward a nation, not 0')
                points[nation] = score
            state[name] = tuple(sorted(points.items()))
            continue
        _whole(name, value)
        if option.low is not None and value < option.low:
            raise ValueError('%s is at least %d, got %d' % (name, option.low, value))
        if option.high is not None and value > option.high:
            raise ValueError('%s is at most %d, got %d' % (name, option.high, value))
        state[name] = value
    nations = tuple(structure.get_nation_ids()) if structure is not None else ()
    if nations:
        if state.get('nation', 0) != 0 and state['nation'] not in nations:
            raise ValueError('nation %r is not one of %s'
                             % (state['nation'], ', '.join(map(str, nations))))
        for nation, _score in state.get('citizenship', ()):
            if nation not in nations:
                raise ValueError('citizenship nation %r is not one of %s'
                                 % (nation, ', '.join(map(str, nations))))
    return PlayerState(**state)


def _citizenship(state, nation):
    start = _OPTION_BY_NAME['citizenship'].start
    if nation is None:
        # The call names no nation: the points held toward the own nation
        if not state.nation:
            return start
        nation = state.nation
    return dict(state.citizenship).get(nation, start)


def state_value(state, call):
    """The value a state function reads on a build's state; HasPvpRank gives a bool."""
    name = call.name
    if name == 'GetWakfuGauge':
        return state.wakfu_gauge
    if name == 'GetStasisGauge':
        return state.stasis_gauge
    if name == 'GetNationId':
        return state.nation
    if name == 'GetCrimeScore':
        return _citizenship(state, call.args[0] if call.args else None)
    if name == 'HasPvpRank':
        return state.pvp_rank >= call.args[0]
    if name == 'GetCompanyRank':
        return state.company_rank
    if name == 'GetGuildLevel':
        return state.guild_level
    raise CriteriaError('%r is not a state function' % (name,))


def _held(state, condition):
    if condition.option == 'citizenship':
        return _citizenship(state, condition.nation)
    return getattr(state, condition.option)


def state_holds(conditions, state):
    return all(_OPERATORS[condition.operator](_held(state, condition), condition.value)
               for condition in conditions)


def unlocking(conditions, state):
    """{option or (option, nation): bound} for each condition the state fails, else None."""
    out = {}
    for condition in conditions:
        if _OPERATORS[condition.operator](_held(state, condition), condition.value):
            continue
        key = ((condition.option, condition.nation)
               if condition.option == 'citizenship' else condition.option)
        out[key] = condition.value
    return out or None


def state_unlocks(items, state):
    """[(item id, unlocking)] of the items the state keeps out, highest level first."""
    out = []
    for item in items:
        conditions = getattr(item, 'state_conditions', ())
        needs = unlocking(conditions, state) if conditions else None
        if needs:
            out.append((item, needs))
    out.sort(key=lambda one: (-(one[0].level or 0), one[0].id))
    return [(item.id, needs) for item, needs in out]


Derived = collections.namedtuple(
    'Derived', 'unusable classes min_stats max_stats worn_with not_worn_with '
               'same_item min_level max_level state')


def _bound(table, key, value, keep):
    table[key] = keep(table[key], value) if key in table else value


def derive(tree, *, stat_keys, breed_names, item_ids):
    """The solver rows one text asks for; CriteriaError on a shape it refuses."""
    unusable = same_item = False
    classes = []
    min_stats, max_stats = {}, {}
    worn_with, not_worn_with, state = [], [], []
    levels = {'min': None, 'max': None}
    stat_keys, breed_names, item_ids = set(stat_keys), set(breed_names), set(item_ids)

    def raise_bound(table, key, value):
        _bound(table, key, value, max)

    def lower_bound(table, key, value):
        _bound(table, key, value, min)

    def bounds(op, value, low, high):
        if op == '>':
            low(value + 1)
        elif op == '>=':
            low(value)
        elif op == '<':
            high(value - 1)
        elif op == '<=':
            high(value)
        elif op == '==':
            low(value)
            high(value)
        else:
            raise CriteriaError('%s is not a bound' % op)

    def level_low(value):
        levels['min'] = value if levels['min'] is None else max(levels['min'], value)

    def level_high(value):
        levels['max'] = value if levels['max'] is None else min(levels['max'], value)

    def a_target(name, argument):
        if argument not in item_ids:
            raise CriteriaError('%s names item %r, which is not in the catalogue'
                                % (name, argument))
        return argument

    def conjunct(node):
        nonlocal unusable, same_item
        if is_history(node):
            return
        if isinstance(node, Const):
            unusable = unusable or not node.value
            return
        if isinstance(node, Hidden):
            raise CriteriaError('a hidden atom that is not a history atom')
        if isinstance(node, Or):
            raise CriteriaError('an or holding an atom that is not a history atom')
        if isinstance(node, And):
            for child in node.children:
                conjunct(child)
            return
        if isinstance(node, Not):
            inner = node.child
            if isinstance(inner, Call) and inner.name == 'HasEquipmentId':
                not_worn_with.append(a_target(inner.name, inner.args[0]))
            elif isinstance(inner, Call) and inner.name == 'HasAnotherSameEquipment':
                same_item = True
            else:
                raise CriteriaError('a not over %r' % (inner,))
            return
        if isinstance(node, Call):
            classify(node.name)
            if node.name == 'IsAdmin':
                unusable = True
            elif node.name == 'IsBreed':
                if classes:
                    raise CriteriaError('a second IsBreed')
                if node.args[0] not in breed_names:
                    raise CriteriaError('IsBreed names %r, not a breed' % (node.args[0],))
                classes.append(node.args[0])
            elif node.name == 'HasEquipmentId':
                worn_with.append(a_target(node.name, node.args[0]))
            elif node.name == 'HasPvpRank':
                state.append(StateCondition('pvp_rank', None, '>=', node.args[0]))
            else:
                raise CriteriaError('%s stands in a shape W2 refuses' % node.name)
            return
        if isinstance(node, Compare):
            call, op, value = node
            name = call.name
            if name in STAT_FUNCTIONS:
                if name == 'GetCharacteristicMax' and call.args[1:] != ('target',):
                    raise CriteriaError('%s needs "target" as its second argument' % name)
                if name != 'GetCharacteristicMax' and call.args[1:]:
                    raise CriteriaError('%s takes one argument' % name)
                key = str(call.args[0]).lower()
                if key not in stat_keys:
                    raise CriteriaError('%s names %r, not a stat' % (name, call.args[0]))
                if key == 'hp':
                    raise CriteriaError('an HP gate needs the level gain, not decoded')
                bounds(op, value,
                       lambda v: raise_bound(min_stats, key, v),
                       lambda v: lower_bound(max_stats, key, v))
            elif name in LEVEL_FUNCTIONS:
                bounds(op, value, level_low, level_high)
            elif name in _OPTION_OF_FUNCTION and name != 'HasPvpRank':
                option = _OPTION_OF_FUNCTION[name].name
                nation = call.args[0] if name == 'GetCrimeScore' and call.args else None
                if op == '!=':
                    raise CriteriaError('a state atom with !=')
                if op == '>':
                    state.append(StateCondition(option, nation, '>=', value + 1))
                elif op == '<':
                    state.append(StateCondition(option, nation, '<=', value - 1))
                else:
                    state.append(StateCondition(option, nation, op, value))
            else:
                raise CriteriaError('%s in a comparison is a shape W2 refuses' % name)
            return
        raise CriteriaError('cannot derive %r' % (node,))

    for node in (tree.children if isinstance(tree, And) else (tree,)):
        conjunct(node)
    return Derived(unusable, tuple(classes), min_stats, max_stats,
                   tuple(worn_with), tuple(not_worn_with), same_item,
                   levels['min'], levels['max'], tuple(state))


Env = collections.namedtuple('Env', 'level breed state totals piece_id other_ids')


def evaluate(tree, env):
    """Whether a text holds for a build; history atoms hold under either polarity."""
    if is_history(tree):
        return True
    if isinstance(tree, Const):
        return tree.value
    if isinstance(tree, Hidden):
        return evaluate(tree.child, env)
    if isinstance(tree, Not):
        return not evaluate(tree.child, env)
    if isinstance(tree, And):
        return all(evaluate(child, env) for child in tree.children)
    if isinstance(tree, Or):
        return any(evaluate(child, env) for child in tree.children)
    if isinstance(tree, Compare):
        call = tree.call
        if call.name in STAT_FUNCTIONS:
            have = env.totals.get(str(call.args[0]).lower(), 0)
        elif call.name in LEVEL_FUNCTIONS:
            have = env.level
        elif classify(call.name) == STATE:
            have = state_value(env.state, call)
        else:
            raise CriteriaError('%s cannot be compared' % call.name)
        return _OPERATORS[tree.op](have, tree.value)
    if isinstance(tree, Call):
        name = tree.name
        if name == 'HasAnotherSameEquipment':
            return env.piece_id in env.other_ids
        if name == 'IsBreed':
            return env.breed == tree.args[0]
        if name == 'HasEquipmentId':
            return tree.args[0] in env.other_ids
        if name == 'IsAdmin':
            return False
        if classify(name) == STATE:
            return bool(state_value(env.state, tree))
        raise CriteriaError('%s cannot be evaluated' % name)
    raise CriteriaError('cannot evaluate %r' % (tree,))


def failing_atoms(tree, env):
    """The false conjuncts of a top And, or the tree itself when it is false."""
    parts = tree.children if isinstance(tree, And) else (tree,)
    return [part for part in parts if not evaluate(part, env)]


def base_values(structure, class_id=None):
    """{stat key: (low, high)} a bare character starts with, from the breed table."""
    bases = structure.get_breed_base_values()
    if not bases:
        raise ValueError('the catalogue has no breed table')
    if class_id is not None:
        if class_id not in bases:
            raise ValueError('class %r is not a breed of the catalogue' % (class_id,))
        return {key: (value, value) for key, value in bases[class_id].items()}
    keys = {key for table in bases.values() for key in table}
    return {key: (min(table.get(key, 0) for table in bases.values()),
                  max(table.get(key, 0) for table in bases.values()))
            for key in keys}
