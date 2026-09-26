# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Dodge, Lock, Prospecting and Pods follow the Touch client, the other versions keep theirs."""

import pickle
import re
from types import SimpleNamespace

from django.test import SimpleTestCase, TestCase
from django.utils import translation

from chardata.smart_build import _set_weights
from chardata.solution_result import stat_sources
from chardata.util import character_own_stats
from fashionistapulp.dofus_constants import STAT_NAME_TO_KEY
from fashionistapulp.model import Model
from fashionistapulp.modelresult import ModelResult
from fashionistapulp.structure import get_structure, set_current_game_version

# POST {"lang": ...}, the tooltips of the characteristics window
TOUCH_DICTIONARY = ('https://dt-proxy-production-login.ankama-games.com'
                    '/data/dictionary')
TOUCH_DEVBLOG = ('https://www.dofus-touch.com/fr/mmorpg/actualites/devblog/'
                 'billets/1692311-modifications-avant-lancement-nouveaux-'
                 'serveurs')

# {secondary stat: ({characteristic: gain per point}, dictionary key)}
RATES = {
    'Dodge': ({'Chance': 0.1}, 'ui.help.chance'),
    'Lock': ({'Agility': 0.1}, 'ui.help.agility'),
    'AP Loss Resist': ({'Wisdom': 0.1}, 'ui.help.wisdom'),
    'MP Loss Resist': ({'Wisdom': 0.1}, 'ui.help.wisdom'),
    'AP Reduction': ({'Wisdom': 0.1}, 'ui.help.wisdom'),
    'MP Reduction': ({'Wisdom': 0.1}, 'ui.help.wisdom'),
    'Initiative': ({'Strength': 1, 'Intelligence': 1, 'Chance': 1,
                    'Agility': 1}, 'ui.help.initiative'),
    'HP': ({'Vitality': 1}, 'ui.help.vitality'),
}

# Prospecting: 100 + level // 3 + gear, the devblog gives 100 + 66 at level 200
LEVELS_PER_PROSPECTING = 3
BASE_PROSPECTING = 100
HP_PER_LEVEL = 5

# The devblog exists in French only
DEVBLOG_STATED = {
    'Prospecting': ("PPbase + Arrondi (Niveau du joueur / 3) + PP obtenue via "
                    "l'équipement"),
    'Prospecting at level 200': ('Soit une prospection pour un niveau 200 de '
                                 ": 100 + 66 + PP obtenue via l'équipement"),
    'Pods': ('nous allons retirer le gain de pods issu de la caractéristique '
             'Force.'),
    'Dodge and Lock': ('La chance augmentera ainsi la Fuite des personnages, '
                       'tandis que l’Agilité augmentera le Tacle.'),
}

# ui.help.strength and ui.help.prospecting are the whole tooltip
STATED = {
    ('en', 'ui.help.chance'): '10 Chance points will increase Dodge by 1.',
    ('fr', 'ui.help.chance'): '10 points de Chance augmentent la Fuite de 1.',
    ('en', 'ui.help.agility'): '10 Agility points will increase Lock by 1.',
    ('fr', 'ui.help.agility'): "10 points d'Agilité augmentent le Tacle de 1.",
    ('en', 'ui.help.wisdom'): ('Investing 10 points gives you 1 point of AP '
                               'and MP Parry and 1 point of AP and MP '
                               'Reduction.'),
    ('en', 'ui.help.initiative'): ('Each Strength, Intelligence, Chance or '
                                   'Agility point gives 1 Initiative point.'),
    ('en', 'ui.help.vitality'): 'Each Vitality point gives 1 HP.',
    ('en', 'ui.help.strength'): 'Strength increases Earth and Neutral damage.',
    ('fr', 'ui.help.strength'): 'La Force augmente les dommages Terre et Neutre.',
    ('en', 'ui.help.prospecting'): ('Prospecting increases your odds of '
                                    'earning equipment from combat.'),
    ('en', 'ui.helpWindow.category2sub2text'): ('Your Prospecting will also '
                                                'increase as you level up '
                                                'your character.'),
    ('fr', 'ui.helpWindow.category2sub2text'): ('La Prospection augmente '
                                                'également à mesure que vous '
                                                'gagnez des niveaux sur votre '
                                                'personnage.'),
    ('en', 'ui.helpWindow.category2sub20text'): ('levelling up your character '
                                                 'will also increase their '
                                                 'Prospecting.'),
}

OTHER_VERSIONS = ('dofus3', 'beta', 'dofus2', 'retro')

CHARACTERISTICS = ('Strength', 'Intelligence', 'Chance', 'Agility', 'Wisdom',
                   'Vitality')

TRAINED = 1000

LEVEL_LABEL = {'en': 'Level', 'fr': 'Niveau', 'es': 'Nivel', 'pt': 'Nível',
               'de': 'Stufe'}


class _Problem:
    def restriction_lt_eq(self, rhs, matrix):
        return list(matrix)


class _Restriction:
    rhs = None

    def changeRHS(self, rhs):
        self.rhs = rhs


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


def _floors(version, minimums, level):
    structure = get_structure(version)
    restrictions = {stat.name: _Restriction()
                    for stat in structure.get_stats_list()}
    model = SimpleNamespace(
        stats_list=structure.get_stats_list(), structure=structure,
        restrictions=SimpleNamespace(minimum_stat_constraints=restrictions),
        modify_advanced_minimum_stat_constraints=lambda minimums: None)
    Model.modify_minimum_stat_constraints(model, minimums, level)
    return {name: restriction.rhs for name, restriction in restrictions.items()}


def _sheet(version, trained=None, level=200):
    base = dict(character_own_stats(level, 'Iop', version))
    base.update(trained or {})
    return ModelResult({
        'base_stats_by_attr': base,
        'options': {'ap_exo': False, 'mp_exo': False, 'range_exo': False},
        'char_level': level,
    })


def _pulp_solver_available():
    try:
        import pulp
        return bool(pulp.listSolvers(onlyAvailable=True))
    except Exception:
        return False


def _weights(version, aspects, race='Iop', level=200):
    char = SimpleNamespace(char_class=race, level=level, game_version=version)
    return _set_weights(char, set(aspects), apply=False)


class TheTouchSolverTests(SimpleTestCase):

    def test_the_solver_derives_each_stat_at_the_client_rate(self):
        expected = {name: rate for name, (rate, _key) in RATES.items()}
        self.assertEqual(expected, _solver_rates('touch'))

    def test_a_prospecting_minimum_counts_a_third_of_the_level(self):
        for level in (1, 2, 3, 4, 60, 199, 200):
            floors = _floors('touch', {'Prospecting': 250}, level)
            with self.subTest(level=level):
                self.assertEqual(-250 + level // LEVELS_PER_PROSPECTING,
                                 floors['Prospecting'])

    def test_the_hit_point_floor_still_counts_five_per_level(self):
        for level in (2, 100, 200):
            with self.subTest(level=level):
                self.assertEqual(
                    HP_PER_LEVEL,
                    _floors('touch', {'HP': 0}, level)['HP']
                    - _floors('touch', {'HP': 0}, level - 1)['HP'])


class TheTouchSheetTests(SimpleTestCase):

    def setUp(self):
        set_current_game_version('touch')
        self.addCleanup(set_current_game_version, 'dofus3')

    def test_a_bare_level_200_character_has_166_prospecting(self):
        self.assertEqual(166, _sheet('touch').get_stats_total()['pp'])

    def test_prospecting_grows_by_one_every_three_levels(self):
        for level in (1, 2, 3, 4, 60, 100, 199, 200):
            with self.subTest(level=level):
                self.assertEqual(
                    BASE_PROSPECTING + level // LEVELS_PER_PROSPECTING,
                    _sheet('touch', level=level).get_stats_total()['pp'])

    def test_each_characteristic_moves_the_sheet_only_at_the_client_rates(self):
        name_by_key = {key: name for name, key in STAT_NAME_TO_KEY.items()}
        bare = _sheet('touch').get_stats_total()
        for trained in CHARACTERISTICS:
            grown = _sheet('touch', {trained: TRAINED}).get_stats_total()
            for key in bare:
                name = name_by_key.get(key)
                if name == trained:
                    expected = TRAINED
                else:
                    expected = TRAINED * RATES.get(name, ({},))[0].get(
                        trained, 0)
                with self.subTest(trained=trained, stat=name or key):
                    self.assertAlmostEqual(expected, grown[key] - bare[key])

    def test_a_thousand_chance_agility_and_strength_give_dodge_lock_and_initiative(self):
        bare = _sheet('touch').get_stats_total()
        grown = _sheet('touch', {'Chance': TRAINED, 'Agility': TRAINED,
                                 'Strength': TRAINED}).get_stats_total()
        gained = {key: grown[key] - bare[key]
                  for key in ('dodge', 'lock', 'pp', 'pod', 'init')}
        self.assertEqual({'dodge': 100, 'lock': 100, 'pp': 0, 'pod': 0,
                          'init': 3000}, gained)


class TheTouchBreakdownTests(SimpleTestCase):

    def setUp(self):
        set_current_game_version('touch')
        self.addCleanup(set_current_game_version, 'dofus3')

    def _lines(self, language='en'):
        result = _sheet('touch', {'Chance': TRAINED, 'Agility': TRAINED,
                                  'Strength': TRAINED})
        with translation.override(language):
            sources = stat_sources(result)
        return result.get_stats_total(), {
            key: {line['label']: line['value'] for line in sources.get(key, [])}
            for key in ('dodge', 'lock', 'pp', 'pod')}

    def test_each_line_names_the_touch_source(self):
        total, lines = self._lines()
        self.assertEqual({'Chance': 100}, lines['dodge'])
        self.assertEqual({'Agility': 100}, lines['lock'])
        self.assertEqual({'Base': BASE_PROSPECTING, 'Level': 66}, lines['pp'])
        self.assertEqual({'Base': total['pod']}, lines['pod'])

    def test_the_lines_add_up_to_the_sheet(self):
        total, lines = self._lines()
        for key, by_label in lines.items():
            with self.subTest(stat=key):
                self.assertEqual(total[key], sum(by_label.values()))

    def test_the_level_line_is_translated(self):
        for language, label in LEVEL_LABEL.items():
            _total, lines = self._lines(language)
            with self.subTest(language=language):
                self.assertEqual(66, lines['pp'].get(label))


class TheTouchWeightsTests(SimpleTestCase):

    CASES = (('Iop', ('str',)), ('Cra', ('agi',)), ('Enutrof', ('cha',)),
             ('Sram', ('agi', 'pvp')), ('Feca', ('int', 'duel')),
             ('Sacrier', ('str', 'agi')))

    def test_agility_pays_for_lock_and_chance_for_dodge(self):
        for race, aspects in self.CASES:
            weights = _weights('touch', aspects, race)
            with self.subTest(race=race, aspects=aspects):
                self.assertGreaterEqual(weights['agi'],
                                        int(weights['lock'] / 10))
                self.assertGreaterEqual(weights['cha'],
                                        int(weights['dodge'] / 10))

    def test_prospecting_adds_no_chance_weight(self):
        self.assertEqual(_weights('touch', ('cha',))['cha'],
                         _weights('touch', ('cha', 'pp'))['cha'])
        self.assertEqual(0, _weights('touch', ('pp',), 'Enutrof')['cha'])

    def test_pods_add_no_strength_weight(self):
        self.assertEqual(_weights('touch', ('agi',))['str'],
                         _weights('touch', ('agi', 'pods'))['str'])


class TheOtherVersionsTests(SimpleTestCase):

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')

    def test_the_solver_keeps_agility_dodge_chance_prospecting_and_strength_pods(self):
        for version in OTHER_VERSIONS:
            derived = _solver_rates(version)
            with self.subTest(version=version):
                self.assertEqual({'Agility': 0.1}, derived['Dodge'])
                self.assertEqual({'Agility': 0.1}, derived['Lock'])
                self.assertEqual({'Chance': 0.1}, derived['Prospecting'])
                self.assertEqual({'Strength': 5}, derived['Pods'])
                self.assertEqual(-250, _floors(version, {'Prospecting': 250},
                                               200)['Prospecting'])

    def test_the_sheet_keeps_agility_dodge_chance_prospecting_and_strength_pods(self):
        for version in OTHER_VERSIONS:
            set_current_game_version(version)
            bare = _sheet(version).get_stats_total()
            grown = _sheet(version, {'Chance': TRAINED, 'Agility': TRAINED,
                                     'Strength': TRAINED}).get_stats_total()
            gained = {key: grown[key] - bare[key]
                      for key in ('dodge', 'lock', 'pp', 'pod')}
            with self.subTest(version=version):
                self.assertEqual(BASE_PROSPECTING, bare['pp'])
                self.assertEqual({'dodge': 100, 'lock': 100, 'pp': 100,
                                  'pod': 5000}, gained)

    def test_the_weights_keep_their_agility_chance_and_strength_floors(self):
        for version in OTHER_VERSIONS:
            weights = _weights(version, ('str',))
            prospector = _weights(version, ('pp',), 'Enutrof')
            porter = _weights(version, ('agi', 'pods'))
            with self.subTest(version=version):
                self.assertGreaterEqual(
                    weights['agi'],
                    int((weights['dodge'] + weights['lock']) / 10))
                self.assertEqual(round(prospector['pp'] / 10),
                                 prospector['cha'])
                self.assertEqual(round(porter['pod'] / 5), porter['str'])


class TheSolvedTouchBuildTests(TestCase):

    def setUp(self):
        from django.contrib.auth.models import User
        set_current_game_version('touch')
        self.addCleanup(set_current_game_version, 'dofus3')
        self.owner = User.objects.create_user('touchpassives',
                                              'tp@test.local', 'pw-42-solid')
        self.client.force_login(self.owner)

    def _solve(self, char):
        from chardata.solution import get_solution
        page = self.client.get('/touch/fashion/%d/' % char.pk)
        self.assertEqual(302, page.status_code)
        self.assertNotIn('infeasible', page['Location'])
        char.refresh_from_db()
        return get_solution(char)

    def test_a_solved_chance_build_meets_its_prospecting_and_dodge_floors(self):
        from django.test import RequestFactory
        from chardata.coaching_view import create_build
        from chardata.min_stats import get_min_stats
        if not _pulp_solver_available():
            self.skipTest('no pulp solver available')
        request = RequestFactory().post('/')
        request.user = self.owner
        char = create_build(request, 'Enutrof', 200, {'cha'}, 'touch')
        first = self._solve(char).get_stats_total()
        minimums = get_min_stats(char)
        minimums.update({'Prospecting': first['pp'] + 20,
                         'Dodge': first['dodge'] + 10})
        char.minimum_stats = pickle.dumps(minimums)
        char.save()
        result = self._solve(char)
        total = result.get_stats_total()
        self.assertGreaterEqual(total['pp'], minimums['Prospecting'])
        self.assertGreaterEqual(total['dodge'], minimums['Dodge'])
        sources = stat_sources(result)
        for key in ('dodge', 'lock', 'pp', 'pod'):
            with self.subTest(stat=key):
                self.assertEqual(total[key], sum(
                    line['value'] for line in sources.get(key, [])))


class TheSourcesTests(SimpleTestCase):

    def test_every_rate_names_a_stated_tooltip(self):
        stated = {key for _language, key in STATED}
        self.assertLessEqual({key for _rate, key in RATES.values()}, stated)

    def test_the_devblog_example_rounds_the_level_third_down(self):
        base, from_level = re.search(
            r'(\d+) \+ (\d+) \+',
            DEVBLOG_STATED['Prospecting at level 200']).groups()
        self.assertEqual((BASE_PROSPECTING, 200 // LEVELS_PER_PROSPECTING),
                         (int(base), int(from_level)))
