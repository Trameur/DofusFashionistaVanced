# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.

"""Wakfu game texts: effect lines, conditions and names, all read from the game's tables."""

import collections
import html
import json
import logging
import math
import re

from fashionistapulp import wakfu_criteria, wakfu_db

LOG = logging.getLogger(__name__)

FALLBACK_LANGUAGE = 'en'
BULLET = '• '
THOUSANDS_SEPARATOR = '\u202f'
GROUP_SEPARATORS = {'fr': '\u202f', 'es': '.', 'pt': '.'}
DEFAULT_GROUP_SEPARATOR = ','
LEVEL_WITHOUT_CHARACTER = 63

STATE_ACTION = 304
JOB_HARVEST_ACTION = 2001
MERGED_ACTIONS = {82: ('resistance', 0), 83: ('resistance', 1), 84: ('resistance', 2),
                  85: ('resistance', 3), 122: ('mastery', 0), 124: ('mastery', 1),
                  123: ('mastery', 2), 125: ('mastery', 3)}

_WORDS = '|'.join((
    'fighter', 'shield', 'glyph', 'paw', 'taque', 'tique', 'backstab', 'sidestab',
    'invisible', 'barrel', 'lucky', 'totem', 'puppet', 'enemy', 'ally', 'caster', 'serein',
    'exalte', 'deposit', 'bomb', 'seed', 'natural', 'unnatural', 'portal', 'rune[1-4]',
    'prey', 'chromatic', 'undrake', 'drake', 'ecnbi', 'ecnbr'))

SHAPES = (
    ('[#N]', r'#\d+'), ('[#N.N]', r'#\d+\.\d+'), ('[£N]', r'£\d+'),
    ('[#charac K]', r'#charac [A-Za-z0-9_]+'), ('[#icon N]', r'#icon \d+'),
    ('[~N]', r'~\d+'), ('[!N]', r'!\d+'), ('[>N]', r'>\d+'), ('[<N]', r'<\d+'),
    ('[=N]', r'=\d+'), ('[N>N]', r'-?\d+>\d+'), ('[N<N]', r'-?\d+<\d+'),
    ('[N=N]', r'-?\d+=\d+'), ('[+N]', r'\+\d+'), ('[-N]', r'-\d+'),
    ('[N*]', r'\d+\*'), ('[pl]', r'pl'), ('[lv]', r'lv'), ('[elN]', r'el\d*'),
    ('[$Nef]', r'\$\d+ef'), ('[$N#N]', r'\$\d+#\d+'), ('[word]', _WORDS),
    ('[stN]', r'st\d+'), ('[li]', r'l[ip]'), ('[se]', r'se'), ('[AREA]', r'[A-Z][A-Z0-9]*'),
)
_SHAPE_PATTERNS = tuple((shape, re.compile(pattern)) for shape, pattern in SHAPES)
KNOWN_SHAPES = frozenset(shape for shape, _pattern in SHAPES)

_BRACKET = re.compile(r'\[([^\[\]]*)\]')
_BLOCK = re.compile(r'\{((?:\[[^\[\]{}?:]*\])+)\s*\?([^{}]*):([^{}]*)\}')
_CONDITION = re.compile(r'\[([^\[\]]*)([~*+\-><!=])([^\[\]]*)\]')
_VALUE = re.compile(r'\[([£#])(\d+)(?:\.(\d+))?\]')
_MEMBER_LINE = re.compile(r'\[\$(\d+)ef\]')
_MEMBER_PARAM = re.compile(r'\[\$(\d+)#(\d+)\]')
_CHARAC = re.compile(r'\[#charac ([A-Za-z0-9_]+)\]')
_ARITHMETIC = re.compile(r'\|(\d[\d\u202f]*(?:\.\d+)?)([^|]*)\|')
_OPERATION = re.compile(r'([+\-*/])(\d+(?:\.\d+)?)')
_GENDER = re.compile(r'\{\[1\*\]\s*\?[^{}:]*:([^{}]*)\}')
_FIGHTER_WORD = re.compile(r'\[(%s)\]' % _WORDS)
_STATE_TAG = re.compile(r'\[st(\d+)\]')
_ICON = re.compile(r'\[#charac [^\]]*\]|\[#icon [^\]]*\]|\[el\d*\]|\[[A-Z][A-Z0-9]*\]'
                   r'|\[(?:%s)\]' % _WORDS)

Line = collections.namedtuple('Line', 'text stat')
Effect = collections.namedtuple('Effect', 'id action params display record_order')
Condition = collections.namedtuple('Condition', 'text missing')

EFFECT_COLUMNS = 'id, action, params, display, record_order'


def token_shape(inner):
    """The census name of one bracketed token, digits as N, None when the parser lacks it."""
    for shape, pattern in _SHAPE_PATTERNS:
        if pattern.fullmatch(inner):
            return shape
    return None


def token_shapes(text):
    """Every bracketed token of a text as (shape or None, token)."""
    return [(token_shape(inner), '[%s]' % inner) for inner in _BRACKET.findall(text or '')]


class TextSource:
    """The game's texts in one language, read lazily; a text the language lacks falls back to
    English and is remembered in `fallbacks` so a test can fail on it."""

    def __init__(self, conn, language):
        self.conn = conn
        self.language = language
        self.fallbacks = set()
        self.unknown = set()
        self._cache = {}

    def _text(self, what, sql, *key):
        marker = (what,) + key
        if marker in self._cache:
            return self._cache[marker]
        value = None
        for language in (self.language, FALLBACK_LANGUAGE):
            row = self.conn.execute(sql, key + (language,)).fetchone()
            if row is not None:
                value = row[0]
                if language != self.language:
                    self.fallbacks.add(marker)
                break
        self._cache[marker] = value
        return value

    def action_text(self, action):
        return self._text('action', 'SELECT text FROM action_texts WHERE action = ?'
                          ' AND language = ?', action)

    def effect_text(self, effect):
        return self._text('effect', 'SELECT text FROM effect_texts WHERE effect = ?'
                          ' AND language = ?', effect)

    def state_name(self, state):
        return self._text('state', 'SELECT name FROM state_texts WHERE state = ?'
                          ' AND language = ?', state)

    def job_name(self, job):
        return self._text('job', 'SELECT name FROM client_job_names WHERE job = ?'
                          ' AND language = ?', job)

    def item_name(self, item):
        return self._text('item', 'SELECT name FROM item_names WHERE item = ?'
                          ' AND language = ?', item)

    def breed_name(self, breed):
        raw = self._text('breed', 'SELECT name FROM client_breed_names WHERE breed = ?'
                         ' AND language = ?', breed)
        return None if raw is None else format_text(raw, [])

    def label(self, key):
        return self._text('label', 'SELECT text FROM criteria_labels WHERE key = ?'
                          ' AND language = ?', key)

    def type_name(self, item_type):
        raw = self._text('type', 'SELECT name FROM client_item_type_names'
                         ' WHERE item_type = ? AND language = ?', item_type)
        return None if raw is None else wakfu_db.singular(raw)

    def rarity_name(self, rarity):
        return self._text('rarity', 'SELECT name FROM rarity_names WHERE rarity = ?'
                          ' AND language = ?', rarity)

    def set_name(self, item_set):
        return self._text('set', 'SELECT name FROM client_set_names WHERE item_set = ?'
                          ' AND language = ?', item_set)

    def description(self, item):
        raw = self._text('description', 'SELECT description FROM item_descriptions'
                         ' WHERE item = ? AND language = ?', item)
        return None if raw is None else _GENDER.sub(lambda found: found.group(1), raw)

    def state_levels(self, state):
        marker = ('state_levels', state)
        if marker not in self._cache:
            row = self.conn.execute('SELECT max_level, cumulable FROM states WHERE id = ?',
                                    (state,)).fetchone()
            self._cache[marker] = row
        return self._cache[marker]

    def ingredient_name(self, ingredient, subtype):
        marker = ('ingredient', ingredient, subtype)
        if marker in self._cache:
            return self._cache[marker]
        value = None
        for language in (self.language, FALLBACK_LANGUAGE):
            row = self.conn.execute(
                'SELECT name FROM item_recipe_ingredient_names WHERE ingredient_ankama_id = ?'
                ' AND ingredient_subtype = ? AND language = ?',
                (ingredient, subtype, language)).fetchone()
            if row is not None:
                value = row[0]
                if language != self.language:
                    self.fallbacks.add(marker)
                break
        self._cache[marker] = value
        return value


class Argument:
    """One parameter of an effect: the whole number the game shows and the exact value."""
    __slots__ = ('whole', 'exact')

    def __init__(self, whole, exact):
        self.whole = whole
        self.exact = exact


def arguments(params, level):
    return [Argument(wakfu_db.level_value(params[2 * index], params[2 * index + 1], level),
                     float(wakfu_db.effect_value(params, index, level)))
            for index in range(len(params) // 2)]


def _number(argument):
    if isinstance(argument, Argument):
        return float(argument.whole)
    if isinstance(argument, (int, float)):
        return float(argument)
    if isinstance(argument, str):
        try:
            return float(argument.replace(',', '.'))
        except ValueError:
            return None
    return None


def _grouped(digits):
    sign = '-' if digits.startswith('-') else ''
    whole, point, fraction = digits.lstrip('-').partition('.')
    groups = []
    while len(whole) > 3:
        groups.insert(0, whole[-3:])
        whole = whole[:-3]
    groups.insert(0, whole)
    return sign + THOUSANDS_SEPARATOR.join(groups) + point + fraction


def localized(text, language):
    """`text` with the renderer's internal thousands mark turned into the separator the
    language's official pages use; German shows the English game text."""
    return text.replace(THOUSANDS_SEPARATOR,
                        GROUP_SEPARATORS.get(language, DEFAULT_GROUP_SEPARATOR))


def _plain(number):
    if number == int(number):
        return _grouped(str(int(number)))
    return _grouped(('%.6f' % number).rstrip('0').rstrip('.'))


def _condition_holds(conditions, args):
    holds = True
    for literal, operator, index in _CONDITION.findall(conditions):
        wanted = int(literal) if literal else 1
        position = int(index) if index else -1
        present = len(args) >= position
        argument = args[position - 1] if present and position >= 1 else None
        number = _number(argument)
        if operator in '<>=':
            if not present:
                continue
            if number is None:
                holds = False
            elif operator == '<':
                holds = holds and math.ceil(number) < wanted
            elif operator == '>':
                holds = holds and math.ceil(number) > wanted
            else:
                holds = holds and number == wanted
        elif operator == '~':
            holds = holds and present and argument is not None and (
                number != 0 if number is not None else argument != '')
        elif operator == '!':
            holds = holds and (not present or argument is None or number == 0
                               or argument == '')
        elif operator == '+':
            holds = holds and present and argument is not None and (number or 0) > 0
        elif operator == '-':
            holds = holds and present and argument is not None and not (number or 0) > 0
        else:
            holds = False
    return holds


def format_text(text, args):
    """Ankama's formatter: conditional blocks, then [#N] values."""
    if not any(mark in text for mark in '[{|'):
        return text
    while True:
        resolved = _BLOCK.sub(
            lambda found: found.group(2) if _condition_holds(found.group(1), args)
            else found.group(3), text)
        if resolved == text:
            break
        text = resolved

    def value(found):
        position = int(found.group(2)) - 1
        if position >= len(args) or args[position] is None:
            return found.group(0)
        argument = args[position]
        if isinstance(argument, str):
            number = _number(argument)
            if number is None:
                return argument
            argument = number
        decimals = int(found.group(3)) if found.group(3) else 0
        if isinstance(argument, Argument):
            shown = argument.exact if decimals else argument.whole
        else:
            shown = argument
        shown = round(shown, decimals) if decimals else math.floor(shown + 0.5)
        if found.group(1) == '£':
            shown = abs(shown)
        return _plain(shown)
    return _VALUE.sub(value, text)


def _arithmetic(text):
    def one(found):
        total = float(found.group(1).replace(THOUSANDS_SEPARATOR, ''))
        for operator, operand in _OPERATION.findall(found.group(2).replace(
                THOUSANDS_SEPARATOR, '')):
            operand = float(operand)
            total = (total + operand if operator == '+' else total - operand
                     if operator == '-' else total * operand if operator == '*'
                     else total / operand)
        return _plain(math.floor(total + 0.5))
    return _ARITHMETIC.sub(one, text)


def tidy(text):
    return re.sub(r'[ \t]+', ' ', _ICON.sub('', text)).strip()


def _members(conn, group_id):
    return [row[0] for row in conn.execute(
        'SELECT effect FROM effect_groups WHERE group_id = ? ORDER BY position',
        (group_id,)).fetchall()]


def _effect(conn, effect_id):
    row = conn.execute('SELECT %s FROM effects WHERE id = ?' % EFFECT_COLUMNS,
                       (effect_id,)).fetchone()
    return None if row is None else _effect_of_row(row)


def _effect_of_row(row):
    return Effect(row[0], row[1], json.loads(row[2]), row[3], row[4])


def effects_of_container(conn, container_type, container, kind=None):
    """The effects of an item, in the order the game lists them; `kind` keeps only the
    NORMAL or the CRITICAL rows."""
    sql = 'SELECT %s FROM effects WHERE container_type = ? AND container = ?' % EFFECT_COLUMNS
    params = (container_type, container)
    if kind is not None:
        sql += ' AND normal_or_critical = ?'
        params += (kind,)
    rows = conn.execute(sql + ' ORDER BY record_order, id', params)
    return [_effect_of_row(row) for row in rows.fetchall()]


def render_effect(source, effect, level, depth=0, simplified=False):
    """The text of one effect, line breaks kept; None when the game shows nothing. A
    simplified rendering ignores the effect's own text, as the game does for a [se] part."""
    if not effect.display or depth > 8:
        return None
    conn = source.conn
    members = _members(conn, effect.id)
    own = None if simplified else source.effect_text(effect.id)
    text = own or source.action_text(effect.action)
    args = arguments(effect.params, level)
    if members and (not text or ('[$' not in text and not own)):
        rendered = [render_effect(source, _effect(conn, member), level, depth + 1)
                    for member in members]
        rendered = [one for one in rendered if one]
        return '\n'.join(rendered) if rendered else None
    if not text:
        return None
    if members:
        text = _MEMBER_LINE.sub(
            lambda found: _member_line(source, members, int(found.group(1)), level, depth),
            text)
        text = _MEMBER_PARAM.sub(
            lambda found: _member_param(conn, members, found, level), text)
    text = text.replace('[pl]', BULLET).replace('[lv]', str(LEVEL_WITHOUT_CHARACTER))
    if '[se]' in text:
        text = text.replace('[se]', render_effect(source, effect, level, depth + 1, True) or '')
    text = _STATE_TAG.sub(lambda found: source.state_name(int(found.group(1)))
                          or found.group(0), text)
    level_label = ''
    if effect.action == STATE_ACTION and args:
        state = args[0].whole
        if '[#1]' in text:
            level_label = _state_level_label(source, state, args)
        if len(args) >= 2 and ('[li]' in text or '[lp]' in text):
            text = _state_effect_list(source, text, state, args[1].whole, depth)
        name = source.state_name(state)
        args[0] = name if name is not None else args[0]
    if effect.action == JOB_HARVEST_ACTION and len(args) >= 2 and args[1].whole:
        name = source.job_name(args[1].whole)
        args[1] = name if name is not None else args[1]
    shown = format_text(text, args)
    if level_label:
        shown = shown.rstrip() + ' ' + level_label
    shown = _FIGHTER_WORD.sub(lambda found: _fighter_word(source, found), shown)
    return _drop_unknown_tokens(source, shown, effect.id)


def _fighter_word(source, found):
    word = source.label(found.group(1)) or ''
    before = found.string[found.start() - 1:found.start()] if found.start() else ''
    if word and before and not before.isspace():
        return ' ' + word
    return word


def _state_effect_list(source, text, state, state_level, depth):
    effects = effects_of_container(source.conn, 'STATE', state)
    lines = effect_lines(source, effects, state_level, depth + 1)
    listing = '\n'.join(line.text for line in lines)
    return text.replace('[li]', listing).replace('[lp]', listing)


def _state_level_label(source, state, args):
    levels = source.state_levels(state)
    if levels is None or len(args) < 2:
        return ''
    max_level, cumulable = levels
    template = source.label('levelShort.customCumulable' if cumulable
                            else 'levelShort.custom')
    if not template:
        return ''
    shown = format_text(template, [min(max_level, args[1].whole)]).strip()
    return '(%s)' % shown


def _drop_unknown_tokens(source, text, owner):
    unknown = [token for shape, token in token_shapes(text) if shape is None]
    if not unknown:
        return text
    log_unknown(source, [(None, token) for token in unknown], owner)
    for token in unknown:
        text = text.replace(token, '')
    return text


def _member_line(source, members, position, level, depth):
    if position > len(members):
        return '[$%def]' % position
    member = _effect(source.conn, members[position - 1])
    return render_effect(source, member, level, depth + 1) or ''


def _member_param(conn, members, found, level):
    position, index = int(found.group(1)), int(found.group(2))
    if position > len(members):
        return found.group(0)
    member = _effect(conn, members[position - 1])
    values = arguments(member.params, level)
    return _plain(values[index - 1].whole) if index <= len(values) else found.group(0)


def _lines_of(text):
    lines = []
    for part in text.split('\n'):
        match = _CHARAC.search(part)
        shown = tidy(part)
        if shown:
            lines.append(Line(shown, match.group(1).lower() if match else None))
    return lines


def _merged_header(source, kind, value):
    template = source.label('effect.description.merged.' + kind)
    return _lines_of(format_text(template, [value])) if template else []


def effect_lines(source, effects, level, depth=0):
    """The lines the game shows for a list of effects, resistance and mastery lines of one
    value gathered where the first of them stands."""
    lines = []
    merged = collections.OrderedDict()
    anchor = None
    for effect in effects:
        text = render_effect(source, effect, level, depth)
        if not text:
            continue
        parts = _lines_of(_arithmetic(text))
        if effect.action in MERGED_ACTIONS and parts:
            kind, order = MERGED_ACTIONS[effect.action]
            if anchor is None:
                anchor = len(lines)
            value = arguments(effect.params, level)[0].whole
            merged.setdefault((kind, value), []).append((order, parts))
            continue
        lines.extend(parts)
    block = []
    for (kind, value), group in merged.items():
        if len(group) > 1:
            block.extend(_merged_header(source, kind, value))
        for _order, parts in sorted(group, key=lambda one: one[0]):
            block.extend(parts)
    if anchor is not None:
        lines[anchor:anchor] = block
    if depth == 0:
        return [Line(localized(line.text, source.language), line.stat) for line in lines]
    return lines


def worn_effects_by_item(conn, item_ids=None):
    """{item id: [Effect]} for every item or for the given ones, in the order the game lists
    them."""
    out = collections.defaultdict(list)
    sql = "SELECT container, %s FROM effects WHERE container_type = 'ITEM_EQUIP'" % EFFECT_COLUMNS
    params = ()
    if item_ids is not None:
        params = tuple(item_ids)
        sql += ' AND container IN (%s)' % ','.join('?' * len(params))
    rows = conn.execute(sql + ' ORDER BY record_order, id', params)
    for row in rows:
        out[row[0]].append(_effect_of_row(row[1:]))
    return out


def item_lines(source, item_id, level, effects=None):
    if effects is None:
        effects = effects_of_container(source.conn, 'ITEM_EQUIP', item_id)
    return effect_lines(source, effects, level)


def use_lines(source, item_id, level, kind='NORMAL'):
    """The lines of an item's use effects of one kind: the NORMAL rows by default, the
    CRITICAL rows when asked, never both."""
    return effect_lines(source, effects_of_container(source.conn, 'ITEM_USE', item_id,
                                                     kind), level)


def bonus_lines(source, effect_id, level):
    effect = _effect(source.conn, effect_id)
    return [] if effect is None else effect_lines(source, [effect], level)


def log_unknown(source, shapes_and_tokens, owner):
    for shape, token in shapes_and_tokens:
        if shape is None and (owner, token) not in source.unknown:
            source.unknown.add((owner, token))
            LOG.warning('unknown Wakfu text token %s in %s', token, owner)


def _lowercase_first(name):
    return name[:1].lower() + name[1:]


CALL_ALIASES = {'IsBreed': 'critere.casterbreed'}
NEGATED_ALIASES = {'HasEquipmentId': 'critere.nothasequip'}
INVERTED_CALLS = {'HasAnotherSameEquipment': 'critere.hasAnotherSameEquipment'}
COMPARISON_KEYS = {'>': 'critere.sup', '>=': 'critere.supeq', '<': 'critere.inf',
                   '<=': 'critere.infeq'}
JOB_FUNCTIONS = ('GetCraftLevel', 'HasCraft')
ITEM_FUNCTIONS = ('HasEquipmentId',)
BREED_FUNCTIONS = ('IsBreed',)


def _stat_keys(key):
    key = str(key).lower()
    return ['critere.' + key, 'critere.' + key.replace('_', '.')]


def _call_keys(call, negated):
    name = call.name
    if call.name in wakfu_criteria.STAT_FUNCTIONS and call.args:
        return _stat_keys(call.args[0])
    if name in INVERTED_CALLS:
        return [INVERTED_CALLS[name]] if negated else []
    if negated:
        keys = [NEGATED_ALIASES[name]] if name in NEGATED_ALIASES else []
        return keys + ['critere.not' + name, 'critere.not.' + _lowercase_first(name)]
    if name in CALL_ALIASES:
        return [CALL_ALIASES[name]]
    stripped = name[3:] if name.startswith('Get') else name
    return ['critere.' + _lowercase_first(name), 'critere.' + _lowercase_first(stripped)]


def _label_template(source, keys):
    for key in keys:
        text = source.label(key)
        if text is not None:
            return text
    return None


def _resolved_arguments(source, call, extra):
    values = list(call.args) + ([extra] if extra is not None else [])
    resolved = []
    unnamed = False
    for position, value in enumerate(values):
        if position < len(call.args):
            if call.name in JOB_FUNCTIONS:
                name = source.job_name(value)
            elif call.name in ITEM_FUNCTIONS:
                name = source.item_name(value)
            elif call.name in BREED_FUNCTIONS:
                breed = source.conn.execute('SELECT id FROM breeds WHERE name = ?',
                                            (value,)).fetchone()
                name = source.breed_name(breed[0]) if breed else None
            elif call.name in wakfu_criteria.STAT_FUNCTIONS:
                continue
            else:
                name = None
            if name is None and isinstance(value, int):
                unnamed = True
                value = ''
            resolved.append(name if name is not None else value)
        else:
            if isinstance(value, int) and not isinstance(value, bool):
                unnamed = True
                value = ''
            resolved.append(value)
    return resolved, unnamed


def _atom_condition(source, node, negated):
    call, comparison, value = (node.call, node.op, node.value) if isinstance(
        node, wakfu_criteria.Compare) else (node, None, None)
    missing = []
    negated = negated or comparison == '!='
    if negated and comparison in COMPARISON_KEYS:
        raise wakfu_criteria.CriteriaError('a negated ordered comparison')
    keys = _call_keys(call, negated)
    template = _label_template(source, keys)
    if template is None:
        return Condition('', ('label:' + call.name,))
    extra = value if comparison in ('==', '!=') and not call.args else None
    resolved, unnamed = _resolved_arguments(source, call, extra)
    if unnamed:
        missing.append('name:' + call.name)
    text = format_text(template, resolved).rstrip()
    shown = [str(one) for one in resolved if one != '']
    if '[#1]' not in template and shown and call.name not in wakfu_criteria.STAT_FUNCTIONS:
        text = (text + ' ' + ' '.join(shown)).strip()
    if comparison in COMPARISON_KEYS:
        shape = source.label(COMPARISON_KEYS[comparison])
        if shape is None:
            return Condition(text, tuple(missing) + ('label:' + comparison,))
        text = format_text(shape, [text, value])
    elif comparison not in (None, '==', '!='):
        missing.append('label:' + comparison)
    return Condition(html.unescape(text), tuple(missing))


def _node_conditions(source, node, negated=False):
    if isinstance(node, wakfu_criteria.Hidden):
        return []
    if isinstance(node, wakfu_criteria.Const):
        if node.value:
            return []
        template = source.label('critere.false')
        return [Condition(template or '', () if template else ('label:False',))]
    if isinstance(node, wakfu_criteria.Not):
        return _node_conditions(source, node.child, not negated)
    if isinstance(node, wakfu_criteria.And):
        if negated and len(node.children) > 1:
            raise wakfu_criteria.CriteriaError('a negated conjunction')
        return [one for child in node.children
                for one in _node_conditions(source, child, negated)]
    if isinstance(node, wakfu_criteria.Or):
        if negated and len(node.children) > 1:
            raise wakfu_criteria.CriteriaError('a negated disjunction')
        parts = [one for child in node.children
                 for one in _node_conditions(source, child, negated)]
        parts = [one for one in parts if one.text or one.missing]
        if not parts:
            return []
        texts = list(collections.OrderedDict.fromkeys(one.text for one in parts if one.text))
        return [Condition(' / '.join(texts),
                          tuple(collections.OrderedDict.fromkeys(
                              reason for one in parts for reason in one.missing)))]
    if isinstance(node, (wakfu_criteria.Call, wakfu_criteria.Compare)):
        return [_atom_condition(source, node, negated)]
    return [Condition('', ('shape:' + type(node).__name__,))]


def condition_lines(source, criteria):
    """The conditions of a criterion text in the game's wording: a list of Condition."""
    if not criteria or not criteria.strip():
        return []
    return [Condition(localized(one.text, source.language), one.missing)
            for one in _node_conditions(source, wakfu_criteria.parse(criteria))]
