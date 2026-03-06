@echo off
cd /d "%~dp0"

if not exist ".venv\Scripts\streamlit.exe" (
    echo [ERROR] Virtual environment not found in groq_streamlit\.venv
    echo Run this first:
    echo   python -m venv .venv
    echo   .venv\Scripts\pip install streamlit==1.35.0 groq==0.9.0 streamlit-ace==0.1.1 python-dotenv==1.0.1
    pause
    exit /b 1
)

if not exist ".env" (
    echo [WARNING] .env file not found. Create it with:
    echo   GROQ_API_KEY=your_key_here
    echo.
)

echo [AI Coder IDE] Starting Groq + Streamlit version...
echo.

.venv\Scripts\streamlit.exe run app.py
if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Streamlit exited with code %ERRORLEVEL%
    pause
)
