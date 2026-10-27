@echo off
chcp 65001 > nul
setlocal EnableDelayedExpansion

echo ============================================================
echo   AUTO-PUSH: FTMO Stellar Lite ($5K) (Batch Runner)
echo ============================================================

cd /d "%~dp0\..\.."

set "COMMIT_MSG=%~1"

if "%COMMIT_MSG%"=="" (
    echo.
    echo Invocando auto_push.ps1 con generacion automatica de mensaje IA...
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0auto_push.ps1"
    goto end
)

echo.
echo Preparando cambios con git add...
git add .

echo Verificando estado de Git...
git status -s

echo Creando commit con mensaje: "%COMMIT_MSG%"
git commit -m "%COMMIT_MSG%"
if errorlevel 1 (
    echo.
    echo Aviso: No habia cambios pendientes para commitear o la operacion se cancelo.
    goto end
)

echo.
echo Intentando subir cambios al repositorio remoto...
git push origin main 2>nul
if errorlevel 1 (
    git push origin master 2>nul
    if errorlevel 1 (
        echo Error: No se pudo realizar el push directamente. Verifique la conexion o el remoto configurado.
    ) else (
        echo Push realizado exitosamente a la rama master!
    )
) else (
    echo Push realizado exitosamente a la rama main!
)

:end
echo.
echo ============================================================
echo  Operacion finalizada.
echo ============================================================
pause
