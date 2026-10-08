# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Item effect texts held against the effects they describe."""

import io
import json
import os
import re

AGREEMENT = re.compile(r'\{\{?~([^{}]*?)\}\}?')
OPTIONAL = re.compile(r'\{\{?~1~2(.*?)\}\}?')
TOKEN = re.compile(r'(#\d|\{\{?~[^{}]*?\}\}?)')
SPELL_LINK = re.compile(r'\{\{spell,(\d+),\d+::')
MARKUP = re.compile(r'\{\{.*?\}\}')
LETTER = re.compile(r'[^\W\d_]')
INTEGER = re.compile(r'[+-]?\d+')


def agree(text, plural):
    """Resolve the agreement markers, keeping the form the count calls for."""
    def one(match):
        parts = [part for part in match.group(1).split('~') if part]
        slots = [(part[0], part[1:]) for part in parts]
        for index, (letter, payload) in enumerate(slots):
            if payload:
                continue
            inherited = next((later for _slot, later in slots[index + 1:]
                              if later), '')
            slots[index] = (letter, inherited)
        for letter, payload in slots:
            if letter == 'p':
                return payload if plural else ''
            if letter == 's':
                return '' if plural else payload
        return ''
    return AGREEMENT.sub(one, text)


def linked_spells(texts):
    return {int(spell) for text in texts if text
            for spell in SPELL_LINK.findall(text)}


class Unreadable(ValueError):
    pass


def _read(path):
    try:
        with io.open(path, encoding='utf-8') as handle:
            return json.load(handle)
    except (OSError, ValueError) as exc:
        raise Unreadable('%s (%s)' % (os.path.basename(path), exc)) from exc


def _records(data):
    """{id: record} and the shared references, from a datacenter table or a plain list."""
    if isinstance(data, list):
        return {row['id']: row for row in data
                if isinstance(row, dict) and 'id' in row}, {}
    refs = {ref['rid']: ref['data'] for ref in data['references']['RefIds']}
    keys = data['objectsById']['m_keys']['Array']
    values = data['objectsById']['m_values']['Array']
    return {key: refs[value['rid']] for key, value in zip(keys, values)
            if value['rid'] in refs}, refs


def _array(value, refs):
    rows = value.get('Array', []) if isinstance(value, dict) else (value or [])
    return [refs.get(row['rid'], {}) if isinstance(row, dict) and set(row) == {'rid'}
            else row for row in rows]


def _effect_id(effect):
    return effect.get('actionId', effect.get('effectId'))


def _literal(text):
    words = [re.escape(word) for word in text.split()]
    if not words:
        return r'\s+' if text else ''
    lead = r'\s+' if text[0].isspace() else ''
    trail = r'\s+' if text[-1].isspace() else ''
    return lead + r'\s+'.join(words) + trail


def mention_pattern(template):
    """A number followed by the words the effect's template writes after it."""
    if not template or '#1' not in template:
        return None
    tail = OPTIONAL.sub('', template.split('#1', 1)[1]).replace('#2', '', 1)
    tail = re.split(r'#\d|\{\{(?!~)', tail)[0].rstrip()
    pieces = AGREEMENT.split(tail)
    literals = pieces[0::2]
    if not LETTER.search(''.join(literals)):
        return None
    body = ''.join(_literal(piece) if index % 2 == 0 else r'[^\W\d_]*'
                   for index, piece in enumerate(pieces))
    return re.compile(r'(?<![\d.,])(\d+)' + body, re.IGNORECASE)


def _mentions(pattern, line):
    markup = [match.span() for match in MARKUP.finditer(line)]
    return [(match.start(1), match.end(1), int(match.group(1)))
            for match in pattern.finditer(line)
            if not any(start < match.end() and match.start() < end
                       for start, end in markup)]


def agreement_pattern(template):
    """The template as a regex whose agreement markers are groups, or None."""
    if not template or OPTIONAL.search(template) or not AGREEMENT.search(template):
        return None
    if re.search(r'\{\{(?!~)', template):
        return None
    tokens = TOKEN.split(template)
    if not any(token.startswith('#') for token in tokens[1::2]):
        return None
    if not LETTER.search(''.join(tokens[0::2])):
        return None
    parts, markers, seen = [], [], set()
    for index, token in enumerate(tokens):
        if index % 2 == 0:
            parts.append(_literal(token))
        elif token.startswith('#'):
            name = 'p' + token[1:]
            parts.append('(?P=%s)' % name if name in seen else '(?P<%s>.+?)' % name)
            seen.add(name)
        else:
            forms = sorted({agree(token, True), agree(token, False)},
                           key=len, reverse=True)
            name = 'm%d' % len(markers)
            markers.append((name, token))
            parts.append('(?P<%s>%s)' % (name, '|'.join(re.escape(form) for form in forms)))
    return re.compile(''.join(parts)), markers


class EffectTexts:

    def __init__(self, templates, numbers):
        self.templates = templates
        self.numbers = numbers
        self._agreements = {}

    def rebuild_numbers(self, texts):
        """{language: text} with each number a language contradicts rebuilt from its effect."""
        carried = {}
        for spell in linked_spells(texts.values()):
            for effect, numbers in self.numbers.get(spell, {}).items():
                carried.setdefault(effect, set()).update(numbers)
        lines = {language: text.split('\n') for language, text in texts.items() if text}
        if not carried or len({len(rows) for rows in lines.values()}) != 1:
            return dict(texts)
        count = len(next(iter(lines.values())))
        for effect in sorted(carried):
            numbers = carried[effect]
            patterns = {language: mention_pattern(self.templates.get(language, {}).get(effect))
                        for language in lines}
            for index in range(count):
                found = {language: _mentions(pattern, lines[language][index])
                         for language, pattern in patterns.items() if pattern}
                agreeing = {(len(hits), hits[0][2]) for hits in found.values()
                            if hits and {n for _s, _e, n in hits} == {hits[0][2]}
                            and hits[0][2] in numbers}
                if len(agreeing) != 1:
                    continue
                size, number = agreeing.pop()
                for language, hits in found.items():
                    wrong = [hit for hit in hits if hit[2] not in numbers]
                    if len(hits) != size or not wrong or len(wrong) != len(hits):
                        continue
                    line = lines[language][index]
                    for start, end, _n in reversed(wrong):
                        line = line[:start] + str(number) + line[end:]
                    lines[language][index] = line
        out = dict(texts)
        out.update({language: '\n'.join(rows) for language, rows in lines.items()})
        return out

    def _agreement_patterns(self, language):
        if language not in self._agreements:
            patterns = {}
            for template in self.templates.get(language, {}).values():
                if template not in patterns:
                    patterns[template] = agreement_pattern(template)
            self._agreements[language] = [pattern for pattern in patterns.values() if pattern]
        return self._agreements[language]

    def agree_with_count(self, line, language):
        """The line with its agreement markers in the form its number calls for."""
        rebuilt = set()
        for pattern, markers in self._agreement_patterns(language):
            match = pattern.fullmatch(line)
            if match is None:
                continue
            numbers = [int(value) for name, value in match.groupdict().items()
                       if name.startswith('p') and value and INTEGER.fullmatch(value)]
            plural = any(abs(number) > 1 for number in numbers)
            text = line
            for name, token in reversed(markers):
                start, end = match.span(name)
                text = text[:start] + agree(token, plural) + text[end:]
            rebuilt.add(text)
        return rebuilt.pop() if len(rebuilt) == 1 else line


def load(raw_dir, languages, spell_ids=()):
    """The effect templates and the numbers of the linked spells, or None and the files missing or unreadable."""
    names = ['effects.json', 'spells.json', 'spell_levels.json'] + [
        '%s.json' % language for language in languages]
    missing = [name for name in names if not os.path.isfile(os.path.join(raw_dir, name))]
    if missing:
        return None, missing
    try:
        return _build(raw_dir, languages, spell_ids), []
    except Unreadable as exc:
        return None, [str(exc)]


def _build(raw_dir, languages, spell_ids):
    effects, _ = _records(_read(os.path.join(raw_dir, 'effects.json')))
    descriptions = {int(effect_id): str(effect.get('descriptionId'))
                    for effect_id, effect in effects.items()
                    if effect.get('descriptionId') is not None}
    templates = {}
    for language in languages:
        texts = _read(os.path.join(raw_dir, '%s.json' % language))
        texts = texts.get('entries') or texts.get('texts') or {}
        templates[language] = {effect_id: texts[key] for effect_id, key in descriptions.items()
                               if texts.get(key)}
        del texts
    wanted = {int(spell) for spell in spell_ids}
    spells, refs = _records(_read(os.path.join(raw_dir, 'spells.json')))
    level_spell = {}
    for spell_id, spell in spells.items():
        if int(spell_id) in wanted:
            for level in _array(spell.get('spellLevels'), refs):
                level_spell[level] = int(spell_id)
    del spells, refs
    levels, refs = _records(_read(os.path.join(raw_dir, 'spell_levels.json')))
    numbers = {}
    for level_id, spell_id in level_spell.items():
        level = levels.get(level_id)
        if level is None:
            continue
        for effect in _array(level.get('effects'), refs):
            effect_id = _effect_id(effect)
            if effect_id is None:
                continue
            found = numbers.setdefault(spell_id, {}).setdefault(int(effect_id), set())
            found.update(abs(int(effect.get(key) or 0)) for key in ('diceNum', 'diceSide', 'value')
                         if effect.get(key))
    return EffectTexts(templates, numbers)
