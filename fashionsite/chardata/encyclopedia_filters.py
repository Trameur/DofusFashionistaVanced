# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Stat rows, order rows and filter keys of the item list, shared by every game.

Each game decides which stat keys a row may name, so the parsers take that
decision as a predicate.
"""
import json

from chardata.util import safe_int

MAX_ORDER_ROWS = 12

FILTER_KEYS = frozenset((
    # /encyclopedia/
    'q', 'type', 'min_level', 'max_level', 'stat_key', 'stat_min',
    'order_rows_json', 'order_key', 'order_dir', 'order_stat',
    'order_direction',
    # /encyclopedia/sets/ and /encyclopedia/monsters/
    'sort', 'drop_kind', 'weak',
))
# Numbered stat filters: stat1, stat1_min, stat2...
FILTER_PREFIX = 'stat'


def is_filter_key(key, extra_keys=()):
    if key in FILTER_KEYS or key in extra_keys:
        return True
    if not key.startswith(FILTER_PREFIX):
        return False
    rest = key[len(FILTER_PREFIX):]
    if rest.endswith('_min'):
        rest = rest[:-len('_min')]
    return rest.isdigit()


def parse_stat_rows(query, is_valid_stat_key):
    """The stat rows shown back in the form and the (key, minimum) pairs to apply."""
    stat_rows = []
    stat_filters = []

    stat_keys = query.getlist('stat_key')
    stat_mins = query.getlist('stat_min')

    if not stat_keys and not stat_mins:
        # Backward compatibility with earlier indexed query params.
        idx = 1
        while ('stat%d' % idx) in query or ('stat%d_min' % idx) in query:
            stat_keys.append(query.get('stat%d' % idx, ''))
            stat_mins.append(query.get('stat%d_min' % idx, ''))
            idx += 1

    row_count = max(len(stat_keys), len(stat_mins), 1)
    for idx in range(row_count):
        stat_key = (stat_keys[idx] if idx < len(stat_keys) else '').strip()
        stat_min_raw = (stat_mins[idx] if idx < len(stat_mins) else '').strip()
        stat_min = safe_int(stat_min_raw, None)

        if stat_key and not is_valid_stat_key(stat_key):
            stat_key = ''

        stat_rows.append({
            'key': stat_key,
            'min': '' if stat_min_raw == '' else stat_min_raw,
        })
        if stat_key and stat_min is not None and stat_min > 0 and is_valid_stat_key(stat_key):
            stat_filters.append((stat_key, stat_min))

    return stat_rows, stat_filters


def parse_order_rows(query, is_valid_stat_key):
    """The order rows shown back in the form and the (key, direction) pairs to apply."""
    order_rows = []
    stat_orders = []

    order_keys = []
    order_dirs = []

    order_rows_json = (query.get('order_rows_json') or '').strip()
    if order_rows_json:
        try:
            parsed_rows = json.loads(order_rows_json)
            if isinstance(parsed_rows, list):
                # DATA_UPLOAD_MAX_NUMBER_FIELDS does not cap JSON rows
                for row in parsed_rows[:MAX_ORDER_ROWS]:
                    if not isinstance(row, dict):
                        continue
                    order_keys.append(str(row.get('key', '')).strip())
                    order_dirs.append(str(row.get('dir', '')).strip().lower())
        except (TypeError, ValueError):
            order_keys = []
            order_dirs = []

    if not order_keys and not order_dirs:
        order_keys = query.getlist('order_key')
        order_dirs = query.getlist('order_dir')

    if not order_keys and not order_dirs:
        # Backward compatibility for earlier single-field ordering params.
        legacy_order_key = (query.get('order_stat') or '').strip()
        legacy_order_dir = (query.get('order_direction') or '').strip().lower()
        if legacy_order_key or legacy_order_dir:
            order_keys = [legacy_order_key]
            order_dirs = [legacy_order_dir]

    order_row_count = max(len(order_keys), len(order_dirs), 1)
    for idx in range(order_row_count):
        order_key = (order_keys[idx] if idx < len(order_keys) else '').strip()
        order_dir = (order_dirs[idx] if idx < len(order_dirs) else '').strip().lower()

        if order_key and not is_valid_stat_key(order_key):
            order_key = ''
        if order_dir not in ('asc', 'desc'):
            order_dir = 'desc'

        order_rows.append({
            'key': order_key,
            'dir': order_dir,
        })

        if order_key and is_valid_stat_key(order_key):
            stat_orders.append((order_key, order_dir))

    return order_rows, stat_orders
