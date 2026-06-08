#!/bin/bash
set -e

cd "$(dirname "$0")"

echo ">>> git pull"
git pull

# Build the new web image first. The old web container keeps serving during the
# build, so there is no downtime until the swap further down.
echo ">>> build web image"
docker compose --profile production build web

# Make sure nginx is running and apply any nginx.conf change via a live reload
# (no downtime, port 443 never drops). nginx must stay up across the web swap so
# users get the maintenance page instead of Cloudflare's origin-down error.
echo ">>> ensure nginx up & reload config"
docker compose --profile production up -d nginx
if docker compose --profile production exec -T nginx nginx -t 2>/dev/null; then
    docker compose --profile production exec -T nginx nginx -s reload || true
fi

# Swap in the freshly built web image. The brief restart gap (migrations,
# collectstatic, gunicorn boot) is covered by nginx error_page -> maintenance.html.
echo ">>> restart web"
docker compose --profile production up -d web

echo ">>> done"
docker compose --profile production ps
