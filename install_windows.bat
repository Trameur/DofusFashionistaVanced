@echo off
setlocal enabledelayedexpansion

REM Install log
if not exist "logs" mkdir logs
set "LOG_FILE=logs\install_%date:~6,4%-%date:~3,2%-%date:~0,2%_%time:~0,2%%time:~3,2%.log"
set "LOG_FILE=%LOG_FILE: =0%"

echo =============================================================== | tee %LOG_FILE%
echo DofusFashionistaVanced install for Windows | tee -a %LOG_FILE%
echo =============================================================== | tee -a %LOG_FILE%
echo. | tee -a %LOG_FILE%
echo This script sets up DofusFashionistaVanced on your Windows system. | tee -a %LOG_FILE%
echo The install log is written to: %LOG_FILE% | tee -a %LOG_FILE%
echo. | tee -a %LOG_FILE%
echo Prerequisites: | tee -a %LOG_FILE%
echo  - Python 3.9+ installed and on the PATH | tee -a %LOG_FILE%
echo  - Administrator rights to install some dependencies | tee -a %LOG_FILE%
echo  - An Internet connection to download the packages | tee -a %LOG_FILE%
echo  - MySQL installed and set up (or installed by you along the way) | tee -a %LOG_FILE%
echo. | tee -a %LOG_FILE%
echo Press any key to start the install, or Ctrl+C to cancel | tee -a %LOG_FILE%
pause > nul

REM Find a real Python interpreter (prefer the py launcher, skip the Microsoft Store stub)
echo Checking Python... | tee -a %LOG_FILE%
set "PY="
py -3 --version >nul 2>&1 && set "PY=py -3"
if not defined PY (
    python --version >nul 2>&1 && set "PY=python"
)
if not defined PY (
    echo ERROR: Python not found ^(the Microsoft Store aliases do not count^). | tee -a %LOG_FILE%
    echo Install Python 3.12+: winget install -e --id Python.Python.3.14 | tee -a %LOG_FILE%
    echo ^(or https://www.python.org/downloads/ and tick "Add Python to PATH" + py launcher^) | tee -a %LOG_FILE%
    pause
    exit /b 1
)

REM Show the Python version found
for /f "tokens=2" %%a in ('%PY% --version 2^>^&1') do set "PYTHON_VERSION=%%a"
echo Python version found: !PYTHON_VERSION! ^(via %PY%^) | tee -a %LOG_FILE%

REM PYTHONPATH
set "CURRENT_DIR=%cd%"
echo Setting PYTHONPATH... | tee -a %LOG_FILE%
setx PYTHONPATH "%CURRENT_DIR%\fashionistapulp" /M
if %ERRORLEVEL% NEQ 0 (
    echo WARNING: could not set PYTHONPATH permanently. | tee -a %LOG_FILE%
    echo The script goes on, but you may have to set it by hand later. | tee -a %LOG_FILE%
)
set "PYTHONPATH=%CURRENT_DIR%\fashionistapulp;%PYTHONPATH%"
echo Temporary PYTHONPATH set. | tee -a %LOG_FILE%

REM Required packages
echo Installing the required Python packages... | tee -a %LOG_FILE%
echo This step can take several minutes. Please wait... | tee -a %LOG_FILE%
%PY% -m pip install --upgrade pip 2>> %LOG_FILE%
if %ERRORLEVEL% NEQ 0 (
    echo WARNING: pip upgrade failed. Trying to go on... | tee -a %LOG_FILE%
)

echo Installing the Python dependencies (1/2)... | tee -a %LOG_FILE%
%PY% -m pip install wheel setuptools 2>> %LOG_FILE%
if %ERRORLEVEL% NEQ 0 (
    echo WARNING: problem while installing wheel/setuptools. Trying to go on... | tee -a %LOG_FILE%
)

echo Installing the Python dependencies (2/2)... | tee -a %LOG_FILE%
%PY% -m pip install -r requirements_win.txt 2>> %LOG_FILE%
if %ERRORLEVEL% NEQ 0 (
    echo WARNING: some packages may not have installed correctly. | tee -a %LOG_FILE%
    echo The script goes on, but some features may not work. | tee -a %LOG_FILE%
)
echo Package install done. | tee -a %LOG_FILE%

REM MySQL
echo Checking for MySQL... | tee -a %LOG_FILE%
mysql --version > nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo MySQL is not installed or not on the PATH. | tee -a %LOG_FILE%
    echo. | tee -a %LOG_FILE%
    echo Please download and install MySQL from: | tee -a %LOG_FILE%
    echo https://dev.mysql.com/downloads/installer/ | tee -a %LOG_FILE%
    echo. | tee -a %LOG_FILE%
    echo During the install, set up MySQL with: | tee -a %LOG_FILE%
    echo - User name: root | tee -a %LOG_FILE%
    echo - Password: your choice, you will need it later | tee -a %LOG_FILE%
    echo. | tee -a %LOG_FILE%
    echo Once MySQL is installed, press any key to go on | tee -a %LOG_FILE%
    echo or close this window and run the script again later. | tee -a %LOG_FILE%
    pause > nul
    
    REM Check again after the user's install
    mysql --version > nul 2>&1
    if %ERRORLEVEL% NEQ 0 (
        echo MySQL is still not found. The install stops here. | tee -a %LOG_FILE%
        echo Please install MySQL and run this script again. | tee -a %LOG_FILE%
        pause
        exit /b 1
    ) else {
        echo MySQL installed. | tee -a %LOG_FILE%
    }
) else (
    echo MySQL is already installed. | tee -a %LOG_FILE%
)

REM Main configuration script
echo. | tee -a %LOG_FILE%
echo Running the main configuration script... | tee -a %LOG_FILE%
echo This step can take several minutes. Please wait... | tee -a %LOG_FILE%
timeout /t 5 > nul
%PY% configure_fashionista_root.py -i -s -d 2>> %LOG_FILE%
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: the configuration failed. | tee -a %LOG_FILE%
    echo See the log for details: %LOG_FILE% | tee -a %LOG_FILE%
    pause
    exit /b 1
)
echo Main configuration done. | tee -a %LOG_FILE%

REM Database
echo. | tee -a %LOG_FILE%
echo Setting up the database... | tee -a %LOG_FILE%
echo Please enter your MySQL credentials: | tee -a %LOG_FILE%
set /p mysql_user="MySQL user name (default: root): " || set "mysql_user=root"
set /p mysql_password="MySQL password: "

echo. | tee -a %LOG_FILE%
echo Connecting to MySQL... | tee -a %LOG_FILE%

REM Test the connection before creating the database
mysql -u %mysql_user% -p%mysql_password% -e "SELECT 1;" > nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: could not connect to MySQL with these credentials. | tee -a %LOG_FILE%
    echo Please check that MySQL is running and that your credentials are correct. | tee -a %LOG_FILE%
    pause
    exit /b 1
)

echo Creating the database... | tee -a %LOG_FILE%
mysql -u %mysql_user% -p%mysql_password% -e "CREATE DATABASE IF NOT EXISTS fashionista CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;" 2>> %LOG_FILE%
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: could not create the database. | tee -a %LOG_FILE%
    echo See the log for details: %LOG_FILE% | tee -a %LOG_FILE%
    pause
    exit /b 1
)
echo Database created. | tee -a %LOG_FILE%

REM Django settings and migrations
echo. | tee -a %LOG_FILE%
echo Updating the database settings... | tee -a %LOG_FILE%
cd fashionsite
echo Running the Django migrations... | tee -a %LOG_FILE%
echo This step can take several minutes. Please wait... | tee -a ..\%LOG_FILE%
%PY% manage.py migrate 2>> ..\%LOG_FILE%
if %ERRORLEVEL% NEQ 0 (
    echo WARNING: problem during the Django migrations. | tee -a ..\%LOG_FILE%
    echo The application may not work correctly. | tee -a ..\%LOG_FILE%
    echo See the log for details: %LOG_FILE% | tee -a ..\%LOG_FILE%
) else (
    echo Django migrations done. | tee -a ..\%LOG_FILE%
)
cd ..

REM Done
echo. | tee -a %LOG_FILE%
echo =============================================================== | tee -a %LOG_FILE%
echo Install complete. | tee -a %LOG_FILE%
echo =============================================================== | tee -a %LOG_FILE%
echo. | tee -a %LOG_FILE%
echo To start DofusFashionistaVanced, run run_fashionista.bat | tee -a %LOG_FILE%
echo. | tee -a %LOG_FILE%
echo If something goes wrong: | tee -a %LOG_FILE%
echo 1. Read the install log: %LOG_FILE% | tee -a %LOG_FILE%
echo 2. Run test_windows_config.bat to diagnose the problems | tee -a %LOG_FILE%
echo. | tee -a %LOG_FILE%
echo Enjoy DofusFashionistaVanced. | tee -a %LOG_FILE%
echo. | tee -a %LOG_FILE%
pause