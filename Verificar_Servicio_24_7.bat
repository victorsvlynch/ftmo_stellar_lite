@echo off
cd /d "%~dp0"
title Verificacion de Operacion 24/7 - FundedNext Stellar Lite (Oracle Cloud)
cls

:: Resolver clave SSH (Auto-configuración en nueva PC)
if not exist "%USERPROFILE%\.ssh" mkdir "%USERPROFILE%\.ssh" >nul 2>&1
if not exist "%USERPROFILE%\.ssh\oracle_vps.key" (
    if exist "%~dp0VPS-Oracle\oracle_vps.key" copy /y "%~dp0VPS-Oracle\oracle_vps.key" "%USERPROFILE%\.ssh\oracle_vps.key" >nul 2>&1
    if exist "%~dp0VPS-Oracle\ssh-key-2026-10-26.key" copy /y "%~dp0VPS-Oracle\ssh-key-2026-10-26.key" "%USERPROFILE%\.ssh\oracle_vps.key" >nul 2>&1
)
set "KEY=%USERPROFILE%\.ssh\oracle_vps.key"
if not exist "%KEY%" set "KEY=%USERPROFILE%\.ssh\ssh-key-2026-10-26.key"
if not exist "%KEY%" set "KEY=%~dp0VPS-Oracle\oracle_vps.key"
if not exist "%KEY%" set "KEY=%~dp0VPS-Oracle\ssh-key-2026-10-26.key"
if not exist "%KEY%" set "KEY=%~dp0VPS-Oracle\ssh-key-2026-10-22-vps-oracle.key"

if not exist "%KEY%" (
    echo [ERROR] No se encontro la clave privada SSH para conectar a Oracle VPS.
    echo Buscado en: %USERPROFILE%\.ssh\
    echo Buscado en: %~dp0VPS-Oracle\
    echo.
    pause
    exit /b 1
)

echo ==============================================================================
echo   VERIFICACION DE OPERACION 24/7 EN ORACLE CLOUD INFRASTRUCTURE (OCI)
echo   Servidor VPS: 157.137.225.144 -- Estrategia Ganadora: NY_OPEN (Oro GC=F)
echo ==============================================================================
echo.
echo [1/3] Consultando estado del servicio en la nube...
ssh -i "%KEY%" -o StrictHostKeyChecking=no ubuntu@157.137.225.144 "systemctl status stellar_ny_open --no-pager"
echo.
echo ==============================================================================
echo [2/3] Ultimos 8 ciclos de analisis ejecutados de forma desatendida:
echo ==============================================================================
ssh -i "%KEY%" -o StrictHostKeyChecking=no ubuntu@157.137.225.144 "journalctl -u stellar_ny_open -n 8 --no-pager"
echo.
echo ==============================================================================
echo [3/3] Opciones de Verificacion:
echo  1. Iniciar Streaming de Logs en Vivo (Segundo a Segundo - Presiona Ctrl+C para salir)
echo  2. Salir
echo ==============================================================================
set "opt=1"
set /p opt="Seleccione una opcion [1-2] (Por defecto 1): "
if "%opt%"=="2" goto FIN

cls
echo Conectando al flujo continuo de logs en tiempo real... (Presiona Ctrl+C para detener)
echo ------------------------------------------------------------------------------
ssh -i "%KEY%" -o StrictHostKeyChecking=no ubuntu@157.137.225.144 "journalctl -u stellar_ny_open -f"

:FIN
echo.
echo ==============================================================================
echo  Verificacion finalizada.
echo ==============================================================================
pause
