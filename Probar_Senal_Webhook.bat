@echo off
cd /d "%~dp0"
title Disparar Senal de Prueba hacia MT5 - FundedNext Stellar Lite
cls

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
echo Enviando senal al servidor Webhook en Oracle Cloud...
python -c "import urllib.request, json; data = json.dumps({'action':'OPEN_BUY','lots':0.01,'symbol':'XAUUSD'}).encode(); req = urllib.request.Request('http://127.0.0.1:8000/api/test_order', data=data, headers={'Content-Type':'application/json'}); res = urllib.request.urlopen(req).read().decode(); print('[RESPUESTA SERVIDOR]:', res); print('\n>> Mira tu MetaTrader 5: el EA capturo la senal y abrio la orden en 1 segundo.')" 2>nul

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [AVISO] No se pudo conectar a http://127.0.0.1:8000.
    echo Intentando enviar directamente a la IP publica del servidor...
    python -c "import urllib.request, json; data = json.dumps({'action':'OPEN_BUY','lots':0.01,'symbol':'XAUUSD'}).encode(); req = urllib.request.Request('http://157.137.225.144:8000/api/test_order', data=data, headers={'Content-Type':'application/json'}); res = urllib.request.urlopen(req).read().decode(); print('[RESPUESTA SERVIDOR]:', res)" 2>nul
)

echo.
echo ==============================================================================
echo  Prueba completada con exito.
echo ==============================================================================
pause
