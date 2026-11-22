# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The resource picker lists every resource a recipe uses, once per label in the reader's language, and the page hands it to the template."""
from django.contrib.auth.models import User
from django.test import TestCase

from chardata import resource_ban
from chardata.models import Char
from fashionistapulp.structure import set_current_game_version

CRIMSON_PEBBLE = '12737:resources'


class ThePickerIndexTests(TestCase):

    def test_every_entry_is_a_known_key_with_a_count_and_an_icon_flag(self):
        known = resource_ban._items_by_resource('dofus3')

        picker = resource_ban.picker_index('dofus3', 'en')

        self.assertTrue(picker)
        for label, (key, count, has_icon) in picker.items():
            self.assertIn(key, known)
            self.assertEqual(len(known[key]), count)
            self.assertIsInstance(has_icon, bool)
        self.assertEqual(len(picker), len({entry[0] for entry in picker.values()}))
        self.assertEqual(CRIMSON_PEBBLE, picker['Crimson Pebble'][0])

    def test_the_labels_are_in_the_readers_language(self):
        english = {entry[0]: label for label, entry in resource_ban.picker_index('dofus3', 'en').items()}
        french = {entry[0]: label for label, entry in resource_ban.picker_index('dofus3', 'fr').items()}

        self.assertNotEqual(english[CRIMSON_PEBBLE], french[CRIMSON_PEBBLE])

    def test_two_resources_sharing_a_name_are_told_apart_by_their_id(self):
        picker = resource_ban.picker_index('retro', 'pt')
        keys = [entry[0] for entry in picker.values()]

        self.assertEqual(len(keys), len(set(keys)))
        told_apart = [label for label in picker if ' (#' in label]
        self.assertTrue(told_apart)
        for label in told_apart:
            self.assertTrue(label.endswith('(#%s)' % picker[label][0].split(':')[0]))


class ThePageEmbedsThePickerTests(TestCase):

    def test_the_page_context_carries_the_picker_and_the_state(self):
        set_current_game_version('dofus3')
        self.addCleanup(set_current_game_version, 'dofus3')
        owner = User.objects.create_user('pickban', 'pk@test.local', 'pw-pick-ban-1')
        char = Char.objects.create(
            name='Pick', char_name='pick', char_class='Iop', char_build='build',
            level=200, minimum_stats=b'', minimum_crits=b'', stats_weight=b'',
            options=b'', inclusions=b'', exclusions=b'', owner=owner,
            link_shared=False, game_version='dofus3')
        self.client.force_login(owner)

        page = self.client.get('/exclusions/%d/' % char.pk)

        self.assertEqual(200, page.status_code)
        self.assertEqual(resource_ban.picker_index('dofus3', 'en'), page.context['resource_picker'])
        self.assertEqual({'items', 'resources', 'total_text'}, set(page.context['exclusions_state']))
