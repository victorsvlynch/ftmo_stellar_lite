@echo off
title Monitor 3: CRYPTO_24H (24/7 Continuo) - FTMO Stellar Lite
mode con: cols=85 lines=25
cls

set "KEY=%USERPROFILE%\.ssh\ssh-key-2026-10-26.key"
if not exist "%KEY%" set "KEY=%USERPROFILE%\.ssh\oracle_vps.key"
if not exist "%KEY%" set "KEY=%~dp0ssh-key-2026-10-26.key"
if not exist "%KEY%" set "KEY=%~dp0ssh-key-2026-10-22-vps-oracle.key"

echo Conectando con Modalidad 3 [CRYPTO_24H | BTC/USDT] en Oracle Cloud...
ssh -tt -i "%KEY%" -o StrictHostKeyChecking=no ubuntu@157.137.225.144 "cd /home/ubuntu/FTMO_Stellar_Lite && python3 -u main.py live --symbol BTC/USDT --provider ccxt --session ALL --db trading_crypto_24h.db"
pause
