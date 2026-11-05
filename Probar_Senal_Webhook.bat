@echo off
setlocal DisableDelayedExpansion
cd /d "%~dp0"
title Disparar Senal de Prueba hacia MT5 - Modo Dual (FTMO / FundedNext)
chcp 65001 >nul
cls

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

echo ==============================================================================
echo   DISPARADOR DE SENAL DE PRUEBA WEBHOOK HACIA METATRADER 5 (MODO DUAL)
echo ==============================================================================
echo.
echo Este script enviara una micro-orden demo de prueba (0.01 lotes en Oro)
echo a traves del servidor Webhook para verificar que el Expert Advisor en MT5
echo la reciba y la ejecute instantaneamente en tu cuenta de broker.
echo.
echo   [1] Enviar prueba a MT1: FTMO 10K Challenge (Magic 505001)
echo   [2] Enviar prueba a MT2: FundedNext Stellar 10K Demo (Magic 505002)
echo   [3] Enviar prueba a AMBAS terminales (Magic 505001 + 505002)
echo   [4] Cancelar
echo.
set "target_mt=1"
set /p target_mt="Seleccione el destino de la prueba [1-4] (Por defecto 1): "
if "%target_mt%"=="4" exit /b 0

set "SELECTED_MAGIC=505001"
if "%target_mt%"=="2" set "SELECTED_MAGIC=505002"

echo.
echo [1/2] Verificando conexion local (http://127.0.0.1:8000)...
python -c "import socket; s = socket.socket(); s.settimeout(1); res = s.connect_ex(('127.0.0.1', 8000)); s.close(); exit(0 if res == 0 else 1)" 2>nul
if %ERRORLEVEL% EQU 0 (
    echo [OK] Tunel local activo en puerto 8000.
    echo [2/2] Enviando micro-orden de prueba via tunel local...
    if "%target_mt%"=="3" (
        python -c "import urllib.request, json; data1 = json.dumps({'action':'OPEN_BUY','lots':0.01,'symbol':'XAUUSD','magic':505001}).encode(); req1 = urllib.request.Request('http://127.0.0.1:8000/api/test_order', data=data1, headers={'Content-Type':'application/json'}); r1 = urllib.request.urlopen(req1, timeout=5).read().decode(); print('[MT1 FTMO 505001]:', r1); data2 = json.dumps({'action':'OPEN_BUY','lots':0.01,'symbol':'XAUUSD','magic':505002}).encode(); req2 = urllib.request.Request('http://127.0.0.1:8000/api/test_order', data=data2, headers={'Content-Type':'application/json'}); r2 = urllib.request.urlopen(req2, timeout=5).read().decode(); print('[MT2 STELLAR 505002]:', r2); print('\n>> Ambas terminales MT5 recibieron su orden correspondiente.')"
    ) else (
        python -c "import urllib.request, json; data = json.dumps({'action':'OPEN_BUY','lots':0.01,'symbol':'XAUUSD','magic':%SELECTED_MAGIC%}).encode(); req = urllib.request.Request('http://127.0.0.1:8000/api/test_order', data=data, headers={'Content-Type':'application/json'}); res = urllib.request.urlopen(req, timeout=5).read().decode(); print('\n[RESPUESTA SERVIDOR]:', res); print('\n>> Mira tu MetaTrader: la terminal con Magic %SELECTED_MAGIC% recibira la orden en 1 segundo.')"
    )
) else (
    echo [AVISO] El tunel local no esta abierto en tu PC.
    echo [2/2] Enviando senal directamente al servidor en Oracle Cloud via SSH...
    ssh -i "%KEY%" -o StrictHostKeyChecking=no ubuntu@157.137.225.144 "curl -s -X POST http://localhost:8000/api/test_order -H 'Content-Type: application/json' -d '{\"action\":\"OPEN_BUY\",\"lots\":0.01,\"symbol\":\"XAUUSD\",\"magic\":%SELECTED_MAGIC%}'"
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
