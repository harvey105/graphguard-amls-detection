# Full PaySim and IBM Task 3 delivery gate, using native Windows Python and Java.
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $repo '.venv\Scripts\python.exe'
$scratch = Join-Path $repo ('results\.task3-check-' + [guid]::NewGuid().ToString('N'))
$log = Join-Path $repo 'results\ibm_aml\check_task3.log'
$transcribing = $false
$exitCode = 0
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'

function Invoke-CheckPython {
    param([string[]]$Arguments)
    # PowerShell 5.1 treats native stderr (including successful unittest output)
    # as ErrorRecord objects. Stream both channels to the host for transcript
    # capture, and use the process exit code to determine success.
    $ErrorActionPreference = 'Continue'
    Write-Host ('Checking: python ' + ($Arguments -join ' '))
    & $python @Arguments 2>&1 | ForEach-Object {
        $line = if ($_ -is [System.Management.Automation.ErrorRecord]) { $_.Exception.Message } else { [string]$_ }
        if (-not [string]::IsNullOrWhiteSpace($line)) { Write-Host $line }
    }
    if ($LASTEXITCODE -ne 0) {
        throw "Python check failed (exit $LASTEXITCODE): $($Arguments -join ' ')"
    }
}

Push-Location $repo
try {
    if (-not (Test-Path -LiteralPath $python)) { throw 'Run scripts\setup_windows.ps1 first.' }
    New-Item -ItemType Directory -Path (Split-Path $log) -Force | Out-Null
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
    raise RuntimeError('JDK 17 required: ' + result.stderr)
for package, expected in [('pyspark', '3.5.1'), ('graphframes-py', '0.12.2')]:
    if metadata.version(package) != expected:
        raise RuntimeError(package + ' must be ' + expected)
print('[PASS] Windows Python ' + sys.version.split()[0] + '; ' + result.stderr.splitlines()[0])
'@
    Invoke-CheckPython -Arguments @('-c', $runtime)
    Invoke-CheckPython -Arguments @('-m', 'pip', 'check')
    Invoke-CheckPython -Arguments @('-m', 'src.ibm_aml.verify_motif_outputs')
    Invoke-CheckPython -Arguments @('-m', 'src.paysim.verify_motif_outputs')
    Invoke-CheckPython -Arguments @('-m', 'unittest', 'tests.test_task3_motifs', 'tests.test_ibm_motif_outputs',
        'tests.test_paysim_motif_outputs', 'tests.test_run_evidence', 'tests.test_ibm_cycle_visual', '-v')
    Invoke-CheckPython -Arguments @('tests\test_ibm_aml_etl.py')
    Invoke-CheckPython -Arguments @('-m', 'src.ibm_aml.motif_finding', '--output-dir', $scratch)
    Invoke-CheckPython -Arguments @('-m', 'src.ibm_aml.verify_motif_outputs', '--output-dir', $scratch, '--compare-dir', 'results\ibm_aml', '--require-evidence')
    $evidenceDir = Join-Path $repo 'results\motif\check_runs\ibm'
    New-Item -ItemType Directory -Path $evidenceDir -Force | Out-Null
    Copy-Item -Path (Join-Path $scratch '*') -Destination $evidenceDir -Force
    $paySimEvidenceDir = Join-Path $repo 'results\motif\check_runs\paysim'
    Invoke-CheckPython -Arguments @('-m', 'src.paysim.motif_finding', '--output-dir', $paySimEvidenceDir)
    Invoke-CheckPython -Arguments @('-m', 'src.paysim.verify_motif_outputs', '--output-dir', $paySimEvidenceDir,
        '--compare-dir', 'results\paysim', '--require-evidence')
    Write-Host '[PASS] Full PaySim and IBM Task 3 delivery check completed.'
} catch {
    Write-Host "[FAIL] $($_.Exception.Message)"
    $exitCode = 1
} finally {
    if (Test-Path -LiteralPath $scratch) { Remove-Item -LiteralPath $scratch -Recurse -Force }
    if ($transcribing) { Stop-Transcript | Out-Null }
    Pop-Location
}
Write-Host "Check log: $log"
exit $exitCode
