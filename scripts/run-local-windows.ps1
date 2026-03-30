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

$repoRoot = Split-Path -Parent $PSScriptRoot
$appDir = Join-Path $repoRoot 'invasi-app'
$venvDir = Join-Path $repoRoot '.venv'
$venvPython = Join-Path $venvDir 'Scripts/python.exe'
$requirementsPath = Join-Path $appDir 'requirements.txt'
$secretPath = Join-Path $appDir 'secret.py'
$instancePath = Join-Path $appDir 'instance'

Write-Step 'Checking prerequisites'
Assert-Command -Command 'python' -InstallHint 'Install Python 3.10+ from https://www.python.org/downloads/windows/ and ensure "Add python.exe to PATH" is enabled.'

$pythonVersionRaw = (& python -c "import sys; print('.'.join(map(str, sys.version_info[:3])))").Trim()
$pythonVersion = [Version]$pythonVersionRaw
if ($pythonVersion -lt [Version]'3.10.0') {
    throw "Python 3.10+ is required. Found: $pythonVersionRaw"
}
Write-Host "Detected Python $pythonVersionRaw" -ForegroundColor Green

Write-Step 'Preparing local virtual environment'
if (-not (Test-Path $venvPython)) {
    & python -m venv $venvDir
}

if (-not (Test-Path $venvPython)) {
    throw "Virtual environment was not created correctly at $venvDir"
}

if (-not $SkipInstall) {
    Write-Step 'Installing Python dependencies'
    & $venvPython -m pip install --upgrade pip setuptools wheel
    & $venvPython -m pip install -r $requirementsPath
} else {
    Write-Host 'Skipping dependency installation because -SkipInstall was provided.' -ForegroundColor Yellow
}

Write-Step 'Verifying required Python libraries'
& $venvPython -c "import flask, flask_sqlalchemy, flask_migrate, flask_login, flask_mail, matplotlib, numpy, sqlalchemy; print('All critical libraries imported successfully.')"

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
