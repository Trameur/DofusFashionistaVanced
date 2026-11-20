# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The DofusBook export adds each Dracorune's stat changes to its global forgemagie totals, and names the runes their field cannot carry."""

from django.test import TestCase

from chardata import dofusbook_export
from chardata.dofusbook_rune_fixtures import (ELEMENT_KEY, code_of, RESISTANCE_KEY, draconize,
                                              export_page, forge_of, lines_of, piece,
                                              stand_in_runes, structure, worn_by)
from chardata.lock_forbid import set_stat_overrides
from fashionistapulp.structure import set_current_game_version


class _RuneExport(TestCase):

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')
        stand_in_runes(self)
        self.positions = dofusbook_export.index_by_stat_key()

    def total(self, forge, key):
        """The forgemagie their field holds for a characteristic: base and scroll taken off."""
        position = self.positions[key]
        value = forge[position] - dofusbook_export.character_base(200).get(position, 0)
        if position < dofusbook_export.BASE_STAT_COUNT and value >= dofusbook_export.SCROLL_STEP:
            value -= dofusbook_export.SCROLL_STEP
        return value


class RuneTotalsTravelTests(_RuneExport):

    def test_a_resistance_rune_moves_points_between_two_totals(self):
        hat = piece('Hat', RESISTANCE_KEY)
        char = worn_by(self.client, [hat])
        draconize(char, [(hat, RESISTANCE_KEY)])
        page = export_page(self.client, char)
        forge = forge_of(page)
        moved = lines_of(hat)['neutresper']
        self.assertEqual(-moved, self.total(forge, 'neutresper'))
        self.assertEqual(moved, self.total(forge, 'earthresper'))
        self.assertNotIn('export-dracorunes-staying', page.content.decode('utf-8'))

    def test_a_rune_adds_to_the_forgemagie_already_sent(self):
        hat = piece('Hat', RESISTANCE_KEY)
        char = worn_by(self.client, [hat])
        rolled = lines_of(hat)['init']
        set_stat_overrides(char, {hat.id: {structure().get_stat_by_key('init').id: rolled + 10}})
        draconize(char, [(hat, RESISTANCE_KEY)])
        moved = lines_of(hat)['neutresper']
        theirs = [{'official': hat.ankama_id,
                   'effects': [{'name': 'ii', 'type': 'E', 'min': rolled, 'max': rolled},
                               {'name': code_of('neutresper'), 'type': 'E', 'min': moved, 'max': moved}]}]
        forge = forge_of(export_page(self.client, char, known=theirs))
        self.assertEqual(10, self.total(forge, 'init'))
        self.assertEqual(moved, self.total(forge, 'earthresper'))
        self.assertEqual(-moved, self.total(forge, 'neutresper'))

    def test_a_rune_moves_the_totals_from_their_value_when_their_catalogue_differs(self):
        hat = piece('Hat', RESISTANCE_KEY)
        char = worn_by(self.client, [hat])
        draconize(char, [(hat, RESISTANCE_KEY)])
        ours = lines_of(hat)['neutresper']
        theirs = [{'official': hat.ankama_id,
                   'effects': [{'name': code_of('neutresper'), 'type': 'E', 'min': ours - 2, 'max': ours - 2}]}]
        forge = forge_of(export_page(self.client, char, known=theirs))
        self.assertEqual(-(ours - 2), self.total(forge, 'neutresper'))
        self.assertEqual(ours, self.total(forge, 'earthresper'))

    def test_a_rune_on_a_line_with_an_override_moves_it_from_the_override(self):
        hat = piece('Hat', RESISTANCE_KEY)
        char = worn_by(self.client, [hat])
        ours = lines_of(hat)['neutresper']
        set_stat_overrides(char, {hat.id: {structure().get_stat_by_key('neutresper').id: ours - 1}})
        draconize(char, [(hat, RESISTANCE_KEY)])
        theirs = [{'official': hat.ankama_id,
                   'effects': [{'name': code_of('neutresper'), 'type': 'E', 'min': ours, 'max': ours}]}]
        forge = forge_of(export_page(self.client, char, known=theirs))
        self.assertEqual(-ours, self.total(forge, 'neutresper'))

    def test_two_runes_on_two_pieces_add_up(self):
        hat = piece('Hat', RESISTANCE_KEY)
        cloak = piece('Cloak', RESISTANCE_KEY)
        char = worn_by(self.client, [hat, cloak])
        draconize(char, [(hat, RESISTANCE_KEY), (cloak, RESISTANCE_KEY)])
        forge = forge_of(export_page(self.client, char))
        moved = lines_of(hat)['neutresper'] + lines_of(cloak)['neutresper']
        self.assertEqual(moved, self.total(forge, 'earthresper'))
        self.assertEqual(-moved, self.total(forge, 'neutresper'))

    def test_a_rune_on_a_piece_that_stays_home_sends_nothing(self):
        hat = piece('Hat', RESISTANCE_KEY)
        cloak = piece('Cloak', RESISTANCE_KEY)
        char = worn_by(self.client, [hat, cloak])
        draconize(char, [(hat, RESISTANCE_KEY), (cloak, RESISTANCE_KEY)])
        known = [{'official': hat.ankama_id, 'effects': []}]
        forge = forge_of(export_page(self.client, char, known=known))
        self.assertEqual(lines_of(hat)['neutresper'], self.total(forge, 'earthresper'))


class RunesTheirFieldCannotCarryTests(_RuneExport):

    def setUp(self):
        super().setUp()
        self.hat = piece('Hat', ELEMENT_KEY)
        self.char = worn_by(self.client, [self.hat])
        draconize(self.char, [(self.hat, ELEMENT_KEY)])

    def test_a_negative_characteristic_total_is_named_and_not_sent(self):
        page = export_page(self.client, self.char)
        forge = forge_of(page)
        self.assertEqual(0, self.total(forge, 'cha'))
        self.assertEqual(0, self.total(forge, 'agi'))
        text = page.content.decode('utf-8')
        self.assertIn('export-dracorunes-staying', text)
        self.assertIn('cannot carry these Dracorunes', text)
        self.assertIn('Emerald Dracorune', text)
        self.assertIn('Emerald Dracorune (%s)' % structure().get_item_name_in_language(self.hat, 'en'), text)

    def test_the_name_is_the_games_in_the_page_language(self):
        text = export_page(self.client, self.char, language='fr').content.decode('utf-8')
        self.assertIn('Dracorune Émeraude', text)
        self.assertIn('ne peut pas porter ces Dracorunes', text)

    def test_the_rune_that_fits_still_travels_beside_the_one_that_does_not(self):
        cloak = piece('Cloak', RESISTANCE_KEY)
        char = worn_by(self.client, [self.hat, cloak])
        draconize(char, [(self.hat, ELEMENT_KEY), (cloak, RESISTANCE_KEY)])
        page = export_page(self.client, char)
        forge = forge_of(page)
        self.assertEqual(lines_of(cloak)['neutresper'], self.total(forge, 'earthresper'))
        self.assertEqual(0, self.total(forge, 'agi'))
        self.assertEqual(1, page.content.decode('utf-8').count('Emerald Dracorune'))
