@echo off
setlocal

set "ROOT=%~dp0"

docker compose version >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Docker Compose is not available.
  exit /b 1
)

pushd "%ROOT%"
docker compose down
if errorlevel 1 (
  popd
  echo [ERROR] Failed to stop services.
  exit /b 1
)
popd

echo [OK] Services stopped.
