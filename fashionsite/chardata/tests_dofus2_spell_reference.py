# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The Dofus 2 page's spell filter must not drop any spell the generated model carries."""
from django.test import SimpleTestCase

from chardata.spell_buffs import get_damage_spells_for_version


class Dofus2SpellReferenceTests(SimpleTestCase):

    def test_the_reference_filter_drops_no_spell_the_model_carries(self):
        from fashionistapulp.dofus_constants_dofus2 import (
            DAMAGE_SPELLS as GENERATED)

        served = get_damage_spells_for_version('dofus2')
        carried = sum(len(spells) for spells in GENERATED.values())
        self.assertGreater(carried, 400,
                           'the generated block is nearly empty: the question '
                           'cannot be asked of it, so a pass here would mean '
                           'nothing')

        lost = []
        for char_class, spells in sorted(GENERATED.items()):
            kept = {spell.name for spell in served.get(char_class, [])}
            for spell in spells:
                if spell.name not in kept:
                    lost.append('%s / %s' % (char_class, spell.name))
        self.assertEqual(sorted(lost), [],
                         'the Dofus 2 page would serve fewer spells than the '
                         'model holds, and the missing ones vanish with their '
                         'damage tables')

    def test_every_class_keeps_the_shape_the_reference_gives_it(self):
        """Says which class lost spells; the count test above only says that one did."""
        from fashionistapulp.dofus_constants_dofus2 import (
            DAMAGE_SPELLS as GENERATED)

        served = get_damage_spells_for_version('dofus2')
        self.assertGreater(len(GENERATED), 15,
                           'almost no class read: the import is wrong')
        halved = []
        for char_class, spells in sorted(GENERATED.items()):
            before, after = len(spells), len(served.get(char_class, []))
            if before and after < before:
                halved.append('%s %d -> %d' % (char_class, before, after))
        self.assertEqual(halved, [])
