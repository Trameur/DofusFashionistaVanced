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

import logging

logger = logging.getLogger(__name__)

from django.utils.translation import gettext_lazy
from itertools import product, combinations
import pickle
from chardata.char_blobs import read_char_blob

from chardata.options import get_options, set_options
from fashionistapulp.dofus_constants import DAMAGE_TYPES, STAT_KEY_TO_NAME, MAIN_STATS


ALL_ASPECTS_LIST = ['str', 'int', 'cha', 'agi',
                    'vit', 'res', 'omni', 'wis',
                    'glasscannon', 'dam', 'crit', 'noncrit', 'heal',
                    'aprape', 'mprape',
                    'pvp', 'duel',
                    'trap', 'summon', 'pushback',
                    'pp', 'pods']

# Per-version overrides of the weight engine, which is tuned for Dofus 3.
# 'zero_stats': stats no item of that version's pool carries.
# 1.29 has no AP/MP dodge/withdrawal item stats: wisdom plays that role (10 wis = 1),
# and % resistance gear is rare there.
VERSION_WEIGHT_TUNING = {
    'dofus3': {},
    'beta': {},
    'dofus2': {
        'zero_stats': ('ref',),
    },
    'touch': {
        'zero_stats': ('ref', 'trapdam', 'trapdamper',
                       'permedam', 'perrandam', 'perweadam', 'perspedam',
                       'respermee', 'resperran', 'resperwea'),
    },
    'retro': {
        'zero_stats': ('cridam', 'apred', 'mpred', 'apres', 'mpres',
                       'lock', 'pshdam', 'pshres', 'crires',
                       'permedam', 'perrandam', 'perweadam', 'perspedam',
                       'respermee', 'resperran', 'resperwea'),
        'res_per_factor': lambda level_pct: 2 + 4 * level_pct,
        'wis_base': 4,
        'wis_rape_floor': 12,
        'init_mult': 3,
    },
}

ALL_ASPECTS = set(ALL_ASPECTS_LIST)

# The stat an aspect exists to raise, for the aspects tied to a stat a version
# may not have. Ticking one whose stat is zeroed changes nothing, so the wizard
# stops offering it. Keyed on the core stat alone: AP removal also leans on
# wisdom, and wisdom is alive everywhere, so asking for a whole tuple to be
# zeroed kept AP and MP removal on the Retro list although no Retro item grants
# either.
ASPECT_CORE_STAT = {
    'aprape': 'apred',
    'mprape': 'mpred',
    'pushback': 'pshdam',
    'trap': 'trapdam',
}


def inert_aspects(game_version):
    """The aspects that cannot change a build in this version."""
    zeroed = set(VERSION_WEIGHT_TUNING.get(game_version, {}).get('zero_stats', ()))
    return sorted(aspect for aspect, stat in ASPECT_CORE_STAT.items()
                  if stat in zeroed)

ASPECT_TO_NAME = {
    'str': gettext_lazy('Strength'),
    'int': gettext_lazy('Intelligence'),
    'cha': gettext_lazy('Chance'),
    'agi': gettext_lazy('Agility'),
    'vit': gettext_lazy('Vitality'),
    'res': gettext_lazy('Resists'),
    'omni': gettext_lazy('Omni-Elemental'),
    'wis': gettext_lazy('Leeching'),
    'dam': gettext_lazy('Linear Damage'),
    'crit': gettext_lazy('Critical Hits'),
    'noncrit': gettext_lazy('Avoid Critical Hits'),
    'heal': gettext_lazy('Linear Heals'),
    'aprape': gettext_lazy('AP Removal'),
    'mprape': gettext_lazy('MP Removal'),
    'pvp': gettext_lazy('Group PVP'),
    'duel': gettext_lazy('Duel PVP'),
    'trap': gettext_lazy('Traps'),
    'summon': gettext_lazy('Summons'),
    'pushback': gettext_lazy('Pushback'),
    'pp': gettext_lazy('Prospecting'),
    'pods': gettext_lazy('Pods'),
    'balanced': gettext_lazy('Balanced'),
    'glasscannon': gettext_lazy('Glass-Cannon'),
}

ASPECT_TO_SHORT_NAME = {
    'str': 'Str',
    'int': 'Int',
    'cha': 'Cha',
    'agi': 'Agi',
    'vit': 'Vit',
    'res': 'Res',
    'omni': 'Omni',
    'wis': 'Leecher',
    'dam': 'Dam',
    'crit': 'Crit',
    'noncrit': 'Non-Crit',
    'heal': 'Heals',
    'aprape': 'AP Red',
    'mprape': 'MP Red',
    'pvp': 'PVP',
    'duel': 'Duel',
    'trap': 'Traps',
    'summon': 'Summons',
    'pushback': 'Pushback',
    'pp': 'PP',
    'pods': 'Pods',
    'glasscannon': 'Glass Cannon',
}

RACE_TO_BUILD_PROFILE = {
    'default': {
        'endgame_mins': (11, 6), # Min AP and MP for level 200.
        'meleeness': 0.5, # Importance of melee attacks (0.0-1.0)
        'neutdam': 0.1, # Neutral damage w. as a fraction of earth damage w.
        'range_importance': 1.0, # Percentage of range required, relative to a highly range
                                 # dependent build.
        'apred_importance': 0.0, # Percentage of importance of AP Reduction.
        'mpred_importance': 0.0, # Percentage of importance of MP Reduction.
        'lock_importance': 0.4, # Percentage of importance of Lock.
        'dodge_importance': 0.4, # Percentage of importance of Dodge.
        'vit_importance': 0.5, # Percentage of importance of Vitality.
        'pshdam_importance': 0.0, # Percentage of importance of Pushback Damage.
        'heals_importance': 0.0, # Percentage of heals importance.
        'summons_are_important': False, # Whether summons weight should scale.
        'min_summons_low_level': 1, # Minimum summons at level 40-149.
        'min_summons_high_level': 1, # Minimum summons at level 150+.
        'pow_power': 1.0, # Percentage of how effective power is.
        'traps_are_important': False, # Whether trap damage matters.
        'earthdam': 0.0, # Importance of earth damage as multiple of Strength.
        'firedam': 0.0, # Importance of fire damage as multiple of Intelligence.
        'waterdam': 0.0, # Importance of water damage as multiple of Chance.
        'airdam': 0.0, # Importance of air damage as multiple of Agility.
        'cridam': 0.45, # Importance of Critical Damage for 1/2 crit chars relative to Damage.
        'fireres': 0.0, # Increase % of Linear Fire Resist
        '%fireres': 0.0, # Increase % of % Fire Resist
    },
    'Cra': {
        'all': {
            'mpred_importance': 0.6,
            'lock_importance': 0.1,
            'dodge_importance': 0.9,
            'vit_importance': 0.4,
            'pshdam_importance': 0.2,
            'meleeness': 0.0,
            'pow_power': 1.0,
        },
        'str': {
            'earthdam': 6.0,
        },
        'int': {
            'firedam': 6.0,
        },
        'cha': {
            'waterdam': 6.0,
        },
        'agi': {
            'airdam': 6.0,
        },
    },
    'Ecaflip': {
        'all': {
            'range_importance': 0.5,
            'cridam': 0.4,
            'vit_importance': 0.6,
            'pow_power': 1.0,
        },
        'str': {
            'earthdam': 6.0,
        },
        'int': {
            'firedam': 6.0,
        },
        'cha': {
            'waterdam': 6.0,
        },
        'agi': {
            'airdam': 6.0,
        },
    },
    'Eniripsa': {
        'all': {
            'apred_importance': 0.1,
            'mpred_importance': 0.1,
            'lock_importance': 0.1,
            'pshdam_importance': 0.05,
            'heals_importance': 0.05,
            'pow_power': 1.0,
        },
        'str': {
            'earthdam': 6.0,
        },
        'int': {
            'firedam': 6.0,
        },
        'cha': {
            'waterdam': 6.0,
        },
        'agi': {
            'airdam': 6.0,
        },
    },
    'Enutrof': {
        'all': {
            'apred_importance': 0.1,
            'mpred_importance': 1.0,
            'dodge_importance': 0.5,
            'min_summons_low_level': 2,
            'min_summons_high_level': 2,
            'pow_power': 1.0,
        },
        'str': {
            'earthdam': 6.0,
        },
        'int': {
            'firedam': 6.0,
        },
        'cha': {
            'waterdam': 6.0,
        },
        'agi': {
            'airdam': 6.0,
        },
    },
    'Feca': {
        'all': {
            'range_importance': 0.5,
            'neutdam': 1.0,
            'apred_importance': 0.2,
            'mpred_importance': 0.2,
            'lock_importance': 0.6,
            'cridam': 0.25,
            'pow_power': 1.0,
        },
        'str': {
            'earthdam': 6.0,
        },
        'int': {
            'firedam': 6.0,
        },
        'cha': {
            'waterdam': 6.0,
        },
        'agi': {
            'airdam': 6.0,
        },
    },
    'Foggernaut': {
        'all': {
            'range_importance': 0.5,
            'lock_importance': 0.2,
            'dodge_importance': 0.5,
            'vit_importance': 0.7,
            'heals_importance': 0.15,
            'mpred_importance': 0.1,
            'cridam': 0.3,
            'pow_power': 1.0,
        },
        'str': {
            'earthdam': 6.0,
        },
        'int': {
            'firedam': 6.0,
        },
        'cha': {
            'waterdam': 6.0,
        },
        'agi': {
            'airdam': 6.0,
        },
    },
    'Iop': {
        'all': {
            'range_importance': 0,
            'mpred_importance': 0.1,
            'lock_importance': 0.6,
            'pow_power': 1.0,
        },
        'str': {
            'earthdam': 6.0,
        },
        'int': {
            'firedam': 6.0,
        },
        'cha': {
            'waterdam': 6.0,
        },
        'agi': {
            'airdam': 6.0,
        },
    },
    'Masqueraider': {
        'all': {
            'meleeness': 0.8,
            'range_importance': 0.5,
            'mpred_importance': 0.1,
            'dodge_importance': 0.1,
            'vit_importance': 0.8,
            'pshdam_importance': 0.1,
            'pow_power': 1.0,
        },
        'str': {
            'earthdam': 6.0,
        },
        'int': {
            'firedam': 6.0,
        },
        'cha': {
            'waterdam': 6.0,
        },
        'agi': {
            'airdam': 6.0,
        },
    },
    'Osamodas': {
        'all': {
            'lock_importance': 0.5,
            'dodge_importance': 0.6,
            'vit_importance': 0.6,
            'range_importance': 0.0,
            'summons_are_important': True,
            'min_summons_low_level': 2,
            'min_summons_high_level': 3,
            'pow_power': 1.0,
        },
        'str': {
            'earthdam': 6.0,
        },
        'int': {
            'firedam': 6.0,
        },
        'cha': {
            'waterdam': 6.0,
        },
        'agi': {
            'airdam': 6.0,
        },
    },
    'Pandawa': {
        'all': {
            'range_importance': 0.5,
            'dodge_importance': 0.3,
            'min_summons_high_level': 2,
            'pow_power': 1.0,
        },
        'str': {
            'earthdam': 6.0,
        },
        'int': {
            'firedam': 6.0,
        },
        'cha': {
            'waterdam': 6.0,
        },
        'agi': {
            'airdam': 6.0,
        },
    },
    'Rogue': {
        'all': {
            'meleeness': 0.0,
            'vit_importance': 0.6,
            'range_importance': 0.5,
            'cridam': 0.25,
            'pow_power': 1.2, # Power important for bomb damage
        },
        'str': {
            'earthdam': 6.0,
        },
        'int': {
            'firedam': 6.0,
        },
        'cha': {
            'waterdam': 6.0,
        },
        'agi': {
            'airdam': 6.0,
        },
    },
    'Sacrier': {
        'all': {
            'meleeness': 1.0,
            'range_importance': 0.25,
            'lock_importance': 0.7,
            'vit_importance': 0.7,
            'pow_power': 1.0,
        },
        'str': {
            'earthdam': 6.0,
        },
        'int': {
            'firedam': 6.0,
        },
        'cha': {
            'waterdam': 6.0,
        },
        'agi': {
            'airdam': 6.0,
        },
    },
    'Sadida': {
        'all': {
            'range_importance': 0.0,
            'mpred_importance': 0.5,
            'dodge_importance': 0.6,
            'min_summons_low_level': 2,
            'min_summons_high_level': 3,
            'pow_power': 1.0,
        },
        'str': {
            'earthdam': 6.0,
        },
        'int': {
            'firedam': 6.0,
        },
        'cha': {
            'waterdam': 6.0,
        },
        'agi': {
            'airdam': 6.0,
        },
    },
    'Sram': {
        'all': {
            'range_importance': 1.0,
            'mpred_importance': 0.2,
            'lock_importance': 0.8,
            'traps_are_important': True,
            'cridam': 0.35,
            'pow_power': 1.0,
        },
        'str': {
            'earthdam': 6.0,
        },
        'int': {
            'firedam': 6.0,
        },
        'cha': {
            'waterdam': 6.0,
        },
        'agi': {
            'airdam': 6.0,
        },
    },
    'Xelor': {
        'all': {
            'meleeness': 0.4,
            'range_importance': 0.5,
            'apred_importance': 1.0,
            'dodge_importance': 0.5,
            'pow_power': 1.0,
        },
        'str': {
            'earthdam': 6.0,
        },
        'int': {
            'firedam': 6.0,
        },
        'cha': {
            'waterdam': 6.0,
        },
        'agi': {
            'airdam': 6.0,
        },
    },
    'Eliotrope': {
        'all': {
            'meleeness': 0.1,
            'range_importance': 0.0,
            'dodge_importance': 0.5,
            'pow_power': 1.0,
        },
        'str': {
            'earthdam': 6.0,
        },
        'int': {
            'firedam': 6.0,
        },
        'cha': {
            'waterdam': 6.0,
        },
        'agi': {
            'airdam': 6.0,
        },
    },
    'Huppermage': {
        'all': {
            'dodge_importance': 0.3,
            'lock_importance': 0.5,
            'pow_power': 1.0,
        },
        'str': {
            'earthdam': 6.0,
        },
        'int': {
            'firedam': 6.0,
        },
        'cha': {
            'waterdam': 6.0,
        },
        'agi': {
            'airdam': 6.0,
        },
        'agi/int': {
            'airdam': 6.0,
            'firedam': 6.0,
        },
        'agi/str': {
            'earthdam': 6.0,
            'airdam': 6.0,
        },
        'cha/int': {
            'firedam': 6.0,
            'waterdam': 6.0,
        },
        'cha/str': {
            'earthdam': 6.0,
            'waterdam': 6.0,
        },
    },
    'Ouginak': {
        'all': {
            'vit_importance': 0.7,
            'range_importance': 0.0,
            'dodge_importance': 0.3,
            'lock_importance': 0.6,
            'mpred_importance': 0.3,
            'pow_power': 1.0,
        },
        'str': {
            'earthdam': 6.0,
        },
        'int': {
            'firedam': 6.0,
        },
        'cha': {
            'waterdam': 6.0,
        },
        'agi': {
            'airdam': 6.0,
        },
    },
    'Forgelance': {
        'all': {
            'meleeness': 0.5,
            'range_importance': 0.5,
            'dodge_importance': 0.5,
            'lock_importance': 0.5,
            'mpred_importance': 0.2,
            'vit_importance': 0.6,
            'pow_power': 1.0,
        },
        'str': {
            'earthdam': 6.0,
        },
        'int': {
            'firedam': 6.0,
        },
        'cha': {
            'waterdam': 6.0,
        },
        'agi': {
            'airdam': 6.0,
        },
    },
}

RACES_WITH_HYBRID_PROFILES = ['Huppermage']

# Per-version overrides of the class build profiles, same shape as
# RACE_TO_BUILD_PROFILE. Resolved most specific first:
#   version race element/preset > version race 'all'
#   > base race element > base race 'all'
#   > version 'default' > base 'default'
RACE_PROFILE_OVERRIDES_BY_VERSION = {
    'beta': {},
    'dofus2': {},
    'touch': {
        # Transfusion Arrow (48-52) leads the kit; the air kit tops at 26-28.
        'Cra': {
            'str': {'earthdam': 6.5},
            'agi': {'airdam': 5.0},
        },
        # Troubling Word (42-44) leads; the air kit is thin (top 28-30).
        # The Touch Eniripsa is a healer, unlike the offensive Dofus 3 profile.
        'Eniripsa': {
            'all': {'heals_importance': 0.5},
            'int': {'firedam': 6.5},
            'agi': {'airdam': 5.0},
        },
        # The fire path lacks power; earth and water kits are even (34-38).
        'Enutrof': {
            'int': {'firedam': 5.5},
        },
        # Furnace (33-37) leads a small, even kit.
        'Feca': {
            'int': {'firedam': 6.5},
        },
        # Ecume (38-42) leads, with 5 water spells.
        'Foggernaut': {
            'cha': {'waterdam': 6.5},
        },
        # Sword of Fate (41-45) leads the kit.
        'Iop': {
            'int': {'firedam': 6.5},
        },
        # The Touch Zobal is restricted to the air pathway; water tops at 26-30.
        'Masqueraider': {
            'agi': {'airdam': 6.5},
            'cha': {'waterdam': 5.5},
        },
        # Pandatak (42-46) leads the kit.
        'Pandawa': {
            'str': {'earthdam': 6.5},
        },
        # Carnage (41-45) leads; the earth kit tops at 28-32.
        'Sacrier': {
            'agi': {'airdam': 6.5},
            'str': {'earthdam': 5.0},
        },
        # Aggressive Brambles (41-46) leads the kit.
        'Sadida': {
            'str': {'earthdam': 6.5},
        },
        # Deadly Attack (50-54) leads; the fire kit tops at 32-36.
        'Sram': {
            'str': {'earthdam': 6.5},
            'int': {'firedam': 5.0},
        },
    },
    'retro': {
        # Expiation (37-39 water) is the hardest hitting arrow; the earth line
        # is down to two spells and the air line leans PvP.
        'Cra': {
            'str': {
                'earthdam': 5.0,
            },
            'cha': {
                'waterdam': 6.5,
            },
            'agi': {
                'airdam': 5.5,
            },
        },
        # The 1.29 Sacrier gets 2 HP per vitality point; Dissolution (22-26
        # water steal, 8 AP) is the PvM path.
        'Sacrier': {
            'all': {
                'vit_importance': 1.0,
            },
            'cha': {
                'waterdam': 6.5,
            },
        },
        # Storm of Power (36-40 fire, lvl 60) and Iop's Wrath (51-70 earth)
        # lead; the air path is weak.
        'Iop': {
            'int': {
                'firedam': 6.5,
            },
            'agi': {
                'airdam': 4.5,
            },
        },
        # The 1.29 Eniripsa is the healer of the game and its heals scale with
        # intelligence; the water path is built around Vampiric Word (31-40 steal).
        'Eniripsa': {
            'all': {
                'heals_importance': 0.6,
            },
            'cha': {
                'waterdam': 6.5,
            },
        },
        # Pelle Massacrante (45-50 water) is the kit's biggest hit, and chance
        # also feeds the class's dropper identity.
        'Enutrof': {
            'cha': {
                'waterdam': 6.5,
            },
        },
        # Earth traps carry the early game, then Deadly Attack (41-60), the
        # kit's biggest hit.
        'Sram': {
            'str': {
                'earthdam': 6.5,
            },
        },
        # The Burning Glyph and the Feca armors both scale with intelligence;
        # the water kit is limited (Bubble 16-24).
        'Feca': {
            'int': {
                'firedam': 6.5,
            },
            'str': {
                'earthdam': 5.0,
            },
            'cha': {
                'waterdam': 5.5,
            },
        },
        # Crackler Punch (18-37 fire) hits through obstacles, and intelligence
        # also boosts the Osamodas heals.
        'Osamodas': {
            'int': {
                'firedam': 6.5,
            },
        },
        # Fire carries the early game; earth hits hardest (Xelor Punch 41-45)
        # but only late, and water needs wisdom and high-level gear.
        'Xelor': {
            'int': {
                'firedam': 6.5,
            },
            'cha': {
                'waterdam': 5.5,
            },
        },
        # Earth is the class's main element: 6 spells, topped by Feline Spirit (36-50).
        'Ecaflip': {
            'str': {
                'earthdam': 6.5,
            },
        },
        # Damage is essentially earth (Aggressive Brambles); the fire kit is
        # marginal (top Wild Grass 11-20) and the air big hit consumes a doll.
        'Sadida': {
            'str': {
                'earthdam': 6.5,
            },
            'int': {
                'firedam': 5.0,
            },
        },
    },
}


def _version_profile(race, game_version):
    return RACE_PROFILE_OVERRIDES_BY_VERSION.get(game_version, {}).get(race)


def param_for_build(race, elements, param, policy='max', game_version='dofus3'):
    if len(elements) == 0:
        return _param_for_race(race, param, game_version)
    elif len(elements) == 1:
        return _param_for_profile_element(race, elements[0], param,
                                          is_combination=False,
                                          game_version=game_version)
    else:
        values = []

        if race in RACES_WITH_HYBRID_PROFILES:
            for element_combination in combinations(elements, 2):
                combination = '/'.join(sorted(element_combination))
                param_for_element = _param_for_profile_element(race, combination, param,
                                                               is_combination=True,
                                                               game_version=game_version)
                if param_for_element is not None:
                    # Weight 2 for combinations.
                    for _ in  range(2):
                        values.append(param_for_element)

        for element in elements:
            param_for_element = _param_for_profile_element(race, element, param,
                                                           is_combination=False,
                                                           game_version=game_version)
            # Weight 1 for single elements.
            values.append(param_for_element)

        if policy == 'max':
            return max(values)
        elif policy == 'float_avg':
            return sum(values) / float(len(values))
        else:
            logger.warning('Unknown aggregation policy %s', policy)

def _param_for_profile_element(race, element, param, is_combination, game_version='dofus3'):
    override = _version_profile(race, game_version)
    if override is not None:
        val = (override.get(element) or {}).get(param)
        if val is not None:
            return val

    profile = RACE_TO_BUILD_PROFILE[race]
    element_profile = profile.get(element, None)
    if element_profile is not None:
        val = element_profile.get(param, None)
        if val is not None:
            return val

    if is_combination:
        return None
    else:
        return _param_for_race(race, param, game_version)

def _param_for_race(race, param, game_version='dofus3'):
    override = _version_profile(race, game_version)
    if override is not None:
        val = (override.get('all') or {}).get(param)
        if val is not None:
            return val

    profile = RACE_TO_BUILD_PROFILE[race]
    val = profile['all'].get(param, None)
    if val is not None:
        return val

    default_override = _version_profile('default', game_version)
    if default_override is not None and param in default_override:
        return default_override[param]
    return RACE_TO_BUILD_PROFILE['default'][param]

def _set_minimums(char, aspects):
    race = char.char_class
    game_version = getattr(char, 'game_version', 'dofus3') or 'dofus3'
    level = char.level
    elements = get_elements(aspects)
    is_mule = not elements and ('pp' in aspects or 'pods' in aspects)
    is_leech = not elements and 'wis' in aspects and 'pp' not in aspects and 'pods' not in aspects

    mins = {}

    # AP/MP/Range/Summons
    if is_mule or is_leech:
        mins['ap'] = 0
        mins['mp'] = 0
        mins['range'] = 0
    elif level < 60:
        mins['ap'], mins['mp'] = 6, 3
        mins['range'] = 0
    elif level < 120:
        mins['ap'], mins['mp'] = 8, 4
        mins['range'] = 2
    elif level < 160:
        mins['ap'], mins['mp'] = 9, 5
        mins['range'] = 3
    elif level < 199:
        mins['ap'], mins['mp'] = 10, 5
        mins['range'] = 4
    elif level < 200:
        mins['ap'], mins['mp'] = 11, 5
        mins['range'] = 4
    else:
        mins['ap'], mins['mp'] = param_for_build(race, elements, 'endgame_mins', game_version=game_version)
        mins['range'] = 4

    if not (is_mule or is_leech):
        mins['range'] = round(mins['range']
                              * param_for_build(race, elements, 'range_importance', 'float_avg', game_version=game_version))

    if not is_mule and not is_leech and char.minimum_stats:
        saved = read_char_blob(char.minimum_stats, {}, 'minimum_stats', char)
        for stat_key, stat_name in [('ap', 'AP'), ('mp', 'MP'), ('range', 'Range')]:
            if stat_name in saved:
                mins[stat_key] = max(mins[stat_key], saved[stat_name])
    
    if level < 40:
        mins['summon'] = 1
    elif level < 180:
        mins['summon'] = param_for_build(race, elements, 'min_summons_low_level', game_version=game_version)
    else:
        mins['summon'] = param_for_build(race, elements, 'min_summons_high_level', game_version=game_version)

    if 'summon' in aspects:
        mins['summon'] += 1
 
    # Options
    options = get_options(char)
    # TODO: Implement soft mode and hard mode. In soft mode, avoid switching options.
    # if level == 200:
    #    options['ap_exo'] = (level == 200)
    #    options['mp_exo'] = True if level == 200 else 'gelano' if level >= 120 else False
    #    options['turq_dofus'] = (level >= 190)
    #options['shields'] = ('duel' in aspects)
    if is_mule or is_leech:
        # Prysmaradites give combat bonuses, useless for mule/leech.
        # The Cawwot Dofus is the wisdom one.
        if is_leech:
            options['dofus'] = 'cawwot'
        options['prysmaradite'] = False
    else:
        options['dofus'] = 'cawwot' if ('wis' in aspects) else True
    set_options(char, options)
    
    # Convert mins keys
    mins_by_name = {}
    for k, v in mins.items():
        mins_by_name[STAT_KEY_TO_NAME[k]] = int(v)
    
    # Set result in char
    char.minimum_stats = pickle.dumps(mins_by_name)

def get_standard_weights(char):
    w = _set_weights(char, get_char_aspects(char), apply=False)
    return w

def _set_weights(char, aspects, apply=True):
    race = char.char_class
    level = char.level
    level_pct = level / 200.0
    elements = get_elements(aspects)
    element_count = len(elements)
    game_version = getattr(char, 'game_version', 'dofus3') or 'dofus3'
    tuning = VERSION_WEIGHT_TUNING.get(game_version, {})

    def pfb(*args, **kwargs):
        kwargs.setdefault('game_version', game_version)
        return param_for_build(*args, **kwargs)

    w = {}

    # Weights
    b = 20

    w['ap'] = (20 + 100 * level_pct) * b
    w['mp'] = (20 + 100 * level_pct) * b
    range_importance = pfb(race, elements, 'range_importance', 'float_avg')
    w['range'] = (16 + 80 * level_pct) * range_importance * b
    attack_factor = {0: 0, 1: 6, 2: 5, 3: 3, 4: 2}[element_count]
    if 'glasscannon' in aspects:
        attack_factor *= 1.5
    dam_mult = 2 if 'dam' in aspects else 1
    if 'res_per_factor' in tuning:
        res_per_factor = tuning['res_per_factor'](level_pct)
    else:
        res_per_factor = 2 + (10 * level_pct * level_pct)
    w['lock'] = pfb(race, elements, 'lock_importance', 'float_avg') * 10 * b
    w['dodge'] = pfb(race, elements, 'dodge_importance', 'float_avg') * 10 * b
    if 'vit' in aspects:
        w['vit'] = 1.5  * b
    else:
        w['vit'] = (pfb(race, elements, 'vit_importance', 'float_avg') + 0.5) * b
    w['hp'] = w['vit']

    w['wis'] = (25 if 'wis' in aspects else tuning.get('wis_base', 2)) * b
    w['str'] = attack_factor * b if 'str' in elements else 0
    w['int'] = attack_factor * b if 'int' in elements else 0
    w['agi'] = attack_factor * b if 'agi' in elements else 0
    w['cha'] = attack_factor * b if 'cha' in elements else 0
    w['agi'] = max(w['agi'], (w['dodge'] + w['lock']) / 10)
    # Power boosts damage in every element you use, so its value scales with the element count.
    w['pow'] = {0: 0, 1: 4, 2: 8, 3: 8, 4: 8.5}[element_count] * b
    if 'glasscannon' in aspects:
        w['pow'] *= 1.5
    w['pow'] *= pfb(race, elements, 'pow_power', 'float_avg')

    w['earthdam'] = w['str'] * pfb(race, elements, 'earthdam') * dam_mult
    w['firedam'] = w['int'] * pfb(race, elements, 'firedam') * dam_mult
    w['airdam'] = w['agi'] * pfb(race, elements, 'airdam') * dam_mult
    w['waterdam'] = w['cha'] * pfb(race, elements, 'waterdam') * dam_mult
    w['neutdam'] = pfb(race, elements, 'neutdam') * w['earthdam']
    w['dam'] = w['neutdam'] + w['earthdam'] + w['firedam'] + w['airdam'] + w['waterdam']
    res_w = ((3 if 'res' in aspects else 1)
             * (0.5 if 'glasscannon' in aspects else 1)
             * b)
    resper_w = res_per_factor * res_w
    for damage_type in DAMAGE_TYPES:
        w['%sres' % damage_type] = res_w
        w['%sresper' % damage_type] = resper_w
    
    linear_res_bonus_factor = (0.5 * level_pct + 0.5)
    w['fireres'] *= (1 + pfb(race, elements, 'fireres', 'float_avg') * linear_res_bonus_factor)
    w['fireresper'] *= (1 + pfb(race, elements, '%fireres', 'float_avg'))
    
    w['apred'] = pfb(race, elements, 'apred_importance', 'float_avg') * 12 * b
    w['mpred'] = pfb(race, elements, 'mpred_importance', 'float_avg') * 12 * b
    w['apres'] = 5 * b if 'pvp' in aspects else 1 * b
    w['mpres'] = 2 * b if 'pvp' in aspects else 1 * b
    
    minimum_red = 20 * b if len(elements) == 0 else 5 * b
    if 'aprape' in aspects:
        w['apred'] = max(2.5 * w['apred'], minimum_red)
    if 'mprape' in aspects:
        w['mpred'] = max(2.5 * w['mpred'], minimum_red)
    w['wis'] = max(w['wis'], (w['apred'] + w['mpred'] + w['apres'] + w['mpres']) / 10.0)
    # In 1.29 wisdom is itself the AP/MP defense stat.
    if 'wis_rape_floor' in tuning and ('aprape' in aspects or 'mprape' in aspects):
        w['wis'] = max(w['wis'], tuning['wis_rape_floor'] * b)
    
    if 'dam' in aspects:
        w['dam'] = max(w['dam'], 30 * b)

    w['heals'] = pfb(race, elements, 'heals_importance', 'float_avg') * 8 * b
    if 'heal' in aspects:
        w['heals'] = 4 * b + w['heals'] * 1.5
        int_per_heals_factor = 5 # TODO: Depend on class
        w['int'] = max(w['int'], w['heals'] / int_per_heals_factor)

    if pfb(race, elements, 'traps_are_important'):
        if 'trap' in aspects:
            w['trapdam'] = 10 * b
            w['trapdamper'] = 3 * b
        else:
            w['trapdam'] = 3 * b
            w['trapdamper'] = 1 * b

    w['pp'] = 10 * b if 'pp' in aspects else 0.2 * b if 'pvp' not in aspects else 0
    w['cha'] = max(w['cha'], w['pp'] / 10.0)
    w['cha'] += 0.1 * w['pp']

    w['init'] = (0.3 * b if 'duel' in aspects else
                 0.1 * b if 'pvp' in aspects else 0.03 * b)
    w['init'] *= tuning.get('init_mult', 1)

    if 'pods' in aspects:
        w['pod'] = 10 * b
        w['str'] = max(w['str'], w['pod'] / 5.0)

    if 'pushback' in aspects:
        w['pshdam'] = 15 * b
    else:
        w['pshdam'] = pfb(race, elements, 'pshdam_importance', 'float_avg') * 10 * b

    if pfb(race, elements, 'summons_are_important'):
        w['summon'] = 40 * b if 'summon' in aspects else 10 * b
    else:
        w['summon'] = 20 * b if 'summon' in aspects else 0 * b

    w['pshres'] = 0.1 * b
    w['crires'] = 2 * res_w if 'pvp' in aspects else 0.2 * res_w

    # Retro has "vs players" resistances, gone from Dofus 3.
    if 'pvp' in aspects or 'duel' in aspects:
        for elem, suffix in product(DAMAGE_TYPES, ['', 'per']):
            w['pvp%sres%s' % (elem, suffix)] = w['%sres%s' % (elem, suffix)]


    # Crits
    if 'crit' in aspects:
        w['ch'] = 140 * b
        w['cridam'] = 1.85 * w['dam'] * pfb(race, elements, 'cridam', 'float_avg')
    elif 'noncrit' in aspects:
        w['ch'] = -4 * b
        w['cridam'] = 0
    else:
        w['ch'] = 12 * b
        w['cridam'] = w['dam'] * pfb(race, elements, 'cridam', 'float_avg')

    marginal_final_damage_effect = _lerp(2, 12, level_pct)
    marginal_final_damage_w = w['pow'] * marginal_final_damage_effect
    meleeness = pfb(race, elements, 'meleeness', 'float_avg')

    # Melee vs ranged % final damage
    chance_of_melee_atk_for_cras = 0.1
    chance_of_melee_atk_for_sacs = 0.7
    chance_of_melee_atk = _lerp(chance_of_melee_atk_for_cras,
                                chance_of_melee_atk_for_sacs,
                                meleeness)
    w['permedam'] = chance_of_melee_atk * marginal_final_damage_w
    w['perrandam'] = (1.0 - chance_of_melee_atk) * marginal_final_damage_w
    
    # Weapon vs spell % final damage
    chance_of_weapon = _lerp(0.0, 0.25, level_pct)
    w['perweadam'] = chance_of_weapon * marginal_final_damage_w
    w['perspedam'] = (1.0 - chance_of_weapon) * marginal_final_damage_w

    # Melee vs ranged % final damage taken
    chance_of_melee_def_for_cras = 0.2
    chance_of_melee_def_for_sacs = 0.4
    chance_of_melee_def = _lerp(chance_of_melee_def_for_cras,
                                chance_of_melee_def_for_sacs,
                                meleeness)
    w['respermee'] = chance_of_melee_def * resper_w * 5
    w['resperran'] = (1.0 - chance_of_melee_def) * resper_w * 5
    
    w['meleeness'] = meleeness

    w['resperwea'] = chance_of_melee_def * resper_w * 5

    # 10 chance = 1 prospecting, so a mule build keeps cha at pp/10.
    if not elements and ('pp' in aspects or 'pods' in aspects):
        for zero_key in ('ap', 'mp', 'range', 'heals', 'summon',
                         'dodge', 'lock', 'agi', 'apred', 'mpred', 'apres', 'mpres',
                         'crires', 'pshres', 'cridam', 'pshdam', 'trapdam',
                         'trapdamper', 'ref', 'permedam', 'perrandam',
                         'perweadam', 'perspedam', 'respermee', 'resperran',
                         'resperwea', 'init', 'wis', 'ch', 'vit', 'hp',
                         'pow', 'str', 'int'):
            w[zero_key] = 0
        for damage_type in DAMAGE_TYPES:
            w['%sres' % damage_type] = 0
            w['%sresper' % damage_type] = 0
            w['%sdam' % damage_type] = 0
        w['dam'] = 0
        w['cha'] = w['pp'] / 10.0

    if not elements and 'wis' in aspects and 'pp' not in aspects and 'pods' not in aspects:
        for zero_key in ('ap', 'mp', 'range', 'heals', 'summon',
                         'dodge', 'lock', 'agi', 'apred', 'mpred', 'apres', 'mpres',
                         'crires', 'pshres', 'cridam', 'pshdam', 'trapdam',
                         'trapdamper', 'ref', 'permedam', 'perrandam',
                         'perweadam', 'perspedam', 'respermee', 'resperran',
                         'resperwea', 'init', 'ch', 'vit', 'hp',
                         'pow', 'str', 'int', 'cha', 'pp'):
            w[zero_key] = 0
        for damage_type in DAMAGE_TYPES:
            w['%sres' % damage_type] = 0
            w['%sresper' % damage_type] = 0
            w['%sdam' % damage_type] = 0
        w['dam'] = 0

    # Stats no item of this version's pool carries; the tuning page expects every key present.
    for zero_key in tuning.get('zero_stats', ()):
        if zero_key in w:
            w[zero_key] = 0

    # Discretize w
    for k in w:
        w[k] = int(round(w[k]))
        
    # Set result in char
    if apply:
        char.stats_weight = pickle.dumps(w)
    else:
        return w

def _lerp(a, b, t):
    return a * (1.0 - t) + b * t

def _apply_aspects(char, aspects, set_minimums):
    if set_minimums:
        _set_minimums(char, aspects)
    _set_weights(char, aspects)
    
def reapply_weights(char):
    _set_weights(char, get_char_aspects(char))
   
def get_elements(aspects):
    elements = []
    if 'omni' in aspects:
        elements.extend(MAIN_STATS)
    else:
        for el in MAIN_STATS:
            if el in aspects:
                elements.append(el)
    return elements

def get_char_aspects(char):
    return read_char_blob(char.aspects, set(), 'aspects', char)
    
def set_char_aspects(char, aspects, reset, set_minimums=True):
    char.aspects = pickle.dumps(aspects)
    if reset:
        _apply_aspects(char, aspects, set_minimums)
    char.char_build = _generate_build_line(aspects)
    char.save()

def char_has_aspect(char, aspect):
    return aspect in get_char_aspects(char)

def _generate_build_line(aspects):
    sections = [[] for _ in range(3)]
    for aspect in aspects:
        if aspect in MAIN_STATS:
            sections[0].append(aspect)
        elif aspect in ['crit', 'noncrit']:
            sections[1].append(aspect)
        elif aspect != 'omni':
            sections[2].append(aspect)

    if 'omni' in aspects:
        sections[0] = ['omni']

    sections = list(filter(bool, sections))
    for section in sections:
        section.sort(key=lambda x: ALL_ASPECTS_LIST.index(x))
        
    return ' '.join(['/'.join([ASPECT_TO_SHORT_NAME[a] for a in section])
        for section in sections])
