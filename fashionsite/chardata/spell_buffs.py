# -*- coding: utf-8 -*-

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

"""Server-side equivalent of the spells page "Fully Buff" button."""

from fashionistapulp.dofus_constants import DAMAGE_SPELLS

# Final-damage multipliers, not characteristics: no row in the solution summary.
_BUFF_STATS_WITHOUT_ROW = {'final', 'finalheals'}


def get_damage_spells_for_version(game_version):
    if game_version == 'retro':
        from fashionistapulp.dofus_constants_retro_spells import RETRO_DAMAGE_SPELLS
        return RETRO_DAMAGE_SPELLS
    if game_version == 'touch':
        from fashionistapulp.dofus_constants_touch_spells import TOUCH_DAMAGE_SPELLS
        return TOUCH_DAMAGE_SPELLS
    if game_version == 'beta':
        from fashionistapulp.dofus_constants_beta import DAMAGE_SPELLS as BETA_DAMAGE_SPELLS
        return BETA_DAMAGE_SPELLS
    if game_version == 'dofus2':
        from fashionistapulp.dofus_constants_dofus2 import DAMAGE_SPELLS as DOFUS2_DAMAGE_SPELLS
        return DOFUS2_DAMAGE_SPELLS
    return DAMAGE_SPELLS


def _spell_is_buff(spell):
    digest = spell.get_effects_digest()
    for level_dams in list(digest.non_crit_dams) + list(digest.crit_dams):
        for effect in level_dams:
            if 'buff' in effect.element:
                return True
    return False


def _decide_spell_level(level_req, char_level):
    """Highest spell-level index the character can cast (mirrors decideLevel)."""
    levels = len(level_req)
    if char_level < level_req[0] or levels == 1:
        return 0
    index = 0
    while index < levels - 1:
        if level_req[index] <= char_level < level_req[index + 1]:
            return index
        index += 1
    return index


def _is_double_buff_slot(spell, buff_spell_names):
    # A "second slot" linked spell shares its slot with the buff it links back
    # to; only the first one counts. is_linked == (rank, name).
    if spell.is_linked and spell.is_linked[0] == 2:
        return spell.is_linked[1] in buff_spell_names
    return False


def _buff_value(buff_scaling, stat, stacks, effect_max_dam):
    """Bonus a buff effect grants at full stacks (mirrors calculateBuffValue)."""
    stat_scaling = None
    if buff_scaling and buff_scaling.get('stats'):
        stat_scaling = buff_scaling['stats'].get(stat)
    if not stat_scaling:
        return stacks * effect_max_dam
    if stacks <= 0:
        return 0
    base = stat_scaling.get('base') or 0
    per_stack = stat_scaling.get('per_stack')
    if per_stack is None:
        per_stack = effect_max_dam
    effective = max(stacks - (buff_scaling.get('stack_offset') or 0), 0)
    max_effective = stat_scaling.get('max_effective')
    if max_effective is not None:
        effective = min(effective, max_effective)
    return base + effective * per_stack


def compute_full_buff_stats(char, game_version):
    """{stat_key: value} deltas if the character's class self-buffs are fully active.

    Category-restricted buffs (weapon- or spell-only Power, glyph/trap Power,
    final damage) have no plain stat row in the solution summary and are dropped.
    """
    spells_by_class = get_damage_spells_for_version(game_version)
    spells = spells_by_class.get(char.char_class, []) + spells_by_class.get('default', [])
    buff_spells = [spell for spell in spells if _spell_is_buff(spell)]
    buff_spell_names = {spell.name for spell in buff_spells}

    totals = {}
    for spell in buff_spells:
        if char.level < spell.level_req[0]:
            continue
        if _is_double_buff_slot(spell, buff_spell_names):
            continue
        digest = spell.get_effects_digest()
        crit_available = len(digest.crit_dams[0]) > 0
        dams = digest.crit_dams if crit_available else digest.non_crit_dams
        for effect in dams[_decide_spell_level(spell.level_req, char.level)]:
            if not effect.element.startswith('buff'):
                continue
            parts = effect.element.split('_')
            stat = parts[1]
            is_category_restricted = len(parts) > 2
            if is_category_restricted:
                continue
            if stat in _BUFF_STATS_WITHOUT_ROW:
                continue
            value = _buff_value(spell.buff_scaling, stat, spell.stacks, effect.max_dam)
            if stat == 'depow':
                stat, value = 'pow', -value
            if value:
                totals[stat] = totals.get(stat, 0) + value
    return totals
