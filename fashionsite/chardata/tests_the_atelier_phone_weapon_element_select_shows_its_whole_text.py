# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""On an Atelier phone the weapon element select shows its whole selected text, and no other design changes."""
import re

from django.test import SimpleTestCase
from django.utils import translation

from chardata import weapon_forge_text
from chardata.tests_the_setup_stylesheet_support import read_css
from fashionistapulp import weapon_forge
from fashionistapulp.dofus_constants import FIRE

PARTS = read_css('modern-solution-parts.css')
BASE = read_css('solution.css')
ROW = 'html.fm-modern .solution-weapon-forge-row'
CURRENT = ROW + ' > .solution-weapon-forge-current'
SELECT = ROW + ' > .solution-weapon-forge-select'


def rule(text, selector):
    """Declarations of the first rule whose selector is exactly this one."""
    match = re.search(re.escape(selector) + r'\s*\{([^}]*)\}', text)
    return match.group(1) if match else ''


def phone_block(text):
    """The first max-width:759px media block that holds the element select rules."""
    for match in re.finditer(r'@media \(max-width:759px\)\s*\{', text):
        end, depth = match.end(), 1
        while depth:
            depth += {'{': 1, '}': -1}.get(text[end], 0)
            end += 1
        body = text[match.end():end - 1]
        if CURRENT in body:
            return body
    return ''


class TheAtelierPhoneWeaponElementSelectShowsItsWholeTextTests(SimpleTestCase):

    def test_the_whole_text_is_hidden_outside_the_phone_rules(self):
        self.assertIn('display: none', rule(BASE, '.solution-weapon-forge-current'))
        self.assertNotIn(CURRENT, PARTS.replace(phone_block(PARTS), ''))

    def test_the_phone_rules_are_atelier_only_and_below_760(self):
        body = phone_block(PARTS)
        self.assertTrue(body)
        for selector in re.findall(r'^\s*([^{@]+?)\s*\{', body, re.M):
            if 'weapon-forge' in selector:
                self.assertTrue(selector.startswith('html.fm-modern '), selector)

    def test_the_whole_text_wraps_and_keeps_a_44px_target(self):
        shown = rule(phone_block(PARTS), CURRENT)
        self.assertIn('display:block', shown)
        self.assertIn('min-height:44px', shown)
        self.assertIn('overflow-wrap:anywhere', shown)
        self.assertIn('flex:1 0 100%', shown)
        self.assertNotIn('nowrap', shown)
        self.assertNotIn('ellipsis', shown)

    def test_the_real_select_stays_clickable_over_the_whole_row(self):
        covers = rule(phone_block(PARTS), SELECT)
        for declaration in ('position:absolute', 'inset:0', 'width:100%', 'height:100%', 'opacity:0'):
            self.assertIn(declaration, covers)
        self.assertIn('position:relative', rule(phone_block(PARTS), ROW))

    def test_keyboard_focus_shows_on_the_visible_text(self):
        self.assertIn(ROW + ':focus-within > .solution-weapon-forge-current', phone_block(PARTS))

    def test_the_control_names_the_selected_text_in_every_language(self):
        chosen = {'damage': (FIRE, weapon_forge.STRONG)}
        stored = {'damage': (FIRE, weapon_forge.STRONG)}
        for language in ('en', 'fr', 'de', 'es', 'pt'):
            for kept in ({}, stored):
                with self.subTest(language=language, stored=bool(kept)),                         translation.override(language):
                    found = weapon_forge_text.controls('dofus3', chosen, kept, language)
                    self.assertTrue(found)
                    for control in found:
                        shown = [option['text'] for option in control['options']
                                 if option['value'] == control['current']]
                        self.assertEqual(shown[0], control['current_text'])
                        self.assertTrue(control['current_text'])
