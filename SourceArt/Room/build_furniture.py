"""Blender: placeholder furniture and props for Maria's room (better than greybox, mobile-light).

Run inside Blender:  exec(open(r"<this file>").read())
Exports SourceArt/Room/Export/SM_<Name>.fbx, one per piece, plus RoomFurniture.blend.

Conventions (so build_room_dressing.py in Unreal can place them):
  * Built in Unreal centimetres via ue(); Blender (x, -y, z) m == Unreal (x, y, z) cm.
  * Each piece is modelled around its own pivot at (0, 0, 0): bottom-centre on the floor, except
    props whose timeline keys use their centre (SM_Glass, SM_Hairbrush: pivot at the centre).
  * "Front" faces local +X (the side a person faces when seated, the drawer fronts, the foot of
    the bed, the screen of the TV, the picture side of a frame).
  * UV0 = 1 m box projection for tiling textures; UV1 = packed lightmap islands.
  * Fab packs to replace these are listed in Docs/Production/Asset_Shortlist.md.
"""
import math
import os

import bmesh
import bpy

OUT = r"D:\Unreal-Projects\WattleviewGrove-ue58\SourceArt\Room\Export"

MATS = {
    "M_Timber": (0.66, 0.50, 0.33),
    "M_TimberDark": (0.40, 0.27, 0.16),
    "M_PaintedTimber": (0.90, 0.89, 0.86),
    "M_UpholsteryPink": (0.72, 0.42, 0.45),
    "M_UpholsteryCream": (0.80, 0.74, 0.66),
    "M_Linen": (0.92, 0.91, 0.88),
    "M_FloralCover": (0.82, 0.60, 0.62),
    "M_Crochet": (0.70, 0.30, 0.35),
    "M_Metal": (0.55, 0.55, 0.56),
    "M_PlasticBlack": (0.04, 0.04, 0.045),
    "M_Screen": (0.10, 0.13, 0.18),
    "M_Ceramic": (0.88, 0.86, 0.82),
    "M_Glass": (0.75, 0.82, 0.86),
    "M_Plant": (0.20, 0.42, 0.16),
    "M_Flower": (0.95, 0.80, 0.25),
    "M_Rug": (0.58, 0.44, 0.28),
    "M_Paper": (0.95, 0.94, 0.90),
    "M_Photo": (0.35, 0.55, 0.30),
    "M_Gold": (0.80, 0.65, 0.30),
    "M_LampShade": (0.95, 0.90, 0.80),
}


def ue(x, y, z):
    return (x / 100.0, -y / 100.0, z / 100.0)


def mat(name):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.diffuse_color = (*MATS[name], 1.0)
    return m


def _finish(ob, m, bevel_cm=0.0, segments=1):
    ob.data.materials.append(mat(m))
    if bevel_cm > 0:
        mod = ob.modifiers.new("bevel", "BEVEL")
        mod.width = bevel_cm / 100.0
        mod.segments = segments
        mod.limit_method = "ANGLE"
        mod.angle_limit = math.radians(40)
    return ob


def rbox(x0, x1, y0, y1, z0, z1, m, bevel_cm=0.4, segments=1):
    """Box from Unreal-cm extents (local to the piece's pivot), optionally bevelled."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    lo, hi = ue(x0, y1, z0), ue(x1, y0, z1)
    for v in bm.verts:
        v.co.x = lo[0] if v.co.x < 0 else hi[0]
        v.co.y = lo[1] if v.co.y < 0 else hi[1]
        v.co.z = lo[2] if v.co.z < 0 else hi[2]
    me = bpy.data.meshes.new("part")
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new("part", me)
    bpy.context.collection.objects.link(ob)
    return _finish(ob, m, bevel_cm, segments)


def cyl(x, y, z0, z1, radius, m, verts=16, bevel_cm=0.0, radius_top=None):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=verts,
                          radius1=radius / 100.0, radius2=(radius_top if radius_top is not None else radius) / 100.0,
                          depth=(z1 - z0) / 100.0)
    me = bpy.data.meshes.new("part")
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new("part", me)
    bpy.context.collection.objects.link(ob)
    ob.location = ue(x, y, (z0 + z1) / 2)
    bpy.context.view_layer.update()
    return _finish(ob, m, bevel_cm)


def sphere(x, y, z, r, m, sx=1.0, sy=1.0, sz=1.0, seg=12):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=max(6, seg // 2), radius=r / 100.0)
    for v in bm.verts:
        v.co.x *= sx
        v.co.y *= sy
        v.co.z *= sz
    me = bpy.data.meshes.new("part")
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new("part", me)
    bpy.context.collection.objects.link(ob)
    ob.location = ue(x, y, z)
    return _finish(ob, m)


def piece(name, parts):
    """Apply modifiers/transforms of all parts and join them into one object at the origin."""
    for p in parts:
        bpy.context.view_layer.objects.active = p
        for mod in list(p.modifiers):
            bpy.ops.object.select_all(action="DESELECT")
            p.select_set(True)
            bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.ops.object.select_all(action="DESELECT")
    for p in parts:
        p.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    bpy.ops.object.join()
    ob = bpy.context.active_object
    ob.name = name
    ob.data.name = name
    bpy.ops.object.shade_flat()
    return ob


# ------------------------------------------------------------------ pieces
def bed():
    L, W = 210.0, 100.0         # length along X (foot at +X), width along Y
    p = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            x, y = sx * (L / 2 - 8), sy * (W / 2 - 8)
            p.append(cyl(x, y, 0, 6, 3.5, "M_PlasticBlack", 12))                  # castors
            p.append(rbox(x - 2, x + 2, y - 2, y + 2, 6, 30, "M_Metal", 0.3))     # legs
    p.append(rbox(-L / 2, L / 2, -W / 2, W / 2, 28, 40, "M_Metal", 0.5))          # base frame
    p.append(rbox(-L / 2 + 2, L / 2 - 2, -W / 2 + 2, W / 2 - 2, 40, 58, "M_Linen", 4, 3))   # mattress
    p.append(rbox(-L / 2 + 30, L / 2 + 1, -W / 2 - 1, W / 2 + 1, 54, 62, "M_FloralCover", 3, 3))  # cover
    p.append(rbox(L / 2 - 60, L / 2 - 20, -W / 2 - 2, W / 2 + 2, 60, 64, "M_Crochet", 1.5, 2))   # crochet blanket
    p.append(rbox(-L / 2 - 4, -L / 2 + 2, -W / 2 - 3, W / 2 + 3, 0, 105, "M_Timber", 1.5, 2))     # headboard
    p.append(rbox(L / 2 - 2, L / 2 + 4, -W / 2 - 3, W / 2 + 3, 0, 72, "M_Timber", 1.5, 2))        # footboard
    for y in (-22, 22):
        p.append(rbox(-L / 2 + 6, -L / 2 + 40, y - 20, y + 20, 56, 70, "M_Linen", 5, 3))          # pillows
    return piece("SM_Bed", p)


def recliner():
    p = [
        rbox(-40, 40, -38, 38, 6, 42, "M_UpholsteryPink", 4, 3),                  # base
        rbox(-30, 38, -30, 30, 40, 52, "M_UpholsteryPink", 5, 3),                 # seat cushion
        rbox(-42, -22, -32, 32, 40, 105, "M_UpholsteryPink", 6, 3),               # back
        rbox(-40, 40, -40, -28, 30, 66, "M_UpholsteryPink", 5, 3),                # arm L
        rbox(-40, 40, 28, 40, 30, 66, "M_UpholsteryPink", 5, 3),                  # arm R
        rbox(-36, 26, -26, 26, 52, 56, "M_FloralCover", 2, 2),                    # throw
    ]
    for sx in (-1, 1):
        for sy in (-1, 1):
            p.append(cyl(sx * 34, sy * 32, 0, 6, 2.5, "M_TimberDark", 10))
    return piece("SM_Recliner", p)


def armchair(name):
    """Dining armchair, seat top 46 cm, faces +X."""
    p = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            p.append(rbox(sx * 20 - 2, sx * 20 + 2, sy * 21 - 2, sy * 21 + 2, 0, 42, "M_Timber", 0.6))
    p.append(rbox(-24, 24, -24, 24, 38, 42, "M_Timber", 0.6))                     # seat frame
    p.append(rbox(-22, 22, -22, 22, 42, 47, "M_UpholsteryCream", 2, 2))           # seat pad
    p.append(rbox(-24, -20, -21, 21, 47, 88, "M_Timber", 0.6))                    # back frame
    p.append(rbox(-21, -17, -18, 18, 55, 84, "M_UpholsteryCream", 2, 2))          # back pad
    for sy in (-1, 1):
        p.append(rbox(-22, 20, sy * 24 - 2, sy * 24 + 2, 62, 65, "M_Timber", 0.8))   # arm rests
        p.append(rbox(16, 20, sy * 24 - 2, sy * 24 + 2, 42, 62, "M_Timber", 0.6))    # arm posts
    return piece(name, p)


def round_table():
    return piece("SM_RoundTable", [
        cyl(0, 0, 71, 75, 47.5, "M_Timber", 40, 0.6),
        cyl(0, 0, 4, 71, 6, "M_TimberDark", 16),
        cyl(0, 0, 0, 4, 27, "M_TimberDark", 24, 0.6),
    ])


def bedside():
    p = [rbox(-23, 23, -26, 26, 4, 62, "M_Timber", 0.8)]
    for i, (z0, z1) in enumerate([(8, 24), (26, 42), (44, 58)]):
        p.append(rbox(23, 24.5, -24, 24, z0, z1, "M_Timber", 0.4))               # drawer fronts
        p.append(rbox(24.5, 26.5, -6, 6, (z0 + z1) / 2 - 1, (z0 + z1) / 2 + 1, "M_Metal", 0.3))
    p.append(rbox(-22, 22, -25, 25, 0, 4, "M_TimberDark", 0.3))
    return piece("SM_Bedside", p)


def wardrobe():
    p = [rbox(-31, 31, -80, 80, 0, 205, "M_Timber", 1.0)]
    for y0, y1 in ((-79, -1), (1, 79)):
        p.append(rbox(31, 32.5, y0, y1, 4, 201, "M_Timber", 0.5))                # doors
    for y in (-6, 6):
        p.append(rbox(32.5, 34.5, y - 1, y + 1, 90, 120, "M_Metal", 0.4))        # handles
    return piece("SM_Wardrobe", p)


def tv_and_cabinet():
    cab = piece("SM_TVCabinet", [
        rbox(-22, 22, -55, 55, 4, 60, "M_Timber", 0.8),
        rbox(22, 23.5, -53, -1, 8, 56, "M_Timber", 0.4),
        rbox(22, 23.5, 1, 53, 8, 56, "M_Timber", 0.4),
        rbox(-21, 21, -54, 54, 0, 4, "M_TimberDark", 0.3),
    ])
    tv = piece("SM_TV", [
        rbox(-3, 3, -43, 43, 70, 122, "M_PlasticBlack", 0.6),                    # body (screen part separate)
        rbox(-10, 6, -12, 12, 60, 62, "M_PlasticBlack", 0.5),                    # stand foot
        rbox(-3, 0, -3, 3, 62, 72, "M_PlasticBlack", 0.3),                       # stand neck
    ])
    screen = piece("SM_TVScreen", [rbox(3, 3.3, -41, 41, 72, 120, "M_Screen", 0.0)])
    return [cab, tv, screen]


def floor_lamp():
    return piece("SM_FloorLamp", [
        cyl(0, 0, 0, 2.5, 15, "M_Metal", 20, 0.4),
        cyl(0, 0, 2.5, 152, 1.2, "M_Metal", 10),
        cyl(0, 0, 148, 178, 19, "M_LampShade", 24, 0.0, radius_top=14),
    ])


def ceiling_fan():
    """Pivot at the ceiling mount; hub + 3 blades hang below (Z negative)."""
    p = [cyl(0, 0, -25, 0, 1.5, "M_PaintedTimber", 10), cyl(0, 0, -34, -25, 10, "M_PaintedTimber", 20, 0.8),
         cyl(0, 0, -40, -34, 8, "M_LampShade", 20)]
    for i in range(3):
        a = math.radians(i * 120)
        blade = rbox(12, 68, -6, 6, -31.5, -30.5, "M_Timber", 0.3)
        blade.rotation_euler = (0.0, math.radians(4), -a)                         # slight pitch, spaced 120 deg
        p.append(blade)
    return piece("SM_CeilingFan", p)


def rug():
    return piece("SM_Rug", [rbox(-100, 100, -97, 97, 0, 0.8, "M_Rug", 0.4)])


def frame(name, w, h, depth=2.5, border=4, picture="M_Photo"):
    """Picture frame facing +X, pivot at the back centre (wall contact)."""
    return piece(name, [
        rbox(0, depth, -w / 2, w / 2, -h / 2, h / 2, "M_TimberDark", 0.3),
        rbox(depth, depth + 0.2, -w / 2 + border, w / 2 - border, -h / 2 + border, h / 2 - border, picture, 0.0),
    ])


def calendar():
    p = [rbox(0, 0.6, -30, 30, -40, 40, "M_Paper", 0.0), rbox(0, 1, -30, 30, 36, 40, "M_Metal", 0.2)]
    for i, (y, z) in enumerate([(-25, 25), (-10, 15), (8, 28), (18, 5), (-22, -8), (-5, -15), (12, -25), (-18, -28)]):
        p.append(rbox(0.6, 0.8, y, y + 9, z, z + 9, "M_Flower", 0.0))               # sticky notes
    return piece("SM_Calendar", p)


def small_props():
    out = []
    out.append(piece("SM_DayDateClock", [rbox(-4, 4, -10, 10, 0, 14, "M_PlasticBlack", 0.8),
                                          rbox(4, 4.2, -9, 9, 2, 12, "M_Screen", 0.0)]))
    out.append(piece("SM_MemoryBox", [rbox(-11, 11, -16, 16, 0, 14, "M_UpholsteryPink", 0.8),
                                       rbox(-11.5, 11.5, -16.5, 16.5, 14, 16, "M_Gold", 0.5)]))
    out.append(piece("SM_CallBell", [cyl(0, 0, 0, 2, 4.5, "M_PlasticBlack", 16, 0.3),
                                      cyl(0, 0, 2, 4, 3.5, "M_Metal", 16, 0.0, radius_top=2.0)]))
    out.append(piece("SM_Vase", [cyl(0, 0, 0, 22, 4.5, "M_Ceramic", 16, 0.0, radius_top=3.0),
                                  sphere(0, 0, 28, 9, "M_Flower", 1, 1, 0.8), sphere(4, 3, 25, 6, "M_Plant")]))
    out.append(piece("SM_Jug", [cyl(0, 0, 0, 22, 6, "M_Glass", 18, 0.0, radius_top=5.0),
                                 rbox(4, 9, -1, 1, 6, 18, "M_Glass", 0.5)]))
    # Centre pivots (timeline keys use the centre).
    out.append(piece("SM_Glass", [cyl(0, 0, -5.5, 5.5, 3.5, "M_Glass", 16)]))
    out.append(piece("SM_Hairbrush", [rbox(-4, 11, -2.5, 2.5, -1.5, 1.5, "M_UpholsteryPink", 0.8),
                                       rbox(-11, -4, -1.2, 1.2, -1.0, 1.0, "M_UpholsteryPink", 0.5)]))
    out.append(piece("SM_Shelf", [rbox(0, 28, -45, 45, -1.5, 1.5, "M_TimberDark", 0.4)]))
    out.append(piece("SM_PlantPot", [cyl(0, 0, 0, 14, 7, "M_Ceramic", 16, 0.0, radius_top=8),
                                      sphere(0, 0, 22, 11, "M_Plant", 1.0, 1.0, 0.9),
                                      sphere(4, -3, 28, 7, "M_Plant")]))
    out.append(piece("SM_Madonna", [cyl(0, 0, 0, 20, 4, "M_Ceramic", 12, 0.0, radius_top=2.5),
                                     sphere(0, 0, 23, 3, "M_Ceramic")]))
    out.append(piece("SM_Clipboard", [rbox(-0.3, 0.3, -11, 11, -16, 16, "M_TimberDark", 0.2),
                                       rbox(0.3, 0.5, -10, 10, -15, 13, "M_Paper", 0.0),
                                       rbox(0.3, 1.5, -4, 4, 13, 16, "M_Metal", 0.3)]))
    return out


def uv_world_and_lightmap(ob, margin=0.02):
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
            co = loop.vert.co
            loop[layer].uv = (co.y, co.z) if ax == 0 else (co.x, co.z) if ax == 1 else (co.x, co.y)
    bm.to_mesh(me)
    bm.free()
    uv1 = me.uv_layers.new(name="Lightmap")
    me.uv_layers.active = uv1
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=margin, scale_to_bounds=False)
    bpy.ops.uv.pack_islands(margin=margin, rotate=True)
    bpy.ops.object.mode_set(mode="OBJECT")
    me.uv_layers.active = uv0


def export(ob):
    os.makedirs(OUT, exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.export_scene.fbx(filepath=os.path.join(OUT, f"{ob.name}.fbx"), use_selection=True,
                             apply_unit_scale=True, apply_scale_options="FBX_SCALE_UNITS", axis_forward="-Y",
                             axis_up="Z", mesh_smooth_type="FACE", add_leaf_bones=False)


def build():
    # Clear the scene (read_homefile would invalidate the operator context under MCP).
    if bpy.context.object and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    for me in list(bpy.data.meshes):
        if me.users == 0:
            bpy.data.meshes.remove(me)
    pieces = [bed(), recliner(), armchair("SM_Armchair"), round_table(), bedside(), wardrobe(),
              *tv_and_cabinet(), floor_lamp(), ceiling_fan(), rug(),
              frame("SM_PhotoFrame_MariaEnzo", 50, 45), frame("SM_PhotoFrame_Small", 30, 40),
              frame("SM_PhotoFrame_Wide", 45, 32), calendar(), *small_props()]
    tris = 0
    for ob in pieces:
        uv_world_and_lightmap(ob)
        export(ob)
        tris += sum(len(p.vertices) - 2 for p in ob.data.polygons)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(os.path.dirname(OUT), "RoomFurniture.blend"))
    print(f"exported {len(pieces)} pieces, ~{tris} triangles total:",
          ", ".join(f"{o.name}:{sum(len(p.vertices) - 2 for p in o.data.polygons)}" for o in pieces))


build()
