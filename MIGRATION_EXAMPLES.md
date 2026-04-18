# Database Migration Examples

Practical examples for different migration scenarios.

## Example 1: Local Development (Docker)

**Scenario**: Sync local MySQL → Local Docker MySQL

```bash
python sync_db.py \
  --source-host localhost \
  --source-port 3306 \
  --source-db fashionista_migration \
  --source-user fashionista \
  --source-pass fashionista \
  --dest-host localhost \
  --dest-port 3307 \
  --dest-db fashionista \
  --dest-user fashionista \
  --dest-pass fashionista
```

**Expected time**: 5-15 minutes  
**Network**: Local (fast)  
**Use case**: Development, testing migrations locally

---

## Example 2: AWS RDS Migration (from Windows)

**Scenario**: Sync local MySQL → AWS RDS

```bash
# First, test connectivity (dry-run)
python sync_db.py \
  --source-host localhost \
  --source-port 3306 \
  --source-db fashionista_migration \
  --source-user fashionista \
  --source-pass fashionista \
  --dest-host fashionista-mysql.c9akciq32.us-east-1.rds.amazonaws.com \
  --dest-port 3306 \
  --dest-db fashionista \
  --dest-user fashionista \
  --dest-pass "AwsRdsPassword123!" \
  --dry-run

# If dry-run succeeds, run actual migration
python sync_db.py \
  --source-host localhost \
  --source-port 3306 \
  --source-db fashionista_migration \
  --source-user fashionista \
  --source-pass fashionista \
  --dest-host fashionista-mysql.c9akciq32.us-east-1.rds.amazonaws.com \
  --dest-port 3306 \
  --dest-db fashionista \
  --dest-user fashionista \
  --dest-pass "AwsRdsPassword123!"
```

**Expected time**: 15-45 minutes  
**Network**: Internet (slower, depends on connection)  
**Use case**: Production deployment

---

## Example 3: RDS to RDS Migration (AWS to AWS)

**Scenario**: Migrate between RDS instances in AWS

```bash
# If running from EC2 instance in same region (fastest)
python sync_db.py \
  --source-host fashionista-staging.xxx.rds.amazonaws.com \
  --source-port 3306 \
  --source-db fashionista \
  --source-user fashionista \
  --source-pass "StagingPassword" \
  --dest-host fashionista-prod.xxx.rds.amazonaws.com \
  --dest-port 3306 \
  --dest-db fashionista \
  --dest-user fashionista \
  --dest-pass "ProdPassword"
```

**Expected time**: 5-20 minutes  
**Network**: AWS internal (very fast)  
**Use case**: Promoting staging to production

---

## Example 4: Using Environment Variables

**Scenario**: Reduce command-line complexity using env vars

```bash
# Set environment variables
$env:SOURCE_DB_HOST = "localhost"
$env:SOURCE_DB_PORT = "3306"
$env:SOURCE_DB_NAME = "fashionista_migration"
$env:SOURCE_DB_USER = "fashionista"
$env:SOURCE_DB_PASSWORD = "fashionista"

$env:DEST_DB_HOST = "fashionista-mysql.xxx.rds.amazonaws.com"
$env:DEST_DB_PORT = "3306"
$env:DEST_DB_NAME = "fashionista"
$env:DEST_DB_USER = "fashionista"
$env:DEST_DB_PASSWORD = "AwsPassword123!"

# Run with minimal arguments
python sync_db.py

# Or override specific values
python sync_db.py --dest-port 3307
```

---

## Example 5: Batch Migration (Multiple Environments)

**Scenario**: Script to sync multiple environments

Create `batch_migrate.ps1`:

```powershell
#!/usr/bin/env pwsh

# Array of environments to migrate
$environments = @(
    @{
        name = "staging"
        source_host = "localhost"
        dest_host = "fashionista-staging.xxx.rds.amazonaws.com"
    },
    @{
        name = "production"
        source_host = "localhost"
        dest_host = "fashionista-prod.xxx.rds.amazonaws.com"
    }
)

foreach ($env in $environments) {
    Write-Host "=== Migrating to $($env.name) ===" -ForegroundColor Green
    
    python sync_db.py `
        --source-host $env.source_host `
        --source-port 3306 `
        --source-db fashionista_migration `
        --source-user fashionista `
        --source-pass fashionista `
        --dest-host $env.dest_host `
        --dest-port 3306 `
        --dest-db fashionista `
        --dest-user fashionista `
        --dest-pass (Read-Host -Prompt "Enter RDS password for $($env.name)" -AsSecureString | ConvertFrom-SecureString)
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "✗ Migration to $($env.name) failed!" -ForegroundColor Red
        break
    }
    
    Write-Host "✓ Migration to $($env.name) completed" -ForegroundColor Green
    Write-Host ""
}
```

Run it:
```bash
./batch_migrate.ps1
```

---

## Example 6: Restore from Backup

**Scenario**: Rollback to previous state after migration

```bash
# List available backups
Get-ChildItem db_backup_*.sql | Sort-Object LastWriteTime -Descending

# Restore specific backup
mysql -h fashionista-mysql.xxx.rds.amazonaws.com \
      -u fashionista \
      -p fashionista < db_backup_fashionista_20260418_103045.sql

# Monitor restore progress
# (MySQL shows CREATE/INSERT progress)
```

---

## Example 7: Incremental/Scheduled Sync

**Scenario**: Sync at regular intervals (daily backup sync)

Create `scheduled_sync.ps1`:

```powershell
# Create scheduled task for daily sync

$trigger = New-ScheduledTaskTrigger -Daily -At 3:00AM
$action = New-ScheduledTaskAction -Execute "python" `
    -Argument 'sync_db.py --source-host localhost --dest-host rds-endpoint.com'
$settings = New-ScheduledTaskSettingsSet -MultipleInstances Parallel -StartWhenAvailable

Register-ScheduledTask -TaskName "Fashionista-DB-Sync" `
    -Trigger $trigger `
    -Action $action `
    -Settings $settings `
    -RunLevel Highest
```

View logs after scheduled run:
```bash
tail -50 db_sync.log
```

---

## Example 8: Verify After Migration

**Scenario**: Check data integrity after migration

```bash
# Connect to RDS
mysql -h fashionista-mysql.xxx.rds.amazonaws.com -u fashionista -p fashionista

# Run verification queries
USE fashionista;

-- Check totals
SELECT 'Total Users' as check_type, COUNT(*) as count FROM auth_user
UNION ALL
SELECT 'Total Characters', COUNT(*) FROM chardata_char
UNION ALL
SELECT 'Total Builds', COUNT(*) FROM chardata_build
UNION ALL
SELECT 'Total Sessions', COUNT(*) FROM django_session;

-- Check data distribution
SELECT class_name, COUNT(*) as char_count 
FROM chardata_char 
GROUP BY class_name 
ORDER BY char_count DESC;

-- Check recent activity
SELECT COUNT(*) as recent_builds 
FROM chardata_build 
WHERE creation_date > DATE_SUB(NOW(), INTERVAL 30 DAY);

-- Check user registration timeline
SELECT 
    DATE_FORMAT(date_joined, '%Y-%m') as month,
    COUNT(*) as new_users
FROM auth_user
GROUP BY DATE_FORMAT(date_joined, '%Y-%m')
ORDER BY month DESC
LIMIT 12;
```

---

## Example 9: Performance Tuning for Large Datasets

**Scenario**: Migrate 50M+ rows efficiently

Edit `sync_db.py` before running:

```python
# Line ~30, increase batch sizes
BATCH_SIZE = 1000        # Was 300
COMMIT_INTERVAL = 20     # Was 10
```

Then run:
```bash
# Consider increasing MySQL max_allowed_packet
mysql -h dest-host -u user -p -e "SET GLOBAL max_allowed_packet = 268435456;"

# Run migration with timing
time python sync_db.py \
    --source-host source \
    --dest-host dest
```

Monitor progress:
```bash
# In another terminal, watch log file
Get-Content db_sync.log -Wait
```

---

## Example 10: Handling Connection Issues

**Scenario**: Migrate with unreliable network

```bash
# Use retry wrapper script in PowerShell
$maxRetries = 3
$retryCount = 0

while ($retryCount -lt $maxRetries) {
    try {
        python sync_db.py `
            --source-host localhost `
            --dest-host rds-endpoint.com
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✓ Migration successful" -ForegroundColor Green
            break
        }
    }
    catch {
        $retryCount++
        if ($retryCount -lt $maxRetries) {
            Write-Host "Migration failed, retrying in 60 seconds... (Attempt $retryCount/$maxRetries)" -ForegroundColor Yellow
            Start-Sleep -Seconds 60
        }
        else {
            Write-Host "✗ Migration failed after $maxRetries attempts" -ForegroundColor Red
            exit 1
        }
    }
}
```

---

## Troubleshooting Tips

### Check MySQL Connection
```bash
# Test if MySQL is running
telnet localhost 3306

# Check MySQL status
mysql -h localhost -u fashionista -p -e "SHOW VARIABLES LIKE 'version';"
```

### Monitor Migration Progress
```bash
# Watch the log file in real-time
Get-Content db_sync.log -Wait

# Or check specific table progress
mysql -e "SELECT COUNT(*) FROM fashionista.chardata_char;"
```

### Common Error Messages
| Error | Solution |
|-------|----------|
| `Can't connect to MySQL` | Check MySQL service is running, verify host/port |
| `Access denied` | Verify username/password, check user permissions |
| `Table doesn't exist` | Ensure schema is created first (run Django migrations) |
| `Packet too large` | Increase `max_allowed_packet` on MySQL server |
| `Connection timeout` | Check network connectivity, firewall rules |

---

**Last Updated**: April 18, 2026  
**Version**: 1.0
