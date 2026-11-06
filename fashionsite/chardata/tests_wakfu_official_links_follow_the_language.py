import os

from django.test import SimpleTestCase

from chardata import wakfu_encyclopedia_data as data
from chardata import wakfu_official_links as links

SECTION_WORDS = {
    'armor': {'fr': 'fr/mmorpg/encyclopedie/armures', 'en': 'en/mmorpg/encyclopedia/armors',
              'es': 'es/mmorpg/enciclopedia/armaduras', 'pt': 'pt/mmorpg/enciclopedia/armaduras'},
    'weapon': {'fr': 'fr/mmorpg/encyclopedie/armes', 'en': 'en/mmorpg/encyclopedia/weapons',
               'es': 'es/mmorpg/enciclopedia/armas', 'pt': 'pt/mmorpg/enciclopedia/armas'},
    'accessory': {'fr': 'fr/mmorpg/encyclopedie/accessoires',
                  'en': 'en/mmorpg/encyclopedia/accessories',
                  'es': 'es/mmorpg/enciclopedia/accesorios',
                  'pt': 'pt/mmorpg/enciclopedia/acessorios'},
}
NO_SECTION_NAMES = ('Torch', 'Tool', 'Pet', 'Mount')


class WakfuOfficialLinksFollowTheLanguageTests(SimpleTestCase):
    """An item links its page on the official encyclopedia in the page language."""

    def setUp(self):
        if not os.path.exists(data.database_path()):
            self.skipTest('no Wakfu database built; run update_data_wakfu.py')
        self.conn = data.connect()
        self.addCleanup(self.conn.close)
        self.weapons = links.weapon_types(self.conn)

    def type_with(self, position):
        row = self.conn.execute(
            'SELECT p.item_type FROM item_type_position p JOIN items i ON i.type = p.item_type'
            ' WHERE p.position = ? AND i.removed = 0 ORDER BY p.item_type', (position,)).fetchone()
        return row[0]

    def item_of_type(self, item_type):
        return self.conn.execute(
            'SELECT id FROM items WHERE removed = 0 AND type = ? ORDER BY id',
            (item_type,)).fetchone()[0]

    def test_the_weapon_types_are_the_types_placed_in_a_weapon_hand(self):
        expected = {row[0] for row in self.conn.execute(
            "SELECT item_type FROM item_type_position WHERE position IN"
            " ('FIRST_WEAPON', 'SECOND_WEAPON')")}
        self.assertEqual(expected, set(self.weapons))
        self.assertTrue(self.weapons)

    def test_a_neck_item_links_the_armor_section_in_each_language(self):
        item_type = self.type_with('NECK')
        item = self.item_of_type(item_type)
        for language in ('fr', 'en', 'es', 'pt'):
            self.assertEqual(
                'https://www.wakfu.com/%s/%d' % (SECTION_WORDS['armor'][language], item),
                links.item_link(item, item_type, language, self.weapons))

    def test_a_weapon_links_the_weapon_section_in_each_language(self):
        item_type = self.type_with('FIRST_WEAPON')
        item = self.item_of_type(item_type)
        for language in ('fr', 'en', 'es', 'pt'):
            self.assertEqual(
                'https://www.wakfu.com/%s/%d' % (SECTION_WORDS['weapon'][language], item),
                links.item_link(item, item_type, language, self.weapons))

    def test_an_accessory_links_the_accessory_section_in_each_language(self):
        item_type = 646
        self.assertEqual('ACCESSORY', self.conn.execute(
            'SELECT position FROM item_type_position WHERE item_type = ?',
            (item_type,)).fetchone()[0])
        item = self.item_of_type(item_type)
        for language in ('fr', 'en', 'es', 'pt'):
            self.assertEqual(
                'https://www.wakfu.com/%s/%d' % (SECTION_WORDS['accessory'][language], item),
                links.item_link(item, item_type, language, self.weapons))

    def test_german_links_the_english_page(self):
        item_type = self.type_with('NECK')
        item = self.item_of_type(item_type)
        self.assertEqual(links.item_link(item, item_type, 'en', self.weapons),
                         links.item_link(item, item_type, 'de', self.weapons))

    def test_a_torch_a_tool_a_pet_and_a_mount_have_no_link(self):
        names = {}
        for item_type, in self.conn.execute(
                'SELECT DISTINCT type FROM items WHERE removed = 0'):
            row = self.conn.execute(
                "SELECT name FROM client_item_type_names WHERE item_type = ? AND language = 'en'",
                (item_type,)).fetchone()
            names[item_type] = row[0] if row else ''
        found = {}
        for item_type, name in names.items():
            for word in NO_SECTION_NAMES:
                if name.startswith(word):
                    found[word] = item_type
        self.assertEqual(set(NO_SECTION_NAMES), set(found), names)
        for item_type in found.values():
            item = self.item_of_type(item_type)
            for language in ('fr', 'en', 'es', 'pt', 'de'):
                self.assertIsNone(links.item_link(item, item_type, language, self.weapons))

    def test_every_live_item_type_is_either_linked_or_named_among_the_unlinked(self):
        unlinked = set()
        for item_type, in self.conn.execute('SELECT DISTINCT type FROM items WHERE removed = 0'):
            item = self.item_of_type(item_type)
            if links.item_link(item, item_type, 'en', self.weapons) is None:
                unlinked.add(item_type)
        self.assertEqual({480, 537, 582, 611}, unlinked)
