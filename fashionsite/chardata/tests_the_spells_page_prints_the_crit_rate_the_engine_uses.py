# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The spells page prints the critical rate that crit_chance gives the best turn."""
import json
import os
import pickle
import re
import shutil
import subprocess
import tempfile

from django.contrib.auth.models import User
from django.test import TestCase

from chardata.models import Char
from chardata.spell_combo import crit_chance, retro_critical_x
from fashionistapulp.modelresult import ModelResultMinimal
from fashionistapulp.structure import get_structure, set_current_game_version

_DRIVER = r"""
var vm = require('vm');
global.$ = function () { return {ready: function () {}}; };
$.each = function (items, callback) {
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
global.document = {};
global.window = global;
vm.runInThisContext(source);
buffsForSpell = {};
spellLevel = {};
var spell = spellDigests.filter(function (d) { return d.type == 'spell'; })[0];
var labels = CASES.map(function (c) {
  charStats = {ch: c[1], agi: 0};
  return critRateLabel(c[0], spell);
});
charStats = {ch: 0, agi: 0};
console.log(JSON.stringify({
  labels: labels,
  weapon_lines: spellDigests.filter(function (d) { return d.type != 'spell'; })
                            .map(function (d) { return referenceLine(d); })
}));
"""

CASES = ((5, -90), (25, -25), (25, -24), (1, 0), (15, 0), (15, 20),
         (30, 70), (30, 400))


class _SpellsPage(TestCase):

    def _run(self, version, cases=(), weapon_id=None):
        node = shutil.which('node')
        if node is None:
            self.skipTest('node is not installed')
        set_current_game_version(version)
        self.addCleanup(set_current_game_version, 'dofus3')
        owner = User.objects.create_user(
            'critpage%d' % User.objects.count(), 'cp@test.local', 'pw-42-solid')
        base = {'Vitality': 0, 'Wisdom': 0, 'Strength': 0, 'Intelligence': 0,
                'Chance': 0, 'Agility': 0}
        minimal = ModelResultMinimal(
            {'weapon': weapon_id} if weapon_id else {},
            {'options': {'ap_exo': False, 'mp_exo': False},
             'origin': 'generated', 'char_level': 200,
             'base_stats_by_attr': base, 'locked_equips': {}},
            {'vit': 0, 'wis': 0, 'str': 0, 'int': 0, 'cha': 0, 'agi': 0})
        char = Char.objects.create(
            name='CritPage', char_name='critpage', char_class='Iop',
            char_build='build', level=200, minimum_stats=b'',
            minimum_crits=b'', stats_weight=b'', options=b'', inclusions=b'',
            exclusions=b'', minimal_solution=pickle.dumps(minimal),
            owner=owner, link_shared=False, game_version=version)
        self.client.force_login(owner)
        prefix = '' if version == 'dofus3' else '/' + version
        page = self.client.get('%s/spells/%d/' % (prefix, char.pk))
        self.assertEqual(200, page.status_code)
        scripts = [body for body in re.findall(
            r'<script\b[^>]*>(.*?)</script\b[^>]*>', page.content.decode('utf-8'), re.S | re.I)
            if 'function critRateLabel' in body]
        self.assertEqual(1, len(scripts))
        driver = _DRIVER.replace('CASES', json.dumps(cases))
        with tempfile.NamedTemporaryFile('w', suffix='.js', encoding='utf-8',
                                         delete=False) as handle:
            handle.write('var source = %s;\n%s' % (json.dumps(scripts[0]),
                                                   driver))
            name = handle.name
        try:
            done = subprocess.run([node, name], capture_output=True, text=True,
                                  encoding='utf-8')
        finally:
            os.unlink(name)
        self.assertEqual(0, done.returncode, done.stderr[-800:])
        return json.loads(done.stdout)


class ThePercentageLabelTests(_SpellsPage):

    def test_each_percentage_version_prints_the_engine_rate(self):
        for version in ('dofus3', 'beta', 'dofus2', 'touch'):
            with self.subTest(version=version):
                labels = self._run(version, CASES)['labels']
                expected = ['%d%%' % round(100 * crit_chance(
                    base, {'ch': crit_hits}, version))
                    for base, crit_hits in CASES]
                self.assertEqual(expected, labels)

    def test_dofus2_prints_zero_where_touch_prints_one(self):
        self.assertEqual(['0%'], self._run('dofus2', ((5, -90),))['labels'])
        self.assertEqual(['1%'], self._run('touch', ((5, -90),))['labels'])


class TheRetroWeaponLineTests(_SpellsPage):

    def _retro_weapons(self, keep):
        structure = get_structure('retro')
        found = []
        for key, weapon in structure.weapons_by_key.items():
            if not str(key).isdigit() or not keep(weapon):
                continue
            item = structure.get_item_by_id(int(key))
            if item is None or structure.get_weapon_by_name(item.name) is not weapon:
                continue
            found.append((item.id, weapon))
        return sorted(found, key=lambda pair: pair[0])

    def test_a_weapon_stored_at_minus_one_prints_no_crit_rate(self):
        set_current_game_version('retro')
        self.addCleanup(set_current_game_version, 'dofus3')
        stored = self._retro_weapons(lambda weapon: (weapon.crit_chance or 0) < 0)
        self.assertEqual(4, len(stored))
        for item_id, weapon in stored:
            with self.subTest(item=item_id):
                self.assertEqual(0.0, crit_chance(weapon.crit_chance,
                                                  {'ch': 0, 'agi': 0}, 'retro'))
                lines = self._run('retro', weapon_id=item_id)['weapon_lines']
                self.assertEqual(1, len(lines))
                self.assertNotIn('1/', lines[0])

    def test_a_weapon_with_a_rate_prints_it(self):
        set_current_game_version('retro')
        self.addCleanup(set_current_game_version, 'dofus3')
        item_id, weapon = self._retro_weapons(
            lambda weapon: (weapon.crit_chance or 0) > 0 and weapon.ap)[0]
        lines = self._run('retro', weapon_id=item_id)['weapon_lines']
        self.assertEqual(1, len(lines))
        self.assertIn('1/%d' % retro_critical_x(weapon.crit_chance, 0, 0),
                      lines[0])
