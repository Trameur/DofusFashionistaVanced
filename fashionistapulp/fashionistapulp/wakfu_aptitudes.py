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

"""Wakfu aptitudes and set bonuses: what the client's effect trees give a build."""

import collections
import re

from .wakfu_criteria import (And, Call, Compare, Const, CriteriaError, Hidden, Not, Or,
                             parse)
from . import wakfu_runes
from .wakfu_db import effect_value
from .wakfu_value_rules import RULES

SOLVE = 'solve'

# Names whose value only a fight settles: nothing below them counts
FIGHT_TIME = frozenset((
    'GetTeamId', 'GetTriggeringEffectTarget', 'GetTriggeringEffectCaster',
    'IsTriggeredByEffectWithREP'))
FIGHT = 'fight_time'

# Actions that carry no characteristic, and why they count nothing
NOT_A_STAT = {
    330: 'runs the effects of its group',
    400: 'never counts',
    304: 'applies a state, whose effects are walked',
    999: 'recomputes its level in the fight',
    1047: 'recomputes its level from the fight',
    430: 'a trigger, not a stat line',
    1093: 'a state effect with no characteristic',
}

# An untagged action a person reviewed, and the characteristic it changes
REVIEWED_UNTAGGED = {986: 'HP_PERCENT'}

# Their subtree counts nothing, and the walk says so
SUBTREE_DROPPED = (999, 1047)
# Leaves that count nothing and are reported
NOTED = (430, 1093)

# Actions 39 and 40 pass the characteristic in params[4]
CHARACTERISTIC_IN_PARAM = {39: 1, 40: -1}
CHARACTERISTIC_BY_ID = {120: 'ARMOR_GIVEN_PERCENT', 121: 'ARMOR_RECEIVED_PERCENT'}
TEMPLATE_ALIASES = {'ARMOR_GIVEN': 'ARMOR_GIVEN_PERCENT',
                    'ARMOR_RECEIVED': 'ARMOR_RECEIVED_PERCENT'}

_CALL_NAME = re.compile(r'([A-Za-z_][A-Za-z0-9_]*)\s*\(')
_CHARAC = re.compile(r'\[#charac ([A-Z_]+)\]')

Line = collections.namedtuple('Line', 'key value effect')
Walked = collections.namedtuple('Walked', 'lines notes')
# abilities {id: (category, cap, [(key, per point)], [notes])},
# tiers {(set, pieces): [(key, value)]}, members {set: [[item ids of one title]]}
Table = collections.namedtuple('Table', 'abilities tiers members')

_OPS = {'==': lambda a, b: a == b, '!=': lambda a, b: a != b,
        '<': lambda a, b: a < b, '>': lambda a, b: a > b,
        '<=': lambda a, b: a <= b, '>=': lambda a, b: a >= b}


def budgets(structure, level):
    """{category: points the level unlocks}."""
    return {category: sum(1 for unlock in unlocks if unlock <= level)
            for category, unlocks in structure.aptitude_categories.items()}


def caps(structure, level):
    """{ability: most points it takes}, its own cap or else its category budget."""
    budget = budgets(structure, level)
    return {ident: min(ddl, budget[category]) if ddl else budget[category]
            for ident, (category, ddl) in structure.aptitude_abilities.items()
            if category in budget}


def _names(text):
    return set(_CALL_NAME.findall(text))


def _history(node):
    if isinstance(node, Compare):
        return node.call.name == 'GetInstanceId'
    if isinstance(node, Call):
        return node.name == 'GetInstanceId'
    if isinstance(node, (Not, Hidden)):
        return _history(node.child)
    if isinstance(node, (And, Or)):
        return all(_history(child) for child in node.children)
    return False


def _hp_literals(node, found):
    if isinstance(node, Compare):
        if node.call.name == 'GetCharac':
            found.append(node.value)
    elif isinstance(node, (Not, Hidden)):
        _hp_literals(node.child, found)
    elif isinstance(node, (And, Or)):
        for child in node.children:
            _hp_literals(child, found)
    return found


def _evaluate(node, level, battleground, hp):
    if _history(node):
        return True
    if isinstance(node, Const):
        return node.value
    if isinstance(node, Hidden):
        return _evaluate(node.child, level, battleground, hp)
    if isinstance(node, Not):
        return not _evaluate(node.child, level, battleground, hp)
    if isinstance(node, And):
        return all(_evaluate(child, level, battleground, hp) for child in node.children)
    if isinstance(node, Or):
        return any(_evaluate(child, level, battleground, hp) for child in node.children)
    if isinstance(node, Compare):
        name = node.call.name
        if name == 'GetLevel':
            return _OPS[node.op](level, node.value)
        if name == 'GetCharac' and node.call.args[:1] == ('HP',):
            return _OPS[node.op](hp, node.value)
        raise CriteriaError('%s cannot be compared in an effect' % name)
    if isinstance(node, Call):
        if node.name == 'IsBattleground':
            return battleground
        if node.name in ('HasEffectWithActionId', 'IsSummon'):
            return False
        raise CriteriaError('%s cannot be evaluated in an effect' % node.name)
    raise CriteriaError('cannot evaluate %r' % (node,))


def criterion_holds(text, level, battleground, hp_bound):
    """True, False, or FIGHT when the text names something only a fight settles."""
    text = (text or '').strip()
    if not text:
        return True
    if _names(text) & FIGHT_TIME:
        return FIGHT
    tree = parse(text)
    samples = {0, hp_bound}
    for value in _hp_literals(tree, []):
        samples.update(near for near in (value - 1, value, value + 1)
                       if 0 <= near <= hp_bound)
    outcomes = {_evaluate(tree, level, battleground, hp) for hp in samples}
    if len(outcomes) > 1:
        raise CriteriaError('%r depends on the HP of the build' % text)
    return outcomes.pop()


def _characteristic(structure, effect):
    """(key, sign) when the effect names a characteristic, else (None, reason)."""
    action = effect.action
    sign = CHARACTERISTIC_IN_PARAM.get(action)
    if sign is not None:
        named = int(effect.params[4]) if len(effect.params) > 4 else None
        key = CHARACTERISTIC_BY_ID.get(named)
        if key is None:
            return None, 'characteristic %s is not named' % named
        return key, sign
    text = structure.aptitude_action_texts.get(action) or ''
    found = _CHARAC.search(text)
    if found:
        malus = text.lstrip().startswith('-') or '] -[#1]' in text
        return TEMPLATE_ALIASES.get(found.group(1), found.group(1)), -1 if malus else 1
    if action in REVIEWED_UNTAGGED:
        return REVIEWED_UNTAGGED[action], 1
    if action in NOT_A_STAT:
        return None, NOT_A_STAT[action]
    raise ValueError('action %d of effect %d has no characteristic and no review'
                     % (action, effect.id))


def untagged_actions(structure):
    """Actions among the raw effects whose template names no characteristic."""
    return {effect.action for effect in structure.aptitude_effects.values()
            if effect.action not in CHARACTERISTIC_IN_PARAM
            and not _CHARAC.search(structure.aptitude_action_texts.get(effect.action) or '')}


def _number(value):
    return int(value) if value == int(value) else value


def _ability_roots(structure, ability):
    return sorted(effect.id for effect in structure.aptitude_effects.values()
                  if effect.container_type == 'ABILITY' and effect.container == ability)


def walk(structure, roots, points_or_level, level, battleground, *, criteria=True):
    """The lines and notes of the effect trees under `roots`, in walk order.

    With criteria=False every criterion but a fight-time one is taken as holding.
    """
    lines = []
    notes = []
    bound = hp_bound(structure, level) if criteria else 0

    def visit(effect_id):
        effect = structure.aptitude_effects[effect_id]
        text = effect.criterion or ''
        if criteria:
            verdict = criterion_holds(text, level, battleground, bound)
            if verdict == FIGHT:
                notes.append('effect %d: a criterion only a fight settles' % effect_id)
                return
            if not verdict:
                return
        elif _names(text) & FIGHT_TIME:
            return
        action = effect.action
        if action in SUBTREE_DROPPED:
            notes.append('action %d: %s' % (action, NOT_A_STAT[action]))
            return
        if action == 400:
            return
        if action == 304:
            for state_root in structure.aptitude_state_roots.get(int(effect.params[0]), ()):
                visit(state_root)
        elif action != 330:
            key, sign = _characteristic(structure, effect)
            if key is not None:
                value = effect_value(effect.params, 0, points_or_level)
                lines.append(Line(key, _number(sign * value), effect_id))
            elif action in NOTED or action in CHARACTERISTIC_IN_PARAM:
                notes.append('action %d: %s' % (action, sign))
        for member in structure.aptitude_effect_groups.get(effect_id, ()):
            visit(member)

    for root in roots:
        visit(root)
    return Walked(lines, notes)


def hp_bound(structure, level):
    """The most HP a build of this level can reach, gear and aptitude lines counted."""
    cache = structure.__dict__.setdefault('_aptitude_hp_bounds', {})
    if level not in cache:
        cache[level] = _hp_bound(structure, level)
    return cache[level]


def _hp_bound(structure, level):
    budget = budgets(structure, level)
    raw = {}
    percent = {}
    for ident, (category, _ddl) in structure.aptitude_abilities.items():
        walked = walk(structure, _ability_roots(structure, ident), 1, level, False,
                      criteria=False)
        for line in walked.lines:
            if line.key == 'HP':
                raw[category] = max(raw.get(category, 0), line.value)
            elif line.key == 'HP_PERCENT':
                percent[category] = max(percent.get(category, 0), line.value)
    hp_stat = structure.get_stat_by_key('hp')
    positions = collections.defaultdict(list)
    for type_id, position in structure.get_type_positions():
        positions[type_id].append(position)
    best = {}
    sockets = {}
    for item in structure.items_dict.values():
        if item.removed or item.level > level:
            continue
        for position in positions[item.type]:
            sockets[position] = max(sockets.get(position, 0), wakfu_runes.sockets_of(item))
        for stat_id, value in item.stats:
            if hp_stat is not None and stat_id == hp_stat.id:
                for position in positions[item.type]:
                    best[position] = max(best.get(position, 0), value)
    life = (RULES['base_life'].value + RULES['life_per_level'].value * level
            + sum(best.values()) + sum(raw[c] * budget[c] for c in raw)
            + _rune_life(structure, level, sockets))
    points = sum(percent[c] * budget[c] for c in percent)
    return int(life + life * points // 100)


def _rune_life(structure, level, sockets):
    """The most Life the runes can add: every socket of a position holds the best Life rune."""
    life = 0
    for position, count in sockets.items():
        best = 0
        for rune in wakfu_runes.valued(structure).values():
            stat = structure.get_stat_by_id(rune.stat)
            if stat is not None and stat.key == 'hp':
                tier = wakfu_runes.allowed_tier(rune, level)
                if tier:
                    best = max(best, wakfu_runes.value(rune, tier, position in rune.doubles))
        life += count * best
    return life


def _per_point(structure, walked, ident):
    totals = collections.OrderedDict()
    for line in walked.lines:
        params = structure.aptitude_effects[line.effect].params
        if params[0] != 0 or params[1] != int(params[1]):
            raise ValueError('ability %d line %d is not a whole number per point'
                             % (ident, line.effect))
        key = line.key.lower()
        totals[key] = totals.get(key, 0) + line.value
    return list(totals.items())


def titles(structure, set_id):
    """The member ids of a set, one list per title, its rarities together."""
    from .wakfu_model import same_item
    groups = collections.OrderedDict()
    for item_id in structure.aptitude_set_members.get(set_id, ()):
        item = structure.items_dict.get(item_id)
        if item is not None:
            groups.setdefault(same_item(item), []).append(item_id)
    return [sorted(ids) for ids in groups.values()]


def table(structure, level, battleground):
    """What the client's trees give at this level, cached per (level, battleground)."""
    cache = structure.__dict__.setdefault('_aptitude_tables', {})
    key = (level, bool(battleground))
    if key not in cache:
        cache[key] = _table(structure, level, bool(battleground))
    return cache[key]


def tiers_reached(table, item_ids):
    """[(set, pieces)] of the tiers whose set has that many titles among the worn ids."""
    worn = set(item_ids)
    return [(item_set, pieces) for item_set, pieces in sorted(table.tiers)
            if sum(1 for title in table.members[item_set] if worn.intersection(title))
            >= pieces]


def _table(structure, level, battleground):
    limits = caps(structure, level)
    abilities = {}
    for ident, (category, _ddl) in sorted(structure.aptitude_abilities.items()):
        if ident in limits:
            walked = walk(structure, _ability_roots(structure, ident), 1, level,
                          battleground)
            abilities[ident] = (category, limits[ident],
                                _per_point(structure, walked, ident), walked.notes)
    tiers = {}
    members = {}
    for item_set, pieces, effect_id in structure.aptitude_set_bonuses:
        walked = walk(structure, [effect_id], level, level, battleground)
        lines = [(line.key.lower(), line.value) for line in walked.lines]
        worn_by = titles(structure, item_set)
        if lines and worn_by:
            tiers.setdefault((item_set, pieces), []).extend(lines)
            members[item_set] = worn_by
    return Table(abilities, tiers, members)
