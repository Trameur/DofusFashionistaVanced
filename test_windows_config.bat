@echo off
echo ===============================================================
echo Windows configuration check for DofusFashionistaVanced
echo ===============================================================
echo.

REM Find a real Python interpreter (prefer the py launcher, skip the Microsoft Store stub)
set "PY="
py -3 --version >nul 2>&1 && set "PY=py -3"
if not defined PY (
    python --version >nul 2>&1 && set "PY=python"
)

REM Python
echo Checking Python...
if not defined PY (
    echo [FAIL] Python not found ^(the Microsoft Store aliases do not count^).
    echo Install Python 3.12+: winget install -e --id Python.Python.3.14
    echo ^(or https://www.python.org/downloads/ and tick "Add Python to PATH" + py launcher^)
) else (
    echo [OK] Python found through "%PY%":
    %PY% --version
)
echo.

REM pip
echo Checking pip...
%PY% -m pip --version > nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [FAIL] pip is not installed correctly.
) else (
    echo [OK] pip is installed.
)
echo.

REM PYTHONPATH
echo Checking PYTHONPATH...
if "%PYTHONPATH%"=="" (
    echo [WARNING] PYTHONPATH is not set.
    echo Run: setx PYTHONPATH "%CD%\fashionistapulp"
) else (
    echo [INFO] Current PYTHONPATH: %PYTHONPATH%
    echo Make sure it contains the path to the fashionistapulp folder.
)
echo.

REM MySQL
echo Checking MySQL...
mysql --version > nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [FAIL] MySQL is not installed or not on the PATH.
    echo Download and install MySQL from: https://dev.mysql.com/downloads/installer/
) else (
    echo [OK] MySQL is installed.
    echo Checking the MySQL service...
    sc query mysql > nul 2>&1
    if %ERRORLEVEL% NEQ 0 (
        echo [WARNING] MySQL service not found. It may have another name.
    ) else (
        sc query mysql | find "RUNNING" > nul
        if %ERRORLEVEL% NEQ 0 (
            echo [FAIL] The MySQL service is not running.
            echo Open Windows Services and start the MySQL service.
        ) else (
            echo [OK] The MySQL service is running.
        )
    )
)
echo.

REM Essential Python packages
echo Checking the essential Python packages...
set "MISSING_PACKAGES="
%PY% -c "import django" 2>nul || set "MISSING_PACKAGES=%MISSING_PACKAGES% Django"
%PY% -c "import social_core" 2>nul || set "MISSING_PACKAGES=%MISSING_PACKAGES% social-auth-core"
%PY% -c "import pulp" 2>nul || set "MISSING_PACKAGES=%MISSING_PACKAGES% PuLP"
%PY% -c "import pymysql" 2>nul || set "MISSING_PACKAGES=%MISSING_PACKAGES% pymysql"

if not "%MISSING_PACKAGES%"=="" (
    echo [FAIL] Missing Python packages:%MISSING_PACKAGES%
    echo Install them with: pip install -r requirements_win.txt
) else (
    echo [OK] The essential Python packages are installed.
)
echo.

REM Configuration files
echo Checking the configuration files...
set "CONFIG_DIR=%APPDATA%\fashionista"
if not exist "%CONFIG_DIR%" (
    echo [FAIL] The configuration folder does not exist: %CONFIG_DIR%
    echo Run configure_fashionista_root.py first.
) else (
    echo [OK] The configuration folder exists: %CONFIG_DIR%
    if not exist "%CONFIG_DIR%\config" (
        echo [FAIL] The config file is missing.
    ) else (
        echo [OK] The config file exists.
    )
    if not exist "%CONFIG_DIR%\gen_config.json" (
        echo [FAIL] The gen_config.json file is missing.
    ) else (
        echo [OK] The gen_config.json file exists.
    )
)
echo.

echo ===============================================================
echo Configuration check summary
echo ===============================================================
echo.
echo If problems were found, follow the instructions above.
echo For a full install, use the install_windows.bat script.
echo.
echo For more information, see the "Windows 11 troubleshooting" section
echo in README.md.
echo.
pause