@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"
title Dashboard en Vivo - Motor Cuantitativo Multi-Perfil
chcp 65001 >nul
cls

set "ACT_NAME=Perfil Activo"
for /f "usebackq delims=" %%A in (`python -c "from profiles import profile_manager; p = profile_manager.get_active_profile(); print(f'{p.name} (${p.initial_balance:,.0f} USD)')" 2^>nul`) do set "ACT_NAME=%%A"

echo ==============================================================================
echo   INICIANDO DASHBOARD EN VIVO -- PERFIL ACTIVO: %ACT_NAME%
echo   Motor de Trading Cuantitativo en Tiempo Real (Alta Velocidad In-Place)
echo ==============================================================================
echo.
python "%~dp0main.py" live --refresh 1.0
echo.
pause
