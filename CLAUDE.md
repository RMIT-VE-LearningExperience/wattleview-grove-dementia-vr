# Wattleview Grove — machine setup & build

Getting this project building and deploying to a **PICO 4 Ultra Enterprise** from a clean Windows
machine. For *why* the stack was chosen (UE 5.7, PICO OpenXR plugin, MetaHuman constraints), see
[README.md](README.md) — this file is the *how*.

Everything below was verified end-to-end on 2026-07-17: clean machine → APK running on device.

---

## 0. What you need before starting

| Thing | Version | Notes |
|---|---|---|
| Unreal Engine | **5.7.4** | Via Epic Games Launcher |
| UE Android support | — | **Separate optional component** — see step 1. Easy to miss. |
| PICO OpenXR plugin | **1.6.1** | From Fab, installs into the engine |
| Android Studio | 2026.1+ | Only used as a delivery vehicle for the SDK + its bundled JDK |
| Android NDK | **27.2.12479018** | Pinned by UE 5.7 — do not substitute |
| Android platform | **android-34** | |
| Build tools | **35.0.1** | |
| CMake | **3.22.1** | |
| JDK | **21** (Studio's JBR) | UE 5.7 ships no JDK of its own |
| Disk | ~30 GB free | Engine + SDK + NDK + DDC |

No Visual Studio C++ workload is needed. This is a Blueprint-only project and stays that way — see
the `-unrealexe` note in step 6.

---

## 1. Engine + Android component (Epic Games Launcher)

Install **UE 5.7.4**, then — this is the step everyone misses:

> Launcher → **Library** → UE 5.7 entry → dropdown chevron → **Options** →
> tick **Android** under Target Platforms → **Apply**

Without it, `Engine/Platforms/Android` exists but contains only a `Plugins` folder, and any Android
build dies instantly with:

```
Missing files required to build Android targets.
Enable Android as an optional download component in the Epic Games Launcher.
```

Verify it took — you should see engine libraries, not an empty shell:

```bash
ls "C:/Program Files/Epic Games/UE_5.7/Engine/Binaries/Android"
# expect: UnrealGame-Android-Shipping-arm64.so, UnrealGame-arm64.so, ...
```

## 2. PICO OpenXR plugin

Install **PICO OpenXR** from Fab into UE 5.7. It lands at
`Engine/Plugins/Marketplace/PICOOpenfe9bc3609ba1V9/PICOOpenXR.uplugin`.

The folder name is opaque; the plugin's real name comes from the `.uplugin` filename (`PICOOpenXR`),
which is what `WattleviewGrove.uproject` references.

**The launcher cannot install into the engine while the Unreal Editor is running.** It will sit
at "Initializing" or "Update Queued" forever with no visible error. The launcher log says:

```
RequestAppInstall: .bAllowInstallWhileRunning: false
LogDownloadManager: SetNewActivePosition: User actions are currently blocked.
```

Close the editor first. Same applies to step 1.

## 3. Android Studio

```
winget install --id Google.AndroidStudio -e --accept-package-agreements --accept-source-agreements --silent
```

**Run this in an interactive terminal and accept the UAC prompt.** The installer requires elevation.
If it can't prompt, winget prints `Successfully installed` and exits 0 **having installed nothing**.
Always verify rather than trust the exit code:

```
winget list --id Google.AndroidStudio -e     # must list it
```

You never need to open Android Studio. It's here for two things: its bundled JBR (which becomes
`JAVA_HOME`) and the registry key `HKLM\SOFTWARE\Android Studio` that SetupAndroid.bat reads.

## 4. Command-line tools

Studio's default install omits these, and SetupAndroid.bat drives everything through `sdkmanager`.
Rather than opening Studio's SDK Manager GUI, install them directly.

Resolve the current version from Google's own manifest (don't hardcode a URL — they rotate):

```bash
curl -s https://dl.google.com/android/repository/repository2-3.xml \
  | grep -oE 'commandlinetools-win-[0-9]+_latest\.zip' | tail -1
```

Download, verify the sha1 against the manifest, and extract so that `sdkmanager.bat` ends up at
exactly:

```
%LOCALAPPDATA%\Android\Sdk\cmdline-tools\latest\bin\sdkmanager.bat
```

The `latest` directory name matters — SetupAndroid.bat probes for it literally.

## 5. Accept SDK licenses

```bash
export JAVA_HOME="/c/Program Files/Android/Android Studio/jbr"
SDK="C:/Users/<you>/AppData/Local/Android/Sdk"
yes | "$SDK/cmdline-tools/latest/bin/sdkmanager.bat" --licenses --sdk_root="$SDK"
```

**Use Git Bash, not PowerShell.** Piping `y` from PowerShell into `sdkmanager.bat` silently fails —
it exits 0 while accepting nothing. Verify by checking the files actually exist:

```bash
ls "$SDK/licenses"     # expect 7 files; no directory at all == nothing accepted
```

## 6. Run SetupAndroid.bat

```
"C:\Program Files\Epic Games\UE_5.7\Engine\Extras\Android\SetupAndroid.bat" android-34 35.0.1 3.22.1 27.2.12479018 -noninteractive
```

It installs the pinned SDK/NDK/CMake and persists these **user-scope** env vars:

| Var | Value |
|---|---|
| `ANDROID_HOME` | `%LOCALAPPDATA%\Android\Sdk` |
| `JAVA_HOME` | `C:\Program Files\Android\Android Studio\jbr` |
| `NDKROOT` / `NDK_ROOT` | `%LOCALAPPDATA%\Android\Sdk\ndk\27.2.12479018` |

It also adds `platform-tools` to PATH, which is where `adb` comes from.

> **Restart every shell, IDE, and the Unreal Editor afterward.** Already-running processes keep the
> old empty environment and will report Android as unavailable. This looks exactly like a broken
> install but is only stale env.

Verify — this is the authoritative check:

```bash
"C:/Program Files/Epic Games/UE_5.7/Engine/Binaries/DotNET/UnrealBuildTool/UnrealBuildTool.exe" \
  -Mode=ValidatePlatforms -Platforms=Android
# expect: ##PlatformValidate: Android VALID
```

Note this only validates the Google SDK — it will report `VALID` even if step 1 was skipped.
Both are required.

---

## 7. Package for the headset

```powershell
& "C:\Program Files\Epic Games\UE_5.7\Engine\Build\BatchFiles\RunUAT.bat" BuildCookRun `
  -project="d:\Unreal-Projects\WattleviewGrove\WattleviewGrove.uproject" `
  -noP4 -platform=Android -cookflavor=ASTC -clientconfig=Development `
  -cook -build -stage -pak -package -archive `
  -archivedirectory="d:\Unreal-Projects\WattleviewGrove\Build\Android" `
  -utf8output -nocompileeditor -unrealexe="UnrealEditor-Cmd.exe"
```

Two flags are load-bearing and non-obvious:

- **`-package`** — actually builds the APK and its OBB. Without it, `-stage -pak` lay out the cooked
  content but the archive step fails with `Error_ObbNotFound` (exit 53).
- **`-unrealexe="UnrealEditor-Cmd.exe"`** — enabling OpenXR makes UAT treat this Blueprint project as
  "code-based" and generate temporary `.Target.cs` files. It then looks for a project-specific editor
  receipt (`Binaries\Win64\WattleviewGroveEditor.target`) that doesn't exist and can't be built
  without a C++ toolchain. Pointing it at the stock editor sidesteps this — a Blueprint project
  cooks fine with the stock editor.

First run takes ~10 min (shader compilation dominates). Subsequent runs are ~40 s.

Output: `Build/Android/WattleviewGrove-arm64.apk` (~102 MB) + `main.1.com.rmit.wattleviewgrove.obb` (~62 MB).

## 8. Deploy

```
cd Build\Android
.\Install_WattleviewGrove-arm64.bat
```

Handles the APK install, OBB placement, and permission grants. Ends with `Installation successful`.

Verify:

```bash
adb shell pm list packages | grep wattleview     # com.rmit.wattleviewgrove
```

---

## Device notes

Target is **PICO 4 Ultra Enterprise** (model `A9210`, codename `sparrow`), Android 14 / SDK 34,
arm64-v8a, firmware 5.15.5 (README requires 5.14.0+). It self-identifies in logcat as
`Build: getProduct check PICO 4 Ultra Enterprise`.

Enable developer mode + USB debugging on the headset; `adb devices` should list it as `device`.

### Things that look like bugs but aren't

- **App launches but no engine logs / nothing renders** — check `adb shell dumpsys power | grep mWakefulness`.
  If `Asleep`, the headset simply isn't being worn. The proximity sensor gates the display, and UE's
  `GameActivity` never initialises. Put the headset on.
- **OBB looks missing** — `adb shell ls /sdcard/Android/obb/<pkg>/` returns *Permission denied*, not
  *not found*, because of Android 11+ scoped storage. That's expected; it doesn't mean the OBB is absent.
- **Device timestamps look 30 min stale** — the headset may be on a different timezone to the PC
  (ACST vs AEST). Compare `adb shell date` against the PC clock before concluding anything is old.
- **App disappears from `adb` / `adb devices` empty after it worked** — usually a half-seated USB
  plug or the headset sleeping and dropping the link, not a driver fault. Check
  `Get-PnpDevice | ? FriendlyName -match 'PICO'` in PowerShell — if Windows shows *PICO Composite ADB
  Interface* as OK, the cable/driver are fine; reseat the plug and `adb kill-server; adb start-server`.

---

## PICO controller input (the non-obvious part)

Head tracking and rendering can work perfectly while **controllers are invisible and dead** — no
pose, no render model, no button/thumbstick input, no teleport. This is not a toolchain problem.

**Cause.** UE only suggests an OpenXR interaction profile when a mapping context binds that
profile's keys. PICO 4 controllers report **dedicated FKeys** — `PICOUltra_*` and `PICO4_*`
(registered by the plugin's `PICOOpenXRInput` module, see `PICO_Controller.cpp`). They do **not**
emulate Oculus Touch. The XRFramework template shipped bindings only for Oculus/Vive/Index/WMR, so
the PICO controllers matched nothing.

**Fix (already committed).** Every `OculusTouch_*` binding in the five
`Content/XRFramework/Input/IMC_*` mapping contexts was mirrored to its `PICOUltra_*` and `PICO4_*`
equivalent (PICO's button layout matches Oculus Touch: X/Y/A/B, thumbstick, grip, trigger, menu).
A fresh clone of this repo already has these — nothing to redo. Only relevant if you build a *new*
project or add new input actions: they need PICO key bindings too.

> **Editor gotcha if you re-edit IMCs via Python/MCP:** `EditorAssetLibrary.save_asset(path)`
> defaults to *save-only-if-dirty* and returns `True` without writing when a programmatic edit didn't
> flag the package dirty. The cook then ships the **old** asset while every log says "success". Use
> `save_asset(path, only_if_is_dirty=False)` and confirm the source `.uasset` mtime actually changed.

---

## Project config facts

- Package name: `com.rmit.wattleviewgrove`; display name "Wattleview Grove"
- `MinSDKVersion` / `TargetSDKVersion` = **32**, while the device runs SDK 34. Installs and runs fine;
  revisit if PICO store submission requires a higher floor.
- `OpenXREyeTracker` is **disabled deliberately** — the 4 Ultra Enterprise has no eye-tracking
  hardware (that was the older 4 Enterprise). Don't re-enable it expecting ETFR.
- Rendering is forward + MSAA (`r.Mobile.AntiAliasing=3`). See README for why this conflicts with
  MetaHuman skin.
- PICO controller bindings live in `Content/XRFramework/Input/IMC_*` — see the controller section
  above. Don't strip the `PICOUltra_*` / `PICO4_*` mappings.

## MCP tooling (optional, per-developer)

Not required to build. See [README.md](README.md#mcp-setup-optional-per-developer) — `Plugins/UnrealMCPython`
and `.mcp.json` are gitignored and machine-specific.
