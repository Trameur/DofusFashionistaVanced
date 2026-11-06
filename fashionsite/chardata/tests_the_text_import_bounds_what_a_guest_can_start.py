"""A pasted text gets a bounded number of closest-name searches, and a guest's imports are capped per session and per address."""
import string
from unittest import mock

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase

from chardata import text_build_import, text_build_view
from chardata.text_build_import import MAX_CLOSEST_NAME_SEARCHES, read_items
from fashionistapulp.structure import (get_current_game_version,
                                       get_structure, set_current_game_version)

BROWSER = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Firefox/120.0'
THROTTLED = 'Too many checks from your address. Wait a few minutes.'


def _junk(count):
    letters = string.ascii_lowercase
    return ['qzxjkw' + letters[i % 26] + letters[(i // 26) % 26] for i in range(count)]


class TheClosestNameSearchIsBounded(SimpleTestCase):

    def setUp(self):
        previous = get_current_game_version()
        set_current_game_version('dofus3')
        self.addCleanup(set_current_game_version, previous)

    def test_lines_past_the_ceiling_are_reported_as_ignored_without_a_search(self):
        lines = _junk(MAX_CLOSEST_NAME_SEARCHES + 20)
        with mock.patch.object(text_build_import, '_closest_pool_entry',
                               wraps=text_build_import._closest_pool_entry) as spy:
            read = read_items('\n'.join(lines), 'dofus3', 'en')
        self.assertEqual(MAX_CLOSEST_NAME_SEARCHES, spy.call_count)
        self.assertEqual(lines, read['ignored'])

    def test_an_exact_name_after_many_unreadable_lines_is_still_read(self):
        structure = get_structure('dofus3')
        item = next(i for i in structure.types[200]['Hat'] if not i.removed)
        name = structure.get_item_name_in_language(item, 'en')
        lines = _junk(MAX_CLOSEST_NAME_SEARCHES + 20) + [name]
        read = read_items('\n'.join(lines), 'dofus3', 'en')
        self.assertEqual([name], [m['name'] for m in read['matched']])


class AGuestsImportsAreCapped(TestCase):

    def post(self, client=None, **extra):
        return (client or self.client).post(
            '/import/text/', {'text': 'some words that are not an item'},
            HTTP_USER_AGENT=BROWSER, **extra)

    def test_the_address_ceiling_stops_a_guest(self):
        with mock.patch.object(text_build_view, 'IMPORT_POSTS_PER_ADDRESS', 3):
            answers = [self.post().content.decode('utf-8') for _ in range(4)]
        self.assertTrue(all(THROTTLED not in a for a in answers[:3]))
        self.assertIn(THROTTLED, answers[3])

    def test_the_session_ceiling_stops_a_guest_who_changes_address(self):
        self.client.cookies['csrftoken'] = 'a' * 32
        with mock.patch.object(text_build_view, 'IMPORT_POSTS_PER_SESSION', 2):
            answers = [self.post(REMOTE_ADDR='10.0.0.%d' % i).content.decode('utf-8')
                       for i in range(3)]
        self.assertTrue(all(THROTTLED not in a for a in answers[:2]))
        self.assertIn(THROTTLED, answers[2])

    def test_a_signed_in_player_is_not_counted(self):
        self.client.force_login(User.objects.create_user('reader', 'r@x.test', 'pw'))
        with mock.patch.object(text_build_view, 'IMPORT_POSTS_PER_ADDRESS', 1):
            answers = [self.post().content.decode('utf-8') for _ in range(3)]
        self.assertTrue(all(THROTTLED not in a for a in answers))
