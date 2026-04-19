@echo off
setlocal enabledelayedexpansion

REM Création d'un journal d'installation
if not exist "logs" mkdir logs
set "LOG_FILE=logs\install_%date:~6,4%-%date:~3,2%-%date:~0,2%_%time:~0,2%%time:~3,2%.log"
set "LOG_FILE=%LOG_FILE: =0%"

echo =============================================================== | tee %LOG_FILE%
echo Installation de DofusFashionistaVanced pour Windows | tee -a %LOG_FILE%
echo =============================================================== | tee -a %LOG_FILE%
echo. | tee -a %LOG_FILE%
echo Ce script va configurer DofusFashionistaVanced sur votre système Windows. | tee -a %LOG_FILE%
echo Les logs d'installation sont enregistrés dans: %LOG_FILE% | tee -a %LOG_FILE%
echo. | tee -a %LOG_FILE%
echo Prérequis: | tee -a %LOG_FILE%
echo  - Python 3.9+ installé et ajouté au PATH | tee -a %LOG_FILE%
echo  - Accès administrateur pour installer certaines dépendances | tee -a %LOG_FILE%
echo  - Connexion Internet pour télécharger les packages | tee -a %LOG_FILE%
echo  - MySQL installé et configuré (ou sera installé par l'utilisateur) | tee -a %LOG_FILE%
echo. | tee -a %LOG_FILE%
echo Appuyez sur une touche pour commencer l'installation ou Ctrl+C pour annuler | tee -a %LOG_FILE%
pause > nul

REM Vérifier que Python est installé
echo Vérification de Python... | tee -a %LOG_FILE%
python --version > nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ERREUR: Python n'est pas installé ou n'est pas dans le PATH. | tee -a %LOG_FILE%
    echo Veuillez installer Python depuis https://www.python.org/downloads/ | tee -a %LOG_FILE%
    echo Assurez-vous de cocher "Add Python to PATH" lors de l'installation. | tee -a %LOG_FILE%
    pause
    exit /b 1
)

REM Vérifier la version de Python
for /f "tokens=2" %%a in ('python --version 2^>^&1') do set "PYTHON_VERSION=%%a"
echo Version Python détectée: %PYTHON_VERSION% | tee -a %LOG_FILE%

REM Définir le PYTHONPATH
set "CURRENT_DIR=%cd%"
echo Définition de PYTHONPATH... | tee -a %LOG_FILE%
setx PYTHONPATH "%CURRENT_DIR%\fashionistapulp" /M
if %ERRORLEVEL% NEQ 0 (
    echo AVERTISSEMENT: Impossible de définir PYTHONPATH de manière permanente. | tee -a %LOG_FILE%
    echo Le script continuera mais vous devrez peut-être le définir manuellement plus tard. | tee -a %LOG_FILE%
)
set "PYTHONPATH=%CURRENT_DIR%\fashionistapulp;%PYTHONPATH%"
echo PYTHONPATH temporaire défini avec succès. | tee -a %LOG_FILE%

REM Installer les packages requis avec gestion des erreurs
echo Installation des packages Python requis... | tee -a %LOG_FILE%
echo Cette étape peut prendre plusieurs minutes. Veuillez patienter... | tee -a %LOG_FILE%
python -m pip install --upgrade pip 2>> %LOG_FILE%
if %ERRORLEVEL% NEQ 0 (
    echo AVERTISSEMENT: Échec de la mise à jour de pip. Tentative de continuer... | tee -a %LOG_FILE%
)

echo Installation des dépendances Python (1/2)... | tee -a %LOG_FILE%
python -m pip install wheel setuptools 2>> %LOG_FILE%
if %ERRORLEVEL% NEQ 0 (
    echo AVERTISSEMENT: Problème lors de l'installation de wheel/setuptools. Tentative de continuer... | tee -a %LOG_FILE%
)

echo Installation des dépendances Python (2/2)... | tee -a %LOG_FILE%
REM Utiliser un timeout pour éviter que pip ne se bloque indéfiniment
powershell -Command "Start-Process python -ArgumentList '-m', 'pip', 'install', '-r', 'requirements_win.txt' -NoNewWindow -Wait" 2>> %LOG_FILE%
if %ERRORLEVEL% NEQ 0 (
    echo AVERTISSEMENT: Certains packages n'ont peut-être pas été installés correctement. | tee -a %LOG_FILE%
    echo Le script continuera, mais certaines fonctionnalités pourraient ne pas fonctionner. | tee -a %LOG_FILE%
)
echo Installation des packages terminée. | tee -a %LOG_FILE%

REM Vérifier la présence de MySQL
echo Vérification de la présence de MySQL... | tee -a %LOG_FILE%
mysql --version > nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo MySQL n'est pas installé ou n'est pas dans le PATH. | tee -a %LOG_FILE%
    echo. | tee -a %LOG_FILE%
    echo Veuillez télécharger et installer MySQL depuis: | tee -a %LOG_FILE%
    echo https://dev.mysql.com/downloads/installer/ | tee -a %LOG_FILE%
    echo. | tee -a %LOG_FILE%
    echo Durant l'installation, configurez MySQL avec: | tee -a %LOG_FILE%
    echo - Nom d'utilisateur: root | tee -a %LOG_FILE%
    echo - Mot de passe: à définir (ce mot de passe sera utilisé plus tard) | tee -a %LOG_FILE%
    echo. | tee -a %LOG_FILE%
    echo Une fois MySQL installé, appuyez sur une touche pour continuer | tee -a %LOG_FILE%
    echo ou fermez cette fenêtre et relancez le script plus tard. | tee -a %LOG_FILE%
    pause > nul
    
    REM Vérifier à nouveau après l'installation par l'utilisateur
    mysql --version > nul 2>&1
    if %ERRORLEVEL% NEQ 0 (
        echo MySQL n'est toujours pas détecté. L'installation s'arrête ici. | tee -a %LOG_FILE%
        echo Veuillez installer MySQL et réexécuter ce script. | tee -a %LOG_FILE%
        pause
        exit /b 1
    ) else {
        echo MySQL installé avec succès! | tee -a %LOG_FILE%
    }
) else (
    echo MySQL est déjà installé. | tee -a %LOG_FILE%
)

REM Exécuter le script de configuration avec gestion du timeout
echo. | tee -a %LOG_FILE%
echo Exécution du script de configuration principal... | tee -a %LOG_FILE%
echo Cette étape peut prendre plusieurs minutes. Veuillez patienter... | tee -a %LOG_FILE%
timeout /t 5 > nul
powershell -Command "Start-Process python -ArgumentList 'configure_fashionista_root.py', '-i', '-s', '-d' -NoNewWindow -Wait" 2>> %LOG_FILE%
if %ERRORLEVEL% NEQ 0 (
    echo ERREUR: La configuration a échoué. | tee -a %LOG_FILE%
    echo Consultez le journal pour plus de détails: %LOG_FILE% | tee -a %LOG_FILE%
    pause
    exit /b 1
)
echo Configuration principale terminée. | tee -a %LOG_FILE%

REM Configuration de la base de données avec gestion des erreurs
echo. | tee -a %LOG_FILE%
echo Configuration de la base de données... | tee -a %LOG_FILE%
echo Veuillez fournir vos identifiants MySQL: | tee -a %LOG_FILE%
set /p mysql_user="Nom d'utilisateur MySQL (default: root): " || set "mysql_user=root"
set /p mysql_password="Mot de passe MySQL: "

echo. | tee -a %LOG_FILE%
echo Tentative de connexion à MySQL... | tee -a %LOG_FILE%

REM Tester la connexion avant de créer la base de données
mysql -u %mysql_user% -p%mysql_password% -e "SELECT 1;" > nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ERREUR: Impossible de se connecter à MySQL avec les identifiants fournis. | tee -a %LOG_FILE%
    echo Veuillez vérifier que MySQL est en cours d'exécution et que vos identifiants sont corrects. | tee -a %LOG_FILE%
    pause
    exit /b 1
)

echo Création de la base de données... | tee -a %LOG_FILE%
mysql -u %mysql_user% -p%mysql_password% -e "CREATE DATABASE IF NOT EXISTS fashionista CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;" 2>> %LOG_FILE%
if %ERRORLEVEL% NEQ 0 (
    echo ERREUR: Impossible de créer la base de données. | tee -a %LOG_FILE%
    echo Consultez le journal pour plus de détails: %LOG_FILE% | tee -a %LOG_FILE%
    pause
    exit /b 1
)
echo Base de données créée avec succès. | tee -a %LOG_FILE%

REM Configurer Django et faire les migrations
echo. | tee -a %LOG_FILE%
echo Mise à jour des paramètres de la base de données... | tee -a %LOG_FILE%
cd fashionsite
echo Exécution des migrations Django... | tee -a %LOG_FILE%
echo Cette étape peut prendre plusieurs minutes. Veuillez patienter... | tee -a ..\%LOG_FILE%
python manage.py migrate 2>> ..\%LOG_FILE%
if %ERRORLEVEL% NEQ 0 (
    echo AVERTISSEMENT: Problème lors des migrations Django. | tee -a ..\%LOG_FILE%
    echo L'application pourrait ne pas fonctionner correctement. | tee -a ..\%LOG_FILE%
    echo Consultez le journal pour plus de détails: %LOG_FILE% | tee -a ..\%LOG_FILE%
) else (
    echo Migrations Django terminées avec succès. | tee -a ..\%LOG_FILE%
)
cd ..

REM Confirmer la fin de l'installation
echo. | tee -a %LOG_FILE%
echo =============================================================== | tee -a %LOG_FILE%
echo Installation terminée! | tee -a %LOG_FILE%
echo =============================================================== | tee -a %LOG_FILE%
echo. | tee -a %LOG_FILE%
echo Pour lancer DofusFashionistaVanced, exécutez run_fashionista.bat | tee -a %LOG_FILE%
echo. | tee -a %LOG_FILE%
echo En cas de problèmes: | tee -a %LOG_FILE%
echo 1. Vérifiez le journal d'installation: %LOG_FILE% | tee -a %LOG_FILE%
echo 2. Exécutez test_windows_config.bat pour diagnostiquer les problèmes | tee -a %LOG_FILE%
echo. | tee -a %LOG_FILE%
echo Profitez de DofusFashionistaVanced! | tee -a %LOG_FILE%
echo. | tee -a %LOG_FILE%
pause