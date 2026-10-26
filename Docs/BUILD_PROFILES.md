# Wattleview Grove build profiles

This file is the source of truth for keeping the PICO and Android tablet
versions reproducible. Both versions share the same map, environment,
characters, materials, animation, and lighting assets.

## Profile status

| Profile | Runtime | Status | Output |
|---|---|---|---|
| `PICO-HQ` | PICO/OpenXR, XR pawn, headset and controllers | Built, installed, and smoke-tested; headset walkthrough pending | `Build/Profiles/PICO-HQ/Development/<timestamp>/Android_ASTC` |
| `Tablet` | Flat Android, grounded character, touch move/look | Runtime profile not implemented yet; build intentionally guarded | `Build/Profiles/Tablet` |

Do not use the current XR APK as a tablet build. It starts in VR, declares
`pvr.app.type=vr`, uses `BP_XRPawn`, and has no touch movement or look input.

## Shared source of truth

- Map: `/Game/Maps/HospitalRoom`
- Character: `/Game/MetaHumans/Maria/BP_Maria`
- Natural gaze AnimBP: `/Game/MetaHumans/Maria/Animations/ABP_Maria_NaturalLook`
- Morning sky: `/Game/HospitalPack/Materials/M_MorningSkyDome`
- Sun disc: `/Game/HospitalPack/Materials/M_MorningSunDisc`
- Expansion rebuild script: `Scripts/Codex/build_corridor_room.py`
- Safe editor QA script: `Scripts/Codex/capture_expansion_safe.py`

Never fork `HospitalRoom` just to make a tablet version. Platform-specific
camera/input behavior belongs in the player pawn, GameMode, and custom config.

## PICO-HQ profile

Current quality-oriented mobile baseline:

- Android ARM64, Vulkan mobile, ASTC textures, with no OpenGL ES fallback
- Forward shading and Mobile HDR off
- 4x MSAA
- Mobile Multi-View and instanced stereo
- Fixed/dynamic foveation support through PICO OpenXR
- Opaque compositor fix:
  `r.Mobile.PropagateAlpha=False`, `xr.OpenXRInvertAlpha=False`
- GameMode: `/Game/XRFramework/Blueprints/BP_XRGameMode`
- Pawn: `/Game/XRFramework/Blueprints/BP_XRPawn`
- Package: `com.rmit.wattleviewgrove`

`PICO-HQ` names the proven quality-oriented PICO profile. It is not a
separate maximum-quality render tier: refresh rate is currently `Default`,
adaptive resolution is `Balanced`, and PICO super-resolution is off. Increase
those only after measuring frame pacing and thermals on the headset.

Build with:

```powershell
.\Scripts\Build\Build-PicoHQ.ps1
```

Each build is timestamped. `Latest.txt` points to the directory containing
the verified manifest, APK, OBB, and installer. Install the newest build from
inside that directory because the generated installer uses relative paths:

```powershell
$profileRoot = (Resolve-Path ".\Build\Profiles\PICO-HQ").Path
$relativeBuild = (
    Get-Content -Raw (Join-Path $profileRoot "Latest.txt")
).Trim()
$buildDir = (Resolve-Path (Join-Path $profileRoot $relativeBuild)).Path

Push-Location $buildDir
try {
    .\Install_WattleviewGrove-arm64.bat <device-serial>
}
finally {
    Pop-Location
}
```

## Android tablet profile

The map is ready to share, but these runtime assets must exist before the
tablet build is enabled:

1. `BP_TabletCharacter`
   - Derive from `Character` for grounded collision and corridor walking.
   - Camera at normal eye height.
   - Touch move and drag-look support.
2. `IMC_Tablet`
   - Axis2D Move and Look actions.
   - Dual virtual sticks, or left stick plus right-side drag look.
3. `BP_TabletGameMode`
   - Default pawn set to `BP_TabletCharacter`.
4. Platform-neutral Maria gaze
   - Replace the hard cast to `BP_XRPawn` with `PlayerCameraManager` camera
     location or a shared player-view interface.
5. Tablet custom configuration
   - `bStartInVR=False`
   - Multi-View and instanced stereo off
   - PICO activity metadata removed
   - OpenXR/PICO runtime disabled for the tablet target
   - Separate package ID, recommended:
     `com.rmit.wattleviewgrove.tablet`
6. Device-specific decision
   - Default to ETC2 for generic Android compatibility.
   - Use ASTC only for a known modern tablet.
7. SDK separation
   - Keep PICO's proven target SDK 32 profile unchanged.
   - Validate the tablet/store profile separately against the installed
     Android SDK 35 and current store requirements.

`Scripts/Build/Build-Tablet.ps1` checks these prerequisites and refuses to
produce a misleading XR-on-tablet package.

## Shared change ledger

### 2026-07-20

- Corrected ceiling material visibility and mobile rendering.
- Added Maria clothing; removed the oversized temporary shoes.
- Added soft 10am-style room lighting, shadows, and a more matte skin response.
- Fixed Maria gaze:
  - Tracks the actual player camera/headset location.
  - Head leads by about 20 degrees.
  - Body follows gradually at about 30 degrees/second.
  - Corrected Maria mesh and head-bone forward axes.
  - Body and face always refresh their bones.
- Corrected PICO spawn:
  - Floor-level XR origin.
  - Starts about 1.4 m in front of Maria.
- Smoothed Maria's gaze response by reducing the tracked-target interpolation
  speed from `3.0` to `2.0`. Head and body tracking remain responsive, but
  headset micro-movements feed into the pose more gradually.
- Added the south building expansion:
  - Corridor: 200 x 600 x 250 cm.
  - Large room: 1000 x 800 x 250 cm.
  - Added modular floor, ceiling, walls, doorway, ceiling fixtures, and window.
  - Expanded `NavBounds` to cover the complete walkable building.
- Replaced the black exterior with a PICO-safe unlit blue sky dome and warm
  sun disc.
- Corrected teleport/navigation after the expansion:
  - Ceiling meshes and fixtures no longer contribute collision or navigation.
  - `NavBounds` covers only the walkable vertical band below the roof.
  - The XR pawn navigation projection extent is `(50, 50, 75)` cm.
  - Floor teleport passed in the original room, corridor, and large room;
    roof and high-point projections were rejected in all three areas.
- Replaced the expansion's harsh movable fill lights with broad static
  RectLights and an inward window SpotLight.
- Rebalanced only the corridor and large-room static lighting after headset
  exposure QA; the patient room and global exposure remain unchanged:
  - Corridor RectLight: `350 lm`, indirect `0.60`.
  - Large-room RectLights: `450 lm` each, indirect `0.60`.
  - Large-room window SpotLight: `400 lm`, indirect `0.70`.
- Added Maria's front-only personal-space response without moving her actor:
  - Starts at `80 cm` and reaches full response at `35 cm`.
  - Smooth front gate from dot `0.25` to `0.55`.
  - `4.5` interpolation speed prevents snapping.
  - Component-space additive neck recoil uses `neck_01 -10°` and
    `neck_02 -6°`, plus only `1.5 cm` rearward head translation.
  - PIE checks passed at far, near, intermediate, and behind-Maria positions
    with no Blueprint runtime errors or visible neck stretch.
- Repaired the hospital wall and legacy floor master-material defaults:
  normal, mask, roughness, and metallic samplers now use compatible textures,
  compression, and linear/sRGB settings.
- Completed a Production Lightmass bake:
  - `116/116` mappings.
  - `0` lights with unbuilt interactions.
  - `0` primitives with unbuilt interactions.
  - The only remaining Lightmass notices are pre-existing overlapping UVs on
    `wheel_chair` and `bed`.
- Verified the post-bake corridor, large room, window, ceiling, and exterior
  sky with captures in
  `Saved/CodexCaptures/BuildingExpansion/ExposureRebalance`.
- Fixed-view image sampling confirmed the corridor's clipped-white pixels
  dropped from `3.26%` to `1.06%`; the large-room overview mean luminance
  dropped from `197.13` to `149.79` while retaining bright morning light.

## Build ledger

### PICO-HQ — 2026-07-20 22:34 Australia/Sydney

- Unreal Engine: 5.7
- Configuration: Development
- Texture format: ASTC
- Result: `BUILD SUCCESSFUL`
- Output:
  `Build/Profiles/PICO-HQ/Development/20260720-223312/Android_ASTC`
- Includes:
  - Expansion-only exposure rebalance and fresh Production lightmaps.
  - Maria's smooth, front-only personal-space head/neck recoil.
- APK:
  - Size: `106620639`
  - SHA-256:
    `A2966142C984FF2C70E18D99B992F9938A86A0723FDEBA4BD47685195523F518`
- OBB:
  - Size: `256712017`
  - SHA-256:
    `4290B2A556EA0BFF8750054571BEF1B3CD3538CE7F553BDD5D924988192000CF`
- Manifest hashes rechecked successfully before installation.
- Installation: successful on PICO serial `PA94Y0MGJ9180026G`.
- Launch: `SplashActivity` handed off to Unreal `GameActivity`; the app
  remained alive after the 18-second smoke window and logcat contained no
  fatal exception, signal, ANR, assertion, or Blueprint runtime error.
- Headset state: PICO's guardian/see-through activity moved in front of the
  running game and must be completed or dismissed in-headset.

### PICO-HQ — 2026-07-20 21:46 Australia/Sydney

- Unreal Engine: 5.7
- Configuration: Development
- Texture format: ASTC
- Result: `BUILD SUCCESSFUL`
- Output:
  `Build/Profiles/PICO-HQ/Development/20260720-214552/Android_ASTC`
- APK:
  - Size: `106620639`
  - SHA-256:
    `872178C556CF0700AE38E6BD32ED409452BA88AB3A647C39F1B3ACB4E6296395`
- OBB:
  - Size: `256696526`
  - SHA-256:
    `77981EE231E69808EADE27A2F96205DF30ED6B1EB000AB1A4E1229260FCE043C`
- Manifest hashes rechecked successfully before installation.
- Installation: successful on PICO serial `PA94Y0MGJ9180026G`.
- Launch: `SplashActivity` handed off to Unreal `GameActivity`; the process
  remained alive and the 18-second smoke log contained no fatal exception,
  signal, ANR, assertion, or Blueprint runtime error.
- Headset state: PICO's guardian/see-through activity is still in front of the
  running game and must be completed or dismissed in-headset.

### PICO-HQ — 2026-07-20 20:29 Australia/Sydney

- Unreal Engine: 5.7
- Configuration: Development
- Texture format: ASTC
- Result: `BUILD SUCCESSFUL`
- APK:
  - Size: `106620639`
  - SHA-256:
    `8BAAA1245CEC4FFA80CE71D30602D62773BD7304726A7C35EA5B835CD2C778EA`
- OBB:
  - Size: `256262539`
  - SHA-256:
    `2A64241BB5FC4BB103FAA71392BBFE91FC2E2BD0597FDB27D9C757BEEA9E02B5`
- Installation: successful on PICO serial `PA94Y0MGJ9180026G`.
- Launch: Unreal GameActivity started; PICO boundary/passthrough screen took
  foreground while waiting for headset confirmation.

## Validation checklist

For every PICO build:

- Confirm PIE is stopped before packaging.
- Confirm Maria faces and tracks the headset naturally without visible jitter.
- Walk from the original room through the open south door and corridor.
- Confirm floor teleport works in all three areas and never selects the roof.
- Confirm there is no "lighting needs to be rebuilt" warning.
- Confirm the outside is blue rather than black through both windows.
- Check frame pacing and thermal behavior on the real PICO.

For every tablet build:

- Confirm the app does not enter stereoscopic/OpenXR mode.
- Confirm touch movement, drag look, collision, and camera height.
- Confirm Maria tracks the tablet camera.
- Confirm the on-screen controls do not cover important scene content.
- Test the selected texture format on the actual tablet model.
- Confirm PICO/OpenXR binaries and `pvr.app.type=vr` metadata are absent from
  the final tablet target, not merely inactive at runtime.
