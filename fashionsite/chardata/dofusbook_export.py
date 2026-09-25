# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.

"""Hand a build over to DofusBook by link, without an account."""

import base64
import json
import urllib.error
import urllib.parse
import urllib.request

# dofus2 and beta have no DofusBook site
HOSTS = {
    'dofus3': 'www.dofusbook.net',
    'touch': 'touch.dofusbook.net',
    'retro': 'retro.dofusbook.net',
}

# Their router only takes fr, es and en
LANGUAGES = ('fr', 'es', 'en')

# Their slot groups and codes, in payload order: the ids are positional
GROUPS = (
    ('Cloak', ('ca',)),
    ('Hat', ('ch',)),
    ('Belt', ('ce',)),
    ('Boots', ('bo',)),
    ('Amulet', ('am',)),
    ('Ring', ('a1', 'a2')),
    ('Dofus', ('d1', 'd2', 'd3', 'd4', 'd5', 'd6')),
    ('Shield', ('br',)),
    ('Weapon', ('ar',)),
    ('Pet', ('fa',)),
)

# Their decoder reads 51 fm entries; the last code of VE is never read
FM_LENGTH = 51

# Their `ve`: the characteristic at each position of `fm`
VE = ('vi', 'sa', 'fo', 'in', 'ch', 'ag', 'pa', 'pm', 'ii', 'pp', 'po', 'ic',
      'rpa', 'epa', 'rpm', 'epm', 'cc', 'so', 'ta', 'fu', 'dmg', 'pu', 'dc',
      'pd', 'dnf', 'dtf', 'dff', 'def', 'daf', 'rv', 'pi', 'pip', 'dp', 'ds',
      'dw', 'dm', 'dd', 'rn', 'rnp', 'rt', 'rtp', 'rf', 'rfp', 're', 'rep',
      'ra', 'rap', 'rc', 'rp', 'rd', 'rm', 'rw')

# AP, MP and range: an exo travels in the flag byte, not in `fm`
EXO_INDEXES = (6, 7, 10)

# vit, wis, str, int, cha, agi, same order as our BASE_STATS
BASE_STAT_COUNT = 6

# Flag byte bits
EXO_AP = 4
EXO_MP = 2
EXO_RANGE = 1

EXO_BIT_BY_INDEX = {6: EXO_AP, 7: EXO_MP, 10: EXO_RANGE}

# Their decoder reads a base field of 100 or more as a full scroll
SCROLL_STEP = 100

# Positions their sheet takes the naked character's value off
BASE_INDEXES = (0, 6, 7, 9, 11, 23)


def index_by_stat_key():
    """{our stat key: position of that characteristic in their `fm`}."""
    from chardata.dofusbook_import import FM_CODES
    positions = {code: index for index, code in enumerate(VE[:FM_LENGTH])}
    table = {}
    for code, key in FM_CODES.items():
        if code in positions:
            table[key] = positions[code]
    return table


def carriable_forge(forge, scrolls=None, level=None):
    """({position: total we can write}, [positions we cannot])."""
    scrolls = scrolls or {}
    garde, refuses = {}, []
    for position, total in sorted(forge.items()):
        if not total or position in EXO_INDEXES:
            continue
        if position < BASE_STAT_COUNT:
            parchote = scrolls.get(position, 0) >= SCROLL_STEP
            if position == 0:
                # The field holds base HP too: refuse a total that crosses 100
                if level is not None:
                    champ = _vitality_field(character_base(int(level))[0],
                                            scrolls.get(0, 0))
                    if (champ + total >= SCROLL_STEP) != (champ >= SCROLL_STEP):
                        refuses.append(position)
                        continue
                garde[position] = total
                continue
            if total < 0 or (not parchote and total >= SCROLL_STEP):
                refuses.append(position)
                continue
        garde[position] = total
    return garde, refuses


def character_base(level):
    """Their naked character by `fm` position, from their `Gt`."""
    return {
        0: (level - 1) * 5 + 55,
        6: 6 if level < 100 else 7,
        7: 3,
        9: 100,
        11: 1,
        23: 1000,
    }


USER_AGENT = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
              '(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36')

TIMEOUT = 20


class ExportError(Exception):
    """No link; `reason` is a key the caller translates."""

    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


def supports(game_version):
    return game_version in HOSTS


def language_for(code):
    """Their language, from the reader's."""
    return code if code in LANGUAGES else 'en'


def _pack(value):
    """Just enough msgpack for this payload: integers and arrays."""
    if isinstance(value, bool):
        raise TypeError('the payload carries no booleans')
    if isinstance(value, int):
        if value < 0:
            # Forgemagie totals can be negative
            if value >= -0x20:
                return bytes([0xe0 | (value + 0x20)])
            if value >= -0x80:
                return b'\xd0' + value.to_bytes(1, 'big', signed=True)
            if value >= -0x8000:
                return b'\xd1' + value.to_bytes(2, 'big', signed=True)
            if value >= -0x80000000:
                return b'\xd2' + value.to_bytes(4, 'big', signed=True)
            raise ValueError('value too small for the payload: %d' % value)
        if value <= 0x7f:
            return bytes([value])
        if value <= 0xff:
            return b'\xcc' + bytes([value])
        if value <= 0xffff:
            return b'\xcd' + value.to_bytes(2, 'big')
        if value <= 0xffffffff:
            return b'\xce' + value.to_bytes(4, 'big')
        raise ValueError('value too large for the payload: %d' % value)
    if isinstance(value, (list, tuple)):
        if len(value) <= 15:
            header = bytes([0x90 | len(value)])
        elif len(value) <= 0xffff:
            header = b'\xdc' + len(value).to_bytes(2, 'big')
        else:
            raise ValueError('array too long for the payload')
        return header + b''.join(_pack(item) for item in value)
    raise TypeError('the payload carries no %s' % type(value).__name__)


MAX_STUFF_LENGTH = 4096
MAX_ARRAY_LENGTH = 256


def _unpack(data, at=0, depth=0):
    """(value, next offset): inverse of `_pack`, plus Dofus-Stuffer's maps."""
    if at >= len(data):
        raise ValueError('the payload ends too early')
    head = data[at]
    if head <= 0x7f:
        return head, at + 1
    if head >= 0xe0:
        return head - 0x100, at + 1
    sizes = {0xcc: (1, False), 0xcd: (2, False), 0xce: (4, False),
             0xcf: (8, False), 0xd0: (1, True), 0xd1: (2, True),
             0xd2: (4, True), 0xd3: (8, True)}
    if head in sizes:
        size, signed = sizes[head]
        if at + 1 + size > len(data):
            raise ValueError('the payload ends too early')
        return (int.from_bytes(data[at + 1:at + 1 + size], 'big', signed=signed),
                at + 1 + size)
    is_map = 0x80 <= head <= 0x8f or head in (0xde, 0xdf)
    if 0x90 <= head <= 0x9f or 0x80 <= head <= 0x8f:
        count, at = head & 0x0f, at + 1
    elif head in (0xdc, 0xdd, 0xde, 0xdf):
        size = 2 if head in (0xdc, 0xde) else 4
        if at + 1 + size > len(data):
            raise ValueError('the payload ends too early')
        count = int.from_bytes(data[at + 1:at + 1 + size], 'big')
        at += 1 + size
    else:
        raise ValueError('the payload carries a 0x%02x' % head)
    if depth >= 2 or count > MAX_ARRAY_LENGTH:
        raise ValueError('the payload nests deeper or longer than a build')
    if is_map:
        table = {}
        for _ in range(count):
            key, at = _map_key(data, at)
            table[key], at = _unpack(data, at, depth + 1)
        return table, at
    values = []
    for _ in range(count):
        value, at = _unpack(data, at, depth + 1)
        values.append(value)
    return values, at


def _map_key(data, at):
    """A map key as the index it stands for: "12" or 12, nothing else."""
    if at >= len(data):
        raise ValueError('the payload ends too early')
    head = data[at]
    if head <= 0x7f:
        return head, at + 1
    if 0xa1 <= head <= 0xa3:
        size = head & 0x1f
        texte = data[at + 1:at + 1 + size]
        if len(texte) == size and texte.isdigit():
            return int(texte), at + 1 + size
    raise ValueError('the payload carries a map key it cannot index')


def _table(valeur):
    """{index: value} for an array or a map, the two shapes `Nc` indexes."""
    if isinstance(valeur, list):
        return dict(enumerate(valeur))
    if isinstance(valeur, dict):
        return valeur
    raise ValueError('the payload is not a build')


def read_payload(stuff):
    """Decode a `stuff` parameter like their `Nc`; ValueError if not a build."""
    import binascii
    import re
    # A query string turns '+' into a space
    texte = re.sub(r'\s', '+', stuff or '')
    if not texte or len(texte) > MAX_STUFF_LENGTH:
        raise ValueError('no stuff parameter to read')
    texte += '=' * (-len(texte) % 4)
    try:
        brut = base64.b64decode(texte, validate=True)
    except (binascii.Error, ValueError):
        raise ValueError('the stuff parameter is not base64')
    valeur, fin = _unpack(brut)
    if fin != len(brut):
        raise ValueError('the payload carries bytes after the build')
    if not isinstance(valeur, (list, dict)):
        raise ValueError('the payload is not a build')
    haut = _table(valeur)
    if any(index not in haut for index in range(6)):
        raise ValueError('the payload is not a build')
    totaux, depenses, nombres, ids = (_table(haut[index]) for index in (0, 1, 4, 5))
    niveau, drapeaux = haut[2], haut[3]
    if not isinstance(niveau, int) or not isinstance(drapeaux, int):
        raise ValueError('the payload is not a build')
    for table in (totaux, depenses, nombres, ids):
        if not all(isinstance(v, int) for v in table.values()):
            raise ValueError('the payload is not a build')

    fm, points, scrolls = [], [], []
    for index in range(FM_LENGTH):
        total = totaux.get(index, 0)
        if index < BASE_STAT_COUNT:
            parchemin = SCROLL_STEP if total >= SCROLL_STEP else 0
            scrolls.append(parchemin)
            fm.append(total - parchemin)
            points.append(depenses.get(index, 0))
        else:
            fm.append(total)
    for index, bit in EXO_BIT_BY_INDEX.items():
        if drapeaux & bit:
            fm[index] += 1

    # A missing count means one piece, like in their decoder
    groupes, suivant = [], 0
    for index in range(len(GROUPS)):
        nombre = max(0, min(nombres.get(index, 1), MAX_ARRAY_LENGTH))
        groupes.append([ids[position] for position
                        in range(suivant, suivant + nombre) if position in ids])
        suivant += nombre
    return {'fm': fm, 'points': points, 'scrolls': scrolls, 'level': niveau,
            'exos': drapeaux, 'ids': groupes}


def global_forge(lu):
    """{position in `VE`: the forgemagie their sheet shows}, zeros left out."""
    base = character_base(int(lu['level']))
    forge = {}
    for index, total in enumerate(lu['fm']):
        valeur = total - base.get(index, 0)
        if index in EXO_BIT_BY_INDEX and lu['exos'] & EXO_BIT_BY_INDEX[index]:
            valeur -= 1
        if valeur:
            forge[index] = valeur
    return forge


def group_ankama_ids(items_by_slot):
    """[[ankama ids], ...] in their group order, cut to the slots they have."""
    grouped = []
    for slot, codes in GROUPS:
        pris = [i for i in (items_by_slot.get(slot) or []) if i][:len(codes)]
        grouped.append(pris)
    return grouped


def vitality_scroll_is_forced(level):
    """Whether their page shows a full vitality scroll whatever we send."""
    return character_base(int(level))[0] >= SCROLL_STEP


def _vitality_field(base_pv, scrolled):
    if base_pv >= SCROLL_STEP or scrolled >= SCROLL_STEP:
        return base_pv + SCROLL_STEP
    return base_pv


def payload(grouped, level, points=None, scrolls=None, exos=0, forge=None):
    """base64(msgpack([fm, points, level, flags, counts, ankama ids]))."""
    scrolls = scrolls or {}
    points = points or {}
    forge = forge or {}
    base = character_base(int(level))
    fm = []
    spent = []
    for index in range(FM_LENGTH):
        forgee = int(forge.get(index, 0))
        if index == 0:
            fm.append(_vitality_field(base[0], scrolls.get(0, 0)) + forgee)
        elif index < BASE_STAT_COUNT:
            # Their decoder splits the field at 100: scroll, then forgemagie
            parchemin = (SCROLL_STEP
                         if scrolls.get(index, 0) >= SCROLL_STEP else 0)
            fm.append(parchemin + forgee)
        else:
            fm.append(base.get(index, 0) + forgee)
    for index in range(BASE_STAT_COUNT):
        spent.append(max(0, int(points.get(index, 0))))
    counts = [len(groupe) for groupe in grouped]
    ids = [int(a) for groupe in grouped for a in groupe]
    brut = _pack([fm, spent, int(level), int(exos), counts, ids])
    return base64.b64encode(brut).decode('ascii')


def build_url(game_version, language, stuff):
    if not supports(game_version):
        raise ExportError('unsupported_version')
    return ('https://%s/desktop/%s/equipement/dofus-stuffer/objets?stuff=%s'
            % (HOSTS[game_version], language_for(language),
               urllib.parse.quote(stuff, safe='')))


def known_ankama_ids(game_version, grouped, opener=None):
    """The Ankama ids their catalogue answers with, out of the ones we ask."""
    return ids_of(stuffer_items(game_version, grouped, opener=opener))


def ids_of(entries):
    connus = set()
    for entree in entries:
        if isinstance(entree, dict) and entree.get('official') is not None:
            connus.add(entree['official'])
    return connus


def their_line_values(entries):
    """{ankama id: {their stat code: the value their sheet counts}}."""
    par_objet = {}
    for entree in entries:
        if not isinstance(entree, dict) or entree.get('official') is None:
            continue
        lignes = {}
        for effet in entree.get('effects') or []:
            if not isinstance(effet, dict) or effet.get('type') != 'E':
                continue
            haut, bas = effet.get('max'), effet.get('min')
            valeur = haut if isinstance(haut, int) and haut > 0 else bas
            if isinstance(valeur, int) and not isinstance(valeur, bool):
                lignes[effet.get('name')] = valeur
        par_objet[entree['official']] = lignes
    return par_objet


def stuffer_items(game_version, grouped, opener=None):
    """Their entry for each id we send; a dropped id is not in their catalogue."""
    if not supports(game_version):
        raise ExportError('unsupported_version')
    host = HOSTS[game_version]
    paires = []
    for (slot, codes), groupe in zip(GROUPS, grouped):
        for code, ankama in zip(codes, groupe):
            paires.append('%s-%d' % (code, int(ankama)))
    if not paires:
        return []
    # Their API ignores the language segment
    url = 'https://%s/api/items/x/stuffer/%s' % (host, ','.join(paires))
    requete = urllib.request.Request(url, headers={
        'User-Agent': USER_AGENT,
        # 403 without a Referer from their own site
        'Referer': 'https://%s/' % host,
        'Accept': 'application/json',
    })
    from chardata.dofusbook_import import BodyTooLarge, _open_allowlisted
    try:
        charge = json.loads(
            _open_allowlisted(requete, HOSTS.values(), opener, TIMEOUT))
    except urllib.error.HTTPError:
        raise ExportError('refused')
    except BodyTooLarge:
        raise ExportError('unreadable')
    except Exception:
        raise ExportError('unreachable')
    if not isinstance(charge, dict) or not isinstance(charge.get('data'), list):
        raise ExportError('unreadable')
    return charge['data']


def keep_known(grouped, connus):
    """The same groups with the ids their catalogue does not carry removed."""
    return [[a for a in groupe if a in connus] for groupe in grouped]
