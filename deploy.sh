#!/bin/bash
set -e

cd "$(dirname "$0")"

echo ">>> git pull"
git pull

echo ">>> update nginx (if config changed)"
docker compose --profile production up -d nginx

echo ">>> rebuild & restart web"
docker compose --profile production up -d --build web

echo ">>> done"
docker compose ps
