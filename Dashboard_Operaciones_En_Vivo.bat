@echo off
cd /d "%~dp0"
title Dashboard en Vivo - Estrategia Ganadora NY_OPEN (Oro GC=F / XAUUSD)
chcp 65001 >nul
cls

echo ==============================================================================
echo   INICIANDO DASHBOARD EN VIVO: ESTRATEGIA GANADORA NY_OPEN (ORO / XAUUSD)
echo   FundedNext Stellar Lite ($5,000) -- Modelo Alta Velocidad In-Place
echo ==============================================================================
echo.
python "%~dp0main.py" winner-live --refresh 1.0
echo.
pause
