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

function Test-TcpPort {
  param(
    [Parameter(Mandatory = $true)][string]$Address,
    [Parameter(Mandatory = $true)][int]$Port,
    [int]$TimeoutMs = 1000
  )

  $client = New-Object System.Net.Sockets.TcpClient
  try {
    $async = $client.BeginConnect($Address, $Port, $null, $null)
    if (-not $async.AsyncWaitHandle.WaitOne($TimeoutMs, $false)) {
      return $false
    }
    $client.EndConnect($async)
    return $true
  } catch {
    return $false
  } finally {
    $client.Dispose()
  }
}

function Wait-HttpReady {
  param(
    [Parameter(Mandatory = $true)][string]$Url,
    [int]$TimeoutSeconds = 25
  )

  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  while ((Get-Date) -lt $deadline) {
    try {
      $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
      if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
        return $true
      }
    } catch {
      Start-Sleep -Milliseconds 750
      continue
    }
  }

  return $false
}

function Ensure-RedisForDev {
  if (Test-TcpPort -Address "127.0.0.1" -Port 6379) {
    Write-Host "Redis: using existing instance at 127.0.0.1:6379"
    return $true
  }

  $dockerCommand = Get-Command docker -ErrorAction SilentlyContinue
  if ($null -eq $dockerCommand) {
    Write-Warning "Redis is not running on 127.0.0.1:6379 and Docker is unavailable. Worker will be skipped."
    return $false
  }

  try {
    & $dockerCommand.Source compose version *> $null
    & $dockerCommand.Source compose up -d redis
  } catch {
    Write-Warning "Failed to start Redis via 'docker compose up -d redis'. Worker will be skipped."
    return $false
  }

  for ($attempt = 0; $attempt -lt 20; $attempt++) {
    if (Test-TcpPort -Address "127.0.0.1" -Port 6379) {
      Write-Host "Redis: started via docker compose"
      return $true
    }
    Start-Sleep -Seconds 1
  }

  Write-Warning "Redis did not become ready on 127.0.0.1:6379. Worker will be skipped."
  return $false
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

$redisReady = if ($DryRun) { $true } else { Ensure-RedisForDev }

Start-DevWindow -Title "EconomistAgent API" -WorkingDirectory $backendDir -Command "uv run dev"

if (-not $DryRun) {
  if (Wait-HttpReady -Url "http://127.0.0.1:8000/health") {
    Write-Host "API: ready at http://127.0.0.1:8000"
  } else {
    Write-Warning "API did not become ready within 25 seconds. Frontend may show temporary proxy errors until backend finishes starting."
  }
}

if ($redisReady) {
  Start-DevWindow -Title "EconomistAgent Worker" -WorkingDirectory $backendDir -Command "`$env:CELERY_WORKER_CONCURRENCY='$WorkerConcurrency'; uv run worker"
} else {
  Write-Warning "Worker was not started because Redis is unavailable. Background jobs will fall back to inline execution when possible."
}

Start-DevWindow -Title "EconomistAgent Frontend" -WorkingDirectory $frontendDir -Command "npm run dev"

Write-Host "Development mode started."
Write-Host "API:      http://127.0.0.1:8000"
Write-Host "Frontend: http://localhost:3000"
Write-Host "Worker concurrency: $WorkerConcurrency"
