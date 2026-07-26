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
import pickle

from fashionistapulp.dofus_constants import SLOTS
from fashionistapulp.structure import get_structure

logger = logging.getLogger(__name__)


# Items the optimiser excludes by default: GM-only, event, joke and duplicate items
# nobody wants the solver to pick. Keyed by Ankama item id (stable across versions and
# localisations), with the item name in a trailing comment. Ids absent from the active
# game version are skipped automatically, so a single list covers every version.
DEFAULT_EXCLUSION_ANKAMA_IDS = [
    9031,   # Gore Master's Ring (Gms Only)
    9202,   # Gore Master's Other Ring (Retro)
    6894,   # Ultra-powerful Combat Bow Meow (GM)
    6895,   # Small Combat Bow Meow (GM)
    7913,   # Animagi (GM)
    7920,   # Tournament Wand (GM)
    2155,   # Jiva Necklace
    18853,  # Fiery Tongue Sword
    8575,   # First Blood Staff
    11761,  # Le Divhugalch (unobtainable retro joke staff, +3 AP/+3 MP)
    8854,   # Crack Sparrow's Own Withered Hat
    2154,   # De Sendar's Ring
    27645,  # Basic Broom
    27268,  # Khardboard Goultard
    27282,  # Khardboard Gobball Headgear
    27267,  # Khardboard Dazzling Cloak
    27265,  # Khardboard Celestial Brooch
    27284,  # Khardboard Gelano
    27278,  # Khardboard Getas
    27266,  # Khardboard Moowolf Belt
    27280,  # Khardboard Bowisse's Shield
    6713,   # Lordsoth Daggers
    13063,  # Split Splinter Sprinter
    8422,   # [wip] (Touch work-in-progress placeholder)
    12596,  # [!] WIP (Touch work-in-progress placeholder)
]

# Per-version defaults: items that are in the game data but shouldn't be proposed
# for that specific version (e.g. an item scraped into Touch that Touch players
# can't actually get). Same forbidden-by-default-but-removable behaviour, version
# scoped so the same Ankama id stays available where it is a real item (10076 is a
# genuine Retro shield but does not exist in Dofus Touch).
DEFAULT_EXCLUSION_ANKAMA_IDS_BY_VERSION = {
    # Items with no way left to get them: verified one by one against the
    # live data (no drop, no recipe, no live quest/achievement) and the
    # wikis. Forbidden by default but removable, like the touch list.
    'dofus3': [
        # GM-only items
        7913,    # Animagi (GM)
        9031,    # Gore Master's Ring (Gms Only)
        # personal one-off gifts to a single player
        2154,    # De Sendar's Ring
        2155,    # Jiva Necklace
        2156,    # Sword of Justice
        # physical Dofus 2.0 Collector box codes (2009)
        10685,   # Haks Or Mask
        10686,   # Haks Or Cloak
        10687,   # Haks Or Ring
        10688,   # Haks Or Belt
        # manga/convention promo prizes
        16343,   # Paintbrush
        # Ankama Lottery rewards; the lottery is long gone
        8941,    # Ecaflip Paw
        8956,    # Ecaflip Paw 2
        8957,    # Ecaflip Paw 3
        8958,    # Ecaflip Paw 4
        8959,    # Ecaflip Paw 5
        8960,    # Ecaflip Paw 6
        8961,    # Ecaflip Paw 7
        8962,    # Ecaflip Paw 8
        8963,    # Ecaflip Paw 9
        8964,    # Ecaflip Paw 10
        8965,    # Ecaflip Paw 11
        8966,    # Perfect Ecaflip Paw
        10054,   # Vampyre Ring
        10055,   # Vampyre Amulet
        10056,   # Vampyre Belt
        10058,   # Vampyre Cape
        10061,   # Vampyre Boots
        10102,   # Vampyre Mask
        11855,   # Stroud's Boots
        12465,   # Brown Varnished Shoes
        12466,   # Boracelet
        # rewards of removed tutorial/Incarnam quests
        6773,    # Tude Amulet
        10784,   # Intrepid Amulet
        10785,   # Intrepid Ring
        10794,   # Intrepid Boots
        10799,   # Intrepid Belt
        10800,   # Intrepid Cloak
        10801,   # Intrepid Hat
        12661,   # Handbag
        # one-off Temporis VII server rewards
        27267,   # Khardboard Dazzling Cloak
        27268,   # Khardboard Goultard
        27280,   # Khardboard Bowisse's Shield
        27282,   # Khardboard Gobball Headgear
        # one-off past contests and events
        1505,    # Flute
        8338,    # Kwismas Sword
        8627,    # Sarr Ys's Flute
        10158,   # Trophy Dark Vlad Shield
        10159,   # Trophy Moon Shield
        10160,   # Trophy Soft Oak Shield
        10161,   # Trophy Dragon Pig Shield
        10162,   # Trophy Minotoror Shield
        10163,   # Trophy Kimbo Shield
        10164,   # Trophy Wa Wabbit Shield
        10165,   # Trophy Koolich Shield
        10166,   # Trophy Sphincter Cell Shield
        10167,   # Trophy Bworker Shield
        11811,   # Prespic Skin Boots
        17456,   # Piney Shoes
        17457,   # Kwismas Ring
        21506,   # Plushy-Ball: Drheller
        21507,   # Plushy-Ball: Gobball
        21508,   # Plushy-Ball: Tofu
        21509,   # Plushy-Ball: Bow Meow
        21510,   # Plushy-Ball: Minikron
        # removed content leftovers (old quests, Frigost exchanges, migrations)
        1628,    # Fire Artefact
        1629,    # Earth Artefact
        1630,    # Air Artefact
        1631,    # Water Artefact
        1632,    # Light Artefact
        1633,    # Life Artefact
        6661,    # Fishing Rod for Quaquack
        6793,    # Tea Ring
        6800,    # Basic Cloak
        6840,    # Yanguru Sword
        6863,    # Astrub Mercenary Helmet
        6886,    # Astrub Mercenary Cloak
        7097,    # Training Shield
        11603,   # Tatty Bim Bonnet
        11610,   # Badly-made Kanigloo Loincloth
        11617,   # Worn-out Indigenous Boots
        11733,   # Clogged-up Turbine Belt
        11748,   # Thanos's Chewed-Up Staff
        # no source left in the live data
        677,     # Pirate Cloak
        856,     # Little Frog
        6713,    # Lordsoth Daggers
        8575,    # First Blood Staff
        8854,    # Crack Sparrow's Own Withered Hat
        13063,   # Split Splinter Sprinter
    ],
    # Same data as dofus3.
    'beta': [
        7913, 9031, 2154, 2155, 2156, 10685, 10686, 10687, 10688, 16343, 8941, 8956, 8957, 8958, 8959, 8960, 8961, 8962, 8963, 8964, 8965, 8966, 10054, 10055, 10056, 10058, 10061, 10102, 11855, 12465, 12466, 6773, 10784, 10785, 10794, 10799, 10800, 10801, 12661, 27267, 27268, 27280, 27282, 1505, 8338, 8627, 10158, 10159, 10160, 10161, 10162, 10163, 10164, 10165, 10166, 10167, 11811, 17456, 17457, 21506, 21507, 21508, 21509, 21510, 1628, 1629, 1630, 1631, 1632, 1633, 6661, 6793, 6800, 6840, 6863, 6886, 7097, 11603, 11610, 11617, 11733, 11748, 677, 856, 6713, 8575, 8854, 13063
    ],
    'touch': [
        # Shields kept out by default. An empty recipe and an empty drop list
        # prove nothing on their own: a quest, the in-game shop and a seasonal
        # event all leave the same empty tables, which is how the Albuera and
        # the Novice shields ended up wrongly hidden here. Every id below is
        # kept for a reason of its own, checked against the Touch sources.
        10076,  # Unique Hispanian Shield (absent from the Touch encyclopedia)
        12615,  # Escudo Epico (Spanish community event, PC only)
        21593,  # [!] Unshakeable test shield (internal test item)
        # PC-only one-off promos: no Touch distribution found for any of them,
        # and none belongs to a set whose other pieces live in Touch.
        17304,  # Beakler
        9566,   # Raydi Shield / Bouclier Pararayon (PC "Legendes anciennes" pack)
        13158,  # Thousand Shield (one-off Italian contest prize, PC)
        # Ankama Lottery rewards, gone long before Touch forked
        8941,    # Ecaflip Paw
        8956,    # Ecaflip Paw
        8957,    # Ecaflip Paw
        8958,    # Ecaflip Paw
        8959,    # Ecaflip Paw
        8960,    # Ecaflip Paw
        8961,    # Ecaflip Paw
        8962,    # Ecaflip Paw
        8963,    # Ecaflip Paw
        8964,    # Ecaflip Paw
        8965,    # Ecaflip Paw
        8966,    # Perfect Ecaflip Paw
        10054,   # Vampyre Ring
        10055,   # Vampyre Amulet
        10056,   # Vampyre Belt
        10058,   # Vampyre Cape
        10061,   # Vampyre Boots
        10102,   # Vampyre Mask
        11855,   # Stroud's Boots
        12465,   # Brown Varnished Shoes
        12466,   # Boracelet
        # GM-only items
        7913,    # Animagi (GM)
        # PC-era one-off events and removed content, no Touch source
        677,     # Pirate Cloak
        1628,    # Fire Artefact
        1629,    # Earth Artefact
        1630,    # Air Artefact
        1631,    # Water Artefact
        1632,    # Light Artefact
        1633,    # Life Artefact
        6713,    # Lordsoth Daggers
        6793,    # Tea Ring
        6800,    # Basic Cloak
        6886,    # Astrub Mercenary Cloak
        8338,    # Kwismas Sword
        8575,    # First Blood Staff
        8627,    # Sarr Ys's Flute
        11603,   # Tatty Bim Bonnet
        11610,   # Badly-made Kanigloo Loincloth
        11617,   # Worn-out Indigenous Boots
        11733,   # Clogged-up Turbine Belt
        11748,   # Thanos's Chewed-Up Staff
        11811,   # Prespic Skin Boots
        13063,   # Split Splinter Sprinter
        # physical Dofus 2.0 Collector box codes (2009, PC only)
        10687,   # Haks Or Ring
        10688,   # Haks Or Belt
        # rewards of PC tutorial quests that never existed on Touch
        6773,    # Tude Amulet
        12661,   # Handbag
        # Ankama Lottery / PC promo set pieces, gone before Touch forked
        9921,    # Slamdance Bracelet
        9922,    # Slamdance Belt
        9923,    # Slamdance Shoes
        9928,    # Siks Wonn Ein Boots
        9929,    # Siks Wonn Ein Belt
        9943,    # Pair o'Shuplins
        9944,    # The Chavate
        10155,   # Amlugo
        10156,   # Slugo
        10157,   # Belugo
        10168,   # Chisp Boots
        10171,   # Chisp Fingerless Gloves
        10180,   # The Esteban
        10181,   # Solaris Ring
        10189,   # Oxo Ring
        10190,   # Oxo Boots
        10191,   # Oxo Belt
        10557,   # Real Gobbly Glove
        # Magik Riktus incarnation weapons, never in the Touch shop rotation
        10125,   # Bandit Archer Bow
        10126,   # Swashbuckling Bandit Sword
        10127,   # Wandering Bandit Staff
        10133,   # Bandit Sorcerer's Wand
        # PC magazine/collector promo items
        9927,    # Bedazzling Boots
        # PC-only content with no Touch source
        9925,    # Bedazzling Fist
        9942,    # Ring of Death
        10186,   # Noke's Necklace
        # ex-Shushumi / Great Emporium ogrine-shop weapons, never sold on Touch
        9711,    # Dagg' Hers
        9712,    # Dagg' Heirs
        9713,    # Dagger Nica
        9716,    # Dagger Khin
        9717,    # Dagger Rilla
        9724,    # Shovel Kroh
        9725,    # Shovel Hem
        9726,    # Shovel Vett
        9727,    # Shovel Ington
        9728,    # Shovel Conquistador
        9729,    # Hammer Maid
        9730,    # Hammer Rhor
        9731,    # Hammer Rigoround
        9735,    # Hammer Udeet
        9736,    # Hammer Leen
        9739,    # Bow Leeng
        9741,    # Mam Bow
        9742,    # Bow Ndjoor
        9743,    # Bow Nuss
        9744,    # Bow Gotta
        9745,    # Wand Erboy
        9746,    # Wand Enonly
        9747,    # Wand Rogenus
        9748,    # Wand Rohid
        9749,    # Wand Herfool
        9750,    # Tex Axe
        9751,    # Axe Enroziz
        9752,    # Axe Ident
        9753,    # Axe Hellerate
        9754,    # Axe Vegax
        9755,    # Staff Renzi
        9756,    # Staff Ro
        9757,    # Staff Ternoon
        9758,    # Staff Amished
        9759,    # Staff Igraf
        10172,   # Slugly Amulet
        10173,   # Slugly Boots
        10558,   # Lamechester United Glove
        # Ankama Lottery / Dofus Mag token prizes, PC-only
        2521,    # Megaboots
        2523,    # Megabelt
        8676,    # Wicked Sword
        8701,    # Nicked Sword
        9190,    # Cra's Burnt Headgear
        9191,    # Pym's Blade
        9402,    # Beezers
        9408,    # Lousy Ring
        9409,    # Lardine Belt
        9412,    # Eastern Wood Belt
        9413,    # Eastern Wood Boots
        9416,    # Zest Ring
        9452,    # Crystalline Ring
        9453,    # Crystalline Belt
        9454,    # Bobblamulet
        9455,    # Bobblering
        9662,    # Slait Ring
        9667,    # Slait Boots
        10559,   # Toot's Belt
        10560,   # Monty's Belt
        10561,   # Real Gobbly Boots
        # GM / staff-only items
        7753,    # Furnace Wand
        7920,    # Tournament Wand (GM)
        # Great Emporium ogrine-shop / Shushumi weapons, never on Touch
        9192,    # Fasstroid Belt
        9193,    # Tartamulet
        9198,    # Beanie Ring
        9199,    # Beanie Boots
        9655,    # Alowa Sandals
        9656,    # Slump Rollers
        9658,    # Alowa Amulet
        9659,    # Slump Necklace
        9706,    # Sword Inary
        9707,    # Nutyprofe Sword
        9708,    # Ascen Sword
        9709,    # Sword Onik
        9710,    # Sword Idd
        10562,   # Lamechester United Boots
        # PC magazine/subscription promo items
        9575,    # Black Wab Belt
        9576,    # Black Wab Boots
        # PC tournament ceremonial rewards
        8067,    # Champion Boots
        8070,    # Champion Belt
        # deprecated pre-revamp set shells
        7887,    # Worn Koolich Headgear
        7888,    # Worn Koolich Bag
        7889,    # Worn Koolich Boots
        7890,    # Worn Koolich Staff
        # deprecated trade-in placeholder shells (level 1, no stats)
        8645,    # Cape Ytal
        8646,    # Cape Anama
        8647,    # Cape Wuera
        8648,    # Cape Hulco
        8649,    # Cape Adossia
        8650,    # Cape Hernaum
        8651,    # Bloody Belt
        8652,    # Belt Sterous
        8653,    # Clinkin Belt
        8654,    # Sleepless Belt
        8655,    # Blub Belt
        8656,    # Belt Atio
        8657,    # Strap Pado
        8658,    # Diezzle Belt
        8659,    # Sticky Strap
        8660,    # Targ Belt
        8661,    # Girdle Belt
        8662,    # Belt Urgid
        8663,    # Boot-a-Hoop
        8664,    # Sleephairs
        8665,    # Boots Hox
        8666,    # Shal'Hal Boots
        8667,    # Antibooties
        8668,    # Boots Hanik
        8669,    # Nailed Thongs
        8670,    # Wawka Boots
        8713,    # Geta Bernacle
        8714,    # Honoh Ring
        8715,    # Blaber Ring
        8716,    # Lion Ring
        8717,    # Ring Bellious
        8718,    # Memo Ring
        8719,    # Rememb Ring
        8720,    # Chee Ring
        8721,    # Ear Ring
        8722,    # Elkebi Ring
        8723,    # Subma Ring
        8724,    # Hai Ring
        8725,    # Ring Neinwonwon
        8726,    # Crusuede Shoes
        8727,    # Relief Boots
        8728,    # Veggie Boots
        # spent revamp tokens: the item text itself says to trade them in, and
        # the Touch backend has no drop, recipe, quest or achievement for them
        12385,   # Hoodwink Headgear
        12386,   # Arpone Mask
        12387,   # Hanging Cloak
        12388,   # Bangin' Cloak
        12389,   # Doc Post-Martems
        12390,   # Notts O'Clever Clogs
        12391,   # Glisserin Belt
        12392,   # Retchual Rope
        12393,   # Enig Mittens
        12394,   # Mithik Bracelet
        13261,   # Diving Bell End
        13262,   # Tanked Backpack
        13263,   # Roboots
        13264,   # Buoy's Belt
        13265,   # Pressure Ring
        14053,   # Flawed Cap
        14054,   # Flawed Ring
        14056,   # Flawed Boots
        # Boufbowl match rings: handed out inside a match, never owned. The Touch
        # backend still has them under their untranslated internal name, with no
        # stat, drop or recipe.
        19961,   # [!] Bague de Boufbowl (Attaquant Bleu)
        19963,   # [!] Bague de Boufbowl (Attaquant Rouge)
        19965,   # [!] Bague de Boufbowl (Defenseur Bleu)
        19967,   # [!] Bague de Boufbowl (Defenseur Rouge)
        19995,   # [!] Samy Bague de Boufbowl (test)
        # Boufbowl match rings again: level 1, no real stats, their only effect
        # casts a team-identity spell during a match.
        18815,   # Gobbowl Ring
        19957,   # Gobbowl Ring (Blue Captain)
        19959,   # Gobbowl Ring (Red Captain)
        # Hispanic set: a Goultarminator prize for the Spanish community on PC,
        # absent from the Dofus Touch encyclopedia altogether.
        12616,   # Caschoygan
        12617,   # Cuarzomyr Masinko
        # Kwismas hats carrying a past year of the Dofus calendar. Kwismas comes
        # back every year, but with that year's number; 648 and 649 are gone.
        15823,   # Kwismas 648 Treetop
        16888,   # Kwismas 649 Treetop
        # [FM] is Ankama's own smithmagic-workbench marker. These three exist in
        # no other version and have no recipe and no drop on Touch either.
        18555,   # [FM] Capistil
        18557,   # [FM] Plantamulet
        18559,   # [FM] Cuttings
    ],
    'retro': [
        7043,   # Ice Dofus / Dofus des Glaces (not in 1.29; scraped as a bogus
                # level 1 Dofus with +10% all resists, a real Dofus 2+ item)
        13171,  # Nolifishield / Grobouclier (Grobe dungeon key shield; a real
                # item but not built with, so hidden by default and removable)
    ],
}

def get_default_exclusions(char):
    s = get_structure()
    ankama_ids = (DEFAULT_EXCLUSION_ANKAMA_IDS
                  + DEFAULT_EXCLUSION_ANKAMA_IDS_BY_VERSION.get(s.game_version, []))
    item_ids = []
    for ankama_id in ankama_ids:
        item = s.get_item_by_ankama_id(ankama_id)
        if item is not None:
            item_ids.append(item.id)
    return item_ids

def set_exclusions_list_and_check_inclusions(char, excluded_items):
    assert type(excluded_items) == list
    for item in excluded_items:
        assert type(item) == int
    _remove_inclusions_by_id(char, excluded_items)
    _save_exclusion_list(char, excluded_items)

def set_inclusions_dict_and_check_exclusions(char, inclusions_dict):
    remove_from_exclusion = []
    for slot in SLOTS:
        included_item = inclusions_dict.get(slot, None)
        if included_item:
            remove_from_exclusion.append(int(included_item))
    remove_items_from_exclusions(char, remove_from_exclusion)
    _save_inclusion_dict(char, inclusions_dict)

def get_all_inclusions_en_names(char):
    item_dict = get_inclusions_dict(char)
    return {key: _item_id_to_local_or_name(value, 'en')
            for key, value in list(item_dict.items())}

def get_inclusions_dict(char):
    inclusions = {}
    if char.inclusions:
        inclusions = pickle.loads(char.inclusions)
    return inclusions

def set_exclusions_list_by_name(char, excluded_items):
    s = get_structure()

    items = []
    for item_name in excluded_items:
        item = s.get_item_by_name(item_name)
        if item is None:
            result = s.get_or_item_by_name(item_name)
            if result:
                item = result[0]
            else:
                logger.warning('Item %s does not exist and cannot be excluded', item_name)

        if item is not None:
            item_id = item.id
            items.append(item_id)
        else:
            logger.warning('Item %s does not exist and cannot be excluded', item_name)
    set_exclusions_list_and_check_inclusions(char, items)
    
def remove_invalid_inclusions(char, level):
    structure = get_structure()
    inclusions = get_inclusions_dict(char)
    for item_type, equip in inclusions.items():
        if equip != '':
            item = structure.get_item_by_id(equip)
            if item is None or item.level > level:
                inclusions[item_type] = ''

    _save_inclusion_dict(char, inclusions)

def set_item_included(char, item_id, slot, included):
    inclusions = get_inclusions_dict(char)
    
    if included:
        inclusions[slot] = item_id
        set_excluded(char, item_id, False)
    else:
        if inclusions.get(slot, '') == item_id:
            inclusions[slot] = ''

    _save_inclusion_dict(char, inclusions)

def get_all_exclusions_with_names(char, language):
    item_list = []
    for item_id in _get_all_exclusions(char):
        item = {'id':  item_id,
                'name': _item_id_to_local_or_name(int(item_id), language)}
        item_list.append(item)
    return item_list

def get_all_exclusions_ids(char):
    return _get_all_exclusions(char)

def get_all_exclusions_en_names(char):
    return [_item_id_to_local_or_name(int(item_id), 'en')
            for item_id in _get_all_exclusions(char)]

def set_excluded(char, item_id, forbidden):
    item_ids = [int(item_id)]
    if forbidden:
        add_items_to_exclusions(char, item_ids)
    else:
        remove_items_from_exclusions(char, item_ids)
   
def _item_id_to_local_or_name(item_id, language):
    structure = get_structure()
    item = structure.get_item_by_id(item_id)

    if item is None:
        # Legacy pickles can reference retired items; fall back to any variant we still know
        for candidate in structure.get_items_by_or_id(item_id):
            if candidate is not None:
                item = candidate
                break

    if item is None:
        return f"Unknown item #{item_id}"

    localized_names = getattr(item, 'localized_names', {}) or {}
    if language in localized_names:
        return localized_names[language]

    if 'en' in localized_names:
        return localized_names['en']

    # Last resort: return first available localization or name/id to avoid crashing the UI
    if localized_names:
        return next(iter(localized_names.values()))
    if getattr(item, 'name', None):
        return item.name

    return str(item_id)

def _save_inclusion_dict(char, inclusions):
    inclusions = {slot: int(value)
                  for slot, value in list(inclusions.items()) if value != ''}
    char.inclusions = pickle.dumps(inclusions)
    char.save()

def _remove_inclusions_by_id(char, item_ids):
    inclusions = get_inclusions_dict(char)

    changed = False
    for slot in SLOTS:
        if inclusions.get(slot, '') in item_ids:
            inclusions[slot] = ''
            changed = True
    
    if changed:
        _save_inclusion_dict(char, inclusions)

def _save_exclusion_list(char, excluded_items):
    char.exclusions = pickle.dumps(excluded_items)
    char.save()

def _get_all_exclusions(char):
    exclusions = []
    if char.exclusions:
        exclusions = pickle.loads(char.exclusions)
    return exclusions

def add_items_to_exclusions(char, item_ids):
    exclusions = get_all_exclusions_ids(char)
    
    changed = False
    for item_id in item_ids:
        if item_id not in exclusions:
            exclusions.append(item_id)
            changed = True

    if changed:
        set_exclusions_list_and_check_inclusions(char, exclusions)

def remove_items_from_exclusions(char, item_ids):
    exclusions = get_all_exclusions_ids(char)

    changed = False
    for item_id in item_ids:
        if item_id in exclusions:
            exclusions.remove(item_id)
            changed = True

    if changed:
        _save_exclusion_list(char, exclusions)

def get_empty_slots(char):
    if char.empty_slots:
        return pickle.loads(char.empty_slots)
    return []

def set_empty_slot(char, slot, is_empty):
    empty = get_empty_slots(char)
    if is_empty:
        if slot not in empty:
            empty.append(slot)
    else:
        if slot in empty:
            empty.remove(slot)
    char.empty_slots = pickle.dumps(empty)
    char.save()

def get_stat_overrides(char):
    if char.stat_overrides:
        return pickle.loads(char.stat_overrides)
    return {}

def set_item_stat_override(char, item_id, stat_id, value):
    overrides = get_stat_overrides(char)
    if item_id not in overrides:
        overrides[item_id] = {}
    overrides[item_id][stat_id] = value
    char.stat_overrides = pickle.dumps(overrides)
    char.save()

def remove_item_stat_override(char, item_id, stat_id):
    overrides = get_stat_overrides(char)
    if item_id in overrides:
        overrides[item_id].pop(stat_id, None)
        if not overrides[item_id]:
            del overrides[item_id]
    char.stat_overrides = pickle.dumps(overrides)
    char.save()

def clear_item_stat_overrides(char, item_id):
    overrides = get_stat_overrides(char)
    overrides.pop(item_id, None)
    char.stat_overrides = pickle.dumps(overrides)
    char.save()
    