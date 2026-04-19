# AWS Migration Quick Start Guide

**TL;DR** for deploying Dofus Fashionista to AWS.

## 30-Second Summary

1. **Create AWS RDS** instance (MySQL 8.0)
2. **Run sync script** to transfer data from local → AWS  
3. **Deploy Docker image** to AWS ECS/Fargate
4. **Point domain** to AWS load balancer

**Cost**: ~$60-80/month  
**Time**: ~2-3 hours of actual work (spread over 2 weeks)

---

## Step-by-Step for AWS

### Week 1: Setup & Data Migration

#### Step 1: Create AWS RDS (30 minutes)
```bash
# Create MySQL 8.0 instance
aws rds create-db-instance \
  --db-instance-identifier fashionista-mysql \
  --db-instance-class db.t3.micro \
  --engine mysql \
  --engine-version 8.0 \
  --master-username fashionista \
  --master-user-password "YourStrongPassword" \
  --allocated-storage 20 \
  --publicly-accessible

# Wait for status to be "available"
aws rds describe-db-instances --db-instance-identifier fashionista-mysql
```

**Note**: You'll get an RDS endpoint like:  
`fashionista-mysql.c9akciq32.us-east-1.rds.amazonaws.com`

#### Step 2: Configure Security (15 minutes)
- Allow inbound on port 3306 from your IP
- Allow inbound on port 3306 from your VPC CIDR (for app containers)

#### Step 3: Test Connectivity (5 minutes)
```bash
# From Windows, verify you can connect
mysql -h fashionista-mysql.c9akciq32.us-east-1.rds.amazonaws.com \
      -u fashionista -p fashionista

# Should see: Welcome to MySQL
```

#### Step 4: Test Data Migration Locally (30 minutes)
```bash
# Always test dry-run first
python sync_db.py --dry-run

# Watch the output for any errors
# Expected output shows all 24 tables would be synced
```

#### Step 5: Migrate Data to AWS (30-60 minutes)
```bash
# Run actual migration to AWS
# Replace endpoint with your actual RDS endpoint
python sync_db.py \
  --source-host localhost \
  --source-port 3306 \
  --source-db fashionista_migration \
  --dest-host fashionista-mysql.c9akciq32.us-east-1.rds.amazonaws.com \
  --dest-port 3306 \
  --dest-db fashionista \
  --source-user fashionista \
  --source-pass fashionista \
  --dest-user fashionista \
  --dest-pass "YourStrongPassword"

# Monitor progress in db_sync.log
type db_sync.log

# Expected: "✓ All tables verified - sync successful!"
```

#### Step 6: Verify Data (10 minutes)
```bash
# Connect to AWS RDS and check key tables
mysql -h fashionista-mysql.c9akciq32.us-east-1.rds.amazonaws.com \
      -u fashionista -p fashionista << 'EOF'
USE fashionista;
SELECT 'auth_user' as tbl, COUNT(*) as cnt FROM auth_user
UNION ALL SELECT 'chardata_char', COUNT(*) FROM chardata_char
UNION ALL SELECT 'chardata_build', COUNT(*) FROM chardata_build;
EOF

# Expected: Around 5662 users, 136295 chars, 136295 builds
```

### Week 2: Application Deployment

#### Step 7: Build & Push Docker Image (15 minutes)
```bash
# Build Docker image
docker build -t dofus-fashionista:latest .

# Tag for ECR
docker tag dofus-fashionista:latest \
  123456789.dkr.ecr.us-east-1.amazonaws.com/fashionista:latest

# Push to AWS ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 123456789.dkr.ecr.us-east-1.amazonaws.com

docker push 123456789.dkr.ecr.us-east-1.amazonaws.com/fashionista:latest
```

#### Step 8: Deploy to ECS (30 minutes)
- Create ECS cluster: `fashionista-cluster`
- Create task definition pointing to ECR image
- Create ECS service with 2-3 tasks
- Create Application Load Balancer
- Configure health checks

#### Step 9: Setup Domain (15 minutes)
- Point domain to ALB DNS name
- Request SSL certificate (ACM)
- Configure HTTPS listener on ALB

#### Step 10: Final Testing (30 minutes)
```bash
# Test application
curl https://your-domain.com/

# Test user login
# Test item search
# Test build creation
# Check admin panel works
```

---

## Using Helper Script

For Windows, use the included helper script:

```bash
# Test migration (dry-run)
.\aws_deploy.bat test-sync

# Sync to Docker locally
.\aws_deploy.bat sync-to-docker

# Sync to AWS RDS
.\aws_deploy.bat sync-to-aws fashionista-mysql.c9akciq32.us-east-1.rds.amazonaws.com

# Show detailed help
.\aws_deploy.bat help

# Check PyMySQL
.\aws_deploy.bat check-pymysql
```

---

## Environment Variables Method

If you don't want to type long commands:

```bash
# Set once in PowerShell
$env:SOURCE_DB_HOST = "localhost"
$env:SOURCE_DB_PORT = "3306"
$env:SOURCE_DB_NAME = "fashionista_migration"
$env:SOURCE_DB_USER = "fashionista"
$env:SOURCE_DB_PASSWORD = "fashionista"

$env:DEST_DB_HOST = "fashionista-mysql.c9akciq32.us-east-1.rds.amazonaws.com"
$env:DEST_DB_PORT = "3306"
$env:DEST_DB_NAME = "fashionista"
$env:DEST_DB_USER = "fashionista"
$env:DEST_DB_PASSWORD = "AwsPassword123"

# Then just run
python sync_db.py
```

---

## Troubleshooting

### "Can't connect to MySQL server"
- Check RDS security group allows your IP
- Verify RDS endpoint is correct
- Test with: `telnet RDS_ENDPOINT 3306`

### "Access denied for user"
- Verify username/password
- Check user has correct permissions
- Verify database name exists

### "Migration failed mid-way"
- Check `db_sync.log` for exact error
- Restore from backup if needed:
  ```bash
  mysql -h RDS_ENDPOINT -u fashionista -p < db_backup_*.sql
  ```
- Fix issue and re-run sync

### "Row counts don't match"
- Check network connectivity
- Check MySQL max_allowed_packet:
  ```bash
  mysql -h RDS_ENDPOINT -u fashionista -p -e "SHOW VARIABLES LIKE 'max_allowed_packet';"
  ```
- If < 16MB, increase it:
  ```bash
  mysql -h RDS_ENDPOINT -u fashionista -p -e "SET GLOBAL max_allowed_packet = 268435456;"
  ```

---

## Important Files

| File | Purpose |
|------|---------|
| [sync_db.py](sync_db.py) | Database sync script (main tool) |
| [AWS_MIGRATION.md](AWS_MIGRATION.md) | Complete AWS setup guide |
| [AWS_DEPLOYMENT_CHECKLIST.md](AWS_DEPLOYMENT_CHECKLIST.md) | Step-by-step checklist |
| [MIGRATION_EXAMPLES.md](MIGRATION_EXAMPLES.md) | 10 practical examples |
| [aws_deploy.bat](aws_deploy.bat) | Windows helper script |

---

## Costs Breakdown

| Service | Size | Cost/Month |
|---------|------|-----------|
| RDS MySQL | db.t3.micro | $20-30 |
| ECS Fargate | 256 CPU, 512 MB | $15-25 |
| ALB | 1 LB | $15 |
| S3 (static) | <1 GB | <$1 |
| **Total** | | **$50-70** |

*Can reduce with Reserved Instances or Spot instances*

---

## Monitoring After Deployment

```bash
# Check RDS metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/RDS \
  --metric-name CPUUtilization \
  --dimensions Name=DBInstanceIdentifier,Value=fashionista-mysql \
  --start-time 2026-04-18T00:00:00Z \
  --end-time 2026-04-19T00:00:00Z \
  --period 300 \
  --statistics Average,Maximum

# Check application logs
aws logs tail /ecs/fashionista-web --follow

# Check costs
aws ce get-cost-and-usage \
  --time-period Start=2026-04-11,End=2026-04-18 \
  --granularity MONTHLY \
  --metrics UnblendedCost
```

---

## Rollback Plan

If something goes wrong:

1. **Keep RDS running** (don't delete, costs almost nothing stopped)
2. **Use ALB to switch** back to old app version
3. **Restore from backup** if needed:
   ```bash
   aws rds restore-db-instance-from-db-snapshot \
     --db-instance-identifier fashionista-restore \
     --db-snapshot-identifier fashionista-backup
   ```

---

## Next Steps

1. **Read** [AWS_MIGRATION.md](AWS_MIGRATION.md) for detailed setup
2. **Follow** [AWS_DEPLOYMENT_CHECKLIST.md](AWS_DEPLOYMENT_CHECKLIST.md) checklist
3. **Review** [MIGRATION_EXAMPLES.md](MIGRATION_EXAMPLES.md) for your scenario
4. **Test locally** first: `python sync_db.py --dry-run`
5. **Deploy with confidence** - all tools are ready!

---

**Everything is prepared for AWS deployment!** 🚀

Use this guide as your reference during deployment.  
All scripts are production-ready and tested locally.

**Need help?** Check the referenced documentation files above.
