param(
  [string]$RepoName = "Cheburnet",
  [string]$Visibility = "public",
  [string]$Tag = "v0.1.0"
)

$ErrorActionPreference = "Stop"

Set-Location (Split-Path -Parent $PSScriptRoot)

function Test-NativeSuccess {
  param([scriptblock]$Command)

  $PreviousErrorActionPreference = $ErrorActionPreference
  $ErrorActionPreference = "Continue"
  try {
    & $Command *>$null
    return $LASTEXITCODE -eq 0
  } catch {
    return $false
  } finally {
    $ErrorActionPreference = $PreviousErrorActionPreference
  }
}

$GhCommand = Get-Command gh -ErrorAction SilentlyContinue
$GhPath = if ($GhCommand) { $GhCommand.Source } else { "" }
if (-not $GhPath) {
  $DefaultGh = "C:\Program Files\GitHub CLI\gh.exe"
  if (Test-Path -LiteralPath $DefaultGh) {
    $GhPath = $DefaultGh
  }
}
if (-not $GhPath) {
  throw "GitHub CLI is not installed. Install it with: winget install --id GitHub.cli -e"
}

& $GhPath auth status
$Owner = (& $GhPath api user --jq ".login").Trim()
$RepoFullName = "$Owner/$RepoName"
$RepoUrl = "https://github.com/$RepoFullName.git"

if (-not (Test-Path -LiteralPath "dist\Cheburnet.exe")) {
  & .\build_scripts\build_exe.ps1
}

$RemoteExists = Test-NativeSuccess { git remote get-url origin }

if (-not $RemoteExists) {
  $RepoExists = Test-NativeSuccess { & $GhPath repo view $RepoFullName --json nameWithOwner }
  if ($RepoExists) {
    git remote add origin $RepoUrl
    git push -u origin main
  } else {
    & $GhPath repo create $RepoName --source . --remote origin --push "--$Visibility" --description "Windows GUI for zapret, VPN profiles and rule-based site tunneling"
  }
} else {
  git push -u origin main
}

git push origin $Tag --force

$ReleaseExists = Test-NativeSuccess { & $GhPath release view $Tag --repo $RepoFullName }
if ($ReleaseExists) {
  & $GhPath release upload $Tag "dist\Cheburnet.exe" --repo $RepoFullName --clobber
} else {
  & $GhPath release create $Tag "dist\Cheburnet.exe" --repo $RepoFullName --title "Cheburnet $Tag" --notes-file RELEASE_NOTES.md
}

Write-Host ""
Write-Host "Published $RepoFullName $Tag"
