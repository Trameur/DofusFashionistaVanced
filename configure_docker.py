#!/usr/bin/env python
# Ce script est utilisé pour configurer les valeurs de base de données
# pour l'environnement Docker

import os
import json
import platform

# Définir le chemin du fichier de configuration selon le système d'exploitation
if platform.system() == 'Windows':
    CONFIG_DIR = os.path.join(os.environ['APPDATA'], 'fashionista')
else:
    CONFIG_DIR = '/etc/fashionista'

# Assurez-vous que le répertoire de configuration existe
os.makedirs(CONFIG_DIR, exist_ok=True)

# Charger la configuration existante si elle existe
config_path = os.path.join(CONFIG_DIR, 'gen_config.json')
if os.path.exists(config_path):
    with open(config_path, 'r') as f:
        config = json.load(f)
else:
    config = {}

# Mettre à jour la configuration pour utiliser la base de données Docker
config.update({
    "mysql_PASSWORD": "fashionista",
    "mysql_USER": "fashionista",
    "TESTER_USERS_EMAILS": []  # Ajouter la clé manquante
})

# Sauvegarder la configuration mise à jour
with open(config_path, 'w') as f:
    json.dump(config, f, indent=4)

# Mettre à jour également le fichier fashionsite/fashionsite/settings.py pour utiliser la base de données Docker
settings_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fashionsite', 'fashionsite', 'settings.py')
if os.path.exists(settings_path):
    with open(settings_path, 'r') as f:
        settings_content = f.read()
    
    # Remplacer 'localhost' par 'db' pour la connexion à la base de données
    settings_content = settings_content.replace("'HOST': 'localhost',", "'HOST': 'db',")
    
    with open(settings_path, 'w') as f:
        f.write(settings_content)

print("Configuration Docker terminée avec succès!")
