[CmdletBinding()]
param(
    [ValidateSet('All', 'PaySim', 'IbmAml')]
    [string]$Dataset = 'All',
    [ValidateSet('PS_20174392719_1491204439457_log.csv', 'HI-Small_Trans.csv', 'HI-Small_accounts.csv', 'HI-Small_Patterns.txt')]
    [string]$FileName,
    [switch]$VerifyOnly,
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $repo '.venv\Scripts\python.exe'
$downloadRoot = Join-Path $repo 'data\raw\.downloads'
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'

$datasets = @(
    [pscustomobject]@{
        Key = 'PaySim'
        Handle = 'ealaxi/paysim1'
        FileName = 'PS_20174392719_1491204439457_log.csv'
        Destination = Join-Path $repo 'data\raw\paysim\PS_20174392719_1491204439457_log.csv'
        MinimumBytes = 450MB
        ExpectedRows = 6362620L
        Header = @(
            'step', 'type', 'amount', 'nameOrig', 'oldbalanceOrg',
            'newbalanceOrig', 'nameDest', 'oldbalanceDest',
            'newbalanceDest', 'isFraud', 'isFlaggedFraud'
        )
    },
    [pscustomobject]@{
        Key = 'IbmAml'
        Handle = 'ealtman2019/ibm-transactions-for-anti-money-laundering-aml'
        FileName = 'HI-Small_Trans.csv'
        Destination = Join-Path $repo 'data\raw\ibm_aml\HI-Small_Trans.csv'
        MinimumBytes = 400MB
        ExpectedRows = 5078345L
        Header = @(
            'Timestamp', 'From Bank', 'Account', 'To Bank', 'Account',
            'Amount Received', 'Receiving Currency', 'Amount Paid',
            'Payment Currency', 'Payment Format', 'Is Laundering'
        )
    },
    [pscustomobject]@{
        Key = 'IbmAml'
        Handle = 'ealtman2019/ibm-transactions-for-anti-money-laundering-aml'
        FileName = 'HI-Small_accounts.csv'
        Destination = Join-Path $repo 'data\raw\ibm_aml\HI-Small_accounts.csv'
        MinimumBytes = 30MB
        ExpectedRows = 518581L
        Header = @('Bank Name', 'Bank ID', 'Account Number', 'Entity ID', 'Entity Name')
    },
    [pscustomobject]@{
        Key = 'IbmAml'
        Handle = 'ealtman2019/ibm-transactions-for-anti-money-laundering-aml'
        FileName = 'HI-Small_Patterns.txt'
        Destination = Join-Path $repo 'data\raw\ibm_aml\HI-Small_Patterns.txt'
        MinimumBytes = 300KB
        ExpectedCycleBlocks = 54
        ExpectedAttemptBlocks = 370
    }
)

if ($Dataset -ne 'All') {
    $datasets = @($datasets | Where-Object { $_.Key -eq $Dataset })
}
if ($FileName) {
    $datasets = @($datasets | Where-Object { $_.FileName -eq $FileName })
    if ($datasets.Count -eq 0) {
        throw "File $FileName does not belong to dataset $Dataset."
    }
}

function Test-GraphGuardDataset {
    param(
        [Parameter(Mandatory = $true)]
        [pscustomobject]$Spec,
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Missing dataset file: $Path"
    }

    $file = Get-Item -LiteralPath $Path
    if ($file.Length -lt $Spec.MinimumBytes) {
        throw "Dataset is too small and may be incomplete: $Path ($($file.Length) bytes)"
    }

    if ($Spec.PSObject.Properties.Name -contains 'ExpectedCycleBlocks') {
        $reader = [System.IO.File]::OpenText($Path)
        try {
            [long]$cycleBlocks = 0
            [long]$attemptBlocks = 0
            while ($null -ne ($line = $reader.ReadLine())) {
                if ($line.StartsWith('BEGIN LAUNDERING ATTEMPT')) { $attemptBlocks++ }
                if ($line.StartsWith('BEGIN LAUNDERING ATTEMPT - CYCLE')) { $cycleBlocks++ }
            }
        } finally {
            $reader.Dispose()
        }
        if ($cycleBlocks -ne $Spec.ExpectedCycleBlocks -or $attemptBlocks -ne $Spec.ExpectedAttemptBlocks) {
            throw "Unexpected IBM pattern counts in $Path. Expected $($Spec.ExpectedCycleBlocks) CYCLE / $($Spec.ExpectedAttemptBlocks) attempts; got $cycleBlocks / $attemptBlocks."
        }
        Write-Host "[PASS] $($Spec.FileName): $cycleBlocks CYCLE blocks, $attemptBlocks attempts"
        return
    }

    $reader = [System.IO.File]::OpenText($Path)
    try {
        $headerLine = $reader.ReadLine()
        if ($null -eq $headerLine) {
            throw "Dataset is empty: $Path"
        }

        $actualHeader = @(
            $headerLine.TrimStart([char]0xFEFF).Split(',') |
                ForEach-Object { $_.Trim().Trim([char]34) }
        )
        $expectedHeader = [string]::Join(',', $Spec.Header)
        if ([string]::Join(',', $actualHeader) -cne $expectedHeader) {
            throw "Unexpected CSV header in $Path. Expected: $expectedHeader"
        }

        [long]$rowCount = 0
        while ($null -ne $reader.ReadLine()) {
            $rowCount++
        }
    } finally {
        $reader.Dispose()
    }

    if ($rowCount -ne $Spec.ExpectedRows) {
        throw "Unexpected row count in $Path. Expected $($Spec.ExpectedRows), got $rowCount."
    }

    $sizeMiB = [Math]::Round($file.Length / 1MB, 1)
    Write-Host "[PASS] $($Spec.Key): $rowCount rows, $sizeMiB MiB"
}

if (-not $VerifyOnly -and -not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw 'Windows .venv is missing. Run scripts\setup_windows.ps1 first.'
}

$downloadCode = @'
import sys
import shutil
import zipfile
from pathlib import Path

import kagglehub

handle, file_name, output_dir, minimum_bytes = sys.argv[1:5]
destination = Path(output_dir) / file_name

# kagglehub 1.0.2 on Windows can save a server-side ZIP wrapper with the
# requested file name. Reuse a complete staged file after an interrupted run.
if not destination.exists() or destination.stat().st_size < int(minimum_bytes):
    destination.unlink(missing_ok=True)
    destination = Path(kagglehub.dataset_download(
        handle,
        path=file_name,
        output_dir=output_dir,
        force_download=True,
    ))

if zipfile.is_zipfile(destination):
    with zipfile.ZipFile(destination) as archive:
        matches = [
            member for member in archive.infolist()
            if not member.is_dir() and Path(member.filename).name == file_name
        ]
        if len(matches) != 1:
            raise RuntimeError(f'Expected one {file_name} member, found {len(matches)}')
        expanded = destination.with_name(destination.name + '.expanded')
        with archive.open(matches[0]) as source, expanded.open('wb') as target:
            shutil.copyfileobj(source, target)
    destination.unlink()
    expanded.replace(destination)

print(destination)
'@

$failures = [System.Collections.Generic.List[string]]::new()
foreach ($spec in $datasets) {
    if ($VerifyOnly) {
        try {
            Test-GraphGuardDataset -Spec $spec -Path $spec.Destination
        } catch {
            $failures.Add("$($spec.Key): $($_.Exception.Message)")
            Write-Host "[FAIL] $($spec.Key): $($_.Exception.Message)" -ForegroundColor Red
        }
        continue
    }

    if ((Test-Path -LiteralPath $spec.Destination -PathType Leaf) -and -not $Force) {
        try {
            Test-GraphGuardDataset -Spec $spec -Path $spec.Destination
            Write-Host "[SKIP] $($spec.Key) is already complete."
            continue
        } catch {
            Write-Warning "Existing $($spec.Key) file is invalid; downloading a clean copy. $($_.Exception.Message)"
        }
    }

    $temporaryDirectory = Join-Path $downloadRoot $spec.Key
    if ($Force -and (Test-Path -LiteralPath $temporaryDirectory)) {
        Remove-Item -LiteralPath $temporaryDirectory -Recurse -Force
    }
    New-Item -ItemType Directory -Path $temporaryDirectory -Force | Out-Null

    Write-Host "[DOWNLOAD] $($spec.Key) / $($spec.FileName)"
    & $python -c $downloadCode $spec.Handle $spec.FileName $temporaryDirectory $spec.MinimumBytes
    if ($LASTEXITCODE -ne 0) {
        throw "Kaggle download failed for $($spec.Key)."
    }

    $downloaded = Join-Path $temporaryDirectory $spec.FileName
    Test-GraphGuardDataset -Spec $spec -Path $downloaded
    New-Item -ItemType Directory -Path (Split-Path $spec.Destination -Parent) -Force | Out-Null
    Move-Item -LiteralPath $downloaded -Destination $spec.Destination -Force
    Remove-Item -LiteralPath $temporaryDirectory -Recurse -Force
    Test-GraphGuardDataset -Spec $spec -Path $spec.Destination
}

if ($failures.Count -gt 0) {
    throw "Dataset verification failed for $($failures.Count) dataset(s)."
}

if (Test-Path -LiteralPath $downloadRoot) {
    $remaining = @(Get-ChildItem -LiteralPath $downloadRoot -Force)
    if ($remaining.Count -eq 0) {
        Remove-Item -LiteralPath $downloadRoot -Force
    }
}

Write-Host 'All selected datasets passed verification.' -ForegroundColor Green
