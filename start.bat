@echo off
cd /d "%~dp0"
if exist .venv\Scripts\python.exe goto :avvia

where py >nul 2>nul
if %errorlevel%==0 (
    py -m venv .venv
    goto :installa
)
where python >nul 2>nul
if %errorlevel%==0 (
    python -m venv .venv
    goto :installa
)

echo.
echo  Python non trovato. Installa Python 3 da https://www.python.org/downloads/
echo  Spunta "Add Python to PATH" durante l'installazione.
echo.
pause
exit /b 1

:installa
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt

:avvia
if "%PORT%"=="" set PORT=8000
if "%HOST%"=="" set HOST=127.0.0.1
echo.
echo   Musica senza pubblicita - avvio del server...
echo   http://%HOST%:%PORT%/
echo.
.venv\Scripts\python.exe -m uvicorn server.main:app --host %HOST% --port %PORT%
