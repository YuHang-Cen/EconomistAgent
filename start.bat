@echo off
setlocal

set "ROOT=%~dp0"
set "ENV_FILE=%ROOT%backend\.env"
set "ENV_EXAMPLE=%ROOT%backend\.env.example"
set "STORAGE_DIR=%ROOT%backend\storage"

docker compose version >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Docker Compose is not available. Please install Docker Desktop first.
  exit /b 1
)

docker info >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Docker daemon is not running. Please start Docker Desktop first.
  exit /b 1
)

if not exist "%ENV_FILE%" (
  if not exist "%ENV_EXAMPLE%" (
    echo [ERROR] Missing backend\.env.example
    exit /b 1
  )
  copy "%ENV_EXAMPLE%" "%ENV_FILE%" >nul
  echo [INFO] Created backend\.env from backend\.env.example
)

if not exist "%STORAGE_DIR%" (
  mkdir "%STORAGE_DIR%" >nul
)

pushd "%ROOT%"
docker compose up -d --build
if errorlevel 1 (
  popd
  echo [ERROR] Failed to start services.
  exit /b 1
)
popd

echo [OK] Services started.
echo Frontend: http://localhost:3000
echo Backend:  http://localhost:8000/health
echo Redis:    localhost:6379
