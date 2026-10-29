param([switch]$BackendOnly, [switch]$FrontendOnly, [switch]$WithoutModel, [switch]$Production)
$ErrorActionPreference = 'Stop'
$projectPath = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectPath
$toolPath = Join-Path (Split-Path -Parent $projectPath) '.tools'
$portableNode = Get-ChildItem -LiteralPath $toolPath -Directory -Filter 'node-v*-win-x64' -ErrorAction SilentlyContinue | Select-Object -First 1
if ($portableNode) { $env:PATH = $portableNode.FullName + ';' + $env:PATH }
$projectPython = Join-Path $projectPath '.venv/Scripts/python.exe'
$portablePython = Join-Path $toolPath 'backend-venv/Scripts/python.exe'
if (Test-Path -LiteralPath $projectPython) { $pythonExe = $projectPython }
elseif (Test-Path -LiteralPath $portablePython) { $pythonExe = $portablePython }
else { $pythonExe = 'python' }
$webCommand = if ($Production) { 'preview' } else { 'dev' }
if ($Production -and !(Test-Path -LiteralPath (Join-Path $projectPath 'dist/index.html'))) {
  & npm.cmd run build
  if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
}
if ($FrontendOnly) { & npm.cmd run $webCommand -- --port 5173 --strictPort; exit $LASTEXITCODE }
if (!(Test-Path -LiteralPath (Join-Path $projectPath 'runtime/farm.sqlite3'))) {
  & $pythonExe scripts/db_init.py
  if ($LASTEXITCODE -ne 0) { throw 'Database initialization failed.' }
}
if (!$WithoutModel -and (Test-Path -LiteralPath (Join-Path $projectPath 'runtime/model-api-key.txt')) -and (Test-Path -LiteralPath (Join-Path $toolPath 'llama-b11960-vulkan/llama-server.exe'))) {
  & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'start-local-model.ps1')
  if ($LASTEXITCODE -ne 0) { throw 'Local model startup failed. Use -WithoutModel to start with explicit model-unavailable state.' }
}
if ($BackendOnly) { & $pythonExe -m backend; exit $LASTEXITCODE }
$backendProcess = $null
try {
  try { $health = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/health' -TimeoutSec 3 }
  catch { $health = $null }
  if ($health -and $health.database -ne 'sqlite') { throw 'Port 8000 is occupied by an unrecognized service.' }
  if (!$health) {
    $backendProcess = Start-Process -FilePath $pythonExe -ArgumentList '-m','backend' -WorkingDirectory $projectPath -WindowStyle Hidden -PassThru
    $ready = $false
    for ($attempt=0; $attempt -lt 30; $attempt++) {
      if ($backendProcess.HasExited) { throw 'Backend exited during startup.' }
      try { $health=Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/health' -TimeoutSec 1; $ready=$health.status -eq 'ok' } catch {}
      if ($ready) { break }
      Start-Sleep -Milliseconds 300
    }
    if (!$ready) { throw 'Backend did not become ready.' }
  }
  Write-Output 'Open http://127.0.0.1:5173 . Ctrl+C stops this frontend and any backend started by this script.'
  & npm.cmd run $webCommand -- --port 5173 --strictPort
}
finally { if ($backendProcess -and !$backendProcess.HasExited) { Stop-Process -Id $backendProcess.Id } }
