#!/bin/sh
set -e

echo "Starting DofusFashionistaVanced container..."

# Fusionner les configurations existantes avec les valeurs par défaut
CONFIG_DIR="/etc/fashionista"
CONFIG_FILE="${CONFIG_DIR}/gen_config.json"

# Exécuter le script Python pour fusionner les configurations
echo "Merging configuration files..."
python3 /app/merge_docker_config.py

# Attendre que la base de données soit disponible
echo "Waiting for database to be available..."
until python3 -c "
import pymysql
import sys
import os
try:
    conn = pymysql.connect(
        host='mysql',
        port=3306,
        user='fashionista',
        password='fashionista',
        database='fashionista'
    )
    conn.close()
    print('Database connection successful!')
    sys.exit(0)
except Exception as e:
    print(f'Database not yet available: {e}')
    sys.exit(1)
"; do
    echo "Database not yet available, waiting..."
    sleep 3
done

# Aller dans le répertoire du projet Django
cd /app/fashionsite

# Exécuter les migrations Django
echo "Running Django migrations..."
python manage.py migrate --noinput

# Collecter les fichiers statiques. Pas de --clear : le volume static_files
# persiste entre les deploys et --clear forcait la recopie COMPLETE des
# ~40k fichiers (webp monstres inclus) a chaque boot, soit plusieurs minutes
# de maintenance sur les I/O du VPS. La copie incrementale suffit ; les
# rares fichiers orphelins restent servis mais ne cassent rien.
echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Starting Gunicorn server..."
# On small instances, 2 workers is usually more stable than 3.
GUNICORN_WORKERS="${GUNICORN_WORKERS:-2}"

# Démarrer Gunicorn avec les bonnes configurations
exec gunicorn fashionsite.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers "${GUNICORN_WORKERS}" \
    --timeout 120 \
    --max-requests 1000 \
    --max-requests-jitter 100 \
    --keep-alive 5 \
    --access-logfile - \
    --error-logfile - \
    --log-level info
