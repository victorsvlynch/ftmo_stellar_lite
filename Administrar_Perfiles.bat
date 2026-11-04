@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"
title Administrador de Perfiles de Trading - Multi-Firma (FundedNext / FTMO)
chcp 65001 >nul

:MENU_PERFILES
cls
echo ==============================================================================
echo        ADMINISTRADOR OFICIAL DE PERFILES DE TRADING -- MULTI-FIRMA
echo        Gestion independiente: Stellar 10K, Stellar 6K y FTMO 10K Challenge
echo ==============================================================================
python "%~dp0main.py" profile --list
echo.
echo   +-- SELECCIONE UNA ACCION -----------------------------------------------+
echo   ^|  1. Activar Perfil: Stellar 10K Demo (Evaluacion 2-Step $10,000 USD)   ^|
echo   ^|  2. Activar Perfil: Stellar 6K Trial (Free Trial Challenge $6,000 USD) ^|
echo   ^|  3. Activar Perfil: FTMO 10K Challenge (Evaluacion 2-Step $10,000 USD) ^|
echo   ^|  4. Ver Ficha Tecnica Completa del Perfil Activo                       ^|
echo   ^|  5. Configurar Numero de Cuenta / Login MT5                            ^|
echo   ^|  6. Reiniciar Estado de la Cuenta del Perfil Activo (Reset)            ^|
echo   ^|  7. Volver al Menu Principal                                           ^|
echo   +------------------------------------------------------------------------+
echo.
set "popt=4"
set /p popt=" Seleccione una opcion [1-7] (Por defecto 4): "

if "%popt%"=="1" goto SET_10K
if "%popt%"=="2" goto SET_6K
if "%popt%"=="3" goto SET_FTMO_10K
if "%popt%"=="4" goto SHOW_CARD
if "%popt%"=="5" goto SET_LOGIN
if "%popt%"=="6" goto RESET_PROFILE
if "%popt%"=="7" goto SALIR
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

:SET_FTMO_10K
cls
python "%~dp0main.py" --switch-profile ftmo_10k_challenge
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
