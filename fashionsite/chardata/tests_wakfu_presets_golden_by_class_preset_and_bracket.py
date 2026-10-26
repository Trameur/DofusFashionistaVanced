import hashlib
import json
import os
from unittest import mock

from django.test import SimpleTestCase

from fashionistapulp import wakfu_presets, wakfu_value

FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures',
                       'wakfu_presets_golden.json')
ELEMENTS = wakfu_value.ELEMENTS
LISTED_BRACKETS = (35, 110, 245)
TOP_WEIGHTS = 12
DECIMALS = 4
CONTENTS = ('pvm', 'pvp')


def elements_of(preset):
    return () if preset == 'mule' else ELEMENTS


def role_fields(built):
    return {'elements': list(built.elements), 'reach': built.reach, 'target': built.target,
            'content': built.content, 'berserk': built.berserk,
            'shares': {name: round(share, DECIMALS) for name, share in built.shares.items()}}


def role_or_reason(class_id, preset, top, content, path):
    try:
        return wakfu_presets.role(class_id, preset, elements_of(preset), top, content, path), None
    except ValueError as error:
        return None, str(error)


def listed_case(class_id, preset, top, path):
    """What the fixture holds for one class, preset and bracket top, in pvm and pvp."""
    out = {}
    for content in CONTENTS:
        built, reason = role_or_reason(class_id, preset, top, content, path)
        out[content] = {'error': reason} if built is None else role_fields(built)
    if 'error' not in out['pvm']:
        found = wakfu_presets.standard_weights(class_id, top, preset, elements_of(preset),
                                               'pvm', path)
        ranked = sorted(((round(weight, DECIMALS), key) for key, weight in found.items()
                         if round(weight, DECIMALS)), key=lambda one: (-one[0], one[1]))
        out['top_weights'] = [[key, weight] for weight, key in ranked[:TOP_WEIGHTS]]
    return out


def digest_of(class_id, preset, path):
    """sha1 of the role fields of a class and preset in every bracket and content."""
    digest = hashlib.sha1()
    for _, top in wakfu_presets._read(path)[0]:
        for content in CONTENTS:
            built, reason = role_or_reason(class_id, preset, top, content, path)
            held = {'error': reason} if built is None else role_fields(built)
            digest.update(json.dumps([top, content, held], sort_keys=True).encode())
    return digest.hexdigest()


def snapshot(path):
    """The whole fixture, computed."""
    classes = {}
    for class_id in sorted(wakfu_presets._read(path)[1]):
        presets = {}
        for preset in wakfu_presets.PRESETS:
            presets[preset] = {str(top): listed_case(class_id, preset, top, path)
                               for top in LISTED_BRACKETS}
        classes[str(class_id)] = {
            'offered': {str(top): list(wakfu_presets.offered(class_id, top, path))
                        for top in LISTED_BRACKETS},
            'presets': presets,
            'digests': {preset: digest_of(class_id, preset, path)
                        for preset in wakfu_presets.PRESETS},
        }
    return {'elements': list(ELEMENTS), 'brackets': LISTED_BRACKETS, 'classes': classes}


class TheWakfuPresetsAreFrozenByClassPresetAndBracketTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from fashionistapulp.fashionista_config import get_items_db_path
        cls.path = get_items_db_path('wakfu')
        cls.held = None
        if os.path.exists(cls.path):
            with open(FIXTURE, encoding='utf-8') as source:
                cls.held = json.load(source)

    def setUp(self):
        if self.held is None:
            self.skipTest('no Wakfu database built; run update_data_wakfu.py')

    def test_the_fixture_holds_eighteen_classes_twelve_presets_and_three_brackets(self):
        self.assertEqual(18, len(self.held['classes']))
        for class_id, entry in self.held['classes'].items():
            self.assertEqual(set(wakfu_presets.PRESETS), set(entry['presets']), class_id)
            self.assertEqual(set(wakfu_presets.PRESETS), set(entry['digests']), class_id)
            for held in entry['presets'].values():
                self.assertEqual({str(top) for top in LISTED_BRACKETS}, set(held))

    def test_the_offered_presets_are_those_of_the_fixture(self):
        for class_id, entry in self.held['classes'].items():
            with self.subTest(class_id=class_id):
                for top, held in entry['offered'].items():
                    self.assertEqual(held, list(wakfu_presets.offered(
                        int(class_id), int(top), self.path)), top)

    def test_the_shares_and_the_role_fields_are_those_of_the_fixture(self):
        for class_id, entry in self.held['classes'].items():
            for preset, brackets in entry['presets'].items():
                for top, held in brackets.items():
                    for content in CONTENTS:
                        with self.subTest(class_id=class_id, preset=preset, bracket=top,
                                          content=content):
                            built, reason = role_or_reason(
                                int(class_id), preset, int(top), content, self.path)
                            found = {'error': reason} if built is None else role_fields(built)
                            self.assertEqual(held[content], found)

    def test_the_top_weights_are_those_of_the_fixture(self):
        for class_id, entry in self.held['classes'].items():
            for preset, brackets in entry['presets'].items():
                for top, held in brackets.items():
                    if 'top_weights' not in held:
                        continue
                    with self.subTest(class_id=class_id, preset=preset, bracket=top):
                        found = listed_case(int(class_id), preset, int(top), self.path)
                        self.assertEqual(held['top_weights'], found['top_weights'])

    def test_a_digest_of_every_bracket_covers_each_class_and_preset(self):
        for class_id, entry in self.held['classes'].items():
            for preset, held in entry['digests'].items():
                with self.subTest(class_id=class_id, preset=preset):
                    self.assertEqual(held, digest_of(int(class_id), preset, self.path))

    def test_the_classes_are_not_read_from_one_table(self):
        heal = [entry['presets']['support']['245']['pvm']
                for entry in self.held['classes'].values()]
        self.assertTrue(any('heal' in one['shares'] for one in heal))
        self.assertTrue(any('heal' not in one['shares'] for one in heal))
        errors = [entry['presets']['heal']['245']['pvm'].get('error')
                  for entry in self.held['classes'].values()]
        self.assertTrue(any(errors))

    def test_no_preset_but_the_mule_is_without_a_damage_share(self):
        for class_id, entry in self.held['classes'].items():
            for preset, brackets in entry['presets'].items():
                for held in brackets.values():
                    for content in CONTENTS:
                        shares = held[content].get('shares')
                        if shares is None:
                            continue
                        with self.subTest(class_id=class_id, preset=preset):
                            self.assertEqual(preset != 'mule', 'damage' in shares)
                            self.assertEqual([] if preset == 'mule' else list(ELEMENTS),
                                             held[content]['elements'])


class TheClassTableOverridesMoveOnlyTheirClassTests(SimpleTestCase):
    FECA, IOP, CRA = 1, 8, 9

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from fashionistapulp.fashionista_config import get_items_db_path
        cls.path = get_items_db_path('wakfu')

    def setUp(self):
        if not os.path.exists(self.path):
            self.skipTest('no Wakfu database built; run update_data_wakfu.py')

    def table(self, class_id, preset='tank', bracket=245):
        return wakfu_presets.shares(class_id, preset, ELEMENTS, 'pvm', bracket, self.path)

    def test_an_override_for_one_class_and_preset_moves_that_class_and_preset_only(self):
        before = {key: self.table(*key) for key in ((self.FECA,), (self.IOP,), (self.CRA,),
                                                    (self.FECA, 'hindrance'))}
        override = {self.FECA: {'tank': {'damage': 0.3, 'lock': 0.7}}}
        with mock.patch.dict(wakfu_presets.SHARES, override):
            self.assertEqual(0.3, self.table(self.FECA)['damage'])
            self.assertEqual(0.7, self.table(self.FECA)['lock'])
            self.assertEqual(before[(self.IOP,)], self.table(self.IOP))
            self.assertEqual(before[(self.CRA,)], self.table(self.CRA))
            self.assertEqual(before[(self.FECA, 'hindrance')],
                             self.table(self.FECA, 'hindrance'))
        self.assertEqual(before[(self.FECA,)], self.table(self.FECA))

    def test_the_override_reaches_the_role_of_its_class_only(self):
        override = {self.IOP: {'tank': {'life': 3}}}
        with mock.patch.dict(wakfu_presets.SHARES, override):
            moved = wakfu_presets.role(self.IOP, 'tank', ELEMENTS, 245, path=self.path)
            kept = wakfu_presets.role(self.FECA, 'tank', ELEMENTS, 245, path=self.path)
        self.assertEqual(3.0, moved.shares['life'])
        self.assertEqual(1.0, kept.shares['life'])
