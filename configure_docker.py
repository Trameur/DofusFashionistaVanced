#!/usr/bin/env python
# Sets the database values for the Docker environment

import os
import json
import platform

# Configuration folder for the operating system
if platform.system() == 'Windows':
    CONFIG_DIR = os.path.join(os.environ['APPDATA'], 'fashionista')
else:
    CONFIG_DIR = '/etc/fashionista'

os.makedirs(CONFIG_DIR, exist_ok=True)

# Existing configuration, if any
config_path = os.path.join(CONFIG_DIR, 'gen_config.json')
if os.path.exists(config_path):
    with open(config_path, 'r') as f:
        config = json.load(f)
else:
    config = {}

# Point the configuration at the Docker database
config.update({
    "mysql_PASSWORD": "fashionista",
    "mysql_USER": "fashionista",
    "TESTER_USERS_EMAILS": []  # the missing key
})

with open(config_path, 'w') as f:
    json.dump(config, f, indent=4)

# Point fashionsite/fashionsite/settings.py at the Docker database too
settings_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fashionsite', 'fashionsite', 'settings.py')
if os.path.exists(settings_path):
    with open(settings_path, 'r') as f:
        settings_content = f.read()
    
    settings_content = settings_content.replace("'HOST': 'localhost',", "'HOST': 'db',")
    
    with open(settings_path, 'w') as f:
        f.write(settings_content)

print("Docker configuration done.")
