#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script pour corriger l'erreur de syntaxe dans le fichier settings.py
de DofusFashionistaVanced.
"""

import os

print("Correction du fichier settings.py...")

# Chemin du fichier settings.py - Correction du chemin
settings_path = os.path.join(os.path.dirname(__file__), 'fashionsite', 'fashionsite', 'settings.py')

# Vérification de l'existence du fichier
if not os.path.exists(settings_path):
    print(f"Erreur: Le fichier {settings_path} n'existe pas")
    exit(1)

# Lecture du fichier
with open(settings_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Créer une sauvegarde
backup_path = settings_path + ".bak"
with open(backup_path, 'w', encoding='utf-8') as f:
    f.writelines(lines)
print(f"Sauvegarde créée: {backup_path}")

# Identifier la section problématique (rechercher l'accolade en trop)
for i, line in enumerate(lines):
    stripped = line.strip()
    if stripped == '}' and i > 0 and lines[i-1].strip().endswith('}'):
        # Vérifier si c'est l'accolade en trop après la définition de CACHES
        prev_section = ''.join(lines[max(0, i-10):i])
        if 'CACHES' in prev_section:
            # Supprimer l'accolade en trop
            print(f"Accolade en trop trouvée à la ligne {i+1}")
            lines[i] = ''  # Supprimer cette ligne
            break

# Écrire le fichier corrigé
with open(settings_path, 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("Correction terminée!")