param([switch]$Restart)
$ErrorActionPreference='Stop'
$projectPath=Split-Path -Parent $PSScriptRoot
$toolPath=Join-Path (Split-Path -Parent $projectPath) '.tools'
$runtimePath=Join-Path $projectPath 'runtime'
$executable=Join-Path $toolPath 'llama-b11960-vulkan/llama-server.exe'
$modelPath=Join-Path $toolPath 'models/Qwen3-4B/Qwen3-4B-Q4_K_M.gguf'
$keyPath=Join-Path $runtimePath 'model-api-key.txt'
$pidPath=Join-Path $runtimePath 'local-model.pid'
foreach($required in @($executable,$modelPath,$keyPath)){if(!(Test-Path -LiteralPath $required)){throw "Missing deployment file: $required"}}
if(Test-Path -LiteralPath $pidPath){
  $previousId=[int](Get-Content -LiteralPath $pidPath -Raw)
  $previous=Get-Process -Id $previousId -ErrorAction SilentlyContinue
  if($previous){
    if($previous.Path -ne $executable){throw 'Stored process ID belongs to another executable; refusing to stop it.'}
    if(!$Restart){Write-Output "Local model already running (PID $previousId)";exit 0}
    Stop-Process -Id $previousId
    $previous.WaitForExit(10000) | Out-Null
  }
}
$logPath=Join-Path $runtimePath 'logs'
New-Item -ItemType Directory -Path $logPath -Force | Out-Null
$arguments=@('-m',('"'+$modelPath+'"'),'-ngl','99','-c','12288','-np','1','--host','127.0.0.1','--port','8081','--alias','qwen3-4b-local','--reasoning','off','-t','8','--api-key-file',('"'+$keyPath+'"'),'--cors-origins','http://127.0.0.1:8000','--no-webui')
$modelProcess=Start-Process -FilePath $executable -ArgumentList $arguments -WorkingDirectory (Split-Path -Parent $executable) -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logPath 'model-stdout.log') -RedirectStandardError (Join-Path $logPath 'model-stderr.log')
$modelProcess.Id | Set-Content -LiteralPath $pidPath
Write-Output "Local model starting on 127.0.0.1:8081 (PID $($modelProcess.Id))"
