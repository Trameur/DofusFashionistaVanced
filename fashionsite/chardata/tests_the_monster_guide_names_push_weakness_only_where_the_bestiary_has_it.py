# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The monster weakness guide speaks of pushback weakness only on a version whose bestiary has a monster with negative pushback resistance."""
import pathlib
import sqlite3

from django.test import SimpleTestCase

LANGUAGES = ('en', 'fr', 'es', 'pt', 'de')


def _push_weak_monsters(version):
    from fashionistapulp.fashionista_config import get_items_db_path
    uri = pathlib.Path(get_items_db_path(version)).as_uri() + '?mode=ro'
    connection = sqlite3.connect(uri, uri=True)
    try:
        columns = {row[1] for row in connection.execute('PRAGMA table_info(monster_grades)')}
        if 'push_damage_reduction' not in columns:
            return 0
        return connection.execute(
            'SELECT COUNT(DISTINCT monster_ankama_id) FROM monster_grades'
            ' WHERE push_damage_reduction < 0').fetchone()[0]
    finally:
        connection.close()


def _body(version, language):
    from chardata.guides_content import get_guide
    return get_guide('monster-weaknesses', language, version)['body']


def _shown_label(language):
    from chardata.encyclopedia_view import MONSTER_UI
    return MONSTER_UI[language]['push_resistance_label']


class ThePushWeaknessFollowsTheBestiaryTests(SimpleTestCase):

    def test_the_beta_bestiary_has_push_weak_monsters(self):
        self.assertGreater(_push_weak_monsters('beta'), 0)

    def test_each_version_speaks_of_it_only_when_its_bestiary_has_one(self):
        from fashionistapulp.game_versions import version_keys
        for version in version_keys():
            weak = _push_weak_monsters(version)
            for language in LANGUAGES:
                with self.subTest(version=version, language=language):
                    self.assertEqual(bool(weak), _shown_label(language) in _body(version, language))

    def test_the_passage_names_the_version_and_its_pushback_damage_label(self):
        from django.utils import translation
        from chardata.guides_content import _version_name
        from chardata.translation_util import localized_stat_name
        for language in LANGUAGES:
            body = _body('beta', language)
            with translation.override(language):
                damage = str(localized_stat_name('Pushback Damage', 'beta'))
            with self.subTest(language=language):
                passage = body[body.index(_shown_label(language)) - 300:]
                self.assertIn(_version_name('beta', language), passage)
                self.assertIn(damage, passage)
