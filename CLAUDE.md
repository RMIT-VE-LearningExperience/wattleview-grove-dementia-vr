# Wattleview Grove — machine setup & build (UE 5.8 branch)

Getting this project building and deploying to a **PICO 4 Ultra Enterprise** from a clean Windows
machine. For *why* the stack was chosen and what the experience is, see [README.md](README.md) and
[Docs/Production/Story_V2_VR_Breakdown.md](Docs/Production/Story_V2_VR_Breakdown.md).

This branch (`ue58`) is a fresh UE 5.8.4 project with Epic's **native PICO support**. The UE 5.7
hospital project, with the Fab PICO OpenXR plugin, stays on `main`.

Verified on 2026-10-26: clean UE 5.8.4 install → template APK and story APK packaged. On-device
verification on the PICO 4 Ultra is still pending.

---

## 0. What you need before starting

| Thing | Version | Notes |
|---|---|---|
| Unreal Engine | **5.8.4** | Via Epic Games Launcher |
| UE Android support | — | **Separate optional component**: see step 1. Easy to miss. |
| UE MetaHuman Creator Core Data | — | Optional component; needed to author the MetaHumans in-engine |
| PICO plugin | **none** | 5.8 ships OpenXR plus Epic's `PICOController` plugin. No Fab plugin. |
| Android Studio | 2026.1+ | Only used as a delivery vehicle for the SDK and its bundled JDK |
| Android NDK | **27.2.12479018** | Pinned by UE 5.8 (same as 5.7) |
| Android platform | **android-36** | UE 5.8 pin (5.7 used android-34) |
| Build tools | **36.0.0** | UE 5.8 pin |
| CMake | **3.22.1** | |
| JDK | **21** (Studio's JBR) | UE 5.8 ships no JDK of its own |
| Disk | ~50 GB free | Engine + Android + MetaHuman data + SDK + DDC |

No Visual Studio C++ workload is needed. This is a Blueprint-only project. See `-unrealexe` in step 7.

---

## 1. Engine + optional components (Epic Games Launcher)

Install **UE 5.8.4**, then:

> Launcher → **Library** → 5.8.4 tile → dropdown chevron → **Options** →
> tick **Android** under Target Platforms (and **MetaHuman Creator Core Data**) → **Apply**

**The launcher cannot modify an engine while that engine's editor is running.** It sits at
"Initializing" / "Update Queued" with no error. Close the editor first. The launcher also auto-opens
the editor after a fresh install; close that too.

Verify Android took: you should see engine libraries, not an empty folder.

```bash
ls "C:/Program Files/Epic Games/UE_5.8/Engine/Binaries/Android"
# expect: UnrealGame-arm64.so, UnrealGame-Android-Shipping-arm64.so, ...
```

On this machine the launcher's `LauncherInstalled.dat` never lists 5.8 even after install. Check the
folder above, not the manifest.

## 2. Android Studio

```
winget install --id Google.AndroidStudio -e --accept-package-agreements --accept-source-agreements --silent
```

**Run this in an interactive terminal and accept the UAC prompt.** If it can't prompt, winget prints
`Successfully installed` and exits 0 **having installed nothing**. Verify:

```
winget list --id Google.AndroidStudio -e     # must list it
```

You never need to open Android Studio. It provides the bundled JBR (which becomes `JAVA_HOME`) and the
registry key `HKLM\SOFTWARE\Android Studio` that SetupAndroid.bat reads.

## 3. Command-line tools

Studio's default install omits these. Resolve the current version from Google's manifest:

```bash
curl -s https://dl.google.com/android/repository/repository2-3.xml \
  | grep -oE 'commandlinetools-win-[0-9]+_latest\.zip' | tail -1
```

Download, verify the sha1 against the manifest, and extract so that `sdkmanager.bat` ends up at exactly
`%LOCALAPPDATA%\Android\Sdk\cmdline-tools\latest\bin\sdkmanager.bat`. The `latest` directory name
matters: SetupAndroid.bat probes for it literally.

## 4. Accept SDK licenses

```bash
export JAVA_HOME="/c/Program Files/Android/Android Studio/jbr"
SDK="C:/Users/<you>/AppData/Local/Android/Sdk"
yes | "$SDK/cmdline-tools/latest/bin/sdkmanager.bat" --licenses --sdk_root="$SDK"
```

**Use Git Bash, not PowerShell.** Piping `y` from PowerShell silently accepts nothing. Verify
`ls "$SDK/licenses"` shows files.

## 5. Install the pinned SDK components

UE 5.8 pins them in `Engine/Config/Android/Android_SDK.json`. Either run SetupAndroid.bat:

```
"C:\Program Files\Epic Games\UE_5.8\Engine\Extras\Android\SetupAndroid.bat" android-36 36.0.0 3.22.1 27.2.12479018 -noninteractive
```

or, if the NDK/CMake are already there from a 5.7 setup, just add the two new pins:

```bash
"$SDK/cmdline-tools/latest/bin/sdkmanager.bat" --sdk_root="$SDK" "platforms;android-36" "build-tools;36.0.0"
```

SetupAndroid.bat persists user-scope `ANDROID_HOME`, `JAVA_HOME`, `NDKROOT`/`NDK_ROOT` and adds
`platform-tools` (adb) to PATH. **Restart every shell and the editor afterwards.**

Authoritative check:

```bash
"C:/Program Files/Epic Games/UE_5.8/Engine/Binaries/DotNET/UnrealBuildTool/UnrealBuildTool.exe" \
  -Mode=ValidatePlatforms -Platforms=Android
# expect: ##PlatformValidate: Android VALID
```

This validates the Google SDK only; it reports VALID even if step 1's Android component is missing.

---

## 6. Open the project

Open `WattleviewGrove.uproject` with UE 5.8. Default map: `/Game/Wattleview/Maps/L_ResidentRoom`.

The room, timeline, director, menu and perception layer are all **generated by scripts** in
`Scripts/Editor/`. Rerun them rather than hand-editing, so the scripts stay the source of truth:

| Script | Builds | How to run |
|---|---|---|
| `build_resident_room.py` | `L_ResidentRoom` greybox, garden, lights, viewpoint cameras, stand-ins | headless (below) |
| `import_room_assets.py` | Blender room meshes, Poly Haven textures, `M_RoomMaster` + `MI_<slot>`, sky | headless |
| `build_room_dressing.py` | swaps the greybox for the imported meshes using `SourceArt/Room/placement.json` | headless |
| `build_characters.py` | retargets idle/walk/sit onto the MetaHuman bodies, swaps the stand-ins for `BP_Maria`/`BP_David`, places `Enzo_Overlay` | headless or open editor |
| `import_garments.py` | Blender garments (`SourceArt/Characters/Garments`), `MI_Garment_*`, dresses the placed MetaHumans | headless or open editor |
| `build_blob_shadows.py` | soft contact shadows under the characters (there is no movable shadow cascade) | headless or open editor |
| `build_story_sequence.py` | `LS_Story` (VR pacing, ~7:50), viewer anchors, blocking, prop keys, fan, `MPC_Perception` keys | headless or open editor |
| `build_perception_layer.py` | Maria's perception materials and actors, memory-garden overlay | headless or open editor |
| `build_story_director.py` | `BP_StoryDirector` and its placement | needs UnrealMCPython (loaded headless too) |
| `build_gaze_start.py` | look-to-start target | headless or open editor |
| `build_lighting.py` | baked daylight: sun, sky light, portal, volumes, Production bake | open editor (bake is long) |
| `build_viewpoint_menu.py` | viewpoint buttons in `WBP_Menu`, Restart fix | open editor, needs UnrealMCPython |
| `capture_viewpoints.py` | PNG from every camera into `Saved/Captures` (`WG_CAPTURE_WAIT` seconds for shaders) | headless |
| `build_metahumans.py` | Maria, David, Enzo, EnzoYoung MetaHuman sources + portraits in `Saved/MetaHumans` | headless |
| `assemble_metahumans.py` | rig, texture download, Optimized/Medium assembly, Android texture caps | after the Epic sign-in |
| `shoot_wall_photo.py` | temporary garden set + young Maria and Enzo, raw capture for the wall photo | open editor (see MetaHumans) |

**Rerunning `build_resident_room.py` recreates the map from scratch.** Then run, in order:
`import_room_assets` (if the Blender exports changed), `build_room_dressing`, `build_characters`,
`build_blob_shadows`, `import_garments`, `build_story_sequence`, `build_perception_layer`, `build_story_director`,
`build_gaze_start`, `build_lighting`. `build_room_dressing` respawns every Env actor and
`build_characters` respawns the MetaHumans, so `import_garments` must run after both.

**Lighting values are written as editor properties** (`set_editor_property("intensity", ...)`).
`set_intensity()`/`set_light_color()` change the live light but don't persist into the saved level,
and after a reload the lights return to their much brighter class defaults. Keep `build_lighting.py`
on editor properties. The headset has no exposure: anything near 1.0 clips, so err darker.

### Room assets (Blender)

Placeholders for the room are modelled by scripts in `SourceArt/Room/Items/` (headless Blender 5.0)
and exported to `SourceArt/Room/Export/SM_*.fbx`. `SourceArt/Room/CONVENTIONS.md` is the spec (units,
pivots, UVs, slot names, budgets). `SourceArt/Room/placement.json` is the single source of truth for
where every piece sits; the Blender audit, the dressing script and the memory overlay all read it.

- `Tools/inspect_asset.py -- Export/SM_X.fbx`: measurements, defects and a six-view contact sheet.
- `Tools/assemble_room.py -- --render`: assembles the room, reports real clashes (not resting contact)
  and fit/clearance violations, renders review views. Its `report.json` also gives the dressing script
  the exact resting heights of props.

### MetaHumans

`build_metahumans.py` authors the characters locally (preset blending, body, aged skin, grooms).
Rigging, the texture download and assembly use Epic's MetaHuman cloud and need a one-time sign-in in
the editor with your own Epic account. The stored token expires, so if `assemble_metahumans.py` reports
"NOT READY", sign in again. Enzo shares David's body measurements so they can cross-fade on one
animation. MariaYoung and EnzoYoung are only for the wall photograph (Optimized builds in
`/Game/MetaHumans/PhotoM`, gitignored, never placed in the room).

Garments are Blender meshes skinned to `metahuman_base_skel`. `import_garments.py` puts them on the
placed actor's outfit component and **clears that component's override materials**. The MetaHuman
Blueprint sets overrides for Epic's default garment, and left in place they cover the shirt and
trouser slots. The Optimized body has no faces under the default garment (torso, upper arms, thighs),
so a garment must cover those regions.

Wall photo: `shoot_wall_photo.py` captures the raw image (hair renders only in the viewport, not in a
SceneCapture). Save it as `SourceArt/Photos/raw_MariaEnzo_young.png`, then
`python Scripts/Tools/grade_wall_photo.py` repaints the eyes and grades a faded print. The young
characters render with glowing eyes, cause not yet found, which is why the eyes are repainted.
`import_room_assets.py` (`PHOTOS`) puts the print on `SM_PhotoFrame_MariaEnzo`. **Don't destroy the
photo-set MetaHuman actors in the editor** (a "pure virtual" crash). Close the editor without saving.

Headless:

```
"C:\Program Files\Epic Games\UE_5.8\Engine\Binaries\Win64\UnrealEditor-Cmd.exe" ^
  "D:\Unreal-Projects\WattleviewGrove-ue58\WattleviewGrove.uproject" ^
  -ExecutePythonScript="<script>" -nosplash
```

Open editor (Python console or MCP `execute_python`): `exec(open(r"<script>").read())`.

Editor-scripting gotchas learned the hard way:

- `-ExecutePythonScript` **closes the editor as soon as the script returns.** A script that needs
  frames to pass (shader compile, captures) must call
  `unreal.EditorPythonScripting.set_keep_python_script_alive(True)` and release it when done.
- `-run=pythonscript` (commandlet) has no editor world: actor spawning returns `None`.
- **Never delete a Blueprint asset while an instance is placed in the level**: the editor crashes
  (TickTaskManager assertion). Destroy the instance first.
- **Never delete a material that placed actors use**: a modal "assets in use" dialog blocks the
  editor and every scripted call times out. Rebuild materials in place
  (`MaterialEditingLibrary.delete_all_material_expressions`).
- **Don't rebuild `MPC_Perception`'s parameter list from scratch**: materials reference collection
  parameters by internal ID. Add missing parameters only.
- **No MCP calls while packaging.** UnrealMCPython's module type `Editor` also loads inside the cook
  commandlet and opens its TCP server there. Python is disabled in commandlets, so any MCP call during
  a cook raises "Python is not available!" and the cook fails (exit 25, Error_UnknownCookFailure).
  Locally, set the module `"Type"` in `Plugins/UnrealMCPython/UnrealMCPython.uplugin` to
  `"EditorNoCommandlet"`. It still loads in the editor and with `-ExecutePythonScript`.
- The UnrealMCPython graph builder can't resolve wildcard pins (for-each, array get). Design graphs
  without them: direct actor references, `IsValid` macro, `Branch`.

## 7. Package for the headset

```powershell
.\Scripts\Build\Build-Pico.ps1             # -Install to also install over adb
```

It runs BuildCookRun for Android ASTC with `-package` and `-unrealexe=UnrealEditor-Cmd.exe`.
Enabling OpenXR makes UAT treat this Blueprint project as code-based; pointing it at the stock editor
avoids needing a project editor build.

First run ~10 min (shader compile), then ~2 min. Output goes to
`Build/Profiles/PICO/Development/<timestamp>/Android_ASTC/`, with `Build/Profiles/PICO/Latest.txt`
pointing at the newest. The template build was a 124 MB APK plus a 54 MB OBB.

### Frame rate on the headset

Budget: 11 ms of GPU per frame at 90 Hz. Frame synthesis is on (`Config/Android/AndroidEngine.ini`),
so the runtime can render at 45 Hz and synthesize 90. Below 45 fps the image still judders.
Measure on the device rather than guessing. Rendering only runs while someone wears the headset:

```bash
adb logcat -s PxrMetric          # once per second: FPS=../90, FrmGpu=..ms, AppSW=on|off, GPU %/MHz
adb shell "am broadcast -a android.intent.action.RUN -e cmd 'pause'"            # freeze the story
adb shell "am broadcast -a android.intent.action.RUN -e cmd 'ShowFlag.Hair 0'"  # any console command
```

Compare off/on pairs with the story paused. Otherwise its viewpoint changes swamp the difference.
Measured costs and pitfalls (27 Oct 2026):
- The sun's movable shadow cascade cost about 7 ms, so it's off. Characters get blob shadows instead.
- `r.VRS.Enable` must be 1, or FB foveation never reaches the GPU.
- `vr.PixelDensity` doesn't exist in 5.8. The eye-buffer scale is
  `xr.SecondaryScreenPercentage.HMDRenderTarget`.
- Full-view translucent spheres cost GPU time even at opacity 0, so they are hidden outside their
  beats.

## 8. Deploy

```
cd <artifact dir>
.\Install_WattleviewGrove-arm64.bat
```

Verify: `adb shell pm list packages | grep wattleview` → `com.rmit.wattleviewgrove`.

---

## Using the experience

- **No controller needed by students.** Launch shows the room with a glowing marker labelled "Look at
  the light to begin". Holding head gaze on it for 2 s fills its ring and starts the story (fade in from
  black). The PICO 4 Ultra Enterprise has **no eye tracking**; this is head gaze. The view recentres
  0.75 s after launch. The marker's place is per view (`GAZE_VIEW` in `build_story_director.py`):
  David's sits about 32 degrees left, on the wall between Maria and her photo. Maria's is 50 cm out,
  in front of the photo. The marker is scaled by its distance, so it looks the same size in every
  view. Before the gaze the characters stand at their t=0 marks, looping an idle.
- Launch defaults to the **support worker (David) view**, as the script requires.
- Teacher: controller **menu button** opens the VR menu. **Support worker view / Resident view / Observer
  view** reopen the room in that viewpoint (the gaze marker appears again). **Restart** restarts in the
  current viewpoint. Thumbstick move/snap-turn are disabled.
- Head rotation is always the user's. Viewpoint changes are fades to black at scripted moments.
- **Pacing.** The Story V2 timestamps are the 5:00 *cinematic* cut. The VR build uses a slower pacing
  table (`BEATS_VR` in `build_story_sequence.py`, ~7:50). `PACING = "cinematic"` rebuilds the 5:00 cut.

### Handing headsets to students (PICO Enterprise kiosk mode)

So students never see the PICO home screen: set the app as the headset's home app. On the headset:
**Settings > Developer > Business settings > Home Screen**, choose Wattleview Grove, reboot. For a fleet,
apply the Kiosk Mode template to a device group in PICO's Business Device Manager / Business Suite. Not
yet verified here: whether the boundary (guardian) setup can be skipped; check before a class session.

## Device notes

Target is **PICO 4 Ultra Enterprise** (`A9210`, `sparrow`), Android 14 / SDK 34, arm64-v8a, firmware
5.15.5 (README requires 5.14.0+).

**A PICO Neo 3 (A7H10, Android 10 / SDK 29) will not run this build.** The APK's minimum SDK is 32, and
5.8's PICOController plugin dropped Neo 3 support. Check `adb shell getprop ro.product.model` before
debugging an install failure.

Enable developer mode and USB debugging on the headset; `adb devices` should list it as `device`.

### Things that look like bugs but aren't

- **App launches but nothing renders**: `adb shell dumpsys power | grep mWakefulness`. `Asleep` means
  the headset isn't being worn; the proximity sensor gates the display.
- **OBB looks missing**: `adb shell ls /sdcard/Android/obb/<pkg>/` returns *Permission denied* under
  Android 11+ scoped storage. That's expected.
- **Device timestamps look 30 min stale**: the headset may be on ACST while the PC is on AEST.
- **No PICO in `adb devices` and Windows only shows "Pico Streaming" audio devices**: the headset isn't
  enumerating on USB at all. Reseat the plug, use a data cable, wake the headset. A flat battery also
  prevents enumeration until it has charged enough to boot.

## PICO controller input

5.8's built-in `PICOController` plugin registers `PICO_Left_*` / `PICO_Right_*` keys for the PICO 4
and PICO 4 Ultra interaction profiles. The VR template's mapping contexts already bind them, mirroring
every Oculus Touch binding, so **no manual remapping is needed** (the 5.7 project needed it). These
keys are not Blueprint-bindable as raw key events; use Enhanced Input actions.

## Rendering facts

- Forward shading, Mobile HDR off, 4x MSAA, Mobile Multi-View: the 5.8 VR template defaults.
- **No exposure on device** (mobile LDR). Keep raw light values near 1. Never tune brightness through
  the desktop renderer or a manual-exposure post-process volume. The headset is the only truthful
  brightness reference.
- Maria's perception layer uses translucent materials driven by `MPC_Perception`, with no
  post-processing. The full-view overlay costs ~186 pixel instructions; profile it first if the frame
  rate suffers.
- `OpenXREyeTracker` and `OpenXRHandTracking` are disabled. The 4 Ultra Enterprise has no eye
  tracking, and the experience doesn't use hands.

## Project config facts

- Package name `com.rmit.wattleviewgrove`, display name "Wattleview Grove".
- `MinSDKVersion` / `TargetSDKVersion` = 32. `bPackageForMetaQuest=False`, `bPackageForOpenXRImmersive=True`,
  activity metadata `pvr.app.type=vr`.
- Fixed foveation: `bIsFBFoveationEnabled`, `xr.OpenXRFBFoveationLevel=2`, dynamic.

## MCP tooling (optional, per-developer)

`Plugins/UnrealMCPython` (GenOrca v2.2.0, **5.8 build**) is gitignored. Download
`UnrealMCPython_5.8_2.2.0.zip` from https://github.com/GenOrca/unreal-mcp/releases and extract to
`Plugins/UnrealMCPython/`. It's enabled in the `.uproject` (Win64 editor only, never packaged). See the
README for the MCP server setup. UE 5.8 also ships Epic's own experimental MCP server plugin.
