# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The monster search matches the name in the page language, accents and case aside, and lists each grade with its target token."""
from django.test import SimpleTestCase

from chardata.targets import SEARCH_LIMIT, _monster_index, read_target, search_monsters
from fashionistapulp.fashion_util import strip_accents


def _named(version, language):
    """(monster id, name in the language, grades) of a monster named in it with an accent if one is."""
    entries = [(monster_id, names[language], grades)
               for monster_id, names, grades in _monster_index(version)[0] if language in names]
    accented = [entry for entry in entries if strip_accents(entry[1]) != entry[1]]
    return (accented or entries)[0]


class TheMonsterSearchTests(SimpleTestCase):

    def test_a_name_is_found_without_its_accents_or_case(self):
        for version in ('dofus3', 'beta'):
            for language in ('en', 'fr', 'es', 'pt', 'de'):
                monster_id, name, grades = _named(version, language)
                query = strip_accents(name).upper()
                found = {entry['id']: entry for entry in search_monsters(
                    version, query, language, limit=len(_monster_index(version)[0]))}
                with self.subTest(version=version, language=language, name=name):
                    self.assertIn(monster_id, found)
                    self.assertEqual(name, found[monster_id]['name'])
                    self.assertEqual([grade for grade, _level, _hp in grades],
                                     [entry['grade'] for entry in found[monster_id]['grades']])

    def test_every_listed_grade_reads_back_as_a_target(self):
        for version in ('dofus3', 'beta'):
            for entry in search_monsters(version, 'a', 'en')[:3]:
                for grade in entry['grades']:
                    target, refused = read_target(version, grade['target'])
                    with self.subTest(version=version, token=grade['target']):
                        self.assertEqual('', refused)
                        self.assertEqual((grade['level'], grade['hp']),
                                         (target.level, target.hp))

    def test_names_starting_with_the_query_come_first_and_the_list_is_bounded(self):
        found = search_monsters('dofus3', 'a', 'en')
        self.assertLessEqual(len(found), SEARCH_LIMIT)
        starts = [strip_accents(entry['name']).lower().startswith('a') for entry in found]
        self.assertEqual(sorted(starts, reverse=True), starts)

    def test_an_empty_query_or_another_version_finds_nothing(self):
        self.assertEqual([], search_monsters('dofus3', '   ', 'en'))
        self.assertEqual([], search_monsters('dofus2', 'a', 'en'))
