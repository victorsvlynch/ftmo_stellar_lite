@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"
title Administrador de Perfiles de Trading - FundedNext (10K Demo / 6K Trial)
chcp 65001 >nul

:MENU_PERFILES
cls
echo ==============================================================================
echo        ADMINISTRADOR OFICIAL DE PERFILES DE TRADING -- FUNDEDNEXT
echo        Gestion independiente de cuentas: Stellar 10K Demo y Stellar 6K Trial
echo ==============================================================================
python "%~dp0main.py" profile --list
echo.
echo   +-- SELECCIONE UNA ACCION -----------------------------------------------+
echo   ^|  1. Activar Perfil: Stellar 10K Demo (Evaluacion 2-Step $10,000 USD)   ^|
echo   ^|  2. Activar Perfil: Stellar 6K Trial (Free Trial Challenge $6,000 USD) ^|
echo   ^|  3. Ver Ficha Tecnica Completa del Perfil Activo                       ^|
echo   ^|  4. Configurar Numero de Cuenta / Login MT5                            ^|
echo   ^|  5. Reiniciar Estado de la Cuenta del Perfil Activo (Reset)            ^|
echo   ^|  6. Volver al Menu Principal                                           ^|
echo   +------------------------------------------------------------------------+
echo.
set "popt=3"
set /p popt=" Seleccione una opcion [1-6] (Por defecto 3): "

if "%popt%"=="1" goto SET_10K
if "%popt%"=="2" goto SET_6K
if "%popt%"=="3" goto SHOW_CARD
if "%popt%"=="4" goto SET_LOGIN
if "%popt%"=="5" goto RESET_PROFILE
if "%popt%"=="6" goto SALIR
goto MENU_PERFILES

:SET_10K
cls
python "%~dp0main.py" --switch-profile stellar_10k_demo
echo.
pause
goto MENU_PERFILES

:SET_6K
cls
python "%~dp0main.py" --switch-profile stellar_6k_trial
echo.
pause
goto MENU_PERFILES

:SHOW_CARD
cls
python "%~dp0main.py" --show-profile
echo.
pause
goto MENU_PERFILES

:SET_LOGIN
cls
echo ==============================================================================
echo   CONFIGURAR NUMERO DE LOGIN DE METATRADER 5 (MT5)
echo ==============================================================================
echo.
set "login_num="
set /p login_num=" Ingrese el numero de Login MT5 (ej. 35338849): "
if defined login_num (
    python "%~dp0main.py" --set-login !login_num!
) else (
    echo [INFO] No se ingreso ningun numero. Operacion cancelada.
)
echo.
pause
goto MENU_PERFILES

:RESET_PROFILE
cls
echo ==============================================================================
echo   REINICIAR CUENTA DEL PERFIL ACTIVO (PRESERVANDO HISTORIAL EN ARCHIVED)
echo ==============================================================================
echo.
set "confirm="
set /p confirm=" Confirma reiniciar la cuenta del perfil activo? [S/N]: "
if /I "!confirm!"=="s" (
    python "%~dp0main.py" reset
) else (
    echo [INFO] Operacion de reinicio cancelada.
)
echo.
pause
goto MENU_PERFILES

:SALIR
exit /b 0
