import json
import os
import re

from django.test import SimpleTestCase

from chardata import wakfu_encyclopedia_data as data
from chardata import wakfu_game_text
from fashionistapulp import wakfu_criteria

LANGUAGES = ('fr', 'en', 'es', 'pt', 'de')
ALLY_LABEL = 'ALLY-LABEL'
LEVEL_TEMPLATE = 'Lv [#1]'
ALLY_BONUS_SQL = (
    "SELECT b.effect FROM set_bonuses b LEFT JOIN effect_groups g ON g.group_id = b.effect"
    " JOIN effect_texts t ON t.effect IN (b.effect, g.effect)"
    " WHERE t.language = 'fr' AND t.text LIKE '%[ally]%' LIMIT 1")


class LabelledSource(wakfu_game_text.TextSource):
    labels = {}

    def label(self, key):
        if key in self.labels:
            return self.labels[key]
        return super().label(key)


class WakfuGameTextKeepsEveryWordTheTablesHoldTests(SimpleTestCase):
    """Fighter words, state levels, gender blocks and unknown tokens are settled in the lines."""

    def setUp(self):
        if not os.path.exists(data.database_path()):
            self.skipTest('no Wakfu database built; run update_data_wakfu.py')
        self.conn = data.connect()
        self.addCleanup(self.conn.close)

    def test_a_fighter_word_in_a_set_bonus_text_becomes_its_label(self):
        row = self.conn.execute(ALLY_BONUS_SQL).fetchone()
        self.assertIsNotNone(row)
        source = LabelledSource(self.conn, 'fr')
        source.labels = {'ally': ALLY_LABEL}
        lines = wakfu_game_text.bonus_lines(source, row[0], 63)
        self.assertTrue(any(ALLY_LABEL in line.text for line in lines), lines)
        self.assertFalse(any('[' in line.text for line in lines), lines)

    def test_a_fighter_word_without_a_label_leaves_no_bracket(self):
        row = self.conn.execute(ALLY_BONUS_SQL).fetchone()
        source = wakfu_game_text.TextSource(self.conn, 'fr')
        for line in wakfu_game_text.bonus_lines(source, row[0], 63):
            self.assertNotIn('[', line.text)

    def state_effect(self, minimum_level):
        levels = data.display_levels(self.conn)
        for item, params in self.conn.execute(
                "SELECT e.container, e.params FROM effects e JOIN items i ON i.id = e.container"
                " WHERE e.action = 304 AND e.container_type = 'ITEM_EQUIP' AND i.removed = 0"
                " AND e.display != 0"):
            state = json.loads(params)
            row = self.conn.execute('SELECT max_level FROM states WHERE id = ?',
                                    (int(state[0]),)).fetchone()
            args = wakfu_game_text.arguments(state, levels[item])
            if row and min(row[0], args[1].whole) >= minimum_level:
                return item, min(row[0], args[1].whole)
        self.fail('no live state effect of level %d' % minimum_level)

    def test_a_state_line_carries_the_level_the_effect_gives(self):
        source = LabelledSource(self.conn, 'fr')
        source.labels = {'levelShort.custom': LEVEL_TEMPLATE,
                         'levelShort.customCumulable': LEVEL_TEMPLATE}
        levels = data.display_levels(self.conn)
        for minimum in (1, 2):
            item, level = self.state_effect(minimum)
            lines = wakfu_game_text.item_lines(source, item, levels[item])
            self.assertTrue(any(line.text.endswith('(Lv %d)' % level) for line in lines),
                            (item, level, lines))

    def test_a_state_line_without_a_level_label_keeps_the_state_name_only(self):
        item, _level = self.state_effect(1)
        source = wakfu_game_text.TextSource(self.conn, 'fr')
        lines = wakfu_game_text.item_lines(
            source, item, data.display_levels(self.conn)[item])
        self.assertFalse(any('Lv' in line.text for line in lines))

    def test_no_live_description_keeps_a_gender_block_in_any_language(self):
        pattern = re.compile(r'\{\[1\*\]')
        found = 0
        for language in LANGUAGES:
            source = wakfu_game_text.TextSource(self.conn, language)
            for item, raw in self.conn.execute(
                    'SELECT d.item, d.description FROM item_descriptions d JOIN items i'
                    ' ON i.id = d.item WHERE i.removed = 0 AND d.language = ?', (language,)):
                if pattern.search(raw or ''):
                    found += 1
                    self.assertIsNone(pattern.search(source.description(item)), item)
        self.assertTrue(found)

    def test_a_gender_block_keeps_the_masculine_branch_and_the_sentence_around_it(self):
        row = self.conn.execute(
            "SELECT item, description FROM item_descriptions WHERE language = 'fr'"
            " AND description LIKE '%{[1*]?%' LIMIT 1").fetchone()
        raw = row[1]
        block = re.search(r'\{\[1\*\]\?([^{}:]*):([^{}]*)\}', raw)
        shown = wakfu_game_text.TextSource(self.conn, 'fr').description(row[0])
        self.assertEqual(shown, raw[:block.start()] + block.group(2) + raw[block.end():])

    def test_a_description_keeps_its_line_breaks(self):
        row = self.conn.execute(
            "SELECT item FROM item_descriptions WHERE language = 'fr'"
            " AND instr(description, char(10)) > 0 LIMIT 1").fetchone()
        shown = wakfu_game_text.TextSource(self.conn, 'fr').description(row[0])
        self.assertIn('\n', shown)

    def test_an_unknown_token_is_logged_once_and_left_out_of_the_line(self):
        item = self.conn.execute(
            "SELECT e.container FROM effects e JOIN items i ON i.id = e.container"
            " WHERE e.container_type = 'ITEM_EQUIP' AND e.display != 0 AND i.removed = 0"
            " AND e.action = 31 LIMIT 1").fetchone()[0]

        class Source(wakfu_game_text.TextSource):
            def effect_text(self, effect):
                return '[nonsense 12] [#1] PA'
        source = Source(self.conn, 'fr')
        with self.assertLogs('chardata.wakfu_game_text', 'WARNING') as logged:
            lines = wakfu_game_text.item_lines(source, item, 63)
            first = len(logged.records)
            wakfu_game_text.item_lines(source, item, 63)
        self.assertGreater(first, 0)
        self.assertEqual(len(logged.records), first)
        self.assertTrue(lines)
        self.assertFalse(any('nonsense' in line.text for line in lines))

    def test_a_negated_ordered_comparison_or_disjunction_is_refused(self):
        source = wakfu_game_text.TextSource(self.conn, 'fr')
        for criterion in ('not (GetLevel() > 5)', 'not (IsDay() or IsNight())'):
            with self.assertRaises(wakfu_criteria.CriteriaError):
                wakfu_game_text.condition_lines(source, criterion)

    def test_an_item_page_survives_a_criterion_the_renderer_refuses(self):
        source = wakfu_game_text.TextSource(self.conn, 'fr')
        shown = data._conditions(source, 'not (GetLevel() > 5)')
        self.assertTrue(shown[0].missing)
