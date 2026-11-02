@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"
title Operaciones Sandbox en Vivo - FundedNext Stellar Lite
chcp 65001 >nul

:: Resolver clave SSH
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

:MENU
cls
echo ==============================================================================
echo        CONSULTA DE OPERACIONES SANDBOX (LABORATORIO TEST SIN MT5)
echo        Oracle Cloud VPS 24/7 (157.137.225.144) ^| $10,000 USD x Cuenta
echo ==============================================================================
echo.
echo   ┌─ [1] INSPECCIÓN DE OPERACIONES EN LA NUBE (ORACLE VPS) ───────────────┐
echo   │  1. Ver Reporte Completo de Operaciones Sandbox (Oro, EUR/USD, SP500) │
echo   │  2. Tablero Multi-Modalidad en Vivo (Posiciones abiertas y PnL)       │
echo   └───────────────────────────────────────────────────────────────────────┘
echo   ┌─ [2] LOGS EN TIEMPO REAL POR ESTRATEGIA (STREAMING JOURNALCTL) ───────┐
echo   │  3. Logs en Vivo: Sandbox Oro (stellar_test_oro.service)              │
echo   │  4. Logs en Vivo: Sandbox EUR/USD (stellar_test_eurusd.service)       │
echo   │  5. Logs en Vivo: Sandbox S&P 500 (stellar_test_sp500.service)        │
echo   └───────────────────────────────────────────────────────────────────────┘
echo   ┌─ [3] ENTORNO LOCAL (ESTA PC) ─────────────────────────────────────────┐
echo   │  6. Ver Reporte de Bases de Datos Locales en Windows                  │
echo   │  7. Salir                                                             │
echo   └───────────────────────────────────────────────────────────────────────┘
echo.
set "opt=1"
set /p opt=" Seleccione una opción [1-7] (Por defecto 1): "

if "%opt%"=="1" (
    cls
    echo Conectando a Oracle Cloud VPS para generar reporte de Sandbox...
    echo.
    ssh -i "%KEY%" -o StrictHostKeyChecking=no ubuntu@157.137.225.144 "cd /home/ubuntu/FTMO_Stellar_Lite && python3 main.py sandbox"
    echo.
    pause
    goto MENU
)
if "%opt%"=="2" (
    cls
    echo Conectando a Tablero en Vivo... (Presione Ctrl+C para salir al menú)
    echo.
    ssh -tt -i "%KEY%" -o StrictHostKeyChecking=no ubuntu@157.137.225.144 "cd /home/ubuntu/FTMO_Stellar_Lite && python3 -u main.py multi-detail --refresh 1.5"
    goto MENU
)
if "%opt%"=="3" (
    cls
    echo Conectando a logs de Sandbox Oro (Ctrl+C para salir)...
    ssh -i "%KEY%" -o StrictHostKeyChecking=no ubuntu@157.137.225.144 "journalctl -u stellar_test_oro -f"
    goto MENU
)
if "%opt%"=="4" (
    cls
    echo Conectando a logs de Sandbox EUR/USD (Ctrl+C para salir)...
    ssh -i "%KEY%" -o StrictHostKeyChecking=no ubuntu@157.137.225.144 "journalctl -u stellar_test_eurusd -f"
    goto MENU
)
if "%opt%"=="5" (
    cls
    echo Conectando a logs de Sandbox S&P 500 (Ctrl+C para salir)...
    ssh -i "%KEY%" -o StrictHostKeyChecking=no ubuntu@157.137.225.144 "journalctl -u stellar_test_sp500 -f"
    goto MENU
)
if "%opt%"=="6" (
    cls
    echo Generando reporte de bases de datos locales en Windows...
    echo.
    python "%~dp0main.py" sandbox
    echo.
    pause
    goto MENU
)
if "%opt%"=="7" exit /b 0

goto MENU
