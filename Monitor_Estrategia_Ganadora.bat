@echo off
cd /d "%~dp0"
title Monitor Estrategia Ganadora NY_OPEN - FundedNext Stellar Lite
mode con: cols=125 lines=32
cls
set "KEY=%USERPROFILE%\.ssh\ssh-key-2026-10-26.key"
if not exist "%KEY%" set "KEY=%~dp0VPS-Oracle\ssh-key-2026-10-26.key"
echo [CONECTANDO] Monitor Estrategia Ganadora NY_OPEN (Oro GC=F)...
ssh -tt -i "%KEY%" -o StrictHostKeyChecking=no ubuntu@157.137.225.144 "cd /home/ubuntu/FTMO_Stellar_Lite && python3 -u main.py live --symbol GC=F --provider yfinance --session NY_OPEN --db trading_ny_open.db"
pause
