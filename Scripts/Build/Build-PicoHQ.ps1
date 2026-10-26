[CmdletBinding()]
param(
    [ValidateSet("Development", "Shipping")]
    [string]$Configuration = "Development",
    [string]$EngineRoot = "C:\Program Files\Epic Games\UE_5.7"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$projectFile = Join-Path $projectRoot "WattleviewGrove.uproject"
$uatPath = Join-Path $EngineRoot "Engine\Build\BatchFiles\RunUAT.bat"
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$profileRoot = Join-Path $projectRoot "Build\Profiles\PICO-HQ"
$archiveDir = Join-Path $profileRoot (Join-Path $Configuration $timestamp)

if (-not (Test-Path -LiteralPath $uatPath)) {
    throw "RunUAT.bat was not found at: $uatPath"
}

if (Get-Process UnrealEditor -ErrorAction SilentlyContinue) {
    throw "Close Unreal Editor before packaging. Live Coding blocks Android builds."
}

New-Item -ItemType Directory -Path $archiveDir -Force | Out-Null

$uatArgs = @(
    "BuildCookRun"
    "-project=$projectFile"
    "-noP4"
    "-platform=Android"
    "-clientconfig=$Configuration"
    "-serverconfig=$Configuration"
    "-cook"
    "-allmaps"
    "-build"
    "-stage"
    "-pak"
    "-package"
    "-archive"
    "-archivedirectory=$archiveDir"
    "-compressed"
    "-prereqs"
    "-cookflavor=ASTC"
    "-unattended"
    "-utf8output"
)

& $uatPath @uatArgs
if ($LASTEXITCODE -ne 0) {
    throw "PICO-HQ build failed with exit code $LASTEXITCODE."
}

$apkMatches = @(
    Get-ChildItem -LiteralPath $archiveDir -Recurse -File `
        -Filter "WattleviewGrove-arm64.apk"
)
if ($apkMatches.Count -ne 1) {
    throw "Expected one archived APK under $archiveDir; found $($apkMatches.Count)."
}

$apk = $apkMatches[0]
$artifactDir = $apk.Directory.FullName
$apkPath = $apk.FullName
$obbPath = Join-Path $artifactDir "main.1.com.rmit.wattleviewgrove.obb"
$obb = Get-Item -LiteralPath $obbPath

$gitCommit = $null
$gitDirty = $null
try {
    $gitCommit = (git -C $projectRoot rev-parse HEAD 2>$null)
    $gitDirty = @((git -C $projectRoot status --porcelain 2>$null)).Count -gt 0
}
catch {
    $gitCommit = "unavailable"
    $gitDirty = $null
}

$manifest = [ordered]@{
    profile = "PICO-HQ"
    timestamp = (Get-Date).ToString("o")
    configuration = $Configuration
    texture_format = "ASTC"
    engine_root = $EngineRoot
    project = $projectFile
    package_name = "com.rmit.wattleviewgrove"
    git_commit = $gitCommit
    git_dirty = $gitDirty
    uat_arguments = $uatArgs
    artifacts = @(
        [ordered]@{
            file = $apk.Name
            bytes = $apk.Length
            sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $apkPath).Hash
        }
        [ordered]@{
            file = $obb.Name
            bytes = $obb.Length
            sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $obbPath).Hash
        }
    )
}

$manifestPath = Join-Path $artifactDir "build-manifest.json"
$manifest | ConvertTo-Json -Depth 8 |
    Set-Content -LiteralPath $manifestPath -Encoding UTF8

$profilePrefix = $profileRoot.TrimEnd(
    [System.IO.Path]::DirectorySeparatorChar,
    [System.IO.Path]::AltDirectorySeparatorChar
) + [System.IO.Path]::DirectorySeparatorChar
if (-not $artifactDir.StartsWith(
    $profilePrefix,
    [System.StringComparison]::OrdinalIgnoreCase
)) {
    throw "Artifact directory is outside the PICO-HQ profile root: $artifactDir"
}
$relativeArchive = $artifactDir.Substring($profilePrefix.Length)
Set-Content -LiteralPath (Join-Path $profileRoot "Latest.txt") `
    -Value $relativeArchive -Encoding UTF8

$apk, $obb | Select-Object Name, Length, LastWriteTime
Write-Output "Manifest: $manifestPath"
Write-Output "Latest: $relativeArchive"
