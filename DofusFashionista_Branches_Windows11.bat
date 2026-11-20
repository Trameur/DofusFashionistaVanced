@echo off
chcp 65001 >nul

powershell -NoProfile -ExecutionPolicy RemoteSigned -Command "& { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8; $OutputEncoding = [System.Text.Encoding]::UTF8; & '%~dp0run_branch_windows11.ps1' %* }"

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo An error occurred, error code %ERRORLEVEL%.
    pause
)
