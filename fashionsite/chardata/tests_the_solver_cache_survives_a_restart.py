# -*- coding: utf-8 -*-
"""The solver cache key must be the same in the next process, or it is not one.

DatabaseSolutionMemory stores its key in a BigIntegerField and looks solves up
by it. That only works if the key can be computed again later. It could not:
`ModelInput.__hash__` builds a tuple of strings -- the game version, the class,
the stat names -- and `hash()` of a str is randomised per process since Python
3.3, with PYTHONHASHSEED set nowhere.

So every solve written before a restart became unreachable, and the two gunicorn
workers never shared one. The dashboard shows what that costs: 391 hits for
2 779 misses in the week of 24 August, steady between 11.7% and 12.3% since
March.

The second test is the one that gives the first its meaning: it runs the OLD
scheme in the same two subprocesses and demands that it disagree with itself.
Without it, a green suite would prove only that the machine is deterministic.
"""
import json
import os
import subprocess
import sys

from django.test import SimpleTestCase

from fashionistapulp.model import ModelInput, _stable_digest

PULP = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), 'fashionistapulp')

#: A value of the same shape as a real cache key: strings at several depths,
#: inside dicts, which is exactly what hash randomisation moves. Kept
#: JSON-round-trippable because that is how it reaches the subprocess -- an
#: integer dict key would come back as a string and the two sides would be
#: hashing different values, which is a fault in the harness and reads exactly
#: like a fault in the code. Integer keys get their own in-process test below.
SAMPLE = ['dofus3', 200, {'Vitality': 100, 'Strength': 50},
          {'AP': 12, 'MP': 6}, None, {'hat': 42}, ['a', 'b'],
          {'Vitality': 1.0}, {'ap': True}, 'Cra', 5, ['ring'],
          {'7': {'Vitality': 3}}]

_SCRIPT = '''
import json, sys
sys.path.insert(0, %r)
from fashionistapulp.model import _stable_digest
valeur = json.loads(sys.argv[1])
ancien = (valeur[0], valeur[9], frozenset(valeur[2].items()))
print(json.dumps({'stable': _stable_digest(valeur), 'ancien': hash(ancien)}))
''' % PULP


def _in_a_fresh_process(value):
    env = dict(os.environ)
    env['PYTHONHASHSEED'] = 'random'      # le defaut, rendu explicite
    out = subprocess.run([sys.executable, '-c', _SCRIPT, json.dumps(value)],
                         capture_output=True, env=env, cwd=PULP)
    ligne = [l for l in out.stdout.decode('utf-8', 'replace').splitlines()
             if l.startswith('{')]
    assert ligne, out.stderr.decode('utf-8', 'replace')[-400:]
    return json.loads(ligne[-1])


class TheSolverCacheSurvivesARestart(SimpleTestCase):

    def test_the_key_is_the_same_in_another_process(self):
        ici = _stable_digest(SAMPLE)
        for _ in range(3):
            self.assertEqual(_in_a_fresh_process(SAMPLE)['stable'], ici)

    def test_the_old_scheme_disagrees_with_itself(self):
        """The control. If this ever passes, the harness stopped measuring
        anything and the test above is worth nothing."""
        vus = {_in_a_fresh_process(SAMPLE)['ancien'] for _ in range(4)}
        self.assertGreater(len(vus), 1,
                           'hash randomisation is off here, so the test above '
                           'proves nothing about a real worker')

    def test_the_key_fits_the_column(self):
        """SolutionMemory.input_hash is a BigIntegerField: signed 64 bits."""
        for value in (SAMPLE, ['x'], [], [{'a': None}]):
            key = _stable_digest(value)
            self.assertIsInstance(key, int)
            self.assertGreaterEqual(key, -2 ** 63)
            self.assertLess(key, 2 ** 63)

    def test_a_different_input_is_a_different_key(self):
        base = _stable_digest(SAMPLE)
        for i in range(len(SAMPLE)):
            autre = list(SAMPLE)
            autre[i] = 'change'
            self.assertNotEqual(_stable_digest(autre), base,
                                'field %d does not reach the key' % i)

    def test_an_integer_key_is_not_its_string(self):
        """A dict keyed by item id must not collide with one keyed by its
        text: the solver's stat_overrides are keyed by integer item ids."""
        self.assertNotEqual(_stable_digest([{7: 'a'}]),
                            _stable_digest([{'7': 'a'}]))

    def test_order_does_not_change_the_key(self):
        """Two dicts that differ only in insertion order are one input."""
        a = _stable_digest([{'Vitality': 1, 'Strength': 2}, {'b', 'a'}])
        b = _stable_digest([{'Strength': 2, 'Vitality': 1}, {'a', 'b'}])
        self.assertEqual(a, b)

    def test_the_cache_asks_for_the_stable_key(self):
        """The wiring, not just the helper: a key nothing calls is decoration."""
        import inspect

        from chardata.solution_memory import DatabaseSolutionMemory
        for method in (DatabaseSolutionMemory.get, DatabaseSolutionMemory.put):
            source = inspect.getsource(method)
            self.assertIn('cache_key()', source)
            self.assertNotIn('__hash__()', source)

    def test_a_model_input_produces_a_key(self):
        entree = ModelInput(200, {'Vitality': 100}, {'AP': 12}, {},
                            [], {'Vitality': 1}, {}, 'Cra', 5)
        self.assertIsInstance(entree.cache_key(), int)
        self.assertEqual(entree.cache_key(), entree.cache_key())
