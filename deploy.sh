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

# Raise the maintenance page for the whole restart window. nginx stays up and
# serves maintenance.html while the flag exists, so users get the "updating" page
# (not Cloudflare's origin-down error) even while web is fully down.
echo ">>> enable maintenance page"
docker compose --profile production exec -T nginx touch /tmp/maintenance.on || true

# Swap in the freshly built web image (migrations, collectstatic, gunicorn boot).
echo ">>> restart web"
docker compose --profile production up -d web

# Wait until web actually answers before lifting maintenance (up to ~3 min).
echo ">>> wait for web to come back"
web_up=0
for i in $(seq 1 90); do
    if docker compose --profile production exec -T web \
        curl -fsS -H 'Host: dofusfashionista.gg' http://localhost:8000/ >/dev/null 2>&1; then
        web_up=1
        echo "web is responding"
        break
    fi
    sleep 2
done
if [ "$web_up" != "1" ]; then
    echo "WARNING: web did not respond in time; leaving maintenance page up for safety."
fi

# Lower the maintenance page only once web is back.
if [ "$web_up" = "1" ]; then
    echo ">>> disable maintenance page"
    docker compose --profile production exec -T nginx rm -f /tmp/maintenance.on || true
fi

echo ">>> done"
docker compose --profile production ps
