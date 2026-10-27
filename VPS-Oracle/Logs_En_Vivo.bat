@echo off
title Logs En Vivo Multi-Modalidad - FTMO Stellar Lite
mode con: cols=120 lines=35
cls

set "KEY=%USERPROFILE%\.ssh\ssh-key-2026-10-26.key"
if not exist "%KEY%" set "KEY=%USERPROFILE%\.ssh\oracle_vps.key"
if not exist "%KEY%" set "KEY=%~dp0ssh-key-2026-10-26.key"
if not exist "%KEY%" set "KEY=%~dp0ssh-key-2026-10-22-vps-oracle.key"

echo Conectando al flujo de logs unificados (5 modalidades) en Oracle Cloud...
ssh -i "%KEY%" -o StrictHostKeyChecking=no ubuntu@157.137.225.144 "sudo journalctl -u 'stellar_*' -f"
pause
