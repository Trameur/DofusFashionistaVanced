#!/bin/bash

trap 'echo "Stopping server..."; exit' INT

PYTHON="${PYTHON:-$(command -v python3.14 || command -v python3)}"

while true
do
    export PYTHONPATH=$PYTHONPATH:~/DofusFashionistaVanced/fashionistapulp

    "$PYTHON" wipe_solution_cache.py

    cd fashionsite
    "$PYTHON" -m django compilemessages
    cd ..

    "$PYTHON" fashionsite/manage.py runserver 0.0.0.0:8000

    echo "Server crashed with exit code $?. Respawning..." >&2
    sleep 1
done
