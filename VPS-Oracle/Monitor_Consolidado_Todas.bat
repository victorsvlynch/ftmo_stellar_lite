@echo off
title Tablero Consolidado Multi-Modalidad (FTMO Stellar Lite - 5 Estrategias)
mode con: cols=105 lines=28
cls

set "KEY=%USERPROFILE%\.ssh\ssh-key-2026-10-26.key"
if not exist "%KEY%" set "KEY=%USERPROFILE%\.ssh\oracle_vps.key"
if not exist "%KEY%" set "KEY=%~dp0ssh-key-2026-10-26.key"
if not exist "%KEY%" set "KEY=%~dp0ssh-key-2026-10-22-vps-oracle.key"

echo Conectando con Tablero Consolidado (5 Modalidades) en Oracle Cloud (157.137.225.144)...
ssh -tt -i "%KEY%" -o StrictHostKeyChecking=no ubuntu@157.137.225.144 "cd /home/ubuntu/FTMO_Stellar_Lite && python3 -u main.py multi"
pause
