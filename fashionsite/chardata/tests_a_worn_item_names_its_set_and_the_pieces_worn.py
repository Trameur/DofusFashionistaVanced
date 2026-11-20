# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Each worn piece of a set on the solution page carries the set name and the pieces worn out of the set total."""
from types import SimpleNamespace

from django.template.loader import render_to_string
from django.test import SimpleTestCase

from chardata.solution_result import set_tags


def piece(slot, set_id, added=True):
    return SimpleNamespace(slot=slot, set=set_id, item_added=added)


def worn_set(set_id, name, worn, total):
    return SimpleNamespace(id=set_id, localized_name=name, number_of_items=worn, total_number_of_items=total)


class TheSetTableFollowsTheSetsTheResultHoldsTests(SimpleTestCase):

    def test_every_piece_of_a_set_gets_the_name_the_pieces_worn_and_the_total(self):
        tags = set_tags([worn_set(7, 'Meno', 2, 3)], [piece('hat', 7), piece('cloak', 7), piece('belt', 9)])
        self.assertEqual({'hat': ('Meno', 2, 3), 'cloak': ('Meno', 2, 3)}, tags)

    def test_a_complete_set_reads_total_over_total(self):
        tags = set_tags([worn_set(4, 'War', 4, 4)], [piece('hat', 4)])
        self.assertEqual(('War', 4, 4), tags['hat'])

    def test_a_single_piece_of_a_set_is_not_a_set_of_the_result_and_has_no_tag(self):
        self.assertEqual({}, set_tags([], [piece('hat', 7)]))

    def test_an_empty_slot_has_no_tag_even_if_its_set_is_worn_elsewhere(self):
        self.assertEqual({}, set_tags([worn_set(7, 'Meno', 2, 3)], [piece('hat', 7, added=False)]))

    def test_two_sets_keep_their_own_counts(self):
        tags = set_tags([worn_set(1, 'A', 2, 3), worn_set(2, 'B', 3, 5)], [piece('hat', 1), piece('belt', 2)])
        self.assertEqual(('A', 2, 3), tags['hat'])
        self.assertEqual(('B', 3, 5), tags['belt'])


class TheItemCardNamesItsSlotAndItsSetTests(SimpleTestCase):

    def render(self, **fields):
        item = SimpleNamespace(slot='hat', id=12, localized_name='Meno Cap', level=200, slot_type='Hat',
                               set_tag=None, file='', link='', stats_lines=[])
        for key, value in fields.items():
            setattr(item, key, value)
        return render_to_string('chardata/solution_item.html', {'item': item})

    def test_a_worn_piece_shows_its_slot_and_its_set_with_the_pieces_worn(self):
        html = self.render(set_tag=('Meno', 2, 3))
        self.assertIn('<div class="fm-slot-label fm-modern-only">Hat</div>', html)
        self.assertIn('<span class="fm-set-tag-name">Meno</span> 2/3', html)

    def test_a_piece_outside_a_worn_set_has_no_tag(self):
        self.assertNotIn('fm-set-tag', self.render())

    def test_an_empty_slot_has_no_slot_label(self):
        self.assertNotIn('fm-slot-label', self.render(id=None))


class TheSetCardDrawsItsTapeTests(SimpleTestCase):

    def render(self, worn, total):
        result_set = SimpleNamespace(
            localized_name='Meno', number_of_items=worn, total_number_of_items=total, url='/x/', id=1,
            parts={}, stats_lines=[])
        return render_to_string('chardata/solution_set.html', {'set_result': result_set})

    def test_the_tape_is_filled_to_the_pieces_worn(self):
        self.assertIn('--w:75%', self.render(3, 4))

    def test_a_complete_set_fills_the_tape(self):
        self.assertIn('--w:100%', self.render(3, 3))

    def test_the_ratio_is_printed(self):
        self.assertIn('>2/3<', self.render(2, 3))
