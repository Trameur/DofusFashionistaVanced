# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A monster spell whose grades summon different monsters names, at each grade of
the monster that casts it, the monster that grade summons."""
import html
import re
import sqlite3

from django.test import SimpleTestCase, TestCase

from chardata.tests import itemscraper_module
from fashionistapulp.fashionista_config import get_items_db_path

VERSIONS = ('dofus3', 'beta')
NEWBORN = 33348
RABBILOPE = 8043
GREGARIOUS_RABBILOPE = 8117
ENRAGED_BOOWOLF = 4795
MILIBOOWOLVES = 8471
SUMMON = 181
KILL_AND_SUMMON = 405
SUMMON_TWO_VALUES = 182
DAMAGE = 98
CAST_GRADE = 792
SUMMON_ICON = 24
BOUFTOU = 42
ROYAL_BOUFTOU = 43
NAMES = {BOUFTOU: 'Bouftou', ROYAL_BOUFTOU: 'Royal Bouftou'}
TEXTS = {'1': 'Summons #1', '2': 'Kills the target and replaces it with the summons: #1',
         '3': 'Summons #1 for #2 turns', '4': '#1{{~1~2 to }}#2 air damage', '5': '#1',
         '9': 'Ankama prose'}
EFFECTS = {
    SUMMON: {'descriptionId': 1, 'textIconReferenceId': SUMMON_ICON},
    KILL_AND_SUMMON: {'descriptionId': 2, 'textIconReferenceId': SUMMON_ICON},
    SUMMON_TWO_VALUES: {'descriptionId': 3, 'textIconReferenceId': SUMMON_ICON},
    DAMAGE: {'descriptionId': 4, 'textIconReferenceId': 7},
    CAST_GRADE: {'descriptionId': 5, 'textIconReferenceId': 20},
}
RELAYING_SPELL = 6951
SUMMON_BAD_ID = re.compile(r'summons?:?\s+\d+|invocation\s*:\s*\d+|invoque\s*:\s*\d+', re.I)


def _storer():
    return itemscraper_module('store_monster_spells')


def _level(grade, *rows):
    return {'grade': grade, 'effects': {'Array': [
        {'actionId': effect_id, 'diceNum': dice_num, 'diceSide': 0, 'targetMask': 'a,A'}
        for effect_id, dice_num in rows]}}


def _spell(*grades, prose=0):
    levels = {100 + index: _level(index + 1, *rows) for index, rows in enumerate(grades)}
    spell = {'descriptionId': prose, 'spellLevels': {'Array': sorted(levels)}}
    return spell, levels


def _rows(version, sql, params=()):
    conn = sqlite3.connect(get_items_db_path(version))
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


class GradeDescriptionTests(SimpleTestCase):

    def test_each_grade_reads_its_own_summon(self):
        storer = _storer()
        spell, levels = _spell([(SUMMON, BOUFTOU)], [(SUMMON, ROYAL_BOUFTOU)])
        self.assertEqual({1: 'Summons Bouftou', 2: 'Summons Royal Bouftou'},
                         storer.grade_descriptions(spell, levels, EFFECTS, TEXTS, NAMES))
        self.assertEqual('Summons Bouftou',
                         storer.spell_description(spell, levels, EFFECTS, TEXTS, NAMES))

    def test_grades_that_read_alike_or_prose_keep_one_description(self):
        storer = _storer()
        alike = _spell([(SUMMON, BOUFTOU)], [(SUMMON, BOUFTOU)])
        self.assertEqual({}, storer.grade_descriptions(*alike, EFFECTS, TEXTS, NAMES))
        prose = _spell([(SUMMON, BOUFTOU)], [(SUMMON, ROYAL_BOUFTOU)], prose=9)
        self.assertEqual({}, storer.grade_descriptions(*prose, EFFECTS, TEXTS, NAMES))
        self.assertEqual('Ankama prose', storer.spell_description(*prose, EFFECTS, TEXTS, NAMES))

    def test_a_kill_and_summon_row_names_the_summon(self):
        storer = _storer()
        summons = storer.summon_effects(EFFECTS, TEXTS)
        self.assertIn(KILL_AND_SUMMON, summons)
        self.assertNotIn(SUMMON_TWO_VALUES, summons)
        self.assertNotIn(DAMAGE, summons)
        spell, levels = _spell([(KILL_AND_SUMMON, BOUFTOU)])
        self.assertEqual('Kills the target and replaces it with the summons: Bouftou',
                         storer.spell_description(spell, levels, EFFECTS, TEXTS, NAMES,
                                                  summons=summons))

    def test_no_stored_description_shows_a_summon_by_its_id(self):
        for version in VERSIONS:
            for table in ('monster_spell_names', 'monster_spell_grade_descriptions'):
                rows = _rows(version, "SELECT spell_ankama_id, description FROM %s "
                                      "WHERE language IN ('en', 'fr')" % table)
                with self.subTest(version=version, table=table):
                    self.assertGreater(len(rows), 1000)
                    self.assertEqual([], [row for row in rows
                                          if row[1] and SUMMON_BAD_ID.search(row[1])][:5])

    def test_the_newborn_spell_keeps_one_summon_per_grade(self):
        for version in VERSIONS:
            stored = _rows(version, "SELECT grade, description "
                                    "FROM monster_spell_grade_descriptions "
                                    "WHERE spell_ankama_id = ? AND language = 'en' ORDER BY grade",
                           (NEWBORN,))
            with self.subTest(version=version):
                self.assertEqual([(1, 'Summons Baby Flashiraffe'), (2, 'Summons Baby Rabbilope'),
                                  (3, 'Summons Baby Brutapir'), (4, 'Summons Baby Heapotamus'),
                                  (5, 'Summons Baby Goatphibian')], stored)


class RelayedGradeTests(SimpleTestCase):

    def _relay(self, grade, chance=0, triggers='I'):
        return {'actionId': CAST_GRADE, 'diceNum': RELAYING_SPELL, 'diceSide': grade,
                'random': chance, 'triggers': triggers, 'targetMask': 'C'}

    def _spell(self, *rows):
        levels = {
            101: {'grade': 1, 'effects': {'Array': list(rows)}},
            102: _level(2, (SUMMON, BOUFTOU)),
            103: _level(3, (SUMMON, ROYAL_BOUFTOU)),
        }
        return {'id': RELAYING_SPELL, 'descriptionId': 0,
                'spellLevels': {'Array': [101, 102, 103]}}, levels

    def test_a_grade_casting_grades_at_random_reads_each_with_its_chance(self):
        spell, levels = self._spell(self._relay(2, 50), self._relay(3, 50))
        self.assertEqual(
            {1: '50%: Summons Bouftou; 50%: Summons Royal Bouftou', 2: 'Summons Bouftou',
             3: 'Summons Royal Bouftou'},
            _storer().grade_descriptions(spell, levels, EFFECTS, TEXTS, NAMES))
        self.assertEqual('50% : Summons Bouftou ; 50% : Summons Royal Bouftou',
                         _storer().spell_description(spell, levels, EFFECTS, TEXTS, NAMES, 'fr'))

    def test_a_grade_that_casts_one_grade_reads_it(self):
        for rows in ((self._relay(3), self._relay(1)), (self._relay(3, 50), self._relay(3, 50))):
            spell, levels = self._spell(*rows)
            with self.subTest(rows=rows):
                self.assertEqual('Summons Royal Bouftou', _storer().grade_descriptions(
                    spell, levels, EFFECTS, TEXTS, NAMES)[1])

    def test_a_grade_that_casts_several_grades_without_a_draw_reads_none(self):
        spell, levels = self._spell(self._relay(2), self._relay(3))
        self.assertNotIn(1, _storer().grade_descriptions(spell, levels, EFFECTS, TEXTS, NAMES))

    def test_a_grade_cast_on_a_trigger_is_not_read_as_its_own(self):
        spell, levels = self._spell(self._relay(2, triggers='D'))
        self.assertNotIn(1, _storer().grade_descriptions(spell, levels, EFFECTS, TEXTS, NAMES))


class DescriptionLinesTests(SimpleTestCase):

    def _lines(self, spell_grades, monster_grades):
        from chardata.encyclopedia_view import _spell_description_lines
        return _spell_description_lines(spell_grades, monster_grades,
                                        {1: 'a', 2: 'b', 3: 'c'}.get, 'prose')

    def test_grades_that_cast_the_same_text_share_a_line(self):
        self.assertEqual([{'text': 'a', 'grades': [1, 4, 5]}, {'text': 'b', 'grades': [2]},
                          {'text': 'c', 'grades': [3]}],
                         self._lines([1, 2, 3, 1, 1], [1, 2, 3, 4, 5]))

    def test_one_text_for_every_grade_names_no_grade(self):
        self.assertEqual([{'text': 'b', 'grades': []}],
                         self._lines([2] * 10, [1, 2, 3, 4, 5, 6]))
        self.assertEqual([{'text': 'b', 'grades': []}], self._lines([1, 2, 2, 2, 2], [2, 3, 4, 5]))

    def test_a_spell_cast_at_some_grades_names_them(self):
        self.assertEqual([{'text': 'a', 'grades': [1]}], self._lines([1, 0, 0], [1, 2, 3]))

    def test_a_spell_no_grade_casts_keeps_its_description(self):
        self.assertEqual([{'text': 'prose', 'grades': []}], self._lines([0, 0], [1, 2]))
        self.assertEqual([{'text': 'prose', 'grades': []}], self._lines([], [1, 2]))


class SpellBlockSourceTests(SimpleTestCase):

    def _spells(self, language):
        from chardata.encyclopedia_view import _monster_spells
        conn = sqlite3.connect(':memory:')
        try:
            conn.executescript("""
                CREATE TABLE monster_spells (monster_ankama_id, position, spell_ankama_id,
                                             grade_mapping);
                CREATE TABLE monster_spell_names (spell_ankama_id, language, name, description);
                CREATE TABLE monster_spell_levels (spell_ankama_id, grade, ap_cost, range_min,
                                                   range_max);
                CREATE TABLE monster_spell_grade_descriptions (spell_ankama_id, grade, language,
                                                               description);
            """)
            conn.executemany('INSERT INTO monster_spells VALUES (1, ?, ?, ?)', [
                (0, 10, '1,2,2'), (1, 11, '1,2,2'), (2, 12, '1,2,2'), (3, 13, '1,1,1'),
                (4, 14, '0,2,2')])
            conn.executemany('INSERT INTO monster_spell_names VALUES (?, ?, ?, ?)', [
                (10, 'fr', 'Dix', 'fr un'), (10, 'en', 'Ten', 'en one'),
                (11, 'fr', 'Onze', 'fr prose'), (11, 'en', 'Eleven', 'en one'),
                (12, 'fr', 'Douze', None), (12, 'en', 'Twelve', 'en one'),
                (13, 'fr', 'Treize', 'fr deux'), (13, 'en', 'Thirteen', 'en two'),
                (14, 'fr', 'Quatorze', 'fr prose'), (14, 'en', 'Fourteen', 'en prose')])
            conn.executemany('INSERT INTO monster_spell_levels VALUES (?, ?, ?, ?, ?)', [
                (spell, grade, grade + 2, 1, grade) for spell in (10, 11, 12, 13, 14)
                for grade in (1, 2)])
            conn.executemany('INSERT INTO monster_spell_grade_descriptions VALUES (?, ?, ?, ?)', [
                (10, 1, 'fr', 'fr un'), (10, 2, 'fr', 'fr deux'),
                (10, 1, 'en', 'en one'), (10, 2, 'en', 'en two'),
                (11, 1, 'en', 'en one'), (11, 2, 'en', 'en two'),
                (12, 1, 'en', 'en one'), (12, 2, 'en', 'en two'),
                (13, 2, 'fr', 'fr deux'), (13, 2, 'en', 'en two')])
            spells = _monster_spells(conn.cursor(), 1, language, [1, 2, 3], True)
        finally:
            conn.close()
        return {spell['id']: spell for spell in spells}

    def test_each_spell_reads_the_closest_text_to_the_page_language(self):
        spells = self._spells('fr')

        def lines(one, two):
            return [{'text': one, 'grades': [1]}, {'text': two, 'grades': [2, 3]}]
        self.assertEqual(lines('fr un', 'fr deux'), spells[10]['descriptions'])
        self.assertEqual([{'text': 'fr prose', 'grades': []}], spells[11]['descriptions'])
        self.assertEqual(lines('en one', 'en two'), spells[12]['descriptions'])

    def test_a_grade_without_text_borrows_none_from_another_grade(self):
        self.assertEqual([], self._spells('fr')[13]['descriptions'])
        self.assertEqual([], self._spells('en')[13]['descriptions'])

    def test_a_spell_cast_from_a_later_grade_shows_that_grades_cost(self):
        spell = self._spells('en')[14]
        self.assertEqual((4, 1, 2), (spell['ap_cost'], spell['range_min'], spell['range_max']))


class MonsterSpellBlockTests(SimpleTestCase):

    def test_each_grade_reads_the_summon_its_spell_grade_casts(self):
        from chardata.encyclopedia_view import _monster_spells
        for version in VERSIONS:
            conn = sqlite3.connect(get_items_db_path(version))
            try:
                spells = _monster_spells(conn.cursor(), ENRAGED_BOOWOLF, 'en', [1, 2, 3, 4, 5],
                                         True)
            finally:
                conn.close()
            spell = next(spell for spell in spells if spell['id'] == MILIBOOWOLVES)
            with self.subTest(version=version):
                self.assertEqual([{'text': 'Summons Sniffling Miliboowolf', 'grades': [1, 4, 5]},
                                  {'text': 'Summons Sneaky Miliboowolf', 'grades': [2]},
                                  {'text': 'Summons Toxic Miliboowolf', 'grades': [3]}],
                                 spell['descriptions'])

    def test_the_grade_texts_cost_no_extra_query(self):
        from chardata.encyclopedia_view import _monster_spells
        calls = []

        class Counting(object):
            def __init__(self, inner):
                self._inner = inner

            def execute(self, sql, *args):
                calls.append(sql)
                return self._inner.execute(sql, *args)

        conn = sqlite3.connect(get_items_db_path('dofus3'))
        try:
            spells = _monster_spells(Counting(conn.cursor()), ENRAGED_BOOWOLF, 'fr',
                                     [1, 2, 3, 4, 5], True)
        finally:
            conn.close()
        self.assertGreater(len(spells), 2)
        self.assertEqual(2, len(calls))


class MonsterPageTests(TestCase):

    def _page(self, version, monster_id):
        from chardata.official_site import get_monster_link
        name = _rows(version, "SELECT name FROM monster_names WHERE monster_ankama_id = ? "
                              "AND language = 'en'", (monster_id,))[0][0]
        response = self.client.get(get_monster_link(monster_id, name, version))
        self.assertEqual(200, response.status_code)
        page = html.unescape(response.content.decode('utf-8'))
        return page[page.index('id="monster-spells"'):]

    def test_each_grade_shows_the_summon_it_casts(self):
        for version in VERSIONS:
            for monster_id in (RABBILOPE, GREGARIOUS_RABBILOPE):
                with self.subTest(version=version, monster=monster_id):
                    spells = self._page(version, monster_id)
                    self.assertIn('Summons Baby Rabbilope', spells)
                    self.assertNotIn('Baby Flashiraffe', spells)
                    self.assertNotIn('class="spell-tip-grades"', spells)

    def test_grades_that_summon_different_monsters_are_named(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                spells = self._page(version, ENRAGED_BOOWOLF)
                for grades, text in (('1, 4, 5', 'Sniffling'), ('2', 'Sneaky'), ('3', 'Toxic')):
                    self.assertIn('<span class="spell-tip-text"><span class="spell-tip-grades">'
                                  'Grade %s</span>Summons %s Miliboowolf</span>' % (grades, text),
                                  spells)
