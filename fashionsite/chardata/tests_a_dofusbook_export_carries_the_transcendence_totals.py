# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The DofusBook export adds each transcendence rune's bonus to its global forgemagie totals, sets the exo bit of an AP, MP or Range rune, and names the runes their field cannot carry."""

import re
import urllib.parse
from types import SimpleNamespace
from unittest import mock

from django.test import TestCase

from chardata import dofusbook_export
from chardata.char_blobs import read_char_blob
from chardata.dofusbook_export_view import _transcendence_positions
from chardata.dofusbook_rune_fixtures import (ELEMENT_KEY, RESISTANCE_KEY, VERSION, draconize,
                                              export_page, forge_of, lines_of, piece,
                                              stand_in_runes, structure, worn_by)
from chardata.lock_forbid import set_stat_overrides
from chardata.solution import set_minimal_solution
from fashionistapulp import transcendence
from fashionistapulp.structure import set_current_game_version
from fashionistapulp.transcendence_terms import rune_fits

BETA_RUNES = transcendence.load_runes('beta')


def rune_for(item, stat_key, rank=1):
    """The Beta rune of that stat and rank, once it fits the piece's line."""
    rune = next(rune for rune in BETA_RUNES if rune['stat_key'] == stat_key and rune['rank'] == rank)
    assert rune_fits(rune, lines_of(item).get(stat_key)), 'the rune does not fit the piece'
    return rune


def stand_in_transcendences(testcase):
    """Lets Dofus 3 read the Beta transcendence runes for the length of the test."""
    def fake(version, folder=None):
        return BETA_RUNES if version == VERSION else transcendence.load_runes(version, folder)

    patcher = mock.patch('fashionistapulp.modelresult.load_transcendence_runes', fake)
    patcher.start()
    testcase.addCleanup(patcher.stop)


def transcend(char, runes_on):
    """Saves [(item, rune)] on the char's solution, each on the slot that holds the item."""
    minimal = read_char_blob(char.minimal_solution, None, 'minimal_solution', char)
    set_current_game_version(VERSION)
    unplaced = minimal.place_transcendences([({item.id}, rune['id'], rune['stat_key'])
                                             for item, rune in runes_on])
    assert not unplaced, 'a rune found no slot'
    set_minimal_solution(char, minimal)
    return minimal


def no_exo_option():
    """Takes the build's own exo options out of the export, to read the runes' flags alone."""
    return mock.patch('chardata.dofusbook_export_view._exos', return_value=0)


def exo_option(bits):
    """Gives the export a build whose own exo options set those bits."""
    return mock.patch('chardata.dofusbook_export_view._exos', return_value=bits)


def without_transcendences():
    """The export as it was before the runes: the two helpers find no rune and no bit."""
    return mock.patch.multiple('chardata.dofusbook_export_view',
                               _worn_transcendences=mock.Mock(return_value=([], 0)),
                               _transcendence_positions=mock.Mock(return_value=({}, 0)))


def page_bytes(client, char):
    """The export page with its per-request CSRF token and its timestamped seen token taken out."""
    page = export_page(client, char).content
    token = re.search(rb"csrfmiddlewaretoken\" type=\"hidden\" value=\"([^\"]*)", page).group(1)
    return re.sub(rb'data-seen="[^"]*"', b'data-seen=""', page.replace(token, b''))


def staying_note(page):
    """The text of the note naming the transcendence runes that stay, or '' when the page has none."""
    found = re.search(r'id="export-transcendences-staying">(.*?)</p>', page.content.decode('utf-8'))
    return found.group(1) if found else ''


def no_scrolls():
    """Sends the export a char with no scroll, so a vitality total that crosses 100 is refused."""
    return mock.patch('chardata.dofusbook_export_view.get_stats_and_scrolled', return_value=({}, {}))


def piece_taking(type_name, key, stat_key, rank=1):
    """The first plain piece of that type that takes the variant and whose line takes the rune."""
    number = 0
    while True:
        found = piece(type_name, key, number)
        try:
            rune_for(found, stat_key, rank)
        except AssertionError:
            number += 1
            continue
        return found


def at_level(char, level):
    """The char as a low-level one, whose base vitality sits under their field's 100."""
    char.level = level
    char.save()
    return char


def refused_page(client, char, language='en'):
    """The export page of a char with no scroll."""
    with no_scrolls():
        return export_page(client, char, language=language)


def fields_of(page):
    """The decoded fields of the link on the page: [fm, points, level, exo bits, counts, ids]."""
    found = re.search(r'stuff=([^"&\'<> ]+)', page.content.decode('utf-8'))
    from chardata.tests_dofusbook_export import champs
    return champs(urllib.parse.unquote(found.group(1)))


class _TranscendedExport(TestCase):

    def setUp(self):
        self.addCleanup(set_current_game_version, VERSION)
        stand_in_runes(self)
        stand_in_transcendences(self)
        self.positions = dofusbook_export.index_by_stat_key()

    def total(self, forge, key):
        """The forgemagie their field holds for a characteristic: base and scroll taken off."""
        position = self.positions[key]
        value = forge[position] - dofusbook_export.character_base(200).get(position, 0)
        if position < dofusbook_export.BASE_STAT_COUNT and value >= dofusbook_export.SCROLL_STEP:
            value -= dofusbook_export.SCROLL_STEP
        return value


class TranscendenceTotalsTravelTests(_TranscendedExport):

    def test_a_rune_adds_its_bonus_to_the_forgemagie_total(self):
        hat = piece('Hat', RESISTANCE_KEY)
        char = worn_by(self.client, [hat])
        rune = rune_for(hat, 'int')
        transcend(char, [(hat, rune)])
        forge = forge_of(export_page(self.client, char))
        self.assertEqual(rune['bonus'], self.total(forge, 'int'))

    def test_a_rune_adds_to_the_forgemagie_already_sent(self):
        hat = piece('Hat', RESISTANCE_KEY)
        char = worn_by(self.client, [hat])
        rune = rune_for(hat, 'init')
        rolled = lines_of(hat)['init']
        set_stat_overrides(char, {hat.id: {structure().get_stat_by_key('init').id: rolled - 10}})
        transcend(char, [(hat, rune)])
        forge = forge_of(export_page(self.client, char))
        self.assertEqual(rune['bonus'] - 10, self.total(forge, 'init'))

    def test_a_transcended_and_draconized_piece_counts_each_rune_once(self):
        hat = piece('Hat', RESISTANCE_KEY)
        char = worn_by(self.client, [hat])
        rune = rune_for(hat, 'int')
        draconize(char, [(hat, RESISTANCE_KEY)])
        transcend(char, [(hat, rune)])
        forge = forge_of(export_page(self.client, char))
        moved = lines_of(hat)['neutresper']
        self.assertEqual(rune['bonus'], self.total(forge, 'int'))
        self.assertEqual(moved, self.total(forge, 'earthresper'))
        self.assertEqual(-moved, self.total(forge, 'neutresper'))

    def test_two_runes_on_two_pieces_add_up(self):
        hat = piece('Hat', RESISTANCE_KEY)
        cloak = piece('Cloak', RESISTANCE_KEY)
        char = worn_by(self.client, [hat, cloak])
        first, second = rune_for(hat, 'int'), rune_for(cloak, 'int', rank=2)
        transcend(char, [(hat, first), (cloak, second)])
        forge = forge_of(export_page(self.client, char))
        self.assertEqual(first['bonus'] + second['bonus'], self.total(forge, 'int'))

    def test_a_rune_on_a_piece_that_stays_home_sends_nothing(self):
        hat = piece('Hat', RESISTANCE_KEY)
        cloak = piece('Cloak', RESISTANCE_KEY)
        char = worn_by(self.client, [hat, cloak])
        transcend(char, [(hat, rune_for(hat, 'int')), (cloak, rune_for(cloak, 'str'))])
        known = [{'official': hat.ankama_id, 'effects': []}]
        forge = forge_of(export_page(self.client, char, known=known))
        self.assertEqual(0, self.total(forge, 'str'))
        self.assertNotEqual(0, self.total(forge, 'int'))

    def test_a_build_without_a_transcendence_rune_keeps_its_link_and_its_page_byte_for_byte(self):
        plain = piece('Hat', RESISTANCE_KEY)
        draconized = piece('Hat', RESISTANCE_KEY, number=1)
        plain_char = worn_by(self.client, [plain])
        dracorune_char = worn_by(self.client, [draconized])
        draconize(dracorune_char, [(draconized, RESISTANCE_KEY)])
        for char in (plain_char, dracorune_char):
            with without_transcendences():
                before = page_bytes(self.client, char)
            now = page_bytes(self.client, char)
            self.assertEqual(before, now)
            self.assertNotIn(b'export-transcendences', now)


class TranscendenceExoAndSummonTests(_TranscendedExport):

    def test_an_ap_rune_exports_as_the_ap_exo_flag(self):
        hat = piece('Hat', RESISTANCE_KEY)
        char = worn_by(self.client, [hat])
        with no_exo_option():
            before = fields_of(export_page(self.client, char))
            transcend(char, [(hat, rune_for(hat, 'ap', rank=4))])
            after = fields_of(export_page(self.client, char))
        self.assertEqual(0, before[3] & dofusbook_export.EXO_AP)
        self.assertEqual(dofusbook_export.EXO_AP, after[3] & dofusbook_export.EXO_AP)
        self.assertEqual(before[0][6], after[0][6])

    def test_an_mp_and_a_range_rune_export_as_their_flags(self):
        hat = piece('Hat', RESISTANCE_KEY)
        cloak = piece('Cloak', RESISTANCE_KEY)
        char = worn_by(self.client, [hat, cloak])
        transcend(char, [(hat, rune_for(hat, 'mp', rank=4)), (cloak, rune_for(cloak, 'range'))])
        with no_exo_option():
            flags = fields_of(export_page(self.client, char))[3]
        self.assertEqual(dofusbook_export.EXO_MP | dofusbook_export.EXO_RANGE, flags)

    def test_an_ap_rune_stays_when_the_build_already_has_the_ap_exo(self):
        hat = piece('Hat', RESISTANCE_KEY)
        char = worn_by(self.client, [hat])
        rune = rune_for(hat, 'ap', rank=4)
        transcend(char, [(hat, rune)])
        with exo_option(dofusbook_export.EXO_AP):
            page = export_page(self.client, char)
        self.assertEqual(dofusbook_export.EXO_AP, fields_of(page)[3])
        self.assertIn(rune['names']['en'], staying_note(page))
        self.assertNotIn('id="export-transcendences"', page.content.decode('utf-8'))

    def test_two_ap_runes_send_one_ap_exo_and_name_the_other(self):
        hat = piece('Hat', RESISTANCE_KEY)
        cloak = piece('Cloak', RESISTANCE_KEY)
        char = worn_by(self.client, [hat, cloak])
        transcend(char, [(hat, rune_for(hat, 'ap', rank=4)), (cloak, rune_for(cloak, 'ap', rank=4))])
        with no_exo_option():
            page = export_page(self.client, char)
        names = [structure().get_item_name_in_language(item, 'en') for item in (hat, cloak)]
        self.assertEqual(dofusbook_export.EXO_AP, fields_of(page)[3])
        self.assertEqual(1, sum('(%s)' % name in staying_note(page) for name in names))
        self.assertIn('id="export-transcendences"', page.content.decode('utf-8'))

    def test_an_mp_rune_still_travels_when_the_ap_exo_is_set(self):
        hat = piece('Hat', RESISTANCE_KEY)
        char = worn_by(self.client, [hat])
        transcend(char, [(hat, rune_for(hat, 'mp', rank=4))])
        with exo_option(dofusbook_export.EXO_AP):
            page = export_page(self.client, char)
        self.assertEqual(dofusbook_export.EXO_AP | dofusbook_export.EXO_MP, fields_of(page)[3])
        self.assertEqual('', staying_note(page))

    def test_an_ap_rune_worth_more_than_the_one_point_of_its_flag_stays(self):
        hat = piece('Hat', RESISTANCE_KEY)
        rune = rune_for(hat, 'ap', rank=4)
        flag = dofusbook_export.EXO_AP
        self.assertEqual(({}, flag), _transcendence_positions(
            SimpleNamespace(transcendence_rune=rune), self.positions))
        self.assertEqual((None, 0), _transcendence_positions(
            SimpleNamespace(transcendence_rune=dict(rune, bonus=2)), self.positions))

    def test_a_summon_rune_travels_at_the_summon_position(self):
        hat = piece('Hat', RESISTANCE_KEY)
        char = worn_by(self.client, [hat])
        transcend(char, [(hat, rune_for(hat, 'summon'))])
        forge = forge_of(export_page(self.client, char))
        self.assertEqual(11, self.positions['summon'])
        self.assertEqual(1, self.total(forge, 'summon'))


class TranscendenceRunesTheirFieldCannotCarryTests(_TranscendedExport):

    def setUp(self):
        super().setUp()
        self.hat = piece_taking('Hat', RESISTANCE_KEY, 'vit')
        self.rune = rune_for(self.hat, 'vit')
        self.char = at_level(worn_by(self.client, [self.hat]), 9)
        transcend(self.char, [(self.hat, self.rune)])

    def test_a_rune_dofusbook_refuses_is_named_staying(self):
        page = refused_page(self.client, self.char)
        text = page.content.decode('utf-8')
        self.assertEqual(dofusbook_export.character_base(9)[0], forge_of(page)[0])
        self.assertIn('export-transcendences-staying', text)
        self.assertIn('cannot carry these transcendence runes', text)
        name = self.rune['names']['en']
        self.assertIn('%s (%s)' % (name, structure().get_item_name_in_language(self.hat, 'en')), text)
        self.assertNotIn('export-dracorunes-staying', text)
        self.assertNotIn('id="export-transcendences"', text)

    def test_the_name_is_the_games_in_the_page_language(self):
        text = refused_page(self.client, self.char, language='fr').content.decode('utf-8')
        self.assertIn(self.rune['names']['fr'], text)
        self.assertIn('ne peut pas porter ces runes de transcendance', text)

    def test_the_rune_that_fits_still_travels_beside_the_one_that_does_not(self):
        cloak = piece('Cloak', RESISTANCE_KEY)
        char = at_level(worn_by(self.client, [self.hat, cloak]), 9)
        carried = rune_for(cloak, 'int')
        transcend(char, [(self.hat, self.rune), (cloak, carried)])
        page = refused_page(self.client, char)
        forge = forge_of(page)
        self.assertEqual(carried['bonus'], self.total(forge, 'int'))
        self.assertEqual(dofusbook_export.character_base(9)[0], forge[0])
        text = page.content.decode('utf-8')
        self.assertEqual(1, text.count(self.rune['names']['en']))
        self.assertIn('id="export-transcendences"', text)

    def test_a_refused_rune_stays_apart_from_a_refused_dracorune(self):
        hat = piece_taking('Hat', ELEMENT_KEY, 'vit')
        char = at_level(worn_by(self.client, [hat]), 9)
        draconize(char, [(hat, ELEMENT_KEY)])
        transcend(char, [(hat, rune_for(hat, 'vit'))])
        text = refused_page(self.client, char).content.decode('utf-8')
        self.assertIn('export-dracorunes-staying', text)
        self.assertIn('export-transcendences-staying', text)


class ThePageSaysTheRunesTravelTests(_TranscendedExport):

    def test_the_page_says_the_runes_travel_as_forgemagie(self):
        hat = piece('Hat', RESISTANCE_KEY)
        char = worn_by(self.client, [hat])
        transcend(char, [(hat, rune_for(hat, 'int'))])
        text = export_page(self.client, char).content.decode('utf-8')
        self.assertIn('id="export-transcendences"', text)
        self.assertIn('DofusBook has no field for transcendence runes: their lines travel in the global forgemagie.', text)
        self.assertNotIn('export-transcendences-staying', text)

    def test_the_sentence_comes_in_the_page_language(self):
        hat = piece('Hat', RESISTANCE_KEY)
        char = worn_by(self.client, [hat])
        transcend(char, [(hat, rune_for(hat, 'int'))])
        text = export_page(self.client, char, language='fr').content.decode('utf-8')
        self.assertIn('leurs lignes partent dans la forgemagie globale', text)
