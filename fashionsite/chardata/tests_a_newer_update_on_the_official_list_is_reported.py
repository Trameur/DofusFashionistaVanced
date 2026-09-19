# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The version watch reads the newest update of each official list and reports one ahead of the labels."""
import contextlib
import io
import urllib.error
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase

from chardata.tests import itemscraper_module

REPO_ROOT = Path(__file__).resolve().parents[2]
check = itemscraper_module('check_game_versions')


def _page(main_entries, aside_entries):
    return (
        '<html><body><div class="breadcrumb">'
        '<a href="/fr/mmorpg/actualites" itemprop="item">'
        '<span itemprop="name">Actualités</span></a></div>'
        '<div class="container ak-main-container"><div class="row ">'
        '<main class="main col-md-9"><div class="ak-list-paginated">'
        '<div class="ak-item-list">' + ''.join(main_entries) + '</div></div>'
        '</main><aside class="col-md-3"><div class="ak-panel-title">Correctifs</div>'
        '<div class="ak-item-list ak-content-list">' + ''.join(aside_entries)
        + '</div></aside></div></div></body></html>')


def _highlight(href, day, title):
    return (
        '<div class="ak-item-elt-content ak-patchnote-highlight ak-highlight">'
        '<div class="ak-highlight-title">'
        '<a class="ak-btn-discover" href="%s">Découvrir</a>'
        '<a class="ak-link-text" href="%s">\n        <span>%s :</span>\n'
        '        %s      </a></div></div>' % (href, href, day, title))


def _tiny(href, number, title, day):
    return (
        '<div class="ak-item-elt-tiny"><div class="ak-item-elt-title">'
        '<a href="%s"><span class="ak-img"><img src="x.jpg" alt="%s"></span></a>'
        '<span class="ak-text"><a href="%s">\n'
        '            <span>MÀJ %s : </span>%s          </a> - '
        '<span class="ak-publication">%s</span></span></div></div>'
        % (href, title, href, number, title, day))


def _correctif(href, prefix, title):
    return (
        '<div class="ak-list-element"><div class="ak-title"><a href="%s">\n'
        '                        <span>%s</span>%s                    </a>'
        '</div></div>' % (href, prefix, title))


TOUCH_SOURCE = '/fr/mmorpg/actualites/maj/1771461-source'
TOUCH_DEDALE = _tiny('/fr/mmorpg/actualites/maj/1770579-dedale', '1.73',
                     'Le Dédale', '30 Juin 2026')
TOUCH_ASIDE = [
    _correctif(TOUCH_SOURCE + '/correctifs/1771831-mise-jour-1-74-4-modifications-apportees',
               'MÀJ 1.74 - ', 'Mise à jour 1.74.4 : modifications apportées'),
    _correctif('/fr/mmorpg/actualites/maj/1770579-dedale/correctifs/'
               '1771569-mise-jour-1-73-12-modifications-apportees',
               'MÀJ 1.73 - ', 'Mise à jour 1.73.12 : modifications apportées'),
]
TOUCH_PAGE = _page(
    [_highlight(TOUCH_SOURCE, '08 Août 2026', 'MÀJ 1.74 - La Source'),
     TOUCH_DEDALE,
     _tiny('/fr/mmorpg/actualites/maj/1768368-duo-choc', '1.72', 'Duo de choc',
           '07 Avril 2026')],
    TOUCH_ASIDE)

RETRO_CONNAISSANCES = '/fr/mmorpg/actualites/maj/1771256-partez-quete-connaissances'
RETRO_PAGE = _page(
    [_highlight(RETRO_CONNAISSANCES, '18 Août 2026',
                'MÀJ 1.49 - Partez en Quête de Connaissances !'),
     _tiny('/fr/mmorpg/actualites/maj/1767862-quete-succes', '1.48',
           'En quête de succès', '25 Février 2026')],
    [_correctif(RETRO_CONNAISSANCES + '/correctifs/1771791-patch-notes-1-49-4-15-09-2026',
                'MÀJ  - ', 'Patch notes 1.49.4 du 15/09/2026')])

DOFUS3_RAID = '/fr/mmorpg/actualites/maj/1770516-raid-not-dead'
DOFUS3_PAGE = _page(
    [_highlight(DOFUS3_RAID, '23 Juin 2026', 'MÀJ 3.6 - Raid is not dead'),
     _tiny('/fr/mmorpg/actualites/maj/1768057-repos-braves', '3.5',
           'Pas de repos pour les braves', '03 Mars 2026')],
    [_correctif(DOFUS3_RAID + '/correctifs/1771654-patch-notes-3-6-11-08-09-2026',
                'MÀJ - ', 'Patch notes 3.6.11 du 08/09/2026'),
     _correctif(DOFUS3_RAID + '/correctifs/1770949-patch-notes-3-6-6-5-07-07-2026',
                'MÀJ 3.6 - ', 'Patch Notes 3.6.6.5 du 07/07/2026')])

AT_OUR_PATCHES = {'dofus3': ('3.6', '3.6'), 'retro': ('1.49', '1.49'),
                  'touch': ('1.74', '1.74')}


def _quiet(call, *args):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        result = call(*args)
    return result, out.getvalue()


class TheNewestUpdateIsReadFromTheUpdateListTests(SimpleTestCase):

    def test_touch_reads_la_source(self):
        self.assertEqual(('1.74', TOUCH_SOURCE), check.newest_update(TOUCH_PAGE))

    def test_retro_reads_its_1_49(self):
        self.assertEqual(('1.49', RETRO_CONNAISSANCES), check.newest_update(RETRO_PAGE))

    def test_dofus3_reads_3_6_while_the_3_7_beta_runs(self):
        self.assertEqual(('3.6', DOFUS3_RAID), check.newest_update(DOFUS3_PAGE))

    def test_the_correctifs_panel_is_never_read_as_an_update(self):
        page = _page([TOUCH_DEDALE], TOUCH_ASIDE)
        self.assertEqual('1.73', check.newest_update(page)[0])
        self.assertIsNone(check.newest_update(_page([], TOUCH_ASIDE)))

    def test_the_highest_number_wins_whatever_the_order(self):
        page = _page([TOUCH_DEDALE, _highlight(TOUCH_SOURCE, '08 Août 2026',
                                               'MÀJ 1.74 - La Source')], [])
        self.assertEqual('1.74', check.newest_update(page)[0])

    def test_a_page_without_the_list_reads_nothing(self):
        for html in ('', '<html><head><title>Un instant...</title></head></html>'):
            with self.subTest(html=html):
                self.assertIsNone(check.newest_update(html))

    def test_the_watch_fetches_the_update_lists_not_the_correctifs(self):
        asked = []

        def fetch(url):
            asked.append(url)
            return TOUCH_PAGE
        with mock.patch.object(check, 'fetch_update_list', fetch):
            self.assertEqual(('1.74', TOUCH_SOURCE), check.read_update_list('touch'))
        self.assertEqual(['https://www.dofus-touch.com/fr/mmorpg/actualites/maj'], asked)
        for url in check.UPDATE_LISTS.values():
            with self.subTest(url=url):
                self.assertTrue(url.endswith('/fr/mmorpg/actualites/maj'))


class ANewerUpdateIsReportedTests(SimpleTestCase):

    def test_touch_1_74_against_labels_at_1_73_is_behind(self):
        self.assertEqual({'touch': ('1.74', '1.73', '1.73')},
                         check.updates_behind({'touch': '1.74'},
                                              {'touch': ('1.73', '1.73')}))

    def test_a_label_moved_without_patch_started_is_still_behind(self):
        self.assertEqual({'retro': ('1.49', '1.49', '1.48')},
                         check.updates_behind({'retro': '1.49'},
                                              {'retro': ('1.49', '1.48')}))

    def test_a_list_at_or_below_our_patch_is_not_behind(self):
        self.assertEqual({}, check.updates_behind(
            {'dofus3': '3.6', 'retro': '1.49', 'touch': '1.74'}, AT_OUR_PATCHES))
        self.assertEqual({}, check.updates_behind({'dofus3': '3.5'}, AT_OUR_PATCHES))

    def test_patch_numbers_compare_as_numbers(self):
        self.assertIn('touch', check.updates_behind({'touch': '1.100'},
                                                    {'touch': ('1.99', '1.99')}))
        self.assertEqual({}, check.updates_behind({'touch': '1.9'},
                                                  {'touch': ('1.10', '1.10')}))

    def test_our_patches_come_from_the_labels_and_patch_started(self):
        import fashionista_version as ours
        mine = check.our_patches()
        self.assertEqual(set(check.UPDATE_LISTS), set(mine))
        self.assertEqual(ours.PATCH_STARTED['touch'][0], mine['touch'][1])
        self.assertTrue(ours.FASHIONISTA_VERSION.startswith(mine['dofus3'][0] + '.'))

    def test_a_newer_update_is_printed_and_flagged_but_never_written(self):
        version_file = REPO_ROOT / 'fashionista_version.py'
        before = version_file.read_bytes()
        pages = {'dofus3': DOFUS3_PAGE, 'retro': RETRO_PAGE,
                 'touch': TOUCH_PAGE.replace('1.74 - La Source', '1.75 - La Suite')}
        with mock.patch.object(check, 'our_patches', lambda: dict(AT_OUR_PATCHES)), \
                mock.patch.object(check, 'read_update_list',
                                  lambda key: check.newest_update(pages[key])):
            flagged, printed = _quiet(check.check_update_lists)
        self.assertEqual([('touch update', '1.75')], flagged)
        self.assertIn('NEWER', printed)
        self.assertIn('update_data_touch.py', printed)
        self.assertEqual(before, version_file.read_bytes())

    def test_lists_at_our_patches_flag_nothing(self):
        pages = {'dofus3': DOFUS3_PAGE, 'retro': RETRO_PAGE, 'touch': TOUCH_PAGE}
        with mock.patch.object(check, 'our_patches', lambda: dict(AT_OUR_PATCHES)), \
                mock.patch.object(check, 'read_update_list',
                                  lambda key: check.newest_update(pages[key])):
            flagged, printed = _quiet(check.check_update_lists)
        self.assertEqual([], flagged)
        self.assertNotIn('NEWER', printed)

    def test_an_unreadable_list_is_flagged_not_skipped(self):
        def read(key):
            if key == 'dofus3':
                raise urllib.error.HTTPError(check.UPDATE_LISTS[key], 403,
                                             'Forbidden', {}, None)
            if key == 'retro':
                return check.newest_update('')
            return check.newest_update(TOUCH_PAGE)
        with mock.patch.object(check, 'our_patches', lambda: dict(AT_OUR_PATCHES)), \
                mock.patch.object(check, 'read_update_list', read):
            flagged, printed = _quiet(check.check_update_lists)
        self.assertEqual([('dofus3 update list', 'unreadable'),
                          ('retro update list', 'unreadable')], flagged)
        self.assertIn('403', printed)
        self.assertIn('--updates dofus3=x.y', printed)

    def test_numbers_read_in_a_browser_go_through_the_same_comparison(self):
        with mock.patch.object(check, 'our_patches', lambda: dict(AT_OUR_PATCHES)):
            self.assertEqual(1, _quiet(check.main, ['--updates', 'touch=1.75'])[0])
            self.assertEqual(0, _quiet(check.main, ['--updates', 'touch=1.74',
                                                    'retro=1.49', 'dofus3=3.6'])[0])
            self.assertEqual(2, _quiet(check.main, ['--updates', 'beta=3.7'])[0])
            self.assertEqual(2, _quiet(check.main, ['--updates', 'touch=1.74.4'])[0])
            self.assertEqual(2, _quiet(check.main, ['--updates'])[0])
