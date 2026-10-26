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

# Baked lighting must exist and be newer than the map, or the room ships unlit/stale.
$map = Join-Path $projectRoot "Content\Wattleview\Maps\L_ResidentRoom.umap"
$builtData = Join-Path $projectRoot "Content\Wattleview\Maps\L_ResidentRoom_BuiltData.uasset"
if (-not (Test-Path $builtData)) {
    throw "Missing $builtData. Run Scripts/Editor/build_lighting.py (bakes lighting) first."
}
if ((Get-Item $builtData).LastWriteTime -lt (Get-Item $map).LastWriteTime.AddMinutes(-30)) {
    Write-Warning "Lighting bake is older than the map by over 30 min; rebake if geometry or lights changed."
}

New-Item -ItemType Directory -Path $archiveDir -Force | Out-Null

$uatArgs = @(
    "BuildCookRun"
    "-project=$projectFile"
    "-noP4"
    "-platform=Android"
    "-cookflavor=ASTC"
    "-clientconfig=$Configuration"
    "-cook", "-map=/Game/Wattleview/Maps/L_ResidentRoom", "-build", "-stage", "-pak", "-package", "-archive"
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
    # Run through cmd and judge by exit code: the generated installer writes harmless
    # messages to stderr (e.g. "rm: ... No such file"), which PowerShell's Stop preference
    # would otherwise treat as fatal, aborting before the OBB is pushed.
    Push-Location $artifactDir
    try {
        $installOut = & cmd.exe /c "`"$($bat.FullName)`" $Serial 2>&1"
        $installOut | Select-Object -Last 3
        if ($LASTEXITCODE -ne 0 -or -not ($installOut -match 'Installation successful')) {
            throw "Install did not report success (exit $LASTEXITCODE). Is the headset connected and awake? Check 'adb devices'."
        }
    }
    finally { Pop-Location }
}
