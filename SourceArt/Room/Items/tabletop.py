"""Blender (headless): round pedestal table + tabletop / shelf / bedside props for Maria's room.

Run (all pieces, saves tabletop.blend):
  "C:\\Program Files\\Blender Foundation\\Blender 5.0\\blender.exe" -b --factory-startup --python tabletop.py
Run a subset (no .blend save):
  ... --python tabletop.py -- SM_Vase SM_Jug

Follows SourceArt/Room/CONVENTIONS.md:
  * Modelled in Unreal centimetres (Blender axes), scaled 0.01 to metres in join(). Front = local +X.
  * Pivot at the bottom centre with the lowest point exactly on the pivot (the room tools add the
    0.2 cm rest gap). SM_Glass and SM_Hairbrush: pivot at the bounding-box centre.
  * UV0 'UVMap' = 1 m box projection (clock screen gets its own 0..1 map); UV1 'Lightmap' = smart
    project + pack, 2 % margin.
  * Real shapes: lathe (Screw modifier) for turned parts, curve sweeps for handles / stems / cords /
    coils, lofted rings for the brush head, thin lens-shaped petals and leaves.
  * No interpenetration inside a piece: parts that are physically one object (handle + jug, clip
    parts, figurine) are fused with an EXACT boolean union; parts that merely rest on each other
    (sheets on the board, bristles on the cushion, button in its bezel, stems in the vase) keep a
    0.02 cm air gap. Rosary beads and links share vertices (one threaded island).
Exports SourceArt/Room/Export/SM_<Name>.fbx and Previews/SM_<Name>.png (Workbench, studio light).
"""
import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

ROOM = r"D:\Unreal-Projects\WattleviewGrove-ue58\SourceArt\Room"
EXPORT = os.path.join(ROOM, "Export")
PREVIEW = os.path.join(ROOM, "Previews")
AIR = 0.02   # cm air gap between separate parts inside one piece

MATS = {
    "M_Timber": (0.66, 0.50, 0.33),
    "M_TimberDark": (0.36, 0.22, 0.12),
    "M_Metal": (0.62, 0.63, 0.65),
    "M_PlasticWhite": (0.90, 0.90, 0.88),
    "M_PlasticBlack": (0.05, 0.05, 0.055),
    "M_Screen": (0.06, 0.09, 0.14),
    "M_Ceramic": (0.90, 0.88, 0.84),
    "M_Glass": (0.70, 0.82, 0.88),
    "M_Plant": (0.24, 0.45, 0.17),
    "M_PlantDark": (0.30, 0.24, 0.08),
    "M_Flower": (0.98, 0.80, 0.12),
    "M_FlowerRed": (0.80, 0.08, 0.07),
    "M_Paper": (0.96, 0.95, 0.92),
    "M_Gold": (0.83, 0.66, 0.28),
    "M_Rubber": (0.10, 0.10, 0.10),
}


def mat(name):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.diffuse_color = (*MATS[name], 1.0)
    m.roughness = 0.4
    return m


def link(name, me):
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def bake(ob):
    """Apply all modifiers (or convert a curve) into a plain mesh object."""
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    name = ob.name
    mw = ob.matrix_world.copy()
    data = ob.data
    bpy.data.objects.remove(ob, do_unlink=True)
    if isinstance(data, bpy.types.Curve) and data.users == 0:
        bpy.data.curves.remove(data)
    new = link(name, me)
    new.matrix_world = mw
    return new


def set_mat(ob, m):
    ob.data.materials.clear()
    ob.data.materials.append(mat(m))
    return ob


def smooth(ob, angle=40.0, recalc=True):
    """Smooth shading with sharp edges above `angle`; optionally recalc normals outward."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
    if recalc:
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    lim = math.radians(angle)
    for f in bm.faces:
        f.smooth = True
    for e in bm.edges:
        if len(e.link_faces) != 2 or e.calc_face_angle(0.0) > lim:
            e.smooth = False
    bm.to_mesh(ob.data)
    bm.free()
    return ob


def xform(ob, m):
    ob.data.transform(m)
    return ob


def move(ob, v):
    return xform(ob, Matrix.Translation(Vector(v)))


def union(base, others, angle=40.0, self_check=False, solver="EXACT"):
    """Fuse closed meshes into `base` with an EXACT boolean union (materials transferred).
    self_check=True runs the solver in self-intersection mode, which is more robust when the inputs
    carry boolean-cut slivers (the Madonna's carved mantle)."""
    for o in others:
        mod = base.modifiers.new("u", "BOOLEAN")
        mod.operation = "UNION"
        mod.solver = solver
        if solver == "EXACT":
            mod.use_self = self_check
        mod.operand_type = "OBJECT"
        mod.object = o
        mod.material_mode = "TRANSFER"
        base = bake(base)
        bpy.data.objects.remove(o, do_unlink=True)
    return smooth(base, angle)


PERM_ZXY = Matrix(((0, 0, 1, 0), (1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 0, 1)))   # lathe axis Z -> X
SWAP_YZ = Matrix(((1, 0, 0, 0), (0, 0, 1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))    # (u, v, w) -> (u, w, v)


# ------------------------------------------------------------------ primitives
def lathe(profile, seg, m, angle=360.0, start=0.0, name="lathe", angle_smooth=40.0, recalc=True):
    """Revolve a 2D (r, z) profile around Z with the Screw modifier, then apply it."""
    a0 = math.radians(start)
    verts = [(r * math.cos(a0), r * math.sin(a0), z) for r, z in profile]
    edges = [(i, i + 1) for i in range(len(verts) - 1)]
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, edges, [])
    ob = link(name, me)
    mod = ob.modifiers.new("screw", "SCREW")
    mod.axis = "Z"
    mod.angle = math.radians(angle)
    mod.steps = seg
    mod.render_steps = seg
    mod.screw_offset = 0.0
    mod.use_merge_vertices = True
    mod.merge_threshold = 1e-3
    mod.use_normal_calculate = True
    ob = bake(ob)
    set_mat(ob, m)
    return smooth(ob, angle_smooth, recalc)


def sweep(points, radius, m, res=4, bevel_res=1, radii=None, cyclic=False, bevel_obj=None,
          caps=True, kind="BEZIER", name="sweep", angle_smooth=60.0):
    """Sweep a round (or bevel_obj) section along a curve through `points` (cm), convert to mesh."""
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.resolution_u = res
    cu.twist_mode = "MINIMUM"
    if bevel_obj is not None:
        cu.bevel_mode = "OBJECT"
        cu.bevel_object = bevel_obj
    else:
        cu.bevel_depth = radius
        cu.bevel_resolution = bevel_res
    cu.use_fill_caps = caps
    sp = cu.splines.new(kind)
    if kind == "BEZIER":
        sp.bezier_points.add(len(points) - 1)
        for i, p in enumerate(points):
            bp = sp.bezier_points[i]
            bp.co = Vector(p)
            bp.handle_left_type = bp.handle_right_type = "AUTO"
            bp.radius = radii[i] if radii else 1.0
    else:
        sp.points.add(len(points) - 1)
        for i, p in enumerate(points):
            sp.points[i].co = (*p, 1.0)
            sp.points[i].radius = radii[i] if radii else 1.0
    sp.use_cyclic_u = cyclic
    ob = link(name, cu)
    ob = bake(ob)
    set_mat(ob, m)
    return smooth(ob, angle_smooth)


def catmull(pts, sub):
    """Catmull-Rom densify an open polyline of Vectors (end points kept). `sub` = steps per span, or a
    list with one step count per span (fewer steps where the curve is nearly straight)."""
    out = []
    P = [pts[0] + (pts[0] - pts[1])] + list(pts) + [pts[-1] + (pts[-1] - pts[-2])]
    for i in range(1, len(P) - 2):
        s = sub[i - 1] if isinstance(sub, (list, tuple)) else sub
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        for j in range(s):
            t = j / s
            t2, t3 = t * t, t * t * t
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    out.append(pts[-1])
    return out


def section_curve(pts2d, name="section"):
    """Closed poly curve in XY used as a bevel object (cm)."""
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "2D"
    sp = cu.splines.new("POLY")
    sp.points.add(len(pts2d) - 1)
    for i, (x, y) in enumerate(pts2d):
        sp.points[i].co = (x, y, 0, 1)
    sp.use_cyclic_u = True
    return link(name, cu)


def ngon(n, rx, ry=None, rot=0.0):
    ry = rx if ry is None else ry
    return [(rx * math.cos(rot + 2 * math.pi * i / n), ry * math.sin(rot + 2 * math.pi * i / n)) for i in range(n)]


def rounded_rect(w, h, r, n=4):
    pts = []
    for cx, cy, a0 in ((w / 2 - r, h / 2 - r, 0), (-w / 2 + r, h / 2 - r, 90),
                       (-w / 2 + r, -h / 2 + r, 180), (w / 2 - r, -h / 2 + r, 270)):
        for i in range(n + 1):
            a = math.radians(a0 + 90 * i / n)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def superellipse(a, b, n_exp, count):
    pts = []
    for i in range(count):
        t = 2 * math.pi * i / count
        c, s = math.cos(t), math.sin(t)
        pts.append((a * math.copysign(abs(c) ** (2 / n_exp), c), b * math.copysign(abs(s) ** (2 / n_exp), s)))
    return pts


def slab(outline, z0, z1, m, bevel=0.0, seg=2, name="slab", angle_smooth=40.0):
    """Extrude a 2D outline (cm, XY) from z0 to z1 and bevel its rim edges."""
    bm = bmesh.new()
    vs = [bm.verts.new((u, v, z0)) for u, v in outline]
    f = bm.faces.new(vs)
    ext = bmesh.ops.extrude_face_region(bm, geom=[f])
    nv = [g for g in ext["geom"] if isinstance(g, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, verts=nv, vec=(0, 0, z1 - z0))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    if bevel > 0:
        caps = [fc for fc in bm.faces if len(fc.verts) > 4]
        rim = {e for fc in caps for e in fc.edges}
        bmesh.ops.bevel(bm, geom=list(rim), offset=bevel, segments=seg, profile=0.5,
                        affect="EDGES", clamp_overlap=True)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = link(name, me)
    set_mat(ob, m)
    return smooth(ob, angle_smooth)


def ball(c, r, m, u=8, v=5, scale=(1, 1, 1), name="ball", angle_smooth=80.0):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=u, v_segments=v, radius=r)
    for vt in bm.verts:
        vt.co = Vector((vt.co.x * scale[0], vt.co.y * scale[1], vt.co.z * scale[2])) + Vector(c)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = link(name, me)
    set_mat(ob, m)
    return smooth(ob, angle_smooth)


def mesh(verts, faces, mats, face_mats=None, name="mesh", angle_smooth=40.0, recalc=True):
    """Mesh from raw data; `mats` is a slot-name list, `face_mats` per-face slot indices."""
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], [tuple(f) for f in faces])
    me.validate()
    for mname in mats:
        me.materials.append(mat(mname))
    if face_mats:
        for p, k in zip(me.polygons, face_mats):
            p.material_index = k
    ob = link(name, me)
    return smooth(ob, angle_smooth, recalc)


def join(name, parts):
    """Join parts, scale cm -> m, name object and data."""
    bpy.ops.object.select_all(action="DESELECT")
    for p in parts:
        p.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    if len(parts) > 1:
        bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    ob.name = name
    ob.data.name = name
    ob.data.transform(Matrix.Scale(0.01, 4))
    ob.matrix_world = Matrix.Identity(4)
    return ob


def bounds(ob):
    xs = [v.co for v in ob.data.vertices]
    lo = Vector((min(p.x for p in xs), min(p.y for p in xs), min(p.z for p in xs)))
    hi = Vector((max(p.x for p in xs), max(p.y for p in xs), max(p.z for p in xs)))
    return lo, hi


def pivot_bottom_centre(ob):
    lo, hi = bounds(ob)
    ob.data.transform(Matrix.Translation((-(lo.x + hi.x) / 2, -(lo.y + hi.y) / 2, -lo.z)))
    return ob


def pivot_centre(ob):
    lo, hi = bounds(ob)
    ob.data.transform(Matrix.Translation(-(lo + hi) / 2))
    return ob


def resample(dense, k, bend=1.5):
    """Pick k indices along a dense polyline, spaced evenly in (arc length + bend * turning), ends kept,
    so rows cluster where the silhouette curves and thin out where it is straight."""
    n = len(dense)
    L = sum((dense[i + 1] - dense[i]).length for i in range(n - 1))
    turn = [0.0] * n
    for i in range(1, n - 1):
        a, b = dense[i] - dense[i - 1], dense[i + 1] - dense[i]
        if a.length > 1e-9 and b.length > 1e-9:
            turn[i] = a.angle(b)
    cum = [0.0]
    for i in range(1, n):
        cum.append(cum[-1] + (dense[i] - dense[i - 1]).length / L + bend * (turn[i - 1] + turn[i]) / (2 * math.pi))
    out = []
    for j in range(k):
        target = cum[-1] * j / (k - 1)
        i = min(range(n), key=lambda q: abs(cum[q] - target))
        if out and i <= out[-1]:
            i = out[-1] + 1
        out.append(i)
    out[-1] = n - 1
    return out


def lathe_rows(rows, m, name="lathe", angle_smooth=40.0):
    """Lathe from (r, z, segments) rows; neighbouring rows may differ in segment count (zipped with
    triangles), so hidden inner walls can use half the segments of the outer silhouette. r = 0 is a pole."""
    V, F, rings = [], [], []
    for r, z, n in rows:
        if r < 1e-6:
            rings.append([len(V)])
            V.append((0.0, 0.0, z))
        else:
            rings.append(list(range(len(V), len(V) + n)))
            V += [(r * math.cos(2 * math.pi * i / n), r * math.sin(2 * math.pi * i / n), z) for i in range(n)]
    for A, B in zip(rings, rings[1:]):
        na, nb = len(A), len(B)
        if na == 1:
            F += [(A[0], B[(j + 1) % nb], B[j]) for j in range(nb)]
        elif nb == 1:
            F += [(A[j], A[(j + 1) % na], B[0]) for j in range(na)]
        elif na == nb:
            F += [(A[j], A[(j + 1) % na], B[(j + 1) % nb], B[j]) for j in range(na)]
        else:
            i = j = 0
            while i < na or j < nb:
                if j >= nb or (i < na and (i + 1) / na <= (j + 1) / nb):
                    F.append((A[i % na], A[(i + 1) % na], B[j % nb]))
                    i += 1
                else:
                    F.append((A[i % na], B[(j + 1) % nb], B[j % nb]))
                    j += 1
    return mesh(V, F, [m], name=name, angle_smooth=angle_smooth)


def triangulate(ob):
    """Triangulate in place (BEAUTY), so later booleans and the exporter see the same triangles."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.triangulate(bm, faces=bm.faces, quad_method="BEAUTY", ngon_method="BEAUTY")
    bm.to_mesh(ob.data)
    bm.free()
    return ob


def heal_cracks(bm, tol=0.02):
    """Close boolean T-junction cracks: a boundary vertex lying on another boundary edge splits that
    edge, and the two coincident vertices are welded. Repeats until no crack is left."""
    from mathutils.geometry import intersect_point_line
    for _ in range(20):
        fixed = False
        bverts = {v for e in bm.edges if e.is_boundary for v in e.verts}
        for e in [e for e in bm.edges if e.is_boundary]:
            if not e.is_valid:
                continue
            a, b = e.verts
            for v in bverts:
                if not v.is_valid or v in (a, b):
                    continue
                pt, fac = intersect_point_line(v.co, a.co, b.co)
                if 0.0 < fac < 1.0 and (pt - v.co).length < tol:
                    ne, nv = bmesh.utils.edge_split(e, a, fac)
                    bmesh.ops.pointmerge(bm, verts=[nv, v], merge_co=v.co)
                    fixed = True
                    break
            if fixed:
                break
        if not fixed:
            return
    return


def clean_shading(ob, sharp=35.0):
    """Tidy boolean shading: mark the cut / opening edges sharp (> `sharp` deg) and bake area-weighted
    custom normals (keep sharp) so the long boolean slivers no longer drag the shading into dark
    patches. (A 0.5 deg limited dissolve was tried here: it left non-manifold edges, so it is not used.)
    (Triangulating the boolean n-gons here was tried: it produced non-manifold slivers, so it is not done.)"""
    smooth(ob, sharp)
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.02)     # boolean leaves near-twin verts (< 0.2 mm)
    bmesh.ops.dissolve_degenerate(bm, dist=0.002, edges=bm.edges)
    heal_cracks(bm)
    bmesh.ops.connect_verts_concave(bm, faces=[f for f in bm.faces if len(f.verts) > 3])
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 3], quad_method="BEAUTY",
                          ngon_method="BEAUTY")
    bm.to_mesh(ob.data)
    bm.free()
    wn = ob.modifiers.new("wn", "WEIGHTED_NORMAL")
    wn.mode = "FACE_AREA"
    wn.keep_sharp = True
    wn.use_face_influence = True
    return bake(ob)


# ------------------------------------------------------------------ pieces
def round_table():
    """95 cm pedestal table: lathed top with a soft round-over, turned column, domed round base."""
    T, th, R, ro = 75.0, 2.6, 47.5, 1.8
    top = [(0.0, T), (R - ro, T)]
    for i in range(1, 4):
        a = math.radians(90 - 90 * i / 4)
        top.append((R - ro + ro * math.cos(a), T - ro + ro * math.sin(a)))
    top += [(R, T - ro), (R, T - th + 0.35), (R - 0.35, T - th), (0.0, T - th)]
    p_top = lathe(top, 48, "M_Timber", name="top", angle_smooth=30)

    hb = 9.6                                                  # base plateau height
    base = [(0.0, 0.0), (26.3, 0.0), (27.0, 0.6), (27.0, 1.5), (26.0, 2.5), (20.5, 4.4),
            (14.5, 6.9), (10.6, 9.0), (9.2, hb), (0.0, hb)]
    p_base = lathe(base, 32, "M_Timber", name="base", angle_smooth=35)

    zt = T - th - AIR                                         # mounting disc just under the top
    zb = hb + AIR                                             # collar just above the base
    col = [(0.0, zt), (8.5, zt), (8.5, zt - 1.1), (4.6, zt - 2.0), (4.1, zt - 3.4), (4.6, 56.0),
           (6.0, 42.0), (6.9, 31.0), (6.4, 24.5), (4.9, 21.8), (5.8, 20.3), (5.0, 18.6),
           (5.6, 15.5), (8.0, 11.2), (8.8, zb + 0.5), (8.8, zb), (0.0, zb)]
    p_col = lathe(col, 24, "M_Timber", name="column", angle_smooth=35)
    return join("SM_RoundTable", [p_top, p_col, p_base])


def flower_head(centre, axis, R=1.9, n=12, rot=0.0, rng=None, cup=0.35):
    """Marguerite head, one closed mesh (72 tris): n blunt strap petals (two tip verts each, a notch
    vert pulled in to 0.45 R between petals so they read separate), tips cupped up with a little
    random lift / angle jitter, an olive-brown domed eye (M_PlantDark) and a shallow yellow underside
    cone that closes every petal down to a calyx point where the stem arrives."""
    rng = rng or random.Random(1)
    q = axis.normalized().to_track_quat("Z", "Y").to_matrix().to_4x4()
    M = Matrix.Translation(centre) @ q @ Matrix.Rotation(rot, 4, "Z")
    pitch = 2 * math.pi / n
    hw = 0.33 * pitch
    V, F, FM = [], [], []
    T1, T2, N = [], [], []
    for i in range(n):
        phi = pitch * i + rng.uniform(-0.12, 0.12) * pitch
        rr = R * rng.uniform(0.9, 1.06)
        z = cup + rng.uniform(-0.12, 0.12)
        T1.append(len(V))
        V.append((rr * math.cos(phi - hw), rr * math.sin(phi - hw), z))
        T2.append(len(V))
        V.append((rr * math.cos(phi + hw), rr * math.sin(phi + hw), z))
        N.append(len(V))
        a = phi + pitch / 2
        V.append((0.45 * R * math.cos(a), 0.45 * R * math.sin(a), 0.12))
    apex, bot = len(V), len(V) + 1
    V += [(0, 0, 0.5), (0, 0, -0.42)]
    for i in range(n):
        F.append((N[i - 1], T1[i], T2[i], N[i]))           # petal top
        FM.append(0)
        F += [(bot, T2[i], T1[i]), (bot, T1[i], N[i - 1]), (bot, N[i], T2[i])]   # underside / petal sides
        FM += [0, 0, 0]
        F.append((N[i - 1], N[i], apex))                     # domed eye
        FM.append(1)
    V = [M @ Vector(v) for v in V]
    return mesh(V, F, ["M_Flower", "M_PlantDark"], FM, name="head", angle_smooth=55)


def flower_bud(base, axis):
    """Closed bud: green calyx cup rising to a yellow tip (20 tris)."""
    q = axis.normalized().to_track_quat("Z", "Y").to_matrix().to_4x4()
    M = Matrix.Translation(base) @ q
    V = [(0, 0, 0)]
    for r, z in ((0.42, 0.45), (0.34, 0.95)):
        V += [(r * math.cos(2 * math.pi * j / 5), r * math.sin(2 * math.pi * j / 5), z) for j in range(5)]
    V.append((0, 0, 1.4))
    F, FM = [], []
    for j in range(5):
        j2 = (j + 1) % 5
        F.append((0, 1 + j2, 1 + j))
        F += [(1 + j, 1 + j2, 6 + j2), (1 + j, 6 + j2, 6 + j)]
        F.append((6 + j, 6 + j2, 11))
        FM += [0, 0, 1, 1]
    V = [M @ Vector(v) for v in V]
    return mesh(V, F, ["M_Plant", "M_Flower"], FM, name="bud", angle_smooth=70)


def leaf(base, out_dir, length=6.2, width=0.75, elev=25.0, droop=1.7, fold=0.25):
    """Lens-shaped leaf with a raised midrib, folded along the rib, drooping towards the tip."""
    rho = Vector((out_dir.x, out_dir.y, 0)).normalized()
    side = Vector((-rho.y, rho.x, 0))
    e = math.radians(elev)
    d = rho * math.cos(e) + Vector((0, 0, math.sin(e)))
    nrm = d.cross(side).normalized()
    if nrm.z < 0:
        nrm = -nrm
    us = [0.25, 0.5, 0.78]

    def c(u):
        return base + d * length * u + Vector((0, 0, -droop * u * u))

    def w(u):
        return width * math.sin(math.pi * u) ** 0.8

    L = [c(u) + side * w(u) - nrm * fold * w(u) for u in us]
    Rr = [c(u) - side * w(u) - nrm * fold * w(u) for u in us]
    Mt = [c(u) + nrm * 0.07 for u in us]
    Mb = [c(u) - nrm * 0.07 for u in us]
    V = [base] + L + Rr + [c(1.0)] + Mt + Mb
    iB, iL, iR, iT = 0, 1, 4, 7
    F = []
    for mid, flip in ((8, False), (11, True)):
        fs = [(iB, iL, mid), (iB, mid, iR)]
        for k in range(2):
            fs += [(iL + k, iL + k + 1, mid + k + 1), (iL + k, mid + k + 1, mid + k),
                   (iR + k, mid + k, mid + k + 1), (iR + k, mid + k + 1, iR + k + 1)]
        fs += [(iL + 2, iT, mid + 2), (mid + 2, iT, iR + 2)]
        F += [tuple(reversed(f)) if flip else f for f in fs]
    return mesh(V, F, ["M_Plant"], name="leaf", angle_smooth=70)


VASE_INNER = [(0.0, 12.3), (2.1, 12.8), (2.5, 14.8), (3.05, 16.8), (3.2, 17.05)]   # (r, z) cavity wall


def vase_inner_r(z):
    for (r0, z0), (r1, z1) in zip(VASE_INNER, VASE_INNER[1:]):
        if z0 <= z <= z1:
            return r0 + (r1 - r0) * (z - z0) / (z1 - z0)
    return None


def vase():
    """Ceramic baluster vase (18-segment lathe, 12 curvature-weighted outer rows, a real throat about
    5 cm deep) with five yellow marguerites and a bud dropped in irregularly: stems lean at different
    angles, two rest against the rim side, heads at 22-31 cm tipped 5-50 degrees, two leaves."""
    ctrl = [Vector((3.5, 0.0, 0)), Vector((5.3, 3.6, 0)), Vector((5.4, 8.2, 0)), Vector((3.6, 12.8, 0)),
            Vector((2.9, 15.0, 0)), Vector((3.45, 16.8, 0))]
    dense = catmull(ctrl, 24)
    outer = [(dense[i].x, dense[i].y) for i in resample(dense, 12, bend=3.2)]   # rows follow the curvature
    SEG = 18
    rows = [(0.0, 0.0, 1)] + [(r, z, SEG) for r, z in outer] + [(3.2, 17.05, SEG)]
    inner = VASE_INNER[::-1][1:]                    # (3.05, 16.8) ... (0, 12.3)
    rows += [(inner[0][0], inner[0][1], SEG)] + [(r, z, SEG // 2 if r > 0 else 1) for r, z in inner[1:]]
    parts = [lathe_rows(rows, "M_Ceramic", name="vase", angle_smooth=60)]
    rng = random.Random(11)
    sec = section_curve(ngon(3, 0.16), "stemsec")
    SR = 0.16
    # (azimuth, r at floor, r at 15, r at 17.4, head radial, head z, tilt deg, twist deg, bend, R, bud)
    flowers = [(10, 0.9, 1.7, 2.45, 6.4, 23.6, 52, 15, 0.9, 2.0, False),
               (70, 0.7, 1.1, 1.45, 3.4, 29.2, 24, -20, -0.7, 1.85, False),
               (140, 1.0, 1.9, 2.55, 6.6, 22.2, 44, -10, 1.1, 2.05, False),
               (215, 0.75, 1.3, 1.8, 4.6, 26.4, 36, 20, -1.2, 1.95, False),
               (300, 1.1, 1.35, 1.5, 1.9, 30.8, 6, 0, 0.5, 1.75, False),
               (333, 0.45, 0.8, 1.05, 2.7, 27.0, 18, 0, 0.4, 0.0, True)]
    stems = []
    worst = 9.0
    for az, rb, r1, r2, rh, zh, tilt, twist, bend, R, bud in flowers:
        a = math.radians(az)
        rad = Vector((math.cos(a), math.sin(a), 0))
        side = Vector((-rad.y, rad.x, 0))
        t, tw = math.radians(tilt), math.radians(twist)
        axis = Vector((0, 0, math.cos(t))) + (rad * math.cos(tw) + side * math.sin(tw)) * math.sin(t)
        hc = rad * rh + Vector((0, 0, zh))
        if bud:
            p4 = hc
        else:
            p4 = hc - axis * (0.42 + 0.03)                 # calyx point minus an air gap
        zf = VASE_INNER[0][1] + (VASE_INNER[1][1] - VASE_INNER[0][1]) * (rb + 0.25) / VASE_INNER[1][0]
        p0 = rad * rb + Vector((0, 0, zf + 0.06))
        p1 = rad * r1 + side * (0.1 * bend) + Vector((0, 0, 15.0))
        p2 = rad * r2 + side * (0.25 * bend) + Vector((0, 0, 17.4))
        # visible part: quadratic Bezier from the rim to the calyx whose end tangent is the head axis,
        # bowed sideways by `bend`, so the stem arrives straight into the head with a smooth arc
        L = (p4 - p2).length
        c = p4 - axis * (0.5 * L) + side * bend
        bz = [(1 - t) ** 2 * p2 + 2 * t * (1 - t) * c + t * t * p4 for t in (0.25, 0.5, 0.75, 1.0)]
        pts = [p0, p1, p2] + (bz if not bud else bz[1::2])
        for p, q2 in zip(pts, pts[1:]):                    # stems stay >= 0.2 cm off the cavity wall
            for k in range(11):
                c = p.lerp(q2, k / 10)
                ri = vase_inner_r(c.z)
                if ri is not None and c.z > 12.9:
                    worst = min(worst, ri - (math.hypot(c.x, c.y) + SR))
        parts.append(sweep([tuple(p) for p in pts], SR, "M_Plant", res=1, bevel_obj=sec, kind="POLY",
                           name="stem", angle_smooth=70))
        if bud:
            parts.append(flower_bud(hc + axis * AIR, axis))
        else:
            parts.append(flower_head(hc, axis, R=R, rot=rng.uniform(0, 1), rng=rng))
        stems.append((rad, pts))
    print(f"VASE: min stem clearance to the cavity wall = {worst:.3f} cm")
    bpy.data.objects.remove(sec, do_unlink=True)
    for idx, ln, zl in ((0, 5.6, 19.6), (3, 5.0, 20.6)):
        rad, pts = stems[idx]
        for p, q2 in zip(pts, pts[1:]):
            if p.z <= zl <= q2.z:
                s = p.lerp(q2, (zl - p.z) / (q2.z - p.z))
                break
        out = Vector((s.x, s.y, 0)).normalized()
        parts.append(leaf(s + out * (SR + 0.06), out, length=ln))
    return join("SM_Vase", parts)


def jug():
    """Glass water jug: straight, gently tapered body (24 segments below z 14, 32 for the rim / spout zone) (almost no waist, so it does not echo
    the vase), 0.4 cm wall offset from the same curve (inner wall at half the segments, it is only
    seen through the mouth), a long pulled pouring spout, and a smooth ear handle: 12-sided flattened
    oval section (1.4 x 2.1 cm, long axis in the handle plane) swept along a Catmull-Rom D, flaring
    1.3x where it meets the wall, fused on."""
    ctrl = [Vector((4.8, 0.0)), Vector((5.7, 0.9)), Vector((6.0, 3.5)), Vector((5.9, 9.0)), Vector((5.6, 14.0)),
            Vector((5.5, 17.5)), Vector((5.7, 20.2)), Vector((5.9, 21.3))]
    dense = catmull(ctrl, 12)
    K = 9
    idx = resample(dense, K + 1, bend=1.6)
    outer = [dense[i] for i in idx]

    def inward(i):
        a, b = dense[max(i - 1, 0)], dense[min(i + 1, len(dense) - 1)]
        t = (b - a).normalized()
        return dense[i] + Vector((-t.y, t.x)) * 0.4

    # inner wall: every row inside the spout zone (z > 15, so the pulled lip keeps its 0.4 cm wall),
    # every second row below it
    top_rows = [i for i in idx if dense[i].y > 15.0]
    low_rows = [i for i in idx if dense[i].y <= 15.0][::-1][1::2]
    inner = [inward(i) for i in top_rows[::-1] + low_rows if inward(i).y > 1.9]
    top_o, top_i = outer[-1], inner[0]
    H = max(top_o.y, top_i.y) + 0.17
    # 32 segments for every row above z 14 (rim, spout, top of the inner wall: the seated viewer looks
    # down into exactly this area), 24 for the outer body below, 12 for the hidden lower inner wall and
    # a 32-gon floor ring. lathe_rows zips rows of different counts with triangle fans.
    SEG, HI = 24, 32
    rows = [(0.0, 0.0, 1), (outer[0].x, 0.0, SEG // 2)]
    rows += [(p.x, p.y, HI if p.y > 14.0 else SEG) for p in outer[1:]]
    rows += [((top_o.x + top_i.x) / 2, H, HI)]
    rows += [(p.x, p.y, HI if p.y > 14.0 else SEG // 2) for p in inner]
    # floor ring 32: a 16-gon (and the old 24-gon) floor read as a polygon straight down through the mouth
    # (compared side by side in round 2); 32 costs +32 tris over 16 and keeps the jug under 1.2k
    rows += [(5.2, 1.2, HI), (0.0, 1.05, 1)]
    body = lathe_rows(rows, "M_Glass", name="jug", angle_smooth=50)
    zs = 15.0
    ring_of = {}                             # ring membership before the pull (rows share r and z)
    for v in body.data.vertices:
        if v.co.z > zs:
            ring_of.setdefault((round(v.co.z, 4), round(math.hypot(v.co.x, v.co.y), 3)), []).append(v.index)
    for v in body.data.vertices:             # pull a pouring lip out of the rim on +X (local lobe)
        if v.co.z <= zs:
            continue
        th = math.atan2(v.co.y, v.co.x)
        w = max(0.0, math.cos(th)) ** 4
        t = ((v.co.z - zs) / (H - zs)) ** 2
        r = math.hypot(v.co.x, v.co.y)
        nr = r + 3.0 * w * t
        v.co.x, v.co.y = nr * math.cos(th), nr * math.sin(th)
        v.co.z += 1.0 * w * t
    # round the spout tip off in plan: three Laplacian passes (factor 0.5, XY only) along each ring above
    # z 15. Smoothing along the ring (not across rows) keeps the 0.4 cm wall from thinning.
    me = body.data
    for _ in range(3):
        for ids in ring_of.values():
            ids = sorted(ids, key=lambda i: math.atan2(me.vertices[i].co.y, me.vertices[i].co.x))
            P = [me.vertices[i].co.copy() for i in ids]
            n = len(P)
            for k, i in enumerate(ids):
                a, b = P[k - 1], P[(k + 1) % n]
                me.vertices[i].co.x = 0.5 * P[k].x + 0.25 * (a.x + b.x)
                me.vertices[i].co.y = 0.5 * P[k].y + 0.25 * (a.y + b.y)
    smooth(body, 50)

    def r_out(z):
        for a, b in zip(dense, dense[1:]):
            if a.y <= z <= b.y:
                return a.x + (b.x - a.x) * (z - a.y) / (b.y - a.y)
        return dense[-1].x

    # ear handle on -X: ends sit mid-wall (0.2 cm into the 0.4 cm wall); inner finger gap >= 2.5 cm
    ztop, zbot = 17.9, 6.6
    hp = [Vector((-(r_out(ztop) - 0.2), 0, ztop)), Vector((-7.4, 0, 17.9)), Vector((-9.2, 0, 16.0)),
          Vector((-9.6, 0, 12.2)), Vector((-8.9, 0, 8.4)), Vector((-7.4, 0, 6.6)),
          Vector((-(r_out(zbot) - 0.2), 0, zbot))]
    pts = catmull(hp, [1, 3, 2, 2, 3, 1])     # fewer steps on the nearly straight middle runs
    cum = [0.0]
    for p, q in zip(pts, pts[1:]):
        cum.append(cum[-1] + (p - q).length)
    radii = []
    for c in cum:
        u = c / cum[-1]
        e = max(0.0, 1 - min(u, 1 - u) / 0.2)         # 1 at the wall, 0 beyond 20 % of the path
        radii.append(1.0 + 0.22 * e * e)                # gentle flare into the wall, no knob
    sec = section_curve(ngon(12, 0.7, 1.05), "hsec")    # long axis (1.05) ends up in the handle (XZ) plane
    handle = sweep([tuple(p) for p in pts], 1.0, "M_Glass", res=1, bevel_obj=sec, radii=radii, kind="POLY",
                   name="handle", angle_smooth=60)
    bpy.data.objects.remove(sec, do_unlink=True)
    body = union(body, [handle], 60)
    return join("SM_Jug", [body])


def glass():
    """Tumbler 11 cm, thick base, 0.25-0.5 cm wall; pivot at the geometric centre."""
    h = 5.5
    prof = [(0.0, -h), (3.0, -h), (3.25, -h + 0.25), (3.3, -h + 1.2), (3.8, h - 0.12),
            (3.72, h), (3.58, h - 0.05), (3.1, -h + 1.3), (2.85, -h + 1.05), (0.0, -h + 1.0)]
    return join("SM_Glass", [lathe(prof, 32, "M_Glass", name="glass", angle_smooth=40)])


def loft(outline, rings, centre, mats, band_mat, top_mat, bottom_mat=0, name="loft", angle_smooth=45):
    """Closed loft through scaled copies of a 2D outline: rings = [(scale, z), ...]; fans close both ends."""
    n = len(outline)
    V = [(centre[0], centre[1], rings[0][1])]
    for s, z in rings:
        V += [(centre[0] + u * s, centre[1] + v * s, z) for u, v in outline]
    V.append((centre[0], centre[1], rings[-1][1] + 0.07))
    F, FM = [], []
    for i in range(n):
        F.append((0, 1 + (i + 1) % n, 1 + i))
        FM.append(bottom_mat)
    for r in range(len(rings) - 1):
        for i in range(n):
            a, b = 1 + r * n + i, 1 + r * n + (i + 1) % n
            F.append((a, b, b + n, a + n))
            FM.append(band_mat[r])
    top = len(V) - 1
    last = 1 + (len(rings) - 1) * n
    for i in range(n):
        F.append((last + i, last + (i + 1) % n, top))
        FM.append(top_mat)
    return mesh(V, F, mats, FM, name=name, angle_smooth=angle_smooth)


def hairbrush():
    """Paddle brush: lofted oval frame with a raised rim around a domed rubber cushion, a dense hex
    field of steel ball-tipped pins standing on the cushion out to ~0.5 cm from the rim, rounded
    flattened handle fused to the head. Pivot at the centre."""
    a, b, ne, cx = 6.0, 3.9, 2.4, 5.0
    out = superellipse(a, b, ne, 26)
    rings = [(0.93, 0.0), (1.0, 1.2), (0.965, 1.62), (0.90, 1.70), (0.87, 1.52), (0.80, 1.92)]
    band = [0, 0, 0, 0, 1]                # 0 timber frame, 1 rubber cushion
    head = loft(out, rings, (cx, 0.0), ["M_TimberDark", "M_Rubber"], band, top_mat=1, name="head")
    for v in head.data.vertices:          # the cap fan's centre vert: low dome over the cushion
        if abs(v.co.x - cx) < 1e-4 and abs(v.co.y) < 1e-4 and v.co.z > 1.9:
            v.co.z = 2.08
    hprof = [(0.0, 0.0), (0.7, 0.1), (1.1, 0.5), (1.25, 1.5), (1.2, 4.0), (0.9, 8.0),
             (1.0, 10.8), (1.35, 12.4), (0.0, 12.7)]
    handle = lathe(hprof, 12, "M_TimberDark", name="handle", angle_smooth=50)
    xform(handle, PERM_ZXY)
    xform(handle, Matrix.Diagonal((1.0, 1.0, 0.6, 1.0)))
    move(handle, (-11.0, 0, 0.80))
    head = union(head, [handle], 45)

    surf = [(0.87, 1.52), (0.80, 1.92), (0.0, 2.08)]

    def z_at(s):
        for (s0, z0), (s1, z1) in zip(surf, surf[1:]):
            if s1 <= s <= s0:
                return z0 + (z1 - z0) * (s0 - s) / (s0 - s1)
        return surf[-1][1]

    # pins: hex grid (1.0 x 0.87 cm), culled at s > 0.80. Each pin is a slender 3-sided shaft from a
    # point on the cushion up to a 0.1 cm collar, then a flared ball tip (0.22 cm) with a low blunt top:
    # 12 triangles, flat-shaded so the 120-degree edges do not average into black pins.
    V, F = [], []
    px, py = 1.0, 0.87
    for iy in range(-6, 7):
        for ix in range(-8, 9):
            x = ix * px + (0.5 * px if iy % 2 else 0.0)
            y = iy * py
            s = (abs(x / a) ** ne + abs(y / b) ** ne) ** (1 / ne)
            if s > 0.80:
                continue
            z = z_at(s) + AIR
            k = len(V)
            V.append((cx + x, y, z))
            rot = 0.7 * ix + 1.3 * iy
            for rr, dz in ((0.05, 1.0), (0.11, 1.08)):
                for j in range(3):
                    t = 2 * math.pi * j / 3 + rot
                    V.append((cx + x + rr * math.cos(t), y + rr * math.sin(t), z + dz))
            V.append((cx + x, y, z + 1.22))
            for j in range(3):
                j2 = (j + 1) % 3
                F.append((k, k + 1 + j2, k + 1 + j))
                F.append((k + 1 + j, k + 1 + j2, k + 4 + j2, k + 4 + j))
                F.append((k + 4 + j, k + 4 + j2, k + 7))
    pins = mesh(V, F, ["M_Metal"], name="pins", angle_smooth=30)
    print(f"HAIRBRUSH: {len(V) // 8} pins")
    return pivot_centre(join("SM_Hairbrush", [head, pins]))


def call_bell(turns=8):
    """Nurse-call pendant: lathed handset (18 segments, extra rows round the shoulder) with a red press
    button in a raised bezel; a 4.4 mm round-section cord leaves the tail, curls into a phone-style
    coil lying beside the handset and tucks back under the handset's flank, so it reads as a cord
    that carries on out of sight (no loose plug on the table)."""
    prof = [(0.0, 0.0), (0.55, 0.0), (0.75, 0.7), (1.25, 1.4), (1.55, 2.5), (1.75, 5.5), (1.88, 9.0),
            (1.85, 10.5), (1.7, 11.65), (1.42, 12.45), (1.0, 12.92), (0.0, 13.15)]
    body = lathe(prof, 18, "M_PlasticWhite", name="handset", angle_smooth=50)
    xform(body, PERM_ZXY)
    sz, sy = 0.72, 1.15
    xform(body, Matrix.Diagonal((1.0, sy, sz, 1.0)))
    zax = 1.88 * sz
    move(body, (0, 0, zax))
    bx = 9.2
    ztop = 2 * zax
    bez = lathe([(0.0, -0.5), (1.25, -0.5), (1.25, 0.05), (1.1, 0.18), (0.95, 0.05), (0.0, 0.05)], 14,
                "M_PlasticWhite", name="bezel", angle_smooth=50)
    move(bez, (bx, 0, ztop))
    body = union(body, [bez], 50)
    cap = lathe([(0.0, 0.05 + AIR), (0.88, 0.05 + AIR), (0.9, 0.30), (0.76, 0.42), (0.0, 0.45)], 14,
                "M_FlowerRed", name="button", angle_smooth=50)   # flat-topped push button, chamfered rim
    move(cap, (bx, 0, ztop))
    parts = [body, cap]

    rw = 0.22                      # cord radius (4.4 mm cable)
    Rc, pitch, per = 0.62, 0.5, 6  # coil radius, pitch (> 2 rw, turns never touch), steps per turn
    yc, x0 = -3.6, -0.6
    lead_in = [Vector((-0.12, 0, zax)), Vector((-0.8, 0, zax - 0.06)), Vector((-1.55, -0.6, 0.6)),
               Vector((-1.95, -1.9, rw)), Vector((-1.5, -3.25, rw)), Vector((x0, yc, rw))]
    pts = catmull(lead_in, [1, 2, 3, 3, 1])[:-1]
    for i in range(turns * per + 1):          # coil lying on the table
        th = 2 * math.pi * i / per
        pts.append(Vector((x0 + pitch * i / per, yc + Rc * math.sin(th), rw + Rc - Rc * math.cos(th))))
    x1 = x0 + pitch * turns
    # lead-out: back towards the handset and under its flank (underside there is ~0.15 cm above the cord)
    lead_out = [Vector((x1, yc, rw)), Vector((x1 + 1.0, yc + 0.25, rw)), Vector((x1 + 1.9, -2.5, rw)),
                Vector((x1 + 2.4, -1.6, rw))]
    pts += catmull(lead_out, [1, 2, 1])[1:]
    sec = section_curve(ngon(5, rw), "cordsec")
    parts.append(sweep([tuple(p) for p in pts], rw, "M_PlasticWhite", res=1, bevel_obj=sec, kind="POLY",
                       name="cord", angle_smooth=80))
    bpy.data.objects.remove(sec, do_unlink=True)
    ob = join("SM_CallBell", parts)
    return pivot_bottom_centre(ob)


def day_date_clock():
    """Dementia day/date clock: rounded white case with an inset screen facing +X, two top buttons,
    tilted back 12 degrees on a rear easel strut (all fused)."""
    W, H, D = 20.0, 14.0, 2.4
    bm = bmesh.new()
    outline = rounded_rect(W, H, 1.8, 5)
    vs = [bm.verts.new((u, v, -D / 2)) for u, v in outline]
    f = bm.faces.new(vs)
    ext = bmesh.ops.extrude_face_region(bm, geom=[f])
    nv = [gg for gg in ext["geom"] if isinstance(gg, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, verts=nv, vec=(0, 0, D))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    caps = [fc for fc in bm.faces if len(fc.verts) > 4]
    rim = {e for fc in caps for e in fc.edges}
    bmesh.ops.bevel(bm, geom=list(rim), offset=0.6, segments=3, profile=0.5, affect="EDGES", clamp_overlap=True)
    front = max((fc for fc in bm.faces), key=lambda fc: fc.normal.z * fc.calc_area())
    bmesh.ops.inset_region(bm, faces=[front], thickness=0.9, depth=0.0, use_even_offset=True)
    bmesh.ops.inset_region(bm, faces=[front], thickness=0.12, depth=-0.18, use_even_offset=True)
    front.material_index = 1
    for v in front.verts:                  # deeper bottom bezel ("chin")
        if v.co.y < -H / 2 + 2.0:
            v.co.y += 0.8
    me = bpy.data.meshes.new("case")
    bm.to_mesh(me)
    bm.free()
    case = link("case", me)
    case.data.materials.append(mat("M_PlasticWhite"))
    case.data.materials.append(mat("M_Screen"))
    smooth(case, 40)
    xform(case, PERM_ZXY)                  # outline in YZ, depth along X, screen facing +X
    btns = []
    for yy in (-5.0, -3.4):
        bt = lathe([(0.0, -0.3), (0.45, -0.3), (0.45, 0.15), (0.35, 0.28), (0.0, 0.3)], 10,
                   "M_PlasticBlack", name="btn", angle_smooth=60)
        move(bt, (-0.3, yy, H / 2))
        btns.append(bt)
    case = union(case, btns, 40)
    tilt = Matrix.Rotation(math.radians(-12), 4, "Y")
    xform(case, tilt)
    lo, _ = bounds(case)
    move(case, (0, 0, -lo.z))
    # rear easel strut: from the upper back (sunk 0.25 into the case) down to the table
    attach = tilt @ Vector((-D / 2 + 0.25, 0, 2.0)) + Vector((0, 0, -lo.z))
    foot = Vector((attach.x - 6.0, 0, 0.3))
    L = (attach - foot).length
    strut = slab(rounded_rect(4.6, L, 1.2, 3), -0.2, 0.2, "M_PlasticWhite", bevel=0.1, seg=1, name="strut")
    ydir = (attach - foot).normalized()
    xdir = Vector((0, 1, 0))
    zdir = xdir.cross(ydir)
    Rm = Matrix((xdir, ydir, zdir)).transposed().to_4x4()
    xform(strut, Matrix.Translation((attach + foot) / 2) @ Rm)
    smin = min(v.co.z for v in strut.data.vertices)
    for v in strut.data.vertices:          # settle the foot end flat on the table plane
        if (v.co - foot).length < 2.5:
            v.co.z = max(0.0, v.co.z - smin)
    case = union(case, [strut], 40)
    ob = join("SM_DayDateClock", [case])
    return pivot_bottom_centre(ob)


def clipboard():
    """A4 hardboard clipboard: three sheets (top one curling), low-profile spring clip fused from
    base plate, rivets, side ears, hinge barrel and curved jaw."""
    parts = []
    t = 0.3
    board = slab(rounded_rect(32.0, 23.0, 1.2, 4), 0.0, t, "M_TimberDark", bevel=0.08, seg=1, name="board")
    parts.append(board)
    th = 0.035
    sheet_cx = -0.95          # paper stays >= 0.1 cm inside the board outline and clear of the clip plate
    for k, (rot, dy, nx, ny) in enumerate(((-0.45, 0.2, 3, 2), (0.35, -0.12, 3, 2), (-0.15, 0.04, 7, 5))):
        bm = bmesh.new()
        bmesh.ops.create_grid(bm, x_segments=nx, y_segments=ny, size=0.5)
        for v in bm.verts:
            v.co.x *= 29.7
            v.co.y *= 21.0
        ext = bmesh.ops.extrude_face_region(bm, geom=list(bm.faces))
        nv = [gg for gg in ext["geom"] if isinstance(gg, bmesh.types.BMVert)]
        bmesh.ops.translate(bm, verts=nv, vec=(0, 0, th))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        Rz = Matrix.Rotation(math.radians(rot), 3, "Z")
        for v in bm.verts:
            u = (v.co.x + 14.85) / 29.7          # 0 free (bottom) edge, 1 clipped edge
            w = (v.co.y + 10.5) / 21.0
            c = Rz @ v.co
            lift = 0.0
            if k == 2:
                lift = 0.8 * max(0.0, 1 - u / 0.35) ** 2 * max(0.0, 1 - w / 0.6) ** 2
            c.z += t + AIR + k * (th + AIR) + lift
            c.x += sheet_cx
            c.y += dy
            v.co = c
        me = bpy.data.meshes.new("sheet")
        bm.to_mesh(me)
        bm.free()
        s = link("sheet", me)
        set_mat(s, "M_Paper")
        smooth(s, 50)
        parts.append(s)
    pt = t + AIR + 2 * (th + AIR) + th              # top of the paper stack
    zp = t + AIR                                     # clip base plate bottom
    plate = slab(rounded_rect(2.0, 11.0, 0.6, 3), zp, zp + 0.14, "M_Metal", bevel=0.05, seg=1, name="plate")
    move(plate, (15.0, 0, 0))
    clip = [plate]
    for yy in (-3.6, 3.6):
        rv = lathe([(0.0, -0.05), (0.38, -0.05), (0.36, 0.06), (0.22, 0.14), (0.0, 0.16)], 10, "M_Metal", name="rivet")
        move(rv, (14.55, yy, zp + 0.14))
        clip.append(rv)
    zb = 1.0
    clip.append(sweep([(15.35, -4.9, zb), (15.35, 4.9, zb)], 0.3, "M_Metal", res=1, bevel_res=2, kind="POLY",
                      name="barrel", angle_smooth=60))
    for yy in (-4.72, 4.72):
        ear = slab([(14.55, zp + 0.08), (15.95, zp + 0.08), (15.75, zb + 0.1), (15.35, zb + 0.2), (14.95, zb + 0.1)],
                   -0.08, 0.08, "M_Metal", bevel=0.03, seg=1, name="ear")
        xform(ear, SWAP_YZ)                  # mirror: flips winding, so recalc normals
        move(ear, (0, yy, 0))
        smooth(ear, 50)
        clip.append(ear)
    prof = [(10.85, pt + 0.34), (11.1, pt + 0.06), (11.7, pt + 0.2), (12.7, pt + 0.6), (13.8, pt + 1.0),
            (14.7, pt + 1.2), (15.3, pt + 1.05), (15.5, zb + 0.15)]      # ends inside the barrel
    tk = 0.09
    up, dn = [], []
    for i, (x, z) in enumerate(prof):
        a2 = Vector(prof[max(i - 1, 0)])
        b2 = Vector(prof[min(i + 1, len(prof) - 1)])
        tg = (b2 - a2).normalized()
        nr = Vector((-tg.y, tg.x))
        up.append(Vector((x, z)) + nr * tk)
        dn.append(Vector((x, z)))
    outline2 = [(p.x, p.y) for p in up] + [(p.x, p.y) for p in reversed(dn)]
    jaw = slab(outline2, -4.6, 4.6, "M_Metal", bevel=0.03, seg=1, name="jaw", angle_smooth=50)
    xform(jaw, SWAP_YZ)
    smooth(jaw, 50)
    clip.append(jaw)
    parts.append(union(clip[0], clip[1:], 50))
    ob = join("SM_Clipboard", parts)
    return pivot_bottom_centre(ob)


def ring_mesh(rings, mats, face_mat, name="rings", angle_smooth=40.0):
    """Closed surface through rings of points (each ring a list of Vectors running counter-clockwise
    from the front, or a single Vector = pole). Neighbouring rings may differ in count (zipped with
    triangles). face_mat(k, j) gives the slot index of the face between ring k and k+1 at column j."""
    V, rid = [], []
    for ring in rings:
        pts = ring if isinstance(ring, list) else [ring]
        rid.append(list(range(len(V), len(V) + len(pts))))
        V += pts
    F, FM = [], []
    for k, (A, B) in enumerate(zip(rid, rid[1:])):
        na, nb = len(A), len(B)
        if na == 1:
            F += [(A[0], B[(j + 1) % nb], B[j]) for j in range(nb)]
            FM += [face_mat(k, j) for j in range(nb)]
        elif nb == 1:
            F += [(A[j], A[(j + 1) % na], B[0]) for j in range(na)]
            FM += [face_mat(k, j) for j in range(na)]
        elif na == nb:
            F += [(A[j], A[(j + 1) % na], B[(j + 1) % nb], B[j]) for j in range(na)]
            FM += [face_mat(k, j) for j in range(na)]
        else:
            i = j = 0
            while i < na or j < nb:
                if j >= nb or (i < na and (i + 1) / na <= (j + 1) / nb):
                    F.append((A[i % na], A[(i + 1) % na], B[j % nb]))
                    i += 1
                else:
                    F.append((A[i % na], B[(j + 1) % nb], B[j % nb]))
                    j += 1
                FM.append(face_mat(k, -1))
    return mesh(V, F, mats, FM, name=name, angle_smooth=angle_smooth)


def madonna():
    """Ceramic Madonna (~20 cm, Our Lady of Grace pose) on a gilt plinth.

    One closed ring surface (no boolean cutter; only the arms are fused on): plinth (14 columns) -> robe skirt with hem folds ->
    mantle and veil (20 columns). In every mantle ring the columns are laid out round the front
    opening: 5 robe-front verts recessed behind the mantle edge, then on each side an outer edge vert
    and a narrow gilt-band vert, then 10 verts round the back (it stands against the wall). So the opening has crisp, clean edges
    (no slivers), the robe front shows between the mantle edges, and at head height the recess
    deepens into the face pocket, which closes in a pointed arch tip on the veil surface above the
    crown of the head. The crown rings above it keep the same column angles (front verts back on the
    surface) and close at a pole, so no band twists. The veil widens as it falls (crown -> veil -> shoulder in one convex line), with long
    vertical folds down the back. The face pocket is an oval fitted round the head (about 0.2 cm
    clear of cheeks, back of the head and crown), pinched in at the throat under the chin. Sleeves
    (12-sided sweeps) start inside the mantle at the shoulders, emerge from under it by the elbows and
    turn in to cuffs that wrap a rounded praying-hands wedge; sleeves + hands are fused into the
    figure (one cast body). A 7-8 heads-tall head with a lowered gaze sits in the pocket, and a thin
    gilt halo stands behind the veil. Faces +X."""
    FL = 0.78

    def flatten(z, zlim=6.0):
        return FL if z > zlim else FL + (1 - FL) * (1 - max(0.0, z - 1.8) / (zlim - 1.8))

    ctrl = [Vector((3.32, 3.0)), Vector((2.95, 6.2)), Vector((2.42, 9.8)), Vector((2.62, 11.6)),
            Vector((2.68, 13.0)), Vector((2.7, 14.2)), Vector((2.3, 15.4)), Vector((1.95, 16.8)),
            Vector((1.75, 18.3)), Vector((0.0, 19.05))]
    dense = catmull(ctrl, 10)

    def r_at(z):
        for p, q in zip(dense, dense[1:]):
            if p.y <= z <= q.y:
                return p.x + (q.x - p.x) * (z - p.y) / (q.y - p.y)
        return 0.0

    NB = 10                     # columns round the back of each mantle ring (it stands against the wall)
    C = NB + 9

    def uniform(r, z, fz, n=None):
        n = n or C
        return [Vector((fz * r * math.cos(2 * math.pi * i / n), r * math.sin(2 * math.pi * i / n), z))
                for i in range(n)]

    def opening(r, z, fz, mode, val, w):
        """Ring laid out round the front opening (see docstring); index 0 = front centre, CCW."""
        def front(y):
            if mode == "flat":
                return val
            if mode == "x":                  # val = x of the back wall on the centre line
                return val - fz * (r - math.sqrt(max(r * r - y * y, 0.0)))
            return fz * math.sqrt(max(r * r - y * y, 0.0)) - val
        fr = [Vector((front(y), y, z)) for y in (0.0, 0.5 * w, w)]           # idx 0, 1, 2
        pe = math.asin(min(w / r, 0.999))
        pb = pe + 0.14 / r

        def on(phi):
            return Vector((fz * r * math.cos(phi), r * math.sin(phi), z))
        ring = fr + [on(pe), on(pb)]                                          # idx 3, 4
        ring += [on(pb + (2 * math.pi - 2 * pb) * k / (NB + 1)) for k in range(1, NB + 1)]  # idx 5..C-5
        ring += [on(-pb), on(-pe)]                                            # idx C-4, C-3
        ring += [Vector((front(-w), -w, z)), Vector((front(-0.5 * w), -0.5 * w, z))]  # idx C-2, C-1
        return ring

    # ---- head first: the face pocket in the veil is fitted round it
    # head: 1.9 wide x 2.4 tall x 1.5 deep, lowered gaze (11 deg), nose / chin forward, eyes set back
    head = ball((0, 0, 0), 1.0, "M_Ceramic", u=10, v=6, name="head", angle_smooth=80)
    me = head.data
    ang = min((math.atan2(v.co.y, v.co.x) for v in me.vertices if math.hypot(v.co.x, v.co.y) > 0.5), key=abs)
    me.transform(Matrix.Rotation(-ang, 4, "Z"))
    for v in me.vertices:
        az = math.degrees(math.atan2(v.co.y, v.co.x))
        if math.hypot(v.co.x, v.co.y) < 0.3:
            continue
        if abs(az) < 1:
            if abs(v.co.z) < 0.05:
                v.co.x += 0.16                     # nose
            elif 0.45 < v.co.z < 0.55:
                v.co.x += 0.04                     # brow
            elif -0.55 < v.co.z < -0.45:
                v.co.x += 0.07                     # chin
        elif 30 < abs(az) < 42 and 0.45 < v.co.z < 0.55:
            v.co.x -= 0.07                         # eye sockets
    me.transform(Matrix.Diagonal((0.75, 0.95, 1.2, 1.0)))
    me.transform(Matrix.Rotation(math.radians(11), 4, "Y"))
    hz = 16.4
    back = min(v.co.x for v in me.vertices)
    me.transform(Matrix.Translation((-0.15 + 0.21 - back, 0, hz)))
    smooth(head, 80)
    HV = [v.co.copy() for v in me.vertices]
    HE = [(HV[e.vertices[0]], HV[e.vertices[1]]) for e in me.edges]

    def hslice(z):
        """Head cross-section at height z (points on its edges)."""
        pts = [p for p in HV if abs(p.z - z) < 1e-6]
        pts += [a.lerp(b, (z - a.z) / (b.z - a.z)) for a, b in HE if (a.z - z) * (b.z - z) < 0]
        return pts

    HP = [Vector((a.x, a.z)).lerp(Vector((b.x, b.z)), a.y / (a.y - b.y)) for a, b in HE if a.y * b.y < 0]
    HP += [Vector((p.x, p.z)) for p in HV if abs(p.y) < 1e-6]

    # ---- face pocket: an oval that follows the head. Each ring: (z, half width, x of the pocket's back
    # wall). Targets come from the head (back wall GAP behind it, sides GAP outside the cheeks); then
    # every span between two rings is sampled and both rings are pushed out wherever the straight span
    # would come closer than GAP to the head. 14.8 is the throat under the chin, where the veil edges
    # close in; 17.9 closes the pocket just above the crown of the head.
    GAP = 0.22
    pz = [14.8, 15.2, 15.8, 16.4, 17.0, 17.5, 17.9]
    pw = [0.72, 0.8, 1.05, 1.15, 1.05, 0.75, 0.1]
    px = []
    for k, z in enumerate(pz):
        S = hslice(z)
        if S:
            px.append(min(p.x for p in S) - GAP)
            pw[k] = max(pw[k], max(abs(p.y) for p in S) + GAP)
        elif z < hz:
            px.append(1.05)                                     # throat: front of the neck
        else:
            px.append(flatten(z) * r_at(z))                     # pointed arch tip ON the veil surface (fixed)
    for _ in range(200):
        done = True
        for k in range(len(pz) - 1):
            for s in range(21):
                t = s / 20
                S = hslice(pz[k] + t * (pz[k + 1] - pz[k]))
                if not S:
                    continue
                dw = max(abs(p.y) for p in S) + GAP - (pw[k] * (1 - t) + pw[k + 1] * t)
                dx = (px[k] * (1 - t) + px[k + 1] * t) - (min(p.x for p in S) - GAP)
                q = (1 - t) ** 2 + t ** 2               # least-norm push: mostly the nearer ring moves
                if dw > 1e-4:
                    pw[k] += dw * (1 - t) / q
                    pw[k + 1] += dw * t / q
                    done = False
                if dx > 1e-4:
                    px[k] -= dx * (1 - t) / q
                    if k + 1 < len(pz) - 1:
                        px[k + 1] -= dx * t / q
                    done = False
        # centre line (y = 0): the head's section must stay GAP in front of the pocket profile measured
        # perpendicular to it, not only horizontally (the ceiling leans forward over the crown)
        for P in HP:
            for k in range(len(pz) - 1):
                A, B = Vector((px[k], pz[k])), Vector((px[k + 1], pz[k + 1]))
                d = B - A
                t = (P - A).dot(d) / d.length_squared
                if not 0.0 <= t <= 1.0:
                    continue
                n = Vector((d.y, -d.x)).normalized()           # points forward, into the pocket
                deficit = GAP - (P - A).dot(n)
                if deficit > 1e-4:
                    q = (1 - t) ** 2 + t ** 2
                    px[k] -= deficit / n.x * (1 - t) / q
                    if k + 1 < len(pz) - 1:
                        px[k + 1] -= deficit / n.x * t / q
                    done = False
        if done:
            break
    print("MADONNA pocket", [(z, round(w, 3), round(x, 3)) for z, w, x in zip(pz, pw, px)])

    rings, kinds = [], []
    rings.append(Vector((0, 0, 0.0)))
    kinds.append("plinth")
    for r, z in ((4.2, 0.0), (4.38, 0.35), (4.05, 1.05), (3.52, 1.8)):
        rings.append([Vector((r * math.cos(2 * math.pi * i / 14), r * math.sin(2 * math.pi * i / 14), z))
                      for i in range(14)])
        kinds.append("plinth")
    skirt = uniform(3.42, 2.3, flatten(2.3))
    for i, v in enumerate(skirt):                               # robe hem folds
        k = 1 + 0.035 * math.sin(6 * 2 * math.pi * i / C)
        v.x *= k
        v.y *= k
    rings.append(skirt)
    kinds.append("robe")
    rings.append(opening(3.1, 2.97, flatten(2.97), "body", 0.0, 1.9))
    kinds.append("hem_under")
    # (z, mode, depth or back-wall x, half width, blend to the opening layout). Sorted by z below: an
    # out-of-order ring folds the robe back through itself.
    spec = [(3.0, "body", 0.25, 1.9, 1.0), (9.8, "body", 0.35, 1.2, 1.0),
            (12.0, "body", 0.42, 1.0, 1.0), (14.2, "body", 0.55, 0.9, 1.0)]
    spec += [(z, "x", x, w, 1.0) for z, w, x in zip(pz, pw, px)]
    spec += [(18.3, None, 0, 0, 0.0), (18.8, None, 0, 0, 0.0)]
    spec.sort(key=lambda s: s[0])
    for z, mode, val, w, bl in spec:
        r = r_at(z) if z > 3.01 else 3.32
        fz = flatten(z)
        if bl > 0.0:
            ring = opening(r, z, fz, mode, val, w)
        else:
            # crown rings above the pocket keep the opening's column angles with the front verts back on
            # the surface: a plain uniform ring here zips column k to a different angle and twists the
            # band into a dark bow-tie "ceiling" over the head
            ring = opening(r, z, fz, "body", 0.0, pw[-1])
        for i, v in enumerate(ring):                            # long veil / mantle folds on the back
            if 5 <= i <= C - 5 or bl == 0.0:
                phi = math.atan2(v.y, v.x / fz)
                wb = min(1.0, max(0.0, (abs(phi) - math.radians(100)) / math.radians(25)))
                amp = 0.05 if z >= 9.5 else 0.035
                amp *= min(1.0, max(0.0, (18.7 - z) / 1.0))
                k = 1 + amp * wb * math.sin(4 * phi)
                v.x *= k
                v.y *= k
        rings.append(ring)
        kinds.append("hem" if z < 3.1 else ("body" if mode == "body" else ("pocket" if bl > 0 else "closed")))
    rings.append(Vector((0, 0, 19.05)))
    kinds.append("crown")

    def face_mat(k, j):
        a, b = kinds[k], kinds[k + 1]
        if a == "plinth":
            return 1
        band = j in (3, C - 4)
        wall = j in (2, C - 3)
        if a == "hem_under" and b == "hem" and 3 <= j <= C - 4:
            return 1                                            # gilt hem lip
        if band and a in ("hem", "body", "pocket") and b in ("hem", "body", "pocket"):
            return 1                                            # gilt trim along the mantle / veil edges
        if wall and a in ("hem", "body") and b in ("hem", "body"):
            return 1                                            # ... and on the mantle edge thickness
        return 0

    fig = ring_mesh(rings, ["M_Ceramic", "M_Gold"], face_mat, name="figure", angle_smooth=40)

    # ---- arms: one cast body with the figure. Each 12-sided sleeve (paid for by 10 back columns and dropping the
    # 6.5 robe ring, which the near-straight lower robe does not need) starts inside the mantle at the
    # shoulder, runs down the side so the upper arm emerges from under the mantle by the elbow, then
    # turns forward and in to a cuff that wraps the praying hands. Sleeves + hands are fused, then
    # fused INTO the figure with an EXACT boolean (arms are the operand; the ring topology is kept).
    def surf_x(z, y):
        r = r_at(z)
        return flatten(z) * math.sqrt(max(r * r - y * y, 0.0))

    sec = section_curve(ngon(12, 1.0, rot=math.pi / 12), "slv")
    parts = []
    for sg in (-1, 1):
        ctl = [Vector((surf_x(14.0, 1.9) - 0.4, sg * 1.9, 14.0)),
               Vector((surf_x(12.4, 1.75), sg * 1.75, 12.4)),
               Vector((2.42, sg * 1.12, 11.95)),
               Vector((2.68, sg * 0.42, 11.62))]
        rad = [0.36, 0.48, 0.53, 0.62]
        steps = [2, 1, 1]
        pts = catmull(ctl, steps)
        radii = [rad[i] + (rad[i + 1] - rad[i]) * j / s for i, s in enumerate(steps) for j in range(s)] + [rad[-1]]
        parts.append(sweep([tuple(p) for p in pts], 1.0, "M_Ceramic", res=1, bevel_obj=sec,
                           radii=radii, kind="POLY", name="sleeve", angle_smooth=50))
    bpy.data.objects.remove(sec, do_unlink=True)

    # praying hands: rounded wedge, 8 verts per ring, 1.0 wide x 0.55 deep at the wrist to a rounded
    # 0.25-wide fingertip cap, tilted 10 degrees forward; its wrist end sits inside the cuffs
    tilt = math.radians(10)
    dirv = Vector((math.sin(tilt), 0, math.cos(tilt)))
    lx = Vector((math.cos(tilt), 0, -math.sin(tilt)))
    ly = Vector((0, 1, 0))
    b0 = Vector((2.7, 0, 11.3))
    L = 1.7
    V = [b0 - dirv * 0.1]
    for u, ax_, by_ in ((0.0, 0.275, 0.5), (0.8, 0.19, 0.26), (0.93, 0.12, 0.15)):
        c = b0 + dirv * L * u
        V += [c + lx * (ax_ * math.cos(2 * math.pi * j / 8)) + ly * (by_ * math.sin(2 * math.pi * j / 8))
              for j in range(8)]
    V.append(b0 + dirv * L)
    F = [(0, 1 + (j + 1) % 8, 1 + j) for j in range(8)]
    for k in range(2):
        F += [(1 + k * 8 + j, 1 + k * 8 + (j + 1) % 8, 1 + (k + 1) * 8 + (j + 1) % 8, 1 + (k + 1) * 8 + j)
              for j in range(8)]
    tip = len(V) - 1
    F += [(1 + 16 + j, 1 + 16 + (j + 1) % 8, tip) for j in range(8)]
    parts.append(mesh(V, F, ["M_Ceramic"], name="hands", angle_smooth=60))
    arms = union(parts[0], parts[1:], 50)

    def key(co):
        return (round(co.x, 4), round(co.y, 4), round(co.z, 4))
    old = {key(v.co) for v in fig.data.vertices}
    print("DBG fig", tri_count(fig), "arms", tri_count(arms), "head", tri_count(head))
    fig = union(fig, [arms], 45)
    print("DBG union", tri_count(fig))
    bm = bmesh.new()
    bm.from_mesh(fig.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.005)
    heal_cracks(bm, 0.005)
    newv = [v for v in bm.verts if key(v.co) not in old]
    newf = {f for v in newv for f in v.link_faces}
    newe = [e for e in bm.edges if e.link_faces and all(f in newf for f in e.link_faces)]
    bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(2), verts=newv, edges=newe, delimit={"MATERIAL"})
    bmesh.ops.connect_verts_concave(bm, faces=[f for f in bm.faces if len(f.verts) > 3])
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4], quad_method="BEAUTY",
                          ngon_method="BEAUTY")
    bm.to_mesh(fig.data)
    bm.free()
    smooth(fig, 45)
    print("DBG cleaned", tri_count(fig))

    # gilt halo: thin ring standing behind the veil, 0.2 cm clear of it
    hr, hzc = 2.1, 17.6
    zlow = hzc - hr
    xh = -flatten(zlow) * r_at(zlow) * 1.03 - 0.2 - 0.08
    V, F = [], []
    nu, nv = 12, 3
    for i in range(nu):
        t = 2 * math.pi * i / nu
        for j in range(nv):
            q = 2 * math.pi * j / nv
            rr = hr + 0.08 * math.cos(q)
            V.append((xh + 0.08 * math.sin(q), rr * math.cos(t), hzc + rr * math.sin(t)))
    for i in range(nu):
        for j in range(nv):
            a0, a1 = i * nv + j, i * nv + (j + 1) % nv
            b0_, b1 = ((i + 1) % nu) * nv + j, ((i + 1) % nu) * nv + (j + 1) % nv
            F.append((a0, b0_, b1, a1))
    halo = mesh(V, F, ["M_Gold"], name="halo", angle_smooth=70)

    S = Matrix.Scale(20.0 / 19.05, 4)
    for o in (fig, head, halo):
        xform(o, S)
    ob = join("SM_Madonna", [fig, head, halo])
    return pivot_bottom_centre(ob)


def rosary():
    """Five-decade rosary lying in a loose loop: 59 round wooden beads (6.4 mm Hail Mary, 8.4 mm Our
    Father) sitting almost touching as on a corded rosary (0.8 mm apart). Each bead is a 16-triangle
    round bead: two staggered 4-vert rings + poles, axis vertical so its outline from above is an
    octagon, shaded as a sphere with custom normals. Steel links only where the strand meets the
    oval centre medal and the crucifix eye; tail with a bevelled crucifix carrying a raised corpus."""
    small, large, gap = 0.32, 0.42, 0.08       # bead radii, surface-to-surface gap along the strand
    lg = 0.28                                  # gap bridged by a steel link (medal, crucifix eye)
    seq = []
    for dec in range(5):
        seq += [small] * 10
        if dec < 4:
            seq.append(large)
    medal_half, medal_b = 0.75, 0.55
    need = 2 * medal_half + 2 * lg + sum(2 * r for r in seq) + (len(seq) - 1) * gap
    N = 720
    raw = []
    for i in range(N):
        t = 2 * math.pi * i / N - math.pi / 2          # i = 0 is the bottom (-Y) of the loop
        rr = 1 + 0.25 * math.sin(3 * t + 0.9)
        raw.append(Vector((6.0 * rr * math.cos(t), 5.0 * rr * math.sin(t), 0)))
    per = sum((raw[(i + 1) % N] - raw[i]).length for i in range(N))
    path = [p * (need / per) for p in raw]
    seg = [(path[(i + 1) % N] - path[i]).length for i in range(N)]
    total = sum(seg)

    def at(s):
        s %= total
        for i in range(N):
            if s <= seg[i]:
                p = path[i].lerp(path[(i + 1) % N], s / seg[i])
                return p, (path[(i + 1) % N] - path[i]).normalized()
            s -= seg[i]
        return path[0], (path[1] - path[0]).normalized()

    V, F, NRM, FM = [], [], [], []
    zl = 0.11                                       # link height at the medal / crucifix eye
    up = Vector((0, 0, 1))

    def bead(p, tg, r, n=4):
        """Round bead resting on the table at p: poles on the vertical axis, two rings of n verts at
        +-0.38 r (radius 0.925 r) staggered by half a step, so the outline from above is a 2n-gon;
        16 triangles. Returns its centre."""
        c = p + up * r
        rot = math.atan2(tg.y, tg.x)
        k = len(V)
        V.append(c + up * r)
        V.append(c - up * r)
        for dz, a0 in ((0.38, 0.0), (-0.38, math.pi / n)):
            for j in range(n):
                a = rot + a0 + 2 * math.pi * j / n
                V.append(c + Vector((0.925 * r * math.cos(a), 0.925 * r * math.sin(a), dz * r)))
        for v in V[k:]:
            NRM.append((v - c).normalized())
        A = [k + 2 + j for j in range(n)]
        B = [k + 2 + n + j for j in range(n)]
        for j in range(n):
            j2 = (j + 1) % n
            F.extend([(k, A[j], A[j2]), (A[j], B[j], A[j2]), (B[j], B[j2], A[j2]), (k + 1, B[j2], B[j])])
            FM.extend([0, 0, 0, 0])
        return c

    def link(a, b):
        """Steel link: slender 3-sided bicone between two free points (tips 0.02 cm off the parts)."""
        d = (b - a).normalized()
        u = d.cross(up)
        if u.length < 1e-6:
            u = Vector((1, 0, 0))
        u.normalize()
        w = d.cross(u)
        mid = (a + b) / 2
        k = len(V)
        V.append(a.copy())
        NRM.append(-d)
        V.append(b.copy())
        NRM.append(d.copy())
        for j in range(3):
            t = 2 * math.pi * j / 3
            dvec = u * math.cos(t) + w * math.sin(t)
            V.append(mid + dvec * 0.06)
            NRM.append(dvec.normalized())
        for j in range(3):
            j2 = (j + 1) % 3
            F.extend([(k, k + 2 + j, k + 2 + j2), (k + 1, k + 2 + j2, k + 2 + j)])
            FM.extend([1, 1])

    medal_c, t0 = at(0.0)
    s = medal_half + lg
    centres = []
    for r in seq:
        p, tg = at(s + r)
        centres.append((bead(p, tg, r), tg, r))
        s += 2 * r + gap
    (c0, tg0, r0), (c1, tg1, r1) = centres[0], centres[-1]
    link(c0 - tg0 * (r0 + AIR), medal_c + t0 * (medal_half + AIR) + up * zl)
    link(c1 + tg1 * (r1 + AIR), medal_c - t0 * (medal_half + AIR) + up * zl)
    # tail: out of the medal towards -Y, gently curving
    nrm = Vector((t0.y, -t0.x, 0)).normalized()
    if nrm.y > 0:
        nrm = -nrm
    pos = medal_c + nrm * (medal_b + AIR)
    d = nrm.copy()
    rot7 = Matrix.Rotation(math.radians(-11), 3, "Z")
    prev = None
    for i, r in enumerate((large, small, small, small, large)):
        d = (rot7 @ d).normalized()
        pos = pos + d * ((lg if i == 0 else gap) + r)
        c = bead(pos, d, r)
        if i == 0:
            link(c - d * (r + AIR), medal_c + nrm * (medal_b + AIR) + up * zl)
        prev = c
        pos = pos + d * r
    d = (rot7 @ d).normalized()
    eye_r = 0.2
    eye_far = pos + d * lg                           # outer edge of the crucifix eye ring
    link(prev + d * (large + AIR), eye_far - d * AIR + up * zl)
    beads = mesh(V, F, ["M_TimberDark", "M_Metal"], FM, name="beads", angle_smooth=179)
    me = beads.data
    if len(me.vertices) == len(NRM):              # bead shading as spheres (zero extra triangles)
        for p in me.polygons:
            p.use_smooth = True
        me.normals_split_custom_set_from_vertices([tuple(nv) for nv in NRM])
    else:
        print("ROSARY: vertex count changed, custom normals skipped")

    md = lathe([(0.0, 0.0), (0.74, 0.0), (0.72, 0.2), (0.0, 0.24)], 8, "M_Metal",
               name="medal", angle_smooth=50)
    xform(md, Matrix.Diagonal((1.0, medal_b / 0.75, 1.0, 1.0)))
    xform(md, Matrix.Rotation(math.atan2(t0.y, t0.x), 4, "Z"))
    move(md, medal_c)

    # crucifix in local coords: eye ring centred at x = -eye_r + 0.08 (overlaps the cross top),
    # long arm along +X; then rotated onto d with the eye's far edge at eye_far
    w = 0.25
    ln, arm, armx = 4.0, 1.3, 1.15
    outline = [(0, -w), (armx - w, -w), (armx - w, -arm), (armx + w, -arm), (armx + w, -w), (ln, -w),
               (ln, w), (armx + w, w), (armx + w, arm), (armx - w, arm), (armx - w, w), (0, w)]
    cr = slab(outline, 0.0, 0.22, "M_Metal", bevel=0.04, seg=1, name="cross", angle_smooth=40)
    zc = 0.22 + AIR - 0.02
    corpus = ball((armx + 0.65, 0, zc), 0.22, "M_Metal", u=6, v=3, scale=(3.2, 0.9, 0.9), name="corpus")
    carms = ball((armx, 0, zc), 0.14, "M_Metal", u=4, v=3, scale=(1.0, 6.0, 0.8), name="carms")
    ecx = -eye_r + 0.08
    eye = sweep([(ecx + eye_r * math.cos(2 * math.pi * i / 5), eye_r * math.sin(2 * math.pi * i / 5), zl)
                 for i in range(5)], 0.05, "M_Metal", res=1, bevel_res=0, cyclic=True, kind="POLY",
                name="eye", angle_smooth=89)
    cross = union(cr, [corpus, carms, eye], 40)
    xform(cross, Matrix.Rotation(math.atan2(d.y, d.x), 4, "Z"))
    move(cross, eye_far - d * (ecx - eye_r - 0.05))
    ob = join("SM_Rosary", [beads, md, cross])
    return pivot_bottom_centre(ob)


# ------------------------------------------------------------------ UVs, export, preview
def uvs(ob, margin=0.02):
    me = ob.data
    while len(me.uv_layers):
        me.uv_layers.remove(me.uv_layers[0])
    uv0 = me.uv_layers.new(name="UVMap")
    bm = bmesh.new()
    bm.from_mesh(me)
    layer = bm.loops.layers.uv[uv0.name]
    screen_idx = [i for i, m in enumerate(me.materials) if m and m.name == "M_Screen"]
    scr = [f for f in bm.faces if f.material_index in screen_idx]
    for f in bm.faces:
        n = f.normal
        ax = max(range(3), key=lambda i: abs(n[i]))
        for loop in f.loops:
            co = loop.vert.co
            loop[layer].uv = (co.y, co.z) if ax == 0 else (co.x, co.z) if ax == 1 else (co.x, co.y)
    if scr:   # screen gets a 0..1 planar map: u to the viewer's right, v up, seen from the front (+X).
        # A viewer at +X looking down -X has +Y (Blender) on the right, i.e. the case's Unreal +Y edge is
        # u = 0 and its Unreal -Y edge u = 1, so the readout texture is neither mirrored nor upside down.
        n = scr[0].normal
        udir = Vector((0, 0, 1)).cross(n).normalized()
        vdir = n.cross(udir).normalized()
        cos = [l.vert.co for f in scr for l in f.loops]
        us = [c.dot(udir) for c in cos]
        vs = [c.dot(vdir) for c in cos]
        for f in scr:
            for loop in f.loops:
                c = loop.vert.co
                loop[layer].uv = ((c.dot(udir) - min(us)) / (max(us) - min(us)),
                                  (c.dot(vdir) - min(vs)) / (max(vs) - min(vs)))
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
    me.uv_layers.active = me.uv_layers["UVMap"]      # (the uv0 reference goes stale once Lightmap exists)
    me.uv_layers["UVMap"].active_render = True


def export(ob):
    os.makedirs(EXPORT, exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.export_scene.fbx(filepath=os.path.join(EXPORT, f"{ob.name}.fbx"), use_selection=True,
                             apply_unit_scale=True, apply_scale_options="FBX_SCALE_UNITS", axis_forward="-Y",
                             axis_up="Z", mesh_smooth_type="FACE", add_leaf_bones=False)


def setup_render():
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.render.resolution_x, sc.render.resolution_y = 900, 700
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = False
    sc.render.image_settings.file_format = "PNG"
    sc.view_settings.view_transform = "Standard"
    sh = sc.display.shading
    sh.light = "STUDIO"
    sh.color_type = "MATERIAL"
    sh.show_cavity = True
    sh.cavity_type = "BOTH"
    sh.show_specular_highlight = True
    sh.show_object_outline = False
    sc.display.render_aa = "16"
    w = bpy.data.worlds.new("white")
    w.color = (1, 1, 1)
    sc.world = w
    cam_data = bpy.data.cameras.new("cam")
    cam_data.lens = 50
    cam = link("cam", cam_data)
    sc.camera = cam
    return cam


def preview(ob, cam, direction=(1.0, -0.8, 0.65), path=None):
    for o in bpy.context.scene.objects:
        if o.type == "MESH":
            o.hide_render = o is not ob
    pts = [ob.matrix_world @ v.co for v in ob.data.vertices]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    c = (lo + hi) / 2
    r = max((p - c).length for p in pts)
    d = Vector(direction).normalized()
    vfov = 2 * math.atan(18 * 700 / 900 / 50)
    dist = r / math.sin(vfov / 2) * 0.92
    cam.location = c + d * dist
    cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    cam.data.clip_start = dist * 0.01
    cam.data.clip_end = dist * 10
    bpy.context.scene.render.filepath = path or os.path.join(PREVIEW, f"{ob.name}.png")
    bpy.ops.render.render(write_still=True)


CLOCK_TEX = os.path.join(EXPORT, "T_DayDateClock_Screen.png")   # made by Items/make_clock_screen.py


def clock_preview(ob, cam):
    """Preview the clock with its readout texture on M_Screen (Base Color + 0.6 Emission). The image
    node is added AFTER the FBX export, so the FBX carries no texture reference: in Unreal the clock's
    M_Screen slot needs a per-instance override (MI_DayDateClockScreen with this texture), because the
    shared M_Screen name also drives the TV screen."""
    m = next(mm for mm in ob.data.materials if mm.name == "M_Screen")
    m.use_nodes = True
    nt = m.node_tree
    bsdf = next(nd for nd in nt.nodes if nd.type == "BSDF_PRINCIPLED")
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(CLOCK_TEX, check_existing=True)
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Emission Color"])
    bsdf.inputs["Emission Strength"].default_value = 0.6
    nt.nodes.active = tex
    sh = bpy.context.scene.display.shading
    sh.color_type = "TEXTURE"
    preview(ob, cam)
    preview(ob, cam, direction=(1.0, -0.12, 0.25), path=os.path.join(PREVIEW, "SM_DayDateClock_front.png"))
    sh.color_type = "MATERIAL"


def tri_count(ob):
    return sum(len(p.vertices) - 2 for p in ob.data.polygons)


BUILDERS = {
    "SM_RoundTable": round_table, "SM_Vase": vase, "SM_Jug": jug, "SM_Glass": glass,
    "SM_Hairbrush": hairbrush, "SM_CallBell": call_bell, "SM_DayDateClock": day_date_clock,
    "SM_Clipboard": clipboard, "SM_Madonna": madonna, "SM_Rosary": rosary,
}


def build():
    want = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    names = [n for n in BUILDERS if not want or n in want]
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    os.makedirs(PREVIEW, exist_ok=True)
    pieces = [BUILDERS[n]() for n in names]
    keep = set(pieces)
    for o in list(bpy.context.scene.objects):          # drop any helper leftovers
        if o not in keep:
            bpy.data.objects.remove(o, do_unlink=True)
    cam = setup_render()
    report = []
    for ob in pieces:
        uvs(ob)
        export(ob)
        if ob.name == "SM_DayDateClock":
            clock_preview(ob, cam)
        else:
            preview(ob, cam)
        lo, hi = bounds(ob)
        lo, hi = lo * 100, hi * 100
        report.append(f"{ob.name}: tris={tri_count(ob)} mats={[m.name for m in ob.data.materials]} "
                      f"bbox_cm=({lo.x:.1f},{lo.y:.1f},{lo.z:.2f})..({hi.x:.1f},{hi.y:.1f},{hi.z:.2f})")
    if not want:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ROOM, "Items", "tabletop.blend"))
    print("\n".join(["TABLETOP REPORT"] + report))


build()
