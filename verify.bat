@echo off
echo Verificando configuración...
cd /d "%~dp0"
set PYTHONPATH=%~dp0src
echo PYTHONPATH=%PYTHONPATH%
echo.
echo Ejecutando prueba Python...
python -c "import sys; sys.path.insert(0, r'C:\Users\USUARIO\Desktop\motor HPR\HPR'); from src.desktop.app import AplicacionHPR, RUTA_LOGO; print('RUTA_LOGO:', RUTA_LOGO); print('OK')"
pause