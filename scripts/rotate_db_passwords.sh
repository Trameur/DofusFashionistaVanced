#!/bin/bash
# Rotates the MySQL passwords with no downtime: the old ones stay valid until --discard.
#
#   scripts/rotate_db_passwords.sh            new random passwords into .env, old ones kept
#   ./deploy.sh                               web and mysql restart on the new passwords
#   scripts/rotate_db_passwords.sh --discard  the old passwords stop working
#   scripts/rotate_db_passwords.sh --abort    undo a rotation that was not deployed
set -euo pipefail
set -f

cd "$(dirname "$0")/.."
MYSQL_CONTAINER="${MYSQL_CONTAINER:-fashionista_mysql}"
WEB_CONTAINER="${WEB_CONTAINER:-fashionista_web}"
BACKUP_DIR="${BACKUP_DIR:-/root/backups}"
ENV_FILE=".env"
PENDING="$ENV_FILE.pending"
APP_USER="fashionista"

die() {
    echo "ERROR: $*" >&2
    exit 1
}

env_value() {
    [ -f "$1" ] || return 0
    grep -E "^$2=" "$1" | tail -n 1 | cut -d= -f2- || true
}

container_env() {
    docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' "$1" \
        | tr -d '\r' | grep -E "^$2=" | cut -d= -f2- || true
}

run_sql_as_root() {
    docker exec -i "$MYSQL_CONTAINER" sh -c \
        'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -uroot --batch --skip-column-names' | tr -d '\r'
}

can_login() {
    printf '%s\n' "$2" | docker exec -i "$MYSQL_CONTAINER" sh -c \
        'read -r P; MYSQL_PWD="$P" mysql -u"$0" --batch --skip-column-names -e "SELECT 1" >/dev/null 2>&1' "$1"
}

hosts_of() {
    printf "SELECT host FROM mysql.user WHERE user='%s';\n" "$1" | run_sql_as_root
}

secondary_passwords() {
    printf "SELECT COUNT(*) FROM mysql.user WHERE user IN ('root', '%s') AND JSON_CONTAINS_PATH(User_attributes, 'one', '\$.additional_password');\n" "$APP_USER" \
        | run_sql_as_root
}

site_answers() {
    docker exec "$WEB_CONTAINER" curl -fsS -o /dev/null -H 'Host: dofusfashionista.gg' http://localhost:8000/
}

without_password_lines() {
    [ -s "$1" ] || return 0
    grep -vE '^(MYSQL_ROOT_PASSWORD|DB_PASSWORD)=' "$1" || true
}

for container in "$MYSQL_CONTAINER" "$WEB_CONTAINER"; do
    docker inspect -f '{{.State.Running}}' "$container" 2>/dev/null | grep -q true \
        || die "container $container is not running"
done

root_hosts="$(hosts_of root)"
app_hosts="$(hosts_of "$APP_USER")"
[ -n "$root_hosts" ] || die "no root account found in mysql.user"
[ -n "$app_hosts" ] || die "no $APP_USER account found in mysql.user"
in_use_root="$(container_env "$MYSQL_CONTAINER" MYSQL_ROOT_PASSWORD)"
in_use_app="$(container_env "$WEB_CONTAINER" DB_PASSWORD)"

if [ "${1:-}" = "--abort" ]; then
    can_login root "$in_use_root" || die "the root password of $MYSQL_CONTAINER does not log in; nothing changed"
    can_login "$APP_USER" "$in_use_app" || die "the password of $WEB_CONTAINER does not log in; nothing changed"
    echo ">>> putting back the passwords the containers run with"
    trap '' HUP INT TERM
    {
        for host in $root_hosts; do
            printf "ALTER USER 'root'@'%s' IDENTIFIED BY '%s';\n" "$host" "$in_use_root"
            printf "ALTER USER 'root'@'%s' DISCARD OLD PASSWORD;\n" "$host"
        done
        for host in $app_hosts; do
            printf "ALTER USER '%s'@'%s' IDENTIFIED BY '%s';\n" "$APP_USER" "$host" "$in_use_app"
            printf "ALTER USER '%s'@'%s' DISCARD OLD PASSWORD;\n" "$APP_USER" "$host"
        done
    } | run_sql_as_root
    can_login root "$in_use_root" || die "root no longer logs in after the abort"
    can_login "$APP_USER" "$in_use_app" || die "$APP_USER no longer logs in after the abort"
    if [ "$(env_value "$ENV_FILE" DB_PASSWORD)" != "$in_use_app" ] \
            || [ "$(env_value "$ENV_FILE" MYSQL_ROOT_PASSWORD)" != "$in_use_root" ]; then
        umask 077
        without_password_lines "$ENV_FILE" > "$ENV_FILE.tmp"
        if [ "$in_use_app" != "fashionista" ] || [ "$in_use_root" != "root_password" ]; then
            printf 'MYSQL_ROOT_PASSWORD=%s\nDB_PASSWORD=%s\n' "$in_use_root" "$in_use_app" >> "$ENV_FILE.tmp"
        fi
        mv "$ENV_FILE.tmp" "$ENV_FILE"
    fi
    rm -f "$PENDING"
    echo ">>> done: the passwords are back to the ones the containers run with"
    exit 0
fi

if [ "${1:-}" = "--discard" ]; then
    new_root="$(env_value "$ENV_FILE" MYSQL_ROOT_PASSWORD)"
    new_app="$(env_value "$ENV_FILE" DB_PASSWORD)"
    [ -n "$new_root" ] && [ -n "$new_app" ] || die "$ENV_FILE holds no rotated passwords; run this script without --discard first"
    [ "$in_use_root" = "$new_root" ] || die "$MYSQL_CONTAINER still runs with the old root password; run ./deploy.sh first"
    [ "$in_use_app" = "$new_app" ] || die "$WEB_CONTAINER still runs with the old password; run ./deploy.sh first"
    if docker exec "$WEB_CONTAINER" grep -q "password='fashionista'" /app/docker-entrypoint.sh; then
        die "the running web image still connects with the old password at boot; run ./deploy.sh first"
    fi
    can_login root "$new_root" || die "the new root password does not log in; nothing discarded"
    can_login "$APP_USER" "$new_app" || die "the new $APP_USER password does not log in; nothing discarded"
    site_answers || die "the site does not answer; nothing discarded"

    echo ">>> discarding the old passwords"
    trap '' HUP INT TERM
    {
        for host in $root_hosts; do
            printf "ALTER USER 'root'@'%s' DISCARD OLD PASSWORD;\n" "$host"
        done
        for host in $app_hosts; do
            printf "ALTER USER '%s'@'%s' DISCARD OLD PASSWORD;\n" "$APP_USER" "$host"
        done
    } | run_sql_as_root

    can_login root "$new_root" || die "the new root password stopped working after the discard"
    can_login "$APP_USER" "$new_app" || die "the new $APP_USER password stopped working after the discard"
    site_answers || die "the site stopped answering after the discard"
    echo ">>> done: only the passwords in $ENV_FILE work now"
    exit 0
fi

[ ! -e "$PENDING" ] \
    || die "$PENDING exists: a rotation stopped half way. Do not rotate again; run: scripts/rotate_db_passwords.sh --abort"
[ "$(secondary_passwords)" = "0" ] \
    || die "an account already has a second password: a rotation is in progress. Run ./deploy.sh then --discard, or --abort"
if [ -n "$(env_value "$ENV_FILE" DB_PASSWORD)" ]; then
    [ "$(env_value "$ENV_FILE" DB_PASSWORD)" = "$in_use_app" ] \
        && [ "$(env_value "$ENV_FILE" MYSQL_ROOT_PASSWORD)" = "$in_use_root" ] \
        || die "$ENV_FILE and the running containers disagree on the passwords; run ./deploy.sh first"
fi
[ -n "$(find "$BACKUP_DIR" -maxdepth 1 -name 'fashionista_*.sql.gz' -mmin -120 2>/dev/null | head -n 1)" ] \
    || die "no backup younger than two hours in $BACKUP_DIR; run scripts/backup_db.sh first"
can_login root "$in_use_root" || die "the current root password of $MYSQL_CONTAINER does not log in"
can_login "$APP_USER" "$in_use_app" || die "the current $APP_USER password of $WEB_CONTAINER does not log in"

others="$(printf "SELECT CONCAT(user, '@', host) FROM mysql.user WHERE user NOT IN ('root', '%s') AND user NOT LIKE 'mysql.%%';\n" "$APP_USER" | run_sql_as_root)"
[ -z "$others" ] || echo "NOTE: other MySQL accounts exist and are not rotated: $(echo $others)"

new_root="$(openssl rand -hex 24)"
new_app="$(openssl rand -hex 24)"
[ "${#new_root}" -eq 48 ] && [ "${#new_app}" -eq 48 ] || die "could not generate the passwords"

umask 077
{
    without_password_lines "$ENV_FILE"
    printf 'MYSQL_ROOT_PASSWORD=%s\nDB_PASSWORD=%s\n' "$new_root" "$new_app"
} > "$PENDING"

stop_half_way() {
    die "$1. The site keeps working on the old passwords. Do not run this script again; run: scripts/rotate_db_passwords.sh --abort"
}

echo ">>> adding the new passwords, the old ones stay valid"
trap '' HUP INT TERM
if ! {
    for host in $root_hosts; do
        printf "ALTER USER 'root'@'%s' IDENTIFIED BY '%s' RETAIN CURRENT PASSWORD;\n" "$host" "$new_root"
    done
    for host in $app_hosts; do
        printf "ALTER USER '%s'@'%s' IDENTIFIED BY '%s' RETAIN CURRENT PASSWORD;\n" "$APP_USER" "$host" "$new_app"
    done
} | run_sql_as_root; then
    stop_half_way "ALTER USER failed"
fi

can_login root "$new_root" || stop_half_way "the new root password does not log in"
can_login "$APP_USER" "$new_app" || stop_half_way "the new $APP_USER password does not log in"
can_login root "$in_use_root" || stop_half_way "the old root password stopped working"
can_login "$APP_USER" "$in_use_app" || stop_half_way "the old $APP_USER password stopped working"

mkdir -p "$BACKUP_DIR"
grep -E '^(MYSQL_ROOT_PASSWORD|DB_PASSWORD)=' "$PENDING" > "$BACKUP_DIR/db_passwords_$(date +%Y%m%d_%H%M%S).env"
mv "$PENDING" "$ENV_FILE"
chmod 600 "$ENV_FILE"
echo ">>> done: new passwords written to $ENV_FILE (copy in $BACKUP_DIR), old and new both work"
echo "    keep a copy in your password manager, then: ./deploy.sh, check the site, then: scripts/rotate_db_passwords.sh --discard"
