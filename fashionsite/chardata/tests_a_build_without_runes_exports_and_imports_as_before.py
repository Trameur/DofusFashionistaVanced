# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A build without runes, and any version without a runes file, exports the same link and page keys and imports the same result as before Dracorunes."""

import re

from django.test import TestCase

from chardata import dofusbook_import
from chardata.char_blobs import read_char_blob
from chardata.dofusbook_rune_fixtures import (LINK, RESISTANCE_KEY, draconize, export_page,
                                              lines_of, opener, piece, public_payload, slot_code,
                                              stand_in_runes, variant_lines, worn_by)
from chardata.options import get_options
from fashionistapulp.structure import set_current_game_version

PAGE_KEYS = {'char', 'char_id', 'version_label', 'link', 'going', 'staying', 'partial_scrolls',
             'forge_travels', 'shiny_travels', 'weapon_by_hand', 'forge_staying',
             'vitality_scroll_forced'}
BUILD_KEYS = {'game_version', 'source_host', 'build_id', 'name', 'level', 'item_ids', 'missing',
              'missing_ankama_ids', 'base_points', 'base_scrolled', 'rolls', 'fm_unmapped',
              'fm_global', 'fm_weapon', 'fm_steal_weapon', 'fm_heal_weapon', 'class_is_unknown'}


def link_of(page):
    return re.search(r'stuff=([^"&\'<> ]+)', page.content.decode('utf-8')).group(1)


def context_keys(page):
    keys = set()
    for context in (page.context if isinstance(page.context, list) else [page.context]):
        for layer in context.dicts:
            keys.update(layer)
    return keys


class AnExportWithoutRunesIsUnchangedTests(TestCase):

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')
        self.hat = piece_for_the_tests()
        self.char = worn_by(self.client, [self.hat])

    def test_a_dofus3_build_gets_the_page_keys_it_always_had(self):
        page = export_page(self.client, self.char)
        keys = context_keys(page)
        self.assertTrue(PAGE_KEYS <= keys)
        self.assertNotIn('dracorunes_staying', keys)
        self.assertNotIn('export-dracorunes-staying', page.content.decode('utf-8'))

    def test_a_saved_rune_on_a_version_without_a_runes_file_changes_nothing(self):
        before = link_of(export_page(self.client, self.char))
        draconize_without_file(self.char, self.hat)
        page = export_page(self.client, self.char)
        self.assertEqual(before, link_of(page))
        self.assertNotIn('dracorunes_staying', context_keys(page))

    def test_a_build_without_runes_gives_the_same_link_with_the_runes_file_present(self):
        before = link_of(export_page(self.client, self.char))
        stand_in_runes(self)
        page = export_page(self.client, self.char)
        self.assertEqual(before, link_of(page))
        self.assertNotIn('dracorunes_staying', context_keys(page))


class AnImportWithoutRunesIsUnchangedTests(TestCase):

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')
        self.hat = piece_for_the_tests()

    def read(self, lines):
        payload = public_payload([(slot_code('Hat'), self.hat, lines)])
        return dofusbook_import.read_build(LINK, opener=opener(payload))

    def test_the_result_has_the_keys_it_always_had_and_no_rune(self):
        lu = self.read(lines_of(self.hat))
        self.assertEqual(BUILD_KEYS, set(lu))

    def test_rune_lines_without_a_runes_file_stay_rolls(self):
        lu = self.read(variant_lines_from_the_file(self.hat))
        self.assertEqual(BUILD_KEYS, set(lu))
        self.assertIn(self.hat.id, lu['rolls'])
        self.assertEqual({'neutresper': 0, 'earthresper': variant_lines_from_the_file(self.hat)['earthresper']},
                         {line['key']: line['value'] for line in lu['rolls'][self.hat.id]})

    def test_the_saved_build_never_writes_the_option(self):
        from unittest import mock
        from chardata import text_build_view
        from chardata.models import Char
        payload = public_payload([(slot_code('Hat'), self.hat, variant_lines_from_the_file(self.hat))])

        def reading(url, opener_=None):
            return dofusbook_import.read_build(url, opener=opener(payload))

        with mock.patch.object(text_build_view, 'read_build', reading):
            self.client.post('/import/text/', {'text': LINK, 'confirm': '1',
                                               'char_class': 'Iop', 'level': '200'})
        char = Char.objects.order_by('-id').first()
        minimal = read_char_blob(char.minimal_solution, None, 'minimal_solution', char)
        self.assertFalse(getattr(minimal, 'dracorunes', None))
        self.assertNotIn('dracorunes', get_options(char))


def piece_for_the_tests():
    return piece('Hat', RESISTANCE_KEY)


def variant_lines_from_the_file(item):
    from chardata.dofusbook_rune_fixtures import REAL_LOAD
    from fashionistapulp import dracorunes
    return dict(dict(dracorunes.variants(list(lines_of(item).items()),
                                         REAL_LOAD('beta')))[RESISTANCE_KEY])


def draconize_without_file(char, item):
    draconize(char, [(item, RESISTANCE_KEY)])
