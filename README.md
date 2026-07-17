# SC&H - Wattleview Grove - Dementia VR Experience

Unreal Engine VR experience targeting **PICO 4 Ultra Enterprise**.

- **UE project name:** `WattleviewGroveVR` (code-safe; the full title above is the Project Display Name)
- **Android package:** `com.rmit.wattleviewgrove`

## Platform decisions

| Decision | Choice | Rationale |
|---|---|---|
| Engine | **UE 5.7** | Newest version supported by PICO's actively-maintained Unreal path. |
| PICO plugin | **PICO Unreal OpenXR Plugin v1.6.0** | Actively shipping (~monthly). Application SpaceWarp is stock on 5.7 — no engine fork needed. |
| Target device | **PICO 4 Ultra Enterprise** only | Requires device system version **5.14.0+**. |
| Environment | Authored 3D meshes | Not Gaussian splats — see PICOSplat below. |
| MCP server | GenOrca `UnrealMCPython_5.7` | Epic's first-party Unreal MCP requires UE 5.8, which PICO's docs do not support. |

### Why not UE 5.6

The PICO Unreal **Integration SDK** (UE 4.27/5.5/5.6) is now labelled LTS — maintenance framing. PICO is
steering Unreal developers onto the OpenXR plugin. The 5.6 path also requires PICO's engine fork for
Application SpaceWarp.

### Why not UE 5.8

Epic's `PICO Controller` plugin in 5.8 provides **controller interaction profiles only** — no passthrough,
tracking, anchors, scene understanding, or foveation. No evidence anyone has shipped PICO on 5.8.
Sources conflict on whether PICO's OpenXR plugin supports 5.8: the Fab listing says `5.2 - 5.8`, PICO's
own quickstart doc says `UE 5.6 or 5.7`. **5.7 is correct under both readings.**

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
MetaHumans. Also excluded by Epic's 5.8 PICO Controller plugin by design.

## Repository

Git LFS is required — see `.gitattributes`. Clone with LFS installed:

```
git lfs install
git clone <url>
```

`Binaries/`, `Intermediate/`, `DerivedDataCache/` and `Saved/` are intentionally not tracked.
