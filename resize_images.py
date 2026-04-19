#!/usr/bin/env python

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

from PIL import Image
import argparse
import os

FOLDERS = [
    'fashionsite/staticfiles/chardata/items/',
    'fashionsite/staticfiles/chardata/pets/',
    'fashionsite/chardata/static/chardata/items/',
    'fashionsite/chardata/static/chardata/pets/',
]

W = 60
H = 60
SUFFIX = '-%d-%d' % (W, H)

def resize_image(folder, item, new_folder):
    print('resize_image(%s, %s, %s)' % (folder, item, new_folder))
    file_path = os.path.join(folder, item)
    if os.path.isfile(file_path):
        file_name_without_ext, e = os.path.splitext(item)
        if e.lower() == '.png' and SUFFIX not in file_name_without_ext:
            im = Image.open(file_path)
            im_resized = im.resize((W, H))
            new_file_name = '%s%s%s' % (file_name_without_ext, SUFFIX, e)
            new_file_path = os.path.join(new_folder, new_file_name)
            im_resized.save(new_file_path)
            print('Writing %s' % new_file_path)

def resize_file_list(file_list):
    for file_path in file_list:
        folder, file_name = os.path.split(file_path)
        new_folder = get_new_folder_that_exists(folder)
        resize_image(folder, file_name, new_folder)

def resize_all():
    for folder in FOLDERS:
        new_folder = get_new_folder_that_exists(folder)
        dirs = os.listdir(folder)
        for item in dirs:
            resize_image(folder, item, new_folder)

def get_new_folder_that_exists(folder):
    new_folder = os.path.join(folder, '%dx%d' % (W, H))
    os.makedirs(new_folder, exist_ok=True)
    return new_folder

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('files', metavar='FILE', type=str, nargs='*',
                        help='files to be resized')
    args = parser.parse_args()
    
    if args.files:
        resize_file_list(args.files)
    else:
        resize_all()

if __name__ == '__main__':
    main()