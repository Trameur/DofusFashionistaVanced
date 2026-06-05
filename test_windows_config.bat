@echo off
echo ===============================================================
echo Test de la configuration Windows pour DofusFashionistaVanced
echo ===============================================================
echo.

REM Détection d'un interpréteur Python réel (préférer le lanceur py ; ignorer le stub Microsoft Store)
set "PY="
py -3 --version >nul 2>&1 && set "PY=py -3"
if not defined PY (
    python --version >nul 2>&1 && set "PY=python"
)

REM Vérification de Python
echo Vérification de Python...
if not defined PY (
    echo [ÉCHEC] Python introuvable ^(les alias Microsoft Store ne comptent pas^).
    echo Installez Python 3.12+ : winget install -e --id Python.Python.3.14
    echo ^(ou https://www.python.org/downloads/ : cochez "Add Python to PATH" + py launcher^)
) else (
    echo [OK] Python détecté via "%PY%" :
    %PY% --version
)
echo.

REM Vérification de pip
echo Vérification de pip...
%PY% -m pip --version > nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ÉCHEC] pip n'est pas installé correctement.
) else (
    echo [OK] pip est installé.
)
echo.

REM Vérification du PYTHONPATH
echo Vérification de PYTHONPATH...
if "%PYTHONPATH%"=="" (
    echo [AVERTISSEMENT] PYTHONPATH n'est pas défini.
    echo Exécutez: setx PYTHONPATH "%CD%\fashionistapulp"
) else (
    echo [INFO] PYTHONPATH actuel: %PYTHONPATH%
    echo Assurez-vous qu'il contient le chemin vers le dossier fashionistapulp.
)
echo.

REM Vérification de MySQL
echo Vérification de MySQL...
mysql --version > nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ÉCHEC] MySQL n'est pas installé ou n'est pas dans le PATH.
    echo Téléchargez et installez MySQL depuis: https://dev.mysql.com/downloads/installer/
) else (
    echo [OK] MySQL est installé.
    echo Vérification du service MySQL...
    sc query mysql > nul 2>&1
    if %ERRORLEVEL% NEQ 0 (
        echo [AVERTISSEMENT] Le service MySQL n'est pas trouvé. Il est peut-être nommé différemment.
    ) else (
        sc query mysql | find "RUNNING" > nul
        if %ERRORLEVEL% NEQ 0 (
            echo [ÉCHEC] Le service MySQL n'est pas démarré.
            echo Lancez les services Windows et démarrez le service MySQL.
        ) else (
            echo [OK] Le service MySQL est en cours d'exécution.
        )
    )
)
echo.

REM Vérification des packages Python essentiels
echo Vérification des packages Python essentiels...
set "MISSING_PACKAGES="
%PY% -c "import django" 2>nul || set "MISSING_PACKAGES=%MISSING_PACKAGES% Django"
%PY% -c "import social_core" 2>nul || set "MISSING_PACKAGES=%MISSING_PACKAGES% social-auth-core"
%PY% -c "import pulp" 2>nul || set "MISSING_PACKAGES=%MISSING_PACKAGES% PuLP"
%PY% -c "import pymysql" 2>nul || set "MISSING_PACKAGES=%MISSING_PACKAGES% pymysql"

if not "%MISSING_PACKAGES%"=="" (
    echo [ÉCHEC] Packages Python manquants:%MISSING_PACKAGES%
    echo Installez-les avec: pip install -r requirements_win.txt
) else (
    echo [OK] Les packages Python essentiels sont installés.
)
echo.

REM Vérification des fichiers de configuration
echo Vérification des fichiers de configuration...
set "CONFIG_DIR=%APPDATA%\fashionista"
if not exist "%CONFIG_DIR%" (
    echo [ÉCHEC] Le répertoire de configuration n'existe pas: %CONFIG_DIR%
    echo Exécutez d'abord configure_fashionista_root.py.
) else (
    echo [OK] Le répertoire de configuration existe: %CONFIG_DIR%
    if not exist "%CONFIG_DIR%\config" (
        echo [ÉCHEC] Le fichier config est manquant.
    ) else (
        echo [OK] Le fichier config existe.
    )
    if not exist "%CONFIG_DIR%\gen_config.json" (
        echo [ÉCHEC] Le fichier gen_config.json est manquant.
    ) else (
        echo [OK] Le fichier gen_config.json existe.
    )
)
echo.

echo ===============================================================
echo Résumé du test de configuration
echo ===============================================================
echo.
echo Si des problèmes ont été détectés, suivez les instructions ci-dessus.
echo Pour une installation complète, utilisez le script install_windows.bat.
echo.
echo Pour plus d'informations, consultez la section "Dépannage Windows 11" 
echo dans le fichier README.md.
echo.
pause