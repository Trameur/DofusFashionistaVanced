#!/usr/bin/env python

# Script pour appliquer spécifiquement les migrations Django pour l'application "chardata"
import os
import platform
import subprocess

def main():
    """Exécute les migrations Django pour réparer la table manquante "chardata_itemdbversion"."""
    print('=' * 60)
    print('Applying Django migrations for chardata app')
    print('=' * 60)
    
    # Détermine la commande Python à utiliser
    python_cmd = "python3" if platform.system() != "Windows" else "python"
    
    # Exécute la migration Django globale
    print("Exécution de migration générale...")
    subprocess.call([python_cmd, 'fashionsite/manage.py', 'migrate'])
    
    # Exécute spécifiquement la migration pour l'app chardata
    print("Exécution de migration spécifique pour chardata...")
    # On essaie d'abord sans l'option --fake-initial
    subprocess.call([python_cmd, 'fashionsite/manage.py', 'migrate', 'chardata'])
    
    # Si la première tentative échoue, on essaie avec --fake-initial
    print("Exécution de migration avec --fake-initial au cas où...")
    subprocess.call([python_cmd, 'fashionsite/manage.py', 'migrate', 'chardata', '--fake-initial'])
    
    print("Vérification de la création des tables...")
    subprocess.call([python_cmd, 'fashionsite/manage.py', 'showmigrations', 'chardata'])
    
    print('=' * 60)
    print('Migrations terminées')
    print('=' * 60)

if __name__ == '__main__':
    main()
