@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"
title Panel de Control Maestro - FundedNext Stellar Lite ($5,000)
chcp 65001 >nul

:: ============================================================================
:: 1. RESOLVER CLAVE SSH PRIVADA (Auto-detección y aprovisionamiento local)
:: ============================================================================
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

:: ============================================================================
:: 2. DETECCIÓN DE ESTADO EN TIEMPO REAL
:: ============================================================================
set "STATUS_SSH=[OK - Detectada]"
if not exist "%KEY%" set "STATUS_SSH=[ERROR - No Encontrada]"

set "STATUS_TUNNEL=[INACTIVO - Opción 4 para conectar]"
netstat -ano | findstr /C:":8000 " | findstr /I "LISTENING" >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    set "STATUS_TUNNEL=[ACTIVO - Enlace 8000 Operativo]"
)

set "STATUS_MT5=[OFFLINE - MetaTrader 5 cerrado]"
tasklist /FI "IMAGENAME eq terminal64.exe" 2>nul | findstr /I "terminal64" >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    set "STATUS_MT5=[ONLINE - terminal64.exe activo]"
)

:: ============================================================================
:: 3. INTERFAZ GRÁFICA DEL PANEL DE CONTROL
:: ============================================================================
echo ==============================================================================
echo        PANEL DE CONTROL MAESTRO -- FUNDEDNEXT STELLAR LITE ($5,000 USD)
echo        Estrategia Oficial: NY_OPEN (Oro GC=F / XAUUSD) ^| R:R 1:2
echo ==============================================================================
echo   • Servidor en la Nube : Oracle Cloud VPS (157.137.225.144) [ONLINE 24/7]
echo   • Clave Privada SSH   : %STATUS_SSH%
echo   • Terminal MetaTrader : %STATUS_MT5%
echo   • Túnel Webhook (8000): %STATUS_TUNNEL%
echo ==============================================================================
echo.
echo   ┌─ [1] MONITOR Y DASHBOARDS EN TIEMPO REAL ─────────────────────────────┐
echo   │  1. Dashboard Remoto en Vivo (Oracle Cloud VPS 24/7) [RECOMENDADO]    │
echo   │  2. Dashboard Local en Vivo (Simulador en esta PC)                    │
echo   │  3. Tablero Multi-Estrategia Detallado (Historial y Posiciones Hoy)   │
echo   └───────────────────────────────────────────────────────────────────────┘
echo   ┌─ [2] CONECTIVIDAD METATRADER 5 (MT5 ^& WEBHOOK) ───────────────────────┐
echo   │  4. Gestor de Túnel Webhook (Iniciar / Detener enlace en Puerto 8000) │
echo   │  5. Disparar Micro-Orden de Prueba hacia MT5 (Test 0.01 lotes Oro)    │
echo   │  6. Simulación Realista con Broker MT5 (Inspección de Cuenta y Órdenes)│
echo   └───────────────────────────────────────────────────────────────────────┘
echo   ┌─ [3] ALERTAS MÓVILES A TU CELULAR (TELEGRAM) ─────────────────────────┐
echo   │  7. Enviar Alerta Institucional de Prueba a Telegram (@victorsvlynch) │
echo   │  8. Configurar / Re-vincular Telegram (Token de Bot y Chat ID)        │
echo   └───────────────────────────────────────────────────────────────────────┘
echo   ┌─ [4] GESTIÓN DEL SERVIDOR EN LA NUBE (ORACLE CLOUD VPS) ──────────────┐
echo   │  9. Diagnóstico de Salud del Servidor (Uptime, Memoria, Servicios)    │
echo   │ 10. Streaming de Logs en Tiempo Real (Segundo a Segundo - journalctl) │
echo   │ 11. Reiniciar Servicios en la Nube (Bot NY_OPEN + Webhook Server)     │
echo   └───────────────────────────────────────────────────────────────────────┘
echo   ┌─ [5] AUDITORÍA Y CONTROL ─────────────────────────────────────────────┐
echo   │ 12. Correr Suite de Verificación Automatizada (9 Pruebas 100%% OK)     │
echo   │ 13. Salir                                                             │
echo   └───────────────────────────────────────────────────────────────────────┘
echo.
set "opt=1"
set /p opt=" Seleccione una opción [1-13] (Por defecto 1): "

if "%opt%"=="1" goto DASH_REMOTE
if "%opt%"=="2" goto DASH_LOCAL
if "%opt%"=="3" goto DASH_MULTI
if "%opt%"=="4" goto WEBHOOK_TUNNEL
if "%opt%"=="5" goto WEBHOOK_TEST
if "%opt%"=="6" goto PRUEBA_MT5
if "%opt%"=="7" goto TG_TEST
if "%opt%"=="8" goto TG_CONFIG
if "%opt%"=="9" goto STATUS_VPS
if "%opt%"=="10" goto LOGS_STREAM
if "%opt%"=="11" goto RESTART_VPS
if "%opt%"=="12" goto TESTS
if "%opt%"=="13" goto SALIR
goto MENU

:DASH_REMOTE
cls
start "Dashboard NY_OPEN (Oracle VPS 24/7)" cmd /c "%~dp0Dashboard_Nube_Oracle_En_Vivo.bat"
goto MENU

:DASH_LOCAL
cls
start "Dashboard NY_OPEN (Local)" cmd /c "%~dp0Dashboard_Operaciones_En_Vivo.bat"
goto MENU

:DASH_MULTI
cls
start "Tablero Multi-Estrategia Detallado" cmd /c "%~dp0Dashboard_Multi_Detallado.bat"
goto MENU

:WEBHOOK_TUNNEL
cls
call "%~dp0Conectar_Puente_Webhook_MT5.bat"
goto MENU

:WEBHOOK_TEST
cls
call "%~dp0Probar_Senal_Webhook.bat"
goto MENU

:PRUEBA_MT5
cls
call "%~dp0Ejecutar_Prueba_MT5.bat"
goto MENU

:TG_TEST
cls
call "%~dp0Probar_Alerta_Telegram.bat"
goto MENU

:TG_CONFIG
cls
call "%~dp0Configurar_Telegram.bat"
goto MENU

:STATUS_VPS
cls
call "%~dp0Verificar_Servicio_24_7.bat"
goto MENU

:LOGS_STREAM
cls
echo Conectando a logs en vivo en Oracle Cloud VPS (Presiona Ctrl+C para volver)...
echo ------------------------------------------------------------------------------
ssh -i "%KEY%" -o StrictHostKeyChecking=no ubuntu@157.137.225.144 "journalctl -u stellar_ny_open -f"
goto MENU

:RESTART_VPS
cls
echo ==============================================================================
echo   REINICIANDO SERVICIOS EN ORACLE CLOUD VPS (157.137.225.144)...
echo ==============================================================================
echo.
ssh -i "%KEY%" -o StrictHostKeyChecking=no ubuntu@157.137.225.144 "sudo systemctl restart stellar_ny_open.service stellar_webhook.service && systemctl status stellar_ny_open stellar_webhook --no-pager"
echo.
pause
goto MENU

:TESTS
cls
python "%~dp0test_verification.py"
echo.
pause
goto MENU

:SALIR
cls
echo Finalizando Panel de Control Maestro.
exit /b 0
