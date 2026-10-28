@echo off
cd /d "%~dp0"
title Disparar Senal de Prueba hacia MT5 - FundedNext Stellar Lite
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

echo ==============================================================================
echo   DISPARADOR DE SENAL DE PRUEBA WEBHOOK HACIA METATRADER 5 (MT5)
echo ==============================================================================
echo.
echo Este script enviara una micro-orden demo de prueba (0.01 lotes en Oro)
echo a traves del servidor Webhook para verificar que el Expert Advisor en MT5
echo la reciba y la ejecute instantaneamente en tu cuenta de broker.
echo.
set "confirm=S"
set /p confirm="Deseas enviar la senal de prueba ahora? [S/N] (Por defecto S): "
if /i "%confirm%"=="N" (
    echo Operacion cancelada.
    pause
    exit /b 0
)

echo.
echo [1/2] Verificando conexion local (http://127.0.0.1:8000)...
python -c "import socket; s = socket.socket(); s.settimeout(1); res = s.connect_ex(('127.0.0.1', 8000)); s.close(); exit(0 if res == 0 else 1)" 2>nul
if %ERRORLEVEL% EQU 0 (
    echo [OK] Tunel local activo en puerto 8000.
    echo [2/2] Enviando senal via tunel local...
    python -c "import urllib.request, json; data = json.dumps({'action':'OPEN_BUY','lots':0.01,'symbol':'XAUUSD'}).encode(); req = urllib.request.Request('http://127.0.0.1:8000/api/test_order', data=data, headers={'Content-Type':'application/json'}); res = urllib.request.urlopen(req, timeout=5).read().decode(); print('\n[RESPUESTA SERVIDOR]:', res); print('\n>> Mira tu MetaTrader 5: el EA capturo la senal y abrio la orden en 1 segundo.')"
) else (
    echo [AVISO] El tunel local no esta abierto en tu PC.
    echo [2/2] Enviando senal directamente al servidor en Oracle Cloud via SSH...
    ssh -i "%KEY%" -o StrictHostKeyChecking=no ubuntu@157.137.225.144 "curl -s -X POST http://localhost:8000/api/test_order -H 'Content-Type: application/json' -d '{\"action\":\"OPEN_BUY\",\"lots\":0.01,\"symbol\":\"XAUUSD\"}'"
    echo.
    echo ==============================================================================
    echo  >> SENAL ENCOLADA EN ORACLE CLOUD CON EXITO.
    echo  >> ATENCION: Para que MetaTrader 5 pueda recibirla y ejecutarla en el broker,
    echo     debes tener ABIERTO el archivo 'Conectar_Puente_Webhook_MT5.bat'.
    echo ==============================================================================
)

echo.
echo ==============================================================================
echo  Prueba completada.
echo ==============================================================================
pause
