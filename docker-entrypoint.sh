#!/bin/sh
set -e

echo "Starting DofusFashionistaVanced container..."

# Attendre que la base de données soit disponible
echo "Waiting for database to be available..."
until python -c "
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

# Collecter les fichiers statiques
echo "Collecting static files..."
python manage.py collectstatic --noinput --clear

echo "Starting Gunicorn server..."
# Démarrer Gunicorn avec les bonnes configurations
exec gunicorn fashionsite.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 3 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile - \
    --log-level info
