param(
  [string]$Tag = "v1.0.0",
  [string]$Platform = "windows-x64"
)

$ErrorActionPreference = "Stop"

Set-Location (Split-Path -Parent $PSScriptRoot)

$DistDir = "dist\CheburNet"
$ExePath = Join-Path $DistDir "CheburNet.exe"
$ArchivePath = "dist\CheburNet-$Tag-$Platform.zip"

if (-not (Test-Path -LiteralPath $ExePath)) {
  & .\build_scripts\build_exe.ps1
  if ($LASTEXITCODE -ne 0) {
    throw "Build failed with exit code $LASTEXITCODE"
  }
}

if (Test-Path -LiteralPath $ArchivePath) {
  Remove-Item -LiteralPath $ArchivePath -Force
}

Compress-Archive -Path "$DistDir\*" -DestinationPath $ArchivePath -Force

Write-Host ""
Write-Host "Packaged: $ArchivePath"
