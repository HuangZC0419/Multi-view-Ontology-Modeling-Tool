@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "ROOT=%~dp0"
set "LOCAL_IP=UNKNOWN"

echo.
echo ============================================
echo   OCR Project - Starting services...
echo ============================================
echo.

rem 1. Find free ports
echo [1/6] Scanning free ports...
call :find_free_port 8000 8100 BACKEND_PORT
if errorlevel 1 goto :startup_error

call :find_free_port 5173 5200 FRONTEND_PORT
if errorlevel 1 goto :startup_error

echo         Backend port : !BACKEND_PORT!
echo         Frontend port: !FRONTEND_PORT!

rem 2. Detect local IPv4
echo [2/6] Detecting local network address...
call :detect_local_ip
echo         Local IP     : !LOCAL_IP!

rem 3. Clean any listener that still sits on the selected ports
echo [3/6] Cleaning stale listeners...
call :kill_port !BACKEND_PORT!
call :kill_port !FRONTEND_PORT!

rem 4. Install frontend dependencies if needed
echo [4/6] Checking frontend dependencies...
pushd "%ROOT%frontend" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Cannot enter frontend directory.
    goto :startup_error
)

if not exist "node_modules" (
    echo         Installing npm packages...
    call npm install
    if errorlevel 1 (
        echo [ERROR] npm install failed.
        popd >nul 2>&1
        goto :startup_error
    )
)
popd >nul 2>&1

rem 5. Start backend
echo [5/6] Starting backend on port !BACKEND_PORT!...
start "OCR-Backend" cmd /k "title OCR-Backend ^&^& cd /d %ROOT%backend ^&^& set VITE_BACKEND_PORT=!BACKEND_PORT! ^&^& uvicorn app.main:app --host 127.0.0.1 --port !BACKEND_PORT!"
timeout /t 3 /nobreak >nul

rem 6. Start frontend
echo [6/6] Starting frontend on port !FRONTEND_PORT!...
start "OCR-Frontend" cmd /k "title OCR-Frontend ^&^& cd /d %ROOT%frontend ^&^& set VITE_BACKEND_PORT=!BACKEND_PORT! ^&^& npx vite --port !FRONTEND_PORT! --host 0.0.0.0"
timeout /t 3 /nobreak >nul

rem 7. Open browser
start "" "http://localhost:!FRONTEND_PORT!"

echo.
echo ============================================
echo   Startup complete.
echo.
echo   Local URL : http://localhost:!FRONTEND_PORT!
if /I not "!LOCAL_IP!"=="UNKNOWN" (
    echo   LAN URL   : http://!LOCAL_IP!:!FRONTEND_PORT!
)
echo.
echo   Backend API: http://localhost:!BACKEND_PORT!/docs
echo ============================================
echo.
echo Press any key to close this window...
pause >nul
exit /b 0

:startup_error
echo.
echo Startup aborted.
pause
exit /b 1

:find_free_port
set "%~3="
set "CURRENT_PORT=%~1"
set "MAX_PORT=%~2"

:find_free_port_loop
netstat -ano 2>nul | findstr /R /C:":!CURRENT_PORT! " | findstr /I "LISTENING" >nul 2>&1
if errorlevel 1 (
    set "%~3=!CURRENT_PORT!"
    exit /b 0
)

set /a CURRENT_PORT+=1
if !CURRENT_PORT! GTR !MAX_PORT! (
    echo [ERROR] No free port in range %~1-%~2.
    exit /b 1
)
goto :find_free_port_loop

:detect_local_ip
set "LOCAL_IP=UNKNOWN"
for /f "tokens=2 delims=:" %%A in ('ipconfig 2^>nul ^| findstr /I "IPv4"') do (
    for /f "tokens=* delims= " %%B in ("%%A") do (
        set "IP_CANDIDATE=%%B"
        if /I not "!IP_CANDIDATE:~0,7!"=="127.0.0" (
            set "LOCAL_IP=!IP_CANDIDATE!"
            exit /b 0
        )
    )
)
exit /b 0

:kill_port
for /f "tokens=5" %%P in ('netstat -ano 2^>nul ^| findstr /R /C:":%~1 " ^| findstr /I "LISTENING"') do (
    taskkill /F /PID %%P >nul 2>&1
)
exit /b 0
