#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (C) 2020 The Dofus Fashionista
# 
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at any later version).
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
# 
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

import boto3
import json
import os
import platform

# Utiliser le chemin de configuration approprié selon le système d'exploitation
if platform.system() == 'Windows':
    CONFIG_DIR = os.path.join(os.environ['APPDATA'], 'fashionista')
else:
    CONFIG_DIR = '/etc/fashionista'

# Ouvrir le fichier de configuration avec le chemin correct
config_file_path = os.path.join(CONFIG_DIR, 'gen_config.json')
try:
    with open(config_file_path, 'r') as f:
        GEN_CONFIGS = json.loads(f.read())
    DBBACKUP_S3_ACCESS_KEY = GEN_CONFIGS['DBBACKUP_S3_ACCESS_KEY']
    DBBACKUP_S3_SECRET_KEY = GEN_CONFIGS['DBBACKUP_S3_SECRET_KEY']
except FileNotFoundError:
    print(f"Configuration file not found: {config_file_path}")
    # Valeurs par défaut en cas d'erreur
    DBBACKUP_S3_ACCESS_KEY = None
    DBBACKUP_S3_SECRET_KEY = None

def get_s3_bucket(bucket):
    if DBBACKUP_S3_ACCESS_KEY is None or DBBACKUP_S3_SECRET_KEY is None:
        print("AWS credentials not configured. Please run configure_fashionista_root.py first.")
        return None
        
    session = boto3.Session(
        aws_access_key_id=DBBACKUP_S3_ACCESS_KEY,
        aws_secret_access_key=DBBACKUP_S3_SECRET_KEY
    )
    s3 = session.resource('s3')
    return s3.Bucket(bucket)

