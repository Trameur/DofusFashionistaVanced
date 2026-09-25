# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""workshop.js pure functions for the copy-as-text and CSV export, run under node."""

import json
import os
import shutil
import subprocess
import tempfile

from django.test import SimpleTestCase


class ShoppingListCopyAndCsvTests(SimpleTestCase):

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
            done = subprocess.run(
                [node, name], capture_output=True, text=True, encoding='utf-8')
        finally:
            os.unlink(name)
        self.assertEqual(done.returncode, 0, done.stderr[-800:])
        return json.loads(done.stdout)

    # ---------- csvField ----------

    def test_csv_field_leaves_a_plain_value_untouched(self):
        self.assertEqual('Ash Wood', self._run("w.csvField('Ash Wood')"))

    def test_csv_field_leaves_accented_characters_unescaped(self):
        self.assertEqual('Écorce noire', self._run("w.csvField('Écorce noire')"))

    def test_csv_field_quotes_a_value_with_a_comma(self):
        self.assertEqual(
            '"Bones, small"', self._run("w.csvField('Bones, small')"))

    def test_csv_field_quotes_and_doubles_an_internal_quote(self):
        raw = 'Blade "Sharp"'
        expected = '"' + raw.replace('"', '""') + '"'
        self.assertEqual(expected, self._run('w.csvField(%s)' % json.dumps(raw)))

    def test_csv_field_quotes_a_value_with_a_newline(self):
        self.assertEqual(
            '"line one\nline two"',
            self._run('w.csvField(%s)' % json.dumps('line one\nline two')))

    def test_csv_field_turns_null_into_an_empty_string(self):
        self.assertEqual('', self._run('w.csvField(null)'))

    # ---------- buildCsv ----------

    def test_build_csv_joins_the_header_and_rows_with_crlf(self):
        result = self._run(
            "w.buildCsv(['Name', 'Needed'], [['Ash Wood', 4], ['Iron Ore', 2]])")
        self.assertEqual(
            'Name,Needed\r\nAsh Wood,4\r\nIron Ore,2', result)

    def test_build_csv_quotes_a_row_field_with_a_comma(self):
        result = self._run(
            "w.buildCsv(['Name', 'Needed'], [['Bones, small', 4]])")
        self.assertEqual('Name,Needed\r\n"Bones, small",4', result)

    def test_build_csv_on_no_rows_is_only_the_header(self):
        result = self._run("w.buildCsv(['Name', 'Needed'], [])")
        self.assertEqual('Name,Needed', result)

    # ---------- buildMissingListCsv ----------

    def _headers(self):
        return {'name': 'Resource name', 'needed': 'Needed',
                'owned': 'Owned', 'missing': 'Missing'}

    def test_missing_list_csv_starts_with_the_utf8_bom(self):
        result = self._run(
            'w.buildMissingListCsv([], %s)' % json.dumps(self._headers()))
        self.assertEqual(0xFEFF, ord(result[0]))

    def test_missing_list_csv_translates_the_header_row(self):
        result = self._run(
            'w.buildMissingListCsv([], %s)' % json.dumps(self._headers()))
        self.assertEqual(
            'Resource name,Needed,Owned,Missing', result[1:].split('\r\n')[0])

    def test_missing_list_csv_includes_every_resource_not_only_the_missing_ones(self):
        items = [
            {'name': 'Ash Wood', 'needed': 10, 'owned': 10, 'missing': 0},
            {'name': 'Iron Ore', 'needed': 8, 'owned': 3, 'missing': 5},
        ]
        result = self._run(
            'w.buildMissingListCsv(%s, %s)' % (json.dumps(items), json.dumps(self._headers())))
        lines = result[1:].split('\r\n')
        self.assertEqual(
            ['Resource name,Needed,Owned,Missing',
             'Ash Wood,10,10,0',
             'Iron Ore,8,3,5'],
            lines)

    def test_missing_list_csv_quotes_a_name_with_a_comma_and_keeps_accents(self):
        items = [{'name': 'Écorce, brute', 'needed': 3, 'owned': 0, 'missing': 3}]
        result = self._run(
            'w.buildMissingListCsv(%s, %s)' % (json.dumps(items), json.dumps(self._headers())))
        self.assertEqual(
            '"Écorce, brute",3,0,3', result[1:].split('\r\n')[1])

    def test_english_keeps_the_comma_and_other_languages_use_a_semicolon(self):
        self.assertEqual(
            [',', ',', ';', ';', ';', ';'],
            self._run('["en", "en-us", "fr", "es", "pt-br", "de"].map(w.csvSeparatorFor)'))

    def test_a_semicolon_csv_quotes_a_name_with_a_semicolon_not_a_comma(self):
        items = [{'name': 'Bois; sec', 'needed': 2, 'owned': 1, 'missing': 1},
                 {'name': 'Écorce, brute', 'needed': 3, 'owned': 0, 'missing': 3}]
        result = self._run(
            'w.buildMissingListCsv(%s, %s, ";")' % (json.dumps(items), json.dumps(self._headers())))
        lines = result[1:].split('\r\n')
        self.assertEqual('"Bois; sec";2;1;1', lines[1])
        self.assertEqual('Écorce, brute;3;0;3', lines[2])

    def test_missing_list_csv_row_order_matches_the_given_order(self):
        items = [
            {'name': 'Zinc Ore', 'needed': 1, 'owned': 0, 'missing': 1},
            {'name': 'Ash Wood', 'needed': 2, 'owned': 0, 'missing': 2},
        ]
        result = self._run(
            'w.buildMissingListCsv(%s, %s)' % (json.dumps(items), json.dumps(self._headers())))
        lines = result[1:].split('\r\n')[1:]
        self.assertEqual(['Zinc Ore,1,0,1', 'Ash Wood,2,0,2'], lines)

    # ---------- buildMissingListText ----------

    def test_missing_list_text_formats_name_colon_missing(self):
        items = [{'name': 'Iron Ore', 'needed': 8, 'owned': 3, 'missing': 5}]
        self.assertEqual(
            'Iron Ore: 5', self._run('w.buildMissingListText(%s)' % json.dumps(items)))

    def test_missing_list_text_skips_fully_gathered_resources(self):
        items = [
            {'name': 'Ash Wood', 'needed': 10, 'owned': 10, 'missing': 0},
            {'name': 'Iron Ore', 'needed': 8, 'owned': 3, 'missing': 5},
        ]
        self.assertEqual(
            'Iron Ore: 5', self._run('w.buildMissingListText(%s)' % json.dumps(items)))

    def test_missing_list_text_keeps_the_given_order_with_one_line_per_resource(self):
        items = [
            {'name': 'Zinc Ore', 'needed': 1, 'owned': 0, 'missing': 1},
            {'name': 'Ash Wood', 'needed': 2, 'owned': 0, 'missing': 2},
        ]
        self.assertEqual(
            'Zinc Ore: 1\nAsh Wood: 2',
            self._run('w.buildMissingListText(%s)' % json.dumps(items)))

    def test_missing_list_text_keeps_accented_names_readable(self):
        items = [{'name': 'Écorce noire', 'needed': 4, 'owned': 0, 'missing': 4}]
        self.assertEqual(
            'Écorce noire: 4',
            self._run('w.buildMissingListText(%s)' % json.dumps(items)))

    def test_missing_list_text_is_empty_when_nothing_is_missing(self):
        items = [{'name': 'Ash Wood', 'needed': 10, 'owned': 10, 'missing': 0}]
        self.assertEqual('', self._run('w.buildMissingListText(%s)' % json.dumps(items)))
