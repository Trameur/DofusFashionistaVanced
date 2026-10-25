import types

from django.test import SimpleTestCase

from chardata.management.commands.wakfu_build import Command


def result(status, model=None, settled=False):
    return types.SimpleNamespace(status=status, model=model, settled=settled)


class TheCommandSaysProvenOnlyForASingleSolveTests(SimpleTestCase):
    def test_a_single_solve_that_ran_to_the_end_is_proven_best(self):
        from fashionistapulp.wakfu_model import PROVEN
        self.assertEqual('proven best', Command.solve_line(result(PROVEN)))

    def test_rounds_that_settled_say_settled_and_never_proven(self):
        from fashionistapulp.wakfu_model import PROVEN
        line = Command.solve_line(result(PROVEN, model=object(), settled=True))
        self.assertEqual('settled', line)
        self.assertNotIn('proven', line)

    def test_rounds_that_did_not_settle_are_not_called_proven(self):
        from fashionistapulp.wakfu_model import PROVEN
        line = Command.solve_line(result(PROVEN, model=object(), settled=False))
        self.assertEqual('last round solved to the end', line)
        self.assertNotIn('proven', line)

    def test_a_crashed_round_is_named_instead_of_saying_the_last_round_ended(self):
        from fashionistapulp.wakfu_model import PROVEN
        crashed = types.SimpleNamespace(crashed=((2, 'exit code'),))
        line = Command.solve_line(result(PROVEN, model=crashed, settled=False))
        self.assertEqual('a round crashed, the best set so far is kept', line)
        self.assertNotIn('proven', line)
        self.assertNotIn('to the end', line)

    def test_a_model_with_no_crashed_round_keeps_the_last_round_line(self):
        from fashionistapulp.wakfu_model import PROVEN
        clean = types.SimpleNamespace(crashed=())
        self.assertEqual('last round solved to the end',
                         Command.solve_line(result(PROVEN, model=clean, settled=False)))

    def test_the_stepwise_and_time_limit_statuses_keep_their_own_words(self):
        from fashionistapulp.wakfu_model import STEPWISE, TIME_LIMIT
        self.assertEqual('solved in steps', Command.solve_line(result(STEPWISE)))
        self.assertEqual('best set found within the time limit',
                         Command.solve_line(result(TIME_LIMIT)))
