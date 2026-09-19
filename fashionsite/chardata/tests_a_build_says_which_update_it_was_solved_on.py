# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A build says which update it was created and solved on, estimated from its dates when not recorded."""
import pickle
import re
from datetime import date, datetime, timedelta, timezone as utc_zone
from types import SimpleNamespace
from unittest import mock

from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings

from chardata.data_versions import build_patch_info, patch_in_force
from chardata.encoded_char_id import encode_char_id
from chardata.models import Char, SolutionGeneration
from fashionistapulp.modelresult import ModelResultMinimal
from fashionistapulp.structure import get_structure, set_current_game_version

CURRENT = '3.7.0.4'
STARTED = date(2026, 9, 17)
BEFORE_START = datetime(2026, 9, 16, 23, 59, tzinfo=utc_zone.utc)
AT_START = datetime(2026, 9, 17, 0, 0, tzinfo=utc_zone.utc)
AFTER_START = datetime(2026, 9, 18, 10, 0, tzinfo=utc_zone.utc)
ON_THE_OLD_PATCH = datetime(2026, 8, 1, 12, 0, tzinfo=utc_zone.utc)
UNDER_THREE_FOUR = datetime(2026, 1, 15, 12, 0, tzinfo=utc_zone.utc)
IN_2018 = datetime(2018, 7, 1, 12, 0, tzinfo=utc_zone.utc)
IN_2013 = datetime(2013, 6, 1, 12, 0, tzinfo=utc_zone.utc)
VERSIONS = dict(settings.SITE_VERSIONS, dofus3=CURRENT)
ON_THREE_SIX = dict(settings.SITE_VERSIONS, dofus3='3.6.11.15')

BROWSER = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
           '(KHTML, like Gecko) Chrome/126.0 Safari/537.36')

STALE_TITLE_EN = 'Solved before update 3.7: the best set may have changed since.'
STALE_TITLE_FR = ('Calculé avant la mise à jour 3.7 : le meilleur équipement '
                  'a pu changer depuis.')
ESTIMATE_TITLE_EN = "Estimated from the build's dates: the solve was not recorded."
ESTIMATE_TITLE_FR = ("Estimation d'après les dates du build : le calcul n'a pas "
                     "été enregistré.")


class _OnPatchThreeSeven(object):

    def setUp(self):
        super().setUp()
        patcher = mock.patch('chardata.data_versions.patch_started',
                             return_value=STARTED)
        patcher.start()
        self.addCleanup(patcher.stop)


def _record(**fields):
    base = dict(game_version='dofus3', created_version='', solved_version='',
                created_time=None, solved_time=None, modified_time=AFTER_START,
                minimal_solution=b'stored')
    base.update(fields)
    return SimpleNamespace(**base)


def _estimates(info):
    return (info['created_patch'], info['created_estimated'],
            info['solved_patch'], info['solved_estimated'], info['state'])


@override_settings(SITE_VERSIONS=VERSIONS)
class TheHelperRecordsOrEstimatesTests(_OnPatchThreeSeven, SimpleTestCase):

    def test_a_solve_on_the_current_patch_is_current(self):
        info = build_patch_info(_record(created_version='3.6.11.15',
                                        solved_version='3.7.0.1'))
        self.assertEqual({'created_patch': '3.6', 'created_estimated': False,
                          'solved_patch': '3.7', 'solved_estimated': False,
                          'current_patch': '3.7', 'state': 'current',
                          'stale': False}, info)

    def test_a_solve_on_an_earlier_patch_is_older(self):
        info = build_patch_info(_record(solved_version='3.6.11.15',
                                        solved_time=AFTER_START))
        self.assertEqual(('3.6', 'older', True),
                         (info['solved_patch'], info['state'], info['stale']))

    def test_patches_compare_as_numbers(self):
        with self.settings(SITE_VERSIONS=dict(VERSIONS, dofus3='3.10.0.1')):
            info = build_patch_info(_record(solved_version='3.9.4.2'))
        self.assertEqual(('3.9', '3.10', 'older'),
                         (info['solved_patch'], info['current_patch'],
                          info['state']))

    def test_an_unstamped_solve_is_estimated_from_its_time(self):
        info = build_patch_info(_record(solved_time=BEFORE_START,
                                        modified_time=AFTER_START))
        self.assertEqual((None, False, '3.6', True, 'older'), _estimates(info))
        self.assertTrue(info['stale'])

    def test_an_unstamped_solve_is_estimated_from_the_last_change(self):
        info = build_patch_info(_record(modified_time=UNDER_THREE_FOUR))
        self.assertEqual((None, False, '3.4', True, 'older'), _estimates(info))

    def test_an_estimate_on_the_current_patch_is_current(self):
        with self.settings(SITE_VERSIONS=ON_THREE_SIX):
            info = build_patch_info(_record(created_time=UNDER_THREE_FOUR,
                                            modified_time=ON_THE_OLD_PATCH))
        self.assertEqual(('3.4', True, '3.6', True, 'current'), _estimates(info))
        self.assertFalse(info['stale'])

    def test_a_recorded_creation_is_not_estimated(self):
        info = build_patch_info(_record(created_version='3.5.17.26',
                                        created_time=UNDER_THREE_FOUR))
        self.assertEqual(('3.5', False), (info['created_patch'],
                                          info['created_estimated']))

    def test_a_build_from_2018_gets_the_dofus_2_patch_of_that_day(self):
        info = build_patch_info(_record(created_time=IN_2018,
                                        modified_time=IN_2018))
        self.assertEqual(('2.47', True, '2.47', True, 'older'), _estimates(info))

    def test_the_first_day_of_a_patch_counts_for_it(self):
        self.assertEqual('3.6', patch_in_force(
            'dofus3', datetime(2026, 6, 23, 0, 0, tzinfo=utc_zone.utc)))
        self.assertEqual('3.5', patch_in_force(
            'dofus3', datetime(2026, 6, 22, 23, 59, tzinfo=utc_zone.utc)))
        self.assertEqual('3.5', patch_in_force(
            'dofus3', datetime(2026, 6, 23, 1, 30, tzinfo=utc_zone(timedelta(hours=2)))))

    def test_a_time_before_the_timeline_is_before_the_patch_day(self):
        info = build_patch_info(_record(created_time=IN_2013,
                                        modified_time=IN_2013))
        self.assertEqual((None, False, None, False, 'before'), _estimates(info))
        self.assertTrue(info['stale'])

    def test_a_build_with_no_time_at_all_is_unknown(self):
        info = build_patch_info(_record(modified_time=None))
        self.assertEqual({'created_patch': None, 'created_estimated': False,
                          'solved_patch': None, 'solved_estimated': False,
                          'current_patch': '3.7', 'state': None,
                          'stale': False}, info)

    def test_a_build_never_solved_claims_only_its_creation(self):
        info = build_patch_info(_record(minimal_solution=b'',
                                        created_time=UNDER_THREE_FOUR,
                                        solved_version='3.6.11.15',
                                        modified_time=BEFORE_START))
        self.assertEqual(('3.4', True, None, False, None), _estimates(info))
        self.assertFalse(info['stale'])

    def test_a_set_not_from_the_solver_claims_no_solve(self):
        info = build_patch_info(_record(created_version='3.6.11.15',
                                        solved_version='3.6.11.15',
                                        modified_time=BEFORE_START),
                                from_solver=False)
        self.assertEqual(('3.6', None, None),
                         (info['created_patch'], info['solved_patch'],
                          info['state']))

    def test_a_caller_can_vouch_for_the_stored_set(self):
        info = build_patch_info(_record(minimal_solution=b'',
                                        modified_time=ON_THE_OLD_PATCH),
                                has_solution=True)
        self.assertEqual(('3.6', True, 'older'),
                         (info['solved_patch'], info['solved_estimated'],
                          info['state']))

    def test_a_saved_solution_uses_its_own_version_or_its_own_time(self):
        char = _record(solved_version='3.7.0.1')
        older = build_patch_info(char, SimpleNamespace(
            data_version='3.6.2.1', created_time=AFTER_START))
        self.assertEqual(('3.6', False, 'older'),
                         (older['solved_patch'], older['solved_estimated'],
                          older['state']))
        estimated = build_patch_info(char, SimpleNamespace(
            data_version='', created_time=UNDER_THREE_FOUR))
        self.assertEqual(('3.4', True, 'older'),
                         (estimated['solved_patch'],
                          estimated['solved_estimated'], estimated['state']))

    def test_a_version_without_a_timeline_gives_only_what_is_recorded(self):
        info = build_patch_info(_record(game_version='wakfu',
                                        created_time=UNDER_THREE_FOUR))
        self.assertEqual({'created_patch': None, 'created_estimated': False,
                          'solved_patch': None, 'solved_estimated': False,
                          'current_patch': None, 'state': None,
                          'stale': False}, info)


def _hat():
    structure = get_structure('dofus3')
    return next(item for item in
                structure.get_unique_items_by_type_and_level('Hat', 200)
                if not item.removed and item.ankama_id)


def _build(owner, name, origin='generated', **stamps):
    solution = ModelResultMinimal({'hat': _hat().id}, {
        'options': {'ap_exo': False, 'mp_exo': False},
        'origin': origin,
        'char_level': 200,
        'base_stats_by_attr': {'Vitality': 0, 'Wisdom': 0, 'Strength': 0,
                               'Intelligence': 0, 'Chance': 0, 'Agility': 0},
        'locked_equips': {},
    }, {})
    char = Char.objects.create(
        name=name, char_name=name.lower(), char_class='Iop',
        char_build='build', level=200, minimum_stats=b'', minimum_crits=b'',
        stats_weight=pickle.dumps({'vit': 1, 'str': 1}), options=b'',
        inclusions=b'', exclusions=b'', minimal_solution=pickle.dumps(solution),
        owner=owner, link_shared=True, game_version='dofus3')
    fields = dict(created_version='', solved_version='', solved_time=None,
                  created_time=ON_THE_OLD_PATCH, modified_time=AFTER_START)
    fields.update(stamps)
    Char.objects.filter(pk=char.pk).update(**fields)
    char.refresh_from_db()
    return char


def _patch_block(page):
    found = re.search(r'<div class="char-banner-patch">(.*?)</div>', page, re.S)
    return found.group(1) if found else None


def _patch_line(page):
    block = _patch_block(page)
    if block is None:
        return None
    return ' '.join(re.sub(r'<[^>]+>', ' ', block).split())


def _title_of(tag):
    title = re.search(r'title="([^"]*)"', tag)
    return title.group(1) if title else None


def _stale_title(page):
    tag = re.search(r'<span[^>]*char-banner-patch-stale[^>]*>', page)
    return _title_of(tag.group(0)) if tag else None


def _estimate_titles(page):
    return [_title_of(tag) for tag in
            re.findall(r'<span[^>]*char-banner-patch-estimated[^>]*>', page)]


class _Pages(_OnPatchThreeSeven):

    def setUp(self):
        super().setUp()
        set_current_game_version('dofus3')
        cache.clear()
        self.addCleanup(cache.clear)
        self.owner = User.objects.create_user('patchowner', 'patch@test.local',
                                              'pw-42-solid')


@override_settings(SITE_VERSIONS=VERSIONS)
class TheBuildPageSaysWhichUpdateTests(_Pages, TestCase):

    def _visit(self, char, language='en'):
        page = self.client.get(
            '/s/%s/%s/' % (char.char_name, encode_char_id(char.pk)),
            HTTP_ACCEPT_LANGUAGE=language, HTTP_USER_AGENT=BROWSER)
        self.assertEqual(200, page.status_code)
        return page.content.decode('utf-8')

    def _own(self, path, language='en'):
        self.client.force_login(self.owner)
        page = self.client.get(path, HTTP_ACCEPT_LANGUAGE=language)
        self.assertEqual(200, page.status_code)
        return page.content.decode('utf-8')

    def _older(self):
        return _build(self.owner, 'OlderSolve', created_version='3.6.11.15',
                      solved_version='3.6.11.15', solved_time=ON_THE_OLD_PATCH)

    def test_an_older_solve_shows_both_updates_and_the_mark(self):
        page = self._visit(self._older())
        self.assertEqual('Created on 3.6 · Solved on 3.6 · Solved before 3.7',
                         _patch_line(page))
        self.assertEqual(STALE_TITLE_EN, _stale_title(page))
        self.assertEqual([], _estimate_titles(page))

    def test_the_line_and_the_mark_read_in_french(self):
        page = self._visit(self._older(), 'fr')
        self.assertEqual('Créé en 3.6 · Calculé en 3.6 · Calculé avant la 3.7',
                         _patch_line(page))
        self.assertEqual(STALE_TITLE_FR, _stale_title(page))

    def test_a_current_solve_carries_no_mark(self):
        page = self._visit(_build(self.owner, 'CurrentSolve',
                                  created_version='3.6.11.15',
                                  solved_version='3.7.0.1',
                                  solved_time=AFTER_START))
        self.assertEqual('Created on 3.6 · Solved on 3.7', _patch_line(page))
        self.assertNotIn('Solved before', page)

    def test_an_unstamped_build_is_estimated_from_its_dates(self):
        page = self._visit(_build(self.owner, 'Estimated',
                                  created_time=UNDER_THREE_FOUR,
                                  modified_time=ON_THE_OLD_PATCH))
        self.assertEqual('Created around 3.4 · Solved around 3.6 · Solved before 3.7',
                         _patch_line(page))
        self.assertEqual([ESTIMATE_TITLE_EN] * 2, _estimate_titles(page))
        self.assertEqual(STALE_TITLE_EN, _stale_title(page))

    def test_an_estimate_on_the_current_update_carries_no_mark(self):
        char = _build(self.owner, 'EstimatedCurrent',
                      created_time=UNDER_THREE_FOUR,
                      modified_time=ON_THE_OLD_PATCH)
        with self.settings(SITE_VERSIONS=ON_THREE_SIX):
            page = self._visit(char)
        self.assertEqual('Created around 3.4 · Solved around 3.6',
                         _patch_line(page))
        self.assertNotIn('Solved before', page)

    def test_the_estimate_reads_in_french(self):
        page = self._visit(_build(self.owner, 'EstimeFr',
                                  created_time=UNDER_THREE_FOUR,
                                  modified_time=ON_THE_OLD_PATCH), 'fr')
        self.assertEqual('Créé vers la 3.4 · Calculé vers la 3.6 · Calculé avant la 3.7',
                         _patch_line(page))
        self.assertEqual([ESTIMATE_TITLE_FR] * 2, _estimate_titles(page))

    def test_a_build_from_2018_names_the_dofus_2_patch_of_that_day(self):
        page = self._visit(_build(self.owner, 'Old2018', created_time=IN_2018,
                                  modified_time=IN_2018))
        self.assertEqual('Created around 2.47 · Solved around 2.47 · Solved before 3.7',
                         _patch_line(page))

    def test_a_build_older_than_the_timeline_is_marked_without_a_number(self):
        page = self._visit(_build(self.owner, 'BeforeAll', created_time=IN_2013,
                                  modified_time=IN_2013))
        self.assertEqual('Solved before 3.7', _patch_line(page))
        self.assertEqual(STALE_TITLE_EN, _stale_title(page))

    def test_a_never_solved_build_shows_only_its_creation(self):
        page = self._visit(_build(self.owner, 'NeverSolved', origin='pasted_text',
                                  created_time=UNDER_THREE_FOUR,
                                  modified_time=ON_THE_OLD_PATCH))
        self.assertEqual('Created around 3.4', _patch_line(page))
        self.assertNotIn('Solved', _patch_block(page))

    def test_an_imported_set_claims_no_solve(self):
        page = self._visit(_build(self.owner, 'ImportedSet', origin='pasted_text',
                                  created_version='3.6.11.15',
                                  solved_version='3.6.11.15',
                                  modified_time=BEFORE_START))
        self.assertEqual('Created on 3.6', _patch_line(page))

    def test_the_owner_gets_the_solve_action_and_a_visitor_does_not(self):
        char = self._older()
        visitor = _patch_block(self._visit(char))
        self.assertIsNotNone(visitor)
        self.assertNotIn('/fashion/', visitor)
        owner = _patch_block(self._own('/solution/%d/' % char.pk))
        self.assertIn('href="/fashion/%d/"' % char.pk, owner)
        self.assertIn('Tailor a New Set', owner)

    def test_a_saved_solution_shows_its_own_update_and_no_action(self):
        char = _build(self.owner, 'SavedSolve', solved_version='3.7.0.1',
                      solved_time=AFTER_START)
        generation = SolutionGeneration.objects.create(
            char=char, game_version='dofus3',
            minimal_solution=char.minimal_solution, data_version='3.6.2.1')
        page = self._own('/solutiongeneration/%d/%d/' % (char.pk, generation.pk))
        self.assertEqual('Created around 3.6 · Solved on 3.6 · Solved before 3.7',
                         _patch_line(page))
        self.assertNotIn('/fashion/', _patch_block(page))


def _card(page, name):
    for card in page.split('<div class="build-card">')[1:]:
        if name in card:
            return card
    raise AssertionError('no card named %s on the gallery' % name)


@override_settings(SITE_VERSIONS=VERSIONS)
class TheGalleryCardSaysWhichUpdateTests(_Pages, TestCase):

    def _gallery_card(self, name):
        page = self.client.get('/sharedbuilds/', HTTP_ACCEPT_LANGUAGE='en')
        self.assertEqual(200, page.status_code)
        return _card(page.content.decode('utf-8'), name)

    def test_a_current_solve_names_its_update(self):
        _build(self.owner, 'CardCurrent', solved_version='3.7.0.1',
               solved_time=AFTER_START)
        card = self._gallery_card('cardcurrent')
        self.assertIn('Solved on 3.7', card)
        self.assertNotIn('Solved before', card)
        self.assertNotIn('build-patch-badge-estimated', card)

    def test_an_older_solve_says_before_the_current_update(self):
        _build(self.owner, 'CardOlder', solved_version='3.6.11.15',
               solved_time=ON_THE_OLD_PATCH)
        card = self._gallery_card('cardolder')
        self.assertIn('Solved before 3.7', card)
        self.assertIn(STALE_TITLE_EN, card)
        self.assertNotIn('Solved on', card)

    def test_an_unstamped_build_older_than_the_update_says_before(self):
        _build(self.owner, 'CardBefore', modified_time=BEFORE_START)
        card = self._gallery_card('cardbefore')
        self.assertIn('Solved before 3.7', card)
        self.assertNotIn('Solved around', card)

    def test_an_unstamped_build_on_the_current_update_says_around(self):
        _build(self.owner, 'CardAround', modified_time=ON_THE_OLD_PATCH)
        with self.settings(SITE_VERSIONS=ON_THREE_SIX):
            card = self._gallery_card('cardaround')
        self.assertIn('Solved around 3.6', card)
        self.assertIn('build-patch-badge-estimated', card)
        self.assertIn(ESTIMATE_TITLE_EN, card)
        self.assertNotIn('Solved on', card)
        self.assertNotIn('Solved before', card)

    def test_a_build_older_than_the_timeline_shows_only_the_mark(self):
        _build(self.owner, 'CardAncient', created_time=IN_2013,
               modified_time=IN_2013)
        card = self._gallery_card('cardancient')
        self.assertIn('Solved before 3.7', card)
        self.assertNotIn('Solved around', card)

    def test_an_imported_set_shows_no_badge(self):
        _build(self.owner, 'CardImported', origin='dofusbook',
               solved_version='3.6.11.15', modified_time=BEFORE_START)
        self.assertNotIn('build-patch-badge', self._gallery_card('cardimported'))

    def test_the_badge_follows_a_new_update_while_the_meta_is_cached(self):
        from chardata import shared_builds_view
        char = _build(self.owner, 'CardCached', solved_version='3.7.0.1',
                      solved_time=AFTER_START)
        self.assertIn('Solved on 3.7', self._gallery_card('cardcached'))
        self.assertIsNotNone(cache.get(
            shared_builds_view._get_shared_build_meta_cache_key(char)))
        with self.settings(SITE_VERSIONS=dict(VERSIONS, dofus3='3.8.0.0')):
            card = self._gallery_card('cardcached')
        self.assertIn('Solved before 3.8', card)
        self.assertNotIn('Solved on', card)

    def test_a_meta_cached_before_the_origin_key_shows_no_badge(self):
        from chardata import shared_builds_view
        char = _build(self.owner, 'CardOldMeta', solved_version='3.6.11.15',
                      solved_time=ON_THE_OLD_PATCH)
        meta = shared_builds_view._get_shared_build_meta(char)
        del meta['from_solver']
        cache.set(shared_builds_view._get_shared_build_meta_cache_key(char),
                  meta, 600)
        self.assertNotIn('build-patch-badge', self._gallery_card('cardoldmeta'))


OLD_KEYS = {'id', 'name', 'char_name', 'char_class', 'level', 'game_version',
            'creator', 'like_count', 'favorite_count', 'view_count',
            'created_at', 'modified_at', 'url', 'tags'}
NEW_KEYS = {'created_version', 'solved_version', 'solved_patch',
            'created_patch', 'created_patch_estimated', 'solved_patch_estimated'}


def _patches(body):
    return (body['created_version'], body['solved_version'],
            body['created_patch'], body['created_patch_estimated'],
            body['solved_patch'], body['solved_patch_estimated'])


@override_settings(SITE_VERSIONS=VERSIONS)
class TheApiGivesTheVersionsTests(_Pages, TestCase):

    def _stamped(self):
        return _build(self.owner, 'ApiStamped', created_version='3.6.11.15',
                      solved_version='3.7.0.1', solved_time=AFTER_START)

    def _detail(self, char):
        return self.client.get('/api/v1/shared-builds/%s/'
                               % encode_char_id(char.pk)).json()

    def test_the_list_adds_the_versions_and_keeps_every_key(self):
        char = self._stamped()
        rows = self.client.get('/api/v1/shared-builds/').json()['results']
        row = next(r for r in rows if r['id'] == encode_char_id(char.pk))
        self.assertEqual(OLD_KEYS | NEW_KEYS, set(row))
        self.assertEqual(('3.6.11.15', '3.7.0.1', '3.6', False, '3.7', False),
                         _patches(row))
        self.assertEqual(('Iop', 200, 'apistamped'),
                         (row['char_class'], row['level'], row['char_name']))

    def test_the_detail_adds_the_versions_and_keeps_every_key(self):
        body = self._detail(self._stamped())
        self.assertEqual(OLD_KEYS | NEW_KEYS | {'comment_count', 'solver'},
                         set(body))
        self.assertEqual(('3.6.11.15', '3.7.0.1', '3.6', False, '3.7', False),
                         _patches(body))

    def test_unrecorded_versions_are_estimated_and_say_so(self):
        body = self._detail(_build(self.owner, 'ApiBlank',
                                   created_time=UNDER_THREE_FOUR,
                                   modified_time=ON_THE_OLD_PATCH))
        self.assertEqual((None, None, '3.4', True, '3.6', True), _patches(body))

    def test_a_build_older_than_the_timeline_stays_null(self):
        body = self._detail(_build(self.owner, 'ApiAncient', created_time=IN_2013,
                                   modified_time=IN_2013))
        self.assertEqual((None, None, None, False, None, False), _patches(body))

    def test_the_tier_list_reads_the_versions_without_a_query_per_row(self):
        for index in range(3):
            _build(self.owner, 'Tier%d' % index, created_version='3.6.11.15',
                   solved_version='3.7.0.1')
        _build(self.owner, 'TierEstimated', created_time=UNDER_THREE_FOUR,
               modified_time=ON_THE_OLD_PATCH)
        with self.assertNumQueries(3):
            body = self.client.get('/api/v1/tier-list/?top=4').json()
        top = body['sections'][0]['top']
        self.assertEqual(4, len(top))
        self.assertEqual({('3.6.11.15', '3.7.0.1', '3.6', False, '3.7', False),
                          (None, None, '3.4', True, '3.6', True)},
                         {_patches(b) for b in top})
