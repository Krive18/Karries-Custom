param(
    [string]$WorkspaceRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [string]$MySqlPassword = $env:MYSQL_PASSWORD
)

$ErrorActionPreference = "Stop"

$localEnvFile = Join-Path $WorkspaceRoot ".env.local"
if (Test-Path -LiteralPath $localEnvFile -PathType Leaf) {
    foreach ($line in Get-Content -LiteralPath $localEnvFile) {
        $trimmedLine = $line.Trim()
        if (-not $trimmedLine -or $trimmedLine.StartsWith("#")) {
            continue
        }

        $separatorIndex = $trimmedLine.IndexOf("=")
        if ($separatorIndex -lt 1) {
            throw "Invalid local environment entry in ${localEnvFile}: $trimmedLine"
        }

        $name = $trimmedLine.Substring(0, $separatorIndex).Trim()
        if ($name -notmatch "^[A-Za-z_][A-Za-z0-9_]*$") {
            throw "Invalid environment variable name in ${localEnvFile}: $name"
        }

        $value = $trimmedLine.Substring($separatorIndex + 1).Trim()
        if (
            $value.Length -ge 2 -and
            (($value.StartsWith('"') -and $value.EndsWith('"')) -or
             ($value.StartsWith("'") -and $value.EndsWith("'")))
        ) {
            $value = $value.Substring(1, $value.Length - 2)
        }
        [Environment]::SetEnvironmentVariable($name, $value, "Process")
    }
}

$backendDir = Join-Path $WorkspaceRoot "backend"
$frontendDir = Join-Path $WorkspaceRoot "apps\desktop"
$runtimeDir = Join-Path $WorkspaceRoot "runtime\local-services"
$python = Join-Path $backendDir ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Backend Python environment was not found: $python"
}

if ($MySqlPassword) {
    $env:MYSQL_PASSWORD = $MySqlPassword
} else {
    Write-Warning "MYSQL_PASSWORD is empty. Backends that require MySQL authentication may start but remain unready."
}

New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null

function Start-LoggedProcess {
    param(
        [string]$Name,
        [string]$FilePath,
        [string[]]$ArgumentList,
        [string]$WorkingDirectory
    )

    $process = Start-Process `
        -FilePath $FilePath `
        -ArgumentList $ArgumentList `
        -WorkingDirectory $WorkingDirectory `
        -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $runtimeDir "$Name.out.log") `
        -RedirectStandardError (Join-Path $runtimeDir "$Name.err.log") `
        -PassThru
    [pscustomobject]@{ Name = $Name; ProcessId = $process.Id }
}

function Test-ListeningPort {
    param([int]$Port)
    return [bool](Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue)
}

$processes = @()

if (-not (Test-ListeningPort 8765)) {
    $processes += Start-LoggedProcess `
        -Name "backend-customer" `
        -FilePath $python `
        -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8765") `
        -WorkingDirectory $backendDir
}

if (-not (Test-ListeningPort 8766)) {
    $processes += Start-LoggedProcess `
        -Name "backend-manager" `
        -FilePath $python `
        -ArgumentList @("-m", "uvicorn", "app.manager_main:app", "--host", "127.0.0.1", "--port", "8766") `
        -WorkingDirectory $backendDir
}

if (-not (Test-ListeningPort 8767)) {
    $processes += Start-LoggedProcess `
        -Name "backend-developer" `
        -FilePath $python `
        -ArgumentList @("-m", "uvicorn", "app.developer_main:app", "--host", "127.0.0.1", "--port", "8767") `
        -WorkingDirectory $backendDir
}

if (-not (Test-ListeningPort 5174)) {
    $env:VITE_API_PROXY_TARGET = "http://127.0.0.1:8765"
    $processes += Start-LoggedProcess `
        -Name "frontend-customer" `
        -FilePath "npm.cmd" `
        -ArgumentList @("run", "dev", "--", "--host", "127.0.0.1", "--port", "5174", "--strictPort") `
        -WorkingDirectory $frontendDir
}

if (-not (Test-ListeningPort 5175)) {
    $env:VITE_API_PROXY_TARGET = "http://127.0.0.1:8766"
    $processes += Start-LoggedProcess `
        -Name "frontend-manager" `
        -FilePath "npm.cmd" `
        -ArgumentList @("run", "dev:manager", "--", "--host", "127.0.0.1", "--port", "5175", "--strictPort") `
        -WorkingDirectory $frontendDir
}

if (-not (Test-ListeningPort 5176)) {
    $env:VITE_API_PROXY_TARGET = "http://127.0.0.1:8767"
    $processes += Start-LoggedProcess `
        -Name "frontend-developer" `
        -FilePath "npm.cmd" `
        -ArgumentList @("run", "dev:developer", "--", "--host", "127.0.0.1", "--port", "5176", "--strictPort") `
        -WorkingDirectory $frontendDir
}

$processes
