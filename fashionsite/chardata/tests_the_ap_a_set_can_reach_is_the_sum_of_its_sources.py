from django.test import SimpleTestCase

from fashionistapulp import wakfu_sublimations
from chardata.wakfu_invented_sublimations import block, state, use_block

STATES = {1: state(lines=[('A', 'ap', 1, 0, ())]), 2: state(lines=[('A', 'ap', 2, 0, ())]),
          3: state(lines=[('A', 'mp', 5, 0, ())])}
SUBLIMATIONS = {110: (1, 1, 'normal', ()), 111: (2, 1, 'normal', ()), 112: (3, 1, 'normal', ())}
PASSIVES = {10: {'breed': 1, 'unlock': 10, 'family': 'A', 'name': 'One', 'conditions': [],
                 'lines': [('A', 'ap', 1, 0, ())], 'conversions': [], 'uncounted': []}}


class TheApASetCanReachIsTheSumOfItsSourcesTests(SimpleTestCase):
    def setUp(self):
        use_block(self, block(STATES, SUBLIMATIONS, passives=PASSIVES))

    def test_two_sources_of_action_points_add_up(self):
        self.assertEqual(3, wakfu_sublimations.most_added('ap'))

    def test_a_source_of_another_stat_adds_nothing(self):
        self.assertEqual(5, wakfu_sublimations.most_added('mp'))
        self.assertEqual(0, wakfu_sublimations.most_added('hp'))

    def test_a_passive_adds_when_a_level_is_given_and_a_slot_is_open(self):
        self.assertEqual(4, wakfu_sublimations.most_added('ap', 10))

    def test_no_passive_adds_below_the_first_slot_level(self):
        self.assertEqual(3, wakfu_sublimations.most_added('ap', 9))
