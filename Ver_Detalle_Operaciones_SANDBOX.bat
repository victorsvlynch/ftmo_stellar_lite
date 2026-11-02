@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"
title Detalle de Operaciones Sandbox - FundedNext Stellar Lite
chcp 65001 >nul
cls

echo ==============================================================================
echo   CONSULTA DE DETALLE DE OPERACIONES SANDBOX (TEST SIN MT5)
echo   3 Cuentas Independientes de $10,000 c/u en Oracle Cloud VPS
echo ==============================================================================
echo.

python "%~dp0consultar_detalle_sandbox.py"

echo.
pause
