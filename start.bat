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
set SITO=http://%HOST%:%PORT%
if "%HOST%"=="0.0.0.0" set SITO=http://127.0.0.1:%PORT%
echo.
echo   Musica senza pubblicita - avvio del server...
echo   %SITO%
echo.
start "" cmd /c "timeout /t 3 >nul & start "" %SITO%"
.venv\Scripts\python.exe -m uvicorn server.main:app --host %HOST% --port %PORT%
