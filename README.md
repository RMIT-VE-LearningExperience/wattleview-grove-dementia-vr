# SC&H - Wattleview Grove - Dementia VR Experience

Unreal Engine VR experience targeting **PICO 4 Ultra Enterprise**: two five-minute, non-interactive
stories of the same morning in an aged-care room, seen as David the support worker, as Maria Russo
(82, Alzheimer's disease, moderate stage), and from an observer's corner. Branching choices and
reflection live in the companion web/Canvas experience. See
[Docs/Production/Story_V2_VR_Breakdown.md](Docs/Production/Story_V2_VR_Breakdown.md).

- **UE project name:** `WattleviewGrove` (code-safe; the full title above is the Project Display Name)
- **Engine build:** UE **5.8.4** on branch `ue58` (the 5.7.4 hospital prototype stays on `main`)
- **Android package:** `com.rmit.wattleviewgrove`
- **Project type:** Blueprint: no C++, no Visual Studio toolchain required

Setup and build steps: [CLAUDE.md](CLAUDE.md).

## How the experience is built

| Piece | Asset | Role |
|---|---|---|
| Room | `L_ResidentRoom` | Maria's room: photo by her recliner, table facing the garden window, TV, fan, door to the corridor |
| Timeline | `LS_Story` | One 5:00 sequence for all three viewpoints: viewer anchors, character blocking, perception parameters |
| Director | `BP_StoryDirector` | Reads the chosen viewpoint, attaches the viewer to its anchor, hides the body the viewer is in, plays the story |
| Perception | `MPC_Perception` + `Materials/Perception` | Maria's view only: soft room, glowing photo, haloed gardener, cooling light and dark edges, backyard memory |
| Menu | `WBP_Menu` (XRFramework) | Support worker / Resident / Observer view, Restart, Reset orientation, Exit |

Characters are UE mannequin stand-ins until the MetaHumans (Maria re-authored, David, Enzo) exist.
Voice lines will be generated with ElevenLabs once the script is final.

## Rendering configuration

Created from the UE 5.8 **Virtual Reality** template:

| Setting | Value |
|---|---|
| `r.ForwardShading` | True |
| `r.MobileHDR` | False |
| `vr.MobileMultiView` / `vr.InstancedStereo` | True |
| `r.Mobile.AntiAliasing` | 3 (MSAA) |

Forward + MSAA is the vendor-recommended VR path. **It conflicts with MetaHuman skin**, which needs
Subsurface Profile -> mobile deferred -> which disables MSAA. In 5.8, Subsurface Profile also renders no
scattering on mobile deferred, and VR Preview has a deferred-rendering regression. Stay on forward.
See the MetaHuman notes below.

## Platform decisions

| Decision | Choice | Rationale |
|---|---|---|
| Engine | **UE 5.8.4** | Native PICO support (July 2026): stock OpenXR plus Epic's PICO-authored `PICOController` plugin. No third-party plugin gating engine upgrades. |
| PICO plugin | **None** | The template's mapping contexts already bind `PICO_*` keys. Fixed foveation uses stock `XR_FB_foveation`. |
| Target device | **PICO 4 Ultra Enterprise** | PICO requires device system version **5.14.0+**. Neo 3 is unsupported by 5.8's plugin. |
| Environment | Authored 3D meshes | Not Gaussian splats; see PICOSplat below. |
| MCP server | GenOrca `UnrealMCPython_5.8` | Scripted Blueprint graph edits. Epic's experimental 5.8 MCP server is an alternative. |

### Why UE 5.8 (changed 2026-10-26)

This README used to argue against 5.8, because PICO's own docs listed 5.6/5.7 only. On 2026-07-15 PICO
announced that UE 5.8 runs on PICO devices and the PICO Emulator with no external plugin. 5.8 is at
5.8.4 (2026-10-20). Other wins: half-precision mobile shaders, Blueprint subtitles, better
audio-driven MetaHuman facial animation, and incremental cooking. Not yet confirmed on our headset:
the alpha/whiteout behaviour the 5.7 Fab plugin needed a workaround for, and frame pacing.

### Why not UE 5.6

The PICO Unreal **Integration SDK** (UE 4.27/5.5/5.6) is labelled LTS (maintenance) and needs PICO's
engine fork for Application SpaceWarp.

## Known constraints

### MetaHumans on PICO — unproven, spike before committing

No public performance data exists for a MetaHuman on **any** PICO headset. Epic has never documented
MetaHuman on standalone VR; their platform support page lists PC/Mac/iOS-Android (flat mobile) only.

Epic's Android/mobile ceiling:

- Best LOD **3** (per-vertex blendshapes only run at LOD 0 — unavailable on mobile)
- **Hair cards only**, no strand grooms
- Max texture 2048
- No Nanite, no Lumen

The structural bind: MetaHuman skin needs Subsurface Profile -> needs mobile deferred -> kills MSAA,
but MSAA + forward is the vendor-recommended VR path. At LOD4+ Epic swaps skin to Default Lit anyway.

**Action:** assemble one MetaHuman via the UE 5.6+ **Assembly** pipeline at "UE Optimized/Low"
(drops characters from 1-2 GB to <100 MB), force LOD3, package to a real 4 Ultra, and measure.
Watch draw calls from 283-joint section-chunking in stereo. This measurement decides the art direction.

Framerate is a **safety constraint**, not polish: the audience may include older adults and VR-naive
clinical staff, for whom dropped frames mean nausea.

### No eye tracking

PICO 4 Ultra Enterprise has **no eye-tracking hardware** — that was the older PICO 4 Enterprise.
Rules out eye-tracked foveated rendering (ETFR). Use fixed foveated rendering (FFR), which works on a
stock engine.

### PICOSplat is unusable

UE **5.4 only** (repo has just `main` and `5.4` branches), Beta, PICO 4 Ultra only, and incompatible with
the mobile deferred shading MetaHuman skin requires. No valid combination with current SDKs.

### Dropped: PICO Neo 3

XR2 Gen 1, firmware frozen at 5.13.7 (Oct 2025). Materially harder target; likely a non-starter for
MetaHumans. Also excluded by Epic's 5.8 PICO Controller plugin by design, and its Android 10 /
SDK 29 is below this project's minimum SDK 32.

## MCP setup (optional, per-developer)

The project can be driven from an MCP client (Claude Code) via **UnrealMCPython** by GenOrca.
It is editor-only and Win64-only, so it never ships in the packaged build. It is deliberately
**not committed** - install your own copy:

1. Download from https://github.com/GenOrca/unreal-mcp/releases (v2.2.0):
   - `UnrealMCPython_5.8_2.2.0.zip` - the precompiled plugin (must match the engine version)
   - `UnrealMCPython_Source_2.2.0.zip` - contains the `mcp-server/` folder the plugin zip lacks
2. Extract the plugin to `Plugins/UnrealMCPython/`
3. Copy `mcp-server/` from the source zip into `Plugins/UnrealMCPython/mcp-server/`
4. Pin Python and install deps (Python **3.14 fails** - `pydantic-core` has no wheels for it yet):
   ```
   cd Plugins/UnrealMCPython/mcp-server
   uv python pin 3.12
   uv sync
   ```
5. Create `.mcp.json` in the project root (gitignored - absolute paths are machine-specific):
   ```json
   {
     "mcpServers": {
       "unreal-mcpython": {
         "command": "uv",
         "args": ["--directory", "<abs>/Plugins/UnrealMCPython/mcp-server", "run", "src/unreal_mcp/main.py"]
       }
     }
   }
   ```
6. Launch your MCP client from the project root. The `UnrealMCPython` and `PythonScriptPlugin`
   plugins are already enabled in the `.uproject`.

## Repository

Git LFS is required — see `.gitattributes`. Clone with LFS installed:

```
git lfs install
git clone <url>
```

`Binaries/`, `Intermediate/`, `DerivedDataCache/` and `Saved/` are intentionally not tracked.
