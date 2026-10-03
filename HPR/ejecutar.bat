@echo off
title Motor HPR - Escritorio Local
rem ============================================================
rem  Motor HPR - Lanzador oficial de la aplicacion de escritorio
rem  Uso: ejecutar.bat [debug]
rem    (sin argumentos) lanzamiento limpio sin consola (pythonw)
rem    debug            lanzamiento con consola para diagnostico
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

echo [HPR] Iniciando Motor HPR - Escritorio Local...

rem --- Arranque: por defecto sin consola (pythonw); debug con consola ---
set "PY=python"
if exist "%VENV%\Scripts\pythonw.exe" set "PY=pythonw"

if "%~1"=="debug" (
    python -m src.desktop
) else (
    %PY% -m src.desktop
)
set "CODIGO=%ERRORLEVEL%"

if not "%CODIGO%"=="0" (
    echo.
    echo [HPR] La aplicacion finalizo con errores ^(codigo %CODIGO%^).
    echo [HPR] Ejecuta "ejecutar.bat debug" para ver la traza completa.
)

echo.
pause
exit /b %CODIGO%
