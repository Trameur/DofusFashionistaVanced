#!/bin/bash
set -e

# Vérifier si docker et docker-compose sont installés
if ! command -v docker &> /dev/null; then
    echo "Docker n'est pas installé. Veuillez l'installer d'abord."
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "Docker Compose n'est pas installé. Veuillez l'installer d'abord."
    exit 1
fi

# Configuration du projet pour Docke
echo "Configuration du projet pour Docker..."
python configure_docker.py

# Construction des images Docke
echo "Construction des images Docker..."
docker-compose build

# Démarrage des conteneurs
echo "Démarrage des conteneurs..."
docker-compose up -d

echo ""
echo "=================================================="
echo "DofusFashionistaVanced est maintenant lancé!"
echo "Vous pouvez y accéder à l'adresse: http://localhost:8000"
echo "Pour voir les logs: docker-compose logs -f"
echo "Pour arrêter: docker-compose down"
echo "=================================================="
