"""Blender 5.0 (headless): SM_Bed + SM_BedLinen for Maria's room.

Run:
  "C:\\Program Files\\Blender Foundation\\Blender 5.0\\blender.exe" -b --factory-startup --python bed.py

Follows SourceArt/Room/CONVENTIONS.md:
  * Modelled in Unreal cm local to the pivot and converted with ue(x, y, z) = (x/100, -y/100, z/100).
  * Pivot at the floor, bed centre. Foot of the bed at local +X, head at -X. ~209 long x 104 wide.
  * SM_BedLinen shares the bed pivot and is placed identically.
  * UV0 'UVMap' (1 UV = 1 m), UV1 'Lightmap' (smart project + pack, 2% margin).

How it is built
  * Bed: swept tubes (curve bevel -> mesh), lathed castor housings/wheels (Screw), bevelled
    curve-outline timber boards, a subdivided + puffed mattress with a swept seam piping.
    Every welded/bolted part is welded and boolean-UNIONED into one closed frame shell (and the
    mattress with its piping into another), so no part passes through another.
  * Linen (revision 1):
    - Pillows: pressurised closed cloth shells (pressure 3.5, quality 15, collision quality 8) with the
      piping rings and corner ears in a stiffer vertex group (structural/shear/bending max), the
      corner ears Laplacian-relaxed after the sim (0.6 x 5), then pushed clear of the bed.
    - Duvet: 74 x 80 cloth grid (156 x 126 cm) dropped from ~10 cm with slack; four light goal pins
      (0.28) on the top lowered by an animated shape key, bending 0.8 / compression 5, the drape
      region grows 7 % so the side drops buckle into vertical folds, turbulence for the first 22
      frames, rounded foot corners that fall into soft dog-ears. Quilted low-frequency puff. The
      turn-back is a separate flap sim pinned only at its fold row on top of a fat round roll
      (radius 1.5 x thickness), smoothed around the fold, then quadric-decimated (keeps folds,
      drops flat areas), untangled, and thickened by hand: floral front, lighter M_Linen reverse
      (what shows on the turned-back flap), rounded rolled hem on every open edge.
    - Crochet blanket: a strip pre-draped and simulated over a clean high-res copy of the duvet
      (top pinned where it lies, drops grow 6 % for gentle waves), rebuilt as two real 1 cm layers
      folded at the foot end, the top layer's scalloped hem stepping back from the bottom layer's,
      slightly lumpy tops; whole column rings are lifted if anything still touches.
    Clearances are enforced and verified with a triangle-crossing test.
  * Revision 2: side rails, mid bars and end posts are octagonal (rail bends 5 segments, posts lathed
    with a domed cap), platform frame corners 4 segments, and every metal-metal edge under 80 degrees is
    smooth-shaded so the tubes read round. Hidden deck slats dropped, sub-rails 4-sided, motor box bevel
    1 segment; castors (12-step housing and wheel) are separate closed shells with 0.2-0.25 mm air gaps
    instead of boolean unions. Linen: propped pillow ears stiffer (bending max 20) + 8 relax passes;
    flap side drops softly pinned in the sim and trimmed to 2.5 cm above the main hem; blanket hems are
    half-sine crochet shells (7.8 cm period, 4 columns per shell) on dense hem columns, with the body
    ring points only on every 4th (flat top) / 3rd (side drops) column.
  * Revision 3 (fix round 1): bed set back under 8k (bed ~4.3k + linen <= 3.69k). Hidden hi-lo chassis, cross
    members, sub-rails and scissor arms are square steel sections, castors lighter (8-step housing, 10-step wheel
    with conical axle bosses, smooth-shaded), deck-frame corners 3 segments, rail bends 4, mattress underside
    dissolved. Turned-back flap: stiffer quilted sim (bending 3, compression 15) and iron_flap() smooths away the
    narrow pleats that stepped the hem, then runs 1-D Taubin along the free edge so the hem is one smooth line;
    rolled hem only on the flap's open edges (plain smooth strip on the hidden drape hems). Propped pillow B is
    subdivided, Taubin-smoothed (8) and decimated to 820 tris, shaded smooth at 60 deg. shell_scale() thins the
    neighbours of crossing verts too and reports crossings after its last step. Blanket: 13 shells (10 cm).
Optional env CHECK_DIR: extra combined/close-up renders for inspection. BED_ONLY=1: frame only, no export.
DBG=1 keeps the duvet mid-surface before/after decimation (DBG_mid / DBG_dec) in the CHECK_BLEND file.
"""
import math
import os
import time

import bmesh
import bpy
from mathutils import Matrix, Vector, noise
from mathutils.bvhtree import BVHTree

ROOT = r"D:\Unreal-Projects\WattleviewGrove-ue58\SourceArt\Room"
OUT = os.path.join(ROOT, "Export")
PREV = os.path.join(ROOT, "Previews")
CHECK = os.environ.get("CHECK_DIR", "")
CM = 0.01
GAP = 0.2 * CM          # air gap between resting soft goods and what they rest on

MATS = {
    "M_Metal": (0.62, 0.63, 0.64),
    "M_Timber": (0.78, 0.68, 0.52),
    "M_Linen": (0.93, 0.92, 0.89),
    "M_PlasticBlack": (0.05, 0.05, 0.055),
    "M_FloralCover": (0.84, 0.58, 0.62),
    "M_Crochet": (0.80, 0.55, 0.45),
}

# ---- bed dimensions (Unreal cm, local) ----
MAT_X0, MAT_X1 = -98.5, 98.0           # mattress length (head .. foot)
MAT_HW = 46.0                          # mattress half width
MAT_Z0, MAT_ZE, MAT_ZT = 44.2, 57.4, 58.0   # bottom, top edge, puffed top centre
HEAD_IN = -102.3                       # inner face of the headboard (1 mm clear of the posts)
FOOT_IN = 102.3                        # inner face of the footboard
BOARD_T = 2.6
POST_X, POST_Y, POST_R = 101.0, 42.0, 1.2


def ue(x, y, z):
    return Vector((x * CM, -y * CM, z * CM))


def mat(name):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.diffuse_color = (*MATS[name], 1.0)
    nt = getattr(m, "node_tree", None)          # FBX carries the Principled base colour
    if nt:
        for nd in nt.nodes:
            if nd.type == "BSDF_PRINCIPLED":
                nd.inputs["Base Color"].default_value = (*MATS[name], 1.0)
    return m


def link(ob):
    bpy.context.scene.collection.objects.link(ob)
    return ob


def bake(ob, m=None, name=None):
    """Evaluate modifiers / curve geometry into a plain mesh object (transform baked in)."""
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    me.transform(ob.matrix_world)
    new = link(bpy.data.objects.new(name or ob.name, me))
    old_data = ob.data
    bpy.data.objects.remove(ob, do_unlink=True)
    if isinstance(old_data, bpy.types.Curve):
        bpy.data.curves.remove(old_data)
    if m:
        me.materials.clear()
        me.materials.append(mat(m))
        for p in me.polygons:
            p.material_index = 0
    return new


def mesh_obj(name, bm, m=None):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = link(bpy.data.objects.new(name, me))
    if m:
        me.materials.append(mat(m))
    return ob


def xform(ob, M):
    ob.data.transform(M)
    ob.data.update()
    return ob


def fillet(pts, radii, segs=3, cyclic=False):
    """Round the corners of a polyline (2D or 3D tuples). radii: scalar or per-point list."""
    pts = [Vector(p) for p in pts]
    n = len(pts)
    if not isinstance(radii, (list, tuple)):
        radii = [radii] * n
    out = []
    for i in range(n):
        if not cyclic and (i == 0 or i == n - 1) or radii[i] <= 0:
            out.append(pts[i])
            continue
        a, b, c = pts[i - 1], pts[i], pts[(i + 1) % n]
        d1, d2 = (b - a), (c - b)
        l1, l2 = d1.length, d2.length
        d1.normalize()
        d2.normalize()
        ang = d1.angle(d2)
        if ang < 1e-3:
            out.append(b)
            continue
        t = radii[i] * math.tan(ang / 2)
        f1 = 0.5 if radii[i - 1] > 0 else 0.95
        f2 = 0.5 if radii[(i + 1) % n] > 0 else 0.95
        t = min(t, l1 * f1, l2 * f2)
        p1, p2 = b - d1 * t, b + d2 * t
        for k in range(segs + 1):
            s = k / segs
            out.append((1 - s) ** 2 * p1 + 2 * (1 - s) * s * b + s * s * p2)
    return out


def tube(pts_cm, r, m, res=1, cyclic=False, name="tube", square=False):
    """Sweep a round section along a polyline (curve bevel_depth, converted to mesh).
    square=True: 4-sided box section (res 0, tilted 45 deg so the faces are level), half-width r."""
    if square:
        res, r = 0, r * math.sqrt(2)
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_mode = "ROUND"
    cu.bevel_depth = r * CM
    cu.bevel_resolution = res
    cu.use_fill_caps = not cyclic
    sp = cu.splines.new("POLY")
    sp.points.add(len(pts_cm) - 1)
    for p, q in zip(sp.points, pts_cm):
        v = ue(*q)
        p.co = (v.x, v.y, v.z, 1.0)
        if square:
            p.tilt = math.pi / 4
    sp.use_cyclic_u = cyclic
    return bake(link(bpy.data.objects.new(name, cu)), m)


def rrect(cx, cy, hx, hy, z, rad, segs=3):
    pts = [(cx - hx, cy - hy, z), (cx + hx, cy - hy, z), (cx + hx, cy + hy, z), (cx - hx, cy + hy, z)]
    return [tuple(p) for p in fillet(pts, rad, segs, cyclic=True)]


def lathe(profile, steps, m, name="lathe"):
    """Screw-modifier lathe of an (r, z) cm profile around local Z."""
    me = bpy.data.meshes.new(name)
    me.from_pydata([(r * CM, 0, z * CM) for r, z in profile],
                   [(i, i + 1) for i in range(len(profile) - 1)], [])
    ob = link(bpy.data.objects.new(name, me))
    mod = ob.modifiers.new("screw", "SCREW")
    mod.axis = "Z"
    mod.steps = steps
    mod.render_steps = steps
    mod.angle = 2 * math.pi
    mod.use_merge_vertices = True
    mod.merge_threshold = 1e-5
    mod.use_normal_calculate = True
    return bake(ob, m)


def board(outline, holes, thickness, bev, m, x_center, name="board"):
    """Filled 2D curve outline (x = Unreal Y, y = Z, cm) extruded + round-bevelled, standing in the YZ plane."""
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "2D"
    cu.fill_mode = "BOTH"
    cu.bevel_mode = "ROUND"
    cu.bevel_depth = bev * CM
    cu.bevel_resolution = 1
    cu.extrude = (thickness / 2 - bev) * CM
    for loop in [outline] + holes:
        sp = cu.splines.new("POLY")
        sp.points.add(len(loop) - 1)
        for p, (a, b) in zip(sp.points, loop):
            p.co = (-a * CM, b * CM, 0, 1)          # Unreal Y -> Blender -Y
        sp.use_cyclic_u = True
    ob = link(bpy.data.objects.new(name, cu))
    # local X -> Blender Y, local Y -> Blender Z, local Z -> Blender X
    ob.matrix_world = Matrix(((0, 0, 1, x_center * CM), (1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 0, 1)))
    return bake(ob, m)


def rbox(x0, x1, y0, y1, z0, z1, m, bev=0.5, seg=2):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    lo, hi = ue(x0, y1, z0), ue(x1, y0, z1)
    for v in bm.verts:
        v.co = Vector((lo.x if v.co.x < 0 else hi.x, lo.y if v.co.y < 0 else hi.y, lo.z if v.co.z < 0 else hi.z))
    ob = mesh_obj("box", bm, m)
    if bev > 0:
        mod = ob.modifiers.new("bevel", "BEVEL")
        mod.width = bev * CM
        mod.segments = seg
    return bake(ob, m)


def join(name, parts):
    bpy.ops.object.select_all(action="DESELECT")
    for p in parts:
        p.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    ob.name = name
    ob.data.name = name
    return ob


def smooth(ob, angle=40.0):
    me = ob.data
    for p in me.polygons:
        p.use_smooth = True
    me.set_sharp_from_angle(angle=math.radians(angle))


def smooth_material(ob, mname, keep_deg=80.0):
    """Clear the sharp flag on every edge whose two faces both use material mname (tube facets shade
    round), except true creases sharper than keep_deg (flat end caps, tube-to-tube junctions)."""
    me = ob.data
    mi = [m.name for m in me.materials].index(mname)
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.normal_update()
    n_sm = n_keep = 0
    for e in bm.edges:
        if len(e.link_faces) == 2 and all(f.material_index == mi for f in e.link_faces):
            if math.degrees(e.calc_face_angle(0.0)) <= keep_deg:
                e.smooth = True
                n_sm += 1
            else:
                e.smooth = False
                n_keep += 1
    bm.to_mesh(me)
    bm.free()
    me.update()
    return n_sm, n_keep


def tri_count(ob):
    ob.data.calc_loop_triangles()
    return len(ob.data.loop_triangles)


def weld(ob, dist=2e-6):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=dist)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()
    return ob


def manifold(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    ok = all(e.is_manifold for e in bm.edges)
    bm.free()
    return ok


def union(name, parts, solver="MANIFOLD"):
    """Boolean-union closed parts into one shell (materials transferred per face)."""
    for p in parts:
        weld(p)
    bad = [p.name for p in parts if not manifold(p)]
    if bad:
        print("  WARNING non-manifold union operands:", bad)
    n_in = sum(tri_count(p) for p in parts)
    base = parts[0]
    coll = bpy.data.collections.new("U_" + name)
    bpy.context.scene.collection.children.link(coll)
    for p in parts[1:]:
        bpy.context.scene.collection.objects.unlink(p)
        coll.objects.link(p)
    mod = base.modifiers.new("U", "BOOLEAN")
    mod.operation = "UNION"
    mod.operand_type = "COLLECTION"
    mod.collection = coll
    mod.solver = solver
    mod.material_mode = "TRANSFER"
    res = bake(base, None, name)
    for p in list(coll.objects):
        d = p.data
        bpy.data.objects.remove(p, do_unlink=True)
        bpy.data.meshes.remove(d)
    bpy.data.collections.remove(coll)
    weld(res, 1e-6)
    print(f"  union {name}: {len(parts)} parts, {n_in} -> {tri_count(res)} tris, manifold={manifold(res)}")
    return res


# =============================================================== SM_Bed
def mattress():
    L, W = MAT_X1 - MAT_X0, 2 * MAT_HW
    cx = (MAT_X0 + MAT_X1) / 2
    H = MAT_ZE - MAT_Z0
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x * L, v.co.y * W, v.co.z * H)) * CM
    # support loops 3.5 cm from every edge + a few interior loops for the puff
    cuts = [((1, 0, 0), x) for x in (-L / 2 + 3.5, L / 2 - 3.5, 0)] + \
           [((0, 1, 0), y) for y in (-W / 2 + 3.5, W / 2 - 3.5)] + \
           [((0, 0, 1), z) for z in (-H / 2 + 2.5, H / 2 - 3.0)]
    for no, d in cuts:
        geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
        bmesh.ops.bisect_plane(bm, geom=geom, plane_co=Vector(no) * d * CM, plane_no=Vector(no))
    ob = mesh_obj("mattress", bm, "M_Linen")
    sub = ob.modifiers.new("subd", "SUBSURF")
    sub.levels = 1
    sub.render_levels = 1
    ob = bake(ob, "M_Linen")
    # puff the top and bulge the sides a touch; keep the bottom flat on the deck
    for v in ob.data.vertices:
        x, y, z = v.co.x / CM, v.co.y / CM, v.co.z / CM
        ux, uy = min(1, abs(x) / (L / 2)), min(1, abs(y) / (W / 2))
        fx, fy = 1 - ux ** 6, 1 - uy ** 4
        t = z / (H / 2)                            # -1 bottom .. 1 top
        if t > 0:
            z += (MAT_ZT - MAT_ZE) * fx * fy * t ** 2
        bul = 0.5 * max(0.0, 1 - t * t)
        y += math.copysign(bul * fx, y) if abs(y) > W / 2 - 4 else 0
        x += math.copysign(bul * fy, x) if abs(x) > L / 2 - 4 else 0
        if z < -H / 2 + 0.15:                      # subdivision lifts the underside up to 1 mm: flatten it
            z = -H / 2
        v.co = Vector((x, y, z)) * CM
    ob.data.update()
    xform(ob, Matrix.Translation(ue(cx, 0, (MAT_Z0 + MAT_ZE) / 2)))
    # the flat underside lies on the deck and is never seen: dissolve its grid into one face
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.normal_update()
    under = [f for f in bm.faces if f.normal.z < -0.999 and all(abs(v.co.z - MAT_Z0 * CM) < 1e-4 for v in f.verts)]
    bmesh.ops.dissolve_faces(bm, faces=under)
    bmesh.ops.dissolve_degenerate(bm, edges=bm.edges[:], dist=1e-6)
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()
    # top seam piping: ray-cast the mattress side at seam height, sweep a 0.5 cm cord half sunk in
    bvh = BVHTree.FromObject(ob, bpy.context.evaluated_depsgraph_get())
    path = rrect(cx, 0, L / 2 - 1.0, W / 2 - 1.0, MAT_ZE - 1.6, 5.0, 3)
    pts = []
    for (x, y, z) in path:
        o = ue(x, y, z)
        d = Vector((o.x - cx * CM, o.y, 0)).normalized()
        start = o + d * 0.08
        hit, nrm, _, _ = bvh.ray_cast(start, -d, 0.2)
        p = hit + d * 0.0025 if hit else o
        pts.append((p.x / CM, -p.y / CM, p.z / CM))
    seam = tube(pts, 0.5, "M_Linen", res=1, cyclic=True, name="seam")
    return union("Mattress", [ob, seam])


def castor(cx, cy, stem_top=16.95):
    parts = []
    dx = -3.0 if cx > 0 else 3.0                   # wheel trails toward the bed centre
    # swivel housing + kingpin stem in one lathe profile. The castor parts are separate closed shells
    # (boolean-unioning them cost ~180 tris per castor in cut loops): the housing sits 0.25 mm above the
    # fork crown and its stem stops just under the chassis tube.
    h = lathe([(0, stem_top), (1.0, stem_top), (1.0, 14.4), (2.4, 14.2), (2.6, 13.3), (2.2, 12.45), (0, 12.45)], 8,
              "M_PlasticBlack")
    parts.append(xform(h, Matrix.Translation(ue(cx, cy, 0))))
    # fork: bent strip from axle up over the wheel and back down, slanted to the trailing axle
    path = fillet([(-2.25, 4.2), (-2.25, 12.25), (2.25, 12.25), (2.25, 4.2)], 1.3, 2)
    bm = bmesh.new()
    rows = []
    for p in path:
        y, z = p.x, p.y
        xc = cx + dx * max(0.0, min(1.15, (12.4 - z) / 6.9))
        rows.append((bm.verts.new(ue(xc - 1.7, cy + y, z)), bm.verts.new(ue(xc + 1.7, cy + y, z))))
    for (a, b), (c, d) in zip(rows, rows[1:]):
        bm.faces.new((a, b, d, c))
    fork = mesh_obj("fork", bm, "M_PlasticBlack")
    sol = fork.modifiers.new("sol", "SOLIDIFY")
    sol.thickness = 0.35 * CM
    sol.offset = 0
    parts.append(bake(fork, "M_PlasticBlack"))
    # wheel: lathed tyre with the axle bosses turned on as a cone (10 steps); the bosses stop
    # 0.25 mm short of the fork cheeks (inner faces at +-2.075)
    w = lathe([(0, 2.05), (0.9, 2.05), (4.4, 1.4), (5.5, 0.7), (5.5, -0.7), (4.4, -1.4),
               (0.9, -2.05), (0, -2.05)], 10, "M_PlasticBlack")
    parts.append(xform(w, Matrix.Translation(ue(cx + dx, cy, 5.52)) @ Matrix.Rotation(math.radians(18), 4, "Y") @
                      Matrix.Rotation(math.pi / 2, 4, "X")))
    # the 10-gon tyre's lowest vertex is not straight down: drop the wheel so it touches the floor (0.2 mm)
    zmin = min(v.co.z for v in w.data.vertices)
    xform(w, Matrix.Translation((0, 0, 0.0002 - zmin)))
    return [weld(q) for q in parts]


def head_foot_board(x_center, z_bottom, z_side, z_top, z_slot, name):
    bev = 0.8
    hw = 50.0 - bev
    z0, zs, zt = z_bottom + bev, z_side - bev, z_top - bev
    arch = [(y, zs + (zt - zs) * (1 - (y / hw) ** 2)) for y in [hw * k / 4 for k in (3, 2, 1, 0, -1, -2, -3)]]
    pts = [(-hw, z0), (hw, z0), (hw, zs)] + arch + [(-hw, zs)]
    radii = [1.5, 1.5, 9.0] + [0] * len(arch) + [9.0]
    outline = [(p.x, p.y) for p in fillet(pts, radii, 3, cyclic=True)]
    # hand-grip slot (stadium)
    sl, sr = 11.0, 2.2
    slot = [(sl * s + sr * math.cos(a) * s, z_slot + sr * math.sin(a) * s)
            for s in (1, -1) for a in [math.radians(-90 + 45 * k) for k in range(5)]]
    return board(outline, [slot], BOARD_T, bev, "M_Timber", x_center, name)


def side_rail(side):
    y = 50.5 * side
    # octagonal (res=2) rail and mid bar, 4-segment bends so the corners read as bent tube
    parts = [tube(fillet([(-96, y, 43.0), (-96, y, 74), (-65, y, 74), (-65, y, 43.0)], 6, 4), 1.4, "M_Metal",
                  res=2, name="rail"),
             tube([(-96, y, 63), (-65, y, 63)], 1.1, "M_Metal", res=2, name="rail_mid")]
    for x in (-96, -65):        # brackets out from the deck frame, kept below the mattress
        parts.append(tube([(x, 45.0 * side, 43.0), (x, y, 43.0)], 1.0, "M_Metal"))
    return parts


def build_bed():
    m_body = mattress()
    p = []
    # platform (mattress) frame + sub-rails. The deck slats were dropped: they sat fully hidden under
    # the mattress (the mattress rests on the frame loop). The hidden sub-rails are 4-sided (res=0).
    p.append(tube(rrect(-0.5, 0, 99.0, 45, 42, 5, 3), 2.0, "M_Metal", cyclic=True))   # ends clear the boards
    for y in (-26.5, 26.5):     # sub-rails: both scissor arms' upper ends ride under them
        p.append(tube([(-75, y, 40.4), (60, y, 40.4)], 1.0, "M_Metal", square=True))
    # chassis loop + cross members
    # hi-lo chassis, cross members and scissor arms: rectangular steel sections (as on real hi-lo beds)
    chassis = tube(rrect(0, 0, 92, 36, 19, 6, 2), 1.6, "M_Metal", cyclic=True, square=True)
    p.append(chassis)
    ch_bvh = bvh_of(chassis)
    for x in (-68, 52):
        p.append(tube([(x, -36, 19), (x, 36, 19)], 1.3, "M_Metal", square=True))
    # hi-lo scissor linkage: inner and outer arms side by side, pivot rod, end pins
    zl, zh = 21.0, 38.6
    for s in (-1, 1):
        p.append(tube([(-68, 25.6 * s, zl), (52, 25.6 * s, zh)], 1.0, "M_Metal", square=True))
        p.append(tube([(-68, 28.4 * s, zh), (52, 28.4 * s, zl)], 1.0, "M_Metal", square=True))
    p.append(tube([(-8, -31, (zl + zh) / 2), (-8, 31, (zl + zh) / 2)], 1.0, "M_Metal"))
    # actuator ram + motor housing bolted to the foot-end cross member
    p.append(tube([(40, 0, 23.5), (-6.5, 0, (zl + zh) / 2)], 1.8, "M_Metal"))
    p.append(rbox(39, 51, -4.5, 4.5, 20.3, 28.0, "M_PlasticBlack", 1.2, 1))
    # castors (separate shells, joined after the union)
    castors = []
    for cx in (-86, 86):
        for cy in (-36, 36):
            # stem stops 0.2 mm under the chassis tube's actual underside (ray cast on the hex tube)
            hit = ch_bvh.ray_cast(ue(cx, cy, 10), Vector((0, 0, 1)), 0.2)
            castors += castor(cx, cy, (hit[0].z / CM - 0.02) if hit[0] is not None else 16.95)
    # end posts (through the deck frame) carrying the boards: octagonal tube with a domed end cap
    for sx, top in ((-1, 82), (1, 52)):
        for sy in (-1, 1):
            post = lathe([(0, 42), (POST_R, 42), (POST_R, top - 0.55), (POST_R * 0.72, top - 0.12), (0, top)], 8,
                         "M_Metal", name="post")
            p.append(xform(post, Matrix.Translation(ue(POST_X * sx, POST_Y * sy, 0)) @
                           Matrix.Rotation(math.pi / 8, 4, "Z")))
    # head-end split side rails (raised)
    for s in (-1, 1):
        p += side_rail(s)
    frame = union("Frame", p)
    # light-ash head (105 high) and foot (72 high) boards, rounded arched tops with grip slots;
    # bolted to the posts, modelled 1 mm clear of them so the boards stay clean closed shells
    boards = [weld(head_foot_board(HEAD_IN - BOARD_T / 2, 30, 97, 105, 96, "headboard")),
              weld(head_foot_board(FOOT_IN + BOARD_T / 2, 30, 65, 72, 64, "footboard"))]
    print("  boards:", [tri_count(b) for b in boards], "mattress:", tri_count(m_body))
    mattress_col = link(bpy.data.objects.new("COL_mattress", m_body.data.copy()))
    bed = join("SM_Bed", [frame, m_body] + boards + castors)
    while bed.data.uv_layers:
        bed.data.uv_layers.remove(bed.data.uv_layers[0])
    smooth(bed, 40)
    smooth_material(bed, "M_PlasticBlack", 60.0)
    n_sm, n_keep = smooth_material(bed, "M_Metal", 80.0)
    print(f"  M_Metal smooth: {n_sm} metal-metal edges smooth, {n_keep} kept sharp (> 80 deg: flat caps / tube junctions)")
    return bed, mattress_col


# =============================================================== SM_BedLinen
def pillow_bm(A=36.5, B=24.0, Ht=8.5, Hb=5.0, nu=11, nv=8, c=0.05, seed=0.0):
    """Puffed pillow (local cm: x = depth, y = length, z = thickness) with a piped seam and corner points.
    Returns (bmesh, stiff, corner): stiff / corner map vertex index -> weight. stiff covers the piping
    rings and the corners (stiffer cloth there), corner the four corner ears (relaxed after the sim)."""
    bm = bmesh.new()
    su = [math.sin((i / (nu - 1) * 2 - 1) * math.pi / 2) for i in range(nu)]
    sv = [math.sin((j / (nv - 1) * 2 - 1) * math.pi / 2) for j in range(nv)]
    T, Bo = {}, {}
    for i, a in enumerate(su):
        for j, b in enumerate(sv):
            y = a * A * (1 - c * (1 - b * b))
            x = b * B * (1 - c * (1 - a * a))
            g = ((1 - a * a) * (1 - b * b)) ** 0.55
            n = noise.noise(Vector((x * 0.07 + seed, y * 0.07, seed)))
            T[i, j] = bm.verts.new((x, y, 0.45 + Ht * g * (1 + 0.10 * n)))
            Bo[i, j] = bm.verts.new((x, y, -(0.45 + Hb * g * (1 + 0.06 * n))))
    for i in range(nu - 1):
        for j in range(nv - 1):
            bm.faces.new((T[i, j], T[i + 1, j], T[i + 1, j + 1], T[i, j + 1]))
            bm.faces.new((Bo[i, j], Bo[i, j + 1], Bo[i + 1, j + 1], Bo[i + 1, j]))
    ring = [(i, 0) for i in range(nu)] + [(nu - 1, j) for j in range(1, nv)] + \
           [(i, nv - 1) for i in range(nu - 2, -1, -1)] + [(0, j) for j in range(nv - 2, 0, -1)]
    pos = [Vector((T[k].co.x, T[k].co.y)) for k in ring]
    N = len(ring)
    rings = [[T[k] for k in ring]]
    beads = []
    for k in range(N):
        t = pos[(k + 1) % N] - pos[k - 1]
        o = Vector((t.y, -t.x)).normalized()
        if o.dot(pos[k]) < 0:
            o = -o
        beads.append(o)
    for off, z in ((0.55, 0.38), (0.55, -0.38)):
        rings.append([bm.verts.new((pos[k].x + beads[k].x * off, pos[k].y + beads[k].y * off, z)) for k in range(N)])
    rings.append([Bo[k] for k in ring])
    for r0, r1 in zip(rings, rings[1:]):
        for k in range(N):
            bm.faces.new((r0[k], r0[(k + 1) % N], r1[(k + 1) % N], r1[k]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    uv = bm.loops.layers.uv.new("UVMap")
    bottom = set(Bo.values())
    for f in bm.faces:
        for lp in f.loops:
            co = lp.vert.co
            lp[uv].uv = (co.x * CM + (0.6 if lp.vert in bottom else 0.0), co.y * CM)
    bm.verts.index_update()
    corners = [Vector((sx * B, sy * A)) for sx in (-1, 1) for sy in (-1, 1)]
    corner, stiff = {}, {}
    for v in bm.verts:
        d = min((Vector((v.co.x, v.co.y)) - q).length for q in corners)
        w = max(0.0, min(1.0, 1.0 - (d - 4.0) / 9.0))
        if w > 0:
            corner[v.index] = w
            stiff[v.index] = w
    for r in rings:
        for v in r:
            stiff[v.index] = 1.0
    for v in bm.verts:
        v.co *= CM
    return bm, stiff, corner


RAY_DIRS = (Vector((0.0123, 0.0217, 1.0)).normalized(), Vector((0.71, -0.3, -0.64)).normalized())


def inside(bvh, co):
    """Point-in-closed-mesh test by ray parity (majority of two rays)."""
    votes = 0
    for d in RAY_DIRS:
        n, p = 0, co
        for _ in range(64):
            hit = bvh.ray_cast(p, d)
            if hit[0] is None:
                break
            n += 1
            p = hit[0] + d * 1e-6
        votes += n % 2
    return votes == 2


class Field:
    """Signed distance to colliders: closed BVH meshes (outward normals) and half-spaces.
    clear: required clearance (m) from every collider."""

    def __init__(self, bvhs=(), planes=(), clear=GAP):
        self.bvhs, self.planes, self.clear = list(bvhs), list(planes), clear

    def each(self, co):
        for b in self.bvhs:
            loc, nor, _, _ = b.find_nearest(co)
            if loc is not None:
                d = co - loc
                s = d.length
                # the nearest face's normal can mislead next to edges: confirm "inside" by ray parity
                if d.dot(nor) < 0 and inside(b, co):
                    s = -s
                n = d.normalized() if d.length > 1e-9 and s > 0 else nor
                yield s, n
        for p, n in self.planes:
            yield (co - p).dot(n), n

    def pen(self, co):
        return max((self.clear - s for s, _ in self.each(co)), default=-1.0)

    def push(self, co):
        for _ in range(4):
            moved = False
            for s, n in self.each(co):
                if s < self.clear:
                    co = co + n * (self.clear - s + 1e-5)
                    moved = True
            if not moved:
                break
        return co


def step_cloth(mod, frames):
    mod.point_cache.frame_start = 1
    mod.point_cache.frame_end = frames
    sc = bpy.context.scene
    sc.frame_start, sc.frame_end = 1, frames
    t0 = time.time()
    for f in range(1, frames + 1):
        sc.frame_set(f)
    print(f"  cloth {mod.id_data.name}: {frames} frames in {time.time() - t0:.1f}s")


def relax(ob, weights, factor=0.6, iters=5):
    """Weighted Laplacian smoothing of the given vertices (index -> weight)."""
    me = ob.data
    nb = [[] for _ in me.vertices]
    for e in me.edges:
        a, b = e.vertices
        nb[a].append(b)
        nb[b].append(a)
    co = [v.co.copy() for v in me.vertices]
    for _ in range(iters):
        new = list(co)
        for i, w in weights.items():
            if w > 0 and nb[i]:
                avg = sum((co[k] for k in nb[i]), Vector()) / len(nb[i])
                new[i] = co[i] + (avg - co[i]) * factor * w
        co = new
    for v, c in zip(me.vertices, co):
        v.co = c
    me.update()


def taubin(ob, weights, iters=10, lam=0.6, mu=-0.64):
    """Weighted Taubin (lambda/mu) smoothing: irons out sharp folds without shrinking the region."""
    me = ob.data
    nb = [[] for _ in me.vertices]
    for e in me.edges:
        a, b = e.vertices
        nb[a].append(b)
        nb[b].append(a)
    co = [v.co.copy() for v in me.vertices]
    for _ in range(iters):
        for f in (lam, mu):
            new = list(co)
            for i, w in weights.items():
                if w > 0 and nb[i]:
                    avg = sum((co[k] for k in nb[i]), Vector()) / len(nb[i])
                    new[i] = co[i] + (avg - co[i]) * f * w
            co = new
    for v, c in zip(me.vertices, co):
        v.co = c
    me.update()


def sim_pillow(name, M, colliders, seed, frames=70, pressure=3.5, relax_iters=5, bend_max=4.0, taubin_iters=0):
    """Pressurised cloth pillow (closed puffed shell with piping) dropped onto the colliders, so it
    sags and moulds over what it lies on. The piping and corners are a stiffer vertex group (they are
    sewn, double-layered fabric) and the corner ears are relaxed afterwards, so they stay sewn points
    instead of crumpling."""
    bm, stiff, corner = pillow_bm(seed=seed)
    bmesh.ops.transform(bm, matrix=M, verts=bm.verts[:])
    ob = mesh_obj(name, bm, "M_Linen")
    vg = ob.vertex_groups.new(name="stiff")
    for i, w in stiff.items():
        vg.add([i], w, "REPLACE")
    for c in colliders:
        add_collision(c, 0.001, 8.0)
    mod = ob.modifiers.new("Cloth", "CLOTH")
    s = mod.settings
    s.quality = 15
    s.mass = 0.25
    s.air_damping = 2.0
    s.tension_stiffness, s.tension_stiffness_max = 25, 80
    s.compression_stiffness, s.compression_stiffness_max = 25, 80
    s.shear_stiffness, s.shear_stiffness_max = 12, 40
    s.bending_stiffness, s.bending_stiffness_max = 0.6, bend_max
    s.vertex_group_structural_stiffness = "stiff"
    s.vertex_group_shear_stiffness = "stiff"
    s.vertex_group_bending = "stiff"
    s.use_pressure = True
    s.uniform_pressure_force = pressure
    cs = mod.collision_settings
    cs.use_collision = True
    cs.distance_min = 0.004
    cs.collision_quality = 8
    cs.use_self_collision = False
    step_cloth(mod, frames)
    new = bake(ob, None, name)
    for vgr in list(new.vertex_groups):
        new.vertex_groups.remove(vgr)
    bpy.context.scene.frame_set(1)
    for cc in colliders:
        clear_mods(cc)
    relax(new, corner, 0.6, relax_iters)
    if taubin_iters:
        taubin(new, corner, taubin_iters)
    return new


def add_collision(ob, thick=0.001, friction=5.0):
    ob.modifiers.new("Collision", "COLLISION")
    ob.collision.thickness_outer = thick
    ob.collision.cloth_friction = friction
    ob.collision.damping = 0.5
    return ob


def clear_mods(ob):
    for mname in [m.name for m in ob.modifiers]:
        ob.modifiers.remove(ob.modifiers[mname])


def decimate(ob, target_tris):
    n = tri_count(ob)
    if n <= target_tris:
        return ob
    mod = ob.modifiers.new("dec", "DECIMATE")
    mod.ratio = target_tris / n
    mod.use_collapse_triangulate = True
    return bake(ob, None, ob.name)


def orient_up(ob):
    """Make the face winding consistent and pointing mostly up (+Z)."""
    me = ob.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.normal_update()
    nz = sum(f.normal.z * f.calc_area() for f in bm.faces)
    if nz < 0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
    bm.to_mesh(me)
    bm.free()
    me.update()


def push_mesh(ob, field, only=None):
    n = 0
    for v in ob.data.vertices:
        if only is not None and v.index not in only:
            continue
        co = field.push(v.co.copy())
        if (co - v.co).length > 1e-7:
            if (co - v.co).length > 0.03:
                print(f"  WARNING big push on {ob.name}: {(co - v.co).length / CM:.1f} cm at {v.co / CM}")
            v.co = co
            n += 1
    ob.data.update()
    return n


def bvh_of(ob):
    return BVHTree.FromObject(ob, bpy.context.evaluated_depsgraph_get())


def tri_data(ob):
    me = ob.data
    me.calc_loop_triangles()
    mw = ob.matrix_world
    verts = [mw @ v.co for v in me.vertices]
    tris = [tuple(t.vertices) for t in me.loop_triangles]
    return verts, tris, BVHTree.FromPolygons(verts, tris, epsilon=0.0)


def crossings(a, b, where=None, tris_out=None):
    """Triangle pairs that genuinely penetrate (each crosses the other's plane), like assemble_room.
    where: optional list that receives the centres (cm) of the penetrating triangles of a."""
    va, ta, ba = tri_data(a)
    vb, tb, bb = tri_data(b)
    pen, eps = 0, 0.0002
    for i, j in ba.overlap(bb):
        A = [va[k] for k in ta[i]]
        B = [vb[k] for k in tb[j]]
        na = (A[1] - A[0]).cross(A[2] - A[0])
        nb = (B[1] - B[0]).cross(B[2] - B[0])
        if na.length < 1e-12 or nb.length < 1e-12:
            continue
        na.normalize()
        nb.normalize()
        da = [na.dot(v - A[0]) for v in B]
        db = [nb.dot(v - B[0]) for v in A]
        if max(da) > eps and min(da) < -eps and max(db) > eps and min(db) < -eps:
            pen += 1
            if tris_out is not None:
                tris_out.update(ta[i])
            if where is not None:
                c = (A[0] + A[1] + A[2]) / 3 / CM
                where.append((round(c.x, 1), round(-c.y, 1), round(c.z, 1)))
    return pen


def resolve(ob, others, step_cm=0.3, iters=15):
    """Nudge the vertices of ob's triangles that pass through any of `others` away from the nearest
    surface (plus half as much on their neighbours) until nothing penetrates."""
    me = ob.data
    nb = [set() for _ in me.vertices]
    for e in me.edges:
        a, b = e.vertices
        nb[a].add(b)
        nb[b].add(a)
    bvhs = [bvh_of(o) for o in others]
    for it in range(iters):
        bad = set()
        for o in others:
            crossings(ob, o, tris_out=bad)
        if not bad:
            return it
        move = {}
        for i in bad:
            move[i] = 1.0
            for k in nb[i]:
                move.setdefault(k, 0.5)
        for i, w in move.items():
            co = me.vertices[i].co
            best = None
            for b in bvhs:
                loc, nor, _, d = b.find_nearest(co)
                if loc is not None and (best is None or d < best[0]):
                    best = (d, loc, nor)
            if best is None:
                continue
            d, loc, nor = best
            dirv = (co - loc)
            dirv = dirv.normalized() if dirv.dot(nor) > 0 and dirv.length > 1e-7 else nor
            me.vertices[i].co = co + dirv * (step_cm * w * CM)
        me.update()
    return iters


# ---- duvet / blanket parameters (cm) ----
DUV_T = 2.2                   # duvet thickness
DUV_H = DUV_T / 2
DUV_CLEAR = DUV_H + 0.25      # mid-surface clearance to colliders after the sim
HEM_R = 1.2                   # rolled hem radius
ROLL_R = 1.5 * DUV_T          # radius of the turned-back roll on top of the bed
X_FOLD, FLAP_L, X_END = -28.0, 33.0, 98.5
FLAP_DROP_PIN = 0.15          # soft goal weight on the turned-back flap's side drops
FLAP_BENDING = 3.0            # the doubled-over quilted flap is stiffer than the single drape (0.8)
FLAP_COMPRESSION = 15.0       # ...and resists bunching into narrow pleats
BLK_L = 1.0                   # crochet blanket layer thickness (two layers)
FLAP_HEM_X = X_FOLD - 2.0     # open edges head-side of this (the turned-back flap) get the rolled hem


def rest_on(bvh, dist_cm):
    """(x, y) cm -> z cm just above the surface below (ray cast down onto bvh) + dist_cm."""
    def f(x, y):
        hit = bvh.ray_cast(ue(x, y, 200), Vector((0, 0, -1)), 3.0)
        return (hit[0].z / CM if hit[0] is not None else MAT_ZT) + dist_cm
    return f


def push_grid(G, field, rows=None):
    for i in (range(len(G)) if rows is None else rows):
        row = G[i]
        for j, co in enumerate(row):
            row[j] = field.push(co)


def grid_obj(name, G, m, UV=None):
    """Quad sheet from a [row][col] grid of Blender-space points (rows advance toward +X for an
    upward-facing sheet). UV: matching [row][col] (u, v) in metres."""
    nr, nc = len(G), len(G[0])
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    V = [[bm.verts.new(co) for co in row] for row in G]
    for i in range(nr - 1):
        for j in range(nc - 1):
            f = bm.faces.new((V[i][j], V[i][j + 1], V[i + 1][j + 1], V[i + 1][j]))
            if UV:
                for lp, (ii, jj) in zip(f.loops, ((i, j), (i, j + 1), (i + 1, j + 1), (i + 1, j))):
                    lp[uvl].uv = UV[ii][jj]
    return mesh_obj(name, bm, m)


def grid_normals(G):
    """Per-point normals of a grid surface, matching grid_obj's face winding."""
    nr, nc = len(G), len(G[0])
    Nn = []
    for i in range(nr):
        row = []
        for j in range(nc):
            di = G[min(i + 1, nr - 1)][j] - G[max(i - 1, 0)][j]
            dj = G[i][min(j + 1, nc - 1)] - G[i][max(j - 1, 0)]
            n = dj.cross(di)
            row.append(n.normalized() if n.length > 1e-12 else Vector((0, 0, 1)))
        Nn.append(row)
    return Nn


def run_cloth(ob, frames, colliders, quality=10, mass=0.3, tension=15, compression=None, shear=5, bending=1.0,
              dist=0.007, self_coll=False, self_dist=0.012, air=1.0, pin=None, pin_stiff=1.0, grow=None,
              grow_amount=0.0, coll_quality=4, friction=5.0):
    for c in colliders:
        add_collision(c, 0.001, friction)
    mod = ob.modifiers.new("Cloth", "CLOTH")
    s = mod.settings
    s.quality = quality
    s.mass = mass
    s.air_damping = air
    s.tension_stiffness = tension
    s.compression_stiffness = tension if compression is None else compression
    s.shear_stiffness = shear
    s.bending_stiffness = bending
    if pin:
        s.vertex_group_mass = pin
        s.pin_stiffness = pin_stiff
    if grow:
        s.vertex_group_shrink = grow       # weight 0 -> shrink_min (grows), weight 1 -> shrink_max (unchanged)
        s.shrink_min = -grow_amount
        s.shrink_max = 0.0
    cs = mod.collision_settings
    cs.use_collision = True
    cs.distance_min = dist
    cs.collision_quality = coll_quality
    cs.use_self_collision = self_coll
    cs.self_distance_min = self_dist
    cs.self_friction = 5.0
    step_cloth(mod, frames)
    new = bake(ob, None, ob.name)
    for vg in list(new.vertex_groups):
        new.vertex_groups.remove(vg)
    if new.data.shape_keys:
        new.shape_key_clear()
    bpy.context.scene.frame_set(1)
    for c in colliders:
        clear_mods(c)
    return new


def read_grid(ob, nr, nc):
    vs = ob.data.vertices
    return [[vs[i * nc + j].co.copy() for j in range(nc)] for i in range(nr)]


def solid_copy(name, G, thick_cm):
    """Thickened temporary copy of a grid sheet (collider for the next layer)."""
    ob = grid_obj(name, G, "M_FloralCover")
    orient_up(ob)
    sol = ob.modifiers.new("sol", "SOLIDIFY")
    sol.thickness = thick_cm * CM
    sol.offset = 0.0
    sol.use_quality_normals = True
    return bake(ob, None, name)


def smoothstep(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


def puff_grid(G, amp_cm, seed, sign=1.0, edge_rows=3, edge_cols=3, row_w=None):
    """Quilted puff: displace each point along its normal by a low-frequency noise (amp_cm max),
    tapered to zero at the sheet edges."""
    Nn = grid_normals(G)
    nr, nc = len(G), len(G[0])
    for i in range(nr):
        for j in range(nc):
            p = G[i][j]
            w = min(1.0, min(i, nr - 1 - i) / edge_rows if edge_rows else 1.0,
                    min(j, nc - 1 - j) / edge_cols if edge_cols else 1.0)
            if row_w:
                w *= row_w(i)
            n = noise.noise(Vector((p.x * 4.0, p.y * 4.0, seed)))          # ~25 cm features
            d = amp_cm * (0.35 + 0.65 * (0.5 + 0.5 * n)) * w
            G[i][j] = p + Nn[i][j] * (sign * d * CM)


def x_end_at(y):
    """Foot edge of the duvet planform: straight at X_END, corners rounded back (soft dog-ears)."""
    a = abs(y) - 56.0
    if a <= 0:
        return X_END
    rc = 22.0
    return X_END - (rc - math.sqrt(max(0.0, rc * rc - a * a)))


def trim_flap(F, M, ys, above_cm=2.5, y_keep=40.0):
    """Shorten the turned-back flap's side drops so they end `above_cm` above the main duvet's side hem
    at the same position along the bed (a fold of the duvet cannot hang below the duvet itself).
    Each flap row's drop part (|y| > y_keep, an arc down the bed side) is resampled along its own
    polyline between the start of the drop and the arc length where it reaches the cut height, so the
    grid stays structured and the new boundary columns get the rolled hem from thicken(). Row 0 (the
    fold, shared with the roll) is left alone: on the side drops it already ends at the main hem."""
    nf, ny = len(F), len(F[0])
    jmid = ny // 2
    mx = [row[jmid].x for row in M]
    left = [j for j in range(ny) if ys[j] < -y_keep]
    right = [j for j in range(ny) if ys[j] > y_keep]
    jl, jr = left[-1] + 1, right[0] - 1           # last kept column on each side (start of the drop)
    trimmed = []
    for k in range(1, nf):
        row = F[k]
        i = min(range(len(M)), key=lambda ii: abs(mx[ii] - row[jmid].x))
        for cols, hem in ((list(range(jl, -1, -1)), M[i][0]), (list(range(jr, ny)), M[i][ny - 1])):
            zcut = hem.z + above_cm * CM
            pts = [row[j].copy() for j in cols]
            acc = [0.0]
            for a, b in zip(pts, pts[1:]):
                acc.append(acc[-1] + (b - a).length)
            s_full, s_cut = acc[-1], acc[-1]
            for q in range(1, len(pts)):
                if pts[q].z < zcut <= pts[q - 1].z:
                    t = (pts[q - 1].z - zcut) / max(1e-9, pts[q - 1].z - pts[q].z)
                    s_cut = acc[q - 1] + t * (acc[q] - acc[q - 1])
                    break
            if s_cut >= s_full - 1e-6:
                continue
            trimmed.append((s_full - s_cut) / CM)
            sc = s_cut / s_full
            for n, j in enumerate(cols):
                target = acc[n] * sc
                q = 1
                while q < len(acc) - 1 and acc[q] < target:
                    q += 1
                t = (target - acc[q - 1]) / max(1e-12, acc[q] - acc[q - 1])
                row[j] = pts[q - 1].lerp(pts[q], max(0.0, min(1.0, t)))
    if trimmed:
        print(f"  flap trim: {len(trimmed)} row ends shortened, up to {max(trimmed):.1f} cm")


def iron_flap(F, ys, iters=8):
    """The turned-back flap is a doubled-over quilted duvet: it lies in broad soft undulations, not narrow
    pleats. Narrow pleats ending at the free edge pinched the hem into a staircase of little steps.
    1. Taubin smoothing over the flat top part of the flap (rows 1.., |y| < ~50); the free edge row is
       smoothed along itself only, so it is not pulled back toward the fold.
    2. the free edge and the two rows behind it: 1-D Taubin along the hem, so the hem runs as one
       continuous smooth line across the bed."""
    nf, ny = len(F), len(F[0])
    wy = [1.0 - smoothstep(42.0, 52.0, abs(y)) for y in ys]
    for _ in range(iters):
        for f in (0.6, -0.63):
            new = [list(r) for r in F]
            for k in range(1, nf):
                for j in range(1, ny - 1):
                    w = wy[j] * (0.5 if k == 1 else 1.0)
                    if w <= 0:
                        continue
                    nb = [F[k][j - 1], F[k][j + 1]]
                    if k < nf - 1:
                        nb += [F[k - 1][j], F[k + 1][j]]
                    avg = sum(nb, Vector()) / len(nb)
                    new[k][j] = F[k][j] + (avg - F[k][j]) * f * w
            F[:] = new
    for k, wk in ((nf - 1, 1.0), (nf - 2, 0.7), (nf - 3, 0.35)):
        row = F[k]
        for _ in range(12):
            for f in (0.5, -0.53):
                row = [row[0]] + [row[j] + ((row[j - 1] + row[j + 1]) / 2 - row[j]) * f * wk * max(0.3, wy[j])
                                  for j in range(1, ny - 1)] + [row[-1]]
        F[k] = row


def build_duvet(bed_col, pillows, duv_field):
    """Floral duvet with a turned-back top.
    1. main sheet (fold line -> foot, 160 cm wide, 74 x 80 grid) dropped from ~10 cm with slack onto
       the bed: light goal pins at four points on the top, low bending / compression so it buckles,
       the drape region grows 7 % so the side drops gather into vertical folds, and a turbulence
       field stirs it for the first ~20 frames. Rounded foot corners collapse into soft dog-ears.
    2. a quilted puff (low-frequency normal displacement) on the main sheet.
    3. the flap: its first row is pinned at the top of a fat round roll (radius 1.5 x thickness),
       the rest drops onto a thickened copy of the main sheet and settles freely.
    4. roll + flap + main become one grid, smoothed around the fold, decimated (quadric collapse,
       which keeps folds and drops flat areas first), then thickened with a rounded hem and a
       lighter (M_Linen) reverse side, which is what shows on the turned-back flap."""
    bed_bvh = bvh_of(bed_col)
    ny, nx = 80, 74
    ys = [-78.0 + 156.0 * j / (ny - 1) for j in range(ny)]
    dist = DUV_H + 0.35
    z0 = MAT_ZT + dist + 8.0
    G0, UV = [], []
    for i in range(nx):
        row, uvr = [], []
        for y in ys:
            x = X_FOLD + (x_end_at(y) - X_FOLD) * i / (nx - 1)
            lift = 2.5 * (0.5 + 0.5 * noise.noise(Vector((x * 0.03, y * 0.03, 1.7))))
            row.append(ue(x, y, z0 + lift))
            uvr.append((x * CM, y * CM))
        G0.append(row)
        UV.append(uvr)
    ob = grid_obj("duvet_main", G0, "M_FloralCover", UV)
    # light goal pins at four points on the top, lowered onto the bed over the first 18 frames
    rest = rest_on(bed_bvh, dist)
    pins = {}
    for (px, py) in ((6, -20), (6, 20), (64, -20), (64, 20)):
        jc = min(range(ny), key=lambda j: abs(ys[j] - py))
        ic = min(range(nx), key=lambda i: abs(X_FOLD + (X_END - X_FOLD) * i / (nx - 1) - px))
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                w = 0.28 if di == dj == 0 else 0.14
                k = (ic + di) * ny + jc + dj
                pins[k] = max(pins.get(k, 0.0), w)
    vg = ob.vertex_groups.new(name="pin")
    for k, w in pins.items():
        vg.add([k], w, "REPLACE")
    # drape region (|y| > 44) grows -> the side drops buckle into vertical folds
    vgg = ob.vertex_groups.new(name="keep")
    for i in range(nx):
        for j, y in enumerate(ys):
            vgg.add([i * ny + j], 1.0 - smoothstep(42.0, 52.0, abs(y)), "REPLACE")
    ob.shape_key_add(name="Basis")
    sk = ob.shape_key_add(name="Down")
    for k in pins:
        co = ob.data.vertices[k].co
        sk.data[k].co = Vector((co.x, co.y, rest(co.x / CM, -co.y / CM) * CM))
    sk.value = 0.0
    sk.keyframe_insert("value", frame=1)
    sk.value = 1.0
    sk.keyframe_insert("value", frame=18)
    bpy.ops.object.effector_add(type="TURBULENCE", location=ue(30, 0, 75))
    turb = bpy.context.object
    turb.field.size = 0.25
    turb.field.strength = 2.5
    turb.keyframe_insert(data_path="field.strength", frame=1)
    turb.field.strength = 0.0
    turb.keyframe_insert(data_path="field.strength", frame=22)
    ob = run_cloth(ob, 120, [bed_col] + pillows, quality=10, mass=0.3, tension=15, compression=5, shear=5,
                   bending=0.8, dist=dist * CM, self_coll=False, air=1.5, pin="pin",
                   pin_stiff=1.0, grow="keep", grow_amount=0.07)
    bpy.data.objects.remove(turb, do_unlink=True)
    M = read_grid(ob, nx, ny)
    bpy.data.objects.remove(ob, do_unlink=True)
    push_grid(M, duv_field)
    zs = [co.z / CM for row in M for co in row]
    print(f"  main sheet z {min(zs):.1f}..{max(zs):.1f}")
    puff_grid(M, 1.0, 4.2, edge_rows=4, edge_cols=4, row_w=lambda i: smoothstep(2, 8, i))
    push_grid(M, duv_field)
    # relax the buckles right at the fold line on the side drops, so the roll and the turned-back
    # flap can lie cleanly over them
    Nm0 = grid_normals(M)
    for _ in range(6):
        new = [list(r) for r in M]
        for i in range(0, 7):
            wi = 1.0 - smoothstep(2, 7, i)
            for j in range(1, ny - 1):
                w = wi * (1.0 - smoothstep(0.5, 0.85, Nm0[0][j].z))
                if w <= 0:
                    continue
                nbrs = [M[i][j - 1], M[i][j + 1], M[i + 1][j]] + ([M[i - 1][j]] if i else [])
                avg = sum(nbrs, Vector()) / len(nbrs)
                new[i][j] = M[i][j] + (avg - M[i][j]) * 0.5 * w
        M = new
    push_grid(M, duv_field)
    main_tmp = solid_copy("duvet_tmp", M, DUV_T)

    # ---- roll geometry along the fold line (main row 0)
    Nm = grid_normals(M)
    K = 6
    tops, roll = [], [[None] * ny for _ in range(K - 1)]
    tang, nrm = [], []
    for j in range(ny):
        n = Nm[0][j]
        t = M[1][j] - M[0][j]
        t = (t - n * t.dot(n)).normalized()
        R = 2.0 + (ROLL_R - 2.0) * smoothstep(0.35, 0.9, n.z)
        C = M[0][j] + n * (R * CM)
        tops.append(C + n * (R * CM))
        for k in range(1, K):
            ph = math.pi * (K - k) / K           # k = 1 -> near the top, k = K-1 -> near main row 0
            roll[k - 1][j] = C - n * (R * CM * math.cos(ph)) - t * (R * CM * math.sin(ph))
        tang.append(t)
        nrm.append(n)
    # ---- flap: row 0 pinned at the roll top, the rest falls onto the thickened main sheet
    nf = 20
    sf = FLAP_L / (nf - 1)
    F0 = []
    for k in range(nf):
        row = []
        for j, y in enumerate(ys):
            lift = 0.0 if k == 0 else (1.2 + 1.0 * k / nf + 0.8 * noise.noise(Vector((k * 0.3, y * 0.05, 5.1))))
            row.append(tops[j] + tang[j] * (k * sf * CM) + nrm[j] * (lift * CM))
        F0.append(row)
    fob = grid_obj("duvet_flap", F0, "M_FloralCover")
    vgp = fob.vertex_groups.new(name="pin")
    vgp.add(list(range(ny)), 1.0, "REPLACE")
    # the flap's side drops start as a band level with the fold (which ends at the main hem): a soft
    # goal there stops them sliding down the main drop (they used to end 8-10 cm below the main hem)
    for k in range(1, nf):
        for j, y in enumerate(ys):
            w = FLAP_DROP_PIN * smoothstep(42.0, 52.0, abs(y))
            if w > 0:
                vgp.add([k * ny + j], w, "REPLACE")
    fdist = DUV_H + 0.45
    fob = run_cloth(fob, 70, [main_tmp, bed_col] + pillows, quality=10, mass=0.3, tension=15,
                    compression=FLAP_COMPRESSION, shear=5, bending=FLAP_BENDING, dist=fdist * CM, self_coll=False,
                    air=1.5, pin="pin", pin_stiff=5.0, friction=40.0)
    F = read_grid(fob, nf, ny)
    iron_flap(F, ys)
    bpy.data.objects.remove(fob, do_unlink=True)
    flap_field = Field(duv_field.bvhs + [bvh_of(main_tmp)], clear=(DUV_H + 0.4) * CM)
    push_grid(F, flap_field, rows=range(1, nf))
    for j in range(ny):
        F[0][j] = tops[j]
    puff_grid(F, 0.6, 7.7, edge_rows=0, edge_cols=4, row_w=lambda i: smoothstep(2, 6, i) * smoothstep(0, 3, nf - 1 - i))
    push_grid(F, flap_field, rows=range(1, nf))
    zs = [co.z / CM for row in F for co in row]
    print(f"  flap z {min(zs):.1f}..{max(zs):.1f} before trim")
    if not os.environ.get("NO_FLAP_TRIM"):
        trim_flap(F, M, ys, above_cm=2.5)
    push_grid(F, flap_field, rows=range(1, nf))
    zs = [co.z / CM for row in F for co in row]
    print(f"  flap z {min(zs):.1f}..{max(zs):.1f} after trim")

    # ---- one grid: flap (free edge first) -> roll -> main
    G = [list(r) for r in reversed(F)] + [list(r) for r in roll] + [list(r) for r in M]
    i_roll0, i_roll1 = nf - 1, nf - 1 + K          # flap row 0 .. main row 0
    # smooth the region around the fold (removes crumples where the flap meets the roll)
    lo, hi = i_roll0 - 6, i_roll1 + 4
    for _ in range(3):
        new = [list(r) for r in G]
        for i in range(lo, hi + 1):
            in_roll = i_roll0 <= i <= i_roll1
            for j in range(ny):
                nbrs = [G[i][jj] for jj in (j - 1, j + 1) if 0 <= jj < ny]
                if not in_roll:
                    nbrs += [G[ii][j] for ii in (i - 1, i + 1)]
                avg = sum(nbrs, Vector()) / len(nbrs)
                w = 0.5 * (1.0 if lo + 2 <= i <= hi - 2 else 0.5)
                new[i][j] = G[i][j] + (avg - G[i][j]) * w
        G = new
    for i in range(lo, hi + 1):
        if i < i_roll0:
            for j in range(ny):
                G[i][j] = flap_field.push(G[i][j])
        else:
            for j in range(ny):
                G[i][j] = duv_field.push(G[i][j])
    bpy.data.objects.remove(main_tmp, do_unlink=True)
    # UVs: arc length along each column (m) x unreal y (m)
    UVc = [[None] * ny for _ in G]
    for j in range(ny):
        s = 0.0
        for i in range(len(G)):
            if i:
                s += (G[i][j] - G[i - 1][j]).length
            UVc[i][j] = (s - 0.6, ys[j] * CM)
    mid = grid_obj("duvet_mid", G, "M_FloralCover", UVc)
    flap_rows = set(range(0, i_roll0))
    flap_idx = {i * ny + j for i in flap_rows for j in range(ny)}
    print(f"  duvet grid {len(G)} x {ny}: {tri_count(mid)} tris")
    return mid, flap_idx


def tri_cross(A, B, eps=0.0001):
    na = (A[1] - A[0]).cross(A[2] - A[0])
    nb = (B[1] - B[0]).cross(B[2] - B[0])
    if na.length < 1e-12 or nb.length < 1e-12:
        return False
    na.normalize()
    nb.normalize()
    da = [na.dot(v - A[0]) for v in B]
    db = [nb.dot(v - B[0]) for v in A]
    return max(da) > eps and min(da) < -eps and max(db) > eps and min(db) < -eps


def shell_scale(src, h):
    """Per-vertex thickness factors so the front and reverse shells never pass through each other
    (large triangles across tight folds would otherwise push the reverse shell out through the front)."""
    src.verts.ensure_lookup_table()
    tris = [tuple(v.index for v in f.verts) for f in src.faces]
    sc = [1.0] * len(src.verts)
    nbr = [[e.other_vert(v).index for e in v.link_edges] for v in src.verts]
    for it in range(17):
        T = [v.co + v.normal * (h * sc[v.index]) for v in src.verts]
        Bv = [v.co - v.normal * (h * sc[v.index]) for v in src.verts]
        bt = BVHTree.FromPolygons(T, tris, epsilon=0.0)
        bb = BVHTree.FromPolygons(Bv, tris, epsilon=0.0)
        bad = set()
        for i, j in bt.overlap(bb):
            if tri_cross([T[k] for k in tris[i]], [Bv[k] for k in tris[j]]):
                bad.update(tris[i])
                bad.update(tris[j])
        # front shell folding through itself in a tight crease
        for i, j in bt.overlap(bt):
            if i < j and not set(tris[i]) & set(tris[j]) and                     tri_cross([T[k] for k in tris[i]], [T[k] for k in tris[j]]):
                bad.update(tris[i])
                bad.update(tris[j])
        if not bad or it == 16:
            break
        # thin the crossing verts and (less) their neighbours: a triangle spanning a thinned vertex and an
        # unthinned one can still reach through the other shell
        ring = {q for k in bad for q in nbr[k]} - bad
        for k in bad:
            sc[k] *= 0.7
        for k in ring:
            sc[k] *= 0.9
    print(f"  thicken: {sum(1 for x in sc if x < 1)} verts thinned, min factor {min(sc):.2f}, "
          f"{len(bad)} verts still crossing",
          sorted({(round(src.verts[k].co.x / CM), round(-src.verts[k].co.y / CM), round(src.verts[k].co.z / CM))
                  for k in bad})[:12])
    shell_scale.bad = sorted(bad)
    return sc


def thicken(mid, h_cm, hem_cm, name, round_edge=None):
    """Give a cloth mid-surface thickness: front shell (M_FloralCover) along +normal, reverse shell
    (M_Linen, the lighter back of the cover) along -normal, and a rounded rolled hem on the open edges.
    round_edge(midpoint) -> bool picks the edges that get the rolled hem (default all); the others are
    closed with a single smooth-shaded strip (2 instead of 4 triangles per edge)."""
    src = bmesh.new()
    src.from_mesh(mid.data)
    src.normal_update()
    suv = src.loops.layers.uv.get("UVMap")
    vuv = {}
    for f in src.faces:
        for lp in f.loops:
            vuv.setdefault(lp.vert.index, lp[suv].uv.copy())
    h, r = h_cm * CM, hem_cm * CM
    sc = shell_scale(src, h)
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    top = {v.index: bm.verts.new(v.co + v.normal * (h * sc[v.index])) for v in src.verts}
    bot = {v.index: bm.verts.new(v.co - v.normal * (h * sc[v.index])) for v in src.verts}
    for f in src.faces:
        idx = [v.index for v in f.verts]
        ft = bm.faces.new([top[i] for i in idx])
        ft.material_index = 0
        for lp, i in zip(ft.loops, idx):
            lp[uvl].uv = vuv[i]
        fb = bm.faces.new([bot[i] for i in reversed(idx)])
        fb.material_index = 1
        for lp, i in zip(fb.loops, reversed(idx)):
            lp[uvl].uv = vuv[i]
    bnd = [e for e in src.edges if e.is_boundary]
    rnd = {e.index for e in bnd if round_edge is None or round_edge((e.verts[0].co + e.verts[1].co) / 2)}
    out = {}
    for e in bnd:
        if e.index not in rnd:
            continue
        a, b = e.verts
        f = e.link_faces[0]
        o = (b.co - a.co).cross(f.normal).normalized()
        if o.dot((a.co + b.co) / 2 - f.calc_center_median()) < 0:
            o = -o
        for v in (a, b):
            out[v.index] = out.get(v.index, Vector()) + o
    hem = {}
    for v in src.verts:
        if v.index in out:
            o = out[v.index]
            o = (o - v.normal * o.dot(v.normal)).normalized()
            hem[v.index] = bm.verts.new(v.co + o * (r * max(0.5, sc[v.index])))
    for e in bnd:
        a, b = (v.index for v in e.verts)
        strips = ((top, hem), (hem, bot)) if e.index in rnd else ((top, bot),)
        for (p, q) in strips:
            f = bm.faces.new((p[a], p[b], q[b], q[a]))
            f.material_index = 0
            for lp, (i, dv) in zip(f.loops, ((a, 0), (b, 0), (b, 1), (a, 1))):
                u = vuv[i]
                lp[uvl].uv = (u.x, u.y + dv * 0.012 + (0.012 if p is hem else 0.0))
    # where a rolled-hem edge meets a plain edge, close the corner with one triangle
    for v in src.verts:
        if v.index in hem and any(e.is_boundary and e.index not in rnd for e in v.link_edges):
            f = bm.faces.new((top[v.index], hem[v.index], bot[v.index]))
            f.material_index = 0
            u = vuv[v.index]
            for lp, dv in zip(f.loops, (0.0, 0.012, 0.024)):
                lp[uvl].uv = (u.x, u.y + dv)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    src.free()
    ob = mesh_obj(name, bm, None)
    ob["shell_bad"] = shell_scale.bad
    ob.data.materials.append(mat("M_FloralCover"))
    ob.data.materials.append(mat("M_Linen"))
    return ob


def boundary_edges(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    n = sum(1 for e in bm.edges if e.is_boundary)
    bm.free()
    return n


def self_crossing_verts(ob):
    me = ob.data
    me.calc_loop_triangles()
    co = [v.co.copy() for v in me.vertices]
    tris = [tuple(t.vertices) for t in me.loop_triangles]
    bt = BVHTree.FromPolygons(co, tris, epsilon=0.0)
    bad = set()
    for i, j in bt.overlap(bt):
        if i < j and not set(tris[i]) & set(tris[j]) and                 tri_cross([co[k] for k in tris[i]], [co[k] for k in tris[j]]):
            bad.update(tris[i])
            bad.update(tris[j])
    return bad


def untangle(ob, field, iters=12):
    """Remove self-intersections of a cloth mid-surface (decimation can fold triangles through each
    other in tight creases): smooth the crossing verts and their neighbours, keep clearances."""
    me = ob.data
    nb = [set() for _ in me.vertices]
    for e in me.edges:
        a, b = e.vertices
        nb[a].add(b)
        nb[b].add(a)
    bad = self_crossing_verts(ob)
    n0 = len(bad)
    for it in range(iters):
        if not bad:
            break
        w = {}
        for i in bad:
            w[i] = 1.0
            for k in nb[i]:
                w.setdefault(k, 0.6)
                for k2 in nb[k]:
                    w.setdefault(k2, 0.3)
        relax(ob, w, 0.5, 3)
        push_mesh(ob, field, only=set(w))
        bad = self_crossing_verts(ob)
    print(f"  untangle: {n0} -> {len(bad)} self-crossing verts")


def dbg_keep(ob, name):
    """DBG=1: keep an unrendered copy of an intermediate mesh (saved with CHECK_BLEND)."""
    if os.environ.get("DBG"):
        c = link(bpy.data.objects.new(name, ob.data.copy()))
        c.matrix_world = ob.matrix_world.copy()
        c.hide_render = True


def duvet_cost(ob):
    """Triangles of thicken(ob): two shells + 4 per rolled-hem edge + 2 per plain edge (+ corner tris)."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    rnd = pln = 0
    for e in bm.edges:
        if e.is_boundary:
            if ((e.verts[0].co.x + e.verts[1].co.x) / 2) < FLAP_HEM_X * CM:
                rnd += 1
            else:
                pln += 1
    bm.free()
    return 2 * tri_count(ob) + 4 * rnd + 2 * pln + 4


def finish_duvet(mid, budget, duv_field):
    """Decimate the mid-surface so the thickened duvet fits the budget, keep clearances, thicken."""
    n0 = tri_count(mid)
    target = (budget - 250) / 2
    for _ in range(8):
        test = link(bpy.data.objects.new("dec_test", mid.data.copy()))
        test = decimate(test, int(target))
        total = duvet_cost(test)
        bpy.data.objects.remove(test, do_unlink=True)
        if total <= budget:
            break
        target -= (total - budget) / 2 + 4
    dbg_keep(mid, "DBG_mid")
    dec = decimate(mid, int(target))
    orient_up(dec)
    untangle(dec, duv_field)
    dbg_keep(dec, "DBG_dec")
    print(f"  duvet mid {n0} -> {tri_count(dec)} tris, {boundary_edges(dec)} hem edges;",
          "pushed", push_mesh(dec, duv_field))
    return dec


def build_blanket(duvet, bed_bvh, bed_col, others):
    """Folded crochet blanket across the foot: a strip simulated over the duvet (low bending, some
    noise lift so the side drops hang in gentle waves), rebuilt as two real 1 cm layers: the strip
    folded over at the foot end, the top layer's scalloped hem stepping back 4-5 cm from the bottom
    layer's scalloped hem, with slightly lumpy tops."""
    dbvh = bvh_of(duvet)
    sdist = BLK_L + 0.35                         # interface surface between the layers -> duvet
    zs = [(duvet.matrix_world @ v.co).z for v in duvet.data.vertices
          if 44 * CM < v.co.x < 100 * CM]                # highest duvet point under the whole strip
    z_start = max(zs) / CM + sdist + 0.6
    nx, x0, x1 = 12, 48.0, 91.0
    ny, y0, y1 = 77, -76.0, 76.0                 # simulated longer; the free ends are discarded
    BLK_HALF = BLK_HALF_W
    xs = [x0 + (x1 - x0) * i / (nx - 1) for i in range(nx)]
    ys = [y0 + (y1 - y0) * j / (ny - 1) for j in range(ny)]
    rest = rest_on(dbvh, sdist + 0.05)
    # start pre-draped (an inverted U just outside the duvet), so the ends settle instead of
    # free-falling and tunnelling through the duvet drop
    yt, rc = 52.0, 6.0
    arc = rc * math.pi / 2
    G0 = []
    for x in xs:
        row = []
        for y in ys:
            a = abs(y)
            lift = 1.0 + 1.5 * (0.5 + 0.5 * noise.noise(Vector((x * 0.08, y * 0.06, 9.3))))
            if a < 38.0:
                yy, z = y, rest(x, y)
            elif a <= yt:
                yy, z = y, z_start + lift
            elif a <= yt + arc:
                t = (a - yt) / rc
                yy, z = math.copysign(yt + rc * math.sin(t), y), z_start + lift - rc * (1 - math.cos(t))
            else:
                yy, z = math.copysign(yt + rc, y), z_start + lift - rc - (a - yt - arc)
            row.append(ue(x, yy, z))
        G0.append(row)
    ob = grid_obj("blanket_sim", G0, "M_Crochet")
    vg = ob.vertex_groups.new(name="pin")
    for i in range(nx):
        for j, y in enumerate(ys):
            w = 1.0 - smoothstep(30.0, 40.0, abs(y))      # the top rests where it lies; the drops hang
            if w > 0:
                vg.add([i * ny + j], w, "REPLACE")
    vgk = ob.vertex_groups.new(name="keep")         # the drops grow 6 % -> gentle vertical waves
    for i in range(nx):
        for j, y in enumerate(ys):
            vgk.add([i * ny + j], 1.0 - smoothstep(44.0, 52.0, abs(y)), "REPLACE")
    ob = run_cloth(ob, 80, [duvet, bed_col], quality=12, mass=0.5, tension=20, compression=6, shear=8,
                   bending=4.5, dist=sdist * CM, air=2.0, pin="pin", pin_stiff=3.0, friction=10.0,
                   coll_quality=6, grow="keep", grow_amount=0.06)
    P = read_grid(ob, nx, ny)
    bpy.data.objects.remove(ob, do_unlink=True)
    push_grid(P, Field([dbvh, bed_bvh], clear=(BLK_L + 0.25) * CM))
    Nn = grid_normals(P)
    # the folded stack keeps its section: blend each normal with its column's mean normal so the
    # layer offsets cannot flip where the free ends crumple
    Nc = [sum((Nn[i][j] for i in range(nx)), Vector()).normalized() for j in range(ny)]
    Nn = [[(Nn[i][j] * 0.35 + Nc[j] * 0.65).normalized() for j in range(ny)] for i in range(nx)]
    # on the side drops the duvet folds bulge between the ring columns: hang the blanket a little
    # further off there so the faces between columns clear the fold crests
    far = Field([dbvh, bed_bvh], clear=(BLK_L + 1.1) * CM)
    for i in range(nx):
        for j in range(ny):
            w = 1.0 - smoothstep(0.45, 0.8, Nc[j].z)
            if w > 0:
                q = far.push(P[i][j])
                P[i][j] = P[i][j] + (q - P[i][j]) * w

    def sample(x, jf):
        fi = (x - x0) / (x1 - x0) * (nx - 1)
        i0 = max(0, min(nx - 2, int(math.floor(fi))))
        j0 = max(0, min(ny - 2, int(math.floor(jf))))
        a, b = fi - i0, jf - j0

        def lerp(Gr):
            return (Gr[i0][j0] * ((1 - a) * (1 - b)) + Gr[i0 + 1][j0] * (a * (1 - b)) +
                    Gr[i0][j0 + 1] * ((1 - a) * b) + Gr[i0 + 1][j0 + 1] * (a * b))
        p = lerp(P)
        n = lerp(Nn).normalized()
        return p, n

    def point(x, jf, level, dx=0.0, lump=0.0):
        p, n = sample(x, jf)
        q, _ = sample(min(x1, x + 1.0), jf)
        q0, _ = sample(max(x0, x - 1.0), jf)
        t = q - q0
        t = (t - n * t.dot(n)).normalized()
        return p + n * ((level + lump) * BLK_L * CM) + t * (dx * CM)

    ncol, K, dense, polys = blanket_layout()
    XF = 89.0                                   # fold edge, clear of the duvet's rounded foot corners
    xb0, xt0 = 52.0, 56.5                       # hem cusp lines: bottom layer, top layer
    R = len(dense)
    full, vcoord, cdirs = [], [], []
    for c in range(ncol):
        yc = -BLK_HALF + 2 * BLK_HALF * c / (ncol - 1)
        jf = (yc - y0) / (y1 - y0) * (ny - 1)
        # crochet shell hem: half-sine arcs meeting at cusps, 7.8 cm period, 4 columns per shell
        sh = BLK_SHELL_AMP * abs(math.sin(math.pi * (c % BLK_SHELL_COLS) / BLK_SHELL_COLS))
        xb, xt = xb0 - sh, xt0 - sh
        pts = [point(xb + 0.25, jf, -1.0)]                                          # 0  B0 (dense)
        pts += [point(xb0 + (XF - xb0) * f, jf, -1.0) for f in (0.25, 0.5, 0.75)]   # 1-3
        pts += [point(XF, jf, -1.0), point(XF, jf, -0.707, 0.707), point(XF, jf, 0.0, 1.0),
                point(XF, jf, 0.707, 0.707), point(XF, jf, 1.0)]                    # 4-8 fold
        pts += [point(XF - (XF - xt0) * 0.5, jf, 1.0)]                              # 9  top layer
        pts += [point(xt + 0.25, jf, 1.0), point(xt, jf, 0.5, -0.3), point(xt + 0.25, jf, 0.05),
                point(xb + 0.25, jf, 0.0), point(xb, jf, -0.5, -0.3)]               # 10-14 hems (dense)
        full.append(pts)
        cdirs.append(sample(70.0, jf)[1])
        vcoord.append(yc * CM)
    u_acc = [0.0]
    for k in range(R):
        u_acc.append(u_acc[-1] + sum((rg[(k + 1) % R] - rg[k]).length for rg in full) / ncol)
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    Kset = set(K)
    V, vcol = {}, []
    for c in range(ncol):
        for k in range(R):
            if dense[k] or c in Kset:
                V[c, k] = bm.verts.new(full[c][k])
                vcol.append(c)
    caps = {0, ncol - 1}
    new_faces = []
    for poly in polys:
        f = bm.faces.new([V[ck] for ck in poly])
        new_faces.append(f)
        is_cap = len({c for c, _ in poly}) == 1
        for lp, (c, k) in zip(f.loops, poly):
            if is_cap:
                co = lp.vert.co
                lp[uv].uv = (co.x, co.z)
            else:
                kk = k
                # the closing segment of the ring (k = R-1 -> 0) uses u = u_acc[R] for k = 0
                if k == 0 and any(q == R - 1 for _, q in poly):
                    kk = R
                lp[uv].uv = (u_acc[kk], vcoord[c])
    bmesh.ops.triangulate(bm, faces=[f for f in new_faces if len(f.verts) > 4], quad_method="BEAUTY",
                          ngon_method="BEAUTY")
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    blanket = mesh_obj("blanket", bm, "M_Crochet")
    print(f"  blanket: {ncol} columns ({len(K)} body columns), ring {R}, {tri_count(blanket)} tris")
    # keep the folded section intact: lift whole columns off whatever they cut into
    me = blanket.data
    moved = [0.0] * ncol
    cols = set()
    for it in range(25):
        bad = set()
        for o in others:
            crossings(blanket, o, tris_out=bad)
        cols = {vcol[i] for i in bad}
        if not cols:
            break
        lift = {}
        for c in cols:
            for dc, w in ((0, 1.0), (1, 0.6), (2, 0.35), (3, 0.15)):
                for c2 in {c - dc, c + dc}:
                    if 0 <= c2 < ncol:
                        lift[c2] = max(lift.get(c2, 0.0), w)
        for i, v in enumerate(me.vertices):
            w = lift.get(vcol[i], 0.0)
            if w:
                v.co += cdirs[vcol[i]] * (0.25 * w * CM)
        for c, w in lift.items():
            moved[c] += 0.25 * w
        me.update()
    print(f"  blanket column lift: {it} iterations, max {max(moved):.2f} cm, still crossing cols {sorted(cols)}")
    return blanket


LINEN_BUDGET = 3690          # bed set budget 8k: SM_Bed ~4.29k + linen <= 3.69k
PILLOW_B_TRIS = 820          # propped pillow (its crease is seen up close from the bedside)
BLK_HALF_W = 66.0            # blanket half length across the bed (cm)
BLK_SHELL_COLS = 4           # columns per crochet shell (cusp, 0.71, crown 1.0, 0.71)
BLK_SHELLS = 13              # shells along each hem -> period 132 / 13 = 10.2 cm
BLK_SHELL_AMP = 1.7          # shell depth (cm) at the crown
BLK_FLAT_Y = 42.0            # |y| below which the blanket lies flat on top: body on the cusp columns only
BLK_DROP_STEP = 3            # body column step on the side drops (7.7 cm, follows the drape over the edge)
BLK_DENSE = (1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1)   # ring points that follow every hem column


def blanket_layout():
    """Topology of the folded blanket (pure python, so the budget is known before it is built).
    Columns run across the bed; every column carries the hem ring points (dense) so the shells are
    round, but the body ring points (the fold and the two layer faces) only exist on the body columns
    K: the cusp columns where the blanket lies flat on top, every 3rd column on the side drops. Mixed strips
    between dense and body ring points become ngons (triangulated later).
    Returns (ncol, K, dense, polys) with polys as lists of (column, ring index)."""
    ncol = BLK_SHELL_COLS * BLK_SHELLS + 1
    dense = BLK_DENSE
    R = len(dense)
    K = []
    for c in range(ncol):
        yc = -BLK_HALF_W + 2 * BLK_HALF_W * c / (ncol - 1)
        if c in (0, ncol - 1) or (abs(yc) <= BLK_FLAT_Y and c % BLK_SHELL_COLS == 0) or                 (abs(yc) > BLK_FLAT_Y and c % BLK_DROP_STEP == 0):
            K.append(c)
    polys = []
    for a, b in zip(K, K[1:]):
        for k in range(R):
            k2 = (k + 1) % R
            if dense[k] and dense[k2]:
                for c in range(a, b):
                    polys.append([(c, k), (c, k2), (c + 1, k2), (c + 1, k)])
            else:
                poly = [(a, k), (a, k2)]
                if dense[k2]:
                    poly += [(c, k2) for c in range(a + 1, b)]
                poly += [(b, k2), (b, k)]
                if dense[k]:
                    poly += [(c, k) for c in range(b - 1, a, -1)]
                polys.append(poly)
    for c in (0, ncol - 1):
        polys.append([(c, k) for k in range(R)])
    return ncol, K, dense, polys


BLANKET_TRIS = sum(len(pl) - 2 for pl in blanket_layout()[3])


def build_linen(bed, mattress_col):
    bed_bvh = bvh_of(bed)
    bed_col = link(bpy.data.objects.new("COL_bed", bed.data.copy()))
    # pillow A: dropped flat onto the mattress, slightly askew
    MA = Matrix.Translation(ue(-60, -1, 65)) @ Matrix.Rotation(math.radians(-2), 4, "Z")
    pa = sim_pillow("pillowA", MA, [bed_col], 1.3, 70, 3.5)
    push_mesh(pa, Field([bed_bvh], clear=GAP))
    a_bvh = bvh_of(pa)
    # pillow B: propped against the headboard, sliding down onto the back of pillow A
    MB = (Matrix.Translation(ue(-74, 2.5, 88)) @ Matrix.Rotation(math.radians(3), 4, "Z") @
          Matrix.Rotation(math.radians(24), 4, "Y"))
    # the propped pillow's ear by the head rail used to fold down into the mattress/headboard gap as a
    # sharp spike: stiffer bending on its piping + ears (max 20 instead of 4) and 8 relax passes
    pb = sim_pillow("pillowB", MB, [bed_col, pa], 4.7, 90, 3.5, relax_iters=8, bend_max=20.0)
    # the propped pillow folds over pillow A and the head end, so its 11 x 8 cloth grid showed long flat
    # facets and a hard ridge along the crease: subdivide once, Taubin-smooth the whole shell, then
    # decimate to PILLOW_B_TRIS (the quadric collapse keeps the crease and ears, drops flat areas)
    sub = pb.modifiers.new("subd", "SUBSURF")
    sub.levels = sub.render_levels = 1
    sub.uv_smooth = "PRESERVE_CORNERS"
    pb = bake(pb, None, "pillowB")
    taubin(pb, {v.index: 1.0 for v in pb.data.vertices}, iters=8)
    pb = decimate(pb, PILLOW_B_TRIS)
    print("  pillowB subdivided + smoothed + decimated:", tri_count(pb), "tris")
    for c in (0.35, 0.6, 0.9, 1.3):
        if crossings(pa, pb) == 0:
            break
        push_mesh(pb, Field([a_bvh, bed_bvh], clear=c * CM))
    push_mesh(pb, Field([bed_bvh], clear=GAP))
    b_bvh = bvh_of(pb)
    duv_field = Field([bed_bvh, a_bvh, b_bvh], clear=DUV_CLEAR * CM)
    mid, flap_idx = build_duvet(bed_col, [pa, pb], duv_field)
    budget = LINEN_BUDGET - tri_count(pa) - tri_count(pb) - BLANKET_TRIS
    # clean high-res thickened copy of the duvet: the blanket is simulated against this
    hi = link(bpy.data.objects.new("COL_duvet_hi", mid.data.copy()))
    orient_up(hi)
    sol = hi.modifiers.new("sol", "SOLIDIFY")
    sol.thickness = DUV_T * CM
    sol.offset = 0.0
    sol.use_quality_normals = True
    hi = bake(hi, None, "COL_duvet_hi")
    dec = finish_duvet(mid, budget, duv_field)
    duvet = None
    for c in (0.0, 0.3, 0.6, 1.0):
        if c:
            print("  duvet clean-up push at", c, "cm:",
                  push_mesh(dec, Field([bed_bvh, a_bvh, b_bvh], clear=(DUV_H + c) * CM)))
        if duvet:
            bpy.data.objects.remove(duvet, do_unlink=True)
        duvet = thicken(dec, DUV_H, HEM_R, "duvet", round_edge=lambda co: co.x < FLAP_HEM_X * CM)
        n = crossings(duvet, bed) + crossings(duvet, pa) + crossings(duvet, pb)
        if n == 0:
            break
    bpy.data.objects.remove(dec, do_unlink=True)
    for ob in (bed_col, pa, pb):
        clear_mods(ob)
    blanket = build_blanket(hi, bed_bvh, bed_col, [duvet, bed, pa, pb])
    bpy.data.objects.remove(hi, do_unlink=True)
    wh = []
    crossings(blanket, duvet, wh)
    print("  blanket-duvet crossings at (cm):", wh[:12])
    bpy.data.objects.remove(bed_col, do_unlink=True)
    parts = {"pillowA": pa, "pillowB": pb, "duvet": duvet, "blanket": blanket}
    stats = {k: tri_count(v) for k, v in parts.items()}
    for k, v in parts.items():
        zs = [w.co.z / CM for w in v.data.vertices]
        print("  part", k, "z range", round(min(zs), 1), round(max(zs), 1))
    checks = {
        "pillowA-pillowB": crossings(pa, pb),
        "duvet-pillowA": crossings(duvet, pa),
        "duvet-pillowB": crossings(duvet, pb),
        "blanket-duvet": crossings(blanket, duvet),
        "blanket-pillows": crossings(blanket, pa) + crossings(blanket, pb),
        "bed-pillowA": crossings(bed, pa),
        "bed-pillowB": crossings(bed, pb),
        "bed-duvet": crossings(bed, duvet),
        "bed-blanket": crossings(bed, blanket),
    }
    for nm, o in (("duvet", duvet), ("blanket", blanket), ("pillowA", pa), ("pillowB", pb)):
        wh = []
        crossings(o, bed, wh)
        if wh:
            print(f"  WARNING bed-{nm} crossings at (cm, local):", sorted(set(wh))[:40])
    for ob, ang in ((pa, 70), (pb, 60), (duvet, 70), (blanket, 89)):
        smooth(ob, ang)
    linen = join("SM_BedLinen", [pa, pb, duvet, blanket])
    return linen, stats, checks


# =============================================================== UVs, export, previews
def box_uv(ob):
    me = ob.data
    uv0 = me.uv_layers.new(name="UVMap")
    bm = bmesh.new()
    bm.from_mesh(me)
    layer = bm.loops.layers.uv[uv0.name]
    for f in bm.faces:
        n = f.normal
        ax = max(range(3), key=lambda i: abs(n[i]))
        for lp in f.loops:
            co = lp.vert.co
            lp[layer].uv = (co.y, co.z) if ax == 0 else (co.x, co.z) if ax == 1 else (co.x, co.y)
    bm.to_mesh(me)
    bm.free()


def lightmap_uv(ob, margin=0.02, boost=1.0, big_m2=0.01):
    """UV1 'Lightmap': Smart UV Project + Pack Islands (2 % margin). boost > 1 scales up the large
    islands (> big_m2 of surface, e.g. mattress and boards) before packing, so the big flat surfaces
    that actually catch baked light get the texels instead of the many small tube/castor islands."""
    me = ob.data
    if "Lightmap" in me.uv_layers:
        me.uv_layers.remove(me.uv_layers["Lightmap"])
    uv1 = me.uv_layers.new(name="Lightmap")
    me.uv_layers.active = uv1
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=margin, scale_to_bounds=False)
    bpy.ops.object.mode_set(mode="OBJECT")
    if boost != 1.0:
        bm = bmesh.new()
        bm.from_mesh(me)
        uvl = bm.loops.layers.uv["Lightmap"]
        par = {}

        def find(k):
            while par.setdefault(k, k) != k:
                par[k] = par[par[k]]
                k = par[k]
            return k
        key = {}
        for f in bm.faces:
            ks = [(lp.vert.index, round(lp[uvl].uv.x, 6), round(lp[uvl].uv.y, 6)) for lp in f.loops]
            key[f] = ks[0]
            for k in ks[1:]:
                par[find(k)] = find(ks[0])
        # loops sharing a vertex and a uv position are one node, so faces join into uv islands
        groups = {}
        for f in bm.faces:
            groups.setdefault(find(key[f]), []).append(f)
        nb = 0
        for faces in groups.values():
            if sum(f.calc_area() for f in faces) < big_m2:
                continue
            nb += 1
            ls = [lp for f in faces for lp in f.loops]
            c = sum((lp[uvl].uv for lp in ls), Vector((0.0, 0.0))) / len(ls)
            for lp in ls:
                lp[uvl].uv = c + (lp[uvl].uv - c) * boost
        bm.to_mesh(me)
        bm.free()
        print(f"  lightmap {ob.name}: {len(groups)} islands, {nb} large islands boosted x{boost}")
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.pack_islands(margin=margin, rotate=True, shape_method="CONCAVE")
    bpy.ops.object.mode_set(mode="OBJECT")
    me.uv_layers.active = me.uv_layers["UVMap"]
    me.uv_layers["UVMap"].active_render = True


def export(ob):
    os.makedirs(OUT, exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.export_scene.fbx(filepath=os.path.join(OUT, f"{ob.name}.fbx"), use_selection=True,
                             apply_unit_scale=True, apply_scale_options="FBX_SCALE_UNITS", axis_forward="-Y",
                             axis_up="Z", mesh_smooth_type="FACE", add_leaf_bones=False)


def setup_render():
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.render.resolution_x, sc.render.resolution_y = 900, 700
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = False
    sc.view_settings.view_transform = "Standard"
    sh = sc.display.shading
    sh.light = "STUDIO"
    sh.color_type = "MATERIAL"
    sh.show_cavity = True
    sh.cavity_type = "BOTH"
    sh.show_object_outline = False
    sh.show_shadows = True
    sh.shadow_intensity = 0.35
    sc.display.render_aa = "8"
    w = bpy.data.worlds.new("white")
    w.color = (1, 1, 1)
    sc.world = w
    cam = link(bpy.data.objects.new("PreviewCam", bpy.data.cameras.new("PreviewCam")))
    cam.data.lens = 50
    sc.camera = cam
    return cam


def preview(objs, path, cam, direction=(1.1, -0.85, 0.75), target=None, fit=None, margin=0.9, radius=None):
    """3/4 preview render. radius (cm): close-up framing a sphere of that radius around target."""
    sc = bpy.context.scene
    for o in sc.objects:
        o.hide_render = o not in objs and o is not cam
    fit = fit or objs
    pts = [o.matrix_world @ v.co for o in fit for v in o.data.vertices]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    tgt = target or (lo + hi) / 2
    d = Vector(direction).normalized()
    rot = (-d).to_track_quat("-Z", "Y")
    right, up, fwd = rot @ Vector((1, 0, 0)), rot @ Vector((0, 1, 0)), -d
    tx = math.tan(cam.data.angle / 2)
    ty = tx * sc.render.resolution_y / sc.render.resolution_x
    corners = [Vector((x, y, z)) for x in (lo.x, hi.x) for y in (lo.y, hi.y) for z in (lo.z, hi.z)]
    D = 0.1
    if radius is not None:
        corners = []
        D = radius * CM / ty
    for c in corners:
        q = c - tgt
        D = max(D, abs(q.dot(right)) / (margin * tx) - q.dot(fwd), abs(q.dot(up)) / (margin * ty) - q.dot(fwd))
    cam.location = tgt + d * D
    cam.rotation_euler = rot.to_euler()
    cam.data.clip_start = 0.01
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)


def world_bounds(ob):
    xs, ys = [], []
    for v in ob.data.vertices:
        xu, yu = v.co.x / CM, -v.co.y / CM
        xs.append(177.5 + yu)
        ys.append(339.0 - xu)
    zs = [v.co.z / CM for v in ob.data.vertices]
    return (min(xs), max(xs)), (min(ys), max(ys)), (min(zs), max(zs))


def main():
    t0 = time.time()
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    bed, mattress_col = build_bed()
    if os.environ.get("BED_ONLY"):             # quick iteration on the frame: count + preview, no export
        cam = setup_render()
        os.makedirs(CHECK or PREV, exist_ok=True)
        preview([bed], os.path.join(CHECK or PREV, "bed_only.png"), cam)
        preview([bed], os.path.join(CHECK or PREV, "bed_only_rail.png"), cam, direction=(0.5, -1.0, 0.35),
                target=ue(-80, 50, 60), radius=25)
        preview([bed], os.path.join(CHECK or PREV, "bed_only_castor.png"), cam, direction=(0.8, -1.0, 0.2),
                target=ue(86, -36, 9), radius=12)
        import collections
        me = bed.data
        me.calc_loop_triangles()
        c = collections.Counter(me.materials[me.polygons[t.polygon_index].material_index].name
                                for t in me.loop_triangles)
        print("RESULT bed only", tri_count(bed), dict(c))
        return
    linen, stats, checks = build_linen(bed, mattress_col)
    bpy.data.objects.remove(mattress_col, do_unlink=True)
    checks["bed-linen"] = crossings(bed, linen)
    for ob in (bed, linen):
        if not ob.data.uv_layers:
            box_uv(ob)
        lightmap_uv(ob, boost=4.0 if ob is bed else 1.0)
        export(ob)
    cam = setup_render()
    os.makedirs(PREV, exist_ok=True)
    preview([bed], os.path.join(PREV, "SM_Bed.png"), cam)
    preview([linen], os.path.join(PREV, "SM_BedLinen.png"), cam)
    if CHECK:
        os.makedirs(CHECK, exist_ok=True)
        preview([bed, linen], os.path.join(CHECK, "combined.png"), cam)
        preview([bed, linen], os.path.join(CHECK, "pillows.png"), cam, direction=(0.9, -0.7, 0.55),
                target=ue(-66, 0, 68), radius=45)
        preview([bed, linen], os.path.join(CHECK, "side.png"), cam, direction=(0.0, -1.0, 0.12))
        preview([bed, linen], os.path.join(CHECK, "foot.png"), cam, direction=(1.0, 0.25, 0.25))
        preview([bed, linen], os.path.join(CHECK, "head.png"), cam, direction=(-1.0, -0.6, 0.6))
        preview([bed, linen], os.path.join(CHECK, "fold.png"), cam, direction=(-0.5, -1.0, 0.8),
                target=ue(-25, 30, 58), radius=30)
        preview([bed, linen], os.path.join(CHECK, "foot_corner.png"), cam, direction=(0.45, -1.0, 0.3),
                target=ue(86, 50, 42), radius=30)
        preview([bed, linen], os.path.join(CHECK, "front.png"), cam, direction=(1.0, 0.0, 0.18))
        preview([linen], os.path.join(CHECK, "top.png"), cam, direction=(0.0, 0.0001, 1.0))
        preview([bed, linen], os.path.join(CHECK, "corner_pa.png"), cam, direction=(0.6, -1.0, 0.6),
                target=ue(-38, 36, 63), radius=14)
        preview([bed, linen], os.path.join(CHECK, "corner_pb.png"), cam, direction=(0.8, -1.0, 0.5),
                target=ue(-92, 35, 93), radius=14)
        preview([bed, linen], os.path.join(CHECK, "corner_pb_low.png"), cam, direction=(0.8, -1.0, 0.5),
                target=ue(-55, 35, 70), radius=14)
        preview([bed, linen], os.path.join(CHECK, "blanket.png"), cam, direction=(0.25, -1.0, 0.75),
                target=ue(70, 30, 56), radius=32)
        preview([bed], os.path.join(CHECK, "castor.png"), cam, direction=(0.8, -1.0, 0.2),
                target=ue(86, -36, 9), radius=12)
        try:
            if os.environ.get("CHECK_BLEND"):
                bpy.ops.wm.save_as_mainfile(filepath=os.environ["CHECK_BLEND"])
        except Exception as ex:
            print("  could not save check blend:", ex)
    print("RESULT tris SM_Bed", tri_count(bed), "SM_BedLinen", tri_count(linen), stats)
    print("RESULT crossings", checks)
    print("RESULT mats", [m.name for m in bed.data.materials], [m.name for m in linen.data.materials])
    print("RESULT uvs", [u.name for u in bed.data.uv_layers], [u.name for u in linen.data.uv_layers])
    print("RESULT world bounds bed", world_bounds(bed), "linen", world_bounds(linen))
    print(f"RESULT done in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
