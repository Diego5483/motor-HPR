@echo off
title Motor HPR - Escritorio Local
rem ============================================================
rem  Motor HPR - Lanzador oficial de la aplicacion de escritorio
rem  Uso: ejecutar.bat  (doble clic o desde la consola)
rem ============================================================

cd /d "%~dp0"

rem --- Localiza el entorno virtual (raiz del repositorio o carpeta del proyecto) ---
set "VENV=..\.venv"
if not exist "%VENV%\Scripts\activate.bat" set "VENV=.venv"
if not exist "%VENV%\Scripts\activate.bat" (
    echo.
    echo [HPR] ERROR: no se encontro el entorno virtual.
    echo [HPR] Crear el entorno e instalar dependencias:
    echo [HPR]     python -m venv .venv
    echo [HPR]     .venv\Scripts\pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

call "%VENV%\Scripts\activate.bat"

rem --- Arranque de la aplicacion de escritorio ---
echo [HPR] Iniciando Motor HPR - Escritorio Local...
python -m src.desktop
set "CODIGO=%ERRORLEVEL%"

if not "%CODIGO%"=="0" (
    echo.
    echo [HPR] La aplicacion finalizo con errores ^(codigo %CODIGO%^).
    echo [HPR] Revisa la salida de la consola para mas detalles.
)

echo.
pause
exit /b %CODIGO%
