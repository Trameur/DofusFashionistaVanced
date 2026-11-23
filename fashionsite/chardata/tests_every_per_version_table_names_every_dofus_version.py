# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Every hand-written table keyed by game version names every Dofus version, so a new key never falls back silently."""
import ast
import importlib
import os
from unittest import mock

from django.test import SimpleTestCase

import chardata
import fashionistapulp
from fashionistapulp import game_versions
from fashionistapulp.game_versions import GameVersion, dofus_versions

STAGED = 'stagedbeta'

KEYED_TABLES = (
    ('chardata.version_compat', 'CLASSES_NOT_IN_VERSION'),
    ('chardata.version_compat', 'CLASSES_AWAITING_DATA'),
    ('chardata.lock_forbid', 'DEFAULT_EXCLUSION_ANKAMA_IDS_BY_VERSION'),
    ('chardata.smart_build', 'RACE_PROFILE_OVERRIDES_BY_VERSION'),
    ('chardata.smart_build', 'VERSION_WEIGHT_TUNING'),
    ('chardata.presets', 'VERSION_PRESETS'),
    ('chardata.encyclopedia_view', 'PET_VARIANT_ID_BASE_BY_VERSION'),
    ('chardata.encyclopedia_view', '_MONSTER_IMAGE_DIRS'),
    ('chardata.encyclopedia_view', '_INGREDIENT_ICON_DIRS'),
    ('fashionistapulp.structure', 'PET_VARIANT_ID_BASE'),
    ('fashionistapulp.structure', 'GELANO_DEPLOYED_IDS'),
    ('chardata.fashionista_build', 'EXAMPLES'),
    ('chardata.spell_combo', 'ONLY_HITS_A_SUMMON'),
    ('chardata.spell_combo', 'PUSH_ENDS_THE_LATE_ROWS'),
    ('chardata.spells_view', 'SPELL_ICON_LANGUAGE'),
    ('chardata.management.commands.store_default_elements', 'KNOWN_BAD_ROWS'),
    ('chardata.guides_content', '_FRENCH_VERSION_NAME'),
    ('chardata.character_look', 'HAS_ART_BY_VERSION'),
    ('chardata.pushback', 'PUBLISHED_FORMULA_BY_VERSION'),
    ('chardata.weapon_header', '_ELEMENTLESS_HEAL_BY_VERSION'),
    ('chardata.admin_tools_view', 'VERSION_COLOURS'),
    ('chardata.compare_sets_view', 'VERSION_WEIGHT_TUNING'),
    ('chardata.forgemagie_data', '_RULESET_BY_VERSION'),
    ('chardata.item_exchange', '_NO_BASE_NO_CRIT_VERSIONS'),
    ('chardata.item_exchange', '_CRIT_ODDS_RATING_BY_VERSION'),
    ('chardata.weapon_header', '_ZERO_CRIT_HIDDEN_BY_VERSION'),
    ('chardata.admin_history', 'LIVE_VERSIONS'),
)

REGISTRY_TABLES = (
    ('chardata.admin_stats', 'VERSION_LABELS'),
    ('chardata.context_processors', '_GAME_VERSION_LABELS'),
    ('chardata.context_processors', '_GAME_VERSION_SEO_WORDS'),
)

SPLIT_TABLES = (
    ('chardata.dofusbook_export', 'HOSTS', 'VERSIONS_WITHOUT_A_SITE'),
)


def _attribute(module_name, attribute):
    return getattr(importlib.import_module(module_name), attribute)


def _missing(module_name, attribute, without=None):
    named = set(_attribute(module_name, attribute))
    if without:
        named |= set(_attribute(module_name, without))
    return [key for key in dofus_versions() if key not in named]


def _missing_reader_version(module_name, attribute):
    named = set(_attribute(module_name, attribute))
    return [key for key in game_versions.version_keys() if key not in named]


def _every_check():
    for module_name, attribute in KEYED_TABLES:
        yield ('%s.%s' % (module_name, attribute),
               lambda m=module_name, a=attribute: _missing(m, a))
    for module_name, attribute, without in SPLIT_TABLES:
        yield ('%s.%s+%s' % (module_name, attribute, without),
               lambda m=module_name, a=attribute, w=without: _missing(m, a, w))


def _stage_a_dofus_version():
    staged = GameVersion(STAGED, 'Staged', 'items.db', 'item_db_dumped.dump',
                         seo_word='3 Staged', experimental=True,
                         family='dofus3', channel='beta')
    return (mock.patch.dict(game_versions.GAME_VERSIONS, {STAGED: staged}),
            mock.patch.object(game_versions, 'VERSION_ORDER',
                              game_versions.VERSION_ORDER + (STAGED,)))


class EveryPerVersionTableNamesEveryDofusVersion(SimpleTestCase):

    def test_every_table_names_every_dofus_version(self):
        self.assertEqual(5, len(dofus_versions()))
        for label, check in _every_check():
            with self.subTest(table=label):
                self.assertEqual([], check())

    def test_every_registry_table_names_every_reader_version(self):
        for module_name, attribute in REGISTRY_TABLES:
            with self.subTest(table=attribute):
                self.assertEqual([], _missing_reader_version(module_name, attribute))

    def test_a_staged_dofus_version_is_missing_from_every_table(self):
        for patcher in _stage_a_dofus_version():
            patcher.start()
            self.addCleanup(patcher.stop)
        self.assertIn(STAGED, dofus_versions())
        for label, check in _every_check():
            with self.subTest(table=label):
                self.assertEqual([STAGED], check())

    def test_a_staged_dofus_version_never_enters_a_registry_table(self):
        patchers = _stage_a_dofus_version()
        for patcher in patchers:
            patcher.start()
        modules = [importlib.import_module(name)
                   for name in ('chardata.context_processors', 'chardata.admin_stats')]
        try:
            for module in modules:
                importlib.reload(module)
            for module_name, attribute in REGISTRY_TABLES:
                with self.subTest(table=attribute):
                    self.assertNotIn(STAGED, _attribute(module_name, attribute))
                    self.assertEqual([], _missing_reader_version(module_name, attribute))
        finally:
            for patcher in patchers:
                patcher.stop()
            for module in modules:
                importlib.reload(module)

    def test_a_split_table_never_names_a_version_on_both_sides(self):
        for module_name, attribute, without in SPLIT_TABLES:
            with self.subTest(table=attribute):
                self.assertEqual(
                    set(), set(_attribute(module_name, attribute))
                    & set(_attribute(module_name, without)))


class NoOtherTableKeyedByVersionHidesAGap(SimpleTestCase):

    SPLIT = {(module_name, attribute)
             for module_name, attribute, _without in SPLIT_TABLES}
    REGISTRY = set(REGISTRY_TABLES)

    def _literal_tables(self):
        every_key = set(game_versions.GAME_VERSIONS)
        for package in (chardata, fashionistapulp):
            root = os.path.dirname(package.__file__)
            for folder, folders, files in os.walk(root):
                folders[:] = [name for name in folders if name not in ('migrations', '__pycache__')]
                for filename in files:
                    if not filename.endswith('.py') or filename.startswith('tests'):
                        continue
                    path = os.path.join(folder, filename)
                    with open(path, encoding='utf-8') as handle:
                        tree = ast.parse(handle.read())
                    relative = os.path.relpath(path, os.path.dirname(root))[:-3]
                    parts = relative.replace(os.sep, '.').split('.')
                    if parts[-1] == '__init__':
                        parts.pop()
                    for node in tree.body:
                        if isinstance(node, ast.Assign):
                            targets, value = node.targets, node.value
                        elif isinstance(node, ast.AnnAssign) and node.value is not None:
                            targets, value = [node.target], node.value
                        else:
                            continue
                        if not isinstance(value, ast.Dict) or not value.keys:
                            continue
                        keys = [key.value if isinstance(key, ast.Constant) else None
                                for key in value.keys]
                        if not all(isinstance(key, str) and key in every_key for key in keys):
                            continue
                        for target in targets:
                            if isinstance(target, ast.Name):
                                yield '.'.join(parts), target.id

    def test_every_literal_dict_keyed_by_version_covers_every_dofus_version(self):
        gaps = []
        seen = 0
        for module_name, name in self._literal_tables():
            if (module_name, name) in self.SPLIT or (module_name, name) in self.REGISTRY:
                continue
            seen += 1
            try:
                value = getattr(importlib.import_module(module_name), name)
            except ImportError:
                continue
            missing = [key for key in dofus_versions() if key not in value]
            if missing:
                gaps.append('%s.%s lacks %s' % (module_name, name, missing))
        self.assertGreater(seen, 15)
        self.assertEqual([], gaps)
