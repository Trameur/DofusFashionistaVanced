# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A build records the item data version it was created and last solved with."""
import contextlib
import importlib.util
import io
import json
import os
import pickle
import re
import runpy
import shutil
import tempfile
from datetime import date, datetime, timezone as utc_zone
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.contrib.auth.models import User
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.utils import timezone

from chardata.char_blobs import read_char_blob
from chardata.data_versions import (current_data_version, patch_in_force, patch_key,
                                    patch_of, patch_started)
from chardata.models import Char, SolutionGeneration
from chardata.tests import _pulp_solver_available
from fashionistapulp.game_versions import version_keys
from fashionistapulp.structure import get_structure, set_current_game_version

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

OLD_STAMP = '3.6.2.1'
OLD_TIME = datetime(2026, 7, 1, 12, 0, tzinfo=utc_zone.utc)


def _base_input():
    return {
        'options': {'ap_exo': False, 'mp_exo': False},
        'origin': 'generated',
        'char_level': 200,
        'base_stats_by_attr': {'Vitality': 0, 'Wisdom': 0, 'Strength': 0,
                               'Intelligence': 0, 'Chance': 0, 'Agility': 0},
        'locked_equips': {},
    }


def _hats():
    structure = get_structure('dofus3')
    return [item for item in structure.get_unique_items_by_type_and_level('Hat', 200)
            if not item.removed and item.ankama_id][:2]


def _wearing(hat):
    from fashionistapulp.modelresult import ModelResultMinimal
    return pickle.dumps(ModelResultMinimal({'hat': hat.id}, _base_input(), {}))


def _stamped_char(owner, hat, game_version='dofus3'):
    char = Char.objects.create(
        name='Stamped', char_name='stamped', char_class='Iop',
        char_build='build', level=200, minimum_stats=b'', minimum_crits=b'',
        stats_weight=pickle.dumps({'vit': 1, 'str': 1}), options=b'',
        inclusions=b'', exclusions=b'', minimal_solution=_wearing(hat),
        owner=owner, link_shared=False, game_version=game_version)
    char.solved_version = OLD_STAMP
    char.solved_time = OLD_TIME
    char.save()
    return char


class ASolveStampsTheDataVersionTests(TestCase):

    def _solve(self, version):
        if not _pulp_solver_available():
            self.skipTest('no pulp solver available')
        from chardata.coaching_view import create_build
        set_current_game_version(version)
        self.addCleanup(set_current_game_version, 'dofus3')
        owner = User.objects.create_user('stamp' + version,
                                         'stamp-%s@test.local' % version,
                                         'pw-42-solid')
        request = RequestFactory().post('/')
        request.user = owner
        char = create_build(request, 'Iop', 200, {'str'}, version)
        self.client.force_login(owner)
        before = timezone.now()
        self.client.get('/fashion/%d/' % char.pk if version == 'dofus3'
                        else '/%s/fashion/%d/' % (version, char.pk))
        after = timezone.now()
        char.refresh_from_db()
        self.assertTrue(char.minimal_solution, 'the solve stored nothing')
        return char, before, after

    def _check(self, version):
        char, before, after = self._solve(version)
        label = settings.SITE_VERSIONS[version]
        self.assertEqual(label, char.created_version)
        self.assertEqual(label, char.solved_version)
        self.assertLessEqual(before, char.solved_time)
        self.assertLessEqual(char.solved_time, after)
        stored = read_char_blob(char.minimal_solution, None, 'minimal_solution')
        self.assertEqual(label, stored.data_version)
        generation = SolutionGeneration.objects.filter(char=char).first()
        self.assertIsNotNone(generation, 'the solve kept no generation')
        self.assertEqual(label, generation.data_version)

    def test_a_dofus3_solve_is_stamped(self):
        self._check('dofus3')

    def test_a_retro_solve_is_stamped(self):
        self._check('retro')


class OnlyASolveMovesTheStampTests(TestCase):

    def setUp(self):
        set_current_game_version('dofus3')
        self.hats = _hats()
        self.assertEqual(2, len(self.hats))
        self.owner = User.objects.create_user('keeper', 'keeper@test.local',
                                              'pw-42-solid')
        self.char = _stamped_char(self.owner, self.hats[0])
        self.created = self.char.created_version
        self.client.force_login(self.owner)

    def _assert_untouched(self):
        self.char.refresh_from_db()
        self.assertEqual(OLD_STAMP, self.char.solved_version)
        self.assertEqual(OLD_TIME, self.char.solved_time)
        self.assertEqual(self.created, self.char.created_version)

    def test_a_swapped_piece_keeps_the_stamp(self):
        answer = self.client.post('/exchange/%d/' % self.char.pk,
                                  {'itemName': str(self.hats[1].id),
                                   'slot': 'hat'})
        self.assertEqual('ok', answer.content.decode())
        self.char.refresh_from_db()
        stored = read_char_blob(self.char.minimal_solution, None,
                                'minimal_solution')
        self.assertEqual(self.hats[1].id, stored.item_per_slot.get('hat'))
        self._assert_untouched()

    def test_a_rename_keeps_the_stamp(self):
        answer = self.client.post('/saveproject/%d/' % self.char.pk,
                                  {'project': 'Renamed', 'charname': 'stamped',
                                   'level': '200', 'class': 'Iop'})
        self.assertEqual(200, answer.status_code)
        self.char.refresh_from_db()
        self.assertEqual('Renamed', self.char.name)
        self._assert_untouched()

    def test_publishing_and_hiding_keep_the_stamp(self):
        self.client.post('/getsharinglink/%d/' % self.char.pk)
        self.char.refresh_from_db()
        self.assertTrue(self.char.link_shared)
        self._assert_untouched()
        self.client.post('/hidesharinglink/%d/' % self.char.pk)
        self.char.refresh_from_db()
        self.assertFalse(self.char.link_shared)
        self._assert_untouched()


class ARestoreCarriesItsGenerationsVersionTests(TestCase):

    def setUp(self):
        set_current_game_version('dofus3')
        hats = _hats()
        self.owner = User.objects.create_user('restorer', 'restorer@test.local',
                                              'pw-42-solid')
        self.char = _stamped_char(self.owner, hats[0])
        self.stamped = SolutionGeneration.objects.create(
            char=self.char, game_version='dofus3',
            minimal_solution=_wearing(hats[1]), data_version='3.6.11.15')
        self.unstamped = SolutionGeneration.objects.create(
            char=self.char, game_version='dofus3',
            minimal_solution=_wearing(hats[1]))
        self.client.force_login(self.owner)

    def _restore(self, generation):
        answer = self.client.post('/restoregeneration/%d/%d/'
                                  % (self.char.pk, generation.pk))
        self.assertEqual(302, answer.status_code)
        self.char.refresh_from_db()

    def test_a_restored_generation_brings_its_version_and_time(self):
        self._restore(self.stamped)
        self.assertEqual('3.6.11.15', self.char.solved_version)
        self.assertEqual(self.stamped.created_time, self.char.solved_time)

    def test_a_generation_without_a_version_keeps_only_its_time(self):
        self._restore(self.unstamped)
        self.assertEqual('', self.char.solved_version)
        self.assertEqual(self.unstamped.created_time, self.char.solved_time)


class ACopyKeepsTheSolveAndGetsItsOwnCreationTests(TestCase):

    def _copy(self, game_version):
        set_current_game_version('dofus3')
        owner = User.objects.create_user('copier' + game_version,
                                         'copier-%s@test.local' % game_version,
                                         'pw-42-solid')
        source = _stamped_char(owner, _hats()[0], game_version)
        Char.objects.filter(pk=source.pk).update(created_version='3.5.17.26')
        self.client.force_login(owner)
        prefix = '' if game_version == 'dofus3' else '/' + game_version
        answer = self.client.post(prefix + '/duplicateproject/',
                                  {'project_id': json.dumps(source.pk)})
        self.assertEqual('ok', answer.content.decode())
        copy = Char.objects.latest('pk')
        self.assertNotEqual(source.pk, copy.pk)
        source.refresh_from_db()
        self.assertEqual('3.5.17.26', source.created_version)
        return copy

    def test_a_copy_keeps_the_solve_stamp(self):
        copy = self._copy('dofus3')
        self.assertEqual(OLD_STAMP, copy.solved_version)
        self.assertEqual(OLD_TIME, copy.solved_time)
        self.assertEqual(settings.SITE_VERSIONS['dofus3'], copy.created_version)

    def test_a_copy_is_created_with_its_own_versions_data(self):
        copy = self._copy('retro')
        self.assertEqual(settings.SITE_VERSIONS['retro'], copy.created_version)


class AnImportIsNotASolveTests(TestCase):

    def test_an_imported_build_has_a_creation_and_no_solve(self):
        set_current_game_version('dofus3')
        structure = get_structure('dofus3')
        names = []
        for type_name in ('Hat', 'Cloak'):
            item = next(i for i in structure.types[200][type_name]
                        if not i.removed and i.ankama_id)
            names.append(structure.get_item_name_in_language(item, 'en'))
        before = Char.objects.order_by('-id').first()
        self.client.post('/import/text/', {
            'text': '\n'.join(names), 'confirm': '1',
            'char_class': 'Cra', 'level': '200'})
        char = Char.objects.order_by('-id').first()
        self.assertIsNotNone(char)
        self.assertNotEqual(before, char, 'the import made no build')
        self.assertTrue(char.minimal_solution)
        self.assertEqual(settings.SITE_VERSIONS['dofus3'], char.created_version)
        self.assertEqual('', char.solved_version)
        self.assertIsNone(char.solved_time)
        self.assertIsNotNone(char.stuff_time)
        self.assertFalse(SolutionGeneration.objects.filter(char=char).exists())


class PatchNumbersTests(SimpleTestCase):

    def test_the_patch_is_the_first_two_parts(self):
        self.assertEqual('3.6', patch_of('3.6.11.15'))
        self.assertEqual('2.73', patch_of('2.73.3.14'))
        self.assertEqual('1.74', patch_of('1.74'))
        self.assertIsNone(patch_of(''))
        self.assertIsNone(patch_of(None))

    def test_patches_compare_as_numbers(self):
        self.assertGreater(patch_key('3.10'), patch_key('3.9'))
        self.assertEqual((1, 74), patch_key('1.74'))
        self.assertLess(patch_key(patch_of('3.6.11.15')), patch_key('3.7'))

    def test_the_current_version_is_the_footer_label(self):
        for key in version_keys():
            with self.subTest(version=key):
                self.assertEqual(settings.SITE_VERSIONS[key],
                                 current_data_version(key))
        self.assertEqual('', current_data_version('wakfu'))

    def test_every_served_version_knows_when_its_patch_started(self):
        today = datetime.now(utc_zone.utc).date()
        for key in version_keys():
            with self.subTest(version=key):
                started = patch_started(key)
                self.assertIsNotNone(started)
                self.assertLessEqual(started, today)

    def test_each_timeline_ends_on_the_current_label(self):
        import fashionista_version
        for key in version_keys():
            with self.subTest(version=key):
                self.assertEqual(patch_of(current_data_version(key)),
                                 fashionista_version.PATCH_TIMELINE[key][-1][1])

    def test_each_timeline_is_sorted_by_day_and_by_patch(self):
        import fashionista_version
        for key, entries in fashionista_version.PATCH_TIMELINE.items():
            with self.subTest(version=key):
                days = [date.fromisoformat(day) for day, _patch in entries]
                self.assertEqual(sorted(set(days)), days)
                keys = [patch_key(patch) for _day, patch in entries]
                self.assertEqual(sorted(set(keys)), keys)

    def test_the_dofus3_timeline_reaches_back_to_the_dofus_2_updates(self):
        self.assertEqual('2.18', patch_in_force(
            'dofus3', datetime(2014, 3, 1, tzinfo=utc_zone.utc)))
        self.assertEqual('2.68', patch_in_force(
            'dofus3', datetime(2023, 9, 1, tzinfo=utc_zone.utc)))
        self.assertEqual('2.69', patch_in_force(
            'dofus3', datetime(2023, 9, 28, tzinfo=utc_zone.utc)))
        self.assertIsNone(patch_in_force(
            'dofus3', datetime(2014, 1, 1, tzinfo=utc_zone.utc)))
        self.assertIsNone(patch_in_force(
            'wakfu', datetime(2026, 1, 1, tzinfo=utc_zone.utc)))


class ThePipelineMovesThePatchDayTests(SimpleTestCase):

    SCRIPTS = (
        ('update_data.py', 'set_version', 'FASHIONISTA_VERSION', 'dofus3'),
        ('update_data_beta.py', 'set_beta_version', 'FASHIONISTA_BETA_VERSION',
         'beta'),
        ('update_data_dofus2.py', 'set_dofus2_version',
         'FASHIONISTA_DOFUS2_VERSION', 'dofus2'),
    )

    def _run(self, script, setter, new_version):
        spec = importlib.util.spec_from_file_location(
            script[:-3] + '_under_test', os.path.join(REPO_ROOT, script))
        module = importlib.util.module_from_spec(spec)
        with contextlib.redirect_stdout(io.StringIO()):
            spec.loader.exec_module(module)
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder, True)
        shutil.copy(os.path.join(REPO_ROOT, 'fashionista_version.py'), folder)
        with mock.patch.object(module, 'ROOT', Path(folder)), \
                contextlib.redirect_stdout(io.StringIO()):
            getattr(module, setter)(new_version)
        return runpy.run_path(os.path.join(folder, 'fashionista_version.py'))

    def test_a_build_of_the_same_patch_keeps_the_day(self):
        import fashionista_version as ours
        for script, setter, constant, key in self.SCRIPTS:
            with self.subTest(script=script):
                parts = getattr(ours, constant).split('.')
                parts[-1] = str(int(parts[-1]) + 1)
                written = self._run(script, setter, '.'.join(parts))
                self.assertEqual('.'.join(parts), written[constant])
                self.assertEqual(ours.PATCH_TIMELINE, written['PATCH_TIMELINE'])

    def test_a_new_patch_is_appended_to_the_timeline_today(self):
        import fashionista_version as ours
        for script, setter, constant, key in self.SCRIPTS:
            with self.subTest(script=script):
                parts = getattr(ours, constant).split('.')
                parts[1] = str(int(parts[1]) + 1)
                before = datetime.now(utc_zone.utc).date().isoformat()
                written = self._run(script, setter, '.'.join(parts))
                after = datetime.now(utc_zone.utc).date().isoformat()
                self.assertEqual('.'.join(parts), written[constant])
                timeline = written['PATCH_TIMELINE']
                self.assertEqual(ours.PATCH_TIMELINE[key], timeline[key][:-1])
                day, patch = timeline[key][-1]
                self.assertEqual('.'.join(parts[:2]), patch)
                self.assertIn(day, {before, after})
                others = dict(timeline)
                del others[key]
                expected = dict(ours.PATCH_TIMELINE)
                del expected[key]
                self.assertEqual(expected, others)


class TheFooterNamesTheCurrentLabelsTests(TestCase):

    FOOTER = re.compile(r'Items up to [^<]*? update ([0-9][0-9.]*)')

    def _footer_version(self, path):
        page = self.client.get(path, HTTP_ACCEPT_LANGUAGE='en')
        self.assertEqual(200, page.status_code, path)
        found = self.FOOTER.search(page.content.decode('utf-8'))
        self.assertIsNotNone(found, 'no data version in the footer of %s' % path)
        return found.group(1)

    def test_retro_shows_1_49_or_later(self):
        shown = self._footer_version('/retro/')
        self.assertEqual(settings.SITE_VERSIONS['retro'], shown)
        self.assertGreaterEqual(patch_key(patch_of(shown)), (1, 49))

    def test_touch_shows_1_74_or_later(self):
        shown = self._footer_version('/touch/')
        self.assertEqual(settings.SITE_VERSIONS['touch'], shown)
        self.assertGreaterEqual(patch_key(patch_of(shown)), (1, 74))
