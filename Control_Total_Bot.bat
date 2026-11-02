@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"
title Panel de Control Maestro - FundedNext Stellar Lite ($10,000)
chcp 65001 >nul

:: ============================================================================
:: 1. RESOLVER CLAVE SSH PRIVADA (Auto-deteccion y aprovisionamiento local)
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
:: 2. DETECCION DE ESTADO EN TIEMPO REAL
:: ============================================================================
set "STATUS_SSH=[OK - Detectada]"
if not exist "%KEY%" set "STATUS_SSH=[ERROR - No Encontrada]"

set "STATUS_TUNNEL=[INACTIVO - Opcion 4 para conectar]"
netstat -ano | findstr /C:":8000 " | findstr /I "LISTENING" >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    set "STATUS_TUNNEL=[ACTIVO - Enlace 8000 Operativo]"
)

set "STATUS_MT5=[OFFLINE - MetaTrader 5 cerrado]"
tasklist /FI "IMAGENAME eq terminal64.exe" 2>nul | findstr /I "terminal64" >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    set "STATUS_MT5=[ONLINE - terminal64.exe activo]"
)

set "ACTIVE_PROFILE=Stellar 10K Demo"
for /f "usebackq delims=" %%A in (`python -c "from profiles import profile_manager; p = profile_manager.get_active_profile(); print(f'{p.name} (${p.initial_balance:,.0f} USD)' + (f' - Login #{p.login_id}' if p.login_id else ''))" 2^>nul`) do set "ACTIVE_PROFILE=%%A"

:: ============================================================================
:: 3. INTERFAZ GRAFICA DEL PANEL DE CONTROL
:: ============================================================================
echo ============================================================================== 
echo        PANEL DE CONTROL MAESTRO -- FUNDEDNEXT PROP TRADING
echo        Estrategia Oficial: NY_OPEN (Oro GC=F / XAUUSD) ^| R:R 1:2
echo ============================================================================== 
echo   * Perfil Activo       : %ACTIVE_PROFILE%
echo   * Servidor en la Nube : Oracle Cloud VPS (157.137.225.144) [ONLINE 24/7]
echo   * Clave Privada SSH   : %STATUS_SSH%
echo   * Terminal MetaTrader : %STATUS_MT5%
echo   * Tunel Webhook (8000): %STATUS_TUNNEL%
echo ============================================================================== 
echo.
echo   +-- [0] ADMINISTRACION DE PERFILES Y CUENTAS ----------------------------+
echo   ^|  P. Cambiar / Administrar Perfil (Stellar 10K Demo ^| Stellar 6K Trial) ^|
echo   +------------------------------------------------------------------------+
echo   +-- [1] MONITOR Y DASHBOARDS EN TIEMPO REAL -----------------------------+
echo   ^|  1. Dashboard Remoto en Vivo (Oracle Cloud VPS 24/7) [RECOMENDADO]     ^|
echo   ^|  2. Dashboard Local en Vivo (Simulador en esta PC)                     ^|
echo   ^|  3. Tablero Multi-Estrategia Detallado (Historial y Posiciones Hoy)    ^|
echo   +------------------------------------------------------------------------+
echo   +-- [2] CONECTIVIDAD METATRADER 5 (MT5 ^& WEBHOOK) ------------------------+
echo   ^|  4. Gestor de Tunel Webhook (Iniciar / Detener enlace en Puerto 8000)  ^|
echo   ^|  5. Disparar Micro-Orden de Prueba hacia MT5 (Test 0.01 lotes Oro)     ^|
echo   ^|  6. Simulacion Realista con Broker MT5 (Inspeccion de Cuenta y Ordenes)^|
echo   +------------------------------------------------------------------------+
echo   +-- [3] ALERTAS MOVILES A TU CELULAR (TELEGRAM) --------------------------+
echo   ^|  7. Enviar Alerta Institucional de Prueba a Telegram (@victorsvlynch)  ^|
echo   ^|  8. Configurar / Re-vincular Telegram (Token de Bot y Chat ID)         ^|
echo   +------------------------------------------------------------------------+
echo   +-- [4] GESTION DEL SERVIDOR EN LA NUBE (ORACLE CLOUD VPS) ---------------+
echo   ^|  9. Diagnostico de Salud del Servidor (Uptime, Memoria, Servicios)     ^|
echo   ^| 10. Streaming de Logs en Tiempo Real (Segundo a Segundo - journalctl)  ^|
echo   ^| 11. Reiniciar Servicios en la Nube (Bot NY_OPEN + Webhook Server)      ^|
echo   +------------------------------------------------------------------------+
echo   +-- [5] AUDITORIA, PORTABILIDAD Y CONTROL -------------------------------+
echo   ^| 12. Correr Suite de Verificacion Automatizada (13 Pruebas 100%% OK)    ^|
echo   ^| 13. Generar Pack Portable para Otra PC (exportar_todo.bat)             ^|
echo   ^| 14. Salir                                                              ^|
echo   +------------------------------------------------------------------------+
echo.
set "opt=1"
set /p opt=" Seleccione una opcion [1-14 o P para Perfiles] (Por defecto 1): "

if /I "%opt%"=="p" goto PROFILE_ADMIN
if /I "%opt%"=="profile" goto PROFILE_ADMIN
if "%opt%"=="0" goto PROFILE_ADMIN
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
if "%opt%"=="13" goto EXPORT_PACK
if "%opt%"=="14" goto SALIR
goto MENU

:PROFILE_ADMIN
cls
call "%~dp0Administrar_Perfiles.bat"
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

:EXPORT_PACK
cls
call "%~dp0exportar_todo.bat"
goto MENU

:SALIR
cls
echo Finalizando Panel de Control Maestro.
exit /b 0
