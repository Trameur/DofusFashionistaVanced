import os

from django.test import SimpleTestCase

from chardata import wakfu_encyclopedia_data, wakfu_game_text


class TheWakfuTextParserKnowsEveryTokenTheGameUsesTests(SimpleTestCase):
    """Every token of every text a live item or set reaches has a shape the renderer settles."""

    def setUp(self):
        if not os.path.exists(wakfu_encyclopedia_data.database_path()):
            self.skipTest('no Wakfu database built; run update_data_wakfu.py')
        self.conn = wakfu_encyclopedia_data.connect()
        self.addCleanup(self.conn.close)

    def test_no_reached_text_holds_a_token_shape_outside_the_known_shapes(self):
        found = wakfu_encyclopedia_data.unsettled_tokens(self.conn)
        self.assertEqual(found, [], 'unsettled (kind, id, shape): %r' % (found[:10],))

    def test_the_guard_flags_a_token_the_parser_lacks(self):
        shapes = [shape for shape, _token in
                  wakfu_game_text.token_shapes('[nonsense 12] and [#1]')]
        self.assertIn(None, shapes)
        self.assertIn('[#N]', shapes)

    def test_the_census_reaches_every_root_effect_and_each_other_one_through_a_group(self):
        census = wakfu_encyclopedia_data.census(self.conn)
        roots, reached = wakfu_encyclopedia_data.reached_effects(self.conn)
        self.assertEqual(census['effects'], reached)
        members = {row[0] for row in self.conn.execute('SELECT effect FROM effect_groups')}
        self.assertEqual(reached - set(roots) - members, set())

    def test_the_census_counts_each_reached_effect_under_its_action(self):
        census = wakfu_encyclopedia_data.census(self.conn)
        reached = sorted(census['effects'])
        expected = {}
        for start in range(0, len(reached), 500):
            chunk = reached[start:start + 500]
            marks = ','.join('?' * len(chunk))
            for action, count in self.conn.execute(
                    'SELECT action, COUNT(*) FROM effects WHERE id IN (%s) GROUP BY action'
                    % marks, chunk):
                expected[action] = expected.get(action, 0) + count
        self.assertEqual(census['actions'], expected)
