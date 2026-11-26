# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The compare page: the Atelier stat rows keep one column per set under their header, the Classic light note is readable on its dark panel, and both Classic designs stack and scroll their tables on a phone."""
import io
import os
import re

from django.test import SimpleTestCase

from chardata.tests_the_setup_stylesheet_support import STATIC, chain_of, declared, stylesheet, winning

SHEETS = [(name, stylesheet(name)) for name in ('forms.css', 'solution.css', 'compare.css', 'compare_lighttheme.css')]
PAGE = [('html', {}), ('table', {'class': 'compare-page'}), ('tbody', {}), ('tr', {})]
STAT_TABLE = ('table', {'class': 'solution-stat-table'})
NOTE = ('td', {'class': 'compare-best-turn-note'})
TITLE = ('td', {'class': 'compare-spell-preview-title'})
TARGET = ('td', {'class': 'compare-target-cell'})
CLASSIC = ['fm-light']
FOUR_SETS = ':has(> :nth-child(6))'
ROW_CELLS = ('html.fm-modern .compare-page .solution-stat-table > tbody > tr.solution-stat-summary-line:not(.fm-stat-group)')


def source(name):
    with io.open(os.path.join(STATIC, name), encoding='utf-8') as handle:
        return handle.read()


def value(classes, element, prop, width):
    found = winning(SHEETS, chain_of(PAGE, element[0], element[1], classes), prop, width)
    return None if found is None else found[0]


class TheAtelierCompareRowsKeepOneColumnPerSetTests(SimpleTestCase):

    MODERN = [('modern.css', stylesheet('modern.css'))]
    ROW = [('html', {}), ('table', {'class': 'compare-page'}), ('tbody', {}), ('tr', {}), ('td', {}),
           ('table', {'class': 'solution-stat-table'}), ('tbody', {})]

    def band(self, selector, prop, media='(max-width:500px)'):
        found = declared(self.MODERN[0][1], selector, prop, media)
        return None if found is None else found[0]

    def find(self, prop, tag='tr', attrs=None, parent=None, width=375):
        chain = chain_of(self.ROW + (parent or []), tag, attrs or {'class': 'solution-stat-summary-line'}, ['fm-modern', 'fm-light'])
        found = winning(self.MODERN, chain, prop, width)
        return None if found is None else found[0]

    def test_the_stat_rows_and_the_header_row_share_fixed_value_columns(self):
        self.assertEqual('20px minmax(0,1fr)', self.find('grid-template-columns', width=501))
        self.assertEqual('column', self.find('grid-auto-flow', width=501))
        self.assertEqual('20px repeat(var(--n),minmax(0,1fr))', self.find('grid-template-columns'))
        self.assertEqual('row', self.find('grid-auto-flow'))

    def test_the_value_cells_take_the_track_width(self):
        row = [('tr', {'class': 'solution-stat-summary-line'})]
        for tag in ('td', 'th'):
            self.assertEqual('auto', self.find('width', tag, {'align': 'center'}, row))
            self.assertEqual('0', self.find('min-width', tag, {'align': 'center'}, row))

    def test_the_built_sheet_carries_the_rule(self):
        built = source('modern-rest.css')
        self.assertIn('grid-auto-columns:76px', built)
        self.assertNotIn('grid-auto-columns:58px', built)
        self.assertIn('grid-template-columns:20px repeat(var(--n),minmax(0,1fr))', built)
        self.assertIn('overflow-wrap:anywhere', built)
        self.assertIn('@media (max-width:400px){', built)
        self.assertIn('grid-template-columns:repeat(4,minmax(0,1fr))', built)
        self.assertIn('hyphens:auto', built)

    def test_above_a_phone_the_value_columns_are_a_fixed_length(self):
        row = chain_of(self.ROW, 'tr', {'class': 'solution-stat-summary-line'}, ['fm-modern', 'fm-light'])
        for width in (501, 760, 900, 1366):
            self.assertEqual('76px', winning(self.MODERN, row, 'grid-auto-columns', width)[0], width)
        for width in (320, 375, 480, 500):
            self.assertIsNone(winning(self.MODERN, row, 'grid-auto-columns', width), width)

    def test_a_phone_gives_the_name_its_own_line_above_the_values(self):
        self.assertEqual('2 / -1', self.band(ROW_CELLS + ' > :nth-child(2)', 'grid-column'))
        self.assertEqual('2', self.band(ROW_CELLS + ' > :nth-child(3)', 'grid-column'))
        self.assertEqual('row', self.band(ROW_CELLS, 'grid-auto-flow'))

    def test_a_phone_shares_the_row_between_the_value_cells_in_equal_tracks(self):
        self.assertEqual('20px repeat(var(--n),minmax(0,1fr))', self.band(ROW_CELLS, 'grid-template-columns'))
        self.assertEqual('3', self.band(ROW_CELLS, '--n'))
        self.assertEqual('4', self.band(ROW_CELLS + ':has(> :nth-child(6))', '--n'))

    def test_four_sets_keep_the_stacked_rows_a_little_wider_than_three(self):
        media = '(min-width:501px) and (max-width:560px)'
        four = ROW_CELLS + ':has(> :nth-child(6))'
        self.assertEqual('4', self.band(four, '--n', media))
        self.assertEqual('20px repeat(var(--n),minmax(0,1fr))', self.band(four, 'grid-template-columns', media))
        self.assertEqual('2 / -1', self.band(four + ' > :nth-child(2)', 'grid-column', media))
        self.assertEqual('2', self.band(four + ' > :nth-child(3)', 'grid-column', media))
        self.assertEqual('none', self.band(four + ':has(> th[scope="col"]) > :nth-child(-n+2)', 'display', media))
        self.assertEqual('row', self.band(four, 'grid-auto-flow', media))
        for tag in ('td', 'th'):
            label = four + ' > ' + tag + '[align="center"] > b'
            self.assertEqual('normal', self.band(label, 'white-space', media))
            self.assertEqual('block', self.band(label, 'display', media))
            self.assertEqual('break-word', self.band(label, 'overflow-wrap', media))
            self.assertEqual('3px 1px', self.band(four + ' > ' + tag + '[align="center"]', 'padding', media))
        self.assertIsNone(self.band(ROW_CELLS, 'grid-template-columns', media))

    def test_four_sets_on_a_small_phone_start_the_value_tracks_under_the_icon(self):
        media = '(max-width:400px)'
        four = ROW_CELLS + ':has(> :nth-child(6))'
        self.assertEqual('repeat(4,minmax(0,1fr))', self.band(four, 'grid-template-columns', media))
        self.assertEqual('1', self.band(four + ' > :nth-child(3)', 'grid-column', media))
        self.assertEqual('1 / -1', self.band(four + ' > :nth-child(2)', 'grid-column', media))
        self.assertEqual('24px', self.band(four + ' > :nth-child(2)', 'margin-left', media))
        self.assertEqual('1', self.band(four + ' > :nth-child(2)', 'grid-row', media))
        self.assertEqual('1', self.band(four + ' > :nth-child(1)', 'grid-column', media))
        self.assertEqual('1', self.band(four + ' > :nth-child(1)', 'grid-row', media))
        self.assertEqual('20px', self.band(four + ' > :nth-child(1)', 'width', media))

    def four_sets(self):
        stripped = []
        for rule in self.MODERN[0][1]:
            copy = dict(rule)
            copy['selectors'] = [selector.replace(FOUR_SETS, '') for selector in rule['selectors']]
            stripped.append(copy)
        return [('modern.css', stripped)]

    def crit_chain(self):
        row = [('tr', {'class': 'solution-stat-summary-line'}), ('td', {'class': 'solution-stat-summary-value-cell'})]
        return chain_of(self.ROW + row, 'span', {'class': 'small-text'}, ['fm-modern', 'fm-light'])

    def note_chain(self):
        row = [('tr', {'class': 'solution-stat-summary-line'}), ('td', {'class': 'solution-stat-summary-value-cell'})]
        return chain_of(self.ROW + row, 'div', {'class': 'small-text'}, ['fm-modern', 'fm-light'])

    def test_four_sets_shrink_the_crit_line_smoothly_so_five_digits_fit_one_line(self):
        sheets = self.four_sets()
        for width in (401, 414, 500, 501, 760, 1366):
            self.assertIsNone(winning(sheets, self.crit_chain(), 'font-size', width), width)
        sizes = {}
        for width in (320, 330, 346, 347, 360, 375, 390, 400):
            found = winning(sheets, self.crit_chain(), 'font-size', width)
            self.assertIsNotNone(found, width)
            match = re.fullmatch(r'clamp\((\d+)px,calc\(\(100vw - (\d+)px\)\*([.\d]+)\),1em\)', found[0])
            self.assertIsNotNone(match, found[0])
            floor, overhead, slope = int(match.group(1)), int(match.group(2)), float(match.group(3))
            sizes[width] = min(15.0, max(float(floor), (width - overhead) * slope))
            cell = (width - 86) / 4.0
            self.assertLessEqual(sizes[width] * 72.52 / 15.0, cell - 1, width)
            self.assertIsNone(winning(sheets, self.crit_chain(), 'white-space', width), width)
        self.assertEqual(15.0, sizes[400])
        widths = sorted(sizes)
        for narrow, wide in zip(widths, widths[1:]):
            self.assertLessEqual(sizes[wide] - sizes[narrow], 0.06 * (wide - narrow) + 0.001, (narrow, wide))
        self.assertGreaterEqual(sizes[320], 11.0)

    def test_three_sets_keep_the_crit_line_at_the_size_of_the_value(self):
        for width in (320, 346, 347, 375, 400, 401, 500, 760):
            self.assertIsNone(winning(self.MODERN, self.crit_chain(), 'font-size', width), width)
            self.assertIsNone(winning(self.MODERN, self.crit_chain(), 'white-space', width), width)

    def test_an_item_note_under_a_value_wraps_anywhere_in_its_cell_at_every_width(self):
        for sheets in (self.MODERN, self.four_sets()):
            for width in (320, 346, 347, 375, 414, 500, 760, 1366):
                chain = self.note_chain()
                self.assertEqual('anywhere', winning(sheets, chain, 'overflow-wrap', width)[0], width)
                self.assertIsNone(winning(sheets, chain, 'white-space', width), width)
                self.assertIsNone(winning(sheets, chain, 'font-size', width), width)

    def test_four_sets_on_a_phone_keep_one_gap_and_one_padding_in_every_band(self):
        row = chain_of(self.ROW, 'tr', {'class': 'solution-stat-summary-line'}, ['fm-modern', 'fm-light'])
        parent = [('tr', {'class': 'solution-stat-summary-line'})]
        four = ROW_CELLS + ':has(> :nth-child(6))'
        for width in (320, 346, 375, 400, 401, 500):
            self.assertEqual('4px', winning(self.MODERN, row, 'column-gap', width)[0], width)
            self.assertEqual('2px', winning(self.MODERN, row, 'row-gap', width)[0], width)
            for tag in ('td', 'th'):
                cell = chain_of(self.ROW + parent, tag, {'align': 'center'}, ['fm-modern', 'fm-light'])
                self.assertEqual('3px 1px', winning(self.MODERN, cell, 'padding', width)[0], (tag, width))
        for prop in ('column-gap', 'row-gap'):
            self.assertIsNone(self.band(four, prop, '(max-width:400px)'))
        for tag in ('td', 'th'):
            self.assertIsNone(self.band(four + ' > ' + tag + '[align="center"]', 'padding', '(max-width:400px)'))

    def test_three_sets_and_the_wider_phones_keep_the_shared_first_column(self):
        for media in ('(max-width:400px)',):
            self.assertIsNone(self.band(ROW_CELLS, 'grid-template-columns', media))
            self.assertIsNone(self.band(ROW_CELLS + ' > :nth-child(3)', 'grid-column', media))
            self.assertIsNone(self.band(ROW_CELLS + ' .small-text', 'white-space', media))
        row = chain_of(self.ROW, 'tr', {'class': 'solution-stat-summary-line'}, ['fm-modern', 'fm-light'])
        for width in (401, 414, 500):
            self.assertEqual('20px repeat(var(--n),minmax(0,1fr))', winning(self.MODERN, row, 'grid-template-columns', width)[0], width)

    def test_the_header_labels_hyphenate_a_word_that_is_too_long_for_its_track(self):
        sheet = self.MODERN[0][1]
        for tag in ('td', 'th'):
            label = 'html.fm-modern .compare-page .solution-stat-table > tbody > tr > ' + tag + '[align="center"] > b'
            self.assertEqual(('auto', False), declared(sheet, label, 'hyphens'))
            self.assertEqual(('auto', False), declared(sheet, label, '-webkit-hyphens'))

    def test_a_header_label_hyphenates_and_wraps_at_its_space_at_every_width(self):
        parent = [('tr', {'class': 'solution-stat-summary-line'})]
        for tag, attrs in (('th', {'align': 'center', 'scope': 'col'}), ('td', {'align': 'center'})):
            for width in (320, 375, 500, 501, 600, 1366):
                chain = chain_of(self.ROW + parent + [(tag, attrs)], 'b', {}, ['fm-modern', 'fm-light'])
                self.assertEqual('auto', winning(self.MODERN, chain, 'hyphens', width)[0], (tag, width))
                self.assertEqual('auto', winning(self.MODERN, chain, '-webkit-hyphens', width)[0], (tag, width))
                nowrap = winning(self.MODERN, chain, 'white-space', width)
                self.assertTrue(nowrap is None or nowrap[0] != 'nowrap', (tag, width))

    def test_a_phone_header_label_keeps_its_hyphens_in_every_four_set_band(self):
        parent = [('tr', {'class': 'solution-stat-summary-line'})]
        for tag, attrs in (('th', {'align': 'center', 'scope': 'col'}), ('td', {'align': 'center'})):
            for width in (320, 375, 400, 401, 500, 501, 530, 560):
                chain = chain_of(self.ROW + parent + [(tag, attrs)], 'b', {}, ['fm-modern', 'fm-light'])
                for sheets in (self.MODERN, self.four_sets()):
                    for prop in ('hyphens', '-webkit-hyphens'):
                        self.assertEqual('auto', winning(sheets, chain, prop, width)[0], (tag, width, prop))

    def test_a_phone_header_row_leaves_its_empty_cells_out_so_the_labels_sit_over_the_values(self):
        for header in (':has(> th[scope="col"])', ':has(> td[align="center"]:not(.solution-stat-summary-value-cell))'):
            self.assertEqual('none', self.band(ROW_CELLS + header + ' > :nth-child(-n+2)', 'display'))

    def test_a_phone_header_label_breaks_at_its_space_inside_its_track(self):
        for tag in ('td', 'th'):
            label = ROW_CELLS + ' > ' + tag + '[align="center"] > b'
            self.assertEqual('normal', self.band(label, 'white-space'))
            self.assertEqual('block', self.band(label, 'display'))
            self.assertEqual('break-word', self.band(label, 'overflow-wrap'))
            self.assertEqual('3px 1px', self.band(ROW_CELLS + ' > ' + tag + '[align="center"]', 'padding'))
        self.assertEqual(('12px', False), declared(self.MODERN[0][1], 'html.fm-modern .compare-page .solution-stat-table > tbody > tr > th[align="center"] > b', 'font-size'))

    def test_a_long_name_breaks_inside_its_own_track_in_every_row_kind(self):
        row = [('tr', {'class': 'solution-stat-summary-line'})]
        names = [('td', {'class': 'compare-spell-name-cell'}), ('th', {'scope': 'row'})]
        for tag, attrs in names:
            chain = chain_of(self.ROW + row, tag, attrs, ['fm-modern', 'fm-light'])
            for width in (320, 375, 500, 1366):
                found = winning(self.MODERN, chain, 'overflow-wrap', width)
                self.assertIsNotNone(found, (tag, attrs, width))
                self.assertEqual('anywhere', found[0])
        self.assertRegex(source('modern.css'), r'solution-stat-summary-line:not\(\.fm-stat-group\) > td:nth-child\(2\),[^{]*\{ overflow-wrap:anywhere; \}')


class TheClassicLightNoteIsReadableTests(SimpleTestCase):

    def test_the_note_and_the_title_are_white_on_the_dark_panel_in_classic_light(self):
        for element in (NOTE, TITLE, TARGET):
            self.assertEqual('#FFFFFF', value(CLASSIC, element, 'color', 1366))

    def test_the_other_designs_keep_their_own_colour(self):
        for design in ('fm-modern', 'fm-enhanced'):
            self.assertNotEqual('#FFFFFF', value(CLASSIC + [design], NOTE, 'color', 1366))


class TheClassicComparePageFitsAPhoneTests(SimpleTestCase):

    def test_both_classic_designs_scroll_the_stat_tables_inside_their_frame_on_a_phone(self):
        for classes in (CLASSIC, CLASSIC + ['fm-enhanced']):
            self.assertEqual('block', value(classes, STAT_TABLE, 'display', 375))
            self.assertEqual('auto', value(classes, STAT_TABLE, 'overflow-x', 375))

    def test_classic_stacks_the_two_columns_on_a_phone_only(self):
        column = ('td', {})
        self.assertEqual('block', value(CLASSIC, column, 'display', 375))
        self.assertNotEqual('block', value(CLASSIC, column, 'display', 1366))

    def test_the_wide_layout_is_untouched(self):
        self.assertIsNone(value(CLASSIC, STAT_TABLE, 'overflow-x', 1366))

    def test_the_wide_rows_stay_inside_the_frame_in_both_classic_designs(self):
        pinned = ('div', {'class': 'compare-pinned'})
        for classes in (CLASSIC, CLASSIC + ['fm-enhanced']):
            chain = chain_of(PAGE + [('td', {})], pinned[0], pinned[1], classes)
            self.assertEqual('sticky', winning(SHEETS, chain, 'position', 375)[0])
            self.assertEqual('10px', winning(SHEETS, chain, 'left', 375)[0])
            self.assertTrue(winning(SHEETS, chain, 'max-width', 375)[0].startswith('calc(100vw'))
            self.assertIsNone(winning(SHEETS, chain, 'position', 1366))

    def test_the_atelier_does_not_pin_the_wide_rows(self):
        chain = chain_of(PAGE + [('td', {})], 'div', {'class': 'compare-pinned'}, ['fm-modern', 'fm-light'])
        self.assertIsNone(winning(SHEETS, chain, 'position', 375))
