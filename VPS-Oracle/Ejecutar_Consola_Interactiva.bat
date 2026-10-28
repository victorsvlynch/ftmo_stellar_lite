@echo off
title FTMO Stellar Lite - Consola CLI Interactiva
cd /d "%~dp0"
if not exist "main.py" if exist "..\main.py" cd /d "%~dp0.."
cls
python main.py interactive
