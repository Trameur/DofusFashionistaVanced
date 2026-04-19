@echo off
REM Script Docker pour DofusFashionistaVanced
REM Usage: run_docker.bat                         -> démarrer (sans supprimer les données)
REM        run_docker.bat reset CONFIRM_DELETE_DATA -> repartir de zéro (supprime la base de données)
echo.
echo =========================================
echo   DofusFashionistaVanced - Docker
echo   Python 3.14 + MySQL 8 + Django
echo =========================================
echo.

REM Vérifier si Docker est installé
docker --version >nul 2>&1
if errorlevel 1 (
    echo ERREUR: Docker n'est pas installe.
    echo Installez Docker Desktop depuis https://www.docker.com/products/docker-desktop
    pause
    exit /b 1
)

REM Vérifier si Docker Compose est disponible
docker compose version >nul 2>&1
if errorlevel 1 (
    echo ERREUR: Docker Compose n'est pas disponible.
    echo Installez Docker Desktop ^(il inclut Docker Compose^).
    pause
    exit /b 1
)

REM Vérifier si on doit repartir de zéro
if /i "%1"=="reset" (
    if /i not "%2"=="CONFIRM_DELETE_DATA" (
        echo ERREUR: la commande reset supprime irreversiblement le volume MySQL Docker local.
        echo Utilisez: run_docker.bat reset CONFIRM_DELETE_DATA
        echo.
        pause
        exit /b 1
    )
    echo Remise a zero: suppression des conteneurs et de la base de donnees...
    docker compose down -v
    echo Remise a zero terminee.
    echo.
)

echo Construction et demarrage...
echo La premiere fois, cela peut prendre 5-10 minutes pour telecharger Python 3.14 et installer les dependances.
echo.

REM Construire et démarrer sans supprimer les données
docker compose up --build -d

if errorlevel 1 (
    echo.
    echo ERREUR lors du demarrage. Logs:
    docker compose logs --tail=50
    echo.
    pause
    exit /b 1
)

echo.
echo Attente que MySQL et Django soient prets...
timeout /t 10 /nobreak >nul

REM Afficher le statut
docker compose ps

echo.
echo =========================================
echo   DofusFashionistaVanced est pret !
echo =========================================
echo.
echo   http://localhost:8000
echo.
echo   Commandes utiles:
echo   - Logs en direct : docker compose logs -f
echo   - Arreter        : docker compose down
echo   - Remettre a zero: run_docker.bat reset
echo.

start http://localhost:8000

echo Si ce n'est pas le cas, allez sur http://localhost:8000
echo.
pause
