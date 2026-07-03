@echo off
chcp 65001 >nul

REM ===============================================================
REM  Cree (ou met a jour) un compte admin LOCAL avec un mot de passe,
REM  utilisable via le formulaire de connexion normal du site
REM  (le bouton Google ne marche pas en local).
REM
REM  IMPORTANT : lance d'abord le serveur avec
REM  DofusFashionista_Windows11.bat et laisse-le tourner, pour que
REM  MySQL soit demarre. Puis lance CE fichier dans une autre fenetre.
REM ===============================================================

cd /d "%~dp0fashionsite"
set "PYTHONPATH=%~dp0fashionistapulp"
set "PYTHONUNBUFFERED=1"
set "PYTHONIOENCODING=UTF-8"
set "DJANGO_SETTINGS_MODULE=fashionsite.settings"

echo ===============================================
echo  Creation d'un compte admin local
echo ===============================================
echo.
set /p ADMINUSER="Nom d'utilisateur admin : "
set /p ADMINEMAIL="Email (optionnel, Entree pour ignorer) : "
echo.

where py >nul 2>nul
if %ERRORLEVEL%==0 (
    py -3 manage.py create_local_admin --username "%ADMINUSER%" --email "%ADMINEMAIL%"
) else (
    python manage.py create_local_admin --username "%ADMINUSER%" --email "%ADMINEMAIL%"
)

echo.
echo Connecte-toi ensuite avec ce nom d'utilisateur et ce mot de passe
echo via le formulaire "Connexion" du site (pas le bouton Google),
echo puis ouvre le lien "Admin tools" du menu.
echo.
pause
