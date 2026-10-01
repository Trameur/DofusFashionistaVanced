# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The spells page's script draws each share of HP on its card, numbered from the build's HP."""
import json
import os
import pickle
import re
import shutil
import subprocess
import tempfile

from django.test import TestCase

from fashionistapulp.dofus_constants import NEUTRAL

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
recalculateDamages();
function walk(node, out) {
  if (node._damage) out.push(['damage'].concat(node._damage));
  if (node._sub !== null) out.push(['line', node._sub]);
  else if (node._html.indexOf('>or<') !== -1) out.push(['or']);
  node._kids.forEach(function (kid) { walk(kid, out); });
  return out;
}
var drawn = {hp: charStats.hp};
spellDigests.forEach(function (spell) {
  if (PICKED.indexOf(spell.canonical) === -1) return;
  var cell = cells[spell.name];
  drawn[spell.canonical] = {
    critBlock: hasCritBlock(spell), critHidden: cell.crit._hidden, deals: spellDealsDamage(spell),
    normal: walk(cell.nonCrit, []), critical: walk(cell.crit, [])};
});
console.log(JSON.stringify(drawn));
"""


def _prefix(version):
    return '' if version == 'dofus3' else version + '/'


class TheCardDrawsTheShareTests(TestCase):

    def _build(self, char_class, version):
        from django.contrib.auth.models import User
        from chardata.models import Char
        from fashionistapulp.modelresult import ModelResultMinimal
        owner = User.objects.create_user('hpshare', 'hp@test.local', 'pw-42-solid')
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
            name='HpShare', char_name='hpshare', char_class=char_class,
            char_build='build', level=LEVEL,
            minimum_stats=b'', minimum_crits=b'', stats_weight=b'',
            options=b'', inclusions=b'', exclusions=b'',
            minimal_solution=pickle.dumps(ModelResultMinimal({}, base_input, stats)),
            owner=owner, link_shared=True, game_version=version)

    def _drawn(self, version, char_class, picked):
        """The cards of the picked spells as the page's script fills them."""
        node = shutil.which('node')
        if node is None:
            self.skipTest('node is not installed')
        from fashionistapulp.structure import set_current_game_version
        set_current_game_version(version)
        self.addCleanup(set_current_game_version, 'dofus3')
        char = self._build(char_class, version)
        page = self.client.get('/%sspells/%d/' % (_prefix(version), char.pk),
                               HTTP_ACCEPT_LANGUAGE='en')
        self.assertEqual(200, page.status_code)
        scripts = [body for body in re.findall(r'<script[^>]*>(.*?)</script>',
                                               page.content.decode('utf-8'), re.S)
                   if 'var spellDigests' in body]
        self.assertEqual(1, len(scripts))
        driver = _DRIVER.replace('PICKED', json.dumps(picked))
        with tempfile.NamedTemporaryFile('w', suffix='.js', encoding='utf-8',
                                         delete=False) as handle:
            handle.write('var source = %s;\n%s' % (json.dumps(scripts[0]), driver))
            name = handle.name
        try:
            done = subprocess.run([node, name], capture_output=True, text=True,
                                  encoding='utf-8')
        finally:
            os.unlink(name)
        self.assertEqual(done.returncode, 0, done.stderr[-800:])
        drawn = json.loads(done.stdout)
        self.assertEqual(set(picked), set(drawn) - {'hp'})
        return drawn

    def test_transfusion_and_punishment_draw_their_line_then_the_share_of_the_builds_hp(self):
        drawn = self._drawn('dofus3', 'Sacrier', ['Transfusion', 'Punishment'])
        hp = drawn['hp']
        self.assertGreater(hp, 0)
        for name, percent in (('Transfusion', 10), ('Punishment', 15)):
            with self.subTest(spell=name):
                card = drawn[name]
                self.assertEqual(
                    [['line', "Neutral damage: %d%% of the caster's HP" % percent],
                     ['damage', NEUTRAL, hp * percent // 100, hp * percent // 100]],
                    card['normal'])
                self.assertTrue(card['deals'])
                self.assertFalse(card['critBlock'])
                self.assertFalse(card['critHidden'])

    def test_masquerade_joins_its_faces_by_or_and_numbers_the_full_hp_one(self):
        drawn = self._drawn('dofus3', 'Masqueraider', ['Masquerade'])
        hp = drawn['hp']
        self.assertEqual(
            [['line', "Neutral damage: 25% of the caster's HP"],
             ['damage', NEUTRAL, hp * 25 // 100, hp * 25 // 100],
             ['or'],
             ['line', "Neutral damage: 25% of the caster's missing HP"]],
            drawn['Masquerade']['normal'])

    def test_retribution_draws_its_eroded_line_without_a_number_after_its_hits(self):
        drawn = self._drawn('dofus2', 'Sacrier', ['Retribution'])
        card = drawn['Retribution']
        for block, percent in (('normal', 35), ('critical', 35)):
            with self.subTest(block=block):
                self.assertTrue([row for row in card[block] if row[0] == 'damage'])
                self.assertEqual(
                    ['line', "%d%% of the caster's eroded HP inflicted as Neutral damage"
                     % percent], card[block][-1])
        self.assertTrue(card['critBlock'])
        self.assertFalse(card['critHidden'])

    def test_reprisal_opens_a_critical_block_for_its_critical_share_alone(self):
        drawn = self._drawn('dofus3', 'Cra', ['Reprisal'])
        card = drawn['Reprisal']
        self.assertTrue(card['deals'])
        self.assertTrue(card['critBlock'])
        self.assertFalse(card['critHidden'])
        self.assertEqual([['line', "Neutral damage: 20% of the target's eroded HP"]],
                         card['normal'])
        self.assertEqual([['line', "Neutral damage: 25% of the target's eroded HP"]],
                         card['critical'])
