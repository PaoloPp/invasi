[CmdletBinding()]
param(
    [switch]$SkipInstall
)

$ErrorActionPreference = 'Stop'

function Write-Step {
    param([string]$Message)
    Write-Host "`n==> $Message" -ForegroundColor Cyan
}

function Assert-Command {
    param(
        [string]$Command,
        [string]$InstallHint
    )

    if (-not (Get-Command $Command -ErrorAction SilentlyContinue)) {
        throw "Required command '$Command' was not found. $InstallHint"
    }
}

function Install-PythonIfMissing {
    param(
        [string]$MinVersion = '3.10.0'
    )

    try {
        Resolve-PythonLauncher | Out-Null
        return
    } catch {
        Write-Host "Python $MinVersion+ was not detected. Attempting automatic installation via winget..." -ForegroundColor Yellow
    }

    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        throw @"
Python is required but was not found, and winget is not available for automatic install.
Install Python from https://www.python.org/downloads/windows/ and then rerun this script.
"@
    }

    & winget install --id Python.Python.3.12 --source winget --accept-package-agreements --accept-source-agreements --silent --disable-interactivity
    if ($LASTEXITCODE -ne 0) {
        throw 'Automatic Python installation failed. Please install Python manually and rerun this script.'
    }
}

function Ensure-VCRuntime {
    Write-Step 'Ensuring Microsoft VC++ runtime is installed (required by matplotlib/kiwisolver)'

    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        Write-Host 'winget not available; skipping VC++ runtime auto-install. If DLL import errors persist, install Microsoft Visual C++ Redistributable (x64).' -ForegroundColor Yellow
        return
    }

    & winget install --id Microsoft.VCRedist.2015+.x64 --source winget --accept-package-agreements --accept-source-agreements --silent --disable-interactivity
    if ($LASTEXITCODE -ne 0) {
        Write-Host 'VC++ runtime installation command returned a non-zero exit code. Continuing, but DLL import issues may persist.' -ForegroundColor Yellow
    }
}

function Resolve-PythonLauncher {
    $candidates = @(
        @{ Name = 'python'; Args = @() },
        @{ Name = 'py'; Args = @('-3') }
    )

    foreach ($candidate in $candidates) {
        if (-not (Get-Command $candidate.Name -ErrorAction SilentlyContinue)) {
            continue
        }

        $versionOutput = (& $candidate.Name @($candidate.Args + @('--version')) 2>&1 | Out-String).Trim()
        $exitCode = $LASTEXITCODE

        if ($exitCode -eq 0 -and $versionOutput -match '^Python\s+\d+\.\d+\.\d+') {
            return $candidate
        }
    }

    throw @'
Python 3.10+ was not found.
Install Python from https://www.python.org/downloads/windows/ and enable:
 - "Add python.exe to PATH"
 - "Install launcher for all users (py)"
If Windows shows a Microsoft Store alias for python, disable it in:
Settings -> Apps -> App execution aliases.
'@
}

$repoRoot = Split-Path -Parent $PSScriptRoot
$appDir = Join-Path $repoRoot 'invasi-app'
$venvDir = Join-Path $repoRoot '.venv'
$venvPython = Join-Path $venvDir 'Scripts/python.exe'
$requirementsPath = Join-Path $appDir 'requirements.txt'
$secretPath = Join-Path $appDir 'secret.py'
$instancePath = Join-Path $appDir 'instance'

Write-Step 'Checking prerequisites'
Install-PythonIfMissing
$pythonLauncher = Resolve-PythonLauncher
$pythonVersionRaw = (& $pythonLauncher.Name @($pythonLauncher.Args + @('-c', "import sys; print('.'.join(map(str, sys.version_info[:3])))")) 2>&1 | Out-String).Trim()
$exitCode = $LASTEXITCODE
if ($exitCode -ne 0 -or [string]::IsNullOrWhiteSpace($pythonVersionRaw)) {
    throw 'Unable to detect the installed Python version. Please verify your Python installation and PATH configuration.'
}

$pythonVersion = [Version]$pythonVersionRaw
if ($pythonVersion -lt [Version]'3.10.0') {
    throw "Python 3.10+ is required. Found: $pythonVersionRaw"
}
Write-Host "Detected Python $pythonVersionRaw via '$($pythonLauncher.Name)'." -ForegroundColor Green

Write-Step 'Preparing local virtual environment'
$recreateVenv = $false
if (Test-Path $venvPython) {
    $venvVersionRaw = (& $venvPython -c "import sys; print('.'.join(map(str, sys.version_info[:3])))" 2>&1 | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($venvVersionRaw)) {
        $recreateVenv = $true
    } elseif ([Version]$venvVersionRaw -lt [Version]'3.10.0') {
        $recreateVenv = $true
    }
}

if ($recreateVenv -and (Test-Path $venvDir)) {
    Write-Host "Existing virtual environment appears invalid/outdated. Recreating '$venvDir'." -ForegroundColor Yellow
    Remove-Item -Recurse -Force $venvDir
}

if (-not (Test-Path $venvPython)) {
    & $pythonLauncher.Name @($pythonLauncher.Args + @('-m', 'venv', $venvDir))
}

if (-not (Test-Path $venvPython)) {
    throw "Virtual environment was not created correctly at $venvDir"
}

if (-not $SkipInstall) {
    Write-Step 'Installing Python dependencies'
    Ensure-VCRuntime
    & $venvPython -m pip install --upgrade pip setuptools wheel
    & $venvPython -m pip install --only-binary=:all: kiwisolver
    & $venvPython -m pip install -r $requirementsPath
} else {
    Write-Host 'Skipping dependency installation because -SkipInstall was provided.' -ForegroundColor Yellow
}

Write-Step 'Verifying required Python libraries'
& $venvPython -c "import flask, flask_sqlalchemy, flask_migrate, flask_login, flask_mail, matplotlib, numpy, sqlalchemy; print('All critical libraries imported successfully.')"
if ($LASTEXITCODE -ne 0) {
    if ($SkipInstall) {
        throw 'Library verification failed and -SkipInstall was provided. Re-run without -SkipInstall to repair the environment.'
    }

    Write-Host 'Library verification failed. Recreating virtual environment and reinstalling dependencies once...' -ForegroundColor Yellow
    if (Test-Path $venvDir) {
        Remove-Item -Recurse -Force $venvDir
    }
    & $pythonLauncher.Name @($pythonLauncher.Args + @('-m', 'venv', $venvDir))
    & $venvPython -m pip install --upgrade pip setuptools wheel
    & $venvPython -m pip install --only-binary=:all: kiwisolver
    & $venvPython -m pip install -r $requirementsPath
    & $venvPython -c "import flask, flask_sqlalchemy, flask_migrate, flask_login, flask_mail, matplotlib, numpy, sqlalchemy; print('All critical libraries imported successfully after rebuild.')"
    if ($LASTEXITCODE -ne 0) {
        throw 'Python dependency import verification still failed after rebuilding the virtual environment.'
    }
}

Write-Step 'Ensuring runtime files and folders exist'
if (-not (Test-Path $instancePath)) {
    New-Item -ItemType Directory -Path $instancePath | Out-Null
}

if (-not (Test-Path $secretPath)) {
    @(
        '# Auto-generated local development secret file.'
        '# Replace these values if you need real email sending.'
        'MAIL_USERNAME = ""'
        'MAIL_PASSWORD = ""'
    ) | Set-Content -Path $secretPath -Encoding UTF8
    Write-Host "Created $secretPath with placeholder values." -ForegroundColor Yellow
}

Write-Step 'Starting Invasi app'
Write-Host 'Open http://127.0.0.1:5000 in your browser when the server is ready.' -ForegroundColor Green
Set-Location $appDir
& $venvPython app.py
