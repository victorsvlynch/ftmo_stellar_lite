@echo off
title Tablero Detallado Multi-Modalidad (FTMO Stellar Lite - Operaciones en Vivo)
mode con: cols=126 lines=38
cls

set "KEY=%USERPROFILE%\.ssh\ssh-key-2026-10-26.key"
if not exist "%KEY%" set "KEY=%USERPROFILE%\.ssh\oracle_vps.key"
if not exist "%KEY%" set "KEY=%~dp0ssh-key-2026-10-26.key"
if not exist "%KEY%" set "KEY=%~dp0ssh-key-2026-10-22-vps-oracle.key"

echo Conectando con Tablero Detallado (5 Modalidades + Operaciones) en Oracle Cloud (157.137.225.144)...
ssh -tt -i "%KEY%" -o StrictHostKeyChecking=no ubuntu@157.137.225.144 "cd /home/ubuntu/FTMO_Stellar_Lite && python3 -u main.py multi-detail"
pause
