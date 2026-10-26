# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.

"""The Wakfu presets come from the Wakfu registry or not at all, and never from Dofus."""
import sys
import types
from unittest import mock

from django.test import SimpleTestCase

from chardata import presets
from chardata.smart_build import get_standard_weights
from fashionistapulp.dofus_constants import STAT_KEY_TO_NAME

REGISTRY = presets.WAKFU_REGISTRY
ENTRY = {'styles': (), 'option_boxes': (), 'modes': ('general',), 'box_modes': {},
         'recipes': (), 'wakfu_presets': ('damage_melee_single', 'mule')}


def _stub(weights=None):
    module = types.ModuleType(REGISTRY)
    module.calls = []
    module.site_entry = lambda: dict(ENTRY)

    def standard_weights(*args):
        module.calls.append(args)
        return dict(weights or {'mastery_fire': 1.0})
    module.standard_weights = standard_weights
    return module


class _Char:
    game_version = 'wakfu'
    level = 245
    char_class = 'Iop'


def _wakfu_char(**fields):
    char = _Char()
    values = dict(wakfu_class_id=4, wakfu_preset='damage_melee_single', wakfu_elements=('fire',))
    values.update(fields)
    for name, value in values.items():
        setattr(char, name, value)
    return char


class WakfuPresetsLinkToTheRegistryTests(SimpleTestCase):
    def setUp(self):
        presets._wakfu_entry = None
        self.addCleanup(setattr, presets, '_wakfu_entry', None)

    def test_the_entry_is_the_registry_entry(self):
        with mock.patch.dict(sys.modules, {REGISTRY: _stub()}):
            found = presets.version_presets('wakfu')
        self.assertEqual(ENTRY, found)
        self.assertIsNot(found, presets.VERSION_PRESETS['dofus3'])

    def test_the_entry_is_cached_per_registry_module(self):
        with mock.patch.dict(sys.modules, {REGISTRY: _stub()}):
            first = presets.version_presets('wakfu')
            self.assertIs(first, presets.version_presets('wakfu'))
        with mock.patch.dict(sys.modules, {REGISTRY: _stub()}):
            self.assertIsNot(first, presets.version_presets('wakfu'))

    def test_a_missing_registry_raises_the_key_error_of_a_version_without_presets(self):
        with mock.patch.dict(sys.modules, {REGISTRY: None}):
            with self.assertRaises(KeyError) as raised:
                presets.version_presets('wakfu')
        self.assertEqual(('wakfu',), raised.exception.args)

    def test_a_registry_that_fails_on_its_own_import_is_not_hidden(self):
        with mock.patch('chardata.presets.importlib.import_module',
                        side_effect=ModuleNotFoundError('no', name='some_other_module')):
            with self.assertRaises(ModuleNotFoundError):
                presets.version_presets('wakfu')

    def test_the_dofus_table_stays_free_of_wakfu(self):
        self.assertNotIn('wakfu', presets.VERSION_PRESETS)
        for entry in presets.VERSION_PRESETS.values():
            self.assertNotIn('wakfu_presets', entry)

    def test_the_other_versions_do_not_load_the_registry(self):
        with mock.patch('chardata.presets.importlib.import_module') as loader:
            presets.version_presets('dofus3')
            presets.version_presets('retro')
        loader.assert_not_called()

    def test_wakfu_weights_come_from_the_registry_with_what_the_char_carries(self):
        stub = _stub({'mastery_fire': 2.5})
        with mock.patch.dict(sys.modules, {REGISTRY: stub}):
            weights = get_standard_weights(_wakfu_char(wakfu_content='pvp'))
        self.assertEqual({'mastery_fire': 2.5}, weights)
        self.assertEqual([(4, 245, 'damage_melee_single', ('fire',), 'pvp')], stub.calls)

    def test_wakfu_weights_never_carry_a_dofus_key(self):
        dofus_keys = set(STAT_KEY_TO_NAME) | {'str', 'int', 'cha', 'agi', 'vit', 'wis', 'pp'}
        with mock.patch.dict(sys.modules, {REGISTRY: _stub()}):
            weights = get_standard_weights(_wakfu_char())
        self.assertFalse(dofus_keys & set(weights))

    def test_a_wakfu_char_missing_a_field_raises_instead_of_getting_dofus_weights(self):
        for field in ('wakfu_class_id', 'wakfu_preset', 'wakfu_elements'):
            char = _wakfu_char()
            setattr(char, field, None)
            with mock.patch.dict(sys.modules, {REGISTRY: _stub()}):
                with mock.patch('chardata.smart_build._set_weights') as dofus:
                    with self.assertRaises(ValueError, msg=field):
                        get_standard_weights(char)
            dofus.assert_not_called()

    def test_a_wakfu_char_without_any_field_raises(self):
        with mock.patch('chardata.smart_build._set_weights') as dofus:
            with self.assertRaises(ValueError):
                get_standard_weights(_Char())
        dofus.assert_not_called()

    def test_a_dofus_char_still_gets_the_dofus_weights(self):
        char = _Char()
        char.game_version = 'dofus3'
        with mock.patch('chardata.smart_build.get_char_aspects', return_value=set()),                 mock.patch('chardata.smart_build._set_weights', return_value={'str': 1}) as dofus:
            self.assertEqual({'str': 1}, get_standard_weights(char))
        dofus.assert_called_once()

    def test_a_mule_without_elements_gets_weights(self):
        for elements in ((), None, ''):
            stub = _stub()
            with mock.patch.dict(sys.modules, {REGISTRY: stub}):
                weights = get_standard_weights(_wakfu_char(wakfu_preset='mule', wakfu_elements=elements))
            self.assertEqual({'mastery_fire': 1.0}, weights)
            self.assertEqual([(4, 245, 'mule', (), 'pvm')], stub.calls)

    def test_a_mule_ignores_the_elements_it_carries(self):
        stub = _stub()
        with mock.patch.dict(sys.modules, {REGISTRY: stub}):
            get_standard_weights(_wakfu_char(wakfu_preset='mule', wakfu_elements=('fire',)))
        self.assertEqual((), stub.calls[0][3])

    def test_a_class_id_of_zero_is_not_missing(self):
        stub = _stub()
        with mock.patch.dict(sys.modules, {REGISTRY: stub}):
            get_standard_weights(_wakfu_char(wakfu_class_id=0))
        self.assertEqual(0, stub.calls[0][0])

    def test_other_presets_still_need_an_element(self):
        for elements in ((), '', None, ' , '):
            with mock.patch.dict(sys.modules, {REGISTRY: _stub()}):
                with self.assertRaises(ValueError, msg=repr(elements)):
                    get_standard_weights(_wakfu_char(wakfu_elements=elements))

    def test_an_element_string_is_one_element_not_its_letters(self):
        stub = _stub()
        with mock.patch.dict(sys.modules, {REGISTRY: stub}):
            get_standard_weights(_wakfu_char(wakfu_elements='fire'))
        self.assertEqual(('fire',), stub.calls[0][3])

    def test_a_comma_separated_string_is_several_elements(self):
        stub = _stub()
        with mock.patch.dict(sys.modules, {REGISTRY: stub}):
            get_standard_weights(_wakfu_char(wakfu_elements='fire, water'))
        self.assertEqual(('fire', 'water'), stub.calls[0][3])

    def test_a_list_of_elements_reaches_the_registry_as_a_tuple(self):
        stub = _stub()
        with mock.patch.dict(sys.modules, {REGISTRY: stub}):
            get_standard_weights(_wakfu_char(wakfu_elements=['fire', 'earth']))
        self.assertEqual(('fire', 'earth'), stub.calls[0][3])

    def test_the_char_level_reaches_the_registry(self):
        for level in (10, 110, 245):
            stub = _stub()
            char = _wakfu_char()
            char.level = level
            with mock.patch.dict(sys.modules, {REGISTRY: stub}):
                get_standard_weights(char)
            self.assertEqual(level, stub.calls[0][1])

    def test_a_wakfu_char_without_a_level_raises(self):
        char = _wakfu_char()
        char.level = 0
        with mock.patch.dict(sys.modules, {REGISTRY: _stub()}):
            with self.assertRaises(ValueError):
                get_standard_weights(char)
