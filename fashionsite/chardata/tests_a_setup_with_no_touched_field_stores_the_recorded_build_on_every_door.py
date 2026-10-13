# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A /setup/ form that posts no weight or minimum stores the recorded golden build through the wizard, optimize and hand doors."""
from django.utils import translation

from chardata import tests_every_preset_keeps_its_weights_and_minimums as golden
from chardata.create_project_view import create_project


def recorded_cases(button):
    """{name: (version, class, level, boxes, temporix, record)} for the golden setup cases made with a button."""
    cases = {}
    for name, record in golden.load_fixture('setup').items():
        parts = name.split(' ')
        if len(parts) < 5 or parts[3] != button:
            continue
        boxes = set() if parts[4] == 'none' else set(parts[4].split('+'))
        cases[name] = (parts[0], parts[1], int(parts[2]), boxes, 'temporix' in parts[5:], record)
    return cases


class TheDoorsStoreTheRecordedBuildWhenNothingIsTouchedTests(
        golden.TheSetupPageKeepsItsAspectsWeightsAndMinimumsTests):
    test_every_case_keeps_its_recorded_values = None

    def replay(self, recorded, pressed):
        cases = recorded_cases(recorded)
        self.assertGreater(len(cases), 20)
        current = {}
        focus = {}
        with translation.override('en'):
            for name, (version, char_class, level, boxes, temporix, _record) in sorted(cases.items()):
                if version not in focus:
                    columns, _labels, _switch = golden._offered_setup(version)
                    focus[version] = [aspect for column in columns[2:] for aspect in column]
                self.focus_column = focus[version]
                data = self._form(char_class, level, boxes, pressed)
                if temporix:
                    data['temporix'] = 'on'
                self.assertFalse([key for key in data if key.startswith(('weight_', 'min_'))])
                current[name] = golden._record(self._post(create_project, version, data))
        expected = {name: case[-1] for name, case in cases.items()}
        rows = golden.differences(expected, current)
        if rows:
            self.fail(golden.describe(pressed, rows, len(current)))
        return len(current)

    def test_the_wizard_door_stores_every_recorded_wizard_build(self):
        self.assertGreater(self.replay('wizard', 'wizard'), 1000)

    def test_the_optimize_door_stores_every_recorded_wizard_build(self):
        self.assertGreater(self.replay('wizard', 'optimize'), 1000)

    def test_the_hand_door_stores_every_recorded_hand_build(self):
        self.assertGreater(self.replay('byhand', 'byhand'), 20)
