from django.test import SimpleTestCase

from fashionistapulp import wakfu_criteria as criteria

STATS = {'ap', 'mp', 'wp', 'ferocity', 'hp', 'range'}
BREEDS = {'ALPHA', 'BETA'}
ITEMS = {10, 11, 12}

SHAPES = {
    'no condition atom': 'True',
    'one breed': 'IsBreed("ALPHA")',
    'level floor': 'GetLevel() >= 50',
    'level window': 'GetRealLevel() > 20 && GetRealLevel() < 60',
    'stat floor': 'GetCharac("FEROCITY") > -10',
    'stat ceiling': 'GetCharac("AP") < 8',
    'stat equal': 'GetCharac("MP") == 4',
    'stat flipped': '7 < GetCharac("WP")',
    'stat window': 'GetCharac("FEROCITY") > -10 && GetCharac("FEROCITY") < 40',
    'max stat': 'GetCharacMax("WP") >= 6',
    'max stat target': 'GetCharacteristicMax("WP", "target") >= 6',
    'worn with': 'HasEquipmentId(10)',
    'not worn with': 'not HasEquipmentId(11)',
    'same item': 'not HasAnotherSameEquipment()',
    'unusable': 'IsAdmin()',
    'false atom': 'False',
    'pvp rank': 'HasPvpRank(7)',
    'gauge': 'GetStasisGauge() >= 56',
    'citizenship of a nation': 'GetCrimeScore(31) >= 500',
    'citizenship of none': 'GetCrimeScore() > 100',
    'company rank': 'GetCompanyRank() >= 10',
    'guild level': 'GetGuildLevel() >= 9',
    'nation': 'GetNationId() == 31',
    'history craft': 'GetCraftLevel(75) >= 80',
    'history or': '(GetInstanceId() == 5 || HasCraft(3))',
    'several conjuncts': 'IsBreed("BETA") && GetCharac("AP") < 8 && not HasEquipmentId(11)',
}


def derive(text):
    return criteria.derive(criteria.parse(text), stat_keys=STATS, breed_names=BREEDS,
                           item_ids=ITEMS)


def env(level=50, breed='ALPHA', state=None, totals=None, piece=10, others=()):
    return criteria.Env(level, breed, state or criteria.start_state(), totals or {},
                        piece, set(others))


class TheWakfuCriteriaParseDeriveAndEvaluateEveryShapeTests(SimpleTestCase):
    def test_every_census_shape_parses(self):
        for label, text in SHAPES.items():
            with self.subTest(label):
                self.assertIsNotNone(criteria.parse(text))
        self.assertEqual(criteria.parse('IsBreed("ALPHA") and GetLevel() > 5'),
                         criteria.parse('IsBreed("ALPHA") && GetLevel() > 5'))

    def test_each_shape_derives_its_rows(self):
        self.assertTrue(derive('IsAdmin()').unusable)
        self.assertTrue(derive('False').unusable)
        self.assertFalse(derive('True').unusable)
        self.assertEqual(('ALPHA',), derive('IsBreed("ALPHA")').classes)
        self.assertEqual(50, derive('GetLevel() >= 50').min_level)
        window = derive('GetRealLevel() > 20 && GetRealLevel() < 60')
        self.assertEqual((21, 59), (window.min_level, window.max_level))
        self.assertEqual({'ferocity': -9}, derive('GetCharac("FEROCITY") > -10').min_stats)
        self.assertEqual({'ap': 7}, derive('GetCharac("AP") < 8').max_stats)
        equal = derive('GetCharac("MP") == 4')
        self.assertEqual(({'mp': 4}, {'mp': 4}), (equal.min_stats, equal.max_stats))
        self.assertEqual({'wp': 8}, derive('7 < GetCharac("WP")').min_stats)
        self.assertEqual({'wp': 6}, derive('GetCharacMax("WP") >= 6').min_stats)
        self.assertEqual({'wp': 6},
                         derive('GetCharacteristicMax("WP", "target") >= 6').min_stats)
        self.assertEqual((10,), derive('HasEquipmentId(10)').worn_with)
        self.assertEqual((11,), derive('not HasEquipmentId(11)').not_worn_with)
        self.assertTrue(derive('not HasAnotherSameEquipment()').same_item)
        option = criteria.StateCondition
        self.assertEqual((option('pvp_rank', None, '>=', 7),), derive('HasPvpRank(7)').state)
        self.assertEqual((option('stasis_gauge', None, '>=', 56),),
                         derive('GetStasisGauge() >= 56').state)
        self.assertEqual((option('citizenship', 31, '>=', 500),),
                         derive('GetCrimeScore(31) >= 500').state)
        self.assertEqual((option('citizenship', None, '>=', 101),),
                         derive('GetCrimeScore() > 100').state)
        self.assertEqual((option('company_rank', None, '>=', 10),),
                         derive('GetCompanyRank() >= 10').state)
        self.assertEqual((option('guild_level', None, '>=', 9),),
                         derive('GetGuildLevel() >= 9').state)
        self.assertEqual((option('nation', None, '==', 31),), derive('GetNationId() == 31').state)
        many = derive('IsBreed("BETA") && GetCharac("AP") < 8 && not HasEquipmentId(11)')
        self.assertEqual((('BETA',), {'ap': 7}, (11,)),
                         (many.classes, many.max_stats, many.not_worn_with))

    def test_hidden_atoms_true_false_and_double_ampersand_parse(self):
        hidden = criteria.parse('#GetCraftLevel(75) >= 80#')
        self.assertIsInstance(hidden, criteria.Hidden)
        self.assertEqual({'GetCraftLevel'}, criteria.functions(hidden))
        self.assertEqual({'True'}, criteria.functions(criteria.parse('True')))
        self.assertEqual({'False'}, criteria.functions(criteria.parse('false')))
        both = criteria.parse('IsBreed("ALPHA") && #GetCraftLevel(75) >= 80#')
        self.assertIsInstance(both, criteria.And)
        self.assertEqual(2, len(both.children))
        self.assertEqual(('ALPHA',), derive('IsBreed("ALPHA") && #GetCraftLevel(75) >= 80#').classes)

    def test_an_unknown_function_raises(self):
        with self.assertRaises(criteria.CriteriaError):
            criteria.classify('GetFavouriteColour')
        with self.assertRaises(criteria.CriteriaError):
            derive('GetFavouriteColour() > 1')
        with self.assertRaises(criteria.CriteriaError):
            criteria.parse('')
        with self.assertRaises(criteria.CriteriaError):
            criteria.parse('GetLevel() >')

    def test_a_refused_shape_raises(self):
        refused = (
            'IsBreed("ALPHA") || IsBreed("BETA")',
            'IsBreed("GAMMA")',
            'IsBreed("ALPHA") && IsBreed("BETA")',
            'HasEquipmentId(99)',
            'GetCharac("HP") > 5',
            'GetCharac("NOWHERE") > 5',
            'GetStasisGauge() != 3',
            'not GetLevel()',
            'GetCharacteristicMax("WP") >= 6',
            'GetCraftLevel(75) >= 80 || GetLevel() > 3',
            '#GetLevel() > 3#',
        )
        for text in refused:
            with self.subTest(text):
                with self.assertRaises(criteria.CriteriaError):
                    derive(text)

    def test_history_atoms_hold_under_either_polarity(self):
        for text in ('GetCraftLevel(75) >= 80', 'not HasCraft(3)', '#IsDay()#',
                     'GetInstanceId() == 5 || IsAchievementComplete(9)'):
            with self.subTest(text):
                tree = criteria.parse(text)
                self.assertTrue(criteria.evaluate(tree, env()))
                self.assertEqual([], criteria.failing_atoms(tree, env()))
        self.assertEqual(criteria.derive(criteria.parse('GetCraftLevel(75) >= 80'),
                                         stat_keys=STATS, breed_names=BREEDS,
                                         item_ids=ITEMS).min_stats, {})

    def test_evaluation_reads_level_breed_state_totals_and_other_pieces(self):
        self.assertTrue(criteria.evaluate(criteria.parse('GetLevel() >= 50'), env(level=50)))
        self.assertFalse(criteria.evaluate(criteria.parse('GetLevel() >= 50'), env(level=49)))
        self.assertTrue(criteria.evaluate(criteria.parse('IsBreed("ALPHA")'), env()))
        self.assertFalse(criteria.evaluate(criteria.parse('IsBreed("ALPHA")'), env(breed='BETA')))
        self.assertFalse(criteria.evaluate(criteria.parse('IsBreed("ALPHA")'), env(breed=None)))
        stat = criteria.parse('GetCharac("AP") < 8')
        self.assertTrue(criteria.evaluate(stat, env(totals={'ap': 7})))
        self.assertFalse(criteria.evaluate(stat, env(totals={'ap': 8})))
        self.assertTrue(criteria.evaluate(criteria.parse('HasEquipmentId(11)'), env(others=[11])))
        self.assertFalse(criteria.evaluate(criteria.parse('HasEquipmentId(11)'), env()))
        self.assertFalse(criteria.evaluate(criteria.parse('not HasEquipmentId(11)'),
                                           env(others=[11])))
        same = criteria.parse('not HasAnotherSameEquipment()')
        self.assertTrue(criteria.evaluate(same, env(piece=10, others=[11])))
        self.assertFalse(criteria.evaluate(same, env(piece=10, others=[10])))
        self.assertFalse(criteria.evaluate(criteria.parse('IsAdmin()'), env()))
        gauge = criteria.parse('GetStasisGauge() >= 56')
        self.assertFalse(criteria.evaluate(gauge, env()))
        raised = criteria.player_state(stasis_gauge=60)
        self.assertTrue(criteria.evaluate(gauge, env(state=raised)))
        crime = criteria.parse('GetCrimeScore(31) >= 500')
        held = criteria.player_state(citizenship={31: 500})
        self.assertTrue(criteria.evaluate(crime, env(state=held)))
        self.assertFalse(criteria.evaluate(crime, env(state=criteria.player_state(
            citizenship={32: 900}))))
        own = criteria.parse('GetCrimeScore() >= 500')
        self.assertTrue(criteria.evaluate(own, env(state=criteria.player_state(
            nation=31, citizenship={31: 500}))))
        self.assertFalse(criteria.evaluate(own, env(state=held)))
        rank = criteria.parse('HasPvpRank(7)')
        self.assertFalse(criteria.evaluate(rank, env()))
        self.assertTrue(criteria.evaluate(rank, env(state=criteria.player_state(pvp_rank=9))))
        both = criteria.parse('IsBreed("ALPHA") && GetCharac("AP") < 8')
        failing = criteria.failing_atoms(both, env(breed='BETA', totals={'ap': 9}))
        self.assertEqual(2, len(failing))
        self.assertEqual(1, len(criteria.failing_atoms(both, env(totals={'ap': 9}))))

    def test_the_strictest_bound_wins_when_one_text_bounds_a_stat_twice(self):
        both = derive('GetCharac("AP") > 2 && GetCharac("AP") >= 5')
        self.assertEqual({'ap': 5}, both.min_stats)
        both = derive('GetCharac("AP") < 9 && GetCharac("AP") <= 7')
        self.assertEqual({'ap': 7}, both.max_stats)
        both = derive('GetLevel() > 10 && GetLevel() >= 30 && GetLevel() <= 90 && GetLevel() < 80')
        self.assertEqual((30, 79), (both.min_level, both.max_level))
