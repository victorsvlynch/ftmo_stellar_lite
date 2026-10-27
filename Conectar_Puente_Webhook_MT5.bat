@echo off
cd /d "%~dp0"
title Puente Webhook MT5 - Oracle Cloud VPS (157.137.225.144)
chcp 65001 >nul
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
    echo ==============================================================================
    echo [ERROR] No se encontro la clave privada SSH para conectar a Oracle VPS.
    echo ==============================================================================
    echo.
    pause
    exit /b 1
)

:MENU
cls
echo ==============================================================================
echo   GESTOR DEL PUENTE WEBHOOK MT5 -- ORACLE CLOUD VPS (157.137.225.144)
echo   Modelo: FundedNext Stellar Lite ($5,000) -- Estrategia: NY_OPEN (Oro)
echo ==============================================================================
echo.

:: Verificar si el túnel local en puerto 8000 está activo
set "TUNNEL_STATUS=INACTIVO"
netstat -ano | findstr /R ":8000 .*LISTENING" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    set "TUNNEL_STATUS=ACTIVO (Conectado a Oracle Cloud)"
)

echo   Estado del Tunel Local (Puerto 8000): [%TUNNEL_STATUS%]
echo.
echo ------------------------------------------------------------------------------
echo   OPCIONES DISPONIBLES:
echo ------------------------------------------------------------------------------
echo   [1] Iniciar Tunel en SEGUNDO PLANO (Recomendado - no ocupa ventana)
echo   [2] Iniciar Tunel en Primer Plano (Ventana interactiva)
echo   [3] Detener Tunel Activo
echo   [4] Probar Conexion con Servidor Webhook (http://127.0.0.1:8000)
echo   [5] Enviar Senal de Prueba a MT5 (0.01 lotes Oro)
echo   [6] Salir
echo ------------------------------------------------------------------------------
echo.
set /p OPC="Selecciona una opcion [1-6] (Por defecto 1): "
if "%OPC%"=="" set OPC=1

if "%OPC%"=="1" goto INICIAR_BACKGROUND
if "%OPC%"=="2" goto INICIAR_FOREGROUND
if "%OPC%"=="3" goto DETENER_TUNEL
if "%OPC%"=="4" goto PROBAR_CONEXION
if "%OPC%"=="5" goto ENVIAR_PRUEBA
if "%OPC%"=="6" exit /b 0
goto MENU

:INICIAR_BACKGROUND
echo.
echo Verificando servicio stellar_webhook en Oracle Cloud...
ssh -i "%KEY%" -o StrictHostKeyChecking=no ubuntu@157.137.225.144 "sudo systemctl start stellar_webhook" >nul 2>&1

echo Iniciando tunel SSH en segundo plano...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process ssh -ArgumentList '-i \"%KEY%\" -o StrictHostKeyChecking=no -N -L 8000:localhost:8000 ubuntu@157.137.225.144' -WindowStyle Hidden"

echo Esperando 3 segundos para confirmar conexion...
timeout /t 3 >nul

netstat -ano | findstr /R ":8000 .*LISTENING" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo.
    echo ==============================================================================
    echo [EXITO] Tunel SSH activado en SEGUNDO PLANO en puerto 8000.
    echo Ya puedes cerrar esta ventana. MT5 mantendra comunicacion 24/7.
    echo ==============================================================================
) else (
    echo.
    echo [AVISO] El puerto tardo en responder. Prueba la opcion 4 para verificar.
)
echo.
pause
goto MENU

:INICIAR_FOREGROUND
cls
echo ==============================================================================
echo   INICIANDO TUNEL EN PRIMER PLANO (Presiona Ctrl+C para detenerlo)
echo ==============================================================================
echo.
echo >> Instrucciones en MT5:
echo    1. Marca 'Permitir WebRequest' en Herramientas -> Opciones -> Asesores Expertos
echo    2. Agrega la URL: http://127.0.0.1:8000
echo    3. Arrastra 'StellarLite_Webhook_Bridge' a tu grafico de Oro (XAUUSD).
echo.
ssh -N -L 8000:localhost:8000 -i "%KEY%" -o StrictHostKeyChecking=no ubuntu@157.137.225.144
pause
goto MENU

:DETENER_TUNEL
echo.
echo Deteniendo procesos de tunel SSH...
powershell -NoProfile -Command "Get-Process ssh -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like '*8000*' -or $_.Path -like '*ssh*' } | Stop-Process -Force -ErrorAction SilentlyContinue"
echo [OK] Tunel detenido.
timeout /t 2 >nul
goto MENU

:PROBAR_CONEXION
echo.
echo Probando conexion con http://127.0.0.1:8000/api/health...
powershell -NoProfile -Command "try { $r = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/health' -TimeoutSec 3; Write-Host '[OK] Conexion Exitosa!' -ForegroundColor Green; Write-Host ($r | ConvertTo-Json) } catch { Write-Host '[ERROR] No se pudo conectar: ' $_.Exception.Message -ForegroundColor Red }"
echo.
pause
goto MENU

:ENVIAR_PRUEBA
call "%~dp0Probar_Senal_Webhook.bat"
goto MENU
