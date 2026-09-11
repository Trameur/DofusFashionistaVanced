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

**The forgemagie, since 2026-09-11.** Their `fm` is one number per
characteristic for the whole build, ours is a value per line per piece, so
the total we write for a characteristic is the sum over the worn pieces of
what the player has minus what their own catalogue gives that piece. Their
number is taken from THEIR endpoint and not from ours, the way their `Pc`
reads it (`max > 0 ? max : min` on every effect of type E), because the two
catalogues do not always agree: measured on the Strigide amulet, their
critical resistance line is -16 to -20 and ours holds -20, so computing the
difference against our own maximum would have written four points of
forgemagie nobody ever forged.

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

#: How many stats their `fm` array carries, read off the loop bound in `Nc`:
#: `for (let p = 0; p < 51; p += 1)`. Their `ve` below holds 52 codes, so the
#: last one is never read from a link.
FM_LENGTH = 51

#: Their `ve`, the characteristic each position of the `fm` array carries,
#: copied from their desktop bundle (index-desktop-CIlE29DC.js) on
#: 2026-09-11. The order is the whole mapping and nothing else states it, so
#: a shifted copy would print the player's forgemagie on the wrong line.
VE = ('vi', 'sa', 'fo', 'in', 'ch', 'ag', 'pa', 'pm', 'ii', 'pp', 'po', 'ic',
      'rpa', 'epa', 'rpm', 'epm', 'cc', 'so', 'ta', 'fu', 'dmg', 'pu', 'dc',
      'pd', 'dnf', 'dtf', 'dff', 'def', 'daf', 'rv', 'pi', 'pip', 'dp', 'ds',
      'dw', 'dm', 'dd', 'rn', 'rnp', 'rt', 'rtp', 'rf', 'rfp', 're', 'rep',
      'ra', 'rap', 'rc', 'rp', 'rd', 'rm', 'rw')

#: The three positions their `Nc` bumps by one from the flag byte, which is
#: how an exo travels. A per piece roll on one of them is turned into its
#: bit and never into a forgemagie total: the game gives one exo point per
#: characteristic for the whole build, so adding a second would be false.
EXO_INDEXES = (6, 7, 10)

#: The six base characteristics, in their order, which is also ours:
#: BASE_STATS is ['vit', 'wis', 'str', 'int', 'cha', 'agi'] and their `st` is
#: ["vi", "sa", "fo", "in", "ch", "ag"].
BASE_STAT_COUNT = 6

#: Their `t[3]` bits, read off `Nc`: bit 4 adds one to index 6 (AP), bit 2 to
#: index 7 (MP), bit 1 to index 10 (range).
EXO_AP = 4
EXO_MP = 2
EXO_RANGE = 1

#: Which bit bumps which position, so a roll read as an exo travels as
#: the flag their decoder expects and never as a forgemagie total.
EXO_BIT_BY_INDEX = {6: EXO_AP, 7: EXO_MP, 10: EXO_RANGE}

#: The scroll their format can hold, and the threshold its own decoder uses.
SCROLL_STEP = 100

#: Where their `Pc` subtracts the naked character's own value from what it
#: reads, so a zero prints a NEGATIVE forgemagie. Measured on their page: an
#: all zero payload at level 200 shows "-7 PA, -3 PM, -1050 Vitalite, -1 PI,
#: -100 Prospection, -1000 Pods", and those six numbers are exactly the six
#: their `Gt(level, class)` returns.
BASE_INDEXES = (0, 6, 7, 9, 11, 23)

#: Index 10 (range) is in their subtracting branch too, but their naked
#: character has no `po` at all and their code reads `(characterStats[...] ||
#: 0)`, so the value subtracted there is zero and the index behaves like any
#: other. It is left out of `character_base` rather than written as a zero
#: that would look like a measurement.


def index_by_stat_key():
    """{our stat key: the position of that characteristic in their `fm`}.

    Their codes are the ones the import already had to learn, so the table
    is read from there rather than written twice; `VE` decides the position.
    The last position is dropped because their loop stops before it, and a
    characteristic of ours their `ve` does not name simply has no position:
    the caller has to say so rather than pick a neighbour.
    """
    from chardata.dofusbook_import import FM_CODES
    positions = {code: index for index, code in enumerate(VE[:FM_LENGTH])}
    table = {}
    for code, key in FM_CODES.items():
        if code in positions:
            table[key] = positions[code]
    return table


def carriable_forge(forge, scrolls=None):
    """({position: total we can write}, [position we cannot]).

    Two positions are refused, both measured on their own decoder:

    - the six base characteristics share their field with the scroll
      (`t[0][p] >= 100 ? 100 : 0`, the rest being the forgemagie), so a
      negative total under a full scroll would read as no scroll at all, and
      a total of a hundred or more without a scroll would invent one;
    - the three exo positions are carried by the flag byte instead.
    """
    scrolls = scrolls or {}
    garde, refuses = {}, []
    for position, total in sorted(forge.items()):
        if not total or position in EXO_INDEXES:
            continue
        if position < BASE_STAT_COUNT:
            parchote = scrolls.get(position, 0) >= SCROLL_STEP
            if position == 0:
                # Vitality already carries the character's own HP, which is
                # far above the hundred their scroll test looks at, so the
                # sum stays on the right side of it.
                garde[position] = total
                continue
            if total < 0 or (not parchote and total >= SCROLL_STEP):
                refuses.append(position)
                continue
        garde[position] = total
    return garde, refuses


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
            # A forgemagie can take a line BELOW its catalogue minimum, so a
            # total is negative as often as it is positive and their decoder
            # is the full msgpack. Only the scroll fields cannot hold one,
            # and `carriable_forge` keeps them out before it gets here.
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


def payload(grouped, level, points=None, scrolls=None, exos=0, forge=None):
    """Their `stuff` parameter, ready to be put in a URL.

    `forge` is {position in their `ve`: total forgemagie on that
    characteristic}, already filtered by `carriable_forge`. It is ADDED to
    whatever the field already had to carry, because their decoder reads one
    number and takes the scroll and the character's own base out of it.
    """
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
            # Their `t[0][p]` is the scroll PLUS the forgemagie on that stat,
            # and their own decoder splits the two at a hundred.
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
    """{ankama id: {their stat code: the number their sheet counts}}.

    Read off their `Pc`: `const u = c.max > 0 ? c.max : c.min` over the
    effects of type E, the same ones they add into `itemStats`. Their D lines
    are the weapon's own damage and their O lines a spell, and neither lands
    on a characteristic.
    """
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
    """Their own entry for each id we are about to send.

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
        return []
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
    return charge['data']


def keep_known(grouped, connus):
    """The same groups with the ids their catalogue does not carry removed."""
    return [[a for a in groupe if a in connus] for groupe in grouped]
