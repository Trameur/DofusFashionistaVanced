#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Regression test for the Dofus Touch data + LP engine.

Loads items_touch.db, checks known items decode correctly, and runs a real
optimisation to confirm the solver produces a valid build for the Touch version.
No dev server needed.

Usage:
    python test_touch.py
"""

import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
for p in (os.path.join(ROOT, "fashionsite"), os.path.join(ROOT, "fashionistapulp"), ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_passed, _failed = [], []
STRUCT = None


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


def main():
    global STRUCT, _passed, _failed

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "fashionsite.settings")
    import django
    django.setup()

    from fashionistapulp.structure import set_current_game_version, get_structure
    from fashionistapulp.model import Model, ModelInput
    from fashionistapulp.fashionista_config import get_items_db_path
    from chardata.version_compat import filter_classes_for_version
    import sqlite3

    _passed, _failed = [], []

    set_current_game_version("touch")
    STRUCT = get_structure("touch")
    items = STRUCT.get_items_list()

    print("\n== data ==")
    check("item count > 2500", len(items) > 2500, f"got {len(items)}")
    check("no mojibake names", not any(it.name and "Ã" in it.name for it in items))

    shields = [it for it in items if STRUCT.get_type_name_by_id(it.type) == "Shield"]
    check("touch has shields", len(shields) > 50, f"got {len(shields)}")

    # English item names are loaded, so the canonical name is English:
    # "Coiffe du Bouftou" -> "Gobball Headgear" (Touch lvl-41 version = 30/30).
    bouftou = item_by_name("Gobball Headgear")
    check("Gobball Headgear present (english names loaded)", bouftou is not None)
    if bouftou:
        check("Gobball Headgear = 30 Strength", stat_value(bouftou, "Strength") == 30,
              f"got {stat_value(bouftou, 'Strength')}")
        check("Gobball Headgear = 30 Intelligence", stat_value(bouftou, "Intelligence") == 30,
              f"got {stat_value(bouftou, 'Intelligence')}")

    # structure.py may suffix duplicate-named items as "Gelano (#1)"; match either.
    gelano = item_by_name("Gelano") or next(
        (it for it in items if it.name and it.name.startswith("Gelano")), None)
    check("Gelano present", gelano is not None)
    if gelano:
        check("Gelano = +1 AP", stat_value(gelano, "AP") == 1, f"got {stat_value(gelano, 'AP')}")

    # Touch-specific (Dofus-2-era) stats still on items: AP/MP parry, dodge/lock, traps.
    parry = [it for it in items if any(STRUCT.get_stat_by_id(sid).name in
             ("AP Loss Resist", "MP Loss Resist") for sid, _ in it.stats)]
    check("touch items carry AP/MP parry stats", len(parry) > 20, f"got {len(parry)}")

    print("\n== weapons ==")
    weapons = [it for it in items if STRUCT.get_type_name_by_id(it.type) == "Weapon"]
    check("weapons present", len(weapons) > 500, f"got {len(weapons)}")
    hit_weapons = [w for w in weapons if w.name in STRUCT.weapons_dict_by_name]
    check("weapons have hit/ap data", len(hit_weapons) > 500, f"got {len(hit_weapons)}")

    print("\n== classes ==")
    all_classes = ["Feca", "Osamodas", "Enutrof", "Sram", "Xelor", "Ecaflip",
                   "Eniripsa", "Iop", "Cra", "Sadida", "Sacrier", "Pandawa",
                   "Rogue", "Masqueraider", "Foggernaut", "Eliotrope",
                   "Huppermage", "Ouginak", "Forgelance"]
    touch_classes = filter_classes_for_version(all_classes, "touch")
    check("touch has exactly 15 classes", len(touch_classes) == 15, f"got {len(touch_classes)}")
    check("Foggernaut available on touch", "Foggernaut" in touch_classes)
    check("Forgelance NOT on touch", "Forgelance" not in touch_classes)
    check("Eliotrope NOT on touch", "Eliotrope" not in touch_classes)

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

    print("\n== set bonuses ==")
    con = sqlite3.connect(get_items_db_path("touch"))
    n_sets = con.execute("SELECT COUNT(DISTINCT item_set) FROM set_bonus").fetchone()[0]
    check("set bonuses populated (100+ sets)", n_sets >= 100, f"{n_sets} sets")
    ap_at_7 = con.execute(
        "SELECT sb.value FROM set_bonus sb JOIN stats st ON sb.stat=st.id "
        "WHERE st.name='AP' AND sb.num_pieces_used=7 AND sb.item_set IN "
        "(SELECT id FROM sets WHERE name LIKE '%Gobball%' OR name LIKE '%Bouftou%')").fetchall()
    check("Gobball 7-piece set grants +1 AP", any(r[0] == 1 for r in ap_at_7), f"ap_rows={ap_at_7}")

    print(f"\n{len(_passed)} passed, {len(_failed)} failed")
    if _failed:
        print("FAILED: " + ", ".join(_failed))
        return 1

    print("All touch checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
