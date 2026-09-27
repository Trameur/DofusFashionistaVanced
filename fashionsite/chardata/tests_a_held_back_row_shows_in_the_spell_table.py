# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Every held-back row that hurts is drawn by the spell table, where its wait is written."""

from django.test import SimpleTestCase

from chardata.spell_buffs import get_damage_spells_for_version
from chardata.spells_view import _create_spell_web_digest

VERSIONS = ('dofus3', 'beta', 'dofus2', 'touch', 'retro')

# Rogue bombs print one line for two rows alike; one per bomb in each version below
TWINS = {'dofus3': 8, 'beta': 8}
TWIN_WAIT = 'bomb'


def _in_version(test, version):
    from fashionistapulp.structure import set_current_game_version
    test.addCleanup(set_current_game_version, 'dofus3')
    set_current_game_version(version)


def _drawn(web, key, rank, width):
    """Row indexes getHits draws: the groups plus the rows that always land."""
    if web['aggregates'] is None:
        return set(range(width))
    drawn = {index for group in web['aggregates'] for index in group[1]}
    extra = (web['always_land'] or {}).get(key) or {}
    return drawn | set(extra.get(str(rank)) or [])


def _line(row):
    return (row.element, row.min_dam, row.max_dam, bool(getattr(row, 'heals', False)))


class AHeldBackRowShowsInTheSpellTableTests(SimpleTestCase):

    def test_each_one_is_drawn_or_prints_the_line_of_a_drawn_twin(self):
        missing, twins, checked = [], {}, 0
        for version in VERSIONS:
            _in_version(self, version)
            seen = set()
            for spells in get_damage_spells_for_version(version).values():
                for spell in spells:
                    waits = getattr(spell, 'conditional', None) or {}
                    if not waits or id(spell) in seen:
                        continue
                    seen.add(id(spell))
                    digest = spell.get_effects_digest()
                    web = _create_spell_web_digest(spell, version)
                    for key, ranks in (('non_crit_dams', digest.non_crit_dams),
                                       ('crit_dams', digest.crit_dams)):
                        for rank, rows in enumerate(ranks or []):
                            drawn = _drawn(web, key.replace('_dams', ''), rank, len(rows))
                            for index, wait in waits.items():
                                if index >= len(rows) or not (rows[index].min_dam
                                                              or rows[index].max_dam):
                                    continue
                                checked += 1
                                if index in drawn:
                                    continue
                                if any(_line(rows[other]) == _line(rows[index])
                                       and waits.get(other) == wait for other in drawn
                                       if other < len(rows)):
                                    twins.setdefault(version, set()).add((spell.name, wait))
                                    continue
                                missing.append((version, spell.name, key, rank, index, wait))
        self.assertEqual([], missing,
                         'these held-back rows are in no group the table draws')
        self.assertEqual(TWINS, {version: len(names) for version, names in twins.items()})
        self.assertEqual({TWIN_WAIT}, {wait for names in twins.values() for _name, wait in names})
        self.assertGreater(checked, 600)
