# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.

"""The Wakfu modules do not read the tables of Dofus."""
import ast
from pathlib import Path

from django.test import SimpleTestCase

FORBIDDEN_MODULES = {'presets', 'smart_build', 'crit_curve', 'forgemagie_data', 'exo_options',
                     'weapon_forge', 'temporix', 'model'}
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
FOLDERS = (ROOT / 'fashionistapulp' / 'fashionistapulp', HERE)


def _forbidden(name):
    last = name.split('.')[-1]
    return last.startswith('dofus_') or last in FORBIDDEN_MODULES


def _wakfu_files():
    return sorted(path for folder in FOLDERS for path in folder.glob('wakfu_*.py'))


def _offending_names(tree):
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend(alias.name for alias in node.names if _forbidden(alias.name))
        elif isinstance(node, ast.ImportFrom):
            if node.module and _forbidden(node.module):
                found.append(node.module)
            found.extend(alias.name for alias in node.names if _forbidden(alias.name))
    return found


class NoWakfuModuleImportsADofusTableTests(SimpleTestCase):
    def test_no_wakfu_module_imports_a_dofus_table(self):
        files = _wakfu_files()
        print('wakfu modules parsed:', len(files))
        self.assertGreaterEqual(len(files), 10)
        offences = {}
        for path in files:
            names = _offending_names(ast.parse(path.read_text(encoding='utf-8')))
            if names:
                offences[path.name] = names
        self.assertEqual({}, offences)

    def test_the_check_names_a_dofus_table_import(self):
        for source in ('from fashionistapulp import dofus_constants',
                       'from fashionistapulp.dofus_constants import CHARACTER_CLASSES',
                       'from .presets import version_presets',
                       'import chardata.smart_build'):
            self.assertTrue(_offending_names(ast.parse(source)), source)
