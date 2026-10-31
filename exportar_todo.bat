@echo off
chcp 65001 > nul
cd /d "%~dp0"
title Generar Pack de Portabilidad - FundedNext Stellar Lite ($10,000)

echo ==============================================================================
echo   EMPAQUETADOR DE PORTABILIDAD - FUNDEDNEXT STELLAR LITE ($10,000 USD)
echo ==============================================================================
echo Este script creará el paquete completo y el archivo ZIP portable:
echo   - Archivos de MetaTrader 5 (EA multi-activo, configuraciones, perfiles)
echo   - Llaves SSH privadas de Oracle Cloud VPS
echo   - Código fuente de Python, bases de datos a $10,000 y lanzadores
echo   - Instalador automático de 1-Clic para la nueva PC
echo ==============================================================================
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0exportar_todo.ps1"

echo.
pause
