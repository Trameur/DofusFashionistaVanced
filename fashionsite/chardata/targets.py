# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""What a turn can be cast on: a monster grade read from its own version's database, or a build the viewer may open."""

import pathlib
import re
import sqlite3

from django.conf import settings

from fashionistapulp.combat.mitigation import is_immune, percent_resisted
from fashionistapulp.combat.rules import load_rules
from fashionistapulp.dofus_constants import AIR, EARTH, FIRE, NEUTRAL, WATER
from fashionistapulp.fashion_util import strip_accents
from fashionistapulp.fashionista_config import get_items_db_path
from fashionistapulp.game_versions import main_game
from fashionistapulp.translation import get_supported_language

TARGET_VERSIONS = ('dofus3', 'beta', 'dofus2', 'touch', 'retro')
PERCENT_ONLY_GAMES = ('dofus2', 'touch', 'retro')
ELEMENTS = (EARTH, FIRE, WATER, AIR, NEUTRAL)
TOKEN = re.compile(r'^m([1-9][0-9]{0,9})\.([1-9][0-9]{0,2})$')

PERCENT_COLUMNS = ('earth_resistance', 'fire_resistance', 'water_resistance',
                   'air_resistance', 'neutral_resistance')
FLAT_COLUMNS = ('earth_flat_resistance', 'fire_flat_resistance', 'water_flat_resistance',
                'air_flat_resistance', 'neutral_flat_resistance')
BUILD_TOKEN = re.compile(r'^b([1-9][0-9]{0,9}|s[A-Za-z0-9._-]{1,64})$')
CRIT_COLUMN = 'critical_damage_reduction'
PUSH_COLUMN = 'push_damage_reduction'
SEARCH_LIMIT = 20
BUILD_LIMIT = 100

_GRADES = {}
_INDEX = {}


class Target(object):
    """One thing a turn lands on; key_parts() is everything the damage reads of it."""

    __slots__ = ('version', 'kind', 'ref', 'level', 'hp', 'percent', 'flat', 'crit_flat',
                 'push_flat', 'received', 'pvp_percent', 'pvp_flat', 'is_player', 'label',
                 'unknown', 'door', 'char_class', 'source')

    def __init__(self, **fields):
        for name in self.__slots__:
            object.__setattr__(self, name, fields.pop(name, None))
        if fields:
            raise TypeError('unknown target fields %s' % sorted(fields))
        object.__setattr__(self, 'ref', tuple(self.ref or ()))
        object.__setattr__(self, 'percent', tuple(self.percent or (None,) * len(ELEMENTS)))
        if self.flat is not None:
            object.__setattr__(self, 'flat', tuple(self.flat))
        object.__setattr__(self, 'is_player', bool(self.is_player))
        object.__setattr__(self, 'unknown', tuple(self.unknown or ()))

    def __setattr__(self, name, value):
        raise AttributeError('a Target is read only')

    def replace(self, **changes):
        fields = {name: getattr(self, name) for name in self.__slots__}
        fields.update(changes)
        return Target(**fields)

    def key_parts(self):
        return ('target', self.version, self.kind, self.ref, self.level, self.hp,
                self.percent, self.flat, self.crit_flat, self.push_flat, self.received,
                self.pvp_percent, self.pvp_flat, self.is_player)

    def token(self):
        if self.kind == 'monster':
            return 'm%d.%d' % (self.ref[1], self.ref[2])
        return self.door or ''

    def counts_pvp(self, attacker_is_player=True):
        """Whether this target's PvP resistances count: both players, and the record adds them."""
        return (self.is_player and attacker_is_player
                and load_rules(self.version).counts_pvp_lines())

    def percent_of(self, element, attacker_is_player=True):
        """The % resistance a hit in this element meets, None when unknown."""
        if element not in ELEMENTS:
            return None
        value = self.percent[ELEMENTS.index(element)]
        if value is not None and self.pvp_percent and self.counts_pvp(attacker_is_player):
            value += self.pvp_percent[ELEMENTS.index(element)] or 0
        return percent_resisted(value, self.is_player, self.version)

    def flat_of(self, element, critical=False, attacker_is_player=True):
        """The flat resistance a hit in this element meets, the critical one on a critical row."""
        value = 0
        if element in ELEMENTS:
            index = ELEMENTS.index(element)
            value += (self.flat or (0,) * len(ELEMENTS))[index] or 0
            if self.pvp_flat and self.counts_pvp(attacker_is_player):
                value += self.pvp_flat[index] or 0
        if critical and self.crit_flat and load_rules(self.version).field(
                'crit_flat_on_crit_only') is True:
            value += self.crit_flat
        return value

    def immune_elements(self):
        return [element for element in ELEMENTS if is_immune(self.percent_of(element))]

    def weakest_elements(self):
        known = [(self.percent_of(element), element) for element in ELEMENTS
                 if self.percent_of(element) is not None]
        if not known:
            return []
        lowest = min(value for value, _element in known)
        if all(value == lowest for value, _element in known):
            return []
        return [element for value, element in known if value == lowest]


def _connect(game_version):
    path = pathlib.Path(get_items_db_path(game_version))
    if not path.exists():
        return None
    return sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)


def _table_columns(cursor, table):
    return {row[1] for row in cursor.execute('PRAGMA table_info(%s)' % table)}


def _memo_key(game_version, ref):
    return (game_version, ref, getattr(settings, 'SITE_VERSIONS', {}).get(game_version, ''))


def _grade_row(game_version, monster_id, grade):
    """{column: value or None} of one grade and {language: name}, None when either is missing."""
    key = _memo_key(game_version, ('m', monster_id, grade))
    if key in _GRADES:
        return _GRADES[key]
    found = None
    conn = _connect(game_version)
    if conn is not None:
        try:
            cursor = conn.cursor()
            grade_columns = _table_columns(cursor, 'monster_grades')
            name_columns = _table_columns(cursor, 'monster_names')
            if ({'monster_ankama_id', 'grade'} <= grade_columns
                    and {'monster_ankama_id', 'language', 'name'} <= name_columns):
                wanted = ('level', 'life_points') + PERCENT_COLUMNS + FLAT_COLUMNS + (
                    CRIT_COLUMN, PUSH_COLUMN)
                selected = ', '.join(column if column in grade_columns else 'NULL'
                                     for column in wanted)
                row = cursor.execute(
                    'SELECT %s FROM monster_grades WHERE monster_ankama_id = ? AND grade = ?'
                    % selected, (monster_id, grade)).fetchone()
                names = {language: name for language, name in cursor.execute(
                    'SELECT language, name FROM monster_names WHERE monster_ankama_id = ?',
                    (monster_id,)) if name}
                if row is not None and names:
                    found = (dict(zip(wanted, row)), names)
        finally:
            conn.close()
    _GRADES[key] = found
    return found


def _name_in(names, language):
    return names.get(language) or names.get('en') or next(iter(sorted(names.values())), '')


def monster_target(game_version, monster_id, grade, language=None):
    """The Target of one monster grade of this version, None when the version, monster or grade is unknown."""
    if game_version not in TARGET_VERSIONS or load_rules(game_version) is None:
        return None
    entry = _monster_index(game_version)[1].get(monster_id)
    if entry is None or grade not in {known for known, _level, _hp in entry[2]}:
        return None
    found = _grade_row(game_version, monster_id, grade)
    if found is None:
        return None
    row, names = found
    percent = tuple(row[column] for column in PERCENT_COLUMNS)
    flat = tuple(row[column] for column in FLAT_COLUMNS)
    held = ('level', 'life_points') + PERCENT_COLUMNS
    # Their game data gives a grade no flat, critical or pushback resistance
    if main_game(game_version) not in PERCENT_ONLY_GAMES:
        held += FLAT_COLUMNS + (CRIT_COLUMN, PUSH_COLUMN)
    unknown = [column for column in held if row[column] is None]
    return Target(version=game_version, kind='monster', ref=('m', monster_id, grade),
                  level=row['level'], hp=row['life_points'], percent=percent,
                  flat=None if all(value is None for value in flat) else flat,
                  crit_flat=row[CRIT_COLUMN], push_flat=row[PUSH_COLUMN],
                  is_player=False, unknown=unknown,
                  label=_name_in(names, language or get_supported_language()))


def build_target(char, solution, game_version, door=''):
    """The Target of a build's final characteristics, as its build page shows them."""
    from chardata.build_name import display_name
    from chardata.stat_availability import stats_with_no_source
    stats = solution.get_stats_total()
    absent = stats_with_no_source(game_version)

    def read(keys):
        return tuple(stats.get(key) or 0 for key in keys)

    def granted(keys):
        return None if all(key in absent for key in keys) else read(keys)

    return Target(version=game_version, kind='build', ref=('b', char.pk), level=char.level,
                  hp=stats.get('hp'), percent=read(['%sresper' % e for e in ELEMENTS]),
                  flat=read(['%sres' % e for e in ELEMENTS]), crit_flat=stats.get('crires') or 0,
                  push_flat=stats.get('pshres') or 0,
                  received=read(('respermee', 'resperran', 'resperwea')),
                  pvp_percent=granted(['pvp%sresper' % e for e in ELEMENTS]),
                  pvp_flat=granted(['pvp%sres' % e for e in ELEMENTS]),
                  is_player=True, label=display_name(char), door=door, char_class=char.char_class,
                  source=(char, solution))


def read_build_target(request, game_version, value):
    """(Target or None, refusal) of a posted 'b<id>' or 'bs<link>'; every refusal is 'build' and reads the same rows whether the build exists or not."""
    from django.core.exceptions import PermissionDenied
    from django.http import Http404
    from chardata.solution import get_solution
    from chardata.util import get_char_possibly_encoded_or_raise
    match = BUILD_TOKEN.fullmatch(value)
    if match is None or request is None:
        return None, 'build'
    if request.user.is_anonymous:
        from chardata.anon_projects import get_anon_char_ids
        get_anon_char_ids(request)
    try:
        char = get_char_possibly_encoded_or_raise(request, match.group(1))
    except (Http404, PermissionDenied):
        return None, 'build'
    if char.game_version != game_version or char.deleted:
        return None, 'build'
    solution = get_solution(char)
    if solution is None:
        return None, 'build'
    return build_target(char, solution, game_version, value), ''


def own_build_targets(request, game_version, limit=BUILD_LIMIT):
    """[{'name', 'class', 'level', 'target'}] of the viewer's own builds of this version, newest first."""
    from chardata.build_name import display_name
    from chardata.models import Char
    from chardata.translation_util import LOCALIZED_CHARACTER_CLASSES
    if game_version not in TARGET_VERSIONS or load_rules(game_version) is None:
        return []
    if request.user.is_anonymous:
        from chardata.anon_projects import get_anon_char_ids
        chars = Char.objects.filter(pk__in=set(get_anon_char_ids(request).values()))
    else:
        chars = Char.objects.filter(owner=request.user)
    chars = chars.filter(game_version=game_version, deleted=False)
    chars = chars.exclude(minimal_solution__isnull=True).exclude(minimal_solution=b'')
    chars = chars.order_by('-pk')[:limit]
    return [{'name': display_name(char),
             'class': str(LOCALIZED_CHARACTER_CLASSES.get(char.char_class, char.char_class)),
             'level': char.level, 'target': 'b%d' % char.pk} for char in chars]


def read_target(game_version, value, language=None, request=None):
    """(Target or None, refusal) of a posted 'm<id>.<grade>', 'b<id>' or 'bs<link>'; refusal is '' when it reads."""
    if not value:
        return None, ''
    if not isinstance(value, str):
        return None, 'malformed'
    if value.startswith('b'):
        if game_version not in TARGET_VERSIONS or load_rules(game_version) is None:
            return None, 'build'
        return read_build_target(request, game_version, value)
    match = TOKEN.fullmatch(value)
    if match is None:
        return None, 'malformed'
    if game_version not in TARGET_VERSIONS or load_rules(game_version) is None:
        return None, 'version'
    monster_id, grade = int(match.group(1)), int(match.group(2))
    target = monster_target(game_version, monster_id, grade, language)
    if target is not None:
        return target, ''
    if monster_id not in _monster_index(game_version)[1]:
        return None, 'monster'
    return None, 'grade'


def _normalized(value):
    return strip_accents(value or '').lower().strip()


def _normalized_names(names):
    normalized = {language: _normalized(name) for language, name in names.items()}
    normalized[None] = _normalized(_name_in(names, None))
    return normalized


def _monster_index(game_version):
    """([(monster id, {language: name}, [(grade, level, hp)])], {monster id: entry}, {monster id: {language or None for the fallback: normalized name}}) of the named monsters with grades."""
    key = _memo_key(game_version, 'index')
    if key in _INDEX:
        return _INDEX[key]
    index = ([], {}, {})
    conn = _connect(game_version)
    if conn is not None:
        try:
            cursor = conn.cursor()
            grade_columns = _table_columns(cursor, 'monster_grades')
            name_columns = _table_columns(cursor, 'monster_names')
            if ({'monster_ankama_id', 'grade'} <= grade_columns
                    and {'monster_ankama_id', 'language', 'name'} <= name_columns):
                level = 'level' if 'level' in grade_columns else 'NULL'
                life = 'life_points' if 'life_points' in grade_columns else 'NULL'
                grades = {}
                for monster_id, grade, grade_level, hp in cursor.execute(
                        'SELECT monster_ankama_id, grade, %s, %s FROM monster_grades '
                        'ORDER BY monster_ankama_id, grade' % (level, life)):
                    grades.setdefault(monster_id, []).append((grade, grade_level, hp))
                names = {}
                for monster_id, language, name in cursor.execute(
                        'SELECT monster_ankama_id, language, name FROM monster_names'):
                    if name and monster_id in grades:
                        names.setdefault(monster_id, {})[language] = name
                entries = [(monster_id, names[monster_id], grades[monster_id])
                           for monster_id in sorted(names)]
                index = (entries, {entry[0]: entry for entry in entries},
                         {monster_id: _normalized_names(monster_names)
                          for monster_id, monster_names, _grades in entries})
        finally:
            conn.close()
    _INDEX[key] = index
    return index


def search_monsters(game_version, query, language=None, limit=SEARCH_LIMIT):
    """[{'id', 'name', 'grades': [{'grade', 'level', 'hp', 'target'}]}] whose name in the language holds the query."""
    if game_version not in TARGET_VERSIONS or load_rules(game_version) is None:
        return []
    needle = _normalized(query)
    if not needle:
        return []
    language = language or get_supported_language()
    found = []
    index = _monster_index(game_version)
    for monster_id, names, grades in index[0]:
        name = _name_in(names, language)
        shown = index[2][monster_id].get(language) or index[2][monster_id][None]
        if needle not in shown and needle != str(monster_id):
            continue
        found.append((not shown.startswith(needle), shown, monster_id, name, grades))
    found.sort(key=lambda entry: entry[:3])
    return [{'id': monster_id, 'name': name,
             'grades': [{'grade': grade, 'level': level, 'hp': hp,
                         'target': 'm%d.%d' % (monster_id, grade)}
                        for grade, level, hp in grades]}
            for _later, _shown, monster_id, name, grades in found[:limit]]
