# Room intersection audit: Maria's room

**Date:** 2026-10-26 | **Round:** 3 | **Auditor:** room integration auditor (automated agent)

## Result in one paragraph

All 57 meshes named in `placement.json` are present and placed. `assemble_room.py` reports
**0 clashes, 0 fit/max_x/min_z rule violations, 0 placement notes and 0 missing meshes**, both
before and after this round's placement edits. The memory-beat overlay pieces, which the standard
check skips, also have **0 penetrations** against anything. Every `rest_on` prop sits fully on its
support: no bottom vertex lacks support and no gap is over 0.5 cm. Every FBX has UV0 `UVMap`
then UV1 `Lightmap`, uses only convention slot names (nothing renders magenta), and has no
lightmap overlap, no intersecting parts and no non-manifold or degenerate geometry.

Since round 2, two fixtures issues are resolved by asset changes: the curtain panels are now
continuous (no fold steps) and the calendar now reads as a month calendar. I made three small
placement edits: Memory_Tomato_0 moved off the sill plant and curtain hem, and two gallery frames
re-spaced. **One regression:** SM_BasilPot went from 1,690 to 2,966 triangles, which pushes the
memory beat to about 75.2k triangles. Still open: the fan canopy coplanar with the ceiling, the
curtain hem jammed against the TV cabinet, the wardrobe/bed aisle, the fence running past the
lawn, the unplaced fence end post, and a few polish items.

## How the check works

| Tool | What it does |
|---|---|
| `Tools/assemble_room.py -- --render` | Imports every `Export/SM_*.fbx` named in `placement.json` and places it at its Unreal cm location and yaw, using `ue(x,y,z) = (x/100, -y/100, z/100)`. `rest_on` pieces are raycast down onto their support and lifted `gap_cm` (0.2 cm). It checks `fit` rectangles, `max_x` (curtains <= 482) and `min_z` (fan >= 225). Then it tests every pair of pieces with BVH triangle overlap. A triangle pair is a **penetration** (clash) only when each triangle strictly crosses the other's plane by more than 0.02 cm. Faces resting on faces only count as touching. It skips shell-vs-shell pairs and `overlay`/`sky` pieces, and treats contact with `Garden_Lawn` as information only. Output: `Previews/Assembly/report.json`, `plan.png` and 14 story-viewpoint renders. |
| `Tools/inspect_asset.py -- Export/SM_X.fbx` | Per piece: triangles, size, pivot, UV layers, slot names, mesh defects, intersecting parts, lightmap UV overlap and coverage. Fourteen reports were older than their FBX, so I re-ran them: CallBell, CeilingFan, Clipboard, DayDateClock, FloorLamp, Glass, Hairbrush, the three PhotoFrames, Rosary, RoundTable, Rug and Vase. All are clean. |
| Extra audit (temporary script outside the repo that reuses the assembly code; output `Previews/Assembly/audit_r3.json` and `r3_*.png`) | (a) **Overlay** pieces against everything, including each other. (b) Minimum vertex-to-surface distance for every interior pair within 3 cm. (c) Bottom vertices of every `rest_on` piece raycast to their support, to catch overhang or floating. (d) Bottom vertices of exterior pieces against the lawn. (e) Ray-parity containment test. (f) UV layer **order** and slot names from a fresh FBX import. (g) Triangle totals by kind. (h) 20 extra close-ups, with and without overlay pieces. |

Rules applied (from `SourceArt/Room/CONVENTIONS.md`):
- Pivot at bottom centre with the front facing +X.
- 0.2 cm air gap where pieces rest on each other.
- Room furniture under 60k triangles in total. Per piece: bed set 8k, armchair 3k, recliner 4k, table 2k, small prop 300-1,500, curtains 3k per side.
- At most 4 materials per mesh.
- Curtains at X <= 482, fan >= 225 cm and blade radius <= 68, sill plant inside the 16 cm sill.

I looked at `plan.png` and all 14 standard renders: david_door, maria_seated, corner,
bed_from_table, window_to_door, table_props, curtain_sill_left/right, bedside, shelf_wardrobe,
door_handle, recliner, tv and window_view_out. I also looked at the 20 `r3_*` close-ups (calendar,
photo frame, gallery, bed head, table low, both sill plants, wardrobe front, curtain hem, curtain/TV
cabinet, curtain seam, fan, lamp/shelf, recliner wall, bed/wardrobe gap, three no-overlay story
views, two overlay views) and the inspect sheets for the recliner, curtains and table.

Note on (e): the ray-parity test flags Chair_Third, SillPlant_0 and WindowFrame vertices as
"inside" tomato plants. These are false positives. The foliage is open, single-sided leaf geometry,
so parity is meaningless there. Distance and penetration tests both show clearance.

## Measured clearances (after the edits; all pass, for reference)

| Pair | Min distance |
|---|---|
| Every `rest_on` piece to its support | 0.20 cm at the contact (curved bases reach 0.2-0.5 cm). No unsupported bottom vertex. |
| Bed_Linen to Bed | 0.36 cm |
| Curtains to CurtainRod / CurtainRod to north wall | 0.20 / 0.20 cm |
| Curtains to floor / to Rug | 1.0 / 0.59 cm |
| Curtains to TV_Cabinet | 2.7 cm (issue 2) |
| Memory_Tomato_0 to Curtains / Chair_Third / SillPlant_0 | 1.29 / 2.77 / > 3 (4.66) cm |
| Memory_Tomato_1 to Memory_Tomato_2 / Skirting | 1.95 / 2.07 cm |
| SillPlant_0/1 to north wall (glazing side) | 2.14 / 2.14 cm |
| Clipboard to MemoryBox (shelf) | 2.0 cm |
| Gallery frames to each other | 6-10 cm (after edits) |
| Wardrobe to Skirting / TV_Cabinet to east wall | 1.91 / 2.0 cm |
| Wardrobe front to bed frame / bedspread drape | 60.9 / 54.9 cm (issue 3) |
| Bed to Bedside | 10.6 cm |
| Exterior bases in the lawn | planted 0.6-1.7 cm, nothing floating |

Walkways: the door swing (X 61-149, Y 0-88) is clear of everything. From the door to the window
the open floor is about 178 cm wide. Between the bed and Chair_Second / TV cabinet it is about
136 cm. The only narrow spot is between the bed and the wardrobe (issue 3).

Triangle totals as placed:
- Interior furniture + soft + props + wall pieces: **56,026** (93% of the 60k budget). The shell adds 6,562.
- Memory overlay: **19,162** (up from 16,168), so the memory beat totals about **75.2k**.
- Exterior: 64,292.
- Sky: 2,208.

## Issue table

Severity: high = visible penetration, or broken in a story view. Medium = budget/rule breach or
clearly visible problem. Low = polish or edge case.

| # | Asset | Other piece | Kind | Severity | Detail | Fix | Status |
|---|---|---|---|---|---|---|---|
| 1 | SM_BasilPot | (small-prop budget) | rule | medium | **Regression.** 2,966 tris (round 2: 1,690), about twice the 1,500 small-prop ceiling. There are two instances on the table, so 5,932 tris for one prop type. | Garden: cut leaf count or leaf segments to <= 1,500, for example fewer, larger leaves with 4-6 verts each. | Open (garden) |
| 2 | SM_Curtains / SM_TVCabinet | each other | visual | low | Round 1 issue 7, still open. The right panel spans to Y 405.8 and the cabinet starts at Y 403.4. The outer fold hangs 2.7 cm off the cabinet's window end and looks jammed in `tv.png` / `r3_curtain_tvcab.png`. Placement cannot fix it: the cabinet fills its 110 cm fit rectangle and already sits 2 cm off the east wall. | Fixtures: pull the right panel's outer fold in to Y <= 401 below Z 65 (collision object at the cabinet). Or casegoods: shorten SM_TVCabinet to about 105 cm. | Open (fixtures or casegoods) |
| 3 | SM_Wardrobe / SM_Bed / SM_BedLinen | each other | placement | medium | Round 1 issue 8, still open. The aisle is **60.9 cm** to the bed frame and **54.9 cm** to the bedspread drape (`r3_bed_wardrobe_gap.png`). Aged-care practice is about 90 cm or more for a carer or walking frame. Moving inside the current fit rectangles gains under 2 cm. | Lead: revisit the wardrobe/bed fit rectangles (for example wardrobe Y 120-280 with the bed shifted +X), or accept the aisle. | Open (lead) |
| 4 | SM_TomatoPlant / overlay set | (room budget) | rule | medium | Round 1 issue 4, now worse. The memory beat shows 56,026 + 19,162 = **about 75.2k tris** against the 60k room budget. That is tomato x3 = 8,910 (2,970 each, up from 2,792), basil x2 = 5,932, fig 2,896 and hose 1,424. | Lead: set a separate memory-beat budget, or hide some room props during the beat. Garden: basil to <= 1.5k (issue 1); tomato to about 2k. | Open (lead + garden) |
| 5 | SM_CeilingFan | SM_Ceiling | rule | low | Round 1 issue 12, still open after the 02:17 re-export. The canopy top is coplanar with the ceiling (0.0 cm, 42 touching tri pairs), which breaks the 0.2 cm air-gap rule. The lowest point is exactly 225.0, so placement cannot lower it. The canopy dome and motor housing still show facets from below (`r3_fan_ceiling.png`). | Fixtures: start the geometry 0.2 cm below the pivot and shorten the downrod 0.2 cm, so the lowest point stays >= 225. Use about 24 or more lathe segments on the canopy and motor housing. | Open (fixtures) |
| 6 | SM_Curtains | (curtain budget) / (self) | rule | low | 6,360 tris against 3k per side (6,000), 6% over. Each panel is still a single-sided sheet (288 boundary edges). At the hem the pleats show razor-thin edges and hard creases (`r3_curtain_hem_left.png`), and dark slivers show between folds in `tv.png`. | Fixtures: reduce fold resolution by about 400 tris (decimate the flat runs). Then add a thin Solidify (about 0.3 cm) on the hem band only, or a rolled hem edge, so the bottom edge has thickness. Keep X <= 482 and the 1 cm hem. | Open (fixtures) |
| 7 | SM_Fence / SM_Lawn | each other | floating | low | Round 1 issue 9, still open. Garden_Fence_11 runs to Y 2099.9, but the lawn ends at Y 2000. The last 100 cm of fence stands over no ground (the sky dome is under it). Moving either piece only splits the overhang across both ends. | Garden: extend SM_Lawn to at least Y 2110 (3,610 cm long), or the lead drops one fence segment. | Open (garden / lead) |
| 8 | SM_Fence_EndPost | placement.json | missing | low | Round 1 issue 10, still open. Exported (108 tris) but not placed, so the fence run ends on a bare picket edge. | Add a `Garden_Fence_End` entry at about (2510, 2100, -20) once issue 7 is settled. It is a new entry, so it is outside this audit's move-only remit. | Open (lead / garden) |
| 9 | SM_Recliner | (self: throw) | visual | low | New. The throw's seat portion lies as a flat sheet with a ragged, torn-looking rear edge (`recliner.png`; top view in `Inspect/SM_Recliner_sheet.png`). The arm drape reads well. No intersection. | Seating: tuck the throw's rear edge into the seat/back crease, or fold it under with a soft rolled edge. Keep the crochet scallop only on the front hem. | Open (seating) |
| 10 | SM_RoundTable | (self) | visual | low | New. The rim silhouette shows straight segments at about 1 m (`r3_table_low.png`). Maria sees this edge from her seat. 1,904 tris, under the 2k budget. | Tabletop: put more segments on the top's outer rim only (for example 64 to 96 around), and pay for them with fewer segments on the pedestal and foot, to stay <= 2k. | Open (tabletop) |
| 11 | SM_Wardrobe (also SM_Bed, SM_PlantPot, SM_TomatoPlant, SM_Rosary) | (lightmap) | visual | low | New info. Low lightmap UV coverage: Wardrobe 0.14, PlantPot 0.16, TomatoPlant 0.15, Rosary 0.10, Bed 0.24. No overlap, but large flat receivers like the wardrobe and bed waste baked resolution. On PICO that shows as blurry contact shadows. | Casegoods / bed: repack UV1 with Pack Islands (rotation on, 2% margin) to aim for >= 0.5 coverage. Small props can stay as they are. | Open (casegoods, bed) |
| 12 | SM_TomatoPlant (Memory_Tomato_0) | SM_PlantPot (SillPlant_0), SM_Curtains, SM_Armchair (Chair_Third) | visual | low | Round 2 issue 4. Tomato_0's leaves and fruit hung 1.81 cm over the left sill geranium, which looked crowded in `r2_ov_tomato0_curtain.png`. Its lowest leaves were 0.34 cm from the curtain hem and 1.99 cm from Chair_Third. | Moved X 468 to 464. Now 4.66 cm from SillPlant_0, 1.29 cm from the curtain and 2.77 cm from Chair_Third. 0 overlay penetrations; base fully on the rug. | Fixed in placement |
| 13 | SM_PhotoFrame_Small (Gallery_4) | SM_PhotoFrame_Wide (Gallery_1) | placement | low | New. The top-row small frame sat **2.0 cm** above the lower wide frame, while every other gallery gap is 6-10 cm. In `r3_gallery.png` it read as a mistake. | Gallery_4 Z 214 to 218: gap now 6 cm, and its bottom lines up with Gallery_3 at Z 198. | Fixed in placement |
| 14 | SM_PhotoFrame_Small (Gallery_2) | SM_PhotoFrame_Wide (Gallery_1), SM_PhotoFrame_Small (Gallery_0) | placement | low | New. The lower row was ragged: Gallery_2 was centred 1 cm lower than Gallery_0, with a 9 cm gap where the others are 10 cm. | Gallery_2 (244, 449.8, 169) to (245, 449.8, 170): lower row now even, 10 cm gaps. | Fixed in placement |
| 15 | SM_Recliner | Skirting (west wall) | placement | low | Round 2 issue 15, unchanged. The back is 1.46 cm off the skirting. That is fine for a static mesh, but a real lift/recline chair needs 10-15 cm behind it. The position is locked by the story timeline. | None now. If the recliner ever animates, model it as a wall-hugger or free the position. | Info (lead) |
| 16 | SM_FigTree (Memory_Fig) | SM_Wall_North (window) | visual | low | New observation. During the memory beat the fig sits 8 cm off the outer wall and its canopy fills most of the right window pane (`curtain_sill_right.png`, `window_view_out.png`). No clash. | Lead: confirm the close framing is intended. If not, move Memory_Fig about +80 cm X. I left it alone because `build_perception_layer.py` mirrors it. | Info (lead) |

### Resolved since round 2 (by asset changes, verified this round)

| Round 2 # | Asset | Was | Now |
|---|---|---|---|
| 5 | SM_Curtains | Hard vertical steps where fold strips ended (torn look) | Continuous panels with no notches (`curtain_sill_left.png`, `r3_curtain_left_seam.png`) |
| 6 | SM_Calendar | Whole page `M_Photo`; read as a green noticeboard | Picture top, `M_Paper` 7 x 6 month grid with crossed-off days, binding rings and hanger. Reads clearly from the door and the recliner (`r3_calendar.png`, `corner.png`) |
| 4 | SM_TomatoPlant (Tomato_0) vs curtain hem | 0.36 cm, leaves brushing the hem | 1.29 cm after this round's move (issue 12) |

## Placement edits made (this round)

All edits keep the one-piece-per-line format and CRLF line endings. Table, Glass, Hairbrush,
Chair_Maria, Chair_Second, Photo_Frame and Recliner were not touched.

| Label | Before | After | Why |
|---|---|---|---|
| Memory_Tomato_0 | loc (468, 129, 0) | loc (**464**, 129, 0) | Clear of SillPlant_0, the curtain hem and Chair_Third (issue 12) |
| Gallery_4 | loc (215, 449.8, 214) | loc (215, 449.8, **218**) | 2 cm gap to Gallery_1 becomes 6 cm (issue 13) |
| Gallery_2 | loc (244, 449.8, 169) | loc (**245**, 449.8, **170**) | Even lower row (issue 14) |

Candidates tested for Tomato_0 before choosing: X 466/464/462 at yaw 0, and yaw ±15/30/45/90.
Every rotation drove leaves into the curtain or Chair_Third (5-48 penetrating pairs). X 464 at
yaw 0 was the best balance. Re-run after the edits: `ASSEMBLY {"missing": [], "clashes": 0,
"rule_violations": 0, "contacts": 35, "notes": 0}`. The 35 contacts are info only: floor pieces on
the floor, the fan on the ceiling, and garden pieces planted in the lawn. Extra audit: 0 overlay
penetrations, 0 unsupported bottom vertices, 0 floating exterior pieces.

Rejected moves:
- **TV_Cabinet/TV +Y** for issue 2: it would break the cabinet's fit rectangle (Y <= 448).
- **CeilingFan z 269.8** for issue 5: it would break min_z 225.
- **Lawn or fence shifts** for issue 7: they only split the overhang across both ends.

## Visual review notes (no issue raised)

- No magenta materials.
- Nothing floating or sunk in the room.
- No props off table, shelf, bedside or sill edges.
- Scale reads correctly throughout.
- Chair arms tuck under the table edge.
- The rosary and day/date clock sit on the bedside.
- The Madonna, memory box and clipboard sit on the shelf. The floor-lamp shade clears the Madonna.
- Both sill geraniums sit inside the sill and clear the glazing.
- The pillows are puffed with seams; one stands against the headboard inside the bed rails.
- The day/date clock and TV screens render black in Workbench (`M_Screen`). That is expected, because Unreal assigns the screen textures.
- Review-tool suggestion (repeat): a `--no-overlay` render switch in `assemble_room.py`, so story views can be checked without the memory set.

## What remains for the asset builders

1. **garden:** SM_BasilPot back under 1.5k (issue 1, regression). SM_TomatoPlant to about 2k (issue 4). SM_Lawn to Y >= 2110 (issue 7).
2. **fixtures:** Ceiling fan 0.2 cm below the ceiling and smoother canopy/motor housing (issue 5). Curtains: trim about 400 tris and give the hem thickness (issue 6). Pull the right panel's outer fold in to Y <= 401 near the TV cabinet (issue 2).
3. **casegoods:** Optionally shorten SM_TVCabinet to about 105 cm, as the alternative fix for issue 2. Repack the wardrobe lightmap UVs (issue 11).
4. **bed:** Repack the SM_Bed lightmap UVs (issue 11).
5. **seating:** Tidy the recliner throw's rear edge on the seat (issue 9).
6. **tabletop:** Smoother table-top rim within 2k tris (issue 10).
7. **Lead decisions:**
   - The wardrobe/bed aisle (issue 3).
   - The memory-beat triangle budget (issue 4).
   - The fence end post and fence length (issues 7-8).
   - Fig framing (issue 16).
   - Recliner wall clearance if it ever animates (issue 15).
