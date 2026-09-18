"""Test runner that isolates the process-global current game version.

The game version is stored in a thread-local in ``fashionistapulp.structure``
and read by code under test (for example ``evolve_result_item`` formats a damage
line from it). Many tests call ``set_current_game_version('retro'/'touch'/...)``
and never reset it, so the version leaks into whatever test runs next in the
same thread and the outcome depends on test order.

Resetting to the default before every test (in ``startTest``) gives each test a
known 'dofus3' baseline, so a test only ever sees the version it sets itself.
This is a single, order-proof fix; individual tests no longer need their own
version-pinning setUp.

It also makes the suite faster. Django hands whole test classes to its worker
processes, so the suite can never finish before its heaviest class, and it
finishes later still when that class is handed out last. Measured 2026-09-18
on the 24-core machine: 383 s with 4 workers, 196 s with 24, while the work
summed 2944 s and the heaviest class took 131 s. So:

- without --parallel, one worker per core (DJANGO_TEST_PROCESSES caps it);
- classes start heaviest first, by the seconds test_weights.json gives them
  (spreading a heavy class one test per worker was tried: no faster, the cores
  were already full);
- --quick leaves out every class of QUICK_LIMIT seconds or more, for the edit
  and check loop; the full suite still runs before a push;
- --save-weights rewrites test_weights.json from the run it ends.

With all of it the full suite took 174 s, and --quick 73 s for 2647 of the
3080 tests.
"""
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
    """What one test leaves behind in its process. The cache matters since the
    ids of a test database start over at 1: a cache_page answer for
    /api/v1/shared-builds/1/ stored by one test was served to the next."""
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
    """Hands the heaviest classes out first, so none starts last, and resets
    each worker between tests like the serial runner does."""

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
