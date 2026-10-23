"""Aptitude and set bonus rows laid over the invented Wakfu items of the solver tests.

The invented database holds no aptitude table, so a test adds the raw rows
the client would give: an ability with a line per point, or an ability copied
from the real database, and a set with tiers. The solver then reads them the
way it reads the real ones.
"""

from django.test import SimpleTestCase

from fashionistapulp.wakfu_db import EffectRow
from fashionistapulp.wakfu_model import SOLVE

from chardata.tests_wakfu_solve_obeys_every_rule_on_invented_items import (
    ALPHA, LEVEL, InventedItemsCase)

ACTION_BASE = 7000
BRACKET_80 = 'IsBattleground() and GetLevel("target") <= 80'
BRACKET_81_110 = ('IsBattleground() and GetLevel("target") >= 81 '
                  'and GetLevel("target") <= 110')


def forget(structure):
    """Drop what the aptitude walker cached for this structure."""
    for name in ('_aptitude_tables', '_aptitude_hp_bounds'):
        structure.__dict__.pop(name, None)


def action_of(structure, stat):
    """An action whose template names this characteristic, added when missing."""
    text = '[#charac %s] [#1]' % stat.upper()
    for action, found in structure.aptitude_action_texts.items():
        if found == text:
            return action
    action = ACTION_BASE + len(structure.aptitude_action_texts)
    structure.aptitude_action_texts[action] = text
    return action


def add_category(structure, category, unlock_levels):
    structure.aptitude_categories[category] = list(unlock_levels)
    forget(structure)


def add_ability(structure, ident, category, ddl, **lines):
    """An ability that gives `per point` of each stat given, ddl 0 for no cap of its own."""
    structure.aptitude_abilities[ident] = (category, ddl)
    for number, (stat, per_point) in enumerate(sorted(lines.items())):
        effect_id = ident * 100 + number
        structure.aptitude_effects[effect_id] = EffectRow(
            effect_id, action_of(structure, stat), 'ABILITY', ident, 'NORMAL',
            [0, per_point], '')
    forget(structure)


def add_tier(structure, item_set, pieces, effect_id, criterion, **lines):
    """A set bonus tier: a root under `criterion` whose group gives each stat given."""
    members = []
    for number, (stat, value) in enumerate(sorted(lines.items()), 1):
        leaf = effect_id * 10 + number
        structure.aptitude_effects[leaf] = EffectRow(
            leaf, action_of(structure, stat), 'SET', item_set, 'NORMAL', [value, 0], '')
        members.append(leaf)
    structure.aptitude_effects[effect_id] = EffectRow(
        effect_id, 330, 'SET', item_set, 'NORMAL', [0, 0], criterion)
    structure.aptitude_effect_groups[effect_id] = members
    structure.aptitude_set_bonuses.append((item_set, pieces, effect_id))
    forget(structure)


def add_set(structure, item_set, item_ids):
    structure.aptitude_set_members[item_set] = list(item_ids)
    forget(structure)


def real_structure():
    """The real Wakfu structure when it holds the aptitude tables, else None."""
    import os
    from fashionistapulp.fashionista_config import get_items_db_path
    if not os.path.exists(get_items_db_path('wakfu')):
        return None
    from fashionistapulp.structure import Structure
    found = Structure('wakfu')
    return found if found.aptitude_abilities else None


class AptitudeCase(InventedItemsCase):
    """Invented items with the aptitude rows that `aptitude_rows` adds."""

    @classmethod
    def aptitude_rows(cls, structure):
        """Add abilities, categories and sets to the structure; the default adds none."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.aptitude_rows(cls.structure)
        forget(cls.structure)

    def solve(self, weights, forbidden=(), locked=(), level=LEVEL, class_id=None,
              aptitudes=SOLVE, battleground=False, full_set=True, levels=None):
        """(build, worn) of hand weights; worn is None when no set exists."""
        from fashionistapulp.wakfu_model import WakfuBuild
        build = WakfuBuild(self.structure, level, weights, forbidden, full_set,
                           locked=locked, class_id=class_id, aptitudes=aptitudes,
                           battleground=battleground, levels=levels)
        return build, build.build().solve()

    def violations(self, worn, level=LEVEL, **options):
        from fashionistapulp import wakfu_legality
        return wakfu_legality.violations(
            self.structure, level,
            {position: self.by_id(ident) for position, ident in worn.items()}, **options)

    def rules(self, worn, **options):
        return {rule for rule, _text in self.violations(worn, **options)}

    def worn_ids_of(self, result):
        return {one.id for one in result.worn.values()}


class NeedsTheRealTables(SimpleTestCase):
    """A real Wakfu structure with the aptitude tables, or a skipped test."""

    def setUp(self):
        self.real = real_structure()
        if self.real is None:
            self.skipTest('no Wakfu database with the aptitude tables')
