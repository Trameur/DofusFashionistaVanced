# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A target's weak element changes which spells the turn casts, while the face a spell lands is still the caster's pick."""
from django.core.cache import caches
from django.test import SimpleTestCase

from chardata.spell_combo import (HpShare, best_turn, castable_spells, final_multiplier,
                                  get_damage_spells_for_version, landed_index, row_value)
from chardata.targets import ELEMENTS, Target
from fashionistapulp.dofus_constants import calculate_damage
from fashionistapulp.structure import get_structure, set_current_game_version

VERSIONS = ('dofus3', 'beta')
STATS = {'str': 450, 'agi': 480, 'int': 470, 'cha': 460, 'pow': 90, 'dam': 30, 'cridam': 25,
         'ch': 45, 'hp': 3900}


def _stats(version):
    stats = {stat.key: 0 for stat in get_structure(version).get_stats_list()}
    for key, value in STATS.items():
        if key in stats:
            stats[key] = value
    return stats


def _target(version, percent):
    return Target(version=version, kind='monster', ref=('m', 1, 1), level=200, hp=10000,
                  percent=tuple(percent), is_player=False, label='a monster')


def _weak_in(version, element):
    """Every element at 50 percent but this one at -50."""
    return _target(version, [-50 if other == element else 50 for other in ELEMENTS])


def _elements(castable, stats):
    """The element of each face, or None when a face mixes elements."""
    out = []
    for rows in castable.plain_alternatives or []:
        found = {damage.element for damage in calculate_damage(
            [row for row in rows if not isinstance(row, HpShare)], stats, False,
            castable.is_spell)}
        out.append(next(iter(found)) if len(found) == 1 else None)
    return out


def _classes(version):
    return sorted(name for name in get_damage_spells_for_version(version) if name != 'default')


class TheTargetPicksTheSpellsTests(SimpleTestCase):

    def setUp(self):
        caches['best_turn'].clear()
        self.addCleanup(caches['best_turn'].clear)
        self.addCleanup(set_current_game_version, 'dofus3')

    def test_two_weak_elements_give_two_turns_for_a_class_hitting_in_both(self):
        for version in VERSIONS:
            set_current_game_version(version)
            stats = _stats(version)
            spells = castable_spells('Cra', 200, version)
            hit = {}
            for castable in spells:
                for element in _elements(castable, stats):
                    if element is not None and len(castable.plain_alternatives) == 1:
                        hit.setdefault(element, castable.name)
            self.assertGreaterEqual(len(hit), 2)
            first, second = sorted(hit)[:2]
            casts = {element: sorted({name for name, _damage in best_turn(
                stats, spells, 11, game_version=version, caster_level=200,
                target=_weak_in(version, element))[1]}) for element in (first, second)}
            with self.subTest(version=version, elements=(first, second)):
                self.assertNotEqual(casts[first], casts[second])


class TheCasterPicksTheFaceTests(SimpleTestCase):

    def setUp(self):
        caches['best_turn'].clear()
        self.addCleanup(caches['best_turn'].clear)
        self.addCleanup(set_current_game_version, 'dofus3')

    def _faced_spells(self, version, stats):
        """[(castable, face elements)] whose faces each hit one element of their own."""
        found = []
        for char_class in _classes(version):
            for castable in castable_spells(char_class, 200, version):
                if getattr(castable, 'random_draw', False) or not castable.cost:
                    continue
                elements = _elements(castable, stats)
                if (len(elements) > 1 and None not in elements
                        and len(set(elements)) == len(elements)):
                    found.append((castable, elements))
        return found

    def test_a_target_immune_to_the_landed_face_takes_nothing_from_it(self):
        for version in VERSIONS:
            set_current_game_version(version)
            stats = _stats(version)
            multiplier = final_multiplier(stats)
            faced = self._faced_spells(version, stats)
            self.assertTrue(faced)
            for castable, elements in faced:
                raw = [row_value([row for row in rows if not isinstance(row, HpShare)], stats,
                                 False, castable.is_spell, multiplier)
                       for rows in castable.plain_alternatives]
                pick = landed_index(castable, raw)
                if pick is None or raw[pick] <= 0:
                    continue
                immune = _target(version, [100 if element == elements[pick] else -50
                                           for element in ELEMENTS])
                with self.subTest(version=version, spell=castable.name):
                    self.assertEqual(0, best_turn(
                        stats, [castable], castable.cost, game_version=version,
                        caster_level=200, target=immune)[0])
