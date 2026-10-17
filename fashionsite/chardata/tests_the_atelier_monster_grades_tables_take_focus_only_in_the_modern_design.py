# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The monster grades tables scroll sideways on a phone, so the modern design lets the keyboard reach them: one inline script gives each scrolling box a tab stop and names the first one, and it takes all of it away whenever the page root does not carry the modern class. The markup itself stays as it was, so the classic tab order is the one it always had."""
import io
import os
import re

from django.test import SimpleTestCase

from chardata.tests_the_setup_stylesheet_support import chain_of, stylesheet, winning

TEMPLATES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates', 'chardata')
MODERN_RULE = 'html.fm-modern .monster-grades-scroll:focus-visible'


def source():
    with io.open(os.path.join(TEMPLATES, 'encyclopedia_monster.html'), encoding='utf-8') as handle:
        return handle.read()


def scripts():
    return [block for block in re.findall(r'<script>(.*?)</script>', source(), re.S) if 'monster-grades-scroll' in block]


def script():
    found = scripts()
    if not found:
        raise AssertionError('the monster template has no script for the grades boxes')
    return found


def after(text, marker):
    if marker not in text:
        raise AssertionError('%r is missing' % marker)
    return text.index(marker)


def reachable_body():
    code = script()[0]
    start = after(code, 'function reachable()')
    return code[start:after(code[start + 30:], 'reachable();') + start + 30]


class MonsterGradesFocusTests(SimpleTestCase):

    def test_there_is_exactly_one_script_that_touches_the_grades_boxes(self):
        self.assertEqual(1, len(scripts()))

    def test_the_modern_class_is_read_inside_the_function_that_runs_on_every_resize(self):
        body = reachable_body()
        self.assertIn("classList.contains('fm-modern')", body)
        self.assertLess(after(body, "classList.contains('fm-modern')"), after(body, 'setAttribute'))
        self.assertEqual(1, script()[0].count("classList.contains('fm-modern')"))

    def test_a_box_gets_a_tab_stop_only_when_it_scrolls_in_the_modern_design(self):
        body = reachable_body()
        self.assertRegex(body, r'modern\s*&&\s*\w+\[\w+\]\.scrollWidth\s*>\s*\w+\[\w+\]\.clientWidth')
        self.assertIn("setAttribute('tabindex', '0')", body)
        self.assertIn("removeAttribute('tabindex')", body)

    def test_the_script_runs_again_on_resize(self):
        self.assertIn("addEventListener('resize', reachable)", script()[0])

    def test_the_script_runs_again_when_the_design_class_of_the_page_changes(self):
        code = script()[0]
        self.assertIn('new MutationObserver(reachable).observe(document.documentElement', code)
        self.assertIn("attributeFilter: ['class']", code)

    def test_only_the_first_box_gets_a_role_and_a_name(self):
        code = script()[0]
        self.assertRegex(code, r"if \(scrolls && i === 0\) \{\s+\w+\[i\]\.setAttribute\('role', 'region'\);")
        names = set(re.findall(r"setAttribute\('aria-labelledby', '([^']+)'\)", code))
        self.assertEqual({'monster-stats-label'}, names)
        self.assertEqual(1, code.count("setAttribute('role', 'region')"))
        self.assertEqual(1, code.count("setAttribute('aria-labelledby'"))

    def test_the_name_comes_from_an_existing_heading_that_precedes_the_first_box(self):
        text = source()
        self.assertEqual(1, text.count('id="monster-stats-label"'))
        self.assertLess(after(text, 'id="monster-stats-label"'), after(text, 'class="monster-grades-scroll"'))
        self.assertIn('<b id="monster-stats-label">{{ mt.stats_section_label }}</b>', text)

    def test_leaving_the_modern_design_removes_the_tab_stop_the_role_and_the_name(self):
        body = reachable_body()
        for attribute in ('tabindex', 'role', 'aria-labelledby'):
            self.assertIn("removeAttribute('%s')" % attribute, body)
        self.assertIn('} else {', body)

    def test_the_script_adds_no_translatable_string(self):
        self.assertNotIn('{%', script()[0])
        self.assertNotIn('{{', script()[0])

    def test_the_markup_of_the_boxes_carries_no_tab_stop_or_name(self):
        boxes = re.findall(r'<div class="monster-grades-scroll"[^>]*>', source())
        self.assertEqual(2, len(boxes))
        for box in boxes:
            self.assertEqual('<div class="monster-grades-scroll">', box)

    def test_the_script_sits_outside_every_template_condition(self):
        text = source()
        position = after(text, '<script>\n(function () {\n    function reachable')
        opened = len(re.findall(r'{%\s*if\b', text[:position]))
        closed = len(re.findall(r'{%\s*endif\s*%}', text[:position]))
        self.assertEqual(opened, closed)


class MonsterGradesFocusRingTests(SimpleTestCase):

    def rules(self):
        return [rule for rule in stylesheet('modern.css') if MODERN_RULE in rule['selectors']]

    def test_the_ring_is_an_inner_outline_so_the_header_cells_cannot_cover_it(self):
        rules = self.rules()
        self.assertEqual(1, len(rules))
        declarations = rules[0]['declarations']
        self.assertEqual(('2px solid var(--fm-accent-text)', False), declarations.get('outline'))
        self.assertEqual(('-2px', False), declarations.get('outline-offset'))
        self.assertEqual(('inset var(--fm-ring)', False), declarations.get('box-shadow'))

    def test_the_ring_rule_is_not_important_and_is_not_inside_a_media_query(self):
        rules = self.rules()
        self.assertEqual([None], [rule['media'] for rule in rules])
        self.assertFalse(any(important for rule in rules for _, important in rule['declarations'].values()))

    def test_the_box_keeps_its_modern_margin_rule(self):
        chain = chain_of((('html', {}), ('body', {'class': 'body-base'}), ('div', {'class': 'encyclopedia-atelier'})),
                         'div', {'class': 'monster-grades-scroll'}, ('fm-modern', 'fm-light'))
        found = winning([('modern.css', stylesheet('modern.css'))], chain, 'margin-top', 375)
        self.assertIsNotNone(found)
        self.assertEqual('var(--fm-space-2)', found[0])
