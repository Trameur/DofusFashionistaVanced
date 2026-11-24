# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The boomerang's buff rides the one element it steals, in the panel total as in the cast."""

from types import SimpleNamespace

from django.test import SimpleTestCase

from chardata.spell_buffs import compute_full_buff_stats, get_damage_spells_for_version
from chardata.spell_combo import Castable, buffs_in_force, drawn_buff_faces

PERFIDIOUS_BOOMERANG = 364
DIAMONDINE_BOOMERANG = 24007
VERSIONS = ('dofus3', 'beta', 'dofus2')
FOUR = ('str', 'int', 'cha', 'agi')


def _in_version(test, version):
    from fashionistapulp.structure import set_current_game_version
    test.addCleanup(set_current_game_version, 'dofus3')
    set_current_game_version(version)


def _spell(version, spell_id):
    return next(spell for spell in get_damage_spells_for_version(version)['default']
                if spell.spell_id == spell_id)


def _caster(level=200):
    return SimpleNamespace(char_class='no such class', level=level)


class TheFullBuffPanelCountsOneElementTests(SimpleTestCase):

    def test_the_four_buffs_of_the_boomerang_share_one_element(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                spell = _spell(version, PERFIDIOUS_BOOMERANG)
                digest = spell.get_effects_digest()
                rows = digest.crit_dams[-1]
                faces = drawn_buff_faces(digest.aggregates, rows)
                self.assertEqual([4, 4, 4, 4], sorted(faces.values()))
                full = {effect.element: effect.max_dam for effect in rows
                        if effect.element.startswith('buff')}
                self.assertEqual(4, len(full))

    def test_the_panel_holds_a_quarter_of_each_characteristic(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                stats = compute_full_buff_stats(_caster(), version)
                self.assertEqual({stat: 45 for stat in FOUR},
                                 {stat: stats.get(stat) for stat in FOUR})

    def test_the_panel_sums_to_one_buff_not_four(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                stats = compute_full_buff_stats(_caster(), version)
                self.assertEqual(180, sum(stats.get(stat, 0) for stat in FOUR))

    def test_the_panel_agrees_with_the_cast(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                _in_version(self, version)
                spell = _spell(version, PERFIDIOUS_BOOMERANG)
                cast = Castable(spell, len(spell.level_req) - 1, crit=True)
                stats = compute_full_buff_stats(_caster(), version)
                self.assertEqual(cast.buff_deltas(spell.stacks),
                                 {stat: stats[stat] for stat in FOUR})

    def test_a_ticked_boomerang_adds_the_same_as_the_panel(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                _in_version(self, version)
                ticked = buffs_in_force('no such class', 200, version,
                                        {'Perfidious Boomerang': 'c1'})
                self.assertEqual({stat: 45 for stat in FOUR}, ticked)

    def test_the_other_boomerang_has_no_buff_to_count(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                spell = _spell(version, DIAMONDINE_BOOMERANG)
                digest = spell.get_effects_digest()
                self.assertEqual({}, drawn_buff_faces(digest.aggregates, digest.crit_dams[-1]))
                self.assertFalse([effect for effect in digest.non_crit_dams[-1]
                                  if effect.element.startswith('buff')])
