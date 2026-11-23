# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""No runtime code branches on a literal Touch, Retro or Dofus 2 key outside its allowlist."""
import ast
import os
import re
from pathlib import Path

from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[2]
SCANNED_DIRS = ('fashionistapulp/fashionistapulp', 'fashionsite')
SKIPPED_DIRS = {'migrations', 'tests', '__pycache__', 'node_modules'}
SCANNED_SUFFIXES = ('.py', '.html', '.js', '.txt')

KEY = r"""['"](?:touch|retro|dofus2)['"]"""
OPERATOR_FIRST = (
    re.compile(r"(?:[!=]==?|\bis\s+not\b|\bis\b)\s*" + KEY),
    re.compile(r"\b(?:not\s+)?in\s*[\(\[\{][^\)\]\}]*" + KEY),
    re.compile(r"\b(?:startswith|endswith)\(\s*" + KEY),
    re.compile(r"\bcase\s+" + KEY),
    re.compile(r"\b(?:not\s+)?in\s+" + KEY),
)
LITERAL_FIRST = re.compile(KEY + r"\s*(?:[!=]==?|\bis\b)")
SUBSET_KEYS = {'touch', 'retro', 'dofus2'}

MAIN_OPERAND = r"(?:main_game\((?:[^()]|\([^()]*\))*\)|current_main_version|\.pointerType)"
MAIN_BEFORE = re.compile(MAIN_OPERAND + r"\s*$")
MAIN_AFTER = re.compile(r"^\s*(?:not\s+)?" + MAIN_OPERAND)

ALLOWED = {
    ('fashionsite/chardata/image_store.py', "if main == 'retro':"):
        'compares the family main returned by main_of',
    ('fashionsite/chardata/spell_buffs.py', "if game_version == 'retro':"):
        'damage spell data module per key; a beta gets its own generated module',
    ('fashionsite/chardata/spell_buffs.py', "if game_version == 'touch':"):
        'damage spell data module per key; a beta gets its own generated module',
    ('fashionsite/chardata/spell_buffs.py', "if game_version == 'dofus2':"):
        'damage spell data module per key; a beta gets its own generated module',
    ('fashionsite/chardata/forgemagie_odds.py', "return DOCUMENTED_ODDS if ruleset == 'retro' else ()"):
        'a forgemagie ruleset name from forgemagie_data, not a version key',
    ('fashionsite/chardata/spells_view.py', "if game_version in ('retro', 'touch'):"):
        'spell icon folder per key; the family fallback belongs to the icon chain',
    ('fashionsite/chardata/spells_view.py', "elif (game_version in ('beta', 'dofus2')"):
        'spell icon folder per key; the family fallback belongs to the icon chain',
    ('fashionistapulp/fashionistapulp/model.py', "_GATED_CONDITION_VERSIONS = frozenset({'retro'})"):
        'main game keys, tested through main_game (checked below)',
    ('fashionsite/chardata/translation_util.py', 'VERSION_STAT_NAMES = {'):
        'main game keys, tested through main_game (checked below)',
    ('fashionsite/chardata/workshop_sources.py', "NO_LEVEL_VERSIONS = ('retro',)"):
        'main game keys, tested through main_game (checked below)',
    ('fashionsite/chardata/guides_content.py', "'version_groups': {'dofus2': 'dofus2', 'retro': 'retro'},"):
        'per-version guide data read through the family fallback (checked below)',
    ('fashionsite/chardata/guides_content.py', "'version_groups': {'dofus2': 'dofus2', 'touch': 'touch', 'retro': 'retro'},"):
        'per-version guide data read through the family fallback (checked below)',
    ('fashionsite/chardata/guides_content.py', "'version_groups': {'retro': 'retro', 'touch': 'touch'},"):
        'per-version guide data read through the family fallback (checked below)',
    ('fashionsite/chardata/guides_content.py', "'version_groups': {'retro': 'retro'},"):
        'per-version guide data read through the family fallback (checked below)',
    ('fashionsite/chardata/guides_content.py', "'version_groups': {'touch': 'touch', 'retro': 'retro'},"):
        'per-version guide data read through the family fallback (checked below)',
}


MAIN_GAME_CONSTANTS = {
    'fashionistapulp/fashionistapulp/model.py': '_GATED_CONDITION_VERSIONS',
    'fashionsite/chardata/translation_util.py': 'VERSION_STAT_NAMES',
    'fashionsite/chardata/weapon_header.py': '_ELEMENTLESS_HEAL_VERSIONS',
    'fashionsite/chardata/workshop_sources.py': 'NO_LEVEL_VERSIONS',
}


def literal_branches(line):
    """The literal version-key comparisons of a line that do not test the main game."""
    found = []
    for pattern in OPERATOR_FIRST:
        for match in pattern.finditer(line):
            if not MAIN_BEFORE.search(line[:match.start()]):
                found.append(match.group(0))
    for match in LITERAL_FIRST.finditer(line):
        if not MAIN_AFTER.search(line[match.end():]):
            found.append(match.group(0))
    return found


def _is_key(node):
    """True for a string literal naming only a Touch, Retro or Dofus 2 key."""
    return isinstance(node, ast.Constant) and node.value in SUBSET_KEYS


def _is_key_entry(node):
    """A key literal, or a tuple that starts with one."""
    return _is_key(node) or (isinstance(node, ast.Tuple) and bool(node.elts) and _is_key(node.elts[0]))


def _main_operand(node):
    """True for main_game(...) or current_main_version, the operands that name a main game."""
    if isinstance(node, ast.Call):
        return getattr(node.func, 'id', getattr(node.func, 'attr', None)) == 'main_game'
    return isinstance(node, ast.Name) and node.id == 'current_main_version'


def _names(node, name):
    """True when the expression is the constant itself or an attribute of that name."""
    return (isinstance(node, ast.Name) and node.id == name) or (
        isinstance(node, ast.Attribute) and node.attr == name)


def subset_table_lines(tree):
    """Line numbers of literals that hold only Touch, Retro or Dofus 2 keys outside a main-game test."""
    tested = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare) and _main_operand(node.left):
            tested.update(id(comparator) for comparator in node.comparators)
    lines = []
    for node in ast.walk(tree):
        if id(node) in tested:
            continue
        if isinstance(node, (ast.Tuple, ast.Set, ast.List)):
            members = node.elts
        elif isinstance(node, ast.Dict):
            members = node.keys
        else:
            continue
        if members and all(member is not None and _is_key_entry(member) for member in members):
            lines.append(node.lineno)
    return lines


def scanned_files():
    """Every runtime source file of the site and the solver, tests and migrations left out."""
    for base in SCANNED_DIRS:
        for directory, dirs, files in os.walk(ROOT / base):
            dirs[:] = sorted(name for name in dirs if name not in SKIPPED_DIRS)
            for name in sorted(files):
                if name.endswith(SCANNED_SUFFIXES) and not name.startswith(('tests', 'test_')):
                    yield Path(directory) / name


def branch_lines():
    """{(repo path, stripped line): [line numbers]} for every literal branch found."""
    found = {}
    for path in scanned_files():
        try:
            text = path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            continue
        relative = path.relative_to(ROOT).as_posix()
        lines = text.splitlines()
        numbers = {number for number, line in enumerate(lines, 1) if literal_branches(line)}
        if path.suffix == '.py':
            try:
                numbers.update(subset_table_lines(ast.parse(text)))
            except SyntaxError:
                pass
        for number in sorted(numbers):
            found.setdefault((relative, lines[number - 1].strip()), []).append(number)
    return found


class RulesBranchOnTheMainGameNotOnAVersionKey(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.found = branch_lines()

    def test_no_literal_branch_outside_the_allowlist(self):
        unexpected = ['%s:%s  %s' % (path, ','.join(map(str, numbers)), line)
                      for (path, line), numbers in sorted(self.found.items())
                      if (path, line) not in ALLOWED]
        self.assertEqual([], unexpected,
                         "test main_game(key) or current_main_version instead of a literal key")

    def test_every_main_game_constant_is_only_tested_through_main_game(self):
        for relative, name in MAIN_GAME_CONSTANTS.items():
            tree = ast.parse((ROOT / relative).read_text(encoding='utf-8'))
            uses = [node for node in ast.walk(tree) if isinstance(node, ast.Compare)
                    and any(_names(comparator, name) for comparator in node.comparators)]
            with self.subTest(constant=name):
                self.assertTrue(uses)
                for node in uses:
                    self.assertTrue(any(_main_operand(part) for part in ast.walk(node.left)),
                                    "%s:%d tests %s without main_game" % (relative, node.lineno, name))

    def test_every_per_version_table_is_read_through_the_family_fallback(self):
        tables = {
            'fashionsite/chardata/spells_view.py': 'SPELL_ICON_LANGUAGE',
            'fashionsite/chardata/spell_combo.py': 'ONLY_HITS_A_SUMMON',
        }
        for relative, name in tables.items():
            tree = ast.parse((ROOT / relative).read_text(encoding='utf-8'))
            reads = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                     and isinstance(node.func, ast.Attribute) and node.func.attr == 'get'
                     and _names(node.func.value, name)]
            with self.subTest(table=name):
                self.assertTrue(reads)
                for node in reads:
                    self.assertTrue(any(_main_operand(part) for part in ast.walk(node)),
                                    "%s:%d reads %s without main_game" % (relative, node.lineno, name))
        guides = ast.parse((ROOT / 'fashionsite/chardata/guides_content.py').read_text(encoding='utf-8'))
        lookup = [node for node in ast.walk(guides) if isinstance(node, ast.FunctionDef)
                  and node.name == '_guide_group']
        self.assertEqual(1, len(lookup))
        self.assertTrue(any(_main_operand(part) for part in ast.walk(lookup[0])))

    def test_every_allowlist_entry_still_exists(self):
        stale = [entry for entry in ALLOWED if entry not in self.found]
        self.assertEqual([], stale)

    def test_the_scan_reads_the_solver_the_views_and_the_templates(self):
        scanned = {path.relative_to(ROOT).as_posix() for path in scanned_files()}
        for expected in ('fashionistapulp/fashionistapulp/dofus_constants.py',
                         'fashionsite/chardata/spells_view.py',
                         'fashionsite/chardata/templates/chardata/solution.html',
                         'fashionsite/chardata/static/chardata/admin_tools.js'):
            self.assertIn(expected, scanned)
        self.assertFalse(any('/migrations/' in path or Path(path).name.startswith('tests')
                             for path in scanned))

    def test_the_patterns_catch_every_form_of_a_literal_branch(self):
        for line in ("if game_version == 'touch':",
                     'if game_version != "retro":',
                     "{% if current_game_version == 'dofus2' %}",
                     "{% elif current_game_version != 'retro' and x %}",
                     "if gv in ('beta', 'dofus2'):",
                     "if gv not in ['retro']:",
                     "if gv.startswith('retro'):",
                     "if 'touch' == gv:",
                     "case 'retro':",
                     "if (version === 'touch') {",
                     "if version is 'retro':",
                     "modern = main_game(gv) != 'beta' and gv == 'retro'",
                     "if gv not in 'retro':"):
            with self.subTest(line=line):
                self.assertTrue(literal_branches(line))

    def test_the_patterns_let_the_main_game_and_plain_data_through(self):
        for line in ("if main_game(game_version) == 'touch':",
                     "if main_game(getattr(s, 'game_version', 'dofus3')) in ('retro', 'touch'):",
                     "{% if current_main_version != 'retro' and current_main_version != 'touch' %}",
                     "if (ev.pointerType === 'touch') { pointAt(ev); }",
                     "if game_version == 'beta':",
                     "'dofus2': 'Dofus',",
                     "reference = get_spell_reference('dofus2')",
                     "_ELEMENTLESS_HEAL_VERSIONS = {'retro', 'touch'}",
                     "if 'touch' == main_game(gv):"):
            with self.subTest(line=line):
                self.assertEqual([], literal_branches(line))

    def test_a_key_held_in_a_constant_is_found(self):
        for source in ("OLD = ('touch', 'retro')",
                       "OLD = frozenset({'retro'})",
                       "BY_KEY = {'retro': False}",
                       "x = {'retro': False}.get(game_version, True)",
                       "PAIRS = {('retro', 'Power'), ('retro', 'Trap')}",
                       "if game_version not in OLD:\n    pass\nOLD = ['dofus2']"):
            with self.subTest(source=source):
                self.assertTrue(subset_table_lines(ast.parse(source)))

    def test_a_table_that_names_every_version_or_a_main_game_test_is_not_a_subset(self):
        for source in ("ALL = ('dofus3', 'beta', 'touch', 'retro')",
                       "BY_KEY = {'dofus3': 1, 'retro': 2}",
                       "if main_game(gv) in ('retro', 'touch'):\n    pass",
                       "if current_main_version in ['retro']:\n    pass",
                       "NAMES = ('Power', 'retro')"):
            with self.subTest(source=source):
                self.assertEqual([], subset_table_lines(ast.parse(source)))
