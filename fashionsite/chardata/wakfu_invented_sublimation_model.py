"""The invented Wakfu catalogue of the rune tests, with sublimations the model can place.

Not a test module: the tests import it. SublimationModelCase swaps the generated block for
an invented one (wakfu_invented_sublimations.use_block) and solves with the sublimation
and passive arguments.
"""

from fashionistapulp import wakfu_legality

from chardata.tests_wakfu_runes_enter_every_total_and_gate import (
    BLUE, GREEN, RED, ARuneCase, socketed)
from chardata.tests_wakfu_solve_obeys_every_rule_on_invented_items import (
    ALPHA, BOOTS, HELMET, LEVEL, item)
from chardata.wakfu_invented_sublimations import block, state, use_block

FERO_HELM, NARROW_LEGS, GATE_HELM = 1501, 1502, 1503

__all__ = ['BLUE', 'GREEN', 'RED', 'ALPHA', 'LEVEL', 'FERO_HELM', 'NARROW_LEGS', 'GATE_HELM',
           'SublimationModelCase', 'block', 'state', 'use_block']


class SublimationModelCase(ARuneCase):
    """The rune catalogue with a ferocity helmet and a boots piece of two sockets only."""

    @classmethod
    def catalogue(cls):
        narrow = socketed(item(NARROW_LEGS, BOOTS, 'Narrow Legs', hp=5000))
        narrow['shard_slots'] = [1, 2]
        extra = [socketed(item(FERO_HELM, HELMET, 'Fero Helm', hp=1000, ferocity=20)), narrow]
        return super().catalogue() + extra

    def invent(self, states=None, sublimations=None, gear=None, passives=None):
        return use_block(self, block(states, sublimations, gear, passives))

    def sublimate(self, weights, sublimations='optimistic', passives=None, runes=None,
                  class_id=ALPHA, forbidden=(), **options):
        """(build, set) of a solve with the sublimation and passive arguments."""
        from fashionistapulp.wakfu_model import WakfuBuild
        build = WakfuBuild(self.structure, options.pop('level', LEVEL), weights, forbidden,
                           class_id=class_id, runes=runes, sublimations=sublimations,
                           passives=passives, **options)
        return build, build.build().solve()

    def rules_broken(self, worn, class_id=ALPHA, level=LEVEL, **options):
        found = wakfu_legality.violations(self.structure, level, worn, class_id=class_id,
                                          runes=worn.runes, **options)
        return [rule for rule, _text in found]

    def assert_objective_is_read_back(self, build, worn):
        self.assertAlmostEqual(build.problem.objective_value, build.objective_of(worn),
                               delta=1e-6)

    def columns(self, build, prefix):
        return [name for name in build.problem.variable_names() if name.startswith(prefix)]
