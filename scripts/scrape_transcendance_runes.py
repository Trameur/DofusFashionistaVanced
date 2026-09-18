#!/usr/bin/env python3
# Copyright (C) 2026 The Dofus Fashionista — LGPL (see COPYING.LESSER)
"""Scrape the transcendence runes from DofusDB and mirror their icons.

    python scripts/scrape_transcendance_runes.py
"""
import argparse
import io
import json
import os
import urllib.parse
import urllib.request

from PIL import Image

API = "https://api.dofusdb.fr"
RUNE_TYPE_IDS = [211]  # 211 = "Rune de transcendance"
HERE = os.path.dirname(os.path.abspath(__file__))
CHARDATA = os.path.normpath(os.path.join(HERE, "..", "fashionsite", "chardata"))
OUT_JSON = os.path.join(CHARDATA, "forgemagie_transcendance.json")
IMG_DIR = os.path.join(CHARDATA, "static", "chardata", "runes_transcendance")
# Same size as the other mirrored artwork (chardata/monsters/96)
ICON_PX = 96

# Ankama effectId -> (FM stat key from forgemagie_data.py, FR label)
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


# Ankama names each rune differently per language
LANGUAGES = ("fr", "en", "es", "pt", "de")


def _noms(item):
    """{language: name}"""
    noms = item.get("name") or {}
    return dict((langue, noms.get(langue) or "") for langue in LANGUAGES)


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
                "$select[0]": "id", "$select[1]": "name", "$select[2]": "iconId",
                "$select[3]": "level", "$select[4]": "effects",
                "$select[5]": "possibleEffects",
            })
            total = page.get("total", 0)
            for it in page.get("data", []):
                # Rank from the French name, other clients rename it (es: Ta/Buta/Suta)
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
                # Effect 2826 = rune weight, zeroed in effects, so read possibleEffects
                weight_eff = next((e for e in it.get("possibleEffects", [])
                                   if e.get("effectId") == 2826), None)
                if weight_eff is None or not weight_eff.get("value"):
                    unmapped.add((it.get("id"), name + " [no weight]"))
                    continue
                runes.append({
                    "id": it["id"], "name": _noms(it),
                    "rank": RANK[prefix], "rank_label": prefix,
                    "stat_key": stat_key, "stat_label": stat_label,
                    "bonus": bonus_eff.get("from", 0),
                    "weight": weight_eff["value"],
                    "level": it.get("level"),
                    "icon_id": icon,
                })
            skip += 50
    runes.sort(key=lambda r: r["id"])
    if unmapped:
        print("WARNING unmapped runes (add effectId to EID2STAT):", sorted(unmapped))
    return runes


def icon_source(icon_id):
    """DofusDB icon url, for the mirror only."""
    return "%s/img/items/%d.png" % (API, icon_id)


def download_images(runes):
    os.makedirs(IMG_DIR, exist_ok=True)
    manquants = []
    for r in runes:
        dest = os.path.join(IMG_DIR, "%d.webp" % r["icon_id"])
        if os.path.exists(dest):
            continue
        try:
            with urllib.request.urlopen(icon_source(r["icon_id"]),
                                        timeout=30) as resp:
                octets = resp.read()
            image = Image.open(io.BytesIO(octets)).convert("RGBA")
            image = image.resize((ICON_PX, ICON_PX), Image.LANCZOS)
            image.save(dest, "WEBP", quality=90, method=6)
            print("img", r["icon_id"])
        except Exception as exc:  # noqa
            manquants.append((r["icon_id"], exc))
            print("FAIL img", r["icon_id"], exc)
    if manquants:
        print("MISSING %d icon(s); the page will show a hole for each"
              % len(manquants))


def main():
    # Rejects the old --images flag
    argparse.ArgumentParser().parse_args()
    runes = fetch_runes()
    out = {
        "source": "DofusDB API typeId=%s (Rune de transcendance)" % RUNE_TYPE_IDS,
        "mechanic": ("100% à la pose (effet 2827) ; verrouille la FM (effet 2825, "
                     "Empêche les futures forgemagies) ; pose légale seulement si "
                     "l'objet n'a ni over ni ligne exotique ET si poids de la rune "
                     "(effet 2826) + poids actuel de la stat visée <= 101"),
        "count": len(runes), "runes": runes,
    }
    with open(OUT_JSON, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print("wrote %d runes -> %s" % (len(runes), OUT_JSON))
    download_images(runes)


if __name__ == "__main__":
    main()
