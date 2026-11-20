# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The header design picker offers the three designs, stores the pick under fm_design_v2 and reloads only when the design changes."""
import io
import json
import os
import re
import subprocess
import unittest
from html.parser import HTMLParser

from django.test import SimpleTestCase, TestCase
from django.utils import translation
from django.utils.translation import gettext

from chardata.tests_the_default_theme_is_automatic_and_a_stored_choice_wins import NODE
from chardata.tests_the_setup_stylesheet_support import stylesheet

TEMPLATES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates', 'chardata')
LABELS = {
    'fr': {'Design': 'Design', 'Classic': 'Classique', 'Enhanced classic': 'Classique amélioré', 'New': 'Nouveau'},
    'de': {'Design': 'Darstellung', 'Classic': 'Klassisch', 'Enhanced classic': 'Klassisch (verbessert)', 'New': 'Neu'},
    'es': {'Design': 'Diseño', 'Classic': 'Clásico', 'Enhanced classic': 'Clásico mejorado', 'New': 'Nuevo'},
    'pt': {'Design': 'Visual', 'Classic': 'Clássico', 'Enhanced classic': 'Clássico aprimorado', 'New': 'Novo'},
}
CLASSES = {'classic': ['fm-light'], 'enhanced': ['fm-enhanced', 'fm-light'], 'atelier': ['fm-modern', 'fm-light']}

HARNESS = '''
var vm = require('vm'), src = process.argv[1], opt = JSON.parse(process.argv[2]);
var classes = new Set(opt.classes), store = Object.assign({}, opt.storage || {}), writes = [], reloads = 0, focused = null, listeners = {}, stopped = false;
function el(attrs){ return {attrs: Object.assign({}, attrs), getAttribute: function(k){ return k in this.attrs ? this.attrs[k] : null; },
  setAttribute: function(k, v){ this.attrs[k] = String(v); }, focus: function(){ focused = this; }}; }
var choices = ['classic', 'enhanced', 'atelier'].map(function(d){ return el({'data-design': d, 'aria-pressed': 'false'}); });
var menu = el({id: 'fm-design-menu'}), button = el({'aria-controls': 'fm-design-menu', 'aria-expanded': 'false'}), outside = el({});
menu.hidden = true;
menu.querySelectorAll = function(){ return choices; };
menu.querySelector = function(){ return choices.filter(function(c){ return c.attrs['aria-pressed'] === 'true'; })[0] || null; };
button.parentNode = {contains: function(n){ return n === button || n === menu || choices.indexOf(n) >= 0; }};
function on(n, f){ (listeners[n] = listeners[n] || []).push(f); }
function fire(n, e){ (listeners[n] || []).forEach(function(f){ f(e); }); }
var document = {documentElement: {classList: {contains: function(c){ return classes.has(c); }}},
  getElementById: function(id){ return id === 'fm-design-menu' ? menu : null; },
  querySelector: function(s){ if (s === '.fm-design-toggle') return button; if (s === '.fm-design-toggle[aria-expanded="true"]') return button.attrs['aria-expanded'] === 'true' ? button : null; return null; },
  addEventListener: function(n, f){ on(n, f); }};
var storage = {getItem: function(k){ if (opt.readThrows) throw new Error('blocked'); return Object.prototype.hasOwnProperty.call(store, k) ? store[k] : null; },
  setItem: function(k, v){ if (opt.writeThrows) throw new Error('quota'); writes.push([k, v]); store[k] = v; }};
var ctx = {document: document, window: {addEventListener: function(n, f){ on('window:' + n, f); }}, localStorage: storage, location: {reload: function(){ reloads++; }}};
vm.runInNewContext(src, ctx);
opt.steps.forEach(function(step){
  if (step[0] === 'toggle') ctx.fmDesignMenu(button);
  else if (step[0] === 'pick') ctx.fmSetDesign(step[1]);
  else if (step[0] === 'key') fire('keydown', {key: step[1], stopPropagation: function(){ stopped = true; }});
  else if (step[0] === 'click') fire('click', {target: step[1] === 'inside' ? choices[0] : outside});
  else if (step[0] === 'pointerdown') fire('pointerdown', {target: step[1] === 'inside' ? choices[0] : outside});
  else if (step[0] === 'focusout') fire('focusout', {relatedTarget: step[1] === 'inside' ? choices[1] : (step[1] === 'nowhere' ? null : outside)});
  else if (step[0] === 'pageshow') fire('window:pageshow', {persisted: step[1]});
});
console.log(JSON.stringify({writes: writes, reloads: reloads, expanded: button.attrs['aria-expanded'], hidden: menu.hidden, stopped: stopped,
  focused: focused === button ? 'button' : (focused ? focused.attrs['data-design'] : null), pressed: choices.map(function(c){ return c.attrs['aria-pressed']; })}));
'''


class StartTags(HTMLParser):
    """The start tags of a fragment as (tag, attributes) pairs."""

    def __init__(self, text):
        super().__init__()
        self.found = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        self.found.append((tag, dict(attrs)))


def base():
    with io.open(os.path.join(TEMPLATES, 'base.html'), encoding='utf-8') as handle:
        return handle.read()


def picker_script():
    return re.search(r'(function fmDesign\(\)\{.*?)</script>', base(), re.S).group(1)


def run_picker(design, steps, **options):
    options.update({'classes': CLASSES[design], 'steps': steps})
    done = subprocess.run([NODE, '-e', HARNESS, picker_script(), json.dumps(options)], capture_output=True, text=True, timeout=60)
    if done.returncode:
        raise AssertionError(done.stderr)
    return json.loads(done.stdout)


class ThePickerMarkupOffersThreeDesignsTests(TestCase):

    def test_the_rendered_header_holds_a_closed_disclosure_with_the_three_designs(self):
        html = self.client.get('/').content.decode('utf-8')
        picker = re.search(r'<div class="fm-design-picker">(.*?)</div></div>', html, re.S).group(1)
        tags = StartTags(picker).found
        toggles = [attrs for tag, attrs in tags if tag == 'button' and attrs.get('class') == 'fm-design-toggle']
        menus = [attrs for tag, attrs in tags if tag == 'div' and attrs.get('class') == 'fm-design-menu']
        self.assertEqual((1, 1), (len(toggles), len(menus)))
        self.assertEqual('false', toggles[0]['aria-expanded'])
        self.assertEqual(toggles[0]['aria-controls'], menus[0]['id'])
        self.assertEqual('group', menus[0]['role'])
        self.assertTrue(menus[0]['aria-label'])
        self.assertIn('hidden', menus[0])
        choices = [attrs for tag, attrs in tags if tag == 'button' and 'data-design' in attrs]
        self.assertEqual(['classic', 'enhanced', 'atelier'], [attrs['data-design'] for attrs in choices])
        self.assertEqual({'false'}, {attrs['aria-pressed'] for attrs in choices})

    def test_the_header_move_carries_the_whole_picker_into_the_new_navigation(self):
        text = base()
        self.assertIn("move(q('.fm-design-picker',hc),end);", text)
        self.assertNotIn("move(q('.fm-design-toggle',hc),end);", text)

    def test_the_old_toggle_is_gone(self):
        text = base()
        for gone in ('fmToggleDesign', 'Classic look', 'New look', 'Switch between the classic and new design'):
            self.assertNotIn(gone, text)


class ThePickerIsHiddenWhereItCannotWorkTests(SimpleTestCase):

    def test_a_page_without_scripts_hides_the_picker_in_its_own_noscript_style(self):
        text = base()
        self.assertIn('<noscript><style>.fm-design-picker{display:none}</style></noscript>', text)
        self.assertIn('<noscript><style>.banner img[data-fm-src]{display:none}</style></noscript>', text)

    def test_a_storage_that_throws_hides_the_picker_from_the_first_paint(self):
        for sheet in ('modern.css', 'modern-core.css'):
            rules = [rule for rule in stylesheet(sheet) if 'html.fm-nostore .fm-design-picker' in rule['selectors']]
            self.assertEqual([{'display': ('none', False)}], [rule['declarations'] for rule in rules], sheet)

    def test_the_phone_menu_never_unhides_the_picker_when_storage_throws(self):
        rules = [rule for rule in stylesheet('modern-nav.css') if rule['declarations'].get('display', (None,))[0] == 'contents'
                 and any('.fm-design-picker' in selector for selector in rule['selectors'])]
        self.assertTrue(rules)
        for rule in rules:
            for selector in rule['selectors']:
                self.assertIn(':not(.fm-nostore)', selector)


@unittest.skipUnless(NODE, 'node is not installed')
class ThePickerStoresAndReloadsTests(SimpleTestCase):

    def test_a_change_of_design_stores_it_and_reloads_once(self):
        for design, pick in (('atelier', 'classic'), ('atelier', 'enhanced'), ('classic', 'atelier'), ('enhanced', 'classic')):
            result = run_picker(design, [['toggle'], ['pick', pick]])
            self.assertEqual([['fm_design_v2', pick]], result['writes'], (design, pick))
            self.assertEqual(1, result['reloads'], (design, pick))

    def test_a_default_visitor_who_picks_the_new_design_is_recorded_without_a_reload(self):
        result = run_picker('atelier', [['toggle'], ['pick', 'atelier']])
        self.assertEqual([['fm_design_v2', 'atelier']], result['writes'])
        self.assertEqual(0, result['reloads'])
        self.assertEqual(('false', True, 'button'), (result['expanded'], result['hidden'], result['focused']))

    def test_picking_the_stored_current_design_writes_nothing_and_closes_the_menu(self):
        result = run_picker('enhanced', [['toggle'], ['pick', 'enhanced']], storage={'fm_design_v2': 'enhanced'})
        self.assertEqual(([], 0), (result['writes'], result['reloads']))
        self.assertEqual(('false', True, 'button'), (result['expanded'], result['hidden'], result['focused']))

    def test_a_storage_that_refuses_the_write_does_not_reload(self):
        for options in ({'writeThrows': True}, {'readThrows': True}):
            result = run_picker('atelier', [['toggle'], ['pick', 'classic']], **options)
            self.assertEqual(([], 0), (result['writes'], result['reloads']), options)
            self.assertEqual('false', result['expanded'], options)

    def test_opening_marks_the_current_design_and_focuses_it(self):
        for design, pressed in (('classic', ['true', 'false', 'false']), ('enhanced', ['false', 'true', 'false']),
                                ('atelier', ['false', 'false', 'true'])):
            result = run_picker(design, [['toggle']])
            self.assertEqual(('true', False), (result['expanded'], result['hidden']), design)
            self.assertEqual(pressed, result['pressed'], design)
            self.assertEqual(design, result['focused'])

    def test_escape_closes_the_menu_returns_focus_and_stops_the_key(self):
        result = run_picker('atelier', [['toggle'], ['key', 'Escape']])
        self.assertEqual(('false', True, 'button', True), (result['expanded'], result['hidden'], result['focused'], result['stopped']))
        self.assertFalse(run_picker('atelier', [['key', 'Escape']])['stopped'])

    def test_a_click_or_a_focus_outside_closes_the_menu_and_one_inside_keeps_it(self):
        for step, expected in ((['click', 'outside'], 'false'), (['click', 'inside'], 'true'), (['focusout', 'outside'], 'false'),
                               (['focusout', 'inside'], 'true'), (['focusout', 'nowhere'], 'true')):
            self.assertEqual(expected, run_picker('classic', [['toggle'], step])['expanded'], step)

    def test_a_pointer_press_outside_closes_the_menu_and_one_inside_keeps_it(self):
        self.assertIn("document.addEventListener('pointerdown',function(e){var b=fmDesignOpen();if(b&&!b.parentNode.contains(e.target))fmDesignMenu(b,false);});", picker_script())
        for where, expected in (('outside', 'false'), ('inside', 'true')):
            self.assertEqual(expected, run_picker('atelier', [['toggle'], ['pointerdown', where]])['expanded'], where)

    def test_a_page_restored_from_the_back_forward_cache_reloads_only_when_the_stored_design_differs(self):
        cases = ((True, {'fm_design_v2': 'classic'}, 1), (True, {}, 0), (True, {'fm_design_v2': 'atelier'}, 0),
                 (False, {'fm_design_v2': 'classic'}, 0))
        for persisted, storage, reloads in cases:
            result = run_picker('atelier', [['pageshow', persisted]], storage=storage)
            self.assertEqual(reloads, result['reloads'], (persisted, storage))
        self.assertEqual(0, run_picker('atelier', [['pageshow', True]], readThrows=True)['reloads'])


class ThePickerLabelsAreTranslatedTests(SimpleTestCase):

    def test_the_four_labels_come_out_in_every_other_language(self):
        for language, labels in LABELS.items():
            with translation.override(language):
                for english, expected in labels.items():
                    self.assertEqual(expected, gettext(english), (language, english))
