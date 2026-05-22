#!/bin/bash
set -e

cd "$(dirname "$0")"

echo ">>> git pull"
git pull

echo ">>> rebuild & restart"
docker compose --profile production up -d --build

echo ">>> done"
docker compose ps
