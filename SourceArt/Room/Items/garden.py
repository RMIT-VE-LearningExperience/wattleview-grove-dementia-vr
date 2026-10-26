"""Blender (headless): garden exterior + memory-scene garden props for Maria's room.

Run:
  "C:\\Program Files\\Blender Foundation\\Blender 5.0\\blender.exe" -b --factory-startup --python garden.py

Pieces
  Exterior (seen through the north window): SM_Lawn, SM_FlowerBed, SM_GardenTree_A (eucalypt),
  SM_GardenTree_B (upright-oval Callery pear), SM_Shrub, SM_Fence, SM_GardenBench.
  Memory scene (Maria's Italian kitchen garden): SM_TomatoPlant, SM_BasilPot, SM_FigTree, SM_GardenHose.

Follows SourceArt/Room/CONVENTIONS.md
  * Modelled in centimetres (Blender axes, so Unreal Y == -Blender Y), scaled 0.01 to metres on join.
    Front = local +X. Pivot bottom centre (lawn: centre of the ground sheet, top near z 0).
  * Real shapes, no boxes: tapered swept trunks/branches, noise-displaced leaf masses union-ed (Manifold
    boolean), voxel-remeshed and decimated once, with soft canopy normals transferred from a smooth hull;
    lathed pots/fittings/fruit, swept hose and ties, lobed / serrated / cupped leaves, bevelled timber.
    Parts that touch are boolean-unioned into one island; separate parts keep a 0.2 cm air gap.
  * UV0 'UVMap' = 1 m box projection (lawn: 2 m tiling). UV1 'Lightmap' = smart project per material
    group (raw and smoothed shape tried, fuller layout kept) + pack with 2 % margins (lawn: planar 0..1).
  * The lawn reads placement.json (read only): exactly z -0.2 within 145 cm of every flower bed (each
    bed's flat base sits 0.2 cm above it), +0.6 cm under trees, shrubs, fence and bench.

HANDOFF NOTES FOR UNREAL (material setup these meshes rely on)
  * M_Plant and M_PlantDark must be Two Sided: leaves, petals and calyces are single-sided sheets
    (SM_FlowerBed, SM_TomatoPlant, SM_BasilPot, SM_FigTree).
  * M_FlowerRed must take its base colour from VertexColor (neutral tint): SM_FlowerBed and
    SM_TomatoPlant carry a 'Col' vertex colour (exported sRGB) that holds the flower variety (red, cerise,
    pink, white geraniums; yellow, white, purple daisies), the ripe / orange tomatoes and the cream cloth
    ties, all on the one M_FlowerRed slot so each mesh stays within 4 slots. Other slots ignore it.
  * Foliage carries custom (soft, upward / canopy) normals: import with Normal Import Method = Import
    Normals (and keep tangents computed).
  * SM_GardenTree_A (gum) needs its own look on its instances to separate it from Tree B: a pale, smooth
    bark (about sRGB 0.62 / 0.58 / 0.52 - e.g. a pale-bark MI, or a new M_BarkPale slot if added to
    CONVENTIONS) and a grey-olive tint on its M_Plant (sunlit crown top) / M_PlantDark. The previews use
    preview-only overrides (PREVIEW_TINT) to show that read; the FBX keeps the convention slots.
  * SM_TomatoPlant carries a darker green 'Col' on ~30 % of its leaflets: only visible if M_Plant reads
    VertexColor (optional; ignored otherwise).
Overview only (no rebuild / re-export): ... --python garden.py -- --overview-only
Exports Export/SM_<Name>.fbx, Previews/SM_<Name>.png and Previews/Assembly_garden/garden_*.png.
Rebuild one piece: ... --python garden.py -- SM_TomatoPlant  (no overview renders then).
"""
import json
import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector, noise
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

ROOM = r"D:\Unreal-Projects\WattleviewGrove-ue58\SourceArt\Room"
EXPORT = os.path.join(ROOM, "Export")
PREVIEW = os.path.join(ROOM, "Previews")
OVERVIEW = os.path.join(PREVIEW, "Assembly_garden")
GAP = 0.2
sys.path.insert(0, os.path.join(ROOM, "Tools"))
from palette import PALETTE  # noqa: E402

LOG = []


def log(msg):
    LOG.append(msg)
    print("GARDEN " + msg)


# ------------------------------------------------------------------ basics
def mat(name):
    m = bpy.data.materials.get(name)
    if m is None:
        m = bpy.data.materials.new(name)
        col = (*PALETTE[name], 1.0)
        m.diffuse_color = col
        m.roughness = 0.7
        try:
            m.use_nodes = True
            bsdf = m.node_tree.nodes.get("Principled BSDF")
            if bsdf:
                bsdf.inputs["Base Color"].default_value = col
        except Exception:
            pass
    return m


def link(name, data):
    ob = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def bake(ob):
    """Apply all modifiers (or convert a curve) into a plain mesh object."""
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    new = link(ob.name, me)
    new.matrix_world = ob.matrix_world.copy()
    data = ob.data
    bpy.data.objects.remove(ob, do_unlink=True)
    if isinstance(data, bpy.types.Curve) and data.users == 0:
        bpy.data.curves.remove(data)
    elif isinstance(data, bpy.types.Mesh) and data.users == 0:
        bpy.data.meshes.remove(data)
    return new


def set_mat(ob, m):
    ob.data.materials.clear()
    ob.data.materials.append(mat(m))
    return ob


def smooth(ob, angle=40.0, recalc=True):
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


def bm_obj(bm, name, m, angle=40.0, recalc=True):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = link(name, me)
    set_mat(ob, m)
    return smooth(ob, angle, recalc)


def frame(direction, up=(0, 0, 1), roll=0.0):
    """Rotation taking local +X to `direction`, local +Z as close to `up` as possible."""
    x = Vector(direction).normalized()
    u = Vector(up).normalized()
    if abs(x.dot(u)) > 0.995:
        u = Vector((1, 0, 0)) if abs(x.x) < 0.9 else Vector((0, 1, 0))
    z = (u - x * u.dot(x)).normalized()
    y = z.cross(x)
    m = Matrix((x, y, z)).transposed().to_4x4()
    return m @ Matrix.Rotation(roll, 4, "X")


def place(ob, pos, direction, up=(0, 0, 1), roll=0.0):
    return xform(ob, Matrix.Translation(Vector(pos)) @ frame(direction, up, roll))


def tri_count(ob):
    return sum(len(p.vertices) - 2 for p in ob.data.polygons)


def nonmanifold(me):
    bm = bmesh.new()
    bm.from_mesh(me)
    n = sum(1 for e in bm.edges if not e.is_manifold)
    bm.free()
    return n


def bounds(ob):
    vs = [v.co for v in ob.data.vertices]
    lo = Vector((min(v.x for v in vs), min(v.y for v in vs), min(v.z for v in vs)))
    hi = Vector((max(v.x for v in vs), max(v.y for v in vs), max(v.z for v in vs)))
    return lo, hi


# ------------------------------------------------------------------ primitives
def lathe(profile, seg, m, name="lathe", angle_smooth=40.0):
    """Revolve a closed (r, z) profile (ends on the axis) around Z with the Screw modifier."""
    verts = [(r, 0.0, z) for r, z in profile]
    edges = [(i, i + 1) for i in range(len(verts) - 1)]
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, edges, [])
    ob = link(name, me)
    mod = ob.modifiers.new("screw", "SCREW")
    mod.axis = "Z"
    mod.angle = math.radians(360)
    mod.steps = seg
    mod.render_steps = seg
    mod.use_merge_vertices = True
    mod.merge_threshold = 1e-3
    mod.use_normal_calculate = True
    ob = bake(ob)
    set_mat(ob, m)
    return smooth(ob, angle_smooth)


def sweep(points, m, radii, res=3, bevel_res=1, kind="BEZIER", name="sweep", angle_smooth=70.0,
          bevel_obj=None, caps=True):
    """Sweep a round section along a curve through `points` (cm); radii are per-point radii in cm."""
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.resolution_u = res
    cu.twist_mode = "MINIMUM"
    if bevel_obj is not None:
        cu.bevel_mode = "OBJECT"
        cu.bevel_object = bevel_obj
    else:
        cu.bevel_depth = 1.0
        cu.bevel_resolution = bevel_res
    cu.use_fill_caps = caps
    sp = cu.splines.new(kind)
    if kind == "BEZIER":
        sp.bezier_points.add(len(points) - 1)
        for i, p in enumerate(points):
            bp = sp.bezier_points[i]
            bp.co = Vector(p)
            bp.handle_left_type = bp.handle_right_type = "AUTO"
            bp.radius = radii[i]
    else:
        sp.points.add(len(points) - 1)
        for i, p in enumerate(points):
            sp.points[i].co = (*p, 1.0)
            sp.points[i].radius = radii[i]
    ob = link(name, cu)
    ob = bake(ob)
    set_mat(ob, m)
    return smooth(ob, angle_smooth)


def rounded_rect(w, h, r, n=3):
    pts = []
    for cx, cy, a0 in ((w / 2 - r, h / 2 - r, 0), (-w / 2 + r, h / 2 - r, 90),
                       (-w / 2 + r, -h / 2 + r, 180), (w / 2 - r, -h / 2 + r, 270)):
        for i in range(n + 1):
            a = math.radians(a0 + 90 * i / n)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def slab(outline, z0, z1, m, bevel=0.0, seg=1, name="slab", angle_smooth=40.0):
    """Extrude a 2D outline (cm, XY) from z0 to z1 and bevel its rim edges."""
    bm = bmesh.new()
    vs = [bm.verts.new((u, v, z0)) for u, v in outline]
    f = bm.faces.new(vs)
    ext = bmesh.ops.extrude_face_region(bm, geom=[f])
    nv = [g for g in ext["geom"] if isinstance(g, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, verts=nv, vec=(0, 0, z1 - z0))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    if bevel > 0:
        caps = [fc for fc in bm.faces if len(fc.verts) > 4 or abs(fc.normal.z) > 0.99]
        rim = {e for fc in caps for e in fc.edges}
        bmesh.ops.bevel(bm, geom=list(rim), offset=bevel, segments=seg, profile=0.5,
                        affect="EDGES", clamp_overlap=True)
    return bm_obj(bm, name, m, angle_smooth)


def bbox(size, m, bevel=0.4, seg=1, name="box", angle_smooth=40.0):
    """Bevelled box centred on the origin (size in cm)."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2]))
    if bevel > 0:
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=bevel, segments=seg, profile=0.5,
                        affect="EDGES", clamp_overlap=True)
    return bm_obj(bm, name, m, angle_smooth)


def beam(p0, p1, w_side, h, m, bevel=0.5, seg=1, up=(0, 1, 0), name="beam"):
    """Bevelled timber member from p0 to p1: h across in the plane, w_side along `up`."""
    p0, p1 = Vector(p0), Vector(p1)
    d = p1 - p0
    ob = bbox((d.length, h, w_side), m, bevel, seg, name)
    return place(ob, (p0 + p1) / 2, d, up)


def blob(c, r, m, scale=(1, 1, 1), sub=2, rough=0.22, freq=1.5, seed=0, squash=0.0, name="blob"):
    """Irregular leaf mass: icosphere displaced by two octaves of Perlin noise."""
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=sub, radius=1.0)
    off = Vector((seed * 7.31 + 1.3, seed * 3.17 - 2.1, seed * 5.53 + 0.7))
    for v in bm.verts:
        n = v.co.normalized()
        d = 1.0 + rough * noise.noise(n * freq + off) + rough * 0.5 * noise.noise(n * freq * 2.6 + off * 1.7)
        p = n * d
        if p.z < 0:
            p.z *= (1.0 - squash)
        v.co = Vector((p.x * r * scale[0], p.y * r * scale[1], p.z * r * scale[2])) + Vector(c)
    return bm_obj(bm, name, m, angle=180.0)


def fan_leaf(outline, centre, m, thick=0.3, cup=0.0, droop=0.0, name="leaf"):
    """Thin closed leaf: outline (x, y) in the leaf plane, base at the origin pointing +X.
    Top and bottom surfaces are fans around `centre`, sharing the outline (a lens section)."""
    xs = [p[0] for p in outline]
    L = max(xs) - min(xs)
    W = max(abs(p[1]) for p in outline) or 1.0

    def z_of(x, y):
        return cup * W * (y / W) ** 2 - droop * L * (x / L) ** 2

    bm = bmesh.new()
    ring = [bm.verts.new((x, y, z_of(x, y))) for x, y in outline]
    cx, cy = centre
    zc = z_of(cx, cy)
    top = bm.verts.new((cx, cy, zc + thick / 2))
    bot = bm.verts.new((cx, cy, zc - thick / 2))
    n = len(ring)
    for i in range(n):
        a, b = ring[i], ring[(i + 1) % n]
        bm.faces.new((top, a, b))
        bm.faces.new((bot, b, a))
    return bm_obj(bm, name, m, angle=75.0)


def oval_leaf(length, width, m, side=3, thick=0.25, cup=0.12, droop=0.08, tip=0.8, name="leaf"):
    pts = [(0.0, 0.0)]
    for k in range(1, side + 1):
        u = k / (side + 1)
        w = width / 2 * math.sin(math.pi * u ** tip) ** 0.85
        pts.append((u * length, -w))
    pts.append((length, 0.0))
    for k in range(side, 0, -1):
        u = k / (side + 1)
        w = width / 2 * math.sin(math.pi * u ** tip) ** 0.85
        pts.append((u * length, w))
    return fan_leaf(pts, (0.45 * length, 0.0), m, thick, cup, droop, name)


def fig_leaf(size, m, n=16, thick=0.35, cup=0.10, droop=0.10, name="figleaf"):
    """Palmate, deeply 5-lobed fig leaf; `size` = lobe-tip radius (cm). Lobe tips sit on outline samples."""
    step = 2 * math.pi / n
    k1, k2 = round(n * 75 / 360), round(n * 135 / 360)
    lobes = [(0.0, 1.0), (k1 * step, 0.85), (-k1 * step, 0.85), (k2 * step, 0.55), (-k2 * step, 0.55)]
    pts = []
    for i in range(n):
        phi = -math.pi + 2 * math.pi * i / n
        f = 0.0
        for pc, a in lobes:
            dphi = math.atan2(math.sin(phi - pc), math.cos(phi - pc))
            f = max(f, a * math.exp(-(dphi / 0.33) ** 2))
        r = size * (0.30 + 0.70 * f)
        pts.append((r * math.cos(phi), r * math.sin(phi)))
    sx = -pts[0][0]
    pts = [(x + sx, y) for x, y in pts]
    return fan_leaf(pts, (sx, 0.0), m, thick, cup, droop, name)


def union(parts, name="union", angle=75.0):
    """Boolean-union closed meshes into one island (Manifold solver, Exact as fallback)."""
    parts = [p for p in parts if p is not None]
    base = parts[0]
    if len(parts) == 1:
        base.name = name
        return base
    bad = [p.name for p in parts if nonmanifold(p.data)]
    tin = sum(tri_count(p) for p in parts)
    lo = Vector((1e9,) * 3)
    hi = Vector((-1e9,) * 3)
    for p in parts:
        a, b = bounds(p)
        lo = Vector(map(min, lo, a))
        hi = Vector(map(max, hi, b))
    col = bpy.data.collections.new(name + "_ops")
    for p in parts[1:]:
        for c in list(p.users_collection):
            c.objects.unlink(p)
        col.objects.link(p)
    mod = base.modifiers.new("u", "BOOLEAN")
    mod.operation = "UNION"
    mod.operand_type = "COLLECTION"
    mod.collection = col
    mod.material_mode = "TRANSFER"
    result = None
    for solver in (("MANIFOLD", "EXACT") if not bad else ("EXACT",)):
        mod.solver = solver
        dg = bpy.context.evaluated_depsgraph_get()
        me = bpy.data.meshes.new_from_object(base.evaluated_get(dg))
        ok = len(me.polygons) > 0
        if ok:
            vs = [v.co for v in me.vertices]
            rlo = Vector((min(v.x for v in vs), min(v.y for v in vs), min(v.z for v in vs)))
            rhi = Vector((max(v.x for v in vs), max(v.y for v in vs), max(v.z for v in vs)))
            ok = (rlo - lo).length < 0.05 and (rhi - hi).length < 0.05
        if ok:
            result = me
            if solver != "MANIFOLD":
                log(f"union {name}: used {solver} (non-manifold inputs: {bad[:5]})")
            break
        bpy.data.meshes.remove(me)
    if result is None:
        raise RuntimeError("union failed: " + name)
    base.modifiers.remove(mod)
    old = base.data
    base.data = result
    if old.users == 0:
        bpy.data.meshes.remove(old)
    for p in list(col.objects):
        d = p.data
        bpy.data.objects.remove(p, do_unlink=True)
        if d.users == 0:
            bpy.data.meshes.remove(d)
    bpy.data.collections.remove(col)
    base.name = name
    smooth(base, angle)
    log(f"union {name}: {len(parts)} parts, {tin} tris in -> {tri_count(base)} out")
    return base


def decimate(ob, target, angle=75.0):
    t = tri_count(ob)
    if t <= target:
        return ob
    mod = ob.modifiers.new("d", "DECIMATE")
    mod.decimate_type = "COLLAPSE"
    mod.ratio = target / t
    mod.use_collapse_triangulate = True
    return smooth(bake(ob), angle)


class Collider:
    """Placed geometry for rejection-sampling leaves so they never pass through each other."""

    def __init__(self):
        self.items = []

    @staticmethod
    def _entry(ob, tag=None):
        me = ob.data
        tree = BVHTree.FromPolygons([v.co.copy() for v in me.vertices], [tuple(p.vertices) for p in me.polygons])
        lo, hi = bounds(ob)
        return (lo, hi, tree, tag)

    def add(self, ob, tag=None):
        self.items.append(self._entry(ob, tag))
        return ob

    def hits(self, ob, ignore=None, pad=0.3):
        lo, hi, tree, _ = self._entry(ob)
        for a, b, t, tag in self.items:
            if ignore is not None and tag == ignore:
                continue
            if all(lo[i] - pad <= b[i] and a[i] - pad <= hi[i] for i in range(3)) and tree.overlap(t):
                return True
        return False


def try_place(col, make, attempts=8, ignore=None, tag=None):
    """make(k) builds candidate k; keep the first that clears everything in `col`, else None."""
    for k in range(attempts):
        ob = make(k)
        if ob is None:
            continue
        if not col.hits(ob, ignore):
            col.add(ob, tag)
            return ob
        d = ob.data
        bpy.data.objects.remove(ob, do_unlink=True)
        bpy.data.meshes.remove(d)
    return None


def surface_z(ob, x, y, top=10000.0):
    """Highest surface point of `ob` under (x, y) (cm), or None."""
    me = ob.data
    tree = BVHTree.FromPolygons([v.co for v in me.vertices], [tuple(p.vertices) for p in me.polygons])
    hit = tree.ray_cast(Vector((x, y, top)), Vector((0, 0, -1)), top * 2)
    return hit[0].z if hit[0] is not None else None


def join(name, parts):
    """Join parts, scale cm -> m, name object and data."""
    parts = [p for p in parts if p is not None]
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


def grow(rng, start, direction, length, nseg, wobble=0.18, lift=0.0, droop=0.0):
    """Points of a gently wandering limb."""
    pts = [Vector(start)]
    d = Vector(direction).normalized()
    step = length / nseg
    for i in range(nseg):
        j = Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1))) * wobble
        d = (d + j + Vector((0, 0, lift - droop * (i + 1) / nseg))).normalized()
        pts.append(pts[-1] + d * step)
    return pts


def taper(n, r0, r1, power=1.0):
    return [r0 + (r1 - r0) * (i / (n - 1)) ** power for i in range(n)]


def polar_dir(az_deg, el_deg):
    a, e = math.radians(az_deg), math.radians(el_deg)
    return Vector((math.cos(a) * math.cos(e), math.sin(a) * math.cos(e), math.sin(e)))


def at_fraction(pts, f):
    """Point and index along a polyline at fraction f of its points."""
    k = f * (len(pts) - 1)
    i = min(int(k), len(pts) - 2)
    t = k - i
    return pts[i].lerp(pts[i + 1], t), i


# ------------------------------------------------------------------ SM_Lawn
LAWN_FOOT = {   # half extents (cm) of each exterior piece's footprint, local X/Y
    "SM_FlowerBed": (45, 150), "SM_Fence": (7, 150), "SM_GardenBench": (34, 77),
    "SM_GardenTree_A": (25, 25), "SM_GardenTree_B": (25, 25), "SM_Shrub": (55, 55), "SM_FigTree": (36, 36),
    "SM_Fence_EndPost": (5, 5),
}


def lawn():
    """2500 x 3500 ground sheet on a 1 m grid, +-7.5 cm Perlin undulation. Flattened under every exterior
    piece from placement.json (read only): exactly z -0.2 within 145 cm of each flower bed (so each bed's
    flat base sits 0.2 cm above the turf, never in it; any grid cell under a bed is fully flat), and
    +0.6 cm within 110 cm of trees, shrubs, fence and bench (planted 0.6 cm into the turf)."""
    cfg = json.load(open(os.path.join(ROOM, "placement.json")))
    lp = next(p for p in cfg["pieces"] if p["mesh"] == "SM_Lawn")
    lx, ly = lp["loc"][0], lp["loc"][1]
    feats, beds = [], []
    for p in cfg["pieces"]:
        on_lawn = p.get("kind") == "exterior" or (p.get("kind") == "overlay" and p["loc"][2] <= -10)
        if on_lawn and p["mesh"] in LAWN_FOOT:
            hx, hy = LAWN_FOOT[p["mesh"]]
            f = (p["loc"][0] - lx, p["loc"][1] - ly, math.radians(p.get("yaw", 0)), hx, hy)
            (beds if p["mesh"] == "SM_FlowerBed" else feats).append(f)
    HX, HY, STEP = 1250.0, 1750.0, 100.0

    def smoothstep(t):
        t = max(0.0, min(1.0, t))
        return t * t * (3 - 2 * t)

    def sdist(ux, uy, fs):
        dmin = 1e9
        for fx, fy, yaw, hx, hy in fs:
            dx, dy = ux - fx, uy - fy
            c, s = math.cos(-yaw), math.sin(-yaw)
            qx, qy = abs(c * dx - s * dy) - hx, abs(s * dx + c * dy) - hy
            dmin = min(dmin, math.hypot(max(qx, 0), max(qy, 0)) + min(max(qx, qy), 0))
        return dmin

    def height(ux, uy):   # Unreal-local cm
        und = 9.0 * noise.noise(Vector((ux / 950.0, uy / 950.0, 0.37))) + \
            3.5 * noise.noise(Vector((ux / 380.0 + 4.1, uy / 380.0 - 2.3, 1.9)))
        und = max(-7.5, min(7.5, und))
        db = sdist(ux, uy, beds)
        wbed = smoothstep((db - 145.0) / 110.0)        # 0 within 145 cm of a bed
        wf = min(smoothstep((sdist(ux, uy, feats) - 110.0) / 160.0), smoothstep((db - 145.0) / 160.0))
        wb = smoothstep((ux + HX - 40.0) / 220.0)      # 0 against the building wall
        flat = -0.2 * (1.0 - wbed) + 0.6 * wbed
        w = wf * wb
        return w * und + (1.0 - w) * flat

    nx, ny = int(2 * HX / STEP), int(2 * HY / STEP)
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    lml = bm.loops.layers.uv.new("Lightmap")
    grid = []
    for j in range(ny + 1):
        row = []
        for i in range(nx + 1):
            ux, uy = -HX + i * STEP, -HY + j * STEP
            row.append(bm.verts.new((ux, -uy, height(ux, uy))))
        grid.append(row)
    for j in range(ny):
        for i in range(nx):
            f = bm.faces.new((grid[j][i], grid[j + 1][i], grid[j + 1][i + 1], grid[j][i + 1]))
            for lp_ in f.loops:
                x, y = lp_.vert.co.x, -lp_.vert.co.y
                lp_[uvl].uv = (x / 200.0, y / 200.0)
                lp_[lml].uv = (0.02 + 0.96 * (x + HX) / (2 * HX), 0.02 + 0.96 * (y + HY) / (2 * HY))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    if bm.faces[0].normal.z < 0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces)
    zs = [v.co.z for v in bm.verts]
    log(f"lawn height range {min(zs):.2f}..{max(zs):.2f} cm")
    ob = bm_obj(bm, "lawn", "M_Grass", angle=180.0, recalc=False)
    ob = join("SM_Lawn", [ob])
    ob["custom_uv"] = True
    return ob


def cluster(c, r, rng, core="M_PlantDark", lumps=("M_Plant", "M_PlantDark"), n=5, scale=(1, 1, 0.85),
            hang=0.0, seed=0, rough=0.24):
    """Leaf mass: a core with smaller noisy lumps bulging out of it (irregular silhouette)."""
    c = Vector(c)
    out = [blob(c, r * 0.72, core, scale, sub=2, rough=0.2, freq=1.6, seed=seed * 13 + 1, squash=0.25,
                name="core")]
    for i in range(n):
        a = rng.uniform(0, 2 * math.pi)
        z = rng.uniform(-0.55 - hang, 0.85)
        d = Vector((math.cos(a), math.sin(a), 0)) * math.sqrt(max(0.0, 1 - z * z)) + Vector((0, 0, z))
        p = c + Vector((d.x * scale[0], d.y * scale[1], d.z * scale[2])) * r * rng.uniform(0.45, 0.6)
        rr = r * rng.uniform(0.3, 0.46)
        out.append(blob(p, rr, lumps[i % len(lumps)], (1, 1, 0.9), sub=2, rough=rough, freq=2.0,
                        seed=seed * 13 + i + 2, squash=0.2, name="lump"))
    return out


# ------------------------------------------------------------------ low-poly plant parts (revision 1)
def bend_down(ob, deg):
    """Curl a leaf (base at the origin, pointing +X, top surface +Z) downward with a SimpleDeform BEND.
    The modifier bends about its Z axis, so the leaf is turned on its side for the deform and back after."""
    xform(ob, Matrix.Rotation(math.radians(90), 4, "X"))
    mod = ob.modifiers.new("bend", "SIMPLE_DEFORM")
    mod.deform_method = "BEND"
    mod.deform_axis = "Z"
    mod.angle = math.radians(deg)
    ob = bake(ob)
    xform(ob, Matrix.Rotation(math.radians(-90), 4, "X"))
    return ob


def strip_leaf(L, W, m, prof=((0.3, 0.9), (0.66, 0.8)), crease=0.35, thick=0.12, bend=40.0, name="leaf"):
    """Closed thin leaf from a 2-wide quad strip: pointed base at the origin, tip at +X, two cross rows.
    The midrib vertex sits `crease` below the rim (V fold); top and bottom share the rim (lens section).
    16 triangles. Curled down with a SimpleDeform BEND of `bend` degrees."""
    bm = bmesh.new()
    base = bm.verts.new((0.0, 0.0, 0.0))
    tip = bm.verts.new((L, 0.0, 0.0))
    rows = []
    for u, wf in prof:
        w = W * wf / 2
        rows.append((bm.verts.new((u * L, -w, 0.0)),
                     bm.verts.new((u * L, 0.0, -crease * wf + thick / 2)),
                     bm.verts.new((u * L, 0.0, -crease * wf - thick / 2)),
                     bm.verts.new((u * L, w, 0.0))))
    for mi, flip in ((1, False), (2, True)):
        fs = []
        l0, m0, r0 = rows[0][0], rows[0][mi], rows[0][3]
        fs += [(base, m0, l0), (base, r0, m0)]
        for a, b in zip(rows[:-1], rows[1:]):
            fs += [(a[0], a[mi], b[mi], b[0]), (a[mi], a[3], b[3], b[mi])]
        lk, mk, rk = rows[-1][0], rows[-1][mi], rows[-1][3]
        fs += [(lk, mk, tip), (mk, rk, tip)]
        for f in fs:
            bm.faces.new(tuple(reversed(f)) if flip else f)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = bm_obj(bm, name, m, angle=60.0)
    if bend:
        ob = bend_down(ob, bend)
        set_mat(ob, m)
        smooth(ob, 60.0)
    return ob


def tri_profile(name="tri_profile"):
    """Unit triangle used as a curve bevel object (3-sided stalks)."""
    cu = bpy.data.curves.new(name, "CURVE")
    sp = cu.splines.new("POLY")
    sp.points.add(2)
    for k in range(3):
        a = 2 * math.pi * k / 3 + math.pi / 2
        sp.points[k].co = (math.cos(a), math.sin(a), 0.0, 1.0)
    sp.use_cyclic_u = True
    return link(name, cu)


def drop_curve_obj(ob):
    cu = ob.data
    bpy.data.objects.remove(ob, do_unlink=True)
    if cu.users == 0:
        bpy.data.curves.remove(cu)


def ball(c, r, m, seg=6, rings=3, name="ball"):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=rings, radius=r)
    ob = bm_obj(bm, name, m, angle=80.0)
    return move(ob, c)


def daisy_head(R, npet, m_pet, m_ctr, cup=0.55, thick=0.15, rng=None):
    """Daisy: closed petal disc (n-gon fan; each petal = two blunt tip verts, notches pulled in to 35 %),
    cupped upward, with a 1 cm domed centre resting 0.25 cm above it. Built facing +Z at the origin."""
    rng = rng or random.Random(0)
    bm = bmesh.new()
    ring = []
    step = 2 * math.pi / npet
    for k in range(npet):
        a0 = k * step
        rr = R * rng.uniform(0.9, 1.05)
        for a, r in ((a0 - 0.2 * step, rr), (a0 + 0.2 * step, rr), (a0 + 0.5 * step, 0.35 * R)):
            ring.append(bm.verts.new((r * math.cos(a), r * math.sin(a), cup * (r / R) ** 2)))
    top = bm.verts.new((0, 0, thick / 2))
    bot = bm.verts.new((0, 0, -thick / 2))
    n = len(ring)
    for i in range(n):
        a, b = ring[i], ring[(i + 1) % n]
        bm.faces.new((top, a, b))
        bm.faces.new((bot, b, a))
    disc = bm_obj(bm, "petals", m_pet, angle=70.0)
    ctr = lathe([(0, 0.42), (0.38, 0.32), (0.5, 0.0), (0, 0.0)], 6, m_ctr, name="disc_centre", angle_smooth=80)
    move(ctr, (0, 0, thick / 2 + 0.25))
    return disc, ctr


def floret5(R, m, cup=0.3, rng=None, name="floret"):
    """Geranium floret: flat 5-petal fan facing +Z, one wedge triangle per petal from a shared centre
    (5 tris), each petal spanning 54 of its 72 deg so the notches between petals read; tips cupped up."""
    rng = rng or random.Random(0)
    bm = bmesh.new()
    c = bm.verts.new((0.0, 0.0, 0.0))
    a0 = rng.uniform(0, 2 * math.pi)
    for k in range(5):
        a = a0 + 2 * math.pi * k / 5
        r = R * rng.uniform(0.9, 1.08)
        v1 = bm.verts.new((r * math.cos(a - 0.47), r * math.sin(a - 0.47), cup))
        v2 = bm.verts.new((r * math.cos(a + 0.47), r * math.sin(a + 0.47), cup))
        bm.faces.new((c, v1, v2))
    return bm_obj(bm, name, m, angle=80.0, recalc=False)


# ------------------------------------------------------------------ SM_FlowerBed
def flower_bed():
    """Raised timber bed 90 x 300 (long axis local Y), soil, a 2 cm soil berm round the base, and a dense,
    mixed planting in ONE mesh (4 slots: M_Timber, M_Soil, M_Plant, M_FlowerRed):
      * 22 plants in three staggered rows (x -24, 0, +24) at 36-42 cm pitch, each its own clump that
        touches but never passes through its neighbours: a low displaced core (20 tris) covered by 6
        leaves - zonal geraniums get rounded, scalloped, cupped leaves (a flat crown leaf plus 5 pitched
        20-50 deg down-and-out over the core), daisies get 6 strap leaves fanning up and out;
      * flower heads 3-8 cm above the foliage on 3-sided stalks, placed round-robin under the 3k budget:
        a geranium umbel is one flattened, jittered, flat-bottomed icosphere ball (18 tris, 4-5.5 cm
        radius), a daisy is an 8-tri disc with a 6-tri raised eye.
    Flower variety is a vertex colour ('Col', exported sRGB) on the one M_FlowerRed slot: red, cerise,
    pink and white geraniums; yellow, white and purple daisies (gold / brown eyes). The review tools
    colour M_FlowerRed flat red; Previews/SM_FlowerBed.png and Assembly_garden/garden_bed_close_vertexcolour
    show the real mix.
    Unreal: M_FlowerRed must use VertexColor as its base colour; M_Plant must be Two Sided (leaves and
    petals are single-sided sheets). All parts are placed against one collider: nothing touches another
    part, the soil or the boards."""
    rng = random.Random(11)
    T, H1, H2 = 4.5, 14.8, 29.8          # board thickness, course tops
    parts = []
    for sx in (1, -1):
        b = bbox((T, 300.0, H1), "M_Timber", 0.5, 1, "board")
        parts.append(move(b, (sx * (45 - T / 2), 0, H1 / 2)))
    for sy in (1, -1):
        b = bbox((90 - 2 * T - 2 * GAP, T, H1), "M_Timber", 0.5, 1, "board")
        parts.append(move(b, (0, sy * (150 - T / 2), H1 / 2)))
    z0 = H1 + GAP
    for sy in (1, -1):
        b = bbox((90.0, T, H2 - z0), "M_Timber", 0.5, 1, "board")
        parts.append(move(b, (0, sy * (150 - T / 2), (z0 + H2) / 2)))
    for sx in (1, -1):
        b = bbox((T, 300 - 2 * T - 2 * GAP, H2 - z0), "M_Timber", 0.5, 1, "board")
        parts.append(move(b, (sx * (45 - T / 2), 0, (z0 + H2) / 2)))

    # soil berm: closed ring hugging the board base (0.2 cm clear), flared 3.5-4.5 cm out, 1.6-2.4 cm high
    path = []
    for (cx, cy, a0) in ((45, 150, 0), (-45, 150, 90), (-45, -150, 180), (45, -150, 270)):
        for k in range(2):
            a = math.radians(a0 + 30 + 30 * k)
            path.append((Vector((cx, cy, 0)), Vector((math.cos(a), math.sin(a), 0))))
        # points along the following side
        nxt = {0: [(0, 150)], 90: [(-45, 75), (-45, 0), (-45, -75)],
               180: [(0, -150)], 270: [(45, -75), (45, 0), (45, 75)]}[a0]
        nrm = Vector((math.cos(math.radians(a0 + 90)), math.sin(math.radians(a0 + 90)), 0))
        for px, py in nxt:
            path.append((Vector((px, py, 0)), nrm))
    bm = bmesh.new()
    sec = []
    for p, nrm in path:
        out = rng.uniform(3.5, 4.5)
        h = rng.uniform(1.6, 2.4)
        sec.append((bm.verts.new(p + nrm * 0.2), bm.verts.new(p + nrm * out),
                    bm.verts.new(p + nrm * 0.2 + Vector((0, 0, h)))))
    n = len(sec)
    for i in range(n):
        a, b = sec[i], sec[(i + 1) % n]
        for k in range(3):
            bm.faces.new((a[k], a[(k + 1) % 3], b[(k + 1) % 3], b[k]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    berm = bm_obj(bm, "berm", "M_Soil", angle=60.0)

    # soil: closed slab, gently domed lumpy top
    SX, SY = 45 - T - GAP, 150 - T - GAP
    nx, ny = 2, 8

    def soil_z(x, y):
        return 24.0 + 2.6 * (1 - (x / SX) ** 2) * (1 - abs(y / SY) ** 6) + \
            0.5 * noise.noise(Vector((x / 14.0, y / 14.0, 3.3)))

    bm = bmesh.new()
    top = [[bm.verts.new((-SX + 2 * SX * i / nx, -SY + 2 * SY * j / ny, 0)) for i in range(nx + 1)]
           for j in range(ny + 1)]
    for row in top:
        for v in row:
            v.co.z = soil_z(v.co.x, v.co.y)
    for j in range(ny):
        for i in range(nx):
            bm.faces.new((top[j][i], top[j][i + 1], top[j + 1][i + 1], top[j + 1][i]))
    loop = [top[0][i] for i in range(nx + 1)] + [top[j][nx] for j in range(1, ny + 1)] + \
        [top[ny][i] for i in range(nx - 1, -1, -1)] + [top[j][0] for j in range(ny - 1, 0, -1)]
    bot = [bm.verts.new((v.co.x, v.co.y, 0.6)) for v in loop]
    n = len(loop)
    for k in range(n):
        bm.faces.new((loop[k], bot[k], bot[(k + 1) % n], loop[(k + 1) % n]))
    bm.faces.new(list(reversed(bot)))
    bmesh.ops.triangulate(bm, faces=bm.faces, quad_method="FIXED", ngon_method="BEAUTY")   # fixed split = what FBX ships
    soil = bm_obj(bm, "soil", "M_Soil", angle=60.0)
    stree = BVHTree.FromPolygons([v.co.copy() for v in soil.data.vertices],
                                 [tuple(p.vertices) for p in soil.data.polygons])

    def ground(x, y):
        hit = stree.ray_cast(Vector((x, y, 100.0)), Vector((0, 0, -1)), 200.0)
        return hit[0].z if hit[0] is not None else 24.0

    def conform(ob):
        """Keep foliage inside the boards and at least 0.35 cm above the soil."""
        for v in ob.data.vertices:
            v.co.x = max(-SX + 0.6, min(SX - 0.6, v.co.x))
            v.co.y = max(-SY + 0.6, min(SY - 0.6, v.co.y))
            fl = ground(v.co.x, v.co.y) + 0.35
            if v.co.z < fl:
                v.co.z = fl
        return ob

    def conform_leaf(ob):
        """Below the board tops keep foliage inside the boards; above them a leaf may spill over the rim
        (to +-48.5 / +-153.5). Everything stays at least 0.35 cm above the soil."""
        for v in ob.data.vertices:
            if v.co.z < H2 + 0.8:
                v.co.x = max(-SX + 0.6, min(SX - 0.6, v.co.x))
                v.co.y = max(-SY + 0.6, min(SY - 0.6, v.co.y))
            else:
                v.co.x = max(-48.5, min(48.5, v.co.x))
                v.co.y = max(-153.5, min(153.5, v.co.y))
            fl = ground(v.co.x, v.co.y) + 0.35
            if v.co.z < fl:
                v.co.z = fl
        return ob

    col = Collider()
    col.add(soil, "soil")
    for b in parts:
        col.add(b, "board")
    prof = tri_profile()
    counts = {"geranium": 0, "daisy": 0, "leaf": 0, "head": 0}
    tris = {"core": 0, "leaf": 0, "head": 0, "stalk": 0}

    # ---- planting: every plant is its own clump (low displaced core + leaves round its upper half),
    # plants touch but never pass through each other; flower heads on short stalks above the foliage
    plants = []
    for rx, y_first, n_row, pitch in ((-24.0, -127.0, 8, 36.3), (0.0, -109.0, 7, 36.3), (24.0, -127.0, 7, 42.3)):
        for k in range(n_row):
            plants.append((rx + rng.uniform(-3.5, 3.5), y_first + pitch * k + rng.uniform(-3.5, 3.5)))
    specs = []
    for idx, (cx, cy) in enumerate(plants):
        kind = "geranium" if idx % 5 in (0, 2, 3) else "daisy"
        s = rng.uniform(1.0, 1.25)
        hue = rng.choice(("red", "red", "cerise", "pink", "white")) if kind == "geranium" else \
            rng.choice(("yellow", "yellow", "white", "purple"))
        specs.append([cx, cy, kind, s, hue])

    cores = []     # (centre, radius, bvh, object, leaves)
    for k, sp_ in enumerate(specs):
        cx, cy, kind, s, hue = sp_
        made = None
        for shrink in range(6):
            r = (rng.uniform(11.5, 13.5) if kind == "geranium" else rng.uniform(10.0, 12.0)) * s * (0.92 ** shrink)
            g = ground(cx, cy)
            C = Vector((cx, cy, g + 0.7 * r * 0.62))
            core = blob((0, 0, 0), r, "M_Plant", (1.0, rng.uniform(0.88, 1.0), 0.7), sub=1, rough=0.16, freq=1.9,
                        seed=700 + k, name="core")
            tex = bpy.data.textures.new("core_clouds", "CLOUDS")
            tex.noise_scale = 4.0
            dm = core.modifiers.new("disp", "DISPLACE")
            dm.texture = tex
            dm.texture_coords = "LOCAL"
            dm.strength = 1.2
            core = bake(core)
            xform(core, Matrix.Translation(C) @ Matrix.Rotation(rng.uniform(0, 6.28), 4, "Z"))
            set_mat(core, "M_Plant")
            conform_leaf(core)
            if not col.hits(core):
                made = (C, r, core)
                break
            discard(core)
        if made is None:
            log(f"flower bed: plant {k} found no room")
            continue
        C, r, core = made
        for p in core.data.polygons:
            p.use_smooth = True
        tag_faces(core, "upn", 1)
        col.add(core, "core")
        tree_ = BVHTree.FromPolygons([v.co.copy() for v in core.data.vertices],
                                     [tuple(p.vertices) for p in core.data.polygons])
        cores.append((k, C, r, tree_, core, []))
        tris["core"] += tri_count(core)

    # leaves: placed round-robin (one leaf per plant per pass) so no plant crowds out its neighbours
    def leaf_candidate(k, C, r, ctree, kind, s, i, n, slot):
        a = slot + rng.uniform(-0.35, 0.35)
        if kind == "geranium":
            top = (i == 0)          # the crown leaf first, so no plant is left with a bald top
            e = math.radians(rng.uniform(68, 85) if top else rng.uniform(22, 58))
        else:
            top = i < 2
            e = math.radians(rng.uniform(50, 70) if top else rng.uniform(-8, 20))
        d = Vector((math.cos(a) * math.cos(e), math.sin(a) * math.cos(e), math.sin(e)))
        hit = ctree.ray_cast(C, d, 3 * r)
        if hit[0] is None:
            return None
        base = hit[0] + d * 0.3
        h = Vector((math.cos(a), math.sin(a), 0.0))
        if kind == "geranium":
            # pitched down-and-out 20-50 deg off horizontal, but never steeper than the core surface there
            slope = math.degrees(math.atan2(0.7 * math.cos(e), max(1e-3, math.sin(e))))
            t = rng.uniform(5, 14) if top else min(rng.uniform(20, 50), slope - 5.0)
            t = max(t, 4.0)
            ld = h * math.cos(math.radians(t)) - Vector((0, 0, math.sin(math.radians(t))))
            lf = round_leaf(rng.uniform(6.5, 7.8) * min(s, 1.1), "M_Plant", nrim=8, lift=rng.uniform(0.15, 0.2),
                            name="gleaf")
            place(lf, base, ld, (0, 0, 1), roll=rng.uniform(-0.2, 0.2))
        else:
            el = math.radians(rng.uniform(28, 45) if top else rng.uniform(12, 32))
            ld = h * math.cos(el) + Vector((0, 0, math.sin(el)))
            lf = strap_leaf(rng.uniform(14.0, 17.0) * min(s, 1.1), rng.uniform(2.9, 3.4), "M_Plant", bend=rng.uniform(25, 45),
                            name="dleaf")
            place(lf, base, ld, (0, 0, 1), roll=rng.uniform(-0.25, 0.25))
        conform_leaf(lf)
        return lf

    order = []
    for (k, C, r, ctree, core, lv) in cores:
        kind, s = specs[k][2], specs[k][3]
        n = 6
        a0 = rng.uniform(0, 2 * math.pi)
        order.append((k, C, r, ctree, kind, s, n, [a0 + 2 * math.pi * i / n for i in range(n)], lv))
    for i in range(6):
        for (k, C, r, ctree, kind, s, n, slots, lv) in order:
            if i >= n:
                continue
            lf = try_place(col, lambda t, k=k, C=C, r=r, ctree=ctree, kind=kind, s=s, i=i, n=n, sl=slots[i]:
                           leaf_candidate(k, C, r, ctree, kind, s, i, n, sl), attempts=8, tag="leaf")
            if lf is not None:
                tag_faces(lf, "upn", 1)
                lv.append(lf)
                counts["leaf"] += 1
                tris["leaf"] += tri_count(lf)

    def geranium_head(R, hd):
        """Umbel as one coloured ball: icosphere (sub 1) with its bottom vertex cut off flat (18 tris),
        flattened to 0.78, 0.4 cm vertex jitter; smooth shaded so its normals point out from its centre."""
        bm = bmesh.new()
        bmesh.ops.create_icosphere(bm, subdivisions=1, radius=1.0)
        bot = min(bm.verts, key=lambda v: v.co.z)
        bmesh.ops.delete(bm, geom=[bot], context="VERTS")
        bmesh.ops.holes_fill(bm, edges=[e for e in bm.edges if e.is_boundary], sides=0)
        bmesh.ops.triangulate(bm, faces=bm.faces)
        for v in bm.verts:
            j = Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1))) * 0.4
            v.co = Vector((v.co.x * R, v.co.y * R, v.co.z * R * 0.78)) + j
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        for f in bm.faces:
            f.smooth = True
        me = bpy.data.meshes.new("ghead")
        bm.to_mesh(me)
        bm.free()
        ob = link("ghead", me)
        set_mat(ob, "M_FlowerRed")
        xform(ob, hd.to_track_quat("Z", "X").to_matrix().to_4x4())
        return ob, 0.447 * 0.78 * R + 0.4      # depth of the flat bottom below the centre

    def daisy_head(R, hd):
        """Daisy: 8-tri disc fan (petal ring, slightly cupped) + 6-tri raised cone eye 0.25 cm above it."""
        bm = bmesh.new()
        ctr = bm.verts.new((0, 0, 0))
        a0 = rng.uniform(0, 1)
        ring = []
        for k in range(8):
            a = a0 + 2 * math.pi * k / 8
            rr = R * rng.uniform(0.9, 1.05)
            ring.append(bm.verts.new((rr * math.cos(a), rr * math.sin(a), 0.35 * (rr / R) ** 2)))
        for k in range(8):
            bm.faces.new((ctr, ring[k], ring[(k + 1) % 8]))
        disc = bm_obj(bm, "dhead", "M_FlowerRed", angle=80.0, recalc=False)
        for p in disc.data.polygons:
            if p.normal.z < 0:
                p.flip()
        bm = bmesh.new()
        apex = bm.verts.new((0, 0, 0.95))
        er = 0.34 * R
        rv = [bm.verts.new((er * math.cos(2 * math.pi * k / 6), er * math.sin(2 * math.pi * k / 6),
                            0.35 * (er / R) ** 2 + 0.25)) for k in range(6)]
        for k in range(6):
            bm.faces.new((apex, rv[k], rv[(k + 1) % 6]))
        eye = bm_obj(bm, "deye", "M_FlowerRed", angle=80.0, recalc=False)
        for p in eye.data.polygons:
            if p.normal.z < 0:
                p.flip()
        m = Matrix.Translation((0, 0, 0)) @ hd.to_track_quat("Z", "X").to_matrix().to_4x4()
        xform(disc, m)
        xform(eye, m)
        return disc, eye

    BED_BUDGET = 2990
    used = sum(tri_count(o) for o in parts + [soil, berm]) + tris["core"] + tris["leaf"]
    plan = []
    for (k, C, r, ctree, core, lv) in cores:
        kind = specs[k][2]
        counts[kind] += 1
        zt = max(max(v.co.z for v in o.data.vertices) for o in [core] + lv)
        plan.append([k, C, r, ctree, core, lv, zt, rng.choice((3, 3, 4)) if kind == "geranium" else 3, 0])
    for pas in range(4):
      for pl in plan:
        k, C, r, ctree, core, lv, zt, nheads, got = pl
        cx, cy, kind, s, hue = specs[k]
        if got >= nheads or got > pas or used + 24 > BED_BUDGET:
            continue
        for attempt in range(12):
            a = rng.uniform(0, 2 * math.pi)
            rr = rng.uniform(0.1, 0.75) * r
            tilt = math.radians(rng.uniform(5, 25))
            hd = Vector((math.cos(a) * math.sin(tilt), math.sin(a) * math.sin(tilt), math.cos(tilt)))
            hc = Vector((cx + rr * math.cos(a), cy + rr * math.sin(a), zt + rng.uniform(3.0, 8.0)))
            hit = ctree.ray_cast(hc, Vector((0, 0, -1)), 80.0)
            if hit[0] is None:
                continue
            if kind == "geranium":
                R = rng.uniform(4.0, 4.8) * min(1.15, s)
                head, depth = geranium_head(R, hd)
                move(head, hc)
                hp = [head]
                end = hc - hd * (depth + 0.15)
            else:
                R = rng.uniform(3.1, 3.6) * min(1.15, s)
                disc, eye = daisy_head(R, hd)
                move(disc, hc)
                move(eye, hc)
                hp = [disc, eye]
                end = hc - hd * 0.2
            tag = HUE[hue]
            for o in hp:
                tag_faces(o, "hue", tag)
            if kind != "geranium":
                tag_faces(hp[1], "hue", HUE["brown" if hue == "yellow" else "gold"])
            st = sweep([tuple(hit[0] + Vector((0, 0, 0.3))), tuple(end)], "M_Plant", [0.28, 0.22], res=1, kind="POLY",
                       name="stalk", bevel_obj=prof, angle_smooth=70, caps=False)
            cand = [st] + hp
            if any(col.hits(o) for o in cand):
                for o in cand:
                    discard(o)
                continue
            for o in cand:
                col.add(o, "flower")
            lv += cand
            pl[8] += 1
            used += sum(tri_count(o) for o in cand)
            counts["head"] += 1
            tris["stalk"] += tri_count(st)
            tris["head"] += sum(tri_count(o) for o in hp)
            break
    flowers = []
    for (k, C, r, ctree, core, lv) in cores:
        flowers += [core] + lv
    drop_curve_obj(prof)
    base_tris = sum(tri_count(o) for o in parts + [soil, berm])
    bed = join("SM_FlowerBed", parts + [soil, berm] + flowers)
    up_normals(bed, bias=0.7)
    paint_hues(bed)
    log(f"flower bed: {tri_count(bed)} tris, {counts}, tris by part {tris}, base {base_tris}")
    return bed


# ------------------------------------------------------------------ trees
def smooth_mats(ob, prefixes, angle_other=80.0):
    """Smooth-shade every face whose material starts with one of `prefixes` (all their edges smooth);
    other faces keep the angle-based smoothing."""
    me = ob.data
    idx = {i for i, m in enumerate(me.materials) if m and m.name.startswith(tuple(prefixes))}
    smooth(ob, angle_other)
    bm = bmesh.new()
    bm.from_mesh(me)
    for f in bm.faces:
        if f.material_index in idx:
            f.smooth = True
    for e in bm.edges:
        if len(e.link_faces) == 2 and all(f.material_index in idx for f in e.link_faces):
            e.smooth = True
    bm.to_mesh(me)
    bm.free()
    return ob


def hanging_mass(c, r, m, rng, seed, droop=10.0, sz=0.6, heading=0.0, stretch=1.0, sub=3, rough=0.3, freq=2.1,
                 elong=1.0):
    """Eucalypt leaf mass: noisy icosphere scaled to z*sz (and stretched along `heading`), its lower
    half pulled down by up to `droop` cm so it hangs like a pendulous spray rather than a ball."""
    ob = blob((0, 0, 0), r, m, (stretch, 1.0 / math.sqrt(stretch), sz), sub=sub, rough=rough, freq=freq, seed=seed,
              name="spray")
    xform(ob, Matrix.Translation(Vector(c)) @ Matrix.Rotation(heading, 4, "Z"))
    cz = c[2]
    h = r * sz
    for v in ob.data.vertices:
        if v.co.z < cz:
            dz = (cz - v.co.z) * elong          # lower half elongated into a teardrop
            v.co.z = cz - dz - droop * min(1.0, dz / (h * elong))
    return ob


def tree(kind):
    """SM_GardenTree_B: Callery / ornamental pear - a dense, upright oval crown. Five limbs with two side
    branches each carry clusters of 7-8 small lumps (finer-grained outline); two side-branch clumps are
    left out so a limb shows through the crown and sky shows near the upper edge; the upper side
    branches carry bare twig ends 10-15 cm beyond their clump. Canopy: union -> voxel remesh (6 cm) ->
    smooth -> one decimate -> smooth shading with soft normals transferred (60 %) from an ellipsoid
    proxy, so baked lighting sees a soft crown rather than triangle facets. Wood keeps its own normals."""
    if kind == "A":
        return tree_eucalypt()
    rng = random.Random(23)
    trunk = [Vector(p) for p in ((0, 0, 0), (0, 0, 22), (3, -2, 90), (2, -1, 165))]
    trad = [18.0, 13.0, 11.0, 9.5]
    # steep limbs (68-80 deg) that end inside the crown: a narrow vase, not a splayed lollipop
    limbs = [(10, 72, 165, 164), (100, 69, 160, 162), (190, 74, 168, 160), (280, 68, 155, 158),
             (55, 80, 170, 150)]
    clump_r = (38, 62)
    clump_scale = (0.9, 0.9, 1.15)
    skip = {(1, 0.55), (3, 0.55)}        # deliberate voids: these side branches stay bare
    wood = [sweep([tuple(p) for p in trunk], "M_Bark", trad, res=3, bevel_res=2, name="trunk", angle_smooth=80)]
    clumps = []

    def trunk_point(z):
        for i in range(len(trunk) - 1):
            if trunk[i].z <= z <= trunk[i + 1].z:
                t = (z - trunk[i].z) / (trunk[i + 1].z - trunk[i].z)
                return trunk[i].lerp(trunk[i + 1], t), trad[i] + (trad[i + 1] - trad[i]) * t
        return trunk[-1], trad[-1]

    seed = 0
    for li, (az, el, length, z_from) in enumerate(limbs):
        az += rng.uniform(-12, 12)
        p0, r_here = trunk_point(z_from)
        start = p0 - polar_dir(az, el) * r_here * 0.6
        pts = grow(rng, start, polar_dir(az, el), length, 4, wobble=0.16, lift=0.10)
        r0 = min(r_here * 0.75, 7.0)
        wood.append(sweep([tuple(p) for p in pts], "M_Bark", taper(len(pts), r0, 2.0, 0.8), res=2, bevel_res=1,
                          name="limb", angle_smooth=80))
        tips = [(pts[-1], 1.0, None)]
        for f, side in ((0.55, 1), (0.78, -1)):
            q, _ = at_fraction(pts, f)
            d = polar_dir(az + side * rng.uniform(35, 55), min(80, el + rng.uniform(0, 12)))
            sp = grow(rng, q - d * 1.5, d, rng.uniform(60, 80), 3, wobble=0.15, lift=0.05)
            wood.append(sweep([tuple(p) for p in sp], "M_Bark", taper(len(sp), r0 * 0.45, 1.2), res=2, bevel_res=1,
                              name="branch", angle_smooth=80))
            if (li, f) in skip:
                continue
            tips.append((sp[-1], 0.75, (sp[-1] - sp[-2]).normalized() if f == 0.78 else None))
        for tip, s, twig_dir in tips:
            seed += 1
            r = rng.uniform(*clump_r) * s
            clumps += cluster(tip + Vector((0, 0, r * 0.1)), r, rng, core="M_Plant", lumps=("M_Plant",),
                              n=rng.choice((7, 8)), scale=clump_scale, hang=0.0, seed=seed, rough=0.35)
            if twig_dir is not None:     # bare twig end poking 10-15 cm out of the clump
                end = tip + twig_dir * (r * 1.15 + rng.uniform(10, 15))
                wood.append(sweep([tuple(tip - twig_dir * 3.0), tuple(tip.lerp(end, 0.5)), tuple(end)], "M_Bark",
                                  [1.3, 0.9, 0.5], res=1, bevel_res=0, name="twig", angle_smooth=80))
    fills = [  # lower ring closes the underside (crown starts ~1.7 m); mid body; tapered, rounded top
        ((60, 20, 240), 55), ((-50, 45, 230), 50), ((-20, -65, 250), 55), ((25, -30, 215), 45),
        ((-35, 70, 340), 52), ((65, -55, 345), 56), ((-10, -75, 300), 50), ((0, 0, 320), 70),
        ((45, 50, 380), 55), ((-50, -35, 380), 56),
        ((10, 6, 432), 50), ((-16, -12, 412), 50)]
    for c, r in fills:
        seed += 1
        clumps += cluster(c, r, rng, core="M_Plant", lumps=("M_Plant",), n=rng.choice((7, 8)), scale=clump_scale,
                          seed=seed, rough=0.35)
    canopy = union(clumps, "canopy", angle=180.0)
    canopy = remesh_smooth(canopy, 6.0, 0.5, 4)
    canopy = decimate(canopy, 1720, angle=180.0)
    set_mat(canopy, "M_Plant")
    # inner / under-crown depth: downward-facing and deep faces on M_PlantDark
    canopy.data.materials.append(mat("M_PlantDark"))
    clo, chi = bounds(canopy)
    cc = (clo + chi) / 2
    crad = sum((chi - clo) / 2) / 3.0
    ndark = 0
    for p in canopy.data.polygons:
        if p.normal.z < -0.4 or (Vector(p.center) - cc).length < 0.5 * crad:
            p.material_index = 1
            ndark += 1
    log(f"pear crown {((chi - clo)).to_tuple(0)} cm (h/w {(chi.z - clo.z) / max(chi.x - clo.x, chi.y - clo.y):.2f}), "
        f"z {clo.z:.0f}..{chi.z:.0f}; {ndark} of {len(canopy.data.polygons)} faces dark")
    wood = [decimate(w, max(24, int(tri_count(w) * 0.55)), angle=80.0) if w.name.startswith(("limb", "branch")) else w
            for w in wood]
    woody = decimate(union(wood, "pear_wood", angle=80.0), 950, angle=80.0)
    tw, tcn = tri_count(woody), tri_count(canopy)
    whole = union([woody, canopy], "tree", angle=80.0)
    smooth_mats(whole, ("M_Plant",))
    whole = soft_normals(whole, ellipsoid_hull(whole, ("M_Plant",)), ("M_Plant",), mix=0.6)
    lo, hi = bounds(whole)
    move(whole, (0, 0, -lo.z))
    log(f"pear size {(hi - lo).to_tuple(1)} cm, wood {tw}, canopy {tcn}, total {tri_count(whole)}")
    return join("SM_GardenTree_B", [whole])


def tree_eucalypt():
    """SM_GardenTree_A: eucalypt (gum). The trunk forks at ~2 m into three co-dominant leaders swept 22-34
    deg off vertical (tallest reaching ~5.1 m); sinuous limbs leave the leaders at 35-60 deg with an S
    bend. The crown is open and lopsided (taller than wide, heavier on one side): 8 large, ragged
    foliage lobes - each 3-5 overlapping hanging masses, taller than wide, drooping 25-40 cm like a
    teardrop spray below its branch tip - with clear sky gaps between them, plus two short bare limbs
    that end in a tiny clump. Canopy: lobes at sub 3, unioned, decimated ONCE to ~1,800 tris, then
    soft canopy normals transferred from a smooth hull (remesh 25 cm, smooth x10, +8 cm). M_PlantDark
    so the gum reads darker/greyer than Tree B."""
    rng = random.Random(5)
    trunk = [Vector(p) for p in ((0, 0, 0), (1, 0, 30), (6, -2, 95), (3, 4, 150), (7, 3, 185))]
    trad = [19.0, 14.0, 12.0, 10.6, 10.0]
    wood = []
    fork = trunk[-2].lerp(trunk[-1], (174.0 - 150.0) / 35.0)    # side leaders leave the trunk ~11 cm below its end
    lobes = []          # (centre point, radius, heading)
    bare = []
    # leaders: azimuth, tilt off vertical, length, start radius; two lean the same way (lopsided crown).
    # Leader 0 IS the trunk continued (one sweep, no end cap); the other two leave the trunk's side wall.
    leaders = [(30, 22, 335, 10.0), (95, 34, 255, 7.2), (215, 28, 230, 6.8)]
    for k, (az, tilt, length, r0) in enumerate(leaders):
        d = polar_dir(az, 90 - tilt)
        if k == 0:
            pts = grow(rng, trunk[-1], d, length, 5, wobble=0.13, lift=0.06)
            wood.append(sweep([tuple(p) for p in trunk + pts[1:]], "M_Bark",
                              trad + taper(len(pts), r0, 2.0, 0.85)[1:], res=3, bevel_res=2, name="trunk",
                              angle_smooth=80))
        else:
            h = Vector((d.x, d.y, 0)).normalized()
            off = fork + h * 3.5 - Vector((0, 0, 3.0))       # inside the trunk, off-centre toward the azimuth
            pts = grow(rng, off, d, length, 5, wobble=0.13, lift=0.06)
            wood.append(sweep([tuple(p) for p in pts], "M_Bark", taper(len(pts), r0, 2.0, 0.85), res=2, bevel_res=1,
                              name="limb", angle_smooth=80))
        lobes.append((pts[-1], rng.uniform(46, 55), math.radians(az)))
        # limbs off the leader, S-bent
        for f, daz, el, ln, kind in (((0.4, 70, 40, 125, "lobe"), (0.62, -80, 50, 110, "lobe"),
                                      (0.8, 150, 55, 80, "lobe")) if k == 0 else
                                     ((0.5, 75, 45, 115, "lobe"), (0.75, -70, 58, 70, "bare")) if k == 1 else
                                     ((0.55, -65, 38, 120, "lobe"), (0.35, 80, 35, 60, "bare"))):
            q, i = at_fraction(pts, f)
            r_par = r0 + (2.0 - r0) * f
            dd = polar_dir(az + daz + rng.uniform(-12, 12), el + rng.uniform(-5, 5))
            sp = grow(rng, q - dd * r_par * 0.7, dd, ln, 4, wobble=0.25, lift=0.08)
            wood.append(sweep([tuple(p) for p in sp], "M_Bark", taper(len(sp), r_par * 0.6, 1.3), res=2, bevel_res=1,
                              name="branch", angle_smooth=80))
            if kind == "lobe":
                lobes.append((sp[-1], rng.uniform(30, 46), math.atan2(dd.y, dd.x)))
            else:
                bare.append(sp[-1])
    masses = []
    centres = []
    seed = 0
    for c, R, hd in lobes:
        for j in range(3):        # 3 hanging sprays per lobe, stacked downward: narrow, tall lobes
            seed += 1
            if j == 0:
                p, rr = c + Vector((0, 0, -0.2 * R)), 0.72 * R
            else:
                a = hd + rng.uniform(-2.0, 2.0)
                p = c + Vector((math.cos(a), math.sin(a), 0)) * R * rng.uniform(0.25, 0.5) + \
                    Vector((0, 0, -R * rng.uniform(0.4, 1.4)))
                rr = R * rng.uniform(0.45, 0.62)
            masses.append(hanging_mass(p, rr, "M_PlantDark", rng, seed, droop=rng.uniform(25, 40),
                                       sz=rng.uniform(1.25, 1.45), heading=hd + rng.uniform(-0.6, 0.6),
                                       stretch=rng.uniform(1.0, 1.2), sub=3, rough=rng.uniform(0.3, 0.36), freq=1.4,
                                       elong=1.3))
            centres.append(p)
    for b in bare:
        seed += 1
        masses.append(hanging_mass(b + Vector((0, 0, -6)), 19.0, "M_PlantDark", rng, seed, droop=12, sz=1.3, sub=3,
                                   rough=0.32, freq=1.6, elong=1.3))
        centres.append(b + Vector((0, 0, -6)))
    # sky gaps: smallest clearance between lobe spheres (logged)
    gaps = []
    for i in range(len(lobes)):
        for j in range(i + 1, len(lobes)):
            (a, ra, _), (b, rb, _) = lobes[i], lobes[j]
            gaps.append(round((a - b).length - 1.25 * (ra + rb), 0))
    log(f"eucalypt: {len(lobes)} lobes, {len(masses)} masses, {len(bare)} bare limbs, lobe gaps {sorted(gaps)[:6]}")
    canopy = union(masses, "gum_canopy", angle=180.0)
    canopy = remesh_smooth(canopy, 6.0, 0.5, 3)      # overlapping hems merge into rounded undersides
    me = canopy.data
    for v in me.vertices:                            # vertical drooping streaks: noise stretched along z
        q = v.co.copy()
        f = noise.noise(Vector((q.x / 10.0, q.y / 10.0, q.z / 70.0 + 3.1))) + \
            0.6 * noise.noise(Vector((q.x / 5.0 + 7.7, q.y / 5.0 - 1.3, q.z / 35.0)))
        nz = v.normal[2]
        # streaks out along the normal; on the undersides the streaks also hang down as drooping fingers
        v.co = q + Vector(v.normal) * (9.0 * f) - Vector((0, 0, 5.0 * max(0.0, -nz) * max(0.0, f + 0.5)))
    canopy = decimate(canopy, 1850, angle=180.0)
    # sun / shade: sprays centred above z 430 on M_Plant (sunlit crown top), the rest M_PlantDark
    kd = KDTree(len(centres))
    for i, c in enumerate(centres):
        kd.insert(c, i)
    kd.balance()
    canopy.data.materials.clear()
    canopy.data.materials.append(mat("M_PlantDark"))
    canopy.data.materials.append(mat("M_Plant"))
    nlit = 0
    for p in canopy.data.polygons:
        _, i, _ = kd.find(p.center)
        p.material_index = 1 if centres[i].z > 430.0 else 0
        nlit += p.material_index
    log(f"eucalypt canopy: {nlit} of {len(canopy.data.polygons)} faces on M_Plant (crown top)")
    hull = canopy_hull(canopy, 25.0, 10, 8.0)
    wood = [decimate(w, max(30, int(tri_count(w) * 0.3)), angle=80.0) if w.name.startswith(("limb", "branch")) else w
            for w in wood]
    woody = union(wood, "gum_wood", angle=80.0)
    vg = woody.vertex_groups.new(name="crotch")      # soften the trunk/leader crotch before the one decimate
    for v in woody.data.vertices:
        dd = min((v.co - fork).length, (v.co - trunk[-1]).length)
        if dd < 25.0:
            vg.add([v.index], 1.0 - dd / 25.0 * 0.5, "REPLACE")
    sm = woody.modifiers.new("crotch", "SMOOTH")
    sm.factor = 0.6
    sm.iterations = 6
    sm.vertex_group = "crotch"
    woody = decimate(bake(woody), 520, angle=80.0)
    tw, tcn = tri_count(woody), tri_count(canopy)
    whole = union([woody, canopy], "gum", angle=80.0)       # no decimation after the union: keeps it clean
    smooth_mats(whole, ("M_Plant",))
    whole = soft_normals(whole, hull, ("M_Plant",), mix=0.75)
    lo, hi = bounds(whole)
    move(whole, (0, 0, -lo.z))
    log(f"eucalypt size {(hi - lo).to_tuple(1)} cm, wood {tw}, canopy {tcn}, total {tri_count(whole)}")
    return join("SM_GardenTree_A", [whole])


# ------------------------------------------------------------------ SM_Shrub
def shrub():
    """Rounded garden shrub (pittosporum / westringia habit), ~1 m: a small core (r 30) wrapped in ~20
    medium and ~50 small leaf pads (flattened lumps, not balls), plus a skirt pulled in to overlap the
    core. Union -> voxel remesh (2.5 cm, fills the pinches) -> Clouds displace (8 cm noise, 4 cm) for
    leaf-clump texture -> bottom 12 cm tucked in towards the stems -> one decimate. Two short curved
    stems show under the skirt on one side."""
    rng = random.Random(41)
    C = Vector((0, 0, 44))
    blobs = [blob(C, 33, "M_PlantDark", (1.15, 1.1, 0.88), sub=3, rough=0.12, freq=1.6, seed=1, squash=0.45,
                  name="core"),
             # filler hull under the pads: pads protrude 3-8 cm from a solid body instead of bridging gaps
             blob(C, 40, "M_Plant", (1.12, 1.08, 0.95), sub=3, rough=0.08, freq=1.6, seed=2, squash=0.5,
                  name="hull")]

    def pad(c, rr, d, flat, seed, m):
        """Lump flattened along the surface normal d (a pad lying on the dome, not a ball)."""
        ob = blob((0, 0, 0), rr, m, (1, 1, 1), sub=2, rough=0.25, freq=2.3, seed=seed, name="pad")
        dn = d.normalized()
        S = Matrix.Identity(3) + (flat - 1.0) * Matrix(((dn.x * dn.x, dn.x * dn.y, dn.x * dn.z),
                                                       (dn.y * dn.x, dn.y * dn.y, dn.y * dn.z),
                                                       (dn.z * dn.x, dn.z * dn.y, dn.z * dn.z)))
        return xform(ob, Matrix.Translation(c) @ S.to_4x4())

    def env(d, ex, ey, ez):
        # flatter crown, lower half pulled up (dome widest low down, flanks sweeping to the ground)
        return C + Vector((d.x * ex, d.y * ey, d.z * ez * (1.0 if d.z >= 0 else 0.5)))

    def rand_dir(zlo, zhi):
        a = rng.uniform(0, 2 * math.pi)
        z = rng.uniform(zlo, zhi)
        return Vector((math.cos(a), math.sin(a), 0)) * math.sqrt(1 - z * z) + Vector((0, 0, z))

    for i in range(22):      # medium pads: the body (sunk into the hull)
        d = rand_dir(-0.7, 0.9)
        blobs.append(pad(env(d, 34, 33, 30), rng.uniform(14, 18), d, rng.uniform(0.6, 0.75), 10 + i, "M_Plant"))
    for i in range(52):      # small outer pads: the leafy surface (each sunk >= half its thickness)
        d = rand_dir(-0.7, 0.9)
        blobs.append(pad(env(d, 41, 40, 37), rng.uniform(6, 11), d, rng.uniform(0.6, 0.75), 40 + i, "M_Plant"))
    stem_gap = math.radians(205)
    for k in range(9):       # skirt: pulled in to overlap the core by over half a radius, lifted
        a = stem_gap + math.radians(24) + 2 * math.pi * k / 9.7 + rng.uniform(-0.18, 0.18)
        rr = rng.uniform(15, 18)
        R = rng.uniform(28.0, 32.0)
        d = Vector((math.cos(a), math.sin(a), -0.5))
        blobs.append(pad(Vector((R * math.cos(a), R * math.sin(a), 27 + rng.uniform(0, 4))), rr, d, 0.7, 120 + k,
                         "M_Plant"))
    canopy = union(blobs, "shrub_canopy", angle=180.0)
    canopy = remesh_smooth(canopy, 2.5, 0.5, 1)
    me = canopy.data
    bm = bmesh.new()
    bm.from_mesh(me)
    euler = len(bm.verts) - len(bm.edges) + len(bm.faces)
    shells = 0
    seen = set()
    for f0 in bm.faces:                     # connected shells
        if f0.index in seen:
            continue
        shells += 1
        stack = [f0]
        seen.add(f0.index)
        while stack:
            f = stack.pop()
            for e in f.edges:
                for g in e.link_faces:
                    if g.index not in seen:
                        seen.add(g.index)
                        stack.append(g)
    bm.free()
    log(f"shrub canopy after remesh: V-E+F = {euler} over {shells} shell(s) (2 per shell = no tunnels)")
    tex = bpy.data.textures.new("shrub_cells", "VORONOI")    # leaf clumps with dark creases between cells
    tex.distance_metric = "DISTANCE"
    tex.color_mode = "INTENSITY"
    tex.noise_scale = 7.0
    tex.noise_intensity = 1.2
    dm = canopy.modifiers.new("cells", "DISPLACE")
    dm.texture = tex
    dm.texture_coords = "LOCAL"
    dm.mid_level = 0.6
    dm.strength = 6.0
    tex2 = bpy.data.textures.new("shrub_leafy", "CLOUDS")
    tex2.noise_scale = 3.0
    dm2 = canopy.modifiers.new("leafy", "DISPLACE")
    dm2.texture = tex2
    dm2.texture_coords = "LOCAL"
    dm2.strength = 1.5
    canopy = bake(canopy)
    lo, hi = bounds(canopy)
    zb = lo.z
    for v in canopy.data.vertices:          # tuck the bottom 5 cm in a little towards the stems
        t = (v.co.z - zb) / 5.0
        if t < 1.0:
            k = 0.9 + 0.1 * max(0.0, t)
            v.co.x *= k
            v.co.y *= k
    move(canopy, (0, 0, 3.0 - zb))           # lowest foliage 3 cm above the ground
    lo, hi = bounds(canopy)                  # dome profile: flanks swell low (h ~0.3), crown pulled in
    H = hi.z - 3.0
    for v in canopy.data.vertices:
        h = (v.co.z - 3.0) / H
        t = max(0.0, min(1.0, (h - 0.7) / 0.3))
        k = 1.0 + 0.16 * math.exp(-((h - 0.3) / 0.25) ** 2) - 0.05 * t * t * (3 - 2 * t)
        v.co.x *= k
        v.co.y *= k
    lo, hi = bounds(canopy)                  # to the target dome: ~110 x 105 x 95 cm
    xform(canopy, Matrix.Translation((0, 0, 3.0)) @ Matrix.Diagonal((110.0 / (hi.x - lo.x), 105.0 / (hi.y - lo.y),
                                                                     92.0 / (hi.z - 3.0), 1.0)) @
          Matrix.Translation((0, 0, -3.0)))
    canopy = decimate(canopy, 2700, angle=180.0)
    lo, hi = bounds(canopy)
    best = max(range(int(lo.z), int(hi.z)), key=lambda z: max(
        (math.hypot(v.co.x, v.co.y) for v in canopy.data.vertices if z <= v.co.z < z + 4), default=0))
    log(f"shrub canopy widest at z ~{best + 2} cm of {hi.z:.0f}")
    set_mat(canopy, "M_Plant")
    stems = []
    for da, rr, h in ((-0.10, 24.0, 20.0), (0.16, 20.0, 24.0)):
        a = stem_gap + da
        d = Vector((math.cos(a), math.sin(a), 0))
        base = d * rr
        mid = d * (rr - 5) + Vector((0, 0, h * 0.45)) + Vector((-d.y, d.x, 0)) * 2.0
        top = d * (rr - 13) + Vector((0, 0, h))
        stems.append(sweep([tuple(base), tuple(mid), tuple(top)], "M_Bark", [1.2, 0.9, 0.6], res=3, bevel_res=1,
                           name="stem", angle_smooth=80))
    whole = union(stems + [canopy], "shrub", angle=80.0)
    smooth_mats(whole, ("M_Plant",))
    lo, hi = bounds(whole)
    move(whole, (0, 0, -lo.z))
    log(f"shrub size {(hi - lo).to_tuple(1)}, tris {tri_count(whole)}")
    return join("SM_Shrub", [whole])


# ------------------------------------------------------------------ SM_Fence
def fence_post():
    """10 x 10 x 150 bevelled post, top sloping towards the back; bottom centre at the origin."""
    post = bbox((10.0, 10.0, 150.0), "M_Timber", 0.6, 2, "post")
    for v in post.data.vertices:          # weathering chamfer: slope the top towards the back
        if v.co.z > 74:
            v.co.z -= 1.2 * (0.5 - v.co.x / 10.0)
    return move(post, (0, 0, 75.0))


def fence_end_post():
    """SM_Fence_EndPost: the segment's post on its own, to close the +Y end of a fence run. Place it
    155.1 cm in +Y (Unreal) from the last segment's pivot, same X and yaw (0.2 cm clear of its rails)."""
    return join("SM_Fence_EndPost", [fence_post()])


def fence():
    rng = random.Random(7)
    parts = []
    # post at the Unreal -Y end (Blender +Y), rails run to 0.2 cm short of the next segment's post
    parts.append(move(fence_post(), (0, 144.9, 0)))
    y_lo, y_hi = -149.9, 139.7            # Blender y range of the rails (Unreal -139.7 .. 149.9)
    for zc in (30.0, 128.0):
        r = bbox((3.8, y_hi - y_lo, 7.5), "M_Timber", 0.4, 1, "rail")
        parts.append(move(r, (3.1, (y_lo + y_hi) / 2, zc)))
    n, w = 30, 9.6
    gapw = (299.8 - n * w) / (n - 1)
    for i in range(n):
        yc = -149.9 + w / 2 + i * (w + gapw)
        zt = 160.0 - rng.uniform(0.0, 0.8)
        zb = 5.0 + rng.uniform(-0.4, 0.4)
        e = 2.0
        outline = [(-w / 2, zb), (w / 2, zb), (w / 2, zt - e), (w / 2 - e, zt), (-w / 2 + e, zt), (-w / 2, zt - e)]
        p = slab(outline, 0.0, 1.6, "M_Timber", bevel=0.25, seg=1, name="paling")
        # outline (u, v, w) -> (x = w, y = u, z = v)
        xform(p, Matrix(((0, 0, 1, 0), (1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 0, 1))))
        xform(p, Matrix.Rotation(math.radians(rng.uniform(-0.5, 0.5)), 4, "Z"))
        parts.append(move(p, (5.25 + rng.uniform(0, 0.15), yc, 0)))
    return join("SM_Fence", parts)


# ------------------------------------------------------------------ SM_GardenBench
def bench():
    parts = []
    YF = 72.0
    for sy in (1, -1):
        y = sy * YF
        fr = []
        fr.append(beam((25, y, 0), (25, y, 63.5), 5.0, 5.5, "M_Timber", 0.5, 1, name="front_leg"))
        fr.append(beam((-21.5, y, 0), (-21.5, y, 44.0), 5.0, 5.5, "M_Timber", 0.5, 1, name="back_leg_lo"))
        fr.append(beam((-21.5, y, 41.0), (-31.0, y, 90.0), 5.0, 5.5, "M_Timber", 0.5, 1, name="back_leg_hi"))
        fr.append(beam((27.4, y, 39.0), (-23.8, y, 39.0), 4.0, 7.0, "M_Timber", 0.5, 1, name="seat_rail"))
        fr.append(beam((25, y, 12.0), (-21.5, y, 12.0), 3.6, 4.5, "M_Timber", 0.4, 1, name="stretcher"))
        arm = slab(rounded_rect(58.0, 5.5, 2.6, 3), 62.0, 64.6, "M_Timber", bevel=0.5, seg=2, name="arm")
        fr.append(move(arm, (2.0, y, 0)))
        parts.append(union(fr, "side_frame", angle=40.0))
    # seat slats resting on the seat rails (top 42.5) with the 0.2 cm gap
    for i in range(5):
        xc = 21.8 - 3.4 - i * (6.8 + 1.2)
        s = bbox((6.8, 148.0, 2.2), "M_Timber", 0.6, 2, "seat_slat")
        parts.append(move(s, (xc, 0, 42.7 + 1.1)))
    # back slats mortised between the back legs (0.25 cm clear of the legs), on the leg centreline
    d = Vector((-9.5, 0, 49.0)).normalized()
    p41 = Vector((-21.5, 0, 41.0))
    for zc in (52.0, 62.0, 72.0, 82.5):
        t = (zc - 41.0) / d.z
        c = p41 + d * t
        s = bbox((2.2, 138.0, 8.0), "M_Timber", 0.6, 2, "back_slat")
        rot = Matrix.Rotation(math.atan2(d.x, d.z), 4, "Y")
        xform(s, Matrix.Translation(c) @ rot)
        parts.append(s)
    return join("SM_GardenBench", parts)


# ------------------------------------------------------------------ SM_TomatoPlant
def discard(ob):
    d = ob.data
    bpy.data.objects.remove(ob, do_unlink=True)
    if d.users == 0:
        bpy.data.meshes.remove(d)


def max_x(ob):
    return max(v.co.x for v in ob.data.vertices)


def max_r(ob):
    return max(math.hypot(v.co.x, v.co.y) for v in ob.data.vertices)


class Keepout:
    """Room geometry around every placement of one mesh, expressed in that mesh's local frame (cm,
    Blender axes), merged over all its placements. Candidate parts closer than `clear` cm to any of it,
    or crossing it, are rejected. Built read-only from placement.json, the exported FBX files and the
    last assembly report's rest_on heights (inst_rest: the mesh's own placements use them too, so local
    z 0 is where a rest_on piece's base actually sits)."""

    def __init__(self, mesh_name, reach=48.0, ztop=175.0, skip_kinds=("sky", "exterior"), skip_labels=(),
                 inst_rest=False):
        cfg = json.load(open(os.path.join(ROOM, "placement.json")))
        rest = {}
        for sub in ("Assembly_garden", "Assembly_review_garden"):
            rp = os.path.join(PREVIEW, sub, "report.json")
            if os.path.exists(rp):
                rest = json.load(open(rp)).get("rest_on_z", {})
                if rest:
                    break
        self.rest = rest
        by_label = {p["label"]: p for p in cfg["pieces"]}
        insts = [p for p in cfg["pieces"] if p.get("mesh") == mesh_name]

        def inst_mat(p):
            z = rest.get(p["label"], p["loc"][2]) if inst_rest else p["loc"][2]
            return Matrix.Translation(u2b(p["loc"][0], p["loc"][1], z)) @ \
                Matrix.Rotation(math.radians(-p.get("yaw", 0)), 4, "Z")
        self.inst = [inst_mat(p) for p in insts]
        inv = [m.inverted() for m in self.inst]
        cache = {}
        verts, tris, names = [], [], set()
        for p in cfg["pieces"]:
            if p.get("kind") in skip_kinds or p.get("mesh") == mesh_name or p["label"] in skip_labels:
                continue
            src = by_label[p["same_as"]] if p.get("same_as") else p
            mesh = p["mesh"]
            if mesh not in cache:
                cache[mesh] = self._load(mesh)
            data = cache[mesh]
            if data is None:
                continue
            lv, lt = data
            x, y, z = src["loc"]
            z = rest.get(src["label"], z)
            mw = Matrix.Translation(u2b(x, y, z)) @ Matrix.Rotation(math.radians(-src.get("yaw", 0)), 4, "Z")
            wv = [mw @ v for v in lv]
            for mi in inv:
                loc = [(mi @ v) * 100.0 for v in wv]

                def near(t):   # triangle bounding box overlaps the local keep-out box
                    a, b, c = loc[t[0]], loc[t[1]], loc[t[2]]
                    return (min(a.x, b.x, c.x) < reach and max(a.x, b.x, c.x) > -reach and
                            min(a.y, b.y, c.y) < reach and max(a.y, b.y, c.y) > -reach and
                            min(a.z, b.z, c.z) < ztop and max(a.z, b.z, c.z) > -5)
                sel = [t for t in lt if near(t)]
                if not sel:
                    continue
                base = len(verts)
                verts += loc
                tris += [(a + base, b + base, c + base) for a, b, c in sel]
                names.add(p["label"])
        self.names = sorted(names)
        self.verts = verts
        self.tree = BVHTree.FromPolygons(verts, tris) if tris else None
        log(f"keepout for {mesh_name}: {len(tris)} tris from {self.names}")

    @staticmethod
    def _load(mesh):
        path = os.path.join(EXPORT, mesh + ".fbx")
        if not os.path.exists(path):
            return None
        before = set(bpy.data.objects)
        mats_before = set(bpy.data.materials)
        bpy.ops.import_scene.fbx(filepath=path)
        new = [o for o in bpy.data.objects if o not in before]
        lv, lt = [], []
        for o in new:
            if o.type != "MESH":
                continue
            me = o.data
            me.calc_loop_triangles()
            base = len(lv)
            lv += [o.matrix_world @ v.co for v in me.vertices]
            lt += [tuple(i + base for i in t.vertices) for t in me.loop_triangles]
        for o in new:
            d = o.data
            bpy.data.objects.remove(o, do_unlink=True)
            if isinstance(d, bpy.types.Mesh) and d.users == 0:
                bpy.data.meshes.remove(d)
        for m in list(bpy.data.materials):
            if m not in mats_before and m.users == 0:
                bpy.data.materials.remove(m)
        return lv, lt

    def dist(self, p, maxd=60.0):
        if self.tree is None:
            return maxd
        hit = self.tree.find_nearest(Vector(p), maxd)
        return hit[3] if hit[0] is not None else maxd

    def hits(self, ob, clear=1.0):
        if self.tree is None:
            return False
        vs = [v.co for v in ob.data.vertices]
        for v in vs:
            if self.tree.find_nearest(v, clear)[0] is not None:
                return True
        t2 = BVHTree.FromPolygons(vs, [tuple(p.vertices) for p in ob.data.polygons])
        return bool(self.tree.overlap(t2))


def sill_ok(ob, zlo=70.0, zhi=90.0, rmax=16.0):
    """Reviewer rule: between z 70 and 90 nothing reaches more than 16 cm from the stake (sill at X 486)."""
    return all(math.hypot(v.co.x, v.co.y) <= rmax for v in ob.data.vertices if zlo <= v.co.z <= zhi)


def serrated_leaflet(L, W, m, thick=0.22, curl=24.0, rng=None, name="leaflet"):
    """Tomato leaflet: 8-vertex outline with a notch on each side (two teeth per side), closed lens
    section (16 tris), curled down with a SimpleDeform BEND."""
    rng = rng or random.Random(0)
    w = W / 2
    j = rng.uniform(-0.03, 0.03)
    right = [(0.24 + j, 0.95 * w), (0.44 + j, 0.62 * w), (0.64 + j, 0.78 * w)]
    left = [(0.28 - j, 1.0 * w), (0.47 - j, 0.66 * w), (0.67 - j, 0.74 * w)]
    pts = [(0.0, 0.0)] + [(u * L, -v) for u, v in right] + [(L, 0.0)] + [(u * L, v) for u, v in reversed(left)]
    lf = fan_leaf(pts, (0.42 * L, 0.0), m, thick, cup=0.10, droop=0.0, name=name)
    lf = bend_down(lf, curl)
    set_mat(lf, m)
    return smooth(lf, 75.0)


def tomato_plant():
    """Staked indeterminate tomato, 140 cm, the memory-scene hero. Budget set per part (logged before
    export), no decimation of the structure:
      * soil mound: 24-step Screw lathe, 6-point profile, Clouds-displaced hill (~190 tris);
      * stake: bevelled 3.8 cm square timber; the stake, mound and vine are boolean-unioned (they enter
        the soil); the vine = 6-sided swept main stem (0.6 -> 0.25 cm), 3-sided petioles, peduncles,
        pedicels and 3 short side shoots (suckers);
      * ~26 compound leaves: terminal leaflet x1.3, two main pairs, basal pair x0.6 and two tiny
        interstitial leaflets (low leaves; upper leaves have one pair), 3-tooth serrated outlines,
        random roll (+-0.6 rad) and curl (10-40 deg); in the sill band (z 70-90) two short leaves per node;
      * 3 trusses of 4-5 fruit graded from ripe red (3 cm radius, nearest the stem) through orange to
        small green at the tip, each with a green calyx star; red / orange are vertex colours on the
        M_FlowerRed slot (Unreal: base colour = VertexColor), green fruit is M_Plant;
      * two cloth ties (cream vertex colour on M_FlowerRed, keeping 4 slots) in a figure-8 hugging stake and stem at 0.2 cm, with a knot and tail.
    Leaves, calyces and fruit are single-sided or separate closed islands with 0.2 cm air gaps; M_Plant
    must be Two Sided. No part comes within 1 cm of the room around the three Memory_Tomato placements
    (window, curtains, Chair_Third...), and nothing in z 70-90 reaches more than 16 cm from the stake."""
    rng = random.Random(3)
    keep = Keepout("SM_TomatoPlant")
    col = Collider()
    budget = {}
    # mound
    mound = lathe([(0, 5.4), (7, 4.4), (12, 1.6), (16, 0.35), (19, 0.0), (0, 0.0)], 16, "M_Soil", name="mound",
                  angle_smooth=60)
    tex = bpy.data.textures.new("mound_clouds", "CLOUDS")
    tex.noise_scale = 7.0
    vg = mound.vertex_groups.new(name="hill")
    for v in mound.data.vertices:
        r = math.hypot(v.co.x, v.co.y)
        vg.add([v.index], max(0.0, min(1.0, (12.0 - r) / 4.0)), "REPLACE")
    mod = mound.modifiers.new("disp", "DISPLACE")
    mod.texture = tex
    mod.texture_coords = "LOCAL"
    mod.strength = 0.9
    mod.mid_level = 0.5
    mod.vertex_group = "hill"
    mound = bake(mound)
    for v in mound.data.vertices:
        v.co.z = max(0.0, v.co.z)
    set_mat(mound, "M_Soil")
    smooth(mound, 60)
    budget["mound"] = tri_count(mound)
    stake = move(bbox((3.8, 3.8, 140.0), "M_Timber", 0.35, 1, "stake"), (0, 0, 70.0))
    budget["stake"] = tri_count(stake)
    col.add(mound, "mound")
    col.add(stake, "stake")
    # main stem: wound loosely round the stake at ~4 cm
    stem_pts = []
    for i in range(12):
        z = 2.5 + i * 128.5 / 11
        a = math.radians(-30 + i * 38)
        rr = 4.5 + 0.2 * math.sin(i * 1.3)
        stem_pts.append(Vector((rr * math.cos(a), rr * math.sin(a), z)))
    stem_r = taper(len(stem_pts), 0.6, 0.25)
    stem = sweep([tuple(p) for p in stem_pts], "M_Plant", stem_r, res=1, bevel_res=1, name="stem", angle_smooth=70)
    budget["stem"] = tri_count(stem)
    col.add(stem, "stem")
    vine = [stem]
    prof = tri_profile()

    def stem_at(z):
        for i in range(len(stem_pts) - 1):
            if stem_pts[i].z <= z <= stem_pts[i + 1].z:
                t = (z - stem_pts[i].z) / (stem_pts[i + 1].z - stem_pts[i].z)
                return stem_pts[i].lerp(stem_pts[i + 1], t), stem_r[i] + (stem_r[i + 1] - stem_r[i]) * t
        return stem_pts[-1], stem_r[-1]

    def tube3(pts, radii, name):
        return sweep([tuple(p) for p in pts], "M_Plant", radii, res=1, kind="POLY", name=name, bevel_obj=prof,
                     angle_smooth=70, caps=False)

    # ---- ties: figure-8 cloth strips round stake and stem
    strip = ngon_profile(3, 0.5, 1.3, name="strip")
    ties = []
    for z0 in (40.0, 97.0):
        s, rs = stem_at(z0)
        u = Vector((s.x, s.y, 0)).normalized()
        v = Vector((-u.y, u.x, 0))
        th_u = math.atan2(u.y, u.x)
        a_st = 2.45
        loop = []
        for k in range(5):                      # round the far side of the stake (superellipse, n=6)
            th = th_u + math.radians(60 + 240 * k / 4)
            c_, s_ = math.cos(th), math.sin(th)
            loop.append(Vector((a_st * math.copysign(abs(c_) ** (1 / 3), c_),
                                a_st * math.copysign(abs(s_) ** (1 / 3), s_), z0)))
        sc = Vector((s.x, s.y, z0))
        dist = math.hypot(s.x, s.y)
        xmid = u * (0.5 * (2.69 + dist - rs)) + Vector((0, 0, z0))   # crossing: stake corner .. stem
        loop.append(xmid + Vector((0, 0, 0.32)))
        R = rs + 0.2 + 0.25
        for k in range(5):                      # round the far side of the stem, clockwise
            th = th_u + math.radians(115 - 230 * k / 4)
            loop.append(sc + Vector((math.cos(th), math.sin(th), 0)) * R)
        loop.append(xmid + Vector((0, 0, -0.32)))
        # densify the four crossing chords, then push every point clear of the stake (rounded-square
        # distance) and the stem by strand half-width + 0.2 cm
        dense = []
        n0 = len(loop)
        for k in range(n0):
            a_, b_ = loop[k], loop[(k + 1) % n0]
            dense.append(a_)
            if k in (4, 5, 10, 11):
                dense += [a_.lerp(b_, 1 / 3), a_.lerp(b_, 2 / 3)]
        clr = 0.3 + 0.2
        for _ in range(6):
            for p in dense:
                qx, qy = abs(p.x) - 1.9, abs(p.y) - 1.9
                dbox = math.hypot(max(qx, 0), max(qy, 0)) + min(max(qx, qy), 0)
                if dbox < clr:
                    g = Vector((math.copysign(max(qx, 0), p.x), math.copysign(max(qy, 0), p.y), 0))
                    if g.length < 1e-6:
                        g = Vector((p.x, p.y, 0))
                    g.normalize()
                    p.x += g.x * (clr - dbox)
                    p.y += g.y * (clr - dbox)
                rel = Vector((p.x - s.x, p.y - s.y, 0))
                if rel.length < rs + clr:
                    rel = rel.normalized() * (rs + clr)
                    p.x, p.y = s.x + rel.x, s.y + rel.y
        loop = dense
        cu = bpy.data.curves.new("tie", "CURVE")
        cu.dimensions = "3D"
        cu.bevel_mode = "OBJECT"
        cu.bevel_object = strip
        cu.use_fill_caps = True
        sp = cu.splines.new("POLY")
        sp.points.add(len(loop) - 1)
        for k, p in enumerate(loop):
            sp.points[k].co = (*p, 1.0)
            sp.points[k].radius = 0.2
        sp.use_cyclic_u = True
        band = bake(link("tie", cu))
        set_mat(band, "M_FlowerRed")
        band.name = "tie"
        tag_faces(band, "hue", HUE["linen"])     # cloth strip: cream vertex colour on the M_FlowerRed slot
        if col.hits(band):
            log(f"tomato: tie at z {z0} touches the stake/stem")
        col.add(band, "tie")
        ties.append(band)
        # knot + loose tail: one swept piece hanging 0.2 cm below the crossing (fat bulb, then the tail)
        for sgn in ():                          # knot tails dropped for the triangle budget
            k0 = xmid - Vector((0, 0, 0.32 + 0.26 + 0.2 + 0.4))
            tail = sweep([tuple(k0 + Vector((0, 0, 0.35))), tuple(k0), tuple(k0 + v * sgn * 0.9 + Vector((0, 0, -1.3))),
                          tuple(k0 + v * sgn * 1.4 + u * 0.4 + Vector((0, 0, -3.4)))], "M_FlowerRed",
                         [0.3, 0.4, 0.2, 0.15], res=1, bevel_res=0, kind="POLY", name="knot_tail")
            if not col.hits(tail):
                tag_faces(tail, "hue", HUE["linen"])
                col.add(tail, "tie")
                ties.append(tail)
                break
            discard(tail)
    drop_curve_obj(strip)
    budget["ties"] = sum(tri_count(t) for t in ties)
    # ---- fruit trusses
    fruits, calyces = [], []
    for z, az0, sizes in ((36, 150, (3.1, 2.8, 2.4, 2.0)), (60, -120, (3.0, 2.6, 2.1)),
                          (112, 95, (2.4, 2.0, 1.7))):
        s, rs = stem_at(z)
        colours = ["ripe", "ripe", "orange", "green"] if z < 50 else \
            ["ripe", "orange", "green"] if z < 80 else ["orange", "green", "green"]
        done = False
        for turn in (0, 35, -35, 70, -70, 110, -110, 150, -150, 180):
            az = math.radians(az0 + turn)
            d = Vector((math.cos(az), math.sin(az), 0))
            side = Vector((-d.y, d.x, 0))
            p0 = s + d * (rs + 0.5)
            ped_pts = [p0, s + d * 4.5 + Vector((0, 0, 1.0)), s + d * 9.5 + Vector((0, 0, -2.0)),
                       s + d * (11.0 + 2.2 * len(sizes)) + Vector((0, 0, -8.0))]
            group = [tube3(ped_pts, [0.3, 0.27, 0.22, 0.16], "peduncle")]
            gf, gc = [], []
            ok = True
            for k, r in enumerate(sizes):
                f = 0.4 + 0.6 * k / max(1, len(sizes) - 1)
                q, _ = at_fraction(ped_pts, min(f, 0.999))
                off = side * ((-1) ** k) * r * 0.8
                apex_target = q + off - Vector((0, 0, 1.6))
                cc = apex_target - Vector((0, 0, 0.35 + 0.2 + 0.82 * r))
                hue = colours[k]
                fr, cx, apex = tomato_fruit(cc, r, "M_Plant" if hue == "green" else "M_FlowerRed",
                                            None if hue == "green" else hue, seg=10 if r > 2.3 else 8,
                                            rings=5 if r > 2.3 else 4, rng=rng)
                ped = tube3([q - Vector((0, 0, 0.45)), apex + Vector((0, 0, 0.2))], [0.15, 0.12], "pedicel")
                group.append(ped)
                for o in (fr, cx):
                    if col.hits(o) or any(Collider._entry(o)[2].overlap(Collider._entry(g)[2]) for g in gf + gc):
                        ok = False
                gf.append(fr)
                gc.append(cx)
            parts_ = group + gf + gc
            why = ("fruit/calyx collides" if not ok else
                   "room keep-out" if any(keep.hits(o) for o in parts_) else
                   "sill band" if any(not sill_ok(o) for o in parts_) else
                   "stalks collide" if any(col.hits(o, ignore="stem") for o in group) else "")
            if os.environ.get("TOMATO_DEBUG"):
                log(f"truss z {z} turn {turn}: {why or 'ok'}")
            if not why:
                for o in gf + gc:
                    col.add(o, "fruit")
                for o in group:
                    col.add(o, "peduncle")
                vine += group
                fruits += gf
                calyces += gc
                done = True
                break
            for o in parts_:
                discard(o)
        if not done:
            log(f"tomato: truss at z {z} found no room")
    budget["fruit+calyx"] = sum(tri_count(o) for o in fruits + calyces)
    # ---- compound leaves
    nodes = []
    for i in range(15):
        z = 14.0 + i * 119.0 / 14
        az = (i * 137.5) % 360
        nodes.append((z, az))
        if 68.0 < z < 92.0 or z > 110.0:
            nodes.append((z + 1.5, az + 180))
    leaflets = []
    nleaves = 0
    pet_tris = 0

    jobs = []          # leaflet spots, placed after every petiole exists, in rank order, under a budget

    def add_leaflets(pts, z, small):
        if small:
            fr_ = ((0.55, 1.0),)
        else:
            fr_ = ((0.25, 0.6), (0.55, 1.0), (0.85, 0.8)) if z < 50 else \
                ((0.25, 0.65), (0.62, 1.0)) if z < 110 else ((0.4, 0.9),)
        spots = [(1.0, 1.3, 0, 0)] + [(f, sc_, sg, 1 + k) for k, (f, sc_) in enumerate(fr_) for sg in (1, -1)]
        if not small and z < 50:
            spots += [(0.4, 0.3, 1, 5), (0.4, 0.3, -1, 5)]        # tiny interstitial leaflets
        for f, scl, sgn, rank in spots:
            q, idx = at_fraction(pts, min(f, 0.999))
            if f >= 1.0:
                q = pts[-1]
            tan = (pts[min(idx + 1, len(pts) - 1)] - pts[idx]).normalized()
            sdir = tan.cross(Vector((0, 0, 1))).normalized()

            def make(a, q=q, tan=tan, sdir=sdir, sgn=sgn, scl=scl):
                ld = (tan * (0.45 + 0.25 * a) + sdir * sgn).normalized() if sgn else tan.copy()
                ld.z -= 0.1 + 0.08 * a
                ld.normalize()
                base_L = rng.uniform(9.5, 12.0) * (0.8 if small else 1.0) * (0.8 if z > 112 else 1.0)
                L = base_L * scl * (1.0 - 0.08 * a)
                tiny = scl < 0.5
                lf = tomato_leaflet(max(L, 2.2), max(L, 2.2) * rng.uniform(0.65, 0.75), "M_Plant",
                                    teeth=1 if tiny else (3 if sgn == 0 else 2), curl=rng.uniform(10, 40))
                place(lf, q + ld * 0.55, ld, (0, 0, 1), roll=rng.uniform(-0.6, 0.6))
                if max_r(lf) > 30.0 or not sill_ok(lf) or keep.hits(lf):
                    discard(lf)
                    return None
                return lf
            jobs.append((rank, len(jobs), make))
        return []

    front_band = set()
    for z, az_deg in nodes:
        s, rs = stem_at(z)
        pet = None
        band = int(z // 20)
        if band not in front_band:       # bias: at least one leaf per 20 cm band crosses the stake's +X side
            az_deg = rng.uniform(-40, 40)
        for attempt in range(16):
            az = math.radians((az_deg + rng.uniform(-25, 25) + attempt * 23) % 360)
            d = Vector((math.cos(az), math.sin(az), 0.7)).normalized()
            length = rng.uniform(20, 26)
            if z > 110.0:                # crown: short leaves, two per node -> a leafy tuft over the stake top
                length = rng.uniform(12, 16)
            if 62.0 < z < 98.0:          # the sill band: short leaves (16 cm reach rule)
                length = rng.uniform(12, 15)
            length *= 1.0 - 0.06 * (attempt // 3)
            pts = [s + Vector((d.x, d.y, 0)).normalized() * (rs + 0.5) + Vector((0, 0, 0.2))]
            nseg = 3 if length > 17.0 else 2         # long petioles arc over and down in three segments
            for k in range(nseg):
                d = (d + Vector((0, 0, -0.45 * 3 / (nseg + 1)))).normalized()
                pts.append(pts[-1] + d * length / nseg)
            cand = tube3(pts, [0.3, 0.24, 0.18, 0.13][:nseg] + [0.13], "petiole")
            if (max_r(cand) < 27.0 and min(v.co.z for v in cand.data.vertices) > 8.0 and sill_ok(cand)
                    and not keep.hits(cand) and not col.hits(cand, ignore="stem")):
                pet = (cand, pts)
                break
            discard(cand)
        if pet is None:
            log(f"tomato: node z {z:.0f} has no room for a leaf")
            continue
        cand, pts = pet
        if abs(math.atan2(pts[-1].y, pts[-1].x)) < math.radians(55):
            front_band.add(band)
        col.add(cand, "petiole")
        vine.append(cand)
        pet_tris += tri_count(cand)
        nleaves += 1
        leaflets += add_leaflets(pts, z, False)
    # suckers: short side shoots in the leaf axils, each with a small leaf at its tip
    nsuck = 0
    for z in (31.0, 52.0, 108.0):
        s, rs = stem_at(z)
        for attempt in range(10):
            az = math.radians(rng.uniform(0, 360))
            d = Vector((math.cos(az), math.sin(az), 1.1)).normalized()
            ln = rng.uniform(10, 14)
            s0 = s + Vector((d.x, d.y, 0)).normalized() * (rs + 0.5) + Vector((0, 0, 0.3))
            pts = [s0, s0 + d * ln * 0.5, s0 + d * ln + Vector((0, 0, 1.0))]
            cand = tube3(pts, [0.26, 0.2, 0.12], "sucker")
            if not keep.hits(cand) and sill_ok(cand) and not col.hits(cand, ignore="stem"):
                col.add(cand, "petiole")
                vine.append(cand)
                pet_tris += tri_count(cand)
                leaflets += add_leaflets(pts, z, True)
                nsuck += 1
                break
            discard(cand)
    drop_curve_obj(prof)
    budget["petioles+peduncles"] = pet_tris + sum(tri_count(o) for o in vine if o.name.startswith(("ped", "pedicel")))
    # leaflets last: terminal leaflets of every leaf first, then the first pairs, second pairs... (interleaved
    # bottom / top) until the piece budget is used, so any shortfall is spread thin instead of baring one leaf
    others = sum(tri_count(o) for o in [mound, stake] + vine + ties + fruits + calyces) + 95   # + union cuts
    leaf_budget = 2990 - others
    used = 0
    order = sorted(jobs, key=lambda j: (j[0], (j[1] * 7919) % len(jobs)))
    for rank, _, make in order:
        if used + 14 > leaf_budget:
            break
        lf = try_place(col, make, attempts=6, tag="leaf")
        if lf is not None:
            if rng.random() < 0.3:
                tag_faces(lf, "hue", HUE["leafdark"])
            leaflets.append(lf)
            used += tri_count(lf)
    budget["leaflets"] = sum(tri_count(o) for o in leaflets)
    log(f"tomato: {len(leaflets)} of {len(jobs)} leaflet spots filled (leaflet budget {leaf_budget})")
    plant = union([mound, stake, stem], "tomato", angle=70.0)
    for v in plant.data.vertices:     # nothing below the floor
        v.co.z = max(v.co.z, 0.0)
    up = []
    for lf in leaflets:
        tag_faces(lf, "upn", 1)
        up.append(lf)
    out = join("SM_TomatoPlant", [plant] + [o for o in vine if o is not stem] + ties + fruits + calyces + up)
    up_normals(out, bias=0.5)
    paint_hues(out)
    lo, hi = bounds(out)
    log(f"tomato size {((hi - lo) * 100).to_tuple(1)}, compound leaves {nleaves}, suckers {nsuck}, leaflets "
        f"{len(leaflets)}, fruit {len(fruits)}, tris {tri_count(out)}; budget {budget}")
    return out


# ------------------------------------------------------------------ SM_BasilPot
POT_RIM_TOP = 12.85


def basil_pot():
    """Terracotta pot on a saucer with a sweet-basil bush (pot about 13 cm, plant to ~25 cm overall):
    10 stems (5-sided, 0.22 -> 0.12 cm, three of them branching at the second node) carrying decussate
    leaf pairs on 1.3 cm internodes from just above the rim, and a 4-leaf tip cluster. Leaves shrink
    towards the top (5.5 -> 2 cm); lower leaves droop 15-30 deg, tip leaves point 40-60 deg up, so the
    foliage is a dense rounded dome ~19 cm across that hides the stems. Each leaf has its own petiole
    starting 0.2 cm off its stem; leaves never cross each other, the stems or the pot rim."""
    rng = random.Random(19)
    SEG = 36
    saucer = lathe([(0, 0.0), (5.8, 0.0), (7.6, 1.4), (7.75, 1.75), (7.35, 1.8), (6.0, 0.45), (0, 0.45)], SEG,
                   "M_Terracotta", name="saucer", angle_smooth=50)
    z0 = 0.45 + GAP
    pot = lathe([(0, z0), (4.75, z0), (6.55, 10.55), (7.35, 11.0), (7.35, 12.6), (7.0, POT_RIM_TOP), (6.4, 12.6),
                 (6.25, 11.0), (4.6, 1.9), (0, 1.9)], SEG, "M_Terracotta", name="pot", angle_smooth=50)

    def inner_r(z):    # inner wall radius of the pot at height z (polygon inscribed radius)
        return (4.6 + (6.25 - 4.6) * (z - 1.9) / (11.0 - 1.9)) * math.cos(math.pi / SEG)

    soil = lathe([(0, 10.55), (3.0, 10.45), (inner_r(10.15) - 0.35, 10.15), (inner_r(9.2) - 0.35, 9.2), (0, 9.2)],
                 24, "M_Soil", name="soil", angle_smooth=60)
    col = Collider()
    prof = ngon_profile(5, name="stem5")
    stems, stem_obs = [], [soil]

    def stem_sweep(pts, radii):
        return sweep([tuple(p) for p in pts], "M_Plant", radii, res=1, kind="POLY", name="bstem", bevel_obj=prof,
                     angle_smooth=70, caps=False)

    stree = BVHTree.FromPolygons([v.co.copy() for v in soil.data.vertices], [tuple(p.vertices) for p in soil.data.polygons])

    def soil_top(x, y):
        hit = stree.ray_cast(Vector((x, y, 30.0)), Vector((0, 0, -1)), 40.0)
        return hit[0].z if hit[0] is not None else 10.5

    for i in range(10):
        a = math.radians(i * 36 + rng.uniform(-12, 12))
        rad = 0.5 if i == 0 else rng.uniform(1.5, 3.4)
        base = Vector((rad * math.cos(a), rad * math.sin(a), 0.0))
        base.z = soil_top(base.x, base.y) + 0.45         # stems stand 0.2 cm clear of the soil (no boolean)
        top_z = (21.6 if i == 0 else 21.8 - 1.3 * rad + rng.uniform(-0.8, 0.8))
        lean = Vector((math.cos(a), math.sin(a), 0)) * (0.2 if i == 0 else rng.uniform(2.2, 3.2))
        h = top_z - base.z
        pts = [base, base + lean * 0.35 + Vector((0, 0, h * 0.45)), base + lean + Vector((0, 0, h))]
        st = stem_sweep(pts, [0.22, 0.17, 0.12])
        stem_obs.append(col.add(st, "stem"))
        stems.append((a, pts, top_z))
    for i, fr in ((2, 0.45), (5, 0.45), (8, 0.45), (0, 0.3), (4, 0.3), (7, 0.3)):   # side shoots
        a, pts, top_z = stems[i]
        if i in (0, 4, 7):
            a = a - 1.8              # lower shoots leave outward on the other flank of their stem
        q, _ = at_fraction(pts, fr)
        d = (Vector((math.cos(a + 0.9), math.sin(a + 0.9), 0)) * 1.0 + Vector((0, 0, 1.3))).normalized()
        q = q + Vector((d.x, d.y, 0)).normalized() * 0.55       # starts 0.2 cm off its parent stem
        sp = [q, q + d * 2.5, q + d * 4.8 + Vector((math.cos(a), math.sin(a), 0)) * 0.6]
        st = stem_sweep(sp, [0.15, 0.13, 0.1])
        if col.hits(st):             # never through a neighbouring stem
            discard(st)
            continue
        stem_obs.append(col.add(st, "stem"))
        stems.append((a + 0.9, sp, sp[-1].z))
    leaves = []
    leaf_tris = [0]
    leaf_cap = 2985 - sum(tri_count(o) for o in [saucer, pot] + stem_obs)

    def leaf_ok(ob):
        for v in ob.data.vertices:
            r = math.hypot(v.co.x, v.co.y)
            if r > 5.6 and v.co.z < POT_RIM_TOP + 0.25 and r < 7.9:
                return False
            if v.co.z < 10.8:
                return False
        return True

    for si, (a, pts, top_z) in enumerate(stems):
        zs = [p.z for p in pts]
        z_first = max(13.05, zs[0] + 1.0)
        node_z = []
        z = z_first + rng.uniform(0, 0.6)
        while z < top_z - 1.6 and len(node_z) < 4:
            node_z.append(z)
            z += 1.3 + rng.uniform(-0.15, 0.25)
        node_z.append(top_z - 0.3)
        span = max(1.0, top_z - 14.0)
        for k, nz in enumerate(node_z):
            tip = (k == len(node_z) - 1)
            t = (nz - zs[0]) / max(0.1, zs[-1] - zs[0])
            q, _ = at_fraction(pts, min(max(t, 0.0), 0.999))
            frac = max(0.0, min(1.0, (nz - 14.0) / span))
            phase = a + (math.pi / 2) * k + rng.uniform(-0.25, 0.25)
            count = 4 if tip else 2
            for j in range(count):
                az0 = phase + 2 * math.pi * j / count + (math.pi / 4 if tip else 0.0)
                L0 = rng.uniform(2.6, 3.4) if tip else (6.0 - 3.0 * frac) * rng.uniform(0.9, 1.05)
                # tip leaves only 20-35 deg up (their upper faces stay turned to the viewer and the sky)
                elev0 = rng.uniform(12, 25) if tip else (-rng.uniform(18, 32) * (1 - frac) + 25 * frac)

                def make(tk, q=q, az0=az0, L0=L0, elev0=elev0):
                    az = az0 + 0.25 * ((tk + 1) // 2) * (1 if tk % 2 else -1)
                    # retries: drooping lower leaves lift step by step until they clear the pot rim
                    el = math.radians(elev0 + (7 * tk if elev0 < 0 else 8 * ((tk + 1) // 2) * (1 if tk % 3 else -1)))
                    d = Vector((math.cos(az) * math.cos(el), math.sin(az) * math.cos(el), math.sin(el)))
                    hd = Vector((math.cos(az), math.sin(az), 0))
                    L = L0 * (1 - 0.05 * tk)
                    lf = basil_leaf(L, "M_Plant", wr=rng.uniform(0.68, 0.72), cup=rng.uniform(0.25, 0.35),
                                    rib=0.15, stalk=rng.uniform(0.8, 1.4) * (0.7 if L < 3 else 1.0))
                    sr = 0.22 if q.z < 16 else 0.15
                    place(lf, q + hd * (sr + 0.2), d, (0, 0, 1), roll=rng.uniform(-0.3, 0.3))
                    if not leaf_ok(lf):
                        discard(lf)
                        return None
                    return lf
                if len(leaves) >= 90 or leaf_tris[0] + 20 > leaf_cap:
                    continue
                lf = try_place(col, make, attempts=8, tag="leaf")
                if lf is not None:
                    leaves.append(lf)
                    leaf_tris[0] += tri_count(lf)
    drop_curve_obj(prof)
    herb = join("basil_stems", stem_obs)
    herb.data.transform(Matrix.Scale(100.0, 4))     # join() scales to metres; undo until the final join
    for lf in leaves:
        tag_faces(lf, "upn", 1)
    out = join("SM_BasilPot", [saucer, pot, herb] + leaves)
    up_normals(out, bias=0.6)
    lo, hi = bounds(out)
    lt = leaf_tris[0]
    log(f"basil size {((hi - lo) * 100).to_tuple(1)}, stems {len(stems)}, leaves {len(leaves)} (~{lt} tris), "
        f"total {tri_count(out)}")
    return out


# ------------------------------------------------------------------ SM_FigTree
def fig_leaf_open(size, m, lift=1.0, pet=5.0, name="figleaf"):
    """Fig leaf, single-sided, 12 tris: 5 palmate lobes kept as lobe-tip and sinus vertices only (middle tip,
    two upper lobes, two small basal lobes, sinuses cut to 40 % of the radius) round a lifted palm centre
    (10-tri fan), plus a 2-tri petiole ribbon. The leaf hangs from its cordate notch: the petiole runs
    from the origin (on the twig) along +X for `pet` cm to the notch, the blade continues along +X.
    Flat shaded. Top +Z."""
    side = [(38, 0.58), (64, 0.95), (104, 0.52), (134, 0.62)]   # broad lobes, shallow-ish sinuses
    polar = [(-180.0, 0.18)] + [(-a, r) for a, r in reversed(side)] + [(0.0, 1.0)] + side
    bm = bmesh.new()
    ring = []
    notch_x = -0.18 * size
    for a, r in polar:
        z = -0.1 * lift + 0.35 * lift * max(0.0, (r - 0.5) / 0.5) ** 2
        ring.append(bm.verts.new((r * size * math.cos(math.radians(a)) - notch_x + pet,
                                  r * size * math.sin(math.radians(a)), z)))
    ctr = bm.verts.new((-notch_x + pet, 0.0, lift))
    n = len(ring)
    for i in range(n):
        f = bm.faces.new((ctr, ring[i], ring[(i + 1) % n]))
        f.smooth = False
    # petiole: a narrow wedge from the twig surface (origin, 0.45 cm wide) sharing the notch vertex, so
    # blade and petiole are one connected sheet
    p0 = bm.verts.new((0.0, -0.22, 0.0))
    p1 = bm.verts.new((0.0, 0.22, 0.0))
    fc = bm.faces.new((p0, ring[0], p1))
    fc.smooth = False
    for f in bm.faces:
        f.normal_update()
        if f.normal.z < 0:
            f.normal_flip()
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = link(name, me)
    set_mat(ob, m)
    return ob


def fig_tree():
    """Small fig (Ficus carica), ~250 cm, low and spreading: two smooth stems out of a soil mound; each
    stem CONTINUES as one leader (one sweep, no stub or end cap at the fork) and three more limbs leave the
    stems' side walls at 55-75 cm; every limb carries two upturned branchlets and 5 extra short twigs fill
    the gaps of the upper leader and the left limb. Every limb and twig tapers to a 0.2 cm bud 3-4 cm past
    its last fork. Wood: 6-sided leaders/limbs, 5-sided twigs at their final resolution, boolean-unioned
    into one island, then only a limited-dissolve (4 deg) + triangulate clean-up: no collapse decimation,
    so the sections stay round. Crown: ~130 big (21-27 cm) 5-lobed leaves placed by crown envelope
    (Fibonacci points on an ellipsoid, each snapped to the nearest twig/limb point), each hanging from
    the wood on its own petiole; 10 teardrop figs (M_Soil, purple-brown) on 1.2 cm stalks (stalk + fig
    unioned) 0.2 cm off the bark. Leaves are single-sided: M_Plant / M_PlantDark must be Two Sided in
    Unreal. Nothing reaches the building wall (Unreal X 515 = local x -105)."""
    rng = random.Random(31)
    WALL_X = -103.5
    mound = lathe([(0, 6.0), (14, 4.6), (24, 2.0), (33, 0.0), (0, 0.0)], 12, "M_Soil", name="mound",
                  angle_smooth=60)
    for v in mound.data.vertices:
        r = math.hypot(v.co.x, v.co.y)
        v.co.z = max(0.0, v.co.z + 1.0 * noise.noise(v.co / 9.0) * min(1.0, (33 - r) / 8.0))
    smooth(mound, 60)
    stems = [  # base, mid, fork, radius at base, radius at the fork
        (Vector((0, 0, 0)), Vector((-3, 2, 36)), Vector((-6, 5, 72)), 7.5, 5.4),
        (Vector((5, -3, 0)), Vector((13, -8, 30)), Vector((21, -14, 57)), 5.8, 4.2),
    ]
    limbs = [  # stem, azimuth (Blender deg), elevation, length, continues the stem?
        (0, 92, 36, 92, False), (0, 168, 30, 74, False), (0, 20, 55, 100, True),
        (1, 236, 34, 96, False), (1, 308, 42, 90, True),
    ]
    skel = []          # (points, radii, kind)

    def tip_out(pts, rads, ext=3.5):
        """Extend past the last point and taper to a 0.2 cm bud."""
        d = (pts[-1] - pts[-2]).normalized()
        return pts + [pts[-1] + d * ext], rads + [0.2]

    for si, az, el, length, cont in limbs:
        a, b, fork, r0, r1 = stems[si]
        az += rng.uniform(-8, 8)
        d0 = polar_dir(az, el)
        if cont:
            body = grow(rng, fork, d0, length, 3, wobble=0.10, lift=0.07)
            pts = [a, a.lerp(b, 0.5), b, b.lerp(fork, 0.5)] + body
            rl = [r0, (r0 + (r0 + r1) / 2) / 2, (r0 + r1) / 2 + 0.3, (r1 + (r0 + r1) / 2) / 2] + \
                taper(len(body), r1, 0.9, 0.85)
        else:
            rl0 = r1 * 0.6
            off = Vector((d0.x, d0.y, 0)).normalized()
            start = fork - d0 * 3.0 + off * (r1 * 0.35)          # inside the stem, toward the limb's side
            pts = [start, fork + d0 * 6.0] + grow(rng, fork + d0 * 6.0, d0, length - 6.0, 3, wobble=0.10,
                                                   lift=0.07)[1:]
            rl = [min(r1 * 0.7, rl0 * 1.2), rl0] + taper(len(pts) - 2, rl0 * 0.95, 0.9, 0.9)
        pts, rl = tip_out(pts, rl)
        skel.append((pts, rl, "stem" if cont else "limb"))
        body_pts = pts[4:] if cont else pts
        body_r = rl[4:] if cont else rl
        for f, sd in ((0.5, 1), (0.78, -1)):
            q, i = at_fraction(body_pts[:-1], f)
            r_par = body_r[i] + (body_r[min(i + 1, len(body_r) - 1)] - body_r[i]) * 0.5
            d = polar_dir(az + sd * rng.uniform(38, 58), min(75.0, el + rng.uniform(15, 28)))
            sp = grow(rng, q - d * 2.0, d, rng.uniform(34, 46), 1, wobble=0.10, lift=0.12)
            spr = [min(r_par * 0.7, 1.9), 0.6]
            sp, spr = tip_out(sp, spr)
            skel.append((sp, spr, "twig"))
    # extra short twigs into the gaps: three on the upper leader (stem 0's), two on the left limb
    leader = next(t for t in skel if t[2] == "stem" and t[0][0].length < 1.0)
    left = skel[[k for k in range(len(skel)) if skel[k][2] == "limb"][1]]
    for src, fr_list in ((leader, (0.62, 0.74, 0.86)), (left, (0.45, 0.7))):
        pts_s, rads_s = src[0], src[1]
        for f in fr_list:
            q, i = at_fraction(pts_s[:-1], f)
            r_par = rads_s[min(i, len(rads_s) - 1)]
            d = polar_dir(rng.uniform(0, 360), rng.uniform(25, 50))
            sp = grow(rng, q - d * min(1.5, r_par), d, rng.uniform(25, 35), 1, wobble=0.12, lift=0.10)
            spr = [min(r_par * 0.7, 1.3), 0.45]
            sp, spr = tip_out(sp, spr)
            skel.append((sp, spr, "twig"))
    # stretch heights so the leafy top lands near 245 cm, spread the crown to ~200 cm, keep off the wall
    ZF = 62.0
    tips0 = [pts[-1] for pts, _, kind in skel]
    s = (232.0 - ZF) / (max(t.z for t in tips0) - ZF)
    sx = max(1.0, min(1.6, 165.0 / (max(t.x for t in tips0) - min(t.x for t in tips0))))
    sy = max(1.0, min(1.6, 165.0 / (max(t.y for t in tips0) - min(t.y for t in tips0))))
    log(f"fig crown spread x{sx:.2f} y{sy:.2f} z{s:.2f}")
    for pts, _, _ in skel:
        for p in pts:
            if p.z > ZF:
                p.z = ZF + (p.z - ZF) * s
            p.x *= sx
            p.y *= sy
            if p.x < -40.0:
                p.x = -40.0 + (p.x + 40.0) * 0.62
    wood = []
    for pts, rads, kind in skel:
        if kind in ("stem", "limb"):       # stems (and the leaders they become) 8-sided, limbs 6-sided
            wood.append(sweep([tuple(p) for p in pts], "M_Bark", rads, res=1, kind="POLY",
                              bevel_res=2 if kind == "stem" else 1, name="fig" + kind, angle_smooth=80))
        else:
            prof5 = ngon_profile(5, name="twig5")
            wood.append(sweep([tuple(p) for p in pts], "M_Bark", rads, res=1, kind="POLY", name="figtwig",
                              bevel_obj=prof5, angle_smooth=80))
            drop_curve_obj(prof5)
    body = union(wood + [mound], "figwood", angle=50.0)
    raw = tri_count(body)
    bm = bmesh.new()                   # clean the boolean seams without collapsing the tube sections
    bm.from_mesh(body.data)
    bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(4), verts=bm.verts, edges=bm.edges)
    bmesh.ops.triangulate(bm, faces=bm.faces, quad_method="BEAUTY", ngon_method="BEAUTY")
    bm.to_mesh(body.data)
    bm.free()
    for v in body.data.vertices:
        v.co.z = max(v.co.z, 0.0)
    smooth(body, 50.0)
    bark_tris = tri_count(body)
    log(f"fig frame: union {raw} -> limited dissolve {bark_tris} tris")
    col = Collider()
    col.add(body, "body")
    # wood sample points (z > 90) for snapping leaves / figs: (point, radius, tangent)
    samples = []
    for pts, rads, kind in skel:
        for k in range(len(pts) - 1):
            for t in (0.0, 0.33, 0.66):
                p = pts[k].lerp(pts[k + 1], t)
                if p.z > 90.0 and rads[k] < 3.0:
                    samples.append((p, rads[k] + (rads[k + 1] - rads[k]) * t, (pts[k + 1] - pts[k]).normalized()))
    kd = KDTree(len(samples))
    for i, (p, _, _) in enumerate(samples):
        kd.insert(p, i)
    kd.balance()
    # figs on short stalks in the leaf axils
    figs = []
    for k in range(60):
        if len(figs) >= 10:
            break
        p, rt, tan = samples[rng.randrange(len(samples))]
        if p.z < 100 or rt > 2.2:
            continue
        a = rng.uniform(0, 2 * math.pi)
        h = Vector((math.cos(a), math.sin(a), 0))
        h = (h - tan * h.dot(tan)).normalized()
        sdir = (h * 0.6 + Vector((0, 0, -0.8))).normalized()        # stalk leaves the bark out and down
        s0 = p + h * (rt + 0.2)                  # the stalk tip, 0.2 cm off the bark
        bm = bmesh.new()                         # teardrop (7 x 5, smooth) whose neck draws out into the stalk
        bmesh.ops.create_uvsphere(bm, u_segments=7, v_segments=5, radius=1.0)
        zt = max(v.co.z for v in bm.verts)
        for v in bm.verts:
            x, y, z = v.co
            pinch = 0.55 if z > 0.3 else 1.0
            v.co = Vector((x * 2.0 * pinch, y * 2.0 * pinch, z * 2.3 + (2.4 if z >= zt - 1e-4 else 0.0)))
        for f in bm.faces:
            f.smooth = True
        fig = bm_obj(bm, "fig", "M_Soil", angle=180.0)
        topz = max(v.co.z for v in fig.data.vertices)
        rot = (-sdir).to_track_quat("Z", "X").to_matrix().to_4x4()
        xform(fig, Matrix.Translation(s0) @ rot @ Matrix.Translation((0, 0, -topz)))
        if col.hits(fig):
            discard(fig)
            continue
        col.add(fig, "fig")
        figs.append(fig)
    fig_tris = sum(tri_count(o) for o in figs)
    # leaves by crown envelope: Fibonacci points on an ellipsoid, snapped to the nearest wood point
    leaves = []
    leaf_cap = 2990 - bark_tris - fig_tris
    used = 0
    N = 520
    env_pts = []
    for i in range(N):
        zf = 1 - 2 * (i + 0.5) / N
        rr = math.sqrt(max(0.0, 1 - zf * zf))
        th = i * math.pi * (3 - math.sqrt(5))
        e = Vector((95 * rr * math.cos(th), 100 * rr * math.sin(th), 165 + 70 * zf))
        if e.z >= 95.0:
            env_pts.append(e)
    rng.shuffle(env_pts)
    for e in env_pts:
        if used + 11 > leaf_cap:
            break
        _, idx, _ = kd.find(e)
        p, rt, tan = samples[idx]
        out = e - p
        h0 = Vector((out.x, out.y, 0))
        if h0.length < 1e-3:
            h0 = Vector((1, 0, 0))
        h0.normalize()
        e0 = math.degrees(math.asin(max(-1.0, min(1.0, out.normalized().z))))

        def make(t, p=p, rt=rt, h0=h0, e0=e0):
            a = math.atan2(h0.y, h0.x) + math.radians(25 * ((t + 1) // 2) * (1 if t % 2 else -1))
            h = Vector((math.cos(a), math.sin(a), 0))
            el = math.radians(max(-45.0, min(10.0, e0 - 15.0)) + rng.uniform(-8, 8))
            ld = h * math.cos(el) + Vector((0, 0, math.sin(el)))
            size = rng.uniform(20.0, 25.0)
            lf = fig_leaf_open(size, "M_PlantDark" if rng.random() < 0.2 else "M_Plant", lift=rng.uniform(1.0, 1.6),
                               pet=rng.uniform(4.0, 6.5))
            base = p + h * (rt + 0.2)
            place(lf, base, ld, (0, 0, 1), roll=rng.uniform(-0.5, 0.5))
            me = lf.data
            nrm = sum((pp.normal * pp.area for pp in me.polygons), Vector()).normalized()
            tilt = math.degrees(math.acos(min(1.0, abs(nrm.z))))
            if not (12.0 <= tilt <= 65.0):
                discard(lf)
                return None
            zs = [v.co.z for v in me.vertices]
            if min(v.co.x for v in me.vertices) < WALL_X or min(zs) < 85.0:
                discard(lf)
                return None
            return lf
        lf = try_place(col, make, attempts=6, tag="leaf")
        if lf is not None:
            leaves.append(lf)
            used += tri_count(lf)
    parts = [body] + figs + leaves
    hz = max(bounds(o)[1].z for o in parts)
    if hz > 250.0:
        for o in parts:
            xform(o, Matrix.Scale(250.0 / hz, 4))
    nd = sum(1 for o in leaves if o.data.materials[0].name.startswith("M_PlantDark"))
    out = join("SM_FigTree", parts)
    lo, hi = bounds(out)
    log(f"fig size {((hi - lo) * 100).to_tuple(1)} cm, branches {len(skel)}, leaves {len(leaves)} ({nd} dark) of "
        f"{len(env_pts)} envelope points, figs {len(figs)} ({fig_tris} tris), bark {bark_tris} tris, "
        f"total {tri_count(out)}, min x {lo.x * 100:.1f}")
    return out


# ------------------------------------------------------------------ SM_GardenHose
def garden_hose():
    """Green garden hose, ~300 cm, coiled the way it is put down: 4 stacked turns of 11 cm radius, each
    turn lifted by one hose diameter + 0.2 cm (so stacked turns never touch), the inner (tap) end tucked
    inside the coil with its brass coupling lying on the table, and a 24-30 cm lead-out that leaves the
    top turn, drapes down beside the coil and ends in a spray nozzle lying on the table.
    Memory_Hose sits on the dining table among the Vase, Glass, Jug, Hairbrush, CallBell and the two
    basil pots, so the coil's phase, winding direction, tuck and lead are searched against a keep-out
    built from placement.json + those exported FBXs in the hose's local frame (loc, yaw, rest_on z):
    every part keeps >= 1 cm from them and >= 1 cm inside the table edge."""
    R = 0.95                     # 19 mm hose
    PITCH = 2 * R + 0.2          # stacked turns: one diameter + 0.2 cm air gap
    RC = 10.6                    # coil centreline radius (4 turns + tuck + lead = ~300 cm)
    TURNS = 4.0
    SEG_TURN = 18                # 20 deg per ring (small-prop budget; smooth shaded)
    TAP_R, NOZ_R = 1.45, 1.6
    keep = Keepout("SM_GardenHose", reach=75.0, ztop=45.0, skip_labels=("Table", "Rug", "Floor"), inst_rest=True)
    cfg = json.load(open(os.path.join(ROOM, "placement.json")))
    tp = next(p for p in cfg["pieces"] if p["label"] == "Table")
    tc = (keep.inst[0].inverted() @ u2b(tp["loc"][0], tp["loc"][1], 0.0)) * 100.0
    table_r = 47.5
    for sub in ("Assembly_garden", "Assembly_review_garden"):
        rp = os.path.join(PREVIEW, sub, "report.json")
        if os.path.exists(rp):
            b = json.load(open(rp)).get("bounds", {}).get("Table")
            if b:
                table_r = min(b["max"][0] - b["min"][0], b["max"][1] - b["min"][1]) / 2
                break

    def sstep(t):
        t = max(0.0, min(1.0, t))
        return t * t * (3 - 2 * t)

    def coil_z(u):     # flat turns; each climbs one pitch between 0.6 and 0.8 of the turn
        n = math.floor(u)
        return R + PITCH * (n + sstep((u - n - 0.6) / 0.2))

    def build(th0, sgn, tuck_len, kappa, lead_len, lead_bend):
        n_c = int(round(TURNS * SEG_TURN))
        coil = []
        for k in range(n_c + 1):
            u = TURNS * k / n_c
            th = th0 + sgn * 2 * math.pi * u
            r = RC + 0.3 * math.sin(4 * math.pi * u + 0.7)       # periodic: stacked turns stay aligned
            coil.append(Vector((r * math.cos(th), r * math.sin(th), coil_z(u))))

        def cpt(u):     # the coil curve itself (end tangents from it, not from the coarse chords)
            th = th0 + sgn * 2 * math.pi * u
            r = RC + 0.3 * math.sin(4 * math.pi * u + 0.7)
            return Vector((r * math.cos(th), r * math.sin(th), 0.0))
        # tuck: backwards from the coil start, curling in towards the centre, rising to the coupling axis
        d = cpt(0.0) - cpt(0.004)
        d.z = 0
        d.normalize()
        p = coil[0].copy()
        n_t = max(2, int(round(tuck_len / 1.5)))
        tuck = []
        for k in range(n_t):
            inward = Vector((-p.x, -p.y, 0)).normalized()
            side = Vector((-d.y, d.x, 0))
            d = Matrix.Rotation(kappa * 1.5 * (1 if side.dot(inward) > 0 else -1), 3, "Z") @ d
            p = p + d * 1.5
            tuck.append(Vector((p.x, p.y, R + (TAP_R - R) * sstep((k + 1) / n_t))))
        tap_dir = d.copy()
        # lead-out from the top turn along its tangent, bending gently
        d = cpt(TURNS) - cpt(TURNS - 0.004)
        d.z = 0
        d.normalize()
        p = coil[-1].copy()
        n_l = int(round(lead_len / 1.6))
        lead = []
        for k in range(n_l):
            d = Matrix.Rotation(lead_bend * 1.6, 3, "Z") @ d
            p = p + d * 1.6
            lead.append(Vector((p.x, p.y, R)))
        noz_dir = d.copy()
        # lead height: stay one diameter + 0.3 above every lower turn it passes over, then drape down at
        # <= 0.5 slope from the top turn to the table, rising to the nozzle axis at the end
        obst = coil[:-max(4, SEG_TURN * 8 // 30)]
        lim = 2 * R + 0.3
        req = []
        for q0 in lead:
            z = R
            for q in obst:
                dxy = math.hypot(q0.x - q.x, q0.y - q.y)
                if dxy < lim:
                    z = max(z, q.z + math.sqrt(lim * lim - dxy * dxy))
            req.append(z)
        req[-1] = max(req[-1], NOZ_R)
        req[-2] = max(req[-2], (NOZ_R + R) / 2 + 0.2)
        s = [1.6 * (k + 1) for k in range(n_l)]
        top = coil[-1].z
        zs = []
        for i in range(n_l):
            z = max(R, top - 0.5 * s[i])
            for k in range(n_l):
                z = max(z, req[k] - 0.5 * abs(s[i] - s[k]))
            zs.append(z)
        for _ in range(8):      # smooth into the departure from the top turn (no kink where it leaves)
            zs = [max(req[i], ((zs[i - 1] if i else top) + 2 * zs[i] + zs[min(i + 1, n_l - 1)]) / 4)
                  for i in range(n_l)]
        for q, z in zip(lead, zs):
            q.z = z
        cl = list(reversed(tuck)) + coil + lead
        rads = [R] * len(cl)
        # fittings as fat centreline samples (axis points), for clearance tests
        fit = []
        e0 = tuck[-1]
        for t in (0.0, 1.7, 3.4, 5.2):
            fit.append((e0 + tap_dir * t, TAP_R))
        e1 = lead[-1]
        for t in (0.0, 3.0, 6.0, 9.0, 12.6):
            fit.append((e1 + noz_dir * t, NOZ_R))
        return cl, rads, fit, tap_dir, noz_dir

    def recentre(cl, rads, fit):
        allp = [(p, r) for p, r in zip(cl, rads)] + fit
        lox = min(p.x - r for p, r in allp)
        hix = max(p.x + r for p, r in allp)
        loy = min(p.y - r for p, r in allp)
        hiy = max(p.y + r for p, r in allp)
        return Vector((-(lox + hix) / 2, -(loy + hiy) / 2, 0.0))

    def margin(cl, rads, fit, off):
        m = 1e9
        for p, r in [(p, r) for p, r in zip(cl, rads)] + fit:
            q = p + off
            m = min(m, keep.dist(q) - r - 1.0)
            m = min(m, table_r - 1.0 - r - math.hypot(q.x - tc.x, q.y - tc.y))
        return m

    def self_clear(cl, rads, fit):
        """Smallest surface gap between parts of the hose more than 8 cm apart along it (fittings
        included as fat axis samples)."""
        arc = [0.0]
        for i in range(1, len(cl)):
            arc.append(arc[-1] + (cl[i] - cl[i - 1]).length)
        pts = [(p, r, a) for p, r, a in zip(cl, rads, arc)]
        pts += [(p, r, -(p - cl[0]).length) for p, r in fit[:4]]
        pts += [(p, r, arc[-1] + (p - cl[-1]).length) for p, r in fit[4:]]
        g, worst = 1e9, None
        for i in range(len(pts)):
            pi, ri, si = pts[i]
            for j in range(i + 1, len(pts)):
                pj, rj, sj = pts[j]
                if abs(si - sj) > 8.0:
                    gg = (pi - pj).length - ri - rj
                    if gg < g:
                        g, worst = gg, (si, sj)
        self_clear.worst = worst
        return g

    cands = []
    for th0d in range(0, 360, 15):
        for sgn in (1, -1):
            for tuck_len, kappa in ((6.0, 0.18), (7.5, 0.16), (9.0, 0.2)):
                for lead_len in (24.0, 27.0, 30.0):
                    for lead_bend in (-0.03, 0.0, 0.03):
                        args = (math.radians(th0d), sgn, tuck_len, kappa, lead_len, lead_bend)
                        cl, rads, fit, _, _ = build(*args)
                        off = recentre(cl, rads, fit)
                        cands.append((margin(cl, rads, fit, off), args))
    cands.sort(key=lambda c: -c[0])
    best = None
    for m, args in cands:
        cl, rads, fit, tap_dir, noz_dir = build(*args)
        g = self_clear(cl, rads, fit)
        if os.environ.get("HOSE_DEBUG"):
            log(f"cand margin {m:.2f} self gap {g:.3f} at arc {self_clear.worst} n_tuck {len(cl) - 121 - int(round(args[4] / 1.6))}")
        if g >= 0.15:
            best = (m, g, args)
            break
    if best is None or best[0] < 0.0:
        raise RuntimeError(f"hose: no coil layout clears the table props (best {cands[0][0]:.2f})")
    m, g, args = best
    cl, rads, fit, tap_dir, noz_dir = build(*args)
    off = recentre(cl, rads, fit)
    cl = [p + off for p in cl]
    length = sum((cl[i] - cl[i - 1]).length for i in range(1, len(cl)))
    log(f"hose layout th0 {math.degrees(args[0]):.0f} dir {args[1]} tuck {args[2]} lead {args[4]} bend {args[5]}: "
        f"prop/table clearance {m + 1.0:.2f} cm, self gap {g:.2f} cm, centreline {length:.1f} cm "
        f"(+ fittings), top {max(p.z for p in cl) + R:.1f} cm")
    hose = sweep([tuple(p) for p in cl], "M_Plant", [R] * len(cl), res=1, bevel_res=1, kind="POLY", name="hose",
                 angle_smooth=70)
    parts = [hose]
    e0, e1 = cl[0], cl[-1]
    tap = lathe([(0, -1.6), (0.85, -1.6), (1.25, -0.2), (1.25, 2.0), (1.45, 2.4), (1.45, 5.0), (0, 5.2)], 10,
                "M_Brass", name="tap", angle_smooth=40)
    xform(tap, Matrix.Translation(e0) @ tap_dir.to_track_quat("Z", "Y").to_matrix().to_4x4())
    parts.append(tap)
    m1 = Matrix.Translation(e1) @ noz_dir.to_track_quat("Z", "Y").to_matrix().to_4x4()
    cpl = lathe([(0, -1.6), (0.85, -1.6), (1.3, 0.0), (1.3, 3.6), (0, 3.6)], 10, "M_Brass",
                name="coupling", angle_smooth=40)
    body = lathe([(0, 3.3), (1.6, 3.5), (1.6, 6.0), (1.1, 11.6), (0, 11.6)], 10,
                 "M_PlasticBlack", name="nozzle", angle_smooth=40)
    tip = lathe([(0, 11.4), (0.9, 11.4), (0.95, 12.3), (0, 12.6)], 10, "M_Brass", name="tip",
                angle_smooth=40)
    for o in (cpl, body, tip):
        xform(o, m1)
        parts.append(o)
    whole = union(parts, "hose_all", angle=70.0)
    lo, hi = bounds(whole)
    shift = Vector((-(lo.x + hi.x) / 2, -(lo.y + hi.y) / 2, -lo.z))
    move(whole, shift)
    # final audit on the real mesh, in the placed frame
    dmin = min(keep.dist(v.co) for v in whole.data.vertices)
    tmin = min(table_r - math.hypot(v.co.x - tc.x, v.co.y - tc.y) for v in whole.data.vertices)
    log(f"hose mesh: recentre shift {shift.to_tuple(2)}, nearest prop {dmin:.2f} cm, table edge margin "
        f"{tmin:.2f} cm, keep-out hit(1 cm) {keep.hits(whole, 1.0)}, size {(hi - lo).to_tuple(1)}")
    return join("SM_GardenHose", [whole])


# ------------------------------------------------------------------ UVs, export, preview
def uvs(ob, margin=0.02):
    """UV0 'UVMap': 1 m box projection. UV1 'Lightmap': lightmap_pass() on the raw shape and (foliage pieces
    only) on a smoothed copy, keeping whichever covers more of 0..1 (2 % margins). Written through the mesh API (no bmesh
    round trip), so custom normals and colour attributes survive."""
    if ob.get("custom_uv"):
        return
    me = ob.data
    while len(me.uv_layers):
        me.uv_layers.remove(me.uv_layers[0])
    uv0 = me.uv_layers.new(name="UVMap")
    for p in me.polygons:
        n = p.normal
        ax = max(range(3), key=lambda i: abs(n[i]))
        for li in p.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            uv0.data[li].uv = (co.y, co.z) if ax == 0 else (co.x, co.z) if ax == 1 else (co.x, co.y)
    me.uv_layers.new(name="Lightmap")
    best = None
    organic = any(m and m.name.startswith("M_Plant") for m in me.materials)
    for its in ((0, 25) if organic else (0,)):      # hard-surface pieces: raw shape only (even texels)
        cov, n, data = lightmap_pass(ob, its, margin)
        if best is None or cov > best[0]:
            best = (cov, n, data, its)
    d = me.uv_layers["Lightmap"].data
    for e, u in zip(d, best[2]):
        e.uv = u
    log(f"{ob.name} lightmap: {best[1]} islands, coverage {best[0]:.3f} (smoothing {best[3]})")
    me.uv_layers.active = me.uv_layers["UVMap"]
    me.uv_layers["UVMap"].active_render = True


def export(ob):
    os.makedirs(EXPORT, exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.export_scene.fbx(filepath=os.path.join(EXPORT, f"{ob.name}.fbx"), use_selection=True,
                             apply_unit_scale=True, apply_scale_options="FBX_SCALE_UNITS", axis_forward="-Y",
                             axis_up="Z", mesh_smooth_type="FACE", add_leaf_bones=False,
                             colors_type="SRGB" if ob.get("vcol") else "NONE")


def setup_render():
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.render.resolution_x, sc.render.resolution_y = 900, 700
    sc.render.film_transparent = False
    sc.render.image_settings.file_format = "PNG"
    sc.view_settings.view_transform = "Standard"
    sh = sc.display.shading
    sh.light = "STUDIO"
    sh.color_type = "MATERIAL"
    sh.show_cavity = True
    sh.cavity_type = "BOTH"
    sh.show_shadows = True
    sh.shadow_intensity = 0.35
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


# Preview-only tints (object-level material overrides; the exported mesh keeps the convention slots).
# Tree A should read as a gum: pale smooth bark and a grey-olive crown. Unreal needs the same on Tree A's
# instance (e.g. a pale bark MI on M_Bark and a grey-green tint on M_Plant / M_PlantDark) - see the handoff.
PREVIEW_TINT = {
    "SM_GardenTree_A": {"M_Bark": (0.62, 0.58, 0.52), "M_Plant": (0.30, 0.36, 0.22), "M_PlantDark": (0.16, 0.21, 0.12)},
}


def apply_tint(ob, mesh_name):
    tint = PREVIEW_TINT.get(mesh_name)
    if not tint:
        return
    for slot in ob.material_slots:
        base = slot.material.name.split(".")[0] if slot.material else ""
        if base in tint:
            pm = bpy.data.materials.get("preview_" + mesh_name + base) or bpy.data.materials.new(
                "preview_" + mesh_name + base)
            pm.diffuse_color = (*tint[base], 1.0)
            slot.link = "OBJECT"
            slot.material = pm


def preview(ob, cam, direction=(1.0, -0.8, 0.55), path=None):
    apply_tint(ob, ob.name)
    for o in bpy.context.scene.objects:
        if o.type == "MESH":
            o.hide_render = o is not ob
    sh = bpy.context.scene.display.shading
    sh.color_type = "VERTEX" if ob.get("vcol") else "MATERIAL"
    pts = [ob.matrix_world @ v.co for v in ob.data.vertices]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    c = (lo + hi) / 2
    r = max((p - c).length for p in pts)
    d = Vector(direction).normalized()
    vfov = 2 * math.atan(18 * 700 / 900 / 50)
    dist = r / math.sin(vfov / 2) * 0.92
    cam.data.type = "PERSP"
    cam.data.lens = 50
    cam.location = c + d * dist
    cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    cam.data.clip_start = dist * 0.01
    cam.data.clip_end = dist * 10
    bpy.context.scene.render.filepath = path or os.path.join(PREVIEW, f"{ob.name}.png")
    bpy.ops.render.render(write_still=True)
    sh.color_type = "MATERIAL"


def u2b(x, y, z):
    return Vector((x / 100.0, -y / 100.0, z / 100.0))


def overview(pieces, cam):
    """Garden laid out from placement.json, seen from Maria's window and from above."""
    os.makedirs(OVERVIEW, exist_ok=True)
    cfg = json.load(open(os.path.join(ROOM, "placement.json")))
    by_name = {o.name: o for o in pieces}
    inst = []
    for p in cfg["pieces"]:
        if p.get("kind") == "exterior" and p["mesh"] in by_name:
            x, y, z = p["loc"]
            mw = Matrix.Translation(u2b(x, y, z)) @ Matrix.Rotation(math.radians(-p.get("yaw", 0)), 4, "Z")
            for mesh, m in [(p["mesh"], mw)]:
                o = link("inst_" + p["label"] + mesh, by_name[mesh].data)
                o.matrix_world = m
                apply_tint(o, mesh)
                inst.append(o)
    fences = [p for p in cfg["pieces"] if p.get("mesh") == "SM_Fence"]
    if fences and "SM_Fence_EndPost" in by_name:
        last = max(fences, key=lambda p: p["loc"][1])        # proposed end post after the last segment
        x, y, z = last["loc"]
        o = link("inst_fence_end", by_name["SM_Fence_EndPost"].data)
        o.matrix_world = Matrix.Translation(u2b(x, y + 155.1, z))
        inst.append(o)
    for o in bpy.context.scene.objects:
        if o.type == "MESH":
            o.hide_render = o not in inst
    sc = bpy.context.scene
    sc.world.color = (0.62, 0.74, 0.88)
    views = [("garden_from_window", (470, 225, 140), (1500, 260, 120), 20),
             ("garden_from_window_wide", (430, 225, 150), (1400, 250, 150), 14),
             ("garden_aerial", (150, 250, 1500), (1500, 250, 0), 20),
             ("garden_bed_close", (640, 260, 120), (760, 260, 10), 28)]
    cam.data.type = "PERSP"
    cam.data.clip_start = 0.05
    cam.data.clip_end = 200
    sc.render.resolution_x, sc.render.resolution_y = 1400, 900
    for name, c, t, lens in views:
        cam.data.lens = lens
        cam.location = u2b(*c)
        look = (u2b(*t) - cam.location).normalized()
        cam.rotation_euler = look.to_track_quat("-Z", "Y").to_euler()
        sc.render.filepath = os.path.join(OVERVIEW, name + ".png")
        bpy.ops.render.render(write_still=True)
    # the review tools colour M_FlowerRed flat red; this one shows the 'Col' vertex colours (flower mix)
    sh = sc.display.shading
    sh.color_type = "VERTEX"
    for name, c, t, lens in views:
        if name != "garden_bed_close":
            continue
        cam.data.lens = lens
        cam.location = u2b(*c)
        look = (u2b(*t) - cam.location).normalized()
        cam.rotation_euler = look.to_track_quat("-Z", "Y").to_euler()
        sc.render.filepath = os.path.join(OVERVIEW, name + "_vertexcolour.png")
        bpy.ops.render.render(write_still=True)
    sh.color_type = "MATERIAL"
    sc.world.color = (1, 1, 1)
    for o in inst:
        bpy.data.objects.remove(o, do_unlink=True)


def ngon_profile(n, sx=1.0, sy=1.0, name="ngon"):
    """Closed n-sided unit polygon used as a curve bevel object (scaled by the curve point radius)."""
    cu = bpy.data.curves.new(name, "CURVE")
    sp = cu.splines.new("POLY")
    sp.points.add(n - 1)
    for k in range(n):
        a = 2 * math.pi * k / n + math.pi / n
        sp.points[k].co = (sx * math.cos(a), sy * math.sin(a), 0.0, 1.0)
    sp.use_cyclic_u = True
    return link(name, cu)


def tag_faces(ob, attr, val):
    """Integer face attribute (survives join) used to colour or re-normal parts after joining."""
    me = ob.data
    a = me.attributes.get(attr) or me.attributes.new(attr, "INT", "FACE")
    for i in range(len(me.polygons)):
        a.data[i].value = val
    return ob


def remesh_smooth(ob, voxel, smooth_fac=0.5, smooth_it=4):
    mod = ob.modifiers.new("rm", "REMESH")
    mod.mode = "VOXEL"
    mod.voxel_size = voxel
    mod.adaptivity = 0.0
    sm = ob.modifiers.new("sm", "SMOOTH")
    sm.factor = smooth_fac
    sm.iterations = smooth_it
    return bake(ob)


def soft_normals(ob, hull, mats, mix=1.0):
    """Give the faces whose material starts with one of `mats` soft, outward 'canopy' normals by
    transferring custom normals from a smooth hull (DataTransfer, POLYINTERP_NEAREST). Vertices shared
    with other materials (wood seams) get weight 0, so the wood keeps its own normals. Deletes the hull."""
    me = ob.data
    idx = {i for i, m in enumerate(me.materials) if m and m.name.startswith(tuple(mats))}
    ok = {}
    for p in me.polygons:
        inside = p.material_index in idx
        for v in p.vertices:
            ok[v] = ok.get(v, True) and inside
    vg = ob.vertex_groups.new(name="soft")
    vg.add([v for v, good in ok.items() if good], 1.0, "REPLACE")
    mod = ob.modifiers.new("dt", "DATA_TRANSFER")
    mod.object = hull
    mod.use_loop_data = True
    mod.data_types_loops = {"CUSTOM_NORMAL"}
    mod.loop_mapping = "POLYINTERP_NEAREST"
    mod.mix_mode = "REPLACE"
    mod.mix_factor = mix
    mod.vertex_group = "soft"
    name = ob.name
    out = bake(ob)
    out.name = name
    discard(hull)
    return out


def canopy_hull(canopy, voxel=25.0, iters=10, push=8.0):
    """Smooth envelope of a canopy (remesh, smooth, pushed out along its normals) for soft_normals."""
    me = canopy.data.copy()
    h = link("hull", me)
    h.matrix_world = canopy.matrix_world.copy()
    h.modifiers.clear()
    mod = h.modifiers.new("rm", "REMESH")
    mod.mode = "VOXEL"
    mod.voxel_size = voxel
    sm = h.modifiers.new("sm", "SMOOTH")
    sm.factor = 1.0
    sm.iterations = iters
    d = h.modifiers.new("dp", "DISPLACE")
    d.strength = push
    d.mid_level = 0.0
    h = bake(h)
    for p in h.data.polygons:
        p.use_smooth = True
    return h


def ellipsoid_hull(ob, mats, grow=1.05):
    """UV-sphere proxy scaled to the bounds of the faces of `mats` (cm), for soft_normals."""
    me = ob.data
    idx = {i for i, m in enumerate(me.materials) if m and m.name.startswith(tuple(mats))}
    vs = {v for p in me.polygons if p.material_index in idx for v in p.vertices}
    cs = [me.vertices[v].co for v in vs]
    lo = Vector((min(c.x for c in cs), min(c.y for c in cs), min(c.z for c in cs)))
    hi = Vector((max(c.x for c in cs), max(c.y for c in cs), max(c.z for c in cs)))
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=16, radius=1.0)
    c, s = (lo + hi) / 2, (hi - lo) / 2 * grow
    for v in bm.verts:
        v.co = Vector((c.x + v.co.x * s.x, c.y + v.co.y * s.y, c.z + v.co.z * s.z))
    for f in bm.faces:
        f.smooth = True
    m2 = bpy.data.meshes.new("ellipsoid")
    bm.to_mesh(m2)
    bm.free()
    return link("ellipsoid", m2)


FLOWER_HUES = [  # sRGB vertex colours carried by the single M_FlowerRed slot
    ("red", (0.80, 0.07, 0.08)), ("pink", (0.95, 0.45, 0.64)), ("white", (0.96, 0.95, 0.91)),
    ("yellow", (0.99, 0.80, 0.10)), ("purple", (0.52, 0.27, 0.74)), ("cerise", (0.86, 0.14, 0.42)),
    ("lilac", (0.80, 0.70, 0.93)), ("gold", (0.92, 0.62, 0.05)), ("brown", (0.36, 0.21, 0.06)),
    ("orange", (0.95, 0.35, 0.06)), ("ripe", (0.78, 0.08, 0.05)), ("linen", (0.86, 0.82, 0.72)),
    ("leafdark", (0.17, 0.33, 0.12)),
]


HUE = {n: i + 1 for i, (n, _) in enumerate(FLOWER_HUES)}


def paint_hues(ob):
    """'Col' BYTE_COLOR corner attribute: faces tagged with a 'hue' get that colour (the flower / fruit
    variety, all on the one M_FlowerRed slot); every other face gets its material's preview colour, so
    a vertex-colour preview reads correctly. Unreal: M_FlowerRed base colour = VertexColor."""
    me = ob.data
    lin = {}
    for i, (_, c) in enumerate(FLOWER_HUES):
        lin[i + 1] = tuple(((x + 0.055) / 1.055) ** 2.4 if x > 0.04045 else x / 12.92 for x in c)
    hue = me.attributes.get("hue")
    col = me.color_attributes.new("Col", "BYTE_COLOR", "CORNER")
    for p in me.polygons:
        h = hue.data[p.index].value if hue else 0
        if h:
            c = lin[h]
        else:
            m = me.materials[p.material_index]
            c = PALETTE.get(m.name.split(".")[0], (0.5, 0.5, 0.5)) if m else (0.5, 0.5, 0.5)
        for li in p.loop_indices:
            col.data[li].color = (*c, 1.0)
    me.color_attributes.active_color = col
    me.color_attributes.render_color_index = me.color_attributes.find("Col")
    if hue:
        me.attributes.remove(hue)
    ob["vcol"] = True
    return ob


def up_normals(ob, attr="upn", bias=1.0):
    """Custom normals for faces tagged `attr`: their smooth vertex normal bent towards +Z (soft, lit-from-
    above foliage); all other corners keep their current normals."""
    me = ob.data
    a = me.attributes.get(attr)
    if a is None:
        return ob
    cn = [Vector(c.vector) for c in me.corner_normals]
    vn = [Vector(v.normal) for v in me.vertices]
    for p in me.polygons:
        if a.data[p.index].value:
            for li in p.loop_indices:
                n = vn[me.loops[li].vertex_index]
                if n.z < 0:
                    n = -n
                cn[li] = (n + Vector((0, 0, bias))).normalized()
    me.normals_split_custom_set(cn)
    me.attributes.remove(a)
    return ob


def round_leaf(r, m, nrim=8, notch=0.35, scallop=0.08, lift=0.18, name="leaf"):
    """Geranium leaf: single-sided rounded fan (nrim rim verts round a centre vertex), notched at the
    stalk (base at the origin, leaf pointing +X), alternate rim verts pulled in for scallops, rim lifted
    `lift` x r into a shallow cup. Smooth shaded. M_Plant is two-sided in Unreal (see module notes)."""
    bm = bmesh.new()
    c = Vector((r, 0.0, 0.0))     # leaf centre
    ctr = bm.verts.new((c.x, c.y, 0.0))
    ring = []
    for k in range(nrim):
        th = math.pi + 2 * math.pi * k / nrim
        if k == 0:
            rr = r * notch            # the sinus at the stalk
        else:
            rr = r * (1.0 - scallop * (k % 2))
        x, y = c.x + rr * math.cos(th), c.y + rr * math.sin(th)
        z = lift * r * (rr / r) ** 2
        ring.append(bm.verts.new((x, y, z)))
    for k in range(nrim):
        bm.faces.new((ctr, ring[k], ring[(k + 1) % nrim]))
    for f in bm.faces:
        if f.normal.z < 0:
            f.normal_flip()
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = link(name, me)
    set_mat(ob, m)
    for p in ob.data.polygons:
        p.use_smooth = True
    # base sits at the notch vertex: shift so the notch is at the origin
    move(ob, (-(r - r * notch), 0, 0))
    return ob


def strap_leaf(L, W, m, crease=0.15, bend=30.0, name="strap"):
    """Daisy leaf: narrow strap, single-sided (base, two cross rows of left/mid/right, tip: 8 tris),
    shallow V along the midrib, curled down with a SimpleDeform BEND."""
    bm = bmesh.new()
    base = bm.verts.new((0.0, 0.0, 0.0))
    tip = bm.verts.new((L, 0.0, 0.0))
    rows = []
    for u, wf in ((0.3, 0.85), (0.68, 1.0)):
        w = W * wf / 2
        rows.append((bm.verts.new((u * L, -w, 0.0)), bm.verts.new((u * L, 0.0, crease * wf)),
                     bm.verts.new((u * L, w, 0.0))))
    fs = [(base, rows[0][0], rows[0][1]), (base, rows[0][1], rows[0][2])]
    fs += [(rows[0][0], rows[1][0], rows[1][1], rows[0][1]), (rows[0][1], rows[1][1], rows[1][2], rows[0][2])]
    fs += [(rows[1][0], tip, rows[1][1]), (rows[1][1], tip, rows[1][2])]
    for f in fs:
        bm.faces.new(f)
    bmesh.ops.triangulate(bm, faces=bm.faces)
    for f in bm.faces:
        if f.normal.z < 0:
            f.normal_flip()
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = link(name, me)
    if bend:
        ob = bend_down(ob, bend)
    set_mat(ob, m)
    for p in ob.data.polygons:
        p.use_smooth = True
    return ob


def daisy_disc(R, npet, m, cup=0.5, rng=None, name="daisy"):
    """Daisy ray florets: single-sided star fan (tip + notch per petal) facing +Z, cupped; plus a small
    open-bottomed 5-sided dome for the eye, 0.25 cm above the disc. Both on `m` (vertex-coloured)."""
    rng = rng or random.Random(0)
    bm = bmesh.new()
    ctr = bm.verts.new((0.0, 0.0, 0.0))
    ring = []
    step = 2 * math.pi / npet
    a0 = rng.uniform(0, step)
    for k in range(npet):
        a = a0 + k * step
        rr = R * rng.uniform(0.9, 1.05)
        ring.append(bm.verts.new((rr * math.cos(a), rr * math.sin(a), cup * (rr / R) ** 2)))
        a2 = a + 0.5 * step
        ring.append(bm.verts.new((0.4 * R * math.cos(a2), 0.4 * R * math.sin(a2), cup * 0.16)))
    n = len(ring)
    for i in range(n):
        bm.faces.new((ctr, ring[i], ring[(i + 1) % n]))
    disc = bm_obj(bm, name, m, angle=80.0, recalc=False)
    bm = bmesh.new()
    apex = bm.verts.new((0, 0, 0.75))
    rv = [bm.verts.new((0.55 * math.cos(2 * math.pi * k / 5), 0.55 * math.sin(2 * math.pi * k / 5), 0.25))
          for k in range(5)]
    for k in range(5):
        bm.faces.new((apex, rv[k], rv[(k + 1) % 5]))
    eye = bm_obj(bm, name + "_eye", m, angle=80.0, recalc=False)
    return disc, eye


def shelf_pack(me, layer="Lightmap", margin=0.02):
    """Pack the UV islands of `layer` into 0..1 with a shelf packer (Blender 5.0's pack_islands shrinks
    and mis-places islands when run headless). Islands keep their relative scale (average_islands_scale
    ran first), are turned so they lie landscape, sorted by height, and laid in rows with `margin`
    between neighbours and margin/2 to the border; the largest scale that fits is found by bisection."""
    uv = me.uv_layers[layer].data
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    parent = list(range(len(bm.faces)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for e in bm.edges:
        lf = e.link_faces
        if len(lf) != 2:
            continue
        f0, f1 = lf
        ok = True
        for v in e.verts:
            l0 = next(l for l in f0.loops if l.vert == v)
            l1 = next(l for l in f1.loops if l.vert == v)
            if (uv[l0.index].uv - uv[l1.index].uv).length > 1e-5:
                ok = False
                break
        if ok:
            a, b = find(f0.index), find(f1.index)
            if a != b:
                parent[a] = b
    isl = {}
    for f in bm.faces:
        isl.setdefault(find(f.index), []).append([l.index for l in f.loops])
    bm.free()
    from mathutils.geometry import convex_hull_2d
    boxes = []
    for loops in isl.values():
        li = [i for fl in loops for i in fl]
        pts = [uv[i].uv.copy() for i in li]
        hull = [pts[k] for k in convex_hull_2d(pts)] if len(pts) > 2 else pts
        best_a, best_area = 0.0, None
        for k in range(len(hull)):      # minimum-area bounding rectangle (rotating calipers)
            e = hull[(k + 1) % len(hull)] - hull[k]
            if e.length < 1e-9:
                continue
            a = -math.atan2(e.y, e.x)
            c, sn = math.cos(a), math.sin(a)
            xs = [p.x * c - p.y * sn for p in hull]
            ys = [p.x * sn + p.y * c for p in hull]
            ar = (max(xs) - min(xs)) * (max(ys) - min(ys))
            if best_area is None or ar < best_area:
                best_a, best_area = a, ar
        c, sn = math.cos(best_a), math.sin(best_a)
        for i in li:
            x, y = uv[i].uv
            uv[i].uv = (x * c - y * sn, x * sn + y * c)
        us = [uv[i].uv[0] for i in li]
        vs = [uv[i].uv[1] for i in li]
        u0, v0, w, h = min(us), min(vs), max(us) - min(us), max(vs) - min(vs)
        rot = h > w
        boxes.append([li, u0, v0, w, h, rot, (h, w) if rot else (w, h)])
    boxes.sort(key=lambda b: -b[6][1])

    def layout(s):
        x, y, row_h, pos = margin / 2, margin / 2, 0.0, []
        for b in boxes:
            w, h = b[6][0] * s, b[6][1] * s
            if x + w > 1.0 - margin / 2 + 1e-9:
                x, y, row_h = margin / 2, y + row_h + margin, 0.0
            if y + h > 1.0 - margin / 2 + 1e-9 or w > 1.0 - margin:
                return None
            pos.append((x, y))
            x += w + margin
            row_h = max(row_h, h)
        return pos
    lo, hi = 0.0, 100.0
    tot = sum(b[6][0] * b[6][1] for b in boxes) or 1.0
    hi = min(hi, 1.0 / math.sqrt(tot) * 1.2 + 1e-6)
    best = None
    for _ in range(40):
        mid = (lo + hi) / 2
        p = layout(mid)
        if p is None:
            hi = mid
        else:
            lo, best = mid, p
    s = lo
    if os.environ.get("LM_DEBUG"):
        log(f"shelf scale {s:.3f}; biggest boxes {[(round(b[6][0] * s, 3), round(b[6][1] * s, 3)) for b in boxes[:6]]}; "
            f"box area {sum(b[6][0] * b[6][1] for b in boxes) * s * s:.3f}")
    for b, (px, py) in zip(boxes, best):
        li, u0, v0, w, h, rot = b[:6]
        for i in li:
            du, dv = uv[i].uv[0] - u0, uv[i].uv[1] - v0
            if rot:      # turn 90 deg: (du, dv) -> (dv, h - du) keeps it inside its box
                du, dv = dv, w - du
            uv[i].uv = (px + du * s, py + dv * s)
    return len(boxes)


def chain_strip(bm, a, b):
    """Triangles between two vertex chains that share their first and last vertex, each sorted by x
    (distance along the leaf); advances along whichever chain's next vertex is nearer the base."""
    bm.faces.new((a[0], a[1], b[1]))          # shared base
    i, j = 1, 1
    while i < len(a) - 2 or j < len(b) - 2:
        if j >= len(b) - 2 or (i < len(a) - 2 and a[i + 1].co.x <= b[j + 1].co.x):
            bm.faces.new((a[i], a[i + 1], b[j]))
            i += 1
        else:
            bm.faces.new((a[i], b[j + 1], b[j]))
            j += 1
    bm.faces.new((a[i], a[-1], b[j]))         # shared tip


def tomato_leaflet(L, W, m, teeth=3, curl=24.0, name="leaflet"):
    """Tomato leaflet, single-sided strip mesh: a midrib row of interior vertices raised 0.08 x W (crease),
    each side's serrated rim (alternating 1.0 / ~0.75 of the half-width, pointed tip: u 0.88 at ~0.38)
    cupped down 0.12 x W x |v| and fanned to the midrib; then curled down with a SimpleDeform BEND, which
    now bends the surface itself. teeth=3: 18 tris, teeth=2: 14, teeth=1 (tiny interstitial): 4."""
    w2 = W / 2
    if teeth >= 3:
        rim = [(0.22, 0.95), (0.45, 0.74), (0.66, 0.9), (0.88, 0.38)]
        mid = [0.25, 0.5, 0.75]
    elif teeth == 2:
        rim = [(0.28, 0.95), (0.56, 0.76), (0.86, 0.4)]
        mid = [0.33, 0.66]
    else:
        rim = [(0.45, 0.9)]
        mid = [0.5]

    def env(u):
        return math.sin(math.pi * min(0.98, u) ** 0.85) ** 0.6

    bm = bmesh.new()
    base = bm.verts.new((0.0, 0.0, 0.0))
    tip = bm.verts.new((L, 0.0, -0.04 * W))
    mids = [bm.verts.new((u * L, 0.0, 0.08 * W * env(u))) for u in mid]
    for sg in (-1, 1):
        rv = []
        for u, f in rim:
            y = w2 * f * (env(u) if u < 0.8 else 1.0)
            v = abs(y) / w2
            rv.append(bm.verts.new((u * L, sg * y, -0.12 * W * v)))
        a = [base] + rv + [tip]
        b = [base] + mids + [tip]
        if sg > 0:
            chain_strip(bm, b, a)
        else:
            chain_strip(bm, a, b)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    if sum((f.normal.z for f in bm.faces), 0.0) < 0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = link(name, me)
    if curl:
        ob = bend_down(ob, curl)
    set_mat(ob, m)
    smooth(ob, 75.0, recalc=False)
    return ob


def tomato_fruit(c, r, m, hue=None, seg=8, rings=6, rng=None):
    """Tomato: UV sphere (seg x rings) scaled to (1, 1, 0.82), every other vertex of the top two rings
    pushed down 0.15 cm for the shoulder lobes; smooth shaded. Plus a calyx: a 5-point star (10-vertex
    outline, radii 1.4 / 0.4 cm, centre raised 0.35 cm into a stem nub) 0.2 cm above the fruit top with
    its tips bent down ~25 deg but never closer than 0.2 cm to the fruit. Returns (fruit, calyx, apex)."""
    rng = rng or random.Random(0)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=rings, radius=1.0)
    zs = sorted({round(v.co.z, 4) for v in bm.verts}, reverse=True)
    top_rings = zs[1:3]
    for v in bm.verts:
        v.co = Vector((v.co.x * r, v.co.y * r, v.co.z * r * 0.82))
    for zr in top_rings:
        ring = sorted([v for v in bm.verts if abs(v.co.z / (r * 0.82) - zr) < 1e-3],
                      key=lambda v: math.atan2(v.co.y, v.co.x))
        for k, v in enumerate(ring):
            if k % 2 == 0:
                v.co.z -= 0.15
    for f in bm.faces:
        f.smooth = True
    me = bpy.data.meshes.new("fruit")
    bm.to_mesh(me)
    bm.free()
    fruit = link("fruit", me)
    set_mat(fruit, m)
    move(fruit, c)
    if hue:
        tag_faces(fruit, "hue", HUE[hue])
    ztop = c[2] + 0.82 * r
    cz = ztop + 0.2

    def surf(rho):
        return c[2] + 0.82 * math.sqrt(max(0.0, r * r - rho * rho))
    bm = bmesh.new()
    a0 = rng.uniform(0, 2 * math.pi)
    ring = []
    for k in range(10):
        a = a0 + 2 * math.pi * k / 10
        rho = 1.4 if k % 2 == 0 else 0.4
        z = cz - (0.6 if k % 2 == 0 else 0.05)
        z = max(z, surf(rho) + 0.2)
        ring.append(bm.verts.new((c[0] + rho * math.cos(a), c[1] + rho * math.sin(a), z)))
    apex = Vector((c[0], c[1], cz + 0.35))
    ctr = bm.verts.new(apex)
    for k in range(10):
        bm.faces.new((ctr, ring[k], ring[(k + 1) % 10]))
    for f in bm.faces:
        if f.normal.z < 0:
            f.normal_flip()
    me = bpy.data.meshes.new("calyx")
    bm.to_mesh(me)
    bm.free()
    calyx = link("calyx", me)
    set_mat(calyx, "M_Plant")
    return fruit, calyx, apex


def basil_leaf(L, m, wr=0.7, cup=0.3, rib=0.15, stalk=1.0, name="bleaf"):
    """Sweet basil leaf, single-sided (~20 tris): a short petiole wedge from the origin to the leaf base at
    x = `stalk`, then a broad ovate blade (width `wr` x L): 5 rim samples per side at u = 0.10 .. 0.88 with
    half-width W/2 sin(pi u)^0.75 (rounded base, widest near 40 %), a blunt tip of two vertices at u 0.97,
    and a midrib (u 0.35 / 0.68 / 0.88) raised `rib` x width with the edges curled down `cup` x width:
    the convex, glossy basil cup. Smooth shaded. M_Plant is two-sided in Unreal."""
    W = L * wr
    bm = bmesh.new()

    def wid(u):
        return W / 2 * math.sin(math.pi * u) ** 0.75

    def rim_z(y):
        return -cup * W * (abs(y) / (W / 2)) ** 2 + rib * W * 0.15

    s0 = bm.verts.new((0.0, -0.06, 0.0))
    s1 = bm.verts.new((0.0, 0.06, 0.0))
    b = bm.verts.new((stalk, 0.0, 0.0))
    mids = [bm.verts.new((stalk + u * L, 0.0, rib * W * f)) for u, f in ((0.35, 1.0), (0.68, 0.75), (0.88, 0.45))]
    tips = {}
    for sg in (-1, 1):
        y = sg * 0.12 * W
        tips[sg] = bm.verts.new((stalk + 0.97 * L, y, rim_z(y) * 0.6))
    faces = [(s0, s1, b)]
    for sg in (-1, 1):
        rv = []
        for u in (0.10, 0.28, 0.50, 0.70, 0.88):
            y = sg * wid(u)
            rv.append(bm.verts.new((stalk + u * L, y, rim_z(y))))
        a = [b] + rv + [tips[sg]]
        c = [b] + mids + [tips[sg]]
        i, k = 0, 0                       # strip between the rim chain and the midrib chain
        while i < len(a) - 1 or k < len(c) - 1:
            if k >= len(c) - 1 or (i < len(a) - 1 and a[i + 1].co.x <= c[k + 1].co.x):
                if a[i + 1] is c[k]:
                    i += 1
                    continue
                faces.append((a[i], a[i + 1], c[k]))
                i += 1
            else:
                if c[k + 1] is a[i]:
                    k += 1
                    continue
                faces.append((a[i], c[k + 1], c[k]))
                k += 1
    faces.append((mids[-1], tips[-1], tips[1]))      # blunt tip
    for f in faces:
        if len(set(f)) < 3:
            continue
        fc = bm.faces.new(f)
        fc.normal_update()
        if fc.normal.z < 0:
            fc.normal_flip()
        fc.smooth = True
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = link(name, me)
    set_mat(ob, m)
    return ob


def lightmap_pass(ob, its, margin):
    """One Lightmap unwrap: smart project per material group (wood / timber 66 deg, foliage and soft parts
    80 deg, no island margin) on a copy of the shape Laplacian-smoothed `its` times (noise-free normals ->
    fewer, larger islands; the real positions are restored afterwards), average island scale, then two
    layouts - Blender's concave packer (ADD margin; headless it under-fills the square, so the result is
    scaled up uniformly, margins only grow) and the shelf packer - keeping the fuller one.
    Returns (coverage, islands, uv list)."""
    me = ob.data
    soft = ("M_Plant", "M_Flower", "M_Soil", "M_Grass", "M_Linen")
    groups = {}
    for i, m in enumerate(me.materials):
        groups.setdefault(80 if (m and m.name.startswith(soft)) else 66, []).append(i)
    orig = [v.co.copy() for v in me.vertices]
    if its:
        nb = [[] for _ in me.vertices]
        for e in me.edges:
            a, b = e.vertices
            nb[a].append(b)
            nb[b].append(a)
        co = [c.copy() for c in orig]
        for _ in range(its):
            co = [co[i].lerp(sum((co[j] for j in nb[i]), Vector()) / len(nb[i]), 0.5) if nb[i] else co[i]
                  for i in range(len(co))]
        for v, c in zip(me.vertices, co):
            v.co = c
    me.uv_layers.active = me.uv_layers["Lightmap"]
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.context.scene.tool_settings.use_uv_select_sync = True
    bpy.ops.object.mode_set(mode="EDIT")
    for ang, mats in groups.items():
        bpy.ops.mesh.select_all(action="DESELECT")
        for mi in mats:
            ob.active_material_index = mi
            bpy.ops.object.material_slot_select()
        bpy.ops.uv.smart_project(angle_limit=math.radians(ang), island_margin=0.0, scale_to_bounds=False)
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.average_islands_scale()
    bpy.ops.uv.pack_islands(margin=margin, rotate=True, scale=True, shape_method="CONCAVE", margin_method="ADD")
    bpy.ops.object.mode_set(mode="OBJECT")
    for v, c in zip(me.vertices, orig):
        v.co = c
    d = me.uv_layers["Lightmap"].data
    me.calc_loop_triangles()

    def coverage():
        cv = 0.0
        for t in me.loop_triangles:
            p = [d[i].uv for i in t.loops]
            cv += abs((p[1].x - p[0].x) * (p[2].y - p[0].y) - (p[2].x - p[0].x) * (p[1].y - p[0].y)) / 2
        return cv
    us = [e.uv[0] for e in d]
    vs = [e.uv[1] for e in d]
    u0, v0 = min(us), min(vs)
    k = (1.0 - margin) / max(max(us) - u0, max(vs) - v0, 1e-6)
    for e in d:
        e.uv = (margin / 2 + (e.uv[0] - u0) * k, margin / 2 + (e.uv[1] - v0) * k)
    c1 = coverage()
    keep = [e.uv.copy() for e in d]
    n = shelf_pack(me, "Lightmap", margin)
    c2 = coverage()
    if c1 > c2:
        for e, u in zip(d, keep):
            e.uv = u
    return max(c1, c2), n, [e.uv.copy() for e in d]


BUILDERS = {
    "SM_Lawn": lawn, "SM_FlowerBed": flower_bed, "SM_GardenTree_A": lambda: tree("A"),
    "SM_GardenTree_B": lambda: tree("B"), "SM_Shrub": shrub, "SM_Fence": fence, "SM_Fence_EndPost": fence_end_post,
    "SM_GardenBench": bench,
    "SM_TomatoPlant": tomato_plant, "SM_BasilPot": basil_pot, "SM_FigTree": fig_tree, "SM_GardenHose": garden_hose,
}


def build():
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    os.makedirs(PREVIEW, exist_ok=True)
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    only = [a for a in args if a.startswith("SM_")]
    if "--overview-only" in args:
        # re-render the garden overview from the exported FBXs (nothing rebuilt or re-exported)
        pieces = []
        for n in BUILDERS:
            path = os.path.join(EXPORT, n + ".fbx")
            if not os.path.exists(path):
                continue
            before = set(bpy.data.objects)
            bpy.ops.import_scene.fbx(filepath=path)
            for o in set(bpy.data.objects) - before:
                if o.type != "MESH":
                    bpy.data.objects.remove(o, do_unlink=True)
                    continue
                o.data.transform(o.matrix_world)
                o.matrix_world = Matrix.Identity(4)
                o.name = n
                for m in o.data.materials:
                    if m and m.name.split(".")[0] in PALETTE:
                        m.diffuse_color = (*PALETTE[m.name.split(".")[0]], 1.0)
                if o.data.color_attributes:
                    o.data.color_attributes.render_color_index = 0
                pieces.append(o)
        overview(pieces, setup_render())
        return
    names = only or list(BUILDERS)
    pieces = []
    for n in names:
        res = BUILDERS[n]()
        for ob in (res if isinstance(res, list) else [res]):
            pieces.append(ob)
            log(f"built {ob.name}: {tri_count(ob)} tris")
    cam = setup_render()
    report = []
    for ob in pieces:
        uvs(ob)
        for lay in ob.data.uv_layers:
            us = [d.uv[0] for d in lay.data]
            vs = [d.uv[1] for d in lay.data]
            log(f"{ob.name} uv '{lay.name}': u {min(us):.3f}..{max(us):.3f} v {min(vs):.3f}..{max(vs):.3f}")
        export(ob)
        preview(ob, cam, (0.25, -1.0, 0.9) if ob.name == "SM_Lawn" else (1.0, -0.8, 0.55))
        lo, hi = bounds(ob)
        lo, hi = lo * 100, hi * 100
        report.append(f"{ob.name}: tris={tri_count(ob)} mats={[m.name for m in ob.data.materials]} "
                      f"uv={[u.name for u in ob.data.uv_layers]} "
                      f"bbox_cm=({lo.x:.1f},{lo.y:.1f},{lo.z:.2f})..({hi.x:.1f},{hi.y:.1f},{hi.z:.2f})")
    if not only:
        overview(pieces, cam)
    print("\n".join(["GARDEN REPORT"] + report + LOG))


build()
