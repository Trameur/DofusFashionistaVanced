@echo off
:RESTART
echo Starting the server...

:: Set the PYTHONPATH
set PYTHONPATH=%PYTHONPATH%;%cd%\fashionista\fashionistapulp

:: Clear solution cache
call wipe_solution_cache.py

:: Compile translations
cd fashionsite
if exist django-admin.py (
    call django-admin.py compilemessages
) else (
    call django-admin compilemessages
)
cd ..

:: Run the server locally on port 8000
call python fashionsite\manage.py runserver 0.0.0.0:8000

:: Check if the server crashed
if %errorlevel% neq 0 (
    echo Server crashed with exit code %errorlevel%. Respawning in 1 second... >&2
    timeout /t 1 /nobreak
    goto RESTART
)

pause
