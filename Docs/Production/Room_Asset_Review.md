# Maria's room: per-asset review

| | |
|---|---|
| Date | 2026-10-26. The last inspector and assembly runs finished in the early hours of 2026-10-27. |
| Audience | Lawrence (project lead) |
| Scope | 55 placeholder meshes built in Blender for Maria's room, the garden seen through the window, the memory-beat overlay props and the sky. Every one has an FBX in `SourceArt/Room/Export`. |
| Status | 42 accepted, 13 sent back for revision. Room assembly: 0 clashes, 0 fit/max_x/min_z violations, 0 missing meshes. Nothing was bought. |

Project root: `D:\Unreal-Projects\WattleviewGrove-ue58`. All paths below are relative to it unless written in full.

---

## 1. Purpose and method

You asked for an independent critique of every room asset, not only a group sign-off. This document records it.

**Pipeline**
1. **Builders.** One builder per group, each with its own Blender script in `SourceArt/Room/Items/`: bed, seating, casegoods, tabletop, fixtures, shell and garden (the sky dome is built by `sky.py`). Rules come from `SourceArt/Room/CONVENTIONS.md`. Builders may not edit `placement.json`.
2. **Group reviewers.** One reviewer per group gave a pass or fail. Bed, seating, casegoods, fixtures and shell passed. Tabletop and garden failed, and their blocking items went into the fix rounds.
3. **One independent critic per asset.** Each critic looked at its asset's contact sheet, the story-viewpoint renders and the inspector JSON, and many re-ran the tools themselves. Each gave a verdict (accept or revise), a realism score out of 10 and a list of open problems ranked high, medium or low. Critiques were repeated after each fix round. The verdicts below are from the final pass.
4. **Room intersection audit.** Three rounds, written up in `Docs/Production/Room_Intersection_Audit.md`. It checks every placed piece against every other piece and against the room rules. It also made three small placement edits (Memory_Tomato_0 moved, Gallery_2 and Gallery_4 respaced).
5. **Fix rounds.** Round 1 covered the bed, seating, casegoods, tabletop, fixtures and garden groups. Round 2 covered seating, casegoods (no mesh changes), tabletop, fixtures and garden. The shell group had no fix work.

**Tools**
- `SourceArt/Room/Tools/inspect_asset.py`, run per FBX. It reports triangles, size, pivot, UV layers, material slots, mesh defects, intersecting parts and lightmap UV overlap and coverage. It writes `Previews/Inspect/<asset>.json` and a six-view contact sheet `<asset>_sheet.png`: front (+X), three-quarter and side on row 1; back three-quarter, top and front-left low on row 2.
- `SourceArt/Room/Tools/assemble_room.py -- --render` places every FBX from `placement.json` in Unreal centimetres. It tests every pair of pieces for triangle penetration and checks fit rectangles, curtain max_x and fan min_z. It writes `report.json`, `plan.png` and 14 story-viewpoint renders to `SourceArt/Room/Previews/Assembly*/`.

**Budgets applied** (from CONVENTIONS): room furniture under 60k tris in total. Per piece: bed set 8k, recliner 4k, armchair 3k, table 2k, small prop 300-1,500 (tabletop props 1.2k), curtains 3k per side, garden pieces 3k. At most 4 materials per mesh. Every mesh needs UV0 `UVMap` and UV1 `Lightmap` with no overlap. A 0.2 cm air gap is required where pieces rest on each other.

**Three critiques are out of date.** The final critiques for SM_Bed, SM_Wardrobe and SM_GardenHose measured an earlier export:
- **SM_Bed:** the critique quotes 4,966 tris. The current FBX is 4,286.
- **SM_Wardrobe:** the critique describes hinged doors at 1,400 tris. The current FBX is the sliding-door rebuild: 1,604 tris, 61.7 cm deep, lightmap coverage 0.14.
- **SM_GardenHose:** the critique quotes 2,816 tris. The current FBX is 1,424.

The Tris column below comes from the current inspector JSON. Re-run those three critiques before treating their findings as settled.

**Reading the contact sheets**
- The inspector lights flat faces with view-dependent studio light, so gradients appear on any flat face. Those gradients are not normal errors; a plain test cube shows the same thing.
- The review palette colours by slot name. Vertex-colour variety (flower beds, tomato fruit and ties) therefore shows as flat red. Only the builders' own previews in `Previews/SM_*.png` show the real colours.
- The memory-box critic found that the row-1 "side (from -Y)" view showed the hinge side, which sits at +Y. The view label may name the wrong side.

---

## 2. Summary

**Score spread:** 8/10 for 6 assets, 7/10 for 39, 6/10 for 7, 5/10 for 3. The weakest pieces are all procedural foliage in the garden and memory beat.

**Open problem tags:** H = high, M = medium, L = low. Only one high item remains: the fig leaves.

**Contact sheets:** all in `D:\Unreal-Projects\WattleviewGrove-ue58\SourceArt\Room\Previews\Inspect\`.

| Asset | Verdict | Realism | Tris | Key open problems | Contact sheet |
|---|---|---|---|---|---|
| **Bed** | | | | | |
| SM_Bed | accept | 7 | 4,286 | M: lightmap coverage 0.24. L: smear in the mattress top shading. L: head and foot boards are plain flat slabs. *Critique measured the earlier build.* | `D:\Unreal-Projects\WattleviewGrove-ue58\SourceArt\Room\Previews\Inspect\SM_Bed_sheet.png` |
| SM_BedLinen | accept | 7 | 3,636 | L: crochet blanket drops are board-like. L: flap side drops are flat with a hard edge. L: no visible pillow piping. L: lightmap coverage 0.42. | `D:\Unreal-Projects\WattleviewGrove-ue58\SourceArt\Room\Previews\Inspect\SM_BedLinen_sheet.png` |
| **Seating** | | | | | |
| SM_Recliner | **revise** | 7 | 3,990 | M: throw border looks jagged or torn at 1 m, and the seat part is a flat sheet. L: 114 open edges on hidden faces (light-leak risk in the bake). L: no lift-chair hand control. L: 1.3 cm off-centre in Y. | `D:\Unreal-Projects\WattleviewGrove-ue58\SourceArt\Room\Previews\Inspect\SM_Recliner_sheet.png` |
| SM_Armchair | accept | 7 | 2,920 | M: seat pad is a thin flat slab. M: back pad is a flat tablet; this is the closest thing to "boxy" left in the room. L: no hand-hold slot, and the rear legs are vertical. | `D:\Unreal-Projects\WattleviewGrove-ue58\SourceArt\Room\Previews\Inspect\SM_Armchair_sheet.png` |
| **Casegoods** | | | | | |
| SM_Bedside | accept | 7 | 948 | L: lightmap coverage 0.38 (hidden faces). L: top overhangs the front by only 0.6 cm. L: 3 mm drawer gaps may disappear under MSAA. | `D:\Unreal-Projects\WattleviewGrove-ue58\SourceArt\Room\Previews\Inspect\SM_Bedside_sheet.png` |
| SM_Wardrobe | accept | 7 | 1,604 | *Critique describes the old hinged-door build. Re-critique the sliding-door version.* Lightmap coverage is now 0.14, the lowest in the room. | `D:\Unreal-Projects\WattleviewGrove-ue58\SourceArt\Room\Previews\Inspect\SM_Wardrobe_sheet.png` |
| SM_TVCabinet | accept | 7 | 1,468 | M: lightmap coverage 0.26, worse than before the rebuild. L: D-bar pulls are thin wire with no mounting roses. | `D:\Unreal-Projects\WattleviewGrove-ue58\SourceArt\Room\Previews\Inspect\SM_TVCabinet_sheet.png` |
| SM_TV | accept | 7 | 728 | M: thin post stand makes it read as a computer monitor. M: screen quad sits only 0.3 mm in front of the recessed glass (z-fight risk). L: boxy rear housing. L: one material for every part. | `D:\Unreal-Projects\WattleviewGrove-ue58\SourceArt\Room\Previews\Inspect\SM_TV_sheet.png` |
| SM_TVScreen | accept | 8 | 2 | L: 0.3 mm depth margin. L: square corners inside a rounded recess. In UE, turn off collision and use a low lightmap resolution. | `D:\Unreal-Projects\WattleviewGrove-ue58\SourceArt\Room\Previews\Inspect\SM_TVScreen_sheet.png` |
| SM_Shelf | accept | 7 | 736 | L: corbel reads as a plain cove, not an ogee. L: no fixing detail. L: clipboard sits 1 cm from the shelf end (placement). | `D:\Unreal-Projects\WattleviewGrove-ue58\SourceArt\Room\Previews\Inspect\SM_Shelf_sheet.png` |
| SM_MemoryBox | accept | 7 | 1,128 | M: lightmap coverage 0.25. L: corner straps read as tape. L: hinge leaves and keyhole float slightly. L: lid fused shut, so it cannot open. Local axes are non-standard (length on X). | `D:\Unreal-Projects\WattleviewGrove-ue58\SourceArt\Room\Previews\Inspect\SM_MemoryBox_sheet.png` |
| **Tabletop** | | | | | |
| SM_RoundTable | accept | 7 | 1,904 | M: slender, bistro-like stance (54 cm base under a 95 cm top). M: thin top joint, so the top looks unsupported. L: straight segments visible on the rim at 1 m (audit). | `D:\Unreal-Projects\WattleviewGrove-ue58\SourceArt\Room\Previews\Inspect\SM_RoundTable_sheet.png` |
| SM_Vase | accept | 7 | 1,184 | M: flower eye too large and renders dark green. L: 3-sided stems shimmer. L: sparse foliage. L: lightmap coverage 0.21. | `D:\Unreal-Projects\WattleviewGrove-ue58\SourceArt\Room\Previews\Inspect\SM_Vase_sheet.png` |
| SM_Jug | **revise** | 7 | 1,190 | L: handle bends are faceted and its ends look stuck on (the requested fix was not applied). L: lightmap coverage 0.45. Placement: yaw 200 hides the handle, and the opaque M_Glass reads as ceramic. | `D:\Unreal-Projects\WattleviewGrove-ue58\SourceArt\Room\Previews\Inspect\SM_Jug_sheet.png` |
| SM_Glass | accept | 7 | 512 | L: 32-segment rim looks faceted at 0.3-0.5 m. L: rim is two flat chamfers. L: reads as a plastic beaker (material). | `D:\Unreal-Projects\WattleviewGrove-ue58\SourceArt\Room\Previews\Inspect\SM_Glass_sheet.png` |
| SM_Hairbrush | accept | 7 | 1,178 | M: head outline faceted at 26 segments, and the brush is handled on the timeline. L: cushion cap is a fan, so the pad reads flat. L: lightmap coverage 0.34. | `D:\Unreal-Projects\WattleviewGrove-ue58\SourceArt\Room\Previews\Inspect\SM_Hairbrush_sheet.png` |
| SM_CallBell | accept | 7 | 1,196 | L: bezel faceted at 0.5 m. L: round underside, so it looks balanced on a keel. L: small button and no LED. L: coil is a hexagonal helix. | `D:\Unreal-Projects\WattleviewGrove-ue58\SourceArt\Room\Previews\Inspect\SM_CallBell_sheet.png` |
| SM_DayDateClock | accept | 7 | 728 | L: the readout exists only in the Blender preview and needs a UE material override. L: screen is one 24-vertex n-gon. L: plain back. | `D:\Unreal-Projects\WattleviewGrove-ue58\SourceArt\Room\Previews\Inspect\SM_DayDateClock_sheet.png` |
| SM_Clipboard | accept | 7 | 1,000 | L: top-sheet curl is kinked. L: paper renders grey, with no printed chart. L: plain clip. | `D:\Unreal-Projects\WattleviewGrove-ue58\SourceArt\Room\Previews\Inspect\SM_Clipboard_sheet.png` |
| SM_Madonna | **revise** | 6 | 1,192 | M: head is a separate island floating 0.3 cm off the figure, with no neck. M: 12-gon halo floats. M: 14-gon plinth, and the crown ends in a point. L: all white with no blue mantle (needs a new slot). L: lightmap coverage 0.40. | `D:\Unreal-Projects\WattleviewGrove-ue58\SourceArt\Room\Previews\Inspect\SM_Madonna_sheet.png` |
| SM_Rosary | accept | 7 | 1,200 | L: regular clover-shaped loop. L: flat cut-out crucifix. L: octagonal medal. L: lightmap coverage 0.10. | `D:\Unreal-Projects\WattleviewGrove-ue58\SourceArt\Room\Previews\Inspect\SM_Rosary_sheet.png` |
| **Fixtures** | | | | | |
| SM_FloorLamp | accept | 7 | 1,440 | M: no power cord or switch. L: spider arms float. L: 22-segment base looks faceted. L: foot ring coplanar with the floor. | `D:\Unreal-Projects\WattleviewGrove-ue58\SourceArt\Room\Previews\Inspect\SM_FloorLamp_sheet.png` |
| SM_CeilingFan | accept | 7 | 1,400 | M: blade tips faceted. L: brackets float under the motor. L: 20-segment lathe. L: canopy coplanar with the ceiling (audit). | `D:\Unreal-Projects\WattleviewGrove-ue58\SourceArt\Room\Previews\Inspect\SM_CeilingFan_sheet.png` |
| SM_Curtains | accept | 7 | 6,360 | L: rings are 8x3 faceted wire with nothing joining them to the fabric. L: clamped straight edge and kink beside the TV cabinet. L: 6,360 tris against a 6,000 budget. M_Curtain must be Two Sided. | `D:\Unreal-Projects\WattleviewGrove-ue58\SourceArt\Room\Previews\Inspect\SM_Curtains_sheet.png` |
| SM_CurtainRod | **revise** | 7 | 1,494 | M: finial balls look like lemons (4-point profile, new in round 2). L: 22 mm rod looks thin across 3.9 m. L: rose rims faceted at 0.3-0.5 m. | `D:\Unreal-Projects\WattleviewGrove-ue58\SourceArt\Room\Previews\Inspect\SM_CurtainRod_sheet.png` |
| SM_Rug | accept | 7 | 1,476 | M: up close the fringe reads as pinked felt, not cord. L: 4-segment corners. L: jute UV runs onto the fringe. | `D:\Unreal-Projects\WattleviewGrove-ue58\SourceArt\Room\Previews\Inspect\SM_Rug_sheet.png` |
| SM_PlantPot | **revise** | 6 | 1,496 | M: 18-segment pot and saucer look faceted, with a weak rim. M: leaves overhang the sill by about 2.5 cm. L: single-sided florets will cull. L: lightmap coverage 0.16. | `D:\Unreal-Projects\WattleviewGrove-ue58\SourceArt\Room\Previews\Inspect\SM_PlantPot_sheet.png` |
| SM_PhotoFrame_MariaEnzo | accept | 8 | 174 | M: photo UVs run under the mat, so 11-13% of the image is hidden at each edge. L: 33 x 28 cm window is not a standard print ratio. | `D:\Unreal-Projects\WattleviewGrove-ue58\SourceArt\Room\Previews\Inspect\SM_PhotoFrame_MariaEnzo_sheet.png` |
| SM_PhotoFrame_Small | accept | 7 | 142 | M: thin, generic moulding. M: no mat. L: the same mesh is used 3 times on one wall. | `D:\Unreal-Projects\WattleviewGrove-ue58\SourceArt\Room\Previews\Inspect\SM_PhotoFrame_Small_sheet.png` |
| SM_PhotoFrame_Wide | accept | 7 | 174 | M: photo UVs run under the mat (9-13% hidden per edge), and the window is 1.66:1. L: timber UV0 is a single projection. | `D:\Unreal-Projects\WattleviewGrove-ue58\SourceArt\Room\Previews\Inspect\SM_PhotoFrame_Wide_sheet.png` |
| SM_Calendar | **revise** | 6 | 1,346 | M: the sticky notes the brief asks for were removed. L: wire binding is sparse. L: month title is a solid black bar, and the grid has no numerals. The picture band needs its own M_Photo instance. | `D:\Unreal-Projects\WattleviewGrove-ue58\SourceArt\Room\Previews\Inspect\SM_Calendar_sheet.png` |
| **Shell** | | | | | |
| SM_Floor | accept | 7 | 12 | M: visible top gets only about 20% of the lightmap. L: no edge strip at the door. | `D:\Unreal-Projects\WattleviewGrove-ue58\SourceArt\Room\Previews\Inspect\SM_Floor_sheet.png` |
| SM_Ceiling | accept | 7 | 12 | M: visible underside gets about 20% of the lightmap. L: bare ceiling (no light, smoke detector or sprinkler). | `D:\Unreal-Projects\WattleviewGrove-ue58\SourceArt\Room\Previews\Inspect\SM_Ceiling_sheet.png` |
| SM_Wall_North | accept | 7 | 52 | M: buried corner strips may bake dark seams at the window-wall corners. M: most of the lightmap goes on hidden faces. L: sill rebate is flush, with no air gap. | `D:\Unreal-Projects\WattleviewGrove-ue58\SourceArt\Room\Previews\Inspect\SM_Wall_North_sheet.png` |
| SM_Wall_South | accept | 7 | 12 | L: only about 32% of the lightmap is on the room face. L: single quad, and UE's default lightmap resolution is too low for it. | `D:\Unreal-Projects\WattleviewGrove-ue58\SourceArt\Room\Previews\Inspect\SM_Wall_South_sheet.png` |
| SM_Wall_East | accept | 7 | 12 | M: exterior face gets the same lightmap share as the interior. L: corner overlaps the north wall. L: no bedhead service panel. | `D:\Unreal-Projects\WattleviewGrove-ue58\SourceArt\Room\Previews\Inspect\SM_Wall_East_sheet.png` |
| SM_Wall_West | accept | 8 | 28 | L: about 45% of the lightmap is on the room face. L: corner volumes duplicated with neighbouring walls. L: sliver triangles from the door cut. | `D:\Unreal-Projects\WattleviewGrove-ue58\SourceArt\Room\Previews\Inspect\SM_Wall_West_sheet.png` |
| SM_Skirting | accept | 8 | 920 | M: about 52% of the lightmap is on hidden back and bottom faces. L: 2 mm slit at each architrave. | `D:\Unreal-Projects\WattleviewGrove-ue58\SourceArt\Room\Previews\Inspect\SM_Skirting_sheet.png` |
| SM_Cornice | accept | 8 | 880 | L: half the lightmap is on hidden back faces. L: needs a raised lightmap resolution for the cove shadow. | `D:\Unreal-Projects\WattleviewGrove-ue58\SourceArt\Room\Previews\Inspect\SM_Cornice_sheet.png` |
| SM_WindowFrame | accept | 7 | 1,280 | M: lightmap margin is 1%, against the 2% rule. L: 6 cm bare strip behind the window board. L: 2 mm slit round the frame (light-leak risk). L: no handles or restrictor. | `D:\Unreal-Projects\WattleviewGrove-ue58\SourceArt\Room\Previews\Inspect\SM_WindowFrame_sheet.png` |
| SM_Door | accept | 7 | 1,436 | L: hinge knuckles float, with no leaves. L: raised fields barely read. L: no kick plate. L: corridor face takes half the lightmap. | `D:\Unreal-Projects\WattleviewGrove-ue58\SourceArt\Room\Previews\Inspect\SM_Door_sheet.png` |
| SM_DoorFrame | accept | 8 | 604 | L: architrave stands only about 1.5 mm proud of the skirting. L: flat field. L: lining only 0.8 cm thick. | `D:\Unreal-Projects\WattleviewGrove-ue58\SourceArt\Room\Previews\Inspect\SM_DoorFrame_sheet.png` |
| SM_DoorHandle | accept | 7 | 1,314 | M: rose and escutcheon rims faceted at 0.5 m. L: blunt lever tip. L: escutcheon smaller than the rose. | `D:\Unreal-Projects\WattleviewGrove-ue58\SourceArt\Room\Previews\Inspect\SM_DoorHandle_sheet.png` |
| **Garden and sky** | | | | | |
| SM_Lawn | accept | 7 | 1,750 | M: undulation is flattened exactly where the viewer looks. L: raw cut edge at the perimeter. L: one huge lightmap island. | `D:\Unreal-Projects\WattleviewGrove-ue58\SourceArt\Room\Previews\Inspect\SM_Lawn_sheet.png` |
| SM_FlowerBed | **revise** | 6 | 2,918 | M: plant cores show as faceted green rocks. M: geranium heads read as cut gems, and there are too few. L: plain box timber edge. L: beds 2.3 cm apart. Relies on M_FlowerRed using VertexColor. | `D:\Unreal-Projects\WattleviewGrove-ue58\SourceArt\Room\Previews\Inspect\SM_FlowerBed_sheet.png` |
| SM_GardenTree_A | **revise** | 6 | 2,454 | M: foliage reads as smooth, glossy pods. L: lightmap coverage 0.29. L: box-projected bark UVs. L: no root flare. | `D:\Unreal-Projects\WattleviewGrove-ue58\SourceArt\Room\Previews\Inspect\SM_GardenTree_A_sheet.png` |
| SM_GardenTree_B | **revise** | 5 | 2,926 | M: dark faces shade as jagged triangles (normals bug). M: crown reads as separate balls. L: wood takes a third of the budget. L: lightmap coverage 0.30. | `D:\Unreal-Projects\WattleviewGrove-ue58\SourceArt\Room\Previews\Inspect\SM_GardenTree_B_sheet.png` |
| SM_Shrub | **revise** | 5 | 2,864 | M: crystalline, faceted surface. M: spiky outline. L: one flat material. L: stems poke out, and the canopy hovers about 1.5 cm. | `D:\Unreal-Projects\WattleviewGrove-ue58\SourceArt\Room\Previews\Inspect\SM_Shrub_sheet.png` |
| SM_Fence | accept | 7 | 1,516 | M: 4 mm paling gaps cause moiré from 20 m. M: 12 instances cost 18.2k tris for a background prop. L: posts at z 0 may float over lawn dips. The end post is not placed. | `D:\Unreal-Projects\WattleviewGrove-ue58\SourceArt\Room\Previews\Inspect\SM_Fence_sheet.png` |
| SM_GardenBench | accept | 7 | 1,708 | M: straight, constant-section members give a flat-pack look. L: shallow 38.8 cm seat. L: slat ends finish flush under the arms. | `D:\Unreal-Projects\WattleviewGrove-ue58\SourceArt\Room\Previews\Inspect\SM_GardenBench_sheet.png` |
| SM_TomatoPlant | **revise** | 6 | 2,970 | M: leaflets are hard polygons. M: the stake dominates the silhouette. L: coarse fruit and mound. L: lightmap coverage 0.15. Also counts against the memory-beat budget. | `D:\Unreal-Projects\WattleviewGrove-ue58\SourceArt\Room\Previews\Inspect\SM_TomatoPlant_sheet.png` |
| SM_BasilPot | **revise** | 6 | 2,966 | M: 20-30% of leaves render near-black (back faces). L: squat at 22.7 cm. L: stems float 4.5 mm above the soil. About twice the 1,500 small-prop budget (audit). | `D:\Unreal-Projects\WattleviewGrove-ue58\SourceArt\Room\Previews\Inspect\SM_BasilPot_sheet.png` |
| SM_FigTree | **revise** | 5 | 2,896 | **H: leaves read as maple stars, not fig.** M: bark shades in faceted bands. M: flat 12-gon mound with no root flare. L: figs are on M_Soil. | `D:\Unreal-Projects\WattleviewGrove-ue58\SourceArt\Room\Previews\Inspect\SM_FigTree_sheet.png` |
| SM_GardenHose | accept | 7 | 1,424 | M: tall stacked coil, not loose flat loops. L: body is on M_Plant, the foliage material. *Critique quoted the earlier 2,816-tri build.* | `D:\Unreal-Projects\WattleviewGrove-ue58\SourceArt\Room\Previews\Inspect\SM_GardenHose_sheet.png` |
| SM_SkyDome | accept | 7 | 2,208 | M: 2048 x 1024 texture is too low-resolution for PICO. M: must be unlit, cast no shadow and have no lightmap in UE, or it blocks the bake. L: park panorama with rooftops, not a clear sky. L: blown-out zenith. | `D:\Unreal-Projects\WattleviewGrove-ue58\SourceArt\Room\Previews\Inspect\SM_SkyDome_sheet.png` |

SM_Fence_EndPost (108 tris, sheet `D:\Unreal-Projects\WattleviewGrove-ue58\SourceArt\Room\Previews\Inspect\SM_Fence_EndPost_sheet.png`) is exported but not placed, and had no critique.

---

## 3. Notes by group

### Bed (SM_Bed, SM_BedLinen)
- **Group review:** passed.
- **Fix round 1:**
  - Removed the stepped hem on the turned-back flap with a stiffer sim plus an ironing pass.
  - Subdivided and smoothed the propped pillow.
  - Brought the bed set from 8,948 to 7,922 tris (bed 4,286, linen 3,636), now under the 8k budget.
- **Now:** both pieces read as a made electric aged-care bed. Two items remain unfixed:
  - The duvet thins almost to zero thickness at a few fold crests. This was done to avoid self-intersection; a relax pass collapsed the roll into the mattress.
  - The crochet blanket still reads as boards.
- The SM_Bed critique was written against the 4,966-tri build, so its castor and budget notes may no longer apply.

### Seating (SM_Recliner, SM_Armchair)
- **Group review:** passed.
- **Fix rounds 1 and 2 (recliner):**
  - Rebuilt the throw as a two-ply folded knit with a scalloped, rolled border and 0 self-intersections.
  - Added stuffing crowns to the arms and back, and real piping cord.
- **Recliner, still revise:** the throw border looks crinkled at 1 m, and the seat run is a flat sheet.
- **Why:** the cloth sim crumpled or sank into the chair with self-collision on, and the 4k budget limits fold detail.
- **Armchair:** never changed. Its flat seat and back pads are the most box-like surfaces left in the room.

### Casegoods (Bedside, Wardrobe, TVCabinet, TV, TVScreen, Shelf, MemoryBox)
- **Group review:** passed.
- **Fix round 1:**
  - TV cabinet rebuilt from separate boards.
  - Memory box redesigned as a keepsake chest (plinth, overhanging lid, plaque, escutcheon, hinges).
  - Wardrobe changed to bypass sliding doors, which removes the door-swing clash with the bed.
- **Fix round 2:** no mesh changes. The wardrobe-to-bed aisle went to you as a placement decision (section 4.3).
- **Still open:**
  - These pieces have the room's lowest lightmap coverage: wardrobe 0.14, memory box 0.25, TV cabinet 0.26.
  - The TV's post stand reads as a computer monitor.
  - Shaker door panels are recessed only 0.4 cm, so they may read flat in VR.

### Tabletop (RoundTable, Vase, Jug, Glass, Hairbrush, CallBell, DayDateClock, Clipboard, Madonna, Rosary)
- **Group review:** failed, on diamond-shaped rosary beads and a faceted call bell.
- **Fix round 1:**
  - Fixed the rosary and call bell.
  - Rebuilt the vase and jug, refilled the hairbrush pins and gave the clock a readout texture.
  - Rebuilt the Madonna.
  - Fixed a `uvs()` bug that had left Lightmap as the active UV on every tabletop piece.
- **Fix round 2:**
  - Cleared the Madonna's 35 self-crossing face pairs.
  - Gave the jug's rim and spout 32 segments.
- **Still revise:**
  - **Madonna:** the head and halo float as separate islands, and the plinth is visibly faceted. The piece is at 1,192 of 1,200 tris.
  - **Jug:** the handle bends are faceted, because the builder coarsened them to pay for the rim.
- Everything else is accepted at 7/10.

### Fixtures (FloorLamp, CeilingFan, Curtains, CurtainRod, Rug, PlantPot, three PhotoFrames, Calendar)
- **Group review:** passed.
- **Fix round 1:**
  - Fixed the inverted left curtain panel and added proper hems.
  - Rebuilt the curtain rod brackets and added a centre support.
  - Rebuilt the rug fringe and repacked its lightmap (coverage 0.85, the best in the room).
  - Rebuilt the plant pot.
- **Fix round 2:**
  - Removed the stair-step kinks from the curtain folds.
  - Put the geranium florets on pedicels.
  - Turned the calendar into a month calendar.
- **Still revise:**
  - **CurtainRod:** new 4-point finial profile from round 2.
  - **Calendar:** sticky notes removed, sparse wire binding.
  - **PlantPot:** at 1,496 of 1,500 tris, with faceting and the sill overhang still there.
- The photo frames score well, but two of them hide 9-13% of each photo under the mat because of how the photo UVs are laid out.

### Shell (Floor, Ceiling, four Walls, Skirting, Cornice, WindowFrame, Door, DoorFrame, DoorHandle)
- **Group review:** passed. No fix work was needed.
- **Scores:** four of the six 8/10 scores are here (Wall_West, Skirting, Cornice, DoorFrame).
- **Shared issue:** lightmap texels go to hidden faces (exterior wall faces, slab tops and bottoms, skirting and cornice backs). The visible room faces get only about 20-45% of each lightmap.
- **Other items:**
  - Buried corner strips could bake dark seams at the window-wall corners.
  - The window frame has a 1% lightmap margin and a 2 mm slit that may leak light.
  - The door hinges have no leaves.

### Garden and sky (Lawn, FlowerBed, Tree A, Tree B, Shrub, Fence, Bench, Tomato, Basil, Fig, Hose, SkyDome)
- **Group review:** failed. The blocking items were:
  - dark "core" polyhedra on the fig
  - single-colour flower beds
  - the hose on a foliage material
  - tomato mounds sinking into the rug
  - the fence running past the lawn
- **Fix rounds 1 and 2:** rebuilt most pieces.
  - The fig cores are gone.
  - Daisies were merged into the bed with vertex colours.
  - Tree A now has a clean gum fork.
  - Tree B now has an upright oval habit.
  - The shrub is a dome with no see-through tunnel.
  - Tomato leaflets now have midribs.
  - The memory tomatoes now rest on the rug.
- **Still revise:** 7 of these 12 pieces (FlowerBed, Tree A, Tree B, Shrub, Tomato, Basil, Fig). Procedural foliage at 3k tris keeps coming out faceted or toy-like.
- **Still open from the group review:**
  - The hose is still on M_Plant.
  - The fence and end post are a placement decision.
- **Sky dome:** the mesh is fine. The texture resolution and UE setup are the risks.

---

## 4. What is still open, and why

### 4.1 The 13 revise verdicts

| Asset | Main remaining problem | Why it was not fixed |
|---|---|---|
| SM_FigTree | Leaves are spiky 5-point stars (maple look); faceted bark; flat 12-gon mound | 3k budget: bark takes about 1,080 tris, leaving about 114 leaves. One vertex per lobe tip gives the spikes. |
| SM_GardenTree_B | PlantDark faces keep flat normals; crown reads as separate balls | Smoothing only covers the M_Plant slot. Dark faces are assigned per triangle on a decimated mesh. |
| SM_Shrub | Crystalline facets and a spiky outline | 7 cm Voronoi cells sit on a mesh with about 5 cm vertex spacing. No smoothing pass after the decimate. |
| SM_GardenTree_A | Glossy pod foliage | The 1,850-tri canopy decimate and soft normals erase the displacement detail. |
| SM_FlowerBed | Faceted cores and gem-like flower heads | 3k budget alongside a 538-tri bed shell: 20 tris per core, 18 per head. |
| SM_TomatoPlant | Polygon leaflets; stake-dominated silhouette | The critics asked for more triangles; the room audit asks for about 2k. These conflict and need your call (4.3). |
| SM_BasilPot | Near-black leaf backs; 2,966 tris | Making the leaves double-sided costs about 1,500 tris. The builder worked to the 3k garden cap, while the audit applies the 1.5k small-prop cap. |
| SM_PlantPot | 18-segment faceting; leaves over the sill edge | At 1,496 of 1,500 tris. Segments were cut to pay for the florets. The sill overhang was not addressed. |
| SM_Madonna | Floating head and halo; faceted plinth; no blue | At 1,192 of 1,200 tris. A blue mantle needs a new slot. The head gap came from a round-1 clearance instruction. |
| SM_Calendar | Sticky notes removed; sparse wire | The notes were dropped instead of re-slotted when M_Flower was removed. The wire was not reworked. |
| SM_CurtainRod | Lemon-shaped finials; thin rod | The finial profile regressed in round 2. The rod radius was never changed. |
| SM_Recliner | Ragged throw border; flat seat run; open hidden shells | Cloth sim instability and the 4k budget. The hidden-face openings are a known shortcut. |
| SM_Jug | Faceted handle bends | Handle triangles were moved to the rim and spout in round 2 (1.2k budget). |

### 4.2 Issues across many assets
- **Lightmap coverage is low almost everywhere.** There is no overlap anywhere, but many pieces use under 0.3 of UV1: wardrobe 0.14, tomato 0.15, plant pot 0.16, flower bed 0.19, vase 0.21, rosary 0.10. The shell pieces spend about half of their lightmap on faces nobody sees. There are two remedies:
  - One shared repack pass: concave pack with rotation and a 2% margin, plus deleting or shrinking hidden faces.
  - Per-mesh lightmap resolutions in UE.
- **Lightmap margin rule conflict:** the seating pieces pack to about a 1.6% gap and the window frame to 1%, against the 2% rule. Decide which wins over coverage.
- **Single-sided foliage and fabric:** fig, basil, tomato, flower-bed florets and curtains. They need Two Sided materials in UE, and the basil and tomato backs will still shade dark.
- **Budgets:**
  - Room furniture is 56,026 tris, under 60k.
  - The memory beat adds 19,162, for about 75.2k.
  - Curtains: 6,360 against 6,000.
  - Basil: 2,966 against the 1,500 small-prop limit.
- **Faceting on curved parts** is the most common low item: fan blades, hairbrush, door handle rose, call bell, finials and plant pot. Most pieces are at their budget, so fixing it means moving triangles off hidden geometry.

### 4.3 Waiting on your decision (placement.json and conventions are yours)
1. **Wardrobe-to-bed aisle:** 60.9 cm to the frame and 54.9 cm to the bedspread, against about 90 cm aged-care practice. Options:
   - **(A)** Move the bed and bedside +35.5 cm in X, with the clock and rosary following. This gives 90.4 cm.
   - **(B)** Move the wardrobe to Y 92-232 and rebuild it 140 cm wide.
   - Accept the current aisle.
   The sliding doors already remove the door-swing clash.
2. **Memory-beat budget:** set a separate budget, hide room props during the beat, or cut the tomato to about 2k and the basil to 1.5k or less.
3. **New material slots** (any unlisted slot renders magenta):
   - M_CeramicBlue, for the Madonna mantle.
   - M_RubberGreen, or tint M_Rubber, for the hose.
   - M_BarkPale and/or M_PlantGrey, for the eucalypt.
   - A brown slot for the flower eyes, or change M_PlantDark to olive-brown.
4. **Placement edits suggested by builders and critics:**
   - Jug yaw to about 110-140 so the handle shows.
   - Call bell on the dining table, or move it to the bedside or bed rail.
   - Drop Garden_Fence_11 (it overhangs the lawn end at Y 2000) and place SM_Fence_EndPost, or extend the lawn to Y 2110 or more.
   - Confirm the Memory_Fig framing (it fills the right window pane).
   - MemoryBox yaw 0 instead of 90, so the mesh can follow the +X front rule.
   - Flower beds and bench sit about 0.8 cm into the lawn.
   - Curtain hem beside the TV cabinet: pull the panel in, or shorten the cabinet to about 105 cm.
5. **Garden hose:** keep the stacked coil on the table, lay it flat in loose loops, or move it to the lawn.
6. **From the shortlist:** who the purchasing entity is (this sets the Fab licence tier), and RMIT's policy on AI-generated assets.

### 4.4 Unreal setup hand-offs (not mesh fixes)
- **M_FlowerRed** must use VertexColor as base colour with a neutral tint. Otherwise every flower bed, tomato fruit and tomato tie renders red.
- **Two Sided materials:** M_Plant, M_PlantDark, M_FlowerRed and M_Curtain.
- **Day-date clock:** per-instance override on its M_Screen slot, using MI_DayDateClockScreen with `SourceArt/Room/Export/T_DayDateClock_Screen.png`, unlit or emissive. The TV shares M_Screen.
- **Calendar:** the picture band needs its own M_Photo instance, separate from the photo frames.
- **Tree A:** pale-bark and grey-olive material instances. **Figs:** currently on M_Soil. **Hose:** currently on M_Plant.
- **Sky dome:** unlit, Cast Shadow off, no lightmap, emissive at 1 or below. Also replace the 2048 x 1024 texture (see section 5).
- **SM_TVScreen:** no collision, low lightmap resolution.

### 4.5 Re-run before relying on them
- The SM_Bed, SM_Wardrobe and SM_GardenHose critiques: they measured earlier exports (section 1).
- The bench and fence critiques quote lightmap coverage from before their re-unwrap. The current figures are 0.19 and 0.20.

---

## 5. Pieces that most deserve a paid Fab replacement

Candidates and prices come from `Docs/Production/Asset_Shortlist.md` (2026-10-26). Prices are USD at the Professional tier; multiply by about 1.42 for AUD. Nothing has been bought, and buying or claiming is your step.

Any pack mesh must still meet the per-piece budget, have clean lightmap UVs and use at most 4 materials. Use the low-poly duplicates (Nanite off) and cap textures at 1-2K. Never copy a pack's config files into the project.

Ranked by how far the Blender placeholder falls short and how much a pack would help:

| Rank | Replace | Current | Shortlist candidate | Pro USD | Notes |
|---|---|---|---|---|---|
| 1 | SM_FigTree | 5/10, high item | Fig (TtjDjg) leaf atlas, ScansLibrary (Should) | 14.99 | Scanned leaf cards on the existing Blender branch frame. Fab has no mobile-ready fig tree (Razor 3D, CropCraft and gold3dlab were rejected). |
| 2 | SM_TomatoPlant, SM_BasilPot | 6/10, over budget | Vegetable Plants, Dexsoft (Must, pick one) **or** 3D Farm & Vegetable Plants Mega Pack, HKhalife | 59.99 or 69.99 | HKhalife covers basil but is UE 5.7 only, with 4K textures to downscale. Dexsoft has LODs and 2K textures, but no basil listed. Check tri counts against the memory-beat budget. |
| 3 | SM_GardenTree_A, SM_GardenTree_B, SM_Shrub | 5-6/10 | Rural Australia, Epic (Must, free) for eucalypts; Realistic Trees 2, Defuse (Should) for the ornamental tree; Garden Plants Pack, G-Star (Should) for shrubs | Free / 9.99 / 19.99 | Trees are seen at 10-20 m through the window, so bake impostors where per-mesh tris are high. Rural Australia per-mesh tris were not captured. |
| 4 | SM_FlowerBed | 6/10 | Garden Flowers Pack, letsmakecoolart (Should), plus G-Star; optionally Flower Beds, Dekogon (Could) for the timber planter | 39.99 (+36.99) | Up to 8,740 tris per flower asset, and there are 7 beds: instance sparingly. |
| 5 | SM_Madonna | 6/10 | Virgin Mary (3D Scan), Eddie Mauro (Should) | Free | A 145k-tri scan. Decimate to about 1.2k and bake normal and colour maps at 512-1K. Not drop-in. |
| 6 | SM_Jug, SM_Glass | 7/10, jug revise | Hospital Room, 3DEverything (Should) | 29.99 | Jug, plastic glass, clock and more, at 200-2,800 verts each. UE 5.5 only, so migrate. Give the glass an opaque material. |
| 7 | SM_Armchair, SM_RoundTable | 7/10, flat pads, slender table | Round Table And Chairs, Vilson Pistori (Should, free); or Suburbs VOL.3 Retro Furniture, Dekogon (Should) | Free / 52.99 | The most-seen furniture in Maria's seated view. Specs for the free set were not captured. |
| 8 | SM_SkyDome texture | 7/10 | No purchase needed: Poly Haven `qwantani_noon_puresky` (CC0), tonemapped to a 4K LDR equirect. Skies, Leeyo Atelier (Could) is the fallback. | Free (23.99) | The current texture is a 2K park panorama with rooftops. The brief asked for clear sky. |
| 9 | SM_Lawn material | 7/10 | Lawn Grass surface, Quixel Megascans (Should) | Free | Texture for M_Grass; keep the mesh. |

**Keep in Blender (no better source on the shortlist):**
- The recliner: no mobile-ready lift recliner exists on Fab.
- Call bell, rosary, day-date clock, calendar and memory box, which are listed as gaps in shortlist section 4.
- The bed: the Dekogon hospital bed is clinical, so use it as reference only.
- Curtains, the shell pieces and the photo frames (use your own licensed photos).
- The garden hose: the Fab hose reel has 4K textures and no tech sheet.
- Possible low-cost swap: if the TV stand is not reworked, PropHaus Flat Screen TV (Could, USD 6.99) is an option. Its specs were not captured.

**Must + Should total from the shortlist:** USD 227.93-237.93, about AUD 324-338.

---

## 6. Where the evidence is

- Inspector reports and contact sheets: `D:\Unreal-Projects\WattleviewGrove-ue58\SourceArt\Room\Previews\Inspect\`
- Builders' previews: `D:\Unreal-Projects\WattleviewGrove-ue58\SourceArt\Room\Previews\SM_*.png`
- Assembly reports and story renders: `D:\Unreal-Projects\WattleviewGrove-ue58\SourceArt\Room\Previews\Assembly\` (latest), plus the `Assembly_fix_*`, `Assembly_review_*` and per-group `Assembly_*` folders
- Room audit: `D:\Unreal-Projects\WattleviewGrove-ue58\Docs\Production\Room_Intersection_Audit.md`
- Shortlist: `D:\Unreal-Projects\WattleviewGrove-ue58\Docs\Production\Asset_Shortlist.md`
- Build scripts: `D:\Unreal-Projects\WattleviewGrove-ue58\SourceArt\Room\Items\` (bed.py, seating.py, casegoods.py, tabletop.py, fixtures.py, shell.py, garden.py, sky.py)
- Rules and layout: `D:\Unreal-Projects\WattleviewGrove-ue58\SourceArt\Room\CONVENTIONS.md`, `placement.json`
