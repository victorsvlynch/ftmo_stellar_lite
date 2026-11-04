@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"
title MODO CONTINGENCIA 100%% LOCAL (SIN VPS) - FundedNext Stellar Lite
chcp 65001 >nul

echo ==============================================================================
echo   MODO DE CONTINGENCIA 100%% LOCAL (AUTONOMO EN ESTA PC SIN ORACLE VPS)
echo   Portafolio Activo: XAUUSD (Oro) + EURUSD + USDJPY ^| S^&P 500 y AUDUSD en Standby
echo ==============================================================================
echo.
echo  [1/3] Cerrando cualquier tunel SSH colgado en el puerto 8000...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000" ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
)

echo  [2/3] Iniciando Servidor Webhook Local en http://127.0.0.1:8000 ...
start "Servidor Webhook Local (Puerto 8000)" cmd /k "cd /d "%~dp0" && python webhook_server.py 8000"
timeout /t 2 /nobreak >nul

echo  [3/3] Iniciando Motor Cuantitativo Local (GC=F,EURUSD=X,USDJPY=X) ...
echo        MetaTrader 5 se conectara automaticamente a 127.0.0.1:8000 sin cambios.
echo ==============================================================================
python main.py run --symbol GC=F,EURUSD=X,USDJPY=X --provider mt5 --risk 0.005 --personal-cap 0.02 --session PORTFOLIO_DUAL --db trading_ny_open.db --interval 60
pause
