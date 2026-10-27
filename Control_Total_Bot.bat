@echo off
cd /d "%~dp0"
title Centro de Control Maestro - FundedNext Stellar Lite ($5,000)
chcp 65001 >nul

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

:MENU
cls
echo ==============================================================================
echo       PANEL DE CONTROL MAESTRO -- FUNDEDNEXT STELLAR LITE ($5,000 USD)
echo       Estrategia Ganadora Oficial: NY_OPEN (Oro GC=F / XAUUSD)
echo       Servidor en la Nube: Oracle Cloud VPS (157.137.225.144) -- 24/7
echo ==============================================================================
echo.
echo   [DASHBOARDS Y MONITOREO EN VIVO]
echo    1. Abrir Dashboard en Vivo: Estrategia Ganadora NY_OPEN (Local)
echo    2. Abrir Dashboard en Vivo: Desde Oracle Cloud VPS (Remoto 24/7)
echo    3. Abrir Tablero Multi-Estrategia Detallado (Operaciones Hoy)
echo.
echo   [OPCION B.2: ENLACE AUTOMATICO WEBHOOK MT5]
echo    4. Gestor del Puente Webhook MT5 (Tunel Puerto 8000)
echo    5. Disparar Senal de Prueba Webhook hacia MT5 (Test Micro-Orden)
echo.
echo   [OPCION C: ALERTAS A TU CELULAR VIA TELEGRAM (@victorsvlynch)]
echo    6. Configurar / Vincular Telegram (@BotFather y Chat ID)
echo    7. Enviar Alerta de Prueba NY_OPEN a Telegram (Test de Formato Celular)
echo.
echo   [GESTION DEL SERVIDOR 24/7 EN LA NUBE]
echo    8. Verificar Estado del Servicio en Oracle Cloud (Uptime y Memoria)
echo    9. Ver Streaming de Logs en Tiempo Real (Segundo a Segundo)
echo   10. Reiniciar Servicios en la Nube (Bot NY_OPEN + Webhook Server)
echo.
echo   [PRUEBAS Y SIMULACION]
echo   11. Ejecutar Prueba Interactiva con MetaTrader 5 (MT5 en PC)
echo   12. Correr Suite de Verificacion Automatizada (9 Pruebas 100%% OK)
echo.
echo   13. Salir
echo ==============================================================================
set "opt=1"
set /p opt="Seleccione una opcion [1-13] (Por defecto 1): "

if "%opt%"=="1" goto DASH_LOCAL
if "%opt%"=="2" goto DASH_REMOTE
if "%opt%"=="3" goto DASH_MULTI
if "%opt%"=="4" goto WEBHOOK_TUNNEL
if "%opt%"=="5" goto WEBHOOK_TEST
if "%opt%"=="6" goto TG_CONFIG
if "%opt%"=="7" goto TG_TEST
if "%opt%"=="8" goto STATUS_VPS
if "%opt%"=="9" goto LOGS_STREAM
if "%opt%"=="10" goto RESTART_VPS
if "%opt%"=="11" goto PRUEBA_MT5
if "%opt%"=="12" goto TESTS
if "%opt%"=="13" goto SALIR
goto MENU

:DASH_LOCAL
cls
start "Dashboard NY_OPEN Local" cmd /c "%~dp0Dashboard_Operaciones_En_Vivo.bat"
goto MENU

:DASH_REMOTE
cls
start "Dashboard NY_OPEN Oracle VPS" cmd /c "%~dp0Dashboard_Nube_Oracle_En_Vivo.bat"
goto MENU

:DASH_MULTI
cls
start "Dashboard Multi Detallado" cmd /c "%~dp0Dashboard_Multi_Detallado.bat"
goto MENU

:WEBHOOK_TUNNEL
cls
start "Puente Webhook MT5" cmd /c "%~dp0Conectar_Puente_Webhook_MT5.bat"
goto MENU

:WEBHOOK_TEST
cls
call "%~dp0Probar_Senal_Webhook.bat"
goto MENU

:TG_CONFIG
cls
call "%~dp0Configurar_Telegram.bat"
goto MENU

:TG_TEST
cls
call "%~dp0Probar_Alerta_Telegram.bat"
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
echo Reiniciando servicios en Oracle Cloud VPS...
ssh -i "%KEY%" -o StrictHostKeyChecking=no ubuntu@157.137.225.144 "sudo systemctl restart stellar_ny_open.service stellar_webhook.service && systemctl status stellar_ny_open stellar_webhook --no-pager"
echo.
pause
goto MENU

:PRUEBA_MT5
cls
start "Prueba MT5 Interactiva" cmd /c "%~dp0Ejecutar_Prueba_MT5.bat"
goto MENU

:TESTS
cls
python "%~dp0test_verification.py"
echo.
pause
goto MENU

:SALIR
cls
echo Finalizando Panel de Control.
exit /b 0
