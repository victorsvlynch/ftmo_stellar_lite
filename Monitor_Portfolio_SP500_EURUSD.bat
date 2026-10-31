@echo off
cd /d "%~dp0"
title Monitor Portafolio Institucional S&P 500 y EUR/USD - FundedNext / FTMO
mode con: cols=125 lines=32
cls
echo ==============================================================================
echo   INICIANDO MONITOR EN VIVO: PORTAFOLIO S^&P 500 + EUR/USD
echo   Estrategia: ORB 15M (EUR/USD LDN/NY + S^&P 500 Cash Open 09:30 EST)
echo   Riesgo Institucional: 0.50%% por trade ($25 USD) ^| R:R 1:2
echo ==============================================================================
echo.
python main.py live --symbol ES=F,EURUSD=X --provider yfinance --session PORTFOLIO_DUAL --db trading_portfolio_sp_eu.db --refresh 1
pause
