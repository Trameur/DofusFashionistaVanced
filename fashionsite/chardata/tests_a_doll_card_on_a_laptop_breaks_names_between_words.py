# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""On a laptop the item column is too narrow for an icon beside the name, so each piece of the doll shows its icon above its name and no word is cut."""
import re

from django.test import SimpleTestCase

from chardata.tests_the_setup_stylesheet_support import declared, read_css, stylesheet

PARTS = stylesheet('modern-solution-parts.css')
NARROW = re.compile(r'@media \(min-width:760px\)\{\s*@container fm-items \(max-width:699px\)\{(?P<rules>.*?)\n  \}\n\}', re.S)


class ADollCardOnALaptopTests(SimpleTestCase):

    def narrow_rules(self):
        return NARROW.search(read_css('modern-solution-parts.css')).group('rules')

    def test_the_item_column_is_the_container_the_rule_measures(self):
        self.assertEqual('fm-items / inline-size',
                         declared(PARTS, 'html.fm-modern .solution-table .solution-item-summary', 'container')[0])

    def test_a_narrow_column_stacks_the_icon_above_the_name(self):
        rules = self.narrow_rules()
        self.assertIn('.fm-sol-doll .solution-item-expand-header > table > tbody > tr{ display:flex; flex-direction:column;', rules)
        self.assertIn('.fm-sol-doll .solution-item-expand-header td:first-child{ align-self:center; }', rules)
        self.assertIn('.fm-sol-doll .solution-item-name-div{ justify-content:center; text-align:center; padding-right:0; }', rules)

    def test_a_short_card_starts_at_the_top_like_its_neighbours(self):
        self.assertIn('.solution-table .solution-item-section.fm-sol-doll .expand-container > .solution-item-expand-header{ align-items:flex-start; }',
                      self.narrow_rules())

    def test_a_set_chip_stays_on_one_line_and_keeps_its_count_whole(self):
        chip = 'html.fm-modern .solution-item-name-div :is(.fm-set-tag,.fm-set-tag-name)'
        self.assertEqual(('nowrap', True), declared(PARTS, chip, 'white-space'))
