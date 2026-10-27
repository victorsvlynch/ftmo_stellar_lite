@echo off
cd /d "%~dp0"
title Probar Alerta de Senal Telegram - FundedNext Stellar Lite
chcp 65001 >nul
cls

echo ==============================================================================
echo   ENVIAR ALERTA DE PRUEBA NY_OPEN A TELEGRAM (@victorsvlynch)
echo   Modelo: FundedNext Stellar Lite ($5,000) -- Oro (XAUUSD)
echo ==============================================================================
echo.

python "%~dp0test_telegram_signal.py"

echo.
pause
