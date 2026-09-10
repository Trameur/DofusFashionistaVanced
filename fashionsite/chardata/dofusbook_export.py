# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.

"""Hand a build over to DofusBook, by link, without an account.

Everything here is read off their own bundle and then tried against their
live site on 2026-09-10. Their `zc` function takes the `stuff` query
parameter of `/desktop/<lang>/equipement/dofus-stuffer/objets`, base64 decodes
it, msgpack decodes that, and rebuilds a draft entirely in the reader's
browser:

    stuff = base64( msgpack( [fm, points, level, flags, counts, ankama ids] ) )

Measured end to end in a browser: 16 of 16 items land in the right slots on
www and on touch, and the sixteen names their page shows are the sixteen names
our own catalogue gives for the same Ankama ids.

**The one measurement that shapes the whole module.** The same test on
`retro.dofusbook.net` lands 13 of 16: their Retro catalogue simply does not
carry Ankama ids 6741, 9347 and 7753. Nothing on their page says so, so the
player would get a build missing three pieces and no warning. That is the
failure this feature exists to avoid, so the ids are checked against their
`items/x/stuffer/` endpoint BEFORE the link is handed over, and what cannot
travel is named on our page.

**Two things are deliberately not encoded.**

`fm`, their per-stat forgemagie total, stays at zero. Our jets are per item;
theirs is one number per characteristic for the whole build, and turning one
into the other would print a forgemagie the player never had.

A partial scroll stays at zero too, and this one is measurable rather than
cautious: their decoder reads `t[0][p] >= 100 ? 100 : 0` as the scroll and
keeps **the remainder as forgemagie**. Sending a scrolled value of 50 would
show up on their page as +50 forgemagie on that characteristic, and sending
Touch's 150 as +50. So the field carries 100 or nothing, which is exactly what
their format can hold.
"""

import base64
import json
import urllib.error
import urllib.parse
import urllib.request

#: Our version to their host. dofus2 and beta have no DofusBook site, so they
#: get no link rather than a link to a catalogue that is not theirs.
HOSTS = {
    'dofus3': 'www.dofusbook.net',
    'touch': 'touch.dofusbook.net',
    'retro': 'retro.dofusbook.net',
}

#: Their router is `path:"/:lang(fr|es|en)/"`, so it accepts three languages
#: and nothing else. A German or Portuguese reader gets the English page
#: rather than a 404.
LANGUAGES = ('fr', 'es', 'en')

#: Their slot groups, in the order their `as` array lists them, with the code
#: each slot carries. The order is what the payload encodes: the ids are a
#: flat list and only their position says where each one goes.
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

#: How many stats their `fm` array carries, read off the loop bound in `Nc`.
FM_LENGTH = 51

#: The six base characteristics, in their order, which is also ours:
#: BASE_STATS is ['vit', 'wis', 'str', 'int', 'cha', 'agi'] and their `st` is
#: ["vi", "sa", "fo", "in", "ch", "ag"].
BASE_STAT_COUNT = 6

#: Their `t[3]` bits, read off `Nc`: bit 4 adds one to index 6 (AP), bit 2 to
#: index 7 (MP), bit 1 to index 10 (range).
EXO_AP = 4
EXO_MP = 2
EXO_RANGE = 1

#: The scroll their format can hold, and the threshold its own decoder uses.
SCROLL_STEP = 100

#: Where their `Pc` subtracts the naked character's own value from what it
#: reads, so a zero prints a NEGATIVE forgemagie. Measured on their page: an
#: all zero payload at level 200 shows "-7 PA, -3 PM, -1050 Vitalite, -1 PI,
#: -100 Prospection, -1000 Pods", and those six numbers are exactly the six
#: their `Gt(level, class)` returns.
BASE_INDEXES = (0, 6, 7, 9, 11, 23)


def character_base(level):
    """Their naked character, from their own `Gt`:

        {ic: 1, pa: level < 100 ? 6 : 7, pd: 1000, pm: 3, pp: 100,
         pv: (level - 1) * 5 + 55}

    The class argument is hardcoded to 1 on the path a link takes, so the one
    branch that depends on it (Retro Enutrof prospection) never fires here.
    Checked against their page at levels 1, 100 and 200: writing these six
    values makes the whole forgemagie block disappear.
    """
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
    """Anything that stops us handing back a link, with a reason key the
    caller turns into a translated sentence."""

    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


def supports(game_version):
    return game_version in HOSTS


def language_for(code):
    """Their language, from the reader's."""
    return code if code in LANGUAGES else 'en'


def _pack(value):
    """Just enough msgpack for the six shapes this payload uses.

    Their decoder is the full @msgpack/msgpack, so the smallest legal encoding
    of each value is read the same as any other; writing only positive fixints,
    uint8, uint16 and arrays keeps this to a page instead of a dependency.
    """
    if isinstance(value, bool):
        raise TypeError('the payload carries no booleans')
    if isinstance(value, int):
        if value < 0:
            raise ValueError('negative value in payload: %d' % value)
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


def group_ankama_ids(items_by_slot):
    """[[ankama ids], ...] in their group order, cut to the slots they have.

    Taking more than a group holds would push every later id into the wrong
    slot, because the flat list is positional: seven dofus would land the
    seventh one on the shield.
    """
    grouped = []
    for slot, codes in GROUPS:
        pris = [i for i in (items_by_slot.get(slot) or []) if i][:len(codes)]
        grouped.append(pris)
    return grouped


def vitality_scroll_is_forced(level):
    """Whether their format will claim a full vitality scroll whatever we do.

    Index 0 has to be two things at once on their side: `Nc` reads it as the
    vitality scroll plus its forgemagie, and `Pc` subtracts the character's
    base HP from it. Cancelling the second means writing at least that HP,
    and their scroll is derived from the very same number as
    `t[0][0] >= 100 ? 100 : 0`. From level 10 on, base HP alone is over 100,
    so their page reads a 100 scroll no matter what we send.

    The alternative is to leave the field at the honest scroll and let their
    page print "-1050 Vitalite" of forgemagie and take that off the totals,
    which is a broken sheet rather than a small overstatement.
    """
    return character_base(int(level))[0] >= SCROLL_STEP


def _vitality_field(base_pv, scrolled):
    if base_pv >= SCROLL_STEP or scrolled >= SCROLL_STEP:
        return base_pv + SCROLL_STEP
    return base_pv


def payload(grouped, level, points=None, scrolls=None, exos=0):
    """Their `stuff` parameter, ready to be put in a URL."""
    scrolls = scrolls or {}
    points = points or {}
    base = character_base(int(level))
    fm = []
    spent = []
    for index in range(FM_LENGTH):
        if index == 0:
            fm.append(_vitality_field(base[0], scrolls.get(0, 0)))
        elif index < BASE_STAT_COUNT:
            # Their `t[0][p]` is scroll plus forgemagie on that stat. We never
            # write forgemagie, so it is the scroll or nothing.
            fm.append(SCROLL_STEP if scrolls.get(index, 0) >= SCROLL_STEP else 0)
        else:
            fm.append(base.get(index, 0))
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
    """The Ankama ids their catalogue answers with, out of the ones we ask.

    Their endpoint wants `<slot code>-<ankama id>` pairs and answers with the
    items it knows, so the ones it drops are exactly the ones that would
    vanish from the player's draft without a word. The language segment is
    ignored by their API, measured: fr, en and a nonsense one all answer the
    same 17109 bytes, so a constant goes there rather than an invented value.
    """
    if not supports(game_version):
        raise ExportError('unsupported_version')
    host = HOSTS[game_version]
    paires = []
    for (slot, codes), groupe in zip(GROUPS, grouped):
        for code, ankama in zip(codes, groupe):
            paires.append('%s-%d' % (code, int(ankama)))
    if not paires:
        return set()
    url = 'https://%s/api/items/x/stuffer/%s' % (host, ','.join(paires))
    requete = urllib.request.Request(url, headers={
        'User-Agent': USER_AGENT,
        # Same refusal as the import side: their site answers 403 to a request
        # that does not look like it came from their own pages.
        'Referer': 'https://%s/' % host,
        'Accept': 'application/json',
    })
    ouvreur = opener or urllib.request.urlopen
    try:
        with ouvreur(requete, timeout=TIMEOUT) as reponse:
            charge = json.load(reponse)
    except urllib.error.HTTPError:
        raise ExportError('refused')
    except Exception:
        raise ExportError('unreachable')
    if not isinstance(charge, dict) or not isinstance(charge.get('data'), list):
        raise ExportError('unreadable')
    connus = set()
    for entree in charge['data']:
        if isinstance(entree, dict) and entree.get('official') is not None:
            connus.add(entree['official'])
    return connus


def keep_known(grouped, connus):
    """The same groups with the ids their catalogue does not carry removed."""
    return [[a for a in groupe if a in connus] for groupe in grouped]
