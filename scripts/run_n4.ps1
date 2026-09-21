$ErrorActionPreference = 'Continue'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $repo '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) { throw 'Run scripts\setup_windows.ps1 first.' }
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'

Push-Location $repo
try {
    & $python -m src.motif.toy_cycle
    if ($LASTEXITCODE -ne 0) { throw 'N4 toy motif script failed.' }
    & $python scripts\run_n4_notebook.py
    if ($LASTEXITCODE -ne 0) { throw 'N4 notebook execution failed.' }
} finally {
    Pop-Location
}
