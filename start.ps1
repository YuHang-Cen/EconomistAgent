Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = Join-Path $repoRoot "backend"
$frontendDir = Join-Path $repoRoot "frontend"
$backendProcess = $null
$frontendProcess = $null

function Require-Command {
  param([Parameter(Mandatory = $true)][string]$Name)
  if ($null -eq (Get-Command $Name -ErrorAction SilentlyContinue)) {
    throw "Missing required command: $Name"
  }
}

function Assert-PortFree {
  param([Parameter(Mandatory = $true)][int]$Port)
  $listener = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
  if ($null -ne $listener) {
    throw "Port $Port is already in use."
  }
}

function Wait-HttpReady {
  param(
    [Parameter(Mandatory = $true)][string]$Url,
    [int]$TimeoutSeconds = 60
  )
  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  while ((Get-Date) -lt $deadline) {
    try {
      $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 2
      if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
        return $true
      }
    } catch {
      Start-Sleep -Milliseconds 500
    }
  }
  return $false
}

function Stop-ProcessTree {
  param([System.Diagnostics.Process]$Process)
  if ($null -eq $Process -or $Process.HasExited) {
    return
  }
  & taskkill.exe /PID $Process.Id /T /F *> $null
}

Require-Command "uv"
Require-Command "node"
Require-Command "npm.cmd"
Assert-PortFree 8000
Assert-PortFree 3000

if (-not (Test-Path (Join-Path $backendDir ".env"))) {
  Copy-Item (Join-Path $backendDir ".env.example") (Join-Path $backendDir ".env")
  Write-Host "[INFO] Created backend/.env"
}
if (-not (Test-Path (Join-Path $frontendDir ".env"))) {
  Copy-Item (Join-Path $frontendDir ".env.example") (Join-Path $frontendDir ".env")
  Write-Host "[INFO] Created frontend/.env"
}
if (-not (Test-Path (Join-Path $frontendDir "node_modules"))) {
  Push-Location $frontendDir
  try { & npm.cmd ci } finally { Pop-Location }
  if ($LASTEXITCODE -ne 0) { throw "npm ci failed" }
}

try {
  Write-Host "[INFO] Starting backend with hot reload..."
  $backendProcess = Start-Process -FilePath "uv" -ArgumentList @("run", "dev") `
    -WorkingDirectory $backendDir -NoNewWindow -PassThru
  if (-not (Wait-HttpReady "http://127.0.0.1:8000/health")) {
    throw "Backend failed to become ready."
  }

  Write-Host "[INFO] Starting frontend with hot reload..."
  $frontendProcess = Start-Process -FilePath "npm.cmd" -ArgumentList @("run", "dev") `
    -WorkingDirectory $frontendDir -NoNewWindow -PassThru
  if (-not (Wait-HttpReady "http://127.0.0.1:3000")) {
    throw "Frontend failed to become ready."
  }

  Write-Host ""
  Write-Host "[OK] EconomistAgent is running."
  Write-Host "Frontend: http://127.0.0.1:3000"
  Write-Host "Backend:  http://127.0.0.1:8000/health"
  Write-Host "Press Ctrl+C to stop both services."

  while (-not $backendProcess.HasExited -and -not $frontendProcess.HasExited) {
    Start-Sleep -Seconds 1
    $backendProcess.Refresh()
    $frontendProcess.Refresh()
  }
  throw "A service exited unexpectedly."
} finally {
  Write-Host ""
  Write-Host "[INFO] Stopping EconomistAgent..."
  Stop-ProcessTree $frontendProcess
  Stop-ProcessTree $backendProcess
  Write-Host "[OK] EconomistAgent stopped."
}
