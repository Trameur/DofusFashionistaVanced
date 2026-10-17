# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The second half of the setup tunnel in the modern design (base characteristics, smart build, quick start, import, no set found): each page carries the opt-in class and its own, the cards and the split are shared, the static inline styles moved to classes with the same values, every rule of the subsection hangs on a tunnel class under the modern prefix, and every input of these templates is matched by a 44 pixel rule."""
import io
import os
import re

from django.test import SimpleTestCase

from chardata.tests_the_setup_stylesheet_support import parse, stylesheet

TEMPLATES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates', 'chardata')
START = '/* Setup tunnel: base stats, smart build, quick start, import, infeasible */'
TOKENS = '/* ---------- Design tokens ---------- */'
BASE = '/* ---------- Base ---------- */'
TUNNEL = '/* ---------- Setup tunnel: weights, wizard, options, lock items, forbid items ---------- */'
PAGES = {
    'chardata.html': 'tunnel-basestats',
    'smart_build.html': 'tunnel-smartbuild',
    'coaching.html': 'tunnel-quickstart',
    'text_build.html': 'tunnel-import',
    'infeasible.html': 'tunnel-infeasible',
}
INPUT_SOURCES = ('chardata.html', 'chardata_line.html', 'smart_build.html', 'coaching.html', 'text_build.html', 'infeasible.html')
SKIPPED_TYPES = ('hidden', 'radio', 'checkbox', 'file', 'range')
THEME_SELECTORS = ('html.fm-modern.fm-light', 'html.fm-modern.fm-dark', 'html.fm-modern:not(.fm-light):not(.fm-dark)')


def read(name):
    with io.open(os.path.join(TEMPLATES, name), encoding='utf-8') as handle:
        return handle.read()


def rules(marker):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'chardata', 'modern.css')
    with io.open(path, encoding='utf-8') as handle:
        source = handle.read()
    return parse(re.sub(r'/\*.*?\*/', '', source[source.index(marker):], flags=re.S))


def subsection():
    return rules(START)


def declared(selector, prop, media=None):
    found = [rule['declarations'][prop][0] for rule in subsection()
             if rule['media'] == media and selector in rule['selectors'] and prop in rule['declarations']]
    return found[-1] if found else None


def compact(value):
    return None if value is None else value.replace(' ', '')


class ThePagesOptInAndKeepTheirContentTests(SimpleTestCase):

    def test_every_page_carries_the_opt_in_class_and_its_own(self):
        for name, own in PAGES.items():
            self.assertRegex(read(name), r'class="[^"]*\btunnel-atelier %s\b' % own, name)

    def test_the_static_inline_styles_moved_to_classes_and_only_the_script_toggled_ones_stay(self):
        for name in list(PAGES) + ['chardata_line.html']:
            for style in re.findall(r'\sstyle="([^"]*)"', read(name)):
                self.assertIn('display:none', style.replace(' ', ''), '%s keeps a static inline style: %s' % (name, style))

    def test_the_classes_carry_the_values_the_inline_styles_had(self):
        values = {}
        for rule in stylesheet('forms.css'):
            for selector in rule['selectors']:
                values[selector] = {key: value[0] for key, value in rule['declarations'].items()}
        self.assertEqual('7px', values['input.button-gap-after']['margin-right'])
        self.assertEqual('7px', values['input.button-gap-before']['margin-left'])
        self.assertEqual('5.5em', values['input.import-level-input']['width'])
        self.assertEqual('12px', values['form.smart-form-confirm']['margin-top'])
        self.assertEqual('20px', values['p.coaching-intro.coaching-full-link']['margin-top'])
        self.assertEqual('0.9em', values['p.coaching-intro.coaching-full-link']['font-size'])

    def test_every_page_puts_its_content_in_a_tunnel_card_and_the_split_pages_carry_the_split(self):
        for name in PAGES:
            self.assertTrue(re.search(r'class="[^"]*\btunnel-card\b', read(name)), name)
        for name in ('chardata.html', 'smart_build.html', 'coaching.html', 'text_build.html'):
            self.assertTrue(re.search(r'class="tunnel-split"', read(name)), name)
        self.assertNotIn('tunnel-split', read('infeasible.html'))


class TheSubsectionStaysUnderTheModernPrefixTests(SimpleTestCase):

    def test_every_selector_starts_with_the_modern_class_and_names_a_tunnel_class(self):
        self.assertTrue(subsection())
        for rule in subsection():
            for selector in rule['selectors']:
                self.assertTrue(selector.startswith('html.fm-modern'), selector)
                self.assertIn('.tunnel-', selector)
            self.assertNotIn('print', rule['media'] or '')

    def test_the_split_pairs_the_columns_from_1280_and_stays_one_column_below(self):
        selector = 'html.fm-modern .tunnel-atelier .tunnel-split'
        self.assertEqual('minmax(0,1fr)', compact(declared(selector, 'grid-template-columns')))
        self.assertEqual('minmax(0,3fr)minmax(0,2fr)', compact(declared(selector, 'grid-template-columns', '(min-width:1280px)')))
        self.assertEqual('repeat(2,minmax(0,1fr))', compact(declared(
            'html.fm-modern .tunnel-basestats .tunnel-split', 'grid-template-columns', '(min-width:1280px)')))

    def test_the_card_is_stitched_with_the_shared_seam(self):
        selector = 'html.fm-modern .tunnel-atelier .tunnel-card'
        self.assertEqual('1.5px dashed var(--fm-seam)', declared(selector, 'outline'))
        self.assertEqual('-6px', declared(selector, 'outline-offset'))

    def test_the_breakpoints_that_override_the_shared_responsive_sheet_match_it(self):
        media = {rule['media'] for rule in subsection() if rule['media']}
        for query in media:
            for number in re.findall(r'(?:max|min)-width:\s*(\d+)px', query):
                self.assertIn(int(number), (480, 900, 901, 1280), query)


class TheErrorColourIsATokenOfTheThreeThemesTests(SimpleTestCase):

    def test_the_token_is_declared_in_the_token_block_for_each_theme_and_nowhere_else(self):
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'chardata', 'modern.css')
        with io.open(path, encoding='utf-8') as handle:
            source = handle.read()
        block = source[source.index(TOKENS):source.index(BASE)]
        in_block = {tuple(rule['selectors']): rule['declarations']['--fm-error-text'][0]
                    for rule in parse(re.sub(r'/\*.*?\*/', '', block, flags=re.S)) if '--fm-error-text' in rule['declarations']}
        self.assertEqual({(THEME_SELECTORS[0],): '#a8281f', (THEME_SELECTORS[1],): '#f4a6a6', (THEME_SELECTORS[2],): '#a8281f'}, in_block)
        self.assertEqual(3, len(re.findall(r'--fm-error-text\s*:', source)))

    def test_the_base_stats_message_takes_the_token_on_the_card(self):
        self.assertEqual('var(--fm-error-text)', declared('html.fm-modern .tunnel-basestats .error-message', 'color'))


class TheInfeasiblePageStacksUnderTheSharedBreakpointTests(SimpleTestCase):

    def test_the_grid_starts_where_the_shared_stacker_stops(self):
        selector = 'html.fm-modern .tunnel-infeasible'
        self.assertEqual('grid', declared(selector, 'display', '(min-width:901px)'))
        self.assertIsNone(declared(selector, 'display'))
        for rule in subsection():
            self.assertNotIn('601', rule['media'] or '')

    def test_the_image_is_at_most_260_pixels_wide_at_every_width(self):
        selector = 'html.fm-modern .tunnel-infeasible > tbody > tr > td > img'
        self.assertEqual('min(100%,260px)', compact(declared(selector, 'width')))
        for rule in subsection():
            if selector in rule['selectors'] and rule['media']:
                self.assertNotIn('width', rule['declarations'])


class TheSmallScreenInputsAreSixteenPixelsTests(SimpleTestCase):

    def test_inputs_selects_and_textareas_of_the_tunnel_are_16_pixels_up_to_900(self):
        for tag in ('input', 'select', 'textarea'):
            self.assertEqual('16px', declared('html.fm-modern .tunnel-atelier ' + tag, 'font-size', '(max-width:900px)'), tag)


class TheBaseStatsHeaderCarriesItsColourAndItsBackgroundTogetherTests(SimpleTestCase):

    def test_one_rule_sets_the_heading_colour_and_the_surface_behind_it(self):
        for selector in ('html.fm-modern .tunnel-basestats .register-stat tr:first-child > *',
                         'html.fm-modern .tunnel-basestats .table-softcap-stat tr:first-child > *'):
            found = [rule['declarations'] for rule in subsection() if selector in rule['selectors']]
            pairs = [item for item in found if 'color' in item or 'background' in item]
            self.assertEqual(1, len(pairs), selector)
            self.assertEqual('var(--fm-head)', pairs[0]['color'][0])
            self.assertEqual('var(--fm-surface-3)', pairs[0]['background'][0])


class EveryInputOfTheSecondPagesIsAFortyFourPixelTargetTests(SimpleTestCase):

    def sized_selectors(self):
        selectors = []
        for rule in rules(TUNNEL):
            height = rule['declarations'].get('min-height', [''])[0]
            if not (height.endswith('px') and float(height[:-2]) >= 44):
                continue
            for selector in rule['selectors']:
                tunnel_classes = set(re.findall(r'\.(tunnel-[a-z]+)', selector))
                if tunnel_classes == {'tunnel-atelier'} or tunnel_classes & set(PAGES.values()):
                    selectors.append(selector)
        return selectors

    def test_every_select_and_textarea_is_matched_by_a_44_pixel_selector(self):
        sized = self.sized_selectors()
        checked = 0
        for name in INPUT_SOURCES:
            for tag in ('select', 'textarea'):
                for attributes in re.findall(r'<%s\b([^>]*)>' % tag, read(name), flags=re.S):
                    classes = []
                    for group in re.findall(r'\bclass\s*=\s*["\']([^"\']*)["\']', attributes):
                        classes.extend(group.split())
                    needles = [tag] + ['.%s' % item for item in classes]
                    checked += 1
                    self.assertTrue(any(needle in selector for selector in sized for needle in needles),
                                    '%s: <%s%s> has no 44 px selector' % (name, tag, attributes))
        self.assertGreaterEqual(checked, 3)

    def test_every_input_is_matched_by_a_44_pixel_selector(self):
        sized = self.sized_selectors()
        checked = 0
        for name in INPUT_SOURCES:
            for attributes in re.findall(r'<input\b([^>]*)>', read(name), flags=re.S):
                kind = re.search(r'\btype\s*=\s*["\']?(\w+)', attributes)
                kind = kind.group(1) if kind else 'text'
                if kind in SKIPPED_TYPES:
                    continue
                classes = []
                for group in re.findall(r'\bclass\s*=\s*["\']([^"\']*)["\']', attributes):
                    classes.extend(group.split())
                needles = ['input[type="%s"]' % kind] + ['.%s' % item for item in classes]
                checked += 1
                self.assertTrue(any(needle in selector for selector in sized for needle in needles),
                                '%s: <input%s> has no 44 px selector' % (name, attributes))
        self.assertGreaterEqual(checked, 5)
