@echo off
title Centro de Control Multi-Servicios - FTMO Stellar Lite (5 Estrategias)
set "KEY=%USERPROFILE%\.ssh\ssh-key-2026-10-26.key"
if not exist "%KEY%" set "KEY=%USERPROFILE%\.ssh\oracle_vps.key"
if not exist "%KEY%" set "KEY=%~dp0ssh-key-2026-10-26.key"
if not exist "%KEY%" set "KEY=%~dp0ssh-key-2026-10-22-vps-oracle.key"

:MENU
cls
echo ==============================================================================
echo     CENTRO DE CONTROL Y GESTION MULTI-MODALIDAD (ORACLE VPS - 5 ESTRATEGIAS)
echo ==============================================================================
echo  1. Ver Estado de Servicios y Resumen de Cuentas (Status Consolidado)
echo  2. Iniciar Todos los Servicios de Trading (Start All 5 Services)
echo  3. Detener Todos los Servicios de Trading (Stop All 5 Services)
echo  4. Reiniciar Todos los Servicios de Trading (Restart All 5 Services)
echo  5. Abrir Tablero en Vivo Consolidado (Live Multi-Dashboard Compacto)
echo  6. Abrir Tablero en Vivo DETALLADO (Live con Operaciones Abiertas y Cerradas)
echo  7. Ver Logs en Vivo de Todas las Estrategias (Combined Logs)
echo  8. Ver Logs Individuales por Estrategia (Submenu 1 a 5)
echo  9. Reiniciar las 5 Cuentas a $5,000.00 Limpios (Reset All DBs)
echo 10. Salir
echo ==============================================================================
set /p opt="Seleccione una opcion [1-10]: "

if "%opt%"=="1" goto STATUS
if "%opt%"=="2" goto START
if "%opt%"=="3" goto STOP
if "%opt%"=="4" goto RESTART
if "%opt%"=="5" goto LIVE
if "%opt%"=="6" goto LIVE_DETAIL
if "%opt%"=="7" goto LOGS_ALL
if "%opt%"=="8" goto SUBMENU_LOGS
if "%opt%"=="9" goto RESET
if "%opt%"=="10" goto EOF
goto MENU

:STATUS
cls
echo Consultando estado en el VPS de las 5 modalidades...
ssh -tt -i "%KEY%" -o StrictHostKeyChecking=no ubuntu@157.137.225.144 "bash /home/ubuntu/FTMO_Stellar_Lite/manage_services.sh status"
pause
goto MENU

:START
cls
echo Iniciando los 5 servicios en el VPS...
ssh -i "%KEY%" -o StrictHostKeyChecking=no ubuntu@157.137.225.144 "bash /home/ubuntu/FTMO_Stellar_Lite/manage_services.sh start-all"
pause
goto MENU

:STOP
cls
echo Deteniendo los 5 servicios en el VPS...
ssh -i "%KEY%" -o StrictHostKeyChecking=no ubuntu@157.137.225.144 "bash /home/ubuntu/FTMO_Stellar_Lite/manage_services.sh stop-all"
pause
goto MENU

:RESTART
cls
echo Reiniciando los 5 servicios en el VPS...
ssh -i "%KEY%" -o StrictHostKeyChecking=no ubuntu@157.137.225.144 "bash /home/ubuntu/FTMO_Stellar_Lite/manage_services.sh restart-all"
pause
goto MENU

:LIVE
call "%~dp0Monitor_Consolidado_Todas.bat"
goto MENU

:LIVE_DETAIL
call "%~dp0Monitor_Detallado_Operaciones.bat"
goto MENU

:LOGS_ALL
call "%~dp0Logs_En_Vivo.bat"
goto MENU

:SUBMENU_LOGS
cls
echo ==============================================================================
echo                 VISOR DE LOGS INDIVIDUALES POR ESTRATEGIA
echo ==============================================================================
echo  1. Logs Modalidad 1: NY_OPEN (stellar_ny_open.service)
echo  2. Logs Modalidad 2: LONDON_OPEN (stellar_london_open.service)
echo  3. Logs Modalidad 3: CRYPTO_24H (stellar_crypto_24h.service)
echo  4. Logs Modalidad 4: COMBO_DUAL (stellar_ny_london.service)
echo  5. Logs Modalidad 5: COMBO_TRIO (stellar_combo_trio.service)
echo  6. Volver al menu principal
echo ==============================================================================
set /p log_opt="Seleccione la modalidad a inspeccionar [1-6]: "

if "%log_opt%"=="1" call "%~dp0Logs_1_NY_Open.bat"
if "%log_opt%"=="2" call "%~dp0Logs_2_London_Open.bat"
if "%log_opt%"=="3" call "%~dp0Logs_3_Crypto_24H.bat"
if "%log_opt%"=="4" call "%~dp0Logs_4_Combo_Dual.bat"
if "%log_opt%"=="5" call "%~dp0Logs_5_Combo_Trio.bat"
if "%log_opt%"=="6" goto MENU
goto SUBMENU_LOGS

:RESET
cls
echo ==============================================================================
echo ADVERTENCIA: Esta accion reiniciara los balances de las 5 modalidades a $5,000.
echo ==============================================================================
set /p confirm="Esta seguro de reiniciar las 5 cuentas? (S/N): "
if /i "%confirm%"=="S" (
    ssh -i "%KEY%" -o StrictHostKeyChecking=no ubuntu@157.137.225.144 "bash /home/ubuntu/FTMO_Stellar_Lite/manage_services.sh reset-all"
)
pause
goto MENU

:EOF
exit /b 0
