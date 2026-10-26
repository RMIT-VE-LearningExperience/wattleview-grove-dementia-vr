"""Blender (headless): seating for Maria's room -> SM_Recliner, SM_Armchair.

Run:
  "C:\\Program Files\\Blender Foundation\\Blender 5.0\\blender.exe" -b --factory-startup --python seating.py

Follows SourceArt/Room/CONVENTIONS.md:
  * Modelled in Unreal centimetres around the piece pivot (bottom centre on the floor), front = +X.
    Geometry is written straight into Blender metres in Blender axes (Blender Y = -Unreal Y), so the
    convention ue(x, y, z) = (x/100, -y/100, z/100) holds for every vertex.
  * Soft goods are real shapes: rounded, puffed cushions (soft_box); the recliner's seams carry real
    piping cord (a D-section swept along the seam loops, floating 0.15-0.25 cm off the upholstery);
    the recliner's knitted throw (70 x 110, folded lengthwise) is a two-stage cloth simulation draped
    over the arm and seat; timber parts are lathed (Screw modifier) or swept along curves.
  * Hard parts that join in reality (chair frame; recliner arms/back/footrest) are fused with an EXACT
    boolean union, so no part passes through another; separate soft parts keep >= 0.2 cm air gaps.
  * UV0 'UVMap' (smart unwrap rescaled to 1 UV = 1 m), UV1 'Lightmap': unwrapped per part before the
    booleans (lathe meridian seam, sweep tube seam, smart project), welded, packed with a 2 % margin.
  * SEATING_ONLY=recliner|armchair builds just one piece.
  * Exports Export/SM_<Name>.fbx and renders Previews/SM_<Name>.png (Workbench, 900x700).
"""
import math
import os
import sys
import time

import bmesh
import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

ROOT = r"D:\Unreal-Projects\WattleviewGrove-ue58\SourceArt\Room"
EXPORT_DIR = os.environ.get("SEATING_EXPORT_DIR", os.path.join(ROOT, "Export"))
PREVIEW_DIR = os.environ.get("SEATING_PREVIEW_DIR", os.path.join(ROOT, "Previews"))
DEBUG_DIR = os.environ.get("SEATING_DEBUG_DIR", "")          # optional extra views
S = 0.01                                                     # cm -> Blender metres

MATS = {
    "M_Timber": (0.70, 0.55, 0.38),
    "M_TimberDark": (0.36, 0.23, 0.13),
    "M_UpholsteryPink": (0.74, 0.47, 0.50),
    "M_UpholsteryCream": (0.82, 0.75, 0.64),
    "M_Crochet": (0.80, 0.42, 0.40),
}


def log(*a):
    print("[seating]", *a)
    sys.stdout.flush()


def mat(name):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.diffuse_color = (*MATS[name], 1.0)
    return m


def link(name, me):
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def tri_count(me):
    return sum(len(p.vertices) - 2 for p in me.polygons)


def bake_object(ob, name=None):
    """Evaluate modifiers + transform into a fresh mesh object at the origin; delete the source."""
    if isinstance(ob.data, bpy.types.Mesh):
        ob.data.update()
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    me.transform(ob.matrix_world)
    mats = [m for m in ob.data.materials] if hasattr(ob.data, "materials") else []
    nm = name or ob.name
    data = ob.data
    bpy.data.objects.remove(ob, do_unlink=True)
    bpy.context.view_layer.update()
    if isinstance(data, bpy.types.Curve) and data.users == 0:
        bpy.data.curves.remove(data)
    elif isinstance(data, bpy.types.Mesh) and data.users == 0:
        bpy.data.meshes.remove(data)
    me.materials.clear()
    for m in mats:
        me.materials.append(m)
    return link(nm, me)


def recalc_normals(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(ob.data)
    bm.free()


# ---------------------------------------------------------------- soft (upholstered) shapes
SOFT_KEYS = {}          # soft_box object name -> (samples per axis, {grid key: vertex index})


def _rad(r, ax):
    if isinstance(r, dict):
        v = r.get(ax, 2.0)
    else:
        v = r
    return (v, v) if not isinstance(v, (tuple, list)) else tuple(v)


def _axis_samples(h, rn, rp, mn, mp, nflat, seam=None, sd=0.0):
    a, b = -h + rn, h - rp
    s = []
    for k in range(mn):
        s.append(a - rn * math.tan(math.radians(45.0 * (mn - k) / mn)))
    if b - a > 1e-6:
        s += [a + (b - a) * i / nflat for i in range(nflat + 1)]
    else:
        s.append(a)
    for k in range(mp - 1, -1, -1):
        s.append(b + rp * math.tan(math.radians(45.0 * (mp - k) / mp)))
    if seam is not None:
        lo, hi = s[0], s[-1]
        s = [v for v in s if abs(v - seam) > 1.6 * sd or v in (lo, hi)]
        s += [seam - sd, seam, seam + sd]
    return sorted(set(round(v, 5) for v in s))


def soft_box(name, mname, x0, x1, y0, y1, z0, z1, r=3.0, m=2, nflat=(2, 2, 2), puff=None, seam=None,
             drop=(), deform=None):
    """Upholstered block with rounded (elliptical) edges, puffed panels and an optional piped seam.

    Extents in Unreal-style cm but Blender axes (front +X, up +Z).
    r      scalar or {'x': rn_or_(rneg, rpos), ...} edge radii per axis/side.
    m      arc segments per half-corner (scalar or per-axis tuple, each entry an int or (neg, pos));
           2 => 4 segments round a 90 deg edge.
    puff   {'+z': cm, '-x': cm, ...} outward bulge at the panel centres (zero at the edges).
    seam   (axis, position_cm_world, bead_cm, half_width_cm): piping ring round the block.
    drop   sides to omit because they are hidden (e.g. '-z' bottoms), saves triangles.
    deform f(Vector_cm) -> Vector_cm applied last (shear/lean/bend).
    """
    C = Vector(((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2))
    H = Vector(((x1 - x0) / 2, (y1 - y0) / 2, (z1 - z0) / 2))
    axes = "xyz"
    R = []
    for i, ax in enumerate(axes):
        rn, rp = _rad(r, ax)
        R.append((min(rn, H[i] * 0.999), min(rp, H[i] * 0.999)))
    M = m if isinstance(m, (tuple, list)) else (m, m, m)
    puff = puff or {}
    samp = []
    for i, ax in enumerate(axes):
        sp = None
        sd = 0.0
        if seam and seam[0] == ax:
            sp = seam[1] - C[i]
            sd = seam[3]
        mn_, mp_ = (M[i], M[i]) if not isinstance(M[i], (tuple, list)) else M[i]   # per-side arc counts
        samp.append(_axis_samples(H[i], R[i][0], R[i][1], mn_, mp_, nflat[i], sp, sd))
    seam_ax = axes.index(seam[0]) if seam else -1
    seam_idx = {}
    if seam:
        arr = samp[seam_ax]
        sp = round(seam[1] - C[seam_ax], 5)
        for j, v in enumerate(arr):
            if abs(v - sp) < 1e-4:
                seam_idx[j] = 1.0
            elif abs(abs(v - sp) - seam[3]) < 1e-4:
                seam_idx[j] = -0.35

    bm = bmesh.new()
    vmap = {}

    def vert(ix, iy, iz):
        key = (ix, iy, iz)
        if key in vmap:
            return vmap[key]
        p = Vector((samp[0][ix], samp[1][iy], samp[2][iz]))
        c = Vector(p)
        u = Vector((0, 0, 0))
        rr = [0, 0, 0]
        for a in range(3):
            lo, hi = -H[a] + R[a][0], H[a] - R[a][1]
            if p[a] < lo - 1e-7:
                c[a], rr[a] = lo, R[a][0]
                u[a] = (p[a] - lo) / R[a][0]
            elif p[a] > hi + 1e-7:
                c[a], rr[a] = hi, R[a][1]
                u[a] = (p[a] - hi) / R[a][1]
            else:
                rr[a] = max(R[a][0], R[a][1])
        L = u.length
        nn = u / L if L > 1e-9 else Vector((0, 0, 1))
        q = Vector([c[a] + nn[a] * (rr[a] if abs(u[a]) > 0 else 0.0) for a in range(3)])
        # surface normal estimate of the ellipse corner
        g = Vector([nn[a] / max(rr[a], 1e-6) for a in range(3)])
        g = g.normalized() if g.length > 1e-9 else nn
        disp = 0.0
        for key2, amt in puff.items():
            sgn = 1.0 if key2[0] == "+" else -1.0
            a = axes.index(key2[1])
            comp = g[a] * sgn
            if comp <= 0:
                continue
            prod = 1.0
            for b in range(3):
                if b != a:
                    t = p[b] / H[b]
                    prod *= max(0.0, 1.0 - t * t)
            disp += comp * comp * amt * prod
        q += g * disp
        if seam and key[seam_ax] in seam_idx:
            perp = Vector(g)
            perp[seam_ax] = 0.0
            if perp.length > 1e-6:
                q += perp.normalized() * seam[2] * seam_idx[key[seam_ax]]
        w = C + q
        if deform:
            w = deform(w)
        v = bm.verts.new(w * S)
        vmap[key] = v
        return v

    n = [len(s) for s in samp]
    for a in range(3):
        b, c = [k for k in range(3) if k != a]
        for side, fixed in (("-", 0), ("+", n[a] - 1)):
            if (side + axes[a]) in drop:
                continue
            for i in range(n[b] - 1):
                for j in range(n[c] - 1):
                    quad = []
                    for (di, dj) in ((0, 0), (1, 0), (1, 1), (0, 1)):
                        idx = [0, 0, 0]
                        idx[a], idx[b], idx[c] = fixed, i + di, j + dj
                        quad.append(tuple(idx))
                    # orientation from the undeformed box
                    pts = [Vector((samp[0][k[0]], samp[1][k[1]], samp[2][k[2]])) for k in quad]
                    nrm = (pts[1] - pts[0]).cross(pts[2] - pts[0])
                    if (nrm[a] > 0) != (side == "+"):
                        quad.reverse()
                    bm.faces.new([vert(*k) for k in quad])
    if not drop:      # lightmap seam: one loop round the middle of the shortest axis -> two halves
        a = min(range(3), key=lambda i: H[i])
        k = n[a] // 2
        key_of = {v: kk for kk, v in vmap.items()}
        for e in bm.edges:
            e.seam = all(key_of[v][a] == k for v in e.verts)
    bm.verts.index_update()
    keys = {k: v.index for k, v in vmap.items()}
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat(mname))
    ob = link(name, me)
    SOFT_KEYS[ob.name] = (n, keys)
    lm_abf(ob)
    return ob


def bevel_box(name, mname, x0, x1, y0, y1, z0, z1, bevel=0.3, segments=1):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector((x1 if v.co.x > 0 else x0, y1 if v.co.y > 0 else y0, z1 if v.co.z > 0 else z0)) * S
    bmesh.ops.bevel(bm, geom=list(bm.edges) + list(bm.verts), offset=bevel * S, segments=segments,
                    affect="EDGES", profile=0.5, clamp_overlap=True)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat(mname))
    ob = link(name, me)
    lm_smart(ob)
    return ob


# ---------------------------------------------------------------- lathe and sweep
def lathe(name, mname, profile, steps=10, loc=(0, 0, 0), tilt=None):
    """Turned part: profile [(radius_cm, z_cm), ...] revolved about local Z with a Screw modifier."""
    me = bpy.data.meshes.new(name)
    verts = [(r * S, 0.0, z * S) for r, z in profile]
    edges = [(i, i + 1) for i in range(len(verts) - 1)]
    me.from_pydata(verts, edges, [])
    me.materials.append(mat(mname))
    ob = link(name, me)
    sc = ob.modifiers.new("lathe", "SCREW")
    sc.axis = "Z"
    sc.angle = math.tau
    sc.steps = steps
    sc.render_steps = steps
    sc.use_merge_vertices = True
    sc.merge_threshold = 1e-5
    sc.use_normal_calculate = True
    mw = Matrix.Translation(Vector(loc) * S)
    if tilt:
        mw = mw @ Matrix.Rotation(tilt[1], 4, tilt[0])
    ob.matrix_world = mw
    ob = bake_object(ob)
    recalc_normals(ob)
    lm_lathe(ob, loc)
    return ob


_profiles = {}


def _profile_obj(key, pts_cm):
    if key in _profiles:
        return _profiles[key]
    cu = bpy.data.curves.new(key, "CURVE")
    cu.dimensions = "2D"
    sp = cu.splines.new("POLY")
    sp.points.add(len(pts_cm) - 1)
    for p, (x, y) in zip(sp.points, pts_cm):
        p.co = (x * S, y * S, 0.0, 1.0)
    sp.use_cyclic_u = True
    ob = link(key, cu)
    ob.hide_render = True
    _profiles[key] = ob
    return ob


def ellipse_pts(a, b, n=8, squish=0.0):
    """Closed section, half-width a (local X) by half-height b (local Y). squish>0 -> rounded rectangle."""
    out = []
    for i in range(n):
        t = math.tau * i / n
        c, s = math.cos(t), math.sin(t)
        e = 2.0 / (2.0 + squish * 4) if squish else 1.0
        out.append((a * math.copysign(abs(c) ** e, c), b * math.copysign(abs(s) ** e, s)))
    return out


def sweep(name, mname, pts, radius=1.0, radii=None, profile=None, res=6, bevel_res=1, caps=True,
          twist="Z_UP"):
    """Rod/rail swept along a Bezier through pts (cm). Round section (radius) or a profile object."""
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.twist_mode = twist
    sp = cu.splines.new("BEZIER")
    sp.bezier_points.add(len(pts) - 1)
    for i, (bp, p) in enumerate(zip(sp.bezier_points, pts)):
        bp.co = Vector(p) * S
        bp.handle_left_type = bp.handle_right_type = "AUTO"
        bp.radius = radii[i] if radii else 1.0
    cu.resolution_u = res
    if profile is not None:
        cu.bevel_mode = "OBJECT"
        cu.bevel_object = profile
    else:
        cu.bevel_mode = "ROUND"
        cu.bevel_depth = radius * S
        cu.bevel_resolution = bevel_res
    cu.use_fill_caps = caps
    ob = link(name, cu)
    cu.materials.append(mat(mname))
    ob = bake_object(ob)
    bmw = bmesh.new()
    bmw.from_mesh(ob.data)
    bmesh.ops.remove_doubles(bmw, verts=bmw.verts, dist=1e-5)
    bmesh.ops.recalc_face_normals(bmw, faces=bmw.faces)
    bmw.to_mesh(ob.data)
    bmw.free()
    lm_sweep(ob)
    return ob


# ---------------------------------------------------------------- joining / uv / export / preview
def join(name, parts, sharp_deg=50.0):
    bm = bmesh.new()
    mats = []
    thr_of = {}
    log(f"join {name}: " + ", ".join(f"{p.name}={tri_count(p.data)}" for p in parts))
    for p in parts:
        me = p.data.copy()
        me.transform(p.matrix_world)
        local = []
        for m_ in p.data.materials:
            if m_ not in mats:
                mats.append(m_)
            local.append(mats.index(m_))
        n0 = len(bm.faces)
        bm.from_mesh(me)
        bm.faces.ensure_lookup_table()
        pthr = math.radians(p.get("sharp_deg", sharp_deg))
        for f in bm.faces[n0:]:
            f.material_index = local[f.material_index] if local else 0
            thr_of[f] = pthr
        bpy.data.meshes.remove(me)
    ngons = [f for f in bm.faces if len(f.verts) > 4]
    if ngons:
        res = bmesh.ops.triangulate(bm, faces=ngons, quad_method="BEAUTY", ngon_method="BEAUTY")
        for f in res["faces"]:
            thr_of.setdefault(f, math.radians(sharp_deg))
    for f in bm.faces:
        f.smooth = True
    thr = math.radians(sharp_deg)
    for e in bm.edges:
        t_e = min((thr_of.get(f, thr) for f in e.link_faces), default=thr)
        e.smooth = not (e.is_manifold and e.calc_face_angle(0.0) > t_e)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for m_ in mats:
        me.materials.append(m_)
    for p in parts:
        d = p.data
        bpy.data.objects.remove(p, do_unlink=True)
        if d.users == 0:
            bpy.data.meshes.remove(d)
    bpy.context.view_layer.update()
    return link(name, me)


def _select_only(ob):
    bpy.context.view_layer.update()
    for o in bpy.context.scene.objects:
        if o is not None and o.name in bpy.context.view_layer.objects:
            o.select_set(False)
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob


def lm_prepare(ob):
    """Give a part UV0 'UVMap' (filled later) and UV1 'Lightmap' in that order."""
    me = ob.data
    while len(me.uv_layers):
        me.uv_layers.remove(me.uv_layers[0])
    me.uv_layers.new(name="UVMap")
    me.uv_layers.new(name="Lightmap")
    me.uv_layers.active = me.uv_layers["Lightmap"]


def lm_abf(ob):
    """Lightmap from the part's own seams (angle-based unwrap): few, compact islands per part."""
    lm_prepare(ob)
    _select_only(ob)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.unwrap(method="ANGLE_BASED", margin=0.0)
    bpy.ops.object.mode_set(mode="OBJECT")


def lm_reunwrap(ob):
    """After boolean + decimation: weld float-noise UV splits, turn the surviving lightmap islands into
    seams and re-unwrap each island angle-based from the decimated surface (removes UV folds)."""
    me = ob.data
    me.uv_layers.active = me.uv_layers["Lightmap"]
    _select_only(ob)
    bpy.context.scene.tool_settings.use_uv_select_sync = True
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.select_all(action="SELECT")
    bpy.ops.uv.remove_doubles(threshold=2e-4, use_unselected=False)
    bpy.ops.uv.seams_from_islands(mark_seams=True)
    bpy.ops.uv.unwrap(method="ANGLE_BASED", margin=0.0)
    bpy.ops.object.mode_set(mode="OBJECT")
    log(f"{ob.name}: lightmap re-unwrapped, {lm_islands(ob.data)} islands")


def lm_smart(ob, angle=66.0):
    """Per-part lightmap islands, unwrapped before booleans/decimation fragment the surface."""
    lm_prepare(ob)
    _select_only(ob)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(angle), island_margin=0.0, scale_to_bounds=False)
    bpy.ops.object.mode_set(mode="OBJECT")


def lm_sweep(ob):
    """Swept part: seams where the curve's own generated UVs split (tube seam + end caps), then a
    proportional angle-based unwrap -> one tube island plus two caps."""
    me = ob.data
    if len(me.uv_layers) == 0:
        lm_smart(ob)
        return
    _select_only(ob)
    me.uv_layers.active = me.uv_layers[0]
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.select_all(action="SELECT")
    bpy.ops.uv.seams_from_islands(mark_seams=True)
    bpy.ops.object.mode_set(mode="OBJECT")
    lm_prepare(ob)
    _select_only(ob)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.unwrap(method="ANGLE_BASED", margin=0.0)
    bpy.ops.object.mode_set(mode="OBJECT")


def lm_islands(me):
    bm = bmesh.new()
    bm.from_mesh(me)
    lay = bm.loops.layers.uv.get("Lightmap")
    if lay is None:
        bm.free()
        return -1
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
        ua = {l.vert: l[lay].uv.copy() for l in lf[0].loops if l.vert in e.verts}
        ub = {l.vert: l[lay].uv.copy() for l in lf[1].loops if l.vert in e.verts}
        if all((ua[k] - ub[k]).length < 1e-5 for k in ua):
            ra, rb = find(lf[0].index), find(lf[1].index)
            if ra != rb:
                parent[ra] = rb
    n = len({find(f.index) for f in bm.faces})
    bm.free()
    return n


def lm_lathe(ob, centre_cm):
    """Turned part: one island, cut along the start meridian of the lathe."""
    lm_prepare(ob)
    cx, cy = centre_cm[0] * S, centre_cm[1] * S
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    for e in bm.edges:
        e.seam = all(abs(v.co.y - cy) < 1e-7 and v.co.x - cx > -1e-7 for v in e.verts)
    bm.to_mesh(ob.data)
    bm.free()
    _select_only(ob)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.unwrap(method="ANGLE_BASED", margin=0.0)
    bpy.ops.object.mode_set(mode="OBJECT")


def uv_layers(ob, margin=0.008, weld=False, keep_uv0=("M_Crochet",)):
    """UV0 'UVMap': smart unwrap of every face except those whose material keeps its own texture UVs
    (the throw's knit grid), scaled so 1 UV == 1 m. UV1 'Lightmap': the per-part islands made while
    building (one smart/angle-based unwrap per part), optionally welded where booleans split them,
    equalised in texel density and packed concave with rotation and a ~1 px margin at 128 px."""
    me = ob.data
    assert [u.name for u in me.uv_layers] == ["UVMap", "Lightmap"], [u.name for u in me.uv_layers]
    skip = {i for i, m_ in enumerate(me.materials) if m_ is not None and m_.name in keep_uv0}
    bm = bmesh.new()
    bm.from_mesh(me)
    for v in bm.verts:
        v.select = False
    for e in bm.edges:
        e.select = False
    for f in bm.faces:
        f.select = False
    for f in bm.faces:
        if f.material_index not in skip:
            f.select_set(True)
    bm.to_mesh(me)
    bm.free()
    _select_only(ob)
    ts = bpy.context.scene.tool_settings
    ts.use_uv_select_sync = True
    ts.mesh_select_mode = (False, False, True)
    me.uv_layers.active = me.uv_layers["UVMap"]
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.0, scale_to_bounds=False)
    bpy.ops.object.mode_set(mode="OBJECT")
    me = ob.data                                   # layer pointers are stale after edit mode
    uvd = me.uv_layers["UVMap"].data
    a3, auv = 0.0, 0.0
    for p in me.polygons:
        if p.material_index in skip:
            continue
        a3 += p.area
        pts = [uvd[li].uv for li in p.loop_indices]
        s = 0.0
        for i in range(len(pts)):
            x0, y0 = pts[i]
            x1, y1 = pts[(i + 1) % len(pts)]
            s += x0 * y1 - x1 * y0
        auv += abs(s) / 2
    k = math.sqrt(a3 / auv) if auv > 0 else 1.0
    for p in me.polygons:
        if p.material_index not in skip:
            for li in p.loop_indices:
                uvd[li].uv = uvd[li].uv * k
    # UV1
    me.uv_layers.active = me.uv_layers["Lightmap"]
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.select_all(action="SELECT")
    if weld:        # booleans leave float-noise splits along cut lines; weld them back together
        bpy.ops.uv.remove_doubles(threshold=2e-4, use_unselected=False)
    bpy.ops.object.mode_set(mode="OBJECT")
    log(f"lightmap islands before packing: {lm_islands(ob.data)}")
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.select_all(action="SELECT")
    bpy.ops.uv.average_islands_scale()
    try:
        bpy.ops.uv.pack_islands(rotate=True, rotate_method="ANY", margin_method="FRACTION", margin=margin,
                                shape_method="CONCAVE")
    except TypeError:
        bpy.ops.uv.pack_islands(rotate=True, margin_method="FRACTION", margin=margin)
    bpy.ops.object.mode_set(mode="OBJECT")
    me = ob.data
    me.uv_layers.active = me.uv_layers["UVMap"]
    me.uv_layers["UVMap"].active_render = True


def export(ob):
    os.makedirs(EXPORT_DIR, exist_ok=True)
    _select_only(ob)
    bpy.ops.export_scene.fbx(filepath=os.path.join(EXPORT_DIR, f"{ob.name}.fbx"), use_selection=True,
                             object_types={"MESH"}, apply_unit_scale=True, apply_scale_options="FBX_SCALE_UNITS",
                             axis_forward="-Y", axis_up="Z", mesh_smooth_type="FACE", add_leaf_bones=False,
                             use_mesh_modifiers=True)


def setup_render():
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_WORKBENCH"
    sh = sc.display.shading
    sh.light = "STUDIO"
    sh.color_type = "MATERIAL"
    sh.show_cavity = True
    sh.cavity_type = "BOTH"
    sh.cavity_ridge_factor = 0.6
    sh.cavity_valley_factor = 1.0
    sh.show_object_outline = False
    sh.show_specular_highlight = True
    if sc.world is None:
        sc.world = bpy.data.worlds.new("World")
    sc.world.color = (1.0, 1.0, 1.0)
    sc.view_settings.view_transform = "Standard"
    sc.render.film_transparent = False
    sc.render.resolution_x, sc.render.resolution_y = 900, 700
    sc.render.resolution_percentage = 100
    sc.display.render_aa = "16"
    if "PreviewCam" not in bpy.data.objects:
        cam = link("PreviewCam", bpy.data.cameras.new("PreviewCam"))
        cam.data.lens = 50
        sc.camera = cam


def render_view(ob, path, view_dir=(1.0, -0.9, 0.55), margin=1.06):
    sc = bpy.context.scene
    for o in sc.objects:
        if o.type == "MESH":
            o.hide_render = o is not ob
    cam = sc.camera
    d = Vector(view_dir).normalized()
    cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    bpy.context.view_layer.update()
    coords = []
    for v in ob.data.vertices:
        coords.extend(ob.matrix_world @ v.co)
    dg = bpy.context.evaluated_depsgraph_get()
    loc, _scale = cam.camera_fit_coords(dg, coords)
    centre = sum((ob.matrix_world @ Vector(b) for b in ob.bound_box), Vector()) / 8
    loc = Vector(loc)
    loc = centre + (loc - centre) * margin
    cam.location = loc
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)


def finish(ob, views=(), weld=False):
    log("finish", ob.name)
    uv_layers(ob, weld=weld)
    log("uv ok")
    export(ob)
    render_view(ob, os.path.join(PREVIEW_DIR, f"{ob.name}.png"))
    if DEBUG_DIR:
        for tag, vd in views:
            render_view(ob, os.path.join(DEBUG_DIR, f"{ob.name}_{tag}.png"), vd)
    bb = [ob.matrix_world @ Vector(b) for b in ob.bound_box]
    mn = Vector([min(v[i] for v in bb) for i in range(3)]) / S
    mx = Vector([max(v[i] for v in bb) for i in range(3)]) / S
    log(f"{ob.name}: tris={tri_count(ob.data)} mats={[m.name for m in ob.data.materials]} "
        f"bbox_cm X[{mn.x:.2f},{mx.x:.2f}] Y(blender)[{mn.y:.2f},{mx.y:.2f}] Z[{mn.z:.2f},{mx.z:.2f}] "
        f"uv={[u.name for u in ob.data.uv_layers]}")
    return ob


def debug_views(obs, tag, views=(("a", (1.0, -0.9, 0.55)), ("b", (0.2, 1.0, 0.4)), ("t", (0.05, 0.0, 1.0)))):
    """With SEATING_DEBUG_DIR set: render a temporary join of `obs` (copies) from a few directions."""
    if not DEBUG_DIR:
        return
    bm = bmesh.new()
    for o in obs:
        me = o.data.copy()
        me.transform(o.matrix_world)
        bm.from_mesh(me)
        bpy.data.meshes.remove(me)
    me = bpy.data.meshes.new("dbg_" + tag)
    bm.to_mesh(me)
    bm.free()
    for f in me.polygons:
        f.use_smooth = True
    ob = link("dbg_" + tag, me)
    hidden = {o.name: o.hide_render for o in bpy.context.scene.objects}
    for vt, vd in views:
        render_view(ob, os.path.join(DEBUG_DIR, f"dbg_{tag}_{vt}.png"), vd)
    for o in bpy.context.scene.objects:
        if o.name in hidden:
            o.hide_render = hidden[o.name]
    bpy.data.objects.remove(ob, do_unlink=True)
    bpy.data.meshes.remove(me)


def bvh_of(obs):
    bm = bmesh.new()
    for o in obs:
        me = o.data.copy()
        me.transform(o.matrix_world)
        bm.from_mesh(me)
        bpy.data.meshes.remove(me)
    t = BVHTree.FromBMesh(bm)
    return t, bm




# ---------------------------------------------------------------- boolean union / fitting helpers
def smoothstep(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def union(name, parts):
    """Fuse closed parts into one manifold shell (EXACT boolean), so no part passes through another.
    Materials of all operands are carried over."""
    base, others = parts[0], parts[1:]
    log(f"union {name} operands: " + ", ".join(f"{p.name}={tri_count(p.data)}/{lm_islands(p.data)}isl" for p in parts))
    coll = bpy.data.collections.new(name + "_ops")
    bpy.context.scene.collection.children.link(coll)
    for p in others:
        for c in list(p.users_collection):
            c.objects.unlink(p)
        coll.objects.link(p)
    md = base.modifiers.new("union", "BOOLEAN")
    md.operation = "UNION"
    md.operand_type = "COLLECTION"
    md.collection = coll
    md.solver = "EXACT"
    try:
        md.material_mode = "TRANSFER"
    except (AttributeError, TypeError):
        pass
    t0 = time.time()
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(base.evaluated_get(dg))
    me.transform(base.matrix_world)
    for p in parts:
        d = p.data
        bpy.data.objects.remove(p, do_unlink=True)
        if d.users == 0:
            bpy.data.meshes.remove(d)
    bpy.data.collections.remove(coll)
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    bmesh.ops.dissolve_degenerate(bm, dist=1e-6, edges=bm.edges)
    nm = [e for e in bm.edges if not e.is_manifold]
    if nm:
        log(f"union {name}: {len(nm)} non-manifold edges, e.g. at cm " +
            ", ".join(str(tuple(round(c / S, 1) for c in e.verts[0].co)) for e in nm[:6]))
    bm.to_mesh(me)
    bm.free()
    ob = link(name, me)
    log(f"union {name}: {len(parts)} parts -> {tri_count(me)} tris, {lm_islands(me)} lightmap islands, "
        f"in {time.time() - t0:.1f}s")
    return ob


def reduce_to(ob, target):
    """Edge-collapse decimation (symmetric in Y) down to a triangle target; keeps the silhouette."""
    cur = tri_count(ob.data)
    if cur <= target:
        return ob
    mats = list(ob.data.materials)
    dm = ob.modifiers.new("reduce", "DECIMATE")
    dm.decimate_type = "COLLAPSE"
    dm.ratio = target / cur
    dm.use_symmetry = True
    dm.symmetry_axis = "Y"
    nm = ob.name
    ob = bake_object(ob, nm)
    log(f"reduce {nm}: {cur} -> {tri_count(ob.data)} tris, {lm_islands(ob.data)} lightmap islands")
    return ob


def bounds_cm(obs):
    mn = Vector((1e9,) * 3)
    mx = Vector((-1e9,) * 3)
    for o in obs:
        for v in o.data.vertices:
            w = o.matrix_world @ v.co
            mn = Vector(map(min, mn, w))
            mx = Vector(map(max, mx, w))
    return mn / S, mx / S


def fit_and_centre(ob, max_x, max_y):
    """Scale X/Y down only if the piece exceeds its footprint, then put the pivot at the bottom centre."""
    mn, mx = bounds_cm([ob])
    sx = min(1.0, max_x / (mx.x - mn.x))
    sy = min(1.0, max_y / (mx.y - mn.y))
    c = (mn + mx) / 2
    m = (Matrix.Diagonal((sx, sy, 1.0, 1.0)) @
         Matrix.Translation(Vector((-c.x, -c.y, -mn.z)) * S))
    ob.data.transform(m)
    mn, mx = bounds_cm([ob])
    log(f"{ob.name}: scale x{sx:.4f} y{sy:.4f}; size {mx.x - mn.x:.2f} x {mx.y - mn.y:.2f} x {mx.z - mn.z:.2f} cm")
    return ob


def island_gaps(ob):
    """Self-check: do separate islands of one mesh touch or pass through each other?"""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.verts.ensure_lookup_table()
    parent = list(range(len(bm.verts)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for e in bm.edges:
        a, b = find(e.verts[0].index), find(e.verts[1].index)
        if a != b:
            parent[a] = b
    tris = bm.calc_loop_triangles()
    verts = [v.co.copy() for v in bm.verts]
    polys = [[l.vert.index for l in t] for t in tris]
    tree = BVHTree.FromPolygons(verts, polys, epsilon=0.0)
    bad = {}
    where = {}
    for i, j in tree.overlap(tree):
        a, b = find(polys[i][0]), find(polys[j][0])
        if a != b:
            k = (min(a, b), max(a, b))
            bad[k] = bad.get(k, 0) + 1
            where[k] = verts[polys[i][0]] / S
    n_isl = len({find(i) for i in range(len(verts))})
    log(f"{ob.name}: {n_isl} islands, {len(bad)} touching/intersecting island pairs")
    for k, n in list(bad.items())[:12]:
        w = where[k]
        log(f"   pair {k}: {n} tri pairs near blender-cm ({w.x:.1f}, {w.y:.1f}, {w.z:.1f})")
    bm.free()
    return bad


# ---------------------------------------------------------------- piping cord along seams
def face_loop(ob, axis, side, blend=0.0):
    """Ordered boundary loop of one face of a soft_box (its seam ring) as (points_cm, normals).
    `blend` tilts each normal toward the face's own axis (used where that face was dropped)."""
    n, keys = SOFT_KEYS[ob.name]
    a = "xyz".index(axis)
    b, c = [k for k in range(3) if k != a]
    f = 0 if side == "-" else n[a] - 1
    nb, nc = n[b] - 1, n[c] - 1
    seq = ([(i, 0) for i in range(0, nb)] + [(nb, j) for j in range(0, nc)] +
           [(i, nc) for i in range(nb, 0, -1)] + [(0, j) for j in range(nc, 0, -1)])
    ax = Vector((0.0, 0.0, 0.0))
    ax[a] = 1.0 if side == "+" else -1.0
    me = ob.data
    m3 = ob.matrix_world.to_3x3()
    pts, nrms = [], []
    for i, j in seq:
        idx = [0, 0, 0]
        idx[a], idx[b], idx[c] = f, i, j
        v = me.vertices[keys[tuple(idx)]]
        pts.append((ob.matrix_world @ v.co) / S)
        nrms.append(((m3 @ v.normal).normalized() + ax * blend).normalized())
    return pts, nrms


def simplify_path(pts, nrms, closed=True, tol_deg=2.0):
    """Drop path points on straight runs (the cord needs vertices only where the seam turns)."""
    keep = list(range(len(pts)))
    changed = True
    while changed:
        changed = False
        m_ = len(keep)
        for k in range(m_):
            if not closed and (k == 0 or k == m_ - 1):
                continue
            i0, i1, i2 = keep[k - 1], keep[k], keep[(k + 1) % m_]
            d0, d1 = pts[i1] - pts[i0], pts[i2] - pts[i1]
            straight = d0.length < 1e-6 or d1.length < 1e-6 or d0.angle(d1) < math.radians(tol_deg)
            if straight and nrms[i0].angle(nrms[i2]) < math.radians(12.0):
                del keep[k]
                changed = True
                break
    return [pts[i] for i in keep], [nrms[i] for i in keep]


def cord(name, mname, pts, nrms, r=0.55, gap=0.15, closed=True, segs=3, span=240.0, seam_every=8):
    """Piping cord swept along a seam path (cm): a D section (round crown of `span` degrees in `segs`
    facets, flat underside toward the upholstery) whose underside floats `gap` cm off the surface
    along the seam normal, so it sits on the seam without sinking in. Smooth-shaded (sharp > 85 deg)."""
    N = len(pts)
    bm = bmesh.new()
    rings = []
    lift = -r * math.cos(math.radians(span / 2)) + gap
    for i in range(N):
        if closed:
            pa, pb = pts[(i - 1) % N], pts[(i + 1) % N]
        else:
            pa, pb = pts[max(i - 1, 0)], pts[min(i + 1, N - 1)]
        t = (pb - pa).normalized()
        nv = nrms[i] - t * nrms[i].dot(t)
        nv.normalize()
        bv = t.cross(nv)
        c = pts[i] + nv * lift
        ring = []
        for j in range(segs + 1):
            th = math.radians(-span / 2 + span * j / segs)
            ring.append(bm.verts.new((c + (nv * math.cos(th) + bv * math.sin(th)) * r) * S))
        rings.append(ring)
    k = segs + 1
    nxt = rings[1:] + ([rings[0]] if closed else [])
    for ra, rb in zip(rings, nxt):
        for j in range(k):
            bm.faces.new((ra[j], ra[(j + 1) % k], rb[(j + 1) % k], rb[j]))
    if not closed:
        bm.faces.new(rings[0])
        bm.faces.new(list(reversed(rings[-1])))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    if closed:
        seam_rings = set(range(0, N, seam_every))
    else:
        seam_rings = {0, N - 1} | set(range(seam_every, N - 1, seam_every))
    seam_pairs = set()
    for si in seam_rings:
        rg = rings[si]
        for j in range(k):
            seam_pairs.add(frozenset((rg[j], rg[(j + 1) % k])))
    for ra, rb in zip(rings, nxt):
        seam_pairs.add(frozenset((ra[0], rb[0])))
    for e in bm.edges:
        e.seam = frozenset(e.verts) in seam_pairs
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat(mname))
    ob = link(name, me)
    ob["sharp_deg"] = 85.0
    lm_abf(ob)
    return ob


def cord_clear(ob, tree, need):
    """Push any cord vertex closer than `need` cm to (or inside) the host surface back out."""
    moved = 0
    for v in ob.data.vertices:
        loc, nrm, _i, dist = tree.find_nearest(v.co)
        if loc is None:
            continue
        out = v.co - loc
        if out.dot(nrm) < 0:
            v.co = loc + nrm * need * S
            moved += 1
        elif dist < need * S:
            v.co = loc + out.normalized() * need * S
            moved += 1
    return moved


def min_dist_cm(ob, tree):
    best = 1e9
    for v in ob.data.vertices:
        loc, nrm, _i, dist = tree.find_nearest(v.co)
        if loc is not None:
            best = min(best, dist if (v.co - loc).dot(nrm) >= 0 else -dist)
    return best / S


# ---------------------------------------------------------------- the throw (cloth sim)
def _cloth_run(ob, frames, clear, pin=None, self_dist=1.2):
    """Simulate ob as a soft, heavy knit for `frames` frames (stepped with frame_set), then apply."""
    cl = ob.modifiers.new("Cloth", "CLOTH")
    st = cl.settings
    st.quality = int(os.environ.get("THROW_Q", "10"))
    st.mass = float(os.environ.get("THROW_MASS", "0.15"))
    st.air_damping = 2.0
    st.tension_stiffness = float(os.environ.get("THROW_TENS", "100"))
    st.compression_stiffness = float(os.environ.get("THROW_TENS", "100"))
    st.shear_stiffness = 20.0
    st.bending_stiffness = float(os.environ.get("THROW_BEND", "1.0"))
    st.tension_damping = 25.0
    st.compression_damping = 25.0
    st.shear_damping = 25.0
    st.shrink_min = 0.0
    st.use_pressure = False
    if pin:
        st.vertex_group_mass = pin
        st.pin_stiffness = 1.0
    cs = cl.collision_settings
    cs.use_collision = True
    cs.distance_min = clear * S
    cs.collision_quality = 4
    cs.use_self_collision = os.environ.get("THROW_SELF", "0") == "1"
    cs.self_distance_min = self_dist * S
    cs.self_friction = 5.0
    cl.point_cache.frame_start = 1
    cl.point_cache.frame_end = frames
    sc = bpy.context.scene
    sc.frame_start, sc.frame_end = 1, frames
    t0 = time.time()
    for f in range(1, frames + 1):
        sc.frame_set(f)
    log(f"cloth {'pinned' if pin else 'free'}: {frames} frames in {time.time() - t0:.1f}s")
    return bake_object(ob, ob.name)


def _push_out(bm, tree, need, need_mid, iters=4):
    """Move throw vertices (and edge/face centres) that sit closer than the clearance back out, then
    relax their 1-ring; repeat."""
    def push():
        moved = []
        for v in bm.verts:
            loc, nrm, _i, dist = tree.find_nearest(v.co)
            if loc is None:
                continue
            out = v.co - loc
            if out.dot(nrm) < 0:
                v.co = loc + nrm * need
                moved.append(v)
            elif dist < need - 1e-6:
                v.co = loc + out.normalized() * need
                moved.append(v)
        for elem in list(bm.edges) + list(bm.faces):
            vs = list(elem.verts)
            c = sum((v.co for v in vs), Vector()) / len(vs)
            loc, nrm, _i, dist = tree.find_nearest(c)
            if loc is None:
                continue
            out = c - loc
            d = dist if out.dot(nrm) >= 0 else -dist
            if d < need_mid:
                dirn = out.normalized() if out.dot(nrm) >= 0 and dist > 1e-9 else nrm
                for v in vs:
                    v.co = v.co + dirn * (need_mid - d)
                moved.extend(vs)
        return list(set(moved))

    moved = push()
    n_first = len(moved)
    for _ in range(iters):
        if not moved:
            break
        ring = set(moved)
        for v in moved:
            for e in v.link_edges:
                ring.add(e.other_vert(v))
        bmesh.ops.smooth_vert(bm, verts=list(ring), factor=0.35, use_axis_x=True, use_axis_y=True,
                              use_axis_z=True)
        moved = push()
    return n_first, len(moved)


def _throw_path(seat_reach=44.0, total=110.0, drop=4.5, fr=2.5, zs=51.0,
                humps=((1.5, 9.0, 3.4), (12.5, 7.0, 2.2))):
    """Cross-section the throw is laid along, in (y, z) cm for the +Y arm, from the bottom of the
    outside hang upward: down the outside of the roll, over the 7 cm roll, down the inside of the arm,
    a small concave fillet dipping into the seat/arm gap, then across the seat. The seat run carries
    slack: `humps` (start past the fillet, width, height) are soft raised folds that add about 5 cm of
    cloth over the same 44 cm reach, so the knit bunches into folds along the seat/arm gap when it
    settles instead of bridging it. Returns (points, normals, hang length, arc length where the seat
    starts); normals point away from the chair."""
    arc, fil = math.pi * ROLL_R, 0.5 * math.pi * fr
    cy, cz = ROLL_C
    drop = cz - zs - fr
    yi = cy - ROLL_R
    fc = (yi - fr, cz - drop)

    def hump(u):
        return sum(h * math.sin(math.pi * (u - u0) / w) ** 2 for u0, w, h in humps if u0 <= u <= u0 + w)
    seat_pts = [(fc[0] - 0.5 * k, zs + hump(0.5 * k)) for k in range(1, int((seat_reach + 20.0) / 0.5) + 1)]
    seat_arc, prev = 0.0, (fc[0], zs)
    for y, z in seat_pts:
        if fc[0] - y > seat_reach + 1e-6:
            break
        seat_arc += math.hypot(y - prev[0], z - prev[1])
        prev = (y, z)
    hang = total - arc - fil - drop - seat_arc
    yo = cy + ROLL_R
    P, N = [], []

    def add(p, n):
        P.append(Vector(p))
        N.append(Vector(n).normalized())
    nh = max(2, int(hang / 0.5))
    for k in range(nh + 1):
        add((yo, cz - hang + hang * k / nh), (1.0, 0.0))
    for k in range(1, 91):
        t = math.pi * k / 90
        add((cy + ROLL_R * math.cos(t), cz + ROLL_R * math.sin(t)), (math.cos(t), math.sin(t)))
    nd = max(2, int(drop / 0.5))
    for k in range(1, nd + 1):
        add((yi, cz - drop * k / nd), (-1.0, 0.0))
    for k in range(1, 21):
        t = -0.5 * math.pi * k / 20
        add((fc[0] + fr * math.cos(t), fc[1] + fr * math.sin(t)), (-math.cos(t), -math.sin(t)))
    for y, z in seat_pts:
        add((y, z), (0.0, 1.0))
    log(f"throw path: seat reach {seat_reach:.0f} cm carries {seat_arc:.1f} cm of cloth "
        f"({seat_arc - seat_reach:.1f} cm slack), hang {hang:.1f} cm")
    return P, N, hang, hang + arc + drop + fil


def _path_at(P, N, off, s):
    """Point at arc length s along the path offset by `off` along its normals (extrapolates)."""
    Q = [p + n * off for p, n in zip(P, N)]
    acc = 0.0
    for a, b in zip(Q, Q[1:]):
        seg = (b - a).length
        if acc + seg >= s:
            return a.lerp(b, (s - acc) / max(seg, 1e-9))
        acc += seg
    a, b = Q[-2], Q[-1]
    return b + (b - a).normalized() * (s - acc)


def drape_throw(colliders, W=70.0, L=110.0, nx=15, ny=37, x_back=3.0, d0=0.45, pin_deg=(130.0, 180.0),
                frames=(12, 48), clear=0.3, n_cols=6, n_rows=10, max_row_gap=13.0, band=2.6,
                scallop_depth=1.4, scallop_period=7.0, scallop_segs=4, fold_w=0.5, thick=0.8, hem=1.6):
    """Knitted floral throw, 70 x 110 cm, folded in half lengthwise (35 x 110, fold toward the front)
    and cloth-draped over the +Y (Blender) arm and the seat.

    * The folded throw is simulated as one 35 x 110 sheet (15 x 37 grid, about 2.5 x 3 cm cells),
      laid along the arm cross-section: outside hang, over the 7 cm roll, down the inside of the arm,
      a fillet over the seat/arm gap, across the seat; soft ripples in the hang and on the seat.
    * Stage 1 pins a strip over the inner arm edge for frames[0] frames; stage 2 releases it and the
      knit settles into soft folds and sags into the seat/arm gap (about frame 60). Collision
      distance 0.3 cm, shrink 0, quality 10, pressure off.
    * Push-out tidy (>= 0.5 cm off the chair), collapse-decimated to the budget, push-out again, then
      an explicit two-ply offset (away from the chair, along smoothed normals): 0.8 cm sheet thickening
      to a 1.6 cm rolled hem with a rounded rim on the scalloped crochet border; the front edge is the fold.
    * UV0 in metres: the underside is the first half of the unfolded 70 x 110 throw, the top the
      second half (mirrored across the fold), so M_Crochet's granny squares tile at real size.
    """
    P, N, hang, s_seat = _throw_path(total=L)
    seat_run = L - s_seat
    sim_clear = float(os.environ.get("THROW_CLEAR", "0.6"))
    d0 = max(d0, sim_clear + 0.5)
    ctree, ctbm = bvh_of(colliders)
    Wf = W / 2
    us = [Wf * i / (nx - 1) for i in range(nx)]
    arc0 = hang                                          # arc length where the roll starts
    pin_s = (arc0 + math.radians(pin_deg[0]) * ROLL_R, arc0 + math.radians(pin_deg[1]) * ROLL_R)
    verts, faces, pin_idx = [], [], []
    for j in range(ny):
        s = L * j / (ny - 1)
        for i, u in enumerate(us):
            x = x_back + u
            if s < hang - 6.0:      # irregular vertical folds in the outside hang, always in toward the arm
                k = min(1.0, (hang - 6.0 - s) / 12.0)
                amp = 2.0 * (0.75 + 0.25 * math.sin(0.37 * x + 1.0))
                ripple = -amp * k * (0.5 + 0.5 * math.cos(math.tau * (x - x_back) / 17.5 + 0.5 * math.sin(x / 9.0)))
                q = _path_at(P, N, d0, s) + Vector((ripple, 0.0))
                z = q.y
            elif s < s_seat:
                q = _path_at(P, N, d0, s)
                z = q.y
            else:                   # across the seat: lie on the real (crowned) cushion, soft waves, splay
                q = _path_at(P, N, d0, s)
                t = (s - s_seat) / seat_run
                x += 3.5 * t * t
                k = min(1.0, (s - s_seat) / 6.0)
                wave = 0.6 * math.sin(math.tau * (x - 4.0) / 17.5 + 0.3) + 0.4 * math.sin(math.tau * x / 23.0 + s / 9.0)
                hit = ctree.ray_cast(Vector((x, q.x, 90.0)) * S, Vector((0.0, 0.0, -1.0)))[0]
                zc = (hit.z / S) if hit is not None else q.y - d0
                lift = q.y - (51.0 + d0)                  # slack humps from _throw_path
                z = max(51.0 + d0, zc + d0 + 0.3) + lift + 1.0 * k * max(0.0, wave)
            q = Vector((q.x, z))
            verts.append(Vector((x, q.x, q.y)) * S)
            if pin_s[0] <= s <= pin_s[1]:
                pin_idx.append(j * nx + i)
    for j in range(ny - 1):
        for i in range(nx - 1):
            a = j * nx + i
            faces.append((a, a + 1, a + nx + 1, a + nx))
    me = bpy.data.meshes.new("Throw")
    me.from_pydata([tuple(v) for v in verts], [], faces)
    me.materials.append(mat("M_Crochet"))
    uv0 = me.uv_layers.new(name="UVMap").data
    me.uv_layers.new(name="Lightmap")
    for poly in me.polygons:
        for li in poly.loop_indices:
            vi = me.loops[li].vertex_index
            i, j = vi % nx, vi // nx
            uv0[li].uv = (us[i] / 100.0, L * j / (ny - 1) / 100.0)
    th = link("Throw", me)
    close = sorted(((ctree.find_nearest(v.co)[3] or 1.0) / S, v.index) for v in me.vertices)[:6]
    log(f"throw start pose: closest to the chair (sim collision distance {sim_clear} cm): " +
        ", ".join(f"{d:.2f} cm at j{vi // nx} i{vi % nx} {tuple(round(c / S, 1) for c in me.vertices[vi].co)}"
                  for d, vi in close))
    vg = th.vertex_groups.new(name="pin")
    vg.add(pin_idx, 1.0, "REPLACE")
    log(f"throw grid {nx}x{ny} (folded 35 x 110, hang {hang:.1f} cm): {len(faces) * 2} tris, {len(pin_idx)} pinned verts")
    debug_views([th] + list(colliders), "throw_start")

    for c in colliders:
        c.modifiers.new("Collision", "COLLISION")
        c.collision.thickness_outer = 0.001
        c.collision.cloth_friction = 40.0
        c.collision.damping = 0.8
    th = _cloth_run(th, frames[0], sim_clear, pin="pin")
    th = _cloth_run(th, frames[1], sim_clear)
    for c in colliders:
        for md in list(c.modifiers):
            c.modifiers.remove(md)

    mn_, mx_ = bounds_cm([th])
    log(f"throw after sim: NaN verts {sum(1 for v in th.data.vertices if any(c != c for c in v.co))}, bounds {tuple(round(c, 1) for c in mn_)} .. {tuple(round(c, 1) for c in mx_)}")
    debug_views([th], "throw_sim", views=(("a", (0.3, -0.5, 1.0)), ("b", (-0.6, 0.3, 0.8))))
    debug_views([th] + list(colliders), "throw_sim_chair")
    ctbm.free()
    tree, cbm = bvh_of(colliders)
    s1 = clear + 0.2                        # underside off the chair (Solidify grows away from it)
    # conform: the knit's weight settles it onto the upholstery (sim ran at a larger, stabler distance)
    me = th.data
    moved = 0
    for v in me.vertices:
        loc, nrm, _i, dist = tree.find_nearest(v.co)
        if loc is None:
            continue
        d = dist / S
        out = v.co - loc
        if out.dot(nrm) < 0 or d >= 2.2 or d <= s1 + 0.05:
            continue
        cm = v.co / S
        if cm.z < ROLL_C[1] - 1.0 or abs(cm.y) < ROLL_C[0] - ROLL_R - 0.5:
            continue                         # only over the roll: the hang and seat keep their folds

        w = 1.0 if d <= 1.2 else smoothstep((2.2 - d) / 1.0)
        d_new = d - (d - (s1 + 0.05)) * w
        v.co = loc + out.normalized() * d_new * S
        moved += 1
    nan = sum(1 for v in me.vertices if any(c != c for c in v.co))
    log(f"throw conform: {moved} verts settled toward the chair; NaN verts {nan}")
    need, need_mid = s1 * S, (s1 - 0.05) * S
    bm = bmesh.new()
    bm.from_mesh(th.data)
    a, b = _push_out(bm, tree, need, need_mid)
    bm.to_mesh(th.data)
    bm.free()
    log(f"throw push-out (sim mesh): {a} verts first pass, {b} on the last pass")
    debug_views([th], "throw_conformed", views=(("a", (0.3, -0.5, 1.0)), ("b", (-0.6, 0.3, 0.8))))

    # remesh the simulated sheet in its own cloth coordinates (u across the folded width, s along the
    # length; the sim keeps the grid order): a coarse interior grid whose rows are picked where the folds
    # are, a border band, and a scalloped crochet edge (4 segments per shell) on the three open edges -
    # the front edge is the fold. Every vertex is placed by bilinear lookup in the simulated grid.
    if DEBUG_DIR:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(DEBUG_DIR, "throw_pre_resample.blend"), copy=True)
    cur = tri_count(th.data)
    G = [v.co.copy() for v in th.data.vertices]
    du, ds = Wf / (nx - 1), L / (ny - 1)

    def at(u, s):
        fi = min(max(u / du, 0.0), nx - 1.0)
        fj = min(max(s / ds, 0.0), ny - 1.0)
        i0, j0 = min(int(fi), nx - 2), min(int(fj), ny - 2)
        a_, b_ = fi - i0, fj - j0
        p0 = G[j0 * nx + i0].lerp(G[j0 * nx + i0 + 1], a_)
        p1 = G[(j0 + 1) * nx + i0].lerp(G[(j0 + 1) * nx + i0 + 1], a_)
        return p0.lerp(p1, b_)

    B, D = band, scallop_depth
    ucols = [B + (Wf - B) * k / n_cols for k in range(n_cols + 1)]
    cand = [B] + [ds * j for j in range(ny) if B + 0.8 < ds * j < L - B - 0.8] + [L - B]
    prof = [[at(u, s) for u in ucols] for s in cand]

    def dp(tol):
        keep, stack = {0, len(cand) - 1}, [(0, len(cand) - 1)]
        while stack:
            lo_, hi_ = stack.pop()
            best, bi = 0.0, None
            for m in range(lo_ + 1, hi_):
                t = (cand[m] - cand[lo_]) / (cand[hi_] - cand[lo_])
                dd = max((prof[m][c] - prof[lo_][c].lerp(prof[hi_][c], t)).length for c in range(len(ucols)))
                if dd > best:
                    best, bi = dd, m
            if bi is not None and best <= tol and cand[hi_] - cand[lo_] > max_row_gap:
                mid_s = 0.5 * (cand[lo_] + cand[hi_])          # long flat stretch: split near the middle
                bi = min(range(lo_ + 1, hi_), key=lambda m: abs(cand[m] - mid_s))
            if bi is not None and (best > tol or cand[hi_] - cand[lo_] > max_row_gap):
                keep.add(bi)
                stack += [(lo_, bi), (bi, hi_)]
        return sorted(keep)
    lo_t, hi_t = 0.0, 20.0 * S
    for _ in range(40):
        mid = 0.5 * (lo_t + hi_t)
        if len(dp(mid)) - 1 > n_rows:
            lo_t = mid
        else:
            hi_t = mid
    rows = [cand[m] for m in dp(hi_t)]

    verts, uvs, wts, inset = [], [], [], {}

    def addv(u, s, w=0.0):
        verts.append(at(u, s))
        uvs.append((u / 100.0, s / 100.0))
        wts.append(w)
        return len(verts) - 1
    gid = {}
    nc = len(ucols) - 1
    for r, s in enumerate(rows):
        for c, u in enumerate(ucols):
            gid[(r, c)] = addv(u, s, fold_w if c == nc else 0.0)
    faces = []
    for r in range(len(rows) - 1):
        for c in range(nc):
            faces.append((gid[(r, c)], gid[(r, c + 1)], gid[(r + 1, c + 1)], gid[(r + 1, c)]))
    R = len(rows) - 1
    # open edges in order: hang end (s = 0, fold -> back), back edge (u = 0), seat end (s = L, back -> fold)
    sides = [(lambda t: (Wf * (1 - t), 0.0), (0.0, 1.0), Wf,
              [(gid[(0, c)], (Wf - ucols[c]) / (Wf - B)) for c in range(nc, -1, -1)]),
             (lambda t: (0.0, L * t), (1.0, 0.0), L,
              [(gid[(r, 0)], (rows[r] - B) / (L - 2 * B)) for r in range(R + 1)]),
             (lambda t: (Wf * t, L), (0.0, -1.0), Wf,
              [(gid[(R, c)], (ucols[c] - B) / (Wf - B)) for c in range(nc + 1)])]
    corner = None
    n_scal = 0
    for edge, inward, length, inner in sides:
        nper = max(1, round(length / scallop_period))
        n = scallop_segs * nper
        outer = []
        for k in range(n + 1):
            if k == 0 and corner is not None:
                outer.append((corner, 0.0))
                continue
            t = k / n
            phi = (k % scallop_segs) / scallop_segs   # crochet shell: a rounded arch between sharp cusps
            off = D * (1.0 - math.sin(math.pi * phi))
            if k in (0, n):
                off = 0.0                     # corners (and the fold ends) carry a full shell
            u0, s0 = edge(t)
            vi = addv(u0 + inward[0] * off, s0 + inward[1] * off, 1.0)
            if 0 < k < n:
                inset[vi] = (u0 + inward[0] * off, s0 + inward[1] * off, inward)
                n_scal += 1 if k % scallop_segs == 0 else 0
            outer.append((vi, t))
        corner = outer[-1][0]
        # the border band between the inner grid row and the scalloped edge is a concave polygon (the
        # shell cusps poke toward the grid): triangulate it in flat cloth space (ear clip + beauty) so no
        # triangle folds over a cusp; a naive zipper here overlaps itself and shades as dark slivers
        poly = [vi for vi, _t in outer] + [vi for vi, _t in reversed(inner)]
        b2 = bmesh.new()
        bv = [b2.verts.new((uvs[k][0], uvs[k][1], 0.0)) for k in poly]
        b2.verts.index_update()
        bf = b2.faces.new(bv)
        bmesh.ops.triangulate(b2, faces=[bf], quad_method="BEAUTY", ngon_method="BEAUTY")
        faces.extend(tuple(poly[v.index] for v in f_.verts) for f_ in b2.faces)
        b2.free()
    # consistent winding in cloth space (u right, s up -> counter-clockwise)
    fixed = []
    for f in faces:
        q = [uvs[k] for k in f]
        area = sum(q[k][0] * q[(k + 1) % len(q)][1] - q[(k + 1) % len(q)][0] * q[k][1] for k in range(len(q)))
        fixed.append(tuple(f) if area > 0 else tuple(reversed(f)))
    me2 = bpy.data.meshes.new("Throw")
    me2.from_pydata([tuple(v) for v in verts], [], fixed)
    me2.materials.append(mat("M_Crochet"))
    uv2 = me2.uv_layers.new(name="UVMap").data
    me2.uv_layers.new(name="Lightmap")
    for poly in me2.polygons:
        for li in poly.loop_indices:
            uv2[li].uv = uvs[me2.loops[li].vertex_index]
    src = th.data
    bpy.data.objects.remove(th, do_unlink=True)
    bpy.data.meshes.remove(src)
    th = link("Throw", me2)
    log(f"throw remeshed sheet self-hits before push-out: {self_hits(th)}")
    log(f"throw remeshed {cur} -> {tri_count(me2)} tris: interior {len(rows)} rows x {len(ucols)} cols, "
        f"band {B} cm, {n_scal + 3} crochet shells ({D} cm deep), {len(inset)} scallop verts")
    bm = bmesh.new()
    bm.from_mesh(th.data)
    a, b = _push_out(bm, tree, need, need_mid)
    log(f"throw remeshed sheet push-out {a} / {b}")
    if DEBUG_DIR:
        bm.to_mesh(th.data)
        debug_views([th], "throw_decimated", views=(("a", (0.3, -0.5, 1.0)), ("b", (-0.6, 0.3, 0.8))))
    bm.normal_update()
    votes = 0
    for f in bm.faces:
        loc, nrm, _i, dist = tree.find_nearest(f.calc_center_median())
        if loc is not None:
            votes += 1 if f.normal.dot(nrm) > 0 else -1
    if votes < 0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces)
    for f in bm.faces:
        f.smooth = True
    bm.to_mesh(th.data)
    bm.free()
    cbm.free()
    log(f"throw remeshed sheet self-hits after push-out: {self_hits(th)}")
    hem_idx = [vi for vi, w in enumerate(wts) if w >= 1.0]
    # --- two-ply knit with a ROLLED, scalloped crochet hem, built explicitly (no Solidify): the shell is
    # offset along smoothed vertex normals (so tight folds never cross over), thickness ramps from the
    # sheet (`thick`) to the fatter hem (`hem`) across the border band and is in between along the fold,
    # and every open edge / the fold gets a rounded rim: one extra loop bulged outward by `roll` x half the
    # local thickness, so the edge reads as a rolled, crocheted bead rather than a knife-cut slab.
    roll = 0.9
    bm = bmesh.new()
    bm.from_mesh(th.data)
    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    bm.normal_update()
    nv0 = len(bm.verts)
    nrm = [v.normal.copy() for v in bm.verts]
    for _ in range(3):                                  # smooth the offset direction over the 1-ring
        nn = []
        for v in bm.verts:
            acc = nrm[v.index] * 2.0
            for e in v.link_edges:
                acc += nrm[e.other_vert(v).index]
            nn.append(acc.normalized())
        nrm = nn
    tk = [(thick + (hem - thick) * w) * S for w in wts]
    bnd = [e for e in bm.edges if e.is_boundary]
    outd = {}
    for e in bnd:
        f = e.link_faces[0]
        for lp in f.loops:                              # orient a -> b along the face winding
            if lp.edge is e:
                a, b = lp.vert, lp.link_loop_next.vert
        o = (b.co - a.co).cross(f.normal)
        if o.length > 1e-12:
            o.normalize()
            for v in (a, b):
                outd[v.index] = outd.get(v.index, Vector()) + o
    for vi, o in outd.items():
        n0 = nrm[vi]
        o = o - n0 * o.dot(n0)
        outd[vi] = o.normalized() if o.length > 1e-9 else Vector()
    sheet_faces = list(bm.faces)
    base = [v.co.copy() for v in bm.verts]
    top = [bm.verts.new(base[i] + nrm[i] * tk[i]) for i in range(nv0)]
    mid = {vi: bm.verts.new(base[vi] + nrm[vi] * (0.5 * tk[vi]) + o * (0.5 * roll * tk[vi]))
           for vi, o in outd.items()}
    uvl = bm.loops.layers.uv["UVMap"]
    kind = {}
    for f in sheet_faces:                               # offset shell keeps the outward (away-from-chair) winding
        g = bm.faces.new([top[v.index] for v in f.verts])
        g.material_index = f.material_index
        for lp, lq in zip(f.loops, g.loops):
            lq[uvl].uv = (W / 100.0 - lp[uvl].uv.x, lp[uvl].uv.y)   # top ply = second half of the throw
        kind[g] = 1
    for e in bnd:
        f = e.link_faces[0]
        for lp in f.loops:
            if lp.edge is e:
                a, b = lp.vert, lp.link_loop_next.vert
                ua, ub = lp[uvl].uv.copy(), lp.link_loop_next[uvl].uv.copy()
        ia, ib = a.index, b.index
        for quad, uvq in (((a, b, mid[ib], mid[ia]), (ua, ub, ub, ua)),
                          ((mid[ia], mid[ib], top[ib], top[ia]), (ua, ub, ub, ua))):
            g = bm.faces.new(quad)
            g.material_index = f.material_index
            for lq, uv_ in zip(g.loops, uvq):
                lq[uvl].uv = uv_
            kind[g] = 2
    # where the knit crumples, a full roll can make the rim cross its own neighbours: unroll those
    # segments toward a straight rim until nothing intersects
    bm.verts.index_update()
    mid_of = {v.index: vi for vi, v in mid.items()}
    unrolled = set()
    for _ in range(4):
        tmp = bm.copy()                                 # test the triangles the engine will draw
        bmesh.ops.triangulate(tmp, faces=list(tmp.faces), quad_method="FIXED", ngon_method="BEAUTY")
        tmp.faces.ensure_lookup_table()
        tb = BVHTree.FromBMesh(tmp, epsilon=0.0)
        tv = [{v.index for v in f_.verts} for f_ in tmp.faces]
        tmp.free()
        bad = set()
        for i, j in tb.overlap(tb):
            if i < j and not (tv[i] & tv[j]):
                bad.update(k for k in tv[i] | tv[j] if k in mid_of)
        if not bad:
            break
        for k in bad:
            vi = mid_of[k]
            mid[vi].co = base[vi] + nrm[vi] * (0.5 * tk[vi]) + outd[vi] * (0.5 * 0.35 * tk[vi])
            unrolled.add(vi)
    bmesh.ops.reverse_faces(bm, faces=sheet_faces)      # underside ply faces the chair
    for f in sheet_faces:
        kind[f] = 0
    for e in bm.edges:
        e.seam = {kind.get(f, 0) for f in e.link_faces} == {0, 2}
    for f in bm.faces:
        f.smooth = True
    counts = [sum(1 for k in kind.values() if k == c) for c in range(3)]
    log(f"throw rolled hem: sheet {thick} cm, hem {hem} cm (fold {thick + (hem - thick) * fold_w:.2f} cm), "
        f"{len(bnd)} rim segments x 2 loops, roll {roll} ({len(unrolled)} rim verts unrolled to 0.35)")
    # lock the triangulation that was checked above (an importer's own quad split could differ)
    bmesh.ops.triangulate(bm, faces=list(bm.faces), quad_method="FIXED", ngon_method="BEAUTY")
    me = th.data
    bm.to_mesh(me)
    bm.free()
    for vg_ in list(th.vertex_groups):
        th.vertex_groups.remove(vg_)
    _select_only(th)
    me.uv_layers.active = me.uv_layers["Lightmap"]
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.unwrap(method="ANGLE_BASED", margin=0.0)
    bpy.ops.object.mode_set(mode="OBJECT")
    me = th.data
    for e in me.edges:
        e.use_seam = False
    bm = bmesh.new()
    bm.from_mesh(me)
    nb = sum(1 for e in bm.edges if e.is_boundary)
    nm = sum(1 for e in bm.edges if not e.is_manifold and not e.is_boundary)
    bm.free()
    mn_, mx_ = bounds_cm([th])
    log(f"throw final bounds {tuple(round(c, 2) for c in mn_)} .. {tuple(round(c, 2) for c in mx_)}")
    th["sharp_deg"] = 75.0                    # rounded top of the hem shades soft; the underside edge stays crisp
    log(f"throw: {tri_count(me)} tris, faces sheet/shell/rim = {counts}, hem verts {len(hem_idx)}, "
        f"boundary edges {nb}, non-manifold {nm}, lightmap islands {lm_islands(me)}, "
        f"self-intersecting tri pairs {self_hits(th)}")
    return th


def self_hits(ob):
    """Triangle pairs of one mesh that intersect without sharing a vertex (folds passing through)."""
    me = ob.data
    verts = [v.co.copy() for v in me.vertices]
    me.calc_loop_triangles()
    tris = [tuple(t.vertices) for t in me.loop_triangles]
    tree = BVHTree.FromPolygons(verts, tris, epsilon=0.0)
    hits = [(i, j) for i, j in tree.overlap(tree) if i < j and not (set(tris[i]) & set(tris[j]))]
    if hits and DEBUG_DIR:
        for i, j in hits[:: max(1, len(hits) // 8)]:
            c = sum((verts[k] for k in tris[i]), Vector()) / 3 / S
            log(f"   self-hit near ({c.x:.1f}, {c.y:.1f}, {c.z:.1f}) tris {tris[i]} / {tris[j]}")
    return len(hits)


def check_clearance(a_obs, b_obs, label):
    ta, abm = bvh_of(a_obs)
    tb, bbm = bvh_of(b_obs)
    pairs = ta.overlap(tb)
    mind = 1e9
    for v in abm.verts:
        loc, nrm, _i, dist = tb.find_nearest(v.co)
        if loc is not None:
            mind = min(mind, dist)
    log(f"clearance {label}: overlapping tri pairs={len(pairs)}, min vertex distance={mind / S:.2f} cm")
    abm.free()
    bbm.free()
    return len(pairs), mind / S


# ---------------------------------------------------------------- SM_Recliner
ROLL_C, ROLL_R = (33.0, 58.0), 7.0            # scroll-arm roll: centre (y, z) and radius, cm
ARM_YI, ARM_YO = 26.0, 35.5                   # inside panel / outside panel (before crown and taper)
ARM_XB, ARM_XF = -30.5, 45.0                  # straight run of the arm (back end rounded behind XB)
ARM_REAR = ((-33.5, 0.78), (-32.2, 0.93))     # (x, scale) rings that round off the back end
ARM_DENSE = (-30.5, -12.0, 7.0, 26.0, 45.0)   # stations of the crowned outside panel
ARM_CROWN, ARM_TAPER = 2.0, 1.0               # stuffing crown of the outside panel; flare at the floor
TUCK_Z = 50.4                                 # arm-top-to-side seam, just under the roll
PLEAT_C = (32.5, 56.0)                        # (y, z) the scroll-front pleats gather toward


def arm_profile():
    """Rolled ('P' / scroll) arm cross-section for the +Y arm, (y, z, kind) cm, counter-clockwise.
    The roll is 24 segments per full circle (15.6 deg); kinds: bi bottom-inside, b bottom-outside,
    o outside panel, t tuck seam, r roll, i inside panel."""
    cy, cz = ROLL_C
    p = [(27.2, 4.5, "bi"), (34.3, 4.5, "b"), (35.2, 5.1, "b")]
    p += [(ARM_YO, z, "o") for z in (6.5, 15.0, 24.0, 33.0, 42.0)]
    p.append((35.4, TUCK_Z, "t"))
    for k in range(17):
        t = math.radians(-70.0 + 250.0 * k / 16)
        p.append((cy + ROLL_R * math.cos(t), cz + ROLL_R * math.sin(t), "r"))
    p += [(ARM_YI, 50.0, "i"), (ARM_YI, 38.0, "i"), (26.2, 5.4, "i")]
    return p


def arm_point(y, z, kind, x):
    """Profile point at station x: the outside panel flares out toward the floor (taper) and is
    crowned with stuffing between the back and front ends."""
    if kind in ("b", "o", "t"):
        y += ARM_TAPER * max(0.0, min(1.0, (TUCK_Z - z) / (TUCK_Z - 4.5)))
    if kind == "o":
        bx = math.sin(math.pi * max(0.0, min(1.0, (x - ARM_XB) / (ARM_XF - ARM_XB))))
        y += ARM_CROWN * bx * math.sin(math.pi * max(0.0, min(1.0, (z - 4.5) / 39.5)))
    return y, z


def rolled_arm(name, mname, sg):
    """Scroll arm: the profile swept from the rounded back end to the front. Only the crowned outside
    panel carries the intermediate stations (the roll and inside panel are straight, so they span
    back-to-front in one face). The front is a domed, gathered scroll face: a ring 4 cm round the
    scroll centre domes out 0.9 cm, eight radial pleat valleys sink back toward it, and the centre is
    pulled 0.6 cm in. Returns (arm, front seam path, front seam normals, tuck path, tuck normals)."""
    prof = arm_profile()
    n = len(prof)
    cy = sum(p[0] for p in prof) / n
    cz = sum(p[1] for p in prof) / n
    bm = bmesh.new()
    chains = []
    for (y0, z0, kind) in prof:
        ch = []
        for x, s in ARM_REAR:
            y, z = arm_point(y0, z0, kind, x)
            ch.append(bm.verts.new(Vector((x, sg * (cy + (y - cy) * s), cz + (z - cz) * s)) * S))
        for x in (ARM_DENSE if kind == "o" else (ARM_XB, ARM_XF)):
            y, z = arm_point(y0, z0, kind, x)
            ch.append(bm.verts.new(Vector((x, sg * y, z)) * S))
        chains.append(ch)
    for i in range(n):
        ci, cj = chains[i], chains[(i + 1) % n]
        for b in range(2):
            bm.faces.new((ci[b], cj[b], cj[b + 1], ci[b + 1]))
        mi, mj = ci[2:], cj[2:]
        if len(mi) == len(mj):
            for b in range(len(mi) - 1):
                bm.faces.new((mi[b], mj[b], mj[b + 1], mi[b + 1]))
        else:
            bm.faces.new(mi + list(reversed(mj)))
    rear = [ch[0] for ch in chains]
    bm.faces.new(rear)
    outline = [ch[-1] for ch in chains]
    C = Vector((ARM_XF, sg * PLEAT_C[0], PLEAT_C[1]))
    angs, dirs = [], []
    for v in outline:
        d = v.co / S - C
        d.x = 0.0
        dirs.append(d.normalized() * min(0.5 * d.length, 4.0))
        angs.append(math.atan2(d.z, sg * d.y))
    valley = set()
    for q in range(8):
        target = -math.pi + (q + 0.5) * math.tau / 8
        valley.add(min(range(n), key=lambda k: abs(math.remainder(angs[k] - target, math.tau))))
    rv = [bm.verts.new((C + dirs[k] + Vector((0.15 if k in valley else 0.9, 0.0, 0.0))) * S) for k in range(n)]
    cv = bm.verts.new((C + Vector((-0.6, 0.0, 0.0))) * S)
    for k in range(n):
        k2 = (k + 1) % n
        bm.faces.new((outline[k], outline[k2], rv[k2], rv[k]))
        bm.faces.new((rv[k], rv[k2], cv))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    seam_pairs = set()
    for ring in (rear, outline):
        for k in range(n):
            seam_pairs.add(frozenset((ring[k], ring[(k + 1) % n])))
    for a_, b_ in zip(chains[0][:-1], chains[0][1:]):
        seam_pairs.add(frozenset((a_, b_)))
    for e in bm.edges:
        e.seam = frozenset(e.verts) in seam_pairs
    nm = sum(1 for e in bm.edges if not e.is_manifold)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat(mname))
    ob = link(name, me)
    lm_abf(ob)
    log(f"{name}: {tri_count(me)} tris, non-manifold edges {nm}, pleat valleys {sorted(valley)}, "
        f"lightmap islands {lm_islands(ob.data)}")

    # seam paths: the front scroll perimeter (normal = bisector of side and front) ...
    P2 = [arm_point(y, z, k, ARM_XF) for (y, z, k) in prof]
    fpts, fn = [], []
    for i in range(n):
        (y0, z0), (y1, z1), (y2, z2) = P2[i - 1], P2[i], P2[(i + 1) % n]
        e1 = Vector((z1 - z0, -(y1 - y0))).normalized()
        e2 = Vector((z2 - z1, -(y2 - y1))).normalized()
        nn = (e1 + e2).normalized()
        fpts.append(Vector((ARM_XF, sg * y1, z1)))
        fn.append(Vector((1.0, sg * nn.x, nn.y)).normalized())
    # ... and the arm-top-to-side seam under the roll, along the arm
    y0, z0, kd = [p for p in prof if p[2] == "t"][0]
    tpts = [Vector((x, sg * arm_point(y0, z0, kd, x)[0], z0)) for x in (-21.0, 0.0, 22.0, 43.4)]
    tn = [Vector((0.0, sg, -0.1)).normalized() for _ in tpts]
    return ob, fpts, fn, tpts, tn


def recliner():
    """Upholstered lift recliner, front +X: swept scroll arms (24-segment roll over a crowned outside
    panel that flares 1 cm toward the floor, domed and pleated scroll fronts), a crowned back shell
    with a separate stuffed outer back panel, waterfall back of three puffed pillows, boxed seat
    cushion, padded footrest, turned bun feet; real piping cord on the scroll fronts, under the rolls,
    round the outer back panel and the seat's top and bottom seams; a cloth-draped knitted throw.
    Placed at (285, 51) yaw 90 with its back to the west wall: footprint <= 95.6 (X) x 83.6 (Y)."""
    UP = "M_UpholsteryPink"
    K, Z0 = 0.15, 30.0                         # back recline: x shift per cm above Z0 (about 8.5 deg)
    BUDGET = 3990
    THROW_EST = int(os.environ.get("THROW_EST", "956"))    # throw tris (two-ply, rolled scalloped hem)

    def lean(v):
        return Vector((v.x - K * max(0.0, v.z - Z0), v.y, v.z))

    parts = []
    foot_prof = [(0, 0), (2.2, 0), (2.8, 1.4), (2.3, 3.5), (0, 4.3)]
    for fx, fy in ((39.0, 30.75), (39.0, -30.75), (-33.0, 30.0), (-33.0, -30.0)):
        parts.append(lathe("foot", "M_TimberDark", foot_prof, steps=8, loc=(fx, fy, 0)))
    # boxed seat cushion: crowned top, bulged boxing, crisp (2-segment) top and bottom edges for piping
    seat = soft_box("seat", UP, -20.8, 45.0, -24.0, 24.0, 41.4, 50.0,
                    r={"x": (3.5, 4.5), "y": 4.0, "z": (1.2, 1.5)}, m=(2, 2, 1), nflat=(2, 2, 1),
                    puff={"+z": 1.8, "+x": 0.8, "+y": 0.4, "-y": 0.4}, drop=("-z",))
    seat_top = simplify_path(*face_loop(seat, "z", "+"))
    seat_bot = simplify_path(*face_loop(seat, "z", "-", blend=1.0), tol_deg=6.0)
    pillows = []
    for i, (za, zb) in enumerate(((51.6, 67.4), (68.2, 84.0), (84.8, 100.6))):
        pillows.append(soft_box(f"pillow{i}", UP, -20.2, -4.5, -24.6, 24.6, za, zb,
                                r={"x": (3.0, 5.5), "y": 5.0, "z": 6.0}, m=((1, 2), 2, 2), nflat=(1, 1, 1),
                                puff={"+x": 2.4}, deform=lean, drop=("-x",)))
    footrest = soft_box("footrest", UP, 44.2, 45.8, -24.0, 24.0, 21.0, 39.8,
                        r={"x": (0.3, 0.75), "y": 2.5, "z": 2.5}, m=((1, 1), 2, 2), nflat=(1, 2, 2),
                        puff={"+x": 1.6}, drop=("-x", "-z"))

    # --- body: crowned back shell + stuffed outer back panel, two scroll arms, seat deck -> one shell
    shell = soft_box("back_shell", UP, -36.0, -20.5, -33.5, 33.5, 4.8, 104.0,
                     r={"x": (5.0, 3.0), "y": 5.5, "z": (1.2, 8.0)}, m=(2, 2, 2), nflat=(1, 2, 3),
                     puff={"+y": 2.0, "-y": 2.0, "+z": 1.0}, deform=lean)
    panel = soft_box("back_panel", UP, -37.2, -35.0, -30.0, 30.0, 8.0, 99.0,
                     r={"x": (1.0, 0.6), "y": 3.0, "z": 3.0}, m=(1, 2, 2), nflat=(1, 3, 4),
                     puff={"-x": 2.2}, deform=lean)
    back_loop = simplify_path(*face_loop(panel, "x", "-"))
    body = [shell, panel]
    arm_paths = []
    for sg in (-1, 1):
        arm, fpts, fn, tpts, tn = rolled_arm("arm", UP, sg)
        body.append(arm)
        arm_paths.append((simplify_path(fpts, fn), (tpts, tn)))
    body.append(soft_box("deck", UP, -24.0, 44.0, -26.6, 26.6, 5.2, 40.2, r=1.0, m=1, nflat=(1, 1, 1)))
    body = union("body", body)

    # --- piping cords
    cords = []
    for (fp, fnn), (tp, tnn) in arm_paths:
        cords.append(cord("cord_scroll", UP, fp, fnn, r=0.55, gap=0.15))
        cords.append(cord("cord_tuck", UP, tp, tnn, r=0.5, gap=0.25, closed=False))
    cords.append(cord("cord_back", UP, *back_loop, r=0.55, gap=0.2))
    cords.append(cord("cord_seat_top", UP, *seat_top, r=0.55, gap=0.15))
    cords.append(cord("cord_seat_bot", UP, *seat_bot, r=0.5, gap=0.15))

    soft = [seat, footrest] + pillows + parts
    others = sum(tri_count(p.data) for p in soft + cords)
    throw_est = THROW_EST
    body_target = BUDGET - others - throw_est
    log(f"recliner: separate parts {others} tris (cords {sum(tri_count(c.data) for c in cords)}), "
        f"throw ~{throw_est}, body {tri_count(body.data)} -> target {body_target}")
    if tri_count(body.data) > body_target:
        # protect the pleated scroll fronts from decimation (inverted group -> highest collapse cost)
        g = body.vertex_groups.new(name="keep")
        g.add([v.index for v in body.data.vertices
               if v.co.x / S > ARM_XF - 0.05 and abs(v.co.y / S) > 25.5], 1.0, "REPLACE")
        cur = tri_count(body.data)
        dm = body.modifiers.new("reduce", "DECIMATE")
        dm.decimate_type = "COLLAPSE"
        dm.ratio = body_target / cur
        dm.use_symmetry = True
        dm.symmetry_axis = "Y"
        dm.vertex_group = "keep"
        dm.invert_vertex_group = True
        dm.vertex_group_factor = 50.0
        body = bake_object(body, "body")
        for vg_ in list(body.vertex_groups):
            body.vertex_groups.remove(vg_)
        log(f"reduce body: {cur} -> {tri_count(body.data)} tris")
    lm_reunwrap(body)

    # cords must float on their seams, never sink into the (boolean / decimated) upholstery
    host, hbm = bvh_of([body, seat, footrest] + pillows)
    for c in cords:
        mv = 0
        for _ in range(4):
            k_ = cord_clear(c, host, 0.18)
            mv += k_
            if not k_:
                break
        log(f"{c.name}: {tri_count(c.data)} tris, pushed {mv} verts, min gap {min_dist_cm(c, host):.2f} cm")
    hbm.free()

    # --- knitted throw over the +Y (Blender) arm, i.e. the window side once placed, and the seat
    throw = drape_throw([body, seat, footrest] + pillows + cords)
    check_clearance([throw], [body, seat, footrest] + pillows + cords + parts, "throw vs chair")
    allp = [body] + soft + cords + [throw]
    ob = join("SM_Recliner", allp)
    fit_and_centre(ob, 95.6, 83.6)
    island_gaps(ob)
    return ob


# ---------------------------------------------------------------- SM_Armchair
def armchair():
    """Aged-care dining armchair: light-ash frame (turned front legs that rise into arm posts, raked
    back legs swept up into the back posts, shaped rails, stretchers, swept arms and crest rail) fused
    into one shell; drop-in upholstered seat pad and inset back pad. Seat top 46, footprint 48 x 52."""
    T, UP = "M_Timber", "M_UpholsteryCream"
    LY = 22.2                                      # leg centre lines at y = +-LY
    FX = 20.2                                      # front leg centre x
    frame = []
    # front legs, turned, continuing up as the arm posts
    front_prof = [(0, 0), (1.2, 0), (1.5, 9), (1.95, 29.5), (2.3, 31.0), (2.3, 31.9), (2.1, 32.6),
                  (2.1, 41.2), (1.65, 42.4), (1.72, 44.5), (1.35, 50.0), (1.6, 55.0), (1.25, 63.0), (0, 63.0)]
    for sy in (-LY, LY):
        frame.append(lathe("leg_f", T, front_prof, steps=10, loc=(FX, sy, 0)))
    # back legs: one swept member from the raked foot up into the reclined back post
    post_pts = [(-22.3, 0.15), (-19.7, 37.5), (-19.95, 52.0), (-21.0, 70.0), (-21.75, 85.6)]
    post_r = [1.3, 1.85, 1.72, 1.55, 1.42]
    post_prof = _profile_obj("post_prof", ellipse_pts(1.0, 1.0, 10))
    for sy in (-LY, LY):
        frame.append(sweep("post", T, [(x, sy, z) for x, z in post_pts], profile=post_prof, radii=post_r,
                           res=3, twist="MINIMUM"))
    # shaped seat rails (rounded-rectangle section), ends buried in the legs
    # 5.5 cm rail with a 0.3 cm chamfer on the top edge and a small bead along the bottom edge
    apron_prof = _profile_obj("apron_prof", [(1.0, -2.0), (1.25, -2.22), (1.25, -2.53), (1.0, -2.75),
                                             (-1.0, -2.75), (-1.25, -2.53), (-1.25, -2.22), (-1.0, -2.0),
                                             (-1.0, 2.45), (-0.7, 2.75), (0.7, 2.75), (1.0, 2.45)])
    za = 38.0
    frame.append(sweep("apron_f", T, [(FX, -LY + 0.6, za), (FX + 0.6, 0.0, za), (FX, LY - 0.6, za)],
                       profile=apron_prof, res=4))
    frame.append(sweep("apron_b", T, [(-19.7, -LY + 0.6, za), (-20.2, 0.0, za), (-19.7, LY - 0.6, za)],
                       profile=apron_prof, res=4))
    for sy in (-LY, LY):
        frame.append(sweep("apron_s", T, [(FX - 0.6, sy, za + 0.05), (-19.1, sy, za + 0.05)], profile=apron_prof,
                           res=1))
    # seat board the pad drops onto (hidden under the pad, fused to the rails)
    frame.append(bevel_box("board", T, -19.3, FX - 0.6, -LY + 0.7, LY - 0.7, 39.2, 40.7, 0.2, 1))
    # side stretchers
    for sy in (-LY, LY):
        frame.append(sweep("stretcher", T, [(FX, sy, 13.0), (0.0, sy, 12.6), (-21.4, sy, 13.0)],
                           radius=0.95, res=3, bevel_res=1))
    # lower back rail and bowed crest rail
    lrail_prof = _profile_obj("lrail_prof", ellipse_pts(0.9, 1.6, 8, squish=0.4))
    frame.append(sweep("lower_rail", T, [(-19.8, -LY, 48.5), (-20.6, 0.0, 48.5), (-19.8, LY, 48.5)],
                       profile=lrail_prof, res=4))
    rail_prof = _profile_obj("rail_prof", ellipse_pts(1.1, 3.1, 10, squish=0.35))
    frame.append(sweep("crest", T, [(-21.4, -23.0, 83.6), (-21.9, -LY + 1.0, 83.9), (-22.8, 0.0, 84.4),
                                    (-21.9, LY - 1.0, 83.9), (-21.4, 23.0, 83.6)],
                       profile=rail_prof, radii=[0.45, 1.0, 1.0, 1.0, 0.45], res=3))
    # arm rests: oval section, bowed outward in plan, rolled nose over the front post
    arm_prof = _profile_obj("arm_prof", ellipse_pts(2.4, 1.25, 10, squish=0.3))
    for sg in (-1, 1):
        pts = [(-20.7, LY, 64.6), (-4.0, LY + 1.3, 65.0), (FX - 1.0, LY + 0.3, 63.8), (23.0, LY, 62.8),
               (23.9, LY, 62.2)]
        frame.append(sweep("armrest", T, [(x, sg * y, z) for x, y, z in pts], profile=arm_prof,
                           radii=[0.62, 1.0, 1.0, 0.8, 0.22], res=3))
    frame = union("frame", frame)
    frame = reduce_to(frame, int(os.environ.get("ARM_TARGET", "2330")))

    parts = [frame]
    # drop-in seat pad: crowned, piped round the top edge, 0.2 cm above the board
    parts.append(soft_box("seat_pad", UP, -17.0, 22.0, -19.9, 19.9, 41.1, 45.1,
                          r={"x": (1.8, 2.6), "y": 2.2, "z": (1.0, 2.0)}, m=(2, 2, 2), nflat=(1, 1, 1),
                          puff={"+z": 0.9, "+x": 0.3}, seam=("z", 43.9, 0.28, 0.35), drop=("-z",)))

    # inset back pad between the posts, reclined with them and bowed like the crest rail
    def back_deform(v):
        px = -19.85 + (v.z - 51.5) * (-21.55 + 19.85) / (80.0 - 51.5)
        return Vector((v.x + px + 0.0025 * v.y * v.y, v.y, v.z))

    parts.append(soft_box("back_pad", UP, -1.2, 3.4, -19.7, 19.7, 51.6, 79.6,
                          r={"x": 2.0, "y": 2.6, "z": 2.6}, m=(1, 2, 2), nflat=(1, 1, 1),
                          puff={"+x": 1.8, "-x": 0.3}, seam=("x", 1.0, 0.28, 0.35), deform=back_deform))
    ob = join("SM_Armchair", parts)
    fit_and_centre(ob, 47.8, 51.8)
    island_gaps(ob)
    return ob


# ---------------------------------------------------------------- main
def main():
    if bpy.context.object and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    os.makedirs(PREVIEW_DIR, exist_ok=True)
    setup_render()
    views = (("back", (-1.0, 0.8, 0.5)), ("side", (0.0, -1.0, 0.15)), ("top", (0.3, -0.2, 1.0)),
             ("front", (1.0, 0.0, 0.2)), ("other", (1.0, 0.9, 0.5)))
    only = os.environ.get("SEATING_ONLY", "")
    if only in ("", "recliner"):
        rec = recliner()
        finish(rec, views, weld=True)
        rec.hide_render = True
    if only in ("", "armchair"):
        arm = armchair()
        finish(arm, views, weld=True)
    for k, o in list(_profiles.items()):
        bpy.data.objects.remove(o, do_unlink=True)
    log("done")


main()
