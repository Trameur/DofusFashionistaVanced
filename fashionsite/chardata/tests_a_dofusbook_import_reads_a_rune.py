# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A DofusBook slot whose forgemagie lines equal one rune variant of its piece is read as that Dracorune; every other slot keeps the rolls path."""

from unittest import mock

from django.test import SimpleTestCase, TestCase

from chardata import dofusbook_import, dracorune_import, text_build_view, version_copy
from chardata.char_blobs import read_char_blob
from chardata.dofusbook_rune_fixtures import (LINK, RESISTANCE_KEY, lines_of, opener, piece,
                                              public_payload, slot_code, stand_in_runes,
                                              variant_lines)
from chardata.models import Char
from chardata.options import get_options, set_setup_choices
from fashionistapulp.structure import set_current_game_version


class _Link(TestCase):

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')
        self.hat = piece('Hat', RESISTANCE_KEY)
        self.cloak = piece('Cloak', RESISTANCE_KEY)

    def read(self, entries):
        return dofusbook_import.read_build(LINK, opener=opener(public_payload(entries)))

    def entries(self, hat_lines, cloak_lines=None):
        found = [(slot_code('Hat'), self.hat, hat_lines)]
        if cloak_lines is not None:
            found.append((slot_code('Cloak'), self.cloak, cloak_lines))
        return found


class ARuneIsReadFromItsLinesTests(_Link):

    def setUp(self):
        super().setUp()
        stand_in_runes(self)

    def test_lines_equal_to_one_variant_are_that_rune(self):
        lu = self.read(self.entries(variant_lines(self.hat, RESISTANCE_KEY)))
        self.assertEqual([(self.hat.id, RESISTANCE_KEY)], lu['dracorunes'])
        self.assertNotIn(self.hat.id, lu['rolls'])
        self.assertNotIn('dracorunes_unread', lu)

    def test_every_rune_of_the_build_is_read(self):
        lu = self.read(self.entries(variant_lines(self.hat, RESISTANCE_KEY),
                                    variant_lines(self.cloak, RESISTANCE_KEY)))
        self.assertEqual({(self.hat.id, RESISTANCE_KEY), (self.cloak.id, RESISTANCE_KEY)},
                         set(lu['dracorunes']))

    def test_the_lines_of_the_base_item_keep_the_rolls_path(self):
        lu = self.read(self.entries(lines_of(self.hat)))
        self.assertNotIn('dracorunes', lu)
        self.assertNotIn('dracorunes_unread', lu)
        self.assertNotIn(self.hat.id, lu['rolls'])

    def test_a_sheet_that_omits_the_removed_line_keeps_the_rolls_path(self):
        payload = public_payload(self.entries(variant_lines(self.hat, RESISTANCE_KEY)))
        sent = payload['fmItems'][slot_code('Hat')]
        self.assertEqual(0, sent.pop('rnp'))
        lu = dofusbook_import.read_build(LINK, opener=opener(payload))
        self.assertNotIn('dracorunes', lu)
        self.assertEqual([{'key': 'earthresper', 'value': variant_lines(self.hat, RESISTANCE_KEY)['earthresper']}],
                         lu['rolls'][self.hat.id])

    def test_the_sparse_sheet_with_the_removed_line_as_zero_is_the_rune(self):
        payload = public_payload(self.entries(variant_lines(self.hat, RESISTANCE_KEY)))
        sent = payload['fmItems'][slot_code('Hat')]
        self.assertEqual({'rnp': 0, 'rtp': variant_lines(self.hat, RESISTANCE_KEY)['earthresper']}, sent)
        lu = dofusbook_import.read_build(LINK, opener=opener(payload))
        self.assertEqual([(self.hat.id, RESISTANCE_KEY)], lu['dracorunes'])

    def test_lines_that_fit_no_variant_keep_the_rolls_path(self):
        lines = variant_lines(self.hat, RESISTANCE_KEY)
        lines['earthresper'] += 1
        lu = self.read(self.entries(lines))
        self.assertNotIn('dracorunes', lu)
        self.assertIn(self.hat.id, lu['rolls'])

    def test_a_piece_forged_by_hand_beside_a_rune_keeps_its_rolls(self):
        forged = dict(lines_of(self.cloak))
        forged['vit'] = forged.get('vit', 0) + 5
        lu = self.read(self.entries(variant_lines(self.hat, RESISTANCE_KEY), forged))
        self.assertEqual([(self.hat.id, RESISTANCE_KEY)], lu['dracorunes'])
        self.assertIn(self.cloak.id, lu['rolls'])
        self.assertNotIn(self.hat.id, lu['rolls'])

    def test_a_piece_the_runes_do_not_take_is_never_read_as_a_rune(self):
        lines = variant_lines(self.hat, RESISTANCE_KEY)
        with mock.patch('fashionistapulp.dracorune_terms.is_eligible', return_value=False):
            lu = self.read(self.entries(lines))
        self.assertNotIn('dracorunes', lu)
        self.assertIn(self.hat.id, lu['rolls'])


class ARuneTheVersionRejectsDegradesToRollsTests(_Link):

    def test_the_sheet_lines_of_a_rejected_rune_come_back_as_rolls(self):
        stand_in_runes(self)
        lu = self.read(self.entries(variant_lines(self.hat, RESISTANCE_KEY)))
        self.assertNotIn(self.hat.id, lu['rolls'])
        lu['dracorunes'] = [(self.hat.id, 'element:nothing>nowhere')]
        back = dracorune_import.rejected_as_rolls(lu, 'dofus3')
        self.assertEqual({'earthresper', 'neutresper'},
                         {line['key'] for line in back['rolls'][self.hat.id]})

    def test_a_rune_the_version_keeps_adds_no_roll(self):
        stand_in_runes(self)
        lu = self.read(self.entries(variant_lines(self.hat, RESISTANCE_KEY)))
        self.assertEqual(lu['rolls'], dracorune_import.rejected_as_rolls(lu, 'dofus3')['rolls'])


class AVersionWithoutARunesFileNeverReadsARuneTests(_Link):

    def test_the_same_lines_stay_rolls(self):
        lines = self.lines_of_the_rune()
        lu = self.read(self.entries(lines))
        self.assertNotIn('dracorunes', lu)
        self.assertNotIn('dracorunes_unread', lu)
        self.assertIn(self.hat.id, lu['rolls'])

    def lines_of_the_rune(self):
        from chardata.dofusbook_rune_fixtures import REAL_LOAD
        from fashionistapulp import dracorunes
        base = lines_of(self.hat)
        return dict(dict(dracorunes.variants(list(base.items()), REAL_LOAD('beta')))[RESISTANCE_KEY])


class TheSavedBuildHoldsTheRuneTests(TestCase):

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')
        stand_in_runes(self)
        self.hat = piece('Hat', RESISTANCE_KEY)
        self.cloak = piece('Cloak', RESISTANCE_KEY)

    def importing(self, entries, confirm=True, language='en'):
        payload = public_payload(entries)

        def reading(url, opener_=None):
            return dofusbook_import.read_build(url, opener=opener(payload))

        with mock.patch.object(text_build_view, 'read_build', reading):
            data = {'text': LINK}
            if confirm:
                data.update({'confirm': '1', 'char_class': 'Iop', 'level': '200'})
            return self.client.post('/import/text/', data, HTTP_ACCEPT_LANGUAGE=language)

    def saved(self):
        char = Char.objects.order_by('-id').first()
        return char, read_char_blob(char.minimal_solution, None, 'minimal_solution', char)

    def test_the_rune_is_in_the_saved_solution_and_the_count_is_raised(self):
        self.importing([(slot_code('Hat'), self.hat, variant_lines(self.hat, RESISTANCE_KEY)),
                        (slot_code('Cloak'), self.cloak,
                         variant_lines(self.cloak, RESISTANCE_KEY))])
        char, minimal = self.saved()
        self.assertEqual({self.hat.id, self.cloak.id},
                         {item for item, _key in minimal.dracorunes.values()})
        self.assertEqual({RESISTANCE_KEY}, {key for _item, key in minimal.dracorunes.values()})
        for slot, (item_id, _key) in minimal.dracorunes.items():
            self.assertEqual(item_id, minimal.item_per_slot[slot])
        self.assertEqual(2, get_options(char)['dracorunes'])
        self.assertEqual(2, minimal.input['options']['dracorunes'])

    def test_a_higher_count_the_build_already_had_is_kept(self):
        self.importing([(slot_code('Hat'), self.hat, lines_of(self.hat))])
        char, _minimal = self.saved()
        set_setup_choices(char, {'dracorunes': 5})
        dracorune_import.put_on_solution(char, {'dracorunes': [(self.hat.id, RESISTANCE_KEY)]})
        self.assertEqual(5, get_options(char)['dracorunes'])

    def test_the_preview_names_the_rune_in_the_page_language(self):
        entries = [(slot_code('Hat'), self.hat, variant_lines(self.hat, RESISTANCE_KEY))]
        page = self.importing(entries, confirm=False).content.decode('utf-8')
        self.assertIn('import-link-dracorunes', page)
        self.assertIn('Read as Dracorunes', page)
        self.assertIn('Ivory Dracorune', page)
        self.assertNotIn('import-link-dracorunes-unread', page)
        french = self.importing(entries, confirm=False, language='fr').content.decode('utf-8')
        self.assertIn('Dracorune Ivoire', french)
        self.assertIn('Lues comme Dracorunes', french)

    def test_a_rune_the_version_cannot_place_is_reported_in_the_preview(self):
        build = {'game_version': 'dofus3', 'item_ids': [self.hat.id],
                 'dracorunes': [(self.hat.id, 'element:nothing>nowhere')]}
        self.assertEqual(([], [self.hat.id]), dracorune_import.checked(build, 'dofus3'))
        self.assertEqual([self.hat.id], dracorune_import.checked(
            {'dracorunes_unread': [self.hat.id]}, 'dofus3')[1])

    def test_lines_that_fit_no_variant_import_as_rolls_without_a_rune(self):
        lines = variant_lines(self.hat, RESISTANCE_KEY)
        lines['earthresper'] += 1
        self.importing([(slot_code('Hat'), self.hat, lines)])
        char, minimal = self.saved()
        self.assertFalse(getattr(minimal, 'dracorunes', None))
        self.assertNotIn('dracorunes', get_options(char))


class AMovedLinkKeepsOnlyTheRunesOfItsPiecesTests(SimpleTestCase):

    def test_a_missing_piece_takes_its_rune_with_it(self):
        build = {'game_version': 'dofus3', 'item_ids': [1], 'dracorunes': [(1, 'x'), (2, 'y')],
                 'dracorunes_unread': [1, 2], 'missing': [], 'missing_ankama_ids': []}
        pieces = mock.Mock()
        pieces.item_id = lambda item_id: 10 if item_id == 1 else None
        with mock.patch.object(version_copy, 'pieces_between', return_value=pieces):
            moved = version_copy.link_build_in(build, 'beta', 'en')
        self.assertEqual([(10, 'x')], moved['dracorunes'])
        self.assertEqual([10], moved['dracorunes_unread'])
