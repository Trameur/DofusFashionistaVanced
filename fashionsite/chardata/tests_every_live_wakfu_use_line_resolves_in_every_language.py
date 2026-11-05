import collections
import os
import re

from django.test import SimpleTestCase

from chardata import wakfu_encyclopedia_data, wakfu_game_text

LANGUAGES = ('fr', 'en', 'es', 'pt', 'de')
LEFTOVER = '[]{}|'
DOUBLE_PARENTHESIS = re.compile(r'\(\s*\(|\)\s*\)')
USE_EFFECTS_SQL = (
    "SELECT e.id, e.action, e.container FROM effects e JOIN items i ON i.id = e.container"
    " WHERE e.container_type = 'ITEM_USE' AND i.removed = 0 AND e.display != 0"
    " AND e.normal_or_critical = 'NORMAL' ORDER BY e.container, e.record_order, e.id")


class EveryLiveWakfuUseLineResolvesInEveryLanguageTests(SimpleTestCase):
    """The use lines of the live items hold no raw token, no empty line and no language fallback."""

    def setUp(self):
        if not os.path.exists(wakfu_encyclopedia_data.database_path()):
            self.skipTest('no Wakfu database built; run update_data_wakfu.py')
        self.conn = wakfu_encyclopedia_data.connect()
        self.addCleanup(self.conn.close)
        self.levels = wakfu_encyclopedia_data.display_levels(self.conn)
        self.effects = self.conn.execute(USE_EFFECTS_SQL).fetchall()

    def lines_by_action(self, language):
        source = wakfu_game_text.TextSource(self.conn, language)
        found = collections.defaultdict(list)
        for effect_id, action, item in self.effects:
            effect = wakfu_game_text._effect(self.conn, effect_id)
            lines = wakfu_game_text.effect_lines(source, [effect], self.levels[item])
            found[action].append((effect_id, item, lines))
        return found, source

    def test_the_live_use_effects_cover_every_action_the_census_lists(self):
        actions = {action for _id, action, _item in self.effects}
        census = {row[0] for row in self.conn.execute(
            "SELECT DISTINCT e.action FROM effects e JOIN items i ON i.id = e.container"
            " WHERE e.container_type = 'ITEM_USE' AND i.removed = 0")}
        self.assertEqual(actions, census)
        self.assertTrue(actions)

    def test_every_live_use_effect_renders_a_line_in_every_language(self):
        for language in LANGUAGES:
            found, _source = self.lines_by_action(language)
            for action, rows in found.items():
                for effect_id, item, lines in rows:
                    with self.subTest(language=language, action=action, effect=effect_id):
                        self.assertTrue(lines, 'action %d, item %d' % (action, item))

    def test_no_use_line_holds_a_raw_token_a_double_parenthesis_or_an_empty_text(self):
        for language in LANGUAGES:
            found, _source = self.lines_by_action(language)
            for action, rows in found.items():
                for effect_id, item, lines in rows:
                    for line in lines:
                        with self.subTest(language=language, action=action, effect=effect_id):
                            self.assertTrue(line.text.strip(), 'action %d' % action)
                            self.assertFalse(set(LEFTOVER) & set(line.text),
                                             'action %d: %r' % (action, line.text))
                            self.assertIsNone(DOUBLE_PARENTHESIS.search(line.text),
                                              'action %d: %r' % (action, line.text))

    def test_no_use_text_meets_a_token_the_parser_lacks_or_a_language_fallback(self):
        for language in LANGUAGES:
            _found, source = self.lines_by_action(language)
            self.assertEqual(source.unknown, set(), language)
            self.assertEqual(source.fallbacks, set(), language)

    def test_a_plain_action_gives_exactly_one_line_per_normal_row(self):
        found, _source = self.lines_by_action('fr')
        for action in (1083, 1084):
            rows = self.conn.execute(
                "SELECT COUNT(*) FROM effects e JOIN items i ON i.id = e.container"
                " WHERE e.container_type = 'ITEM_USE' AND i.removed = 0 AND e.action = ?"
                " AND e.normal_or_critical = 'NORMAL'", (action,)).fetchone()[0]
            self.assertTrue(rows, action)
            self.assertEqual(sum(len(lines) for _id, _item, lines in found[action]), rows,
                             action)
