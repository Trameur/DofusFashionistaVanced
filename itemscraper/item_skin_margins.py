# -*- coding: utf-8 -*-
"""How big a lead over the runner up a skin match needs before it is trusted.

Set from item_skin_eval.json, the hand-labelled sample. The first cut used 32
pairs and read weapons as a coin flip at any lead, so their floor went to 0.20.
The sample now holds 96 pairs, 44 of them weapons, and says otherwise: weapons
are right 84% of the time at any lead and 91% from 0.02. The old floor kept one
weapon in 44, which is why under a third of them had art.

The other three keep their floors: nine labelled hats and ten shields are too
few to move a number on.

A floor on the score itself was measured and turned down. It does separate
(right matches sit at 0.711, wrong ones at 0.653) and a 0.65 floor lifts
precision from 86% to 91%, but it drops 302 of the 1127 items, mostly weapons,
and it rests on ten labelled failures. That is the same thin evidence that set
the 0.20 weapon floor in the first place. A wrong match draws a different
weapon the reader can hide; a rejected one draws nothing at all.
"""
MIN_MARGIN = {'Cloak': 0.02, 'Hat': 0.10, 'Shield': 0.05, 'Weapon': 0.02}
