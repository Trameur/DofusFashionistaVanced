"""Test runner: resets the game version before every test and hands the heaviest classes out first, one worker per core."""
import json
import os
import re
import unittest

from django.core.cache import caches
from django.test.runner import (DiscoverRunner, ParallelTestSuite,
                                RemoteTestResult, RemoteTestRunner,
                                get_max_test_processes, iter_test_cases)

from fashionistapulp.structure import set_current_game_version

WEIGHTS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            'test_weights.json')
QUICK_LIMIT = 10.0
_TEST_ID = re.compile(r'\(([\w.]+)\.\w+\)')


def _load_weights():
    try:
        with open(WEIGHTS_PATH, encoding='utf-8') as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return {}


def _class_of(test):
    return '%s.%s' % (type(test).__module__, type(test).__qualname__)


def _reset_between_tests():
    set_current_game_version('dofus3')
    for cache in caches.all():
        cache.clear()


class ResettingRemoteTestResult(RemoteTestResult):
    def startTest(self, test):
        _reset_between_tests()
        super().startTest(test)


class ResettingRemoteTestRunner(RemoteTestRunner):
    resultclass = ResettingRemoteTestResult


class WeightedParallelTestSuite(ParallelTestSuite):

    runner_class = ResettingRemoteTestRunner

    def __init__(self, subsuites, *args, **kwargs):
        weights = _load_weights()

        def weight(subsuite):
            first = next(iter(iter_test_cases(subsuite)), None)
            return weights.get(_class_of(first), 0.0) if first else 0.0

        super().__init__(sorted(subsuites, key=weight, reverse=True),
                         *args, **kwargs)


class ResetGameVersionRunner(DiscoverRunner):
    parallel_test_suite = WeightedParallelTestSuite

    def __init__(self, *args, quick=False, save_weights=False, **kwargs):
        if (not kwargs.get('parallel') and not kwargs.get('pdb')
                and not kwargs.get('debug_mode')):
            kwargs['parallel'] = get_max_test_processes()
        super().__init__(*args, **kwargs)
        self.quick = quick
        self.save_weights = save_weights

    @classmethod
    def add_arguments(cls, parser):
        super().add_arguments(parser)
        parser.add_argument(
            '--quick', action='store_true',
            help='Leave out the test classes that take %d s or more.'
                 % QUICK_LIMIT)
        parser.add_argument(
            '--save-weights', action='store_true',
            help='Rewrite test_weights.json from the durations of this run.')

    def load_tests_for_label(self, label, discover_kwargs):
        tests = super().load_tests_for_label(label, discover_kwargs)
        if not self.quick:
            return tests
        weights = _load_weights()
        kept, left_out = [], set()
        for test in iter_test_cases(tests):
            if weights.get(_class_of(test), 0.0) >= QUICK_LIMIT:
                left_out.add(_class_of(test))
            else:
                kept.append(test)
        if left_out:
            self.log('Quick run: %d slow class(es) left out; run the full '
                     'suite before pushing.' % len(left_out))
        return self.test_suite(kept)

    def run_suite(self, suite, **kwargs):
        result = super().run_suite(suite, **kwargs)
        if self.save_weights:
            weights = {}
            for test_id, elapsed in getattr(result, 'collectedDurations', []):
                match = _TEST_ID.search(test_id)
                if match:
                    name = match.group(1)
                    weights[name] = round(weights.get(name, 0.0) + elapsed, 1)
            if weights:
                with open(WEIGHTS_PATH, 'w', encoding='utf-8') as handle:
                    json.dump(weights, handle, indent=1, sort_keys=True)
                    handle.write('\n')
                self.log('Saved the weights of %d classes to %s.'
                         % (len(weights), WEIGHTS_PATH))
        return result

    def get_resultclass(self):
        base = super().get_resultclass() or unittest.TextTestResult

        class ResetGameVersionResult(base):
            def startTest(self, test):
                _reset_between_tests()
                super().startTest(test)

        return ResetGameVersionResult
