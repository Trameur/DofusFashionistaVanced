# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""In the Atelier design each game with a beta shows one pill and a chevron that opens its versions menu on hover, click, tap and keys; the script reads the games from the markup, so a new beta gets the menu with no script change."""
import re
from unittest import mock

from django.template.loader import render_to_string
from django.test import SimpleTestCase

from chardata.context_processors import switcher_groups
from chardata.tests_the_atelier_phone_bar_is_one_row_with_a_menu_button import BASE, NAV, block
from fashionistapulp import game_versions
from fashionistapulp.game_versions import GameVersion, version_keys

SCRIPT = BASE[BASE.index('var vopen=null'):BASE.index("var bar=q('.fm-buildbar')")]
TAP = NAV[NAV.rindex('@media (max-width:760px)'):]
TINY = block(NAV, '@media (max-width:389px)')


def rule(css, selector):
    found = re.search(re.escape(selector) + r'\{([^}]*)\}', css)
    return found.group(1) if found else None


class TheScriptReadsTheGamesFromTheMarkupTests(SimpleTestCase):

    def test_the_menus_are_built_from_every_group_that_names_one(self):
        self.assertIn("vsel.querySelectorAll('.version-game[data-menu]')", SCRIPT)
        self.assertIn("g.querySelectorAll('a.version-link')", SCRIPT)
        self.assertIn("menu.id='fm-vs-menu-'+g.getAttribute('data-family')", SCRIPT)

    def test_no_version_key_is_written_in_the_script(self):
        for key in version_keys(include_experimental=True):
            with self.subTest(key=key):
                self.assertNotIn("'%s'" % key, SCRIPT)
                self.assertNotIn('"%s"' % key, SCRIPT)

    def test_the_pill_is_the_current_member_or_the_main_and_the_others_are_hidden(self):
        self.assertIn("pill=q('.version-link.active',g)||ls[0]", SCRIPT)
        self.assertIn('if(ls[i]!==pill)ls[i].hidden=true', SCRIPT)

    def test_the_chevron_is_a_disclosure_button_named_by_the_group(self):
        self.assertIn("btn.type='button'", SCRIPT)
        self.assertIn("btn.className='fm-vs-more'", SCRIPT)
        self.assertIn("btn.setAttribute('aria-expanded','false')", SCRIPT)
        self.assertIn("btn.setAttribute('aria-controls',menu.id)", SCRIPT)
        self.assertIn("btn.setAttribute('aria-label',g.getAttribute('data-menu'))", SCRIPT)
        self.assertNotIn("role", SCRIPT)

    def test_the_rows_are_plain_links_and_the_current_one_says_so(self):
        self.assertIn("row.className='fm-vs-choice'", SCRIPT)
        self.assertIn("row.setAttribute('aria-current','page')", SCRIPT)


class TheMenuOpensAndClosesAsAReaderExpectsTests(SimpleTestCase):

    def test_a_mouse_opens_after_80_ms_and_leaving_closes_after_250_ms(self):
        self.assertIn("window.matchMedia('(hover:hover) and (pointer:fine)')", SCRIPT)
        self.assertRegex(SCRIPT, r"'pointerenter',function\(e\)\{if\(e\.pointerType!=='mouse'.*setTimeout\(function\(\)\{openVers\(m,false\);\},80\)")
        self.assertRegex(SCRIPT, r"'pointerleave',function\(e\)\{.*if\(vopen&&!vopen\.pin\)vtimer=setTimeout\(function\(\)\{closeVers\(false\);\},250\)")

    def test_focus_never_opens_a_menu(self):
        self.assertNotIn("'focus'", SCRIPT)
        focusin = re.search(r"document\.addEventListener\('focusin',function\(e\)\{([^\n]*)\}\);", SCRIPT).group(1)
        self.assertNotIn('openVers', focusin)
        self.assertIn('closeVers(false)', focusin)

    def test_arrow_keys_open_and_walk_the_rows(self):
        self.assertIn("if(e.key!=='ArrowDown')return;e.preventDefault();openVers(m,true);vfocus(m,vcurrent(m));", SCRIPT)
        for key in ('ArrowUp', 'Home', 'End'):
            self.assertIn("'%s'" % key, SCRIPT)
        self.assertIn('focus({preventScroll:true})', SCRIPT)

    def test_scrolling_the_row_resizing_and_an_outside_press_close_it(self):
        self.assertIn("vsel.addEventListener('scroll',function(){if(vopen&&Math.abs(vsel.scrollLeft-vopen.at)>2)closeVers(false);}", SCRIPT)
        self.assertIn("window.addEventListener('resize',function(){if(window.innerWidth===vwidth)return;vwidth=window.innerWidth;closeVers(false);});", SCRIPT)
        self.assertIn("document.addEventListener('pointerdown',function(e){if(vopen&&!vopen.g.contains(e.target))closeVers(false);});", SCRIPT)

    def test_one_menu_is_open_at_a_time_across_tools_and_versions(self):
        self.assertIn('closeVers(false);closeTools(false);vopen=m;', SCRIPT)
        self.assertIn("tools.addEventListener('toggle',function(){if(tools.open)closeVers(false);});", BASE)
        self.assertIn("burger.addEventListener('click',function(){closeVers(false);", BASE)
        self.assertRegex(BASE, r'var place=function\(\)\{\s*closeVers\(false\);')

    def test_escape_closes_the_versions_menu_before_the_burger(self):
        burger = BASE.index("if(e.key!=='Escape'||!nav0.classList.contains('fm-open')||q('.fm-topnav-tools[open]')||vopen)return;")
        closer = BASE.index("document.addEventListener('keydown',function(e){if(e.key==='Escape'&&vopen)closeVers(vopen.g.contains(document.activeElement));});")
        self.assertLess(burger, closer)
        self.assertIn('if(back)m.btn.focus();', SCRIPT)
        self.assertIn('closeVers(vopen.g.contains(document.activeElement))', BASE)

    def test_the_fade_masks_are_dropped_while_open_and_restored_on_close(self):
        self.assertIn("vsel.classList.remove('fm-vs-less','fm-vs-more');", SCRIPT)
        self.assertIn('var fade=function(){if(vopen)return;', BASE)
        self.assertRegex(SCRIPT, r"closeVers=function\(back\)\{[^\n]*fade\(\);")

    def test_the_menu_is_clamped_inside_the_16px_gutters(self):
        self.assertIn('Math.max(16,Math.min(gr.left,vw-16-m.menu.offsetWidth))-vr.left', SCRIPT)


class TheMenuStyleTests(SimpleTestCase):

    def test_every_menu_rule_sits_under_the_modern_prefix(self):
        selectors = [s.strip() for s in re.findall(r'([^{}]*fm-vs-[^{}]*)\{', NAV)]
        self.assertGreaterEqual(len(selectors), 20)
        for selector in selectors:
            for part in selector.split(','):
                with self.subTest(selector=part.strip()):
                    self.assertTrue(part.strip().startswith('html.fm-modern'))

    def test_no_menu_selector_puts_a_list_inside_is_or_where(self):
        for selector in re.findall(r'([^{}]*fm-vs-[^{}]*)\{', NAV):
            with self.subTest(selector=selector.strip()):
                self.assertNotRegex(selector, r':(?:is|where)\([^)]*,')

    def test_the_menu_overlays_from_the_version_box_and_stacks_like_tools(self):
        self.assertIn('html.fm-modern .fm-topnav-vers{ position:relative; }', NAV)
        menu = rule(NAV, 'html.fm-modern .fm-vs-menu')
        for part in ('position:absolute', 'z-index:40', 'background:var(--fm-nav)', 'border:1px solid var(--fm-navline)', 'border-radius:14px', 'max-width:calc(100vw - 32px)'):
            self.assertIn(part, menu)
        self.assertIn('display:none', rule(NAV, 'html.fm-modern .fm-vs-menu[hidden]'))
        self.assertIn('height:8px', rule(NAV, 'html.fm-modern .fm-vs-menu::before'))

    def test_reduced_motion_drops_the_fade(self):
        self.assertIn('transition:opacity .12s', rule(NAV, 'html.fm-modern .fm-vs-menu'))
        motion = block(NAV, '@media (prefers-reduced-motion:reduce)')
        self.assertIn('html.fm-modern .fm-vs-menu{ transition:none; }', motion)

    def test_a_hidden_member_never_shows(self):
        self.assertIn('display:none !important', rule(NAV, 'html.fm-modern .fm-topnav .version-link[hidden]'))

    def test_the_chevron_is_32px_wide_and_reaches_44px_on_touch_screens(self):
        self.assertIn('flex:0 0 32px', rule(NAV, 'html.fm-modern .fm-topnav button.fm-vs-more'))
        self.assertIn('inset:-7px -1px', rule(TAP, '  html.fm-modern .fm-topnav button.fm-vs-more::after'))
        selector = rule(TAP, '  html.fm-modern .fm-topnav.fm-nav-js .fm-topnav-vers .version-selector')
        self.assertIn('padding:6px 3px !important', selector)
        self.assertIn('margin:-3px 0', selector)
        self.assertIn('min-height:44px', rule(TAP, '  html.fm-modern .fm-vs-menu a.fm-vs-choice'))

    def test_the_beta_pill_shows_its_game_and_a_beta_chip(self):
        name = rule(NAV, 'html.fm-modern .fm-topnav .version-link.fm-vs-pill .version-game-name')
        self.assertIn('position:static', name)
        self.assertIn('clip:auto', name)
        chip = rule(NAV, 'html.fm-modern .fm-topnav .version-link.fm-vs-pill .version-channel')
        self.assertIn('background:#241A06', chip)
        self.assertIn('color:var(--fm-navgold)', chip)

    def test_on_the_smallest_phones_four_games_and_three_chevrons_share_the_row(self):
        self.assertIn('padding:8px 6px !important; font-size:12px;', rule(TINY, '  html.fm-modern .fm-topnav.fm-nav-js .version-link'))
        self.assertIn('gap:1px', rule(TINY, '  html.fm-modern .fm-topnav.fm-nav-js .fm-topnav-vers .version-selector'))


class ASecondGameWithABetaGetsTheSameMenuTests(SimpleTestCase):

    def fake_touch_beta(self):
        touch = game_versions.GAME_VERSIONS['touch']
        fake = GameVersion('touchbeta', 'Touch Beta', touch.db_file, touch.dump_file, seo_word='Touch Beta',
                           family='touch', channel='beta')
        order = list(game_versions.VERSION_ORDER)
        order.insert(order.index('touch') + 1, 'touchbeta')
        return (mock.patch.dict(game_versions.GAME_VERSIONS, {'touchbeta': fake}),
                mock.patch.object(game_versions, 'VERSION_ORDER', tuple(order)))

    def render(self):
        context = {'version_switch_games': switcher_groups(), 'current_game_version': 'touchbeta',
                   'version_switch_base_path': '/', 'version_switch_language_prefix': ''}
        return render_to_string('chardata/version-selector.html', context)

    def test_the_fake_beta_joins_its_game_and_the_group_names_its_menu(self):
        registry, order = self.fake_touch_beta()
        with registry, order:
            html = self.render()
        touch = re.search(r'<span class="version-game" data-family="touch"([^>]*)>(.*?)</span>\s*<span class="version-game"', html, re.S)
        self.assertIn('data-menu="Touch versions"', touch.group(1))
        self.assertEqual(['touch', 'touchbeta'], re.findall(r'data-version="([^"]+)"', touch.group(2)))
        self.assertIn('version-beta active', touch.group(2))
        self.assertEqual(2, html.count('data-menu="'))

    def test_the_registry_is_untouched_after_the_fake(self):
        registry, order = self.fake_touch_beta()
        with registry, order:
            pass
        self.assertNotIn('touchbeta', game_versions.GAME_VERSIONS)
        self.assertNotIn('touchbeta', version_keys(include_experimental=True))
