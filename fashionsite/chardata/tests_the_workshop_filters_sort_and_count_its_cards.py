# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""workshop.js pure functions behind the filter chips and the sort select."""

import json
import os
import shutil
import subprocess
import tempfile

from django.test import SimpleTestCase


class WorkshopFilterSortCountTests(SimpleTestCase):

    def _run(self, expression):
        node = shutil.which('node')
        if node is None:
            self.skipTest('node is not installed')
        js_path = os.path.join(os.path.dirname(__file__), 'static', 'chardata',
                               'workshop.js')
        with open(js_path, encoding='utf-8') as handle:
            source = handle.read()
        driver = r"""
var vm = require('vm');
global.window = {};
global.document = {getElementById: function () { return null; }};
vm.runInThisContext(source);
var w = window.FashionWorkshop;
console.log(JSON.stringify(EXPR));
"""
        driver = driver.replace('EXPR', expression)
        with tempfile.NamedTemporaryFile('w', suffix='.js', encoding='utf-8',
                                         delete=False) as handle:
            handle.write('var source = %s;\n%s' % (json.dumps(source), driver))
            name = handle.name
        try:
            done = subprocess.run([node, name], capture_output=True, text=True)
        finally:
            os.unlink(name)
        self.assertEqual(done.returncode, 0, done.stderr[-800:])
        return json.loads(done.stdout)

    def test_ready_matches_only_a_done_card(self):
        self.assertTrue(self._run("w.cardMatchesFilter('done', 'ready')"))
        for state in ('part', 'none', 'norecipe'):
            with self.subTest(state=state):
                self.assertFalse(
                    self._run("w.cardMatchesFilter('%s', 'ready')" % state))

    def test_progress_matches_only_a_part_card(self):
        self.assertTrue(self._run("w.cardMatchesFilter('part', 'progress')"))
        for state in ('done', 'none', 'norecipe'):
            with self.subTest(state=state):
                self.assertFalse(
                    self._run("w.cardMatchesFilter('%s', 'progress')" % state))

    def test_not_started_covers_none_and_norecipe(self):
        self.assertTrue(self._run("w.cardMatchesFilter('none', 'notstarted')"))
        self.assertTrue(self._run("w.cardMatchesFilter('norecipe', 'notstarted')"))
        for state in ('done', 'part'):
            with self.subTest(state=state):
                self.assertFalse(
                    self._run("w.cardMatchesFilter('%s', 'notstarted')" % state))

    def test_all_matches_every_state(self):
        for state in ('done', 'part', 'none', 'norecipe'):
            with self.subTest(state=state):
                self.assertTrue(self._run("w.cardMatchesFilter('%s', 'all')" % state))

    def test_filter_counts_tally_every_bucket(self):
        result = self._run(
            "w.filterCounts(['done', 'done', 'part', 'none', 'norecipe'])")
        self.assertEqual(
            {'all': 5, 'ready': 2, 'progress': 1, 'notstarted': 2}, result)

    def test_filter_counts_on_an_empty_workshop(self):
        self.assertEqual(
            {'all': 0, 'ready': 0, 'progress': 0, 'notstarted': 0},
            self._run('w.filterCounts([])'))

    def test_sort_by_level_is_descending(self):
        cards = [{'name': 'a', 'level': 50}, {'name': 'b', 'level': 200},
                 {'name': 'c', 'level': 120}]
        result = self._run('w.sortCards(%s, "level")' % json.dumps(cards))
        self.assertEqual(['b', 'c', 'a'], [c['name'] for c in result])

    def test_sort_by_name_is_alphabetical(self):
        cards = [{'name': 'Wolf Cape'}, {'name': 'Amakna Sword'},
                 {'name': 'Bworky Ring'}]
        result = self._run('w.sortCards(%s, "name")' % json.dumps(cards))
        self.assertEqual(['Amakna Sword', 'Bworky Ring', 'Wolf Cape'],
                         [c['name'] for c in result])

    def test_sort_by_state_puts_unfinished_cards_first(self):
        cards = [{'name': 'ready', 'state': 'done'},
                 {'name': 'empty', 'state': 'norecipe'},
                 {'name': 'started', 'state': 'part'},
                 {'name': 'fresh', 'state': 'none'}]
        result = self._run('w.sortCards(%s, "state")' % json.dumps(cards))
        self.assertEqual(['fresh', 'started', 'ready', 'empty'],
                         [c['name'] for c in result])

    def test_sort_by_added_keeps_the_given_order(self):
        cards = [{'name': 'c', 'order': 2}, {'name': 'a', 'order': 0},
                 {'name': 'b', 'order': 1}]
        result = self._run('w.sortCards(%s, "added")' % json.dumps(cards))
        self.assertEqual(['a', 'b', 'c'], [c['name'] for c in result])

    def test_sort_is_stable_on_ties(self):
        cards = [{'name': 'first', 'level': 100}, {'name': 'second', 'level': 100}]
        result = self._run('w.sortCards(%s, "level")' % json.dumps(cards))
        self.assertEqual(['first', 'second'], [c['name'] for c in result])

    def test_an_unknown_sort_key_falls_back_to_added_order(self):
        cards = [{'name': 'c', 'order': 2}, {'name': 'a', 'order': 0}]
        result = self._run('w.sortCards(%s, "bogus")' % json.dumps(cards))
        self.assertEqual(['a', 'c'], [c['name'] for c in result])
