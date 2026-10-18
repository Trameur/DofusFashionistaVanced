# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The forgemagie tables scroll sideways on a phone, so the modern design lets the keyboard reach them: one inline script gives each scrolling box a tab stop and, where a heading names it, a region role, and it takes all of it away whenever the page root does not carry the modern class. The markup carries no tab stop, so the classic tab order is the one it always had."""
import io
import os
import re

from django.test import SimpleTestCase

from chardata.tests_the_setup_stylesheet_support import stylesheet

TEMPLATES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates', 'chardata')
LABELS = ('fm-odds-label', 'fm-ref-label', 'fm-nostat-label', 'fm-trans-label')


def source():
    with io.open(os.path.join(TEMPLATES, 'forgemagie.html'), encoding='utf-8') as handle:
        return handle.read()


def scripts():
    return [block for block in re.findall(r'<script>(.*?)</script>', source(), re.S) if 'fm-table-wrapper' in block]


def code():
    found = scripts()
    if len(found) != 1:
        raise AssertionError('expected one script for the table boxes, found %d' % len(found))
    return found[0]


def body():
    text = code()
    start = text.index('function reachable()')
    return text[start:text.index('reachable();', start + 30)]


class ForgemagieTableFocusTests(SimpleTestCase):

    def test_one_script_touches_the_table_boxes(self):
        self.assertEqual(1, len(scripts()))

    def test_the_modern_class_is_read_inside_the_function_that_runs_every_time(self):
        text = body()
        self.assertIn("classList.contains('fm-modern')", text)
        self.assertLess(text.index("classList.contains('fm-modern')"), text.index('setAttribute'))
        self.assertEqual(1, code().count("classList.contains('fm-modern')"))

    def test_a_box_gets_a_tab_stop_only_when_it_scrolls_in_the_modern_design(self):
        text = body()
        self.assertRegex(text, r'modern\s*&&\s*\w+\[\w+\]\.scrollWidth\s*>\s*\w+\[\w+\]\.clientWidth')
        self.assertIn("setAttribute('tabindex', '0')", text)
        self.assertIn("removeAttribute('tabindex')", text)

    def test_every_box_that_is_not_scrolling_in_the_modern_design_loses_all_three_attributes(self):
        text = body()
        for attribute in ('tabindex', 'role', 'aria-labelledby'):
            self.assertIn("removeAttribute('%s')" % attribute, text)

    def test_a_region_is_named_only_when_the_box_scrolls_and_its_heading_exists(self):
        text = body()
        self.assertRegex(text, r"if \(scrolls && label && document\.getElementById\(label\)\) \{\s+\w+\[i\]\.setAttribute\('role', 'region'\);")
        self.assertIn("setAttribute('aria-labelledby', label)", text)
        self.assertEqual(1, code().count("setAttribute('role', 'region')"))

    def test_the_script_runs_again_on_resize_and_when_the_design_class_changes(self):
        text = code()
        self.assertIn("addEventListener('resize', reachable)", text)
        self.assertIn('new MutationObserver(reachable).observe(document.documentElement', text)
        self.assertIn("attributeFilter: ['class']", text)

    def test_every_box_and_its_table_is_watched_for_a_size_change_so_a_card_shown_later_is_covered(self):
        text = code()
        self.assertIn('new ResizeObserver(reachable)', text)
        self.assertIn("document.querySelectorAll('.fm-table-wrapper')", text[text.index('new ResizeObserver'):])
        self.assertIn('sizes.observe(wrappers[k])', text)
        self.assertIn("wrappers[k].querySelector('table')", text)
        self.assertIn('sizes.observe(inner)', text)

    def test_the_item_card_box_is_named_by_the_item_name_it_shows(self):
        page = source()
        self.assertEqual(1, page.count('id="fm-item-name"'))
        self.assertEqual(1, page.count('data-fm-label="fm-item-name"'))
        name = page.index('id="fm-item-name"')
        box = page.index('data-fm-label="fm-item-name"')
        self.assertLess(name, box)
        self.assertEqual('<div class="fm-table-wrapper" ', page[box - 30:box])

    def test_each_named_box_points_at_a_heading_that_exists_once_and_comes_before_it(self):
        page = source()
        for label in LABELS:
            marker = 'id="%s"' % label
            self.assertEqual(1, page.count(marker), label)
            self.assertEqual(1, page.count('data-fm-label="%s"' % label), label)
            self.assertLess(page.index(marker), page.index('data-fm-label="%s"' % label), label)
            self.assertIn('fm-section-title', page[page.index(marker) - 60:page.index(marker)])

    def test_the_odds_card_and_the_rune_reference_are_among_the_named_boxes(self):
        page = source()
        self.assertIn('id="fm-odds-label">{{ t.odds_title }}', page)
        self.assertIn('id="fm-ref-label">{{ t.ref_title }}', page)

    def test_the_markup_carries_no_tab_stop_role_or_name_of_its_own(self):
        boxes = re.findall(r'<div class="fm-table-wrapper"[^>]*>', source())
        self.assertEqual(6, len(boxes))
        for box in boxes:
            for attribute in ('tabindex', 'role=', 'aria-labelledby'):
                self.assertNotIn(attribute, box)

    def test_the_script_adds_no_translatable_string_and_sits_outside_template_conditions(self):
        self.assertNotIn('{%', code())
        self.assertNotIn('{{', code())
        page = source()
        before = page[:page.index(code())]
        self.assertEqual(len(re.findall(r'{%\s*if\b', before)), len(re.findall(r'{%\s*endif\s*%}', before)))


class ForgemagieTableFocusRingTests(SimpleTestCase):

    def rules(self):
        return [rule for rule in stylesheet('modern.css') if 'html.fm-modern .fm-table-wrapper:focus-visible' in rule['selectors']]

    def test_the_boxes_get_the_gold_ring_of_the_monster_boxes_under_the_modern_prefix(self):
        rules = self.rules()
        self.assertEqual(1, len(rules))
        declarations = rules[0]['declarations']
        self.assertEqual(('2px solid var(--fm-accent-text)', False), declarations.get('outline'))
        self.assertEqual(('-2px', False), declarations.get('outline-offset'))
        self.assertEqual(('inset var(--fm-ring)', False), declarations.get('box-shadow'))
        self.assertIn('html.fm-modern .monster-grades-scroll:focus-visible', rules[0]['selectors'])

    def test_the_ring_is_not_important_and_not_inside_a_media_query(self):
        rules = self.rules()
        self.assertEqual([None], [rule['media'] for rule in rules])
        self.assertFalse(any(important for rule in rules for _, important in rule['declarations'].values()))
