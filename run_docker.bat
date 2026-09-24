@echo off
REM Docker script for DofusFashionistaVanced
REM Usage: run_docker.bat                         -> start (keeps the data)
REM        run_docker.bat reset CONFIRM_DELETE_DATA -> start from scratch (deletes the database)
echo.
echo =========================================
echo   DofusFashionistaVanced - Docker
echo   Python 3.14 + MySQL 8 + Django
echo =========================================
echo.

REM Is Docker installed
docker --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Docker is not installed.
    echo Install Docker Desktop from https://www.docker.com/products/docker-desktop
    pause
    exit /b 1
)

REM Is Docker Compose available
docker compose version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Docker Compose is not available.
    echo Install Docker Desktop ^(it includes Docker Compose^).
    pause
    exit /b 1
)

REM Start from scratch when asked
if /i "%1"=="reset" (
    if /i not "%2"=="CONFIRM_DELETE_DATA" (
        echo ERROR: reset permanently deletes the local Docker MySQL volume.
        echo Use: run_docker.bat reset CONFIRM_DELETE_DATA
        echo.
        pause
        exit /b 1
    )
    echo Reset: removing the containers and the database...
    docker compose down -v
    echo Reset done.
    echo.
)

echo Building and starting...
echo The first time, this can take 5-10 minutes to download Python 3.14 and install the dependencies.
echo.

REM Build and start, keeping the data
docker compose up --build -d

if errorlevel 1 (
    echo.
    echo ERROR while starting. Logs:
    docker compose logs --tail=50
    echo.
    pause
    exit /b 1
)

echo.
echo Waiting for MySQL and Django to be ready...
timeout /t 10 /nobreak >nul

REM Status
docker compose ps

echo.
echo =========================================
echo   DofusFashionistaVanced is ready
echo =========================================
echo.
echo   http://localhost:8000
echo.
echo   Useful commands:
echo   - Live logs : docker compose logs -f
echo   - Stop      : docker compose down
echo   - Reset     : run_docker.bat reset
echo.

start http://localhost:8000

echo If the browser did not open, go to http://localhost:8000
echo.
pause
