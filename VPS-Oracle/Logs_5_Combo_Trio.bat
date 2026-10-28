@echo off
title Logs Modalidad 5: COMBO_TRIO (stellar_combo_trio.service)
mode con: cols=120 lines=35
cls

set "KEY=%USERPROFILE%\.ssh\ssh-key-2026-10-26.key"
if not exist "%KEY%" set "KEY=%USERPROFILE%\.ssh\oracle_vps.key"
if not exist "%KEY%" set "KEY=%~dp0ssh-key-2026-10-26.key"
if not exist "%KEY%" set "KEY=%~dp0ssh-key-2026-10-22-vps-oracle.key"

echo Mostrando logs en vivo de Modalidad 5 (COMBO_TRIO)...
ssh -i "%KEY%" -o StrictHostKeyChecking=no ubuntu@157.137.225.144 "sudo journalctl -u stellar_combo_trio.service -f"
pause
