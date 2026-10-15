# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The title font has one weight, 400: no rule that sets it sets a heavier weight, and the page title resolves to 400 at every width."""
import glob
import os
import re

from django.test import SimpleTestCase

from chardata.tests_the_setup_stylesheet_support import (
    STATIC, chain_of, parse, read_css, winning, stylesheet)

WIDTHS = (375, 768, 1280, 1440, 1920, 2560)
TITLE_FONT = re.compile(r'--fm-font-display|IM Fell')
HEAVY = {'bold', 'bolder'}


def weight_is_heavy(value):
    if value in HEAVY:
        return True
    return value.isdigit() and int(value) > 400


def all_rules():
    for path in sorted(glob.glob(os.path.join(STATIC, '*.css'))):
        name = os.path.basename(path)
        yield name, parse(read_css(name))


class NoRuleThatUsesTheTitleFontSetsAHeavyWeightTests(SimpleTestCase):

    def test_a_rule_naming_the_title_font_never_sets_a_weight_above_400(self):
        users = []
        heavy = []
        for name, rules in all_rules():
            for rule in rules:
                declarations = rule['declarations']
                if any(TITLE_FONT.search(declarations[prop][0]) for prop in ('font-family', 'font') if prop in declarations):
                    users.append((name, rule['selectors']))
                    weight = declarations.get('font-weight', ('400', False))[0]
                    shorthand = declarations.get('font', ('', False))[0]
                    if weight_is_heavy(weight) or re.search(r'\b(bold|[5-9]00)\b', shorthand):
                        heavy.append((name, rule['selectors'], weight))
        self.assertTrue(users, 'no rule uses the title font, so this proves nothing')
        self.assertEqual([], heavy)

    def test_the_font_face_of_the_title_font_declares_only_weight_400(self):
        source = read_css('modern.css')
        weights = []
        for body in re.findall(r'@font-face\s*\{([^}]*)\}', source):
            if 'IM Fell English SC' in body:
                weights += re.findall(r'font-weight:\s*(\w+)', body)
        self.assertEqual(['400'], weights)

    def test_no_descendant_of_a_title_inherits_a_heavier_weight(self):
        rules = stylesheet('modern.css')
        children = [rule for rule in rules if 'html.fm-modern h1 *' in rule['selectors']]
        self.assertEqual(1, len(children))
        self.assertEqual(('inherit', False), children[0]['declarations']['font-weight'])
        self.assertEqual(('inherit', False), children[0]['declarations']['font-family'])


class ThePageTitleResolvesToTheTitleFontAtRegularWeightTests(SimpleTestCase):

    def test_h1_is_in_the_title_font_at_400_at_every_width_in_the_modern_design(self):
        sheets = [(name, parse(read_css(name))) for name in ('common.css', 'forms.css', 'setup.css', 'responsive.css',
                                                            'modern.css')]
        for state in (('fm-modern', 'fm-light'), ('fm-modern', 'fm-dark')):
            chain = chain_of([('html', {}), ('body', {'class': 'body-base'})], 'h1', {}, state)
            for width in WIDTHS:
                with self.subTest(width=width, state=state):
                    weight = winning(sheets, chain, 'font-weight', width)
                    family = winning(sheets, chain, 'font-family', width)
                    self.assertEqual('400', weight[0])
                    self.assertEqual('var(--fm-font-display)', family[0])

    def test_h1_in_the_page_column_keeps_400_where_a_page_rule_names_it(self):
        sheets = [(name, parse(read_css(name))) for name in ('common.css', 'forms.css', 'responsive.css', 'modern.css')]
        chain = chain_of([('html', {}), ('body', {'class': 'body-base'}), ('div', {'class': 'main-div'})], 'h1', {},
                         ('fm-modern', 'fm-light'))
        for width in WIDTHS:
            with self.subTest(width=width):
                self.assertEqual('400', winning(sheets, chain, 'font-weight', width)[0])


TEMPLATES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates', 'chardata')
H1_TAG = re.compile(r'<h1\b([^>]*)>')


def h1_attributes():
    for path in sorted(glob.glob(os.path.join(TEMPLATES, '*.html'))):
        with open(path, encoding='utf-8') as handle:
            for match in H1_TAG.finditer(handle.read()):
                yield os.path.basename(path), match.group(1)


class EveryTitleInTheTemplatesResolvesToRegularWeightTests(SimpleTestCase):

    def test_h1_with_an_inline_font_weight_loses_to_an_important_400(self):
        inline = [(name, attrs) for name, attrs in h1_attributes()
                  if re.search(r'style="[^"]*font-weight', attrs)]
        self.assertTrue(inline, 'no h1 carries an inline weight, so this proves nothing')
        rules = stylesheet('modern.css')
        winner = [rule for rule in rules if 'html.fm-modern h1' in rule['selectors']
                  and 'font-weight' in rule['declarations']]
        self.assertEqual([('400', True)], [rule['declarations']['font-weight'] for rule in winner])

    def test_h1_with_a_class_resolves_to_400_in_the_modern_design(self):
        sheets = [(os.path.basename(path), parse(read_css(os.path.basename(path))))
                  for path in sorted(glob.glob(os.path.join(STATIC, '*.css')))
                  if os.path.basename(path) != 'modern.css']
        sheets.append(('modern.css', parse(read_css('modern.css'))))
        classes = set()
        for _, attrs in h1_attributes():
            match = re.search(r'class="([^"{}]*)"', attrs)
            if match:
                classes.add(match.group(1).strip())
        self.assertIn('fm-title', classes)
        for html_classes in classes:
            for state in (('fm-modern', 'fm-light'), ('fm-modern', 'fm-dark')):
                with self.subTest(classes=html_classes, state=state):
                    chain = chain_of([('html', {}), ('body', {'class': 'body-base'})], 'h1',
                                     {'class': html_classes}, state)
                    weight = winning(sheets, chain, 'font-weight', 1280)
                    self.assertEqual('400', weight[0])
