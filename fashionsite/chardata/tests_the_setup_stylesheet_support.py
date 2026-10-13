# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Reads the static stylesheets as rule lists, so a test can ask which declaration a selector gets under a media query and what a colour token comes to."""
import io
import os
import re

STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'chardata')


def read_css(name):
    with io.open(os.path.join(STATIC, name), encoding='utf-8') as handle:
        return re.sub(r'/\*.*?\*/', '', handle.read(), flags=re.S)


def _declarations(body):
    found = {}
    for piece in body.split(';'):
        if ':' not in piece:
            continue
        prop, value = piece.split(':', 1)
        value = ' '.join(value.split())
        important = value.endswith('!important')
        if important:
            value = value[:-len('!important')].strip()
        found[prop.strip()] = (value, important)
    return found


def parse(source, media=None):
    rules = []
    position = 0
    while True:
        opening = source.find('{', position)
        if opening == -1:
            return rules
        prelude = source[position:opening].strip()
        depth = 1
        index = opening + 1
        while depth:
            if source[index] == '{':
                depth += 1
            elif source[index] == '}':
                depth -= 1
            index += 1
        body = source[opening + 1:index - 1]
        position = index
        if prelude.startswith('@media'):
            rules.extend(parse(body, ' '.join(prelude[len('@media'):].split())))
        elif not prelude.startswith('@'):
            rules.append({'media': media,
                          'selectors': [' '.join(piece.split()) for piece in prelude.split(',')],
                          'declarations': _declarations(body)})


def stylesheet(name):
    return parse(read_css(name))


SHEET_NAMES = ('common.css', 'forms.css', 'setup.css', 'responsive.css', 'modern.css')
DESIGNS = {'classic dark': ('fm-dark',), 'classic light': ('fm-light',), 'modern light': ('fm-modern', 'fm-light'),
           'modern dark': ('fm-modern', 'fm-dark')}


def setup_sheets():
    """The stylesheets that style a /setup/ page and set the properties the tests ask about, in the order the page loads them."""
    return [(name, stylesheet(name)) for name in SHEET_NAMES]


def matching(rules, selector, media=None):
    return [rule for rule in rules if rule['media'] == media and selector in rule['selectors']]


def declared(rules, selector, prop, media=None):
    found = [rule['declarations'][prop] for rule in matching(rules, selector, media)
             if prop in rule['declarations']]
    return found[-1] if found else None


def rule_order(rules, selector, media=None):
    return [index for index, rule in enumerate(rules)
            if rule['media'] == media and selector in rule['selectors']]


PART = re.compile(r"""(?P<tag>[a-zA-Z][\w-]*|\*)|#(?P<id>[\w-]+)|\.(?P<class>[\w-]+)|\[(?P<attr>[^\]]+)\]"""
                  r"""|:not\((?P<not>[^)]*)\)|(?P<pseudo>::?[\w-]+(?:\([^)]*\))?)""")
WIDTH = re.compile(r'(min|max)-width:\s*(\d+)px')


def _parts(compound):
    found = {'tag': None, 'ids': [], 'classes': [], 'attrs': [], 'nots': [], 'pseudos': []}
    at = 0
    while at < len(compound):
        match = PART.match(compound, at)
        if match is None:
            raise ValueError('unreadable selector part %r' % compound[at:])
        at = match.end()
        if match.group('tag'):
            found['tag'] = match.group('tag')
        elif match.group('id'):
            found['ids'].append(match.group('id'))
        elif match.group('class'):
            found['classes'].append(match.group('class'))
        elif match.group('attr'):
            found['attrs'].append(match.group('attr'))
        elif match.group('not') is not None:
            found['nots'].append(match.group('not').strip())
        else:
            found['pseudos'].append(match.group('pseudo'))
    return found


def _split(selector):
    compounds, joints = [], []
    current, depth, pending = '', 0, None
    for char in selector.strip():
        if char in '[(':
            depth += 1
        elif char in '])':
            depth -= 1
        if depth == 0 and (char.isspace() or char == '>'):
            if current:
                compounds.append(current)
                current, pending = '', ' '
            if char == '>':
                pending = '>'
            continue
        if pending is not None:
            joints.append(pending)
            pending = None
        current += char
    compounds.append(current)
    return compounds, joints


def specificity(selector):
    ids = classes = elements = 0
    for compound in _split(selector)[0]:
        parts = _parts(compound)
        ids += len(parts['ids'])
        classes += len(parts['classes']) + len(parts['attrs'])
        elements += 1 if parts['tag'] not in (None, '*') else 0
        for pseudo in parts['pseudos']:
            if pseudo.startswith('::'):
                elements += 1
            else:
                classes += 1
        for negated in parts['nots']:
            inner = specificity(negated)
            ids, classes, elements = ids + inner[0], classes + inner[1], elements + inner[2]
    return ids, classes, elements


def node(tag, classes=(), element_id=None, **attrs):
    return {'tag': tag, 'id': element_id, 'classes': set(classes), 'attrs': attrs}


def chain_of(ancestors, tag, attrs, html_classes):
    """The element and its ancestors as match nodes; the html node carries the design and theme classes of the visitor."""
    chain = []
    for name, own in tuple(ancestors) + ((tag, attrs),):
        classes = html_classes if name == 'html' else (own.get('class') or '').split()
        chain.append(node(name, classes, own.get('id'), **{key: value for key, value in own.items()
                                                           if key not in ('class', 'id')}))
    return chain


def _fits_node(compound, element):
    try:
        parts = _parts(compound)
    except ValueError:
        return False
    if parts['pseudos']:
        return False
    if parts['tag'] not in (None, '*') and parts['tag'] != element['tag']:
        return False
    if any(element['id'] != wanted for wanted in parts['ids']):
        return False
    if not set(parts['classes']) <= element['classes']:
        return False
    for attr in parts['attrs']:
        name, _, value = attr.partition('=')
        if name.endswith(('*', '^', '$', '~', '|')):
            return False
        if name not in element['attrs'] or (value and element['attrs'][name] != value.strip('"\'')):
            return False
    return not any(_fits_node(negated, element) for negated in parts['nots'])


def _fits(compounds, joints, chain, at):
    if not _fits_node(compounds[-1], chain[at]):
        return False
    if len(compounds) == 1:
        return True
    if joints[-1] == '>':
        return at > 0 and _fits(compounds[:-1], joints[:-1], chain, at - 1)
    return any(_fits(compounds[:-1], joints[:-1], chain, before) for before in range(at))


def selector_matches(selector, chain):
    compounds, joints = _split(selector)
    return _fits(compounds, joints, chain, len(chain) - 1)


def media_applies(media, width):
    if media is None:
        return True
    conditions = re.findall(r'\(([^)]*)\)', media)
    if not conditions:
        return False
    for condition in conditions:
        found = WIDTH.fullmatch(condition.strip())
        if found is None:
            return False
        limit = int(found.group(2))
        if (found.group(1) == 'min' and width < limit) or (found.group(1) == 'max' and width > limit):
            return False
    return True


def winning(sheets, chain, prop, width):
    """(value, sheet name, selector) the cascade gives the last node of the chain at a viewport width, or None: importance, then specificity, then load order."""
    best = None
    for order, (name, rules) in enumerate(sheets):
        for index, rule in enumerate(rules):
            if prop not in rule['declarations'] or not media_applies(rule['media'], width):
                continue
            value, important = rule['declarations'][prop]
            for selector in rule['selectors']:
                if selector_matches(selector, chain):
                    key = (important, specificity(selector), order, index)
                    if best is None or key > best[0]:
                        best = (key, value, name, selector)
    return None if best is None else best[1:]


def rgb(colour):
    colour = colour.strip().lower()
    if colour.startswith('#'):
        digits = colour[1:]
        if len(digits) == 3:
            digits = ''.join(char * 2 for char in digits)
        return tuple(int(digits[index:index + 2], 16) for index in (0, 2, 4)), 1.0
    match = re.fullmatch(r'rgba?\(([^)]*)\)', colour)
    parts = [part.strip() for part in match.group(1).split(',')]
    alpha = float(parts[3]) if len(parts) == 4 else 1.0
    return tuple(int(float(part)) for part in parts[:3]), alpha


def flatten(colour, backdrop):
    (red, green, blue), alpha = rgb(colour)
    under, _ = rgb(backdrop)
    return tuple(alpha * top + (1 - alpha) * low for top, low in zip((red, green, blue), under))


def luminance(channels):
    def linear(value):
        value = value / 255.0
        return value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4
    red, green, blue = (linear(value) for value in channels)
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast(first, second):
    high, low = sorted((luminance(first), luminance(second)), reverse=True)
    return (high + 0.05) / (low + 0.05)
