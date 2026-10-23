param(
    [switch]$ArtifactsOnly,
    [switch]$Refresh,
    [ValidateSet('4g', '5g')][string]$MaxHeap = '5g'
)

# Full-data acceptance. Development samples never satisfy this gate.
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $repo '.venv\Scripts\python.exe'
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
$env:OPENBLAS_NUM_THREADS = '1'
$env:OMP_NUM_THREADS = '1'
$previousHeapCeiling = $env:GRAPHGUARD_MAX_HEAP
$env:GRAPHGUARD_MAX_HEAP = $MaxHeap
$exitCode = 0

function Invoke-ProjectPython {
    param([string[]]$Arguments)
    $ErrorActionPreference = 'Continue'
    & $python @Arguments 2>&1 | ForEach-Object {
        $line = if ($_ -is [System.Management.Automation.ErrorRecord]) { $_.Exception.Message } else { [string]$_ }
        if (-not [string]::IsNullOrWhiteSpace($line)) { Write-Host $line }
    }
    if ($LASTEXITCODE -ne 0) { throw "Full project check failed (exit $LASTEXITCODE): $($Arguments -join ' ')" }
}

Push-Location $repo
try {
    if (-not (Test-Path -LiteralPath $python)) { throw 'Run scripts\setup_windows.ps1 first.' }
    if ($Refresh -and $ArtifactsOnly) { throw '-Refresh executes full notebooks; omit -ArtifactsOnly.' }
    Invoke-ProjectPython -Arguments @('-m', 'pip', 'check')
    Invoke-ProjectPython -Arguments @('-m', 'unittest', 'tests.test_hardware_guard.PolicyTests',
        'tests.test_notebook_checkpoint', 'tests.test_ibm_motif_outputs', 'tests.test_paysim_motif_outputs',
        'tests.test_run_evidence', 'tests.test_ibm_cycle_visual', 'tests.test_project_audit.ProjectAuditTests',
        'tests.test_project_audit.FullSystemPolicyTests', 'tests.test_project_audit.FullDegreeComparisonTests', '-v')
    if ($Refresh) {
        Invoke-ProjectPython -Arguments @('-m', 'unittest', 'tests.test_hardware_guard.NativeGuardTests', '-v')
        Invoke-ProjectPython -Arguments @('-m', 'unittest', 'tests.test_project_audit.NativeFullSystemTests', '-v')
        # Smaller IBM first; never start the next notebook until the runner exits.
        Invoke-ProjectPython -Arguments @('scripts\run_n4_notebook.py', '--notebook',
            'notebooks\IBM_full_system.ipynb', '--cell-timeout', '7200')
        Invoke-ProjectPython -Arguments @('scripts\run_n4_notebook.py', '--notebook',
            'notebooks\PaySIM_full_system.ipynb', '--cell-timeout', '7200')
        Invoke-ProjectPython -Arguments @('-m', 'src.comparison.degree_distribution')
    }
    Invoke-ProjectPython -Arguments @('-m', 'src.common.project_audit', '--full-system')
    Invoke-ProjectPython -Arguments @('-m', 'src.comparison.degree_distribution', '--verify-only')
    if (-not $ArtifactsOnly) {
        if (-not $Refresh) {
            Invoke-ProjectPython -Arguments @('-m', 'unittest', 'tests.test_hardware_guard.NativeGuardTests', '-v')
            Invoke-ProjectPython -Arguments @('-m', 'unittest', 'tests.test_project_audit.NativeFullSystemTests', '-v')
        }
        Invoke-ProjectPython -Arguments @('-m', 'unittest', 'tests.test_project_audit.NativeAlgorithmTests', '-v')
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'check_task3.ps1') -MaxHeap $MaxHeap
        if ($LASTEXITCODE -ne 0) { throw "Task 3 full query/evidence gate failed (exit $LASTEXITCODE)" }
    }
    Write-Host '[PASS] Full project gate completed; predictive quality is reported separately.'
} catch {
    Write-Host "[FAIL] $($_.Exception.Message)"
    $exitCode = 1
} finally {
    $env:GRAPHGUARD_MAX_HEAP = $previousHeapCeiling
    Pop-Location
}
exit $exitCode
