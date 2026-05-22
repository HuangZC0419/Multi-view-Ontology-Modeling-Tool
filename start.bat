@echo off
chcp 65001 >nul 2>&1
setlocal

echo.
echo ============================================
echo   OCR Project - Building ^& Starting...
echo ============================================
echo.
echo   Backend:  http://localhost:8000
echo   API docs: http://localhost:8000/docs
echo   Frontend: http://localhost:8000
echo.

echo [1/3] Building frontend...
cd /d "%~dp0frontend"
call npm install
call npm run build
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Frontend build failed!
    pause
    exit /b 1
)
cd /d "%~dp0"

echo [2/3] Starting backend...
start "OCR-Backend" cmd /k "cd /d %~dp0backend && uvicorn app.main:app --host 0.0.0.0 --port 8000"

timeout /t 3 /nobreak >nul

echo.
echo ============================================
echo   Backend started in new window.
echo   Open http://localhost:8000 in browser.
echo ============================================
echo.
echo Press any key to close this window...
pause >nul
