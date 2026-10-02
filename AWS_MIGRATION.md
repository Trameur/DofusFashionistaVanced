# AWS Migration Guide - Dofus Fashionista

This guide explains how to migrate the Dofus Fashionista application and its data to AWS.

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [Prerequisites](#prerequisites)
3. [AWS Setup](#aws-setup)
4. [Data Migration](#data-migration)
5. [Deployment](#deployment)
6. [EC2 Host (Amazon Linux 2023)](#ec2-host-amazon-linux-2023)
7. [Verification](#verification)
8. [Troubleshooting](#troubleshooting)
9. [MySQL Upgrades](#mysql-upgrades)

## Architecture Overview

### Current Local Setup
- **Local MySQL** (port 3306): Contains `fashionista_migration` database with production user data
- **Docker MySQL** (port 3307): Contains `fashionista` database (development environment)
- **Django App**: Runs on port 8000 locally

### AWS Target Setup
- **RDS MySQL 8.4**: Managed database service (replaces local MySQL)
- **ECS/Fargate**: Runs the Docker image built from the `Dockerfile` (Python 3.14, Django 6.0)
- **EC2 (alternative)**: One Amazon Linux 2023 host with Apache and mod_wsgi, see [EC2 Host](#ec2-host-amazon-linux-2023)
- **S3**: Static files storage (images, CSS, JS) and database backups
- **CloudFront**: CDN for static content

### Software Versions
- **Python**: 3.12 or later, because Django 6.0 needs it. The Docker image runs 3.14.
- **MySQL**: 8.4 on RDS. RDS moved MySQL 8.0 to paid Extended Support on 1 August 2026,
  and Django 6.1 needs MySQL 8.4 or later. The newer MySQL versions (9.x, 26.7) are only in
  the RDS Database Preview environment, which is not for production.
- **Python packages**: `requirements-docker.txt` for the image, `requirements_aws.txt`
  for an EC2 host (the same pins plus mod_wsgi).

## Prerequisites

### Before Starting
- [ ] AWS account with appropriate permissions
- [ ] AWS CLI configured locally
- [ ] Docker Desktop running (for local testing)
- [ ] Python 3.12 or later installed
- [ ] The site's packages installed: `pip install -r requirements.txt` (PyMySQL included)
- [ ] Access to local Windows fashionista config: `%APPDATA%\fashionista\gen_config.json`

### Local Test (Recommended)
Test the sync script locally first:

```bash
# Test dry-run mode
python sync_db.py --dry-run

# This will show you what would be transferred without making changes
```

## AWS Setup

### Step 1: Create RDS MySQL Instance

#### Via AWS Console:
1. Go to RDS → Databases → Create Database
2. **Engine Options:**
   - Engine: MySQL
   - Version: the latest MySQL 8.4 minor version
   - Multi-AZ: No (for development/testing)
   
3. **Connectivity:**
   - Public accessibility: Yes (for initial migration from local machine)
   - New security group: Allow inbound on port 3306 from your IP
   
4. **Database Authentication:**
   - Initial database name (under Additional configuration): `fashionista`
   - Master username: `fashionista`
   - Master password: (generate strong password)

#### Via AWS CLI:
```bash
aws rds create-db-instance \
  --db-instance-identifier fashionista-mysql \
  --db-instance-class db.t3.micro \
  --engine mysql \
  --engine-version 8.4 \
  --db-name fashionista \
  --master-username fashionista \
  --master-user-password "YourStrongPassword123!" \
  --allocated-storage 20 \
  --publicly-accessible
```

Without `--db-name`, RDS creates no `fashionista` database and every later step fails
with "Unknown database".

MySQL 8.4 signs users in with `caching_sha2_password` by default. PyMySQL handles it
through the `cryptography` package, which the requirements files pin.

### Step 2: Configure Security Groups

Allow connections from:
- Your local machine IP (for migration)
- VPC CIDR block (for app containers)

```bash
# Get your public IP
curl https://checkip.amazonaws.com

# Add to RDS security group inbound rules:
# Type: MySQL/Aurora (3306), Protocol: TCP, Source: YOUR_IP/32
```

### Step 3: Create Credentials File for AWS

Create `~/.aws/fashionista_aws_config.json`, then pass it to `sync_db.py` with
`--config ~/.aws/fashionista_aws_config.json`. Its values win over the command line options,
and the passwords stay out of your shell history:

```json
{
  "source": {
    "host": "localhost",
    "port": 3306,
    "db": "fashionista_migration",
    "user": "fashionista",
    "password": "YOUR_LOCAL_PASSWORD"
  },
  "destination": {
    "host": "fashionista-mysql.xxxxx.us-east-1.rds.amazonaws.com",
    "port": 3306,
    "db": "fashionista",
    "user": "fashionista",
    "password": "YOUR_RDS_PASSWORD"
  }
}
```

## Data Migration

### Step 1: Verify Connectivity

Test connection to AWS RDS:

```bash
# From Windows, test RDS connectivity
mysql -h fashionista-mysql.xxxxx.us-east-1.rds.amazonaws.com \
      -u fashionista -p fashionista

# Or from Python
python -c "import pymysql; c = pymysql.connect(host='YOUR_RDS_ENDPOINT', user='fashionista', password='PASSWORD', database='fashionista'); print('✓ Connected')"
```

### Step 2: Create the Tables on RDS

`sync_db.py` copies rows into tables that already exist: it creates none. Build the schema
on RDS with Django migrations, from a checkout at the same version as the code that wrote
the source database (PowerShell, with your local `gen_config.json` in place):

```powershell
$env:DB_HOST = "fashionista-mysql.xxxxx.us-east-1.rds.amazonaws.com"
$env:DB_USER = "fashionista"
$env:DB_PASSWORD = "YOUR_RDS_PASSWORD"
python fashionsite\manage.py migrate
Remove-Item Env:DB_HOST, Env:DB_USER, Env:DB_PASSWORD
```

### Step 3: Take an RDS Snapshot

`sync_db.py` writes no backup of its own, and it empties every table it copies on the
destination. Take a snapshot before every real run:

```bash
aws rds create-db-snapshot \
  --db-instance-identifier fashionista-mysql \
  --db-snapshot-identifier fashionista-before-sync
```

### Step 4: Run Dry-Run Migration

Always test first without making changes:

```bash
python sync_db.py \
  --source-host localhost \
  --source-port 3306 \
  --source-db fashionista_migration \
  --dest-host fashionista-mysql.xxxxx.us-east-1.rds.amazonaws.com \
  --dest-port 3306 \
  --dest-db fashionista \
  --source-user fashionista \
  --source-pass "YOUR_LOCAL_PASSWORD" \
  --dest-user fashionista \
  --dest-pass "YOUR_RDS_PASSWORD" \
  --dry-run
```

A dry run reads every source table and checks that each one exists on RDS. It writes
nothing and compares no row counts. When a table is missing, as after a skipped Step 2, it
names the table and exits with code 1.

### Step 5: Execute Real Migration

Once dry-run succeeds:

```bash
python sync_db.py \
  --source-host localhost \
  --source-port 3306 \
  --source-db fashionista_migration \
  --dest-host fashionista-mysql.xxxxx.us-east-1.rds.amazonaws.com \
  --dest-port 3306 \
  --dest-db fashionista \
  --source-user fashionista \
  --source-pass "YOUR_LOCAL_PASSWORD" \
  --dest-user fashionista \
  --dest-pass "YOUR_RDS_PASSWORD"
```

#### What Happens:
1. Lists every base table of the source database
2. Turns foreign key checks off on the destination connection, so the tables load in any order
3. Empties each destination table (no backup is written: see Step 3)
4. Transfers data in batches of 300 rows
5. Commits every 3000 rows (10 batches)
6. Verifies row counts match between source and destination. A table that failed to copy
   or does not match is named in the log, and the script exits with code 1
7. Writes detailed log to `db_sync.log`

#### Expected Output:
```
2026-04-18 10:30:44 - INFO - Tables in the source: 43
2026-04-18 10:30:45 - INFO - Syncing table: auth_user
2026-04-18 10:30:45 - INFO -   Total rows: 5662
2026-04-18 10:30:47 - INFO -   Progress: 3000/5662 rows synced
2026-04-18 10:30:49 - INFO -   ✓ Synced 5662 rows
...
2026-04-18 10:45:32 - INFO - ✓ All tables verified - sync successful!
2026-04-18 10:45:32 - INFO - Total rows synced: 2,247,368
```

### Migration Time Estimates

Based on local Docker test (2.2M rows):
- **Local → Docker (same network)**: ~5-15 minutes
- **Local → AWS RDS (across internet)**: ~15-45 minutes (varies by connection speed)

**Tip**: Run migration during off-peak hours to minimize impact.

## Deployment

### Step 1: Django Configuration

No edit to `settings.py` is needed. It reads the database from environment variables:

| Variable | Default |
|----------|---------|
| `DB_HOST` | `localhost` |
| `DB_PORT` | `3306` |
| `DB_NAME` | `fashionista` |
| `DB_USER` | `mysql_USER` from `gen_config.json` |
| `DB_PASSWORD` | `mysql_PASSWORD` from `gen_config.json` |

Everything else comes from files in `/etc/fashionista`, or in the folder named by the
`FASHIONISTA_CONFIG_DIR` environment variable:

- `gen_config.json`: `SECRET_KEY`, mail, OAuth and S3 keys. The image bakes a default one
  whose `SECRET_KEY` is public: production needs its own.
- `debug_mode`: `True` or `False`. The image writes `False`.
- `serve_static`: the image writes `True`.

`DEBUG` and `ALLOWED_HOSTS` environment variables are ignored. `ALLOWED_HOSTS` is a fixed
list in `settings.py`, and with `DEBUG` off any other `Host` gets a 400: the ALB DNS name
and the ALB health checks included (see Step 3).

### Step 2: Run the Image Against RDS Locally

The image's default command is the development server. Production starts through
`docker-entrypoint.sh`, as in `docker-compose.yml`: it waits for the database, runs the
migrations, collects static files and starts Gunicorn on port 8000. The first boot can
take several minutes, longer when it bakes the character previews.

```bash
docker build -t dofus-fashionista:latest .
docker run --rm -p 127.0.0.1:8000:8000 \
  -e DB_HOST=fashionista-mysql.xxxxx.us-east-1.rds.amazonaws.com \
  -e DB_USER=fashionista \
  -e DB_PASSWORD="YOUR_RDS_PASSWORD" \
  -v "$PWD/docker/gen_config.json:/etc/fashionista/gen_config.json" \
  --entrypoint /bin/sh \
  dofus-fashionista:latest /app/docker-entrypoint.sh

# In another terminal, with a Host the site accepts
curl -fsS -H "Host: dofusfashionista.gg" http://localhost:8000/ > /dev/null && echo up
```

### Step 3: Deploy to AWS ECS

```bash
# Create ECR repository
aws ecr create-repository --repository-name dofus-fashionista

# Log Docker in to ECR
aws ecr get-login-password --region {REGION} | docker login --username AWS --password-stdin {YOUR_AWS_ACCOUNT_ID}.dkr.ecr.{REGION}.amazonaws.com

# Build and push Docker image
docker build -t dofus-fashionista:latest .
docker tag dofus-fashionista:latest {YOUR_AWS_ACCOUNT_ID}.dkr.ecr.{REGION}.amazonaws.com/dofus-fashionista:latest
docker push {YOUR_AWS_ACCOUNT_ID}.dkr.ecr.{REGION}.amazonaws.com/dofus-fashionista:latest
```

What the task definition needs beyond the image:

- **Entry point**: `["/bin/sh", "/app/docker-entrypoint.sh"]`, or the task starts the
  development server.
- **Port**: container port 8000.
- **Environment**: `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, and `DB_PASSWORD` as a
  Secrets Manager secret.
- **Configuration files**: a Fargate task cannot mount files from a host. Its bind mounts
  are empty volumes shared by the containers of the task, gone when the task stops. Put
  `gen_config.json`, `debug_mode` (`False`) and `serve_static` (`True`) on an EFS volume,
  mount it, and set `FASHIONISTA_CONFIG_DIR` to the mount path.
- **Container health check**: the one from `docker-compose.yml`,
  `curl -fsS -H 'Host: dofusfashionista.gg' http://localhost:8000/ > /dev/null || exit 1`.
  ECS allows a start period of 300 seconds at most, and `docker-compose.yml` allows 600:
  use `startPeriod` 300, `interval` 30 and `retries` 10, which waits up to 600 seconds.
- **Load balancer health check**: the ALB sends `Host: <task private IP>`, which
  `ALLOWED_HOSTS` refuses with a 400, and each task gets a new private IP. Set the target
  group's success codes to `400`. A check that gets a 200 needs a code change in
  `settings.py`. Give the service a health check grace period of 600 seconds: it covers
  both the load balancer and the container checks during the first boot.

### Step 4: Static Files

With `DEBUG` off, Django serves no file under `/static/`: in `docker-compose.yml` the
nginx container serves them from the `static_files` volume. On ECS, pick one before the
switch, or every page loads without its CSS and scripts:

- an nginx container in the same task, sharing a task bind mount with the web container,
  with the `/static/` block of `docker/nginx.conf`;
- or the files on S3 behind CloudFront and `STATIC_URL` in `settings.py` pointing there.
  `upload_static_files.py` uploads the hashed files that `collectstatic` lists in
  `staticfiles.json`, which it writes only with `debug_mode` set to `False`.

The baked character previews live in the `character_cache` volume, which
`docker-compose.yml` fills by hand. Without it the entry point turns the preview off.

## EC2 Host (Amazon Linux 2023)

The scripts at the repository root also run the site on one EC2 instance, with Apache and
mod_wsgi instead of containers. On Amazon Linux 2023, `python3` is Python 3.9 for the life
of the release, too old for Django 6.0, so every step names `python3.14`.

```bash
# As ec2-user. wsgi.py adds /home/ec2-user/DofusFashionistaVanced to the path.
sudo dnf install -y git python3.14
git clone https://github.com/Trameur/DofusFashionistaVanced.git ~/DofusFashionistaVanced
cd ~/DofusFashionistaVanced

# System packages (gcc, httpd, httpd-devel, python3.14 headers and pip, mariadb114,
# cronie...), then requirements_aws.txt through python3.14 -m pip, mod_wsgi included
sudo python3.14 ./configure_fashionista_root.py -i -s

# Database and schema
python3.14 ./configure_fashionista.py

# Static files and translations: the repository holds neither collected nor compiled
cd fashionsite
python3.14 manage.py collectstatic --noinput
python3.14 manage.py compilemessages
cd ..

# Apache runs as the apache user, and /home/ec2-user is 0700
chmod 711 /home/ec2-user

# The LoadModule and WSGIPythonHome lines for Apache
mod_wsgi-express module-config
```

Then write the Apache virtual host, which is not in the repository, for example
`/etc/httpd/conf.d/fashionista.conf`. Apache 2.4 refuses every folder outside its own
until a `Require all granted` opens it:

```apache
# The two lines printed by mod_wsgi-express module-config
WSGIScriptAlias / /home/ec2-user/DofusFashionistaVanced/fashionsite/fashionsite/wsgi.py
<Directory /home/ec2-user/DofusFashionistaVanced/fashionsite/fashionsite>
    <Files wsgi.py>
        Require all granted
    </Files>
</Directory>

Alias /static/ /home/ec2-user/DofusFashionistaVanced/fashionsite/staticfiles/
<Directory /home/ec2-user/DofusFashionistaVanced/fashionsite/staticfiles>
    Require all granted
</Directory>
```

SELinux is permissive by default on Amazon Linux 2023; set to enforcing, it also needs
labels on these folders. Start the services and the cron jobs:

```bash
sudo systemctl enable --now httpd crond
python3.14 ./setup_cron_jobs.py
```

The cron jobs back the database up to S3 every day (`backup_db.py`), clean old rows
(`cleanup_db.py`) and restart Apache when `https://dofusfashionista.gg` stops answering
(`auto_restart_apache.py`): install that last one only on the host serving that domain.
`backup_db.py` runs `mysqldump` from the MariaDB 11.4 client, not MySQL's: before relying
on the backups, check that `command -v mysqldump` finds it and that one dump restores into
a scratch database on RDS.

After an update, run the `collectstatic` line again, then `bash run_fashionista_apache.sh`,
which compiles the translations and restarts httpd.

With RDS, put its user and password in `gen_config.json` (`mysql_USER`, `mysql_PASSWORD`)
and give `DB_HOST` to every process that opens the database, before the steps above:

- your shell: `export DB_HOST=fashionista-mysql.xxxxx.rds.amazonaws.com`;
- Apache: `sudo systemctl edit httpd`, then `[Service]` and
  `Environment=DB_HOST=fashionista-mysql.xxxxx.rds.amazonaws.com`;
- cron: a `DB_HOST=...` line at the top of `crontab -e`, added again after every run of
  `setup_cron_jobs.py`, which replaces the whole crontab.

## Verification

### Database Verification Checklist

```bash
# Connect to AWS RDS
mysql -h fashionista-mysql.xxxxx.us-east-1.rds.amazonaws.com \
      -u fashionista -p fashionista

# Run verification queries
USE fashionista;

# Check row counts on key tables
SELECT 'auth_user' as tbl, COUNT(*) as cnt FROM auth_user
UNION ALL
SELECT 'chardata_char', COUNT(*) FROM chardata_char
UNION ALL
SELECT 'django_session', COUNT(*) FROM django_session;

# Verify data integrity
SELECT COUNT(DISTINCT id) as unique_users FROM auth_user;
SELECT COUNT(DISTINCT id) as unique_builds FROM chardata_char;
```

`chardata_char` holds the builds. `sync_db.py` already compares the row count of every
table at the end of a run.

### Application Testing

```bash
# Test Django migrations
docker run --rm -e DB_HOST=RDS_ENDPOINT -e DB_USER=fashionista -e DB_PASSWORD="YOUR_RDS_PASSWORD" \
  dofus-fashionista python fashionsite/manage.py migrate --check

# Test data access
docker run --rm -it -e DB_HOST=RDS_ENDPOINT -e DB_USER=fashionista -e DB_PASSWORD="YOUR_RDS_PASSWORD" \
  dofus-fashionista python fashionsite/manage.py shell
# In Django shell:
>>> from chardata.models import Char
>>> Char.objects.count()
136295  # Should match source

# Test homepage, with a Host that ALLOWED_HOSTS accepts
curl -H "Host: dofusfashionista.gg" http://localhost:8000/
# Should return full HTML with items data
```

## Troubleshooting

### Common Issues

#### 1. Connection Timeout to RDS

**Error**: `pymysql.err.OperationalError: (2003, "Can't connect to MySQL server...`

**Solutions**:
- Verify RDS security group allows your IP on port 3306
- Check RDS endpoint is correct
- Ensure RDS instance is in "available" state
- Test with: `telnet RDS_ENDPOINT 3306`

#### 2. Authentication Failed

**Error**: `pymysql.err.OperationalError: (1045, "Access denied for user...`

**Solutions**:
- Verify username and password are correct
- Check database name exists
- Ensure user has appropriate permissions

#### 3. Character Encoding Issues

**Error**: `Incorrect string value for column...`

**Solutions**:
- Ensure RDS uses `utf8mb4` charset
- Run on RDS:
  ```sql
  ALTER DATABASE fashionista CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
  ALTER TABLE auth_user CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
  -- Repeat for all tables
  ```

#### 4. Migration Script Fails Mid-Process

**Recovery**:
```bash
# Check db_sync.log for exact error
tail -100 db_sync.log

# Fix issue then re-run: every table is emptied and copied again
python sync_db.py ...
```

To go back to the state before the run, restore the snapshot of Data Migration Step 3 to
a new instance, then point the site at it:

```bash
aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier fashionista-mysql-restored \
  --db-snapshot-identifier fashionista-before-sync
```

#### 5. Row Count Verification Fails

**Debug**:
```python
# Run manual verification
from sync_db import DatabaseSyncManager

src_cfg = {'host': 'localhost', 'port': 3306, 'db': 'fashionista_migration', 'user': 'fashionista', 'password': '...'}
dst_cfg = {'host': 'RDS_ENDPOINT', 'port': 3306, 'db': 'fashionista', 'user': 'fashionista', 'password': '...'}

mgr = DatabaseSyncManager(src_cfg, dst_cfg)
mgr.connect()
mgr.tables = mgr.list_tables()
mgr.verify_sync()
mgr.disconnect()
```

### Performance Optimization

#### For Large Datasets (>5M rows):
1. Increase `BATCH_SIZE` in `sync_db.py` to 1000
2. Increase `COMMIT_INTERVAL` to 20 (commit every 20 batches)
3. Run during non-peak hours
4. Consider AWS Database Migration Service (DMS), or a `mysqldump` restored on RDS, for
   100M+ rows. AWS DataSync copies files, not MySQL tables.

#### Network Optimization:
Run the migration from an EC2 instance in the same region as RDS rather than from the
local machine.

## Post-Migration Checklist

- [ ] Verify row counts match (use verification queries above)
- [ ] Test Django admin login with migrated user
- [ ] Test character search and build features
- [ ] Verify social auth (Google, Facebook) still works
- [ ] Check static files are accessible (see [Deployment Step 4](#step-4-static-files))
- [ ] Monitor RDS for performance issues
- [ ] Set RDS backup retention to 30 days
- [ ] Enable RDS Enhanced Monitoring
- [ ] Create read replica for disaster recovery
- [ ] Update DNS/load balancer to point to new AWS deployment

## Rollback Plan

If migration fails or causes issues:

1. **Keep RDS instance**: Don't delete, just stop it (costs less)
2. **Restore the snapshot** taken before the sync (Data Migration Step 3)
3. **Continue using local**: While investigating issues
4. **Contact AWS support**: For RDS-specific issues

## MySQL Upgrades

MySQL 8.4 is the newest version RDS offers outside its Database Preview environment, and
RDS keeps MySQL 8.0 only under paid Extended Support since 1 August 2026. List what RDS
offers before choosing a minor version:

```bash
aws rds describe-db-engine-versions --engine mysql \
  --query "DBEngineVersions[].EngineVersion" --output text
```

An instance created at 8.0 moves to 8.4 in place after a snapshot, or through an RDS
Blue/Green deployment with a short switchover. Read the AWS post "Upgrade strategies for
Amazon RDS for MySQL 8.0 to 8.4" first:
https://aws.amazon.com/blogs/database/upgrade-strategies-for-amazon-rds-for-mysql-8-0-to-8-4/

```bash
aws rds create-db-snapshot \
  --db-instance-identifier fashionista-mysql \
  --db-snapshot-identifier fashionista-before-8-4
aws rds modify-db-instance \
  --db-instance-identifier fashionista-mysql \
  --engine-version {8.4 VERSION FROM THE LIST ABOVE} \
  --allow-major-version-upgrade \
  --apply-immediately
```

`sync_db.py` copies rows, not files, so a local MySQL 8.0 source can fill an 8.4
destination directly.

## Performance Monitoring

After deployment, monitor:

```bash
# RDS CPU and Memory
aws cloudwatch get-metric-statistics \
  --namespace AWS/RDS \
  --metric-name CPUUtilization \
  --dimensions Name=DBInstanceIdentifier,Value=fashionista-mysql \
  --start-time 2026-04-18T00:00:00Z \
  --end-time 2026-04-18T23:59:59Z \
  --period 300 \
  --statistics Maximum,Average

# Application Error Logs
docker logs fashionista_web | tail -100
```

## Support & Documentation

- **Django Documentation**: https://docs.djangoproject.com/en/6.0/
- **AWS RDS**: https://docs.aws.amazon.com/rds/
- **PyMySQL**: https://pymysql.readthedocs.io/
- **Project README**: See [README.md](README.md)

---

**Last Updated**: October 2, 2026  
**Version**: 1.0  
**Author**: Database Migration Script
