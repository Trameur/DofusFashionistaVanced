# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The modern skin is written once, in modern.css; the sheets a page links are cut from it here."""
import io
import os
import re

STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'chardata')
SOURCE = 'modern.css'
SHEETS = {
    'shell': 'modern-core.css',
    'solution': 'modern-solution.css',
    'encyclopedia': 'modern-encyclopedia.css',
    'rest': 'modern-rest.css',
}
HEADER = '/* ---------- '
FIRST_PAGE_SECTION = 'Solution stats panel'
END_OF_SOLUTION = 'Content, account, error and tool pages'
FIRST_ENCYCLOPEDIA_SECTION = 'Encyclopedia: index, item and set pages'
END_OF_ENCYCLOPEDIA = 'Tools: workshop and inventory'
SHELL_SECTION = 'Comparison cart, own colours for every theme'
BEGIN = '/* shell: begin */'
MARKED = re.compile(r'/\* shell: begin \*/\n(.*?)/\* shell: end \*/\n', re.S)


def _at(lines, title):
    for number, line in enumerate(lines):
        if line.startswith(HEADER + title):
            return number
    raise ValueError('no section called %r' % title)


def _next_header(lines, number):
    for after in range(number + 1, len(lines)):
        if lines[after].startswith(HEADER):
            return after
    return len(lines)


def _strip(text):
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
    return '\n'.join(line.rstrip() for line in text.split('\n') if line.strip()) + '\n'


def build_sheets(source):
    """The four sheets as {name: text}, comments and blank lines stripped.

    The shell holds everything before the first page section, the cart section and the blocks marked
    shell: begin and shell: end, so every rule classic needs is in it. A page links the shell and the
    sheet of its kind; a page that names none gets the rest sheet, which holds every later section.
    """
    lines = source.split('\n')
    first_page = _at(lines, FIRST_PAGE_SECTION)
    cart = _at(lines, SHELL_SECTION)
    later = '\n'.join(lines[first_page:])
    marked = MARKED.findall(later)
    if BEGIN in '\n'.join(lines[:first_page]) or later.count(BEGIN) != len(marked):
        raise ValueError('a shell marker is unpaired or sits before the first page section')
    shell = '\n'.join(lines[:first_page] + lines[cart:_next_header(lines, cart)]) + '\n' + ''.join(marked)
    encyclopedia = lines[_at(lines, FIRST_ENCYCLOPEDIA_SECTION):_at(lines, END_OF_ENCYCLOPEDIA)]
    return {
        'shell': _strip(shell),
        'solution': _strip('\n'.join(lines[first_page:_at(lines, END_OF_SOLUTION)])),
        'encyclopedia': _strip('\n'.join(encyclopedia)),
        'rest': _strip(later),
    }


def read_source():
    with io.open(os.path.join(STATIC, SOURCE), encoding='utf-8') as handle:
        return handle.read()
