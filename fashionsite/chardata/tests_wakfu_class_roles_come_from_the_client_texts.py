import os
import sqlite3

from django.test import SimpleTestCase

from fashionistapulp import wakfu_presets, wakfu_turn, wakfu_value
from fashionistapulp.wakfu_stats import OUT_OF_COMBAT_CAPS

#: the role ids of breed.role.desc.<breed>.<id> in the client texts of build 1.93.1.62
CLIENT_ROLE_IDS = {
    1: (2, 7, 8), 2: (4, 6, 8), 3: (0, 1, 4), 4: (0, 1, 4), 5: (1, 4, 5), 6: (3, 4, 7),
    7: (0, 3, 8), 8: (0, 2, 4), 9: (0, 4, 7), 10: (3, 6, 8), 11: (2, 4, 5), 12: (2, 3, 5),
    13: (0, 4, 7), 14: (3, 4, 5), 15: (2, 4, 7), 16: (2, 4, 7), 18: (4, 5, 7),
    19: (0, 4, 7),
}
SPECIALTY_WORDS = {
    3: ('Prospecting', 'Prospection'), 4: ('Murderer', 'Assassinat'),
    7: ('Medicine', 'Médecine'), 8: ('Melee', 'Mêlée'),
    9: ('Long Range', 'Distance'), 13: ('Bombs', 'Bombes'),
    19: ('Versatility', 'Polyvalence'),
}
FECA, OSAMODAS, ENUTROF, XELOR, ENIRIPSA, IOP, CRA, SADIDA, ROGUE, ELIOTROPE, HUPPERMAGE = (
    1, 2, 3, 5, 7, 8, 9, 10, 13, 18, 19)
ELEMENTS = wakfu_value.ELEMENTS
LEVEL = 245


class TheClassRolesComeFromTheClientTextsTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from fashionistapulp.fashionista_config import get_items_db_path
        cls.path = get_items_db_path('wakfu')
        cls.conn = None
        if os.path.exists(cls.path):
            cls.conn = sqlite3.connect('file:%s?mode=ro' % cls.path, uri=True)

    @classmethod
    def tearDownClass(cls):
        if cls.conn is not None:
            cls.conn.close()
        super().tearDownClass()

    def setUp(self):
        if self.conn is None:
            self.skipTest('no Wakfu database built; run update_data_wakfu.py')

    def test_eighteen_classes_hold_three_role_ids_each(self):
        found = wakfu_presets.class_roles(self.conn)
        self.assertEqual(CLIENT_ROLE_IDS, {breed: tuple(one.id for one in roles)
                                           for breed, roles in found.items()})
        for breed, roles in found.items():
            for one in roles:
                self.assertEqual('breed.role.desc.%d.%d' % (breed, one.id), one.key)
                self.assertTrue(self.conn.execute(
                    'SELECT 1 FROM client_breed_texts WHERE key = ?', (one.key,)).fetchone())

    def test_the_specialty_words_are_those_of_the_english_and_the_french_texts(self):
        for breed, (english, french) in SPECIALTY_WORDS.items():
            with self.subTest(breed=breed):
                self.assertEqual(english, wakfu_presets.specialty_word(self.conn, breed))
                self.assertEqual(french, wakfu_presets.specialty_word(self.conn, breed, 'fr'))
                known = wakfu_presets.SPECIALTY[english]
                self.assertEqual((english, french), (known.english, known.french))
        for breed in set(CLIENT_ROLE_IDS) - set(SPECIALTY_WORDS):
            self.assertIsNone(wakfu_presets.specialty_word(self.conn, breed))

    def test_every_client_role_id_has_a_meaning(self):
        self.assertEqual({1, 2, 3, 4, 5, 6, 7, 8}, set(wakfu_presets.ROLE_OF_ID))
        self.assertEqual(('hindrance', 'placement'), wakfu_presets.ROLE_OF_ID[7])
        self.assertEqual(('summons',), wakfu_presets.ROLE_OF_ID[6])

    def test_the_official_roles_follow_the_client_role_ids(self):
        expected = {
            FECA: ('tank', 'hindrance', 'placement', 'support'),
            ENUTROF: ('mule', 'hindrance', 'damage'),
            ENIRIPSA: ('heal', 'support'),
            IOP: ('damage', 'tank'),
            CRA: ('damage', 'hindrance', 'placement'),
        }
        for breed, roles in expected.items():
            with self.subTest(breed=breed):
                self.assertEqual(roles, wakfu_presets.official_roles(breed, self.path))

    def test_the_default_reach_comes_from_the_specialty(self):
        self.assertEqual('melee', wakfu_presets.class_reach(IOP, self.path))
        self.assertEqual('distance', wakfu_presets.class_reach(CRA, self.path))
        for breed in (FECA, ENUTROF, ENIRIPSA, HUPPERMAGE):
            self.assertEqual('mixed', wakfu_presets.class_reach(breed, self.path))

    def test_a_class_with_no_role_text_raises(self):
        with self.assertRaises(ValueError):
            wakfu_presets.official_roles(17, self.path)

    def test_every_class_is_offered_a_damage_preset_first_then_its_official_roles(self):
        for breed in CLIENT_ROLE_IDS:
            with self.subTest(breed=breed):
                offered = wakfu_presets.offered(breed, LEVEL, self.path)
                self.assertEqual(wakfu_presets.default_preset(breed, self.path), offered[0])
                self.assertIn(offered[0], wakfu_presets.DAMAGE_PRESETS)
                self.assertEqual(len(offered), len(set(offered)))
                roles = [key for key in offered if key in wakfu_presets.ROLE_PRESETS]
                self.assertEqual(roles, list(offered[1:1 + len(roles)]))
                self.assertEqual(set(wakfu_presets.DAMAGE_PRESETS),
                                 set(offered) & set(wakfu_presets.DAMAGE_PRESETS))

    def test_offered_covers_the_roles_of_the_client_texts_that_the_class_can_read(self):
        for breed in CLIENT_ROLE_IDS:
            offered = wakfu_presets.offered(breed, LEVEL, self.path)
            for name in wakfu_presets.official_roles(breed, self.path):
                preset = wakfu_presets.ROLE_PRESET.get(name)
                defining = wakfu_presets.DEFINING.get(preset, ())
                readable = not defining or any(
                    wakfu_presets.reads(breed, family, LEVEL, self.path) for family in defining)
                if preset is None:
                    continue
                with self.subTest(breed=breed, role=name):
                    self.assertEqual(readable, preset in offered)

    def test_a_control_class_is_offered_the_family_it_can_read_and_no_other(self):
        self.assertEqual(('placement',), self.roles_offered(CRA, 'placement', 'hindrance'))
        self.assertEqual(('hindrance',), self.roles_offered(ROGUE, 'placement', 'hindrance'))
        self.assertEqual((), self.roles_offered(ELIOTROPE, 'placement', 'hindrance'))
        self.assertEqual((), self.roles_offered(XELOR, 'placement', 'hindrance'))
        self.assertEqual(('placement', 'hindrance'),
                         self.roles_offered(FECA, 'placement', 'hindrance'))

    def roles_offered(self, breed, *names, bracket=LEVEL):
        offered = wakfu_presets.offered(breed, bracket, self.path)
        return tuple(name for name in names if name in offered)

    def test_only_the_prospecting_class_is_offered_the_mule(self):
        for breed in CLIENT_ROLE_IDS:
            self.assertEqual(breed == ENUTROF,
                             'mule' in wakfu_presets.offered(breed, LEVEL, self.path), breed)

    def test_the_default_is_a_damage_preset_for_a_class_whose_roles_have_no_damage(self):
        for breed in (FECA, ENIRIPSA, 10, 12):
            self.assertNotIn('damage', wakfu_presets.official_roles(breed, self.path))
            self.assertEqual('damage_mixed_single',
                             wakfu_presets.default_preset(breed, self.path))
            self.assertEqual('damage_mixed_single',
                             wakfu_presets.offered(breed, LEVEL, self.path)[0])

    def test_a_preset_the_class_cannot_read_is_not_offered_and_its_share_is_dropped(self):
        self.assertFalse(wakfu_presets.reads(FECA, 'heal', LEVEL, self.path))
        self.assertNotIn('heal', wakfu_presets.offered(FECA, LEVEL, self.path))
        self.assertIn('support', wakfu_presets.offered(FECA, LEVEL, self.path))
        support = wakfu_presets.shares(FECA, 'support', ELEMENTS, 'pvm', LEVEL, self.path)
        self.assertNotIn('heal', support)
        self.assertEqual({'damage', 'armor', 'life', 'initiative'}, set(support))
        with self.assertRaisesMessage(ValueError, 'reads no heal turn'):
            wakfu_presets.shares(FECA, 'heal', ELEMENTS, 'pvm', LEVEL, self.path)
        self.assertIn('heal', wakfu_presets.shares(ENIRIPSA, 'support', ELEMENTS, 'pvm',
                                                   LEVEL, self.path))

    def test_a_support_preset_with_neither_armor_nor_heal_to_read_is_not_offered(self):
        self.assertFalse(wakfu_presets.reads(OSAMODAS, 'armor', LEVEL, self.path))
        self.assertFalse(wakfu_presets.reads(OSAMODAS, 'heal', LEVEL, self.path))
        self.assertNotIn('support', wakfu_presets.offered(OSAMODAS, LEVEL, self.path))
        with self.assertRaisesMessage(ValueError, 'reads no armor or heal turn'):
            wakfu_presets.shares(OSAMODAS, 'support', ELEMENTS, 'pvm', LEVEL, self.path)

    def test_a_placement_or_hindrance_preset_the_class_cannot_read_raises(self):
        for preset in ('placement', 'hindrance'):
            self.assertNotIn(preset, wakfu_presets.offered(XELOR, LEVEL, self.path))
            with self.assertRaisesMessage(ValueError, 'reads no %s turn' % preset):
                wakfu_presets.shares(XELOR, preset, ELEMENTS, 'pvm', LEVEL, self.path)
        self.assertIn('placement', wakfu_presets.shares(CRA, 'placement', ELEMENTS, 'pvm',
                                                        LEVEL, self.path))

    def test_the_heal_of_a_bracket_is_offered_only_where_the_class_reads_it(self):
        self.assertFalse(wakfu_presets.reads(SADIDA, 'heal', 20, self.path))
        self.assertNotIn('heal', wakfu_presets.offered(SADIDA, 20, self.path))
        with self.assertRaises(ValueError):
            wakfu_presets.role(SADIDA, 'heal', ('water',), 20, path=self.path)
        self.assertTrue(wakfu_presets.reads(SADIDA, 'heal', LEVEL, self.path))
        self.assertIn('heal', wakfu_presets.offered(SADIDA, LEVEL, self.path))

    def test_the_bracket_is_a_required_argument(self):
        with self.assertRaises(TypeError):
            wakfu_presets.offered(FECA, path=self.path)
        with self.assertRaises(TypeError):
            wakfu_presets.shares(FECA, 'support', ELEMENTS, 'pvm', path=self.path)
        with self.assertRaises(TypeError):
            wakfu_presets.reads(FECA, 'armor', path=self.path)

    def test_every_preset_a_class_is_offered_reads_a_component_above_one(self):
        ceiling = {name.lower(): cap for name, cap in OUT_OF_COMBAT_CAPS.items()}
        book = wakfu_turn.SpellBook(self.path)
        try:
            for breed in CLIENT_ROLE_IDS:
                for preset in wakfu_presets.offered(breed, LEVEL, self.path):
                    if preset in wakfu_presets.DAMAGE_PRESETS:
                        continue
                    with self.subTest(breed=breed, preset=preset):
                        built = wakfu_presets.role(breed, preset, ELEMENTS, LEVEL,
                                                   path=self.path)
                        turns = wakfu_presets.build_turns(book, breed, LEVEL, built, self.path)
                        self.assertGreater(
                            wakfu_value.value(built, LEVEL, ceiling, turns), float('-inf'))
                        worth = wakfu_value.components(built, LEVEL, ceiling, turns)
                        for family in wakfu_value.FAMILY_COMPONENTS:
                            if family in built.shares:
                                self.assertGreater(worth[family], 1, family)
        finally:
            book.close()
