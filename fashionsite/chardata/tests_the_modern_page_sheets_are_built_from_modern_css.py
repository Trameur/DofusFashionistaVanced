# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The modern skin is written once in modern.css and cut into a shell and three page sheets: the committed sheets are what the builder makes of it, each keeps the source order, every rule classic needs is in the shell, each page links the sheets it needs, and no page drops a sheet whose rules it uses."""
import io
import os
import re

from django.test import SimpleTestCase, TestCase

from chardata.modern_sheets import SHEETS, STATIC, build_sheets, read_source

TEMPLATES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
LINK = 'href="/static/chardata/%s"'

# Words that are styled only in a sheet the page skips, and sit in the page for another reason.
FROZEN = {
    'register': 'only .setup-atelier .register is styled; base.html says serviceWorker.register',
    'build-boxes-tip': 'styled only under .setup-atelier; base.html names it inside a script',
    'selected': 'only .compare-build-choice-card.selected is styled',
    'blanket': 'a variable name in blanket.js; these pages use #blanket-language and #blanket-theme',
    'popUpDiv': 'a variable name in blanket.js; these pages use #blanket-language and #blanket-theme',
    'proj_info': 'main-header.html renders it only with a build in context, never on these pages',
    'proj-info-side': 'main-header.html renders it only with a build in context, never on these pages',
    'proj-info-main': 'main-header.html renders it only with a build in context, never on these pages',
    'loading-progress-label': 'loading.html is included only when char_id is not 0',
    'tailoring': 'loading.html is included only when char_id is not 0',
}


def read_sheet(key):
    with io.open(os.path.join(STATIC, SHEETS[key]), encoding='utf-8') as handle:
        return handle.read()


def strip_comments(css):
    return re.sub(r'/\*.*?\*/', '', css, flags=re.S)


def rules(css):
    """The top-level rules of a stylesheet, whitespace collapsed."""
    found, depth, start = [], 0, 0
    css = strip_comments(css)
    for position, char in enumerate(css):
        if char == '{':
            depth += 1
        elif char == '}':
            depth -= 1
            if depth == 0:
                found.append(re.sub(r'\s+', ' ', css[start:position + 1]).strip())
                start = position + 1
    return found


def selectors_of(rule):
    """Every selector of a rule, looking inside @media and @supports, skipping @font-face and @keyframes."""
    head, _, body = rule.partition('{')
    head = head.strip()
    if head.startswith(('@media', '@supports')):
        return [selector for inner in rules(body[:body.rindex('}')]) for selector in selectors_of(inner)]
    if head.startswith('@'):
        return []
    return [selector.strip() for selector in head.split(',')]


def tokens(css):
    found = set()
    for head in re.findall(r'([^{}]+)\{', strip_comments(css)):
        if head.strip().startswith('@'):
            continue
        found |= {match.group(2) for match in re.finditer(r'([.#])(-?[A-Za-z_][\w-]*)', head)}
    return found


def closure(name, seen, scripts):
    path = os.path.join(TEMPLATES, name)
    if name in seen or not os.path.exists(path):
        return
    seen.add(name)
    with io.open(path, encoding='utf-8', errors='ignore') as handle:
        source = handle.read()
    scripts.update(re.findall(r'{%\s*static\s+["\']([^"\']+\.js)["\']', source))
    for found in re.findall(r'{%\s*(?:include|extends)\s+["\']([^"\']+)["\']', source):
        closure(found, seen, scripts)


def words_of_page(name):
    seen, scripts = set(), set()
    closure(name, seen, scripts)
    found = set()
    for template in seen:
        with io.open(os.path.join(TEMPLATES, template), encoding='utf-8', errors='ignore') as handle:
            found |= set(re.findall(r'[A-Za-z_][\w-]*', handle.read()))
    for script in scripts:
        path = os.path.join(STATIC, script)
        if os.path.exists(path) and not script.endswith('.min.js'):
            with io.open(path, encoding='utf-8', errors='ignore') as handle:
                found |= set(re.findall(r'[A-Za-z_][\w-]*', handle.read()))
    return found


class TheSheetsAreCutFromOneSourceTests(SimpleTestCase):

    def test_the_committed_sheets_are_what_the_builder_makes_of_modern_css(self):
        built = build_sheets(read_source())
        for key in SHEETS:
            with self.subTest(sheet=SHEETS[key]):
                self.assertEqual(built[key], read_sheet(key), 'run manage.py build_modern_sheets')

    def test_each_sheet_keeps_the_source_order_of_its_rules(self):
        source = rules(read_source())
        for key in SHEETS:
            with self.subTest(sheet=SHEETS[key]):
                position = 0
                for rule in rules(read_sheet(key)):
                    try:
                        position = source.index(rule, position) + 1
                    except ValueError:
                        self.fail('%s: rule out of order or not in modern.css: %s' % (SHEETS[key], rule[:90]))

    def test_every_rule_classic_sees_is_in_the_shell(self):
        shell = set(rules(read_sheet('shell')))
        missing = []
        for rule in rules(read_source()):
            if any(not selector.startswith('html.fm-modern') for selector in selectors_of(rule)):
                if rule not in shell:
                    missing.append(rule[:90])
        self.assertEqual([], missing)

    def test_the_sheets_carry_no_comment(self):
        for key in SHEETS:
            with self.subTest(sheet=SHEETS[key]):
                self.assertNotIn('/*', read_sheet(key))

    def test_the_shell_markers_come_in_pairs_after_the_first_page_section(self):
        source = read_source()
        self.assertEqual(3, source.count('/* shell: begin */'))
        self.assertEqual(3, source.count('/* shell: end */'))


class EveryPageLinksTheSheetsItNeedsTests(TestCase):

    def links(self, path):
        html = self.client.get(path).content.decode()
        return [name for name in SHEETS.values() if LINK % name in html]

    def test_home_links_the_shell_only(self):
        self.assertEqual(['modern-core.css'], self.links('/'))

    def test_the_encyclopedia_links_the_shell_and_its_sheet(self):
        self.assertEqual(['modern-core.css', 'modern-encyclopedia.css'], self.links('/encyclopedia/'))

    def test_a_page_that_names_no_sheet_gets_the_rest(self):
        self.assertEqual(['modern-core.css', 'modern-rest.css'], self.links('/faq/'))

    def test_the_solution_page_links_the_shell_and_the_solution_sheet(self):
        with io.open(os.path.join(TEMPLATES, 'chardata', 'solution.html'), encoding='utf-8') as handle:
            source = handle.read()
        self.assertIn('{% block modern_page_css %}<link rel="stylesheet" type="text/css" href="{% static "chardata/modern-solution.css" %}">{% endblock %}', source)

    def test_every_encyclopedia_template_links_the_encyclopedia_sheet(self):
        names = sorted(name for name in os.listdir(os.path.join(TEMPLATES, 'chardata')) if re.match(r'encyclopedia[\w]*\.html$', name))
        self.assertEqual(9, len(names))
        for name in names:
            with self.subTest(template=name):
                with io.open(os.path.join(TEMPLATES, 'chardata', name), encoding='utf-8') as handle:
                    source = handle.read()
                self.assertIn('{% block modern_page_css %}<link rel="stylesheet" type="text/css" href="{% static "chardata/modern-encyclopedia.css" %}">{% endblock %}', source)


class ASkippedSheetStylesNothingThePageUsesTests(SimpleTestCase):

    def test_a_page_without_the_rest_sheet_uses_no_class_only_the_skipped_sheets_style(self):
        shell = tokens(read_sheet('shell'))
        rest = tokens(read_sheet('rest'))
        pages = [('home.html', shell), ('solution.html', shell | tokens(read_sheet('solution')))]
        pages += [(name, shell | tokens(read_sheet('encyclopedia')))
                  for name in sorted(os.listdir(os.path.join(TEMPLATES, 'chardata')))
                  if re.match(r'encyclopedia[\w]*\.html$', name)]
        for name, loaded in pages:
            with self.subTest(template=name):
                dropped = (rest - loaded) & words_of_page('chardata/' + name)
                self.assertEqual([], sorted(dropped - set(FROZEN)))
