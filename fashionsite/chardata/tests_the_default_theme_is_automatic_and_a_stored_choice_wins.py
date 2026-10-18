# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A visitor who never picked a theme follows the browser's colour scheme, and a visitor who did pick one keeps it. The theme cookie is the only store: a first visit is given automatic for the browser session, and a pick from the theme menu is kept for a year."""
import io
import os
import json
import re
import shutil
import subprocess
import unittest

from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, TestCase

from chardata.themes import ALLOWED_THEMES, check_theme, get_theme
from fashionsite import settings, settings_dev

TEMPLATES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates', 'chardata')


def request_with(**cookies):
    request = RequestFactory().get('/')
    request.COOKIES.update(cookies)
    return request


def head_script():
    with io.open(os.path.join(TEMPLATES, 'base.html'), encoding='utf-8') as handle:
        text = handle.read()
    return re.search(r'<script>\s*(\(function\(\)\{var h=document\.documentElement,d=.*?)</script>', text, re.S).group(1)


NODE = shutil.which('node')

HARNESS = '''
var vm = require('vm'), src = process.argv[1], opt = JSON.parse(process.argv[2]);
var classes = new Set(), ready = [], links = (opt.lightLinks || []).map(function(){ var a = {media: 'light'}; a.removeAttribute = function(){ a.media = null; }; return a; });
var document = {documentElement: {classList: {add: function(c){ classes.add(c); }, remove: function(){ for (var i = 0; i < arguments.length; i++) classes.delete(arguments[i]); }, contains: function(c){ return classes.has(c); }}},
  cookie: opt.cookie || '', addEventListener: function(n, f){ if (n === 'DOMContentLoaded') ready.push(f); }, querySelectorAll: function(s){ return s === 'link[media="(prefers-color-scheme: light)"]' ? links : []; }};
var ctx = {document: document, window: {}};
ctx.window.matchMedia = opt.noMatchMedia ? undefined : function(q){ return {matches: !!opt.matches[q], addEventListener: function(){}}; };
if (opt.storageThrows) Object.defineProperty(ctx, 'localStorage', {get: function(){ throw new Error('blocked'); }});
else ctx.localStorage = {getItem: function(){ return opt.design || null; }};
vm.runInNewContext(src, ctx);
ready.forEach(function(f){ f(); });
console.log(JSON.stringify({classes: Array.from(classes).sort(), auto: typeof ctx.window.fmAutoTheme === 'function' ? ctx.window.fmAutoTheme() : null, media: links.map(function(l){ return l.media; })}));
'''


def run_node(harness, source, options):
    done = subprocess.run([NODE, '-e', harness, source, json.dumps(options)], capture_output=True, text=True, timeout=60)
    if done.returncode:
        raise AssertionError(done.stderr)
    return json.loads(done.stdout)


def run_head(**options):
    options.setdefault('matches', {})
    return run_node(HARNESS, head_script(), options)


def set_sheets_script():
    with io.open(os.path.join(TEMPLATES, 'base.html'), encoding='utf-8') as handle:
        text = handle.read()
    return re.search(r'(function fmSetSheets\(data, auto\)\{.*?)\s*function fmApplyThemeClass', text, re.S).group(1)


SET_SHEETS_HARNESS = '''
var vm = require('vm'), src = process.argv[1], opt = JSON.parse(process.argv[2]);
var links = opt.links.map(function(l){ return {cls: l[0], media: l[1], href: l[2]}; }), seen = [];
function W(items){ this.items = items; }
W.prototype.each = function(f){ this.items.slice().forEach(function(it){ f.call(it); }); return this; };
W.prototype.attr = function(k, v){ var it = this.items[0]; if (typeof k === 'object') { for (var key in k) it[key] = k[key]; return this; } if (v === undefined) return it[k] === null ? undefined : it[k]; it[k] = v; return this; };
W.prototype.removeAttr = function(k){ this.items[0][k] = null; return this; };
W.prototype.remove = function(){ var i = links.indexOf(this.items[0]); if (i >= 0) links.splice(i, 1); return this; };
W.prototype.clone = function(){ var it = this.items[0]; return new W([{cls: it.cls, media: it.media, href: it.href}]); };
W.prototype.insertAfter = function(other){ links.splice(links.indexOf(other.items[0]) + 1, 0, this.items[0]); return this; };
function $(x){ if (typeof x === 'string') { var c = x.split('.')[1].replace('-css', ''); return new W(links.filter(function(l){ return l.cls === c; })); } return new W([x]); }
function data(theme){ var d = {}; ['common', 'forms'].forEach(function(n){ d[n] = n + '_' + theme; d[n + 'lighttheme'] = n + '_lighttheme'; d[n + 'darktheme'] = n + '_darktheme'; }); return d; }
var ctx = {$: $, fmSchemeKnown: function(){ return opt.known; }};
vm.runInNewContext(src, ctx);
opt.calls.forEach(function(theme){ ctx.fmSetSheets(data(theme), theme === 'auto'); seen.push(links.map(function(l){ return [l.cls, l.media, l.href]; })); });
console.log(JSON.stringify(seen));
'''


def run_set_sheets(known, calls, links):
    return run_node(SET_SHEETS_HARNESS, set_sheets_script(), {'known': known, 'calls': calls, 'links': links})


def encyclopedia_item_script():
    with io.open(os.path.join(TEMPLATES, 'encyclopedia_item.html'), encoding='utf-8') as handle:
        text = handle.read()
    return re.search(r'<script>\s*(\(function\(\) \{\s*var root = document\.documentElement;.*?)</script>', text, re.S).group(1)


ENCYCLOPEDIA_HARNESS = '''
var vm = require('vm'), src = process.argv[1], opt = JSON.parse(process.argv[2]);
function list(){ var s = new Set(); return {add: function(c){ s.add(c); }, remove: function(){ for (var i = 0; i < arguments.length; i++) s.delete(arguments[i]); }, contains: function(c){ return s.has(c); }, toggle: function(c, on){ if (on) s.add(c); else s.delete(c); }}; }
var root = {classList: list()}, body = {classList: list()}, observed = null, filter = null, out = [];
opt.start.forEach(function(c){ root.classList.add(c); });
function MutationObserver(f){ this.observe = function(target, o){ if (target === root) { observed = f; filter = o.attributeFilter; } }; }
vm.runInNewContext(src, {document: {documentElement: root, body: body}, MutationObserver: MutationObserver});
out.push(body.classList.contains('dark-theme-active'));
opt.steps.forEach(function(dark){ root.classList.remove('fm-light', 'fm-dark'); root.classList.add(dark ? 'fm-dark' : 'fm-light'); if (observed) observed([]); out.push(body.classList.contains('dark-theme-active')); });
console.log(JSON.stringify({states: out, filter: filter}));
'''


class DefaultThemeTests(SimpleTestCase):

    def test_the_default_is_the_value_the_code_already_calls_automatic(self):
        self.assertEqual('auto', settings.DEFAULT_THEME)
        self.assertEqual('auto', settings_dev.DEFAULT_THEME)
        self.assertIn(settings.DEFAULT_THEME, ALLOWED_THEMES)

    def test_a_visitor_without_the_cookie_is_automatic(self):
        self.assertEqual('auto', get_theme(request_with()))

    def test_a_visitor_with_a_stored_choice_keeps_it(self):
        for choice in ('lighttheme', 'darktheme', 'auto'):
            self.assertEqual(choice, get_theme(request_with(theme=choice)))

    def test_a_new_visitor_is_given_the_automatic_cookie(self):
        response = HttpResponse()
        check_theme(request_with(), response)
        self.assertEqual('auto', response.cookies['theme'].value)

    def test_a_stored_choice_is_never_overwritten_by_the_default(self):
        for choice in ('lighttheme', 'darktheme'):
            response = HttpResponse()
            check_theme(request_with(theme=choice), response)
            self.assertNotIn('theme', response.cookies)

    def test_the_page_head_falls_back_to_automatic_when_the_cookie_is_missing(self):
        text = head_script()
        self.assertIn("||[])[1]||'auto';", text)
        self.assertNotIn("||'lighttheme'", text)

    def test_automatic_follows_the_browser_colour_scheme_and_not_the_clock(self):
        text = head_script()
        self.assertIn("window.matchMedia('(prefers-color-scheme: dark)')", text)
        self.assertIn("{matches:false}", text)
        self.assertIn("d.matches?'darktheme':'lighttheme'", text)
        self.assertIn("h.classList.add(c()==='darktheme'?'fm-dark':'fm-light')", text)
        self.assertNotIn('getHours', text)

    def test_a_live_change_of_the_colour_scheme_is_followed(self):
        text = head_script()
        self.assertIn("d.addEventListener('change',a)", text)

    def test_no_template_decides_the_theme_by_the_hour(self):
        for name in os.listdir(TEMPLATES):
            if name.endswith('.html'):
                with io.open(os.path.join(TEMPLATES, name), encoding='utf-8') as handle:
                    self.assertNotIn('getHours', handle.read(), name)

    def test_the_page_no_longer_posts_the_resolved_theme_to_the_server(self):
        with io.open(os.path.join(TEMPLATES, 'base.html'), encoding='utf-8') as handle:
            self.assertNotIn('changeautotheme', handle.read())

    def test_the_modern_design_is_the_default_and_classic_is_a_stored_choice(self):
        text = head_script()
        self.assertIn("if(localStorage.getItem('fm_design')!=='classic')h.classList.add('fm-modern')", text)

    def test_the_automatic_resolver_is_defined_before_the_storage_is_touched(self):
        text = head_script()
        self.assertLess(text.index('window.fmAutoTheme='), text.index('localStorage'))



@unittest.skipUnless(NODE, 'node is not installed')
class HeadScriptBehaviourTests(SimpleTestCase):
    DARK = '(prefers-color-scheme: dark)'
    LIGHT = '(prefers-color-scheme: light)'

    def test_a_page_whose_storage_throws_still_defines_the_resolver_and_sets_the_theme_class(self):
        for matches, expected in (({self.DARK: True}, 'fm-dark'), ({self.LIGHT: True}, 'fm-light')):
            result = run_head(storageThrows=True, cookie='theme=auto', matches=matches)
            self.assertIn(expected, result['classes'], matches)
            self.assertIn(result['auto'], ('darktheme', 'lighttheme'))

    def test_a_page_whose_storage_throws_gets_the_modern_design(self):
        self.assertIn('fm-modern', run_head(storageThrows=True, cookie='theme=auto')['classes'])

    def test_a_stored_classic_choice_is_not_given_the_modern_design(self):
        self.assertNotIn('fm-modern', run_head(design='classic', cookie='theme=auto')['classes'])

    def test_a_browser_that_answers_neither_scheme_query_gets_the_light_sheets_without_media(self):
        for options in ({'matches': {}}, {'noMatchMedia': True}):
            result = run_head(lightLinks=[1, 2], cookie='theme=auto', **options)
            self.assertEqual([None, None], result['media'], options)
            self.assertIn('fm-light', result['classes'])

    def test_a_browser_that_answers_a_scheme_query_keeps_the_media_pair(self):
        for matches in ({self.DARK: True}, {self.LIGHT: True}):
            result = run_head(lightLinks=[1, 2], cookie='theme=auto', matches=matches)
            self.assertEqual(['light', 'light'], result['media'], matches)

    def test_a_cookie_that_is_not_a_theme_follows_the_browser_like_automatic(self):
        for matches, expected in (({self.DARK: True}, 'fm-dark'), ({self.LIGHT: True}, 'fm-light')):
            self.assertIn(expected, run_head(cookie='theme=bogus', matches=matches)['classes'], matches)

    def test_a_chosen_theme_wins_over_the_browser_scheme(self):
        self.assertIn('fm-light', run_head(cookie='theme=lighttheme', matches={self.DARK: True})['classes'])
        self.assertIn('fm-dark', run_head(cookie='theme=darktheme', matches={self.LIGHT: True})['classes'])


PAIR = [['common', '(prefers-color-scheme: light)', 'common_lighttheme'], ['common', '(prefers-color-scheme: dark)', 'common_darktheme']]
UNPAIRED = [['common', None, 'common_lighttheme'], ['common', '(prefers-color-scheme: dark)', 'common_darktheme']]
SINGLE_DARK = [['common', None, 'common_darktheme']]
SINGLE_LIGHT = [['common', None, 'common_lighttheme']]


@unittest.skipUnless(NODE, 'node is not installed')
class ThemeSwitchKeepsOneSheetKindTests(SimpleTestCase):

    def test_a_browser_without_scheme_queries_gets_the_light_sheet_alone_when_it_switches_to_automatic(self):
        for links in (PAIR, UNPAIRED, SINGLE_DARK):
            for state in run_set_sheets(False, ['auto', 'auto'], links):
                self.assertEqual(SINGLE_LIGHT, state, links)

    def test_a_browser_without_scheme_queries_never_piles_up_sheets_across_switches(self):
        states = run_set_sheets(False, ['darktheme', 'auto', 'lighttheme', 'auto', 'darktheme'], UNPAIRED)
        self.assertEqual([SINGLE_DARK, SINGLE_LIGHT, SINGLE_LIGHT, SINGLE_LIGHT, SINGLE_DARK], states)

    def test_a_browser_with_scheme_queries_gets_the_pair_back_when_it_switches_to_automatic(self):
        states = run_set_sheets(True, ['darktheme', 'auto', 'auto'], PAIR)
        self.assertEqual([SINGLE_DARK, PAIR, PAIR], states)


@unittest.skipUnless(NODE, 'node is not installed')
class EncyclopediaItemFollowsTheRootClassTests(SimpleTestCase):

    def run_page(self, start, steps):
        return run_node(ENCYCLOPEDIA_HARNESS, encyclopedia_item_script(), {'start': start, 'steps': steps})

    def test_the_dark_state_comes_from_the_root_class(self):
        self.assertEqual([True], self.run_page(['fm-modern', 'fm-dark'], [])['states'])
        self.assertEqual([False], self.run_page(['fm-modern', 'fm-light'], [])['states'])

    def test_a_change_of_the_root_class_is_followed(self):
        result = self.run_page(['fm-light'], [True, False, True])
        self.assertEqual([False, True, False, True], result['states'])
        self.assertEqual(['class'], result['filter'])


LIGHT_MEDIA = 'media="(prefers-color-scheme: light)"'
DARK_MEDIA = 'media="(prefers-color-scheme: dark)"'


def common_links(html):
    return re.findall(r'<link[^>]*class="common-css"[^>]*>', html)


class RenderedStylesheetTests(TestCase):

    def page(self, theme=None):
        if theme is not None:
            self.client.cookies['theme'] = theme
        return self.client.get('/faq/').content.decode('utf-8')

    def test_automatic_renders_both_stylesheets_and_lets_the_browser_pick(self):
        for theme in (None, 'auto'):
            self.client.cookies.clear()
            links = common_links(self.page(theme))
            self.assertEqual(2, len(links), theme)
            self.assertIn('common_lighttheme.css', links[0])
            self.assertIn(LIGHT_MEDIA, links[0])
            self.assertIn('common_darktheme.css', links[1])
            self.assertIn(DARK_MEDIA, links[1])

    def test_automatic_does_not_depend_on_the_current_auto_cookie(self):
        self.client.cookies['current_auto'] = 'lighttheme'
        first = common_links(self.page('auto'))
        self.client.cookies['current_auto'] = 'darktheme'
        self.assertEqual(first, common_links(self.page('auto')))

    def test_a_chosen_light_theme_renders_one_stylesheet_without_media(self):
        links = common_links(self.page('lighttheme'))
        self.assertEqual(1, len(links))
        self.assertIn('common_lighttheme.css', links[0])
        self.assertNotIn('media=', links[0])

    def test_a_chosen_dark_theme_renders_one_stylesheet_without_media(self):
        links = common_links(self.page('darktheme'))
        self.assertEqual(1, len(links))
        self.assertIn('common_darktheme.css', links[0])
        self.assertNotIn('media=', links[0])

    def test_every_themed_sheet_of_a_page_is_paired_in_automatic_and_single_otherwise(self):
        self.client.cookies['theme'] = 'auto'
        html = self.client.get('/faq/').content.decode('utf-8')
        pairs = re.findall(r'class="(\w+-css)[ "][^>]*media="\(prefers-color-scheme: (light|dark)\)"', html)
        names = {name for name, _ in pairs}
        self.assertTrue({'home-css', 'common-css', 'changelog-css', 'forms-css'} <= names)
        for name in names:
            kinds = [kind for n, kind in pairs if n == name]
            self.assertEqual(kinds.count('light'), kinds.count('dark'), name)
            self.assertGreaterEqual(kinds.count('light'), 1, name)
        self.client.cookies['theme'] = 'darktheme'
        html = self.client.get('/faq/').content.decode('utf-8')
        self.assertNotIn('prefers-color-scheme', re.sub(r'<script>.*?</script>', '', html, flags=re.S))

    def test_the_head_script_unpairs_exactly_the_light_links_the_page_renders(self):
        selector = re.search(r"querySelectorAll\('link\[(media=\"[^\"]+\")\]'\)", head_script()).group(1)
        self.assertEqual(LIGHT_MEDIA, selector)
        self.assertIn(LIGHT_MEDIA, ''.join(common_links(self.page('auto'))))

    def test_a_value_that_is_not_a_theme_renders_like_automatic(self):
        self.client.cookies.clear()
        expected = common_links(self.page('auto'))
        self.client.cookies.clear()
        self.assertEqual(expected, common_links(self.page('bogus')))
        self.assertEqual(2, len(expected))
