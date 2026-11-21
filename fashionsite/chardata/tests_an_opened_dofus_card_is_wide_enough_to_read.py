# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""An opened Dofus or trophy card takes several columns of its row, so its stats and buttons stay inside it."""
import os
import re

from django.test import SimpleTestCase

from chardata.tests_the_setup_stylesheet_support import declared, read_css, stylesheet

PARTS = stylesheet('modern-solution-parts.css')
ROW = 'html.fm-modern .solution-item-section:not(.fm-sol-doll)'
OPEN = ROW + ' .expand-container.fm-open'
TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates', 'chardata', 'solution.html')


def script_function(name):
    with open(TEMPLATE, encoding='utf-8') as page:
        source = page.read()
    return re.search(r'function %s\(.*?\n        }\n' % name, source, re.S).group(0)


class AnOpenedDofusCardTests(SimpleTestCase):

    def test_an_open_card_spans_three_columns_and_two_on_a_wide_row(self):
        self.assertEqual('span 3', declared(PARTS, OPEN, 'grid-column')[0])
        self.assertEqual('fm-row / inline-size', declared(PARTS, ROW, 'container')[0])
        wide = re.search(r'@container fm-row \(min-width:700px\)\{(?P<rule>.*?)\n\}', read_css('modern-solution-parts.css'), re.S)
        self.assertIn(OPEN + '{ grid-column:span 2; }', wide.group('rule'))

    def test_the_closed_cards_beside_it_keep_their_own_height(self):
        busy = ROW + ':has(.expand-container.fm-open)'
        self.assertEqual('start', declared(PARTS, busy, 'align-items')[0])
        self.assertEqual('row dense', declared(PARTS, busy, 'grid-auto-flow')[0])
        self.assertEqual('0 0 auto', declared(
            PARTS, 'html.fm-modern .solution-item-section .expand-container.fm-open > .solution-item-expand-header', 'flex')[0])

    def test_a_button_in_an_open_card_wraps_inside_it(self):
        button = 'html.fm-modern .solution-item-expand-content .button-generic'
        self.assertEqual('100%', declared(PARTS, button, 'max-width')[0])
        self.assertEqual('normal', declared(PARTS, button, 'white-space')[0])

    def test_every_way_of_opening_a_card_marks_it_open_and_every_way_of_closing_unmarks_it(self):
        for opener in ('toggle_expand', 'expand_expand'):
            with self.subTest(opener=opener):
                self.assertIn("$header.parent().addClass('fm-open');", script_function(opener))
        self.assertIn("$header.parent().toggleClass('fm-open', $content.is(':visible'));", script_function('toggle_expand'))
        self.assertIn("$header.parent().removeClass('fm-open');", script_function('collapse_expand'))

    def test_a_card_closing_while_another_opens_unmarks_itself_and_not_the_other(self):
        for function in ('toggle_expand', 'expand_expand', 'collapse_expand'):
            with self.subTest(function=function):
                self.assertIn('var $content = $header.next();', script_function(function))
        self.assertIn('var $header = $(this);', script_function('toggle_expand'))
