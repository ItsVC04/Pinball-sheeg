param(
    [string]$PythonExe = ".venv\Scripts\python.exe"
)

$ErrorActionPreference = "Stop"

$root = if ($PSScriptRoot) { $PSScriptRoot } else { Get-Location }
Set-Location $root

if (-not (Test-Path $PythonExe)) {
    throw "Python executable not found: $PythonExe"
}

& $PythonExe -m pip install pyinstaller
& $PythonExe -m PyInstaller --clean --noconfirm ".\SheegLauncher.spec"

Write-Host ""
Write-Host "Build complete:"
Write-Host "  $root\dist\SheegLauncher.exe"
