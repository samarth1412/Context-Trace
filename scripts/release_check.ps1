param(
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"

$RootDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$PackageDir = Join-Path $RootDir "packages\contexttrace"
$SmokeDir = Join-Path $RootDir ".tmp-release-check"

function Invoke-Checked {
    param(
        [string]$FilePath,
        [string[]]$Arguments
    )

    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed: $FilePath $($Arguments -join ' ')"
    }
}

function Remove-SafeDirectory {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        return
    }
    $Resolved = (Resolve-Path -LiteralPath $Path).Path
    if (-not $Resolved.StartsWith($RootDir)) {
        throw "Refusing to remove outside repository: $Resolved"
    }
    Remove-Item -LiteralPath $Resolved -Recurse -Force
}

Write-Host "==> Cleaning previous builds"
Remove-SafeDirectory (Join-Path $PackageDir "dist")
Remove-SafeDirectory (Join-Path $PackageDir "build")
Get-ChildItem -Path $PackageDir -Filter "*.egg-info" -Directory -ErrorAction SilentlyContinue |
    ForEach-Object { Remove-SafeDirectory $_.FullName }
Remove-SafeDirectory $SmokeDir

Write-Host "==> Installing build tools"
Invoke-Checked $Python @("-m", "pip", "install", "--upgrade", "build", "twine")

Write-Host "==> Building package"
Push-Location $PackageDir
try {
    Invoke-Checked $Python @("-m", "build")
    Invoke-Checked $Python @("-m", "twine", "check", "dist/*")
} finally {
    Pop-Location
}

Write-Host "==> Creating wheel smoke-test environment"
Invoke-Checked $Python @("-m", "venv", (Join-Path $SmokeDir "venv"))

$VenvPython = Join-Path $SmokeDir "venv\Scripts\python.exe"
$VenvContextTrace = Join-Path $SmokeDir "venv\Scripts\contexttrace.exe"
$Wheel = Get-ChildItem -Path (Join-Path $PackageDir "dist") -Filter "contexttrace-*.whl" |
    Select-Object -First 1

if (-not $Wheel) {
    throw "No wheel found in $PackageDir\dist"
}

Write-Host "==> Installing built wheel"
Invoke-Checked $VenvPython @("-m", "pip", "install", $Wheel.FullName)

Write-Host "==> Running installed-package smoke test"
$WorkDir = Join-Path $SmokeDir "work"
New-Item -ItemType Directory -Force -Path $WorkDir | Out-Null
Push-Location $WorkDir
try {
    Invoke-Checked $VenvContextTrace @("--version")
    Invoke-Checked $VenvPython @("-c", "from contexttrace import ContextTrace, __version__; print(__version__, ContextTrace.__name__)")
    Invoke-Checked $VenvContextTrace @("init")
    Invoke-Checked $VenvContextTrace @("demo", "--dataset", "refund_policy")
    Invoke-Checked $VenvContextTrace @("report", "--last")
    Invoke-Checked $VenvContextTrace @("doctor")
} finally {
    Pop-Location
}

Write-Host "==> Release check passed"
