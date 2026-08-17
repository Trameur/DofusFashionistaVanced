# -*- coding: utf-8 -*-
"""AP cost, critical rate and heal line of a weapon, worded the same way in the
encyclopedia and the picker.

Retro states the rate the way the game does, one hit in X: its data holds 30,
50, even 200, and -1 for a weapon that cannot crit. Dofus 2 turned the same
field into a percentage and every later version kept that.
"""
from django.utils.translation import gettext as _

# Modern Dofus types the weapon heal by element and says so: the Hidsad Bow reads
# "12 to 42 Fire heals". Retro and Touch call the same line "PDV rendus", and
# their effect carries no element field at all. The stored element is what scales
# the roll, Intelligence in every version, so it must not be printed where the
# game keeps quiet about it.
_ELEMENTLESS_HEAL_VERSIONS = {'retro', 'touch'}


def format_weapon_header(game_version, weapon_type, ap, crit_chance, crit_bonus):
    """The header line of a weapon's damage block, empty when it says nothing.

    Four Retro items are typed as weapons while the game's own files hold -1 for
    every weapon parameter, so their AP cost is unknown. Writing an unknown cost
    as a number answered 500 on the item picker, so it is left out instead.
    """
    retro = game_version == 'retro'
    values = {'weapon_type': weapon_type, 'AP': ap,
              'crit_chance': crit_chance, 'crit_bonus': crit_bonus}

    has_crit = (crit_chance is not None and crit_bonus is not None
                and not (retro and (crit_chance <= 0 or weapon_type is None)))
    if ap is None:
        segments = []
        if weapon_type is not None:
            segments.append('(%(weapon_type)s)' % values)
        if has_crit:
            segments.append(
                _('CH: 1/%(crit_chance)d (+%(crit_bonus)d)') % values if retro
                else _('CH: %(crit_chance)d%% (+%(crit_bonus)d)') % values)
        return ' '.join(segments)
    if not has_crit:
        if weapon_type is None:
            return _('AP: %(AP)d') % values
        return _('(%(weapon_type)s) AP: %(AP)d') % values

    if retro:
        return _('(%(weapon_type)s) AP: %(AP)d / CH: 1/%(crit_chance)d (+%(crit_bonus)d)') % values
    if weapon_type is None:
        return _('AP: %(AP)d / CH: %(crit_chance)d%% (+%(crit_bonus)d)') % values
    return _('(%(weapon_type)s) AP: %(AP)d / CH: %(crit_chance)d%% (+%(crit_bonus)d)') % values


def format_heal_hit(game_version, min_dam, max_dam, element, localized_elements):
    values = {'min': min_dam, 'max': max_dam}
    if game_version in _ELEMENTLESS_HEAL_VERSIONS or element not in localized_elements:
        return _('%(min)d to %(max)d (HP restored)') % values
    values['element'] = localized_elements[element]
    return _('%(min)d to %(max)d %(element)s heals') % values


def format_weapon_hit(game_version, hit, localized_elements):
    """One line of a weapon's damage block.

    The solution page has worded these for years; the encyclopedia had only the
    elemental cases and printed the internal token for the rest, so a Treestaff
    read "1 to 1 (removes_ap)" on its own page and "Removes 1 AP" in a build.
    """
    element = getattr(hit, 'element', None)
    lo, hi = hit.min_dam, hit.max_dam
    span = {'min': lo, 'max': hi}
    flat = lo == hi

    if hit.steals:
        return _('%(min)d to %(max)d (%(element)s steal)') % {
            'min': lo, 'max': hi,
            'element': localized_elements.get(element, element)}
    if hit.heals:
        return format_heal_hit(game_version, lo, hi, element, localized_elements)
    if element == 'pushes':
        return (_('Pushes %(cells)d cells') % {'cells': lo} if flat
                else _('Pushes %(min)d to %(max)d cells') % span)
    if element == 'attracts':
        return (_('Attracts %(cells)d cells') % {'cells': lo} if flat
                else _('Attracts %(min)d to %(max)d cells') % span)
    if element == 'advances':
        return (_('Advances %(cells)d cells') % {'cells': lo} if flat
                else _('Advances %(min)d to %(max)d cells') % span)
    if element == 'steals':
        return (_('Steals %(kamas)d kamas') % {'kamas': lo} if flat
                else _('Steals %(min)d to %(max)d kamas') % span)
    if element == 'steals_mp':
        return (_('Steals %(mp)d MP') % {'mp': lo} if flat
                else _('Steals %(min)d to %(max)d MP') % span)
    if element == 'removes_ap':
        return (_('Removes %(ap)d AP') % {'ap': lo} if flat
                else _('Removes %(min)d to %(max)d AP') % span)
    if element == 'removes_mp':
        return (_('Removes %(mp)d MP') % {'mp': lo} if flat
                else _('Removes %(min)d to %(max)d MP') % span)
    return _('%(min)d to %(max)d (%(element)s)') % {
        'min': lo, 'max': hi,
        'element': localized_elements.get(element, element)}
