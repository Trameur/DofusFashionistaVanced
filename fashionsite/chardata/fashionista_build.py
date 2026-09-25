# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The fashionista-build format: a build another site sends here, and ours written out the same way."""

import base64
import binascii
import json
import re
import urllib.parse

from django.utils import translation
from django.utils.translation import gettext_lazy

from chardata.build_import import _can_be_worn_twice
from chardata.dofusbook_import import ImportError_, MAX_POINTS
from fashionistapulp.dofus_constants import (CHARACTER_CLASSES, SLOTS,
                                             STATS_NAMES,
                                             TYPE_NAME_TO_SLOT_NUMBER,
                                             max_scroll_for_version)
from fashionistapulp.game_versions import get_game_version, version_keys
from fashionistapulp.structure import PET_VARIANT_ID_BASE, get_structure

FORMAT = 'fashionista-build'
FORMAT_VERSION = 1
READABLE_VERSIONS = (1,)

MAX_LINK_DATA = 6000
MAX_JSON = 32000
MAX_ITEMS = 32
MAX_STAT_LINES = 40
MAX_STAT_VALUE = 99999
MAX_LEVEL = 200
NAME_LENGTH = 50
STAT_KEY_LENGTH = 40
SOURCE_LENGTH = 190
BACK_URL_LENGTH = 2000
CLASS_DIGITS = 4
ISSUES_PER_CODE = 20

SITE_HOST = 'dofusfashionista.gg'
SCHEMA_PATH = '/api/v1/import/schema/%d/' % FORMAT_VERSION
VALIDATE_PATH = '/api/v1/import/validate/'

#: (field name, our stat name), in our base stat order
CHARACTERISTICS = tuple((name.lower(), name) for name, _key in STATS_NAMES)

#: (field name, build option)
EXOS = (('ap', 'ap_exo'), ('mp', 'mp_exo'), ('range', 'range_exo'))

FIELDS = ('format', 'version', 'game', 'class', 'level', 'name', 'items',
          'characteristics', 'scrolls', 'exos', 'source', 'back_url')
ITEM_FIELDS = ('id', 'type', 'stats')
STAT_LINE_FIELDS = ('key', 'value')

ERRORS = (
    ('too_large', gettext_lazy('This build is too large to be read.')),
    ('bad_encoding', gettext_lazy('The data in the link is not valid base64url.')),
    ('not_json', gettext_lazy('This build is not valid JSON.')),
    ('not_an_object', gettext_lazy('This build must be a JSON object.')),
    ('wrong_format', gettext_lazy('The format field must say fashionista-build.')),
    ('unsupported_version', gettext_lazy('Only version 1 of the format can be read.')),
    ('unknown_game', gettext_lazy('The game field must be dofus3, beta, dofus2, touch or retro.')),
    ('bad_items', gettext_lazy('The items field must be a list of Ankama ids, or of objects with an id.')),
    ('too_many_items', gettext_lazy('Too many items for one build.')),
    ('bad_stats', gettext_lazy('The stats of an item must be a list of lines, each with a key and a whole number.')),
    ('bad_level', gettext_lazy('The level must be a whole number from 1 to 200.')),
    ('bad_characteristics', gettext_lazy('Characteristics and scrolls only take vitality, wisdom, strength, intelligence, chance and agility, each a whole number from 0 up.')),
    ('bad_exos', gettext_lazy('Exos only take ap, mp and range, each true or false.')),
    ('no_known_item', gettext_lazy('None of these items is in our catalogue for this game.')),
    ('wrong_game', gettext_lazy('These items belong to another version of the game. Check the game field.')),
    ('rate_limited', gettext_lazy('Too many checks from your address. Wait a few minutes.')),
    ('method_not_allowed', gettext_lazy('Send the build with POST.')),
)

WARNINGS = (
    ('unknown_item', gettext_lazy('This id is not in our catalogue for this game: the piece is left out.')),
    ('item_from_another_game', gettext_lazy('This id only exists in another version of the game: the piece is left out.')),
    ('slot_full', gettext_lazy('No slot is left for this piece: it is left out.')),
    ('already_placed', gettext_lazy('This piece is already worn as many times as the game allows: it is left out.')),
    ('removed_item', gettext_lazy('This piece is no longer in the game.')),
    ('item_above_level', gettext_lazy('This piece needs a higher level than the build has.')),
    ('unknown_stat', gettext_lazy('This stat key does not exist: the line is left out.')),
    ('duplicate_stat', gettext_lazy('This stat key comes more than once on the piece: the last line is kept.')),
    ('stat_out_of_range', gettext_lazy('This value is outside what the piece can roll: it is kept as sent.')),
    ('unknown_class', gettext_lazy('Unknown class: the player picks one.')),
    ('class_not_in_game', gettext_lazy('This class does not exist in this game: the player picks another one.')),
    ('scroll_capped', gettext_lazy('A scroll above what this game allows is lowered to its cap.')),
    ('exos_not_in_game', gettext_lazy('This game has no exos: they are left out.')),
    ('name_truncated', gettext_lazy('The name is cut to the length build names allow.')),
    ('name_ignored', gettext_lazy('The name must be text: it is left out.')),
    ('source_ignored', gettext_lazy('The source field is not a domain name: it is ignored.')),
    ('back_url_ignored', gettext_lazy('The back_url field is not an https address: it is ignored.')),
    ('unknown_field', gettext_lazy('Unknown field: it is ignored.')),
)

_MESSAGES = dict(ERRORS + WARNINGS)

_BASE64URL = re.compile(r'^[A-Za-z0-9_-]*={0,2}$')

_CONTROL = re.compile(r'[\x00-\x1f\x7f]+')


class FormatError(ImportError_):
    """Stops a sent build; reason is a stable code, source the sender's domain when it was readable."""

    def __init__(self, reason, source=''):
        super().__init__(reason)
        self.source = source


def message(code):
    return str(_MESSAGES.get(code, code))


def _whole(value):
    """The value as an int when it is a whole JSON number, else None."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer() and abs(value) < 1e15:
        return int(value)
    return None


def _refuse_constant(name):
    raise ValueError(name)


def looks_sent(text):
    """Whether a paste is a JSON object, which the import reads in this format."""
    stripped = (text or '').strip()
    return stripped.startswith('{') and stripped.endswith('}')


def decode_link_data(data):
    """The JSON text a link's data parameter carries; FormatError when it cannot be decoded."""
    data = (data or '').strip()
    if len(data) > MAX_LINK_DATA:
        raise FormatError('too_large')
    if data.startswith('{'):
        return data
    # Plain base64 and a '+' the query string turned into a space still read
    data = data.replace(' ', '+').replace('+', '-').replace('/', '_')
    if not _BASE64URL.match(data):
        raise FormatError('bad_encoding')
    data = data.rstrip('=')
    try:
        return base64.urlsafe_b64decode(data + '=' * (-len(data) % 4)).decode('utf-8')
    except (binascii.Error, ValueError, UnicodeDecodeError):
        raise FormatError('bad_encoding')


def encode_link_data(payload):
    """base64url of the compact JSON, without padding."""
    text = json.dumps(payload, ensure_ascii=False, separators=(',', ':'))
    return base64.urlsafe_b64encode(text.encode('utf-8')).decode('ascii').rstrip('=')


def parse_json(text):
    """The JSON object in the text; FormatError otherwise."""
    text = (text or '').strip()
    if len(text) > MAX_JSON:
        raise FormatError('too_large')
    try:
        payload = json.loads(text, parse_constant=_refuse_constant)
        # A lone surrogate escape such as \ud800 parses but can never be written out
        json.dumps(payload, ensure_ascii=False).encode('utf-8')
    except (ValueError, RecursionError):
        raise FormatError('not_json')
    if not isinstance(payload, dict):
        raise FormatError('not_an_object')
    return payload


def _domain(value):
    """The lowercase ASCII domain in value, without www., or None."""
    from chardata.text_build_view import _DOMAIN, _INTERNAL_TLDS
    if not isinstance(value, str):
        return None
    value = value.strip()
    if '://' in value:
        try:
            value = urllib.parse.urlsplit(value).hostname or ''
        except ValueError:
            return None
    try:
        host = value.rstrip('.').encode('idna').decode('ascii').lower()
    except (UnicodeError, ValueError):
        return None
    if host.startswith('www.'):
        host = host[4:]
    if (not host or len(host) > SOURCE_LENGTH or not _DOMAIN.match(host)
            or host.split('.')[-1] in _INTERNAL_TLDS):
        return None
    return host


def _back_url(value):
    """(address, host shown) for an https address, or None."""
    if not isinstance(value, str) or len(value) > BACK_URL_LENGTH:
        return None
    value = value.strip()
    if _CONTROL.search(value) or ' ' in value:
        return None
    try:
        parts = urllib.parse.urlsplit(value)
        port = parts.port
    except ValueError:
        return None
    if (parts.scheme.lower() != 'https' or parts.username or parts.password
            or port not in (None, 443)):
        return None
    host = _domain(parts.hostname or '')
    if host is None:
        return None
    return value, host


def _class_of(value):
    """Our class key for a class key in any case or an Ankama breed id, else None."""
    from chardata.character_look import CLASS_TO_BREED
    if isinstance(value, str):
        wanted = value.strip()
        if wanted.isascii() and wanted.isdigit():
            if len(wanted) > CLASS_DIGITS:
                return None
            value = int(wanted)
        else:
            return next((key for key in CHARACTER_CLASSES
                         if key.lower() == wanted.lower()), None)
    breed = _whole(value)
    if breed is None:
        return None
    return next((key for key, number in CLASS_TO_BREED.items()
                 if number == breed), None)


class Reading:
    """What one payload says, and what is wrong with it."""

    def __init__(self, language):
        self.language = language
        self.errors = []
        self.warnings = []
        self.errors_omitted = 0
        self.warnings_omitted = 0
        self._per_code = {}
        self.game = None
        self.char_class = None
        self.level = None
        self.name = ''
        self.source = ''
        self.back_url = None
        self.back_host = None
        self.points = {}
        self.scrolls = {}
        self.exos = None
        self.pieces = []
        self.worn_twice = []
        self.gelano_mp = False
        self.build = None

    def _kept(self, code):
        self._per_code[code] = self._per_code.get(code, 0) + 1
        return self._per_code[code] <= ISSUES_PER_CODE

    def error(self, code, path, **details):
        if self._kept(code):
            self.errors.append(dict(details, code=code, path=path))
        else:
            self.errors_omitted += 1

    def warn(self, code, path, **details):
        if self._kept(code):
            self.warnings.append(dict(details, code=code, path=path))
        else:
            self.warnings_omitted += 1

    @property
    def valid(self):
        return not self.errors


def _unknown_fields(reading, entry, known, path):
    for field in entry:
        if field not in known:
            reading.warn('unknown_field', path + str(field)[:60])


def _read_six(reading, payload, field, ceiling):
    """{our stat name: value} for characteristics or scrolls; None when absent or wrong."""
    value = payload.get(field)
    if value is None:
        return None
    if not isinstance(value, dict):
        reading.error('bad_characteristics', field)
        return None
    names = dict(CHARACTERISTICS)
    read = {}
    for key, number in value.items():
        whole = _whole(number)
        if key not in names or whole is None or not 0 <= whole <= MAX_POINTS:
            reading.error('bad_characteristics', '%s.%s' % (field, str(key)[:40]))
            continue
        if ceiling is not None and whole > ceiling:
            reading.warn('scroll_capped', '%s.%s' % (field, key), cap=ceiling)
            whole = ceiling
        read[names[key]] = whole
    return read


def _read_exos(reading, payload):
    """{build option: flag}; no exos field means no exos. None on Retro or when wrong."""
    value = payload.get('exos')
    if value is None:
        if reading.game == 'retro':
            return None
        return {option: False for _key, option in EXOS}
    if (not isinstance(value, dict)
            or any(key not in dict(EXOS) or not isinstance(flag, bool)
                   for key, flag in value.items())):
        reading.error('bad_exos', 'exos')
        return None
    if reading.game == 'retro':
        reading.warn('exos_not_in_game', 'exos')
        return None
    return {option: bool(value.get(key)) for key, option in EXOS}


def _read_entries(reading, payload):
    """[(index, ankama id, kind, [(key, value)])], or None when the list itself is wrong."""
    entries = payload.get('items')
    if not isinstance(entries, list) or not entries:
        reading.error('bad_items', 'items')
        return None
    if len(entries) > MAX_ITEMS:
        reading.error('too_many_items', 'items', limit=MAX_ITEMS)
        return None
    read = []
    for index, entry in enumerate(entries):
        path = 'items[%d]' % index
        ankama = _whole(entry)
        if ankama is not None:
            if ankama < 1:
                reading.error('bad_items', path)
                continue
            read.append((index, ankama, 'item', []))
            continue
        if not isinstance(entry, dict):
            reading.error('bad_items', path)
            continue
        ankama = _whole(entry.get('id'))
        if ankama is None or ankama < 1:
            reading.error('bad_items', path + '.id')
            continue
        kind = entry.get('type', 'item')
        if kind not in ('item', 'mount'):
            reading.error('bad_items', path + '.type')
            continue
        _unknown_fields(reading, entry, ITEM_FIELDS, path + '.')
        lines = _read_lines(reading, entry.get('stats', []), path + '.stats')
        if lines is None:
            continue
        read.append((index, ankama, kind, lines))
    return read


def _read_lines(reading, lines, path):
    if not isinstance(lines, list) or len(lines) > MAX_STAT_LINES:
        reading.error('bad_stats', path)
        return None
    read = []
    for number, line in enumerate(lines):
        where = '%s[%d]' % (path, number)
        if not isinstance(line, dict):
            reading.error('bad_stats', where)
            return None
        key, value = line.get('key'), _whole(line.get('value'))
        if (not isinstance(key, str) or not 0 < len(key) <= STAT_KEY_LENGTH
                or value is None or abs(value) > MAX_STAT_VALUE):
            reading.error('bad_stats', where)
            return None
        _unknown_fields(reading, line, STAT_LINE_FIELDS, where + '.')
        read.append((key, value))
    return read


def _mounts(structure):
    return {item.ankama_id: item for item in structure.get_items_list()
            if item.ankama_type == 'mounts' and item.ankama_id is not None}


def _lookup(structure, ankama, kind, mounts):
    if kind == 'mount':
        return mounts.get(ankama)
    return structure.get_item_by_ankama_id(ankama)


def _stat_keys(structure, item):
    """{stat key: value} of a catalogue piece, lines on one stat summed."""
    keys = {}
    for stat_id, value in item.stats or ():
        stat = structure.get_stat_by_id(stat_id)
        if stat is not None:
            keys[stat.key] = keys.get(stat.key, 0) + value
    return keys


def _variant(structure, item, lines):
    """The pet variant whose stat keys are exactly the lines sent, else the piece itself."""
    base = PET_VARIANT_ID_BASE.get(structure.game_version)
    if base is None or not lines or item.id >= base:
        return item
    wanted = {key for key, _value in lines}
    matches = [other for other in structure.get_items_list()
               if other.ankama_id == item.ankama_id and other.id >= base
               and set(_stat_keys(structure, other)) == wanted]
    return matches[0] if len(matches) == 1 else item


def _gelanos(structure):
    """(Gelano (#1), the Gelano it is sent as), or None; (#1) is the Gelano with its MP exo and has no Ankama id."""
    with_mp = structure.get_item_by_name('Gelano (#1)')
    plain = structure.get_item_by_name('Gelano (#2)')
    if with_mp is None or plain is None or plain.ankama_id is None:
        return None
    return with_mp, plain


def _last_per_key(reading, lines, path):
    """[(line number, key, value)], one line per key: the last one sent."""
    kept = {}
    for number, (key, value) in enumerate(lines):
        if key in kept:
            reading.warn('duplicate_stat', '%s.stats[%d]' % (path, number))
        kept[key] = (number, value)
    return [(number, key, value) for key, (number, value) in kept.items()]


def _other_games(game, ankama, kind):
    found = []
    for other in version_keys():
        if other == game:
            continue
        structure = get_structure(other)
        mounts = _mounts(structure) if kind == 'mount' else {}
        if _lookup(structure, ankama, kind, mounts) is not None:
            found.append(other)
    return found


def _resolve(reading, entries):
    """Item ids, rolls and everything left out, from the entries."""
    from chardata.text_build_import import _jets_de_la_piece
    structure = get_structure(reading.game)
    mounts = (_mounts(structure) if any(kind == 'mount' for _i, _a, kind, _l in entries)
              else {})
    gelanos = _gelanos(structure)
    free = dict(TYPE_NAME_TO_SLOT_NUMBER)
    worn = {}
    item_ids, missing, wrong_game, left_out = [], [], [], []
    rolls, unmapped = {}, []
    for index, ankama, kind, lines in entries:
        path = 'items[%d]' % index
        piece = {'index': index, 'id': ankama, 'type': kind, 'found': False,
                 'name': None, 'slot': None, 'level': None, 'placed': False}
        reading.pieces.append(piece)
        item = _lookup(structure, ankama, kind, mounts)
        if item is None:
            others = _other_games(reading.game, ankama, kind)
            if others:
                piece['games'] = others
                reading.warn('item_from_another_game', path, id=ankama, games=others)
                wrong_game.append('#%d (%s)' % (ankama, ', '.join(
                    get_game_version(other).label for other in others)))
            else:
                reading.warn('unknown_item', path, id=ankama)
                missing.append('#%d' % ankama)
            continue
        lines = _last_per_key(reading, lines, path)
        item = _variant(structure, item, [(key, value) for _n, key, value in lines])
        if gelanos and item is gelanos[1]:
            stats = dict(_stat_keys(structure, item))
            stats.update((key, value) for _n, key, value in lines)
            if stats == _stat_keys(structure, gelanos[0]):
                item = gelanos[0]
        type_name = structure.get_type_name_by_id(item.type)
        name = (structure.get_item_name_in_language(item, reading.language)
                or item.name)
        piece.update({'found': True, 'name': name, 'slot': type_name,
                      'level': item.level})
        if item.removed:
            reading.warn('removed_item', path, id=ankama)
        copies = worn.get((kind, ankama), 0)
        if copies and (copies >= 2 or not _can_be_worn_twice(
                structure, item, type_name, reading.game)):
            reading.warn('already_placed', path, id=ankama)
            reading.worn_twice.append(name)
            continue
        if free.get(type_name, 0) <= 0:
            reading.warn('slot_full', path, id=ankama)
            left_out.append(name)
            continue
        free[type_name] -= 1
        worn[(kind, ankama)] = copies + 1
        piece['placed'] = True
        item_ids.append(item.id)
        if gelanos and item is gelanos[0]:
            reading.gelano_mp = True
        if reading.level is not None and item.level > reading.level:
            reading.warn('item_above_level', path, id=ankama)
        # Overrides are stored per item id: a second copy shares the first one's
        if copies:
            continue
        catalogue = _stat_keys(structure, item)
        sent, numbers = [], {}
        for number, key, value in lines:
            if structure.get_stat_by_key(key) is None:
                reading.warn('unknown_stat', '%s.stats[%d]' % (path, number))
                unmapped.append((item.id, key, value))
                continue
            if catalogue.get(key) != value:
                sent.append({'key': key, 'value': value})
                numbers[key] = number
        if not sent:
            continue
        rolls[item.id] = sent
        _applied, detail = _jets_de_la_piece(structure, item, sent, reading.game,
                                             lignes_ajoutees=True)
        for line in detail:
            if line['out_of_range']:
                reading.warn('stat_out_of_range',
                             '%s.stats[%d]' % (path, numbers[line['key']]),
                             low=line['low'], high=line['high'])
    return item_ids, missing, wrong_game, left_out, rolls, unmapped


def check(payload, language='en'):
    """Everything a payload says, with its errors and warnings; reading.build is set when it can be imported."""
    reading = Reading(language)
    if not isinstance(payload, dict):
        reading.error('not_an_object', '')
        return reading
    if 'source' in payload:
        reading.source = _domain(payload.get('source')) or ''
        if not reading.source:
            reading.warn('source_ignored', 'source')
    if payload.get('format') != FORMAT:
        reading.error('wrong_format', 'format')
        return reading
    if _whole(payload.get('version')) not in READABLE_VERSIONS:
        reading.error('unsupported_version', 'version')
        return reading
    if payload.get('game') not in version_keys():
        reading.error('unknown_game', 'game')
        return reading
    reading.game = payload['game']
    _unknown_fields(reading, payload, FIELDS, '')

    if payload.get('level') is not None:
        level = _whole(payload.get('level'))
        if level is None or not 1 <= level <= MAX_LEVEL:
            reading.error('bad_level', 'level')
        else:
            reading.level = level

    if payload.get('class') is not None:
        from chardata.version_compat import class_exists_in_version
        char_class = _class_of(payload.get('class'))
        if char_class is None:
            reading.warn('unknown_class', 'class')
        elif not class_exists_in_version(char_class, reading.game):
            reading.warn('class_not_in_game', 'class')
        else:
            reading.char_class = char_class

    name = payload.get('name')
    if name is not None:
        if not isinstance(name, str):
            reading.warn('name_ignored', 'name')
        else:
            name = _CONTROL.sub(' ', name).strip()
            if len(name) > NAME_LENGTH:
                reading.warn('name_truncated', 'name', limit=NAME_LENGTH)
                name = name[:NAME_LENGTH].strip()
            reading.name = name

    if payload.get('back_url') is not None:
        found = _back_url(payload.get('back_url'))
        if found is None:
            reading.warn('back_url_ignored', 'back_url')
        else:
            reading.back_url, reading.back_host = found

    ceiling = max_scroll_for_version(reading.game, reading.level or MAX_LEVEL)
    points = _read_six(reading, payload, 'characteristics', None)
    scrolls = _read_six(reading, payload, 'scrolls', ceiling)
    reading.points = {name: (points or {}).get(name, 0)
                      for _field, name in CHARACTERISTICS}
    # No scrolls field: fully scrolled, as a new build here starts
    reading.scrolls = {name: (scrolls.get(name, 0) if scrolls is not None
                              else ceiling)
                       for _field, name in CHARACTERISTICS}
    reading.exos = _read_exos(reading, payload)

    entries = _read_entries(reading, payload)
    if entries is None or reading.errors:
        if entries is not None:
            _resolve(reading, entries)
        return reading
    item_ids, missing, wrong_game, left_out, rolls, unmapped = _resolve(
        reading, entries)
    if not item_ids:
        found_elsewhere = sorted({game for piece in reading.pieces
                                  for game in piece.get('games', ())})
        if found_elsewhere:
            reading.error('wrong_game', 'game', games=found_elsewhere)
        else:
            reading.error('no_known_item', 'items')
        return reading

    exo_options = reading.exos
    if reading.gelano_mp and exo_options is not None and not exo_options['mp_exo']:
        exo_options = dict(exo_options, mp_exo='gelano')
    reading.build = {
        'game_version': reading.game,
        'source_host': reading.source,
        'build_id': None,
        'name': reading.name,
        'level': reading.level,
        'item_ids': item_ids,
        'missing': missing,
        'wrong_game': wrong_game,
        'left_out': left_out,
        'worn_twice': reading.worn_twice,
        'base_points': {name: value for name, value in reading.points.items()
                        if value},
        'base_scrolled': {name: value for name, value in reading.scrolls.items()
                          if value},
        'base_stats_complete': True,
        'rolls': rolls,
        'fm_unmapped': unmapped,
        'fm_global': {},
        'fm_weapon': None,
        'exo_options': exo_options,
        'char_class': reading.char_class,
        'class_is_unknown': reading.char_class is None,
        'back_url': reading.back_url,
        'back_host': reading.back_host,
        'sent': True,
    }
    return reading


def read_build(text, language='en'):
    """The build a pasted or sent fashionista-build carries, shaped like the link readers' builds; FormatError otherwise."""
    payload = parse_json(text)
    reading = check(payload, language)
    if not reading.valid:
        raise FormatError(reading.errors[0]['code'], reading.source)
    return reading.build


def _issues(issues, language):
    with translation.override(language):
        return [dict(issue, message=message(issue['code'])) for issue in issues]


def link_for(payload, game):
    """Our import address for this payload, or None when it does not fit a link."""
    from chardata.url_language import SITE_URL
    data = encode_link_data(payload)
    if len(data) > MAX_LINK_DATA:
        return None
    prefix = '' if game == 'dofus3' else '/' + game
    return '%s%s/import/build/?data=%s' % (SITE_URL, prefix, data)


def report(payload, language='en'):
    """The validator's answer for a parsed payload."""
    reading = check(payload, language)

    def six(values):
        if not reading.game:
            return None
        return {field: values.get(name, 0) for field, name in CHARACTERISTICS}

    return {
        'format': FORMAT,
        'version': FORMAT_VERSION,
        'valid': reading.valid,
        'game': reading.game,
        'class': reading.char_class,
        'level': reading.level,
        'name': reading.name or None,
        'items': reading.pieces,
        'characteristics': six(reading.points),
        'scrolls': six(reading.scrolls),
        'exos': ({key: reading.exos[option] for key, option in EXOS}
                 if reading.exos is not None else None),
        'source': reading.source or None,
        'back_url': reading.back_url,
        'errors': _issues(reading.errors, language),
        'warnings': _issues(reading.warnings, language),
        'errors_omitted': reading.errors_omitted,
        'warnings_omitted': reading.warnings_omitted,
        'link': link_for(payload, reading.game) if reading.valid else None,
    }


def refusal(code, language='en'):
    """The validator's answer when nothing could be read."""
    return {
        'format': FORMAT, 'version': FORMAT_VERSION, 'valid': False,
        'game': None, 'class': None, 'level': None, 'name': None,
        'items': [], 'characteristics': None, 'scrolls': None, 'exos': None,
        'source': None, 'back_url': None,
        'errors': _issues([{'code': code, 'path': ''}], language),
        'warnings': [], 'errors_omitted': 0, 'warnings_omitted': 0,
        'link': None,
    }


def _lines_of(structure, item, overrides, own=False):
    """[{key, value}] a piece needs to come back as it is: its own lines when own or a pet variant, then its overrides."""
    values = {}
    base = PET_VARIANT_ID_BASE.get(structure.game_version)
    if own or (base is not None and item.id >= base):
        for stat_id, value in item.stats or ():
            values[stat_id] = values.get(stat_id, 0) + value
    values.update(overrides or {})
    lines = []
    for stat_id, value in sorted(values.items()):
        stat = structure.get_stat_by_id(stat_id)
        if stat is not None:
            lines.append({'key': stat.key, 'value': int(value)})
    return lines


def export_build(char):
    """The build as a fashionista-build dict, or None when it wears nothing."""
    from fashionistapulp.structure import (get_current_game_version,
                                           set_current_game_version)
    # The inventory rolls read the thread's catalogue
    previous = get_current_game_version()
    set_current_game_version(char.game_version)
    try:
        return _export(char)
    finally:
        set_current_game_version(previous)


def _export(char):
    from chardata.build_name import display_name
    from chardata.char_blobs import read_char_blob
    from chardata.inventory_solver import get_effective_stat_overrides
    from chardata.options import get_options
    from chardata.url_language import SITE_URL
    from chardata.util import get_stats_and_scrolled, shared_build_path
    from fashionistapulp.modelresult import get_item_in_slot

    structure = get_structure(char.game_version)
    minimal = read_char_blob(char.minimal_solution, None, 'minimal_solution', char)
    per_slot = getattr(minimal, 'item_per_slot', None) or {}
    overrides = get_effective_stat_overrides(char) or {}
    gelanos = _gelanos(structure)
    items = []
    for slot in SLOTS:
        stored = per_slot.get(slot)
        if stored is None:
            continue
        item = get_item_in_slot(structure, structure.current_item_id(stored), slot)
        if item is None:
            continue
        with_mp = bool(gelanos) and item is gelanos[0]
        ankama = gelanos[1].ankama_id if with_mp else item.ankama_id
        if ankama is None:
            continue
        entry = {'id': ankama}
        if item.ankama_type == 'mounts':
            entry['type'] = 'mount'
        lines = _lines_of(structure, item, overrides.get(item.id), own=with_mp)
        if lines:
            entry['stats'] = lines
        items.append(entry if len(entry) > 1 else ankama)
    if not items:
        return None

    spent, scrolled = get_stats_and_scrolled(char)
    payload = {
        'format': FORMAT,
        'version': FORMAT_VERSION,
        'game': char.game_version,
    }
    if char.char_class in CHARACTER_CLASSES:
        payload['class'] = char.char_class
    payload['level'] = max(1, min(int(char.level or MAX_LEVEL), MAX_LEVEL))
    payload['name'] = display_name(char)[:NAME_LENGTH]
    payload['items'] = items
    payload['characteristics'] = {field: max(0, spent.get(name, 0))
                                  for field, name in CHARACTERISTICS}
    payload['scrolls'] = {field: max(0, scrolled.get(name, 0))
                          for field, name in CHARACTERISTICS}
    if char.game_version != 'retro':
        options = get_options(char)
        # 'gelano' means the Gelano carries the MP, not an exo
        payload['exos'] = {key: options.get(option) is True
                           for key, option in EXOS}
    payload['source'] = SITE_HOST
    if char.link_shared:
        payload['back_url'] = SITE_URL + shared_build_path(char)
    return payload


def _first_items(structure, type_name, level, count=1):
    base = PET_VARIANT_ID_BASE.get(structure.game_version)
    type_id = structure.get_type_id_by_name(type_name)
    candidates = sorted(
        (item for item in structure.get_items_list()
         if item.type == type_id and not item.removed
         and item.ankama_id is not None and item.ankama_type != 'mounts'
         and item.level <= level and (base is None or item.id < base)
         and structure.get_item_by_ankama_id(item.ankama_id) is item),
        key=lambda item: (-item.level, item.ankama_id))
    return candidates[:count]


#: game: (level, class as sent, characteristics)
EXAMPLES = {
    'dofus3': (200, 'Iop', {'vitality': 0, 'wisdom': 0, 'strength': 398,
                            'intelligence': 0, 'chance': 0, 'agility': 0}),
    'retro': (100, 9, {'vitality': 0, 'wisdom': 0, 'strength': 0,
                       'intelligence': 0, 'chance': 0, 'agility': 200}),
}


def example_payload(game):
    """A complete payload for the developer page, from real pieces of that game."""
    structure = get_structure(game)
    level, char_class, characteristics = EXAMPLES.get(game, EXAMPLES['dofus3'])
    items = []
    for type_name, count in (('Hat', 1), ('Cloak', 1), ('Amulet', 1),
                             ('Ring', 2), ('Belt', 1), ('Boots', 1),
                             ('Weapon', 1)):
        items.extend(_first_items(structure, type_name, level, count))
    entries = [item.ankama_id for item in items]
    if items:
        hat = items[0]
        ranges = getattr(hat, 'stat_ranges', None) or {}
        # A roll one below the top of its range
        lines = [{'key': structure.get_stat_by_id(stat_id).key, 'value': value - 1}
                 for stat_id, value in sorted(hat.stats or ())
                 if stat_id in ranges and ranges[stat_id][0] < value <= ranges[stat_id][1]][:1]
        if lines:
            entries[0] = {'id': hat.ankama_id, 'stats': lines}
    payload = {
        'format': FORMAT,
        'version': FORMAT_VERSION,
        'game': game,
        'class': char_class,
        'level': level,
        'name': 'Example build',
        'items': entries,
        'characteristics': dict(characteristics),
        'scrolls': {field: max_scroll_for_version(game, level)
                    for field, _name in CHARACTERISTICS},
    }
    if game != 'retro':
        payload['exos'] = {'ap': True, 'mp': False, 'range': False}
    payload['source'] = 'example.org'
    payload['back_url'] = 'https://example.org/builds/42'
    return payload


def json_schema():
    """The JSON Schema of version 1."""
    from chardata.character_look import CLASS_TO_BREED
    from chardata.url_language import SITE_URL
    six = {
        'type': ['object', 'null'],
        'additionalProperties': False,
        'properties': {field: {'type': 'integer', 'minimum': 0,
                               'maximum': MAX_POINTS}
                       for field, _name in CHARACTERISTICS},
    }
    stat_line = {
        'type': 'object',
        'required': ['key', 'value'],
        'properties': {
            'key': {'type': 'string', 'minLength': 1,
                    'maxLength': STAT_KEY_LENGTH},
            'value': {'type': 'integer', 'minimum': -MAX_STAT_VALUE,
                      'maximum': MAX_STAT_VALUE},
        },
    }
    item = {
        'oneOf': [
            {'type': 'integer', 'minimum': 1},
            {'type': 'object', 'required': ['id'], 'properties': {
                'id': {'type': 'integer', 'minimum': 1},
                'type': {'enum': ['item', 'mount']},
                'stats': {'type': 'array', 'maxItems': MAX_STAT_LINES,
                          'items': stat_line},
            }},
        ],
    }
    return {
        '$schema': 'https://json-schema.org/draft/2020-12/schema',
        '$id': SITE_URL + SCHEMA_PATH,
        'title': FORMAT,
        'description': 'A build sent to Dofus Fashionista, version %d. '
                       'Documentation: %s/developers/send-a-build/'
                       % (FORMAT_VERSION, SITE_URL),
        'type': 'object',
        'required': ['format', 'version', 'game', 'items'],
        'properties': {
            'format': {'const': FORMAT},
            'version': {'const': FORMAT_VERSION},
            'game': {'enum': list(version_keys())},
            'class': {'oneOf': [
                {'type': 'string', 'minLength': 1, 'maxLength': 40,
                 'examples': list(CHARACTER_CLASSES)},
                {'type': 'integer', 'minimum': 1,
                 'examples': sorted(CLASS_TO_BREED.values())},
                {'type': 'null'},
            ]},
            'level': {'type': ['integer', 'null'], 'minimum': 1,
                      'maximum': MAX_LEVEL},
            'name': {'type': ['string', 'null']},
            'items': {'type': 'array', 'minItems': 1, 'maxItems': MAX_ITEMS,
                      'items': item},
            'characteristics': six,
            'scrolls': six,
            'exos': {
                'type': ['object', 'null'],
                'additionalProperties': False,
                'properties': {key: {'type': 'boolean'} for key, _o in EXOS},
            },
            'source': {'type': ['string', 'null']},
            'back_url': {'type': ['string', 'null']},
        },
    }
