param(
  [string]$RepoName = "Cheburnet",
  [string]$Visibility = "public",
  [string]$Tag = "v0.4.0",
  [string]$Platform = "windows-x64"
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

function Invoke-Native {
  param(
    [scriptblock]$Command,
    [string]$Message
  )

  & $Command
  if ($LASTEXITCODE -ne 0) {
    throw "$Message (exit code $LASTEXITCODE)"
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

Invoke-Native { & $GhPath auth status } "GitHub CLI is not authenticated. Run: gh auth login"
$Owner = (& $GhPath api user --jq ".login").Trim()
if ($LASTEXITCODE -ne 0 -or -not $Owner) {
  throw "Cannot read GitHub user from GitHub CLI."
}
$RepoFullName = "$Owner/$RepoName"
$RepoUrl = "https://github.com/$RepoFullName.git"
$CurrentBranch = (git branch --show-current).Trim()
if (-not $CurrentBranch) {
  $CurrentBranch = "main"
}
$DistDir = "dist\CheburNet"
$ExePath = Join-Path $DistDir "CheburNet.exe"
$ArchivePath = "dist\CheburNet-$Tag-$Platform.zip"

Invoke-Native { & .\build_scripts\package_release.ps1 -Tag $Tag -Platform $Platform } "Packaging failed"

$RemoteExists = Test-NativeSuccess { git remote get-url origin }
if (-not $RemoteExists) {
  $RepoExists = Test-NativeSuccess { & $GhPath repo view $RepoFullName --json nameWithOwner }
  if ($RepoExists) {
    Invoke-Native { git remote add origin $RepoUrl } "Cannot add origin remote"
    Invoke-Native { git push -u origin $CurrentBranch } "Cannot push branch $CurrentBranch"
  } else {
    Invoke-Native { & $GhPath repo create $RepoName --source . --remote origin --push "--$Visibility" --description "Windows GUI for sing-box VPN and Flowseal Zapret" } "Cannot create GitHub repository"
  }
} else {
  Invoke-Native { git push -u origin $CurrentBranch } "Cannot push branch $CurrentBranch"
}

if (-not (Test-NativeSuccess { git rev-parse $Tag })) {
  Invoke-Native { git tag $Tag } "Cannot create tag $Tag"
}
Invoke-Native { git push origin $Tag } "Cannot push tag $Tag"

$ReleaseExists = Test-NativeSuccess { & $GhPath release view $Tag --repo $RepoFullName }
if ($ReleaseExists) {
  Invoke-Native { & $GhPath release upload $Tag $ArchivePath --repo $RepoFullName --clobber } "Cannot upload release asset"
} else {
  Invoke-Native { & $GhPath release create $Tag $ArchivePath --repo $RepoFullName --title "CheburNet $Tag" --notes-file RELEASE_NOTES.md } "Cannot create GitHub release"
}

Write-Host ""
Write-Host "Published $RepoFullName $Tag"
