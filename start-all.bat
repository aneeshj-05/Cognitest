@echo off
echo ========================================
echo    Cognitest - Starting All Services
echo ========================================
echo.

:: Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH
    pause
    exit /b 1
)

:: Check if Node is installed
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Node.js is not installed or not in PATH
    pause
    exit /b 1
)

echo Starting Python Service (FastAPI) on port 8000...
start "Python Service" cmd /k "cd python-service && pip install -r requirements.txt && uvicorn src.main:app --reload --port 8000"

timeout /t 5 /nobreak >nul

echo Starting Backend (Node.js) on port 5000...
start "Backend" cmd /k "cd backend && npm install && npm run dev"

timeout /t 3 /nobreak >nul

echo Starting Frontend (Vite) on port 5173...
start "Frontend" cmd /k "cd frontend && npm install && npm run dev"

echo.
echo ========================================
echo    All services are starting...
echo ========================================
echo.
echo    Frontend:       http://localhost:5173
echo    Backend:        http://localhost:5000
echo    Python Service: http://localhost:8000
echo.
echo Press any key to exit this window...
pause >nul
