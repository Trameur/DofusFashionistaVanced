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

"""WSGI config for fashionsite; exposes the WSGI callable as application."""

import os
import sys
import platform

# Config file path per operating system
if platform.system() == 'Windows':
    config_file_path = os.path.join(os.environ['APPDATA'], 'fashionista', 'config')
else:
    config_file_path = '/etc/fashionista/config'

# Project root from the config file
try:
    with open(config_file_path) as f:
        path = f.read().strip()  # using strip() to remove any leading/trailing whitespace
except FileNotFoundError:
    # Fallback: parent of the current folder
    print(f"Configuration file not found: {config_file_path}")
    print("Using default project path as fallback")
    path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    # Create the config file for later runs
    try:
        os.makedirs(os.path.dirname(config_file_path), exist_ok=True)
        with open(config_file_path, 'w') as f:
            f.write(path)
        print(f"Created configuration file at {config_file_path}")
    except Exception as e:
        print(f"Warning: Could not create configuration file: {e}")

print(f"Using project path: {path}")

# Add the project paths to sys.path
sys.path.append(path)  # Adding the main project directory to sys.path

# On Windows, skip the Linux-only paths
if platform.system() != 'Windows':
    sys.path.append('/home/ec2-user/DofusFashionistaVanced')
    sys.path.append('/home/ec2-user/DofusFashionistaVanced/fashionistapulp')
    sys.path.append('/home/ec2-user/.local/lib/python3.9/site-packages')
    sys.path.append('/usr/local/lib/python3.9/site-packages')

sys.path.append(os.path.join(path, 'fashionistapulp'))
sys.path.append(os.path.join(path, 'fashionsite'))

os.environ['DJANGO_SETTINGS_MODULE'] = 'fashionsite.settings' 

# Start Django
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()

# Warm the encyclopedia caches in the background
import threading

def _warm_encyclopedia_caches():
    try:
        from chardata.encyclopedia_view import warm_caches
        warm_caches()
    except Exception:
        pass

threading.Thread(target=_warm_encyclopedia_caches, daemon=True,
                 name='encyclopedia-warmup').start()
