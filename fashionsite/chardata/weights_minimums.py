# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Rows and state of the weights and minimums page."""
from chardata.min_stats import get_min_stats, get_min_stats_by_key, set_min_stats
from chardata.stat_availability import stats_with_no_source
from chardata.stat_icons import get_stat_icon_path
from chardata.stats_weights import get_stats_weights
from chardata.temporix_mode import char_uses_temporix
from chardata.translation_util import localized_stat_name
from chardata.util import safe_int
from chardata.wizard_sliders import (AGGREGATE_SLIDERS, Slider, _damage_is_derived,
                                     _element_keys, _label, _members, _raw_sections,
                                     _sections, _shown_value, _unreachable_stats)
from fashionistapulp.dofus_constants import NON_STAT_WEIGHT_KEYS, STAT_NAME_TO_KEY, \
    get_stat_maximum
from fashionistapulp.model import _minimum_dependencies
from fashionistapulp.structure import get_structure
from static_s3.templatetags.static_s3 import static

CAP_SHOWN = ('ap', 'mp', 'range')


def _get_stat_icon_url(stat_key):
    icon_path = get_stat_icon_path(stat_key)
    return static(icon_path) if icon_path else ''


def _get_adv_stat_icon_urls(structure, adv_stat):
    stat_name_to_key = {stat.name: stat.key for stat in structure.get_stats_list()}
    local_name = adv_stat.get('local_name', '')
    ordered_stat_names = list(adv_stat.get('stats', []))

    if local_name and ' + ' in local_name:
        localized_name_to_stat_name = {
            localized_stat_name(stat.name): stat.name for stat in structure.get_stats_list()
        }
        ordered_from_label = []
        for localized_part in local_name.split(' + '):
            stat_name = localized_name_to_stat_name.get(localized_part)
            if stat_name in ordered_stat_names and stat_name not in ordered_from_label:
                ordered_from_label.append(stat_name)
        if len(ordered_from_label) == len(ordered_stat_names):
            ordered_stat_names = ordered_from_label

    if adv_stat.get('key') in ('sum_perc_res', 'sum_res'):
        ordered_stat_names = [
            stat_name for stat_name in ordered_stat_names
            if stat_name not in ('% Neutral Resist', 'Neutral Resist')
        ] + [
            stat_name for stat_name in ordered_stat_names
            if stat_name in ('% Neutral Resist', 'Neutral Resist')
        ]

    icon_urls = []
    for stat_name in ordered_stat_names:
        stat_key = stat_name_to_key.get(stat_name)
        icon_url = _get_stat_icon_url(stat_key)
        if icon_url:
            icon_urls.append(icon_url)
    return icon_urls


def _version(char):
    return getattr(char, 'game_version', None) or 'dofus3'


def _is_set(value):
    return value != '' and value is not None


def _kept_minimum(key, value):
    return _is_set(value) and not (key == 'range' and value == 0)


def minimum_keys(game_version):
    """Stat keys a minimum can be reached on: a source, or a stat the solver counts toward it."""
    no_source = stats_with_no_source(game_version)
    dependencies = _minimum_dependencies(game_version)
    return [stat.key for stat in get_structure(game_version).get_stats_list()
            if stat.key not in no_source or stat.name in dependencies]


def _weight_keys(game_version):
    return {key for _key, _label_text, keys in _sections(game_version) for key in keys}


def _caps(char):
    caps = get_stat_maximum(_version(char), temporix=char_uses_temporix(char))
    return {STAT_NAME_TO_KEY[name]: cap for name, cap in caps.items()
            if name in STAT_NAME_TO_KEY}


def _stored_minimums(char):
    stored = get_min_stats_by_key(char)
    stored.pop('adv_mins', None)
    return {key: value for key, value in stored.items() if _kept_minimum(key, value)}


def edit_sections(char):
    game_version = _version(char)
    unreachable = _unreachable_stats(game_version)
    derived = _damage_is_derived(unreachable)
    weight_keys = _weight_keys(game_version)
    min_keys = minimum_keys(game_version)
    caps = _caps(char)
    stored = _stored_minimums(char)
    placed = {key for _key, _label_text, keys in _raw_sections() for key in keys}
    unplaced = [key for key in min_keys if key not in placed]

    def stat_row(key):
        weight = key in weight_keys
        is_derived = key == 'dam' and derived
        minimum = key in min_keys
        if not (weight or is_derived or minimum):
            return None
        cap = caps.get(key) if minimum else None
        return {'key': key, 'label': _label(key, game_version),
                'icon_url': _get_stat_icon_url(key), 'aggregate': False,
                'members': [], 'member': False, 'weight': weight,
                'derived': is_derived,
                'sum_of': _element_keys('%sdam') if is_derived else [],
                'minimum': minimum, 'cap': cap, 'cap_shown': key in CAP_SHOWN}

    sections = []
    for section_key, label, keys in _raw_sections():
        if section_key == 'special':
            keys = list(keys) + unplaced
        rows_by_key = {}
        for key in keys:
            if key not in AGGREGATE_SLIDERS:
                row = stat_row(key)
                if row is not None:
                    rows_by_key[key] = row
        rows = []
        for key in keys:
            if key in AGGREGATE_SLIDERS:
                members = [member for member in AGGREGATE_SLIDERS[key]
                           if member in rows_by_key]
                if not members:
                    continue
                for member in members:
                    rows_by_key[member]['member'] = True
                rows.append({'key': key, 'label': _label(key, game_version),
                             'icon_url': '', 'aggregate': True, 'members': members,
                             'member': False, 'weight': key in weight_keys,
                             'derived': False, 'sum_of': [],
                             'minimum': any(rows_by_key[member]['minimum']
                                            for member in members),
                             'cap': None, 'cap_shown': False})
            elif key in rows_by_key:
                rows.append(rows_by_key[key])
        if not rows:
            continue
        count = len([row for row in rows
                     if not row['aggregate'] and row['minimum'] and row['key'] in stored])
        sections.append({'key': section_key, 'label': label, 'rows': rows,
                         'open': section_key == 'apmprange' or count > 0,
                         'count': count})
    return sections


def combined_rows(char):
    structure = get_structure(_version(char))
    rows = structure.get_adv_mins()
    for row in rows:
        row['icon_urls'] = _get_adv_stat_icon_urls(structure, row)
    return rows


def combined_open(char):
    adv_mins = get_min_stats_by_key(char).get('adv_mins', {})
    return any(_is_set(value) for value in adv_mins.values())


def other_saved_rows(char):
    game_version = _version(char)
    offered = set(minimum_keys(game_version))
    names = {stat.key: stat.name for stat in get_structure(game_version).get_stats_list()}
    return [{'key': key, 'label': localized_stat_name(names[key], game_version),
             'icon_url': _get_stat_icon_url(key)}
            for key in sorted(_stored_minimums(char))
            if key not in offered and key in names]


def page_state(char):
    game_version = _version(char)
    unreachable = _unreachable_stats(game_version)
    stored_weights = get_stats_weights(char, persist=False)
    weights = {key: _shown_value(value) for key, value in stored_weights.items()
               if key not in NON_STAT_WEIGHT_KEYS}

    by_key = get_min_stats_by_key(char)
    minimums = {stat.key: '' for stat in get_structure(game_version).get_stats_list()}
    for key, value in by_key.items():
        if key != 'adv_mins':
            minimums[key] = value if _kept_minimum(key, value) else ''
    for adv in get_structure(game_version).get_adv_mins():
        value = by_key.get('adv_mins', {}).get(adv['key'])
        minimums[adv['key']] = value if _is_set(value) else ''

    ranges = {}
    members = {}
    for _key, _label_text, keys in _sections(game_version):
        for key in keys:
            key_members = (_members(key, unreachable) if key in AGGREGATE_SLIDERS
                           else None)
            if key_members:
                members[key] = key_members
            slider = Slider(key, '', False, key_members)
            slider.calculate(stored_weights)
            ranges[key] = [slider.min_value, slider.max_value]
    return {'weights': weights, 'minimums': minimums, 'ranges': ranges,
            'members': members}


def merge_minimum_fields(char, post):
    """Saves the posted min_ fields over the stored minimums; a field not posted keeps its value."""
    structure = get_structure(_version(char))
    merged = dict(get_min_stats(char))
    adv_mins = dict(merged.get('adv_mins') or {})

    def merge(target, name, field_name):
        if field_name not in post:
            return
        raw = (post.get(field_name) or '').strip()
        if raw == '':
            target.pop(name, None)
            return
        value = safe_int(raw)
        if value is not None:
            target[name] = value

    adv_stats = structure.get_adv_mins()
    adv_keys = {adv['key'] for adv in adv_stats}
    stat_keys = set()
    for stat in structure.get_stats_list():
        if stat.key in adv_keys:
            continue
        stat_keys.add(stat.key)
        merge(merged, stat.name, 'min_%s' % stat.key)
    if 'hp' not in stat_keys:
        merge(merged, 'HP', 'min_hp')
    for adv in adv_stats:
        merge(adv_mins, adv['name'], 'min_%s' % adv['key'])
    merged['adv_mins'] = adv_mins
    set_min_stats(char, merged)
