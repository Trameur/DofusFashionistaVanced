# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The smithmagic page of the modern design: it fills the shell instead of a column, its cards sit in two columns from 1100 pixels, its section titles carry the display font over a dashed seam, every control is a 44 pixel target, its tables scroll inside their card on a phone with the stat column pinned, the roll colours read on both themes, the page carries the opt-in class, the static inline styles moved to classes, and every new rule is prefixed by the modern class so the classic design is untouched."""
import io
import os
import re

from django.test import SimpleTestCase

from chardata.tests_the_setup_stylesheet_support import STATIC, chain_of, parse, stylesheet, winning

MODERN = 'modern.css'
TEMPLATES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates', 'chardata')
MODERN_LIVE = ['fm-modern', 'fm-light']
MODERN_DARK = ['fm-modern', 'fm-dark']
CLASSIC_LIVE = ['fm-light']
MARKER = '/* ---------- Tools: smithmagic ---------- */'

SHEETS = [(name, stylesheet(name)) for name in ('forms.css', 'responsive.css', 'forgemagie.css', MODERN)]

ROOT = ('div', {'class': 'fm-page text tools-atelier', 'id': 'fm-page'})
BOX = ('div', {'class': 'fm-box brown-box'})
WRAPPER = ('div', {'class': 'fm-table-wrapper'})
TABLE = ('table', {'class': 'fm-table'})
PAGE_RULE = 'html.fm-modern .fm-page.tools-atelier'


def template():
    with io.open(os.path.join(TEMPLATES, 'forgemagie.html'), encoding='utf-8') as handle:
        return handle.read()


def value(ancestors, element, prop, width, classes=MODERN_LIVE):
    found = winning(SHEETS, chain_of([('html', {})] + ancestors, element[0], element[1], classes), prop, width)
    return None if found is None else found[0]


def rules_after_the_marker():
    with io.open(os.path.join(STATIC, MODERN), encoding='utf-8') as handle:
        source = handle.read()
    return parse(re.sub(r'/\*.*?\*/', '', source[source.index(MARKER):], flags=re.S))


class TheSmithmagicPageFillsTheShellAndPairsItsReadingCardsTests(SimpleTestCase):

    def test_the_page_is_a_grid_of_one_column_on_a_phone_and_two_from_1100_pixels(self):
        columns = {rule['media']: rule['declarations']['grid-template-columns'][0].replace(' ', '')
                   for rule in rules_after_the_marker()
                   if PAGE_RULE in rule['selectors'] and 'grid-template-columns' in rule['declarations']}
        self.assertEqual('minmax(0,1fr)', columns[None])
        self.assertEqual('repeat(2,minmax(0,1fr))', columns['(min-width:1100px)'])

    def test_the_page_is_not_held_to_a_column(self):
        self.assertEqual('none', value([], ROOT, 'max-width', 1920))
        self.assertEqual('100%', value([], ROOT, 'max-width', 1920, CLASSIC_LIVE))

    def test_the_boxes_span_the_page_but_the_two_reading_cards_share_a_row(self):
        declared = {selector: rule['declarations']['grid-column'][0]
                    for rule in rules_after_the_marker() if rule['media'] == '(min-width:1100px)'
                    for selector in rule['selectors'] if 'grid-column' in rule['declarations']}
        self.assertEqual('1 / -1', declared[PAGE_RULE + ' > *'])
        self.assertEqual('auto', declared[PAGE_RULE + ' > .fm-how + .fm-how'])

    def test_the_section_titles_are_in_the_display_font_over_a_dashed_seam(self):
        title = ('div', {'class': 'fm-section-title big-text'})
        self.assertEqual('var(--fm-font-display)', value([ROOT, BOX], title, 'font-family', 1280))
        self.assertEqual('1px dashed var(--fm-seam)', value([ROOT, BOX], title, 'border-bottom', 1280))
        self.assertIsNone(value([ROOT, BOX], title, 'font-family', 1280, CLASSIC_LIVE))

    def test_the_item_icon_sits_in_a_loot_frame_in_modern_only(self):
        icon = ('img', {'id': 'fm-item-image'})
        header = ('div', {'class': 'fm-item-header'})
        self.assertEqual('2px solid var(--fm-frame-gold)', value([ROOT, BOX, header], icon, 'border', 1280))
        self.assertIsNone(value([ROOT, BOX, header], icon, 'border', 1280, CLASSIC_LIVE))


class EveryControlOfTheSmithmagicPageIsA44PixelTargetTests(SimpleTestCase):

    def test_the_buttons_inputs_and_selects(self):
        row = ('div', {'class': 'fm-exo-row'})
        cell = ('td', {})
        search = ('div', {'class': 'fm-search-wrapper'})
        for ancestors, element in (([ROOT, BOX, row], ('button', {'class': 'button-thin'})),
                                   ([ROOT, BOX, row], ('button', {'class': 'button-generic'})),
                                   ([ROOT, BOX, row], ('select', {'class': 'pretty-input'})),
                                   ([ROOT, BOX, row], ('input', {'class': 'pretty-input fm-kamas-input'})),
                                   ([ROOT, BOX, search], ('input', {'class': 'pretty-input', 'id': 'fm-search'})),
                                   ([ROOT, BOX, WRAPPER, TABLE, cell], ('input', {'class': 'pretty-input fm-input'})),
                                   ([ROOT, BOX, WRAPPER, TABLE, cell], ('button', {'class': 'button-thin fm-sac-btn'})),
                                   ([ROOT, BOX, WRAPPER, TABLE, cell], ('button', {'class': 'button-thin fm-remove-btn'})),
                                   ([ROOT, BOX], ('div', {'class': 'fm-search-result'})),
                                   ([ROOT, BOX], ('span', {'class': 'fm-trans-opt'})),
                                   ([ROOT, BOX], ('label', {'class': 'small-explain fm-inventory-toggle'}))):
            for width in (375, 1920):
                self.assertEqual('44px', value(ancestors, element, 'min-height', width), element)

    def test_the_workbench_inputs_are_wide_enough_for_four_digits(self):
        element = ('input', {'class': 'pretty-input fm-input'})
        self.assertEqual('72px', value([ROOT, BOX, WRAPPER, TABLE, ('td', {})], element, 'width', 1280))


class TheSmithmagicTablesScrollInsideTheirCardOnAPhoneTests(SimpleTestCase):

    def test_the_tables_keep_a_width_that_reads_instead_of_breaking_words_letter_by_letter(self):
        self.assertEqual('560px', value([ROOT, BOX, WRAPPER], TABLE, 'min-width', 375))
        for width in (700, 768, 900):
            self.assertEqual('560px', value([ROOT, BOX, WRAPPER], TABLE, 'min-width', width), width)
            self.assertEqual('auto', value([ROOT, BOX, WRAPPER], TABLE, 'table-layout', width), width)
            self.assertEqual('normal', value([ROOT, BOX, WRAPPER, TABLE], ('td', {}), 'word-break', width), width)
            self.assertEqual('normal', value([ROOT, BOX, WRAPPER, TABLE], ('td', {}), 'overflow-wrap', width), width)
            self.assertEqual('.92rem', value([ROOT, BOX, WRAPPER, TABLE], ('td', {}), 'font-size', width), width)
        self.assertIsNone(value([ROOT, BOX, WRAPPER], TABLE, 'table-layout', 901))
        self.assertIsNone(value([ROOT, BOX, WRAPPER], TABLE, 'min-width', 1280))
        self.assertEqual('auto', value([ROOT, BOX, WRAPPER], TABLE, 'table-layout', 375))
        self.assertEqual('fixed', value([ROOT, BOX, WRAPPER], TABLE, 'table-layout', 375, CLASSIC_LIVE))

    def test_the_cells_do_not_wrap_except_the_rune_column(self):
        self.assertEqual('nowrap', value([ROOT, BOX, WRAPPER, TABLE], ('td', {}), 'white-space', 375))
        self.assertEqual('normal', value([ROOT, BOX, WRAPPER, TABLE], ('td', {'class': 'fm-cell-runes'}), 'white-space', 375))

    def test_the_stat_column_stays_pinned_while_the_table_scrolls(self):
        selectors = ' '.join(selector for rule in rules_after_the_marker() if rule['media'] is None
                             for selector in rule['selectors'])
        self.assertIn('.fm-table tbody td:first-child', selectors)
        pinned = [rule['declarations'] for rule in rules_after_the_marker() if rule['media'] is None
                  and any(selector.endswith('.fm-table thead th:first-child') for selector in rule['selectors'])]
        self.assertEqual('sticky', pinned[0]['position'][0])


class TheRollColoursReadOnBothModernThemesTests(SimpleTestCase):

    def test_the_success_failure_and_warning_colours_are_re_tinted_per_theme(self):
        for classes, ok, bad, warn in ((MODERN_LIVE, 'var(--fm-ok)', 'var(--fm-bad)', 'var(--fm-warn)'),
                                       (MODERN_DARK, 'var(--fm-ok)', 'var(--fm-bad)', '#e0a458')):
            self.assertEqual(ok, value([ROOT], ('td', {'class': 'fm-ok'}), 'color', 1280, classes))
            self.assertEqual(bad, value([ROOT], ('td', {'class': 'fm-bad'}), 'color', 1280, classes))
            self.assertEqual(warn, value([ROOT], ('p', {'class': 'fm-warn'}), 'color', 1280, classes))

    def test_the_quality_label_colours_the_script_writes_inline_are_overridden_on_both_themes(self):
        source = ' '.join(selector for rule in rules_after_the_marker() for selector in rule['selectors'])
        for red in ('142', '201', '46', '124', '178', '214'):
            for theme in ('fm-light', 'fm-dark'):
                wanted = 'html.fm-modern.%s .fm-page.tools-atelier .fm-quality-label span[style*="%s"]' % (theme, red)
                self.assertIn(wanted, source)

    def test_a_transcendence_option_the_script_dims_is_marked_by_more_than_its_opacity(self):
        dimmed = [rule for rule in rules_after_the_marker()
                  if any('.fm-trans-opt[style*="opacity"]' in selector for selector in rule['selectors'])]
        self.assertEqual(1, len(dimmed))
        self.assertEqual('dashed', dimmed[0]['declarations']['border-style'][0])
        self.assertEqual('1', dimmed[0]['declarations']['opacity'][0])


class TheSmithmagicPageCarriesTheOptInClassAndNoStaticInlineStyleTests(SimpleTestCase):

    def test_the_root_carries_the_opt_in_class(self):
        self.assertIn('<div class="fm-page text tools-atelier" id="fm-page">', template())

    def test_the_inline_styles_left_are_the_ones_a_script_toggles(self):
        tags = re.findall(r'<[a-z][^>]*\sstyle="[^"]*"[^>]*>', template())
        self.assertGreater(len(tags), 10)
        for tag in tags:
            self.assertRegex(tag, r'style="display:none;?"', tag)

    def test_the_moved_styles_keep_their_classic_values(self):
        sheet = stylesheet('forgemagie.css')
        for selector, prop, expected in (('.fm-page label.fm-inventory-toggle', 'margin-top', '4px'),
                                         ('.fm-page label.fm-inventory-toggle', 'display', 'block'),
                                         ('.fm-page label.fm-inventory-toggle', 'cursor', 'pointer'),
                                         ('.fm-exo-row .fm-new-folder-input', 'width', '180px'),
                                         ('.fm-section-title.fm-section-title-spaced', 'margin-top', '12px')):
            rules = [rule for rule in sheet if selector in rule['selectors']]
            self.assertEqual(1, len(rules), selector)
            self.assertEqual(expected, rules[0]['declarations'][prop][0])

    def test_every_selector_after_the_marker_starts_with_the_modern_prefix(self):
        rules = rules_after_the_marker()
        self.assertGreater(len(rules), 60)
        for rule in rules:
            for selector in rule['selectors']:
                self.assertTrue(selector.startswith('html.fm-modern'), selector)
