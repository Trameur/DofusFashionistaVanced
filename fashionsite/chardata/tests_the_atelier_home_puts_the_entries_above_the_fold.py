# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The home page of the modern design: a compact head, framed item slots on one row, entries as cards, featured builds in a stitched panel, and a classic design that keeps its absolute entries."""
import os
import re

from django.test import SimpleTestCase, TestCase

from chardata.tests_the_atelier_modern_rules_stay_under_the_modern_prefix import FROZEN_UNPREFIXED
from chardata.tests_the_setup_stylesheet_support import chain_of, declared, matching, media_applies, read_css, stylesheet, winning

MODERN = stylesheet('modern.css')
HOME = stylesheet('home.css')
RESPONSIVE = stylesheet('responsive.css')
SHEETS = [('home.css', HOME), ('responsive.css', RESPONSIVE), ('modern.css', MODERN)]
ROOT = 'html.fm-modern'
MAIN = ROOT + ' .main-div'
CARD = ROOT + ' .giant-button'
TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates', 'chardata', 'home.html')
MODERN_HTML = ('fm-modern', 'fm-light')
FORCED = '(forced-colors:active)'
ENTRY = r'<div\b[^>]*class="giant-button[ "][^>]*>'


def at(selector, prop, width):
    """The value modern.css gives a property for exactly this selector at a viewport width: the last rule in file order."""
    found = None
    for rule in MODERN:
        if selector in rule['selectors'] and prop in rule['declarations'] and media_applies(rule['media'], width):
            found = rule['declarations'][prop][0]
    return found


def tracks(value):
    repeated = re.match(r'repeat\((\d+),', value)
    if repeated:
        return int(repeated.group(1))
    depth, count, inside = 0, 0, False
    for char in value:
        if char == '(':
            depth += 1
        elif char == ')':
            depth -= 1
        if char.isspace() and depth == 0:
            inside = False
        elif not inside:
            inside = True
            count += 1
    return count


def home_chain(tag, attrs, parent=None):
    ancestors = [('html', {}), ('body', {'class': 'body-base'}), ('div', {'class': 'maincolumn'})]
    if parent:
        ancestors.append(parent)
    return chain_of(ancestors, tag, attrs, MODERN_HTML)


def template_without_style_blocks():
    with open(TEMPLATE, encoding='utf-8') as handle:
        return re.sub(r'<style>.*?</style>', '', handle.read(), flags=re.S)


class TheHomeTemplateCarriesNoInlineStylesTests(SimpleTestCase):

    def test_no_element_of_the_home_template_has_a_style_attribute(self):
        self.assertEqual([], re.findall(r'<\w+[^>]*\sstyle=', template_without_style_blocks()))

    def test_each_former_inline_style_is_a_class_that_the_classic_sheet_declares(self):
        wanted = {
            '.home-title': {'font-size': '1.5em', 'font-weight': 'bold', 'margin': '6px 0 4px', 'line-height': '1.25'},
            '.home-heritage': {'margin': '0 0 10px', 'font-size': '0.86em', 'letter-spacing': '0.08em',
                               'text-transform': 'uppercase'},
            '.home-intro-text': {'max-width': '760px', 'margin': '0 auto 12px', 'opacity': '0.85', 'line-height': '1.5'},
            '.home-intro-last': {'margin-bottom': '16px'},
            '.home-links': {'margin-top': '18px'},
            '.home-browse': {'margin-top': '10px'},
        }
        for selector, declarations in wanted.items():
            for prop, value in declarations.items():
                with self.subTest(selector=selector, prop=prop):
                    self.assertEqual((value, False), declared(HOME, selector, prop))

    def test_the_classic_sheet_declares_the_last_intro_margin_after_the_shared_one(self):
        order = [index for index, rule in enumerate(HOME) if '.home-intro-text' in rule['selectors']
                 or '.home-intro-last' in rule['selectors']]
        self.assertEqual(['.home-intro-text', '.home-intro-last'], [HOME[index]['selectors'][0] for index in order])

    def test_the_template_names_every_class_the_stylesheets_use(self):
        source = template_without_style_blocks()
        for name in ('home-head', 'home-title', 'home-heritage', 'home-intro-text', 'home-intro-last', 'home-links',
                     'home-browse', 'giant-button fm-seam', 'featured-builds-wrap fm-seam'):
            with self.subTest(name=name):
                self.assertIn(name, source)

    def test_the_head_wraps_the_title_and_both_intro_paragraphs_and_nothing_else(self):
        source = template_without_style_blocks()
        head = source[source.index('class="home-head"'):source.index('<div class="main-div"')]
        for name in ('home-title', 'home-heritage', 'home-optimizer-intro', 'home-workshop-intro'):
            self.assertIn(name, head)
        self.assertNotIn('giant-button', head)


class TheClassicHomeKeepsItsAbsoluteEntriesTests(SimpleTestCase):

    def test_the_classic_entries_are_still_placed_by_absolute_offsets(self):
        self.assertEqual(('absolute', False), declared(HOME, '.giant-button', 'position'))
        self.assertEqual(('90px', False), declared(HOME, '.giant-button', 'top'))
        for selector, left in (('.first-button', '82px'), ('.second-button', '324px'), ('.third-button', '566px')):
            with self.subTest(selector=selector):
                self.assertEqual((left, False), declared(HOME, selector, 'left'))

    def test_the_seam_class_on_the_entries_and_the_panel_means_nothing_to_classic(self):
        for name in ('home.css', 'common.css', 'responsive.css', 'common_lighttheme.css', 'common_darktheme.css',
                     'home_lighttheme.css', 'home_darktheme.css'):
            with self.subTest(sheet=name):
                self.assertNotIn('fm-seam', read_css(name))

    def test_no_new_rule_of_this_page_is_missing_its_prefix(self):
        names = ('.home-head', '.home-title', '.home-heritage', '.home-intro', '.home-intro-text', '.home-links', '.home-browse',
                 '.giant-button', '.featured-builds', '.featured-build-card', '.home-pic-holder', '.home-pic')
        loose = [selector for rule in MODERN for selector in rule['selectors']
                 if not selector.startswith(ROOT + ' ') and selector not in FROZEN_UNPREFIXED
                 and any(name in selector for name in names)]
        self.assertEqual([], loose)


class TheHomeHeadSitsInTwoColumnsFromTheLaptopWidthTests(SimpleTestCase):

    HEAD = ROOT + ' .home-head'

    def test_the_head_is_a_block_below_1280(self):
        for width in (375, 768, 901, 1279):
            with self.subTest(width=width):
                self.assertIsNone(at(self.HEAD, 'display', width))

    def test_the_head_is_a_two_track_grid_from_1280(self):
        for width in (1280, 1440, 1920, 2560):
            with self.subTest(width=width):
                self.assertEqual('grid', at(self.HEAD, 'display', width))
                self.assertEqual(2, tracks(at(self.HEAD, 'grid-template-columns', width)))

    def test_the_title_and_the_heritage_line_span_both_tracks(self):
        for selector in (self.HEAD + ' > .home-title', self.HEAD + ' > .home-heritage'):
            with self.subTest(selector=selector):
                self.assertEqual('1 / -1', at(selector, 'grid-column', 1280))

    def test_the_intro_paragraphs_keep_the_reading_measure_and_full_opacity(self):
        chain = home_chain('p', {'class': 'home-intro home-intro-text', 'id': 'home-optimizer-intro'}, ('div', {'class': 'home-head'}))
        self.assertEqual('var(--fm-measure)', winning(SHEETS, chain, 'max-width', 1920)[0])
        self.assertEqual('1', winning(SHEETS, chain, 'opacity', 1920)[0])


class TheMainBlockIsAGridOfSixTracksFromTheLaptopWidthTests(SimpleTestCase):

    def test_below_901_the_main_block_stays_the_flex_column_of_the_responsive_sheet(self):
        for width in (375, 768, 900):
            with self.subTest(width=width):
                self.assertIsNone(at(MAIN, 'display', width))

    def test_from_901_it_is_a_six_track_grid(self):
        for width in (901, 1100, 1280, 1920, 2560):
            with self.subTest(width=width):
                self.assertEqual('grid', at(MAIN, 'display', width))
                self.assertEqual(6, tracks(at(MAIN, 'grid-template-columns', width)))

    def test_every_child_takes_the_full_row_except_the_three_entries(self):
        for width in (901, 1920):
            with self.subTest(width=width):
                self.assertEqual('1 / -1', at(MAIN + ' > *', 'grid-column', width))
                self.assertEqual('span 2', at(MAIN + ' > .giant-button', 'grid-column', width))

    def test_the_entries_are_cards_in_flow_not_absolute_boxes(self):
        for tag_class in ('giant-button first-button', 'giant-button second-button', 'giant-button third-button'):
            chain = home_chain('div', {'class': tag_class}, ('div', {'class': 'main-div'}))
            with self.subTest(button=tag_class):
                for width in (375, 1280, 1920):
                    self.assertEqual('relative', winning(SHEETS, chain, 'position', width)[0])
                    self.assertEqual('auto', winning(SHEETS, chain, 'top', width)[0])
                    self.assertEqual('auto', winning(SHEETS, chain, 'left', width)[0])
                    self.assertEqual('flex', winning(SHEETS, chain, 'display', width)[0])

    def test_the_card_stands_the_art_beside_the_label_from_1280_and_above_it_from_901_to_1279(self):
        selector = MAIN + ' > .giant-button'
        for width in (1280, 1440, 1920, 2560):
            with self.subTest(width=width):
                self.assertEqual('row', at(selector, 'flex-direction', width))
        for width in (901, 1100, 1279):
            with self.subTest(width=width):
                self.assertEqual('column', at(selector, 'flex-direction', width))

    def test_the_label_link_covers_the_whole_card_so_the_focus_ring_surrounds_the_card(self):
        chain = home_chain('a', {'class': 'giant-button-text', 'href': '/setup/'}, ('div', {'class': 'giant-button'}))
        self.assertEqual('absolute', winning(SHEETS, chain, 'position', 1920)[0])
        self.assertEqual('0', winning(SHEETS, chain, 'inset', 1920)[0])
        self.assertEqual('var(--fm-radius)', winning(SHEETS, chain, 'border-radius', 1920)[0])

    def test_from_901_to_1279_the_label_stays_in_flow_under_the_art_so_the_card_grows_with_its_text(self):
        chain = home_chain('a', {'class': 'giant-button-text', 'href': '/setup/'}, ('div', {'class': 'giant-button'}))
        for width in (901, 1100, 1279):
            with self.subTest(width=width):
                self.assertEqual('static', winning(SHEETS, chain, 'position', width)[0])
                self.assertEqual('block', winning(SHEETS, chain, 'display', width)[0])
                self.assertNotIn('56px', at(MAIN + ' > .giant-button', 'padding-bottom', width) or '')
                self.assertEqual('absolute', at(CARD + '-text::after', 'position', width))
                self.assertEqual('0', at(CARD + '-text::after', 'inset', width))
                self.assertEqual("''", at(CARD + '-text::after', 'content', width))

    def test_the_label_is_a_box_over_the_card_again_from_1280_and_below_901(self):
        chain = home_chain('a', {'class': 'giant-button-text', 'href': '/setup/'}, ('div', {'class': 'giant-button'}))
        for width in (375, 900, 1280, 2560):
            with self.subTest(width=width):
                self.assertEqual('absolute', winning(SHEETS, chain, 'position', width)[0])
                self.assertIn(at(CARD + '-text::after', 'content', width), (None, 'none'))

    def test_the_label_is_set_in_the_title_face_at_the_regular_weight(self):
        chain = home_chain('a', {'class': 'giant-button-text', 'href': '/setup/'}, ('div', {'class': 'giant-button'}))
        self.assertEqual('var(--fm-font-display)', winning(SHEETS, chain, 'font-family', 1920)[0])
        self.assertEqual('400', winning(SHEETS, chain, 'font-weight', 1920)[0])


class TheItemSlotsAreOneFramedRowThatFillsTheContentWidthTests(SimpleTestCase):

    TABLE = MAIN + ' > table'

    def test_the_icon_table_is_a_grid_in_flow_that_no_longer_floats_behind_the_cards(self):
        self.assertEqual('grid', at(self.TABLE, 'display', 1920))
        self.assertEqual('static', at(self.TABLE, 'position', 1920))
        self.assertEqual('1', at(self.TABLE, 'opacity', 1920))
        self.assertEqual('none', at(self.TABLE, 'mask', 1920))

    def test_columns_are_whole_tiles_spread_over_the_full_width_so_no_band_is_left_empty_on_one_side(self):
        self.assertEqual('repeat(auto-fill,var(--fm-home-tile))', at(self.TABLE, 'grid-template-columns', 1920))
        self.assertEqual('space-between', at(self.TABLE, 'justify-content', 1920))

    def test_only_whole_rows_are_shown_and_later_rows_have_no_height(self):
        self.assertEqual('repeat(var(--fm-home-rows),var(--fm-home-tile))', at(self.TABLE, 'grid-template-rows', 1920))
        self.assertEqual('0', at(self.TABLE, 'grid-auto-rows', 1920))
        self.assertEqual('hidden', at(self.TABLE, 'overflow', 1920))
        height = at(self.TABLE, 'height', 1920)
        self.assertIn('var(--fm-home-rows)', height)
        self.assertIn('var(--fm-home-tile)', height)

    def test_the_tile_is_44px_below_1280_and_52px_from_1280(self):
        values = {}
        for width in (901, 1279, 1280, 1920):
            for rule in MODERN:
                if MAIN in rule['selectors'] and '--fm-home-tile' in rule['declarations'] and media_applies(rule['media'], width):
                    values[width] = rule['declarations']['--fm-home-tile'][0]
        self.assertEqual({901: '44px', 1279: '44px', 1280: '52px', 1920: '52px'}, values)

    def test_the_row_count_is_one_so_the_strip_does_not_push_the_entries_down(self):
        rows = [rule['declarations']['--fm-home-rows'][0] for rule in MODERN if '--fm-home-rows' in rule['declarations']]
        self.assertEqual(['1'], rows)

    def test_the_slots_carry_the_loot_frame_and_forced_colours_turn_it_into_a_plain_border(self):
        selector = MAIN + ' .home-pic-holder'
        self.assertEqual(('2px solid var(--fm-frame-gold)', False), declared(MODERN, selector, 'border'))
        self.assertEqual(('inset 0 0 0 2px var(--fm-surface), inset 0 0 0 3px var(--fm-frame-gold)', False),
                         declared(MODERN, selector, 'box-shadow'))
        self.assertEqual(('CanvasText', False), declared(MODERN, selector, 'border-color', FORCED))
        self.assertEqual(('none', False), declared(MODERN, selector, 'box-shadow', FORCED))

    def test_the_slots_are_squares_at_full_opacity_with_the_icon_filling_them(self):
        chain = home_chain('div', {'class': 'home-pic-holder'}, ('div', {'class': 'main-div'}))
        self.assertEqual('1', winning(SHEETS, chain, 'opacity', 1920)[0])
        self.assertEqual('1', winning(SHEETS, chain, 'aspect-ratio', 1920)[0])
        image = home_chain('img', {'class': 'home-pic'}, ('div', {'class': 'main-div'}))
        self.assertEqual('1', winning(SHEETS, image, 'opacity', 1920)[0])
        self.assertEqual('100%', winning(SHEETS, image, 'width', 1920)[0])

    def test_the_strip_is_decoration_that_takes_no_pointer(self):
        self.assertEqual('none', at(self.TABLE, 'pointer-events', 1920))

    def test_the_strip_stays_hidden_on_the_phone_and_the_tablet(self):
        for width in (375, 768, 900):
            with self.subTest(width=width):
                self.assertEqual('none', at(self.TABLE, 'display', width))


class TheFeaturedBuildsAreAStitchedPanelWhoseLastRowIsCentredTests(SimpleTestCase):

    GRID = ROOT + ' .featured-builds-grid'
    CARD = ROOT + ' .featured-build-card'
    COLUMNS = '--fm-fb-cols'

    def columns(self, width):
        found = None
        for rule in MODERN:
            if MAIN in rule['selectors'] and self.COLUMNS in rule['declarations'] and media_applies(rule['media'], width):
                found = rule['declarations'][self.COLUMNS][0]
        return int(found)

    def test_the_grid_is_a_centred_wrapping_flex_row_so_an_incomplete_last_row_has_no_hole_on_one_side(self):
        self.assertEqual('flex', at(self.GRID, 'display', 1920))
        self.assertEqual('wrap', at(self.GRID, 'flex-wrap', 1920))
        self.assertEqual('center', at(self.GRID, 'justify-content', 1920))

    def test_the_cards_share_the_row_equally_through_the_column_count(self):
        basis = at(self.CARD, 'flex', 1920)
        self.assertIn('var(--fm-fb-cols)', basis)
        self.assertTrue(basis.startswith('0 0 calc('))

    def test_the_column_count_follows_the_width(self):
        expected = {375: 1, 520: 1, 768: 2, 900: 2, 901: 2, 999: 2, 1000: 3, 1280: 3, 1839: 3, 1840: 6, 1920: 6, 2560: 6}
        self.assertEqual(expected, {width: self.columns(width) for width in expected})

    def test_every_column_count_the_page_uses_divides_the_featured_builds_into_whole_rows(self):
        from chardata.home_view import FEATURED_BUILDS_COUNT
        for count in {self.columns(width) for width in (375, 520, 768, 901, 1000, 1280, 1840, 2560)}:
            with self.subTest(columns=count):
                self.assertEqual(0, FEATURED_BUILDS_COUNT % count)

    def test_the_panel_is_a_container_with_the_workshop_surface_and_the_seam_class_from_the_template(self):
        chain = home_chain('div', {'class': 'featured-builds-wrap fm-seam'}, ('div', {'class': 'main-div'}))
        self.assertEqual('var(--fm-surface)', winning(SHEETS, chain, 'background', 1920)[0])
        self.assertEqual('none', winning(SHEETS, chain, 'max-width', 1920)[0])
        self.assertEqual('1.5px dashed var(--fm-seam)', winning(SHEETS, chain, 'outline', 1920)[0])

    def test_the_panel_takes_the_full_content_width_where_the_inline_block_capped_it_at_980(self):
        chain = home_chain('div', {'class': 'featured-builds-wrap fm-seam'}, ('div', {'class': 'main-div'}))
        self.assertNotEqual('980px', winning(SHEETS, chain, 'max-width', 1920)[0])

    def test_the_seam_never_sits_on_the_cards_which_are_links(self):
        card = home_chain('a', {'class': 'featured-build-card', 'href': '/x/'}, ('div', {'class': 'featured-builds-grid'}))
        self.assertIsNone(winning(SHEETS, card, 'outline', 1920))

    def test_the_panel_title_uses_the_title_face_at_the_regular_weight(self):
        title = home_chain('h2', {'class': 'featured-builds-title'}, ('div', {'class': 'featured-builds-wrap'}))
        self.assertEqual('var(--fm-font-display)', winning(SHEETS, title, 'font-family', 1920)[0])
        self.assertEqual('400', winning(SHEETS, title, 'font-weight', 1920)[0])


class ThePhraseLinksOfTheIntroStayInOneLineTests(SimpleTestCase):

    def chain(self):
        return home_chain('a', {'href': '/quickstart/'}, ('p', {'class': 'home-intro home-links'}))

    def test_the_paragraph_is_not_held_to_the_reading_measure(self):
        chain = home_chain('p', {'class': 'home-intro home-links'}, ('div', {'class': 'main-div'}))
        self.assertEqual('none', winning(SHEETS, chain, 'max-width', 1920)[0])

    def test_a_link_phrase_never_breaks_from_601_up(self):
        selector = MAIN + ' .home-links a'
        for width in (601, 768, 1280, 1920):
            with self.subTest(width=width):
                self.assertEqual('nowrap', at(selector, 'white-space', width))
        self.assertIsNone(at(selector, 'white-space', 600))

    def test_the_paragraph_leaves_room_above_it_for_the_entries(self):
        chain = home_chain('p', {'class': 'home-intro home-links'}, ('div', {'class': 'main-div'}))
        self.assertEqual('18px auto 22px', winning(SHEETS, chain, 'margin', 1920)[0])


class TheHomePageIsRenderedWithTheNewMarkupTests(TestCase):

    def get_home(self, path='/'):
        page = self.client.get(path)
        self.assertEqual(200, page.status_code)
        return page.content.decode('utf-8', 'replace')

    def test_the_three_entries_carry_the_seam_class_and_stay_divisions(self):
        page = self.get_home()
        entries = re.findall(ENTRY, page)
        self.assertEqual(3, len(entries))
        for entry in entries:
            with self.subTest(entry=entry):
                self.assertIn('fm-seam', entry)

    def test_the_head_holds_the_title_and_both_intro_paragraphs(self):
        page = self.get_home()
        head = page[page.index('home-head'):page.index('main-div')]
        for name in ('home-title', 'home-optimizer-intro', 'home-workshop-intro'):
            self.assertIn(name, head)

    def test_no_element_of_the_head_or_the_links_paragraph_carries_a_style_attribute(self):
        page = self.get_home()
        body = page[page.index('home-head'):page.index('home-links')]
        body = re.sub(r'<style\b.*?</style>', '', body, flags=re.S)
        self.assertEqual([], re.findall(r'\sstyle=', body))

    def test_every_version_and_language_home_renders_the_same_structure(self):
        for path in ('/', '/beta/', '/dofus2/', '/retro/', '/touch/', '/de/', '/fr/', '/es/', '/pt/'):
            with self.subTest(path=path):
                page = self.get_home(path)
                self.assertEqual(1, page.count('class="home-head"'))
                self.assertEqual(3, len(re.findall(ENTRY, page)))
                self.assertIn('home-links', page)
