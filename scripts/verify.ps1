$ErrorActionPreference = "Stop"

Push-Location "$PSScriptRoot\..\backend"
python -m pytest -q
Pop-Location

Push-Location "$PSScriptRoot\..\apps\desktop"
npm run build
Pop-Location
