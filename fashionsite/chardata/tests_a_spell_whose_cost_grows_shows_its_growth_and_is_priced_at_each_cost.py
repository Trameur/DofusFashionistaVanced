# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A spell whose AP cost grows shows the growth on its card and is priced at each cast's cost; the new waits read in every language."""
import json
import os
import pickle
import re
import shutil
import subprocess
import tempfile
from types import SimpleNamespace
from unittest import mock

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.utils import translation
from django.utils.translation import gettext

from chardata.models import Char
from chardata.spell_buffs import get_damage_spells_for_version
from chardata.spell_combo import ARMED_BY_ITS_OWN_CAST, BOOSTED_COPIES
from fashionistapulp.modelresult import ModelResultMinimal
from fashionistapulp.structure import set_current_game_version

HARASSING_ARROW = 12439
GROWTH = {'en': '2 AP, then +1 per cast', 'fr': '2 PA, puis +1 par lancer',
          'es': '2 PA, luego +1 por lanzamiento', 'pt': '2 PA, depois +1 por lançamento',
          'de': '2 AP, dann +1 pro Einsatz'}
WITHIN_3_TURNS = {'en': 'on its casts over the next 3 turns', 'fr': 'lors de ses lancers des 3 tours suivants',
                  'es': 'en sus lanzamientos de los 3 turnos siguientes',
                  'pt': 'nos seus lançamentos dos 3 turnos seguintes',
                  'de': 'beim Wirken in den nächsten 3 Runden'}
TARGET_IN_A_STATE = {
    'en': 'only on a target in the state the spell names, in place of its plain hit',
    'fr': "seulement sur une cible dans l'état que le sort nomme, à la place de son coup simple",
    'es': 'solo sobre un objetivo en el estado que el hechizo nombra, en lugar de su golpe simple',
    'pt': 'apenas em um alvo no estado que o feitiço nomeia, no lugar do seu golpe simples',
    'de': 'nur auf einem Ziel in dem Zustand, den der Zauber nennt, anstelle seines einfachen Treffers'}

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
var spells = spellDigests.filter(function (d) { return d.type == 'spell' && d.reference; });
console.log(JSON.stringify({
  grown: spells.filter(function (d) { return d.ap_growth; }).map(function (d) { return referenceLine(d); }),
  plain: spells.filter(function (d) { return !d.ap_growth; }).map(function (d) { return referenceLine(d); })
}));
"""


class TheCardHeaderShowsTheCostGrowthTests(TestCase):

    def _lines(self, version, language):
        node = shutil.which('node')
        if node is None:
            self.skipTest('node is not installed')
        set_current_game_version(version)
        self.addCleanup(set_current_game_version, 'dofus3')
        owner = User.objects.create_user('growthpage%d' % User.objects.count(), 'gp@test.local', 'pw-42-solid')
        base = {'Vitality': 0, 'Wisdom': 0, 'Strength': 0, 'Intelligence': 0, 'Chance': 0, 'Agility': 0}
        minimal = ModelResultMinimal(
            {}, {'options': {'ap_exo': False, 'mp_exo': False}, 'origin': 'generated', 'char_level': 200,
                 'base_stats_by_attr': base, 'locked_equips': {}},
            {'vit': 0, 'wis': 0, 'str': 0, 'int': 0, 'cha': 0, 'agi': 0})
        char = Char.objects.create(
            name='GrowthPage', char_name='growthpage', char_class='Cra', char_build='build', level=200,
            minimum_stats=b'', minimum_crits=b'', stats_weight=b'', options=b'', inclusions=b'',
            exclusions=b'', minimal_solution=pickle.dumps(minimal), owner=owner, link_shared=False,
            game_version=version)
        self.client.force_login(owner)
        prefix = '' if language == 'en' else '/' + language
        page = self.client.get('%s/%s/spells/%d/' % (prefix, version, char.pk))
        self.assertEqual(200, page.status_code)
        scripts = [body for body in re.findall(r'<script\b[^>]*>(.*?)</script\b[^>]*>',
                                               page.content.decode('utf-8'), re.S | re.I)
                   if 'function referenceLine' in body]
        self.assertEqual(1, len(scripts))
        with tempfile.NamedTemporaryFile('w', suffix='.js', encoding='utf-8', delete=False) as handle:
            handle.write('var source = %s;\n%s' % (json.dumps(scripts[0]), _DRIVER))
            name = handle.name
        try:
            done = subprocess.run([node, name], capture_output=True, text=True, encoding='utf-8')
        finally:
            os.unlink(name)
        self.assertEqual(0, done.returncode, done.stderr[-800:])
        return json.loads(done.stdout)

    def test_the_growing_spell_names_its_first_cost_and_its_step(self):
        for language in ('en', 'fr'):
            with self.subTest(language=language):
                lines = self._lines('touch', language)
                self.assertEqual(1, len(lines['grown']))
                self.assertTrue(lines['grown'][0].startswith(GROWTH[language]), lines['grown'][0])
                self.assertFalse([line for line in lines['plain'] if GROWTH[language] in line])

    def test_only_a_spell_with_a_growth_carries_one_in_its_digest(self):
        from chardata.spells_view import _create_spell_web_digest
        self.addCleanup(set_current_game_version, 'dofus3')
        for version in ('touch', 'touchbeta'):
            set_current_game_version(version)
            grown = [spell.spell_id for spells in get_damage_spells_for_version(version).values()
                     for spell in spells if _create_spell_web_digest(spell, version).get('ap_growth')]
            with self.subTest(version=version):
                self.assertEqual([HARASSING_ARROW], grown)


class TheNewLabelsReadInEachLanguageTests(SimpleTestCase):

    def test_the_growth_reads_in_each_language(self):
        for language, text in GROWTH.items():
            with translation.override(language), self.subTest(language=language):
                self.assertEqual(gettext('%(ap)s AP, then +%(step)s per cast') % {'ap': 2, 'step': 1}, text)

    def test_the_three_turn_window_and_the_target_state_read_in_each_language(self):
        from chardata.spells_view import _CONDITIONAL_LABELS
        for language in GROWTH:
            with translation.override(language), self.subTest(language=language):
                self.assertEqual(str(_CONDITIONAL_LABELS['later_cast_within_3_turns']), WITHIN_3_TURNS[language])
                self.assertEqual(str(_CONDITIONAL_LABELS['target_in_a_state']), TARGET_IN_A_STATE[language])

    def test_the_three_turn_window_waits_for_the_spell_own_casts(self):
        self.assertIn('later_cast_within_3_turns', ARMED_BY_ITS_OWN_CAST)
        self.assertIn('target_in_a_state', BOOSTED_COPIES)


def _row(low):
    return SimpleNamespace(min_dam=low, max_dam=low)


class TheBlindGatePricesAGrowingCostAtEachCastTests(SimpleTestCase):

    def _share(self, grown):
        from chardata import weight_tuning as tuning
        grown_cast = SimpleNamespace(spell_id=1, cost=2, cost_growth=1, limit=3, plain_alternatives=[[_row(10)]],
                                     alternatives=[], waiting_plain=[],
                                     recasts=[([[_row(20)]], None), ([[_row(30)]], None)] if grown else None)
        waiting = SimpleNamespace(spell_id=2, cost=3, plain_alternatives=[[_row(30)]], alternatives=[],
                                  waiting_plain=[])
        spell = SimpleNamespace(spell_id=2, casting=True, level_req=(1,), castable=waiting)
        reference = {'Cls': [{'id': 1, 'name': {'en': 'spell 1'}, 'description': {'en': 'Inflicts Fire damage.'}}]}
        with mock.patch('chardata.spell_reference.get_spell_reference', return_value=reference), \
                mock.patch('chardata.spell_buffs.get_damage_spells_for_version', return_value={'Cls': [spell]}), \
                mock.patch('chardata.spell_combo.castable_spells', return_value=[grown_cast]), \
                mock.patch('chardata.spell_combo.Castable', side_effect=lambda spell, level, crit: spell.castable), \
                mock.patch('chardata.spell_combo._chosen_level', return_value=0):
            return tuning.visible_damage_share('Cls', 200, 'dofus3')

    def test_each_cast_lands_its_own_damage_at_the_cost_it_pays(self):
        seen = (10.0 + 20.0 + 30.0) / (2 + 3 + 4)
        self.assertAlmostEqual(seen / (seen + 10.0), self._share(grown=True))

    def test_a_cast_that_lands_like_the_first_still_pays_its_grown_cost(self):
        seen = 3 * 10.0 / (2 + 3 + 4)
        self.assertAlmostEqual(seen / (seen + 10.0), self._share(grown=False))
