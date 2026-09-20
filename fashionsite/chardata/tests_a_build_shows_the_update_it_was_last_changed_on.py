# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A build shows only the number of the game update in force at its last change."""
import html
import importlib
import pickle
import re
from datetime import datetime, timedelta, timezone as utc_zone
from types import SimpleNamespace
from unittest import mock

from django.apps import apps
from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

import fashionista_version
from chardata.data_versions import build_patch_info, last_change, patch_in_force
from chardata.encoded_char_id import encode_char_id
from chardata.models import Char, SolutionGeneration
from chardata.stuff_time_backfill import backfill_stuff_time, batch_minutes
from fashionistapulp.modelresult import ModelResultMinimal
from fashionistapulp.structure import get_structure, set_current_game_version

CURRENT = '3.7.0.4'
TIMELINE = {'dofus3': [('2025-12-09', '3.4'), ('2026-03-05', '3.5'),
                       ('2026-06-23', '3.6'), ('2026-09-17', '3.7')]}
LONG_TIMELINE = {'dofus3': [('2024-06-18', '2.72'), ('2024-11-08', '2.73'),
                            ('2024-11-29', '3.0'), ('2025-04-22', '3.1'),
                            ('2025-07-22', '3.2'), ('2025-10-01', '3.3')]
                 + TIMELINE['dofus3']}
VERSIONS = dict(settings.SITE_VERSIONS, dofus3=CURRENT)

IN_SEPTEMBER = datetime(2026, 9, 18, 10, 0, tzinfo=utc_zone.utc)
IN_AUGUST = datetime(2026, 8, 1, 12, 0, tzinfo=utc_zone.utc)
IN_JANUARY = datetime(2026, 1, 15, 12, 0, tzinfo=utc_zone.utc)
IN_2025 = datetime(2025, 6, 1, 12, 0, tzinfo=utc_zone.utc)
IN_2024 = datetime(2024, 8, 1, 12, 0, tzinfo=utc_zone.utc)
BATCH_MINUTE = datetime(2025, 11, 6, 10, 0, tzinfo=utc_zone.utc)

BROWSER = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
           '(KHTML, like Gecko) Chrome/126.0 Safari/537.36')

TITLE_EN = "Game update at the build's last change"
OLDER_TITLE_EN = "Game update at the build's last change; the game is now on 3.7"
TITLE_FR = 'Mise à jour du jeu au dernier changement du build'
OLDER_TITLE_FR = ('Mise à jour du jeu au dernier changement du build ; '
                  'le jeu est maintenant en 3.7')


class _Timeline(object):

    def setUp(self):
        super().setUp()
        patcher = mock.patch.dict(fashionista_version.PATCH_TIMELINE, TIMELINE)
        patcher.start()
        self.addCleanup(patcher.stop)


def _record(**fields):
    base = dict(game_version='dofus3', solved_time=None, modified_time=IN_SEPTEMBER,
                stuff_time=IN_SEPTEMBER, minimal_solution=b'stored')
    base.update(fields)
    return SimpleNamespace(**base)


@override_settings(SITE_VERSIONS=VERSIONS)
class TheHelperReadsTheLastChangeTests(_Timeline, SimpleTestCase):

    def test_a_build_changed_on_the_current_update_is_current(self):
        self.assertEqual({'patch': '3.7', 'current_patch': '3.7', 'older': False},
                         build_patch_info(_record()))

    def test_a_build_changed_on_an_earlier_update_is_older(self):
        self.assertEqual({'patch': '3.6', 'current_patch': '3.7', 'older': True},
                         build_patch_info(_record(stuff_time=IN_AUGUST)))

    def test_only_the_change_of_the_set_counts(self):
        self.assertEqual(IN_AUGUST, last_change(_record(stuff_time=IN_AUGUST,
                                                        solved_time=IN_SEPTEMBER,
                                                        modified_time=IN_SEPTEMBER)))
        self.assertEqual('3.6', build_patch_info(_record(stuff_time=IN_AUGUST,
                                                         modified_time=IN_SEPTEMBER))['patch'])
        self.assertEqual('3.4', build_patch_info(_record(stuff_time=IN_JANUARY,
                                                         solved_time=IN_SEPTEMBER))['patch'])
        self.assertIsNone(last_change(_record(stuff_time=None, solved_time=IN_SEPTEMBER,
                                              modified_time=IN_SEPTEMBER)))

    def test_patches_compare_as_numbers(self):
        later = {'dofus3': TIMELINE['dofus3'] + [('2026-09-19', '3.9')]}
        with self.settings(SITE_VERSIONS=dict(VERSIONS, dofus3='3.10.0.1')), \
                mock.patch.dict(fashionista_version.PATCH_TIMELINE, later):
            info = build_patch_info(_record(stuff_time=datetime(
                2026, 9, 19, 12, 0, tzinfo=utc_zone.utc)))
        self.assertEqual({'patch': '3.9', 'current_patch': '3.10', 'older': True}, info)

    def test_a_build_without_a_stored_set_shows_nothing(self):
        self.assertEqual({'patch': None, 'current_patch': '3.7', 'older': False},
                         build_patch_info(_record(minimal_solution=b'')))

    def test_a_caller_can_vouch_for_the_stored_set(self):
        info = build_patch_info(_record(minimal_solution=b'', stuff_time=IN_AUGUST),
                                has_solution=True)
        self.assertEqual(('3.6', True), (info['patch'], info['older']))

    def test_a_build_older_than_the_timeline_shows_nothing(self):
        self.assertEqual({'patch': None, 'current_patch': '3.7', 'older': False},
                         build_patch_info(_record(stuff_time=IN_2025)))

    def test_a_build_whose_set_never_changed_shows_nothing(self):
        self.assertIsNone(last_change(_record(stuff_time=None)))
        self.assertIsNone(build_patch_info(_record(stuff_time=None))['patch'])

    def test_a_saved_solution_uses_its_own_time(self):
        info = build_patch_info(_record(solved_time=IN_SEPTEMBER),
                                SimpleNamespace(created_time=IN_AUGUST))
        self.assertEqual(('3.6', True), (info['patch'], info['older']))

    def test_the_first_day_of_an_update_counts_for_it(self):
        def patch_at(moment):
            return build_patch_info(_record(stuff_time=moment))['patch']
        self.assertEqual('3.7', patch_at(datetime(2026, 9, 17, 0, 0, tzinfo=utc_zone.utc)))
        self.assertEqual('3.6', patch_at(datetime(2026, 9, 16, 23, 59, tzinfo=utc_zone.utc)))
        self.assertEqual('3.6', patch_at(datetime(
            2026, 9, 17, 1, 30, tzinfo=utc_zone(timedelta(hours=2)))))

    def test_a_version_without_a_timeline_shows_nothing(self):
        self.assertEqual({'patch': None, 'current_patch': None, 'older': False},
                         build_patch_info(_record(game_version='wakfu')))


def _hats():
    structure = get_structure('dofus3')
    return [item for item in structure.get_unique_items_by_type_and_level('Hat', 200)
            if not item.removed and item.ankama_id][:2]


def _hat():
    return _hats()[0]


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
                  created_time=IN_AUGUST, modified_time=IN_SEPTEMBER,
                  stuff_time=IN_SEPTEMBER)
    fields.update(stamps)
    Char.objects.filter(pk=char.pk).update(**fields)
    char.refresh_from_db()
    return char


_PILL = re.compile(r'<span\b([^>]*char-banner-patch-pill[^>]*)>(.*?)</span>', re.S)
_BADGE = re.compile(r'<span\b([^>]*build-patch-badge[^>]*)>(.*?)</span>', re.S)


def _patch_block(page):
    found = re.search(r'<div class="char-banner-patch">(.*?)</div>', page, re.S)
    return found.group(1) if found else None


def _patch_line(page):
    block = _patch_block(page)
    if block is None:
        return None
    return ' '.join(re.sub(r'<[^>]+>', ' ', block).split())


def _shown(found, muted_class):
    """(number, tooltip, muted) of a matched pill or badge."""
    title = re.search(r'title="([^"]*)"', found.group(1))
    return (found.group(2).strip(),
            html.unescape(title.group(1)) if title else None,
            muted_class in found.group(1))


class _Pages(_Timeline):

    def setUp(self):
        super().setUp()
        set_current_game_version('dofus3')
        cache.clear()
        self.addCleanup(cache.clear)
        self.owner = User.objects.create_user('patchowner', 'patch@test.local',
                                              'pw-42-solid')


@override_settings(SITE_VERSIONS=VERSIONS)
class TheBuildPageShowsTheUpdateTests(_Pages, TestCase):

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

    def _pill(self, page):
        found = _PILL.search(page)
        self.assertIsNotNone(found, 'no update pill on the page')
        return _shown(found, 'char-banner-patch-old')

    def test_a_current_build_shows_the_number_alone(self):
        page = self._visit(_build(self.owner, 'CurrentSolve', solved_time=IN_SEPTEMBER))
        self.assertEqual(('3.7', TITLE_EN, False), self._pill(page))
        self.assertEqual('3.7', _patch_line(page))

    def test_an_older_build_is_muted_and_its_tooltip_names_the_current_update(self):
        page = self._visit(_build(self.owner, 'OlderSolve', solved_time=IN_AUGUST,
                                  stuff_time=IN_AUGUST))
        self.assertEqual(('3.6', OLDER_TITLE_EN, True), self._pill(page))
        self.assertEqual('3.6', _patch_line(page))

    def test_the_tooltips_read_in_french(self):
        current = self._visit(_build(self.owner, 'CourantFr'), 'fr')
        self.assertEqual(('3.7', TITLE_FR, False), self._pill(current))
        older = self._visit(_build(self.owner, 'AncienFr', stuff_time=IN_AUGUST), 'fr')
        self.assertEqual(('3.6', OLDER_TITLE_FR, True), self._pill(older))

    def test_a_later_save_does_not_move_the_number(self):
        saved_later = self._visit(_build(self.owner, 'SavedLater', solved_time=IN_AUGUST,
                                         stuff_time=IN_AUGUST, modified_time=IN_SEPTEMBER))
        self.assertEqual(('3.6', OLDER_TITLE_EN, True), self._pill(saved_later))

    def test_a_build_whose_set_never_changed_shows_nothing(self):
        page = self._visit(_build(self.owner, 'NeverChanged', stuff_time=None,
                                  solved_time=IN_SEPTEMBER))
        self.assertIsNone(_patch_block(page))
        self.assertIsNone(_PILL.search(page))

    def test_an_imported_set_shows_its_update_too(self):
        page = self._visit(_build(self.owner, 'ImportedSet', origin='pasted_text',
                                  stuff_time=IN_AUGUST))
        self.assertEqual(('3.6', OLDER_TITLE_EN, True), self._pill(page))

    def test_a_build_older_than_the_timeline_shows_nothing(self):
        page = self._visit(_build(self.owner, 'Ancient', created_time=IN_2025,
                                  modified_time=IN_2025, stuff_time=IN_2025))
        self.assertIsNone(_patch_block(page))
        self.assertIsNone(_PILL.search(page))

    def test_the_owner_gets_the_solve_action_only_when_older(self):
        older = _build(self.owner, 'OlderOwned', stuff_time=IN_AUGUST)
        self.assertNotIn('/fashion/', _patch_block(self._visit(older)))
        owned = _patch_block(self._own('/solution/%d/' % older.pk))
        self.assertIn('href="/fashion/%d/"' % older.pk, owned)
        self.assertIn('Tailor a New Set', owned)
        current = _build(self.owner, 'CurrentOwned')
        self.assertNotIn('/fashion/', _patch_block(self._own('/solution/%d/' % current.pk)))

    def test_a_saved_solution_shows_its_own_time_and_no_action(self):
        char = _build(self.owner, 'SavedSolve', solved_time=IN_SEPTEMBER)
        generation = SolutionGeneration.objects.create(
            char=char, game_version='dofus3',
            minimal_solution=char.minimal_solution, data_version='3.6.2.1')
        SolutionGeneration.objects.filter(pk=generation.pk).update(created_time=IN_AUGUST)
        page = self._own('/solutiongeneration/%d/%d/' % (char.pk, generation.pk))
        self.assertEqual(('3.6', OLDER_TITLE_EN, True), self._pill(page))
        self.assertNotIn('/fashion/', _patch_block(page))


def _card(page, name):
    for card in page.split('<div class="build-card">')[1:]:
        if name in card:
            return card
    raise AssertionError('no card named %s on the gallery' % name)


@override_settings(SITE_VERSIONS=VERSIONS)
class TheGalleryCardShowsTheUpdateTests(_Pages, TestCase):

    def _gallery_card(self, name):
        page = self.client.get('/sharedbuilds/', HTTP_ACCEPT_LANGUAGE='en')
        self.assertEqual(200, page.status_code)
        return _card(page.content.decode('utf-8'), name)

    def _badge(self, card):
        found = _BADGE.search(card)
        self.assertIsNotNone(found, 'no update badge on the card')
        return _shown(found, 'build-patch-badge-old')

    def test_a_current_build_shows_the_number_alone(self):
        _build(self.owner, 'CardCurrent')
        self.assertEqual(('3.7', TITLE_EN, False),
                         self._badge(self._gallery_card('cardcurrent')))

    def test_an_older_build_is_muted_and_its_tooltip_names_the_current_update(self):
        _build(self.owner, 'CardOlder', stuff_time=IN_AUGUST)
        self.assertEqual(('3.6', OLDER_TITLE_EN, True),
                         self._badge(self._gallery_card('cardolder')))

    def test_a_later_save_does_not_move_the_number(self):
        _build(self.owner, 'CardSaved', stuff_time=IN_AUGUST, modified_time=IN_SEPTEMBER)
        self.assertEqual('3.6', self._badge(self._gallery_card('cardsaved'))[0])

    def test_an_imported_set_shows_its_update_too(self):
        _build(self.owner, 'CardImported', origin='dofusbook', stuff_time=IN_AUGUST)
        self.assertEqual('3.6', self._badge(self._gallery_card('cardimported'))[0])

    def test_a_build_older_than_the_timeline_shows_no_badge(self):
        _build(self.owner, 'CardAncient', created_time=IN_2025, modified_time=IN_2025,
               stuff_time=IN_2025)
        self.assertNotIn('build-patch-badge', self._gallery_card('cardancient'))

    def test_a_build_whose_set_never_changed_shows_no_badge(self):
        _build(self.owner, 'CardNever', stuff_time=None)
        self.assertNotIn('build-patch-badge', self._gallery_card('cardnever'))

    def test_the_badge_follows_a_new_update_while_the_meta_is_cached(self):
        from chardata import shared_builds_view
        char = _build(self.owner, 'CardCached')
        self.assertEqual(('3.7', TITLE_EN, False),
                         self._badge(self._gallery_card('cardcached')))
        self.assertIsNotNone(cache.get(
            shared_builds_view._get_shared_build_meta_cache_key(char)))
        with self.settings(SITE_VERSIONS=dict(VERSIONS, dofus3='3.8.0.0')):
            card = self._gallery_card('cardcached')
        self.assertEqual(('3.7', OLDER_TITLE_EN.replace('3.7', '3.8'), True),
                         self._badge(card))


OLD_KEYS = {'id', 'name', 'char_name', 'char_class', 'level', 'game_version',
            'creator', 'like_count', 'favorite_count', 'view_count',
            'created_at', 'modified_at', 'url', 'tags'}
NEW_KEYS = {'created_version', 'solved_version', 'solved_patch', 'last_update_patch',
            'stuff_changed_at'}


def _patches(body):
    return (body['created_version'], body['solved_version'],
            body['solved_patch'], body['last_update_patch'])


@override_settings(SITE_VERSIONS=VERSIONS)
class TheApiGivesTheVersionsTests(_Pages, TestCase):

    def _stamped(self):
        return _build(self.owner, 'ApiStamped', created_version='3.6.11.15',
                      solved_version='3.7.0.1', solved_time=IN_SEPTEMBER)

    def _detail(self, char):
        return self.client.get('/api/v1/shared-builds/%s/'
                               % encode_char_id(char.pk)).json()

    def test_the_list_adds_the_versions_and_keeps_every_key(self):
        char = self._stamped()
        rows = self.client.get('/api/v1/shared-builds/').json()['results']
        row = next(r for r in rows if r['id'] == encode_char_id(char.pk))
        self.assertEqual(OLD_KEYS | NEW_KEYS, set(row))
        self.assertEqual(('3.6.11.15', '3.7.0.1', '3.7', '3.7'), _patches(row))
        self.assertEqual(('Iop', 200, 'apistamped'),
                         (row['char_class'], row['level'], row['char_name']))

    def test_the_detail_adds_the_versions_and_keeps_every_key(self):
        body = self._detail(self._stamped())
        self.assertEqual(OLD_KEYS | NEW_KEYS | {'comment_count', 'solver'},
                         set(body))
        self.assertEqual(('3.6.11.15', '3.7.0.1', '3.7', '3.7'), _patches(body))

    def test_an_unstamped_build_gets_the_update_of_its_last_change(self):
        body = self._detail(_build(self.owner, 'ApiBlank', stuff_time=IN_AUGUST))
        self.assertEqual((None, None, '3.6', '3.6'), _patches(body))

    def test_a_build_older_than_the_timeline_stays_null(self):
        body = self._detail(_build(self.owner, 'ApiAncient', created_time=IN_2025,
                                   modified_time=IN_2025, stuff_time=IN_2025))
        self.assertEqual((None, None, None, None), _patches(body))

    def test_the_time_of_the_last_set_change_is_given_beside_the_save_time(self):
        body = self._detail(_build(self.owner, 'ApiTimes', stuff_time=IN_AUGUST,
                                   modified_time=IN_SEPTEMBER))
        self.assertEqual(IN_AUGUST.isoformat(), body['stuff_changed_at'])
        self.assertEqual(IN_SEPTEMBER.isoformat(), body['modified_at'])
        self.assertEqual('3.6', body['last_update_patch'])
        never = self._detail(_build(self.owner, 'ApiNever', stuff_time=None))
        self.assertIsNone(never['stuff_changed_at'])
        self.assertIsNone(never['last_update_patch'])

    def test_the_tier_list_reads_the_versions_without_a_query_per_row(self):
        for index in range(3):
            _build(self.owner, 'Tier%d' % index, created_version='3.6.11.15',
                   solved_version='3.7.0.1')
        _build(self.owner, 'TierOlder', stuff_time=IN_AUGUST)
        with self.assertNumQueries(3):
            body = self.client.get('/api/v1/tier-list/?top=4').json()
        top = body['sections'][0]['top']
        self.assertEqual(4, len(top))
        self.assertEqual({('3.6.11.15', '3.7.0.1', '3.7', '3.7'),
                          (None, None, '3.6', '3.6')},
                         {_patches(b) for b in top})


def _pill_of(page):
    found = _PILL.search(page)
    return _shown(found, 'char-banner-patch-old') if found else None


@override_settings(SITE_VERSIONS=VERSIONS)
class TheChangeOfTheSetStampsTheBuildTests(_Pages, TestCase):

    def setUp(self):
        super().setUp()
        self.hats = _hats()
        self.assertEqual(2, len(self.hats))
        self.char = _build(self.owner, 'Stamped', stuff_time=IN_AUGUST,
                           modified_time=IN_AUGUST)
        self.client.force_login(self.owner)

    def _stamps(self):
        self.char.refresh_from_db()
        return self.char.stuff_time, self.char.modified_time

    def _own_page(self):
        page = self.client.get('/solution/%d/' % self.char.pk, HTTP_ACCEPT_LANGUAGE='en')
        self.assertEqual(200, page.status_code)
        return page.content.decode('utf-8')

    def test_a_swap_stamps_the_change(self):
        before = timezone.now()
        answer = self.client.post('/exchange/%d/' % self.char.pk,
                                  {'itemName': str(self.hats[1].id), 'slot': 'hat'})
        self.assertEqual('ok', answer.content.decode())
        stuff, modified = self._stamps()
        self.assertGreaterEqual(stuff, before)
        self.assertGreaterEqual(modified, stuff)
        self.assertEqual(('3.7', TITLE_EN, False), _pill_of(self._own_page()))

    def test_removing_a_piece_stamps_the_change(self):
        before = timezone.now()
        answer = self.client.post('/remove/%d/' % self.char.pk, {'slot': 'hat'})
        self.assertEqual('ok', answer.content.decode())
        self.assertGreaterEqual(self._stamps()[0], before)

    def test_a_rename_leaves_the_stamp_and_the_number(self):
        answer = self.client.post('/saveproject/%d/' % self.char.pk,
                                  {'project': 'Renamed', 'charname': 'stamped',
                                   'level': '200', 'class': 'Iop'})
        self.assertEqual(200, answer.status_code)
        stuff, modified = self._stamps()
        self.assertEqual('Renamed', self.char.name)
        self.assertEqual(IN_AUGUST, stuff)
        self.assertGreater(modified, IN_AUGUST)
        self.assertEqual(('3.6', OLDER_TITLE_EN, True), _pill_of(self._own_page()))

    def test_publishing_and_hiding_leave_the_stamp(self):
        Char.objects.filter(pk=self.char.pk).update(link_shared=False)
        self.client.post('/getsharinglink/%d/' % self.char.pk)
        self.assertEqual(IN_AUGUST, self._stamps()[0])
        self.assertTrue(self.char.link_shared)
        self.client.post('/hidesharinglink/%d/' % self.char.pk)
        self.assertEqual(IN_AUGUST, self._stamps()[0])
        self.assertFalse(self.char.link_shared)

    def test_a_restore_takes_the_time_of_the_restored_solution(self):
        generation = SolutionGeneration.objects.create(
            char=self.char, game_version='dofus3',
            minimal_solution=self.char.minimal_solution, data_version='3.4.0.1')
        SolutionGeneration.objects.filter(pk=generation.pk).update(created_time=IN_JANUARY)
        answer = self.client.post('/restoregeneration/%d/%d/'
                                  % (self.char.pk, generation.pk))
        self.assertEqual(302, answer.status_code)
        self.assertEqual(IN_JANUARY, self._stamps()[0])
        self.assertEqual(('3.4', OLDER_TITLE_EN, True), _pill_of(self._own_page()))


def _filler_rows(count):
    return [Char(name='filler%d' % index, char_name='filler%d' % index, char_class='Iop',
                 char_build='build', level=200, minimum_stats=b'', minimum_crits=b'',
                 stats_weight=b'', options=b'', inclusions=b'', exclusions=b'',
                 minimal_solution=b'', link_shared=False, game_version='dofus3')
            for index in range(count)]


@override_settings(SITE_VERSIONS=VERSIONS)
class TheBackfillReadsTheTimeOfTheLastSetChangeTests(_Pages, TestCase):

    def setUp(self):
        super().setUp()
        patcher = mock.patch.dict(fashionista_version.PATCH_TIMELINE, LONG_TIMELINE)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _batch(self, count=100):
        Char.objects.bulk_create(_filler_rows(count))
        fillers = Char.objects.filter(name__startswith='filler').order_by('id')
        ids = list(fillers.values_list('id', flat=True))
        half = len(ids) // 2
        Char.objects.filter(id__in=ids[:half]).update(
            modified_time=BATCH_MINUTE + timedelta(seconds=5))
        Char.objects.filter(id__in=ids[half:]).update(
            modified_time=BATCH_MINUTE + timedelta(seconds=59))

    def _stamp(self, char):
        char.refresh_from_db()
        return char.stuff_time

    def test_a_minute_with_a_hundred_saves_is_a_batch(self):
        self._batch(100)
        self.assertEqual({BATCH_MINUTE}, batch_minutes(Char))
        self.assertEqual(set(), batch_minutes(Char, threshold=101))

    def test_each_build_takes_the_time_its_set_last_changed(self):
        self._batch()
        generated = _build(self.owner, 'Generated', solved_time=IN_AUGUST, stuff_time=None,
                           modified_time=BATCH_MINUTE + timedelta(seconds=7))
        for moment in (IN_SEPTEMBER, IN_JANUARY):
            generation = SolutionGeneration.objects.create(
                char=generated, game_version='dofus3',
                minimal_solution=generated.minimal_solution)
            SolutionGeneration.objects.filter(pk=generation.pk).update(created_time=moment)
        solved = _build(self.owner, 'Solved', solved_time=IN_JANUARY, stuff_time=None,
                        modified_time=BATCH_MINUTE)
        clean = _build(self.owner, 'Clean', created_time=IN_JANUARY, stuff_time=None,
                       modified_time=IN_AUGUST)
        old = _build(self.owner, 'Old', created_time=IN_2024, stuff_time=None,
                     modified_time=BATCH_MINUTE + timedelta(seconds=30))
        bare = _build(self.owner, 'Bare', minimal_solution=b'', stuff_time=None,
                      modified_time=IN_AUGUST)
        counts, minutes = backfill_stuff_time(Char, SolutionGeneration, range_size=7)
        self.assertEqual({BATCH_MINUTE}, minutes)
        self.assertEqual({'generation': 1, 'solved_time': 1, 'modified_time': 1,
                          'batch_minute': 1, 'view_saved': 0, 'no_modified_time': 0,
                          'no_set': 101},
                         dict(counts))
        self.assertEqual(IN_SEPTEMBER, self._stamp(generated))
        self.assertEqual(IN_JANUARY, self._stamp(solved))
        self.assertEqual(IN_AUGUST, self._stamp(clean))
        self.assertEqual(IN_2024, self._stamp(old))
        self.assertIsNone(self._stamp(bare))
        self.assertEqual(0, Char.objects.filter(name__startswith='filler',
                                                stuff_time__isnull=False).count())

    def test_a_dry_run_counts_without_writing(self):
        self._batch()
        old = _build(self.owner, 'Old', created_time=IN_2024, stuff_time=None,
                     modified_time=BATCH_MINUTE)
        counts, minutes = backfill_stuff_time(Char, SolutionGeneration, apply=False)
        self.assertEqual(({BATCH_MINUTE}, 1), (minutes, counts['batch_minute']))
        self.assertIsNone(self._stamp(old))

    def test_an_old_build_batch_saved_under_a_later_update_shows_its_own(self):
        self._batch()
        old = _build(self.owner, 'Ancestral', created_time=IN_2024, stuff_time=None,
                     modified_time=BATCH_MINUTE + timedelta(seconds=30))
        self.assertEqual('3.3', patch_in_force('dofus3', BATCH_MINUTE))
        migration = importlib.import_module('chardata.migrations.0043_backfill_stuff_time')
        migration.fill(apps, None)
        page = self.client.get(
            '/s/%s/%s/' % (old.char_name, encode_char_id(old.pk)),
            HTTP_ACCEPT_LANGUAGE='en', HTTP_USER_AGENT=BROWSER).content.decode('utf-8')
        self.assertEqual(('2.72', OLDER_TITLE_EN, True), _pill_of(page))

    def test_a_shared_build_saved_by_a_visit_keeps_its_creation_time(self):
        visited = _build(self.owner, 'Visited', created_time=IN_2024, stuff_time=None,
                         modified_time=IN_JANUARY)
        private = _build(self.owner, 'Private', created_time=IN_2024, stuff_time=None,
                         modified_time=IN_JANUARY, link_shared=False)
        before = _build(self.owner, 'Before', created_time=IN_2024, stuff_time=None,
                        modified_time=IN_2025)
        after = _build(self.owner, 'After', created_time=IN_2024, stuff_time=None,
                       modified_time=IN_AUGUST)
        counts, _ = backfill_stuff_time(Char, SolutionGeneration)
        self.assertEqual((1, 3), (counts['view_saved'], counts['modified_time']))
        self.assertEqual(IN_2024, self._stamp(visited))
        self.assertEqual(IN_JANUARY, self._stamp(private))
        self.assertEqual(IN_2025, self._stamp(before))
        self.assertEqual(IN_AUGUST, self._stamp(after))

    def test_the_refill_rewrites_only_the_visited_builds(self):
        visited = _build(self.owner, 'Visited', created_time=IN_2024, stuff_time=IN_JANUARY,
                         modified_time=IN_JANUARY)
        edited = _build(self.owner, 'Edited', created_time=IN_2024, stuff_time=IN_2025,
                        modified_time=IN_AUGUST)
        migration = importlib.import_module(
            'chardata.migrations.0044_refill_stuff_time_of_visited_builds')
        migration.refill(apps, None)
        self.assertEqual(IN_2024, self._stamp(visited))
        self.assertEqual(IN_2025, self._stamp(edited))

    def test_an_old_build_visited_under_a_later_update_shows_its_own(self):
        old = _build(self.owner, 'Ancestral', created_time=IN_2024, stuff_time=IN_JANUARY,
                     modified_time=IN_JANUARY)
        self.assertEqual('3.4', patch_in_force('dofus3', IN_JANUARY))
        migration = importlib.import_module(
            'chardata.migrations.0044_refill_stuff_time_of_visited_builds')
        migration.refill(apps, None)
        page = self.client.get(
            '/s/%s/%s/' % (old.char_name, encode_char_id(old.pk)),
            HTTP_ACCEPT_LANGUAGE='en', HTTP_USER_AGENT=BROWSER).content.decode('utf-8')
        self.assertEqual(('2.72', OLDER_TITLE_EN, True), _pill_of(page))
