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
$backendEnvFile = Join-Path $backendDir ".env"

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

function Get-PortListenerInfo {
  param(
    [Parameter(Mandatory = $true)][int]$Port
  )

  $listeners = Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
    Where-Object { $_.LocalPort -eq $Port } |
    Sort-Object -Property LocalAddress

  foreach ($listener in $listeners) {
    $process = Get-CimInstance Win32_Process -Filter "ProcessId = $($listener.OwningProcess)" -ErrorAction SilentlyContinue
    [PSCustomObject]@{
      LocalAddress = $listener.LocalAddress
      LocalPort = $listener.LocalPort
      OwningProcess = $listener.OwningProcess
      ProcessName = if ($null -ne $process) { $process.Name } else { $null }
      CommandLine = if ($null -ne $process) { $process.CommandLine } else { $null }
    }
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

function Test-HttpReady {
  param(
    [Parameter(Mandatory = $true)][string]$Url,
    [int]$TimeoutSeconds = 3
  )

  try {
    $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec $TimeoutSeconds
    return ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500)
  } catch {
    return $false
  }
}

function Format-ListenerSummary {
  param(
    [Parameter(Mandatory = $true)][object[]]$Listeners
  )

  return (
    $Listeners |
      ForEach-Object {
        $commandLine = if ($_.CommandLine) { $_.CommandLine.Trim() } else { "<unknown>" }
        "PID $($_.OwningProcess) [$($_.ProcessName)] $commandLine"
      }
  ) -join "; "
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

function Get-EnvFileValue {
  param(
    [Parameter(Mandatory = $true)][string]$Path,
    [Parameter(Mandatory = $true)][string]$Key
  )

  if (-not (Test-Path $Path)) {
    return $null
  }

  foreach ($line in Get-Content -Path $Path) {
    $trimmed = $line.Trim()
    if ($trimmed.Length -eq 0 -or $trimmed.StartsWith("#")) {
      continue
    }
    if ($trimmed -match "^(?<name>[A-Za-z_][A-Za-z0-9_]*)=(?<value>.*)$" -and $Matches.name -eq $Key) {
      return $Matches.value.Trim()
    }
  }

  return $null
}

function Resolve-ServiceStartupDecision {
  param(
    [Parameter(Mandatory = $true)][string]$ServiceName,
    [Parameter(Mandatory = $true)][int]$Port,
    [Parameter(Mandatory = $true)][string]$HealthUrl
  )

  $listeners = @(Get-PortListenerInfo -Port $Port)
  if ($listeners.Count -eq 0) {
    return [PSCustomObject]@{
      Action = "start"
      Message = $null
    }
  }

  if (Test-HttpReady -Url $HealthUrl) {
    return [PSCustomObject]@{
      Action = "reuse"
      Message = "${ServiceName}: reusing existing service on port $Port"
    }
  }

  $summary = Format-ListenerSummary -Listeners $listeners
  return [PSCustomObject]@{
    Action = "blocked"
    Message = "${ServiceName}: port $Port is already occupied by $summary"
  }
}

$redisReady = if ($DryRun) { $true } else { Ensure-RedisForDev }

$apiDecision = if ($DryRun) {
  [PSCustomObject]@{ Action = "start"; Message = $null }
} else {
  Resolve-ServiceStartupDecision -ServiceName "API" -Port 8000 -HealthUrl "http://127.0.0.1:8000/health"
}

switch ($apiDecision.Action) {
  "start" {
    Start-DevWindow -Title "EconomistAgent API" -WorkingDirectory $backendDir -Command "uv run dev"
  }
  "reuse" {
    Write-Host $apiDecision.Message
  }
  "blocked" {
    throw $apiDecision.Message
  }
}

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

$frontendDecision = if ($DryRun) {
  [PSCustomObject]@{ Action = "start"; Message = $null }
} else {
  Resolve-ServiceStartupDecision -ServiceName "Frontend" -Port 3000 -HealthUrl "http://127.0.0.1:3000"
}

switch ($frontendDecision.Action) {
  "start" {
    $analysisOnly = Get-EnvFileValue -Path $backendEnvFile -Key "VITE_UI_ANALYSIS_ONLY"
    if ([string]::IsNullOrWhiteSpace($analysisOnly)) {
      $analysisOnly = "false"
    }
    Start-DevWindow -Title "EconomistAgent Frontend" -WorkingDirectory $frontendDir -Command "`$env:VITE_UI_ANALYSIS_ONLY='$analysisOnly'; npm run dev"
  }
  "reuse" {
    Write-Host $frontendDecision.Message
  }
  "blocked" {
    throw $frontendDecision.Message
  }
}

Write-Host "Development mode started."
Write-Host "API:      http://127.0.0.1:8000"
Write-Host "Frontend: http://localhost:3000"
Write-Host "Worker concurrency: $WorkerConcurrency"
