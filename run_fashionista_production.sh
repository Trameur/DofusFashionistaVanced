#!/bin/bash

# Trap Ctrl+C
trap 'echo "Stopping server..."; exit' INT

BASE_DIR="$HOME/DofusFashionistaVanced"
FASHIONSITE_DIR="$BASE_DIR/fashionsite"

export PYTHONPATH="$PYTHONPATH:$BASE_DIR:$FASHIONSITE_DIR"

while true
do
    cd "$BASE_DIR" || exit 1

    bash -c './wipe_solution_cache.py'

    cd "$FASHIONSITE_DIR" || exit 1
    bash -c 'django-admin compilemessages'

    cd "$BASE_DIR" || exit 1

    bash -c 'gunicorn fashionsite.wsgi:application --bind 0.0.0.0:8000 --timeout 150'

    echo "Server crashed with exit code $?. Respawning..." >&2
    sleep 1
done
