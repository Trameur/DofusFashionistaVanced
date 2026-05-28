#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Regression test for the Dofus Retro (1.29) data + LP engine.

Loads items_retro.db, checks known items decode correctly, and runs a real
optimisation to confirm the version-conditioned solver produces a valid build.
No dev server needed.

Usage:
    python test_retro.py
"""

import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
for p in (os.path.join(ROOT, "fashionsite"), os.path.join(ROOT, "fashionistapulp"), ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "fashionsite.settings")
import django
django.setup()

from fashionistapulp.structure import set_current_game_version, get_structure
from fashionistapulp.model import Model, ModelInput

_passed, _failed = [], []


def check(name, cond, detail=""):
    (_passed if cond else _failed).append(name)
    mark = "[OK]" if cond else "[FAIL]"
    print(f"  {mark} {name}" + (f" -- {detail}" if detail and not cond else ""))


def stat_value(item, stat_name):
    sid = STRUCT.get_stat_by_name(stat_name).id
    for s_id, val in item.stats:
        if s_id == sid:
            return val
    return None


def item_by_name(name):
    for it in STRUCT.get_items_list():
        if it.name == name:
            return it
    return None


set_current_game_version("retro")
STRUCT = get_structure("retro")
items = STRUCT.get_items_list()

print("\n== data ==")
check("item count > 5000", len(items) > 5000, f"got {len(items)}")
check("no mojibake names", not any(it.name and "Ã" in it.name for it in items))

# English item names are loaded (items_en.json), so the canonical name is English:
# "Coiffe du Bouftou" -> "Gobball Headgear".
bouftou = item_by_name("Gobball Headgear")
check("Gobball Headgear present (english names loaded)", bouftou is not None)
if bouftou:
    check("Gobball Headgear = 40 Strength", stat_value(bouftou, "Strength") == 40)
    check("Gobball Headgear = 40 Intelligence", stat_value(bouftou, "Intelligence") == 40)

print("\n== weapons ==")
weapon_type_id = None
weapons = [it for it in items if STRUCT.get_type_name_by_id(it.type) == "Weapon"]
check("weapons present", len(weapons) > 1000, f"got {len(weapons)}")
hit_weapons = [w for w in weapons if w.name in STRUCT.weapons_dict_by_name]
check("weapons have hit/ap data", len(hit_weapons) > 1000, f"got {len(hit_weapons)}")

print("\n== solve (Iop 100) ==")
base = {n: 0 for n in [
    "Power", "Damage", "Heals", "AP", "Critical Hits", "Agility", "Strength",
    "Neutral Damage", "Earth Damage", "Intelligence", "Fire Damage", "Air Damage",
    "Chance", "Water Damage", "Vitality", "Initiative", "Summon", "Neutral Resist",
    "Range", "% Neutral Resist", "Wisdom", "% Water Resist", "Water Resist",
    "Air Resist", "Fire Resist", "Earth Resist", "MP", "% Air Resist",
    "% Fire Resist", "% Earth Resist", "Prospecting", "Pods"]}
base["AP"] = 6
base["MP"] = 3
base["Summon"] = 1
base["Strength"] = 100
base["Vitality"] = 100

_okeys = ["vit", "wis", "str", "int", "cha", "agi", "pow", "ap", "mp", "range",
          "summon", "ch", "init", "pp", "lock", "dodge", "apred", "mpred", "apres",
          "mpres", "pshres", "crires", "pod", "ref", "trapdam", "trapdamper", "dam",
          "neutdam", "earthdam", "firedam", "airdam", "waterdam", "cridam", "pshdam",
          "heals", "neutres", "earthres", "fireres", "airres", "waterres",
          "neutresper", "earthresper", "fireresper", "airresper", "waterresper"]
objective = {k: 0 for k in _okeys}
objective.update({"str": 50, "dam": 100, "earthdam": 50, "vit": 5, "ap": 200, "mp": 100})
options = {"ap_exo": False, "range_exo": False, "mp_exo": False, "dofus": True,
           "dragoturkey": True, "seemyool": True, "rhineetle": True, "prysmaradite": False}

model = Model()
model.setup(ModelInput(100, base, {"AP": 8, "MP": 4}, {}, set(), objective, options, "Iop", 5 * 99))
model.run(2)
status = model.get_solved_status()
check("solve status is Optimal", status == "Optimal", status)

if status == "Optimal":
    ips = model.get_result_minimal().item_per_slot
    filled = {s: i for s, i in ips.items() if i is not None}
    check("build fills >= 10 slots", len(filled) >= 10, f"got {len(filled)}")
    ring_ids = [ips.get("ring1"), ips.get("ring2")]
    check("two rings are different items (no 1.29 ring doubling)",
          ring_ids[0] != ring_ids[1] or None in ring_ids)

print(f"\n{len(_passed)} passed, {len(_failed)} failed")
if _failed:
    print("FAILED: " + ", ".join(_failed))
    sys.exit(1)
print("All retro checks passed.")
