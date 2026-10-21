@echo off
cd /d "%~dp0"

if exist .venv\Scripts\python.exe goto :pip_check
goto :crea_venv

:crea_venv
where py >nul 2>nul
if %errorlevel%==0 (
    py -m venv .venv
    goto :pip_check
)
where python >nul 2>nul
if %errorlevel%==0 (
    python -m venv .venv
    goto :pip_check
)
echo.
echo  Python non trovato. Installa Python 3 da https://www.python.org/downloads/
echo  Spunta "Add Python to PATH" durante l'installazione.
echo.
pause
exit /b 1

:pip_check
.venv\Scripts\python.exe -m pip --version >nul 2>nul
if not errorlevel 1 goto :dipendenze
echo  Preparo pip nell'ambiente virtuale...
.venv\Scripts\python.exe -m ensurepip --upgrade >nul 2>nul
.venv\Scripts\python.exe -m pip --version >nul 2>nul
if not errorlevel 1 goto :dipendenze

echo  Ricreo l'ambiente virtuale con pip...
if exist .venv rmdir /s /q .venv
where py >nul 2>nul
if %errorlevel%==0 (py -m venv .venv) else (python -m venv .venv)
.venv\Scripts\python.exe -m ensurepip --upgrade >nul 2>nul
.venv\Scripts\python.exe -m pip --version >nul 2>nul
if not errorlevel 1 goto :dipendenze

echo.
echo  pip non e' disponibile: scarico get-pip.py...
powershell -NoProfile -Command "Invoke-WebRequest -Uri https://bootstrap.pypa.io/get-pip.py -OutFile get-pip.py" >nul 2>nul
if exist get-pip.py (
    .venv\Scripts\python.exe get-pip.py >nul
    del get-pip.py
)
.venv\Scripts\python.exe -m pip --version >nul 2>nul
if not errorlevel 1 goto :dipendenze

echo.
echo  pip non installabile automaticamente. Riprova con:
echo    python -m venv --clear .venv
echo    .venv\Scripts\python -m pip install -r requirements.txt
echo.
pause
exit /b 1

:dipendenze
.venv\Scripts\python.exe -c "import uvicorn, fastapi, yt_dlp" >nul 2>nul
if not errorlevel 1 goto :avvia
echo.
echo   Installo le dipendenze necessarie...
echo.
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -c "import uvicorn, fastapi, yt_dlp" >nul 2>nul
if errorlevel 1 (
    echo.
    echo   Dipendenze ancora mancanti. Controlla l'output del pip qui sopra.
    echo.
    pause
    exit /b 1
)

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
