# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

"""Best damage turn of a Wakfu class, from the spell tables of items_wakfu.db.

    book = SpellBook()
    turn = best_turn(book.spells(class_id, level), role, totals)
"""

import collections
import io
import json
import math
import re
import sqlite3

from . import wakfu_value
from .wakfu_stats import OUT_OF_COMBAT_CAPS
from .wakfu_value_rules import RULES

# The tables hold the French figures and the French level-245 text
TEXT_LANGUAGE = 'fr'
TEXT_LEVEL = 245

DAMAGE_ELEMENTS = wakfu_value.ELEMENTS + ('light',)

ENEMY = 'enemy'
EVENT = 'event'
OTHERWISE = 'otherwise'
BERSERK = 'berserk'
PICTURED = 'pictured target'
OBJECT = 'object target'
STILL = 'stood still'
GAUGE = 'class gauge'
STATE = 'class state'
SKIPPED = 'row'
# "no portal" holds while the role does not take "portal"
NOT = 'no '

DEFAULT_CONDITIONS = frozenset((ENEMY,))

LABELS = {
    ENEMY: 'cast on an enemy',
    EVENT: 'lands on a later event, never on the cast',
    OTHERWISE: 'the other branch of the condition before it',
    BERSERK: 'caster under Berserk',
    PICTURED: 'cast on a target the text only pictures',
    OBJECT: 'cast on an object',
    STILL: 'the caster has not moved this turn',
    GAUGE: 'class gauge',
    STATE: 'class state',
    SKIPPED: 'damage row not counted',
    'damage bonus': 'percent damage bonus',
    'repeat': 'repeats or doubles its effects',
    'next cast': 'changes a later cast',
    'carrying': 'the Pandawa carries a target',
    'dragon form': 'dragon form',
    'bounce': 'bounces to another enemy',
    'summon target': 'the target is a summon',
    'precise shot': 'precise shot, spends Precision',
    'portal': 'a portal is involved',
    'turret': 'a turret is on the field',
    'serein': 'Serein stance',
    'exalte': 'Exalte stance',
    'fourbe': 'Fourbe mode',
    'fuyard': 'Fuyard mode',
    'enutrof form': 'Enutrof form',
    'phorzerker form': 'Phorzerker form',
}

# The character is always in exactly one of these
STANCES = (('serein', 'exalte'), ('fourbe', 'fuyard'),
           ('enutrof form', 'phorzerker form'))

FIGURE = re.compile(r"\b(Dommages?|Soins?)(\s+supplémentaires)?\s*:\s*(-?\d+)"
                    r"(?!\d|[.,]\d)")
SEPARATOR = re.compile(r"(\s*:\s*-(?!\d)\s*|\s*:\s*|\s+-\s+|^\s*-\s+)")
SECTION = re.compile(r"\b(?:Effets\s+si\s+(\w+)|Effets\s+normaux)\b")
STARTER = re.compile(
    r"(?:^|(?<=\s))(Si|Sinon|Sur|Par|Tous|Lancé|En|Au|À|Lorsqu|Quand|Forme|Tir"
    r"|Serein|Exalté|Fourbe|Fuyard|Deux|Chaque|Rebond)\b")
COST_CHANGE = re.compile(r"co[uû]te\s+(\d+)\s+(PA|PW|PM)\s+(supplémentaires?|de moins)",
                         re.I)
RESOURCE = {'PA': 'ap', 'PW': 'wp', 'PM': 'mp'}
ALWAYS_REACH = re.compile(r"(?<!:\s)Les dommages sont toujours (mêlée|distance)")
ROW_MELEE = re.compile(r"^\s*\((?:dommages\s+)?mêlée\)")
ADDS = re.compile(r"^\s*(?:supplémentaires?\b|\(sur l'Armure\))")
INSTEAD = re.compile(r"^\s*(?:\([^)]*\)\s*)?à la place\b")
ON_SUMMONS = re.compile(r"^\s*sur (?:les )?invocations\b")
EACH_CAST = re.compile(r"\bà chaque fois que ce sort est lancé[^:]*", re.I)
INFLICTS = re.compile(r"\binflige(?:nt)?\s*$")

EVENT_WORDS = re.compile(
    r"\b(?:en début|en fin|au début|à la mort|lorsqu|quand|en subissant"
    r"|au prochain|meurt|déclenchement|au lancer du sort|à chaque perte"
    r"|en appliquant|en déplaçant|après)", re.I)
AREA_WORDS = re.compile(r"^en$|\b(?:en zone|en ligne|en cercle|sur le chemin)\b",
                        re.I)
TWICE_WORDS = re.compile(r"^deux fois$", re.I)
ENEMY_WORDS = re.compile(
    r"(?:lancé sur (?:un |l')?ennemi|lancé sur (?:une )?cible|sur une autre cible)$",
    re.I)
PICTURED_WORDS = re.compile(r"(?:^|\s)lancé sur$", re.I)
OBJECT_WORDS = re.compile(r"lancé sur (?:le|la|les|le cadran|tourelle)$|^sur graine",
                          re.I)
OTHERWISE_WORDS = re.compile(r"^sinon$", re.I)
STILL_WORDS = re.compile(r"n'a pas utilisé de PM pour se déplacer", re.I)
NEGATION = re.compile(r"\b(?:aucune?|pas|sans|jamais)\b|\bn'|\bne\b", re.I)
NAMED = (
    ('carrying', re.compile(r"\ble pandawa porte\b", re.I)),
    ('dragon form', re.compile(r"\bforme draconique\b", re.I)),
    ('enutrof form', re.compile(r"\bforme enutrof\b", re.I)),
    ('phorzerker form', re.compile(r"\bforme phorzerker\b", re.I)),
    ('serein', re.compile(r"\bserein\b", re.I)),
    ('exalte', re.compile(r"\bexalté\b", re.I)),
    ('fourbe', re.compile(r"\bfourbe\b", re.I)),
    ('fuyard', re.compile(r"\bfuyard\b", re.I)),
    ('bounce', re.compile(r"rebond|^\d+(?:er|e|ème)$", re.I)),
    ('precise shot', re.compile(r"\btir précis\b", re.I)),
    ('summon target', re.compile(r"\binvocation", re.I)),
    ('portal', re.compile(r"\bportail", re.I)),
)
# The object is a picture the text drops: "Doit cibler un", "Doit cibler une ou un Arbre"
REQUIREMENTS = (
    (OBJECT, re.compile(r"\bDoit cibler (?:un|une)(?:\s+ou\s+(?:un|une))?(?=\s+[A-Z]|\s*$)")),
    ('portal', re.compile(r"\bNe peut être lancé que sur un Portail", re.I)),
    ('turret', re.compile(r"\bLa tourelle doit être sur le terrain", re.I)),
)
MECHANICS = (
    ('repeat', re.compile(r"\bRépète\b|\brépliqué|\beffets(?: du sort)? sont doublés"
                          r"|\bdommages sont propagés", re.I)),
    ('next cast', re.compile(r"\b(?:le|la) prochaine?\b", re.I)),
    ('damage bonus', re.compile(
        r"(?<![-\d.,])\d+(?:[.,]\d+)?\s*%\s*(?:à\s+\d+\s*%\s*)?"
        r"(?:(?:de\s+)?(?:dommages?\s+)?supp|dommages infligés)"
        r"|\(\+\d+\s*%|%\s*des dommages du sort", re.I)),
)
GAUGES = (
    ('Concentration', re.compile(r"\bConcentration\b")),
    ('Point Faible', re.compile(r"\bPoint Faible\b")),
    ('Précision', re.compile(r"\bPrécision\b")),
    ('Retour de flamme', re.compile(r"\bRetour de flamme\b")),
    ('BQ', re.compile(r"\bBQ\b")),
    ('runes', re.compile(r"\b[Rr]unes?\b")),
    ('Charge de Rouage', re.compile(r"\bCharge de Rouage\b")),
    ('Veine', re.compile(r"\bVeine\b")),
    ('Propagateur', re.compile(r"\bPropagateur\b")),
    ('Engrainé', re.compile(r"\bEngrainé\b")),
    ('Pulsar', re.compile(r"\bPulsar\b")),
    ('Traqueur', re.compile(r"\bTraqueur\b")),
    ('Surpression', re.compile(r"\bSurpression\b")),
    ('PS', re.compile(r"\bPS\b")),
)
STATES = (
    ('Berserk', re.compile(r"\bBerserk\b")),
    ('Bouclier', re.compile(r"\b[Bb]oucliers?\b")),
    ('Trésors', re.compile(r"\bTrésors\b")),
    ('Hémorragie', re.compile(r"\bHémorragie\b")),
    ('heure courante', re.compile(r"\b[Hh]eure courante\b")),
    ('Courroux', re.compile(r"\bCourroux\b")),
    ('Égaré', re.compile(r"\bÉgaré\b")),
    ('Imbibé', re.compile(r"\bImbibé\b")),
    ('Ivre', re.compile(r"\bIvre\b")),
    ('Dynamite', re.compile(r"\bDynamite\b")),
    ('Retour de dague', re.compile(r"\bRetours? de dague\b")),
    ('Proie', re.compile(r"\bProie\b")),
    ('Don Céleste', re.compile(r"\bDon Céleste\b")),
    ('Cœur de Lumière', re.compile(r"\bC(?:œ|oe)ur de Lumière\b")),
)

# A turn at 0 damage, in percent of value
NO_DAMAGE = -1000.0


class Row(collections.namedtuple(
        'Row', 'position element base critical critical_read conditions unless '
               'mode hits reach heading cost')):
    """One damage row of a spell at one level.

    conditions: keys that must all hold; unless: keys that cancel the row.
    mode: 'hit' lands with the spell, 'adds' on top, 'instead' replaces the hits.
    """


class Spell(collections.namedtuple(
        'Spell', 'id name branch ap wp mp low high rows skipped read mechanics')):
    """A castable spell; skipped: (position, reason) of rows no turn counts.

    mechanics: (key, French text) of what the text says about damage beyond its rows.
    """


def rule(name):
    return RULES[name].value


def _range(text):
    numbers = [int(n) for n in re.findall(r'\d+', text or '')]
    return (numbers[0], numbers[-1]) if numbers else (0, 0)


def _clean(heading):
    return re.sub(r'\s+', ' ', heading or '').strip(' -')


def _trim(heading):
    heading = _clean(heading)
    starts = [found.start() for found in STARTER.finditer(heading)]
    return heading[starts[-1]:] if starts else heading


def classify(heading):
    """(condition keys, hits) of a heading, trimmed to its last clause; an area is none."""
    text = _trim(heading)
    if not text or AREA_WORDS.search(text) and not EVENT_WORDS.search(text):
        return frozenset(), 1
    if EVENT_WORDS.search(text):
        return frozenset((EVENT,)), 1
    if TWICE_WORDS.search(text):
        return frozenset(), 2
    for key, pattern in ((OTHERWISE, OTHERWISE_WORDS), (ENEMY, ENEMY_WORDS),
                         (OBJECT, OBJECT_WORDS), (PICTURED, PICTURED_WORDS),
                         (STILL, STILL_WORDS)):
        if pattern.search(text):
            return frozenset((key,)), 1
    keys = frozenset(key for key, pattern in NAMED if pattern.search(text))
    if NEGATION.search(text):
        keys = frozenset(NOT + key for key in keys) if len(keys) == 1 else frozenset()
    return keys or frozenset(('if: ' + text.lower(),)), 1


def _headings(before):
    """Headings a figure sits under, innermost first; None when it starts its own line.

    An empty list means the figure continues the list of the figure before it.
    """
    parts = SEPARATOR.split(before)
    texts, seps = parts[0::2], parts[1::2]
    last = len(texts) - 1
    tail = texts[last]
    if tail.strip() and not INFLICTS.search(tail):
        return None
    if not seps:
        return [] if INFLICTS.search(tail) else None

    def kind(sep):
        if ':' in sep:
            return 'list' if '-' in sep else 'colon'
        return 'dash'

    def starts_a_line(text):
        # "Stabilisé (1 tour) Lancé sur ennemi": an item, then a heading of its own
        return _trim(text) != _clean(text)

    found = []
    if not tail.strip() and kind(seps[last - 1]) != 'dash':
        position = last - 1
        found.append(texts[position])
    else:
        position = last
    in_item = position == last
    while position > 0 and not (found and starts_a_line(found[-1])):
        if not in_item:
            if kind(seps[position - 1]) in ('colon', 'list'):
                position -= 1
                found.append(texts[position])
                continue
            in_item = True
        opener = None
        for index in range(position - 1, -1, -1):
            if kind(seps[index]) == 'list':
                opener = index
                break
        if opener is None:
            break
        position = opener
        found.append(texts[position])
        in_item = False
    return [text for text in found if text.strip()]


def _cost_change(text):
    change = collections.Counter()
    for amount, resource, direction in COST_CHANGE.findall(text or ''):
        sign = -1 if 'moins' in direction else 1
        change[RESOURCE[resource.upper()]] += sign * int(amount)
    return change


def read_clauses(normal, critical=None):
    """One entry per damage or healing figure of the level-245 text, in text order.

    (kind, value, critical value or None, conditions, unless, mode, hits, reach,
    heading, cost change)
    """
    normal = normal or ''
    figures = list(FIGURE.finditer(normal))
    critical_values = [int(found.group(3)) for found in FIGURE.finditer(critical or '')]
    if len(critical_values) != len(figures):
        critical_values = [None] * len(figures)
    always = ALWAYS_REACH.search(normal)
    spell_reach = None
    if always:
        spell_reach = 'melee' if always.group(1) == 'mêlée' else 'distance'

    unconditional = []
    out = []
    previous = (frozenset(), 1, '')
    previous_conditional = frozenset()
    for index, found in enumerate(figures):
        start = figures[index - 1].end() if index else 0
        before = normal[start:found.start()]
        stop = figures[index + 1].start() if index + 1 < len(figures) else len(normal)
        after = SEPARATOR.split(normal[found.end():stop])[0]

        headings = _headings(before)
        hits, heading_text = 1, ''
        if headings is None:
            keys = frozenset()
        elif not headings:
            keys, hits, heading_text = previous
        else:
            heading_text = _trim(headings[0])
            collected = set()
            for heading in headings:
                more, many = classify(heading)
                collected |= more
                hits = max(hits, many)
            keys = frozenset(collected)
        previous = (keys, hits, heading_text)

        # "Dommage : 181 en fin de tour de la cible"
        tail = after.strip()
        if tail[:1].islower() and EVENT_WORDS.match(tail):
            keys = keys | {EVENT}
            cut = STARTER.search(tail, 1)
            heading_text = heading_text or (tail[:cut.start()].strip() if cut else tail)

        cost = None
        sections = list(SECTION.finditer(normal, 0, found.start()))
        if sections and sections[-1].group(1):
            state = sections[-1].group(1).lower()
            keys = keys | {BERSERK if state == 'berserk' else 'if: effets si ' + state}
            cost = _cost_change(normal[sections[-1].end():found.start()])

        unless = frozenset()
        if OTHERWISE in keys:
            unless = previous_conditional
            keys = keys - {OTHERWISE}
        if ON_SUMMONS.search(after):
            keys = keys | {'summon target'}
        ramp = EACH_CAST.search(after)
        if ramp:
            keys = keys | {'if: ' + _clean(ramp.group(0)).lower()}

        if found.group(2) or ADDS.search(after):
            mode = 'adds'
        elif INSTEAD.search(after):
            mode = 'instead'
        else:
            mode = None

        reach = spell_reach
        if ROW_MELEE.search(after):
            reach = 'melee'

        if cost is None:
            cost = _cost_change(before) if keys - DEFAULT_CONDITIONS \
                else collections.Counter()
        kind = 'damage' if found.group(1).startswith('Dommage') else 'healing'
        out.append([kind, int(found.group(3)), critical_values[index], keys,
                    unless, mode, hits, reach, heading_text, cost])
        if kind == 'damage' and not keys and not unless:
            unconditional.append(index)
        if keys - DEFAULT_CONDITIONS:
            previous_conditional = keys

    for entry in out:
        keys, unless, mode = entry[3], entry[4], entry[5]
        conditional = bool(keys - DEFAULT_CONDITIONS) or bool(unless)
        if mode is None:
            if not conditional or unless:
                entry[5] = 'hit'
            else:
                entry[5] = 'instead' if unconditional else 'adds'
        if PICTURED in keys and not unconditional:
            entry[3] = (keys - {PICTURED}) | {ENEMY}
    return [tuple(entry) for entry in out]


def _align(rows, clauses):
    """{row position: clause index}, rows and figures matched in order; None if one is missing."""
    matched = {}
    at = 0
    for position, kind, value in rows:
        while at < len(clauses) and (clauses[at][0], clauses[at][1]) != (kind, value):
            at += 1
        if at == len(clauses):
            return None
        matched[position] = at
        at += 1
    return matched


def requirements(normal):
    return frozenset(key for key, pattern in REQUIREMENTS if pattern.search(normal or ''))


def mechanics(normal):
    """(key, French text) of each damage mechanic of the text no figure carries, gauges last."""
    found = []
    for part in SEPARATOR.split(FIGURE.sub(' - ', normal or ''))[0::2]:
        for key, pattern in MECHANICS:
            match = pattern.search(part)
            if match:
                cut = STARTER.search(part, match.end())
                found.append((key, _clean(part[:cut.start()] if cut else part)))
                break
    found.extend((GAUGE, name) for name, pattern in GAUGES if pattern.search(normal or ''))
    return tuple(found)


def harvest_criticals(path, levels):
    """{(spell id, level): critical value of each damage row} from a spells_fr.json harvest."""
    with io.open(path, encoding='utf-8') as handle:
        pages = json.load(handle)
    wanted = {str(max(1, min(level, TEXT_LEVEL))) for level in levels}
    out = {}
    for spell_id, spell in pages.items():
        for level in wanted:
            page = spell['levels'].get(level)
            if page and len(page['damage']) == len(page['critical_damage']):
                out[(int(spell_id), int(level))] = [
                    value for _element, value in page['critical_damage']]
    return out


class SpellBook:
    """Damage spells of the Wakfu classes, from items_wakfu.db.

    critical: optional {(spell id, level): [critical value of each damage row]},
    used where the tables hold no critical value (every level but 245).
    """

    def __init__(self, db_path=None, critical=None):
        if db_path is None:
            from .fashionista_config import get_items_db_path
            db_path = get_items_db_path('wakfu')
        self.conn = sqlite3.connect('file:%s?mode=ro' % db_path, uri=True)
        self.critical = critical or {}
        self._clauses = {}
        self._mechanics = {}

    def close(self):
        self.conn.close()

    def clauses(self, spell_id):
        """(clauses of the level-245 text, {row position: clause index} or None, requirements)."""
        if spell_id not in self._clauses:
            text = self.conn.execute(
                'SELECT normal, critical FROM spell_text WHERE spell = ? AND language = ?',
                (spell_id, TEXT_LANGUAGE)).fetchone() or ('', '')
            clauses = read_clauses(*text)
            rows = self.conn.execute(
                'SELECT position, kind, value FROM spell_effects WHERE spell = ? AND level = ?'
                ' ORDER BY position', (spell_id, TEXT_LEVEL)).fetchall()
            self._clauses[spell_id] = (clauses, _align(rows, clauses),
                                       requirements(text[0]))
            self._mechanics[spell_id] = mechanics(text[0])
        return self._clauses[spell_id]

    def names(self, class_id):
        """{spell id: name} of every spell of the class, passives included."""
        return dict(self.conn.execute(
            'SELECT spells.id, spell_names.name FROM spells JOIN spell_names'
            ' ON spell_names.spell = spells.id AND spell_names.language = ?'
            ' WHERE spells.class = ?', (TEXT_LANGUAGE, class_id)).fetchall())

    def class_mechanics(self, class_id):
        """((key, name, spell ids)) of the gauges and states named in the class's texts."""
        texts = self.conn.execute(
            'SELECT spells.id, spell_text.normal FROM spells JOIN spell_text'
            ' ON spell_text.spell = spells.id AND spell_text.language = ?'
            ' WHERE spells.class = ? ORDER BY spells.id', (TEXT_LANGUAGE, class_id)).fetchall()
        out = []
        for key, vocabulary in ((GAUGE, GAUGES), (STATE, STATES)):
            for name, pattern in vocabulary:
                ids = tuple(spell_id for spell_id, text in texts if pattern.search(text or ''))
                if ids:
                    out.append((key, name, ids))
        return tuple(out)

    def spells(self, class_id, level):
        """Every castable spell of the class with a damage row at `level`."""
        level = max(1, min(level, TEXT_LEVEL))
        out = []
        for spell_id, branch, ap, mp, wp, reach in self.conn.execute(
                'SELECT id, element, ap, mp, wp, range FROM spells WHERE class = ?'
                ' ORDER BY id', (class_id,)).fetchall():
            if not (ap or wp or mp):
                continue
            effects = self.conn.execute(
                "SELECT position, element, value, is_percent, conditional FROM spell_effects"
                " WHERE spell = ? AND level = ? AND kind = 'damage' ORDER BY position",
                (spell_id, level)).fetchall()
            if not effects:
                continue
            spell = self._spell(spell_id, branch, ap, mp, wp, reach, level, effects)
            if spell.rows or spell.skipped:
                out.append(spell)
        return tuple(out)

    def _spell(self, spell_id, branch, ap, mp, wp, reach, level, effects):
        name = self.conn.execute(
            'SELECT name FROM spell_names WHERE spell = ? AND language = ?',
            (spell_id, TEXT_LANGUAGE)).fetchone()
        clauses, aligned, needs = self.clauses(spell_id)
        given = self.critical.get((spell_id, level))
        plain = [effect for effect in effects if not effect[3]]
        if given is not None and len(given) != len(plain):
            given = None
        rows, skipped = [], []
        for position, element, value, is_percent, conditional in effects:
            element = (element or '').lower()
            if is_percent:
                skipped.append((position, 'a share of life, not a base damage'))
                continue
            if element not in DAMAGE_ELEMENTS:
                skipped.append((position, 'no mastery for element %s' % element))
                continue
            if aligned is None:
                if conditional or rows:
                    skipped.append((position, 'text not read, only the first '
                                              'always-landing row counts'))
                    continue
                keys, unless, mode, hits, row_reach, heading, cost = \
                    frozenset(), frozenset(), 'hit', 1, None, '', collections.Counter()
                text_critical = None
            else:
                (_kind, _value, text_critical, keys, unless, mode, hits, row_reach,
                 heading, cost) = clauses[aligned[position]]
            if given is not None:
                critical = given[[effect[0] for effect in plain].index(position)]
                read = 'given'
            elif level == TEXT_LEVEL and text_critical is not None:
                critical, read = text_critical, 'encyclopedia'
            else:
                critical = math.floor(value * rule('critical_multiplier'))
                read = 'x%s' % rule('critical_multiplier')
            rows.append(Row(position, element, value, critical, read, keys | needs,
                            unless, mode, hits, row_reach, heading, cost))
        low, high = _range(reach)
        return Spell(spell_id, name[0] if name else str(spell_id),
                     (branch or '').lower() or None, ap or 0, wp or 0, mp or 0,
                     low, high, tuple(rows), tuple(skipped), aligned is not None,
                     self._mechanics[spell_id])


class Turn(collections.namedtuple(
        'Turn', 'damage casts elements stance counted dropped usable settings unmodelled')):
    """Best turn: expected damage, spell ids in cast order, {element: damage}.

    counted: (spell id, row position, condition keys, heading) of the conditional
    rows of the cast spells; dropped: the same for the rows of every usable spell
    the conditions leave out. unmodelled: (spell ids, key, detail) of what the
    usable spells do to damage that no counted row carries, and of the class
    mechanics best_turn was given.
    """


def _hit(row, totals, reach, orientation, accepted, damage_inflicted, chance):
    if row.element == 'light':
        own = max(totals.get(wakfu_value.MASTERY_OF[e], 0) for e in wakfu_value.ELEMENTS) \
            if rule('light_uses_best_element_mastery') else 0
    else:
        own = totals.get(wakfu_value.MASTERY_OF[row.element], 0)
    mastery = (own + totals.get(wakfu_value.ELEMENTAL_MASTERY, 0)
               + totals.get(wakfu_value.REACH_MASTERY[row.reach or reach], 0))
    factor = 1.0
    if orientation == 'rear':
        mastery += totals.get('backstab_bonus', 0)
        factor = rule('rear_hit_multiplier')
    elif orientation == 'side':
        factor = rule('side_hit_multiplier')
    if BERSERK in accepted:
        mastery += totals.get('berserk_dmg', 0)
    normal = wakfu_value.hit_damage(row.base, mastery, damage_inflicted=damage_inflicted,
                                    orientation=factor)
    critical = wakfu_value.hit_damage(
        row.critical, mastery + totals.get('critical_bonus', 0),
        damage_inflicted=damage_inflicted, orientation=factor)
    return row.hits * ((1 - chance) * normal + chance * critical)


def holds(key, accepted):
    if key.startswith(NOT):
        return key[len(NOT):] not in accepted
    return key in accepted


def lands(row, accepted):
    if EVENT in row.conditions and not rule('later_event_rows_count'):
        return False
    return (all(holds(key, accepted) for key in row.conditions - {EVENT})
            and not (row.unless and all(holds(key, accepted) for key in row.unless)))


def counted_rows(spell, totals, reach, orientation, accepted, damage_inflicted=0):
    """[(row, expected damage)] of the rows one cast counts."""
    chance = wakfu_value.critical_chance(totals.get('ferocity', 0))
    hits, adds, instead = [], [], []
    for row in spell.rows:
        if not lands(row, accepted):
            continue
        worth = _hit(row, totals, reach, orientation, accepted, damage_inflicted, chance)
        {'instead': instead, 'adds': adds}.get(row.mode, hits).append((row, worth))
    if instead:
        hits = [max(instead, key=lambda one: one[1])]
    return hits + adds


def cast_damage(spell, totals, reach, orientation, accepted, damage_inflicted=0):
    """(expected damage of one cast, {element: part of it}, cost change)."""
    cost = collections.Counter()
    for row in spell.rows:
        if lands(row, accepted):
            for key, change in row.cost.items():
                cost[key] = change
    parts = collections.Counter()
    for row, worth in counted_rows(spell, totals, reach, orientation, accepted,
                                   damage_inflicted):
        parts[row.element] += worth
    return sum(parts.values()), parts, cost


def reaches(spell, reach):
    if reach == 'melee':
        return spell.low <= rule('melee_mastery_up_to_cells')
    return spell.high > rule('melee_mastery_up_to_cells')


def castable(spell, elements):
    """A spell of the role's elements; a spell of no branch is anyone's."""
    return spell.branch is None or spell.branch in elements


def rotation(options, ap, wp, mp):
    """(damage, spell ids) of the best bounded knapsack.

    options: [(spell id, damage, (AP, WP, MP) cost, most casts)].
    """
    best = {(0, 0, 0): (0.0, ())}
    for spell_id, worth, cost, limit in options:
        for _ in range(limit):
            grown = dict(best)
            for (used_ap, used_wp, used_mp), (damage, casts) in best.items():
                state = (used_ap + cost[0], used_wp + cost[1], used_mp + cost[2])
                if state[0] > ap or state[1] > wp or state[2] > mp:
                    continue
                if grown.get(state, (-1.0,))[0] < damage + worth:
                    grown[state] = (damage + worth, casts + (spell_id,))
            best = grown
    return max(best.values(), key=lambda one: (one[0], -len(one[1])))


def _stance_options(usable, chosen):
    present = set()
    for spell in usable:
        for row in spell.rows:
            present |= row.conditions
    for group in STANCES:
        if present & set(group) and not chosen & set(group):
            return list(group)
    return [None]


def movement_split(role, mp):
    """(MP left for spells, MP spent moving) of a turn with `mp` MP, from role.movement.

    role.movement is the share of MP spent moving, 0 to 1; None spends none.
    """
    share = getattr(role, 'movement', None) or 0.0
    moving = min(mp, int(math.ceil(mp * share - 1e-9)))
    return mp - moving, moving


def stood_still(role, moving):
    """Whether a row that needs the caster not to have moved counts.

    A role that states no movement share takes the caster_does_not_move rule.
    """
    if getattr(role, 'movement', None) is None:
        return rule('caster_does_not_move')
    return not moving


def best_turn(spells, role, totals, conditions=(), orientation='front',
              casts_per_spell=None, wp=None, mp=None, class_mechanics=()):
    """Best expected damage of one turn on one enemy.

    role: a wakfu_value.DamageDealer (elements, reach, % damage inflicted, movement);
    conditions: keys the role adds to DEFAULT_CONDITIONS, see LABELS. A class
    with stances gets its best one unless conditions name one. mp: the turn's MP
    before the role's movement takes its share. class_mechanics: from
    SpellBook.class_mechanics, listed in unmodelled in place of the gauges the
    usable spells name.
    """
    if orientation not in ('front', 'side', 'rear'):
        raise ValueError('orientation is front, side or rear, got %r' % orientation)
    casts_per_spell = casts_per_spell or rule('casts_per_spell_per_turn')
    ap = int(totals.get('ap', 0))
    wp = int(min(totals.get('wp', 0), rule('wp_spent_per_turn') if wp is None else wp))
    mp, moving = movement_split(
        role, int(max(totals.get('mp', 0) if mp is None else mp, 0)))
    inflicted = role.damage_inflicted + totals.get('damage_inflicted', 0)
    chosen = set(DEFAULT_CONDITIONS) | set(conditions)
    if stood_still(role, moving):
        chosen.add(STILL)

    usable = [spell for spell in spells
              if castable(spell, role.elements) and reaches(spell, role.reach)]
    best = None
    for stance in _stance_options(usable, chosen):
        accepted = frozenset(chosen | ({stance} if stance else set()))
        worths, options = {}, []
        for spell in usable:
            worth, parts, change = cast_damage(
                spell, totals, role.reach, orientation, accepted, inflicted)
            if worth <= 0:
                continue
            cost = (max(spell.ap + change['ap'], 0), max(spell.wp + change['wp'], 0),
                    max(spell.mp + change['mp'], 0))
            worths[spell.id] = parts
            options.append((spell.id, worth, cost, casts_per_spell))
        damage, casts = rotation(options, ap, wp, mp)
        if best is None or damage > best[0]:
            best = (damage, casts, stance, accepted, worths)

    damage, casts, stance, accepted, worths = best
    elements = collections.Counter()
    for spell_id in casts:
        elements.update(worths[spell_id])
    cast = set(casts)
    if stance and not any(stance in row.conditions for spell in usable
                          if spell.id in cast for row in spell.rows):
        accepted, stance = accepted - {stance}, None

    counted, dropped = [], []
    for spell in usable:
        for row in spell.rows:
            if not (row.conditions - DEFAULT_CONDITIONS or row.unless
                    or ENEMY in row.conditions):
                continue
            keys = sorted(row.conditions) + [_opposite(key) for key in sorted(row.unless)]
            entry = (spell.id, row.position, tuple(keys), row.heading)
            if not lands(row, accepted):
                dropped.append(entry)
            elif spell.id in cast:
                counted.append(entry)
    settings = {'ap': ap, 'wp': wp, 'mp': mp, 'mp_moving': moving,
                'casts_per_spell': casts_per_spell, 'orientation': orientation,
                'conditions': tuple(sorted(accepted))}
    return Turn(damage, casts, dict(elements), stance, tuple(counted), tuple(dropped),
                tuple(spell.id for spell in usable), settings,
                _unmodelled(usable, class_mechanics))


def _opposite(key):
    return key[len(NOT):] if key.startswith(NOT) else 'not ' + key


def _unmodelled(usable, class_mechanics=()):
    out, gauges = [], collections.OrderedDict()
    for spell in usable:
        for position, reason in spell.skipped:
            out.append(((spell.id,), SKIPPED, 'row %d, %s' % (position, reason)))
        for key, detail in spell.mechanics:
            if key == GAUGE:
                gauges.setdefault(detail, []).append(spell.id)
            else:
                out.append(((spell.id,), key, detail))
    if class_mechanics:
        out.extend((tuple(ids), key, name) for key, name, ids in class_mechanics)
    else:
        out.extend((tuple(ids), GAUGE, name) for name, ids in gauges.items())
    return tuple(out)


def _plus(totals, key, amount=1):
    out = collections.Counter(totals)
    out[key] += amount
    return out


class TurnModel:
    """The damage side of the value from a class's best turn, for wakfu_value.

        model = TurnModel(book.spells(class_id, level), role)
        wakfu_value.solve(structure, level, role, forbidden, turn=model)

    options go to best_turn.
    """

    def __init__(self, spells, role, **options):
        self.spells = collections.OrderedDict((spell.id, spell) for spell in spells)
        self.role = role
        self.options = options

    def best(self, totals):
        return best_turn(tuple(self.spells.values()), self.role, totals, **self.options)

    def damage(self, totals):
        return self.best(totals).damage

    def _mastery_keys(self, row, totals, orientation, accepted):
        keys = [wakfu_value.REACH_MASTERY[row.reach or self.role.reach]]
        if row.element != 'light':
            keys.append(wakfu_value.MASTERY_OF[row.element])
        elif rule('light_uses_best_element_mastery'):
            order = list(self.role.elements) + [
                element for element in wakfu_value.ELEMENTS if element not in self.role.elements]
            keys.append(wakfu_value.MASTERY_OF[max(
                order, key=lambda element: totals.get(wakfu_value.MASTERY_OF[element], 0))])
        if orientation == 'rear':
            keys.append('backstab_bonus')
        if BERSERK in accepted:
            keys.append('berserk_dmg')
        return keys

    def weights(self, totals):
        """{stat key: percent of the turn per point just above totals}, the rotation held.

        AP is the best turn one AP up. Elemental mastery has no weight of its own:
        the solver adds the four element weights.
        """
        turn = self.best(totals)
        if turn.damage <= 0:
            return {}
        orientation = turn.settings['orientation']
        accepted = frozenset(turn.settings['conditions'])
        reach = self.role.reach
        inflicted = self.role.damage_inflicted + totals.get('damage_inflicted', 0)
        chance = wakfu_value.critical_chance(totals.get('ferocity', 0))
        every = _plus(totals, wakfu_value.ELEMENTAL_MASTERY)
        critical = _plus(totals, 'critical_bonus')
        ferocity = _plus(totals, 'ferocity')
        gains = collections.Counter()
        for spell_id in turn.casts:
            spell = self.spells[spell_id]
            for row, worth in counted_rows(spell, totals, reach, orientation, accepted,
                                           inflicted):
                per_point = _hit(row, every, reach, orientation, accepted, inflicted,
                                 chance) - worth
                for key in self._mastery_keys(row, totals, orientation, accepted):
                    gains[key] += per_point
                gains['critical_bonus'] += _hit(row, critical, reach, orientation, accepted,
                                                inflicted, chance) - worth
            gains['ferocity'] += (
                cast_damage(spell, ferocity, reach, orientation, accepted, inflicted)[0]
                - cast_damage(spell, totals, reach, orientation, accepted, inflicted)[0])
        weights = {key: 100 * gain / turn.damage for key, gain in gains.items() if gain > 0}
        weights['ap'] = 100 * (self.damage(_plus(totals, 'ap')) - turn.damage) / turn.damage
        return weights

    def ap_values(self, totals, high=None):
        """{AP total: 100 x log(turn at that AP / turn at totals)}, from 0 AP to the AP cap."""
        high = OUT_OF_COMBAT_CAPS['AP'] if high is None else high
        damages = {}
        for ap in range(high + 1):
            moved = collections.Counter(totals)
            moved['ap'] = ap
            damages[ap] = self.damage(moved)
        here = self.damage(totals)
        reference = here if here > 0 else max(damages.values())
        if reference <= 0:
            return {ap: 0.0 for ap in damages}
        return {ap: 100 * math.log(damage / reference) if damage > 0 else NO_DAMAGE
                for ap, damage in damages.items()}


def describe(condition):
    """English label of a condition key; an unnamed one is Ankama's French heading."""
    if condition.startswith(NOT) and condition[len(NOT):] in LABELS:
        return 'unless ' + LABELS[condition[len(NOT):]]
    return LABELS.get(condition, condition)
