@echo off
cd /d "%~dp0"
title Puente Webhook MT5 - Oracle Cloud VPS (157.137.225.144)
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
echo   PUENTE ENCRIPTADO WEBHOOK MT5 -- ORACLE CLOUD VPS (157.137.225.144)
echo   Modelo: FundedNext Stellar Lite ($5,000) -- Estrategia: NY_OPEN
echo ==============================================================================
echo.
echo [1/2] Verificando servicio webhook en Oracle Cloud VPS...
ssh -i "%KEY%" -o StrictHostKeyChecking=no ubuntu@157.137.225.144 "systemctl is-active stellar_webhook" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [AVISO] Iniciando servicio stellar_webhook en el servidor...
    ssh -i "%KEY%" -o StrictHostKeyChecking=no ubuntu@157.137.225.144 "sudo systemctl start stellar_webhook"
)

echo [OK] Servidor Webhook activo en Oracle Cloud.
echo.
echo [2/2] Estableciendo tunel seguro (Puerto 8000) para MetaTrader 5...
echo ------------------------------------------------------------------------------
echo  >> INSTRUCCIONES EN METATRADER 5:
echo     1. Abre tu terminal MetaTrader 5.
echo     2. Ve a: Herramientas -> Opciones -> Asesores Expertos.
echo     3. Marca 'Permitir WebRequest para las siguientes URL'.
echo     4. Agrega las URLs:
echo        http://127.0.0.1:8000
echo        http://157.137.225.144:8000
echo     5. En el Navegador de MT5, arrastra 'StellarLite_Webhook_Bridge' a tu grafico de Oro (XAUUSD).
echo ------------------------------------------------------------------------------
echo  >> El tunel esta CONECTADO Y ACTIVO. Deja esta ventana abierta mientras operes.
echo  >> Para detener el tunel, presiona Ctrl+C o cierra esta ventana.
echo ------------------------------------------------------------------------------
echo.

ssh -N -L 8000:localhost:8000 -i "%KEY%" -o StrictHostKeyChecking=no ubuntu@157.137.225.144
pause
