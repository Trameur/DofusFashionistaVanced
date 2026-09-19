# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A build shows only the number of the game update in force at its last change."""
import html
import pickle
import re
from datetime import datetime, timedelta, timezone as utc_zone
from types import SimpleNamespace
from unittest import mock

from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings

import fashionista_version
from chardata.data_versions import build_patch_info, last_change
from chardata.encoded_char_id import encode_char_id
from chardata.models import Char, SolutionGeneration
from fashionistapulp.modelresult import ModelResultMinimal
from fashionistapulp.structure import get_structure, set_current_game_version

CURRENT = '3.7.0.4'
TIMELINE = {'dofus3': [('2025-12-09', '3.4'), ('2026-03-05', '3.5'),
                       ('2026-06-23', '3.6'), ('2026-09-17', '3.7')]}
VERSIONS = dict(settings.SITE_VERSIONS, dofus3=CURRENT)

IN_SEPTEMBER = datetime(2026, 9, 18, 10, 0, tzinfo=utc_zone.utc)
IN_AUGUST = datetime(2026, 8, 1, 12, 0, tzinfo=utc_zone.utc)
IN_JANUARY = datetime(2026, 1, 15, 12, 0, tzinfo=utc_zone.utc)
IN_2025 = datetime(2025, 6, 1, 12, 0, tzinfo=utc_zone.utc)

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
                minimal_solution=b'stored')
    base.update(fields)
    return SimpleNamespace(**base)


@override_settings(SITE_VERSIONS=VERSIONS)
class TheHelperReadsTheLastChangeTests(_Timeline, SimpleTestCase):

    def test_a_build_changed_on_the_current_update_is_current(self):
        self.assertEqual({'patch': '3.7', 'current_patch': '3.7', 'older': False},
                         build_patch_info(_record()))

    def test_a_build_changed_on_an_earlier_update_is_older(self):
        self.assertEqual({'patch': '3.6', 'current_patch': '3.7', 'older': True},
                         build_patch_info(_record(modified_time=IN_AUGUST)))

    def test_the_later_of_the_solve_and_the_save_counts(self):
        self.assertEqual(IN_SEPTEMBER, last_change(_record(solved_time=IN_SEPTEMBER,
                                                           modified_time=IN_AUGUST)))
        self.assertEqual(IN_SEPTEMBER, last_change(_record(solved_time=IN_AUGUST,
                                                           modified_time=IN_SEPTEMBER)))
        self.assertEqual('3.6', build_patch_info(_record(solved_time=IN_AUGUST,
                                                         modified_time=IN_JANUARY))['patch'])
        self.assertEqual('3.4', build_patch_info(_record(solved_time=None,
                                                         modified_time=IN_JANUARY))['patch'])

    def test_patches_compare_as_numbers(self):
        later = {'dofus3': TIMELINE['dofus3'] + [('2026-09-19', '3.9')]}
        with self.settings(SITE_VERSIONS=dict(VERSIONS, dofus3='3.10.0.1')), \
                mock.patch.dict(fashionista_version.PATCH_TIMELINE, later):
            info = build_patch_info(_record(modified_time=datetime(
                2026, 9, 19, 12, 0, tzinfo=utc_zone.utc)))
        self.assertEqual({'patch': '3.9', 'current_patch': '3.10', 'older': True}, info)

    def test_a_build_without_a_stored_set_shows_nothing(self):
        self.assertEqual({'patch': None, 'current_patch': '3.7', 'older': False},
                         build_patch_info(_record(minimal_solution=b'')))

    def test_a_caller_can_vouch_for_the_stored_set(self):
        info = build_patch_info(_record(minimal_solution=b'', modified_time=IN_AUGUST),
                                has_solution=True)
        self.assertEqual(('3.6', True), (info['patch'], info['older']))

    def test_a_build_older_than_the_timeline_shows_nothing(self):
        self.assertEqual({'patch': None, 'current_patch': '3.7', 'older': False},
                         build_patch_info(_record(modified_time=IN_2025)))

    def test_a_build_with_no_time_at_all_shows_nothing(self):
        self.assertIsNone(last_change(_record(modified_time=None)))
        self.assertIsNone(build_patch_info(_record(modified_time=None))['patch'])

    def test_a_saved_solution_uses_its_own_time(self):
        info = build_patch_info(_record(solved_time=IN_SEPTEMBER),
                                SimpleNamespace(created_time=IN_AUGUST))
        self.assertEqual(('3.6', True), (info['patch'], info['older']))

    def test_the_first_day_of_an_update_counts_for_it(self):
        def patch_at(moment):
            return build_patch_info(_record(modified_time=moment))['patch']
        self.assertEqual('3.7', patch_at(datetime(2026, 9, 17, 0, 0, tzinfo=utc_zone.utc)))
        self.assertEqual('3.6', patch_at(datetime(2026, 9, 16, 23, 59, tzinfo=utc_zone.utc)))
        self.assertEqual('3.6', patch_at(datetime(
            2026, 9, 17, 1, 30, tzinfo=utc_zone(timedelta(hours=2)))))

    def test_a_version_without_a_timeline_shows_nothing(self):
        self.assertEqual({'patch': None, 'current_patch': None, 'older': False},
                         build_patch_info(_record(game_version='wakfu')))


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
                  created_time=IN_AUGUST, modified_time=IN_SEPTEMBER)
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
                                  modified_time=IN_AUGUST))
        self.assertEqual(('3.6', OLDER_TITLE_EN, True), self._pill(page))
        self.assertEqual('3.6', _patch_line(page))

    def test_the_tooltips_read_in_french(self):
        current = self._visit(_build(self.owner, 'CourantFr'), 'fr')
        self.assertEqual(('3.7', TITLE_FR, False), self._pill(current))
        older = self._visit(_build(self.owner, 'AncienFr', modified_time=IN_AUGUST), 'fr')
        self.assertEqual(('3.6', OLDER_TITLE_FR, True), self._pill(older))

    def test_the_later_of_the_solve_and_the_save_counts(self):
        saved_later = self._visit(_build(self.owner, 'SavedLater', solved_time=IN_AUGUST,
                                         modified_time=IN_SEPTEMBER))
        self.assertEqual('3.7', self._pill(saved_later)[0])
        solved_later = self._visit(_build(self.owner, 'SolvedLater',
                                          solved_time=IN_SEPTEMBER,
                                          modified_time=IN_AUGUST))
        self.assertEqual('3.7', self._pill(solved_later)[0])

    def test_an_imported_set_shows_its_update_too(self):
        page = self._visit(_build(self.owner, 'ImportedSet', origin='pasted_text',
                                  modified_time=IN_AUGUST))
        self.assertEqual(('3.6', OLDER_TITLE_EN, True), self._pill(page))

    def test_a_build_older_than_the_timeline_shows_nothing(self):
        page = self._visit(_build(self.owner, 'Ancient', created_time=IN_2025,
                                  modified_time=IN_2025))
        self.assertIsNone(_patch_block(page))
        self.assertIsNone(_PILL.search(page))

    def test_the_owner_gets_the_solve_action_only_when_older(self):
        older = _build(self.owner, 'OlderOwned', modified_time=IN_AUGUST)
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
        _build(self.owner, 'CardOlder', modified_time=IN_AUGUST)
        self.assertEqual(('3.6', OLDER_TITLE_EN, True),
                         self._badge(self._gallery_card('cardolder')))

    def test_an_imported_set_shows_its_update_too(self):
        _build(self.owner, 'CardImported', origin='dofusbook', modified_time=IN_AUGUST)
        self.assertEqual('3.6', self._badge(self._gallery_card('cardimported'))[0])

    def test_a_build_older_than_the_timeline_shows_no_badge(self):
        _build(self.owner, 'CardAncient', created_time=IN_2025, modified_time=IN_2025)
        self.assertNotIn('build-patch-badge', self._gallery_card('cardancient'))

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
NEW_KEYS = {'created_version', 'solved_version', 'solved_patch', 'last_update_patch'}


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
        body = self._detail(_build(self.owner, 'ApiBlank', modified_time=IN_AUGUST))
        self.assertEqual((None, None, '3.6', '3.6'), _patches(body))

    def test_a_build_older_than_the_timeline_stays_null(self):
        body = self._detail(_build(self.owner, 'ApiAncient', created_time=IN_2025,
                                   modified_time=IN_2025))
        self.assertEqual((None, None, None, None), _patches(body))

    def test_the_tier_list_reads_the_versions_without_a_query_per_row(self):
        for index in range(3):
            _build(self.owner, 'Tier%d' % index, created_version='3.6.11.15',
                   solved_version='3.7.0.1')
        _build(self.owner, 'TierOlder', modified_time=IN_AUGUST)
        with self.assertNumQueries(3):
            body = self.client.get('/api/v1/tier-list/?top=4').json()
        top = body['sections'][0]['top']
        self.assertEqual(4, len(top))
        self.assertEqual({('3.6.11.15', '3.7.0.1', '3.7', '3.7'),
                          (None, None, '3.6', '3.6')},
                         {_patches(b) for b in top})
