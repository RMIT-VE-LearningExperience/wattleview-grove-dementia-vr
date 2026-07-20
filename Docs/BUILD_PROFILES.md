# Wattleview Grove build profiles

This file is the source of truth for keeping the PICO and Android tablet
versions reproducible. Both versions share the same map, environment,
characters, materials, animation, and lighting assets.

## Profile status

| Profile | Runtime | Status | Output |
|---|---|---|---|
| `PICO-HQ` | PICO/OpenXR, XR pawn, headset and controllers | Built and installed; headset walkthrough pending | `Build/Profiles/PICO-HQ` |
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

Install with the generated installer and the headset serial:

```powershell
.\Build\Profiles\PICO-HQ\Install_WattleviewGrove-arm64.bat <device-serial>
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
- Added the south building expansion:
  - Corridor: 200 x 600 x 250 cm.
  - Large room: 1000 x 800 x 250 cm.
  - Added modular floor, ceiling, walls, doorway, ceiling fixtures, and window.
  - Expanded `NavBounds` to cover the complete walkable building.
- Replaced the black exterior with a PICO-safe unlit blue sky dome and warm
  sun disc.
- Verified architecture visually and with collision traces.

## Build ledger

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
- Confirm Maria faces and tracks the headset naturally.
- Walk from the original room through the open south door and corridor.
- Confirm the large-room floor, doorway, walls, and teleport/navigation.
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
