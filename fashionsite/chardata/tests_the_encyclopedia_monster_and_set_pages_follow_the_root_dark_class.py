# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The monster, monsters, set and sets pages dress their dark theme from the class the root element carries, because no script on those pages ever sets a class on the body. The new design keeps its own dark look."""
import io
import os
import re

from django.test import SimpleTestCase

TEMPLATES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates', 'chardata')
PAGES = ('encyclopedia_monster.html', 'encyclopedia_monsters.html', 'encyclopedia_set.html', 'encyclopedia_sets.html')
CLASSIC_DARK = ':where(html:not(.fm-modern)).fm-dark'


def style_selectors(name):
    with io.open(os.path.join(TEMPLATES, name), encoding='utf-8') as handle:
        text = handle.read()
    css = ''.join(re.findall(r'<style>(.*?)</style>', text, re.S))
    css = re.sub(r'/\*.*?\*/', '', css, flags=re.S)
    css = re.sub(r'@media[^{]*\{', '', css)
    selectors = []
    for head in re.findall(r'([^{}]+)\{[^{}]*\}', css):
        selectors.extend(part.strip() for part in head.split(',') if part.strip())
    return selectors


class TheEncyclopediaDarkRulesFollowTheRootClassTests(SimpleTestCase):
    def test_no_page_style_waits_for_a_body_class_that_nothing_sets(self):
        for name in PAGES:
            with self.subTest(page=name):
                with io.open(os.path.join(TEMPLATES, name), encoding='utf-8') as handle:
                    self.assertNotIn('dark-theme-active', handle.read())

    def test_every_page_has_dark_rules_under_the_root_class(self):
        for name in PAGES:
            with self.subTest(page=name):
                dark = [s for s in style_selectors(name) if 'fm-dark' in s]
                self.assertGreater(len(dark), 5)

    def test_every_dark_rule_sits_under_the_root_class_and_names_the_design_it_serves(self):
        for name in PAGES:
            for selector in style_selectors(name):
                if 'fm-dark' not in selector:
                    continue
                with self.subTest(page=name, selector=selector):
                    self.assertTrue(selector.startswith(CLASSIC_DARK + ' ') or selector.startswith('html.fm-dark '), selector)

    def test_the_new_design_is_never_matched_by_a_rule_that_only_the_classic_look_needs(self):
        for name in PAGES:
            for selector in style_selectors(name):
                if selector.startswith('html.fm-dark '):
                    continue
                if 'fm-dark' in selector:
                    with self.subTest(page=name, selector=selector):
                        self.assertIn(':not(.fm-modern)', selector)

    def test_a_classic_dark_rule_keeps_the_specificity_of_a_single_class_before_its_target(self):
        for name in PAGES:
            for selector in style_selectors(name):
                if selector.startswith(CLASSIC_DARK):
                    with self.subTest(page=name, selector=selector):
                        self.assertNotIn('html.fm-dark:not', selector)
