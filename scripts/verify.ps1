$ErrorActionPreference = "Stop"

function Invoke-NativeCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string] $FilePath,

        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]] $Arguments
    )

    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$FilePath exited with code $LASTEXITCODE"
    }
}

$PythonPath = Join-Path "$PSScriptRoot\.." ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $PythonPath)) {
    $PythonPath = "python"
}

Push-Location "$PSScriptRoot\..\backend"
try {
    Invoke-NativeCommand $PythonPath -m pytest -q
}
finally {
    Pop-Location
}

Push-Location "$PSScriptRoot\..\apps\desktop"
try {
    Invoke-NativeCommand npm.cmd test
    Invoke-NativeCommand npm.cmd run typecheck
    Invoke-NativeCommand npm.cmd run build
}
finally {
    Pop-Location
}
