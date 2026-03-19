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

import requests
import json

LANGUAGES = ['en', 'fr', 'es', 'pt', 'de']

# API base URL
api_base = "https://api.dofusdu.de/dofus3/v1/"

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


def download_and_save(lang, category, endpoint):
    api_url = f"{api_base}{lang}{endpoint}"
    response = requests.get(api_url, timeout=60)
    if response.status_code != 200:
        print(f"Failed to retrieve {category} data for {lang}. Status code: {response.status_code}")
        return

    json_data = response.json()
    filename = f"all_{category}_{lang}.json"
    with open(filename, 'w', encoding='utf-8') as out_file:
        json.dump(json_data, out_file, ensure_ascii=False, indent=4)
    print(f"Successfully saved all {category} data in {lang} to '{filename}'")


def main():
    for lang in LANGUAGES:
        for category, endpoint in endpoints.items():
            download_and_save(lang, category, endpoint)


if __name__ == '__main__':
    main()