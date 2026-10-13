# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The /setup/ script sends a weight or a minimum only when its value differs from the preset the panel showed, under names the server saves."""
import json

from django.test import SimpleTestCase, TestCase

from chardata.setup_edits import touched_fields
from chardata.tests_every_preset_keeps_its_weights_and_minimums import VERSIONS
from chardata.tests_the_setup_creation_doors_support import TouchedDoors, panel_rows
from chardata.tests_the_setup_script_sends_the_form_and_shows_only_the_last_change import run_script


def fields_sent(case, baseline, current):
    return run_script(case, 'return setupTouchedFields(setupEdits(%s, %s));'
                      % (json.dumps(baseline), json.dumps(current)))


class TheScriptSendsOnlyWhatWasTouchedTests(SimpleTestCase):

    BASELINE = {'ap': {'weight': '50', 'min': '11'}, 'mp': {'weight': '40', 'min': '6'},
                'str': {'weight': '3', 'min': ''}, 'vit': {'weight': '2', 'min': ''}}

    def current(self, **changes):
        current = json.loads(json.dumps(self.BASELINE))
        for key, values in changes.items():
            current[key].update(values)
        return current

    def test_a_form_nothing_was_typed_in_sends_no_field(self):
        self.assertEqual([], fields_sent(self, self.BASELINE, self.current()))

    def test_one_weight_typed_in_is_the_only_field_sent(self):
        self.assertEqual([['weight_str', '9']],
                         fields_sent(self, self.BASELINE, self.current(str={'weight': '9'})))

    def test_one_minimum_typed_in_is_the_only_field_sent(self):
        self.assertEqual([['min_vit', '15']],
                         fields_sent(self, self.BASELINE, self.current(vit={'min': '15'})))

    def test_a_cleared_minimum_is_sent_empty(self):
        self.assertEqual([['min_ap', '']],
                         fields_sent(self, self.BASELINE, self.current(ap={'min': ''})))

    def test_several_fields_come_out_in_the_order_of_their_names_weight_before_minimum(self):
        current = self.current(vit={'min': '4'}, ap={'weight': '51', 'min': '12'}, str={'weight': '0'})
        self.assertEqual([['weight_ap', '51'], ['min_ap', '12'], ['weight_str', '0'],
                          ['min_vit', '4']], fields_sent(self, self.BASELINE, current))

    def test_a_field_put_back_to_the_preset_value_is_not_sent(self):
        for put_back in ('50', ' 50 ', '050', '50.0'):
            with self.subTest(put_back=put_back):
                self.assertEqual([], fields_sent(self, self.BASELINE,
                                                 self.current(ap={'weight': put_back})))
        self.assertEqual([], fields_sent(self, self.BASELINE, self.current(vit={'min': '  '})))

    def test_an_empty_minimum_is_not_the_same_as_zero(self):
        self.assertEqual([['min_vit', '0']],
                         fields_sent(self, self.BASELINE, self.current(vit={'min': '0'})))

    def test_a_row_the_preset_did_not_have_is_not_sent(self):
        current = self.current()
        current['new'] = {'weight': '5', 'min': '5'}
        self.assertEqual([], fields_sent(self, self.BASELINE, current))

    def test_a_row_with_one_input_sends_that_column_only(self):
        baseline = {'chance': {'min': '4'}, 'dam': {'weight': '9'}}
        current = {'chance': {'min': '5'}, 'dam': {'weight': '10'}}
        self.assertEqual([['min_chance', '5'], ['weight_dam', '10']],
                         fields_sent(self, baseline, current))

    def test_an_aggregate_row_is_never_sent_its_members_are(self):
        baseline = {'linres': {'weight': '1', 'min': '', 'aggregate': True},
                    'neutres': {'weight': '1', 'min': ''}, 'airres': {'weight': '1', 'min': ''}}
        current = {'linres': {'weight': '7', 'min': '5', 'aggregate': True},
                   'neutres': {'weight': '7', 'min': ''}, 'airres': {'weight': '7', 'min': ''}}
        self.assertEqual([['weight_airres', '7'], ['weight_neutres', '7']],
                         fields_sent(self, baseline, current))


class TheNamesTheScriptSendsAreTheFieldsTheServerSavesTests(TouchedDoors, TestCase):

    def test_every_editable_row_of_every_version_is_sent_under_a_name_the_server_finds_touched(self):
        for version in VERSIONS:
            weight_keys, minimum_keys = panel_rows(version)
            base = self.build(version, 'wizard')
            state = self.state(version, base)
            baseline = {key: {} for key in set(weight_keys) | set(minimum_keys)}
            current = {key: {} for key in baseline}
            for key in weight_keys:
                baseline[key]['weight'] = str(state['weights'][key])
                current[key]['weight'] = str(state['weights'][key] + 1)
            for key in minimum_keys:
                shown = state['minimums'][key]
                baseline[key]['min'] = str(shown)
                current[key]['min'] = str(shown + 1) if shown != '' else '1'
            sent = fields_sent(self, baseline, current)
            with self.subTest(version=version):
                self.assertEqual(len(weight_keys) + len(minimum_keys), len(sent))
                self.assertEqual(len(sent), len({name for name, _value in sent}))
                weights, minimums = touched_fields(base, dict(sent))
                self.assertEqual(sorted(name for name, _value in sent),
                                 sorted(list(weights) + list(minimums)))
                self.assertEqual({name: value for name, value in sent},
                                 {**weights, **minimums})
