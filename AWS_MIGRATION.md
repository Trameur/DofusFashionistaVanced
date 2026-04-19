# AWS Migration Guide - Dofus Fashionista

This guide explains how to migrate the Dofus Fashionista application and its data to AWS.

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [Prerequisites](#prerequisites)
3. [AWS Setup](#aws-setup)
4. [Data Migration](#data-migration)
5. [Deployment](#deployment)
6. [Verification](#verification)
7. [Troubleshooting](#troubleshooting)

## Architecture Overview

### Current Local Setup
- **Local MySQL** (port 3306): Contains `fashionista_migration` database with production user data
- **Docker MySQL** (port 3307): Contains `fashionista` database (development environment)
- **Django App**: Runs on port 8000 locally

### AWS Target Setup
- **RDS MySQL**: Managed database service (replaces local MySQL)
- **ECS/EC2**: Container orchestration for Django app (replaces Docker Desktop)
- **S3**: Static files storage (images, CSS, JS)
- **CloudFront**: CDN for static content

## Prerequisites

### Before Starting
- [ ] AWS account with appropriate permissions
- [ ] AWS CLI configured locally
- [ ] Docker Desktop running (for local testing)
- [ ] Python 3.9+ installed
- [ ] PyMySQL installed: `pip install pymysql`
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
   - Version: 8.0 (or compatible with Docker)
   - Multi-AZ: No (for development/testing)
   
3. **Connectivity:**
   - Public accessibility: Yes (for initial migration from local machine)
   - New security group: Allow inbound on port 3306 from your IP
   
4. **Database Authentication:**
   - Database name: `fashionista`
   - Master username: `fashionista`
   - Master password: (generate strong password)

#### Via AWS CLI:
```bash
aws rds create-db-instance \
  --db-instance-identifier fashionista-mysql \
  --db-instance-class db.t3.micro \
  --engine mysql \
  --engine-version 8.0 \
  --master-username fashionista \
  --master-user-password "YourStrongPassword123!" \
  --allocated-storage 20 \
  --publicly-accessible
```

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

Create `~/.aws/fashionista_aws_config.json`:

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

### Step 2: Run Dry-Run Migration

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

### Step 3: Execute Real Migration

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
1. Creates a backup file: `db_backup_fashionista_YYYYMMDD_HHMMSS.sql`
2. Truncates each destination table
3. Transfers data in batches of 300 rows
4. Commits every 3000 rows (10 batches)
5. Verifies row counts match between source and destination
6. Writes detailed log to `db_sync.log`

#### Expected Output:
```
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

### Step 1: Update Django Configuration

Update `fashionsite/fashionsite/settings.py`:

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.environ.get('DB_NAME', 'fashionista'),
        'USER': os.environ.get('DB_USER', 'fashionista'),
        'PASSWORD': os.environ.get('DB_PASSWORD', ''),
        'HOST': os.environ.get('DB_HOST', 'fashionista-mysql.xxxxx.rds.amazonaws.com'),
        'PORT': os.environ.get('DB_PORT', '3306'),
        'OPTIONS': {
            'charset': 'utf8mb4',
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
        }
    }
}
```

### Step 2: Create Docker Container for AWS

Update `docker-compose.yml` for AWS deployment:

```yaml
services:
  web:
    image: dofus-fashionista:latest
    restart: always
    environment:
      - PYTHONPATH=/app:/app/fashionistapulp:/app/fashionsite
      - DB_HOST=fashionista-mysql.xxxxx.rds.amazonaws.com
      - DB_PORT=3306
      - DB_NAME=fashionista
      - DB_USER=fashionista
      - DB_PASSWORD=${RDS_PASSWORD}  # Inject at runtime
      - DEBUG=False  # Production mode!
    ports:
      - "8000:8000"
    command: >
      /bin/sh -c "cd /app/fashionsite &&
      python manage.py migrate --noinput &&
      python manage.py collectstatic --noinput &&
      gunicorn fashionsite.wsgi --bind 0.0.0.0:8000 --workers 4"
```

### Step 3: Deploy to AWS ECS

```bash
# Create ECR repository
aws ecr create-repository --repository-name dofus-fashionista

# Build and push Docker image
docker build -t dofus-fashionista:latest .
docker tag dofus-fashionista:latest {YOUR_AWS_ACCOUNT_ID}.dkr.ecr.{REGION}.amazonaws.com/dofus-fashionista:latest
docker push {YOUR_AWS_ACCOUNT_ID}.dkr.ecr.{REGION}.amazonaws.com/dofus-fashionista:latest

# Deploy to ECS (detailed instructions depend on your cluster setup)
```

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
SELECT 'chardata_build', COUNT(*) FROM chardata_build
UNION ALL
SELECT 'django_session', COUNT(*) FROM django_session;

# Verify data integrity
SELECT COUNT(DISTINCT id) as unique_users FROM auth_user;
SELECT COUNT(DISTINCT id) as unique_chars FROM chardata_char;
SELECT COUNT(DISTINCT id) as unique_builds FROM chardata_build;
```

### Application Testing

```bash
# Test Django migrations
docker run -e DB_HOST=RDS_ENDPOINT dofus-fashionista python manage.py migrate --check

# Test data access
docker run -e DB_HOST=RDS_ENDPOINT dofus-fashionista python manage.py shell
# In Django shell:
>>> from chardata.models import Char
>>> Char.objects.count()
136295  # Should match source

# Test homepage
curl http://localhost:8000/
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

# Restore backup if needed
mysql -h RDS_ENDPOINT -u fashionista -p fashionista < db_backup_fashionista_*.sql

# Fix issue then re-run
python sync_db.py ...
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
mgr.verify_sync()
mgr.disconnect()
```

### Performance Optimization

#### For Large Datasets (>5M rows):
1. Increase `BATCH_SIZE` in `sync_db.py` to 1000
2. Increase `COMMIT_INTERVAL` to 20 (commit every 20 batches)
3. Run during non-peak hours
4. Consider AWS DataSync or Database Migration Service (DMS) for 100M+ rows

#### Network Optimization:
```bash
# Run migration from EC2 instance in same region (faster)
# Instead of from local machine

# Or use AWS DataSync:
aws datasync create-task \
  --source-location-arn SOURCE_LOCATION \
  --destination-location-arn DEST_LOCATION
```

## Post-Migration Checklist

- [ ] Verify row counts match (use verification queries above)
- [ ] Test Django admin login with migrated user
- [ ] Test character search and build features
- [ ] Verify social auth (Google, Facebook) still works
- [ ] Check static files are accessible
- [ ] Monitor RDS for performance issues
- [ ] Set RDS backup retention to 30 days
- [ ] Enable RDS Enhanced Monitoring
- [ ] Create read replica for disaster recovery
- [ ] Update DNS/load balancer to point to new AWS deployment

## Rollback Plan

If migration fails or causes issues:

1. **Keep RDS instance**: Don't delete, just stop it (costs less)
2. **Restore backup**: `mysql ... < db_backup_fashionista_*.sql`
3. **Continue using local**: While investigating issues
4. **Contact AWS support**: For RDS-specific issues

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

- **Django Documentation**: https://docs.djangoproject.com/en/1.11/
- **AWS RDS**: https://docs.aws.amazon.com/rds/
- **PyMySQL**: https://pymysql.readthedocs.io/
- **Project README**: See [README.md](README.md)

---

**Last Updated**: April 18, 2026  
**Version**: 1.0  
**Author**: Database Migration Script
