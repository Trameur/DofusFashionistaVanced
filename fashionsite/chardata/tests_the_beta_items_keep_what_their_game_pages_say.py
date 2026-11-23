# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The Beta items and sets read back from the database as the item pages of their client describe them."""
import contextlib
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile

from django.test import SimpleTestCase, TestCase
from django.utils import translation

from chardata.encyclopedia_view import _get_set_bonuses
from chardata.official_site import get_item_link, get_set_link
from chardata.solution_result import evolve_result_item
from chardata.solver_guard import pulp_solver_required
from chardata.tests_a_piece_for_one_sex_or_one_name_is_worn_only_by_that_character import (
    OPTIONS as SOLVE_OPTIONS)
from fashionistapulp import dracorunes
from fashionistapulp.dofus_constants import STATS_NAMES
from fashionistapulp.model import Model, ModelInput
from fashionistapulp.modelresult import ModelResultItem, ModelResultSet
from fashionistapulp.spell_text import fold_spell_blocks
from fashionistapulp.structure import get_structure, set_current_game_version

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PAGES = os.path.join(ROOT, 'itemscraper', 'beta')
LANGUAGES = ('en', 'fr', 'es', 'pt', 'de')
ITEM_CATEGORIES = ('equipment', 'resources', 'consumables', 'quest_items', 'cosmetics')


def page(category, language):
    with open(os.path.join(PAGES, 'all_%s_%s.json' % (category, language)), encoding='utf-8') as handle:
        body = json.load(handle)
    return body['sets' if category == 'sets' else 'items']


def clean_display_name(name):
    if 'untranslated_tag' not in sys.modules:
        spec = importlib.util.spec_from_file_location(
            'untranslated_tag', os.path.join(ROOT, 'itemscraper', 'untranslated_tag.py'))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        sys.modules['untranslated_tag'] = module
    return sys.modules['untranslated_tag'].clean_display_name(name)


class TheBetaItemsKeepWhatTheirGamePagesSayTests(SimpleTestCase):

    def test_an_untranslated_beta_name_shows_the_french_text_without_its_tag(self):
        structure = get_structure('beta')
        french = {row['ankama_id']: row['name'] for row in page('equipment', 'fr')}
        checked, wrong = 0, []
        for language in LANGUAGES:
            for row in page('equipment', language):
                if not row['name'].startswith('[!]'):
                    continue
                item = structure.get_item_by_ankama_id(row['ankama_id'])
                if item is None:
                    continue
                checked += 1
                shown = item.localized_names.get(language)
                if shown != clean_display_name(row['name']) or shown != french[row['ankama_id']]:
                    wrong.append((row['ankama_id'], language, shown))
        self.assertEqual([], wrong[:5])
        tagged_sets = [(row['ankama_id'], language) for language in LANGUAGES for row in page('sets', language)
                       if row['name'].startswith('[!]')]
        for set_id, language in tagged_sets:
            item_set = next((s for s in structure.get_sets_list() if s.ankama_id == set_id), None)
            if item_set is not None:
                checked += 1
                with self.subTest(set=set_id, language=language):
                    self.assertFalse(item_set.localized_names.get(language, '').startswith('[!]'))
        self.assertTrue(checked)

    def test_a_set_whose_member_is_missing_from_the_game_keeps_its_bonuses(self):
        structure = get_structure('beta')
        in_game = {row['ankama_id'] for category in ITEM_CATEGORIES for row in page(category, 'en')}
        sets = [row for row in page('sets', 'en') if set(row['equipment_ids']) - in_game]
        for row in sets:
            item_set = next((s for s in structure.get_sets_list() if s.ankama_id == row['ankama_id']), None)
            with self.subTest(set=row['ankama_id']):
                self.assertIsNotNone(item_set)
                present = [ankama_id for ankama_id in row['equipment_ids'] if ankama_id in in_game]
                members = sorted(structure.get_item_by_id(item_id).ankama_id for item_id in item_set.items)
                self.assertEqual(sorted(present), members)
                tiers = sorted(int(count) for count, effects in row['effects'].items() if effects)
                self.assertEqual(tiers, sorted(item_set.bonus_per_num_items))
                reachable = [count for count in tiers if count <= len(present)]
                self.assertTrue(reachable, 'no bonus tier is reachable with %d members' % len(present))
                for count in reachable:
                    self.assertTrue(item_set.bonus_per_num_items[count])

    def test_a_beta_dracorune_is_a_game_resource_and_never_also_an_item(self):
        runes = dracorunes.load_runes('beta')
        rune_ids = [rune['item_id'] for rune in runes['runes']]
        self.assertTrue(rune_ids)
        self.assertEqual(len(rune_ids), len(set(rune_ids)))
        resources = {row['ankama_id'] for row in page('resources', 'en')}
        self.assertEqual([], [rune_id for rune_id in rune_ids if rune_id not in resources])
        structure = get_structure('beta')
        self.assertEqual([], [rune_id for rune_id in rune_ids if structure.get_item_by_ankama_id(rune_id)])
        names = {name for item in structure.get_concatenated_items_lists() for name in item.localized_names.values()}
        self.assertEqual([], [rune['names'] for rune in runes['runes'] if set(rune['names'].values()) & names])


def max_effects():
    if 'max_effects' not in sys.modules:
        spec = importlib.util.spec_from_file_location(
            'max_effects', os.path.join(ROOT, 'itemscraper', 'max_effects.py'))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        sys.modules['max_effects'] = module
    return sys.modules['max_effects']


def page_caps(row):
    """[(stat name, max value)] of the "Max." effects an item page lists."""
    return max_effects().max_caps(
        [(effect['int_minimum'], effect['int_maximum'], effect['type']['name'])
         for effect in row.get('effects') or []])


DRACONIFER_FINERY = 34725
GUIRAS_ASHES = 1119


class AnItemMaxCapReachesTheSolverTests(SimpleTestCase):

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')
        set_current_game_version('beta')
        self.structure = get_structure('beta')

    def test_every_max_effect_of_an_item_page_reaches_its_item(self):
        checked, wrong = 0, []
        for row in page('equipment', 'en'):
            caps = page_caps(row)
            if not caps:
                continue
            item = self.structure.get_item_by_ankama_id(row['ankama_id'])
            self.assertIsNotNone(item, row['ankama_id'])
            checked += 1
            expected = sorted((self.structure.get_stat_by_name(name).id, value) for name, value in caps)
            if sorted(item.max_caps) != expected:
                wrong.append((row['ankama_id'], item.max_caps, expected))
        self.assertEqual([], wrong)
        self.assertGreaterEqual(checked, 4)

    def solve(self, locked):
        base = {name: 0 for name, _key in STATS_NAMES}
        base.update({'AP': 6, 'MP': 3, 'Summon': 1, 'Prospecting': 100, 'Pods': 1000})
        model = Model()
        model.setup(ModelInput(30, base, {}, locked, [], {'vit': 1, 'ap': 400},
                               dict(SOLVE_OPTIONS), 'Iop', 145))
        model.run()
        self.assertEqual('Optimal', model.get_solved_status())
        ap = self.structure.get_stat_by_key('ap').id
        return model.problem.pulp_vars['stat_%d' % ap].varValue

    @pulp_solver_required
    def test_a_worn_capping_item_holds_the_build_at_its_cap(self):
        finery = self.structure.get_item_by_ankama_id(DRACONIFER_FINERY)
        ap = self.structure.get_stat_by_key('ap').id
        cap = dict(finery.max_caps)[ap]
        self.assertGreater(self.solve({}), cap, 'no build at this level goes past the cap')
        self.assertLessEqual(self.solve({'amulet': finery.id}), cap)

    def test_the_result_and_its_card_show_the_cap(self):
        finery = self.structure.get_item_by_ankama_id(DRACONIFER_FINERY)
        result_item = ModelResultItem(finery)
        self.assertEqual((('ap', 'AP', 7),), tuple(result_item.get_max_caps()))
        with translation.override('fr'):
            evolve_result_item(result_item)
        self.assertIn('Max. PA 7', [line.text for line in result_item.stats_lines])


class ASetSpecialSpellIsShownTests(SimpleTestCase):

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')
        set_current_game_version('beta')
        self.structure = get_structure('beta')

    def item_set(self, set_id):
        return next(s for s in self.structure.get_sets_list() if s.ankama_id == set_id)

    def test_every_special_spell_of_a_set_page_reaches_its_tier(self):
        checked, wrong = 0, []
        for language in LANGUAGES:
            for row in page('sets', language):
                for count, effects in (row.get('effects') or {}).items():
                    lines = [effect['formatted'] for effect in effects or []
                             if effect['type']['name'] == '-special spell-']
                    if not lines:
                        continue
                    checked += 1
                    item_set = self.item_set(row['ankama_id'])
                    stored = item_set.localized_extras.get(int(count), {}).get(language)
                    if stored != '\n'.join(lines).split('\n'):
                        wrong.append((row['ankama_id'], count, language))
        self.assertEqual([], wrong)
        self.assertTrue(checked)

    def test_guiras_ashes_shows_its_spell_at_two_and_three_pieces(self):
        item_set = self.item_set(GUIRAS_ASHES)
        rows = {row['ankama_id']: row for row in page('sets', 'fr')}
        spell = next(effect['formatted'] for effect in rows[GUIRAS_ASHES]['effects']['2']
                     if effect['type']['name'] == '-special spell-')
        name = fold_spell_blocks(spell.split('\n'))[0][0]
        with translation.override('fr'):
            groups = {group['num_pieces']: group
                      for group in _get_set_bonuses(self.structure, item_set, 'fr')}
            for pieces in (2, 3):
                with self.subTest(pieces=pieces):
                    extras = groups[pieces]['extras']
                    self.assertEqual([name], [extra['text'] for extra in extras])
                    self.assertIsNotNone(extras[0]['spell_tip'])
                    result_set = ModelResultSet(item_set, pieces)
                    self.assertEqual([name], result_set.get_extras()[0])
        self.assertNotIn(1, groups)


class TheEncyclopediaPagesShowTheCapAndTheSpellTests(TestCase):

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')
        self.structure = get_structure('beta')

    def test_the_set_page_names_the_spell_of_each_tier(self):
        item_set = next(s for s in self.structure.get_sets_list() if s.ankama_id == GUIRAS_ASHES)
        name = fold_spell_blocks(item_set.localized_extras[2]['en'])[0][0]
        answer = self.client.get(get_set_link(GUIRAS_ASHES, item_set.localized_names['en'], 'beta'))
        self.assertEqual(200, answer.status_code)
        self.assertEqual(2, answer.content.decode('utf-8').count('<span class="spell-line">%s</span>' % name))

    def test_the_item_page_shows_the_cap_of_the_item(self):
        finery = self.structure.get_item_by_ankama_id(DRACONIFER_FINERY)
        answer = self.client.get(get_item_link(finery.ankama_type, finery.ankama_id,
                                               finery.localized_names['en'], 'beta'))
        self.assertEqual(200, answer.status_code)
        self.assertContains(answer, 'Max. AP 7')


class MaxEffectCharacteristicsAreReadFromTheClientTests(SimpleTestCase):

    def extraction(self, entries):
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder, True)
        refs = [{'data': {'id': char_id, 'keyword': keyword}} for char_id, keyword in entries]
        with open(os.path.join(folder, 'characteristics.json'), 'w', encoding='utf-8') as handle:
            json.dump({'references': {'RefIds': refs}}, handle)
        return folder

    def test_the_ids_come_from_the_keywords_of_the_file(self):
        module = max_effects()
        folder = self.extraction([(5, 'actionPoints'), (6, 'range'), (7, 'movementPoints'),
                                  (8, 'maxSummonedCreaturesBoost'), (9, 'vitality')])
        stats, keywords = module.load_cap_stats(folder)
        self.assertEqual({5: 'AP', 6: 'Range', 7: 'MP', 8: 'Summon'}, stats)
        self.assertEqual('vitality', keywords[9])
        caps = module.max_caps([(5, 7, 'Max.'), (7, 4, 'Max.'), (9, 1, 'Max.'), (5, 3, 'AP')], stats, keywords)
        self.assertEqual([('AP', 7), ('MP', 4)], caps)

    def test_a_folder_without_the_file_keeps_the_fixed_table(self):
        module = max_effects()
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder, True)
        stats, keywords = module.load_cap_stats(folder)
        self.assertEqual(module.FALLBACK_STAT_NAME_BY_ID, stats)
        self.assertEqual({}, keywords)
        self.assertEqual(module.FALLBACK_STAT_NAME_BY_ID, module.load_cap_stats(None)[0])

    def test_a_mapped_keyword_the_file_lacks_is_reported(self):
        module = max_effects()
        folder = self.extraction([(5, 'actionPoints')])
        with contextlib.redirect_stdout(io.StringIO()) as out:
            module.load_cap_stats(folder)
        for keyword in ('range', 'movementPoints', 'maxSummonedCreaturesBoost'):
            self.assertIn(keyword, out.getvalue())

    def test_a_max_row_naming_an_unmapped_characteristic_is_reported_once(self):
        module = max_effects()
        module._warned.discard(4242)
        with contextlib.redirect_stdout(io.StringIO()) as out:
            for _ in range(2):
                self.assertEqual([], module.max_caps([(4242, 9, 'Max.')], {1: 'AP'}, {4242: 'vitality'}))
        self.assertEqual(1, out.getvalue().count('4242'))
        self.assertIn('vitality', out.getvalue())
