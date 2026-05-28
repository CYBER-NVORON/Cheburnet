$ErrorActionPreference = "Stop"

Set-Location (Split-Path -Parent $PSScriptRoot)

python -m PyInstaller --clean --noconfirm build/cheburnet.spec
if ($LASTEXITCODE -ne 0) {
  throw "PyInstaller failed with exit code $LASTEXITCODE"
}

Write-Host ""
Write-Host "Built: dist\CheburNet\CheburNet.exe"
