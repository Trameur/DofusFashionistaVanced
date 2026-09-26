# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Each version's effect table still matches that version's game texts."""
from django.test import SimpleTestCase

from fashionistapulp.item_effects import (EQUIVALENT_KEYS, load_effect_table,
                                          text_fingerprint, versions_with_effect_table)

LANGUAGES = ('fr', 'en')


def _key(item):
    return str(item.ankama_id) if item.ankama_id is not None else 'site:%d' % item.id


def _carries_an_effect(item):
    return bool(item.localized_extras.get('fr') or item.localized_extras.get('en')
                or any(item.weird_conditions.values()) or item.spell_tooltips)


def _resolve(structure, key):
    if key.startswith('site:'):
        return structure.get_item_by_id(int(key[len('site:'):]))
    return structure.get_item_by_ankama_id(int(key))


class EveryEffectTextMatchesItsTableTests(SimpleTestCase):

    def setUp(self):
        from fashionistapulp.structure import set_current_game_version
        self.addCleanup(set_current_game_version, 'dofus3')

    def _structure(self, version):
        from fashionistapulp.structure import get_structure, set_current_game_version
        set_current_game_version(version)
        return get_structure(version)

    def test_dofus3_has_its_table(self):
        self.assertIn('dofus3', versions_with_effect_table())
        self.assertEqual('dofus3', load_effect_table('dofus3')['version'])

    def test_every_effect_item_has_an_entry_with_the_same_text(self):
        for version in versions_with_effect_table():
            with self.subTest(version=version):
                structure = self._structure(version)
                items = load_effect_table(version)['items']
                problems, seen = [], set()
                for item in structure.get_items_list():
                    if not _carries_an_effect(item):
                        continue
                    key = _key(item)
                    seen.add(key)
                    name = item.localized_names.get('fr') or item.name
                    entry = items.get(key)
                    if entry is None:
                        problems.append('new: %s %s' % (key, name))
                        continue
                    for language in LANGUAGES:
                        if (text_fingerprint(item.localized_extras.get(language))
                                != entry['fingerprint'][language]):
                            problems.append('text changed (%s): %s %s'
                                            % (language, key, name))
                for key, entry in items.items():
                    has_text = any(entry['text'][language] for language in LANGUAGES)
                    if has_text and key not in seen:
                        problems.append('gone: %s %s' % (key, entry['name']['fr']))
                self.assertFalse(problems, 'regenerate the %s effect table: %s'
                                 % (version, problems[:20]))

    def test_every_entry_resolves_to_an_item(self):
        for version in versions_with_effect_table():
            with self.subTest(version=version):
                structure = self._structure(version)
                unresolved = [key for key in load_effect_table(version)['items']
                              if _resolve(structure, key) is None]
                self.assertFalse(unresolved)

    def test_the_equivalents_only_use_keys_the_objective_reads(self):
        for version in versions_with_effect_table():
            unknown = set()
            for entry in load_effect_table(version)['items'].values():
                groups = [entry.get('equivalents') or {}]
                for field in ('equivalents_by_elements', 'equivalents_by_element_set'):
                    groups.extend((entry.get(field) or {}).values())
                for group in groups:
                    unknown.update(k for k in group if k != 'sets' and k not in EQUIVALENT_KEYS)
            with self.subTest(version=version):
                self.assertFalse(unknown)

    def test_the_table_was_built_on_the_current_patch(self):
        from chardata.data_versions import current_data_version, patch_of
        for version in versions_with_effect_table():
            with self.subTest(version=version):
                measured = load_effect_table(version)['measurement']['data_version']
                self.assertEqual(patch_of(current_data_version(version)), patch_of(measured),
                                 'a new patch needs a new measurement and a regenerated table')
