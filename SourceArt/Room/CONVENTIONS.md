# Room asset conventions (Blender -> Unreal, PICO 4 Ultra)

Every placeholder asset for Maria's room follows these rules so it drops into `L_ResidentRoom`
without hand-fixing. Placeholders stand in for the Fab packs in
`Docs/Production/Asset_Shortlist.md` until they are bought.

## Quality bar (from Lawrence)

- **No boxed objects.** Model the real shape: turned parts lathed from a profile (Screw
  modifier), handles/rails/rods swept along curves (curve bevel or Curve->Mesh), soft goods
  (pillows, mattress top, duvet, blankets, throws, cushions, curtains) puffed or
  cloth-simulated, edges bevelled. A pillow is a puffed pillow with a seam, never a box.
- **No intersections** with neighbouring pieces or the room shell. Resting contact is fine;
  leave 0.2 cm air gaps instead of coplanar faces. Respect the footprints and clearances below.
- Mobile VR budget: total room furniture < 60k triangles. Rough per-piece budgets: bed set 8k,
  armchair 3k, recliner 4k, table 2k, small prop 300-1,500, curtains 3k each side.
  Few materials per mesh (<= 4). No alpha-cutout or translucent geometry except where stated.

## Units and axes

- Model in **Unreal centimetres** and convert with `ue(x, y, z) = (x/100, -y/100, z/100)`
  (Blender metres, Y mirrored). Verified round trip: Blender (x, -y, z) m == Unreal (x, y, z) cm.
- Export FBX: `apply_unit_scale=True, apply_scale_options='FBX_SCALE_UNITS', axis_forward='-Y',
  axis_up='Z', mesh_smooth_type='FACE', add_leaf_bones=False`. Apply all modifiers/transforms
  before export.
- File per piece: `SourceArt/Room/Export/SM_<Name>.fbx`. The object name equals the file stem.

## Pivot and facing

- Pivot (object origin) at **bottom centre** on the floor, unless stated. "Front" faces local
  **+X** (seated person's facing direction, drawer fronts, foot of the bed, TV screen, picture
  side of a frame). Wall-mounted pieces: pivot at the back centre (wall contact), front +X.
- `SM_Glass` and `SM_Hairbrush`: pivot at the geometric centre (timeline keys use it).
- `SM_CeilingFan`: pivot at the ceiling mount, geometry hangs into -Z.

## UVs

- UV0 named `UVMap`: texture UVs, real-world scale (1 UV = 1 m) for tiling materials, or a
  sensible unwrap for organic pieces.
- UV1 named `Lightmap`: non-overlapping islands in 0..1 with >= 2% margin (Smart UV Project
  then Pack Islands). Required for baked lighting.

## Material slot names (Unreal assigns materials by these names)

`M_Timber` (light ash), `M_TimberDark`, `M_PaintedTimber` (white satin), `M_UpholsteryPink`,
`M_UpholsteryCream`, `M_Linen` (white bedding), `M_FloralCover`, `M_Crochet`, `M_Metal`
(brushed steel), `M_Brass`, `M_PlasticBlack`, `M_PlasticWhite`, `M_Screen`, `M_Ceramic`,
`M_Glass` (opaque glossy placeholder, no translucency), `M_Plant`, `M_PlantDark`, `M_Flower`,
`M_FlowerRed`, `M_Rug` (jute), `M_Paper`, `M_Photo`, `M_Gold`, `M_LampShade`, `M_Curtain`
(sheer), `M_Bark`, `M_Soil`, `M_Grass`, `M_Terracotta`, `M_Rubber`, `M_Sky` (unlit sky dome).
Room shell only: `M_WallPaint`, `M_Ceiling`, `M_Carpet`, `M_DoorTimber`.
Any other slot name renders magenta in the review tools and gets no material in Unreal.
Set a believable `diffuse_color` on each for previews; Unreal replaces them.

## Room shell (Unreal cm)

Interior X 0..500, Y 0..450, Z 0..270; walls 15 cm thick. North wall (window) at X=500;
west wall (door) at Y=0; east wall at Y=450; south wall at X=0.
Skirting 10 cm high, 1.8 cm proud of every wall face. Cornice 6 cm at the ceiling.
Window opening Y 100..350, Z 80..220; interior sill board X 486..502, Z 77.5..80, Y 94..356.
Door opening X 60..150, Z 0..210; architrave 7 cm wide on the room side.

## Footprints and placement

`placement.json` is the single source of truth for where every piece goes (Unreal cm, yaw in
degrees). The Blender overlap check and the Unreal placement script both read it. Key rules:

- Floor pieces have their pivot on the floor (z 0). Pieces with `rest_on` (tabletop props, TV,
  chairs and table on the rug, shelf props, sill plants) are dropped by the tools onto the
  support with a 0.2 cm gap, so model them with the pivot at the bottom and do not bake any
  height offset into the mesh.
- `fit` rectangles: bed X 124..231, Y 230..448; bedside X 240..292, Y 395..448; wardrobe
  X 1.8..68, Y 140..300; recliner X 243..327, Y 2..100 (back to the west wall, facing +Y);
  TV cabinet and TV X 370..490, Y 403..448; floor lamp shade radius <= 19 at (30, 426).
- `SM_TV`: pivot at the bottom of its stand; `SM_TVScreen` shares the TV's pivot exactly.
- `SM_PlantPot` is a small window-sill plant: pot diameter <= 13 cm, height <= 35 cm, leaf
  spread radius <= 13 cm, so it sits on the 16 cm deep sill without touching the glazing.
- Curtains hang in front of the sill at X <= 482 from a rod at X 479, Z 243 (brackets back to
  the wall at X 500); panels span Y 44..112 and 338..406; bottom 1 cm above the floor.
- Ceiling fan: lowest point >= 225 cm (head clearance), blade radius <= 68 cm.
- Table top surface at 75 cm above the table's own base (75.8 once it sits on the rug).
- Garden: `SM_FlowerBed` and `SM_Fence` run along local Y (long axis), front +X; the bench
  faces +X and is placed with yaw 180 to face the window. Lawn pivot at its centre, top
  surface near z 0 with gentle undulation of no more than +-8 cm.
- `SM_SkyDome` is centred at (1500, 250, -20) so the whole garden sits inside it.

## Review tools (run them; reviewers will)

- `Tools/inspect_asset.py -- Export/SM_X.fbx` writes `Previews/Inspect/SM_X.json` and a
  six-view `SM_X_sheet.png`: triangles, Unreal-cm size, pivot offsets, UV layers, slot names,
  mesh defects, parts that pass through each other, lightmap UV overlap.
- `Tools/assemble_room.py -- --render [--out <dir>]` assembles the room from `placement.json`,
  reports clashes (real penetrations, not resting contact), fit/clearance violations and
  renders plan and close-up views.

## Previews

Each builder renders a preview PNG per piece (Workbench or EEVEE, 3/4 view, neutral light) to
`SourceArt/Room/Previews/SM_<Name>.png` and checks it before handing off.
