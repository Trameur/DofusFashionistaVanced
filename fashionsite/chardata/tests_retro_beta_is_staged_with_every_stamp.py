# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Retro Beta is registered as a staged member of the Retro family, with its stamps, and the main Retro run is unchanged."""
import contextlib
import io
from pathlib import Path
import sys
from unittest import mock

from django.conf import settings
from django.test import SimpleTestCase

import fashionista_version
import update_all as updater
from fashionistapulp.game_versions import (GAME_VERSIONS, VERSION_ORDER, dofus_versions, family_members,
                                           is_beta, main_of, reader_dofus_versions, switcher_games,
                                           version_keys)

from chardata.tests import itemscraper_module

ROOT = Path(__file__).resolve().parents[2]
ITEMSCRAPER = ROOT / 'itemscraper'
if str(ITEMSCRAPER) not in sys.path:
    sys.path.insert(0, str(ITEMSCRAPER))
import retro_release  # noqa: E402
import store_retro_monster_grades as grades  # noqa: E402
import update_data_retro as pipeline  # noqa: E402

OLD_TOKENS = ('dofus3', 'beta', 'dofus2', 'touch', 'retro', 'wakfu', 'touchbeta')
OWN_FIELDS = {'key', 'label', 'db_file', 'dump_file', 'prefix', 'seo_word', 'experimental', 'channel'}


class RetroBetaIsAStagedRetroVersionTests(SimpleTestCase):

    def test_it_is_the_beta_channel_of_retro(self):
        retrobeta = GAME_VERSIONS['retrobeta']
        self.assertEqual('retro', main_of('retrobeta'))
        self.assertTrue(is_beta('retrobeta'))
        self.assertTrue(retrobeta.experimental)
        self.assertTrue(retrobeta.dofus)
        self.assertEqual(('Retro Beta', 'Dofus Retro Beta'), (retrobeta.label, retrobeta.game_name))
        self.assertEqual(('items_retrobeta.db', 'item_db_dumped_retrobeta.dump'),
                         (retrobeta.db_file, retrobeta.dump_file))
        self.assertEqual('retrobeta', retrobeta.prefix)

    def test_it_carries_every_retro_rule(self):
        retro, retrobeta = GAME_VERSIONS['retro'], GAME_VERSIONS['retrobeta']
        for rule in sorted(set(vars(retro)) - OWN_FIELDS):
            with self.subTest(rule=rule):
                self.assertEqual(getattr(retro, rule), getattr(retrobeta, rule))

    def test_it_sits_after_retro_and_reaches_no_reader(self):
        self.assertEqual(('dofus3', 'beta', 'dofus2', 'touch', 'touchbeta', 'retro', 'retrobeta', 'wakfu'),
                         VERSION_ORDER)
        self.assertIn('retrobeta', dofus_versions())
        self.assertNotIn('retrobeta', version_keys())
        self.assertNotIn('retrobeta', reader_dofus_versions())
        self.assertEqual(['retro'], family_members('retro'))
        self.assertIn(('retro', ['retro']), switcher_games())

    def test_the_release_helpers_name_the_registry_files(self):
        self.assertEqual('beta', retro_release.release_of('retrobeta'))
        self.assertEqual('main', retro_release.release_of('retro'))
        self.assertIsNone(retro_release.release_of('touchbeta'))
        self.assertEqual(GAME_VERSIONS['retrobeta'].db_file, retro_release.db_path('beta').name)
        self.assertEqual(GAME_VERSIONS['retro'].dump_file, retro_release.dump_path().name)


class RetroBetaHasItsStampsTests(SimpleTestCase):

    def test_the_footer_stamp_is_its_own_build(self):
        self.assertEqual(fashionista_version.FASHIONISTA_RETROBETA_VERSION, settings.SITE_VERSIONS['retrobeta'])
        self.assertNotEqual(settings.SITE_VERSIONS['retro'], settings.SITE_VERSIONS['retrobeta'])

    def test_its_timeline_ends_on_its_stamp(self):
        patch = '.'.join(fashionista_version.FASHIONISTA_RETROBETA_VERSION.split('.')[:2])
        self.assertEqual(patch, fashionista_version.PATCH_TIMELINE['retrobeta'][-1][1])

    def test_the_rebuild_tools_know_its_files(self):
        self.assertEqual('fashionistapulp/fashionistapulp/items_retrobeta.db',
                         itemscraper_module('check_rebuild').COMMITTED['retrobeta'])
        self.assertTrue(itemscraper_module('store_weapon_uses_per_turn').WORK_DIR['retrobeta']
                        .endswith('retrobeta'))


class TheUpdaterKeepsEveryOldChoiceTests(SimpleTestCase):

    def _rows(self):
        return [{'key': key, 'error': None, 'changed': True} for key in updater.VERSIONS]

    def test_every_old_number_keeps_its_version(self):
        rows = self._rows()
        for number, key in enumerate(OLD_TOKENS, 1):
            with self.subTest(number=number):
                self.assertEqual([key], updater.selection(str(number), rows))
                self.assertEqual([key], updater.restore_keys(str(number)))
        self.assertEqual(['retrobeta'], updater.selection('8', rows))
        self.assertEqual(OLD_TOKENS + ('retrobeta',), tuple(updater.VERSIONS))

    def test_its_tables_name_the_retro_pipeline(self):
        self.assertEqual(('Dofus Retro Beta', 'update_data_retro', 'FASHIONISTA_RETROBETA_VERSION'),
                         (updater.NAMES['retrobeta'], updater.PIPELINES['retrobeta'],
                          updater.METADATA['retrobeta']))

    def test_all_and_changed_never_pick_a_staged_beta(self):
        rows = self._rows()
        self.assertEqual(['dofus3', 'beta', 'dofus2', 'touch', 'retro'], updater.selection('all', rows))
        self.assertEqual(['dofus3', 'beta', 'dofus2', 'touch', 'retro'], updater.selection('changed', rows))

    def test_the_search_reports_the_staged_beta_without_reading_any_source(self):
        with mock.patch.object(updater, 'fetch_json', side_effect=AssertionError('no source read')), \
                mock.patch.object(updater, 'touch_build_version', side_effect=AssertionError('no source read')):
            with self.assertRaisesRegex(ValueError, '^staged'):
                updater.probe('retrobeta')


class TheMainRetroRunIsUnchangedTests(SimpleTestCase):

    def steps(self, *argv):
        steps = {}

        def run_step(label, cmd, cwd=None):
            steps[label] = [str(part) for part in cmd[1:]]
            return True, []

        with mock.patch.object(pipeline, 'run_step', side_effect=run_step), \
                mock.patch.object(pipeline, 'export_lang_root', return_value='ROOT'), \
                mock.patch.object(sys, 'argv', ['update_data_retro.py'] + list(argv)), \
                contextlib.redirect_stdout(io.StringIO()):
            pipeline.main()
        return steps

    def test_the_steps_the_beta_now_runs_keep_their_main_commands(self):
        steps = self.steps()
        self.assertEqual({
            'items/load-db': ['load_item_db.py', '--game-version', 'retro'],
            'recipes/store': ['store_retro_recipes.py'],
            'pets/store': ['store_retro_pet_bonuses.py'],
            'drops/store': ['store_drops.py', '--drops', 'transformed_drops_retro.json', '--game-version', 'retro'],
            'monsters/grades': ['store_retro_monster_grades.py'],
            'monsters/subareas': ['store_retro_monster_subareas.py'],
            'craftjobs/store': ['store_craft_jobs.py', '--jobs', 'transformed_craft_jobs_retro.json',
                                '--game-version', 'retro'],
            'descriptions/store': ['store_retro_descriptions.py'],
            'resource-icons': ['download_resource_icons.py', '--game-version', 'retro'],
            'spells/tooltips': ['-m', 'itemscraper.store_spell_tooltips', '--game-version', 'retro'],
            'items/corrections': ['store_item_corrections.py', '--game-version', 'retro'],
            'verify/rebuild': ['check_rebuild.py', '--only', 'retro'],
            'drops/transform': ['get_monsters_retro.py', '--output', 'transformed_drops_retro.json'],
        }, {label: steps[label] for label in (
            'items/load-db', 'recipes/store', 'pets/store', 'drops/store', 'monsters/grades', 'monsters/subareas',
            'craftjobs/store', 'descriptions/store', 'resource-icons', 'spells/tooltips', 'items/corrections',
            'verify/rebuild', 'drops/transform')})

    def test_the_beta_hands_on_the_main_drops_it_is_given(self):
        steps = self.steps('--release', 'beta', '--main-drops', 'main_drops.json')
        self.assertEqual(['--main-drops', 'main_drops.json'], steps['drops/transform'][-2:])
        self.assertNotIn('--main-drops', self.steps('--release', 'beta')['drops/transform'])


class TheBetaGradesStartFromMainTests(SimpleTestCase):

    def test_the_lang_of_the_release_is_put_over_the_rows_of_main(self):
        main_rows = [(1, 1, 10, 100, 6, 3, 5, 5, 0, 0, 0, 0, 0),
                     (1, 2, 12, 120, 6, 3, 5, 5, 0, 0, 0, 0, 0),
                     (2, 1, 30, 300, 7, None, 9, 9, 1, 1, 1, 1, 1),
                     (3, 1, 50, 500, 8, 4, 0, 0, 0, 0, 0, 0, 0)]
        lang = {1: {2: {'level': 12, 'lp': None, 'ap': None, 'mp': None, 'ap_dodge': 5, 'mp_dodge': 5,
                        'earth': 10, 'air': 0, 'fire': 0, 'water': 0, 'neutral': 0}},
                2: {1: {'level': 30, 'lp': None, 'ap': None, 'mp': -1, 'ap_dodge': 9, 'mp_dodge': 9,
                        'earth': 1, 'air': 1, 'fire': 1, 'water': 1, 'neutral': 1}}}
        rows, counts = grades.release_grade_rows(main_rows, lang, {1, 2, 4})
        self.assertEqual([(1, 1, 10, 100, 6, 3, 5, 5, 0, 0, 0, 0, 0),
                          (1, 2, 12, 120, 6, 3, 5, 5, 10, 0, 0, 0, 0),
                          (2, 1, 30, 300, 7, None, 9, 9, 1, 1, 1, 1, 1)], rows)
        self.assertEqual({'reused': 3, 'lang_changed': 1, 'no_main_row': 1}, counts)


class TheBetaTooltipsReadTheBetaLangTests(SimpleTestCase):

    def test_each_retro_key_reads_its_own_raw_folder(self):
        tooltips = itemscraper_module('store_spell_tooltips')
        with mock.patch.object(tooltips, '_retro_tooltips', side_effect=lambda raw_dir=None: raw_dir) as read:
            self.assertEqual(retro_release.raw_dir('beta'), tooltips.collect('retrobeta'))
            self.assertEqual(retro_release.raw_dir(), tooltips.collect('retro'))
        self.assertEqual(2, read.call_count)
