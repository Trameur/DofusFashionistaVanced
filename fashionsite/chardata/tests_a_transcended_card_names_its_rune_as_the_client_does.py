# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A transcended card names its rune as each client does, in each language and version, and tells a Beta-only rune apart."""
import re
from unittest import mock

from django.test import SimpleTestCase
from django.utils.html import escape
from django.utils.translation import override

from chardata.transcendence_card_fixtures import (card_of, minimal_with, plain_pieces,
                                                  rune_of_stat)
from fashionistapulp.modelresult import model_result_from_minimal
from fashionistapulp.structure import get_structure, set_current_game_version

LANGUAGES = ('en', 'fr', 'de', 'es', 'pt')
VERSIONS = ('dofus3', 'beta', 'dofus2')
MARK = re.compile(r'<span class="solution-item-mark solution-item-transcendence-mark" '
                  r'id="transcendence-mark-hat" title="(?P<title>[^"]*)">(?P<text>[^<]*)</span>')


def expected_name(rune, language):
    return rune['names'].get(language) or rune['names'].get('en') or rune['names'].get('fr')


class ATranscendedCardNamesItsRuneAsTheClientDoesTests(SimpleTestCase):

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')

    def card(self, version, rune, language):
        set_current_game_version(version)
        hat = plain_pieces('Hat', version, 1, rune)[0]
        result = model_result_from_minimal(minimal_with({'hat': hat.id}, {'hat': (hat.id, rune['id'])}))
        with override(language):
            return card_of(result, 'hat')

    def test_the_mark_is_the_rune_name_in_each_language_and_version(self):
        for version in VERSIONS:
            rune = rune_of_stat('vit', version)
            for language in LANGUAGES:
                with self.subTest(version=version, language=language):
                    piece, page = self.card(version, rune, language)
                    mark = MARK.search(page)
                    self.assertIsNotNone(mark)
                    self.assertEqual(escape(expected_name(rune, language)), mark.group('text'))
                    self.assertEqual(escape(piece.transcendence_label), mark.group('title'))
                    self.assertTrue(piece.transcendence_label.startswith(expected_name(rune, language)))

    def test_a_beta_only_rune_shows_its_notice(self):
        rune = rune_of_stat('ap', 'beta', 4)
        self.assertTrue(rune['beta_only'])
        for language in LANGUAGES:
            with self.subTest(language=language):
                piece, page = self.card('beta', rune, language)
                self.assertEqual(rune['notice'][language], piece.transcendence_notice)
                self.assertIn('id="transcendence-hat">%s %s<' % (
                    escape(piece.transcendence_label), escape(rune['notice'][language])), page)

    def test_a_rune_of_every_client_shows_no_notice(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                piece, page = self.card(version, rune_of_stat('vit', version), 'en')
                self.assertIsNone(piece.transcendence_notice)
                self.assertIn('id="transcendence-hat">%s<' % escape(piece.transcendence_label), page)

    def test_the_label_is_the_rune_name_a_colon_and_the_line_it_adds(self):
        rune = rune_of_stat('vit')
        piece, _page = self.card('beta', rune, 'en')
        stat_name = get_structure('beta').get_stat_by_key('vit').name
        self.assertEqual('%s: +%d %s' % (expected_name(rune, 'en'), rune['bonus'], stat_name),
                         piece.transcendence_label)

    def test_the_label_goes_through_the_translation_for_its_format_and_its_stat_name(self):
        rune = rune_of_stat('vit')
        stat_name = get_structure('beta').get_stat_by_key('vit').name
        with mock.patch('chardata.solution_result._', side_effect=lambda text: '<%s>' % text):
            piece, _page = self.card('beta', rune, 'en')
        self.assertEqual('<%s: +%d <%s>>' % (expected_name(rune, 'en'), rune['bonus'], stat_name),
                         piece.transcendence_label)
