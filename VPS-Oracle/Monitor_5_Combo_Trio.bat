@echo off
title Monitor 5: COMBO_TRIO (London + NY + Crypto 24/7) - FTMO Stellar Lite
mode con: cols=85 lines=25
cls

set "KEY=%USERPROFILE%\.ssh\ssh-key-2026-10-26.key"
if not exist "%KEY%" set "KEY=%USERPROFILE%\.ssh\oracle_vps.key"
if not exist "%KEY%" set "KEY=%~dp0ssh-key-2026-10-26.key"
if not exist "%KEY%" set "KEY=%~dp0ssh-key-2026-10-22-vps-oracle.key"

echo Conectando con Modalidad 5 [COMBO_TRIO | London + NY + Crypto 24/7] en Oracle Cloud...
ssh -tt -i "%KEY%" -o StrictHostKeyChecking=no ubuntu@157.137.225.144 "cd /home/ubuntu/FTMO_Stellar_Lite && python3 -u main.py live --symbol GC=F,BTC/USDT --provider multi --session COMBO_TRIO --db trading_combo_trio.db"
pause
