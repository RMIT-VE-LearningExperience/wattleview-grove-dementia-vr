[CmdletBinding()]
param(
    [ValidateSet("Development", "Shipping")]
    [string]$Configuration = "Development",
    [string]$EngineRoot = "C:\Program Files\Epic Games\UE_5.8",
    [switch]$Install,
    [string]$Serial
)

# Packages Wattleview Grove for PICO 4 Ultra (Android, ASTC) with UE 5.8 native PICO
# support (OpenXR + built-in PICOController plugin), optionally installs it over adb.
#
# -unrealexe points UAT at the stock editor: enabling non-default plugins makes UAT treat
# this Blueprint project as code-based and look for a project editor receipt that a
# Blueprint-only checkout never has.

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$projectFile = Join-Path $projectRoot "WattleviewGrove.uproject"
$uatPath     = Join-Path $EngineRoot "Engine\Build\BatchFiles\RunUAT.bat"
$timestamp   = Get-Date -Format "yyyyMMdd-HHmmss"
$archiveDir  = Join-Path $projectRoot "Build\Profiles\PICO\$Configuration\$timestamp"

if (-not (Test-Path -LiteralPath $uatPath)) { throw "RunUAT.bat not found: $uatPath" }
if (-not (Get-ChildItem (Join-Path $EngineRoot "Engine\Binaries\Android") -ErrorAction SilentlyContinue)) {
    throw "Engine Android component missing. Launcher > Library > 5.8 > Options > tick Android."
}
if (Get-Process UnrealEditor -ErrorAction SilentlyContinue) {
    throw "Close Unreal Editor before packaging."
}

New-Item -ItemType Directory -Path $archiveDir -Force | Out-Null

$uatArgs = @(
    "BuildCookRun"
    "-project=$projectFile"
    "-noP4"
    "-platform=Android"
    "-cookflavor=ASTC"
    "-clientconfig=$Configuration"
    "-cook", "-allmaps", "-build", "-stage", "-pak", "-package", "-archive"
    "-archivedirectory=$archiveDir"
    "-compressed"
    "-unattended"
    "-utf8output"
    "-nocompileeditor"
    "-unrealexe=UnrealEditor-Cmd.exe"
)

& $uatPath @uatArgs
if ($LASTEXITCODE -ne 0) { throw "PICO build failed with exit code $LASTEXITCODE." }

$apk = @(Get-ChildItem -LiteralPath $archiveDir -Recurse -File -Filter "*.apk")
if ($apk.Count -ne 1) { throw "Expected one APK under $archiveDir; found $($apk.Count)." }
$artifactDir = $apk[0].Directory.FullName
Set-Content -LiteralPath (Join-Path $projectRoot "Build\Profiles\PICO\Latest.txt") -Value $artifactDir -Encoding UTF8
Get-ChildItem $artifactDir -File | Select-Object Name, Length | Format-Table -AutoSize
Write-Output "Artifacts: $artifactDir"

if ($Install) {
    $bat = Get-ChildItem $artifactDir -Filter "Install_*.bat" | Select-Object -First 1
    if (-not $bat) { throw "No installer .bat in $artifactDir" }
    Push-Location $artifactDir
    try { if ($Serial) { & $bat.FullName $Serial } else { & $bat.FullName } }
    finally { Pop-Location }
}
