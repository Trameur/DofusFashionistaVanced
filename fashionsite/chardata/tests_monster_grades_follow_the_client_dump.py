# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Dofus 3 and Beta monster grades are the rows the version's own client dump gives."""
import html
import io
import json
import os
import re
import sqlite3
from html.parser import HTMLParser

from django.test import SimpleTestCase, TestCase

import fashionista_version
from fashionistapulp.fashionista_config import get_items_db_path

BLUE_LARVA = 31
ANIMATED_GIFT = 3106
DRUNKARDS_BARREL = 5843
TOFU = 8070
BOMBOLA = 4146
LANGUAGES = ('en', 'fr', 'es', 'pt', 'de')
TAGS = {'dofus3': fashionista_version.FASHIONISTA_VERSION,
        'beta': fashionista_version.FASHIONISTA_BETA_VERSION}

CLIENT_TEXT_IDS = {
    'ap_dodge_label': '1113674', 'mp_dodge_label': '1113675',
    'critical_resistance_label': '806734', 'push_resistance_label': '806735',
}
FLAT_RESISTANCE_EFFECTS = {
    'earth_flat_label': 240, 'water_flat_label': 241, 'air_flat_label': 242,
    'fire_flat_label': 243, 'neutral_flat_label': 244,
}
WISDOM_EFFECT = 124
NEVER_NULL = ('ap_dodge', 'mp_dodge', 'earth_resistance', 'air_resistance', 'fire_resistance',
              'water_resistance', 'neutral_resistance', 'wisdom')
RESISTANCE_LABELS = ('earth_flat_label', 'fire_flat_label', 'water_flat_label', 'air_flat_label',
                     'neutral_flat_label', 'critical_resistance_label', 'push_resistance_label')
RESISTANCE_COLUMNS = ('earth_flat_resistance', 'fire_flat_resistance', 'water_flat_resistance',
                      'air_flat_resistance', 'neutral_flat_resistance',
                      'critical_damage_reduction', 'push_damage_reduction')

GRADE_36 = {
    'grade': 1, 'level': 16, 'lifePoints': 90, 'actionPoints': 5, 'movementPoints': 2,
    'paDodge': 3, 'pmDodge': 4, 'earthResistance': 6, 'airResistance': -9,
    'fireResistance': 7, 'waterResistance': -8, 'neutralResistance': 1,
    'bonusCharacteristics': {'lifePoints': 0}, 'wisdom': 48,
}
GRADE_37 = {
    'grade': 1, 'level': 16, 'lifePoints': 90, 'actionPoints': 5, 'movementPoints': 2,
    'paLostDodge': 3, 'mpLostDodge': 4, 'reductionEarth': 6, 'reductionAir': -9,
    'reductionFire': 7, 'reductionWater': -8, 'reductionNeutral': 1,
    'bonusCharacteristics': {'lifePoints': 0}, 'wisdom': 48,
    'reductionEarthFlat': 11, 'reductionAirFlat': 12, 'reductionFireFlat': 13,
    'reductionWaterFlat': 14, 'reductionNeutralFlat': 15, 'criticalDamageReduction': 16,
    'pushDamageReduction': 17, 'percentDamageBonus': 18,
}
ONLY_37 = ('earth_flat_resistance', 'air_flat_resistance', 'fire_flat_resistance',
           'water_flat_resistance', 'neutral_flat_resistance', 'critical_damage_reduction',
           'push_damage_reduction', 'percent_damage_bonus')


def _summon(life_points, share):
    return dict(GRADE_37, lifePoints=life_points, bonusCharacteristics={'lifePoints': share})


def _client_label(text):
    """An effect text without its value placeholders, as a heading."""
    text = re.sub(r'\s+', ' ', re.sub(r'\{\{[^}]*\}\}|#\d', '', text)).strip()
    text = re.sub(r'^de ', '', text)
    return text[:1].upper() + text[1:]


def _storer():
    from chardata.tests import itemscraper_module
    return itemscraper_module('store_monster_grades')


def _columns(storer, monster_id, grade):
    return dict(zip(storer.COLUMNS, storer.grade_row(monster_id, grade)))


class _Tables(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tables = []
        self.cell = None

    def handle_starttag(self, tag, attrs):
        if tag == 'table':
            self.tables.append([])
        elif tag == 'tr' and self.tables:
            self.tables[-1].append([])
        elif tag in ('td', 'th') and self.tables:
            self.cell = ''

    def handle_endtag(self, tag):
        if tag in ('td', 'th') and self.cell is not None:
            self.tables[-1][-1].append(self.cell.strip())
            self.cell = None

    def handle_data(self, data):
        if self.cell is not None:
            self.cell += data


def _grade_tables(page):
    parser = _Tables()
    parser.feed(page)
    return [table for table in parser.tables if table and table[0]]


def _rows(version, sql, params=()):
    conn = sqlite3.connect(get_items_db_path(version))
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


class GradeRowTests(SimpleTestCase):

    def test_both_schemas_give_the_same_row(self):
        storer = _storer()
        old = _columns(storer, BLUE_LARVA, GRADE_36)
        new = _columns(storer, BLUE_LARVA, GRADE_37)
        expected = (BLUE_LARVA, 1, 16, 90, 5, 2, 3, 4, 6, -9, 7, -8, 1, None, 48)
        self.assertEqual(expected, tuple(old[column] for column in storer.COLUMNS[:15]))
        self.assertEqual(expected, tuple(new[column] for column in storer.COLUMNS[:15]))

    def test_fields_the_36_schema_lacks_are_null(self):
        storer = _storer()
        old = _columns(storer, BLUE_LARVA, GRADE_36)
        new = _columns(storer, BLUE_LARVA, GRADE_37)
        self.assertEqual([None] * len(ONLY_37), [old[column] for column in ONLY_37])
        self.assertEqual([11, 12, 13, 14, 15, 16, 17, 18], [new[column] for column in ONLY_37])

    def test_flat_critical_and_push_resistances_come_from_their_own_fields(self):
        storer = _storer()
        grade = dict(GRADE_37, reductionNeutralFlat=200, reductionFireFlat=15,
                     criticalDamageReduction=30, pushDamageReduction=-200, percentDamageBonus=350)
        row = _columns(storer, ANIMATED_GIFT, grade)
        self.assertEqual((11, 12, 15, 14, 200, 30, -200, 350),
                         tuple(row[column] for column in ONLY_37))

    def test_a_grade_with_neither_or_both_schemas_raises(self):
        storer = _storer()
        neither = {key: value for key, value in GRADE_37.items() if key != 'reductionAir'}
        both = dict(GRADE_36, **GRADE_37)
        no_bonus = {key: value for key, value in GRADE_37.items() if key != 'bonusCharacteristics'}
        no_flat = {key: value for key, value in GRADE_37.items() if key != 'reductionWaterFlat'}
        no_wisdom = {key: value for key, value in GRADE_36.items() if key != 'wisdom'}
        for grade in (neither, both, no_bonus, no_flat, no_wisdom):
            with self.assertRaises(storer.UnknownGradeSchema):
                storer.grade_row(BLUE_LARVA, grade)

    def test_a_grade_without_life_points_or_level_is_dropped(self):
        storer = _storer()
        self.assertIsNone(storer.grade_row(BLUE_LARVA, dict(GRADE_37, lifePoints=0)))
        self.assertIsNone(storer.grade_row(BLUE_LARVA, dict(GRADE_37, level=0)))
        self.assertIsNone(storer.grade_row(DRUNKARDS_BARREL, dict(_summon(0, 60), level=0)))

    def test_a_summon_keeps_its_share_of_the_summoners_life_points(self):
        storer = _storer()
        for life_points, share, expected in ((0, 60, (None, 60)), (18, 80, (18, 80)),
                                             (90, 0, (90, None))):
            with self.subTest(life_points=life_points, share=share):
                row = _columns(storer, DRUNKARDS_BARREL, _summon(life_points, share))
                self.assertEqual(expected, (row['life_points'], row['summoner_life_percent']))

    def test_negative_ap_and_mp_are_stored_as_null(self):
        storer = _storer()
        row = _columns(storer, BLUE_LARVA, dict(GRADE_37, actionPoints=-1, movementPoints=-100))
        self.assertIsNone(row['action_points'])
        self.assertIsNone(row['movement_points'])
        row = _columns(storer, BLUE_LARVA, dict(GRADE_37, actionPoints=0, movementPoints=0))
        self.assertEqual((0, 0), (row['action_points'], row['movement_points']))

    def test_a_negative_ap_dodge_is_stored_as_the_client_gives_it(self):
        row = _columns(_storer(), BLUE_LARVA, dict(GRADE_37, paLostDodge=-1))
        self.assertEqual(-1, row['ap_dodge'])

    def test_a_summon_keeps_its_share_of_the_summoners_other_stats(self):
        storer = _storer()
        new = dict(GRADE_37, bonusCharacteristics={
            'lifePoints': 50, 'wisdom': 50, 'paLostDodge': 75, 'mpLostDodge': 0,
            'reductionFireFlat': 25, 'pushDamageReduction': 10, 'strength': 100})
        old = dict(GRADE_36, bonusCharacteristics={
            'lifePoints': 0, 'wisdom': 120, 'waterResistance': 30, 'strength': 100})
        self.assertEqual('ap_dodge:75,wisdom:50,fire_flat_resistance:25,push_damage_reduction:10',
                         _columns(storer, TOFU, new)['summoner_shares'])
        self.assertEqual('water_resistance:30,wisdom:120',
                         _columns(storer, TOFU, old)['summoner_shares'])
        self.assertIsNone(_columns(storer, BLUE_LARVA, GRADE_37)['summoner_shares'])

    def test_too_few_rows_or_a_null_resistance_or_wisdom_stops_the_store(self):
        storer = _storer()
        row = storer.grade_row(BLUE_LARVA, GRADE_37)
        with self.assertRaises(ValueError):
            storer.check_rows([row] * 19999)
        storer.check_rows([row] * 20000)
        for column in NEVER_NULL:
            index = storer.COLUMNS.index(column)
            broken = row[:index] + (None,) + row[index + 1:]
            with self.subTest(column=column), self.assertRaises(ValueError):
                storer.check_rows([row] * 20000 + [broken])


class StoredGradesMatchTheDumpTests(SimpleTestCase):

    def test_the_table_holds_the_rows_the_dump_gives(self):
        storer = _storer()
        for version, tag in TAGS.items():
            with self.subTest(version=version, tag=tag):
                path = os.path.join(storer.RAW_ROOT, tag, 'monsters.json')
                if not os.path.exists(path):
                    self.skipTest('raw/%s not fetched on this machine' % tag)
                known = {row[0] for row in _rows(
                    version, 'SELECT DISTINCT monster_ankama_id FROM monster_names')}
                stored = set(_rows(version, 'SELECT %s FROM monster_grades' % ', '.join(storer.COLUMNS)))
                rows, _empty, _unnamed = storer.build_rows(storer._table(path), known)
                built = set(rows)
                self.assertEqual(len(rows), len(built))
                self.assertEqual([], sorted(built - stored, key=str)[:5])
                self.assertEqual([], sorted(stored - built, key=str)[:5])

    def test_the_new_labels_are_the_clients_own_texts(self):
        from chardata.encyclopedia_view import MONSTER_UI
        storer = _storer()
        for version, tag in TAGS.items():
            effects_path = os.path.join(storer.RAW_ROOT, tag, 'effects.json')
            if not os.path.exists(effects_path):
                self.skipTest('raw/%s not fetched on this machine' % tag)
            effects = storer._table(effects_path)
            for effect_id in FLAT_RESISTANCE_EFFECTS.values():
                with self.subTest(tag=tag, effect=effect_id):
                    self.assertEqual(0, effects[effect_id]['isInPercent'])
            label_effects = dict(FLAT_RESISTANCE_EFFECTS, wisdom_label=WISDOM_EFFECT)
            for language in LANGUAGES:
                with io.open(os.path.join(storer.RAW_ROOT, tag, '%s.json' % language),
                             encoding='utf-8') as handle:
                    entries = json.load(handle)['entries']
                for key, text_id in CLIENT_TEXT_IDS.items():
                    with self.subTest(tag=tag, language=language, key=key):
                        self.assertEqual(entries[text_id], MONSTER_UI[language][key])
                for key, effect_id in label_effects.items():
                    text = entries[str(effects[effect_id]['descriptionId'])]
                    with self.subTest(tag=tag, language=language, key=key):
                        self.assertEqual(_client_label(text), MONSTER_UI[language][key])


class GradePageTests(TestCase):

    def _page(self, version, monster_id):
        from chardata.official_site import get_monster_link
        name = _rows(version, "SELECT name FROM monster_names WHERE monster_ankama_id = ? "
                              "AND language = 'en'", (monster_id,))[0][0]
        response = self.client.get(get_monster_link(monster_id, name, version))
        self.assertEqual(200, response.status_code)
        return html.unescape(response.content.decode('utf-8'))

    def test_a_beta_summon_shows_its_share_and_the_hint(self):
        from chardata.encyclopedia_view import MONSTER_UI
        grades = _rows('beta', 'SELECT level, life_points, summoner_life_percent FROM monster_grades '
                               'WHERE monster_ankama_id = ?', (DRUNKARDS_BARREL,))
        self.assertTrue(grades)
        page = self._page('beta', DRUNKARDS_BARREL)
        for level, life_points, share in grades:
            self.assertLess(level, 200)
            self.assertIsNone(life_points)
            self.assertRegex(page, r'<td>\s*%d%%\s*</td>' % share)
        self.assertIn(MONSTER_UI['en']['summoner_hp_hint'], page)

    def test_dodge_shows_the_grades_own_plus_one_per_ten_wisdom(self):
        from chardata.encyclopedia_view import MONSTER_UI
        from fashionistapulp.modelresult import wisdom_per_ap_mp_dodge_point
        labels = MONSTER_UI['en']
        for version in TAGS:
            per_point = wisdom_per_ap_mp_dodge_point(version)
            with self.subTest(version=version):
                stored = _rows(version, 'SELECT grade, level, ap_dodge, mp_dodge, wisdom FROM monster_grades '
                                        'WHERE monster_ankama_id = ? ORDER BY grade', (BLUE_LARVA,))
                self.assertLess(stored[0][1], 200)
                table = next(table for table in _grade_tables(self._page(version, BLUE_LARVA))
                             if labels['ap_dodge_label'] in table[0])
                header = table[0]
                shown = [(int(row[0]), int(row[header.index(labels['ap_dodge_label'])]),
                          int(row[header.index(labels['mp_dodge_label'])])) for row in table[1:]]
                self.assertEqual([(grade, ap + wisdom // per_point, mp + wisdom // per_point)
                                  for grade, _level, ap, mp, wisdom in stored], shown)

    def test_the_resistance_table_shows_the_columns_the_monster_has(self):
        from chardata.encyclopedia_view import MONSTER_UI
        labels = [MONSTER_UI['en'][key] for key in RESISTANCE_LABELS]
        for version in TAGS:
            for monster_id in (ANIMATED_GIFT, BLUE_LARVA):
                with self.subTest(version=version, monster=monster_id):
                    stored = _rows(version, 'SELECT grade, %s FROM monster_grades '
                                            'WHERE monster_ankama_id = ? ORDER BY grade'
                                   % ', '.join(RESISTANCE_COLUMNS), (monster_id,))
                    shown = [index for index in range(len(labels))
                             if any(row[index + 1] for row in stored)]
                    tables = [table for table in _grade_tables(self._page(version, monster_id))
                              if any(label in table[0] for label in labels)]
                    if not shown:
                        self.assertEqual([], tables)
                        continue
                    self.assertEqual(1, len(tables))
                    self.assertEqual([MONSTER_UI['en']['grade_label']]
                                     + [labels[index] for index in shown], tables[0][0])
                    self.assertEqual([[str(row[0])] + [str(row[index + 1]) for index in shown]
                                      for row in stored], tables[0][1:])

    def test_the_weakest_hint_sits_under_the_coloured_table(self):
        from chardata.encyclopedia_view import MONSTER_UI
        page = self._page('beta', ANIMATED_GIFT)
        hint = page.index(MONSTER_UI['en']['weakest_hint'])
        tables = [match.start() for match in re.finditer('<table class="monster-grades">', page)]
        self.assertEqual(2, len(tables))
        self.assertLess(tables[0], hint)
        self.assertLess(hint, tables[1])

    def test_a_summon_lists_its_share_of_the_summoners_stats(self):
        from chardata.encyclopedia_view import MONSTER_UI
        labels = MONSTER_UI['en']
        for version, monster_id in (('beta', TOFU), ('dofus3', BOMBOLA)):
            with self.subTest(version=version, monster=monster_id):
                stored = _rows(version, 'SELECT level, life_points, summoner_life_percent, '
                                        'summoner_shares FROM monster_grades '
                                        'WHERE monster_ankama_id = ?', (monster_id,))
                self.assertTrue(any(level < 200 for level, _hp, _share, _shares in stored))
                shares = dict(pair.split(':') for pair in stored[0][3].split(','))
                page = self._page(version, monster_id)
                line = next((paragraph for paragraph in re.findall(r'<p[^>]*>([^<]*)</p>', page)
                             if paragraph.startswith(labels['summoner_share_hint'])), '')
                self.assertIn('%s %s%%' % (labels['wisdom_label'], shares['wisdom']), line)
                for column, label in (('ap_dodge', 'ap_dodge_label'), ('mp_dodge', 'mp_dodge_label')):
                    if column in shares:
                        self.assertIn('%s %s%%' % (labels[label], shares[column]), line)
                self.assertNotIn(labels['grade_label'], line)
                has_hp_share = any(share for _level, _hp, share, _shares in stored)
                self.assertEqual(has_hp_share, labels['summoner_hp_hint'] in page)

    def test_the_other_versions_show_no_dodge_or_resistance_column(self):
        from chardata.encyclopedia_view import MONSTER_UI
        for version in ('dofus2', 'touch', 'retro'):
            with self.subTest(version=version):
                page = self._page(version, BLUE_LARVA)
                self.assertTrue(_grade_tables(page))
                for key in list(CLIENT_TEXT_IDS) + list(FLAT_RESISTANCE_EFFECTS) + ['summoner_share_hint']:
                    self.assertNotIn(MONSTER_UI['en'][key], page)
