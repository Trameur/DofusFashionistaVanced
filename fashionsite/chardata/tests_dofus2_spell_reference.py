# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The Dofus 2 page must not lose spells the model already carries.

`_dofus2_damage_spells` filters the generated block against
`spell_reference/dofus2.json`, and that filter was written when the block held
Dofus 3 content bootstrapped for want of 2.73 spell levels. The block is
generated from 2.73 now, so the reason is gone, but the filter stayed and found
itself a second justification: that the breeds table lists retired spells.

Measured on 2026-08-27, that second justification was false and expensive. The
filter dropped **265 of 543 spells**, about half of every class, damage tables
and all. All 265 were the second member of a `spell_variants.json` pair, none
lay outside one, and every one of them had ranks and an access level in the
2.73 archive itself. They were absent from the reference only because
`read_dofus2` walked `breedSpellsId` without following the variants, so the
reference named 418 spells where a 2.73 player casts 836.

The source is fixed. This asserts the consequence, because a docstring saying
"the filter drops nothing today" is exactly the kind of claim our own next
commit turns false without a word.
"""
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
        """A class must not quietly lose half its list.

        The count test above catches a spell dropped anywhere; this one says
        where. Half a class is the shape the defect took, and the shape is what
        a reader recognises in a failure message.
        """
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
