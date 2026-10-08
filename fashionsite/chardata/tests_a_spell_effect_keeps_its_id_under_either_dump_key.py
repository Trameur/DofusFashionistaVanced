# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A Dofus 3 effect instance keeps its effect id whether the dump names the key effectId or actionId."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from django.test import SimpleTestCase

from chardata.tests import itemscraper_module

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

GUST = 201
GUST_LEVEL = 2001
BLUE_LARVA = 31
STATE = 3531
AIR_DAMAGE = 98
PUSH = 5
SUMMON = 181
KEYS = ('effectId', 'actionId')

TEXTS = {'1': 'Gust', '10': '#1{{~1~2 to }}#2 air damage', '11': 'Pushes back #1 cells',
         '12': 'Summons: #1', '13': 'Unknown effect'}
EFFECT_DATA = [
    {'id': 0, 'descriptionId': 13, 'category': 7},
    {'id': AIR_DAMAGE, 'descriptionId': 10, 'category': 2, 'elementId': 4, 'useDice': 1},
    {'id': PUSH, 'descriptionId': 11, 'category': 0},
    {'id': SUMMON, 'descriptionId': 12, 'category': 0},
]


def _instance(effect_id, dice_num, dice_side, element=-1, mask='a,A', uid=1):
    return {'effectId': effect_id, 'effectUid': uid, 'spellId': GUST, 'order': uid,
            'diceNum': dice_num, 'diceSide': dice_side, 'effectElement': element,
            'targetMask': mask, 'triggers': 'I', 'value': 0, 'delay': 0, 'duration': 0,
            'random': 0, 'zoneDescr': {'shape': 80, 'param1': 1, 'param2': 0}}


AIR_HIT = _instance(AIR_DAMAGE, 13, 18, element=4, uid=1)
EFFECTS = [AIR_HIT,
           _instance(PUSH, 2, 0, mask='A,*E%d' % STATE, uid=2),
           _instance(SUMMON, BLUE_LARVA, 1, uid=3)]
CRITICAL = [_instance(AIR_DAMAGE, 16, 21, element=4, uid=4)]


def _keyed(instance, key):
    out = {name: value for name, value in instance.items() if name != 'effectId'}
    if key:
        out[key] = instance['effectId']
    return out


def _unity(records):
    references = [{'rid': rid, 'data': record} for rid, record in enumerate(records, 1)]
    return {'objectsById': {'m_keys': {'Array': [record['id'] for record in records]},
                            'm_values': {'Array': [{'rid': ref['rid']} for ref in references]}},
            'references': {'RefIds': references}}


def _dump(root, tag, key, effects=EFFECTS):
    directory = Path(root) / tag
    directory.mkdir(parents=True)
    level = {'id': GUST_LEVEL, 'spellId': GUST, 'grade': 1, 'minPlayerLevel': 1, 'apCost': 3,
             'effects': {'Array': [_keyed(effect, key) for effect in effects]},
             'criticalEffect': {'Array': [_keyed(effect, key) for effect in CRITICAL]}}
    tables = {
        'spells.json': [{'id': GUST, 'nameId': 1, 'descriptionId': 0, 'typeId': 0, 'order': 1,
                         'spellLevels': {'Array': [GUST_LEVEL]}}],
        'spell_levels.json': [level],
        'spell_types.json': [],
        'spell_variants.json': [],
        'effects.json': EFFECT_DATA,
    }
    for name, records in tables.items():
        (directory / name).write_text(json.dumps(_unity(records)), encoding='utf-8')
    (directory / 'en.json').write_text(json.dumps({'entries': TEXTS}), encoding='utf-8')
    return directory


class _TempRoot(SimpleTestCase):

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)

    def _transformer(self, tag, key):
        reader = itemscraper_module('get_spells')
        return reader.SpellTransformer(_dump(self.root, tag, key), self.root / 'out.json',
                                       languages=('en',))


class TheSpellTransformReadsEitherKeyTests(_TempRoot):

    def test_both_keys_give_the_same_spell(self):
        old, new = (self._transformer(tag, key).build()
                    for tag, key in (('3.7.3.3', 'effectId'), ('3.7.1.0', 'actionId')))
        self.assertEqual(old, new)
        level = new[0]['levels'][0]
        self.assertEqual([AIR_DAMAGE, PUSH, SUMMON],
                         [effect['effect_id'] for effect in level['effects']])
        self.assertEqual([AIR_DAMAGE], [effect['effect_id'] for effect in level['critical_effects']])
        templates = new[0]['damage_templates']
        self.assertEqual([('AIR', ['13-18'])],
                         [(row['element'], row['ranges']) for row in templates['normal']])
        self.assertEqual([('AIR', ['16-21'])],
                         [(row['element'], row['ranges']) for row in templates['critical']])

    def test_an_instance_under_neither_key_stops_the_transform(self):
        transformer = self._transformer('3.7.4.4', None)
        with self.assertRaisesRegex(ValueError, 'spell %d' % GUST):
            transformer.build()

    def test_the_state_a_push_waits_on_is_found_under_either_key(self):
        states = itemscraper_module('store_spell_states')
        for key in KEYS:
            with self.subTest(key=key):
                path = self.root / ('%s.json' % key)
                path.write_text(json.dumps(self._transformer(key, key).build()), encoding='utf-8')
                self.assertEqual({STATE}, states.state_ids_in_use(str(path)))


class TheDuplicateFinderReadsEitherKeyTests(_TempRoot):

    def test_a_row_the_next_dump_doubles_is_found_across_the_two_keys(self):
        _dump(self.root, '3.7.0.0', 'effectId')
        _dump(self.root, '3.7.1.0', 'actionId', effects=[AIR_HIT, AIR_HIT] + EFFECTS[1:])
        output = self.root / 'duplicated.json'
        done = subprocess.run(
            [sys.executable, '-m', 'itemscraper.find_duplicated_damage_rows',
             '--raw-root', str(self.root), '--output', str(output)],
            cwd=_REPO, capture_output=True, text=True, timeout=120,
            env={key: value for key, value in os.environ.items() if key != 'PYTHONPATH'})
        self.assertEqual(0, done.returncode, done.stderr)
        self.assertEqual({str(GUST): {'kept': 1, 'seen': '3.7.0.0 -> 3.7.1.0'}},
                         json.loads(output.read_text(encoding='utf-8')))


class TheMonsterSpellTextReadsEitherKeyTests(SimpleTestCase):

    def test_a_spell_without_prose_reads_its_rows_under_either_key(self):
        storer = itemscraper_module('store_monster_spells')
        spell = {'id': GUST, 'nameId': 1, 'descriptionId': 0,
                 'spellLevels': {'Array': [GUST_LEVEL]}}
        effects = {record['id']: record for record in EFFECT_DATA}
        for key in KEYS:
            with self.subTest(key=key):
                levels = {GUST_LEVEL: {'effects': {'Array': [_keyed(effect, key)
                                                             for effect in EFFECTS]}}}
                self.assertEqual(
                    '13 to 18 air damage, Pushes back 2 cells, Summons: Blue Larva',
                    storer.spell_description(spell, levels, effects, TEXTS,
                                             {BLUE_LARVA: 'Blue Larva'}))
