@echo off
cd /d "%~dp0"
title Simulacion Realista MetaTrader 5 (MT5) - FundedNext Stellar Lite
mode con: cols=95 lines=40
cls
echo ==============================================================================
echo  Iniciando Prueba de Simulacion Realista con MetaTrader 5 (MT5)
echo ==============================================================================
python "%~dp0prueba_mt5_simulacion.py"
echo.
pause
