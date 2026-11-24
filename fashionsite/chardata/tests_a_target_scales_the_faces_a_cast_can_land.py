# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A random draw averages the faces on the target, and a cast lands the caster's face with that face's values on the target."""
from django.core.cache import caches
from django.test import SimpleTestCase

from chardata.spell_combo import (HpShare, _late_landed, best_turn, castable_spells,
                                  final_multiplier, get_damage_spells_for_version, landed_index,
                                  row_value)
from chardata.targets import ELEMENTS, Target
from fashionistapulp.dofus_constants import calculate_damage
from fashionistapulp.structure import get_structure, set_current_game_version

VERSIONS = ('dofus3', 'beta', 'dofus2', 'touch', 'retro')
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


def _hits(rows):
    return [row for row in rows if not isinstance(row, HpShare)]


def _classes(version):
    return sorted(name for name in get_damage_spells_for_version(version) if name != 'default')


def _element_of(rows, stats, castable):
    found = {damage.element for damage in calculate_damage(_hits(rows), stats, False,
                                                           castable.is_spell)}
    return next(iter(found)) if len(found) == 1 else None


class TheFacesOnATargetTests(SimpleTestCase):

    def setUp(self):
        caches['best_turn'].clear()
        self.addCleanup(caches['best_turn'].clear)
        self.addCleanup(set_current_game_version, 'dofus3')

    def test_a_random_draw_averages_its_faces_as_the_target_takes_them(self):
        seen = 0
        for version in VERSIONS:
            set_current_game_version(version)
            stats = _stats(version)
            multiplier = final_multiplier(stats)
            for char_class in _classes(version):
                for castable in castable_spells(char_class, 200, version):
                    faces = castable.alternatives or []
                    if (not getattr(castable, 'random_draw', False) or len(faces) < 2
                            or getattr(castable, 'late_by_effect', None)
                            or getattr(castable, 'recasts', None)
                            or any(isinstance(row, HpShare) for rows in faces for row in rows)):
                        continue
                    seen += 1
                    target = _target(version, [20, -40, 60, 0, 35])
                    expected = sum(row_value(_hits(rows), stats, True, castable.is_spell,
                                             multiplier, target)
                                   for rows in faces) / len(faces)
                    raw = sum(row_value(_hits(rows), stats, True, castable.is_spell,
                                        multiplier) for rows in faces) / len(faces)
                    found = best_turn(stats, [castable], castable.cost, crit=True,
                                      game_version=version, caster_level=200, target=target)[0]
                    with self.subTest(version=version, spell=castable.name):
                        self.assertNotAlmostEqual(raw, expected, delta=0.5)
                        self.assertAlmostEqual(expected, found, delta=1e-6 * expected)
        self.assertGreater(seen, 0)

    def test_the_face_a_cast_lands_carries_its_values_on_the_target(self):
        seen = 0
        for version in VERSIONS:
            set_current_game_version(version)
            stats = _stats(version)
            multiplier = final_multiplier(stats)
            for char_class in _classes(version):
                for castable in castable_spells(char_class, 200, version):
                    faces = castable.plain_alternatives or []
                    elements = [_element_of(rows, stats, castable) for rows in faces]
                    if (len(faces) < 2 or None in elements
                            or len(set(elements)) != len(elements)
                            or any(isinstance(row, HpShare) for rows in faces for row in rows)):
                        continue
                    raw = [row_value(_hits(rows), stats, False, castable.is_spell, multiplier)
                           for rows in faces]
                    pick = landed_index(castable, raw)
                    if pick is None or raw[pick] <= 0:
                        continue
                    seen += 1
                    target = _target(version, [50 if element == elements[pick] else -50
                                               for element in ELEMENTS])
                    scored, _late = _late_landed(castable, faces, stats, False, multiplier,
                                                 target)
                    expected = row_value(_hits(faces[pick]), stats, False, castable.is_spell,
                                         multiplier, target)
                    with self.subTest(version=version, spell=castable.name):
                        self.assertAlmostEqual(expected, scored, delta=1e-6 * max(1.0, expected))
        self.assertGreater(seen, 0)
