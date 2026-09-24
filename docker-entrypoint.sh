#!/bin/sh
set -e

# Unbuffered Python output: during the 2026-07-20 outage the boot looked
# frozen because every print was stuck in a stdio buffer while only the
# sqlite CLI's stderr reached the logs.
export PYTHONUNBUFFERED=1

echo "Starting DofusFashionistaVanced container..."

# Merge the existing configuration with the defaults
CONFIG_DIR="/etc/fashionista"
CONFIG_FILE="${CONFIG_DIR}/gen_config.json"

echo "Merging configuration files..."
python3 /app/merge_docker_config.py

# Wait for the database
echo "Waiting for database to be available..."
until python3 -c "
import pymysql
import sys
import os
try:
    conn = pymysql.connect(
        host=os.environ.get('DB_HOST', 'mysql'),
        port=int(os.environ.get('DB_PORT', '3306')),
        user=os.environ.get('DB_USER', 'fashionista'),
        password=os.environ['DB_PASSWORD'],
        database=os.environ.get('DB_NAME', 'fashionista')
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

# Django project folder
cd /app/fashionsite

# Django migrations
echo "Running Django migrations..."
python manage.py migrate --noinput

# Memoized solves are keyed on the player's request alone, not on the data or
# the solver, so every boot forgets them. Saved builds are left alone.
echo "Forgetting memoized solves..."
python manage.py clear_solution_cache || echo "solution cache not cleared"

# No --clear: the static_files volume persists between deploys, and --clear
# would copy every file again at each boot. The incremental copy is enough.
echo "Collecting static files..."
python manage.py collectstatic --noinput

# A body is 539 parts and takes 22 s to bake, a head 10 s. Baked on demand that
# lands on the first visitor of each class. Skipped when the bundles are absent.
echo "Baking character bodies and heads..."
python manage.py prebake_characters || echo "no character bundles, preview off"

# View records keep an IP address to count one visit per address per 24 h.
# The view also prunes as it goes, which covers long stretches without a deploy.
echo "Dropping view records older than a day..."
python manage.py cleanup_old_views || echo "view cleanup skipped"

# Nothing else deletes expired sessions.
echo "Dropping expired sessions..."
python manage.py clearsessions || echo "session cleanup skipped"

echo "Starting Gunicorn server..."
# On small instances, 2 workers is usually more stable than 3.
GUNICORN_WORKERS="${GUNICORN_WORKERS:-2}"

# Start Gunicorn
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
