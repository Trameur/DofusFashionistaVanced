# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The account alias, build tabs, language ring, history deltas, item icon row and swap pager stay readable and reachable."""
import os
import re

from django.test import SimpleTestCase

from chardata.tests_the_setup_stylesheet_support import STATIC

NAV = open(os.path.join(STATIC, 'modern-nav.css'), encoding='utf-8').read()
PARTS = open(os.path.join(STATIC, 'modern-solution-parts.css'), encoding='utf-8').read()
POPUP = open(os.path.join(STATIC, 'solution_popup.js'), encoding='utf-8').read()


class TheTopBarFitsItsContentTests(SimpleTestCase):

    def test_a_logged_in_alias_stays_at_5em_from_1280_to_1535_and_grows_to_9em_only_from_1366(self):
        wide = NAV.split('@media (min-width:1280px) and (max-width:1535px){', 1)[1].split(chr(10) + '}' + chr(10), 1)[0]
        self.assertIn('#logged_user_alias{ max-width:5em; }', wide)
        self.assertNotIn('max-width:9em', wide)
        self.assertRegex(NAV, r'@media \(min-width:1366px\) and \(max-width:1535px\)\{[^}]*#logged_user_alias\{ max-width:9em; \}')

    def test_a_logged_in_search_box_may_shrink_to_120px_so_it_never_covers_a_version_pill(self):
        wide = NAV.split('@media (min-width:1280px) and (max-width:1535px){', 1)[1].split(chr(10) + '}' + chr(10), 1)[0]
        self.assertIn('.fm-nav-user .nav-search{ min-width:120px; }', wide)

    def test_the_language_button_fills_the_whole_ring(self):
        self.assertRegex(NAV, r'\.fm-topnav #flag\.flag-btn\{[^}]*width:38px; height:38px;')

    def test_the_build_tabs_tighten_their_padding_on_a_laptop(self):
        self.assertRegex(NAV, r'@media \(min-width:761px\) and \(max-width:1439px\)\{[^}]*\.fm-buildbar-tabs a:link,[^}]*padding:0 7px !important;')


class TheSolutionPartsAreReadableTests(SimpleTestCase):

    def test_history_deltas_use_the_theme_tokens_at_full_opacity(self):
        self.assertIn('.solution-history-entry-score-delta{ opacity:1; }', PARTS)
        self.assertIn('.solution-history-entry-score-delta-positive{ color:var(--fm-ok); }', PARTS)
        self.assertIn('.solution-history-entry-score-delta-negative{ color:var(--fm-bad); }', PARTS)

    def test_on_a_phone_the_icon_row_starts_below_the_source_line(self):
        phone = PARTS.split('@media (max-width:760px){', 1)[1]
        self.assertRegex(phone, r'\.solution-item-icons\{ margin-top:12px !important; \}')

    def test_swap_page_controls_are_at_least_32px_on_a_phone(self):
        phone = PARTS.split('@media (max-width:760px){', 1)[1]
        self.assertRegex(phone, r'#pages \.pages-current\{ min-width:32px; min-height:32px; \}')

    def test_the_current_page_is_visibly_marked(self):
        self.assertRegex(PARTS, r'#pages \.pages-current\{[^}]*background:')

    def test_a_focused_page_link_shows_the_ring(self):
        self.assertRegex(PARTS, r'#pages \.pages-link:focus-visible\{[^}]*var\(--fm-ring\)')

    def test_the_current_page_label_shows_the_ring_when_the_keyboard_lands_on_it(self):
        self.assertRegex(PARTS, r'#pages \.pages-current:focus-visible\{ outline:none; box-shadow:var\(--fm-ring\); \}')


class TheSwapPagerIsReachableByKeyboardTests(SimpleTestCase):

    def test_a_page_label_is_a_focusable_button(self):
        self.assertIn("label.attr({role: 'button', tabindex: 0});", POPUP)

    def test_enter_and_space_open_the_page(self):
        body = POPUP.split('function createPageLabel', 1)[1]
        self.assertIn("e.key === 'Enter' || e.key === ' '", body)

    def test_the_current_page_is_announced(self):
        self.assertIn("class='pages-current' aria-current='page'", POPUP)

    def test_a_keyboard_activated_page_change_gives_the_focus_back_to_the_current_page(self):
        setpage = POPUP.split('function setPage', 1)[1].split('function createPageLabel', 1)[0]
        self.assertIn("if (pageFocusPending) {", setpage)
        self.assertIn(".pages-current').attr('tabindex', -1).focus()", setpage)
        keydown = POPUP.split('label.keydown', 1)[1]
        self.assertIn('pageFocusPending = true;', keydown)
        self.assertNotIn('pageFocusPending', POPUP.split('label.click(go)', 1)[0].split('function createPageLabel', 1)[1])

    def test_a_failed_page_request_clears_the_pending_focus_in_both_request_paths(self):
        body = POPUP.split('function populateSwitchDiv(', 1)[1].split('function checkIfViolationsAreFatal', 1)[0]
        self.assertEqual(body.count('.fail(function()'), 2)
        self.assertEqual(body.count('pageFocusPending = false;'), 2)
