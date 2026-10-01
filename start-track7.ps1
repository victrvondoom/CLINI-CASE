param([switch]$SQLite, [switch]$AI)
$ErrorActionPreference = 'Stop'
$taskPython = Join-Path $PSScriptRoot 'backend\.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $taskPython)) { $taskPython = (Get-Command python -ErrorAction Stop).Source }
$demoArgs = @((Join-Path $PSScriptRoot 'backend\scripts\track7_demo.py'), '--keep-running', '--open')
if ($SQLite) { $demoArgs += '--sqlite' }
if ($AI) { $demoArgs += '--ai' }
& $taskPython @demoArgs
exit $LASTEXITCODE
