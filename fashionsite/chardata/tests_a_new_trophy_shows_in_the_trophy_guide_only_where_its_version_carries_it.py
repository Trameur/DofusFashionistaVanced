# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The trophy guide names the summon and pods trophies, with their lines, only on a version whose Dofus slot holds them."""
import pathlib
import re
import sqlite3

from django.test import SimpleTestCase

LANGUAGES = ('en', 'fr', 'es', 'pt', 'de')
WITH_TROPHIES = ('dofus3', 'beta', 'dofus2', 'touch')
TRAINER, TAMER, MULE = 34612, 34613, 34616


def _slot_values(version, ankama_id):
    """Sorted line values of the piece in the version's Dofus slot, None when the slot has no such piece."""
    from fashionistapulp.fashionista_config import get_items_db_path
    uri = pathlib.Path(get_items_db_path(version)).as_uri() + '?mode=ro'
    connection = sqlite3.connect(uri, uri=True)
    try:
        rows = connection.execute(
            'SELECT s.value FROM items i JOIN item_types t ON t.id = i.type'
            ' LEFT JOIN stats_of_item s ON s.item = i.id'
            " WHERE i.ankama_id = ? AND t.name = 'Dofus'"
            ' AND COALESCE(i.removed, 0) = 0', (ankama_id,)).fetchall()
    finally:
        connection.close()
    if not rows:
        return None
    return sorted(int(round(value)) for (value,) in rows if value)


def _name(version, ankama_id, language):
    from fashionistapulp.structure import get_structure
    structure = get_structure(version)
    return structure.get_item_name_in_language(
        structure.get_item_by_ankama_id(ankama_id), language)


def _body(version, language):
    from chardata.guides_content import get_guide
    html = get_guide('dofus-and-trophies', language, version)['body']
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', html))


def _lines(version, ankama_id, language):
    from chardata.guides_content import _fill_measured_numbers
    return _fill_measured_numbers('[[lines:%d]]' % ankama_id, version, language)


class TheNewTrophiesFollowTheCatalogueTests(SimpleTestCase):

    def test_the_beta_slot_holds_all_three_with_lines(self):
        for ankama_id in (TRAINER, TAMER, MULE):
            with self.subTest(piece=ankama_id):
                self.assertTrue(_slot_values('beta', ankama_id))

    def test_each_piece_shows_its_own_versions_lines_or_is_left_out(self):
        for version in WITH_TROPHIES:
            for ankama_id in (TRAINER, TAMER, MULE):
                values = _slot_values(version, ankama_id)
                for language in LANGUAGES:
                    body = _body(version, language)
                    with self.subTest(version=version, piece=ankama_id, language=language):
                        if values is None:
                            self.assertNotIn(_name('beta', ankama_id, language), body)
                            continue
                        self.assertIn(_name(version, ankama_id, language), body)
                        shown = _lines(version, ankama_id, language)
                        self.assertEqual(values, sorted(
                            int(number) for number in re.findall(r'[+-]\d+', shown)))
                        self.assertIn(shown, body)
