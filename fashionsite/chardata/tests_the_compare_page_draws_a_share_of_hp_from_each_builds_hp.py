# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The set compare lists the spells that deal a share of HP and numbers each share from each build's own HP."""
import json
import math
import os
import pickle
import re
import shutil
import subprocess
import tempfile
from types import SimpleNamespace
from unittest import mock

from django.test import TestCase
from django.utils import translation

from chardata.spell_buffs import get_damage_spells_for_version
from chardata.spell_combo import HP_SHARE_ELEMENTS, HpShare, hp_share_hits_for_version
from chardata.spell_modifiers import SpellModifier, item_spell_modifiers
from fashionistapulp.dofus_constants import STAT_KEY_TO_NAME

LEVEL = 200
TRANSFUSION = 12738
PUNISHMENT = 12760
RETRIBUTION = 12741
MASQUERADE = 13404
REPRISAL = 32472
SPELL_TIP_JS = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            'static', 'chardata', 'spell_tip.js')

_DRIVER = r"""
var vm = require('vm');
var fs = require('fs');
var cellsByName = {};
var rowKeys = [];
var linked = 0;
function node(markup) {
  var self = {markup: String(markup), kids: [], said: null, panel: null, beforeBreak: false};
  self.append = function () {
    for (var i = 0; i < arguments.length; i++) {
      var kid = arguments[i];
      self.kids.push(typeof kid === 'string' ? node(kid) : kid);
    }
    return self;
  };
  self.appendTo = function (parent) { parent.append(self); return self; };
  self.html = function (value) { self.markup = String(value); self.kids = []; return self; };
  self.text = function (value) { self.said = String(value); return self; };
  self.find = function (selector) {
    if (selector === '.spell-tip-panel') {
      if (!self.panel) self.panel = node('');
      return self.panel;
    }
    return {remove: function () { return this; }};
  };
  self.children = function (selector) {
    var found = selector === 'br' && self.markup.indexOf('<br>') !== -1;
    return {first: function () {
      return {length: found ? 1 : 0,
              before: function (other) { other.beforeBreak = true; self.kids.push(other); }};
    }};
  };
  self.addClass = function () { return self; };
  self.removeClass = function () { return self; };
  return self;
}
global.window = global;
global.document = {readyState: 'complete', addEventListener: function () {},
                   querySelectorAll: function () { return []; }};
global.addEventListener = function () {};
vm.runInThisContext(fs.readFileSync(SPELL_TIP, 'utf8'));
window.linkSpellTipPanels = function () { linked += 1; };
global.$ = function (selector) {
  if (typeof selector === 'string') {
    var cell = /^td\[name=(.+)\]$/.exec(selector);
    if (cell) {
      if (!cellsByName[cell[1]]) cellsByName[cell[1]] = node('-');
      return cellsByName[cell[1]];
    }
    if (selector === '.compare-spell-row') {
      return {each: function (callback) {
        rowKeys.forEach(function (key) { callback.call({spellKey: key}); });
      }};
    }
    if (selector.charAt(0) === '<') return node(selector);
  }
  if (selector && selector.spellKey) {
    return {data: function () { return selector.spellKey; }};
  }
  return {ready: function () {}, is: function () { return false; },
          val: function () { return MODE; }};
};
$.each = function (items, callback) {
  if (!items) return items;
  var keys = Array.isArray(items) ? items.map(function (_v, i) { return i; })
                                  : Object.keys(items);
  for (var i = 0; i < keys.length; i++) {
    if (callback.call(items[keys[i]], keys[i], items[keys[i]]) === false) break;
  }
  return items;
};
$.extend = function (target) {
  for (var i = 1; i < arguments.length; i++) Object.assign(target, arguments[i]);
  return target;
};
$.ajaxSetup = function () {};
vm.runInThisContext(source);
rowKeys = compareSpellDigests.map(function (spell) { return spell.compare_key; });
updateSpellPreview();
function read(cell) {
  var tip = null;
  cell.kids.forEach(function (kid) {
    if (kid.panel) {
      tip = {markup: kid.markup, beforeBreak: kid.beforeBreak,
             lines: kid.panel.kids.map(function (row) {
               return row.kids.length ? ['strong', row.kids[0].said] : ['text', row.said];
             })};
    }
  });
  return {summary: cell.markup, tip: tip};
}
var out = {ids: allCharIds, hp: {}, gear_hp: {}, spells: {}, linked: linked, probe: PROBE};
allCharIds.forEach(function (id) {
  out.hp[id] = allStatTotals[id].hp;
  out.gear_hp[id] = allStatGears[id].hp;
});
compareSpellDigests.forEach(function (spell) {
  var diff = cellsByName['spell_damage_' + spell.compare_key + '_diff'];
  var drawn = {diff: diff ? diff.markup : null, builds: {}};
  allCharIds.forEach(function (id) {
    drawn.builds[id] = read(cellsByName['spell_damage_' + spell.compare_key + '_' + id]);
  });
  out.spells[spell.canonical] = drawn;
});
console.log(JSON.stringify(out));
"""


def _js_round(value):
    return math.floor(value + 0.5)


def _prefix(version):
    return '' if version == 'dofus3' else '/' + version


def _spell(version, char_class, spell_id):
    return next(spell for spell in get_damage_spells_for_version(version)[char_class]
                if spell.spell_id == spell_id)


def _entry(version, char_class, spell_id):
    return hp_share_hits_for_version(version)[char_class][spell_id]


def _rank(version, char_class, spell_id, level=LEVEL):
    spell = _spell(version, char_class, spell_id)
    return max(index for index, need in enumerate(spell.level_req) if need <= level)


def _text(row, rank, language='en'):
    return row['text'][rank][language]


def _share(row, rank, hp):
    share = HpShare(HP_SHARE_ELEMENTS[row['element']], row['percent'][rank])
    return hp * share.min_dam // 100, hp * share.max_dam // 100


def _shown(low, high):
    return str(low) if low == high else '%d - %d' % (low, high)


def _said(message, language='en'):
    from django.utils.translation import gettext
    with translation.override(language):
        return gettext(message)


class TheComparePageNumbersTheShareTests(TestCase):

    def setUp(self):
        from django.contrib.auth.models import User
        self.owner = User.objects.create_user('hpcompare', 'hpc@test.local', 'pw-42-solid')
        self.client.force_login(self.owner)

    def _use(self, version):
        from fashionistapulp.structure import set_current_game_version
        set_current_game_version(version)
        self.addCleanup(set_current_game_version, 'dofus3')

    def _build(self, name, char_class, version='dofus3', level=LEVEL, vitality=0,
               item_ids=()):
        from chardata.models import Char, CharBaseStats
        from fashionistapulp.modelresult import ModelResultMinimal
        self._use(version)
        base_input = {
            'options': {'ap_exo': False, 'mp_exo': False},
            'origin': 'generated', 'char_level': level,
            'base_stats_by_attr': {'Vitality': 0, 'Wisdom': 0, 'Strength': 0,
                                   'Intelligence': 0, 'Chance': 0, 'Agility': 0},
            'locked_equips': {},
        }
        stats = {'vit': 0, 'wis': 0, 'str': 0, 'int': 0, 'cha': 0, 'agi': 0}
        if item_ids:
            minimal = ModelResultMinimal.from_item_id_list(list(item_ids), base_input, stats)
        else:
            minimal = ModelResultMinimal({}, base_input, stats)
        char = Char.objects.create(
            name=name, char_name=name.lower(), char_class=char_class,
            char_build='build', level=level,
            minimum_stats=b'', minimum_crits=b'', stats_weight=b'',
            options=b'', inclusions=b'', exclusions=b'',
            minimal_solution=pickle.dumps(minimal),
            owner=self.owner, link_shared=True, game_version=version)
        if vitality:
            CharBaseStats.objects.create(char=char, stat=STAT_KEY_TO_NAME['vit'],
                                         total_value=vitality, scrolled_value=0)
        return char

    def _compare(self, char_class, first, second, version='dofus3', mode='final',
                 language='en', probe='null'):
        node = shutil.which('node')
        if node is None:
            self.skipTest('node is not installed')
        self._use(version)
        with translation.override(language):
            page = self.client.get(
                '%s/compare_sets/%d/%d/' % (_prefix(version), first.pk, second.pk),
                {'spell_class': char_class}, HTTP_ACCEPT_LANGUAGE=language)
        self.assertEqual(200, page.status_code)
        scripts = [body for body in re.findall(r'<script\b[^>]*>(.*?)</script\b[^>]*>',
                                               page.content.decode('utf-8'), re.S | re.I)
                   if 'var compareSpellDigests' in body]
        self.assertEqual(1, len(scripts))
        driver = (_DRIVER.replace('SPELL_TIP', json.dumps(SPELL_TIP_JS))
                  .replace('MODE', json.dumps(mode)).replace('PROBE', probe))
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
        result = json.loads(done.stdout)
        self.assertEqual([str(first.pk), str(second.pk)], result['ids'])
        options = [option['value'] for option in page.context['spell_preview_spell_options']]
        return result, options

    def _cell(self, result, name, build):
        return result['spells'][name]['builds'][str(build.pk)]

    def _assert_numbered(self, result, name, build, row, rank, language='en'):
        hp = result['hp'][str(build.pk)]
        low, high = _share(row, rank, hp)
        cell = self._cell(result, name, build)
        self.assertEqual([['text', _text(row, rank, language)], ['strong', _shown(low, high)]],
                         cell['tip']['lines'])
        self.assertEqual(str(_js_round((low + high) / 2.0)), cell['summary'])
        return int(cell['summary'])

    def test_transfusion_is_listed_and_numbered_from_each_builds_hp(self):
        frail = self._build('Frail', 'Sacrier')
        sturdy = self._build('Sturdy', 'Sacrier', vitality=1000)
        result, options = self._compare('Sacrier', frail, sturdy)
        for name in ('Transfusion', 'Punishment', 'Retribution'):
            with self.subTest(spell=name):
                self.assertIn(name, options)
                self.assertIn(name, result['spells'])
        self.assertGreater(result['hp'][str(sturdy.pk)], result['hp'][str(frail.pk)])
        row = _entry('dofus3', 'Sacrier', TRANSFUSION)['normal'][0]
        rank = _rank('dofus3', 'Sacrier', TRANSFUSION)
        shown = [self._assert_numbered(result, 'Transfusion', build, row, rank)
                 for build in (frail, sturdy)]
        self.assertIn('>Transfusion<', self._cell(result, 'Transfusion', frail)['tip']['markup'])
        self.assertGreater(shown[1], shown[0])
        self.assertIn('>%d<' % (shown[1] - shown[0]), result['spells']['Transfusion']['diff'])
        self.assertGreater(result['linked'], 0)

    def test_retribution_names_its_eroded_share_once_beside_its_number(self):
        entry = _entry('dofus3', 'Sacrier', RETRIBUTION)
        rank = _rank('dofus3', 'Sacrier', RETRIBUTION)
        self.assertEqual([(_text(row, rank), row['percent'][rank]) for row in entry['normal']],
                         [(_text(row, rank), row['percent'][rank]) for row in entry['critical']])
        frail = self._build('Frail', 'Sacrier')
        sturdy = self._build('Sturdy', 'Sacrier', vitality=1000)
        result, _options = self._compare('Sacrier', frail, sturdy)
        for build in (frail, sturdy):
            with self.subTest(build=build.name):
                cell = self._cell(result, 'Retribution', build)
                self.assertEqual([['text', _text(entry['normal'][0], rank)]],
                                 cell['tip']['lines'])
                self.assertIn('<br>', cell['summary'])
                self.assertTrue(cell['tip']['beforeBreak'])

    def test_equip_mode_numbers_the_share_from_the_builds_total_hp(self):
        from fashionistapulp.structure import get_structure
        self._use('dofus3')
        structure = get_structure('dofus3')
        vit = structure.get_stat_by_key('vit').id
        flat_hp = structure.get_stat_by_key('hp').id
        piece = next(item for item in structure.types[LEVEL]['Amulet']
                     if not item.removed and item.ankama_id
                     and dict(item.stats).get(vit, 0) > 0 and flat_hp not in dict(item.stats)
                     and not item_spell_modifiers('dofus3', item.ankama_id))
        bare = self._build('Bare', 'Sacrier')
        worn = self._build('Worn', 'Sacrier', item_ids=[piece.id])
        result, _options = self._compare('Sacrier', bare, worn, mode='equip')
        row = _entry('dofus3', 'Sacrier', TRANSFUSION)['normal'][0]
        rank = _rank('dofus3', 'Sacrier', TRANSFUSION)
        shown = []
        for build in (bare, worn):
            with self.subTest(build=build.name):
                self.assertEqual(0, result['gear_hp'][str(build.pk)])
                self.assertGreater(result['hp'][str(build.pk)], 0)
                shown.append(self._assert_numbered(result, 'Transfusion', build, row, rank))
        self.assertGreater(shown[1], shown[0])
        self.assertIn('>%d<' % (shown[1] - shown[0]), result['spells']['Transfusion']['diff'])

    def test_masquerade_joins_its_two_faces_by_or_and_numbers_the_full_hp_one(self):
        entry = _entry('dofus3', 'Masqueraider', MASQUERADE)
        full, missing = entry['normal']
        self.assertEqual(('caster_hp', 'caster_missing_hp'), (full['of'], missing['of']))
        frail = self._build('Frail', 'Masqueraider')
        sturdy = self._build('Sturdy', 'Masqueraider', vitality=1000)
        result, options = self._compare('Masqueraider', frail, sturdy)
        self.assertIn('Masquerade', options)
        rank = _rank('dofus3', 'Masqueraider', MASQUERADE)
        shown = []
        for build in (frail, sturdy):
            with self.subTest(build=build.name):
                low, high = _share(full, rank, result['hp'][str(build.pk)])
                cell = self._cell(result, 'Masquerade', build)
                self.assertEqual(
                    [['text', _text(full, rank)], ['strong', _shown(low, high)],
                     ['text', _said('or')], ['text', _text(missing, rank)]],
                    cell['tip']['lines'])
                self.assertEqual(str(_js_round((low + high) / 2.0)), cell['summary'])
                shown.append(int(cell['summary']))
        self.assertGreater(shown[1], shown[0])

    def test_masquerade_speaks_french_on_the_french_page(self):
        entry = _entry('dofus3', 'Masqueraider', MASQUERADE)
        full, missing = entry['normal']
        rank = _rank('dofus3', 'Masqueraider', MASQUERADE)
        self.assertNotEqual(_text(full, rank), _text(full, rank, 'fr'))
        self.assertNotEqual('or', _said('or', 'fr'))
        first = self._build('Premier', 'Masqueraider')
        second = self._build('Second', 'Masqueraider', vitality=1000)
        result, _options = self._compare('Masqueraider', first, second, language='fr')
        name = _spell('dofus3', 'Masqueraider', MASQUERADE).name
        for build in (first, second):
            with self.subTest(build=build.name):
                low, high = _share(full, rank, result['hp'][str(build.pk)])
                self.assertEqual(
                    [['text', _text(full, rank, 'fr')], ['strong', _shown(low, high)],
                     ['text', _said('or', 'fr')], ['text', _text(missing, rank, 'fr')]],
                    self._cell(result, name, build)['tip']['lines'])

    def test_reprisal_is_listed_with_its_normal_and_critical_shares(self):
        entry = _entry('dofus3', 'Cra', REPRISAL)
        rank = _rank('dofus3', 'Cra', REPRISAL)
        normal, critical = entry['normal'][0], entry['critical'][0]
        self.assertNotEqual(_text(normal, rank), _text(critical, rank))
        frail = self._build('Frail', 'Cra')
        sturdy = self._build('Sturdy', 'Cra', vitality=1000)
        result, options = self._compare('Cra', frail, sturdy)
        self.assertIn('Reprisal', options)
        self.assertEqual('-', result['spells']['Reprisal']['diff'])
        for build in (frail, sturdy):
            with self.subTest(build=build.name):
                cell = self._cell(result, 'Reprisal', build)
                self.assertEqual('-', cell['summary'])
                self.assertEqual(
                    [['text', _text(normal, rank)], ['strong', _said('Critical hit')],
                     ['text', _text(critical, rank)]],
                    cell['tip']['lines'])

    def test_each_build_reads_the_rank_its_level_reaches(self):
        levels = _spell('dofus3', 'Sacrier', TRANSFUSION).level_req
        self.assertGreater(len(levels), 2)
        below = self._build('Below', 'Sacrier', level=levels[0] - 1, vitality=300)
        middle = self._build('Middle', 'Sacrier', level=levels[1], vitality=300)
        result, _options = self._compare('Sacrier', below, middle)
        self.assertEqual({'summary': '-', 'tip': None}, self._cell(result, 'Transfusion', below))
        self.assertEqual('-', result['spells']['Transfusion']['diff'])
        rank = _rank('dofus3', 'Sacrier', TRANSFUSION, levels[1])
        self.assertEqual(1, rank)
        row = _entry('dofus3', 'Sacrier', TRANSFUSION)['normal'][0]
        self.assertNotEqual(row['percent'][rank], row['percent'][-1])
        self._assert_numbered(result, 'Transfusion', middle, row, rank)

    def test_beta_and_dofus2_number_their_own_shares(self):
        for version in ('beta', 'dofus2'):
            with self.subTest(version=version):
                frail = self._build('Frail' + version, 'Sacrier', version=version)
                sturdy = self._build('Sturdy' + version, 'Sacrier', version=version,
                                     vitality=1000)
                result, options = self._compare('Sacrier', frail, sturdy, version=version)
                for spell_id in (TRANSFUSION, PUNISHMENT):
                    name = _spell(version, 'Sacrier', spell_id).name
                    self.assertIn(name, options)
                    row = _entry(version, 'Sacrier', spell_id)['normal'][0]
                    rank = _rank(version, 'Sacrier', spell_id)
                    shown = [self._assert_numbered(result, name, build, row, rank)
                             for build in (frail, sturdy)]
                    self.assertGreater(shown[1], shown[0])

    def test_a_counted_share_lands_when_no_scored_face_does_at_that_rank(self):
        frail = self._build('Frail', 'Sacrier')
        sturdy = self._build('Sturdy', 'Sacrier', vitality=1000)
        probe = ("[summarizeCompareHits({scored: {}}, [{element: 'neut', min_dam: 10, max_dam: 20}],"
                 " false, {}, [], 50),"
                 " summarizeCompareHits({scored: {}}, [{element: 'neut', min_dam: 10, max_dam: 20}],"
                 " false, {}, [], null)]")
        result, _options = self._compare('Sacrier', frail, sturdy, probe=probe)
        self.assertEqual([{'avg': 50}, None], result['probe'])


class TheWornDigestKeepsTheShareTests(TestCase):

    def test_a_worn_piece_on_transfusion_keeps_its_share_of_hp(self):
        from chardata.compare_sets_view import _worn_spell_digests
        from chardata.spells_view import _create_spell_web_digest
        from fashionistapulp.structure import set_current_game_version
        set_current_game_version('dofus3')
        self.addCleanup(set_current_game_version, 'dofus3')
        spell = _spell('dofus3', 'Sacrier', TRANSFUSION)
        entry = _entry('dofus3', 'Sacrier', TRANSFUSION)
        build = SimpleNamespace(pk=7)
        worn = {TRANSFUSION: [SpellModifier('ap_cost', -1, 'Test piece')]}
        with translation.override('en'), \
                mock.patch('chardata.compare_sets_view.worn_spell_modifiers',
                           return_value=worn):
            digests = _worn_spell_digests(
                [build], {7: None},
                [{'spell': spell, 'row': {'key': 'spell_0'}, 'hp_share': entry}], 'dofus3')
            plain = _create_spell_web_digest(spell, 'dofus3', hp_share=entry)
        digest = digests['7']['spell_0']
        self.assertTrue(digest['item_notes'])
        self.assertIsNotNone(digest['hp_share'])
        self.assertEqual(plain['hp_share'], digest['hp_share'])
