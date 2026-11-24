# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The popular builds of the home never end on a short row, in the classic and the modern design, at every width, and the modern cards show the update badge."""
import os
import re

from django.test import SimpleTestCase

from chardata.home_view import FEATURED_BUILDS_COUNT
from chardata.tests_the_setup_stylesheet_support import parse, stylesheet

MODERN = stylesheet('modern-home.css')
GRID = 'html.fm-modern .fm-lower .featured-builds-grid'
CARD = 'html.fm-modern .fm-lower .featured-build-card'
CLASSIC_CARD = 'html:not(.fm-modern, .fm-enhanced) .featured-build-card'
TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates', 'chardata', 'home.html')


def applies(media, width):
    if media is None:
        return True
    for alternative in media.split(','):
        bounds = re.findall(r'\((min|max)-width:\s*(\d+)px\)', alternative)
        ranged = re.fullmatch(r'\s*\((?:(\d+)px\s*<=\s*)?width\s*(?:(<|<=)\s*(\d+)px)?\s*\)\s*', alternative)
        if ranged:
            low, operator, high = ranged.groups()
            if (low is None or width >= int(low)) and (high is None or (width < int(high) if operator == '<' else width <= int(high))):
                return True
        elif bounds and all(width >= int(limit) if kind == 'min' else width <= int(limit) for kind, limit in bounds):
            return True
    return False


def shown_cards(rules, grid, card, width, count, hider_card=None):
    columns, cap, hides_trailing_row = None, None, False
    for rule in rules:
        if not applies(rule['media'], width):
            continue
        for selector in rule['selectors']:
            if selector == grid and 'grid-template-columns' in rule['declarations']:
                value = rule['declarations']['grid-template-columns'][0]
                repeated = re.match(r'repeat\((\d+),', value)
                columns = int(repeated.group(1)) if repeated else 1
            found = re.fullmatch(re.escape(card) + r':nth-child\(n\+(\d+)\)', selector)
            if found and rule['declarations'].get('display', ('',))[0] == 'none':
                cap = int(found.group(1)) - 1 if cap is None else min(cap, int(found.group(1)) - 1)
    if columns is None:
        return None, 0
    shown = count if cap is None else min(count, cap)
    if columns > 1:
        trailing = '%s:not(:first-child):nth-child(%dn+1):nth-last-child(-n+%d)' % (hider_card or card, columns, columns - 1)
        hidden_from = trailing + ' ~ .featured-build-card'
        declared = [rule for rule in rules if applies(rule['media'], width) and trailing in rule['selectors']
                    and hidden_from in rule['selectors'] and rule['declarations'].get('display', ('',))[0] == 'none']
        if declared:
            for index in range(columns + 1, count + 1, columns):
                if count - index + 1 <= columns - 1:
                    shown = min(shown, index - 1)
                    break
    return columns, shown


def columns_and_visible(rules, grid, card, width, hider_card=None):
    return shown_cards(rules, grid, card, width, FEATURED_BUILDS_COUNT, hider_card)


class TheModernPopularBuildsFillWholeRowsAtEveryWidthTests(SimpleTestCase):

    def test_every_width_from_320_to_2560_shows_whole_rows_only(self):
        for width in range(320, 2561):
            columns, visible = columns_and_visible(MODERN, GRID, CARD, width)
            if columns is None or visible == 0 or visible % columns:
                self.fail('width %d: %s cards over %s columns' % (width, visible, columns))

    def test_a_desktop_shows_one_or_two_rows_and_a_phone_two_to_four_cards(self):
        for width in range(700, 2561):
            columns, visible = columns_and_visible(MODERN, GRID, CARD, width)
            self.assertIn(visible // columns, (1, 2), width)
            if width >= 1720:
                self.assertEqual((5, 5), (columns, visible), width)
        for width in range(320, 500):
            self.assertIn(columns_and_visible(MODERN, GRID, CARD, width)[1], (2, 3, 4), width)

    def test_the_cards_asked_for_never_exceed_what_the_view_sends(self):
        for width in range(320, 2561):
            self.assertLessEqual(columns_and_visible(MODERN, GRID, CARD, width)[1], FEATURED_BUILDS_COUNT)


class TheClassicPopularBuildsFillWholeRowsAtEveryWidthTests(SimpleTestCase):

    def rules(self):
        with open(TEMPLATE, encoding='utf-8') as handle:
            block = re.search(r'<style>(.*?featured-builds-wrap.*?)</style>', handle.read(), flags=re.S).group(1)
        return parse(block)

    def test_every_width_from_320_to_2560_shows_whole_rows_only(self):
        rules = self.rules()
        for width in range(320, 2561):
            columns, visible = columns_and_visible(rules, '.featured-builds-grid', '.featured-build-card', width,
                                                   CLASSIC_CARD)
            if columns is None or visible == 0 or visible % columns:
                self.fail('width %d: %s cards over %s columns' % (width, visible, columns))


class ThePopularBuildsFillWholeRowsWhateverNumberOfBuildsSurvivesTests(SimpleTestCase):

    def assert_whole_rows(self, rules, grid, card, widths, hider_card=None):
        for count in range(1, FEATURED_BUILDS_COUNT + 1):
            for width in widths:
                columns, shown = shown_cards(rules, grid, card, width, count, hider_card)
                if columns is None or shown < 1 or (shown % columns and shown != count) or (shown != count and shown % columns):
                    self.fail('%d builds at width %d: %s cards over %s columns' % (count, width, shown, columns))
                if shown == count and count > columns and count % columns:
                    self.fail('%d builds at width %d: short last row over %s columns' % (count, width, columns))

    def test_the_modern_design_ends_on_a_full_row_for_every_count_of_builds(self):
        self.assert_whole_rows(MODERN, GRID, CARD, list(range(320, 2561)) + [1359.5, 499.5, 1719.5])

    def test_the_classic_design_ends_on_a_full_row_for_every_count_of_builds(self):
        with open(TEMPLATE, encoding='utf-8') as handle:
            block = re.search(r'<style>(.*?featured-builds-wrap.*?)</style>', handle.read(), flags=re.S).group(1)
        self.assert_whole_rows(parse(block), '.featured-builds-grid', '.featured-build-card', range(320, 2561, 7),
                               CLASSIC_CARD)

    def test_the_classic_trailing_row_hider_never_reaches_the_modern_design(self):
        with open(TEMPLATE, encoding='utf-8') as handle:
            block = re.search(r'<style>(.*?featured-builds-wrap.*?)</style>', handle.read(), flags=re.S).group(1)
        hiders = [selector for rule in parse(block) for selector in rule['selectors'] if 'nth-last-child' in selector]
        self.assertTrue(hiders)
        for selector in hiders:
            self.assertTrue(selector.startswith((CLASSIC_CARD, 'html.fm-enhanced .featured-build-card')), selector)

    def test_every_width_falls_in_exactly_one_modern_band_even_when_fractional(self):
        grid_rules = [rule for rule in MODERN if GRID in rule['selectors'] and rule['media']]
        for width in (499.5, 699.5, 899.5, 1099.5, 1359.5, 1719.5, 500, 700, 900, 1100, 1360, 1720):
            bands = {rule['media'] for rule in MODERN if rule['media'] and applies(rule['media'], width)
                     and any(re.fullmatch(re.escape(CARD) + r':nth-child\(n\+\d+\)', s) for s in rule['selectors'])}
            self.assertEqual(1, len(bands), (width, bands))


class TheModernCardsShowTheUpdateBadgeTests(SimpleTestCase):

    def test_no_modern_rule_hides_the_patch_line_of_a_card(self):
        for rule in MODERN:
            if any('featured-build-patch' in selector for selector in rule['selectors']):
                self.assertNotEqual('none', rule['declarations'].get('display', ('',))[0], rule['selectors'])

    def test_a_build_from_the_previous_update_keeps_its_dashed_badge_in_the_modern_design(self):
        selector = 'html.fm-modern .fm-lower .featured-build-patch .build-patch-badge-old'
        declared = {prop: value for rule in MODERN if selector in rule['selectors']
                    for prop, (value, _) in rule['declarations'].items()}
        self.assertEqual('dashed', declared['border-style'])

    def test_the_badge_is_a_pill_in_the_text_colour_on_the_workshop_surface(self):
        selector = 'html.fm-modern .fm-lower .featured-build-patch .build-patch-badge'
        declared = {prop: value for rule in MODERN if selector in rule['selectors']
                    for prop, (value, _) in rule['declarations'].items()}
        self.assertEqual('999px', declared['border-radius'])
        self.assertEqual('var(--fm-text)', declared['color'])
        self.assertEqual('var(--fm-surface-3)', declared['background'])
