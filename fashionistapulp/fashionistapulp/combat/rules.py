# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The combat rules record of one game version, loaded and checked."""

import json
import os
import re

from fashionistapulp.game_versions import main_game

RECORD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          'combat_rules')

STAGES = ('X', 'F', 'P', 'R', 'V', 'Z')
APPLIED_STAGES = ('P',)
ROUNDINGS = ('floor', 'round', 'none', 'unknown')
SOURCE_KINDS = ('client_code', 'ankama_text', 'readings', 'fan_last_resort')
UNKNOWN = 'unknown'

FIELDS = ('version', 'revision', 'verified_on_tag', 'enabled_stages', 'order', 'rounding',
          'tolerance_per_hit', 'percent_at_or_above_100', 'percent_below_0',
          'crit_flat_on_crit_only', 'pvp_lines', 'best_element_considers_target',
          'steal_heal_share', 'heal_stages', 'base_erosion_percent', 'shield_rules',
          'melee_rule', 'monster_keyword_meanings', 'sources')
UNSOURCED_FIELDS = ('version', 'revision', 'verified_on_tag', 'enabled_stages',
                    'tolerance_per_hit', 'sources')
CHOICES = {
    'percent_at_or_above_100': ('zero', UNKNOWN),
    'percent_below_0': ('amplify', UNKNOWN),
    'crit_flat_on_crit_only': (True, False, UNKNOWN),
    'pvp_lines': ('none', 'additive_before_cap', 'own_stage', UNKNOWN),
    'best_element_considers_target': (True, False, UNKNOWN),
}
DATE = re.compile(r'^\d{4}-\d{2}-\d{2}$')

SHARES_ITS_MAIN_RECORD = ('touchbeta', 'retrobeta')

_LOADED = {}


class RecordError(ValueError):
    pass


def record_version(game_version):
    """The version whose record this version reads: its own, except the Touch and Retro betas."""
    if game_version in SHARES_ITS_MAIN_RECORD:
        return main_game(game_version)
    return game_version


def record_path(game_version):
    return os.path.join(RECORD_DIR, '%s.json' % record_version(game_version))


class RuleSet(object):
    """One version's checked record, read only."""

    __slots__ = ('_record',)

    def __init__(self, record):
        check_record(record)
        object.__setattr__(self, '_record', json.loads(json.dumps(record)))

    def __setattr__(self, name, value):
        raise AttributeError('a RuleSet is read only')

    @property
    def version(self):
        return self._record['version']

    @property
    def revision(self):
        return self._record['revision']

    @property
    def enabled_stages(self):
        return tuple(self._record['enabled_stages'])

    @property
    def tolerance_per_hit(self):
        return self._record['tolerance_per_hit']

    def field(self, name):
        return self._record[name]

    def enabled(self, stage):
        return stage in self._record['enabled_stages']

    def rounding_of(self, stage):
        return self._record['rounding'].get(stage, UNKNOWN)

    def key(self):
        """(version, revision): what a cache key needs of the record."""
        return (self._record['version'], self._record['revision'])

    def rounds(self):
        """Whether an enabled stage rounds, so a hit's mean needs every roll."""
        return any(self.rounding_of(stage) in ('floor', 'round')
                   for stage in self._record['enabled_stages'])


def _check_sources(record, field):
    entries = record['sources'].get(field)
    if not entries or not isinstance(entries, list):
        raise RecordError('%s has no source' % field)
    for entry in entries:
        if (not isinstance(entry, dict) or entry.get('kind') not in SOURCE_KINDS
                or not entry.get('where') or not DATE.match(str(entry.get('date', '')))):
            raise RecordError('%s has a malformed source: %r' % (field, entry))


def _is_unknown(value):
    if isinstance(value, dict):
        return all(_is_unknown(item) for item in value.values())
    if isinstance(value, list):
        return all(_is_unknown(item) for item in value)
    return value == UNKNOWN


def check_record(record):
    """Raises RecordError unless the record follows the format and every known field has a source."""
    if not isinstance(record, dict):
        raise RecordError('a record is an object')
    missing = [field for field in FIELDS if field not in record]
    extra = [field for field in record if field not in FIELDS]
    if missing or extra:
        raise RecordError('fields missing %s, unknown %s' % (missing, extra))
    if not isinstance(record['sources'], dict):
        raise RecordError('sources is an object')
    if type(record['revision']) is not int or record['revision'] < 1:
        raise RecordError('revision is a positive integer')
    stages = record['enabled_stages']
    if not isinstance(stages, list) or len(set(stages)) != len(stages):
        raise RecordError('enabled_stages is a list of distinct stages')
    for stage in stages:
        if stage not in STAGES:
            raise RecordError('unknown stage %r' % stage)
        if stage not in APPLIED_STAGES:
            raise RecordError('stage %s has no code yet' % stage)
        _check_sources(record, stage)
    if not isinstance(record['rounding'], dict):
        raise RecordError('rounding is an object')
    for stage, rounding in record['rounding'].items():
        if stage not in STAGES or rounding not in ROUNDINGS:
            raise RecordError('rounding %r: %r' % (stage, rounding))
    if len(stages) > 1:
        order = record['order']
        if not isinstance(order, list) or any(stage not in order for stage in stages):
            raise RecordError('several stages need a sourced order')
    tolerance = record['tolerance_per_hit']
    if type(tolerance) is not int or tolerance < 0:
        raise RecordError('tolerance_per_hit is a whole number of points')
    if any(record['rounding'].get(stage, UNKNOWN) == UNKNOWN for stage in stages) and not tolerance:
        raise RecordError('a stage of unknown rounding needs a tolerance')
    for field, allowed in CHOICES.items():
        if record[field] not in allowed:
            raise RecordError('%s: %r' % (field, record[field]))
    for field in FIELDS:
        if field in UNSOURCED_FIELDS or _is_unknown(record[field]):
            continue
        _check_sources(record, field)
    return record


def read_record(path):
    with open(path, encoding='utf-8') as handle:
        return json.load(handle)


def load_rules(game_version):
    """The RuleSet of this version, None when it has no record."""
    own = record_version(game_version)
    if own not in _LOADED:
        path = record_path(game_version)
        if not os.path.exists(path):
            _LOADED[own] = None
        else:
            record = read_record(path)
            if record.get('version') != own:
                raise RecordError('%s holds the record of %r' % (path, record.get('version')))
            _LOADED[own] = RuleSet(record)
    return _LOADED[own]
