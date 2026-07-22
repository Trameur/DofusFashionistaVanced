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
"""
import unittest

from django.test.runner import DiscoverRunner

from fashionistapulp.structure import set_current_game_version


class ResetGameVersionRunner(DiscoverRunner):
    def get_resultclass(self):
        base = super().get_resultclass() or unittest.TextTestResult

        class ResetGameVersionResult(base):
            def startTest(self, test):
                set_current_game_version('dofus3')
                super().startTest(test)

        return ResetGameVersionResult
