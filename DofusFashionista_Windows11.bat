@echo off
chcp 65001 >nul

echo ===============================================
echo Launching DofusFashionistaVanced for Windows 11...
echo ===============================================
echo.

REM Run PowerShell script with appropriate parameters and force UTF-8 encoding
powershell -NoProfile -ExecutionPolicy RemoteSigned -Command "& { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8; $OutputEncoding = [System.Text.Encoding]::UTF8; & '%~dp0run_windows11.ps1' %* }"

REM If PowerShell encounters an error, display it
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ==================================================
    echo An error occurred while starting the application.
    echo.
    echo Error code: %ERRORLEVEL%
    echo.
    echo Check the logs in the "logs" folder for more information.
    echo ==================================================
    pause
)