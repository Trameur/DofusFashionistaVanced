# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A hit that lands in one element is drawn once, not once per element."""
from django.test import SimpleTestCase

from chardata.spell_buffs import get_damage_spells_for_version
from chardata.spell_combo import element_runs
from chardata.spells_view import convert_aggregates, _one_lands_kind

VERSIONS = ('dofus3', 'beta', 'dofus2', 'touch', 'retro')

# Spells with a declared one-element run, per version
SORTS_DECLARES = {'dofus3': 33, 'beta': 33, 'dofus2': 26, 'touch': 6,
                  'retro': 1}
# Declared and undeclared runs, all versions
SUITES_DECLAREES = 197
SUITES_NON_DECLAREES = 86


def _rows_of(spell):
    digest = spell.get_effects_digest()
    return digest, (digest.non_crit_dams[0] if digest.non_crit_dams else [])


def _find(version, class_name, spell_name):
    for spell in get_damage_spells_for_version(version)[class_name]:
        if spell.name == spell_name:
            return spell
    raise AssertionError('%s/%s/%s left the catalogue'
                         % (version, class_name, spell_name))


class AHitThatLandsInOneElementIsDrawnOnceTests(SimpleTestCase):

    def test_the_witness_that_showed_eight_lines_shows_two(self):
        spell = _find('dofus3', 'Eniripsa', 'Scalpel')
        digest, rows = _rows_of(spell)
        self.assertEqual(8, len(digest.aggregates),
                         'the generator no longer writes one group per '
                         'element: %s' % (digest.aggregates,))
        groups = convert_aggregates(digest.aggregates, 'dofus3', rows)
        self.assertEqual(2, len(groups), groups)
        self.assertEqual([[0, 1, 2, 3], [4, 5, 6, 7]],
                         [group[1] for group in groups])
        self.assertEqual(['best', 'best'], [group[2] for group in groups])
        self.assertFalse(rows[0].heals)
        self.assertTrue(rows[4].heals,
                        'the second group is no longer the healing half')

    def test_a_random_element_keeps_its_faces(self):
        """The game draws the element, so no face is picked."""
        spell = _find('retro', 'Ecaflip', 'Bluff')
        digest, rows = _rows_of(spell)
        groups = convert_aggregates(digest.aggregates, 'retro', rows)
        self.assertEqual(1, len(groups), groups)
        self.assertEqual([0, 1], groups[0][1])
        self.assertEqual('one', groups[0][2])
        self.assertEqual({'air', 'water'},
                         {rows[0].element, rows[1].element})

    def test_the_table_and_the_turn_read_the_same_cut(self):
        """Each merged group is exactly one declared run."""
        checked = 0
        for version in VERSIONS:
            for class_name, spells in get_damage_spells_for_version(
                    version).items():
                for spell in spells:
                    digest, rows = _rows_of(spell)
                    if not digest.aggregates or not rows:
                        continue
                    declared = {
                        tuple(index for _label, indices in run
                              for index in indices)
                        for run in element_runs(digest.aggregates, rows)
                        if any(_one_lands_kind(label)
                               for label, _indices in run)}
                    if not declared:
                        continue
                    groups = convert_aggregates(digest.aggregates, version,
                                                rows)
                    merged = {tuple(group[1]) for group in groups
                              if len(group) > 2}
                    with self.subTest(version=version, spell=spell.name):
                        self.assertEqual(declared, merged)
                    checked += 1
        self.assertEqual(sum(SORTS_DECLARES.values()), checked)

    def test_the_scope_is_the_one_that_was_measured(self):
        by_version, declared, undeclared = {}, 0, 0
        for version in VERSIONS:
            touched = set()
            for class_name, spells in get_damage_spells_for_version(
                    version).items():
                for spell in spells:
                    digest, rows = _rows_of(spell)
                    if not rows:
                        continue
                    for run in element_runs(digest.aggregates, rows):
                        if any(_one_lands_kind(label)
                               for label, _indices in run):
                            declared += 1
                            touched.add((class_name, spell.name))
                        else:
                            undeclared += 1
            by_version[version] = len(touched)
        self.assertEqual(SORTS_DECLARES, by_version)
        self.assertEqual(SUITES_DECLAREES, declared)
        self.assertEqual(SUITES_NON_DECLAREES, undeclared,
                         'runs the generator does not declare must stay '
                         'untouched, and their number must be stated')

    def test_a_run_the_generator_did_not_declare_is_left_alone(self):
        """Elemental Drain rows are labelled by state, not by a choice."""
        spell = _find('dofus3', 'Huppermage', 'Elemental Drain')
        digest, rows = _rows_of(spell)
        runs = element_runs(digest.aggregates, rows)
        self.assertEqual(1, len(runs), len(runs))
        self.assertEqual(4, len(runs[0]))
        self.assertFalse([run for run in runs
                          if any(_one_lands_kind(label)
                                 for label, _indices in run)])
        groups = convert_aggregates(digest.aggregates, 'dofus3', rows)
        self.assertEqual(len(digest.aggregates), len(groups))
        self.assertFalse([group for group in groups if len(group) > 2])

    def test_the_weapon_keeps_its_groups_built_by_hand(self):
        """No rows, no merge."""
        aggregates = [('', [0, 1]), ('', [2])]
        self.assertEqual([['', [0, 1]], ['', [2]]],
                         convert_aggregates(aggregates))
