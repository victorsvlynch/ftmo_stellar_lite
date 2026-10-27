@echo off
cd /d "%~dp0"
title Tablero Multi-Estrategia Detallado en Vivo - FundedNext Stellar Lite
chcp 65001 >nul
cls

echo ==============================================================================
echo   TABLERO MULTI-ESTRATEGIA DETALLADO (POSICIONES ABIERTAS Y CERRADAS)
echo   FundedNext Stellar Lite ($5,000) -- Portafolio Completo
echo ==============================================================================
echo.
python "%~dp0main.py" multi-detail --refresh 1.5
echo.
pause
