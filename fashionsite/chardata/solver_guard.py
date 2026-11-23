# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The guard solver tests use: skip when pulp is not installed, fail loudly when its solver cannot be reached."""
import functools
import time
import unittest

SKIP_MESSAGE = 'no pulp solver available'
ATTEMPTS = 3
PAUSE_SECONDS = 0.2


class PulpSolverUnreachable(AssertionError):
    """pulp is installed but the solver the site solves with could not be reached."""


def pulp_installed():
    """True when pulp can be imported."""
    try:
        import pulp
    except ImportError:
        return False
    return True


def pulp_solver_available():
    """False only when pulp is not installed; raises PulpSolverUnreachable after retries when its solver is missing."""
    if not pulp_installed():
        return False
    failure = None
    for attempt in range(ATTEMPTS):
        try:
            from fashionistapulp.lpproblem import SOLVER
            if SOLVER is not None and SOLVER.available():
                return True
            failure = 'the solver reports itself unavailable'
        except Exception as error:
            failure = '%s: %s' % (type(error).__name__, error)
        if attempt + 1 < ATTEMPTS:
            time.sleep(PAUSE_SECONDS)
    raise PulpSolverUnreachable(
        'pulp is installed but its solver could not be reached after %d attempts (%s); '
        'this is not a skip, the solver tests cannot vouch for the build' % (ATTEMPTS, failure))


def pulp_solver_required(target):
    """Skip a test or class when pulp is not installed, otherwise check the solver as the test starts."""
    if not pulp_installed():
        return unittest.skip(SKIP_MESSAGE)(target)
    if isinstance(target, type):
        original = target.setUp

        @functools.wraps(original)
        def set_up(self, *args, **kwargs):
            pulp_solver_available()
            return original(self, *args, **kwargs)

        target.setUp = set_up
        return target

    @functools.wraps(target)
    def wrapper(*args, **kwargs):
        pulp_solver_available()
        return target(*args, **kwargs)

    return wrapper
