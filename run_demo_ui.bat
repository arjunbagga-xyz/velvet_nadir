@echo off
setlocal
echo ======================================================
echo   VELVET NADIR — PASSIVE UI DEMO MODE
echo ======================================================
echo.
echo [1/2] Changing directory to UI application...
cd /d "%~dp0sw\UI\app"

echo [2/2] Launching local server and browser...
echo.
echo NOTE: The console will stay open to serve the files.
echo Close this window or press Ctrl+C to stop the demo.
echo.

:: Start the browser first (it will wait for the server to be ready)
start "" "http://localhost:8080"

:: Start Python's built-in HTTP server
python -m http.server 8080

pause
