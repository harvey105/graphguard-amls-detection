param(
    [switch]$Full,
    [ValidateRange(1, 3)][int]$Runs = 2,
    [switch]$SkipTests,
    [string]$DriverMemory,
    [ValidateRange(1, 2)][int]$Parallelism = 2
)

# Run Hoang's existing IBM LPA, then independently verify the exported CSVs.
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $repo '.venv\Scripts\python.exe'
$scope = if ($Full) { 'full' } else { 'sample' }
if (-not $DriverMemory) { $DriverMemory = if ($Full) { '6g' } else { '4g' } }
$inputDir = if ($Full) { 'data\processed\ibm_aml' } else { 'data\processed\sample\ibm_aml' }
$checkDir = Join-Path $repo ('results\ibm_aml\task4_check\' + $scope)
$log = Join-Path $repo 'results\ibm_aml\check_task4.log'
$exitCode = 0
$transcribing = $false
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'

function Invoke-CheckPython {
    param([string[]]$Arguments)
    $ErrorActionPreference = 'Continue'
    Write-Host ('Checking: python ' + ($Arguments -join ' '))
    & $python @Arguments 2>&1 | ForEach-Object {
        $line = if ($_ -is [System.Management.Automation.ErrorRecord]) { $_.Exception.Message } else { [string]$_ }
        if (-not [string]::IsNullOrWhiteSpace($line)) { Write-Host $line }
    }
    if ($LASTEXITCODE -ne 0) { throw "Task 4 check failed (exit $LASTEXITCODE)" }
}

Push-Location $repo
try {
    if (-not (Test-Path -LiteralPath $python)) { throw 'Run scripts\setup_windows.ps1 first.' }
    New-Item -ItemType Directory -Path $checkDir -Force | Out-Null
    Start-Transcript -LiteralPath $log -Force | Out-Null
    $transcribing = $true
    $runtime = @'
import importlib.metadata as metadata
import os, re, subprocess, sys
from src.common.windows_runtime import prepare_windows_spark
if os.name != 'nt' or sys.version_info[:2] != (3, 12):
    raise RuntimeError('Native Windows Python 3.12 required')
prepare_windows_spark()
result = subprocess.run([os.path.join(os.environ['JAVA_HOME'], 'bin', 'java.exe'), '-version'], capture_output=True, text=True, check=True)
if not re.search(r'version .17[.]', result.stderr):
    raise RuntimeError('JDK 17 required')
for package, expected in [('pyspark', '3.5.1'), ('graphframes-py', '0.12.2')]:
    if metadata.version(package) != expected:
        raise RuntimeError(package + ' must be ' + expected)
print('[PASS] Native Windows runtime for Task 4')
'@
    Invoke-CheckPython -Arguments @('-c', $runtime)
    Invoke-CheckPython -Arguments @('-m', 'pip', 'check')
    if (-not $SkipTests) {
        Invoke-CheckPython -Arguments @('-m', 'unittest', 'tests.test_task4_checker', '-v')
    }
    for ($run = 1; $run -le $Runs; $run++) {
        $outputDir = Join-Path $checkDir ('run_' + $run)
        $checkpoint = 'checkpoints\task4_check\' + $scope + '\run_' + $run
        # Remove only the known check-run folder, so old CSVs cannot masquerade as a new run.
        if (Test-Path -LiteralPath $outputDir) { Remove-Item -LiteralPath $outputDir -Recurse -Force }
        Invoke-CheckPython -Arguments @('-m', 'src.ibm_aml.community_detection', '--input-dir', $inputDir,
            '--output-dir', $outputDir, '--checkpoint-dir', $checkpoint, '--max-iter', '5',
            '--driver-memory', $DriverMemory, '--parallelism', [string]$Parallelism)
        $arguments = @('-m', 'src.ibm_aml.verify_communities', '--input-dir', $inputDir, '--output-dir', $outputDir,
            '--lpa-max-iter', '5', '--lpa-driver-memory', $DriverMemory, '--lpa-parallelism', [string]$Parallelism,
            '--require-run-evidence')
        if ($run -gt 1) { $arguments += @('--compare-dir', (Join-Path $checkDir 'run_1')) }
        Invoke-CheckPython -Arguments $arguments
    }
    Write-Host "[PASS] IBM Task 4 $($scope): $Runs checked run(s). See per-run task4_check.json."
} catch {
    Write-Host "[FAIL] $($_.Exception.Message)"
    $exitCode = 1
} finally {
    if ($transcribing) { Stop-Transcript | Out-Null }
    Pop-Location
}
exit $exitCode
