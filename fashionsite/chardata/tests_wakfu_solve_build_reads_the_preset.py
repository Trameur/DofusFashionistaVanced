import os

from django.test import SimpleTestCase

from fashionistapulp import wakfu_presets, wakfu_solve, wakfu_value

IOP = 8
LEVEL = 110
FIRE = ('fire',)


class SolveBuildReadsThePresetTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from fashionistapulp.fashionista_config import get_items_db_path
        cls.path = get_items_db_path('wakfu')
        cls.structure = None
        if os.path.exists(cls.path):
            from fashionistapulp.structure import get_structure
            cls.structure = get_structure('wakfu')

    def setUp(self):
        if self.structure is None:
            self.skipTest('no Wakfu database built; run update_data_wakfu.py')

    def solve(self, **options):
        options.setdefault('class_id', IOP)
        options.setdefault('level', LEVEL)
        options.setdefault('elements', ())
        options.setdefault('reach', None)
        return wakfu_solve.solve_build(self.structure, seconds=20, **options)

    def test_a_preset_needs_a_class(self):
        with self.assertRaisesMessage(ValueError, 'needs a class'):
            self.solve(preset='tank', elements=FIRE, class_id=None)

    def test_a_preset_takes_its_reach_and_its_defense_from_the_registry(self):
        with self.assertRaisesMessage(ValueError, 'come from the preset'):
            self.solve(preset='tank', elements=FIRE, reach='melee')
        with self.assertRaisesMessage(ValueError, 'come from the preset'):
            self.solve(preset='tank', elements=FIRE, defense=0.5)

    def test_a_preset_is_valued_on_the_class_turns(self):
        with self.assertRaisesMessage(ValueError, 'class turns'):
            self.solve(preset='tank', elements=FIRE, on_class_turn=False)

    def test_every_preset_but_the_mule_asks_for_an_element(self):
        for preset in wakfu_presets.PRESETS:
            if preset == 'mule':
                continue
            with self.subTest(preset=preset):
                with self.assertRaisesMessage(ValueError, 'elements are'):
                    self.solve(preset=preset)

    def test_an_unknown_preset_or_content_raises(self):
        with self.assertRaisesMessage(ValueError, 'preset is one of'):
            self.solve(preset='budget', elements=FIRE)
        with self.assertRaisesMessage(ValueError, 'content is'):
            self.solve(preset='tank', elements=FIRE, content='arena')

    def test_without_a_preset_the_elements_and_the_reach_are_still_required(self):
        with self.assertRaisesMessage(ValueError, 'elements are required'):
            self.solve()
        with self.assertRaisesMessage(ValueError, 'reach is required'):
            self.solve(elements=FIRE)

    def test_the_role_of_a_preset_is_the_registry_role(self):
        built = wakfu_presets.role(IOP, 'tank', FIRE, LEVEL, 'pvp', self.path)
        self.assertIsInstance(built, wakfu_value.Role)
        self.assertEqual(('fire',), built.elements)
        self.assertEqual('melee', built.reach)
        self.assertEqual('pvp', built.content)
        top = wakfu_presets.bracket_of(LEVEL, self.path)[1]
        self.assertEqual(wakfu_presets.shares(IOP, 'tank', FIRE, 'pvp', top, self.path), built.shares)
        for name in wakfu_presets.PVP_SHARES:
            self.assertIn(name, built.shares)

    def test_a_damage_preset_solves_with_the_damage_floor_of_its_content(self):
        for content in wakfu_value.CONTENTS:
            with self.subTest(content=content):
                found = self.solve(preset=wakfu_presets.DAMAGE_PRESETS[0], elements=FIRE,
                                   content=content, rounds=1)
                self.assertEqual(wakfu_value.rule('damage_floor')[content],
                                 found.model.damage_floor)
        self.assertIsNone(self.solve(preset='tank', elements=FIRE, rounds=1).model.damage_floor)
