# Docker for DofusFashionistaVanced

This document explains how to run DofusFashionistaVanced with Docker.

## Prerequisites

- Docker
- Docker Compose

## Quick start

### On Windows

1. Run the `run_docker.bat` script by double-clicking it or from the command line.

```
run_docker.bat
```

### On Linux/macOS

1. Make the script executable:

```bash
chmod +x run_docker.sh
```

2. Run the script:

```bash
./run_docker.sh
```

## Opening the application

Once the containers are up, the application is available at:

```
http://localhost:8000
```

## Useful commands

- To follow the container logs:

```bash
docker-compose logs -f
```

- To stop the containers:

```bash
docker-compose down
```

- To restart the containers:

```bash
docker-compose restart
```

- To rebuild the Docker images (after a change):

```bash
docker-compose build
```

## Containers

The application uses three Docker containers:

1. **web** - Django web server with gunicorn
2. **db** - MySQL server
3. **memcached** - Memcached server for the cache

## Persistent data

The database data lives in a Docker volume named `fashionista_db_data`, so it survives restarts.

## Database passwords

`docker-compose.yml` reads `MYSQL_ROOT_PASSWORD` and `DB_PASSWORD` from `.env` (gitignored). Locally the defaults of `.env.example` apply. In production `deploy.sh` refuses to run without them. To set or rotate them on the server, with no downtime:

```bash
scripts/backup_db.sh                      # dump to /root/backups, checked before it is kept
scripts/rotate_db_passwords.sh            # new random passwords in .env, the old ones still work
./deploy.sh                               # web and mysql restart on the new passwords
scripts/rotate_db_passwords.sh --discard  # the old passwords stop working
```

A rotation stopped half way is undone with `scripts/rotate_db_passwords.sh --abort`; the script refuses to start a second rotation over it. A copy of each new pair of passwords is kept in `/root/backups`.

To restore a backup (the password stays inside the container):

```bash
gunzip -c /root/backups/fashionista_<stamp>.sql.gz | docker exec -i fashionista_mysql sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -uroot'
```

MySQL (3307) and gunicorn (8000) are published on 127.0.0.1 only; nginx reaches web through the Docker network.

## Character preview

The preview draws pieces baked in advance from the Ankama bundles. The bundles (861 MB) are only needed for the bake and are not needed in production; only the baked cache (150 MB) is needed, in the `character_cache` volume. Without it the page falls back to the old avatar, so nothing breaks; the preview is simply missing.

To fill the volume from a local bake:

```bash
docker cp character_cache/. fashionista_web:/app/character_cache/
```

nginx serves the pieces that already exist and passes to Django only the pieces not baked yet, which happens once per piece. After any change to `docker/nginx.conf`, check it with `docker compose exec nginx nginx -t` before reloading.

## Custom configuration

To customize the configuration, you can edit these files:

- `docker-compose.yml` - Docker service configuration
- `/etc/fashionista/gen_config.json` (inside the container) - application configuration
