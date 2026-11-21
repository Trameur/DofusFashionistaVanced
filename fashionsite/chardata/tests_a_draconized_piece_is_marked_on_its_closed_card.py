# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A piece wearing a Dracorune carries a mark on its card header, seen before the item is opened: the rune's game name, the full line as its title."""
import re

from django.template.loader import render_to_string
from django.utils.html import escape
from django.utils.translation import override

from chardata.dracorune_fixtures import BetaModelTestCase, eligible_items, element_key, element_move, runes
from chardata.solution_result import SolutionResult
from chardata.tests_the_build_page_shows_the_draconized_lines import lines_of, minimal_for
from fashionistapulp import dracorunes
from fashionistapulp.modelresult import model_result_from_minimal

LANGUAGES = ('en', 'fr', 'de', 'es', 'pt')
FALLBACK = {'en': 'Dracorune', 'fr': 'Dracorune', 'de': 'Drachenrune', 'es': 'Dracorruna', 'pt': 'Dracorruna'}
MARK = re.compile(r'<span class="solution-item-mark solution-item-dracorune-mark" id="dracorune-mark-hat" '
                  r'title="(?P<title>[^"]*)">(?P<text>[^<]*)</span>')


def header_and_content(page):
    """The card header the player sees closed, and the content that opens under it."""
    start = page.index('expand-content')
    return page[:start], page[start:]


class ADraconizedPieceIsMarkedOnItsClosedCardTests(BetaModelTestCase):

    def setUp(self):
        super().setUp()
        source, target = element_move()
        self.key = element_key(source, target)
        self.hat = next(item for item in eligible_items('Hat')
                        if lines_of(item).get(source, 0) > 0
                        and self.key in dict(dracorunes.variants(list(lines_of(item).items()), runes())))
        self.rune = dracorunes.rune_of(self.key, runes())

    def card(self, saved_runes, rename=None):
        result = model_result_from_minimal(minimal_for({'hat': self.hat.id}, saved_runes))
        if rename is not None:
            for item in result.item_list:
                if item.dracorune:
                    item.dracorune['name'] = rename
        piece = next(item for item in SolutionResult(result).get_params()['all_items'] if item.slot == 'hat')
        return piece, render_to_string('chardata/solution_item.html', {'item': piece})

    def test_the_closed_card_names_the_rune_and_titles_the_full_line_in_five_languages(self):
        for language in LANGUAGES:
            with override(language):
                piece, page = self.card({'hat': (self.hat.id, self.key)})
            header, _content = header_and_content(page)
            mark = MARK.search(header)
            self.assertIsNotNone(mark, language)
            self.assertEqual(escape(self.rune['names'][language]), mark.group('text'), language)
            self.assertEqual(escape(piece.dracorune_label), mark.group('title'), language)

    def test_the_opened_card_still_shows_the_full_line(self):
        piece, page = self.card({'hat': (self.hat.id, self.key)})
        _header, content = header_and_content(page)
        self.assertIn('id="dracorune-hat">%s<' % escape(piece.dracorune_label), content)

    def test_a_rune_without_a_game_name_is_marked_with_the_word_in_five_languages(self):
        for language in LANGUAGES:
            with override(language):
                piece, page = self.card({'hat': (self.hat.id, self.key)}, rename='')
            mark = MARK.search(header_and_content(page)[0])
            self.assertIsNotNone(mark, language)
            self.assertEqual(FALLBACK[language], mark.group('text'), language)
            self.assertEqual(escape(piece.dracorune_label), mark.group('title'), language)

    def test_a_piece_without_a_rune_carries_no_mark(self):
        _piece, page = self.card(None)
        self.assertNotIn('solution-item-dracorune-mark', page)
