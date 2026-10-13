# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The flash a changed row of the /setup/ panel gets leaves its name at WCAG AA contrast in both classic designs."""
import os
import re

from django.test import SimpleTestCase

STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'chardata')
AA = 4.5
CLASSIC_DARK_FLASH = 'html:not(.fm-modern):not(.fm-light) .setup-preview'
CLASSIC_LIGHT_FLASH = 'html.fm-light .setup-preview'
THEME_SHEETS = {'dark': ('forms_darktheme.css', CLASSIC_DARK_FLASH),
                'light': ('forms_lighttheme.css', CLASSIC_LIGHT_FLASH)}


def rules(name):
    source = open(os.path.join(STATIC, name), encoding='utf-8').read()
    source = re.sub(r'/\*.*?\*/', '', source, flags=re.S)
    found = []
    for selectors, body in re.findall(r'([^{}]+)\{([^{}]*)\}', source):
        declarations = dict((key.strip(), value.strip()) for key, value in
                            re.findall(r'([\w-]+)\s*:\s*([^;]+);?', body))
        found.append(([part.strip() for part in selectors.split(',')], declarations))
    return found


def declared(name, selector, prop):
    values = [declarations[prop] for selectors, declarations in rules(name)
              if selector in selectors and prop in declarations]
    assert len(values) == 1, (name, selector, prop, values)
    return values[0]


def colour(text):
    text = text.strip()
    if text.startswith('#'):
        digits = text[1:]
        if len(digits) == 3:
            digits = ''.join(digit * 2 for digit in digits)
        return tuple(int(digits[i:i + 2], 16) for i in (0, 2, 4)), 1.0
    match = re.fullmatch(r'rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*([\d.]+)\s*)?\)', text)
    assert match, text
    return tuple(int(match.group(i)) for i in (1, 2, 3)), float(match.group(4) or 1)


def over(top, bottom):
    (colour_top, alpha), (colour_bottom, _alpha) = top, bottom
    return tuple(colour_top[i] * alpha + colour_bottom[i] * (1 - alpha) for i in range(3)), 1.0


def luminance(rgb):
    def channel(value):
        value /= 255.0
        return value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4
    red, green, blue = (channel(value) for value in rgb)
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast(text, background):
    lighter, darker = sorted((luminance(text[0]), luminance(background[0])), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def row_background(sheet, parity):
    return colour(declared(sheet, '.weight-stat-line:nth-child(%s)' % parity, 'background-color'))


def row_text(sheet):
    return colour(declared(sheet, '.wm-row', 'color'))


class TheFlashKeepsTheRowNamesReadableTests(SimpleTestCase):

    def flashed(self, design, parity):
        sheet, selector = THEME_SHEETS[design]
        flash = colour(declared('setup.css', selector, '--setup-flash'))
        return over(flash, row_background(sheet, parity)), row_text(sheet)

    def test_a_flashed_row_name_keeps_the_aa_ratio_in_every_classic_design_and_on_both_stripes(self):
        found = {}
        for design in THEME_SHEETS:
            for parity in ('odd', 'even'):
                background, text = self.flashed(design, parity)
                found[(design, parity)] = round(contrast(text, background), 2)
        self.assertEqual([], sorted(key for key, ratio in found.items() if ratio < AA), found)

    def test_the_checker_would_have_refused_the_flash_the_classic_dark_design_had_before(self):
        flash = colour('rgba(227, 191, 77, 0.34)')
        background = over(flash, row_background('forms_darktheme.css', 'odd'))
        self.assertEqual(4.41, round(contrast(row_text('forms_darktheme.css'), background), 2))
        self.assertLess(contrast(row_text('forms_darktheme.css'), background), AA)

    def test_the_stripes_and_the_text_are_the_ones_the_panel_rows_wear(self):
        self.assertEqual(((51, 51, 51), 1.0), row_background('forms_darktheme.css', 'odd'))
        self.assertEqual(((33, 33, 33), 1.0), row_background('forms_darktheme.css', 'even'))
        self.assertEqual(((221, 221, 221), 1.0), row_text('forms_darktheme.css'))
        self.assertEqual(((202, 204, 167), 1.0), row_background('forms_lighttheme.css', 'odd'))
        self.assertEqual(((228, 230, 188), 1.0), row_background('forms_lighttheme.css', 'even'))
        self.assertEqual(((61, 32, 13), 1.0), row_text('forms_lighttheme.css'))
