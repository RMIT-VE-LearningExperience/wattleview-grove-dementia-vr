# Wattleview Grove project quality audit

**Date:** 27 October 2026
**Project:** UE 5.8, `D:\Unreal-Projects\WattleviewGrove-ue58`
**Audience:** Lawrence, Claude Code, and any agent continuing the project
**Status:** Active remediation; character mobile-stability pass in progress

## Current work instruction

Lawrence resumed project changes on 28 October 2026.  The current priority is to make Maria and
David's neutral white T-shirt/shorts wardrobe stable through the complete cinematic on PICO before
further character dressing.  A desktop/editor result is not sufficient evidence; the deformation
must be accepted in the headset.

## Update — 28 October 2026, cinematic mobile clothing pass

- Headset observation: Maria and David's lower garments deform much more severely in the PICO
  build than in editor captures, with the shorts stretching downward during motion.
- The live characters use the MetaHuman-assembled `MariaReference_Outfits` and
  `DavidReference_Outfits`, not the older procedural Maria skirt/cardigan asset.
- Both wardrobes are leader-posed from their matching `Body` component.  Their LODSync previously
  remained automatic, allowing the PICO to select a reduced body/wardrobe bone tier during a shot.
- Maria and David are now locked to MetaHuman global LOD 0 in `L_ResidentRoom`.  In this
  Optimized/Medium assembly that evaluates body LOD 0, wardrobe LOD 1 and groom-card LOD 3, keeping
  one matched deformation tier for the whole cinematic.
- Runtime cloth creation/simulation is disabled on both wardrobe components.  Motion comes only
  from the baked skeletal animation clips; the distant gardener remains automatic.
- The repeatable editor step is
  `Scripts/Editor/apply_cinematic_mobile_character_settings.py`; `build_characters.py` applies the
  same settings after future character rebuilds.
- Development PICO build `Build/Profiles/PICO/Development/20261028-162758/Android_ASTC` built and
  installed successfully.  APK SHA-256:
  `2B51C12B5BB67B62067FEF8175E8466C84C2632E902719B51AEAA6F91C8FFA87`; OBB SHA-256:
  `9471B5F7DBAB92E0E7A623E4AB1C0B97D9C6C68E066285E9D9242406067FB987`.
- Android smoke test: package launched and remained alive; no fatal signal, Java fatal exception,
  assertion, ANR or Unreal low-level fatal was found in either package process log.
- **Still pending:** visual headset acceptance through idle, walking, turning and sitting.  Do not
  call the clothing fixed until that test shows no downward stretch, crotch split or shirt/shorts
  separation.

### 17:32 follow-up — root cause and Pico-safe rebuild

- Six close-range device captures under `Saved/HeadsetScreenshots/Codex/20261028-closeup` proved
  that both white outfits had missing triangular regions around the chest, sleeves, waist and
  lower body.  This was GPU skinning corruption, not cloth motion and not a single bad pose.
- A Geometry Script audit measured 7–12 influences per vertex in the assembled outfit LODs while
  this Android build uses the limited GPU-skinning path (`r.GPUSkin.UnlimitedBoneInfluences=0`).
- The untouched MetaHuman originals remain under `/Game/MetaHumans`.  Four-influence, normalized
  copies now live at `/Game/Wattleview/Characters/MobileSafe/*_Outfits_Pico`; all eight LOD checks
  report a maximum of four influences, no zero-weight vertices and no non-normalized vertices.
- `L_ResidentRoom` now assigns those copies to `Maria_StandIn` and `David_StandIn` and preserves
  the Body leader-pose relationship.  `build_characters.py` and
  `apply_cinematic_mobile_character_settings.py` reapply them after future rebuilds.
- Development build `Build/Profiles/PICO/Development/20261028-172938/Android_ASTC` completed and
  installed successfully.  APK SHA-256 is
  `5BF313308F03A2B02FB17DFE0BE4C5E09B99A8ED048E0AD533A27C6539158A3C`; OBB SHA-256 is
  `D16CC6048158B2B85CE108ACB338BAEF2769DA8FA1656C0962A202E02A3675B8`.  The headset slept before post-install captures, so visual device
  acceptance remains pending and the result must not yet be called fixed.
- Computer-side prevention: run `audit_runtime_outfit_weights.py` with the temporary
  `-EnablePlugins=GeometryScripting` command-line option.  Unreal's Android Vulkan Mobile Preview
  should be used for routine material/render checks, but the exact Pico build remains the final
  deformation, XR-compositor and performance authority.

### 17:55 follow-up — physical-headset visual result: failed

- Eight direct headset captures are stored under
  `Saved/HeadsetScreenshots/Codex/20261028-pico-safe-live`.  The user's clearer stereo screenshot
  pair is stored under `Saved/HeadsetScreenshots/User/20261028-latest`.
- The four-influence conversion reduced the former extreme floor-length stretching, but did not
  make the outfits acceptable.  The foreground character still shows an inverted/open armpit,
  jagged sleeve boundary, a narrow shirt strip pulled down the torso, and shredded geometry around
  the hem/shorts.  The older character behind also shows damaged lower clothing.
- Device acceptance is therefore **failed**, not pending.  A maximum of four normalized weights is
  necessary for this limited mobile skinning path but is not sufficient proof that the outfit uses
  a compatible reference pose, bone map, section layout and leader-pose deformation.
- Do not iterate further by pruning weights on these assembled outfit copies.  The next repair must
  start from a body-compatible mobile garment or rebuild/rebind the simple T-shirt and shorts to the
  exact runtime body skeleton and reference pose, then pass Android Vulkan Mobile Preview and the
  same close-range physical-headset capture gate.

### 18:35 follow-up — independent wardrobe-pose build installed; visual check pending

- Epic's Android issue report for generated MetaHuman clothing matches this project: the garment is
  correct on desktop but becomes severely distorted when it follows Body through Leader Pose on the
  Android render path.  Four-influence pruning did not solve that relationship-level failure.
- The level now uses the untouched generated Maria, David, Gardener and Enzo outfit assets.  A small
  runtime world subsystem clears their Leader Pose links after BeginPlay.  `LS_Story` contains a
  matching independent baked animation track for every Body and wardrobe component, so no runtime
  cloth, copying or procedural retarget is required.
- A Win64 game-world smoke test logged all four wardrobe components successfully switching to the
  independent pose path.  The project module compiled for Win64 Editor and Android ARM64.
- Android now uses Epic's documented mobile section limit, `Compat.MAX_GPUSKIN_BONES=75`.
- Development build `Build/Profiles/PICO/Development/20261028-182930/Android_ASTC` built, cooked,
  packaged and installed successfully.  APK SHA-256 is
  `9A9CF2549A7CD32F50E76FE2569DB4AC4D18C224C41DCF9254F3EC0BD836A45B`; OBB SHA-256 is
  `32CC4A152FDA499C1BFC7056CDC4AFE7AD3E68F1224073D831440E243F31F927`.
- The first automated screenshots are black because the headset reports `Asleep`; this is not a
  visual pass or failure.  Final status remains pending a fresh awake close-range capture.
- A Windows Vulkan ES3.1 preview reached BeginPlay and confirmed the runtime wardrobe switch, then
  crashed in NVIDIA's Vulkan driver (`nvoglv64.dll` / Vulkan RHI thread).  Do not use that preview
  crash as evidence about the Android package; use it only to document that this workstation cannot
  currently provide a reliable substitute for the physical Pico visual gate.

### 19:08 follow-up — user headset captures fail; clean-room restart authorised

- The user's 14-frame stereo burst is stored under
  `Saved/HeadsetScreenshots/User/20261028-1738-rigidity`.  It is the acceptance evidence for this
  build; automated captures are not being substituted for it.
- At normal distance, the long rubber-band stretch is reduced, but the T-shirt and shorts behave as
  rigid shells.  Their silhouettes barely respond to shoulder, waist, hip and thigh motion.
- At close range, face/head geometry collapses into red polygonal shapes and hair separates into
  large floating masses.  The independent-pose build therefore **fails** physical-device visual
  acceptance.  It is not a usable compromise.
- Lawrence authorised a total character-pipeline restart.  The existing Wattleview Grove project is
  preserved as evidence and environment work; the failed MetaHuman wardrobe chain will not receive
  further patch iterations.
- A separate clean-room UE 5.8 project now exists at
  `D:\Unreal-Projects\WattleviewCharacterLab-ue58`.  It deliberately excludes MetaHuman,
  Leader Pose, Copy Pose, LODSync, grooms, cloth and modular character components from the first
  validation gates.
- Gate 0 passed Win64 Editor compilation, Android ARM64 compilation, ASTC cook/package, side-by-side
  installation and process launch.  The clean package is `com.rmit.wattleviewcharacterlab`; APK
  SHA-256 is `4679D905B4FF902EFD36F998E0F2522257CD5301529DFC3CC32DFFD6626C89C6`.
  Headset visual confirmation of the empty neutral stage remains pending because the headset was
  sleeping and opened its guardian/seethrough screen after launch.

### 20:28 direction correction — production MetaHumans retained

- The primitive one-mesh figure was useful only for proving that the clean renderer could animate a
  skeletal mesh. Lawrence rejected it as a character direction. It is no longer spawned and must
  not be presented as production work.
- The clean lab now enables the UE 5.8 MetaHuman Character plugin and uses the latest approved
  `MariaAge40Reference` MetaHuman identity, generated body, face, hair, white T-shirt, and shorts.
- The generated MetaHuman and its dependency closure were migrated into the isolated lab. The old
  Wattleview scene Blueprint, garment patches, Leader Pose/Copy Pose chain, and independent-pose
  workaround were not migrated.
- D3D12 static evidence is stored in
  `D:\Unreal-Projects\WattleviewCharacterLab-ue58\Saved\Validation\Maria_Neutral.png` and the
  adjacent `Maria_ViewA.png` / `Maria_ViewB.png`. This passes only the desktop load/appearance gate;
  animation deformation and physical-PICO validation remain pending.
- The next gate is the real MetaHuman under an extreme direct animation. The project will not add
  the remaining cast or reintegrate with Wattleview Grove until Maria passes that motion gate on the
  headset.

## Current conclusion

The project is not ready for visual sign-off or a definitive Pico acceptance test. The resident room is functional and substantially dressed, but several results previously described as fixed do not meet a natural visual standard. The most urgent problems are:

1. Maria's shoulders and neckline remain visibly broken in the current Unreal render.
2. The garment validator produced a technical pass for a result that visibly fails.
3. The corridor and larger room are absent from the active UE5.8 map and therefore cannot be present in its Pico build.
4. Both the four-influence build and the independent-pose build failed physical-headset visual acceptance. Character work has moved to the isolated clean-room project.
5. Maria's natural player tracking and close-proximity recoil from the earlier project were not ported into the UE5.8 rebuild.
6. The current story has no cooked dialogue or ambience tracks.

The word **fixed** must only be used after the applicable technical, visual, motion, in-engine, and device checks all pass. A closed or valid mesh is not automatically a natural-looking asset.

## Source-of-truth snapshot

- Branch / reviewed HEAD: `ue58` / `8eeae8f`.
- The working tree is dirty. Newer map and garment work is not represented by a clean commit.
- Active startup and cooked map: `/Game/Wattleview/Maps/L_ResidentRoom`.
- Latest installed APK: `Build/Profiles/PICO/Development/20261028-182930/Android_ASTC/WattleviewGrove-arm64.apk`.
- That APK/OBB pair is installed on the connected PICO headset; its clothing visual acceptance failed.
- Clean-room package `com.rmit.wattleviewcharacterlab` is installed side-by-side from
  `D:\Unreal-Projects\WattleviewCharacterLab-ue58\Build\Gate0-Pico\Android_ASTC`.
- Current map and BuiltData are aligned, and the latest MapCheck did not report a lighting-rebuild warning.
- Current scene captures are in `Saved/Captures/ScenePhotos` and current Maria garment captures are in `Saved/Captures/GarmentValidation/Maria`.

## Priority definitions

- **P0:** Blocks truthful review, expected content, or the core headset experience.
- **P1:** Strongly damages believability, comfort, or release readiness.
- **P2:** Important polish, maintainability, or performance debt after P0 and P1.
- **Confirmed:** Directly visible in current captures, present in current source/assets, or reported by current logs.
- **Unverified risk:** Evidence shows a credible risk, but the final runtime behaviour still requires a targeted test.

# P0 findings

## P0-01 Maria's shoulders and neckline remain visibly broken

**Status:** Confirmed in the latest Unreal captures.

> **Update, 27 Oct 2026 (evening, Claude):** root cause of the body-coloured wedges found and fixed; the sleeve/shoulder construction still fails review.
> - The wedges were **not** the body mesh. Maria's *face* mesh carries the neck plus a skirt of shoulder skin (out to ~13 cm from the neck, up to z 1.29 m). The proxy-torso cardigan sits up to 5–7 cm below the real trapezius, so that skin showed through. A Maria-only skin material (`Content/Wattleview/Characters/MetaHumanFix/M_skin_unified_baked_NeckHide`, `NeckHide*` parameters) now sinks that skin under the clothes. Two independent reviews (rest probes, 15 story poses × 7 angles, 30 motion frames) found no skin wedges.
> - Still failing (independent naturalness review, FAIL): the sleeves read as separate tubes with angular caps and a step at the armhole; a see-through slit under the back collar; skin visible under the front collar from low angles; a grey transition band at the nape. A shoulder redesign of `build_maria_outfit.py` is in progress.
> - The Optimized body has no torso because the default T-shirt wardrobe item removes it at assembly (body hidden-face map). Re-assembling each character with the Outfits slot cleared gives a full-torso body (`SourceArt/Characters/Bodies/SKM_<Name>_BodyMesh_Full.fbx`, 32k verts, all correctives) — the proper fitting and weight-transfer source for the garment builder. Measured against it, the current cardigan is inside the real body over the shoulder tops (median −0.5 cm, half the verts >5 mm inside) and upper back (p10 −3.8 cm).
> - Research on engine/GitHub routes: `Docs/Production/GitHub_MetaHuman_Clothing_Research_2026-10-27.md` (wardrobe hidden-face maps as the proper replacement for the material trick; GeometryScript weight inpainting; GarmentCode armhole maths for the sleeve).

The hollow sleeve sockets have been capped, but the repair is not visually acceptable. Large flat body-coloured wedges protrude above both shoulders. The sleeve roots look patched and angular, and the blouse, cardigan, and collar overlap with hard gaps and floating edges. This reads as a broken character at normal conversational VR distance.

**Evidence**

- [Front shoulder close-up](../../Saved/Captures/GarmentValidation/Maria/live_04_shoulders.png)
- [Three-quarter garment view](../../Saved/Captures/GarmentValidation/Maria/live_02_three_quarter.png)
- [Rear shoulder close-up](../../Saved/Captures/GarmentValidation/Maria/live_06_rear_shoulders.png)
- [User-reported screenshot](C:/Users/lawre/AppData/Local/Temp/codex-clipboard-dd30a911-92d0-44c2-83f8-12a5fba431d9.png)

**Required result**

Rebuild the upper cardigan as a continuous, naturally shaped shoulder yoke rather than separate safety caps. Integrate the sleeve roots under that surface, smooth normals and clavicle-to-upper-arm weights, make the blouse and collar layering intentional, and mask body faces only where clothing genuinely covers them.

**Acceptance test**

Current Unreal front, three-quarter, profile, rear, and over-shoulder close-ups must show a continuous shoulder slope, clean armholes, and intentional neckline layering. No body slabs, grey gaps, floating edges, zig-zag seams, or visible angular caps are allowed.

## P0-02 The garment coverage validator produced a false pass

**Status:** Confirmed.

The current Blender vertex/ray checks reported zero exposed shoulder vertices even though Unreal visibly renders exposed body wedges. The validation measured geometric coverage, not the final screen-space appearance, and therefore answered the wrong question.

**Evidence**

- [Maria garment builder](../../SourceArt/Characters/Garments/Maria/build_maria_outfit.py)
- [Current Unreal shoulder capture](../../Saved/Captures/GarmentValidation/Maria/live_04_shoulders.png)
- The current `live_*` images are unanimated; the idle, walk, and seated captures predate the latest garment.

**Required result**

Add an Unreal screen-space coverage pass. Render the body with a fluorescent debug material or material/object ID while the clothes use a contrasting neutral material. Define forbidden body-visibility regions for the shoulders, upper torso, hips, and thighs. Body pixels in those regions must fail the test.

**Acceptance test**

The current asset must pass rest, idle, walk, reach, sit 25/45/65/85 percent, and close-player recoil poses from front, three-quarter, side, rear, shoulder, and low seated angles. A separate human naturalness review retains veto power after automated checks pass.

## P0-03 The corridor and larger room are absent from the active UE5.8 map

**Status:** Confirmed.

`L_ResidentRoom.umap` contains no `WG_Corridor_*` or `WG_LargeRoom_*` actors. The current camera positions named corridor and large room instead show a resident-room wall or the exterior garden. The expansion exists only in the older `D:\Unreal-Projects\WattleviewGrove\Content\Maps\HospitalRoom.umap` and related older scripts/captures.

**Evidence**

- [Active engine configuration](../../Config/DefaultEngine.ini)
- [Cook configuration](../../Config/DefaultGame.ini)
- [Current corridor-labelled capture](../../Saved/Captures/ScenePhotos/05_Corridor.png)
- [Current large-room-labelled capture](../../Saved/Captures/ScenePhotos/06_Large_Room.png)
- [Current large-room-window-labelled capture](../../Saved/Captures/ScenePhotos/07_Large_Room_Window.png)
- Older source: `D:\Unreal-Projects\WattleviewGrove\Scripts\Codex\build_corridor_room.py`

This also explains why a teleport destination could place the player outside or on top of the room: the target can exist where the intended floor and enclosing geometry do not.

**Required result**

Migrate or rebuild the expansion inside `L_ResidentRoom`, or use an explicitly loaded and cooked sublevel. Do not migrate the old version unchanged; it is a sterile modular box with visible seams, green colour cast, a saturated red door, minimal furnishing, and no clear destination identity.

**Acceptance test**

In a packaged Pico build, walk through the resident-room door into a complete corridor and then a distinct larger room. Every teleport or anchor destination must land on an interior floor/nav surface. No roof landing, exterior fall-through, blocked doorway, or false capture name is allowed. Captures 05 through 07 must visibly show the spaces named by their filenames.

## P0-04 The current headset does not contain the reviewed project state

**Status:** Confirmed blocker.

The installed `com.rmit.wattleviewgrove` package predates both the newest APK and later map/garment changes. Headset observations currently refer to an older state and cannot confirm the latest fixes or regressions.

**Required result**

When changes resume, package the exact reviewed state and record the Git SHA, dirty state, map/BuiltData times, and APK/OBB hashes in a build manifest. Install and launch that artifact before collecting feedback.

**Acceptance test**

The installed package update time and hash match the reviewed artifact. A smoke test launches `GameActivity`, keeps the process alive, and reports no fatal signal, ANR, assert, or Blueprint runtime error.

## P0-05 Maria's natural tracking and proximity recoil are missing in UE5.8

**Status:** Confirmed source regression.

The current story directly drives skeletal animation through Sequencer and single-node animation. The earlier `ABP_Maria_NaturalLook`, smoothing work, and personal-space recoil implementation are not present in this UE5.8 project.

**Evidence**

- [Current story sequence builder](../../Scripts/Editor/build_story_sequence.py)
- Earlier behaviour exists in the previous project history around commit `310ab58`, not in the current UE5.8 assets.

**Required result**

Port the behaviour as an additive AnimBP or Control Rig layer compatible with Sequencer. Head motion should lead, upper torso contribution should build gradually, and close approach should produce a restrained head/neck lean-back without replacing the story animation.

**Acceptance test**

On Pico, move around Maria through at least plus/minus 90 degrees and vary near/far distance. Her gaze should follow smoothly without snapping, stretching, or stiff whole-body rotation. Story animation must continue underneath. Close approach should produce a subtle, anatomically plausible recoil.

## P0-06 Dialogue and ambience are not cooked into the current story

**Status:** Confirmed missing runtime content.

Story WAV files exist under `Docs/Production/tts_out`, but there are no corresponding Wattleview dialogue or ambience assets under `Content`, and `LS_Story` has no audio tracks.

**Acceptance test**

Import the approved audio, add and time the sequence tracks, then verify the complete story on Pico for dialogue timing, audibility, spatialization, transitions, and clipping.

# P1 findings

## Characters and clothing

| ID | Status | Finding | Acceptance test |
|---|---|---|---|
| P1-CHAR-01 | Confirmed in Blender; Unreal motion unverified | Maria's seated skirt balloons and bridges beneath the hips instead of compressing and folding naturally. The Blender seated harness also stretches limbs into rods and is not a trustworthy final reference. | Live Unreal seated front, side, rear, and low views show one continuous skirt, believable lap compression, and no rear curtain, tunnel, split, or leg show-through. |
| P1-CHAR-02 | Confirmed | Maria's shoes remain oversized and generic, despite the earlier direction to omit shoes if proper ones were unavailable. | Remove them or use correctly proportioned flats that enclose the feet cleanly in rest, walk, and sit. |
| P1-CHAR-03 | Confirmed; Pico check pending | Maria's cardigan pattern aliases, while the skirt and shoes look smooth and plastic. Hair is very white/aliased and skin still looks shiny in validation renders. | At about 0.75 m and 1.5 m in the final room and on Pico, cloth weave remains stable, skin reads matte, hair alpha is stable, and no moire dominates. |
| P1-CHAR-04 | Confirmed risk | David and Enzo import with invalid bind poses and Unreal rebinds them to time zero. | Eliminate the warnings where possible and pass live Unreal rest, walk, reach, and sit views with no detachment, collapse, clipping, or abnormal stretching. |
| P1-CHAR-05 | Confirmed in source previews | David's clothing looks glossy and armour-like, with padded/angular shoulders, a crude collar, and extreme reach/seat stretching. | Final Unreal rest, reach, and seated views show cloth-like forms and clean shirt, belt, trouser, and crotch deformation. |
| P1-CHAR-06 | Confirmed in source previews | Enzo's shirt is inflated and rigid; rolled cuffs look like tubes and collar/pocket pieces look like flat overlays. | Final Unreal rest, reach, and seated views show natural shoulder/cuff forms and clean waist, seat, and trouser deformation. |

## Environment and lighting

| ID | Status | Finding | Acceptance test |
|---|---|---|---|
| P1-ENV-01 | Confirmed | The exterior combines a hard-ended rectangular lawn plane, a photographic panorama, low-poly trees, faceted foliage, and a fence with obvious style/parallax mismatch. | From seated, standing, window-approach, and plus/minus 30 cm head-motion views, no terrain edge is visible and foreground/background horizon, scale, lighting, and style agree. |
| P1-ENV-02 | Confirmed on desktop; Pico pending | Interior lighting is readable but too amber and contrast-heavy for neutral soft 10am daylight. Sun patches approach white while under-table/bed regions are comparatively heavy. | On Pico, cream walls remain neutral, white linen retains detail, timber and rug remain distinct, and shaded areas stay readable. Use the same fixed cameras and device brightness for comparison. |
| P1-ENV-03 | Confirmed implementation limitation | Movable shadow cascades are disabled for performance and characters rely on blob shadows that do not clearly ground them. | Pico video shows soft, stable foot contact with no card edge, sliding, z-fighting, or halo while meeting the agreed frame-time target. |
| P1-ENV-04 | Confirmed by measurement | The bed/wardrobe aisle is 60.9 cm to the frame and 54.9 cm to the linen, below the project's approximately 90 cm aged-care target. | At least 90 cm of continuous clear width, including collision and linen, and a clean Pico traversal. |
| P1-ENV-05 | Confirmed | Chairs and the round table still read as simplified placeholders: thin pads, angular frames, faceted rim, and weak supportive proportions. | Supportive aged-care proportions, credible cushion thickness, correct scale, clean silhouettes at 0.5–2 m, no body/hand intersections, and mobile-appropriate collision/material budgets. |

## VR, performance, and tablet

| ID | Status | Finding | Acceptance test |
|---|---|---|---|
| P1-VR-01 | Unverified high risk | The combined Pico optimizations have never been validated on-device. A prior baseline was about 30 FPS / 26–28 ms GPU; the optimized APK is not installed and no stored `PxrMetric` run exists. | Cold and warm complete runs in every viewpoint sustain at least the frame-synthesis floor, with no repeated over-budget GPU periods, thermal collapse, or visible animation judder. Record `PxrMetric`. |
| P1-VR-02 | Confirmed risk | `r.PSOPrecaching=0` and the project contains no bundled PSO cache, so first-run shader hitches are likely. | Compare cold and warm story runs; add precaching/cache data until first-appearance hitches are absent. |
| P1-VR-03 | Confirmed, behaviour unverified | Default move/turn input is removed, but a 40 cm physical displacement triggers an abrupt pawn correction without sweep or fade. | Test 39/41 cm movement in every direction from seated and standing recenter. No roof/wall relocation or disorienting visible jump. |
| P1-TABLET-01 | Confirmed blocker for tablet target | No tablet build profile, non-XR GameMode, touch input, camera, or tablet-specific package/config exists. Current Android settings start immersive VR. | A separate tablet profile builds and completes the same scene/story flow on a physical Android tablet. |
| P1-TABLET-02 | Confirmed blocker for walking tablet controls | Imported room meshes deliberately use no collision and the map has no navmesh. | Appropriate simple collision and navigation allow complete traversal without falling through, walking through walls, or snagging. |

# P2 findings

| ID | Status | Finding | Acceptance test |
|---|---|---|---|
| P2-01 | Confirmed | The gallery frames are blank olive panels; the TV is a uniform pale-blue screen; the calendar and some narrative displays remain placeholders. | Every visible display has intentional, correctly cropped, non-distracting content that remains legible in the headset. |
| P2-02 | Confirmed | Soft goods still look mechanically cut: slab-like rug and serrated edge, hard bed folds and dark hems, razor-thin curtains, and a flat/ragged recliner throw. | Hems have thickness, folds follow gravity, and no coplanar seams or black hairlines appear at required viewpoints. |
| P2-03 | Confirmed | The memory beat is about 75.2k triangles against the current 60k room budget. The table/fan are faceted, the fence extends past the lawn and lacks an end post, and large lightmap receivers have poor UV coverage. | Meet an explicitly approved budget with Pico evidence; remove visible faceting; ground and terminate the fence; repack large baked receivers and verify clean shadows. |
| P2-04 | Confirmed | Some QA cameras are inside characters or fail to show their named target. Successful file output is currently mistaken for successful evidence. | Pre-capture bounds and target-visibility checks pass; target is visible; viewer bodies, gaze markers, and debug UI are hidden for environment captures. |
| P2-05 | Confirmed pipeline gap | Builds lack traceable manifests, unique versioning, automatic launch checks, crash/log review, and stored performance evidence. | Every build records source state and hashes, installs, launches, smoke-tests, and stores the relevant log and performance evidence. |
| P2-06 | Confirmed pipeline weakness | The Pico build script warns about stale lighting but does not fail. | Build fails when lighting data is stale relative to light-affecting map changes, then validates the packaged mobile-LDR result. |
| P2-07 | Confirmed editor risk | Recent automated editor sessions generated game-thread/render-thread ensures and several crash folders. This does not prove a Pico runtime crash. | A clean editor automation/edit/capture/PIE/close cycle creates no new crash folder or ensure. |

# What is currently good

- The latest bed view no longer shows the stray linen rod or a floating lamp shade.
- The latest room intersection audit found all placed room meshes supported, with no confirmed mesh clashes or missing room props.
- Static furniture shadows are present.
- Current map and BuiltData timestamps are aligned, and recent MapCheck output reports no lighting-rebuild warning.
- ARM64, Vulkan, Android ASTC, and OpenXR immersive packaging are configured, and the latest recorded UAT package completed successfully.
- The PICO 4 Ultra Enterprise is visible over ADB.
- Default move/turn mappings that previously contributed to unintended locomotion have been removed from the current source; the result still requires testing in the current installed build.

# Required validation standard

## 1. Define intent before editing

Record the intended visual or behavioural result and at least one reference. For garments, define which skin regions are intentionally visible. For environments, define scale, lighting time, material character, and viewpoint. For interaction, define natural motion limits and response timing.

## 2. Run structural checks

Check topology, skeleton/import health, material assignments, collision, navigation, light-build state, packaging, and budgets. Structural success only proves that the asset is technically usable.

## 3. Run visual debug checks

Use high-contrast body-coverage materials for garments, collision/navigation views for locomotion, lighting-only and shadow views for illumination, and target-presence checks for captures. Debug checks must measure what a viewer will actually see.

## 4. Review naturalness in standard views

Capture front, rear, side, both three-quarter angles, relevant close-ups, and normal user viewpoints. Review silhouette, construction logic, scale, contact, layering, material response, and whether anything appears physically implausible. Any unexplained artifact fails; do not assume it is intentional.

## 5. Review motion and interaction

Test all representative poses and transitions, including idle, walk, reach, sit, gaze tracking, proximity recoil, viewpoint changes, recentering, and locomotion boundaries. A static pose cannot approve an animated asset.

## 6. Validate in the final runtime

Desktop Unreal captures are useful but cannot approve Pico exposure, aliasing, frame time, comfort, or first-run shader behaviour. Test the exact packaged artifact on the target device. Tablet approval requires its own build, controls, camera, collision, and device test.

## 7. Use independent review with an explicit rubric

An independent reviewer must answer the naturalness questions, not merely repeat the automated result. The earlier garment review failed because every reviewer inherited the narrow question, “Are the sleeve openings closed?” rather than, “Does this look like a naturally constructed garment?”

## 8. Report one honest state

- **Pass:** Every applicable gate passed and evidence is linked.
- **Pass with limitations:** The result is usable, and every known limitation is explicit and accepted.
- **Fail:** Any important visual, behavioural, device, or evidence gate failed or remains unknown.

Do not call a result fixed while a required gate is failed or untested.

# Recommended order when changes resume

1. Repair the validation and capture pipeline so subsequent evidence is trustworthy.
2. Rebuild Maria's shoulders/neckline and validate the current garment through motion.
3. Decide whether to remove or properly replace Maria's shoes.
4. Port Maria's natural tracking and proximity recoil into UE5.8.
5. Restore the corridor and larger room to the active/cooked map, then correct their layout, lighting, and purpose.
6. Address the main resident-room realism issues: exterior integration, chairs/table, neutral daylight, and character grounding.
7. Correct and live-test David and Enzo garments.
8. Add story audio.
9. Produce a traceable Pico build, install it, and complete visual, interaction, crash, and performance acceptance.
10. Build the independent tablet profile and validate it on a physical tablet.

# Related detailed reviews

- [Viewpoint capture review](Viewpoint_Review_2026-10-27.md)
- [Room asset review](Room_Asset_Review.md)
- [Room intersection audit](Room_Intersection_Audit.md)
- [Story V2 VR breakdown](Story_V2_VR_Breakdown.md)
- [Project build and platform notes](../../CLAUDE.md)
