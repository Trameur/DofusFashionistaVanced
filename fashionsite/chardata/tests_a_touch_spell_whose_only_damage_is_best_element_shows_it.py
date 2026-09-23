# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A Touch spell whose only damage is best element shows it as four faces of one hit."""
from django.test import SimpleTestCase

from fashionistapulp.dofus_constants import DAMAGE_TYPE_TO_MAIN_STAT
from fashionistapulp.dofus_constants_touch_spells import TOUCH_DAMAGE_SPELLS

#: Class and damage at the last rank
LUS = {
    'Flèche Cinglante': ('Cra', 26, 30),
    'Punition': ('Sacrier', 37, 40),
    'Vol du Temps': ('Xelor', 33, 36),
    'Epée Divine': ('Iop', 22, 24),
    'Intimidation': ('Iop', 10, 12),
    'Projection': ('Sacrier', 12, 14),
}

#: Left out: each needs a state or a summon the turn does not model
DEHORS = ('Flasque Explosive', 'Fouet', 'Carnavalo')

FACES = ('earth', 'fire', 'water', 'air')


def _touch_spells():
    for class_name, spells in TOUCH_DAMAGE_SPELLS.items():
        for spell in spells:
            yield class_name, spell


class ATouchSpellWhoseOnlyDamageIsBestElementShowsItTests(SimpleTestCase):

    def test_the_six_spells_hit_in_four_faces_of_the_same_size(self):
        vus = {}
        for class_name, spell in _touch_spells():
            if spell.name not in LUS:
                continue
            vus[spell.name] = class_name
            attendue_classe, low, high = LUS[spell.name]
            digest = spell.get_effects_digest()
            rows = digest.non_crit_dams[-1]
            with self.subTest(sort=spell.name):
                self.assertEqual(attendue_classe, class_name)
                self.assertEqual(list(FACES),
                                 [row.element for row in rows])
                self.assertEqual({(low, high)},
                                 {(row.min_dam, row.max_dam) for row in rows},
                                 'the four faces are one hit, so they hold '
                                 'one value')
        self.assertEqual(set(LUS), set(vus), 'a spell left the Touch table')

    def test_the_four_faces_are_one_hit_and_not_four(self):
        for _class_name, spell in _touch_spells():
            if spell.name not in LUS:
                continue
            labels = [label for label, _indices in (spell.aggregates or [])]
            with self.subTest(sort=spell.name):
                self.assertEqual(4, len(labels), labels)
                self.assertEqual('Hit in best element', labels[0])
                self.assertEqual(['', '', ''], labels[1:])

    def test_neutral_is_not_a_face_because_it_has_no_stat_of_its_own(self):
        """Neutral reads the same stat as earth, so it is never the best one."""
        self.assertEqual(DAMAGE_TYPE_TO_MAIN_STAT['neut'],
                         DAMAGE_TYPE_TO_MAIN_STAT['earth'])
        for _class_name, spell in _touch_spells():
            if spell.name not in LUS:
                continue
            with self.subTest(sort=spell.name):
                self.assertNotIn('neutral',
                                 [row.element
                                  for row in spell.get_effects_digest()
                                  .non_crit_dams[-1]])

    def test_the_three_that_stay_out_stay_out(self):
        present = {spell.name for _class_name, spell in _touch_spells()}
        for name in DEHORS:
            with self.subTest(sort=name):
                self.assertNotIn(name, present)

    def test_only_the_six_best_element_spells_have_the_group(self):
        grouped = [spell.name for _class_name, spell in _touch_spells()
                   if any(label == 'Hit in best element'
                          for label, _indices in (spell.aggregates or []))]
        self.assertEqual(sorted(LUS), sorted(grouped),
                         'only the spells read on Ankama\'s sentence carry '
                         'the group')
