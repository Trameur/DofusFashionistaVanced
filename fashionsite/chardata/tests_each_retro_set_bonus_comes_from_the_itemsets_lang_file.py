# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Retro set bonuses are the ones decoded from the game's itemsets lang file."""
import contextlib
import io
import json
import os
import sqlite3
import tempfile

from django.test import SimpleTestCase

from fashionistapulp.fashionista_config import get_items_db_path

from chardata.tests import itemscraper_module

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRAPER = os.path.join(REPO, 'itemscraper')
RAW = os.path.join(SCRAPER, 'retro_raw')
SHIPPED = os.path.join(SCRAPER, 'retro_set_bonuses.json')
SNAPSHOT = os.path.join(SCRAPER, 'retro_set_bonuses_drt.json')


def _decoder():
    return itemscraper_module('get_retro_set_bonuses')


def _transform():
    return itemscraper_module('get_equipments_retro')


def _raw_roots():
    sets_path = os.path.join(RAW, 'itemsets_fr.json')
    items_path = os.path.join(RAW, 'items_fr.json')
    if not (os.path.exists(sets_path) and os.path.exists(items_path)):
        return None
    with open(sets_path, encoding='utf-8') as handle:
        sets_root = json.load(handle)['IS']
    with open(items_path, encoding='utf-8') as handle:
        items_root = json.load(handle)['I']['u']
    return sets_root, items_root


def _database():
    path = get_items_db_path('retro')
    if not os.path.exists(path):
        return None
    return sqlite3.connect('file:%s?mode=ro' % path, uri=True)


def _shipped():
    with open(SHIPPED, encoding='utf-8') as handle:
        return json.load(handle)


def _database_bonuses(connection):
    rows = connection.execute(
        """SELECT s.ankama_id, b.num_pieces_used, st.name, b.value
           FROM set_bonus b
           JOIN sets s ON s.id = b.item_set
           JOIN stats st ON st.id = b.stat""").fetchall()
    out = {}
    for ankama_id, pieces, stat, value in rows:
        out.setdefault(ankama_id, {}).setdefault(pieces, {})[stat] = value
    return out


class EachRetroSetBonusComesFromTheItemsetsLangFileTests(SimpleTestCase):
    """The decoded lang file, the shipped JSON and the database all carry the same lines."""

    def test_the_committed_json_is_the_decoded_lang_file(self):
        roots = _raw_roots()
        if roots is None:
            self.skipTest('no retro lang files')
        entries, _unmapped = _decoder().decode_sets(*roots)
        self.assertEqual(entries, _shipped())

    def test_the_database_holds_the_lines_the_transform_reads(self):
        connection = _database()
        if connection is None:
            self.skipTest('no retro database')
        try:
            stored = _database_bonuses(connection)
        finally:
            connection.close()
        wanted = {}
        for ankama_id, _names, stats_list in _transform().load_set_bonuses(SHIPPED):
            for tier in stats_list:
                for value, _same, stat in tier['effects']:
                    wanted.setdefault(ankama_id, {}).setdefault(
                        tier['effect_key'], {})[stat] = value
        self.assertEqual(stored, wanted)

    def test_no_shipped_line_is_dropped_by_the_transform(self):
        connection = _database()
        if connection is None:
            self.skipTest('no retro database')
        try:
            known = {row[0] for row in connection.execute('SELECT name FROM stats')}
        finally:
            connection.close()
        types = {line['type'] for entry in _shipped()
                 for tier in entry['bonus'] for line in tier}
        transform = _transform()
        self.assertEqual(
            sorted(t for t in types if transform._map_set_stat(t) != t), [])
        self.assertEqual(sorted(types - known), [])

    def test_every_set_in_the_database_has_a_bonus(self):
        connection = _database()
        if connection is None:
            self.skipTest('no retro database')
        try:
            ids = {row[0] for row in connection.execute('SELECT ankama_id FROM sets')}
            stored = set(_database_bonuses(connection))
        finally:
            connection.close()
        self.assertEqual(sorted(ids - stored), [])

    def test_a_line_with_no_stat_is_one_the_item_decoder_drops(self):
        roots = _raw_roots()
        if roots is None:
            self.skipTest('no retro lang files')
        _entries, unmapped = _decoder().decode_sets(*roots)
        decode_stats = _transform().decode_stats
        kept = []
        for set_id, pieces, part in unmapped:
            lines, hits = decode_stats(part)
            if any(low is not None for low, _high, _name in lines):
                kept.append((set_id, pieces, part))
        self.assertEqual(kept, [])

    def test_the_community_snapshot_never_changes_the_output(self):
        if _raw_roots() is None or not os.path.exists(SNAPSHOT):
            self.skipTest('no retro lang files or snapshot')
        decoder = _decoder()
        with tempfile.TemporaryDirectory() as folder:
            with_snapshot = os.path.join(folder, 'with.json')
            without = os.path.join(folder, 'without.json')
            with contextlib.redirect_stdout(io.StringIO()):
                decoder.main(['--raw-dir', RAW, '--out', with_snapshot,
                              '--snapshot', SNAPSHOT])
                decoder.main(['--raw-dir', RAW, '--out', without,
                              '--snapshot', os.path.join(folder, 'absent.json')])
            with open(with_snapshot, 'rb') as first, open(without, 'rb') as second:
                self.assertEqual(first.read(), second.read())

    def test_a_ranged_line_counts_its_top_roll(self):
        stats, unmapped = _decoder().decode_tier('7d#0#64#0')
        self.assertEqual((stats, unmapped), ({'Vitality': 100}, []))

    def test_a_stat_named_twice_in_a_tier_is_summed(self):
        stats, unmapped = _decoder().decode_tier('7b#7d#0#0,7b#19#0#0')
        self.assertEqual((stats, unmapped), ({'Chance': 150}, []))

    def test_a_part_with_no_stat_is_reported_not_dropped_silently(self):
        stats, unmapped = _decoder().decode_tier('b7#2#0#0,7d#5#0#0')
        self.assertEqual((stats, unmapped), ({'Vitality': 5}, ['b7#2#0#0']))

    def test_a_part_with_a_flag_and_no_value_is_reported(self):
        for part in ('31b#0#0#0', '31b#0#0#1', '867#0#0#0'):
            with self.subTest(part=part):
                stats, unmapped = _decoder().decode_tier(part)
                self.assertEqual((stats, unmapped), ({}, [part]))

    def test_main_prints_the_effects_it_could_not_map(self):
        decoder = _decoder()
        with tempfile.TemporaryDirectory() as folder:
            raw = os.path.join(folder, 'raw')
            os.mkdir(raw)
            with open(os.path.join(raw, 'itemsets_fr.json'), 'w', encoding='utf-8') as handle:
                json.dump({'IS': {'5': {'n': 'a', 'i': [1],
                                        'b': {'e2': 'b7#2#0#0,7d#5#0#0'}}}}, handle)
            with open(os.path.join(raw, 'items_fr.json'), 'w', encoding='utf-8') as handle:
                json.dump({'I': {'u': {}}}, handle)
            printed = io.StringIO()
            with contextlib.redirect_stdout(printed):
                decoder.main(['--raw-dir', raw, '--out', os.path.join(folder, 'out.json'),
                              '--snapshot', os.path.join(folder, 'absent.json')])
        self.assertIn('Warning: 1 bonus parts unmapped (no stat the site models), effects [183]',
                      printed.getvalue())

    def test_a_part_with_a_non_hex_effect_is_reported_not_fatal(self):
        stats, unmapped = _decoder().decode_tier('zz#1#0#0')
        self.assertEqual((stats, unmapped), ({}, ['zz#1#0#0']))

    def test_a_lang_file_that_lost_its_bonuses_is_refused(self):
        decoder = _decoder()
        previous = [{'ankama_id': 5, 'bonus': [[], [{'type': 'Vitality', 'value': '5'}]]},
                    {'ankama_id': 6, 'bonus': [[], []]}]
        sets_root = {'5': {'n': 'a', 'i': [1], 'b': {}},
                     '6': {'n': 'b', 'i': [2], 'b': {}}}
        entries, _unmapped = decoder.decode_sets(sets_root, {})
        self.assertEqual(decoder.lost_sets(previous, entries), [5])

    def test_main_refuses_a_lang_file_that_lost_its_bonuses_and_keeps_the_old_json(self):
        decoder = _decoder()
        with tempfile.TemporaryDirectory() as folder:
            raw = os.path.join(folder, 'raw')
            os.mkdir(raw)
            with open(os.path.join(raw, 'itemsets_fr.json'), 'w', encoding='utf-8') as handle:
                json.dump({'IS': {'5': {'n': 'a', 'i': [1], 'b': {}}}}, handle)
            with open(os.path.join(raw, 'items_fr.json'), 'w', encoding='utf-8') as handle:
                json.dump({'I': {'u': {}}}, handle)
            out = os.path.join(folder, 'out.json')
            old = json.dumps([{'ankama_id': 5, 'bonus': [
                [], [{'type': 'Vitality', 'value': '5'}]]}]).encode('utf-8')
            with open(out, 'wb') as handle:
                handle.write(old)
            with contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit):
                    decoder.main(['--raw-dir', raw, '--out', out,
                                  '--snapshot', os.path.join(folder, 'absent.json')])
            with open(out, 'rb') as handle:
                self.assertEqual(handle.read(), old)

    def test_a_language_whose_bonuses_differ_is_reported(self):
        decoder = _decoder()
        french = {'5': {'i': [1], 'b': {'e2': '7d#5#0#0'}},
                  '6': {'i': [2], 'b': {'e2': '7d#6#0#0'}}}
        spanish = {'5': {'i': [1], 'b': {'e2': '7d#5#0#0'}},
                   '6': {'i': [2], 'b': {'e2': '7d#7#0#0'}}}
        bare = {'5': {'i': [1]}, '6': {'i': [2]}}
        self.assertEqual(
            decoder.other_language_mismatches(french, {'es': spanish, 'de': bare}),
            {'es': [6]})

    def test_a_snapshot_line_that_differs_is_listed_and_one_that_agrees_is_not(self):
        decoder = _decoder()
        entries = [{'ankama_id': 5, 'bonus': [
            [], [{'type': 'Vitality', 'value': '5'}, {'type': 'Wisdom', 'value': '3'}]]}]
        records = [{'ankama_id': 5, 'tiers': {'2': {'HP': 5, 'Wisdom': 3}}}]
        self.assertEqual(decoder.cross_check(entries, records),
                         [(5, 2, 'HP', None, 5), (5, 2, 'Vitality', 5, None)])

    def test_the_game_file_wins_where_the_community_differed(self):
        connection = _database()
        if connection is None:
            self.skipTest('no retro database')
        try:
            stored = _database_bonuses(connection)
        finally:
            connection.close()
        self.assertEqual(stored[89][2].get('Power'), 3)
        self.assertNotIn('Heals', stored[89][2])
        self.assertEqual(stored[90][5].get('Summon'), 1)
        self.assertNotIn('Vitality', {stat for tier in stored[107].values() for stat in tier})
        self.assertEqual(stored[1][7].get('Vitality'), 30)
        self.assertNotIn('HP', stored[1][7])
        self.assertIn(4, stored[200])
        self.assertTrue(stored.get(141))
