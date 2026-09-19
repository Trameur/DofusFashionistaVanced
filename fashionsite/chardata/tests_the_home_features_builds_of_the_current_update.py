# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The home features popular builds solved on the current update, then on the previous one."""
import html
import pickle
import re
from datetime import datetime, timezone as utc_zone
from unittest import mock

from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext

import fashionista_version
from chardata.home_view import FEATURED_BUILDS_COUNT, _score_featured_builds
from chardata.models import BuildVote, Char
from fashionistapulp.modelresult import ModelResultMinimal
from fashionistapulp.structure import set_current_game_version

VERSIONS = dict(settings.SITE_VERSIONS, dofus3='3.7.0.4')
EARLY = datetime(2026, 9, 17, 10, 0, tzinfo=utc_zone.utc)
LATE = datetime(2026, 9, 18, 10, 0, tzinfo=utc_zone.utc)
AUGUST = datetime(2026, 8, 1, 12, 0, tzinfo=utc_zone.utc)
SOLUTION = pickle.dumps(ModelResultMinimal({}, {'origin': 'generated'}, {}))
UP_TO_THREE_SEVEN = [('2026-03-05', '3.5'), ('2026-06-23', '3.6'), ('2026-09-17', '3.7')]
UP_TO_THREE_EIGHT = UP_TO_THREE_SEVEN + [('2026-09-19', '3.8')]
TITLE = "Game update at the build's last change"
OLDER_TITLE = "Game update at the build's last change; the game is now on %s"

_CARD = re.compile(r'<a\b[^>]*featured-build-card[^>]*>(.*?)</a>', re.S)
_BADGE = re.compile(r'<span\b([^>]*build-patch-badge[^>]*)>(.*?)</span>', re.S)


def _cards(page):
    return [' '.join(re.sub(r'<[^>]+>', ' ', body).split())
            for body in _CARD.findall(page)]


def _badges(page):
    """(number, tooltip, muted) per card, None on a card without a badge."""
    shown = []
    for body in _CARD.findall(page):
        badge = _BADGE.search(body)
        if badge is None:
            shown.append(None)
            continue
        title = re.search(r'title="([^"]*)"', badge.group(1))
        shown.append((badge.group(2).strip(),
                      html.unescape(title.group(1)) if title else None,
                      'build-patch-badge-old' in badge.group(1)))
    return shown


def _timeline(entries):
    return mock.patch.dict(fashionista_version.PATCH_TIMELINE, {'dofus3': entries})


class _Featured(object):

    def setUp(self):
        super().setUp()
        set_current_game_version('dofus3')
        cache.clear()
        self.addCleanup(cache.clear)
        self.owner = User.objects.create_user('featuredowner', 'featured@test.local',
                                              'pw-42-solid')

    def _shared(self, name, solved_version='', views=0, solved_time=LATE, **fields):
        base = dict(name=name, char_name=name, char_class='Iop', char_build='build',
                    level=200, minimum_stats=b'', minimum_crits=b'',
                    stats_weight=pickle.dumps({'vit': 1}), options=b'',
                    inclusions=b'', exclusions=b'', minimal_solution=SOLUTION,
                    owner=self.owner, link_shared=True, deleted=False,
                    game_version='dofus3', view_count=views,
                    solved_version=solved_version,
                    solved_time=solved_time if solved_version else None)
        base.update(fields)
        return Char.objects.create(**base)

    def _featured(self):
        return [build['name'] for build in _score_featured_builds('dofus3')]


@override_settings(SITE_VERSIONS=VERSIONS)
class TheHomePicksBuildsOfTheCurrentUpdateTests(_Featured, TestCase):

    def test_a_current_build_outranks_a_more_popular_previous_one(self):
        self._shared('previous', '3.6.11.15', views=50)
        for rank in range(FEATURED_BUILDS_COUNT):
            self._shared('current%d' % rank, '3.7.0.%d' % rank, views=rank + 1)
        self.assertEqual(['current5', 'current4', 'current3', 'current2',
                          'current1', 'current0'], self._featured())

    def test_the_previous_update_completes_the_row(self):
        self._shared('current1', '3.7.0.4', views=1)
        self._shared('current2', '3.7.0.1', views=2)
        for views in range(10, 15):
            self._shared('previous%d' % views, '3.6.11.15', views=views)
        self.assertEqual(['current2', 'current1', 'previous14', 'previous13',
                          'previous12', 'previous11'], self._featured())

    def test_an_update_older_than_the_previous_one_is_not_featured(self):
        self._shared('current', '3.7.0.4', views=1)
        self._shared('previous', '3.6.2.1', views=2)
        self._shared('older', '3.5.4.0', views=50)
        self.assertEqual(['current', 'previous'], self._featured())

    def test_the_last_recorded_update_below_the_current_one_stands_in(self):
        self._shared('older', '3.5.4.0', views=1)
        self._shared('oldest', '3.4.0.9', views=50)
        self.assertEqual(['older'], self._featured())

    def test_patches_compare_as_numbers(self):
        self._shared('ten', '3.10.0.1', views=1)
        self._shared('nine', '3.9.4.2', views=2)
        self._shared('eight', '3.8.1.0', views=40)
        self._shared('one', '3.1.0.5', views=50)
        with self.settings(SITE_VERSIONS=dict(VERSIONS, dofus3='3.10.0.1')):
            self.assertEqual(['ten', 'nine'], self._featured())

    def test_a_version_that_is_not_a_number_is_ignored(self):
        self._shared('current', '3.7.0.4', views=1)
        self._shared('word', 'unknown', views=50)
        self._shared('dotted', '3.x.1', views=50)
        self.assertEqual(['current'], self._featured())

    def test_a_build_never_solved_is_not_featured(self):
        self._shared('current', '3.7.0.4', views=1)
        self._shared('unsolved', '', views=50)
        self.assertEqual(['current'], self._featured())

    def test_a_build_without_a_stored_solution_is_not_featured(self):
        self._shared('current', '3.7.0.4', views=1)
        self._shared('nosolution', '3.7.0.4', views=50, minimal_solution=b'')
        self.assertEqual(['current'], self._featured())

    def test_only_shared_live_builds_of_the_version_are_featured(self):
        self._shared('current', '3.7.0.4', views=1)
        self._shared('private', '3.7.0.4', views=50, link_shared=False)
        self._shared('deleted', '3.7.0.4', views=50, deleted=True)
        self._shared('beta', '3.7.0.4', views=50, game_version='beta')
        self.assertEqual(['current'], self._featured())

    def test_a_tie_goes_to_the_most_recent_solve(self):
        self._shared('late', '3.7.0.4', views=5, solved_time=LATE)
        self._shared('early', '3.7.0.4', views=5, solved_time=EARLY)
        self.assertEqual(['late', 'early'], self._featured())

    def test_a_tie_on_the_solve_time_goes_to_the_newest_build(self):
        self._shared('first', '3.7.0.4', views=5)
        self._shared('second', '3.7.0.4', views=5)
        self.assertEqual(['second', 'first'], self._featured())

    def test_the_score_counts_likes_favorites_and_capped_views(self):
        self._shared('viewed', '3.7.0.4', views=500)
        voted = self._shared('voted', '3.7.0.4', views=40)
        for index in range(3):
            voter = User.objects.create_user('voter%d' % index,
                                             'v%d@test.local' % index, 'pw-42-solid')
            BuildVote.objects.create(user=voter, build=voted, vote_type='like')
            if index < 2:
                BuildVote.objects.create(user=voter, build=voted,
                                         vote_type='favorite')
        featured = _score_featured_builds('dofus3')
        self.assertEqual(['voted', 'viewed'], [b['name'] for b in featured])
        self.assertEqual((3, 2, 40), (featured[0]['like_count'],
                                      featured[0]['favorite_count'],
                                      featured[0]['view_count']))

    def test_the_query_count_does_not_grow_with_the_builds(self):
        self._shared('current', '3.7.0.4', views=1)
        with CaptureQueriesContext(connection) as few:
            _score_featured_builds('dofus3')
        for index in range(12):
            self._shared('more%d' % index, '3.7.0.4' if index % 2 else '3.6.11.15',
                         views=index)
        with CaptureQueriesContext(connection) as many:
            featured = _score_featured_builds('dofus3')
        self.assertEqual(FEATURED_BUILDS_COUNT, len(featured))
        self.assertEqual(len(few), len(many))
        self.assertLessEqual(len(many), 3)


@override_settings(SITE_VERSIONS=VERSIONS)
class TheHomeSectionReadsPopularTests(_Featured, TestCase):

    def _home(self, path='/', language='en'):
        page = self.client.get(path, HTTP_ACCEPT_LANGUAGE=language)
        self.assertEqual(200, page.status_code)
        return page.content.decode('utf-8')

    def test_the_heading_reads_popular_in_english_and_french(self):
        self._shared('current', '3.7.0.4')
        english = self._home()
        self.assertIn('Popular community builds', english)
        self.assertNotIn('Top community builds', english)
        french = self._home('/fr/', 'fr')
        self.assertIn('Builds populaires de la communauté', french)
        self.assertNotIn('Meilleurs builds', french)

    def _changed_on(self, char, when):
        Char.objects.filter(pk=char.pk).update(solved_time=when, modified_time=when)

    def test_each_card_shows_the_update_of_its_last_change(self):
        self._changed_on(self._shared('current', '3.7.0.4', views=2), LATE)
        self._changed_on(self._shared('previous', '3.6.11.15', views=1), AUGUST)
        with _timeline(UP_TO_THREE_SEVEN):
            page = self._home()
            cards = _cards(page)
            self.assertEqual(2, len(cards))
            self.assertIn('current', cards[0])
            self.assertIn('previous', cards[1])
            self.assertEqual([('3.7', TITLE, False),
                              ('3.6', OLDER_TITLE % '3.7', True)], _badges(page))
            self.assertNotIn('Solved', ' '.join(cards))
            cache.clear()
            self.assertEqual('Mise à jour du jeu au dernier changement du build',
                             _badges(self._home('/fr/', 'fr'))[0][1])

    def test_the_section_is_hidden_when_nothing_qualifies(self):
        self._shared('unsolved', '', views=50)
        self._shared('nosolution', '3.7.0.4', views=50, minimal_solution=b'')
        page = self._home()
        self.assertEqual([], _cards(page))
        self.assertNotIn('Popular community builds', page)

    def test_a_new_update_is_not_served_from_the_old_entry(self):
        self._changed_on(self._shared('onthree', '3.7.0.4', views=50), LATE)
        with _timeline(UP_TO_THREE_SEVEN):
            self.assertEqual([('3.7', TITLE, False)], _badges(self._home()))
        self._changed_on(self._shared('onfour', '3.8.0.0', views=1),
                         datetime(2026, 9, 20, 10, 0, tzinfo=utc_zone.utc))
        with _timeline(UP_TO_THREE_EIGHT), \
                self.settings(SITE_VERSIONS=dict(VERSIONS, dofus3='3.8.0.0')):
            page = self._home()
        cards = _cards(page)
        self.assertEqual(2, len(cards))
        self.assertIn('onfour', cards[0])
        self.assertEqual([('3.8', TITLE, False),
                          ('3.7', OLDER_TITLE % '3.8', True)], _badges(page))


@override_settings(SITE_VERSIONS=dict(settings.SITE_VERSIONS, dofus3='3.6.11.15'))
class ABuildUpdatedDuringTheCurrentUpdateCountsTests(_Featured, TestCase):

    def setUp(self):
        super().setUp()
        patcher = _timeline([('2025-12-09', '3.4'), ('2026-03-05', '3.5'),
                             ('2026-06-23', '3.6')])
        patcher.start()
        self.addCleanup(patcher.stop)

    def _left_on(self, name, when, views=50):
        left = self._shared(name, '', views=views)
        Char.objects.filter(pk=left.pk).update(modified_time=when)
        return left

    def test_an_unstamped_build_updated_since_the_update_started_is_current(self):
        self._shared('previous', '3.5.17.26', views=50)
        self._shared('updated', '', views=1)
        self.assertEqual(['updated', 'previous'], self._featured())

    def test_an_unstamped_build_left_during_the_previous_update_completes_the_row(self):
        self._shared('current', '3.6.11.15', views=1)
        self._left_on('previous', datetime(2026, 5, 1, 12, 0, tzinfo=utc_zone.utc))
        self._left_on('lastday', datetime(2026, 6, 22, 23, 0, tzinfo=utc_zone.utc),
                      views=40)
        self.assertEqual(['current', 'previous', 'lastday'], self._featured())

    def test_an_unstamped_build_left_before_the_previous_update_is_not_featured(self):
        self._left_on('older', datetime(2026, 3, 4, 23, 0, tzinfo=utc_zone.utc))
        self.assertEqual([], self._featured())

    def test_an_unstamped_card_shows_the_update_of_its_last_change(self):
        self._shared('updated', '', views=2)
        self._left_on('previous', datetime(2026, 5, 1, 12, 0, tzinfo=utc_zone.utc),
                      views=1)
        page = self.client.get('/', HTTP_ACCEPT_LANGUAGE='en').content.decode('utf-8')
        self.assertEqual(2, len(_cards(page)))
        self.assertEqual([('3.6', TITLE, False), ('3.5', OLDER_TITLE % '3.6', True)],
                         _badges(page))
        for word in ('Solved', 'around', 'Estimated'):
            self.assertNotIn(word, ' '.join(_cards(page)))
        cache.clear()
        french = self.client.get('/fr/', HTTP_ACCEPT_LANGUAGE='fr').content.decode('utf-8')
        self.assertEqual('Mise à jour du jeu au dernier changement du build ; '
                         'le jeu est maintenant en 3.6', _badges(french)[1][1])
