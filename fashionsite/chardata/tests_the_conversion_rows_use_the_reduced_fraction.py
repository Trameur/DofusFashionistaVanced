import itertools
import types

from django.test import SimpleTestCase

from fashionistapulp.lpproblem import LpProblem2
from fashionistapulp.wakfu_model import CONVERTED, SHARE_SCALE, WakfuBuild

NAME = 'v'
VALUE = '%s_%s' % (CONVERTED, NAME)
INDICATOR = ('act', 'on')
ON = 'act_on'


class Recorder:
    def __init__(self):
        self.rows = {}

    def add_row(self, terms, sense, rhs, name=None):
        self.rows[name] = (list(terms), sense, rhs)


def rows_of(share, terms, base, columns):
    """(rows, scale, most, total) of the conversion rows of one share, as the model adds them."""
    scale = round(share * SHARE_SCALE)
    lowest = sum(min(0, value * top) for (value, _cat, _one), top in zip(terms, columns))
    highest = sum(max(0, value * top) for (value, _cat, _one), top in zip(terms, columns))
    total = types.SimpleNamespace(terms=terms, low=base, lowest=lowest, highest=highest)
    low, high = base + lowest, base + highest
    most = scale * high // SHARE_SCALE
    recorder = Recorder()
    build = types.SimpleNamespace(problem=recorder)
    WakfuBuild._conversion_rows(build, NAME, INDICATOR, total, scale, most, low, high)
    return recorder.rows, scale, most, total


def holds(row, values):
    terms, sense, rhs = row
    return sum(coefficient * values[variable] for coefficient, variable in terms) <= rhs


def feasible(rows, assignment, converted, on):
    values = dict(assignment, **{VALUE: converted, ON: on})
    return all(holds(row, values) for row in rows.values())


class TheConversionRowsUseTheReducedFractionTests(SimpleTestCase):
    TERMS = [(7, 'worn', 'a'), (-5, 'worn', 'b')]
    COLUMNS = (4, 3)

    def coefficients(self, name, rows):
        return {variable: coefficient for coefficient, variable in rows[name][0]}

    def test_a_half_is_one_over_two(self):
        rows, _scale, most, _total = rows_of(0.5, [(3, 'worn', 'a')], 10, (4,))
        up = self.coefficients('convert_v_up', rows)
        self.assertEqual({VALUE: 2, 'worn_a': -3, ON: 0}, up)
        down = self.coefficients('convert_v_down', rows)
        self.assertEqual(-2, down[VALUE])
        self.assertEqual(3, down['worn_a'])
        self.assertEqual(11, most)

    def test_thirty_seven_hundredths_is_thirty_seven_over_one_hundred(self):
        rows, _scale, _most, _total = rows_of(0.37, [(3, 'worn', 'a')], 10, (4,))
        up = self.coefficients('convert_v_up', rows)
        self.assertEqual(100, up[VALUE])
        self.assertEqual(-111, up['worn_a'])
        self.assertEqual(37 * 10, rows['convert_v_up'][2])

    def test_no_coefficient_or_bound_reaches_the_share_scale_times_the_total(self):
        rows, _scale, _most, _total = rows_of(0.37, self.TERMS, 900, self.COLUMNS)
        biggest = max(abs(coefficient) for terms, _sense, rhs in rows.values()
                      for coefficient, _variable in terms)
        self.assertLess(biggest, 10 ** 5)
        self.assertLess(max(abs(rhs) for _terms, _sense, rhs in rows.values()), 10 ** 5)

    def test_a_term_that_is_not_a_whole_number_keeps_the_unreduced_rows(self):
        rows, _scale, _most, _total = rows_of(0.5, [(0.5, 'worn', 'a')], 10, (4,))
        self.assertEqual(SHARE_SCALE, self.coefficients('convert_v_up', rows)[VALUE])


class TheConversionRowsForceTheFlooredAmountTests(SimpleTestCase):
    SHARES = (0.01, 0.37, 0.5, 0.333333, 0.123456, 0.999999, 1.0)
    TERMS = [(7, 'worn', 'a'), (-5, 'worn', 'b')]
    COLUMNS = (4, 3)

    def check(self, share, base):
        rows, scale, most, total = rows_of(share, self.TERMS, base, self.COLUMNS)
        low = total.low + total.lowest
        seen = set()
        for a, b in itertools.product(range(self.COLUMNS[0] + 1), range(self.COLUMNS[1] + 1)):
            amount = base + 7 * a - 5 * b
            seen.add(amount)
            assignment = {'worn_a': a, 'worn_b': b}
            allowed = [v for v in range(most + 1) if feasible(rows, assignment, v, 0)]
            self.assertEqual([0], allowed, (share, base, amount, 'indicator off'))
            allowed = [v for v in range(most + 1) if feasible(rows, assignment, v, 1)]
            if amount >= 0:
                self.assertEqual([scale * amount // SHARE_SCALE], allowed,
                                 (share, base, amount))
        return low, seen

    def test_the_amount_is_the_floor_of_the_share_for_every_total_from_below_zero(self):
        for share in self.SHARES:
            for base in (-10, 0, 12, 61, 400):
                with self.subTest(share=share, base=base):
                    low, seen = self.check(share, base)
                    if base == -10:
                        self.assertLess(low, 0)
                        self.assertTrue(any(amount < 0 for amount in seen))
                        self.assertTrue(any(amount > 0 for amount in seen))
