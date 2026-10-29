param([switch]$WithoutModel)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$toolsRoot = Join-Path (Split-Path -Parent $projectRoot) '.tools'
$venvRoot = Join-Path $toolsRoot 'backend-venv'
$pythonExe = Join-Path $venvRoot 'Scripts/python.exe'
if (-not (Test-Path -LiteralPath $pythonExe)) {
    New-Item -ItemType Directory -Force -Path $toolsRoot | Out-Null
    & python -m venv $venvRoot
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.12 virtual environment creation failed' }
}
function Invoke-PythonChecked {
    param([string[]]$Arguments)
    & $pythonExe @Arguments
    if ($LASTEXITCODE -ne 0) { throw ('Backend deployment step failed: ' + ($Arguments -join ' ')) }
}
Invoke-PythonChecked -Arguments @('-m','pip','install','-r','requirements.txt')
Invoke-PythonChecked -Arguments @('-X','utf8','scripts/db_migrate.py')
Invoke-PythonChecked -Arguments @('-X','utf8','scripts/db_init.py')
if (-not $WithoutModel) {
    Invoke-PythonChecked -Arguments @('-X','utf8','scripts/setup_local_model.py')
    Invoke-PythonChecked -Arguments @('-X','utf8','scripts/configure_local_model.py')
    & (Join-Path $PSScriptRoot 'start-local-model.ps1')
}
Write-Host 'Backend prepared. Start the integrated app with: powershell -File scripts/start.ps1 -Production'
