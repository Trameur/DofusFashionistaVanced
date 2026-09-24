#!/bin/bash
# Dumps the production database to /root/backups and checks the dump before trusting it.
set -euo pipefail

CONTAINER="${MYSQL_CONTAINER:-fashionista_mysql}"
BACKUP_DIR="${BACKUP_DIR:-/root/backups}"
STAMP="$(date +%Y%m%d_%H%M%S)"
TARGET="$BACKUP_DIR/fashionista_$STAMP.sql.gz"

if ! docker inspect -f '{{.State.Running}}' "$CONTAINER" 2>/dev/null | grep -q true; then
    echo "ERROR: container $CONTAINER is not running." >&2
    exit 1
fi

mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

schema_mb="$(docker exec "$CONTAINER" sh -c \
    'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -uroot --batch --skip-column-names -e "SELECT CEIL(SUM(data_length + index_length) / 1048576) FROM information_schema.tables WHERE table_schema = DATABASE()" "$MYSQL_DATABASE"' \
    | tr -d '\r')"
free_mb="$(df -Pm "$BACKUP_DIR" | awk 'NR == 2 {print $4}')"
if [ "$free_mb" -lt $((schema_mb + 2048)) ]; then
    echo "ERROR: $free_mb MB free in $BACKUP_DIR for a $schema_mb MB database; free some space first." >&2
    exit 1
fi

echo ">>> dumping the database ($schema_mb MB) to $TARGET"
if ! docker exec "$CONTAINER" sh -c \
        'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysqldump -uroot --single-transaction --routines --triggers --events --set-gtid-purged=OFF --databases "$MYSQL_DATABASE"' \
        | gzip -c > "$TARGET.partial"; then
    rm -f "$TARGET.partial"
    echo "ERROR: mysqldump failed, nothing was kept." >&2
    exit 1
fi

echo ">>> checking the dump"
gzip -t "$TARGET.partial"
if ! gzip -dc "$TARGET.partial" | tail -n 1 | grep -q '^-- Dump completed'; then
    echo "ERROR: the dump does not end with '-- Dump completed', keeping it as $TARGET.partial for inspection." >&2
    exit 1
fi
tables="$(gzip -dc "$TARGET.partial" | grep -c '^CREATE TABLE' || true)"
if [ "$tables" -lt 10 ]; then
    echo "ERROR: only $tables tables in the dump, keeping it as $TARGET.partial for inspection." >&2
    exit 1
fi

mv "$TARGET.partial" "$TARGET"
chmod 600 "$TARGET"
echo ">>> backup ok: $TARGET ($(du -h "$TARGET" | cut -f1), $tables tables)"
