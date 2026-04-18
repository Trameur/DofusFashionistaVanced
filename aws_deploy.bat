@echo off
REM AWS Deployment Helper Script for Dofus Fashionista
REM This script provides quick commands for AWS operations

setlocal enabledelayedexpansion

if "%1"=="" (
    call :show_menu
) else (
    call :%1 %*
    if errorlevel 1 exit /b 1
)

exit /b 0

:show_menu
echo.
echo ============================================
echo  AWS Deployment Helper for Dofus Fashionista
echo ============================================
echo.
echo Usage: aws_deploy.bat [command] [options]
echo.
echo Available commands:
echo.
echo   test-sync          Test database sync (dry-run)
echo                      Usage: aws_deploy.bat test-sync
echo.
echo   sync-to-docker     Sync local MySQL to Docker
echo                      Usage: aws_deploy.bat sync-to-docker
echo.
echo   sync-to-aws        Sync local MySQL to AWS RDS
echo                      Usage: aws_deploy.bat sync-to-aws [rds-endpoint]
echo.
echo   help               Show detailed help
echo                      Usage: aws_deploy.bat help
echo.
echo   check-pymysql      Verify PyMySQL is installed
echo                      Usage: aws_deploy.bat check-pymysql
echo.
echo Examples:
echo   aws_deploy.bat test-sync
echo   aws_deploy.bat sync-to-docker
echo   aws_deploy.bat sync-to-aws fashionista-mysql.c9akciq32.us-east-1.rds.amazonaws.com
echo.
goto :eof

:test-sync
echo.
echo Running database sync in DRY-RUN mode...
echo (No changes will be made)
echo.
python sync_db.py --dry-run
if errorlevel 1 (
    echo.
    echo ERROR: Dry-run test failed!
    echo.
    exit /b 1
)
echo.
echo SUCCESS: Dry-run completed successfully!
echo.
goto :eof

:sync-to-docker
echo.
echo Syncing local MySQL to Docker MySQL...
echo.
python sync_db.py ^
    --source-host localhost ^
    --source-port 3306 ^
    --source-db fashionista_migration ^
    --source-user fashionista ^
    --source-pass fashionista ^
    --dest-host localhost ^
    --dest-port 3307 ^
    --dest-db fashionista ^
    --dest-user fashionista ^
    --dest-pass fashionista

if errorlevel 1 (
    echo.
    echo ERROR: Sync to Docker failed!
    echo.
    exit /b 1
)
echo.
echo SUCCESS: Data synced to Docker MySQL!
echo.
goto :eof

:sync-to-aws
if "%2"=="" (
    echo.
    echo ERROR: AWS RDS endpoint is required!
    echo.
    echo Usage: aws_deploy.bat sync-to-aws [rds-endpoint]
    echo.
    echo Example:
    echo   aws_deploy.bat sync-to-aws fashionista-mysql.c9akciq32.us-east-1.rds.amazonaws.com
    echo.
    exit /b 1
)

set RDS_ENDPOINT=%2

echo.
echo WARNING: This will sync data to AWS RDS
echo Endpoint: %RDS_ENDPOINT%
echo.
echo You will be prompted to enter the RDS password.
echo Press Ctrl+C to cancel...
echo.
pause

echo.
echo Syncing to AWS RDS...
echo.
python sync_db.py ^
    --source-host localhost ^
    --source-port 3306 ^
    --source-db fashionista_migration ^
    --source-user fashionista ^
    --source-pass fashionista ^
    --dest-host %RDS_ENDPOINT% ^
    --dest-port 3306 ^
    --dest-db fashionista ^
    --dest-user fashionista ^
    --dest-pass 

if errorlevel 1 (
    echo.
    echo ERROR: Sync to AWS RDS failed!
    echo Check db_sync.log for details.
    echo.
    exit /b 1
)
echo.
echo SUCCESS: Data synced to AWS RDS!
echo.
goto :eof

:help
echo.
echo ============================================
echo  AWS Deployment Helper - Detailed Help
echo ============================================
echo.
echo QUICK REFERENCE:
echo.
echo 1. First time setup:
echo    - Read AWS_MIGRATION.md for architecture overview
echo    - Read AWS_DEPLOYMENT_CHECKLIST.md for step-by-step guide
echo.
echo 2. Test data migration locally:
echo    aws_deploy.bat test-sync
echo    aws_deploy.bat sync-to-docker
echo.
echo 3. Migrate to AWS RDS:
echo    aws_deploy.bat sync-to-aws [your-rds-endpoint]
echo.
echo 4. View migration log:
echo    type db_sync.log
echo.
echo REQUIREMENTS:
echo.
echo - Python 3.9+ installed
echo - PyMySQL installed: pip install pymysql
echo - Local MySQL running (port 3306)
echo - AWS account with RDS access
echo.
echo DOCUMENTATION FILES:
echo.
echo - AWS_MIGRATION.md
echo   Complete guide for AWS setup and data migration
echo   Includes RDS setup, security, deployment steps
echo.
echo - AWS_DEPLOYMENT_CHECKLIST.md
echo   Actionable checklist with timeline and costs
echo   Includes pre/post deployment verification
echo.
echo - MIGRATION_EXAMPLES.md
echo   10 practical examples for different scenarios
echo   Includes troubleshooting and performance tips
echo.
echo - sync_db.py
echo   Reusable Python script for database synchronization
echo   Can be run from anywhere with proper parameters
echo.
echo COMMON TASKS:
echo.
echo Test migration (no changes):
echo   python sync_db.py --dry-run
echo.
echo Sync to Docker locally:
echo   python sync_db.py --dest-host localhost --dest-port 3307
echo.
echo Sync to AWS RDS:
echo   python sync_db.py --dest-host fashionista-mysql.xxxxx.rds.amazonaws.com
echo.
echo Use environment variables:
echo   set DEST_DB_HOST=fashionista-mysql.xxxxx.rds.amazonaws.com
echo   python sync_db.py
echo.
echo Check migration log:
echo   type db_sync.log
echo.
goto :eof

:check-pymysql
echo.
echo Checking PyMySQL installation...
echo.
python -c "import pymysql; print('✓ PyMySQL version:', pymysql.__version__)"
if errorlevel 1 (
    echo.
    echo ERROR: PyMySQL not found!
    echo.
    echo Install it with:
    echo   pip install pymysql
    echo.
    exit /b 1
)
echo.
goto :eof

echo.
echo ERROR: Unknown command '%1'
echo.
call :show_menu
exit /b 1
