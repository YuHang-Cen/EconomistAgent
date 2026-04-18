param(
  [ValidateSet("single", "multi")]
  [string]$Mode = "single",
  [int]$WorkerConcurrency,
  [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = Join-Path $repoRoot "backend"
$frontendDir = Join-Path $repoRoot "frontend"

if (-not (Test-Path $backendDir)) {
  throw "backend directory not found: $backendDir"
}
if (-not (Test-Path $frontendDir)) {
  throw "frontend directory not found: $frontendDir"
}

if (-not $PSBoundParameters.ContainsKey("WorkerConcurrency")) {
  $WorkerConcurrency = if ($Mode -eq "multi") { 8 } else { 4 }
}

function Start-DevWindow {
  param(
    [Parameter(Mandatory = $true)][string]$Title,
    [Parameter(Mandatory = $true)][string]$WorkingDirectory,
    [Parameter(Mandatory = $true)][string]$Command
  )

  $bootstrap = "`$Host.UI.RawUI.WindowTitle = '$Title'; Set-Location '$WorkingDirectory'; $Command"

  if ($DryRun) {
    Write-Host "[DRY-RUN] $Title => $bootstrap"
    return
  }

  Start-Process -FilePath "powershell.exe" `
    -WorkingDirectory $WorkingDirectory `
    -ArgumentList @("-NoExit", "-ExecutionPolicy", "Bypass", "-Command", $bootstrap) `
    | Out-Null
}

Start-DevWindow -Title "EconomistAgent API" -WorkingDirectory $backendDir -Command "uv run dev"
Start-DevWindow -Title "EconomistAgent Worker" -WorkingDirectory $backendDir -Command "`$env:CELERY_WORKER_CONCURRENCY='$WorkerConcurrency'; uv run worker"
Start-DevWindow -Title "EconomistAgent Frontend" -WorkingDirectory $frontendDir -Command "npm run dev"

Write-Host "Development mode started."
Write-Host "API:      http://127.0.0.1:8000"
Write-Host "Frontend: http://localhost:3000"
Write-Host "Worker concurrency: $WorkerConcurrency"
