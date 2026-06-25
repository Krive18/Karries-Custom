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

Push-Location "$PSScriptRoot\..\backend"
try {
    Invoke-NativeCommand python -m pytest -q
}
finally {
    Pop-Location
}

Push-Location "$PSScriptRoot\..\apps\desktop"
try {
    Invoke-NativeCommand npm run build
}
finally {
    Pop-Location
}
