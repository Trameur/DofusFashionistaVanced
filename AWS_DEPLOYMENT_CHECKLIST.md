# AWS Deployment Checklist

Quick reference for deploying Dofus Fashionista to AWS.

## Pre-Deployment (Local)

### 1. Test Locally First ✓
- [ ] Test migration locally with Docker
  ```bash
  python sync_db.py --dry-run  # Test dry-run
  python sync_db.py            # Run actual migration
  ```
- [ ] Verify `db_sync.log` shows successful completion
- [ ] Verify row counts match (all tables should show ✓)
- [ ] Test Django app with migrated data on localhost:8000

### 2. Prepare Credentials
- [ ] Create AWS account with billing enabled
- [ ] Generate strong RDS password (20+ chars, mix of types)
- [ ] Configure AWS CLI: `aws configure`
- [ ] Store credentials securely (not in git!)

### 3. Code Preparation
- [ ] Update `fashionsite/settings.py` with RDS endpoint
- [ ] Set `DEBUG=False` for production
- [ ] Collect static files locally: `python manage.py collectstatic`
- [ ] Run migrations locally: `python manage.py migrate`
- [ ] Test on local Docker one more time

## AWS Setup (Week 1)

### 1. RDS Instance Creation ✓
- [ ] Create RDS MySQL 8.0 instance
  - [ ] Instance ID: `fashionista-mysql`
  - [ ] Instance class: `db.t3.micro` (free tier eligible)
  - [ ] Allocated storage: 20-50 GB
  - [ ] Multi-AZ: No (save cost)
  - [ ] Database name: `fashionista`
  - [ ] Master username: `fashionista`
  - [ ] Auto backup: Yes, 30 days retention
  - [ ] Enable Enhanced Monitoring
  
- [ ] Note down RDS endpoint (will look like: `fashionista-mysql.xxxxx.rds.amazonaws.com`)
- [ ] Wait for RDS status to be "Available" (~10 minutes)

### 2. Security Group Setup ✓
- [ ] Create/modify security group for RDS
  - [ ] Inbound Rule 1: MySQL (3306) from your local IP
  - [ ] Inbound Rule 2: MySQL (3306) from VPC CIDR (for app)
  - [ ] Outbound: Allow all (default)
  
- [ ] Test connectivity from local machine
  ```bash
  mysql -h fashionista-mysql.xxxxx.rds.amazonaws.com \
        -u fashionista -p fashionista -e "SELECT VERSION();"
  ```

### 3. Create S3 Bucket for Static Files ✓
- [ ] Create S3 bucket: `fashionista-static-files`
  - [ ] Block Public Access: Off (for CloudFront)
  - [ ] Enable versioning (optional, for rollback)
  - [ ] Enable server-side encryption (default)
  
- [ ] Create CloudFront distribution pointing to S3
  - [ ] Origin: S3 bucket
  - [ ] Cache policy: CachingOptimized
  - [ ] Note CloudFront URL (will be used in Django settings)

## Data Migration (Week 1)

### 1. Pre-Migration
- [ ] Create RDS backup: `aws rds create-db-snapshot --db-instance-identifier fashionista-mysql --db-snapshot-identifier fashionista-backup-pre-migration`
- [ ] Verify local MySQL is running
- [ ] Verify Docker MySQL is running for local test

### 2. Dry-Run Test ✓
- [ ] Run migration in dry-run mode
  ```bash
  python sync_db.py \
    --source-host localhost \
    --source-port 3306 \
    --source-db fashionista_migration \
    --dest-host fashionista-mysql.xxxxx.rds.amazonaws.com \
    --dest-port 3306 \
    --dest-db fashionista \
    --dry-run
  ```
- [ ] Verify no errors in output
- [ ] Check `db_sync.log` for warnings

### 3. Actual Migration ✓
- [ ] Schedule during low-usage time
- [ ] Notify team if production-bound
- [ ] Run migration (no --dry-run)
  ```bash
  python sync_db.py \
    --source-host localhost \
    --source-port 3306 \
    --source-db fashionista_migration \
    --dest-host fashionista-mysql.xxxxx.rds.amazonaws.com \
    --dest-port 3306 \
    --dest-db fashionista
  ```
- [ ] Monitor `db_sync.log` for completion
- [ ] Expected time: 15-45 minutes

### 4. Post-Migration Verification ✓
- [ ] Connect to RDS and run verification queries:
  ```bash
  mysql -h fashionista-mysql.xxxxx.rds.amazonaws.com \
        -u fashionista -p fashionista < MIGRATION_EXAMPLES.md
  # Run the "Verify After Migration" example queries
  ```
- [ ] Verify row counts for key tables:
  - [ ] `auth_user`: ~5,662 rows
  - [ ] `chardata_char`: ~136,295 rows
  - [ ] `chardata_build`: ~136,295+ rows
  - [ ] `django_session`: ~46,984 rows
  
- [ ] Create RDS backup post-migration: `aws rds create-db-snapshot ...`

## App Deployment (Week 2)

### 1. Container Registry (ECR)
- [ ] Create ECR repository: `fashionista`
- [ ] Get login credentials: `aws ecr get-login-password --region us-east-1`
- [ ] Build and push Docker image:
  ```bash
  docker build -t dofus-fashionista:latest .
  docker tag dofus-fashionista:latest {ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com/fashionista:latest
  docker push {ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com/fashionista:latest
  ```

### 2. ECS/Fargate Setup
- [ ] Create ECS cluster: `fashionista-cluster`
- [ ] Create task definition:
  - [ ] Container image: ECR URI
  - [ ] Memory: 512-1024 MB
  - [ ] CPU: 256-512 units
  - [ ] Port: 8000
  - [ ] Environment variables:
    - `DB_HOST`: RDS endpoint
    - `DB_PORT`: 3306
    - `DB_NAME`: fashionista
    - `DB_USER`: fashionista
    - `DB_PASSWORD`: (from secrets manager)
    - `DEBUG`: False
    - `ALLOWED_HOSTS`: your domain

- [ ] Create ECS service:
  - [ ] Task definition: above
  - [ ] Number of tasks: 2-3 (for HA)
  - [ ] Load balancer: ALB
  - [ ] Health check path: `/`

### 3. Load Balancer Setup
- [ ] Create Application Load Balancer (ALB)
  - [ ] Listeners: 80 (HTTP) → 8000 (app)
  - [ ] HTTPS listener: 443 → 8000 (optional)
  - [ ] Target group: ECS cluster
  - [ ] Health check: Every 30s, healthy threshold 2

- [ ] Configure auto-scaling (optional)
  - [ ] Min tasks: 1
  - [ ] Max tasks: 5
  - [ ] Target: 70% CPU

### 4. Domain & SSL
- [ ] Point domain to ALB DNS name (in Route53 or registrar)
- [ ] Request SSL certificate (ACM):
  - [ ] Certificate for your domain
  - [ ] Add CNAME records in DNS to verify
  - [ ] Wait for certificate issuance (~10 minutes)
  
- [ ] Update ALB listener for HTTPS:
  - [ ] Port 443 with SSL certificate
  - [ ] Redirect HTTP→HTTPS

## Post-Deployment Testing

### 1. Application Testing ✓
- [ ] Access homepage: https://your-domain.com/
- [ ] Check navbar loads
- [ ] Test user login
- [ ] Search for an item
- [ ] Create a test build
- [ ] Access admin panel: /admin/
- [ ] Test social auth (Google, Facebook)

### 2. Performance Testing ✓
- [ ] Load test with 100 concurrent users:
  ```bash
  # Using Apache Bench
  ab -n 1000 -c 100 https://your-domain.com/
  ```
- [ ] Monitor RDS CloudWatch metrics:
  - [ ] CPU < 50%
  - [ ] Memory < 60%
  - [ ] Connections < 50% of max

### 3. Monitoring Setup ✓
- [ ] Enable CloudWatch logs for application
- [ ] Set up alarms for:
  - [ ] RDS CPU > 80%
  - [ ] RDS Storage > 80%
  - [ ] ALB target health
  - [ ] ECS task failures
  
- [ ] Set up SNS notifications (email alerts)

### 4. Backup & Disaster Recovery ✓
- [ ] Verify RDS automated backups (30-day retention)
- [ ] Create manual RDS backup (keep forever)
- [ ] Test restore procedure (dry-run):
  ```bash
  # Create test snapshot
  aws rds create-db-snapshot \
    --source-db-instance-identifier fashionista-mysql \
    --db-snapshot-identifier fashionista-test-restore
  
  # Then restore to test instance
  aws rds restore-db-instance-from-db-snapshot \
    --db-instance-identifier fashionista-mysql-test \
    --db-snapshot-identifier fashionista-test-restore
  ```

## Cost Optimization

### Monthly Cost Estimate (US East 1)
- RDS t3.micro: ~$20-30/month
- ECS Fargate: ~$15-25/month (1 task)
- ALB: ~$15/month
- S3 static files: <$1/month (small project)
- **Total**: ~$50-70/month

### Cost Reduction Tips
- [ ] Use RDS Reserved Instances for 1-3 year discount
- [ ] Use Fargate Spot instances (70% discount, less reliable)
- [ ] Scale down outside business hours
- [ ] Archive old session data regularly

## Maintenance (Ongoing)

### Weekly
- [ ] Check CloudWatch dashboards
- [ ] Review application logs for errors
- [ ] Monitor disk space on RDS

### Monthly
- [ ] Review AWS billing
- [ ] Test backup restore procedure
- [ ] Update Docker image (security patches)
- [ ] Clean up old logs and backups

### Quarterly
- [ ] Major version updates (Django, MySQL, etc.)
- [ ] Performance tuning based on metrics
- [ ] Security audit (access logs, permissions)
- [ ] Plan capacity for growth

## Rollback Plan

If deployment fails:

### Option 1: Use Old RDS Snapshot
```bash
# Restore from pre-migration snapshot
aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier fashionista-mysql-restore \
  --db-snapshot-identifier fashionista-backup-pre-migration

# Modify app task definition to point to restored RDS
# Update ECS service with new task definition
```

### Option 2: Keep Previous Version Running
```bash
# Keep old Docker container running while testing new
# Update ALB target group to point to old container
# Monitor for issues before full migration
```

### Option 3: Use Database Backup
```bash
# If issue is within RDS, restore point-in-time
aws rds restore-db-instance-to-point-in-time \
  --source-db-instance-identifier fashionista-mysql \
  --target-db-instance-identifier fashionista-mysql-restored \
  --restore-time 2026-04-18T10:30:00Z
```

## Quick Reference Commands

```bash
# Monitor RDS
aws rds describe-db-instances --db-instance-identifier fashionista-mysql

# Check ECS tasks
aws ecs list-tasks --cluster fashionista-cluster --launch-type FARGATE

# View logs
aws logs tail /ecs/fashionista-web --follow

# Connect to RDS
mysql -h ENDPOINT -u fashionista -p fashionista

# Check DNS
nslookup your-domain.com

# Test SSL
openssl s_client -connect your-domain.com:443

# Monitor costs (last 7 days)
aws ce get-cost-and-usage \
  --time-period Start=2026-04-11,End=2026-04-18 \
  --granularity MONTHLY \
  --metrics UnblendedCost
```

## Support Contacts

- AWS Support: https://console.aws.amazon.com/support/
- RDS Documentation: https://docs.aws.amazon.com/rds/
- ECS Documentation: https://docs.aws.amazon.com/ecs/
- Django Documentation: https://docs.djangoproject.com/

---

**Last Updated**: April 18, 2026  
**Version**: 1.0  
**Status**: Ready for deployment
