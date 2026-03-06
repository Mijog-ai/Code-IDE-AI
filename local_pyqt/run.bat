@echo off
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found in local_pyqt\.venv
    echo Run this first:
    echo   python -m venv .venv
    echo   .venv\Scripts\pip install PyQt6 transformers accelerate
    echo   .venv\Scripts\pip install torch --index-url https://download.pytorch.org/whl/cu128
    pause
    exit /b 1
)

echo [AI Coder IDE] Starting local model version...
echo Python: %~dp0.venv\Scripts\python.exe
echo.

.venv\Scripts\python.exe main.py
if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] App exited with code %ERRORLEVEL%
    pause
)
