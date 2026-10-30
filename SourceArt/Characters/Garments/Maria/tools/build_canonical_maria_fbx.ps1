param(
    [string]$GarmentFbx,
    [string]$OutputFbx
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..\..\..')).Path
$SourceBody = Join-Path $ProjectRoot 'SourceArt\Characters\Bodies\SKM_Maria_BodyMesh.fbx'
if (-not $GarmentFbx) {
    $GarmentFbx = Join-Path $ProjectRoot 'SourceArt\Characters\Garments\Maria\SKM_Maria_Outfit_Blender.fbx'
}
if (-not $OutputFbx) {
    $OutputFbx = Join-Path $ProjectRoot 'SourceArt\Characters\Garments\Maria\SKM_Maria_Outfit.fbx'
}

$UnrealRoot = 'C:\Program Files\Epic Games\UE_5.8\Engine'
$FbxRoot = Join-Path $UnrealRoot 'Source\ThirdParty\FBX\2020.2'
$FbxDll = Join-Path $UnrealRoot 'Binaries\ThirdParty\FBX\2020.2\Win64'
$VcVars = 'C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars64.bat'
$Source = Join-Path $PSScriptRoot 'canonicalize_maria_fbx.cpp'
$Exe = Join-Path $env:TEMP 'canonicalize_maria_fbx.exe'

foreach ($Required in @($SourceBody, $GarmentFbx, $Source, $VcVars)) {
    if (-not (Test-Path -LiteralPath $Required)) {
        throw "Required path not found: $Required"
    }
}

$Compile = 'call "{0}" >nul && cl.exe /nologo /EHsc /MD /std:c++17 /I"{1}" "{2}" /Fe:"{3}" /link /LIBPATH:"{4}" libfbxsdk.lib' -f `
    $VcVars, (Join-Path $FbxRoot 'include'), $Source, $Exe, (Join-Path $FbxRoot 'lib\vs2017\x64\release')
& cmd.exe /d /c $Compile
if ($LASTEXITCODE -ne 0) {
    throw "Canonicalizer compilation failed with exit code $LASTEXITCODE"
}

$env:PATH = "$FbxDll;$env:PATH"
& $Exe $SourceBody $GarmentFbx $OutputFbx
if ($LASTEXITCODE -ne 0) {
    throw "Canonicalizer failed with exit code $LASTEXITCODE"
}

Get-Item -LiteralPath $OutputFbx | Select-Object FullName, Length, LastWriteTime
