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
import platform
import tempfile
from subprocess import call, run
import s3_fashionista

# Utiliser un répertoire temporaire approprié selon le système d'exploitation
if platform.system() == 'Windows':
    STATIC_ROOT = os.path.join(tempfile.gettempdir(), 'statictemp')
    CONFIG_DIR = os.path.join(os.environ['APPDATA'], 'fashionista')
else:
    STATIC_ROOT = '/tmp/statictemp'
    CONFIG_DIR = '/etc/fashionista'

DBBACKUP_S3_BUCKET = 'fashionistavanced'

def main():
    # Utiliser le chemin de configuration approprié
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

    # Nettoyer le répertoire temporaire de manière compatible avec Windows/Linux
    if platform.system() == 'Windows':
        if os.path.exists(STATIC_ROOT):
            import shutil
            shutil.rmtree(STATIC_ROOT, ignore_errors=True)
        os.makedirs(STATIC_ROOT, exist_ok=True)
    else:
        call(['rm', '-rf', STATIC_ROOT])

    old_map = {}
    with open('static_file_map.csv', 'r', newline='', encoding='utf-8') as file_map_old:
        csvreader = csv.reader(file_map_old)
        for row in csvreader:
            if len(row) > 0:
                old_map[row[0]] = row[1]
    
    new_map = {}
    keys = []
    with open('static_file_map.csv', 'w', newline='', encoding='utf-8') as file_map:
    
        os.chdir('fashionsite')
        # Utiliser python ou python3 selon le système
        python_cmd = 'python' if platform.system() == 'Windows' else 'python3'
        if platform.system() == 'Windows':
            run([python_cmd, 'manage.py', 'collectstatic', '--noinput'], shell=True)
        else:
            call([python_cmd, 'manage.py', 'collectstatic', '--noinput'])
        
        csvwriter = csv.writer(file_map)
    
        os.chdir(STATIC_ROOT)
        for root, subdirs, files in os.walk(STATIC_ROOT):
            for file_name in files:
                pieces = file_name.split('.')
                if len(pieces) >= 3:
                    len_pieces = len(pieces)
                    original = os.path.relpath(root, start=STATIC_ROOT) + '/'
                    new = os.path.relpath(root, start=STATIC_ROOT) + '/'
                    for i in range(0, len_pieces-2):
                        original += pieces[i] + '.'
                        new += pieces[i] + '.'
                    original += pieces[len_pieces-1]
                    new += pieces[len_pieces-2] + '.' + pieces[len_pieces-1]                
                    keys.append(original)
                    new_map[original] = new
        
        keys.sort()
        for original_name in keys:
            csvwriter.writerow([original_name, new_map[original_name]])
        
        bucket = s3_fashionista.get_s3_bucket(DBBACKUP_S3_BUCKET)
        if bucket:
            for (original_name, new_name) in new_map.items():
                if original_name not in old_map:
                    print('Uploading ' + original_name + ': not in original map')
                    key = bucket.new_key(new_name)
                    key.set_contents_from_filename(new_name, cb=_update_progress, num_cb=1)
                else:
                    if old_map[original_name] != new_map[original_name]:
                        print('Uploading ' + original_name + ': Hash changed')
                        key = bucket.new_key(new_name)
                        key.set_contents_from_filename(new_name, cb=_update_progress, num_cb=1)
        else:
            print("S3 bucket configuration incomplete. Static files will not be uploaded.")

def _update_progress(so_far, total):
   print('%d bytes transferred out of %d' % (so_far, total))
              
if __name__ == '__main__':
    main()
