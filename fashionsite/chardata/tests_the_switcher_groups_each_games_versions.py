# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The header switcher groups the versions of each game in one span, main version first, and every design styles the group."""
import os
import re

from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import translation

from chardata.context_processors import switcher_groups
from chardata.tests_the_setup_stylesheet_support import STATIC
from fashionistapulp.game_versions import GAME_VERSIONS, is_beta, switcher_games, version_keys

TEMPLATES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates', 'chardata')
SELECTOR = '<div class="version-selector">'


def sheet(name):
    with open(os.path.join(STATIC, name), encoding='utf-8') as handle:
        return handle.read()


def selector_block(html):
    return html.split(SELECTOR)[1].split('</div>')[0]


def groups_of(block):
    chunks = block.split('<span class="version-game" data-family="')[1:]
    return [(chunk.split('"', 1)[0], re.findall(r'data-version="([^"]+)"', chunk)) for chunk in chunks]


class TheServerMarkupGroupsEachGameTests(TestCase):

    def block(self, path='/'):
        page = self.client.get(path)
        self.assertEqual(page.status_code, 200, path)
        html = page.content.decode('utf-8')
        self.assertEqual(1, html.count(SELECTOR))
        return selector_block(html)

    def test_one_span_per_game_in_registry_order(self):
        families = re.findall(r'<span class="version-game" data-family="([^"]+)"', self.block())
        self.assertEqual([main for main, _ in switcher_games()], families)

    def test_each_span_holds_its_members_main_first(self):
        self.assertEqual(switcher_games(), groups_of(self.block()))

    def test_exactly_one_link_per_reader_version(self):
        keys = re.findall(r'<a [^>]*data-version="([^"]+)"', self.block())
        self.assertEqual(sorted(version_keys()), sorted(keys))

    def test_no_div_opens_inside_the_selector(self):
        self.assertNotIn('<div', self.block())

    def test_every_link_keeps_the_attribute_order_the_page_tests_read(self):
        links = re.findall(r'<a [^>]*>', self.block())
        self.assertTrue(links)
        for tag in links:
            self.assertRegex(tag, r'^<a class="version-link[^"]*"(?: data-version="[^"]*")? href="[^"]+">$')

    def test_the_beta_link_names_its_game_and_wears_the_channel_chip(self):
        beta = re.search(r'<a [^>]*data-version="beta"[^>]*>(.*?)</a>', self.block(), re.S)
        self.assertIn('version-beta', beta.group(0))
        self.assertIn('<span class="version-game-name">Dofus 3\u00a0</span>', beta.group(1))
        self.assertIn('<span class="version-channel">Beta</span>', beta.group(1))

    def test_a_main_link_has_no_game_name_span(self):
        main = re.search(r'<a [^>]*data-version="dofus3"[^>]*>(.*?)</a>', self.block(), re.S).group(1)
        self.assertNotIn('version-game-name', main)
        self.assertTrue(main.startswith('Dofus 3'))

    @override_settings(SITE_VERSIONS={'dofus3': '3.7.14.18', 'beta': '3.8.2.3', 'touch': '1.74'})
    def test_the_patch_number_is_bare_and_hidden_from_readers(self):
        patches = re.findall(r'<span ([^>]*)>([^<]*)</span>', self.block())
        patches = [(attributes, number) for attributes, number in patches if 'version-patch' in attributes]
        self.assertEqual(3, len(patches))
        for attributes, number in patches:
            self.assertIn('aria-hidden="true"', attributes)
            self.assertRegex(number, r'^\d+\.\d+$')

    def test_only_a_game_with_a_beta_carries_the_menu_name(self):
        block = self.block()
        for main, members in switcher_games():
            tag = re.search(r'<span class="version-game" data-family="%s"[^>]*>' % main, block).group(0)
            self.assertEqual(len(members) > 1, 'data-menu=' in tag, main)

    def test_the_menu_name_is_translated(self):
        expected = {'fr': 'Versions de Dofus 3', 'es': 'Versiones de Dofus 3', 'de': 'Dofus 3-Versionen',
                    'pt': 'Versões de Dofus 3', 'en': 'Dofus 3 versions'}
        for language, text in expected.items():
            prefix = '' if language == 'en' else '/' + language
            self.assertIn('data-menu="%s"' % text, self.block(prefix + '/'), language)

    def test_the_active_link_follows_the_current_version(self):
        active = re.findall(r'<a class="version-link[^"]*? active" data-version="([^"]+)"', self.block('/beta/'))
        self.assertEqual(['beta'], active)


class TheGroupsComeFromTheRegistryTests(SimpleTestCase):

    def test_the_groups_are_the_registry_games(self):
        groups = switcher_groups()
        self.assertEqual([main for main, _ in switcher_games()], [group['key'] for group in groups])
        for group, (main, members) in zip(groups, switcher_games()):
            self.assertEqual(members, [member['key'] for member in group['members']])
            self.assertEqual(GAME_VERSIONS[main].label, group['label'])
            self.assertEqual(len(members) > 1, group['has_menu'])
            for member in group['members']:
                self.assertEqual(is_beta(member['key']), member['is_beta'])

    @override_settings(SITE_VERSIONS={'dofus3': '3.7.14.18', 'beta': '3.8.2.3'})
    def test_the_patch_is_major_dot_minor_of_the_site_version(self):
        patches = {member['key']: member['patch'] for group in switcher_groups() for member in group['members']}
        self.assertEqual('3.7', patches['dofus3'])
        self.assertEqual('3.8', patches['beta'])
        self.assertEqual('', patches['touch'])

    def test_the_game_label_is_not_translated(self):
        with translation.override('fr'):
            self.assertEqual('Dofus 3', switcher_groups()[0]['label'])


class EveryDesignStylesTheGroupTests(SimpleTestCase):

    def test_the_name_and_the_patch_are_hidden_for_the_eye_only(self):
        rule = re.search(r'\.version-game-name,\s*\.version-patch\s*\{([^}]*)\}', sheet('home.css')).group(1)
        self.assertIn('position: absolute', rule)
        self.assertIn('clip', rule)
        self.assertNotIn('display: none', rule)
        self.assertNotIn('visibility', rule)

    def test_each_game_is_one_pill_and_the_beta_segment_is_smaller(self):
        home = sheet('home.css')
        self.assertRegex(home, r'\.version-game\s*\{[^}]*border-radius')
        beta = re.search(r'\.version-link\.version-beta\s*\{[^}]*font-size:\s*(\d+)px', home)
        link = re.search(r'\.version-link\s*\{[^}]*font-size:\s*(\d+)px', home)
        self.assertLess(int(beta.group(1)), int(link.group(1)))

    def test_the_classic_themes_separate_segments_inside_the_group(self):
        for name in ('home_darktheme.css', 'home_lighttheme.css'):
            text = sheet(name)
            self.assertNotIn('.version-link:first-child', text, name)
            self.assertNotIn('.version-link:last-child', text, name)
            self.assertIn('.version-link + .version-link { border-left: none; }', text, name)

    def test_enhanced_draws_the_pill_on_the_group_not_the_selector(self):
        text = sheet('enhanced.css')
        self.assertRegex(text, r'html\.fm-enhanced \.version-game\{[^}]*border:1px solid[^}]*border-radius:999px')
        self.assertIn('html.fm-enhanced .version-selector{ border:0 !important;', text)

    def test_the_shared_header_pill_rule_keeps_its_round_corners(self):
        text = sheet('enhanced.css')
        match = re.search(r'html\.fm-enhanced \.login,\s*html\.fm-enhanced \.version-selector\{([^}]*)\}', text)
        self.assertIsNotNone(match)
        self.assertIn('border-radius:999px', match.group(1))
        self.assertRegex(text, r'html\.fm-enhanced \.version-selector\{ border:0 !important; border-radius:0;')

    def test_the_phone_links_never_break_over_two_lines(self):
        text = sheet('responsive.css')
        self.assertRegex(text, r'\.version-link \{[^}]*white-space: nowrap')

    def test_the_atelier_group_rules_sit_under_the_modern_prefix(self):
        nav = sheet('modern-nav.css')
        selectors = [s.strip() for s in re.findall(r'^\s*([^{}@/]*\.version-game[^{}]*)\{', nav, re.M)]
        self.assertGreaterEqual(len(selectors), 4)
        for selector in selectors:
            self.assertTrue(selector.startswith('html.fm-modern'), selector)

    def test_the_atelier_phone_row_lets_each_game_grow(self):
        small = sheet('modern-nav.css').split('@media (max-width:599px){', 1)[1].split('\n}', 1)[0]
        self.assertIn('.version-game{ flex:1 1 auto; }', small)

    def test_the_modern_script_no_longer_reorders_the_links(self):
        with open(os.path.join(TEMPLATES, 'base.html'), encoding='utf-8') as handle:
            base = handle.read()
        self.assertNotIn("['dofus3','beta'", base)
        self.assertNotIn('vsel.appendChild', base)
