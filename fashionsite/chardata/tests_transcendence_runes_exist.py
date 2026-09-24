# -*- coding: utf-8 -*-
"""Transcendence runes the page names must exist in the resource table, matched by name."""
import json
import os

from django.test import SimpleTestCase

from chardata.forgemagie_data import get_fm_stats

# The resource table's own type for a transcendence rune, not DofusDB's.
TRANSCENDENCE_TYPE = 140


def repository_root():
    from fashionistapulp.fashionista_config import get_fashionista_path
    return get_fashionista_path()


class TheTranscendenceRunesExist(SimpleTestCase):

    def setUp(self):
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            'forgemagie_transcendance.json')
        with open(path, encoding='utf-8') as handle:
            self.data = json.load(handle)
        self.runes = self.data['runes']

    def game_names(self):
        path = os.path.join(repository_root(), 'itemscraper',
                            'all_resources_fr.json')
        if not os.path.exists(path):
            self.skipTest('%s not in this checkout' % path)
        with open(path, encoding='utf-8') as handle:
            data = json.load(handle)
        items = data if isinstance(data, list) else data['items']
        return {item['name'] for item in items
                if isinstance(item, dict)
                and (item.get('type') or {}).get('id') == TRANSCENDENCE_TYPE}

    def test_the_page_names_no_rune_the_game_does_not_have(self):
        game = self.game_names()
        invented = sorted({r['name']['fr'] for r in self.runes} - game)
        self.assertEqual([], invented,
                         'the page would send a player looking for these on '
                         'the market, and the game has no such rune')

    def test_no_transcendence_rune_is_left_out(self):
        """The other half: a rune missing from the page is a hole this catches."""
        game = self.game_names()
        missing = sorted(game - {r['name']['fr'] for r in self.runes})
        self.assertEqual([], missing)

    def test_the_count_it_announces_is_the_count_it_holds(self):
        self.assertEqual(self.data['count'], len(self.runes))

    def test_every_stat_key_is_one_the_rest_of_the_tool_knows(self):
        known = set(get_fm_stats('dofus3'))
        unknown = sorted({r['stat_key'] for r in self.runes} - known)
        self.assertEqual([], unknown,
                         'the picker would offer a rune for a line it cannot '
                         'display')

    def test_the_ranks_run_from_one_without_a_gap(self):
        by_stat = {}
        for rune in self.runes:
            by_stat.setdefault(rune['stat_key'], []).append(rune)
        for key, runes in sorted(by_stat.items()):
            ranks = sorted(r['rank'] for r in runes)
            self.assertEqual(list(range(1, len(ranks) + 1)), ranks,
                             'ranks for %s: %s' % (key, ranks))

    def test_a_higher_rank_gives_a_bigger_bonus(self):
        by_stat = {}
        for rune in self.runes:
            by_stat.setdefault(rune['stat_key'], []).append(rune)
        for key, runes in sorted(by_stat.items()):
            runes.sort(key=lambda r: r['rank'])
            bonuses = [r['bonus'] for r in runes]
            self.assertEqual(sorted(set(bonuses)), bonuses,
                             'bonuses for %s do not grow with the rank: %s'
                             % (key, bonuses))
