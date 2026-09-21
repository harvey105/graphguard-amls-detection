param()

$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$venv = Join-Path $repo '.venv'
$python = Join-Path $venv 'Scripts\python.exe'
$hadoop = Join-Path $venv 'hadoop'
$winutils = Join-Path $hadoop 'bin\winutils.exe'
$hadoopDll = Join-Path $hadoop 'bin\hadoop.dll'
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'

function Assert-Hash($Path, $Expected) {
    $actual = (Get-FileHash -Algorithm SHA256 -Path $Path).Hash
    if ($actual -ne $Expected) {
        throw "SHA256 mismatch for $Path. Expected $Expected, got $actual"
    }
}

if (-not (Test-Path $python)) {
    $py = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($py) {
        & $py.Source -3.12 -m venv $venv
    } else {
        $fallback = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'
        if (-not (Test-Path $fallback)) {
            throw 'Python 3.12 Windows was not found. Install it with winget install --id Python.Python.3.12 --exact.'
        }
        & $fallback -m venv $venv
    }
    if ($LASTEXITCODE -ne 0) { throw 'Could not create Windows .venv.' }
}

$version = & $python --version 2>&1
if ($LASTEXITCODE -ne 0 -or $version -notmatch 'Python 3\.12\.') {
    throw ".venv must contain Windows Python 3.12. Found: $version"
}

$javaHome = [Environment]::GetEnvironmentVariable('JAVA_HOME', 'Machine')
if (-not $javaHome) { $javaHome = [Environment]::GetEnvironmentVariable('JAVA_HOME', 'User') }
if (-not $javaHome) { $javaHome = $env:JAVA_HOME }
$java = if ($javaHome) { Join-Path $javaHome 'bin\java.exe' } else { '' }
if (-not (Test-Path $java)) {
    throw 'JDK 17 Windows/JAVA_HOME was not found. Install it with winget install --id EclipseAdoptium.Temurin.17.JDK --exact.'
}
$javaVersion = (Get-Item $java).VersionInfo.ProductVersion
if ($javaVersion -notmatch '^17\.') {
    throw "JDK 17 is required. Found: $javaVersion"
}

Write-Host "Python: $version"
Write-Host "Java: $javaVersion"
& $python -m pip install --disable-pip-version-check --quiet -r (Join-Path $repo 'requirements.txt')
if ($LASTEXITCODE -ne 0) { throw 'pip install failed.' }
& $python -m pip check
if ($LASTEXITCODE -ne 0) { throw 'pip check failed.' }

# PySpark bundles Hadoop 3.3.4. On Windows it also needs matching native tools.
# Pin the archive and binary hashes so the team gets the same files.
$zipHash = 'F89C4E4EB2415F87EADE9E5A803D29D405BF91212DF19AC4B5F32A9833C45392'
$winutilsHash = 'C3493FAB5987BFE9A7713298C80031747062D98076AFAD009B8020B7C6B79E90'
$dllHash = '69771305A2476E7DFCC0B86C084FDB04A1A854691390D0B2F4C037793CE607B3'
if (-not ((Test-Path $winutils) -and (Test-Path $hadoopDll))) {
    $archive = Join-Path $venv 'hadoop-win-utils.zip'
    $url = 'https://github.com/notepass/hadoop-native-win-libs/releases/download/rel/release-3.3.4/hadoop-win-utils.zip'
    try {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -Uri $url -OutFile $archive -UseBasicParsing
        Assert-Hash $archive $zipHash
        New-Item -ItemType Directory -Path $hadoop -Force | Out-Null
        Expand-Archive -Path $archive -DestinationPath $hadoop -Force
    } finally {
        Remove-Item $archive -ErrorAction SilentlyContinue
    }
}
Assert-Hash $winutils $winutilsHash
Assert-Hash $hadoopDll $dllHash

Write-Host 'Windows environment is ready.'
Write-Host 'Next: powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\download_datasets.ps1'
Write-Host 'N4 demo: powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_n4.ps1'
