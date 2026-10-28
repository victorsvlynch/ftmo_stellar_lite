@echo off
cd /d "%~dp0"
title Configurar Alertas Telegram (@victorsvlynch) - FundedNext Stellar Lite
chcp 65001 >nul
cls

echo ==============================================================================
echo   VINCULAR ALERTAS DE TELEGRAM A TU CELULAR (@victorsvlynch)
echo   Modelo: FundedNext Stellar Lite ($5,000) -- Estrategia: NY_OPEN (Oro)
echo ==============================================================================
echo.

python "%~dp0configurar_telegram.py"

echo.
echo Presione una tecla para salir...
pause >nul
