"""Ankama equip criteria such as 'CS>20&(PG=1|PG=2)': parsed, and sorted by what a build can check."""

from __future__ import annotations

import json
import re
from pathlib import Path

STAT = 'stat'
CLASS = 'class'
LEVEL = 'level'
SET_BONUS = 'set_bonus'
SETS_EQUIPPED = 'sets_equipped'
SPELL_RANK = 'spell_rank'
UNUSABLE = 'unusable'
NOT_WORN_WITH = 'not_worn_with'
SEX = 'sex'
NAME = 'name'
ENFORCED = frozenset((STAT, CLASS, LEVEL, SET_BONUS, SETS_EQUIPPED, SPELL_RANK,
                      UNUSABLE, NOT_WORN_WITH, SEX, NAME))

# Player state a build does not carry, the character's server or the calendar
ALIGNMENT = 'alignment'
PVP_RANK = 'pvp_rank'
JOB = 'job'
KAMAS = 'kamas'
MARRIED = 'married'
EMOTE = 'emote'
SUBSCRIPTION = 'subscription'
ACCOUNT_RIGHTS = 'account_rights'
QUEST = 'quest'
SERVER = 'server'
DATE = 'date'
MAP = 'map'
SUBAREA = 'subarea'
INVENTORY = 'inventory'
# Other pieces worn: the only such piece has no stats
WORN_WITH = 'worn_with'
UNKNOWN = 'unknown'

STAT_CODES = {
    'CS': 'Strength', 'CI': 'Intelligence', 'CA': 'Agility',
    'CV': 'Vitality', 'CC': 'Chance', 'CW': 'Wisdom',
    # Total AP and MP, the piece's own bonus included
    'CP': 'AP', 'CM': 'MP',
}

_STATS = {(code, operator): STAT for code in STAT_CODES for operator in '<>='}

KINDS = {
    'dofus3': {
        **_STATS,
        ('PG', '='): CLASS,
        ('PL', '<'): LEVEL,
        ('Pk', '<'): SET_BONUS,
        ('pk', '<'): SETS_EQUIPPED,
        ('BI', '='): UNUSABLE,
        ('Ps', '='): ALIGNMENT, ('Pa', '>'): ALIGNMENT,
        ('PJ', '>'): JOB,
        ('PK', '>'): KAMAS,
        ('PN', '~'): NAME,
        ('PS', '='): SEX,
        ('PE', '='): EMOTE,
        ('PZ', '='): SUBSCRIPTION,
        ('PX', '='): ACCOUNT_RIGHTS,
        ('Qa', '='): QUEST, ('Qf', '='): QUEST, ('Qo', '>'): QUEST,
        ('Qo', '<'): QUEST, ('Qo', '='): QUEST,
        ('Sc', '='): SERVER,
        ('SG', '='): DATE, ('Sd', '>'): DATE, ('Sd', '<'): DATE,
        ('Pm', '='): MAP,
        ('PO', '!'): INVENTORY,
        ('OS', '='): UNKNOWN,
        ('Pn', '!'): UNKNOWN,
    },
    'beta': {
        **_STATS,
        ('PG', '='): CLASS,
        ('PL', '<'): LEVEL,
        ('Pk', '<'): SET_BONUS,
        ('pk', '<'): SETS_EQUIPPED,
        ('BI', '='): UNUSABLE,
        ('Ps', '='): ALIGNMENT, ('Pa', '>'): ALIGNMENT,
        ('PJ', '>'): JOB,
        ('PK', '>'): KAMAS,
        ('PN', '~'): NAME,
        ('PS', '='): SEX,
        ('PE', '='): EMOTE,
        ('PZ', '='): SUBSCRIPTION,
        ('PX', '='): ACCOUNT_RIGHTS,
        ('Qa', '='): QUEST, ('Qf', '='): QUEST, ('Qo', '>'): QUEST,
        ('Qo', '<'): QUEST, ('Qo', '='): QUEST,
        ('Sc', '='): SERVER, ('SC', '='): SERVER, ('ST', '='): SERVER,
        ('SG', '='): DATE, ('Sd', '>'): DATE, ('Sd', '<'): DATE,
        ('Pm', '='): MAP,
        ('PO', '!'): INVENTORY,
        ('OS', '='): UNKNOWN,
        ('Pn', '!'): UNKNOWN,
    },
    'dofus2': {
        **_STATS,
        ('PG', '='): CLASS,
        ('PL', '<'): LEVEL,
        ('Pk', '<'): SET_BONUS,
        ('BI', '='): UNUSABLE,
        ('PO', 'X'): NOT_WORN_WITH,
        ('Ps', '='): ALIGNMENT, ('Pa', '>'): ALIGNMENT,
        ('PJ', '>'): JOB,
        ('PK', '>'): KAMAS,
        ('PN', '~'): NAME,
        ('PS', '='): SEX,
        ('PE', '='): EMOTE,
        ('PZ', '='): SUBSCRIPTION,
        ('PX', '='): ACCOUNT_RIGHTS,
        ('Qa', '='): QUEST, ('Qf', '='): QUEST, ('Qo', '>'): QUEST,
        ('Qo', '<'): QUEST, ('Qo', '='): QUEST,
        ('Sc', '='): SERVER, ('SI', '='): SERVER,
        ('SG', '='): DATE, ('Sd', '>'): DATE, ('Sd', '<'): DATE,
        ('Pm', '='): MAP,
        ('PO', '!'): INVENTORY,
        ('OS', '='): UNKNOWN,
        ('HA', '!'): UNKNOWN,
        ('Mw', '='): UNKNOWN,
        ('Pn', '!'): UNKNOWN,
    },
    'touch': {
        **_STATS,
        ('PG', '='): CLASS,
        ('PL', '>'): LEVEL, ('PL', '<'): LEVEL,
        ('Pk', '<'): SET_BONUS,
        ('Pt', '='): SPELL_RANK,
        ('BI', '='): UNUSABLE,
        ('Ps', '='): ALIGNMENT, ('Pa', '>'): ALIGNMENT,
        ('PP', '>'): PVP_RANK,
        ('PJ', '>'): JOB,
        ('PN', '~'): NAME,
        ('PS', '='): SEX,
        ('PR', '='): MARRIED,
        ('PE', '='): EMOTE,
        ('PX', '='): ACCOUNT_RIGHTS,
        ('Qa', '='): QUEST, ('Qf', '='): QUEST,
        ('Sc', '='): SERVER,
        ('SG', '='): DATE,
        ('PB', '='): SUBAREA, ('PB', '!'): SUBAREA,
        ('PO', '!'): INVENTORY,
        ('OP', '!'): UNKNOWN, ('OP', '='): UNKNOWN,
        ('Ft', '!'): UNKNOWN,
    },
    'retro': {
        **_STATS,
        ('PG', '='): CLASS, ('PG', '!'): CLASS,
        ('PL', '>'): LEVEL, ('PL', '<'): LEVEL,
        ('BI', '='): UNUSABLE,
        ('Ps', '='): ALIGNMENT, ('Pa', '>'): ALIGNMENT,
        ('PP', '>'): PVP_RANK,
        ('PJ', '>'): JOB, ('PJ', '='): JOB,
        ('PK', '>'): KAMAS,
        ('PN', '~'): NAME,
        ('PS', '='): SEX,
        ('PZ', '='): SUBSCRIPTION,
        ('PX', '='): ACCOUNT_RIGHTS,
        ('Qa', '='): QUEST,
        ('Sc', '='): SERVER, ('SI', '='): SERVER,
        ('SG', '='): DATE, ('Sd', '>'): DATE, ('Sd', '<'): DATE,
        ('PB', '='): SUBAREA, ('PB', '!'): SUBAREA,
        ('PO', '!'): INVENTORY, ('PO', 'E'): WORN_WITH,
        ('Pg', '='): UNKNOWN,
    },
}

_TOKEN = re.compile(r'\s*([()&|])\s*|\s*([^()&|]+)')
_ATOM = re.compile(r'([A-Za-z]{2})([=!<>~XE])(.*)', re.S)


class CriteriaError(ValueError):
    pass


def _tokens(criteria):
    out = []
    for symbol, atom in _TOKEN.findall(criteria):
        if symbol:
            out.append(symbol)
        elif atom.strip():
            match = _ATOM.fullmatch(atom.strip())
            if match is None:
                raise CriteriaError('unreadable condition %r in %r' % (atom, criteria))
            out.append((match.group(1), match.group(2), match.group(3).strip()))
    return out


def parse(criteria):
    """criteria -> ('and' | 'or', [nodes]) or an atom (code, operator, value); None when empty."""
    text = str(criteria or '').strip()
    if not text or text == 'null':
        return None
    tokens = _tokens(text)
    position = 0

    def group():
        nonlocal position
        nodes, joins = [term()], set()
        while position < len(tokens) and tokens[position] in ('&', '|'):
            joins.add(tokens[position])
            position += 1
            nodes.append(term())
        if len(joins) > 1:
            raise CriteriaError('& and | mixed without parentheses in %r' % text)
        if len(nodes) == 1:
            return nodes[0]
        return ('and' if joins == {'&'} else 'or', nodes)

    def term():
        nonlocal position
        if position >= len(tokens):
            raise CriteriaError('truncated condition %r' % text)
        token = tokens[position]
        position += 1
        if token == '(':
            node = group()
            if position >= len(tokens) or tokens[position] != ')':
                raise CriteriaError('unbalanced parentheses in %r' % text)
            position += 1
            return node
        if isinstance(token, tuple):
            return token
        raise CriteriaError('unexpected %r in %r' % (token, text))

    tree = group()
    if position != len(tokens):
        raise CriteriaError('trailing text in %r' % text)
    return tree


def read(criteria, item_id):
    """parse(), or None with a warning line: the census test then names the piece."""
    try:
        return parse(criteria)
    except CriteriaError as error:
        print('warning: equip criteria of item %s left unread: %s' % (item_id, error))
        return None


def atoms(tree):
    if tree is None:
        return []
    if isinstance(tree[1], list):
        return [atom for node in tree[1] for atom in atoms(node)]
    return [tree]


def _is_atom(node):
    return not isinstance(node[1], list)


def holds(tree, truth):
    """Whether the criteria hold when truth(atom) says which atoms do."""
    if tree is None:
        return True
    if _is_atom(tree):
        return bool(truth(tree))
    results = (holds(node, truth) for node in tree[1])
    return all(results) if tree[0] == 'and' else any(results)


def kinds(version, tree):
    """{(code, operator): kind or None} of every atom, None for a kind the version does not list."""
    table = KINDS[version]
    return {(code, operator): table.get((code, operator))
            for code, operator, _value in atoms(tree)}


def _class_holds(atom, class_id):
    code, operator, value = atom
    try:
        wanted = int(value)
    except ValueError:
        return False
    return (class_id == wanted) if operator == '=' else (class_id != wanted)


def allowed_classes(tree, class_names):
    """Names of the classes that can meet the criteria, or None when every class can."""
    allowed = []
    for class_id, name in sorted(class_names.items()):
        if holds(tree, lambda atom: (_class_holds(atom, class_id)
                                     if atom[0] == 'PG' else True)):
            allowed.append(name)
    if len(allowed) == len(class_names):
        return None
    return allowed


def is_unusable(tree):
    """Whether an unusable-item condition (BI) makes the criteria impossible to meet."""
    return not holds(tree, lambda atom: atom[0] != 'BI')


def _sex_holds(atom, sex):
    try:
        wanted = int(atom[2])
    except ValueError:
        return False
    return (sex == wanted) if atom[1] == '=' else (sex != wanted)


def allowed_sexes(tree):
    """The sexes (the game's PS flag: 0 male, 1 female) that can meet the criteria, or None when both can."""
    allowed = [sex for sex in (0, 1)
               if holds(tree, lambda atom: (_sex_holds(atom, sex)
                                            if atom[0] == 'PS' else True))]
    return None if len(allowed) == 2 else allowed


def name_fits(char_name, wanted):
    """PN~: the character's name, whatever its case."""
    return (char_name or '').strip().lower() == wanted.lower()


def allowed_names(tree):
    """The character names that can meet the criteria, as the data writes them, or None when any name can."""
    names = sorted({atom[2] for atom in atoms(tree) if atom[0] == 'PN'})
    if not names:
        return None

    def fits(char_name):
        return holds(tree, lambda atom: ((atom[1] == '~' and name_fits(char_name, atom[2]))
                                         if atom[0] == 'PN' else True))

    if fits('\x00'):
        return None
    return [name for name in names if fits(name)]


def _top_level(tree):
    if tree is None:
        return []
    if not _is_atom(tree) and tree[0] == 'and':
        return tree[1]
    return [tree]


def level_bounds(tree):
    """(lowest, highest) character level the top-level PL parts allow, None when open."""
    lowest = highest = None
    for node in _top_level(tree):
        if not _is_atom(node) or node[0] != 'PL':
            continue
        value = int(node[2])
        if node[1] == '>':
            lowest = max(lowest or 0, value + 1)
        elif node[1] == '<':
            highest = value - 1 if highest is None else min(highest, value - 1)
    return lowest, highest


def not_worn_with(tree):
    """Ankama ids of the pieces this one cannot be worn with (PO with operator X)."""
    return [int(node[2]) for node in _top_level(tree)
            if _is_atom(node) and node[0] == 'PO' and node[1] == 'X'
            and node[2].isdigit()]


def set_bonus_caps(tree):
    """['Set bonus < 3'] for a top-level Pk part."""
    return ['Set bonus < %s' % node[2] for node in _top_level(tree)
            if _is_atom(node) and node[0] == 'Pk' and node[1] == '<']


def sets_equipped_caps(tree):
    """['Sets equipped < 2'] for a top-level pk part."""
    return ['Sets equipped < %s' % node[2] for node in _top_level(tree)
            if _is_atom(node) and node[0] == 'pk' and node[1] == '<']


def _stat_gate(atom):
    code, operator, value = atom
    return '%s %s %s' % (STAT_CODES[code], operator, int(value))


def _only_stats(tree):
    """The criteria with every non-stat atom taken as met: True, or a tree of stat atoms."""
    if _is_atom(tree):
        return tree if (tree[0] in STAT_CODES and tree[2].lstrip('-').isdigit()) else True
    kept = []
    for node in tree[1]:
        reduced = _only_stats(node)
        if reduced is True:
            if tree[0] == 'or':
                return True
            continue
        kept.append(reduced)
    if not kept:
        return True
    if len(kept) == 1:
        return kept[0]
    return (tree[0], kept)


def _branches(tree):
    """A stat tree as OR of AND branches, each a list of atoms."""
    if _is_atom(tree):
        return [[tree]]
    if tree[0] == 'or':
        return [branch for node in tree[1] for branch in _branches(node)]
    combined = [[]]
    for node in tree[1]:
        combined = [left + right for left in combined for right in _branches(node)]
    return combined


def stat_conditions(tree):
    """['Strength > 20', 'MP < 6 | AP < 12', ...]: parts ANDed, the OR parts in one string."""
    if tree is None:
        return []
    reduced = _only_stats(tree)
    if reduced is True:
        return []
    out = []
    either = None
    for node in _top_level(reduced):
        branches = _branches(node)
        if len(branches) == 1:
            out.extend(_stat_gate(atom) for atom in branches[0])
            continue
        # The dump keeps one OR group per piece
        if either is None:
            either = len(out)
            out.append(branches)
        else:
            out[either] = [left + right for left in out[either] for right in branches]
    if either is not None:
        out[either] = ' | '.join(' & '.join(_stat_gate(atom) for atom in branch)
                                 for branch in out[either])
    return out


def load_raw_items_criteria(path):
    """{ankama id: criteria} from a dofusdude items.json, the Dofus 2 list or the Dofus 3 Unity export."""
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    out = {}
    if isinstance(data, dict):
        for reference in (data.get('references') or {}).get('RefIds') or []:
            record = reference.get('data') or {}
            if 'id' in record and 'criterions' in record:
                out[int(record['id'])] = record.get('criterions') or ''
    else:
        for record in data:
            if isinstance(record, dict) and 'id' in record:
                out[int(record['id'])] = record.get('criteria') or ''
    return out


def load_raw_class_names(raw_dir):
    """{breed id: English short name} from a dofusdude dump's breeds.json and en.json."""
    raw_dir = Path(raw_dir)
    breeds = json.loads((raw_dir / 'breeds.json').read_text(encoding='utf-8'))
    language = json.loads((raw_dir / 'en.json').read_text(encoding='utf-8'))
    # Dofus 3 files its strings under "entries", Dofus 2 under "texts"
    texts = language.get('entries') or language.get('texts') or {}
    if isinstance(breeds, dict):
        records = [reference.get('data') or {} for reference
                   in (breeds.get('references') or {}).get('RefIds') or []]
    else:
        records = breeds
    out = {}
    for record in records:
        if 'id' in record and 'shortNameId' in record:
            name = texts.get(str(record['shortNameId']))
            if name:
                out[int(record['id'])] = name
    return out


def describe(tree, class_names, version):
    """The fields the dump writes for one piece, from its criteria."""
    out = {}
    classes = allowed_classes(tree, class_names)
    if classes is not None:
        out['classes'] = classes
    if is_unusable(tree):
        out['unusable'] = True
    lowest, highest = level_bounds(tree)
    if lowest is not None:
        out['min_level'] = lowest
    if highest is not None:
        out['max_level'] = highest
    others = not_worn_with(tree)
    if others and KINDS[version].get(('PO', 'X')) == NOT_WORN_WITH:
        out['not_worn_with'] = others
    sexes = allowed_sexes(tree)
    if sexes is not None:
        out['sexes'] = sexes
    names = allowed_names(tree)
    if names is not None:
        out['names'] = names
    return out
