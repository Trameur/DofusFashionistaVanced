# Copyright (C) 2020 The Dofus Fashionista
# 
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
# 
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

from django.utils.translation import gettext_lazy
from django.utils.translation import gettext as _
from django.utils.translation import pgettext


# A stat whose name the versions do not agree on. Dofus 3 calls the percent
# trap stat Trap Power and Dofus 2 Traps (Power), both characteristics; Retro's
# effect 226 is a plain percentage, "+X% de dommages aux pieges", so calling it
# Power there says the wrong thing about what it does. The catalogue carries
# the version as the context, and the version that says nothing keeps the
# default: pgettext returns the msgid untouched when the context is missing,
# so only the pairs listed here may go through it.
VERSION_STAT_NAMES = {
    ('retro', '% Trap Damage'),
    # Same argument one stat over, and it took longer to notice because this
    # one is a headline stat. Retro's effect 138 is "Augmente les dommages de
    # X%", a plain percentage, where Dofus 3 and Dofus 2 read "X Puissance", a
    # characteristic. Both land in the model's `pow`, which is right -- 1.29
    # adds that percentage to the characteristic in the same multiplier -- but
    # a Retro player reading "Power 10" on an item whose tooltip says
    # "Augmente les dommages de 10%" has no way to connect the two.
    ('retro', 'Power'),
}


def localized_stat_name(name, game_version=None):
    """The stat's name as the running version's own game words it."""
    if game_version is None:
        from fashionistapulp.structure import get_current_game_version
        game_version = get_current_game_version()
    if (game_version, name) in VERSION_STAT_NAMES:
        return pgettext(game_version, name)
    return _(name)


LOCALIZED_CHARACTER_CLASSES = {
    'Eniripsa': gettext_lazy('Eniripsa'),
    'Iop': gettext_lazy('Iop'),
    'Xelor': gettext_lazy('Xelor'),
    'Osamodas': gettext_lazy('Osamodas'),
    'Feca': gettext_lazy('Feca'),
    'Sacrier': gettext_lazy('Sacrier'),
    'Ecaflip': gettext_lazy('Ecaflip'),
    'Enutrof': gettext_lazy('Enutrof'),
    'Sram': gettext_lazy('Sram'),
    'Sadida': gettext_lazy('Sadida'),
    'Cra': gettext_lazy('Cra'),
    'Pandawa': gettext_lazy('Pandawa'),
    'Rogue': gettext_lazy('Rogue'),
    'Masqueraider': gettext_lazy('Masqueraider'),
    'Foggernaut': gettext_lazy('Foggernaut'),
    'Eliotrope': gettext_lazy('Eliotrope'),
    'Huppermage': gettext_lazy('Huppermage'),
    'Ouginak': gettext_lazy('Ouginak'),
    'Forgelance': gettext_lazy('Forgelance'),
}

LOCALIZED_ELEMENTS = {
    'fire': gettext_lazy('Fire'),
    'earth': gettext_lazy('Earth'),
    'neut': gettext_lazy('Neutral'),
    'water': gettext_lazy('Water'),
    'air': gettext_lazy('Air'),
    'best': gettext_lazy('Best element'),
}

OTHERS = {
    'project': gettext_lazy('project'),
    'min_stats_all_but_neut': _('Sum of all % Resists except neutral'),
    'min_stats_all': _('Sum of all % Resists'),
    'min_stats_all_lin': _('Sum of all Linear Resists'),
    'min_stats_all_lin_but_neut': _('Sum of all Linear Resists except neutral'),
}

LOCALIZED_STATS = {
    'HP': gettext_lazy('HP'),
    'Vitality': gettext_lazy('Vitality'),
    'Wisdom': gettext_lazy('Wisdom'),
    'Strength': gettext_lazy('Strength'),
    'Intelligence': gettext_lazy('Intelligence'),
    'Chance': gettext_lazy('Chance'),
    'Agility': gettext_lazy('Agility'),
    'Power': gettext_lazy('Power'),
    'AP': gettext_lazy('AP'),
    'MP': gettext_lazy('MP'),
    'Range': gettext_lazy('Range'),
    'Summons': gettext_lazy('Summons'),
    'Summon': gettext_lazy('Summon'),
    'Critical Hits': gettext_lazy('Critical Hits'),
    'Initiative': gettext_lazy('Initiative'),
    'Prospecting': gettext_lazy('Prospecting'),
    'Lock': gettext_lazy('Lock'),
    'Dodge': gettext_lazy('Dodge'),
    'AP Reduction': gettext_lazy('AP Reduction'),
    'MP Reduction': gettext_lazy('MP Reduction'),
    'AP Loss Resist': gettext_lazy('AP Loss Resist'),
    'MP Loss Resist': gettext_lazy('MP Loss Resist'),
    'Pushback Resist': gettext_lazy('Pushback Resist'),
    'Critical Resist': gettext_lazy('Critical Resist'),
    'Pods': gettext_lazy('Pods'),
    'Reflects': gettext_lazy('Reflects'),
    'Trap Damage': gettext_lazy('Trap Damage'),
    '% Trap Damage': gettext_lazy('% Trap Damage'),
    'Damage': gettext_lazy('Damage'),
    'Neutral Damage': gettext_lazy('Neutral Damage'),
    'Earth Damage': gettext_lazy('Earth Damage'),
    'Fire Damage': gettext_lazy('Fire Damage'),
    'Water Damage': gettext_lazy('Water Damage'),
    'Air Damage': gettext_lazy('Air Damage'),
    'Critical Damage': gettext_lazy('Critical Damage'),
    'Pushback Damage': gettext_lazy('Pushback Damage'),
    'Heals': gettext_lazy('Heals'),
    'Neutral Resist': gettext_lazy('Neutral Resist'),
    'Earth Resist': gettext_lazy('Earth Resist'),
    'Fire Resist': gettext_lazy('Fire Resist'),
    'Water Resist': gettext_lazy('Water Resist'),
    'Air Resist': gettext_lazy('Air Resist'),
    '% Melee Damage': gettext_lazy('% Melee Damage'),
    '% Ranged Damage': gettext_lazy('% Ranged Damage'),
    '% Weapon Damage': gettext_lazy('% Weapon Damage'),
    '% Spell Damage': gettext_lazy('% Spell Damage'),
    '% Melee Resist': gettext_lazy('% Melee Resist'),
    '% Ranged Resist': gettext_lazy('% Ranged Resist'),
    '% Weapon Resist': gettext_lazy('% Weapon Resist'),
}

LOCALIZED_WEAPON_TYPES = {
    'Hammer': gettext_lazy('Hammer'),
    'Axe': gettext_lazy('Axe'),
    'Shovel': gettext_lazy('Shovel'),
    'Staff': gettext_lazy('Staff'),
    'Sword': gettext_lazy('Sword'),
    'Dagger': gettext_lazy('Dagger'),
    'Bow': gettext_lazy('Bow'),
    'Wand': gettext_lazy('Wand'),
    'Pickaxe': gettext_lazy('Pickaxe'),
    'Scythe': gettext_lazy('Scythe'),
    'Lance': gettext_lazy('Lance'),
    'Crossbow': gettext_lazy('Crossbow'),
    'Magic Weapon': gettext_lazy('Magic Weapon'),
}
"""
OTHER_STRINGS = {
    'shield_violation': _("Can't equip a two handed weapon and a shield.")
}
"""