@echo off
rem Avvio one-click di FreeSic: prepara l'ambiente, avvia il server
rem e apre automaticamente il sito nel browser.
rem Stessa logica su Linux, macOS e Windows (vedi strumenti\avvia.py).
cd /d "%~dp0"

rem --- cerca un Python 3.10 o successivo -------------------------------
py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)" >nul 2>nul
if not errorlevel 1 (
    set "PYEXE=py -3"
    goto :avvia
)

python -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)" >nul 2>nul
if not errorlevel 1 (
    set "PYEXE=python"
    goto :avvia
)

echo.
echo   Python 3.10 o successivo non trovato.
echo   Installalo da https://www.python.org/downloads/
echo   Spunta "Add Python to PATH" durante l'installazione.
echo.
pause
exit /b 1

:avvia
if "%PORT%"=="" set "PORT=8000"
if "%HOST%"=="" set "HOST=127.0.0.1"
%PYEXE% strumenti\avvia.py
if errorlevel 1 pause
