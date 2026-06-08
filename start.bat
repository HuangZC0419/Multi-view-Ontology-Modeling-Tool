@echo off
chcp 65001 >nul 2>&1
setlocal

set "ROOT=%~dp0"
set "BACKEND_PORT=8000"

echo.
echo ============================================
echo   OCR Project - Building ^& Starting...
echo ============================================
echo.
echo   Backend:  http://localhost:%BACKEND_PORT%
echo   API docs: http://localhost:%BACKEND_PORT%/docs
echo   Frontend: http://localhost:%BACKEND_PORT%
echo.

echo [0/3] Killing old processes on port %BACKEND_PORT%...
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:":%BACKEND_PORT% " ^| findstr LISTENING 2^>nul') do (
    taskkill /F /PID %%P >nul 2>&1
)

echo [1/3] Building frontend...
cd /d "%ROOT%frontend"
if not exist "node_modules" (
    call npm install
    if %ERRORLEVEL% NEQ 0 (
        echo [ERROR] npm install failed!
        pause
        exit /b 1
    )
)
call npm run build
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Frontend build failed!
    pause
    exit /b 1
)
cd /d "%ROOT%"

echo [2/3] Starting backend...
start "OCR-Backend" cmd /k "cd /d %ROOT%backend && uvicorn app.main:app --host 127.0.0.1 --port %BACKEND_PORT%"

timeout /t 3 /nobreak >nul

echo [3/3] Opening browser...
start "" "http://localhost:%BACKEND_PORT%"

echo.
echo ============================================
echo   Backend started in new window.
echo   Open http://localhost:%BACKEND_PORT% in browser.
echo ============================================
echo.
echo Press any key to close this window...
pause >nul
