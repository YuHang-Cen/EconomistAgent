@echo off
setlocal

set MODE=%~1
if "%MODE%"=="" set MODE=single

set CONCURRENCY=%~2

if "%CONCURRENCY%"=="" (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-dev.ps1" -Mode %MODE%
) else (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-dev.ps1" -Mode %MODE% -WorkerConcurrency %CONCURRENCY%
)
