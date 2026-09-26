# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A placed hit whose rows split on the target lands one face; the set compare sums one face of each cast."""
import json
import math
import os
import pickle
import re
import shutil
import subprocess
import tempfile
from unittest import mock

from django.test import SimpleTestCase, TestCase
from django.utils import translation

from chardata.spell_buffs import get_damage_spells_for_version

LETHAL_TRAP = 12921
LETHAL_ATTACK = 12917
PASTURELAND = 13013
VENDETTA = 32473
BLUFF = 109
LANGUAGES = ('en', 'fr', 'es', 'pt', 'de')
THRESHOLDS = {'dofus3': '50', 'beta': '50', 'dofus2': '25'}

_REFERENCE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              'spell_reference')

_HP_LABEL = re.compile(r'^Target with (?:less than )?(\d+)% of its HP(?: or more)?$')

_SHOWN = {
    'en': ('Trap damage - Target with {}% of its HP or more',
           'Trap damage - Target with less than {}% of its HP'),
    'fr': ('Dégâts du piège - Cible à {}% de sa vie ou plus',
           'Dégâts du piège - Cible à moins de {}% de sa vie'),
    'es': ('Daños de la trampa - Objetivo con el {}% de su vida o más',
           'Daños de la trampa - Objetivo con menos del {}% de su vida'),
    'pt': ('Danos da armadilha - Alvo com {}% da vida ou mais',
           'Danos da armadilha - Alvo com menos de {}% da vida'),
    'de': ('Fallenschaden - Ziel mit {} % seiner Lebenspunkte oder mehr',
           'Fallenschaden - Ziel mit weniger als {} % seiner Lebenspunkte'),
}


def _generator():
    from chardata.tests import itemscraper_module
    return itemscraper_module('generate_damage_spells')


def _placed(kind, rows):
    spell = {'ankama_id': 1, 'name_en': 'Probe', 'level_requirements': [1],
             'damage_templates': {'normal': [], 'placed': [
                 {'kind': kind, 'waits': kind, 'normal': rows}]}}
    return _generator().convert_spell(spell)


def _row(situation, ranges, element='EARTH', **extra):
    return dict({'element': element, 'ranges': [ranges],
                 'situation': situation}, **extra)


def _spell(spell_id, version, char_class='Sram'):
    return next(spell for spell in get_damage_spells_for_version(version)[char_class]
                if spell.spell_id == spell_id)


def _ranges(rows):
    return [(row.min_dam, row.max_dam) for row in rows]


def _prefix(version):
    return '' if version == 'dofus3' else version + '/'


def _faces(label_pair, threshold):
    return [[label_pair[0].format(threshold), [0]],
            [label_pair[1].format(threshold), [1]]]


class TheGeneratorSplitsAPlacedBlockOnItsTargetTests(SimpleTestCase):

    def test_a_trap_on_an_hp_threshold_is_two_faces_with_the_plain_one_first(self):
        entry = _placed('trap', [_row('a,A,v50|80,1,0', '31-35'),
                                 _row('a,A,V50|80,1,0', '39-44')])
        self.assertEqual([('Trap damage - Target with 50% of its HP or more', [0]),
                          ('Trap damage - Target with less than 50% of its HP', [1])],
                         entry.aggregates)
        self.assertEqual({0: 'trap', 1: 'trap'}, entry.conditional)

    def test_the_dofus2_table_splits_a_trap_on_its_own_threshold(self):
        generator = _generator()
        with mock.patch.object(generator, 'TARGET_CONDITIONS',
                               generator.TARGET_CONDITIONS_BY_VERSION['dofus2']):
            entry = _placed('trap', [_row('a,A,v25|', '31-35'),
                                     _row('a,A,V25|', '39-44')])
        self.assertEqual([('Trap damage - Target with 25% of its HP or more', [0]),
                          ('Trap damage - Target with less than 25% of its HP', [1])],
                         entry.aggregates)

    def test_a_placed_block_without_a_target_token_stays_one_group(self):
        entry = _placed('trap', [_row('a,A|80,1,0', '31-35'),
                                 _row('a,A|80,1,0', '39-44')])
        self.assertEqual([('Trap damage', [0, 1])], entry.aggregates)

    def test_a_best_element_block_heads_only_its_first_face(self):
        entry = _placed('bomb', [
            _row('a,A|', '10-12', element, best_element_group=1)
            for element in ('EARTH', 'FIRE', 'WATER', 'AIR')])
        self.assertEqual([('Bomb damage - Hit in best element', [0]),
                          ('', [1]), ('', [2]), ('', [3])], entry.aggregates)


class TheTablesCarryTheTrapFacesTests(SimpleTestCase):

    def test_lethal_trap_splits_on_the_threshold_of_each_version(self):
        for version, threshold in THRESHOLDS.items():
            with self.subTest(version=version):
                spell = _spell(LETHAL_TRAP, version)
                self.assertEqual(
                    [('Trap damage - Target with %s%% of its HP or more' % threshold, [0]),
                     ('Trap damage - Target with less than %s%% of its HP' % threshold, [1])],
                    spell.aggregates)
                self.assertEqual({0: 'trap', 1: 'trap'}, spell.conditional)
                top = spell.get_effects_digest().non_crit_dams[-1]
                self.assertEqual([(39, 43), (49, 54)], _ranges(top))

    def test_each_placed_split_is_one_the_spell_text_states(self):
        from chardata.spell_combo import PLACED_LABEL
        for version in THRESHOLDS:
            with open(os.path.join(_REFERENCE_DIR, '%s.json' % version),
                      encoding='utf-8') as handle:
                reference = json.load(handle)
            texts = {entry['id']: entry.get('description') or {}
                     for entries in reference.values() for entry in entries}
            checked = 0
            for spells in get_damage_spells_for_version(version).values():
                for spell in spells:
                    for label, _indices in spell.aggregates or []:
                        placed = PLACED_LABEL.match(label or '')
                        match = placed and _HP_LABEL.match(placed.group(2) or '')
                        if not match:
                            continue
                        checked += 1
                        description = texts.get(spell.spell_id) or {}
                        for language in LANGUAGES:
                            with self.subTest(version=version, spell=spell.name,
                                              language=language, label=label):
                                self.assertRegex(
                                    (description.get(language) or '').lower(),
                                    r'\b%s\s?%%' % match.group(1))
            with self.subTest(version=version):
                self.assertGreaterEqual(checked, 2)


class TheTrapFacesSpeakEveryLanguageTests(SimpleTestCase):

    def test_each_trap_face_reads_natively_in_five_languages(self):
        from chardata.spells_view import convert_aggregates
        for version, threshold in THRESHOLDS.items():
            spell = _spell(LETHAL_TRAP, version)
            digest = spell.get_effects_digest()
            for language, pair in _SHOWN.items():
                with translation.override(language):
                    shown = convert_aggregates(digest.aggregates, version,
                                               digest.non_crit_dams[0])
                with self.subTest(version=version, language=language):
                    self.assertEqual(_faces(pair, threshold), shown)


class TheCompareDigestListsTheScoredFacesTests(SimpleTestCase):

    def _scored(self, spell, version):
        from chardata.spells_view import _create_spell_web_digest
        from fashionistapulp.structure import set_current_game_version
        set_current_game_version(version)
        try:
            return _create_spell_web_digest(spell, version)['scored']
        finally:
            set_current_game_version('dofus3')

    def test_lethal_trap_counts_its_plain_face_at_each_rank(self):
        for version in THRESHOLDS:
            with self.subTest(version=version):
                self.assertEqual({'non_crit': {'0': [[0]], '1': [[0]]},
                                  'crit': {}, 'draw': False},
                                 self._scored(_spell(LETHAL_TRAP, version), version))

    def test_lethal_attack_counts_its_plain_face(self):
        for version in THRESHOLDS:
            with self.subTest(version=version):
                scored = self._scored(_spell(LETHAL_ATTACK, version), version)
                self.assertEqual({'0': [[0]]}, scored['non_crit'])
                self.assertEqual({'0': [[0]]}, scored['crit'])

    def test_a_best_element_hit_lists_one_face_per_element(self):
        scored = self._scored(_spell(VENDETTA, 'dofus3', 'Cra'), 'dofus3')
        self.assertEqual([[0], [1], [2], [3]], scored['non_crit']['0'])
        self.assertFalse(scored['draw'])

    def test_a_hit_the_game_draws_is_averaged(self):
        spell = next(spell for spell in get_damage_spells_for_version('retro')['Ecaflip']
                     if spell.spell_id == BLUFF)
        scored = self._scored(spell, 'retro')
        self.assertTrue(scored['draw'])
        self.assertEqual([[0], [1]], scored['non_crit'][str(len(spell.level_req) - 1)])

    def test_a_glyph_waiting_beside_a_direct_hit_shares_its_face(self):
        for version in THRESHOLDS:
            with self.subTest(version=version):
                scored = self._scored(_spell(PASTURELAND, version, 'Feca'), version)
                self.assertEqual({'0': [[0, 1]]}, scored['non_crit'])
                self.assertEqual({'0': [[0, 1]]}, scored['crit'])

    def test_a_spell_without_groups_or_waiting_rows_sums_every_row(self):
        spell = next(spell for spell in get_damage_spells_for_version('dofus3')['Sram']
                     if not spell.aggregates and not spell.conditional)
        self.assertIsNone(self._scored(spell, 'dofus3'))

    def test_every_listed_face_points_at_a_row_of_its_rank(self):
        from chardata.spells_view import _scored_faces_by_rank
        from fashionistapulp.structure import set_current_game_version
        for version in ('dofus3', 'beta', 'dofus2', 'touch', 'retro'):
            listed = 0
            set_current_game_version(version)
            try:
                for spells in get_damage_spells_for_version(version).values():
                    for spell in spells:
                        digest = spell.get_effects_digest()
                        scored = _scored_faces_by_rank(spell, digest)
                        if scored is None:
                            continue
                        for key, ranks in (('non_crit', digest.non_crit_dams),
                                           ('crit', digest.crit_dams)):
                            for rank, faces in scored[key].items():
                                listed += 1
                                rows = ranks[int(rank)]
                                with self.subTest(version=version, spell=spell.name,
                                                  key=key, rank=rank):
                                    self.assertTrue(faces)
                                    self.assertTrue(all(
                                        0 <= index < len(rows)
                                        for face in faces for index in face))
            finally:
                set_current_game_version('dofus3')
            with self.subTest(version=version):
                self.assertGreater(listed, 0)


class TheSramPagesShowTheTrapFacesTests(TestCase):

    def _build(self, version):
        from fashionistapulp.structure import (get_structure,
                                               set_current_game_version)
        from chardata.models import Char
        set_current_game_version(version)
        try:
            structure = get_structure(version)
            names = []
            for type_name in ('Hat', 'Cloak', 'Belt', 'Boots', 'Amulet'):
                item = next(i for i in structure.types[200][type_name]
                            if not i.removed and i.ankama_id)
                names.append(structure.get_item_name_in_language(item, 'en'))
        finally:
            set_current_game_version('dofus3')
        self.client.post('/%simport/text/' % _prefix(version), {
            'text': '\n'.join(names), 'confirm': '1',
            'char_class': 'Sram', 'level': '200'})
        return Char.objects.order_by('-id').first()

    def _digest(self, char, language, version):
        page = self.client.get('/%sspells/%d/' % (_prefix(version), char.id),
                               HTTP_ACCEPT_LANGUAGE=language, follow=True)
        self.assertEqual(200, page.status_code)
        found = re.search(r'var spellDigests = (.*);', page.content.decode('utf-8'))
        self.assertTrue(found, 'the page carries no spell digests')
        return {digest.get('canonical'): digest
                for digest in json.loads(found.group(1))}['Lethal Trap']

    def test_each_version_names_both_trap_faces_in_five_languages(self):
        for version, threshold in THRESHOLDS.items():
            char = self._build(version)
            self.assertEqual((version, 'Sram'),
                             (char.game_version or 'dofus3', char.char_class))
            for language, pair in _SHOWN.items():
                with self.subTest(version=version, language=language):
                    digest = self._digest(char, language, version)
                    self.assertEqual(_faces(pair, threshold), digest['aggregates'])
                    self.assertEqual(['0', '1'], sorted(digest['conditional']))
                    self.assertEqual(digest['conditional']['0'],
                                     digest['conditional']['1'])
                    self.assertEqual({'0': [[0]], '1': [[0]]},
                                     digest['scored']['non_crit'])


_COMPARE_STATS = {'str': 150, 'int': 100, 'cha': 200, 'agi': 250, 'pow': 50,
                  'dam': 20, 'earthdam': 5, 'firedam': 7, 'waterdam': 3,
                  'airdam': 9, 'cridam': 30}

_COMPARE_DRIVER = r"""
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
var spell = compareSpellDigests[0];
var charLevel = compareCharLevels[allCharIds[0]];
var level = getCompareSpellLevel(spell, charLevel);
var rows = (spell.non_crit_dams[level] || []).map(function (hit) {
  if (!isCompareDirectDamageHit(hit)) return null;
  var resolved = $.extend({}, hit, {element: resolveCompareBestElement(hit.element, stats)});
  return [calculateCompareDamageValue(resolved, false, true, spell, stats),
          calculateCompareDamageValue(resolved, false, false, spell, stats)];
});
console.log(JSON.stringify({
  names: compareSpellDigests.map(function (digest) { return digest.canonical; }),
  scored: spell.scored,
  shown: summarizeCompareSpell(spell, stats, charLevel).normalAvg,
  rows: rows
}));
"""


def _face_value(rows, face):
    return sum(rows[index][0] + rows[index][1] for index in face) / 2.0


def _js_round(value):
    return math.floor(value + 0.5)


class TheSetCompareSumsOneFaceTests(TestCase):

    def _build(self, owner, name, char_class, version):
        from chardata.models import Char
        from fashionistapulp.modelresult import ModelResultMinimal
        base_input = {
            'options': {'ap_exo': False, 'mp_exo': False},
            'origin': 'generated', 'char_level': 200,
            'base_stats_by_attr': {'Vitality': 0, 'Wisdom': 0, 'Strength': 0,
                                   'Intelligence': 0, 'Chance': 0, 'Agility': 0},
            'locked_equips': {},
        }
        stats = {'vit': 0, 'wis': 0, 'str': 0, 'int': 0, 'cha': 0, 'agi': 0}
        return Char.objects.create(
            name=name, char_name=name.lower(), char_class=char_class,
            char_build='build', level=200,
            minimum_stats=b'', minimum_crits=b'', stats_weight=b'',
            options=b'', inclusions=b'', exclusions=b'',
            minimal_solution=pickle.dumps(ModelResultMinimal({}, base_input, stats)),
            owner=owner, link_shared=True, game_version=version)

    def _compare(self, version, char_class, spell_name):
        """The compare page's own script run under node on one spell."""
        node = shutil.which('node')
        if node is None:
            self.skipTest('node is not installed')
        from django.contrib.auth.models import User
        from fashionistapulp.structure import set_current_game_version
        set_current_game_version(version)
        self.addCleanup(set_current_game_version, 'dofus3')
        owner = User.objects.create_user('facecompare', 'fc@test.local', 'pw-42-solid')
        first = self._build(owner, 'FaceOne', char_class, version)
        second = self._build(owner, 'FaceTwo', char_class, version)
        self.client.force_login(owner)
        page = self.client.get(
            '/%scompare_sets/%d/%d/' % (_prefix(version), first.pk, second.pk),
            {'spell_class': char_class, 'spell_name': spell_name})
        self.assertEqual(200, page.status_code)
        scripts = [body for body in re.findall(r'<script[^>]*>(.*?)</script>',
                                               page.content.decode('utf-8'), re.S)
                   if 'var compareSpellDigests' in body]
        self.assertEqual(1, len(scripts))
        driver = _COMPARE_DRIVER.replace('STATS', json.dumps(_COMPARE_STATS))
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
        self.assertEqual([spell_name], result['names'])
        return result

    def test_lethal_trap_shows_its_plain_face_alone(self):
        result = self._compare('dofus3', 'Sram', 'Lethal Trap')
        self.assertEqual({'non_crit': {'0': [[0]], '1': [[0]]}, 'crit': {}, 'draw': False},
                         result['scored'])
        rows = result['rows']
        self.assertEqual(_js_round(_face_value(rows, [0])), result['shown'])
        self.assertNotEqual(_js_round(_face_value(rows, [0, 1])), result['shown'])

    def test_a_best_element_trap_shows_its_highest_face(self):
        result = self._compare('dofus3', 'Cra', 'Vendetta')
        faces = [_face_value(result['rows'], [index]) for index in range(4)]
        self.assertEqual(_js_round(max(faces)), result['shown'])
        self.assertNotEqual(_js_round(sum(faces) / len(faces)), result['shown'])

    def test_a_hit_the_game_draws_shows_the_mean_of_its_faces(self):
        result = self._compare('retro', 'Ecaflip', 'Bluff')
        faces = [_face_value(result['rows'], [0]), _face_value(result['rows'], [1])]
        self.assertEqual(_js_round(sum(faces) / len(faces)), result['shown'])
        self.assertNotEqual(_js_round(max(faces)), result['shown'])

    def test_a_glyph_waiting_beside_a_direct_hit_adds_to_it(self):
        result = self._compare('dofus3', 'Feca', 'Pastureland')
        rows = result['rows']
        self.assertEqual(_js_round(_face_value(rows, [0, 1])), result['shown'])
        self.assertNotEqual(_js_round(_face_value(rows, [0])), result['shown'])
