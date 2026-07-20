#!/bin/bash
set -e

cd "$(dirname "$0")"

if [ -z "${DEPLOY_REEXECED:-}" ]; then
    echo ">>> git pull"
    git pull
    # deploy.sh / nginx.conf may have just been updated by the pull. Bash is already
    # running the PRE-pull version of this script, so its changes (the maintenance
    # logic below included) would not take effect until the NEXT deploy. Re-exec the
    # freshly pulled script so it applies on THIS run.
    export DEPLOY_REEXECED=1
    exec bash "$0" "$@"
fi

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

# Self-check: hit the origin directly (bypassing Cloudflare) and print the status.
# It should be 503 + the "updating" page. If users still see Cloudflare's error while
# this prints 503, the problem is Cloudflare-side (not the origin) -> share this line.
sleep 1
echo "    origin self-check (maintenance on): HTTP $(curl -sk -o /dev/null -w '%{http_code}' -H 'Host: dofusfashionista.gg' https://localhost/ 2>/dev/null || echo '??? (curl failed)')"

# Swap in the freshly built web image (migrations, collectstatic, gunicorn boot).
echo ">>> restart web"
docker compose --profile production up -d web

# Wait until web actually answers before lifting maintenance (up to ~10 min:
# the boot imports the item dumps before gunicorn listens, and they keep
# growing; 3 min was not enough once the monster data landed).
echo ">>> wait for web to come back"
web_up=0
for i in $(seq 1 300); do
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
