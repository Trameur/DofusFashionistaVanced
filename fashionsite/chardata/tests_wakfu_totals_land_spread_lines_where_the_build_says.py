import collections

from chardata.tests_wakfu_solver_rings_removed_items_and_element_lines import (
    MASTERY, RESISTANCE, WakfuDatabaseCase)
from chardata.wakfu_invented_sublimations import block, use_block

KEL_DWA = 21697
LEVEL = 245


class WakfuTotalsLandSpreadLinesWhereTheBuildSaysTests(WakfuDatabaseCase):
    def build(self, weights):
        from fashionistapulp.wakfu_model import WakfuBuild
        return WakfuBuild(self.structure, LEVEL, weights)

    def spread_items(self):
        found = []
        for ident, in self.rows('SELECT DISTINCT item FROM stat_element_count ORDER BY item'):
            piece = self.structure.get_item_by_id(ident)
            if piece is not None and any(self.key(stat_id) in MASTERY + RESISTANCE
                                         for stat_id, _v, _e in piece.element_spread or ()):
                found.append(piece)
            if len(found) == 6:
                break
        return found

    def key(self, stat_id):
        return self.structure.get_stat_by_id(stat_id).key

    def worn_of(self, pieces):
        return {'POSITION_%d' % at: piece for at, piece in enumerate(pieces)}

    def test_the_default_equals_the_totals_by_the_weights_on_real_items(self):
        build = self.build({'dmg_fire_percent': 1, 'res_water_percent': 1})
        pieces = self.spread_items()
        self.assertGreaterEqual(len(pieces), 2)
        worn = self.worn_of(pieces)
        by_weights = {(position, index): build._lands_on(self.key(stat_id), value, elements)
                      for position, piece in worn.items()
                      for index, (stat_id, value, elements) in enumerate(piece.element_spread)
                      if self.key(stat_id) in MASTERY + RESISTANCE}
        self.assertTrue(by_weights)
        self.assertEqual(build.sheet_totals(worn), build.sheet_totals(worn, by_weights))
        self.assertEqual(build.totals(worn), build.totals(worn, by_weights))
        self.assertEqual(build.sheet_totals(worn), build.sheet_totals(worn, {}))

    def test_the_default_landing_is_the_sum_of_the_spread_lines_by_the_weights(self):
        build = self.build({'dmg_fire_percent': 1})
        worn = self.worn_of(self.spread_items())
        expected = collections.Counter()
        for _position, _piece, _key, value, landed in build.spread_lines(worn):
            for name in landed:
                expected[name] += value
        self.assertEqual(expected, build.where_the_spread_lands(worn))

    def loss_on(self, element):
        kel_dwa = self.item(KEL_DWA)
        worn = {'LEFT_HAND': kel_dwa}
        index = next(at for at, (stat_id, _v, _e) in enumerate(kel_dwa.element_spread)
                     if self.key(stat_id) == 'res_in_percent')
        return worn, {('LEFT_HAND', index): [element]}

    def test_a_given_landing_puts_the_loss_on_the_element_it_names(self):
        build = self.build({'res_fire_percent': 1})
        worn, landing = self.loss_on('res_air_percent')
        self.assertEqual({'res_air_percent': -250}, dict(build.where_the_spread_lands(worn, landing)))
        weighed = build.where_the_spread_lands(worn)
        self.assertEqual({'res_water_percent': -250}, dict(weighed))
        weighed = build.sheet_totals(worn)
        said = build.sheet_totals(worn, landing)
        self.assertEqual(-250, said['res_air_percent'] - weighed['res_air_percent'])
        self.assertEqual(250, said['res_water_percent'] - weighed['res_water_percent'])

    def test_the_given_landing_reaches_the_fight_totals(self):
        build = self.build({'res_fire_percent': 1})
        worn, landing = self.loss_on('res_air_percent')
        weighed = build.totals(worn)
        said = build.totals(worn, landing)
        self.assertEqual(-250, said['res_air_percent'] - weighed['res_air_percent'])

    def test_the_fight_conditions_read_the_sheet_the_landing_gives(self):
        from fashionistapulp.wakfu_model import WakfuBuild
        spell = 10
        passive = {'name': 'Passive', 'breed': 1, 'unlock': 10, 'family': 'J',
                   'lines': [('J', 'ferocity', 7, 0, (0,))],
                   'conditions': [('GetCharac', 'res_air_percent', '<=', -100)],
                   'conversions': [], 'uncounted': []}
        use_block(self, block(passives={spell: passive}))
        build = WakfuBuild(self.structure, LEVEL, {'res_fire_percent': 1}, passives='none')

        class Worn(dict):
            passives = [spell]

        base, landing = self.loss_on('res_air_percent')
        worn = Worn(base)
        weighed = build.totals(worn)
        said = build.totals(worn, landing)
        self.assertEqual(7, said['ferocity'] - weighed['ferocity'])
        self.assertEqual(-250, said['res_air_percent'] - weighed['res_air_percent'])

    def test_a_landing_that_does_not_fit_its_line_is_refused(self):
        build = self.build({'res_fire_percent': 1})
        worn, landing = self.loss_on('res_air_percent')
        (position, index), = landing
        for bad in ({('LEFT_HAND', 99): ['res_air_percent']},
                    {('NOWHERE', 0): ['res_air_percent']},
                    {(position, index): ['air']},
                    {(position, index): ['res_air_percent', 'res_fire_percent']}):
            with self.subTest(landing=bad):
                with self.assertRaises(ValueError):
                    build.where_the_spread_lands(worn, bad)
