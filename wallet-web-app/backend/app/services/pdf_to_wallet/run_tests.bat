@echo off
echo ========================================
echo PDF to Wallet Pass Test Runner
echo ========================================
echo.

cd /d "%~dp0"

echo Current directory: %CD%
echo.

echo Checking Python installation...
python --version
if errorlevel 1 (
    echo Error: Python not found! Please install Python.
    pause
    exit /b 1
)
echo.

echo Running tests...
python run_tests.py

echo.
echo ========================================
echo Test run completed
echo ========================================
pause
