# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Measures the modern stylesheet fixes for small phone targets, low-contrast text and the swap dialog: each rule is declared once in modern.css and carried by the sheet the pages load."""
from django.test import SimpleTestCase

from .tests_the_setup_stylesheet_support import declared, matching, stylesheet

PHONE = '(max-width:760px)'
NARROW = '(max-width:700px)'
TABLET = '(max-width:900px)'
M = 'html.fm-modern '


class TheModernPhoneTargetsAndTextColoursStayReadableTests(SimpleTestCase):
    """The changelog close button, build names, drop links, tips, errors, hovers and swap dialog keep their fixes."""

    def setUp(self):
        self.source = stylesheet('modern.css')

    def check(self, selector, prop, value, media=None, sheet='modern.css'):
        rules = self.source if sheet == 'modern.css' else stylesheet(sheet)
        self.assertEqual(declared(rules, selector, prop, media)[0], value)

    def test_the_changelog_close_button_is_a_forty_four_pixel_target(self):
        """The cross is 44 px square and its negative margins keep the header height."""
        self.check(M + '.changelog-close', 'min-width', '44px')
        self.check(M + '.changelog-close', 'min-height', '44px')
        self.check(M + '.changelog-close', 'margin', '-11px -10px -11px 0')
        self.check(M + '.changelog-close', 'min-height', '44px', sheet='modern-core.css')

    def test_the_build_name_link_fills_its_cell_on_a_phone(self):
        """A short build name stays a full-width tap target under the phone query."""
        selector = M + '.load-project-line > td:nth-child(3) a'
        self.check(selector, 'width', '100%', PHONE)
        self.assertEqual(matching(self.source, selector, None), [])

    def test_the_forge_reference_tables_wrap_instead_of_scrolling_on_a_phone(self):
        """Tables without the editor rows wrap their text and shed the 560 px minimum under 900 px."""
        table = M + '.fm-page.tools-atelier .fm-table'
        self.check(table + ':not(:has(th:nth-child(4)))', 'min-width', '0', TABLET)
        self.check(table + ':not(:has(th:nth-child(4))) td', 'white-space', 'normal', TABLET)
        self.check(table + ':not(:has(#fm-rows)) th', 'white-space', 'normal', NARROW)
        self.check(table + ':not(:has(#fm-rows)) td:first-child', 'white-space', 'normal', NARROW)

    def test_the_error_message_uses_the_theme_error_token(self):
        """The shared error colour is the token, which passes contrast in both themes."""
        self.check(M + '.error-message', 'color', 'var(--fm-error-text)')
        self.check(M + '.error-message', 'color', 'var(--fm-error-text)', sheet='modern-core.css')

    def test_the_light_hover_of_the_chips_and_import_links_uses_the_link_hover_token(self):
        """The smart build chip and the import links no longer fall to the pale gold on hover."""
        for tail in ('.tunnel-smartbuild .smart-example:hover', '.tunnel-import .import-partner:hover',
                     '.tunnel-import .import-developers a:hover', '.tunnel-import .import-back a:hover'):
            self.check('html.fm-modern.fm-light ' + tail, 'color', 'var(--fm-link-hover)', sheet='modern-rest.css')

    def test_the_monster_drop_links_are_taller_on_a_phone(self):
        """Drop links are padded blocks under 700 px so wrapped lines do not crowd each other."""
        selector = M + '.encyclopedia-atelier .encyclopedia-monster-drop-link'
        self.check(selector, 'display', 'inline-block', NARROW)
        self.check(selector, 'padding', '4px 0', NARROW)
        self.assertEqual(matching(self.source, selector, None), [])

    def test_the_swap_icon_keeps_its_natural_size_at_every_width(self):
        """The popup icon is exempt from the 100 percent cap that shrank it to nothing, and only the popup icon."""
        self.check(M + '#popUpDiv .item-exchange-icon', 'max-width', 'none')
        self.check(M + '.maincontent table td img', 'max-width', '100%', '(max-width: 900px)')
        nones = [selector for rule in self.source if rule['declarations'].get('max-width', ('',))[0] == 'none'
                 for selector in rule['selectors'] if selector.endswith('.item-exchange-icon')]
        self.assertEqual(nones, [M + '#popUpDiv .item-exchange-icon'])

    def test_the_swap_radios_are_inline_blocks_so_they_wrap(self):
        """Table cells made the two radio labels sit side by side and widen the card; inline blocks wrap."""
        for text in ('.item-atrib-text', '.item-comp-text'):
            self.check(M + '#popUpDiv ' + text, 'display', 'inline-block')

    def test_the_swap_warning_uses_the_warning_token(self):
        """The violations warning takes the themed warning colour instead of the classic orange."""
        self.check(M + '.item-exchange-violations-warning', 'color', 'var(--fm-warn)')

    def test_the_transcendence_tip_is_a_forty_four_pixel_target_on_a_phone(self):
        """Padding and negative margins give a 44 px hit box without moving the card layout."""
        selector = M + '.solution-item-section .transcendence-tip'
        self.check(selector, 'padding', '20px 15px 6px', PHONE, 'modern-core.css')
        self.check(selector, 'margin', '-20px -15px -6px', PHONE, 'modern-core.css')
