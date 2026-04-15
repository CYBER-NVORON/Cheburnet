$ErrorActionPreference = "Stop"

Set-Location (Split-Path -Parent $PSScriptRoot)

python -m PyInstaller --clean --noconfirm Cheburnet.spec

Write-Host ""
Write-Host "Built: dist\Cheburnet.exe"
