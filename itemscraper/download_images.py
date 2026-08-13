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

import json
import os
import time
import requests


JSON_TO_DIR = {
    'transformed_equipment.json': 'items',
    #'itemswithurl.json': 'items',
    #'pets.json': 'pets',
    #'mounts.json': 'mounts',
}

def download_image(url, path):
    response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
    if response.status_code == 200:  # OK
        with open(path, 'wb') as f:
            f.write(response.content)
    else:
        print(f"Failed to download {url}. Status code: {response.status_code}")


def main():
    i = 1
    for json_file, folder_name in JSON_TO_DIR.items():
        folder = '../fashionsite/chardata/static/chardata/%s' % folder_name
        with open(json_file) as f:
            for entry in json.load(f):
                name = entry.get('name')
                if not name:
                    print('[%d] This entry doesnt have a name %s' % (i, entry))
                else:
                    image_path = folder + '/' + entry['name'] + '.png'
                    if not os.path.isfile(image_path):
                        image_url = entry.get('image_url')
                        if image_url:
                            image_path = os.path.join(folder, f"{name}.png")
                            print('[%d] Downloading %s' % (i, entry['name']))
                            download_image(entry['image_url'], image_path)
                            time.sleep(1)
                        else:
                            print('[%d] You need to manually download %s' % (i, entry['name']))
                    else:
                        print('Skipping %s' % entry['name'])
                i += 1

main()
