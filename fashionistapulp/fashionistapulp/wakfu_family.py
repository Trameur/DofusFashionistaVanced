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

"""What a spell does besides damage, read from the client spell table.

The families are heal, armor, placement (push, pull, teleport, switch) and hindrance
(AP, MP, range and WP removal). A row is read when its criteria use only the functions
of POLICY and every effect group above it is the plain group; any other row is
skipped, and the skip names the function. A family turn never counts what it cannot
read.
"""

import collections
import operator
import re

from . import wakfu_criteria
from .wakfu_value_rules import RULES

#: The client action that runs the effects of its group
GROUP_ACTION = 330

#: Family of the turn -> the families of the client rows it reads
CLIENT_FAMILIES = {
    'heal': ('heal',),
    'armor': ('armor',),
    'placement': ('push', 'teleport'),
    'hindrance': ('removal',),
}
FAMILIES = tuple(CLIENT_FAMILIES)

#: Who the rows of a family are aimed at: the team a criterion on the target is read against
AIM = {'heal': 'ally', 'armor': 'ally', 'placement': 'any', 'hindrance': 'enemy'}

#: Resources a removal row takes, by client action
REMOVED = {55: 'ap', 56: 'ap', 48: 'mp', 57: 'mp', 161: 'range', 194: 'wp', 192: 'wp'}

#: Selectors of a heal row's third parameter pair that read the share of maximum health
PERCENT_OF_MAXIMUM = (1, 4)

TRUE, AIMED, DISTANCE, DECK, STATE, FALSE, BREED, TEAM = (
    'true', 'aimed', 'distance', 'deck', 'state', 'false', 'breed', 'team')

#: Criterion functions a family turn reads, and how
POLICY = {
    'IsEnemy': AIMED, 'IsEnnemy': AIMED, 'HasLineOfSight': TRUE, 'IsTargetCellFree': TRUE,
    'GetDistanceBetweenCasterAndTarget': DISTANCE,
    'IsSpellInDeck': DECK,
    'HasState': STATE, 'HasStateFromUser': STATE, 'GetStateLevel': STATE,
    'HasStateFromLevel': STATE,
    'IsOwnSummon': FALSE, 'IsSummon': FALSE, 'IsCarried': FALSE, 'IsCarrying': FALSE,
    'IsBreedId': BREED, 'GetTeamId': TEAM,
}

SAME_TEAM, OTHER_TEAM = 'IsSameTeam', 'IsOtherTeam'
READ = frozenset(POLICY) | {SAME_TEAM, OTHER_TEAM, 'True', 'False'}
UNPARSED = 'an expression the criteria reader does not parse'

# The caster and the target in one comparison share the team the family is aimed at
TEAM_COMPARISON = re.compile(
    r'GetTeamId\("\w+"\)\s*(==|!=)\s*GetTeamId\("\w+"\)')
CALL_NAME = re.compile(r'([A-Za-z_]\w*)\(')

_OPERATORS = {'==': operator.eq, '!=': operator.ne, '<': operator.lt, '>': operator.gt,
              '<=': operator.le, '>=': operator.ge}


#: Shared by every row that changes no cost; never changed
NO_COST = collections.Counter()


class FamilyRow(collections.namedtuple(
        'FamilyRow', 'id action element base critical critical_read trees conditions '
                     'unless mode hits reach cost percent area recipients',
        defaults=((), frozenset(), frozenset(), 'hit', 1, None, NO_COST, False, False,
                  None))):
    """One row of a family at one level.

    id: the client effect id; base and critical: the value of the row at the level
    (a heal row that is a share of life holds the share, percent True); trees: the
    parsed criteria; conditions, unless, mode, hits, reach, cost: the structure the
    encyclopedia text gives a heal row, as for a damage row; recipients: the sides an
    armor row reaches (a frozenset over caster, possibly_caster, allies, enemies), None
    when not read.
    """


class FamilySpell(collections.namedtuple(
        'FamilySpell', 'id name breed branch ap wp mp low high unlock level rows skipped')):
    """A castable spell with rows of one family; skipped: (row id, reason, functions)."""


Context = collections.namedtuple('Context', 'aim distance states deck breed')


def rule(name):
    return RULES[name].value


def prepare(criterion):
    """(tree or None, names the policy does not read) of one client criterion."""
    text = TEAM_COMPARISON.sub(
        lambda found: SAME_TEAM + '()' if found.group(1) == '==' else OTHER_TEAM + '()',
        criterion.replace('<>', '!='))
    try:
        tree = wakfu_criteria.parse(text)
    except wakfu_criteria.CriteriaError:
        named = {name for name in CALL_NAME.findall(text) if name not in READ}
        return None, named or {UNPARSED}
    return tree, wakfu_criteria.functions(tree) - READ


def _number(call, spell, context):
    name, args = call.name, call.args
    if name in (SAME_TEAM, OTHER_TEAM):
        wanted = ('ally', 'any') if name == SAME_TEAM else ('enemy', 'any')
        return context.aim in wanted
    if name == 'True' or name == 'False':
        return name == 'True'
    how = POLICY[name]
    if how == TRUE:
        return True
    if how == AIMED:
        return context.aim in ('enemy', 'any')
    if how == DISTANCE:
        return context.distance
    if how == DECK:
        return args[0] in context.deck
    if how == STATE:
        level = context.states.get(args[0], 0)
        if name == 'HasStateFromLevel' and len(args) > 1:
            return level >= args[1]
        return level if name == 'GetStateLevel' else level > 0
    if how == BREED:
        return context.breed == args[0]
    if how == TEAM:
        return 0
    return False


def _resolved(node, spell, context):
    """The tree with every atom replaced by the constant the policy gives it."""
    if isinstance(node, (wakfu_criteria.And, wakfu_criteria.Or)):
        return type(node)(tuple(_resolved(child, spell, context) for child in node.children))
    if isinstance(node, (wakfu_criteria.Not, wakfu_criteria.Hidden)):
        return type(node)(_resolved(node.child, spell, context))
    if isinstance(node, wakfu_criteria.Const):
        return node
    if isinstance(node, wakfu_criteria.Compare):
        return wakfu_criteria.Const(bool(_OPERATORS[node.op](
            _number(node.call, spell, context), node.value)))
    return wakfu_criteria.Const(bool(_number(node, spell, context)))


def row_holds(row, spell, context):
    """Whether every criterion of the row holds in the context."""
    return all(wakfu_criteria.evaluate(_resolved(tree, spell, context), None)
               for tree in row.trees)


def distance(spell, reach):
    """Cells between caster and target the role's reach puts a cast at."""
    if not spell.high:
        return 0
    return max(spell.low, 1) if reach == 'melee' else spell.high


def removal_share(willpower, target=None):
    """Share of a removal that lands: half at equal willpower, one more 1/200 per point."""
    target = rule('target_willpower') if target is None else target
    asked = rule('removal_share_at_equal_willpower')
    return min(max(asked['at_equal'] + (willpower - target) * asked['per_point'], 0.0), 1.0)


def self_aimed(spell):
    """A spell that can be cast only on its caster has range 0."""
    return not spell.high
