# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A /setup/ option group changes the new build only when its marker is posted, and then stores what the wizard would store."""
from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase

from chardata.char_blobs import read_char_blob
from chardata.create_project_view import create_project
from chardata.lock_forbid import get_all_exclusions_ids, get_default_exclusions
from chardata.models import Char, CharBaseStats, InventoryFolder
from chardata.options import DOFUS_OPTIONS, get_available_options
from chardata.tests_every_preset_keeps_its_weights_and_minimums import VERSIONS
from chardata.tests_the_hand_door_saves_no_minimum_as_the_setup_panel_says import one_element_box
from chardata.tests_the_setup_creation_doors_support import door_fields
from chardata.tests_the_setup_preview_matches_the_build_the_door_creates import classes_of
from chardata.wizard_view import HUNDRED, wizard_post
from fashionistapulp.dofus_constants import max_scroll_for_version
from fashionistapulp.structure import get_structure, set_current_game_version

GROUPS = ('exos', 'mounts', 'dofus', 'scrolls', 'points')


def markers(*groups):
    return [('setup_options', group) for group in groups]


def contrary_fields(version):
    """Every option field set against what a new build starts with: one Dofus kept, the rest left unchecked."""
    set_current_game_version(version)
    available = get_available_options()
    if available['exo_per_item']:
        fields = [('ap_exo', '0'), ('mp_exo', '2'), ('range_exo', '1')]
    else:
        fields = [('ap_exo', 'no'), ('mp_exo', 'gelano' if available['gelano'] else 'no'),
                  ('range_exo', 'yes')]
    fields += [(entry['key'], 'on') for entry in available['dofuses'][:1]]
    return fields + [('scrolling', 'clean')]


def group_option_keys(version):
    set_current_game_version(version)
    available = get_available_options()
    keys = ['ap_exo', 'mp_exo', 'range_exo']
    keys += [name for name in ('dragoturkey', 'seemyool', 'rhineetle', 'prysmaradite', 'trophies')
             if available.get(name)]
    return keys


class _Creations(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user('setup-more', 'more@test.local', 'pw-setup-more-5')

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')

    def request(self, version, fields, user=None):
        set_current_game_version(version)
        data = {}
        for key, value in fields:
            data.setdefault(key, []).append(value)
        request = RequestFactory().post('/', data)
        request.user = user or self.owner
        request.game_version = version
        return request

    def create(self, version, extra=(), level=200):
        char_class = sorted(classes_of(version))[0]
        fields = door_fields('optimize', char_class, level, one_element_box(version)) + list(extra)
        response = create_project(self.request(version, fields))
        self.assertEqual(302, response.status_code)
        set_current_game_version(version)
        return Char.objects.order_by('-id').first()

    def stored(self, char):
        set_current_game_version(char.game_version)
        char = Char.objects.get(pk=char.pk)
        return {'options': read_char_blob(char.options, {}, 'options', char),
                'excluded': sorted(get_all_exclusions_ids(char)),
                'distribution': char.allow_points_distribution,
                'scrolls': sorted(CharBaseStats.objects.filter(char=char)
                                  .values_list('stat', 'scrolled_value', 'total_value'))}


class AGroupWithoutItsMarkerChangesNothingTests(_Creations):

    def test_option_fields_posted_without_a_marker_store_the_build_of_today(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                today = self.stored(self.create(version))
                posted = self.stored(self.create(version, contrary_fields(version)))
                self.assertEqual(today, posted)

    def test_an_unknown_group_name_changes_nothing(self):
        today = self.stored(self.create('dofus3'))
        posted = self.stored(self.create('dofus3', contrary_fields('dofus3') + markers('everything')))
        self.assertEqual(today, posted)


class AMarkedGroupIsStoredAsTheWizardStoresItTests(_Creations):

    def test_every_marked_group_stores_the_options_exclusions_and_scrolls_the_wizard_stores(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                fields = contrary_fields(version)
                from_setup = self.stored(self.create(version, fields + markers(*GROUPS)))
                plain = self.create(version)
                response = wizard_post(self.request(version, fields), plain.pk)
                self.assertEqual(302, response.status_code)
                from_wizard = self.stored(plain)
                keys = group_option_keys(version)
                self.assertEqual({key: from_wizard['options'].get(key) for key in keys},
                                 {key: from_setup['options'].get(key) for key in keys})
                self.assertEqual(from_wizard['excluded'], from_setup['excluded'])
                self.assertEqual(from_wizard['scrolls'], from_setup['scrolls'])
                self.assertNotEqual(self.stored(self.create(version))['excluded'],
                                    from_setup['excluded'])

    def test_a_marked_group_leaves_the_other_groups_as_a_new_build_has_them(self):
        today = self.stored(self.create('dofus3'))
        exos_only = self.stored(self.create('dofus3', contrary_fields('dofus3') + markers('exos')))
        self.assertEqual(today['excluded'], exos_only['excluded'])
        self.assertEqual(today['scrolls'], exos_only['scrolls'])
        self.assertTrue(exos_only['distribution'])
        for key in ('dragoturkey', 'seemyool', 'rhineetle', 'prysmaradite'):
            self.assertEqual(today['options'].get(key), exos_only['options'].get(key), key)
        self.assertEqual((False, 'gelano', True), tuple(exos_only['options'][key]
                                                        for key in ('ap_exo', 'mp_exo', 'range_exo')))

    def test_a_mount_the_version_does_not_offer_keeps_the_value_a_new_build_has(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                set_current_game_version(version)
                missing = [name for name in ('dragoturkey', 'seemyool', 'rhineetle')
                           if not get_available_options().get(name)]
                today = self.stored(self.create(version))['options']
                posted = self.stored(self.create(version, markers('mounts')))['options']
                for name in missing:
                    self.assertEqual(today.get(name), posted.get(name), name)


class TheDofusGroupLeavesADofusAboveTheLevelAloneTests(_Creations):

    def test_an_unchecked_dofus_above_the_level_keeps_the_exclusion_a_new_build_has(self):
        level = 100
        char = self.create('dofus3', markers('dofus'), level=level)
        set_current_game_version('dofus3')
        structure = get_structure()
        excluded = set(self.stored(char)['excluded'])
        default = set(get_default_exclusions(char))
        checked = []
        for key, name in sorted(DOFUS_OPTIONS.items()):
            item = structure.get_item_by_name(name)
            if item is None:
                continue
            expected = item.id in default if item.level > level else True
            checked.append(item.level > level)
            self.assertEqual(expected, item.id in excluded, (key, item.level))
        self.assertIn(True, checked)
        self.assertIn(False, checked)


class TheScrollChoiceSetsEveryCharacteristicTests(_Creations):

    def scrolled(self, version, choice, level=200, marked=True):
        extra = [('scrolling', choice)] + (markers('scrolls') if marked else [])
        rows = self.stored(self.create(version, extra, level=level))['scrolls']
        self.assertTrue(rows)
        return {(scrolled, total) for _stat, scrolled, total in rows}

    def test_none_hundred_and_full_scroll_every_characteristic_on_every_version(self):
        for version in VERSIONS:
            for level in (150, 200):
                with self.subTest(version=version, level=level):
                    full = max_scroll_for_version(version, level)
                    self.assertEqual({(0, 0)}, self.scrolled(version, 'clean', level))
                    hundred = min(HUNDRED, full)
                    self.assertEqual({(hundred, hundred)}, self.scrolled(version, 'hundred', level))
                    self.assertEqual({(full, full)}, self.scrolled(version, 'fully', level))
                    self.assertEqual({(full, full)}, self.scrolled(version, 'clean', level, False))

    def test_touch_at_level_200_scrolls_to_100_below_its_ceiling(self):
        self.assertGreater(max_scroll_for_version('touch', 200), HUNDRED)
        self.assertEqual({(HUNDRED, HUNDRED)}, self.scrolled('touch', 'hundred'))


class ThePointsBoxDecidesWhoDistributesThePointsTests(_Creations):

    def test_an_unchecked_box_lets_the_player_distribute_and_a_checked_one_does_not(self):
        self.assertFalse(self.stored(self.create('dofus3', markers('points')))['distribution'])
        self.assertTrue(self.stored(self.create(
            'dofus3', markers('points') + [('choose_stats', 'choose_stats')]))['distribution'])
        self.assertTrue(self.stored(self.create('dofus3'))['distribution'])


class AnUncheckedPointsBoxOpensTheCharacteristicsPageBeforeAnySolveTests(_Creations):

    def door(self, door, extra):
        char_class = sorted(classes_of('dofus3'))[0]
        fields = door_fields(door, char_class, 200, one_element_box('dofus3')) + list(extra)
        response = create_project(self.request('dofus3', fields))
        self.assertEqual(302, response.status_code)
        return response['Location'], Char.objects.order_by('-id').first()

    def test_the_optimize_and_wizard_doors_open_the_characteristics_page_when_the_player_places_the_points(self):
        for door in ('optimize', 'wizard'):
            with self.subTest(door=door):
                location, char = self.door(door, markers('points'))
                self.assertFalse(char.allow_points_distribution)
                self.assertIn('/initbasestats/%d/' % char.pk, location)

    def test_a_checked_box_or_the_hand_door_goes_where_it_always_went(self):
        checked = markers('points') + [('choose_stats', 'choose_stats')]
        for door, extra, path in (('optimize', checked, '/solution/%d/'),
                                  ('wizard', checked, '/wizard/%d/'),
                                  ('optimize', [], '/solution/%d/'),
                                  ('byhand', markers('points'), '/solution/%d/')):
            with self.subTest(door=door, extra=extra):
                location, char = self.door(door, extra)
                self.assertIn(path % char.pk, location)


class TheItemSourceIsStoredOnlyForTheOwnFolderTests(_Creations):

    def test_an_own_folder_is_stored_with_its_mode(self):
        folder = InventoryFolder.objects.create(user=self.owner, name='mine', game_version='dofus3')
        options = self.stored(self.create('dofus3', markers('inventory') + [
            ('inventory_mode', 'mixed'), ('inventory_folder', str(folder.id))]))['options']
        self.assertEqual(('mixed', folder.id),
                         (options.get('inventory_mode'), options.get('inventory_folder')))

    def test_a_folder_of_another_player_falls_back_to_the_encyclopedia(self):
        other = User.objects.create_user('setup-more-other', 'other@test.local', 'pw-other-5')
        folder = InventoryFolder.objects.create(user=other, name='theirs', game_version='dofus3')
        options = self.stored(self.create('dofus3', markers('inventory') + [
            ('inventory_mode', 'only'), ('inventory_folder', str(folder.id))]))['options']
        self.assertEqual(('all', None),
                         (options.get('inventory_mode'), options.get('inventory_folder')))

    def test_without_the_marker_the_folder_is_not_stored(self):
        folder = InventoryFolder.objects.create(user=self.owner, name='mine', game_version='dofus3')
        options = self.stored(self.create('dofus3', [
            ('inventory_mode', 'only'), ('inventory_folder', str(folder.id))]))['options']
        self.assertNotIn('inventory_folder', options)
