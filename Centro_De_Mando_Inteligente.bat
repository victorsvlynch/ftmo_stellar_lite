@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"
title Centro de Mando Inteligente - Escudo Anti-Fakeouts 48H
chcp 65001 >nul
cls

:MENU
cls
python dashboard_centro_mando.py

echo ======================================================================================
echo   ACCIONES RAPIDAS DEL CENTRO DE MANDO:
echo ======================================================================================
echo   [1] Actualizar Diagnostico de Mercado ahora mismo
echo   [2] Iniciar Bot en Modo Seguro (Respeta Cuarentenas 48H y Freno Anti-Tilt)
echo   [3] Ver Detalle Historico de Operaciones en MT5
echo   [4] Liberar Cuarentena de 48H manualmente (Forzar desbloqueo)
echo   [5] Salir
echo ======================================================================================
set /p opt="Seleccione una opcion (1-5): "

if "%opt%"=="1" (
    echo Actualizando diagnostico...
    goto MENU
)

if "%opt%"=="2" (
    echo.
    echo Iniciando Dashboard en Vivo de Trading Seguro...
    start "Dashboard en Vivo" cmd /k "python main.py live --refresh 1.0"
    echo Dashboard abierto en ventana independiente.
    pause
    goto MENU
)

if "%opt%"=="3" (
    echo.
    python consultar_detalle_operaciones.py
    echo.
    pause
    goto MENU
)

if "%opt%"=="4" (
    echo.
    echo ATENCION: Desbloquearas todos los activos en cuarentena...
    set /p conf="Confirmar desbloqueo manual? (S/N): "
    if /i "!conf!"=="S" (
        python -c "import json, os; p='quarantine_status.json'; os.path.exists(p) and os.remove(p); print('Cuarentenas restablecidas.')"
        python market_regime_sentinel.py >nul
        echo Listo. Cuarentenas liberadas.
    ) else (
        echo Operacion cancelada.
    )
    pause
    goto MENU
)

if "%opt%"=="5" (
    exit /b 0
)

goto MENU