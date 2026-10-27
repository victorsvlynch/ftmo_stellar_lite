@echo off
cd /d "%~dp0"
title Verificacion de Operacion 24/7 - FundedNext Stellar Lite (Oracle Cloud)
mode con: cols=105 lines=38
cls

set "KEY=%USERPROFILE%\.ssh\ssh-key-2026-10-26.key"
if not exist "%KEY%" set "KEY=%USERPROFILE%\.ssh\oracle_vps.key"
if not exist "%KEY%" set "KEY=%~dp0VPS-Oracle\ssh-key-2026-10-26.key"

echo ==============================================================================
echo   VERIFICACION DE OPERACION 24/7 EN ORACLE CLOUD INFRASTRUCTURE (OCI)
echo   Servidor VPS: 157.137.225.144 | Estrategia Ganadora: NY_OPEN (Oro GC=F)
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
echo  1. Iniciar Streaming de Logs en Vivo (Segundo a Segundo - Ctrl+C para salir)
echo  2. Salir
echo ==============================================================================
set /p opt="Seleccione una opcion [1-2] (Por defecto 1): "
if "%opt%"=="2" goto FIN
cls
echo Conectando al flujo continuo de logs en tiempo real... (Presiona Ctrl+C para detener)
echo ------------------------------------------------------------------------------
ssh -i "%KEY%" -o StrictHostKeyChecking=no ubuntu@157.137.225.144 "journalctl -u stellar_ny_open -f"

:FIN
echo.
pause
