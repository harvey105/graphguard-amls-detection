param(
    [switch]$ArtifactsOnly,
    [switch]$Refresh,
    [string]$SignalRoot = 'results\project_check\signals',
    [ValidateSet('4g', '5g', '6g')][string]$MaxHeap = '5g'
)

# Run bounded preflight first; preserve the original Task 3 gate after it passes.
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $repo '.venv\Scripts\python.exe'
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
$env:OPENBLAS_NUM_THREADS = '1'
$env:OMP_NUM_THREADS = '1'
$exitCode = 0
$previousHeapCeiling = $env:GRAPHGUARD_MAX_HEAP
$env:GRAPHGUARD_MAX_HEAP = $MaxHeap

function Invoke-ProjectPython {
    param([string[]]$Arguments)
    $ErrorActionPreference = 'Continue'
    & $python @Arguments 2>&1 | ForEach-Object {
        $line = if ($_ -is [System.Management.Automation.ErrorRecord]) { $_.Exception.Message } else { [string]$_ }
        if (-not [string]::IsNullOrWhiteSpace($line)) { Write-Host $line }
    }
    if ($LASTEXITCODE -ne 0) { throw "Project check failed (exit $LASTEXITCODE): $($Arguments -join ' ')" }
}

Push-Location $repo
try {
    if (-not (Test-Path -LiteralPath $python)) { throw 'Run scripts\setup_windows.ps1 first.' }
    if ($Refresh -and $ArtifactsOnly) { throw '-Refresh runs algorithms; omit -ArtifactsOnly.' }
    $signalPath = if ([System.IO.Path]::IsPathRooted($SignalRoot)) { $SignalRoot } else { Join-Path $repo $SignalRoot }
    if ($Refresh) {
        # Reject conflicting outputs before starting any protected heavy work.
        foreach ($dataset in @('paysim', 'ibm_aml')) {
            foreach ($branch in @('centrality', 'community')) {
                $output = Join-Path (Join-Path $signalPath $dataset) $branch
                if ((Test-Path -LiteralPath $output) -and
                    ((-not (Test-Path -LiteralPath $output -PathType Container)) -or
                     @(Get-ChildItem -LiteralPath $output -Force).Count -gt 0)) {
                    throw "Use a new/empty -SignalRoot; existing experiment: $output"
                }
            }
        }
    }
    Invoke-ProjectPython -Arguments @('-m', 'pip', 'check')
    # No native guard admission/Spark tests here: use their dedicated heavy gates.
    Invoke-ProjectPython -Arguments @('-m', 'unittest', 'tests.test_hardware_guard.PolicyTests',
        'tests.test_notebook_checkpoint', 'tests.test_ibm_motif_outputs', 'tests.test_paysim_motif_outputs',
        'tests.test_run_evidence', 'tests.test_ibm_cycle_visual', 'tests.test_project_audit.ProjectAuditTests', '-v')
    if ($Refresh) {
        Invoke-ProjectPython -Arguments @('-m', 'unittest', 'tests.test_hardware_guard.NativeGuardTests.test_small_profile_installs_lower_os_cap', '-v')
        Invoke-ProjectPython -Arguments @('-m', 'unittest', 'tests.test_project_audit.NativeAlgorithmTests', '-v')
        Invoke-ProjectPython -Arguments @('-m', 'src.paysim.graph_analysis', '--sample')
        Invoke-ProjectPython -Arguments @('-m', 'src.paysim.metrics')
        Invoke-ProjectPython -Arguments @('-m', 'src.ibm_aml.metrics')
        Invoke-ProjectPython -Arguments @('-m', 'src.paysim.community_detection', '--check-stability')
        Invoke-ProjectPython -Arguments @('-m', 'src.ibm_aml.community_detection')
        foreach ($dataset in @('paysim', 'ibm_aml')) {
            foreach ($branch in @('centrality', 'community')) {
                $output = Join-Path (Join-Path $signalPath $dataset) $branch
                Invoke-ProjectPython -Arguments @('-m', 'src.common.project_audit', '--signals', $branch,
                    '--dataset', $dataset, '--output-dir', $output)
            }
        }
    }
    Invoke-ProjectPython -Arguments @('-m', 'src.common.project_audit', '--signals-root', $signalPath)
    if (-not $ArtifactsOnly) {
        if (-not $Refresh) {
            Invoke-ProjectPython -Arguments @('-m', 'unittest', 'tests.test_hardware_guard.NativeGuardTests', '-v')
            Invoke-ProjectPython -Arguments @('-m', 'unittest', 'tests.test_project_audit.NativeAlgorithmTests', '-v')
        }
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'check_task3.ps1') -MaxHeap $MaxHeap
        if ($LASTEXITCODE -ne 0) { throw "Original Task 3 runtime gate failed (exit $LASTEXITCODE)" }
    }
} catch {
    Write-Host "[FAIL] $($_.Exception.Message)"
    $exitCode = 1
} finally {
    $env:GRAPHGUARD_MAX_HEAP = $previousHeapCeiling
    Pop-Location
}
exit $exitCode
