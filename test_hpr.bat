@echo off
rem ===================================================
rem HPR Desktop Application Diagnostics
rem ===================================================

cd /d "%~dp0HPR"
set PYTHONPATH=%CD%

echo.
echo Iniciando Motor HPR en modo diagnostico...
echo.

python src\desktop\app.py %*

echo.
echo ===================================================
echo LA APLICACION SE HA CERRADO.
echo Revisa si arriba aparece algun error o excepcion.
echo ===================================================
pause