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
import io
import json
import os
import sys
from pathlib import Path

import requests
from PIL import Image, ImageChops, ImageStat

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'fashionistapulp'))

from fashionistapulp.fashion_util import normalize_name, safe_icon_name


def sanitize_filename(name):
    # The runtime looks icons up under safe_icon_name(normalize_name(item)),
    # so the files must be written under that exact name.
    return safe_icon_name(normalize_name(name))


def images_differ(existing_path, new_content, threshold=0.01):
    """Return True if the difference between images exceeds the threshold."""
    if not os.path.exists(existing_path):
        return True
    try:
        with Image.open(existing_path) as old_img, Image.open(io.BytesIO(new_content)) as new_img:
            old_converted = old_img.convert('RGBA')
            new_converted = new_img.convert('RGBA')
            if old_converted.size != new_converted.size:
                return True
            diff = ImageChops.difference(old_converted, new_converted)
            stat = ImageStat.Stat(diff)
            total_components = diff.size[0] * diff.size[1] * len(diff.getbands())
            diff_ratio = sum(stat.sum) / (255 * total_components)
            return diff_ratio > threshold
    except Exception as exc:
        print(f"Image comparison failed for {existing_path}: {exc}. Overwriting.")
        return True


def download_image(url, filename, threshold=0.01):
    response = requests.get(url)
    if response.status_code != 200:
        print(f"Failed to download {url}: HTTP {response.status_code}")
        return False
    new_content = response.content
    if not images_differ(filename, new_content, threshold):
        print(f"Skipping {filename}: change below {threshold * 100:.2f}%.")
        return False
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    with open(filename, 'wb') as file:
        file.write(new_content)
    return True


def main():
    parser = argparse.ArgumentParser(description="Download Dofus item images")
    parser.add_argument("--game-version", default="dofus3",
                        help="Game version (dofus3, beta, retro, touch). Default: dofus3")
    parser.add_argument("--input-file", default=None,
                        help="Path to transformed_equipment.json (default: ./transformed_equipment.json)")
    args = parser.parse_args()

    game_version = args.game_version
    input_file = args.input_file or os.path.join(os.path.dirname(__file__), 'transformed_equipment.json')

    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    current_directory = os.path.dirname(os.path.abspath(__file__))
    # dofus3 and touch share the root items/ directory.
    version_subdir = '' if game_version in ('dofus3', 'touch') else game_version + '/'

    target_directories = [
        os.path.join(current_directory, '../fashionsite/staticfiles/chardata/'),
        os.path.join(current_directory, '../fashionsite/chardata/static/chardata/'),
    ]

    total = len(data)
    count = 0
    last_percentage = -1
    print(f"Total images to download: {total}")
    for item in data:
        image_url = item.get('image_url')
        if image_url:
            original_name = f"{item['name_en']}.png"
            sanitized_name = f"{sanitize_filename(item['name_en'])}.png"
            if original_name != sanitized_name:
                print(f"Filename modified: {original_name} -> {sanitized_name}")

            for target_directory in target_directories:
                _MOUNT_TYPES = ('Petsmount', 'Pet', 'Dragoturkey', 'Seemyool', 'Rhineetle',
                                'Dragodinde', 'Muldo', 'Volkorne', 'Mount')
                type_subdir = "pets/" if any(t in item.get('w_type', '') for t in _MOUNT_TYPES) else "items/"
                directory = os.path.join(target_directory, type_subdir, version_subdir)
                filename = os.path.join(directory, sanitized_name)
                download_image(image_url, filename)

            count += 1
            percentage = int((count / total) * 100)
            if percentage > last_percentage:
                print(f"Progress: {percentage}%")
                last_percentage = percentage


if __name__ == '__main__':
    main()
