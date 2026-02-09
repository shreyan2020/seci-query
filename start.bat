@echo off
echo Starting SECI Query Explorer System...
echo ==================================

REM Check if Ollama is running
curl -s http://localhost:11434/api/tags >nul 2>&1
if %errorlevel% neq 0 (
    echo WARNING: Ollama is not running. Please start it with:
    echo    ollama serve
    echo.
    echo    And make sure you have the required model:
    echo    ollama pull qwen2.5:7b-instruct
    echo.
    echo Continue anyway? (y/N)
    set /p response=
    if /i not "%response%"=="y" exit /b 1
)

echo Starting backend server...
cd backend
start /B python -c "import uvicorn; uvicorn.run('main:app', host='0.0.0.0', port=8000)"

echo Waiting for backend to start...
timeout /t 3 /nobreak >nul

echo Starting frontend server...
cd ..\frontend
start /B npm run dev

echo.
echo Services started!
echo    Backend: http://localhost:8000
echo    Frontend: http://localhost:3000 (or 3001/3002/3003 if needed)
echo    API Docs: http://localhost:8000/docs
echo.
echo Press Ctrl+C to stop all services
pause