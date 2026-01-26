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

import io
import json
import os
import re

import requests
from PIL import Image, ImageChops, ImageStat

with open('transformed_equipment.json', 'r', encoding='utf-8') as file:
    data = json.load(file)

def sanitize_filename(name):
    return re.sub(r'[\\/*?:"<>|]', "", name)

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
current_directory = os.path.dirname(__file__)
target_directory = os.path.join(current_directory, '../fashionsite/staticfiles/chardata/')

total = len(data)
count = 0
last_percentage = -1
print(f"Total images to download: {total}")
for item in data:
    image_url = item.get('image_url')
    if image_url:
        original_name = f"{item['name_en']}.png"
        sanitized_name = sanitize_filename(original_name)

        if item['w_type'] == 'Petsmount' or item['w_type'] == 'Pet':
            directory = os.path.join(target_directory, "pets/")
        else:
            directory = os.path.join(target_directory, "items/")
        
        filename = os.path.join(directory, sanitized_name)
        
        if original_name != sanitized_name:
            print(f"Filename modified: {original_name} -> {sanitized_name}")
        
        download_image(image_url, filename)
        
        count += 1
        percentage = int((count / total) * 100)
        if percentage > last_percentage:
            print(f"Progress: {percentage}%")
            last_percentage = percentage