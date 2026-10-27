@echo off
title FTMO Stellar Lite - Estado Financiero de las 5 Modalidades
cd /d "%~dp0"
if not exist "main.py" if exist "..\main.py" cd /d "%~dp0.."
cls
python main.py multi-status
pause
