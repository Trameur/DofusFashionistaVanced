@echo off
chcp 65001 >nul

REM ===============================================================
REM  Creates (or updates) a LOCAL admin account with a password,
REM  for the site's normal login form (the Google button does not
REM  work locally).
REM
REM  IMPORTANT: start the server first with
REM  DofusFashionista_Windows11.bat and leave it running, so that
REM  MySQL is up. Then run THIS file in another window.
REM ===============================================================

cd /d "%~dp0fashionsite"
set "PYTHONPATH=%~dp0fashionistapulp"
set "PYTHONUNBUFFERED=1"
set "PYTHONIOENCODING=UTF-8"
set "DJANGO_SETTINGS_MODULE=fashionsite.settings"

echo ===============================================
echo  Creating a local admin account
echo ===============================================
echo.
set /p ADMINUSER="Admin user name: "
set /p ADMINEMAIL="Email (optional, Enter to skip): "
echo.

where py >nul 2>nul
if %ERRORLEVEL%==0 (
    py -3 manage.py create_local_admin --username "%ADMINUSER%" --email "%ADMINEMAIL%"
) else (
    python manage.py create_local_admin --username "%ADMINUSER%" --email "%ADMINEMAIL%"
)

echo.
echo Then log in with this user name and password
echo through the site's login form (not the Google button),
echo and open the "Admin tools" link in the menu.
echo.
pause
