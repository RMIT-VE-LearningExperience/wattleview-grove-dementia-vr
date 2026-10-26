[CmdletBinding()]
param(
    [ValidateSet("Development", "Shipping")]
    [string]$Configuration = "Development",
    [ValidateSet("ASTC", "ETC2")]
    [string]$TextureFormat = "ETC2",
    [string]$EngineRoot = "C:\Program Files\Epic Games\UE_5.7"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$requiredAssets = @(
    "Content\Tablet\BP_TabletCharacter.uasset"
    "Content\Tablet\BP_TabletGameMode.uasset"
    "Content\Tablet\Input\IMC_Tablet.uasset"
)

$missingAssets = @(
    foreach ($relativePath in $requiredAssets) {
        $absolutePath = Join-Path $projectRoot $relativePath
        if (-not (Test-Path -LiteralPath $absolutePath)) {
            $relativePath
        }
    }
)

if ($missingAssets.Count -gt 0) {
    $missingList = $missingAssets -join ", "
    throw "Tablet runtime is not ready. Missing: $missingList. See Docs\BUILD_PROFILES.md."
}

throw @"
Tablet runtime assets exist, but the clean Tablet target/config has not yet
been enabled. Add the checked-in Tablet target rules and Config\Custom\Tablet
overrides described in Docs\BUILD_PROFILES.md before removing this guard.
Requested configuration: $Configuration
Requested texture format: $TextureFormat
Engine root: $EngineRoot
"@
