@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"
title Detalle de Operaciones MT5 y Nube - FundedNext Stellar Lite
chcp 65001 >nul
cls

echo ==============================================================================
echo   CONSULTA DE DETALLE DE OPERACIONES (PORTFOLIO MT5 OFICIAL)
echo   MetaTrader 5 + Servidor Oracle Cloud VPS (trading_ny_open.db)
echo ==============================================================================
echo.

python "%~dp0consultar_detalle_operaciones.py"

echo.
pause
