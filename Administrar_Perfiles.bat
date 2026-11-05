@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"
title Administrador Institucional de Perfiles - FTMO 10K & Stellar 10K
chcp 65001 >nul

:MENU_PERFILES
cls

:: Detección de procesos MT5 en vivo
set "MT1_STAT=[OFFLINE]"
set "MT2_STAT=[OFFLINE]"

tasklist /FI "IMAGENAME eq terminal64.exe" /FO CSV 2>nul | findstr /I "terminal64" >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    powershell -NoProfile -Command "if (Get-Process terminal64 -ErrorAction SilentlyContinue | Where-Object { $_.Path -like '*MetaTrader 5\*' }) { exit 0 } else { exit 1 }" >nul 2>&1
    if !ERRORLEVEL! EQU 0 set "MT1_STAT=[ONLINE]"
    
    powershell -NoProfile -Command "if (Get-Process terminal64 -ErrorAction SilentlyContinue | Where-Object { $_.Path -like '*MetaTrader 5 - 2\*' }) { exit 0 } else { exit 1 }" >nul 2>&1
    if !ERRORLEVEL! EQU 0 set "MT2_STAT=[ONLINE]"
)

:: Obtener información del modo y perfil activo
set "ACT_ID=ftmo_10k_challenge"
set "ACT_NAME=FTMO 10K Challenge"
set "ACT_MAGIC=505001"
set "ACT_SYMS=Oro, EURUSD, US500"
set "ACT_LOGIN=---"
set "ACT_MODE=DUAL"

for /f "usebackq tokens=1,2,3,4,5,6 delims=|" %%A in (`python -c "from profiles import profile_manager; p = profile_manager.get_active_profile(); syms = ', '.join(p.allowed_symbols); log = str(p.login_id) if p.login_id else '---'; mode = profile_manager.get_execution_mode(); print(f'{p.id}|{p.name}|{p.magic_number}|{syms}|{log}|{mode}')" 2^>nul`) do (
    set "ACT_ID=%%A"
    set "ACT_NAME=%%B"
    set "ACT_MAGIC=%%C"
    set "ACT_SYMS=%%D"
    set "ACT_LOGIN=%%E"
    set "ACT_MODE=%%F"
)

echo ==================================================================================================
echo                  ADMINISTRADOR INSTITUCIONAL DE PERFILES -- PROP TRADING MULTI-CUENTA
echo               MetaTrader 1 (FTMO 10K Challenge)  ^&  MetaTrader 2 (FundedNext 10K)
echo ==================================================================================================
echo   🖥️  MT1 FTMO 10K Challenge   !MT1_STAT! ^| Magic: 505001 ^| Activos: Oro, EUR/USD, S^&P 500 (US500)
echo   💻  MT2 Stellar 10K Demo     !MT2_STAT! ^| Magic: 505002 ^| Activos: Oro, EUR/USD, USD/JPY (USDJPY)
echo --------------------------------------------------------------------------------------------------
if "!ACT_MODE!"=="DUAL" (
    echo   * MODO DE EJECUCION : [DUAL / VARIOS SIMULTANEOS] (MT1 FTMO + MT2 Stellar operando en paralelo)
    echo   * ENRUTAMIENTO ORDENES: Oro y EUR/USD se envian a AMBAS terminales ^| Activos exclusivos a su MT5
) else (
    echo   * MODO DE EJECUCION : [INDIVIDUAL EXCLUSIVO] (Operando unicamente con: !ACT_NAME!)
    echo   * ENRUTAMIENTO ORDENES: Todas las operaciones van exclusivamente a !ACT_NAME! (Magic !ACT_MAGIC!)
)
echo   * PERFIL PYTHON ACTIVO : !ACT_NAME! (!ACT_ID!) ^| Magic: !ACT_MAGIC! ^| Login MT5: #!ACT_LOGIN!
echo ==================================================================================================
echo.
python "%~dp0main.py" --list-profiles
echo.
echo   +-- [1] SELECCION DE MODO DE OPERACION (VARIOS vs INDIVIDUAL) -----------------------------------+
echo   ^|  1. Activar MODO DUAL / VARIOS (MT1 FTMO 10K + MT2 Stellar 10K simultaneos en paralelo)       ^|
echo   ^|  2. Activar MODO INDIVIDUAL: Solo FTMO 10K Challenge (MT1 - $10,000 USD ^| Magic 505001)       ^|
echo   ^|  3. Activar MODO INDIVIDUAL: Solo Stellar 10K Demo (MT2 - $10,000 USD ^| Magic 505002)         ^|
echo   ^|  4. Activar MODO INDIVIDUAL: Solo Stellar 6K Trial (Free Trial $6,000 USD ^| Magic 505003)    ^|
echo   +-- [2] INSPECCION, AUDITORIA Y CONFIGURACION --------------------------------------------------+
echo   ^|  5. Ver Tablero Comparativo DUAL Completo (FTMO 10K vs Stellar 10K)                           ^|
echo   ^|  6. Ver Ficha Tecnica Completa del Perfil Activo                                             ^|
echo   ^|  7. Configurar Numero de Cuenta / Login MT5 para el Perfil Activo                            ^|
echo   ^|  8. Sincronizar Balance y Equidad en Vivo con MetaTrader 5 (Sync SQLite)                      ^|
echo   ^|  9. Reiniciar Cuenta del Perfil Activo (Reset preservando trades en 'archived')              ^|
echo   ^| 10. Lanzar Monitores DUALES en Vivo (Dashboards Paralelos FTMO + FundedNext)                  ^|
echo   ^|  0. Volver / Salir                                                                            ^|
echo   +-----------------------------------------------------------------------------------------------+
echo.
set "popt=1"
set /p popt=" Seleccione una opcion [0-10] (Por defecto 1): "

if "%popt%"=="1" goto SET_DUAL
if "%popt%"=="2" goto SET_FTMO_10K
if "%popt%"=="3" goto SET_10K
if "%popt%"=="4" goto SET_6K
if "%popt%"=="5" goto SHOW_DUAL_TABLE
if "%popt%"=="6" goto SHOW_CARD
if "%popt%"=="7" goto SET_LOGIN
if "%popt%"=="8" goto SYNC_MT5
if "%popt%"=="9" goto RESET_PROFILE
if "%popt%"=="10" goto LAUNCH_DUAL_MONITOR
if "%popt%"=="0" goto SALIR
goto MENU_PERFILES

:SET_DUAL
cls
python "%~dp0main.py" --set-dual
echo.
echo Presione cualquier tecla para continuar...
pause >nul
goto MENU_PERFILES

:SET_FTMO_10K
cls
python "%~dp0main.py" --set-individual ftmo_10k_challenge
echo.
echo Presione cualquier tecla para continuar...
pause >nul
goto MENU_PERFILES

:SET_10K
cls
python "%~dp0main.py" --set-individual stellar_10k_demo
echo.
echo Presione cualquier tecla para continuar...
pause >nul
goto MENU_PERFILES

:SET_6K
cls
python "%~dp0main.py" --set-individual stellar_6k_trial
echo.
echo Presione cualquier tecla para continuar...
pause >nul
goto MENU_PERFILES

:SHOW_DUAL_TABLE
cls
echo ==================================================================================================
echo                  TABLERO COMPARATIVO DUAL: FTMO 10K CHALLENGE vs STELLAR 10K DEMO
echo ==================================================================================================
echo.
python -c "
from profiles import profile_manager
p_ftmo = profile_manager.get_profile('ftmo_10k_challenge')
p_st = profile_manager.get_profile('stellar_10k_demo')
sep = '=' * 98
sub = '-' * 98
print(sep)
print(f' {\"PARAMETRO INSTITUCIONAL\":<30} | {\"METATRADER 1 (FTMO 10K)\":<30} | {\"METATRADER 2 (STELLAR 10K)\":<30}')
print(sub)
print(f' {\"Modelo de Evaluacion\":<30} | {p_ftmo.account_type:<30} | {p_st.account_type:<30}')
print(f' {\"Capital Base\":<30} | {f\"${p_ftmo.initial_balance:,.0f} USD\":<30} | {f\"${p_st.initial_balance:,.0f} USD\":<30}')
print(f' {\"Instancia MT5 en PC\":<30} | {\"Terminal 1 (MetaTrader 5)\":<30} | {\"Terminal 2 (MetaTrader 5 - 2)\":<30}')
print(f' {\"Magic Number EA\":<30} | {str(p_ftmo.magic_number):<30} | {str(p_st.magic_number):<30}')
print(f' {\"Portafolio de Activos\":<30} | {\"Oro, EUR/USD, S&P 500 (US500)\":<30} | {\"Oro, EUR/USD, USD/JPY (USDJPY)\":<30}')
print(f' {\"Base de Datos SQLite\":<30} | {p_ftmo.db_file:<30} | {p_st.db_file:<30}')
print(f' {\"Target Fase 1 / Fase 2\":<30} | {f\"+{p_ftmo.profit_target_pct*100:.0f}% / +{p_ftmo.profit_target_phase2_pct*100:.0f}%\":<30} | {f\"+{p_st.profit_target_pct*100:.0f}% / +{p_st.profit_target_phase2_pct*100:.0f}%\":<30}')
print(f' {\"Meta Fase 1 / Fase 2 (USD)\":<30} | {f\"$1,000 / $500 USD\":<30} | {f\"$800 / $400 USD\":<30}')
print(f' {\"Perdida Diaria Maxima\":<30} | {f\"-{p_ftmo.daily_loss_limit_pct*100:.0f}% (${p_ftmo.daily_loss_amount:,.0f})\":<30} | {f\"-{p_st.daily_loss_limit_pct*100:.0f}% (${p_st.daily_loss_amount:,.0f})\":<30}')
print(f' {\"Drawdown Total Maximo\":<30} | {f\"-{p_ftmo.max_drawdown_limit_pct*100:.0f}% (Piso ${p_ftmo.max_loss_floor:,.0f})\":<30} | {f\"-{p_st.max_drawdown_limit_pct*100:.0f}% (Piso ${p_st.max_loss_floor:,.0f})\":<30}')
print(f' {\"Regla Max Open Risk\":<30} | {\"3.0% ($300 USD) max.\":<30} | {\"3.0% ($300 USD) max.\":<30}')
print(f' {\"Freno Personal Diario\":<30} | {f\"-{p_ftmo.personal_daily_cap_pct*100:.1f}% (${p_ftmo.personal_daily_cap_amount:,.0f})\":<30} | {f\"-{p_st.personal_daily_cap_pct*100:.1f}% (${p_st.personal_daily_cap_amount:,.0f})\":<30}')
print(f' {\"Dias Minimos Operativos\":<30} | {f\"{p_ftmo.min_trading_days} Dias por Fase\":<30} | {f\"{p_st.min_trading_days} Dias por Fase\":<30}')
print(f' {\"EA InpEnableSP500\":<30} | {\"true (ACTIVO)\":<30} | {\"false (INACTIVO)\":<30}')
print(f' {\"EA InpEnableUSDJPY\":<30} | {\"false (INACTIVO)\":<30} | {\"true (ACTIVO)\":<30}')
print(sep)
"
echo.
echo Presione cualquier tecla para continuar...
pause >nul
goto MENU_PERFILES

:SHOW_CARD
cls
python "%~dp0main.py" --show-profile
echo.
echo Presione cualquier tecla para continuar...
pause >nul
goto MENU_PERFILES

:SET_LOGIN
cls
echo ==============================================================================
echo   CONFIGURAR NUMERO DE LOGIN DE METATRADER 5 PARA: %ACT_NAME%
echo ==============================================================================
echo.
echo  Perfil Seleccionado : %ACT_NAME% (%ACT_ID%)
echo  Login Actual        : #%ACT_LOGIN%
echo.
set "login_num="
set /p login_num=" Ingrese el nuevo numero de Login MT5 (ej. 1515193448): "
if defined login_num (
    python "%~dp0main.py" --profile %ACT_ID% --set-login !login_num!
) else (
    echo [INFO] No se ingreso ningun numero. Operacion cancelada.
)
echo.
echo Presione cualquier tecla para continuar...
pause >nul
goto MENU_PERFILES

:SYNC_MT5
cls
echo ==============================================================================
echo   SINCRONIZAR BALANCE Y EQUIDAD CON METATRADER 5 EN VIVO
echo ==============================================================================
echo.
echo Sincronizando perfil activo (%ACT_NAME%)...
python "%~dp0main.py" --profile %ACT_ID% sync-mt5
echo.
echo Presione cualquier tecla para continuar...
pause >nul
goto MENU_PERFILES

:RESET_PROFILE
cls
echo ==============================================================================
echo   REINICIAR CUENTA: %ACT_NAME%
echo   (El historial actual se archiva intacto en la tabla 'archived_trades')
echo ==============================================================================
echo.
echo ADVERTENCIA: Esta accion restablecera el balance a $10,000 USD y la fase a FASE_1.
set "confirm="
set /p confirm=" Confirma reiniciar la cuenta del perfil activo? [S/N]: "
if /I "!confirm!"=="s" (
    python "%~dp0main.py" --profile %ACT_ID% reset
) else (
    echo [INFO] Operacion de reinicio cancelada.
)
echo.
echo Presione cualquier tecla para continuar...
pause >nul
goto MENU_PERFILES

:LAUNCH_DUAL_MONITOR
cls
echo ==============================================================================
echo   LANZANDO MONITORES DUALES EN TIEMPO REAL
echo ==============================================================================
echo.
echo   [1/2] Abriendo monitor para MT1 (FTMO 10K Challenge)...
start "MT1: FTMO 10K Challenge [Oro, EURUSD, US500]" cmd /k "chcp 65001 >nul && python %~dp0main.py --profile ftmo_10k_challenge live"

echo   [2/2] Abriendo monitor para MT2 (FundedNext Stellar 10K)...
start "MT2: FundedNext Stellar 10K [Oro, EURUSD, USDJPY]" cmd /k "chcp 65001 >nul && python %~dp0main.py --profile stellar_10k_demo live"

echo.
echo [EXITO] Ambas ventanas de monitoreo han sido desplegadas en paralelo.
echo.
echo Presione cualquier tecla para volver al menu...
pause >nul
goto MENU_PERFILES

:SALIR
exit /b 0
