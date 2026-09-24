# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""workshop.js pure functions, run for real under node.

cardState([]) must never read as 'done': an item with no recipe rows, or the
placeholder for a removed item, would otherwise pass every() vacuously and
show up as ready to craft.
"""

import json
import os
import shutil
import subprocess
import tempfile

from django.test import SimpleTestCase


class WorkshopJsPureFunctionTests(SimpleTestCase):

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

    def test_the_module_exposes_its_pure_functions(self):
        self.assertEqual(
            ['cardState', 'chunkKeys', 'clampOwned', 'clampQuantity', 'format',
             'keyOf', 'rowState', 'stillMissing'],
            sorted(self._run('Object.keys(w)')))

    def test_a_row_is_none_at_zero_owned(self):
        self.assertEqual('none', self._run('w.rowState(0, 40)'))

    def test_a_row_is_part_between_one_and_the_need(self):
        for owned in (1, 12, 39):
            with self.subTest(owned=owned):
                self.assertEqual('part', self._run('w.rowState(%d, 40)' % owned))

    def test_a_row_is_done_at_or_past_the_need(self):
        for owned in (40, 41, 999):
            with self.subTest(owned=owned):
                self.assertEqual('done', self._run('w.rowState(%d, 40)' % owned))

    def test_an_empty_card_is_norecipe_never_done(self):
        self.assertEqual('norecipe', self._run('w.cardState([])'))

    def test_a_card_with_every_row_done_is_done(self):
        self.assertEqual(
            'done',
            self._run('w.cardState([{owned: 40, need: 40}, {owned: 5, need: 5}])'))

    def test_a_card_with_nothing_owned_is_none(self):
        self.assertEqual(
            'none',
            self._run('w.cardState([{owned: 0, need: 40}, {owned: 0, need: 5}])'))

    def test_a_card_with_some_progress_is_part(self):
        self.assertEqual(
            'part',
            self._run('w.cardState([{owned: 40, need: 40}, {owned: 0, need: 5}])'))

    def test_clamp_owned_matches_the_backends_bounds(self):
        cases = {
            "''": 0,
            "'-3'": 0,
            "'12,5'": 12,
            '100000000': 9999999,
            "'40'": 40,
        }
        for expr, expected in cases.items():
            with self.subTest(expr=expr):
                self.assertEqual(expected, self._run('w.clampOwned(%s)' % expr))

    def test_clamp_owned_respects_a_custom_ceiling(self):
        self.assertEqual(5000, self._run('w.clampOwned(9000, 5000)'))

    def test_clamp_quantity_stays_inside_one_and_the_backends_cap(self):
        cases = {"''": 1, '0': 1, '-5': 1, '8': 8, '5000': 999}
        for expr, expected in cases.items():
            with self.subTest(expr=expr):
                self.assertEqual(expected, self._run('w.clampQuantity(%s)' % expr))

    def test_still_missing_never_goes_negative(self):
        self.assertEqual(0, self._run('w.stillMissing(40, 90)'))
        self.assertEqual(28, self._run('w.stillMissing(40, 12)'))

    def test_key_of_joins_the_ankama_id_and_the_subtype(self):
        self.assertEqual('1234:resources', self._run("w.keyOf(1234, 'resources')"))

    def test_format_substitutes_named_tokens(self):
        self.assertEqual(
            '3 / 8 resources',
            self._run("w.format('{done} / {total} resources', {done: 3, total: 8})"))

    def test_format_leaves_an_unknown_token_untouched(self):
        self.assertEqual(
            'Owned: {missing}',
            self._run("w.format('Owned: {missing}', {})"))

    def test_chunk_keys_stays_one_chunk_under_the_limit(self):
        self.assertEqual(
            [['a', 'b', 'c']],
            self._run("w.chunkKeys(['a', 'b', 'c'], 300)"))

    def test_chunk_keys_splits_at_the_limit_with_no_empty_tail(self):
        self.assertEqual(
            [['a', 'b'], ['c', 'd']],
            self._run("w.chunkKeys(['a', 'b', 'c', 'd'], 2)"))

    def test_chunk_keys_carries_the_remainder_in_its_own_chunk(self):
        result = self._run(
            "w.chunkKeys(Array.from({length: 301}, function (_, i) { "
            "return 'k' + i; }), 300).map(function (c) { return c.length; })")
        self.assertEqual([300, 1], result)
