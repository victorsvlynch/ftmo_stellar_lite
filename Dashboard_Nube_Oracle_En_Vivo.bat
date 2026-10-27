@echo off
cd /d "%~dp0"
title Dashboard Remoto en Vivo - Oracle Cloud VPS (NY_OPEN 24/7)
chcp 65001 >nul
cls

:: Resolver clave SSH
set "KEY=%USERPROFILE%\.ssh\ssh-key-2026-10-26.key"
if not exist "%KEY%" set "KEY=%USERPROFILE%\.ssh\oracle_vps.key"
if not exist "%KEY%" set "KEY=%~dp0VPS-Oracle\ssh-key-2026-10-26.key"
if not exist "%KEY%" set "KEY=%~dp0VPS-Oracle\ssh-key-2026-10-22-vps-oracle.key"

if not exist "%KEY%" (
    echo [ERROR] No se encontro la clave privada SSH para conectar a Oracle VPS.
    echo.
    pause
    exit /b 1
)

echo ==============================================================================
echo   CONECTANDO CON ORACLE CLOUD VPS (157.137.225.144) -- MODO EN VIVO 24/7
echo   Estrategia Ganadora: NY_OPEN (Oro GC=F) -- Sincronizacion Directa
echo ==============================================================================
echo.
ssh -tt -i "%KEY%" -o StrictHostKeyChecking=no ubuntu@157.137.225.144 "cd /home/ubuntu/FTMO_Stellar_Lite && python3 -u main.py winner-live --refresh 1.0"
echo.
pause
