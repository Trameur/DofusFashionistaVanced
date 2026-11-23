# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A beta key registered under Touch, Retro or Dofus 2 answers every game rule as its main game does."""
import inspect
import sqlite3
import tempfile
from pathlib import Path
from unittest import mock

from django.test import RequestFactory, SimpleTestCase
from django.utils import translation

from chardata import (context_processors, forgemagie_data, guides_content, spell_combo,
                      spells_view, translation_util, weapon_header, weight_tuning, workshop_sources)
from chardata.spell_modifiers import SpellModifier
from fashionistapulp import dofus_constants, model, modelresult
from fashionistapulp.game_versions import GAME_VERSIONS, GameVersion, main_game, version_keys

STAGED_BETAS = {
    'touchbeta': GameVersion('touchbeta', 'Touch Beta', 'items_touchbeta.db',
                             'item_db_dumped_touchbeta.dump', seo_word='Touch Beta',
                             experimental=True, temporix=True, extra_slot_types=('Emblem',),
                             family='touch', channel='beta'),
    'retrobeta': GameVersion('retrobeta', 'Retro Beta', 'items_retrobeta.db',
                             'item_db_dumped_retrobeta.dump', seo_word='Retro Beta',
                             experimental=True, rings_can_double=False, exo_per_item=True,
                             family='retro', channel='beta'),
    'dofus2beta': GameVersion('dofus2beta', 'Dofus 2 Beta', 'items_dofus2beta.db',
                              'item_db_dumped_dofus2beta.dump', seo_word='2 Beta',
                              experimental=True, family='dofus2', channel='beta'),
}


def stat_names(key):
    with translation.override('fr'):
        return [translation_util.localized_stat_name(name, key)
                for _, name in sorted(translation_util.VERSION_STAT_NAMES)]


def one_percent_weights(key):
    distinct = {'modern': 31, 'dofus2': 32, 'touch': 33, 'retro': 34}
    with mock.patch.dict(forgemagie_data._ONE_PERCENT_OVER_WEIGHT, distinct):
        return forgemagie_data.get_one_percent_over_weight(key)


def heal_hits(key):
    with translation.override('en'):
        return [weapon_header.format_heal_hit(key, 3, 9, element, {'Fire': 'Fire'})
                for element in ('Fire', 'Water', None)]


def craft_levels(key):
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / 'items.db'
        conn = sqlite3.connect(path)
        conn.execute('CREATE TABLE item_craft_jobs (item INTEGER, job_ankama_id INTEGER, level INTEGER)')
        conn.execute('CREATE TABLE job_names (job_ankama_id INTEGER, language TEXT, name TEXT)')
        conn.execute('INSERT INTO item_craft_jobs VALUES (1, 2, 80)')
        conn.execute("INSERT INTO job_names VALUES (2, 'en', 'Smith')")
        conn.commit()
        conn.close()
        with mock.patch.object(workshop_sources, 'get_items_db_path', return_value=str(path)):
            return workshop_sources.get_item_craft_jobs([1], key, 'en')


def guide_groups(key):
    return [guides_content._guide_group(guide, key)
            for guide in guides_content.GUIDES.values() if 'i18n_by_group' in guide]


def crit_rates(key):
    return [spell_combo.crit_chance(base, stats, key)
            for base in (-1, 0, 5, 30, 50)
            for stats in ({}, {'ch': 10}, {'ch': -20, 'agi': 300})]


def weapon_headers(key):
    with translation.override('en'):
        return [weapon_header.format_weapon_header(key, weapon_type, ap, chance, 5)
                for weapon_type in (None, 'Sword') for ap in (None, 4)
                for chance in (-1, 0, 30)]


def modifier_phrases(key):
    with translation.override('en'):
        return [spells_view._modifier_phrase(SpellModifier(kind, 3, 'Ring'), key)
                for kind in ('critical', 'damage')]


RULES = {
    'percent_resist_cap': dofus_constants.percent_resist_cap,
    'get_stat_maximum': dofus_constants.get_stat_maximum,
    'get_soft_caps_for': lambda key: dofus_constants.get_soft_caps_for(key, 'Iop'),
    'scrolls_push_cost_curve': dofus_constants.scrolls_push_cost_curve,
    'max_scroll_for_version': lambda key: [dofus_constants.max_scroll_for_version(key, level)
                                           for level in (None, 150, 200)],
    '_minimum_dependencies': model._minimum_dependencies,
    '_minimum_bound': lambda key: model._minimum_bound(key, 'Prospecting', 300, 200),
    'wisdom_per_ap_mp_dodge_point': modelresult.wisdom_per_ap_mp_dodge_point,
    'characteristic_passives': modelresult.characteristic_passives,
    'level_prospecting': lambda key: modelresult.level_prospecting(key, 200),
    'crit_chance': crit_rates,
    'format_weapon_header': weapon_headers,
    '_modifier_phrase': modifier_phrases,
    'get_ruleset': forgemagie_data.get_ruleset,
    'get_one_percent_over_weight': one_percent_weights,
    'localized_stat_name': stat_names,
    'format_heal_hit': heal_hits,
    'get_item_craft_jobs': craft_levels,
    'spell_icon_language': spells_view._icon_language,
    'summon_only_spells': spell_combo.summon_only_spells,
    'guide_group': guide_groups,
}

# weapon_header.py tests the zero crit rate on a per-version table, which must name each key itself
NAMED_PER_KEY = {('touchbeta', 'format_weapon_header'), ('dofus2beta', 'format_weapon_header')}


class ABetaFollowsItsMainGamesRules(SimpleTestCase):

    def setUp(self):
        patcher = mock.patch.dict(GAME_VERSIONS, STAGED_BETAS)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_main_game_names_the_family_and_leaves_an_unknown_key_alone(self):
        self.assertEqual('touch', main_game('touchbeta'))
        self.assertEqual('retro', main_game('retrobeta'))
        self.assertEqual('dofus3', main_game('beta'))
        for key in version_keys(include_experimental=True):
            self.assertEqual(GAME_VERSIONS[key].family, main_game(key))
        for unknown in (None, '', 'nope'):
            self.assertEqual(unknown, main_game(unknown))

    def test_every_rule_answers_for_a_beta_as_for_its_main_game(self):
        for beta, version in STAGED_BETAS.items():
            for name, rule in RULES.items():
                if (beta, name) in NAMED_PER_KEY:
                    continue
                with self.subTest(beta=beta, rule=name):
                    self.assertEqual(rule(version.family), rule(beta))

    def test_the_rules_compared_do_tell_the_main_games_apart(self):
        for main in ('touch', 'retro', 'dofus2'):
            differing = [name for name, rule in RULES.items() if rule(main) != rule('dofus3')]
            with self.subTest(main=main):
                self.assertTrue(differing)

    def test_the_summon_only_spells_reach_the_weight_tuning_check(self):
        source = inspect.getsource(weight_tuning.visible_damage_share)
        self.assertIn('in summon_only_spells(game_version)', source)
        self.assertNotIn('ONLY_HITS_A_SUMMON', source)

    def test_an_explicit_entry_of_a_beta_wins_over_its_main_game(self):
        with mock.patch.dict(spells_view.SPELL_ICON_LANGUAGE, {'retrobeta': 'es'}), \
                mock.patch.dict(spell_combo.ONLY_HITS_A_SUMMON, {'retrobeta': {1: 'x'}}):
            self.assertEqual('es', spells_view._icon_language('retrobeta'))
            self.assertEqual({1: 'x'}, spell_combo.summon_only_spells('retrobeta'))
        self.assertEqual('fr', spells_view._icon_language('retrobeta'))

    def test_the_six_current_keys_answer_as_before(self):
        self.assertEqual(['en', 'en', 'en', 'fr', 'fr', 'en'],
                         [spells_view._icon_language(key)
                          for key in ('dofus3', 'beta', 'dofus2', 'touch', 'retro', 'wakfu')])
        self.assertEqual({}, spell_combo.summon_only_spells('dofus2'))
        self.assertEqual({}, spell_combo.summon_only_spells(None))

    def test_templates_receive_the_main_game_of_the_page(self):
        for key, expected in (('touchbeta', 'touch'), ('retrobeta', 'retro'), ('beta', 'dofus3'),
                              ('dofus3', 'dofus3'), ('touch', 'touch')):
            request = RequestFactory().get('/encyclopedia/')
            request.game_version = key
            with self.subTest(key=key):
                self.assertEqual(expected,
                                 context_processors.game_version(request)['current_main_version'])
