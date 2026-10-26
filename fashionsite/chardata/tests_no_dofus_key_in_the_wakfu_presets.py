import os
import sqlite3

from django.test import SimpleTestCase

from chardata.smart_build import ASPECT_TO_NAME
from fashionistapulp import wakfu_presets, wakfu_value
from fashionistapulp.dofus_constants import STAT_KEY_TO_NAME

DOFUS_KEYS = {'str', 'int', 'cha', 'agi', 'vit', 'wis', 'pp', 'pods', 'pod', 'pow', 'dam',
              'cf', 'ch', 'ref', 'summon', 'heals', 'crit', 'omni', 'solo_pvm', 'group_pvm',
              'farm', 'koli_1v1', 'koli_3v3'}
#: words both games use for their own stat
SHARED_WORDS = {'hp', 'ap', 'mp', 'range', 'dodge', 'init', 'lock', 'heal', 'pvp'}
ELEMENTS = wakfu_value.ELEMENTS


def words_of(value):
    """Every string held anywhere inside a registry value, keys included."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, inside in value.items():
            yield from words_of(key)
            yield from words_of(inside)
    elif isinstance(value, (list, tuple, set, frozenset)):
        for inside in value:
            yield from words_of(inside)


class NoDofusKeyInTheWakfuPresetsTests(SimpleTestCase):
    def dofus_keys(self):
        return (DOFUS_KEYS | set(STAT_KEY_TO_NAME) | set(ASPECT_TO_NAME)) - SHARED_WORDS

    def test_no_key_of_the_registry_is_a_dofus_key(self):
        registry = {'presets': dict(wakfu_presets.PRESETS),
                    'starting': wakfu_presets.STARTING_SHARES,
                    'pvp': wakfu_presets.PVP_SHARES, 'shares': wakfu_presets.SHARES,
                    'roles': wakfu_presets.ROLE_OF_ID, 'role_presets': wakfu_presets.ROLE_PRESET,
                    'site': wakfu_presets.site_entry()}
        self.assertEqual(set(), set(words_of(registry)) & self.dofus_keys())

    def test_a_preset_holds_role_fields_and_no_element(self):
        elements = set(ELEMENTS) | {'light', 'physical'}
        for key, spec in wakfu_presets.PRESETS.items():
            with self.subTest(preset=key):
                self.assertEqual(set(), set(words_of(spec)) & elements)
                self.assertEqual({'reach', 'target', 'berserk'}, set(spec))
        for key, table in wakfu_presets.STARTING_SHARES.items():
            self.assertEqual(set(), set(table) - set(wakfu_value.COMPONENTS), key)
            self.assertEqual(set(), set(table) & elements)
        self.assertEqual(12, len(wakfu_presets.PRESETS))

    def test_the_site_entry_names_the_presets_and_holds_no_dofus_option(self):
        entry = wakfu_presets.site_entry()
        self.assertEqual(('damage_melee_single', 'damage_melee_area', 'damage_distance_single',
                          'damage_distance_area', 'damage_mixed_single', 'damage_mixed_area',
                          'tank', 'heal', 'support', 'placement', 'hindrance', 'mule'),
                         entry['wakfu_presets'])
        self.assertEqual(((), (), ('general',), {}, ()),
                         (entry['styles'], entry['option_boxes'], entry['modes'],
                          entry['box_modes'], entry['recipes']))

    def test_every_weight_key_of_a_preset_is_a_wakfu_stat(self):
        from fashionistapulp.fashionista_config import get_items_db_path
        path = get_items_db_path('wakfu')
        if not os.path.exists(path):
            self.skipTest('no Wakfu database built; run update_data_wakfu.py')
        conn = sqlite3.connect('file:%s?mode=ro' % path, uri=True)
        try:
            stats = {key for (key,) in conn.execute('SELECT key FROM stats')}
        finally:
            conn.close()
        stats |= {'ap', 'mp', 'wp', 'range', wakfu_value.FINAL_DAMAGE, 'hp_percent',
                  'block', 'dmg_in_percent'}
        for class_id, preset in ((8, 'tank'), (7, 'heal'), (3, 'mule'),
                                 (19, 'damage_mixed_area')):
            with self.subTest(preset=preset):
                found = wakfu_presets.standard_weights(
                    class_id, 245, preset, () if preset == 'mule' else ELEMENTS, path=path)
                self.assertTrue(found)
                self.assertEqual(set(), set(found) - stats)
                self.assertEqual(set(), set(found) & {'str', 'int', 'cha', 'agi', 'vit', 'wis',
                                                       'pp'})
