import json
import os

from django.http import QueryDict
from django.test import SimpleTestCase, TestCase

from chardata.encyclopedia_filters import (
    MAX_ORDER_ROWS, is_filter_key, parse_order_rows, parse_stat_rows)
from chardata.encyclopedia_view import _is_searchable_stat_key


def _query(text):
    return QueryDict(text)


def _accepting(keys):
    return lambda key: key in keys


class TheStatRowsFollowThePredicate(SimpleTestCase):

    def test_a_key_the_predicate_accepts_becomes_a_filter(self):
        rows, filters = parse_stat_rows(
            _query('stat_key=hp&stat_min=5'), _accepting({'hp'}))
        self.assertEqual([{'key': 'hp', 'min': '5'}], rows)
        self.assertEqual([('hp', 5)], filters)

    def test_the_dofus_predicate_still_drops_hp_and_pvp_keys(self):
        rows, filters = parse_stat_rows(
            _query('stat_key=hp&stat_min=5&stat_key=pvp_damage&stat_min=2'
                   '&stat_key=ap&stat_min=1'),
            _is_searchable_stat_key)
        self.assertEqual(['', '', 'ap'], [row['key'] for row in rows])
        self.assertEqual([('ap', 1)], filters)

    def test_a_key_outside_the_given_keys_is_blanked_but_its_minimum_is_echoed(self):
        rows, filters = parse_stat_rows(
            _query('stat_key=nothing&stat_min=4'), _accepting({'hp'}))
        self.assertEqual([{'key': '', 'min': '4'}], rows)
        self.assertEqual([], filters)

    def test_a_minimum_that_is_not_a_positive_number_applies_no_filter(self):
        for minimum in ('abc', '0', '-3', ''):
            with self.subTest(minimum=minimum):
                _rows, filters = parse_stat_rows(
                    _query('stat_key=hp&stat_min=%s' % minimum), _accepting({'hp'}))
                self.assertEqual([], filters)

    def test_the_numbered_form_is_read_when_the_plain_form_is_absent(self):
        rows, filters = parse_stat_rows(
            _query('stat1=hp&stat1_min=2&stat2=ap&stat2_min=1'),
            _accepting({'hp', 'ap'}))
        self.assertEqual([('hp', 2), ('ap', 1)], filters)
        self.assertEqual(2, len(rows))

    def test_an_empty_query_still_shows_one_empty_row(self):
        rows, filters = parse_stat_rows(_query(''), _accepting({'hp'}))
        self.assertEqual([{'key': '', 'min': ''}], rows)
        self.assertEqual([], filters)


class TheOrderRowsFollowThePredicate(SimpleTestCase):

    def test_an_order_on_a_key_the_predicate_accepts_is_applied(self):
        rows, orders = parse_order_rows(
            _query('order_key=hp&order_dir=asc'), _accepting({'hp'}))
        self.assertEqual([{'key': 'hp', 'dir': 'asc'}], rows)
        self.assertEqual([('hp', 'asc')], orders)

    def test_the_dofus_predicate_still_drops_an_order_on_hp(self):
        rows, orders = parse_order_rows(
            _query('order_key=hp&order_dir=asc'), _is_searchable_stat_key)
        self.assertEqual([{'key': '', 'dir': 'asc'}], rows)
        self.assertEqual([], orders)

    def test_an_unknown_direction_becomes_descending(self):
        rows, _orders = parse_order_rows(
            _query('order_key=hp&order_dir=sideways'), _accepting({'hp'}))
        self.assertEqual('desc', rows[0]['dir'])

    def test_the_json_form_wins_over_the_plain_form(self):
        payload = json.dumps([{'key': 'ap', 'dir': 'asc'}])
        query = QueryDict(mutable=True)
        query['order_rows_json'] = payload
        query['order_key'] = 'hp'
        _rows, orders = parse_order_rows(query, _accepting({'hp', 'ap'}))
        self.assertEqual([('ap', 'asc')], orders)

    def test_the_json_form_is_bounded(self):
        payload = json.dumps([{'key': 'hp', 'dir': 'desc'}] * (MAX_ORDER_ROWS * 40))
        query = QueryDict(mutable=True)
        query['order_rows_json'] = payload
        rows, orders = parse_order_rows(query, _accepting({'hp'}))
        self.assertEqual(MAX_ORDER_ROWS, len(rows))
        self.assertEqual(MAX_ORDER_ROWS, len(orders))

    def test_a_json_form_that_is_not_a_list_of_objects_gives_one_empty_row(self):
        for payload in ('not json', json.dumps({'key': 'hp'}), json.dumps([1, 'hp', None])):
            with self.subTest(payload=payload):
                query = QueryDict(mutable=True)
                query['order_rows_json'] = payload
                rows, orders = parse_order_rows(query, _accepting({'hp'}))
                self.assertEqual([{'key': '', 'dir': 'desc'}], rows)
                self.assertEqual([], orders)

    def test_the_single_field_form_is_read_last(self):
        _rows, orders = parse_order_rows(
            _query('order_stat=hp&order_direction=ASC'), _accepting({'hp'}))
        self.assertEqual([('hp', 'asc')], orders)


class TheFilterKeysAreNamedOnce(SimpleTestCase):

    def test_the_keys_the_item_list_reads_are_filters(self):
        for key in ('q', 'type', 'min_level', 'max_level', 'stat_key', 'stat_min',
                    'order_rows_json', 'order_key', 'order_dir', 'stat3', 'stat12_min'):
            with self.subTest(key=key):
                self.assertTrue(is_filter_key(key))

    def test_tracking_parameters_and_the_page_number_are_not_filters(self):
        for key in ('utm_source', 'fbclid', 'page', 'statistics', 'stat_', 'statx_min'):
            with self.subTest(key=key):
                self.assertFalse(is_filter_key(key))

    def test_a_key_a_game_adds_is_a_filter_only_for_that_game(self):
        self.assertFalse(is_filter_key('rarity'))
        self.assertTrue(is_filter_key('rarity', extra_keys=('rarity',)))

    def test_every_query_key_the_filter_module_reads_is_a_filter_key(self):
        import ast

        path = os.path.join(os.path.dirname(__file__), 'encyclopedia_filters.py')
        with open(path, encoding='utf-8') as handle:
            tree = ast.parse(handle.read())
        read = set()
        for call in ast.walk(tree):
            if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)):
                continue
            if call.func.attr not in ('get', 'getlist'):
                continue
            if not (isinstance(call.func.value, ast.Name) and call.func.value.id == 'query'):
                continue
            if call.args and isinstance(call.args[0], ast.Constant) \
                    and isinstance(call.args[0].value, str):
                read.add(call.args[0].value)
        self.assertIn('stat_key', read, 'the source was not read at all')
        unnamed = sorted(key for key in read if not is_filter_key(key))
        self.assertEqual([], unnamed)


class TheDofusListStillDropsHpAndPvpRows(TestCase):

    def _context(self, query):
        response = self.client.get('/encyclopedia/', query)
        self.assertEqual(200, response.status_code)
        return response.context

    def test_a_stat_row_on_hp_applies_no_filter_on_the_dofus_list(self):
        context = self._context({'stat_key': 'hp', 'stat_min': '5'})
        self.assertEqual([], context['selected_stat_filters'])
        self.assertEqual('', context['selected_stat_rows'][0]['key'])

    def test_a_stat_row_on_a_searchable_stat_applies_on_the_dofus_list(self):
        context = self._context({'stat_key': 'ap', 'stat_min': '1'})
        self.assertEqual([('ap', 1)], context['selected_stat_filters'])

    def test_an_order_row_on_a_pvp_key_is_dropped_on_the_dofus_list(self):
        context = self._context({'order_key': 'pvp_damage', 'order_dir': 'asc'})
        self.assertEqual('', context['selected_order_rows'][0]['key'])


class TheFilterScriptLivesInOnePartial(SimpleTestCase):

    def _read(self, relative):
        path = os.path.join(os.path.dirname(__file__), 'templates', 'chardata', relative)
        with open(path, encoding='utf-8') as handle:
            return handle.read()

    def test_the_dofus_list_includes_the_partial_and_holds_no_copy_of_the_script(self):
        page = self._read('encyclopedia.html')
        self.assertIn('{% include "chardata/encyclopedia_filter_script.html" %}', page)
        self.assertNotIn("getElementById('stat-filter-list')", page)

    def test_the_partial_is_one_script_that_reads_only_dom_ids(self):
        partial = self._read('encyclopedia_filter_script.html')
        self.assertEqual(1, partial.count('<script'))
        self.assertEqual(1, partial.count('</script>'))
        self.assertNotIn('{{', partial)
        self.assertNotIn('{%', partial)
        self.assertIn("getElementById('stat-filter-list')", partial)
