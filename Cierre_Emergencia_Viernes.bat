@echo off
chcp 65001 >nul
title Guardian de Viernes - Cierre Institucional Anti-Gap
echo ===============================================================================
echo     GUARDIÁN DE VIERNES: CONTROL DE CIERRE INSTITUCIONAL ANTI-GAP
echo ===============================================================================
echo.
echo  1. Consultar estado actual (Ventana 15:30 EST y Posiciones abiertas)
echo  2. Forzar CIERRE INMEDIATO de todas las posiciones abiertas en MT5
echo  3. Iniciar Guardián en bucle continuo de monitoreo
echo  4. Salir
echo.
set /p opcion="Seleccione una opción (1-4): "

if "%opcion%"=="1" (
    echo.
    python friday_guardian.py --check
    echo.
    pause
    goto :eof
)

if "%opcion%"=="2" (
    echo.
    echo ATENCIÓN: Se cerrarán todas las posiciones abiertas en tus terminales MT5...
    set /p seguro="¿Confirmar cierre inmediato? (S/N): "
    if /i "%seguro%"=="S" (
        python friday_guardian.py --force
    ) else (
        echo Cancelado.
    )
    echo.
    pause
    goto :eof
)

if "%opcion%"=="3" (
    echo.
    echo Iniciando Guardián continuo de Viernes en primer plano...
    python friday_guardian.py --daemon
    goto :eof
)

echo Salir.
