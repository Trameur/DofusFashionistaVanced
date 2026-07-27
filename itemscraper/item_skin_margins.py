# -*- coding: utf-8 -*-
"""How big a lead over the runner up a skin match needs before it is trusted.

Set from 32 hand-labelled pairs: hats go wrong below 0.10, weapons are a coin
flip at any lead so their floor is high.
"""
MIN_MARGIN = {'Cloak': 0.02, 'Hat': 0.10, 'Shield': 0.05, 'Weapon': 0.20}
