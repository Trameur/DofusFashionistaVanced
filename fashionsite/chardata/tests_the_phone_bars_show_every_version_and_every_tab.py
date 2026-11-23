# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""On a phone the version switch sits on its own row, the build tabs fade where more exist, and the changelog mark keeps its space."""
import os
import re

from django.test import SimpleTestCase

from chardata.tests_the_atelier_phone_bar_is_one_row_with_a_menu_button import BASE, NAV, block
from chardata.tests_the_setup_stylesheet_support import STATIC

COMMON = open(os.path.join(STATIC, 'common.css'), encoding='utf-8').read()
SMALL = block(NAV, '@media (max-width:599px)')
TABS = block(NAV, '@media (max-width:760px)')


class TheVersionSwitchHasItsOwnRowTests(SimpleTestCase):

    def test_on_a_small_phone_the_switch_spans_the_second_row(self):
        self.assertRegex(SMALL, r'\.fm-topnav-vers\{ grid-column:1 / -1; grid-row:2; \}')

    def test_the_switch_fills_the_row_without_the_legacy_margin(self):
        self.assertRegex(SMALL, r'\.version-selector\{ flex:1 1 auto; margin:0; \}')

    def test_each_game_grows_with_its_link_so_the_row_stays_full(self):
        self.assertRegex(SMALL, r'\.version-game\{ flex:1 1 auto; \}')

    def test_every_link_keeps_a_tap_height_of_32px(self):
        padding = re.search(r'\.version-link\{[^}]*padding:(\d+)px', SMALL)
        self.assertGreaterEqual(int(padding.group(1)) * 2 + 16, 32)

    def test_every_rule_sits_under_the_modern_prefix(self):
        for selector in re.findall(r'([^{}]+)\{', SMALL.split('{', 1)[1]):
            self.assertTrue(selector.strip().startswith('html.fm-modern'), selector)


class TheBuildTabsShowThatMoreExistTests(SimpleTestCase):

    def test_the_strip_fades_on_the_side_that_overflows(self):
        self.assertRegex(TABS, r'\.fm-buildbar-tabs\.fm-tabs-more\{[^}]*mask-image:linear-gradient\(to right')
        self.assertRegex(TABS, r'\.fm-buildbar-tabs\.fm-tabs-less\{[^}]*mask-image:linear-gradient\(to left')
        self.assertIn('.fm-buildbar-tabs.fm-tabs-less.fm-tabs-more{', TABS)

    def test_the_script_toggles_both_classes_and_centres_the_active_tab(self):
        self.assertIn("tabs.classList.toggle('fm-tabs-less'", BASE)
        self.assertIn("tabs.classList.toggle('fm-tabs-more'", BASE)
        self.assertIn("q('a.on',tabs)", BASE)
        self.assertIn('tabs.scrollLeft+=', BASE)

    def test_the_active_tab_is_looked_up_when_the_centring_runs(self):
        self.assertRegex(BASE, r"var tcenter=function\(\)\{var ton=q\('a\.on',tabs\)")


class TheChangelogMarkKeepsItsSpaceTests(SimpleTestCase):

    def test_the_mark_starts_with_a_space_a_flex_footer_cannot_collapse(self):
        self.assertRegex(BASE, r'id="changelog-new" hidden>&nbsp;\(\{% trans "new entries" %\}\)</span>')

    def test_the_space_is_text_so_a_screen_reader_says_it(self):
        self.assertNotRegex(COMMON, r'\.changelog-new \{[^}]*margin')
