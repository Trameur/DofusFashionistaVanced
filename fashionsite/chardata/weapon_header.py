# -*- coding: utf-8 -*-
"""AP cost and critical rate of a weapon, worded the same way in the
encyclopedia and the picker.

Retro states the rate the way the game does, one hit in X: its data holds 30,
50, even 200, and -1 for a weapon that cannot crit. Dofus 2 turned the same
field into a percentage and every later version kept that.
"""
from django.utils.translation import gettext as _


def format_weapon_header(game_version, weapon_type, ap, crit_chance, crit_bonus):
    retro = game_version == 'retro'
    values = {'weapon_type': weapon_type, 'AP': ap,
              'crit_chance': crit_chance, 'crit_bonus': crit_bonus}

    has_crit = (crit_chance is not None and crit_bonus is not None
                and not (retro and (crit_chance <= 0 or weapon_type is None)))
    if not has_crit:
        if weapon_type is None:
            return _('AP: %(AP)d') % values
        return _('(%(weapon_type)s) AP: %(AP)d') % values

    if retro:
        return _('(%(weapon_type)s) AP: %(AP)d / CH: 1/%(crit_chance)d (+%(crit_bonus)d)') % values
    if weapon_type is None:
        return _('AP: %(AP)d / CH: %(crit_chance)d%% (+%(crit_bonus)d)') % values
    return _('(%(weapon_type)s) AP: %(AP)d / CH: %(crit_chance)d%% (+%(crit_bonus)d)') % values
