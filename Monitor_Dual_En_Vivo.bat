@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"
title Monitor DUAL en Vivo - FTMO 10K (MT1) & FundedNext Stellar 10K (MT2)
chcp 65001 >nul
cls

echo ==============================================================================
echo        MONITOR DUAL EN TIEMPO REAL -- ARQUITECTURA MULTI-CUENTA
echo ==============================================================================
echo.
echo   [1/2] Iniciando Monitor MT1: FTMO 10K Challenge (Oro, EUR/USD, S^&P 500)...
start "MT1: FTMO 10K Challenge (Magic 505001)" cmd /k "chcp 65001 >nul && python %~dp0main.py --profile ftmo_10k_challenge live"

echo   [2/2] Iniciando Monitor MT2: FundedNext Stellar 10K (Oro, EUR/USD, USD/JPY)...
start "MT2: FundedNext Stellar 10K (Magic 505002)" cmd /k "chcp 65001 >nul && python %~dp0main.py --profile stellar_10k_demo live"

echo.
echo ==============================================================================
echo   [OK] Ambas consolas han sido iniciadas en paralelo de forma independiente.
echo   Cada ventana refleja en vivo: Balance, Drawdown, Trades, PnL y Reglas.
echo ==============================================================================
echo.
pause
