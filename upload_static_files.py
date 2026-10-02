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

import os
import csv
import json
import mimetypes
import platform
import sys
from subprocess import call
import s3_fashionista

REPO_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_ROOT = os.path.join(REPO_DIR, 'fashionsite', 'staticfiles')
STATIC_FILE_MAP = os.path.join(REPO_DIR, 'static_file_map.csv')
MANIFEST_NAME = 'staticfiles.json'
CACHE_CONTROL = 'public, max-age=2592000, no-transform'
if platform.system() == 'Windows':
    CONFIG_DIR = os.path.join(os.environ['APPDATA'], 'fashionista')
else:
    CONFIG_DIR = '/etc/fashionista'

DBBACKUP_S3_BUCKET = 'fashionistavanced'

def main():
    config_file_path = os.path.join(CONFIG_DIR, 'serve_static')
    try:
        with open(config_file_path) as f:
            serve_static = f.read().startswith('True')
            if not serve_static:
                print('Fashionista needs to be configured with serve_static=True')
                exit(1)
    except FileNotFoundError:
        print(f"Configuration file not found: {config_file_path}")
        print("Please run configure_fashionista_root.py -s first")
        exit(1)

    old_map = {}
    with open(STATIC_FILE_MAP, 'r', newline='', encoding='utf-8') as file_map_old:
        csvreader = csv.reader(file_map_old)
        for row in csvreader:
            if len(row) > 0:
                old_map[row[0]] = row[1]

    call([sys.executable, 'manage.py', 'collectstatic', '--noinput'],
         cwd=os.path.join(REPO_DIR, 'fashionsite'))

    new_map = read_manifest()
    if new_map is None:
        print('No %s in %s: collectstatic hashes the file names only with DEBUG off.'
              % (MANIFEST_NAME, STATIC_ROOT))
        exit(1)

    with open(STATIC_FILE_MAP, 'w', newline='', encoding='utf-8') as file_map:
        csvwriter = csv.writer(file_map)
        for original_name in sorted(new_map):
            csvwriter.writerow([original_name, new_map[original_name]])

    bucket = s3_fashionista.get_s3_bucket(DBBACKUP_S3_BUCKET)
    if bucket:
        for original_name in sorted(new_map):
            new_name = new_map[original_name]
            if original_name not in old_map:
                print('Uploading ' + original_name + ': not in original map')
            elif old_map[original_name] != new_name:
                print('Uploading ' + original_name + ': Hash changed')
            else:
                continue
            upload(bucket, os.path.join(STATIC_ROOT, new_name), new_name)
    else:
        print("S3 bucket configuration incomplete. Static files will not be uploaded.")

def read_manifest():
    try:
        with open(os.path.join(STATIC_ROOT, MANIFEST_NAME), encoding='utf-8') as manifest:
            return json.load(manifest)['paths']
    except FileNotFoundError:
        return None

def upload(bucket, local_path, key_name):
    extra_args = {'CacheControl': CACHE_CONTROL}
    content_type = mimetypes.guess_type(local_path)[0]
    if content_type:
        extra_args['ContentType'] = content_type
    bucket.upload_file(local_path, key_name, ExtraArgs=extra_args, Callback=_update_progress)

def _update_progress(bytes_amount):
    print('%d bytes transferred' % bytes_amount)
              
if __name__ == '__main__':
    main()
