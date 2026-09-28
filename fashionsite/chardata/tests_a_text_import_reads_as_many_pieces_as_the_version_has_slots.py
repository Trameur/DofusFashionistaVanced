# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A pasted build stops at the version's own slot count: sixteen on Dofus 3, eighteen with Touch's seals."""

from django.test import SimpleTestCase

from chardata.text_build_import import MAX_OBJETS, MIN_LIGNE, read_items
from fashionistapulp.dofus_constants import SLOTS, slots_for
from fashionistapulp.structure import get_structure


def _distinct_names(version, count):
    structure = get_structure(version)
    names = []
    for item in structure.get_items_list():
        name = structure.get_item_name_in_language(item, 'en') or ''
        if (not getattr(item, 'removed', False) and len(name) >= MIN_LIGNE + 5
                and name not in names and ':' not in name
                and not any(char.isdigit() for char in name)):
            names.append(name)
        if len(names) == count:
            return names
    raise AssertionError('only %d names on %s' % (len(names), version))


class TheCapFollowsTheVersionSlotsTests(SimpleTestCase):

    def test_the_shared_cap_is_the_sixteen_slots_every_version_has(self):
        self.assertEqual(16, MAX_OBJETS)
        self.assertEqual(len(SLOTS), MAX_OBJETS)
        self.assertEqual(MAX_OBJETS, len(slots_for('dofus3')))

    def test_each_version_reads_up_to_its_own_slot_count(self):
        for version, wanted in (('dofus3', 16), ('touch', 18)):
            with self.subTest(version=version):
                self.assertEqual(wanted, len(slots_for(version)))
                read = read_items('\n'.join(_distinct_names(version, 30)),
                                  version, 'en')
                self.assertEqual(wanted, len(read['item_ids']))
                self.assertTrue(read['truncated'])
