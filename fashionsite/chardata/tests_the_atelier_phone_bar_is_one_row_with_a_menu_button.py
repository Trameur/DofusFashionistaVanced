# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""On a phone the top bar is one row (brand, game version switch, menu button) and the links sit in a panel that the button opens; without scripts every link stays in the flow, and the classic design never sees any of it."""
import os
import re

from django.test import SimpleTestCase

from chardata.tests_the_setup_stylesheet_support import STATIC

TEMPLATES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates', 'chardata')


def read(*parts):
    with open(os.path.join(*parts), encoding='utf-8') as handle:
        return handle.read()


BASE = read(TEMPLATES, 'base.html')
NAV = read(STATIC, 'modern-nav.css')


def block(css, header):
    start = css.index(header)
    depth, end = 0, start
    for index in range(css.index('{', start), len(css)):
        depth += {'{': 1, '}': -1}.get(css[index], 0)
        if depth == 0:
            end = index
            break
    return css[start:end + 1]


PHONE = block(NAV, '@media (max-width:767px)')


class ThePhoneBarMarkupTests(SimpleTestCase):

    def test_the_button_is_a_real_button_that_names_what_it_controls(self):
        button = re.search(r'<button type="button" class="fm-topnav-burger"[^>]*>', BASE).group(0)
        self.assertIn('aria-expanded="false"', button)
        self.assertIn('aria-controls="fm-topnav-links fm-topnav-end"', button)
        for identifier in ('fm-topnav-links', 'fm-topnav-end'):
            self.assertEqual(1, BASE.count('id="%s"' % identifier))

    def test_the_brand_keeps_its_full_name_for_screen_readers(self):
        self.assertRegex(BASE, r'class="fm-topnav-brand"[^>]*><span class="fm-topnav-brand-full">Dofus Fashionista</span><span class="fm-topnav-brand-mark" aria-hidden="true">DF</span>')

    def test_the_script_opens_the_panel_by_class_and_closes_it_on_escape_giving_the_focus_back(self):
        self.assertIn("nav0.classList.add('fm-nav-js')", BASE)
        self.assertIn("burger.setAttribute('aria-expanded',on?'true':'false')", BASE)
        self.assertRegex(BASE, r"e\.key!=='Escape'\|\|!nav0\.classList\.contains\('fm-open'\)")
        self.assertIn('burger.focus()', BASE)
        self.assertNotIn('.focus()', re.search(r"var setOpen=.*?\n", BASE).group(0))

    def test_the_version_switch_moves_next_to_the_brand_only_on_a_phone(self):
        self.assertIn("window.matchMedia('(max-width:767px)')", BASE)
        self.assertIn('inner.insertBefore(vers,burger)', BASE)
        self.assertIn('inner.insertBefore(vers,links0.nextSibling)', BASE)


class ThePhoneBarStyleTests(SimpleTestCase):

    def test_the_bar_is_modern_only_and_the_button_and_brand_are_hidden_by_default(self):
        self.assertRegex(NAV, r'html\.fm-modern \.fm-topnav-brand,\s*html\.fm-modern \.fm-topnav-burger\{ display:none; \}')
        self.assertIn('html:not(.fm-modern) .fm-topnav', NAV)

    def test_the_panel_is_closed_only_when_the_script_ran(self):
        self.assertIn('html.fm-modern .fm-topnav.fm-nav-js:not(.fm-open) .fm-topnav-links', PHONE)
        self.assertIn('html.fm-modern .fm-topnav.fm-nav-js:not(.fm-open) .fm-topnav-end', PHONE)
        self.assertNotRegex(PHONE, r'\.fm-topnav:not\(\.fm-open\)')

    def test_the_row_is_a_three_column_grid_of_brand_versions_and_button(self):
        self.assertRegex(PHONE, r'\.fm-nav-js \.fm-topnav-in\{[^}]*grid-template-columns:auto minmax\(0,1fr\) auto')

    def test_every_phone_rule_sits_under_the_modern_prefix(self):
        for selector in re.findall(r'([^{}]+)\{', PHONE.split('{', 1)[1]):
            for part in selector.split(','):
                with self.subTest(selector=part.strip()):
                    self.assertTrue(part.strip().startswith('html.fm-modern'))

    def test_the_signed_in_row_greeting_is_dropped_and_the_name_truncated_from_1280(self):
        wide = block(NAV, '@media (min-width:1280px){')
        self.assertIn('.fm-login-txt{ display:none; }', wide)
        self.assertIn('#logged_user_alias{ max-width:7em; }', wide)
        self.assertIn('text-overflow:ellipsis', NAV)
        self.assertIn("alias.title=alias.textContent.trim()", BASE)
        self.assertNotRegex(NAV, r'logout[^{]*\{[^}]*display:none')

    def test_from_1280_the_search_narrows_before_the_bar_wraps_in_every_language(self):
        wide = block(NAV, '@media (min-width:1280px){')
        self.assertIn('.fm-topnav-end{ flex:1 1 0; flex-wrap:nowrap;', wide)
        self.assertIn('.fm-topnav-end > *{ flex-shrink:0; }', wide)
        self.assertRegex(wide, r'\.nav-search\{ flex:0 1 \d+px; min-width:\d+px; \}')

    def test_the_design_switch_keeps_its_icon_when_its_label_is_hidden(self):
        tight = block(NAV, '@media (min-width:1280px) and (max-width:1535px)')
        self.assertIn('.fm-design-label{ display:none; }', tight)
        self.assertIn('.fm-design-toggle span[aria-hidden]{ display:inline-flex; }', tight)

    def test_the_signed_in_pill_grows_instead_of_spilling_on_a_phone(self):
        self.assertRegex(PHONE, r'\.fm-topnav \.login\{[^}]*height:auto; min-height:40px;')

    def test_the_tools_menu_opens_inside_the_screen_on_a_narrow_tablet(self):
        self.assertIn('.fm-topnav-menu{ left:auto; right:0; }', block(NAV, '@media (min-width:768px) and (max-width:839px)'))

    def test_below_390_the_band_shrinks_so_the_whole_wordmark_stays_on_screen(self):
        small = block(NAV, '@media (max-width:389px)')
        self.assertIn('--fm-band-h:calc(100vw * 84 / 390)', small)
        self.assertIn('background-position:right calc(100vw * -26 / 390) center', small)
