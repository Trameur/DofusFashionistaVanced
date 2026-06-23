#!/usr/bin/env python3
# Copyright (C) 2026 The Dofus Fashionista — LGPL (see COPYING.LESSER)
"""Scrape the full transcendence-rune catalogue from the DofusDB API and
(optionally) mirror their icons locally.

Why this exists
---------------
"Runes de transcendance" (item type 211, "Rune de transcendance") are the
legendary FM runes that finalise an item at 100% success and then *prevent any
further forgemagie* ("Empêche les futures forgemagies"). They come from the
Songes Infinis, in 3 ranks (Ta / Pata / Rata) per stat. This script pulls the
whole roster so the smithmagic simulator can list them with real values + icons.

Outputs
-------
- chardata/forgemagie_transcendance.json  (catalogue consumed by the simulator)
- chardata/static/chardata/runes_transcendance/<iconId>.png  (with --images)

Usage
-----
    python scripts/scrape_transcendance_runes.py            # refresh the JSON
    python scripts/scrape_transcendance_runes.py --images   # + download icons

Notes
-----
- Read-only public API, no auth. Re-run after a major Dofus update to refresh.
- Corruption runes (bonus+malus) are not a current DofusDB item type in the
  Songes range (205-225); only transcendence (211) exists. If Ankama ships a
  corruption type later, add its id to RUNE_TYPE_IDS below.
"""
import argparse
import json
import os
import urllib.parse
import urllib.request

API = "https://api.dofusdb.fr"
RUNE_TYPE_IDS = [211]  # 211 = "Rune de transcendance"
HERE = os.path.dirname(os.path.abspath(__file__))
CHARDATA = os.path.normpath(os.path.join(HERE, "..", "fashionsite", "chardata"))
OUT_JSON = os.path.join(CHARDATA, "forgemagie_transcendance.json")
IMG_DIR = os.path.join(CHARDATA, "static", "chardata", "runes_transcendance")

# Ankama effectId -> (Fashionista FM stat key, FR label). Mirrors the keys used
# in forgemagie_data.py so transcendence runes line up with existing stats.
EID2STAT = {
    126: ("int", "Intelligence"), 118: ("str", "Force"), 119: ("agi", "Agilité"),
    123: ("cha", "Chance"), 125: ("vit", "Vitalité"), 174: ("init", "Initiative"),
    158: ("pod", "Pods"), 138: ("pow", "Puissance"),
    416: ("pshres", "Résistance Poussée"), 420: ("crires", "Résistance Critique"),
    414: ("pshdam", "Dommages Poussée"), 418: ("cridam", "Dommages Critique"),
    422: ("earthdam", "Dommages Terre"), 424: ("firedam", "Dommages Feu"),
    426: ("waterdam", "Dommages Eau"), 428: ("airdam", "Dommages Air"),
    430: ("neutdam", "Dommages Neutre"),
    2807: ("resperran", "Résistance % Distance"), 2803: ("respermee", "Résistance % Mêlée"),
    2812: ("perspedam", "Dommages % Sort"), 2808: ("perweadam", "Dommages % Arme"),
    2804: ("perrandam", "Dommages % Distance"), 2800: ("permedam", "Dommages % Mêlée"),
    752: ("dodge", "Fuite"), 753: ("lock", "Tacle"),
    160: ("apres", "Résistance PA"), 161: ("mpres", "Résistance PM"),
    410: ("apred", "Retrait PA"), 412: ("mpred", "Retrait PM"),
    210: ("earthresper", "Résistance % Terre"), 213: ("fireresper", "Résistance % Feu"),
    211: ("waterresper", "Résistance % Eau"), 212: ("airresper", "Résistance % Air"),
    214: ("neutresper", "Résistance % Neutre"),
    115: ("ch", "Coups Critiques"), 178: ("heals", "Soins"),
}
RANK = {"Ta": 1, "Pata": 2, "Rata": 3}


def _get(path, params):
    url = "%s/%s?%s" % (API, path, urllib.parse.urlencode(params, doseq=True))
    with urllib.request.urlopen(url, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_runes():
    runes, unmapped = [], set()
    for type_id in RUNE_TYPE_IDS:
        skip, total = 0, None
        while total is None or skip < total:
            page = _get("items", {
                "typeId": type_id, "$limit": 50, "$skip": skip, "$sort": "id",
                "lang": "fr",
                "$select[0]": "id", "$select[1]": "name", "$select[2]": "iconId",
                "$select[3]": "level", "$select[4]": "effects",
            })
            total = page.get("total", 0)
            for it in page.get("data", []):
                name = (it.get("name") or {}).get("fr") or ""
                parts = name.split()
                prefix = parts[1] if len(parts) > 1 else ""
                # main bonus = first effect on a real characteristic (cat 0/1)
                bonus_eff = next((e for e in it.get("effects", [])
                                  if e.get("category") in (0, 1) and e.get("effectId") in EID2STAT), None)
                if bonus_eff is None or prefix not in RANK:
                    unmapped.add((it.get("id"), name))
                    continue
                stat_key, stat_label = EID2STAT[bonus_eff["effectId"]]
                icon = it.get("iconId")
                runes.append({
                    "id": it["id"], "name_fr": name,
                    "rank": RANK[prefix], "rank_label": prefix,
                    "stat_key": stat_key, "stat_label": stat_label,
                    "bonus": bonus_eff.get("from", 0), "level": it.get("level"),
                    "icon_id": icon, "img": "%s/img/items/%d.png" % (API, icon),
                })
            skip += 50
    runes.sort(key=lambda r: r["id"])
    if unmapped:
        print("WARNING unmapped runes (add effectId to EID2STAT):", sorted(unmapped))
    return runes


def download_images(runes):
    os.makedirs(IMG_DIR, exist_ok=True)
    for r in runes:
        dest = os.path.join(IMG_DIR, "%d.png" % r["icon_id"])
        if os.path.exists(dest):
            continue
        try:
            urllib.request.urlretrieve(r["img"], dest)
            print("img", r["icon_id"])
        except Exception as exc:  # noqa
            print("FAIL img", r["icon_id"], exc)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--images", action="store_true", help="also download icons locally")
    args = ap.parse_args()
    runes = fetch_runes()
    out = {
        "source": "DofusDB API typeId=%s (Rune de transcendance)" % RUNE_TYPE_IDS,
        "mechanic": ("100% à la pose ; verrouille la FM (Empêche les futures "
                     "forgemagies) ; pose seulement si l'objet ne dépasse pas son jet max"),
        "count": len(runes), "runes": runes,
    }
    with open(OUT_JSON, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print("wrote %d runes -> %s" % (len(runes), OUT_JSON))
    if args.images:
        download_images(runes)


if __name__ == "__main__":
    main()
