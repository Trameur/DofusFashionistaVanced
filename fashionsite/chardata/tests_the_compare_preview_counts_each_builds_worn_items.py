# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The set compare's spell preview reads the spell modifiers each build wears."""
import json
import os
import re
import shutil
import subprocess
import tempfile

from django.test import TestCase
from django.utils import translation

from chardata.spell_modifiers import item_spell_modifiers

HONOH_RING = 'Honoh Ring'
ROBBIE_HOODIE_CAP = 'Robbie Hoodie Cap'
BOOT_A_HOOP = 'Boot-a-Hoop'

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
vm.runInThisContext(source);
var stats = STATS;
var out = {};
allCharIds.forEach(function (charId) {
  var spells = {};
  compareSpellDigests.forEach(function (shared) {
    var spell = getCompareSpellForRow(shared.compare_key, charId);
    var level = getCompareSpellLevel(spell, compareCharLevels[charId]);
    spells[spell.canonical] = {
      own: spell !== shared,
      notes: spell.item_notes,
      item_stats: spell.item_stats,
      rows: (spell.non_crit_dams[level] || []).map(function (hit) {
        return [hit.min_dam, hit.max_dam];
      }),
      summary: summarizeCompareSpell(spell, stats, compareCharLevels[charId])
    };
  });
  out[charId] = spells;
});
console.log(JSON.stringify({ids: allCharIds, spells: out,
                            worn: Object.keys(compareSpellDigestsByChar)}));
"""


def _prefix(version):
    return '' if version == 'dofus3' else version + '/'


class TheComparePreviewCountsEachBuildsWornItemsTests(TestCase):

    def setUp(self):
        from django.contrib.auth.models import User
        self.owner = User.objects.create_user('wornowner', 'w@x.test', 'pw')
        self.client.force_login(self.owner)

    def _common(self, version, skip):
        from fashionistapulp.structure import (get_structure,
                                               set_current_game_version)
        set_current_game_version(version)
        try:
            structure = get_structure(version)
            names = []
            for type_name in ('Hat', 'Cloak', 'Belt', 'Boots', 'Amulet'):
                if type_name in skip:
                    continue
                item = next(i for i in structure.types[200][type_name]
                            if not i.removed and i.ankama_id
                            and not item_spell_modifiers(version, i.ankama_id))
                names.append(structure.get_item_name_in_language(item, 'en'))
        finally:
            set_current_game_version('dofus3')
        return names

    def _build(self, version, char_class, worn, skip=()):
        from chardata.models import Char
        names = self._common(version, skip) + list(worn)
        self.client.post('/%simport/text/' % _prefix(version), {
            'text': '\n'.join(names), 'confirm': '1',
            'char_class': char_class, 'level': '200'})
        char = Char.objects.order_by('-id').first()
        self.assertEqual((version, char_class),
                         (char.game_version or 'dofus3', char.char_class))
        return char

    def _run(self, version, char_class, first, second, spell_name='',
             stats=None):
        node = shutil.which('node')
        if node is None:
            self.skipTest('node is not installed')
        with translation.override('en'):
            page = self.client.get(
                '/%scompare_sets/%d/%d/' % (_prefix(version), first.pk,
                                            second.pk),
                {'spell_class': char_class, 'spell_name': spell_name},
                HTTP_ACCEPT_LANGUAGE='en')
        self.assertEqual(200, page.status_code)
        scripts = [body for body in re.findall(r'<script[^>]*>(.*?)</script>',
                                               page.content.decode('utf-8'),
                                               re.S)
                   if 'var compareSpellDigests' in body]
        self.assertEqual(1, len(scripts))
        driver = _DRIVER.replace('STATS', json.dumps(stats or {}))
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
        self.assertEqual(done.returncode, 0, done.stderr[-800:])
        result = json.loads(done.stdout)
        self.assertEqual([str(first.pk), str(second.pk)], result['ids'])
        return (result['spells'][str(first.pk)],
                result['spells'][str(second.pk)], result['worn'])

    def test_the_honoh_ring_names_its_changes_on_the_ring_build_only(self):
        ring = self._build('dofus3', 'Cra', [HONOH_RING])
        bare = self._build('dofus3', 'Cra', [])
        worn, plain, carriers = self._run('dofus3', 'Cra', ring, bare)
        self.assertEqual([str(ring.pk)], carriers)
        self.assertEqual(['Honoh Ring: -1 AP'],
                         worn['Arrow of Judgement']['notes'])
        self.assertEqual([], plain['Arrow of Judgement']['notes'])
        self.assertEqual({'ch': 30}, worn['Explosive Arrow']['item_stats'])
        self.assertEqual({}, plain['Explosive Arrow']['item_stats'])
        self.assertEqual(plain['Explosive Arrow']['summary'],
                         worn['Explosive Arrow']['summary'])
        self.assertFalse(any(spell['own'] for spell in plain.values()))

    def test_a_base_damage_item_raises_its_arrow_on_its_build_only(self):
        capped = self._build('dofus3', 'Cra', [HONOH_RING, ROBBIE_HOODIE_CAP],
                             skip=('Hat',))
        bare = self._build('dofus3', 'Cra', [])
        stats = {'str': 100, 'int': 100, 'cha': 100, 'agi': 100}
        worn, plain, _carriers = self._run('dofus3', 'Cra', capped, bare,
                                           'Slow-Down Arrow', stats)
        self.assertEqual(['Slow-Down Arrow'], list(worn))
        worn, plain = worn['Slow-Down Arrow'], plain['Slow-Down Arrow']
        self.assertEqual(1, len(plain['rows']))
        self.assertEqual([[low + 6, high + 6] for low, high in plain['rows']],
                         worn['rows'])
        self.assertEqual(plain['summary']['normalAvg'] + 12,
                         worn['summary']['normalAvg'])
        self.assertEqual(['Robbie Hoodie Cap: +6 base damage'], worn['notes'])

    def test_retro_spell_damage_adds_to_its_spell_on_its_build_only(self):
        booted = self._build('retro', 'Iop', [BOOT_A_HOOP], skip=('Boots',))
        bare = self._build('retro', 'Iop', [])
        worn, plain, carriers = self._run('retro', 'Iop', booted, bare)
        sword = 'Epée de Iop'
        self.assertEqual([str(booted.pk)], carriers)
        self.assertEqual({'dam': 30}, worn[sword]['item_stats'])
        self.assertEqual(['Boot-a-Hoop: +30 damage'], worn[sword]['notes'])
        self.assertEqual(plain[sword]['rows'], worn[sword]['rows'])
        self.assertEqual(1, len(plain[sword]['rows']))
        for key in ('normalAvg', 'criticalAvg'):
            with self.subTest(key=key):
                self.assertEqual(plain[sword]['summary'][key] + 30,
                                 worn[sword]['summary'][key])
        changed = {name for name in worn
                   if worn[name]['summary'] != plain[name]['summary']}
        self.assertEqual({sword}, changed)
