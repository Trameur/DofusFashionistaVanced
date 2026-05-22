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
import requests
import json

LANGUAGES = ['en', 'fr', 'es', 'pt', 'de']

DEFAULT_API_BASE = "https://api.dofusdu.de/dofus3/v1/"

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

    json_data = response.json()
    filename = os.path.join(work_dir, f"all_{category}_{lang}.json")
    with open(filename, 'w', encoding='utf-8') as out_file:
        json.dump(json_data, out_file, ensure_ascii=False, indent=4)
    print(f"Successfully saved all {category} data in {lang} to '{filename}'")


def main():
    parser = argparse.ArgumentParser(description="Download Dofus equipment data from dofusdu.de API")
    parser.add_argument("--api-url", default=DEFAULT_API_BASE, help="API base URL (default: dofus3)")
    parser.add_argument("--work-dir", default=None, help="Directory to save downloaded JSON files (default: script directory)")
    parser.add_argument("--skip-endpoints", nargs="*", default=[], metavar="CATEGORY",
                        help="Endpoint categories to skip (e.g. mounts)")
    args = parser.parse_args()

    api_base = args.api_url
    if not api_base.endswith('/'):
        api_base += '/'

    work_dir = args.work_dir if args.work_dir else os.path.dirname(os.path.abspath(__file__))
    os.makedirs(work_dir, exist_ok=True)

    skip = set(args.skip_endpoints)
    for lang in LANGUAGES:
        for category, endpoint in endpoints.items():
            if category in skip:
                continue
            download_and_save(lang, category, endpoint, api_base, work_dir)


if __name__ == '__main__':
    main()