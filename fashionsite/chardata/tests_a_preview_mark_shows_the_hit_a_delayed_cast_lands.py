# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The 3.8 preview mark still shows the hit a spell's delayed recast lands next turn."""
from django.test import SimpleTestCase

RAINING_ARROWS = 32431


def _spell(game_version, spell_id):
    from chardata.spell_buffs import get_damage_spells_for_version
    return next(spell for spells in get_damage_spells_for_version(game_version).values()
                for spell in spells if spell.spell_id == spell_id)


class APreviewMarkShowsTheDelayedHitTests(SimpleTestCase):

    def test_raining_arrows_keeps_its_next_turn_hit_on_the_beta(self):
        live, beta = _spell('dofus3', RAINING_ARROWS), _spell('beta', RAINING_ARROWS)
        self.assertTrue(getattr(live, 'delayed', None))
        self.assertEqual(live.delayed, beta.delayed)
        self.assertEqual(len(live.effects.non_crit_ranges), len(beta.effects.non_crit_ranges))
