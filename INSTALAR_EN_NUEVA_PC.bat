@echo off
chcp 65001 > nul
setlocal EnableDelayedExpansion
cd /d "%~dp0"

title FUNDEDNEXT STELLAR LITE ($10,000) - INSTALADOR EN NUEVA PC

echo ==========================================================================
echo   FUNDEDNEXT STELLAR LITE ($10,000 USD) - INSTALADOR PORTABLE EN NUEVA PC
echo ==========================================================================
echo.
echo Este script configurará automáticamente en esta computadora:
echo   1. Las llaves SSH de Oracle Cloud VPS (en %%USERPROFILE%%\.ssh).
echo   2. El Expert Advisor y configuración WebRequest en MetaTrader 5.
echo   3. Las dependencias requeridas de Python.
echo   4. Prueba de conectividad con la nube.
echo.
pause

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Restaurar_Sistema_Nueva_PC.ps1"

echo.
echo Presione cualquier tecla para abrir el Centro de Control del Bot...
pause > nul

if exist "%~dp0Control_Total_Bot.bat" (
    start "" "%~dp0Control_Total_Bot.bat"
) else if exist "%~dp003_Codigo_Python_Proyecto\Control_Total_Bot.bat" (
    start "" "%~dp003_Codigo_Python_Proyecto\Control_Total_Bot.bat"
)
