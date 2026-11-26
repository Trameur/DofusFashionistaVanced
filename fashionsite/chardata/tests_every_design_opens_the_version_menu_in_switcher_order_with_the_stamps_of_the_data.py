# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Every design lists the versions in the switcher order, names each one with the stamp its data carries, and opens the same version menu."""
import copy
import os
import re
from unittest import mock

from django.conf import settings
from django.template.loader import render_to_string
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import translation

from chardata.context_processors import ACTIVE_GAME_VERSIONS, switcher_groups, switcher_member
from chardata.readable_versions import readable_keys
from chardata.tests_the_setup_stylesheet_support import STATIC
from fashionistapulp import game_versions
from fashionistapulp.game_versions import (GAME_VERSIONS, is_beta, main_of, reader_dofus_versions,
                                           switcher_order, version_keys)

TEMPLATES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates', 'chardata')
SWITCHER_ORDER = ['dofus3', 'beta', 'touch', 'touchbeta', 'retro', 'retrobeta', 'dofus2']
PROBE = {key: 'stamp-of-' + key for key in GAME_VERSIONS}
CLASSIC = 'html:not(.fm-modern, .fm-enhanced) '


def sheet(name):
    with open(os.path.join(STATIC, name), encoding='utf-8') as handle:
        return handle.read()


def base_template():
    with open(os.path.join(TEMPLATES, 'base.html'), encoding='utf-8') as handle:
        return handle.read()


def rule(css, selector):
    """The declarations of the first rule whose selector list is exactly this selector."""
    match = re.search(r'(?:^|\})\s*' + re.escape(selector) + r'\s*\{([^}]*)\}', css, re.M)
    return match.group(1) if match else None


def staged_betas_live():
    live = {}
    for key in version_keys(include_experimental=True):
        if is_beta(key) and GAME_VERSIONS[key].experimental:
            live[key] = copy.copy(GAME_VERSIONS[key])
            live[key].experimental = False
    return mock.patch.dict(game_versions.GAME_VERSIONS, live)


def render_selector(key='dofus3'):
    context = {'version_switch_games': switcher_groups(), 'current_game_version': key,
               'version_switch_base_path': '/', 'version_switch_language_prefix': ''}
    return render_to_string('chardata/version-selector.html', context)


class TheSwitcherOrderTests(SimpleTestCase):

    def test_the_reader_versions_run_dofus3_its_beta_touch_retro_then_dofus2(self):
        self.assertEqual([key for key in SWITCHER_ORDER if key in version_keys()], switcher_order())

    def test_every_staged_beta_once_live_sits_right_after_its_main_game(self):
        with staged_betas_live():
            self.assertEqual(SWITCHER_ORDER, switcher_order())

    def test_dofus2_closes_the_list_and_each_beta_follows_its_main(self):
        with staged_betas_live():
            order = switcher_order()
            self.assertEqual('dofus2', order[-1])
            for index, key in enumerate(order):
                if is_beta(key):
                    start = order.index(main_of(key))
                    self.assertLess(start, index, key)
                    self.assertEqual({main_of(key)}, {main_of(other) for other in order[start:index + 1]}, key)

    def test_every_reader_list_follows_the_switcher_order(self):
        order = switcher_order()
        self.assertEqual(order, [key for key, _label in ACTIVE_GAME_VERSIONS])
        dofus = [key for key in order if GAME_VERSIONS[key].dofus]
        self.assertEqual(dofus, reader_dofus_versions())
        self.assertEqual(dofus, readable_keys())

    def test_the_rendered_selector_follows_the_switcher_order(self):
        with staged_betas_live():
            self.assertEqual(switcher_order(), re.findall(r'data-version="([^"]+)"', render_selector()))


class ThePageListsTheVersionsInSwitcherOrderTests(TestCase):

    def test_the_home_page_links_follow_the_switcher_order(self):
        html = self.client.get('/').content.decode('utf-8')
        block = html.split('<div class="version-selector">')[1].split('</div>')[0]
        self.assertEqual(switcher_order(), re.findall(r'data-version="([^"]+)"', block))


class TheLabelsComeFromTheDataTests(SimpleTestCase):

    def test_each_stamp_is_the_whole_site_version_of_its_data(self):
        for key in switcher_order():
            self.assertEqual(settings.SITE_VERSIONS.get(key, ''), switcher_member(key)['stamp'], key)

    @override_settings(SITE_VERSIONS=PROBE)
    def test_a_new_stamp_in_the_data_reaches_the_member_and_its_tooltip(self):
        with translation.override('en'):
            for key in switcher_order():
                member = switcher_member(key)
                self.assertEqual(PROBE[key], member['stamp'])
                self.assertEqual('%s \u00b7 %s' % (GAME_VERSIONS[key].game_name, PROBE[key]), member['title'])

    @override_settings(SITE_VERSIONS=PROBE)
    def test_a_new_stamp_in_the_data_reaches_the_markup(self):
        with staged_betas_live(), translation.override('en'):
            html = render_selector()
            for key in switcher_order():
                link = re.search(r'<a [^>]*data-version="%s"[^>]*>.*?</a>' % key, html, re.S).group(0)
                self.assertIn('title="%s \u00b7 %s"' % (GAME_VERSIONS[key].game_name, PROBE[key]), link)
                self.assertIn('<span class="version-name">%s</span>' % GAME_VERSIONS[key].game_name, link)
                self.assertIn('<span class="version-patch">%s</span>' % PROBE[key], link)

    @override_settings(SITE_VERSIONS={})
    def test_a_version_without_a_stamp_shows_its_name_alone(self):
        with translation.override('en'):
            html = render_selector()
            for key in switcher_order():
                self.assertEqual(GAME_VERSIONS[key].game_name, switcher_member(key)['title'])
            self.assertNotIn('version-patch', html)
            self.assertNotIn('version-sep', html)

    def test_no_label_says_the_game_twice_in_any_language(self):
        with staged_betas_live():
            for language in ('en', 'fr', 'es', 'pt', 'de'):
                with translation.override(language):
                    html = render_selector()
                    self.assertNotIn('Dofus Dofus', html, language)
                    self.assertNotIn('Dofus&nbsp;Dofus', html, language)
                    self.assertNotIn('Dofus\u00a0Dofus', html, language)

    def test_the_french_rows_write_beta_with_its_accent(self):
        with translation.override('fr'):
            name = switcher_member('beta')['name']
        self.assertIn('B\u00eata', name)
        self.assertTrue(name.startswith(GAME_VERSIONS['dofus3'].game_name))

    def test_the_short_pill_is_hidden_from_readers_and_the_full_label_is_read(self):
        html = render_selector()
        for key in switcher_order():
            link = re.search(r'<a [^>]*data-version="%s"[^>]*>(.*?)</a>' % key, html, re.S).group(1)
            self.assertTrue(link.startswith('<span class="version-short" aria-hidden="true">'), key)
            self.assertIn('<span class="version-full"><span class="version-name">', link)


class EveryDesignDrawsTheMenuTests(SimpleTestCase):

    def test_the_menu_script_runs_in_every_design(self):
        base = base_template()
        self.assertNotIn("if(!h.classList.contains('fm-modern'))return;", base)
        self.assertIn("vsel=vsel||q('.version-selector');", base)
        self.assertIn('if(modern&&end&&hc){', base)
        self.assertIn('if(modern)(function(){', base)

    def test_the_menu_keeps_its_delays_and_its_keys(self):
        base = base_template()
        self.assertIn('vtimer=setTimeout(function(){openVers(m,false);},80);', base)
        self.assertIn('vtimer=setTimeout(function(){closeVers(false);},250);', base)
        self.assertIn("if(e.key!=='ArrowDown')return;", base)
        self.assertIn("if(e.key==='Escape'&&vopen)closeVers(vopen.g.contains(document.activeElement));", base)
        self.assertIn("document.addEventListener('pointerdown',function(e){if(vopen&&!vopen.g.contains(e.target))closeVers(false);});", base)

    def test_the_menu_is_placed_inside_its_own_positioned_box(self):
        self.assertIn('var vr=m.menu.offsetParent.getBoundingClientRect()', base_template())

    def test_a_row_carries_no_tooltip_of_its_own(self):
        self.assertIn("row.className='fm-vs-choice';row.removeAttribute('title');", base_template())

    def test_classic_draws_the_menu_over_the_page(self):
        home = sheet('home.css')
        self.assertIn('position: relative', rule(home, CLASSIC + '.version-selector'))
        menu = rule(home, CLASSIC + '.fm-vs-menu')
        self.assertIn('position: absolute', menu)
        self.assertIn('z-index', menu)
        self.assertIn('display: none', rule(home, CLASSIC + '.fm-vs-menu[hidden]'))
        self.assertIn('display: none !important', rule(home, CLASSIC + '.version-link[hidden]'))
        self.assertIn('display: none', rule(home, CLASSIC + '.fm-vs-menu .version-short'))
        self.assertIn('position: static', rule(home, CLASSIC + '.fm-vs-menu .version-full'))
        self.assertIn('inline-flex', rule(home, CLASSIC + 'button.fm-vs-more'))

    def test_classic_names_its_menu_colours_in_both_themes(self):
        for name in ('home_lighttheme.css', 'home_darktheme.css'):
            text = sheet(name)
            self.assertIn('background: #', rule(text, CLASSIC + '.fm-vs-menu'), name)
            for selector in ('button.fm-vs-more', '.fm-vs-menu a.fm-vs-choice:hover',
                             '.fm-vs-menu a.fm-vs-choice[aria-current="page"]'):
                declarations = rule(text, CLASSIC + selector)
                self.assertIsNotNone(declarations, (name, selector))
                self.assertRegex(declarations, r'(?:^|\s)color: #', (name, selector))
                self.assertNotIn('opacity', declarations, (name, selector))
                self.assertNotIn('inherit', declarations, (name, selector))

    def test_enhanced_draws_the_menu_with_its_tokens(self):
        text = sheet('enhanced.css')
        self.assertIn('html.fm-enhanced .version-selector{ position:relative; }', text)
        menu = rule(text, 'html.fm-enhanced .fm-vs-menu')
        self.assertIn('position:absolute', menu)
        self.assertIn('z-index', menu)
        self.assertIn('var(--fm-surface)', menu)
        self.assertIn('var(--fm-border)', menu)
        self.assertIn('display:none', rule(text, 'html.fm-enhanced .fm-vs-menu[hidden]'))
        self.assertIn('display:none !important', rule(text, 'html.fm-enhanced .version-link[hidden]'))
        self.assertIn('display:none', rule(text, 'html.fm-enhanced .fm-vs-menu .version-short'))
        self.assertIn('position:static', rule(text, 'html.fm-enhanced .fm-vs-menu .version-full'))
        self.assertIn('var(--fm-muted)', rule(text, 'html.fm-enhanced .fm-vs-menu .version-patch'))

    def test_the_atelier_rows_show_the_full_label(self):
        nav = sheet('modern-nav.css')
        self.assertIn('display:none', rule(nav, 'html.fm-modern .fm-vs-menu .version-short'))
        self.assertIn('position:static', rule(nav, 'html.fm-modern .fm-vs-menu .version-full'))

    def test_every_design_hides_the_full_label_inside_the_pill_for_the_eye_only(self):
        hidden = re.search(r'\.version-game-name,\s*\.version-full,\s*\.version-sep\s*\{([^}]*)\}', sheet('home.css')).group(1)
        self.assertIn('position: absolute', hidden)
        self.assertIn('clip', hidden)
        self.assertNotIn('display: none', hidden)


class TheSmallestPhonesKeepTheRowTests(SimpleTestCase):

    def small(self, name, query):
        return sheet(name).split(query, 1)[1].split('\n}', 1)[0]

    def test_classic_keeps_twelve_pixel_text_and_trims_the_padding(self):
        block = self.small('responsive.css', '@media (max-width: 389px) {')
        self.assertIn(CLASSIC + '.version-link { padding:', block)
        self.assertIn(CLASSIC + 'button.fm-vs-more { width:', block)
        self.assertNotIn('font-size', block)
        self.assertIn('.version-link { padding: 7px 11px; font-size: 12px; }', sheet('responsive.css'))

    def test_enhanced_keeps_twelve_pixel_text_and_trims_the_padding(self):
        block = self.small('enhanced.css', '@media (max-width: 389px){')
        self.assertIn('font-size:12px', rule(block, 'html.fm-enhanced .version-link'))
        self.assertIn('width:', rule(block, 'html.fm-enhanced button.fm-vs-more'))

    def test_the_enhanced_tray_opens_centred_on_a_phone(self):
        blocks = [part.split('\n}', 1)[0] for part in sheet('enhanced.css').split('@media (max-width: 600px){')[1:]]
        block = [part for part in blocks if '.compare-cart-panel' in part][0]
        panel = rule(block, 'html.fm-enhanced .compare-cart-panel')
        self.assertIn('left:50%', panel)
        self.assertIn('translateX(-50%)', panel)
        self.assertIn('max-width:calc(100vw - 12px)', panel)


class TheClearButtonStaysOnOneLineTests(SimpleTestCase):

    def test_the_clear_button_never_wraps_nor_shrinks(self):
        for name in ('modern.css', 'modern-core.css'):
            declarations = rule(sheet(name), '.compare-cart-panel .cc-clear')
            self.assertIsNotNone(declarations, name)
            self.assertIn('white-space:nowrap', declarations, name)
            self.assertIn('flex:0 0 auto', declarations, name)

    def test_no_design_lets_the_clear_button_wrap(self):
        for name in ('home.css', 'home_lighttheme.css', 'home_darktheme.css', 'enhanced.css', 'responsive.css',
                     'modern.css', 'modern-nav.css'):
            for match in re.finditer(r'([^{}]*cc-clear[^{}]*)\{([^}]*)\}', sheet(name)):
                self.assertNotRegex(match.group(2), r'white-space:\s*(?:normal|pre-wrap)', name)
