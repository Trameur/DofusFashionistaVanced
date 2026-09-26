# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Retro secondary stats, base prospecting and critical odds follow Retro's own rules."""

import glob
import html
import json
import os
import pickle
import re
import shutil
import struct
import subprocess
import tempfile
import zlib
from types import SimpleNamespace

from django.test import SimpleTestCase, TestCase
from django.utils import translation

from chardata.models import Char
from chardata.solution import _repair_character_base
from chardata.spell_combo import crit_chance, retro_critical_x
from chardata.util import base_stats_by_attr_for
from fashionistapulp.dofus_constants import STAT_NAME_TO_KEY
from fashionistapulp.model import Model
from fashionistapulp.modelresult import ModelResult, ModelResultMinimal
from fashionistapulp.structure import get_structure, set_current_game_version

# {secondary stat: ({characteristic: gain per point}, text id)}
RATES = {
    'Prospecting': ({'Chance': 0.1}, 'HELP_CHANCE'),
    'AP Loss Resist': ({'Wisdom': 0.25}, 'dofux-130'),
    'MP Loss Resist': ({'Wisdom': 0.25}, 'dofux-130'),
    'Pods': ({'Strength': 5}, 'KBA-36'),
    'Initiative': ({'Strength': 1, 'Intelligence': 1, 'Chance': 1,
                    'Agility': 1}, 'HELP_INITIATIVE'),
    'HP': ({'Vitality': 1}, 'HELP_VITALITY'),
}

# Retro says Wisdom raises these (KBA-17) but states no rate, they take the dodge rate
INFERRED = {
    'AP Reduction': RATES['AP Loss Resist'][0],
    'MP Reduction': RATES['MP Loss Resist'][0],
}

# Retro weighs Agility against Agility, it states no rate for these
UNRATED = {'Dodge': 'KBA-15', 'Lock': 'KBA-15'}

HP_PER_LEVEL = (5, 'HELP_LIFE')

ENUTROF_PROSPECTING = (120, 'KBA-14-enutrof')

STATED = {
    'HELP_CHANCE': '10 en chance augmente la prospection de 1',
    'HELP_INITIATIVE': ("1 point en force, intelligence, chance ou agilité "
                        "donne 1 point d'initiative"),
    'HELP_VITALITY': '1 point donne +1 en vie',
    'HELP_LIFE': ('A chaque niveau, un personnage gagne 5 points de vie '
                  'supplémentaire'),
    'HELP_WISDOM': "esquiver plus facilement les pertes de PA et PM",
    'HELP_AGILITY': 'tes probabilités de faire des coups critiques',
    'KBA-14-enutrof': ('100 points de Prospection quand tu débutes '
                       '(120 pour les Enutrofs)'),
    'KBA-15': "dépend de l'agilité des deux combattants",
    'KBA-17': ('elle augmente les chances de faire perdre des PA ou des PM '
               'à ses adversaires'),
    'KBA-36': 'Un point de force rapporte également 5 pods',
    'dofux-130': ("L'esquive (PA-PM) est boostée par la sagesse "
                  "(Sagesse/4 arrondi à l'inférieur.)"),
}

WEB_PAGES = {'dofux-130': 'https://www.dofux.org'}

DOFUX_CREDIT = ('part of the Dofus Retro pet bonuses, and the AP and MP Loss '
                'Resist that Wisdom gives in Dofus Retro')

LANGUAGES = ('en', 'fr', 'es', 'pt', 'de')

OTHER_VERSIONS = ('dofus3', 'beta', 'dofus2', 'touch')

WISDOM_STATS = ('AP Loss Resist', 'MP Loss Resist', 'AP Reduction',
                'MP Reduction')

CHARACTERISTICS = ('Strength', 'Intelligence', 'Chance', 'Agility', 'Wisdom',
                   'Vitality')

TRAINED = 100


class _Problem:
    def restriction_lt_eq(self, rhs, matrix):
        return list(matrix)


def _solver_rates(version):
    structure = get_structure(version)
    model = SimpleNamespace(
        stats_list=structure.get_stats_list(), problem=_Problem(),
        structure=structure,
        restrictions=SimpleNamespace(minimum_stat_constraints={}))
    Model.create_minimum_stat_constraints(model)
    name_by_id = {stat.id: stat.name for stat in model.stats_list}
    derived = {}
    for name, matrix in model.restrictions.minimum_stat_constraints.items():
        sources = {name_by_id[stat_id]: -coefficient
                   for coefficient, _kind, stat_id in matrix
                   if name_by_id[stat_id] != name}
        if sources:
            derived[name] = sources
    return derived


def _sheet_totals(base, level=200):
    return ModelResult({
        'base_stats_by_attr': dict(base),
        'options': {'ap_exo': False, 'mp_exo': False, 'range_exo': False},
        'char_level': level,
    }).get_stats_total()


class _Restriction:
    rhs = None

    def changeRHS(self, rhs):
        self.rhs = rhs


class TheSolverTests(SimpleTestCase):

    def test_the_solver_derives_each_stat_at_its_stated_or_inferred_rate(self):
        derived = _solver_rates('retro')
        for name in UNRATED:
            derived.pop(name, None)
        expected = {name: rate for name, (rate, _text) in RATES.items()}
        expected.update(INFERRED)
        self.assertEqual(expected, derived)

    def test_the_solver_counts_five_hit_points_per_level(self):
        structure = get_structure('retro')
        floors = []
        for level in (1, 2, 100, 200):
            restrictions = {stat.name: _Restriction()
                            for stat in structure.get_stats_list()}
            model = SimpleNamespace(
                stats_list=structure.get_stats_list(),
                restrictions=SimpleNamespace(
                    minimum_stat_constraints=restrictions),
                modify_advanced_minimum_stat_constraints=lambda minimums: None)
            Model.modify_minimum_stat_constraints(model, {'HP': 0}, level)
            floors.append(restrictions['HP'].rhs)
        self.assertEqual([HP_PER_LEVEL[0], HP_PER_LEVEL[0] * 98,
                          HP_PER_LEVEL[0] * 100],
                         [b - a for a, b in zip(floors, floors[1:])])


class TheStatSheetTests(SimpleTestCase):

    def setUp(self):
        set_current_game_version('retro')
        self.addCleanup(set_current_game_version, 'dofus3')

    @staticmethod
    def _totals(base, level=200):
        return _sheet_totals(base, level)

    def test_each_characteristic_moves_the_sheet_at_the_retro_rates(self):
        name_by_key = {key: name for name, key in STAT_NAME_TO_KEY.items()}
        bare = self._totals({})
        for trained in CHARACTERISTICS:
            grown = self._totals({trained: TRAINED})
            for key in bare:
                name = name_by_key.get(key)
                if name in UNRATED:
                    continue
                if name == trained:
                    expected = TRAINED
                else:
                    rates = INFERRED.get(name) or RATES.get(name, ({},))[0]
                    expected = TRAINED * rates.get(trained, 0)
                with self.subTest(trained=trained, stat=name or key):
                    self.assertAlmostEqual(expected, grown[key] - bare[key])

    def test_the_wisdom_quarter_rounds_down(self):
        bare = self._totals({})
        for wisdom, gained in ((3, 0), (4, 1), (7, 1), (8, 2), (551, 137)):
            grown = self._totals({'Wisdom': wisdom})
            for key in ('apres', 'mpres', 'apred', 'mpred'):
                with self.subTest(wisdom=wisdom, stat=key):
                    self.assertEqual(gained, grown[key] - bare[key])

    def test_the_sheet_counts_five_hit_points_per_level(self):
        for level in (2, 100, 200):
            with self.subTest(level=level):
                self.assertEqual(HP_PER_LEVEL[0],
                                 self._totals({}, level)['hp']
                                 - self._totals({}, level - 1)['hp'])


class TheCriticalOddsTests(SimpleTestCase):

    def test_agility_shortens_x_as_the_client_computes_it(self):
        cases = (
            (50, 42, 141, 4),
            (50, 10, 1400, 16),
            (50, 0, 100, 31),
            (30, 0, 200, 16),
            (50, 0, 100000, 12),
        )
        for base, bonus, agility, x in cases:
            with self.subTest(base=base, bonus=bonus, agility=agility):
                self.assertAlmostEqual(
                    1.0 / x,
                    crit_chance(base, {'ch': bonus, 'agi': agility}, 'retro'))

    def test_low_agility_never_lengthens_x(self):
        for agility in (0, 1, 5):
            with self.subTest(agility=agility):
                self.assertAlmostEqual(
                    1 / 50.0, crit_chance(50, {'ch': 0, 'agi': agility}, 'retro'))

    def test_x_never_drops_under_two(self):
        self.assertAlmostEqual(
            0.5, crit_chance(4, {'ch': 0, 'agi': 1000}, 'retro'))

    def test_a_negative_bonus_or_agility_counts_as_zero(self):
        self.assertAlmostEqual(
            1 / 50.0, crit_chance(50, {'ch': -10, 'agi': 0}, 'retro'))
        self.assertAlmostEqual(
            1 / 50.0, crit_chance(50, {'ch': 0, 'agi': -30}, 'retro'))

    def test_percentage_versions_do_not_read_agility(self):
        for version in ('dofus3', 'beta', 'dofus2', 'touch'):
            with self.subTest(version=version):
                self.assertAlmostEqual(
                    0.15, crit_chance(15, {'ch': 0, 'agi': 1000}, version))


class TheEnutrofProspectingTests(TestCase):

    @staticmethod
    def _char(char_class, game_version):
        return Char.objects.create(
            name='p', char_name='p', char_class=char_class, char_build='b',
            level=200, minimum_stats=b'', minimum_crits=b'', stats_weight=b'',
            options=b'', inclusions=b'', exclusions=b'', link_shared=False,
            game_version=game_version)

    def test_a_retro_enutrof_starts_with_its_own_prospecting(self):
        base = base_stats_by_attr_for(self._char('Enutrof', 'retro'))
        self.assertEqual(ENUTROF_PROSPECTING[0], base['Prospecting'])

    def test_other_retro_classes_start_with_one_hundred(self):
        base = base_stats_by_attr_for(self._char('Iop', 'retro'))
        self.assertEqual(100, base['Prospecting'])

    def test_a_legacy_retro_solution_is_repaired_with_its_class_prospecting(self):
        for char_class, expected in (('Enutrof', ENUTROF_PROSPECTING[0]),
                                     ('Iop', 100)):
            minimal = ModelResultMinimal({}, {'char_level': 200}, {})
            _repair_character_base(self._char(char_class, 'retro'), minimal)
            with self.subTest(char_class=char_class):
                self.assertEqual(
                    expected, minimal.input['base_stats_by_attr']['Prospecting'])

    def test_the_repair_never_overwrites_a_stored_base(self):
        stored = {'AP': 7, 'Prospecting': 100}
        minimal = ModelResultMinimal({}, {'base_stats_by_attr': dict(stored)},
                                     {})
        _repair_character_base(self._char('Enutrof', 'retro'), minimal)
        self.assertEqual(stored, minimal.input['base_stats_by_attr'])


class TheOtherVersionsTests(SimpleTestCase):

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')

    def test_every_other_version_still_derives_one_point_per_ten_wisdom(self):
        for version in OTHER_VERSIONS:
            derived = _solver_rates(version)
            set_current_game_version(version)
            bare = _sheet_totals({})
            grown = _sheet_totals({'Wisdom': TRAINED})
            for name in WISDOM_STATS:
                key = STAT_NAME_TO_KEY[name]
                with self.subTest(version=version, stat=name):
                    self.assertEqual({'Wisdom': 0.1}, derived[name])
                    self.assertEqual(TRAINED // 10, grown[key] - bare[key])


def _retro_lang_cache():
    """Bytes of the Retro client's cached UI texts and knowledge base."""
    root = os.path.join(os.environ.get('APPDATA', ''), 'Dofus Retro',
                        'Pepper Data', 'Shockwave Flash', 'WritableRoot',
                        '#SharedObjects')
    wanted = {b'ANKLANGSO_0', b'ANKXTRASO_0_KBA'}
    found = {}
    for path in glob.glob(os.path.join(root, '*', '*', '*', '*.sol')):
        with open(path, 'rb') as fh:
            data = fh.read()
        if len(data) < 18:
            continue
        size = struct.unpack('>H', data[16:18])[0]
        name = data[18:18 + size]
        if name in wanted:
            found[name] = data
    return b''.join(found.values()) if len(found) == len(wanted) else None


def _retro_client_code():
    path = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Ankama', 'Retro',
                        'resources', 'app', 'retroclient', 'loader.swf')
    if not os.path.exists(path):
        return None
    with open(path, 'rb') as fh:
        data = fh.read()
    return zlib.decompress(data[8:]) if data[:3] == b'CWS' else data[8:]


class TheShippedRetroClientTests(SimpleTestCase):

    def test_every_rule_names_a_stated_sentence(self):
        named = {text for _rate, text in RATES.values()}
        named |= set(UNRATED.values())
        named |= {HP_PER_LEVEL[1], ENUTROF_PROSPECTING[1]}
        self.assertLessEqual(named, set(STATED))

    def test_no_inferred_rate_claims_a_sentence(self):
        self.assertFalse(set(INFERRED) & set(RATES))

    def test_the_retro_client_still_states_these_rules(self):
        cache = _retro_lang_cache()
        if cache is None:
            self.skipTest('no Retro client texts on this machine')
        for text_id, fragment in STATED.items():
            if text_id in WEB_PAGES:
                continue
            with self.subTest(text=text_id):
                self.assertIn(fragment.encode('utf-8'), cache)

    def test_the_retro_client_still_ships_its_critical_function(self):
        code = _retro_client_code()
        if code is None:
            self.skipTest('no Retro client on this machine')
        self.assertIn(b'\x00isTemporis\x00E\x00log\x00min\x00floor\x00', code)
        self.assertIn(b'\x00ACTUAL_CRITICAL_CHANCE\x00', code)


class TheAboutPageCreditsTheWebSourceTests(TestCase):

    def test_dofux_is_credited_for_the_wisdom_dodge_rate_in_five_languages(self):
        shown = {}
        for language in LANGUAGES:
            page = self.client.get('/about/',
                                   headers={'accept-language': language})
            self.assertEqual(200, page.status_code, language)
            body = html.unescape(page.content.decode('utf-8'))
            with translation.override(language):
                credit = translation.gettext(DOFUX_CREDIT)
            for link in set(WEB_PAGES.values()):
                with self.subTest(language=language, link=link):
                    item = re.search(
                        r'<li>\s*<a href="%s">[^<]*</a>(.*?)</li>'
                        % re.escape(link), body, re.S)
                    self.assertIsNotNone(item)
                    self.assertIn(credit, item.group(1))
            shown[language] = credit
        self.assertEqual(len(LANGUAGES), len(set(shown.values())))


_LABEL_DRIVER = r"""
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
var spell = spellDigests.filter(function (d) { return d.type == 'spell'; })[0];
buffsForSpell = {};
console.log(JSON.stringify(CASES.map(function (c) {
  charStats = {ch: c[1], agi: c[2]};
  return critRateLabel(c[0], spell);
})));
"""

LABEL_CASES = (
    (50, 42, 141),
    (50, 10, 1400),
    (50, 0, 100),
    (30, 0, 200),
    (50, 0, 7),
    (50, 0, 0),
    (50, -10, 0),
    (50, 0, -30),
    (4, 0, 1000),
    (50, 60, 0),
)


class TheSpellsPageLabelTests(TestCase):

    def test_the_retro_crit_label_shows_the_x_the_best_turn_uses(self):
        node = shutil.which('node')
        if node is None:
            self.skipTest('node is not installed')
        from django.contrib.auth.models import User
        set_current_game_version('retro')
        self.addCleanup(set_current_game_version, 'dofus3')
        owner = User.objects.create_user('critlabel', 'cl@test.local',
                                         'pw-42-solid')
        base = {'Vitality': 0, 'Wisdom': 0, 'Strength': 0, 'Intelligence': 0,
                'Chance': 0, 'Agility': 0}
        minimal = ModelResultMinimal({}, {
            'options': {'ap_exo': False, 'mp_exo': False},
            'origin': 'generated', 'char_level': 200,
            'base_stats_by_attr': base, 'locked_equips': {}},
            {'vit': 0, 'wis': 0, 'str': 0, 'int': 0, 'cha': 0, 'agi': 0})
        char = Char.objects.create(
            name='CritLabel', char_name='critlabel', char_class='Iop',
            char_build='build', level=200, minimum_stats=b'',
            minimum_crits=b'', stats_weight=b'', options=b'', inclusions=b'',
            exclusions=b'', minimal_solution=pickle.dumps(minimal),
            owner=owner, link_shared=False, game_version='retro')
        self.client.force_login(owner)
        page = self.client.get('/retro/spells/%d/' % char.pk)
        self.assertEqual(200, page.status_code)
        scripts = [body for body in re.findall(
            r'<script[^>]*>(.*?)</script>', page.content.decode('utf-8'), re.S)
            if 'function critRateLabel' in body]
        self.assertEqual(1, len(scripts))
        driver = _LABEL_DRIVER.replace('CASES', json.dumps(LABEL_CASES))
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
        labels = json.loads(done.stdout)
        expected = ['1/%d' % retro_critical_x(base_rate, bonus, agility)
                    for base_rate, bonus, agility in LABEL_CASES]
        self.assertEqual(expected, labels)
