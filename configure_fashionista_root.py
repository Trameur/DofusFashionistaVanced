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

import argparse
import platform
import sys
import getpass
import json
import os
from subprocess import call, check_call, run, PIPE
import shutil

if platform.system() == 'Windows':
    CONFIG_DIR = os.path.join(os.environ['APPDATA'], 'fashionista')
else:
    CONFIG_DIR = '/etc/fashionista'

PACKAGES_TO_INSTALL = {
    'apt-get': [
        'python3-pip',
        'sqlite3',
        'pngcrush',
        'imagemagick',
        'mariadb-server',
        'mariadb-client',
        'python3-dev',
        'libmariadb-dev',
        'libevent-dev',
        'memcached',
    ],
    'yum': [
        'python3-pip',
        'sqlite',
        'pngcrush',
        'ImageMagick',
        'mariadb-server',
        'mariadb',
        'python3-devel',
        'mariadb-devel',
        'libevent-devel',
        'memcached',
    ],
    # Added for Fedora
    'dnf': [
        'python3-pip',
        'sqlite',
        'pngcrush',
        'ImageMagick',
        'mariadb-server',
        'mariadb',
        'python3-devel',
        'mariadb-devel',
        'libevent-devel',
        'memcached',
    ],
    # Added for Windows 
    'windows': [
        'https://aka.ms/vs/17/release/vc_redist.x64.exe', # Visual C++ Redistributable
        'https://download.imagemagick.org/ImageMagick/download/binaries/ImageMagick-7.1.1-21-Q16-HDRI-x64-dll.exe', # ImageMagick
    ]
}

PIP_PACKAGES_TO_INSTALL = [
    'Django==4.2.6', # Updated Django version
    'python-social-auth==0.2.21', # Federated SSO.
    'social-auth-core',
    'social-auth-app-django',
    'PuLP', # Bindings for LP solver.
    'Scrapy', # Web crawler.
    'jsonpickle', # Powerful json encoder for ajax.
    'django-htmlmin', # Minifier for HTML.
    'boto3', # S3 client for uploading db.
    'pymysql',
    'python-memcached',
    'django-sslserver',
    'unidecode',
]

WINDOWS_PIP_PACKAGES = [
    'pillow',
    'mysql-connector-python',
    'lxml',
    'mysqlclient',
    'wheel',
]

GEN_CONFIG_FILE = {
    'PASSWORD_RESET_SALT': 'my_salt',
    'EMAIL_CONFIRMATION_SALT': 'my_salt_2',
    'SECRET_KEY': 'my_secret_key',
    "mysql_PASSWORD": "my_password",
    "mysql_USER": "root", 
    'EMAIL_HOST_USER': "my_username",
    'EMAIL_HOST_PASSWORD': "my_password",
    'SOCIAL_AUTH_GOOGLE_OAUTH2_KEY': None,
    'SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET': None,
    'SOCIAL_AUTH_FACEBOOK_KEY': None,
    'SOCIAL_AUTH_FACEBOOK_SECRET': None,
    'DBBACKUP_S3_ACCESS_KEY': None,
    'DBBACKUP_S3_SECRET_KEY': None,
    'url_captcha_secret': None,
    'char_id_SECRET_PART_1': 'my_secret',
    'char_id_SECRET_PART_2': 'my_other_secret',
    'google_analytics_id': None,
    'TESTER_USERS_EMAILS': ["my_email@here.com"],
    'SUPER_USERS_EMAILS': [],
    "EMAIL_USE_TLS": True,
    "EMAIL_HOST": "smtp@host.com",
    "EMAIL_PORT": 587,
}

def main():
    is_windows = platform.system() == 'Windows'
    
    if getpass.getuser() != 'root' and not is_windows:
        print('Run this script as root.')
        return
        
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--install_deps', action='store_true', help='install packages Fashionista depends on')
    parser.add_argument('-s', '--serve_static_files', action='store_true', help='serve static files instead of linking to S3')
    parser.add_argument('-d', '--debug_mode', action='store_true', help='run server in DEBUG mode')
    args = parser.parse_args()
    
    _print_header('Writing config files')
    if not os.path.exists(CONFIG_DIR):
        os.makedirs(CONFIG_DIR)
        
    path_config_file_path = os.path.join(CONFIG_DIR, 'config')
    with open(path_config_file_path, 'w') as f:
        f.write(os.getcwd())
    print(f'Wrote path to {path_config_file_path}')
    
    path_gen_config_file_path = os.path.join(CONFIG_DIR, 'gen_config.json')
    if not os.path.exists(path_gen_config_file_path):
        with open(path_gen_config_file_path, 'w') as f:
            f.write(json.dumps(GEN_CONFIG_FILE, indent=4, sort_keys=True))
        print(f'Wrote path to {path_gen_config_file_path}. Please fill it out manually.')
        input('Press Enter once it is done.')
    else:
        print(f'Skipping creation of {path_gen_config_file_path}: already exists.')
    
    static_config_file_path = os.path.join(CONFIG_DIR, 'serve_static')
    with open(static_config_file_path, 'w') as f:
        f.write(str(args.serve_static_files))
    print(f'Wrote serve static to {static_config_file_path}')

    debug_config_file_path = os.path.join(CONFIG_DIR, 'debug_mode')
    with open(debug_config_file_path, 'w') as f:
        f.write(str(args.debug_mode))
    print(f'Wrote debug mode to {debug_config_file_path}')

    with open(path_gen_config_file_path, 'r') as f:
        GEN_CONFIGS = json.load(f)
    
    mysql_config_file_path = os.path.join(os.path.expanduser('~'), '.my.cnf')
    with open(mysql_config_file_path, 'w') as f:
        f.write(f"""
[client]
user={GEN_CONFIGS['mysql_USER']}
password={GEN_CONFIGS['mysql_PASSWORD']}

[mysqldump]
user={GEN_CONFIGS['mysql_USER']}
password={GEN_CONFIGS['mysql_PASSWORD']}
""")
    if os.name == 'nt':  # Windows
        import stat
        os.chmod(mysql_config_file_path, stat.S_IREAD | stat.S_IWRITE)
    else:  # Unix/Linux
        call(['chmod', '644', mysql_config_file_path])
    print(f'Wrote MySQL config to {mysql_config_file_path}')

    if args.install_deps:
        _print_header('Installing dependencies')
        
        if is_windows:
            _install_windows_deps()
        else:
            package_manager = _get_package_manager()
            if package_manager:
                call(['sudo', package_manager, 'install', '-y'] + PACKAGES_TO_INSTALL[package_manager])
                call(['pip3', 'install'] + PIP_PACKAGES_TO_INSTALL)

    _print_header('Done')

def _install_windows_deps():
    _print_header("Installing Windows dependencies")
    
    temp_dir = os.path.join(os.environ['TEMP'], 'fashionista_deps')
    os.makedirs(temp_dir, exist_ok=True)
    
    try:
        run(['pip', '--version'], check=True, stdout=PIPE, stderr=PIPE)
    except:
        print("Pip n'est pas installé ou n'est pas dans le PATH.")
        print("Veuillez installer Python avec pip et réessayer.")
        return
    
    print("Installation des packages Python...")
    all_pip_packages = PIP_PACKAGES_TO_INSTALL + WINDOWS_PIP_PACKAGES
    run(['pip', 'install'] + all_pip_packages, check=True)
    
    print("Vérification de MySQL...")
    mysql_installed = False
    try:
        result = run(['mysql', '--version'], stdout=PIPE, stderr=PIPE)
        if result.returncode == 0:
            mysql_installed = True
            print("MySQL est déjà installé.")
    except:
        print("MySQL n'est pas installé ou n'est pas dans le PATH.")
    
    if not mysql_installed:
        print("\nVeuillez installer MySQL manuellement depuis:")
        print("https://dev.mysql.com/downloads/installer/")
        print("Choisissez l'option 'Server only' pendant l'installation.")
        input("Appuyez sur Entrée une fois MySQL installé...")
    
    print("\nTéléchargement et installation des dépendances supplémentaires...")
    for url in PACKAGES_TO_INSTALL['windows']:
        file_name = url.split('/')[-1]
        file_path = os.path.join(temp_dir, file_name)
        
        print(f"Téléchargement de {file_name}...")
        try:
            import urllib.request
            urllib.request.urlretrieve(url, file_path)
            
            print(f"Installation de {file_name}...")
            run([file_path], shell=True)
        except Exception as e:
            print(f"Erreur lors du téléchargement/installation de {file_name}: {e}")
            print(f"Veuillez télécharger et installer manuellement depuis:\n{url}")
    
    print("\nInstallation des dépendances Windows terminée.")
    print("Certains composants peuvent nécessiter une installation manuelle si des erreurs se sont produites.")

def _get_package_manager():
    if platform.system() == 'Windows':
        return 'windows'
        
    try:
        with open('/etc/os-release', 'r') as f:
            lines = f.read().lower()
        if 'ubuntu' in lines or 'debian' in lines:
            return 'apt-get'
        elif 'amzn' in lines or 'centos' in lines:
            return 'yum'
        elif 'fedora' in lines:
            return 'dnf'
    except Exception as e:
        print(f"Error determining package manager: {e}")
        return None

def _print_header(header):
    print('=' * 60)
    print(header)
    print('=' * 60)

if __name__ == '__main__':
    main()
