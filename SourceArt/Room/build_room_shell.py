"""Blender: build Maria's room shell for Unreal with proper lightmap UVs.

Run inside Blender (MCP execute or Text Editor):  exec(open(r"<this file>").read())
Exports one FBX per piece to SourceArt/Room/Export/SM_<name>.fbx.

Why: the greybox used scaled engine cubes, whose lightmap layout gives every face an equal
share, so big walls got ~5 cm lightmap texels (pixelated light). These meshes have:
  UV0 "UVMap"    world-scale box projection, 1 UV = 1 m (tiling textures)
  UV1 "Lightmap" smart-projected and packed islands with margins (Lightmass)

Coordinates: written in Unreal centimetres; ue() converts to Blender metres with Y mirrored
(verified round-trip: Blender (x, -y, z) m -> Unreal (x, y, z) * 100). All pieces keep the
world origin so they drop into L_ResidentRoom at (0, 0, 0).

Room (Unreal cm): interior X 0..500 (north/window wall at X=500), Y 0..450 (west/door wall at
Y=0, east wall at Y=450), Z 0..270, walls 15 cm thick. Window opening Y 100..350, Z 80..220.
Door opening X 60..150, Z 0..210.
"""
import math
import os

import bmesh
import bpy

OUT = r"D:\Unreal-Projects\WattleviewGrove-ue58\SourceArt\Room\Export"
X, Y, H, T = 500.0, 450.0, 270.0, 15.0
WIN = dict(y0=100.0, y1=350.0, z0=80.0, z1=220.0)
DOOR = dict(x0=60.0, x1=150.0, z1=210.0)


def ue(x, y, z):
    return (x / 100.0, -y / 100.0, z / 100.0)


def clear():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()
    for block in (bpy.data.meshes, bpy.data.materials):
        for item in list(block):
            if item.users == 0:
                block.remove(item)


def material(name, rgb):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.diffuse_color = (*rgb, 1.0)
    return m


MATS = {
    "M_WallPaint": (0.80, 0.77, 0.71),
    "M_Ceiling": (0.85, 0.84, 0.81),
    "M_Carpet": (0.45, 0.42, 0.38),
    "M_PaintedTimber": (0.90, 0.89, 0.86),
    "M_DoorTimber": (0.62, 0.47, 0.32),
    "M_Metal": (0.55, 0.55, 0.56),
    "M_Curtain": (0.92, 0.90, 0.85),
}


def box_obj(name, x0, x1, y0, y1, z0, z1, mat):
    """Axis-aligned box from Unreal-cm extents."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    lo, hi = ue(x0, y1, z0), ue(x1, y0, z1)          # y mirrored: swap
    for v in bm.verts:
        v.co.x = lo[0] if v.co.x < 0 else hi[0]
        v.co.y = lo[1] if v.co.y < 0 else hi[1]
        v.co.z = lo[2] if v.co.z < 0 else hi[2]
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    me.materials.append(material(mat, MATS[mat]))
    return ob


def cut(target, x0, x1, y0, y1, z0, z1):
    """Boolean-difference an axis-aligned opening out of target."""
    cutter = box_obj("_cutter", x0, x1, y0, y1, z0, z1, "M_WallPaint")
    mod = target.modifiers.new("cut", "BOOLEAN")
    mod.operation = "DIFFERENCE"
    mod.solver = "EXACT"
    mod.object = cutter
    bpy.context.view_layer.objects.active = target
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(cutter, do_unlink=True)


def join(name, parts):
    bpy.ops.object.select_all(action="DESELECT")
    for p in parts:
        p.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join()
    ob = bpy.context.active_object
    ob.name = name
    ob.data.name = name
    return ob


def bevel(ob, width_cm=0.4, segments=1):
    mod = ob.modifiers.new("bevel", "BEVEL")
    mod.width = width_cm / 100.0
    mod.segments = segments
    mod.limit_method = "ANGLE"
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.modifier_apply(modifier=mod.name)


def curtain(name, x_face, y0, y1, z0, z1, folds=7, depth_cm=5.0):
    """Folded curtain: a vertical sheet with sine folds along its width, facing -X."""
    cols, rows = folds * 8, 4
    verts, faces = [], []
    for r in range(rows + 1):
        z = z0 + (z1 - z0) * r / rows
        for c in range(cols + 1):
            t = c / cols
            y = y0 + (y1 - y0) * t
            x = x_face - depth_cm * 0.5 * (1 + math.sin(t * folds * 2 * math.pi))
            verts.append(ue(x, y, z))
    for r in range(rows):
        for c in range(cols):
            a = r * (cols + 1) + c
            faces.append((a, a + 1, a + cols + 2, a + cols + 1))
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    me.materials.append(material("M_Curtain", MATS["M_Curtain"]))
    # thickness so it lights and shadows from both sides
    mod = ob.modifiers.new("solid", "SOLIDIFY")
    mod.thickness = 0.008
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.modifier_apply(modifier=mod.name)
    return ob


def uv_world_and_lightmap(ob, margin=0.01):
    """UV0: 1 m box projection. UV1: smart project + pack for Lightmass."""
    me = ob.data
    while len(me.uv_layers):
        me.uv_layers.remove(me.uv_layers[0])
    uv0 = me.uv_layers.new(name="UVMap")
    bm = bmesh.new()
    bm.from_mesh(me)
    layer = bm.loops.layers.uv[uv0.name]
    for f in bm.faces:
        n = f.normal
        ax = max(range(3), key=lambda i: abs(n[i]))
        for loop in f.loops:
            co = ob.matrix_world @ loop.vert.co
            if ax == 0:
                loop[layer].uv = (co.y, co.z)
            elif ax == 1:
                loop[layer].uv = (co.x, co.z)
            else:
                loop[layer].uv = (co.x, co.y)
    bm.to_mesh(me)
    bm.free()
    uv1 = me.uv_layers.new(name="Lightmap")
    me.uv_layers.active = uv1
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=margin, area_weight=1.0,
                             correct_aspect=True, scale_to_bounds=False)
    bpy.ops.uv.pack_islands(margin=margin, rotate=True)
    bpy.ops.object.mode_set(mode="OBJECT")
    me.uv_layers.active = uv0
    uv0.active_render = True


def export(ob):
    os.makedirs(OUT, exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    path = os.path.join(OUT, f"{ob.name}.fbx")
    bpy.ops.export_scene.fbx(filepath=path, use_selection=True, apply_unit_scale=True,
                             apply_scale_options="FBX_SCALE_UNITS", axis_forward="-Y", axis_up="Z",
                             mesh_smooth_type="FACE", use_mesh_modifiers=True, add_leaf_bones=False)
    return path


def build():
    clear()
    pieces = []

    # Floor and ceiling slabs.
    pieces.append(box_obj("SM_Floor", -T, X + T, -T, Y + T, -10, 0, "M_Carpet"))
    pieces.append(box_obj("SM_Ceiling", -T, X + T, -T, Y + T, H, H + 10, "M_Ceiling"))

    # Walls with openings.
    north = box_obj("SM_Wall_North", X, X + T, -T, Y + T, 0, H, "M_WallPaint")
    cut(north, X - 1, X + T + 1, WIN["y0"], WIN["y1"], WIN["z0"], WIN["z1"])
    west = box_obj("SM_Wall_West", -T, X + T, -T, 0, 0, H, "M_WallPaint")
    cut(west, DOOR["x0"], DOOR["x1"], -T - 1, 1, -1, DOOR["z1"])
    south = box_obj("SM_Wall_South", -T, 0, 0, Y, 0, H, "M_WallPaint")
    east = box_obj("SM_Wall_East", -T, X + T, Y, Y + T, 0, H, "M_WallPaint")
    pieces += [north, west, south, east]

    # Skirting (10 cm high, 1.8 cm proud), split around the door.
    sk = [box_obj("_sk", 0, X, 0, 1.8, 0, 10, "M_PaintedTimber"),                 # placeholder, rebuilt below
          ]
    bpy.data.objects.remove(sk[0], do_unlink=True)
    sk = [
        box_obj("_sk1", 0, DOOR["x0"] - 7, 0, 1.8, 0, 10, "M_PaintedTimber"),
        box_obj("_sk2", DOOR["x1"] + 7, X, 0, 1.8, 0, 10, "M_PaintedTimber"),       # west wall
        box_obj("_sk3", 0, X, Y - 1.8, Y, 0, 10, "M_PaintedTimber"),               # east wall
        box_obj("_sk4", 0, 1.8, 0, Y, 0, 10, "M_PaintedTimber"),                   # south wall
        box_obj("_sk5", X - 1.8, X, 0, WIN["y0"], 0, 10, "M_PaintedTimber"),       # north wall
        box_obj("_sk6", X - 1.8, X, WIN["y1"], Y, 0, 10, "M_PaintedTimber"),
        box_obj("_sk7", X - 1.8, X, WIN["y0"], WIN["y1"], 0, 10, "M_PaintedTimber"),
    ]
    skirting = join("SM_Skirting", sk)
    bevel(skirting, 0.3)
    pieces.append(skirting)

    # Cornice (6 cm cove block) around the ceiling.
    co = [
        box_obj("_c1", 0, X, 0, 4, H - 6, H, "M_PaintedTimber"),
        box_obj("_c2", 0, X, Y - 4, Y, H - 6, H, "M_PaintedTimber"),
        box_obj("_c3", 0, 4, 4, Y - 4, H - 6, H, "M_PaintedTimber"),
        box_obj("_c4", X - 4, X, 4, Y - 4, H - 6, H, "M_PaintedTimber"),
    ]
    cornice = join("SM_Cornice", co)
    bevel(cornice, 1.5, 2)
    pieces.append(cornice)

    # Window: frame ring in the opening, centre mullion, sill board inside, architrave.
    fz0, fz1, fy0, fy1 = WIN["z0"], WIN["z1"], WIN["y0"], WIN["y1"]
    wf = [
        box_obj("_w1", X + 4, X + 11, fy0, fy0 + 6, fz0, fz1, "M_PaintedTimber"),
        box_obj("_w2", X + 4, X + 11, fy1 - 6, fy1, fz0, fz1, "M_PaintedTimber"),
        box_obj("_w3", X + 4, X + 11, fy0, fy1, fz1 - 6, fz1, "M_PaintedTimber"),
        box_obj("_w4", X + 4, X + 11, fy0, fy1, fz0, fz0 + 6, "M_PaintedTimber"),
        box_obj("_w5", X + 5, X + 10, (fy0 + fy1) / 2 - 2.5, (fy0 + fy1) / 2 + 2.5, fz0, fz1, "M_PaintedTimber"),
        box_obj("_w6", X - 14, X + 2, fy0 - 6, fy1 + 6, fz0 - 2.5, fz0, "M_PaintedTimber"),   # sill board
        box_obj("_w7", X - 1.5, X, fy0 - 8, fy0, fz0, fz1 + 8, "M_PaintedTimber"),            # architrave
        box_obj("_w8", X - 1.5, X, fy1, fy1 + 8, fz0, fz1 + 8, "M_PaintedTimber"),
        box_obj("_w9", X - 1.5, X, fy0 - 8, fy1 + 8, fz1, fz1 + 8, "M_PaintedTimber"),
    ]
    window = join("SM_WindowFrame", wf)
    bevel(window, 0.4)
    pieces.append(window)

    # Door: slab (slightly ajar? closed), frame/architrave, lever handle.
    door = box_obj("SM_Door", DOOR["x0"] + 1, DOOR["x1"] - 1, -9, -4.5, 0, DOOR["z1"] - 1, "M_DoorTimber")
    bevel(door, 0.4)
    pieces.append(door)
    df = [
        box_obj("_d1", DOOR["x0"] - 7, DOOR["x0"], 0, 1.5, 0, DOOR["z1"] + 7, "M_PaintedTimber"),
        box_obj("_d2", DOOR["x1"], DOOR["x1"] + 7, 0, 1.5, 0, DOOR["z1"] + 7, "M_PaintedTimber"),
        box_obj("_d3", DOOR["x0"] - 7, DOOR["x1"] + 7, 0, 1.5, DOOR["z1"], DOOR["z1"] + 7, "M_PaintedTimber"),
        box_obj("_d4", DOOR["x0"], DOOR["x0"] + 2, -T, 0, 0, DOOR["z1"], "M_PaintedTimber"),   # jambs
        box_obj("_d5", DOOR["x1"] - 2, DOOR["x1"], -T, 0, 0, DOOR["z1"], "M_PaintedTimber"),
        box_obj("_d6", DOOR["x0"], DOOR["x1"], -T, 0, DOOR["z1"] - 2, DOOR["z1"], "M_PaintedTimber"),
    ]
    frame = join("SM_DoorFrame", df)
    bevel(frame, 0.3)
    pieces.append(frame)
    lever = join("SM_DoorHandle", [
        box_obj("_h1", 136, 138, -3.5, 0, 98, 106, "M_Metal"),      # rose
        box_obj("_h2", 126, 138, -3.5, -1.5, 100.5, 102.5, "M_Metal"),  # lever
    ])
    bevel(lever, 0.3)
    pieces.append(lever)

    # Sheer curtains either side of the window, on a rod.
    cl = curtain("_cl", X - 6, fy0 - 50, fy0 + 8, 6, fz1 + 22)
    cr = curtain("_cr", X - 6, fy1 - 8, fy1 + 50, 6, fz1 + 22)
    curtains = join("SM_Curtains", [cl, cr])
    pieces.append(curtains)
    rod = box_obj("SM_CurtainRod", X - 9, X - 7, fy0 - 60, fy1 + 60, fz1 + 22, fz1 + 24, "M_Metal")
    pieces.append(rod)

    paths = []
    for ob in pieces:
        uv_world_and_lightmap(ob)
        paths.append(export(ob))
    blend = os.path.join(os.path.dirname(OUT), "RoomShell.blend")
    bpy.ops.wm.save_as_mainfile(filepath=blend)
    print("exported", len(paths), "pieces:", [os.path.basename(p) for p in paths])


build()
