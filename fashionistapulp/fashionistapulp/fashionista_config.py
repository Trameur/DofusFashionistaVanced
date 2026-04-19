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
import platform
import sys

path = None

def get_fashionista_path():
    global path
    if path is None:
        system_type = platform.system()
        config_file_path = ''
        if system_type == 'Windows':
            config_file_path = os.path.join(os.environ['APPDATA'], 'fashionista', 'config')
        else:  # Linux, macOS, etc.
            config_file_path = '/etc/fashionista/config'

        try:
            with open(config_file_path) as f:
                path = f.read().strip()
        except FileNotFoundError:
            # Si le fichier de configuration n'existe pas, on utilise le répertoire courant ou parent
            print(f"Configuration file not found: {config_file_path}")
            print("Using current directory as fallback")
            
            # Utiliser le répertoire parent du dossier fashionistapulp comme racine
            current_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            path = current_dir
            
            # Créer le fichier de configuration pour les futures utilisations
            try:
                os.makedirs(os.path.dirname(config_file_path), exist_ok=True)
                with open(config_file_path, 'w') as f:
                    f.write(path)
                print(f"Created configuration file at {config_file_path}")
            except Exception as e:
                print(f"Warning: Could not create configuration file: {e}")
    
    return path

def get_items_db_path():
    return os.path.join(get_fashionista_path(), 'fashionistapulp', 'fashionistapulp', 'items.db')

def get_items_dump_path():
    return os.path.join(get_fashionista_path(), 'fashionistapulp', 'fashionistapulp', 'item_db_dumped.dump')

def load_items_db_from_dump():
    run_root_script('load_item_db.py')

def save_items_db_to_dump():
    run_root_script('dump_item_db.py')

def run_root_script(script_path):
    python_cmd = "python" if platform.system() == 'Windows' else "python3"
    env_var = f'PYTHONPATH={os.path.join(get_fashionista_path(), "fashionistapulp")}'
    load_script_path = os.path.join(get_fashionista_path(), script_path)
    
    if platform.system() == 'Windows':
        # Utiliser une méthode qui fonctionne sur Windows
        os.environ['PYTHONPATH'] = os.path.join(get_fashionista_path(), "fashionistapulp")
        os.system(f'{python_cmd} {load_script_path}')
    else:
        # Méthode originale pour Linux/macOS
        os.system(f'{env_var} {load_script_path}')

serve_static = None

def serve_static_files():
    global serve_static
    if serve_static is None:
        system_type = platform.system()
        serve_static_file_path = ''
        if system_type == 'Windows':
            serve_static_file_path = os.path.join(os.environ['APPDATA'], 'fashionista', 'serve_static')
        else:  # Linux, macOS, etc.
            serve_static_file_path = '/etc/fashionista/serve_static'

        try:
            with open(serve_static_file_path) as f:
                serve_static = f.read().startswith('True')
        except FileNotFoundError:
            # Valeur par défaut si le fichier n'existe pas
            print(f"Static file configuration not found: {serve_static_file_path}")
            print("Using default value: True")
            serve_static = True
            
            # Tenter de créer le fichier pour les futures utilisations
            try:
                os.makedirs(os.path.dirname(serve_static_file_path), exist_ok=True)
                with open(serve_static_file_path, 'w') as f:
                    f.write("True")
            except Exception as e:
                print(f"Warning: Could not create static configuration file: {e}")
    
    return serve_static