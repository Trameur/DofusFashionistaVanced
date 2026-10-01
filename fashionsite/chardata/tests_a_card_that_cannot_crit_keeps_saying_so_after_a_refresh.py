# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A card that cannot crit keeps its no-crit block through every redraw, a card that can keeps its rows."""
import json
import os
import pickle
import re
import shutil
import subprocess
import tempfile

from django.test import TestCase

LEVEL = 200

_DRIVER = r"""
var vm = require('vm');
var readyCallbacks = [];
function make(html) {
  var node = {_html: String(html), _kids: [], _sub: null, _damage: null, _hidden: false,
              _parent: null};
  var proxy = new Proxy(node, {
    get: function (target, prop) {
      if (prop in target) return target[prop];
      if (prop === 'append') return function () {
        for (var i = 0; i < arguments.length; i++) {
          var kid = arguments[i];
          if (kid !== undefined && kid !== null) {
            node._kids.push(typeof kid === 'string' ? make(kid) : kid);
          }
        }
        return proxy;
      };
      if (prop === 'appendTo') return function (parent) { parent.append(proxy); return proxy; };
      if (prop === 'empty') return function () { node._kids = []; return proxy; };
      if (prop === 'hide') return function () { node._hidden = true; return proxy; };
      if (prop === 'show') return function () { node._hidden = false; return proxy; };
      if (prop === 'ready') return function (callback) {
        readyCallbacks.push(callback);
        return proxy;
      };
      if (prop === 'find') return function () {
        var found = make('');
        found._parent = proxy;
        return found;
      };
      if (prop === 'end') return function () { return node._parent || proxy; };
      if (prop === 'text') return function (value) {
        if (value === undefined) return '';
        if (node._parent) { node._parent._sub = value; } else { node._sub = value; }
        return proxy;
      };
      if (prop === 'length') return 1;
      if (prop === 'val' || prop === 'attr' || prop === 'data' || prop === 'prop') {
        return function (name, value) { return arguments.length > 1 ? proxy : undefined; };
      }
      if (typeof prop === 'symbol') return undefined;
      return function () { return proxy; };
    }
  });
  return proxy;
}
var statics = {
  each: function (items, callback) {
    if (!items) return items;
    var keys = Array.isArray(items) ? items.map(function (_v, i) { return i; })
                                    : Object.keys(items);
    for (var i = 0; i < keys.length; i++) {
      if (callback.call(items[keys[i]], keys[i], items[keys[i]]) === false) break;
    }
    return items;
  },
  extend: function () {
    var args = Array.prototype.slice.call(arguments);
    if (typeof args[0] === 'boolean') args.shift();
    for (var i = 1; i < args.length; i++) Object.assign(args[0], args[i]);
    return args[0];
  },
  isArray: Array.isArray,
  trim: function (text) { return String(text).trim(); },
  inArray: function (value, items) { return items.indexOf(value); }
};
global.$ = new Proxy(function (selector) {
  return make(typeof selector === 'string' ? selector : '');
}, {
  get: function (target, prop) {
    return prop in statics ? statics[prop] : function () { return make(''); };
  }
});
global.jQuery = global.$;
global.document = {};
global.window = {location: {pathname: '/', search: '', hash: ''}, addEventListener: function () {}};
global.localStorage = {getItem: function () { return null; }, setItem: function () {}};
global.setTimeout = function () {};
vm.runInThisContext(source);
readyCallbacks.forEach(function (callback) { callback(); });
writeDamageLine = function (element, minDam, maxDam, heals, steals, table) {
  var node = make('');
  node._damage = [element, minDam, maxDam];
  table.append(node);
};
function html(node) {
  return node._html + node._kids.map(html).join('');
}
function damageRows(node) {
  return (node._damage ? 1 : 0) + node._kids.reduce(function (total, kid) {
    return total + damageRows(kid);
  }, 0);
}
function state() {
  var out = {};
  spellDigests.forEach(function (spell) {
    var cell = cells[spell.name];
    if (!cell) return;
    out[spell.canonical || spell.name] = {
      critBlock: hasCritBlock(spell),
      titleHidden: cell.critTitle._hidden,
      critHidden: cell.crit._hidden,
      normalLabelHidden: cell.normalLabel._hidden,
      title: html(cell.critTitle),
      crit: html(cell.crit),
      critDamageRows: damageRows(cell.crit)};
  });
  return out;
}
var drawn = {built: state()};
recalculateDamages();
drawn.refreshed = state();
recalculateDamages();
drawn.again = state();
console.log(JSON.stringify(drawn));
"""

_NO_CRIT_NOTE = 'This spell never lands one.'


class TheNoCritBlockStaysTests(TestCase):

    def _build(self, char_class, version):
        from django.contrib.auth.models import User
        from chardata.models import Char
        from fashionistapulp.modelresult import ModelResultMinimal
        owner = User.objects.create_user('nocrit', 'nocrit@test.local', 'pw-42-solid')
        base_input = {
            'options': {'ap_exo': False, 'mp_exo': False},
            'origin': 'generated', 'char_level': LEVEL,
            'base_stats_by_attr': {'Vitality': 0, 'Wisdom': 0, 'Strength': 0,
                                   'Intelligence': 0, 'Chance': 0, 'Agility': 0},
            'locked_equips': {},
        }
        stats = {'vit': 0, 'wis': 0, 'str': 0, 'int': 0, 'cha': 0, 'agi': 0}
        self.client.force_login(owner)
        return Char.objects.create(
            name='NoCrit', char_name='nocrit', char_class=char_class,
            char_build='build', level=LEVEL,
            minimum_stats=b'', minimum_crits=b'', stats_weight=b'',
            options=b'', inclusions=b'', exclusions=b'',
            minimal_solution=pickle.dumps(ModelResultMinimal({}, base_input, stats)),
            owner=owner, link_shared=True, game_version=version)

    def _drawn(self, version, char_class):
        """Every card of the class as the page's script leaves it after building, then after two redraws."""
        node = shutil.which('node')
        if node is None:
            self.skipTest('node is not installed')
        from fashionistapulp.structure import set_current_game_version
        set_current_game_version(version)
        self.addCleanup(set_current_game_version, 'dofus3')
        char = self._build(char_class, version)
        prefix = '' if version == 'dofus3' else version + '/'
        page = self.client.get('/%sspells/%d/' % (prefix, char.pk),
                               HTTP_ACCEPT_LANGUAGE='en')
        self.assertEqual(200, page.status_code)
        scripts = [body for body in re.findall(r'<script[^>]*>(.*?)</script>',
                                               page.content.decode('utf-8'), re.S)
                   if 'var spellDigests' in body]
        self.assertEqual(1, len(scripts))
        with tempfile.NamedTemporaryFile('w', suffix='.js', encoding='utf-8',
                                         delete=False) as handle:
            handle.write('var source = %s;\n%s' % (json.dumps(scripts[0]), _DRIVER))
            name = handle.name
        try:
            done = subprocess.run([node, name], capture_output=True, text=True,
                                  encoding='utf-8')
        finally:
            os.unlink(name)
        self.assertEqual(done.returncode, 0, done.stderr[-800:])
        return json.loads(done.stdout)

    def _assert_says_it_cannot_crit(self, card):
        self.assertFalse(card['critBlock'])
        self.assertFalse(card['titleHidden'])
        self.assertFalse(card['critHidden'])
        self.assertFalse(card['normalLabelHidden'])
        self.assertIn('no-crit', card['title'])
        self.assertIn('No critical hit', card['title'])
        self.assertIn(_NO_CRIT_NOTE, card['crit'])
        self.assertEqual(0, card['critDamageRows'])

    def _assert_has_its_critical_block(self, card):
        self.assertTrue(card['critBlock'])
        self.assertFalse(card['titleHidden'])
        self.assertFalse(card['critHidden'])
        self.assertNotIn('no-crit', card['title'])
        self.assertIn('Critical hit', card['title'])
        self.assertNotIn(_NO_CRIT_NOTE, card['crit'])

    def test_the_shares_of_hp_and_a_plain_spell_that_cannot_crit_keep_the_sentences(self):
        drawn = self._drawn('dofus3', 'Sacrier')
        for moment in ('built', 'refreshed', 'again'):
            for name in ('Transfusion', 'Punishment', 'Mutilation'):
                with self.subTest(moment=moment, spell=name):
                    self._assert_says_it_cannot_crit(drawn[moment][name])
            with self.subTest(moment=moment, spell='Retribution'):
                self._assert_has_its_critical_block(drawn[moment]['Retribution'])
        for moment in ('refreshed', 'again'):
            with self.subTest(moment=moment, spell='Retribution'):
                self.assertGreater(drawn[moment]['Retribution']['critDamageRows'], 0)

    def test_every_card_of_the_page_says_which_block_it_has_after_a_redraw(self):
        cards = self._drawn('dofus3', 'Sacrier')['again']
        sans = [name for name, card in cards.items() if not card['critBlock']]
        avec = [name for name, card in cards.items() if card['critBlock']]
        self.assertTrue(sans)
        self.assertTrue(avec)
        for name in sans:
            with self.subTest(spell=name):
                self._assert_says_it_cannot_crit(cards[name])
        for name in avec:
            with self.subTest(spell=name):
                self._assert_has_its_critical_block(cards[name])
