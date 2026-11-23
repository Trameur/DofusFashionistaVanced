# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Every count field of the Atelier options page keeps one 80 px width and a 44 px height up to 900 px, and the two classic designs keep their 60 px rule."""
import io
import os
import re

from django.test import SimpleTestCase

STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'chardata')
TEMPLATES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates', 'chardata')
PHONE = re.compile(r'@media \(max-width:900px\)\{(.*?)\n\}', re.S)
FIELD = 'html.fm-modern .tunnel-options .pretty-input.exo-count-input'
ROW = 'html.fm-modern .tunnel-options label:has(> .exo-count-input)'


def read(folder, name):
    with io.open(os.path.join(folder, name), encoding='utf-8') as handle:
        return handle.read().replace('\r\n', '\n')


def phone_blocks(sheet):
    return [block for block in PHONE.findall(read(STATIC, sheet)) if FIELD in block]


class TheAtelierCountFieldsShareOneWidthTests(SimpleTestCase):

    def test_the_source_sheet_and_the_built_sheet_carry_one_phone_block(self):
        for sheet in ('modern.css', 'modern-rest.css'):
            self.assertEqual(len(phone_blocks(sheet)), 1, sheet)

    def test_a_count_field_is_80_px_wide_and_44_px_tall_whatever_its_label(self):
        block = phone_blocks('modern.css')[0]
        rule = re.search(re.escape(FIELD) + r'\{([^}]*)\}', block).group(1)
        self.assertIn('width:5rem !important', rule)
        self.assertIn('min-height:44px', rule)
        self.assertIn('flex:none', rule)

    def test_the_label_is_a_row_that_centres_its_text_on_the_field(self):
        block = phone_blocks('modern.css')[0]
        rule = re.search(re.escape(ROW) + r'\{([^}]*)\}', block).group(1)
        self.assertIn('display:flex', rule)
        self.assertIn('align-items:center', rule)

    def test_every_count_field_of_the_options_page_is_one_the_rule_reaches(self):
        for name in ('options.html', 'dracorune_option.html', 'transcendence_option.html'):
            text = read(TEMPLATES, name)
            for field in re.findall(r'<input[^>]*type="number"[^>]*>', text):
                self.assertIn('pretty-input', field, name)
                self.assertIn('exo-count-input', field, name)
            self.assertIn('<label>', text.replace('<label class="setup-more-count">', ''), name)

    def test_the_line_break_after_a_count_label_is_hidden_so_no_card_grows_an_empty_line(self):
        block = phone_blocks('modern.css')[0]
        self.assertIn('html.fm-modern .tunnel-options label:has(> .exo-count-input) + br{ display:none; }', block)
        self.assertIn('<br>', read(TEMPLATES, 'options.html'))

    def test_the_two_classic_designs_keep_their_60_px_rule(self):
        text = read(STATIC, 'responsive.css')
        self.assertIn('html:not(.fm-modern, .fm-enhanced) .pretty-input.exo-count-input, html.fm-enhanced .pretty-input.exo-count-input { width: 60px !important; }', text)

    def test_no_rule_of_the_phone_block_reaches_the_classic_designs(self):
        for line in phone_blocks('modern.css')[0].splitlines():
            if '{' in line:
                self.assertTrue(line.strip().startswith('html.fm-modern '), line)
