@echo off
title FTMO Stellar Lite - Suite de Verificacion Integral
cd /d "%~dp0"
if not exist "test_verification.py" if exist "..\test_verification.py" cd /d "%~dp0.."
cls
python test_verification.py
pause
