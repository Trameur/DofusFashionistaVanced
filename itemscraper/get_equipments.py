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

import argparse
import os
from pathlib import Path
import requests
import json

from download_raw_data import DEFAULT_REPO, download_assets
import release_items

LANGUAGES = ['en', 'fr', 'es', 'pt', 'de']

DEFAULT_API_BASE = "https://api.dofusdu.de/dofus3/v1/"
RAW_DIR = Path(__file__).resolve().parent / "raw"

# Endpoints
endpoints = {
    "equipment": "/items/equipment/all",
    "resources": "/items/resources/all",
    "consumables": "/items/consumables/all",
    "quest_items": "/items/quest/all",
    "cosmetics": "/items/cosmetics/all",
    "mounts": "/mounts/all",
    "sets": "/sets/all"
}


def download_and_save(lang, category, endpoint, api_base, work_dir):
    api_url = f"{api_base}{lang}{endpoint}"
    response = requests.get(api_url, timeout=60)
    if response.status_code != 200:
        print(f"Failed to retrieve {category} data for {lang}. Status code: {response.status_code}")
        return

    save(work_dir, category, lang, response.json())


def save(work_dir, category, lang, json_data):
    filename = os.path.join(work_dir, f"all_{category}_{lang}.json")
    with open(filename, 'w', encoding='utf-8') as out_file:
        json.dump(json_data, out_file, ensure_ascii=False, indent=4)
    print(f"Successfully saved all {category} data in {lang} to '{filename}'")


def served_version(api_base):
    response = requests.get(f"{api_base}meta/version", timeout=60)
    response.raise_for_status()
    return response.json()["version"]


def read_json(path):
    with open(path, encoding='utf-8') as handle:
        return json.load(handle)


def rebuild_from_release(repo, tag, api_base, work_dir, categories):
    download_assets(repo, tag, RAW_DIR, filters=list(release_items.ASSETS), skip_existing=False)
    release_dir = RAW_DIR / tag
    missing = [name for name in release_items.ASSETS if not (release_dir / name).is_file()]
    if missing:
        raise SystemExit(f"Release {repo}@{tag} lacks {', '.join(missing)}: items cannot be rebuilt")
    items, sets, recipes = (read_json(release_dir / name) for name in release_items.ASSETS)
    pages = release_items.rebuild(items, sets, recipes, f"{api_base}img/item", categories)
    for lang in LANGUAGES:
        for category in categories:
            save(work_dir, category, lang, pages[category, lang])


def main(argv=None):
    parser = argparse.ArgumentParser(description="Download Dofus equipment data from dofusdu.de API")
    parser.add_argument("--api-url", default=DEFAULT_API_BASE, help="API base URL (default: dofus3)")
    parser.add_argument("--work-dir", default=None, help="Directory to save downloaded JSON files (default: script directory)")
    parser.add_argument("--skip-endpoints", nargs="*", default=[], metavar="CATEGORY",
                        help="Endpoint categories to skip (e.g. mounts)")
    parser.add_argument("--tag", help="Version to import: read from the API only when it serves this version, "
                                      "rebuilt from the release files of this tag otherwise")
    parser.add_argument("--repo", default=DEFAULT_REPO, help="dofusdude release repo for --tag")
    args = parser.parse_args(argv)

    api_base = args.api_url
    if not api_base.endswith('/'):
        api_base += '/'

    work_dir = args.work_dir if args.work_dir else os.path.dirname(os.path.abspath(__file__))
    os.makedirs(work_dir, exist_ok=True)

    categories = [category for category in endpoints if category not in args.skip_endpoints]
    if args.tag:
        served = served_version(api_base)
        if served != args.tag:
            print(f"Warning: the dofusdude API serves {served}, not {args.tag}: "
                  f"items rebuilt from the {args.tag} release files")
            rebuild_from_release(args.repo, args.tag, api_base, work_dir, categories)
            return
        print(f"Items from the dofusdude API, which serves {served}")
    for lang in LANGUAGES:
        for category in categories:
            download_and_save(lang, category, endpoints[category], api_base, work_dir)


if __name__ == '__main__':
    main()