import contextlib
import os

from django.test import SimpleTestCase

from chardata import wakfu_encyclopedia_data, wakfu_game_text

LANGUAGES = ('fr', 'en', 'es', 'pt', 'de')
LEFTOVER = '[]{}|'


class EveryWakfuEffectRendersInEveryLanguageTests(SimpleTestCase):
    """Each live item and set bonus renders with no template token left and no language fallback."""

    def setUp(self):
        if not os.path.exists(wakfu_encyclopedia_data.database_path()):
            self.skipTest('no Wakfu database built; run update_data_wakfu.py')
        self.conn = wakfu_encyclopedia_data.connect()
        self.addCleanup(self.conn.close)

    def visible_items_by_rule(self):
        """Live items with a visible effect that has a text of its own, an action text or members."""
        rows = self.conn.execute(
            "SELECT DISTINCT e.container FROM effects e JOIN items i ON i.id = e.container"
            " WHERE e.container_type = 'ITEM_EQUIP' AND i.removed = 0 AND e.display != 0 AND ("
            " EXISTS (SELECT 1 FROM effect_texts t WHERE t.effect = e.id)"
            " OR EXISTS (SELECT 1 FROM action_texts a WHERE a.action = e.action)"
            " OR EXISTS (SELECT 1 FROM effect_groups g WHERE g.group_id = e.id))")
        return {row[0] for row in rows}

    def items_with_a_visible_effect(self):
        rows = self.conn.execute(
            "SELECT DISTINCT e.container FROM effects e JOIN items i ON i.id = e.container"
            " WHERE e.container_type = 'ITEM_EQUIP' AND i.removed = 0 AND e.display != 0")
        return {row[0] for row in rows}

    def test_item_lines_carry_no_template_token_and_no_fallback_in_every_language(self):
        effects = wakfu_game_text.worn_effects_by_item(self.conn)
        for language in LANGUAGES:
            idx = wakfu_encyclopedia_data.index(language)
            source = wakfu_game_text.TextSource(self.conn, language)
            for item in idx.items:
                for line in wakfu_game_text.item_lines(
                        source, item.id, item.level, effects.get(item.id, [])):
                    with self.subTest(language=language, item=item.id):
                        self.assertTrue(line.text.strip())
                        self.assertFalse(set(LEFTOVER) & set(line.text), line.text)
            self.assertEqual(source.fallbacks, set(), language)

    def test_set_bonus_lines_carry_no_template_token_and_no_fallback_in_every_language(self):
        bonuses = self.conn.execute('SELECT item_set, effect FROM set_bonuses').fetchall()
        self.assertTrue(bonuses)
        for language in LANGUAGES:
            source = wakfu_game_text.TextSource(self.conn, language)
            for set_id, effect in bonuses:
                for line in wakfu_game_text.bonus_lines(source, effect, 63):
                    with self.subTest(language=language, item_set=set_id, effect=effect):
                        self.assertFalse(set(LEFTOVER) & set(line.text), line.text)
            self.assertEqual(source.fallbacks, set(), language)

    def test_an_item_shows_lines_exactly_when_a_visible_effect_has_a_text(self):
        effects = wakfu_game_text.worn_effects_by_item(self.conn)
        source = wakfu_game_text.TextSource(self.conn, 'fr')
        idx = wakfu_encyclopedia_data.index('fr')
        expected = self.visible_items_by_rule()
        shown = {item.id for item in idx.items if wakfu_game_text.item_lines(
            source, item.id, item.level, effects.get(item.id, []))}
        self.assertEqual(shown - self.items_with_a_visible_effect(), set())
        self.assertEqual(expected - shown, set())
