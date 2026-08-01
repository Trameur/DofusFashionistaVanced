# -*- coding: utf-8 -*-
"""How big a lead over the runner up a skin match needs before it is trusted.

Set from item_skin_eval.json, the hand-labelled sample. The first cut used 32
pairs and read weapons as a coin flip at any lead, so their floor went to 0.20.
The sample now holds 96 pairs, 44 of them weapons, and says otherwise: weapons
are right 84% of the time at any lead and 91% from 0.02. The old floor kept one
weapon in 44, which is why under a third of them had art.

The other three keep their floors: nine labelled hats and ten shields are too
few to move a number on.
"""
MIN_MARGIN = {'Cloak': 0.02, 'Hat': 0.10, 'Shield': 0.05, 'Weapon': 0.02}
