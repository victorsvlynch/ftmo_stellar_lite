@echo off
chcp 65001 > nul
setlocal

echo ============================================================
echo   DESPLIEGUE A ORACLE CLOUD VPS (Batch Runner)
echo ============================================================

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0desplegar_a_vps.ps1" %*

echo.
pause
