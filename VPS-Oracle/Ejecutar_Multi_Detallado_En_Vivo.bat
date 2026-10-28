@echo off
title FTMO Stellar Lite - Tablero Detallado en Vivo (5 Modalidades con Operaciones)
cd /d "%~dp0"
if not exist "main.py" if exist "..\main.py" cd /d "%~dp0.."
cls
python main.py multi-detail
pause
