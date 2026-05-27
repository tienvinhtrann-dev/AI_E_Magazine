@echo off
REM ============================================
REM AI E-MAGAZINE - QUICK START SCRIPT
REM ============================================

echo ========================================
echo   AI E-MAGAZINE - Quick Start
echo ========================================
echo.

REM Check if MySQL is running
echo [1/4] Checking MySQL...
netstat -ano | findstr ":3306" >nul
if errorlevel 1 (
    echo   [!] MySQL is NOT running!
    echo   [!] Please start MySQL in XAMPP Control Panel
    pause
    exit /b 1
) else (
    echo   [OK] MySQL is running
)

echo.
echo [2/4] Checking Python packages...
"%~dp0.venv\Scripts\python.exe" -m pip show flask >nul 2>&1
if errorlevel 1 (
    echo   [!] Installing required packages...
    "%~dp0.venv\Scripts\python.exe" -m pip install -r requirements_simple.txt
) else (
    echo   [OK] Packages installed
)

echo.
echo [3/4] Checking database...
"%~dp0.venv\Scripts\python.exe" -c "from database.db_simple import test_connection; test_connection()" 2>nul
if errorlevel 1 (
    echo   [!] Database not found. Initializing...
    "%~dp0.venv\Scripts\python.exe" -c "from database.db_simple import init_database; init_database()"
) else (
    echo   [OK] Database ready
)

echo.
echo [4/4] Starting Flask server...
echo ========================================
echo.
echo   Access your app at: http://127.0.0.1:5000
echo.
echo   Admin account:
echo   - Email: admin@magazine.com
echo   - Password: admin123
echo.
echo ========================================
echo.

"%~dp0.venv\Scripts\python.exe" app_simple.py

pause
