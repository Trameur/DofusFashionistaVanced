from django.test import SimpleTestCase

from fashionistapulp import wakfu_legality, wakfu_sublimations


class AStateTheCheckerCountsMustBeReportedTests(SimpleTestCase):
    def report(self, level):
        return wakfu_sublimations.StateReport(1, 3, level, 'A', True, {'ferocity': 10})

    def rules(self, reported, computed):
        return [rule for rule, _text in wakfu_legality.state_violations(reported, computed)]

    def test_a_computed_state_the_report_omits_is_flagged(self):
        self.assertEqual([wakfu_legality.STACK],
                         self.rules({7: self.report(1)}, {7: self.report(1), 8: self.report(2)}))

    def test_equal_reports_are_not_flagged(self):
        self.assertEqual([], self.rules({7: self.report(1)}, {7: self.report(1)}))

    def test_a_reported_state_the_checker_does_not_compute_is_flagged(self):
        self.assertEqual([wakfu_legality.STACK], self.rules({7: self.report(1)}, {}))
