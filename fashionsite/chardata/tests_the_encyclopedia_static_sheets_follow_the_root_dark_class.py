# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The encyclopedia, detail, missing, compare and choose sheets dress their classic dark look from the class the root element carries. Only the item page sets a class on the body, so only the detail sheet may still name it, and every such rule has a classic twin for the pages that load the same sheet."""
import io
import os
import re

from django.test import SimpleTestCase

CHARDATA = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(CHARDATA, 'static', 'chardata')
TEMPLATES = os.path.join(CHARDATA, 'templates', 'chardata')
SHEETS = ('encyclopedia.css', 'encyclopedia_detail.css', 'encyclopedia_missing.css', 'compare.css', 'choose_compare_sets.css')
BODY_CLASS = '.dark-theme-active'
CLASSIC_DARK = ':where(html:not(.fm-modern)).fm-dark'
SETTER = 'encyclopedia_item.html'


def read(path):
    with io.open(path, encoding='utf-8') as handle:
        return handle.read()


def rules(name):
    css = re.sub(r'/\*.*?\*/', '', read(os.path.join(STATIC, name)), flags=re.S)
    css = re.sub(r'@media[^{]*\{', '', css)
    found = []
    for head, body in re.findall(r'([^{}]+)\{([^{}]*)\}', css):
        found.append(([part.strip() for part in head.split(',') if part.strip()], body))
    return found


def selectors(name):
    return [selector for heads, _ in rules(name) for selector in heads]


def target(selector):
    for prefix in (BODY_CLASS, CLASSIC_DARK, 'html.fm-dark'):
        if selector.startswith(prefix + ' '):
            return selector[len(prefix) + 1:]
    return None


class TheStaticSheetsDarkRulesFollowTheRootClassTests(SimpleTestCase):
    def test_the_sheets_the_item_page_does_not_load_no_longer_wait_for_a_body_class(self):
        item = read(os.path.join(TEMPLATES, SETTER))
        for name in SHEETS:
            if '"chardata/%s"' % name in item:
                continue
            with self.subTest(sheet=name):
                self.assertNotIn(BODY_CLASS, ''.join(selectors(name)))

    def test_only_the_item_page_sets_the_body_class_and_it_loads_the_one_sheet_that_names_it(self):
        setters = [name for name in sorted(os.listdir(TEMPLATES)) if name.endswith('.html') and 'dark-theme-active' in read(os.path.join(TEMPLATES, name))]
        self.assertEqual([SETTER], setters)
        loaders = [name for name in SHEETS if BODY_CLASS in ''.join(selectors(name))]
        self.assertEqual(['encyclopedia_detail.css'], loaders)
        self.assertIn('"chardata/encyclopedia_detail.css"', read(os.path.join(TEMPLATES, SETTER)))

    def test_a_rule_that_still_names_the_body_class_has_a_classic_twin_in_the_same_rule(self):
        for name in SHEETS:
            for heads, _ in rules(name):
                for selector in heads:
                    if not selector.startswith(BODY_CLASS + ' '):
                        continue
                    with self.subTest(sheet=name, selector=selector):
                        self.assertIn(CLASSIC_DARK + selector[len(BODY_CLASS):], heads)

    def test_a_classic_dark_rule_names_the_design_it_serves_and_keeps_the_specificity_of_the_class_it_replaces(self):
        for name in SHEETS:
            for selector in selectors(name):
                if 'fm-dark' not in selector:
                    continue
                with self.subTest(sheet=name, selector=selector):
                    self.assertIsNotNone(target(selector), selector)
                    self.assertNotIn('html.fm-dark:not', selector)

    def test_the_new_design_is_never_matched_by_a_rule_that_only_the_classic_look_needs(self):
        for name in SHEETS:
            for selector in selectors(name):
                if CLASSIC_DARK in selector:
                    with self.subTest(sheet=name, selector=selector):
                        self.assertTrue(selector.startswith(CLASSIC_DARK + ' '), selector)

    def test_the_classic_dark_rules_the_sheets_carry_are_the_ones_the_pages_needed(self):
        expected = {
            'encyclopedia.css': ['.encyclopedia-resource-hit', '.encyclopedia-family-nav a'],
            'encyclopedia_missing.css': ['.encyclopedia-missing-card', '.encyclopedia-missing a'],
            'choose_compare_sets.css': ['.compare-picker-section', '.compare-build-choice-card', '.compare-build-choice-card.selected'],
        }
        for name, targets in expected.items():
            with self.subTest(sheet=name):
                found = [target(s) for s in selectors(name) if s.startswith(CLASSIC_DARK + ' ')]
                self.assertEqual(sorted(targets), sorted(found))

    def test_the_rules_the_root_class_already_served_in_both_designs_stay_single(self):
        for name, wanted in (('encyclopedia.css', '.encyclopedia-card-stat-negative'), ('compare.css', '.compare-spell-best'),
                             ('encyclopedia_detail.css', '.encyclopedia-set-caps span')):
            with self.subTest(sheet=name):
                found = [s for s in selectors(name) if target(s) == wanted]
                self.assertEqual(['html.fm-dark ' + wanted], found)
