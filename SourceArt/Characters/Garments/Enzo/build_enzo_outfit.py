# Enzo placeholder outfit: flannel shirt (rolled sleeves), brown work trousers, worn belt, work boots.
# Headless:  blender -b --factory-startup --python build_enzo_outfit.py
#
# NOTE: SKM_David_BodyMesh is the MetaHuman "UE Optimized" body with the faces hidden under the
# default T-shirt/shorts already culled (no torso, shoulder caps, thigh tops). Those zones therefore
# have no skin to copy weights from or to keep clearance against; the garment there is shaped from
# skeleton landmarks (corrective joints sit just under the skin) and weighted procedurally along the
# bone chains, then blended into Data-Transfer weights wherever real skin exists (arms, legs, feet).
import bpy, bmesh, math, os, sys, json, time
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

OUT_DIR = r"D:\Unreal-Projects\WattleviewGrove-ue58\SourceArt\Characters\Garments\Enzo"
BODY_FBX = r"D:\Unreal-Projects\WattleviewGrove-ue58\SourceArt\Characters\Bodies\SKM_David_BodyMesh.fbx"
OUT_FBX = os.path.join(OUT_DIR, "SKM_Enzo_Outfit.fbx")
PREV = os.path.join(OUT_DIR, "Previews")
GNAME = "SKM_Enzo_Outfit"
SLOTS = ["M_FlannelShirt", "M_Trousers", "M_Belt", "M_Shoes"]
M_SHIRT, M_TROUS, M_BELT, M_SHOES, M_CAP = 0, 1, 2, 3, 4
SLOT_COL = {"M_FlannelShirt": (0.50, 0.09, 0.07, 1), "M_Trousers": (0.30, 0.20, 0.11, 1),
            "M_Belt": (0.13, 0.07, 0.035, 1), "M_Shoes": (0.24, 0.12, 0.05, 1), "CAP_TMP": (1, 0, 1, 1)}
STATS = {}
os.makedirs(PREV, exist_ok=True)
TAU = 2 * math.pi


def log(*a):
    print("[ENZO]", *a, flush=True)


def ss(e0, e1, x):
    if e0 == e1:
        return 1.0 if x >= e1 else 0.0
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


def lerp(a, b, t):
    return a + (b - a) * t


def wrap_pi(a):
    return (a + math.pi) % TAU - math.pi


def interp_table(table, x):
    """table: list of (x, v0, v1, ...) sorted by x; linear interpolation, clamped."""
    if x <= table[0][0]:
        return list(table[0][1:])
    if x >= table[-1][0]:
        return list(table[-1][1:])
    for a, b in zip(table, table[1:]):
        if a[0] <= x <= b[0]:
            t = (x - a[0]) / (b[0] - a[0])
            return [lerp(p, q, t) for p, q in zip(a[1:], b[1:])]


def override(ob):
    return bpy.context.temp_override(object=ob, active_object=ob, selected_objects=[ob],
                                     selected_editable_objects=[ob])


# --------------------------------------------------------------------------------------------
# Scene / body
# --------------------------------------------------------------------------------------------
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=BODY_FBX)
ARM = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
BODY = next(o for o in bpy.data.objects if o.type == 'MESH')
log("armature", ARM.name, "body", BODY.name, "bones", len(ARM.data.bones))
BW = [BODY.matrix_world @ v.co for v in BODY.data.vertices]
BN = [(BODY.matrix_world.to_3x3() @ v.normal).normalized() for v in BODY.data.vertices]
BPOLY = [tuple(p.vertices) for p in BODY.data.polygons]
BVH_BODY = BVHTree.FromPolygons(BW, BPOLY)


def side_bvh(sign):
    keep = [p for p in BPOLY if all(BW[i].x * sign > -1e-4 for i in p)]
    return BVHTree.FromPolygons(BW, keep)


BVH_SIDE = {1: side_bvh(1), -1: side_bvh(-1)}
BONE = {b.name: (ARM.matrix_world @ b.head_local, ARM.matrix_world @ b.tail_local) for b in ARM.data.bones}


def H(n):
    return BONE[n][0].copy()


def sfx(name, s):
    return name + ("_l" if s > 0 else "_r")


# materials (shared datablocks -> joins keep indices)
MATS = []
for n in SLOTS + ["CAP_TMP"]:
    m = bpy.data.materials.new(n)
    m.diffuse_color = SLOT_COL[n]
    MATS.append(m)
for m in BODY.data.materials:
    if m:
        m.diffuse_color = (0.72, 0.55, 0.45, 1)


# --------------------------------------------------------------------------------------------
# Mesh builder
# --------------------------------------------------------------------------------------------
class MB:
    def __init__(s):
        s.v, s.f, s.m, s.uv, s.inner, s.col = [], [], [], [], [], []

    def av(s, p):
        s.v.append(Vector(p))
        return len(s.v) - 1

    def af(s, idx, mat, uvs=None, inner=0, col=1.0):
        idx = tuple(idx)
        if len(set(idx)) < 3:
            return
        s.f.append(idx)
        s.m.append(mat)
        s.uv.append(uvs if uvs else [(0.0, 0.0)] * len(idx))
        s.inner.append(inner)
        s.col.append(col)

    def obj(s, name):
        me = bpy.data.meshes.new(name)
        me.from_pydata([tuple(v) for v in s.v], [], s.f)
        for m in MATS:
            me.materials.append(m)
        me.polygons.foreach_set('material_index', s.m)
        uvl = me.uv_layers.new(name='UVMap')
        for pi, p in enumerate(me.polygons):
            for k, li in enumerate(p.loop_indices):
                uvl.data[li].uv = s.uv[pi][k]
        a = me.attributes.new('inner', 'INT', 'FACE')
        a.data.foreach_set('value', s.inner)
        c = me.attributes.new('Col', 'BYTE_COLOR', 'CORNER')
        cols = []
        for pi, p in enumerate(me.polygons):
            for _ in p.loop_indices:
                g = s.col[pi]
                cols += [g, g, g, 1.0]
        c.data.foreach_set('color', cols)
        me.update()
        ob = bpy.data.objects.new(name, me)
        bpy.context.scene.collection.objects.link(ob)
        return ob


def ring_arcs(ring, closed=True):
    u = [0.0]
    n = len(ring)
    for j in range(n if closed else n - 1):
        u.append(u[-1] + (ring[(j + 1) % n] - ring[j]).length)
    return u


def add_tube(mb, rings, mat, inner_rows=(), cap0=None, cap1=None, closed=True, vco=None, u_off=0.0):
    N = len(rings[0])
    idx = [[mb.av(p) for p in r] for r in rings]
    arcs = [ring_arcs(r, closed) for r in rings]
    if vco is None:
        vco = [0.0]
        for i in range(1, len(rings)):
            vco.append(vco[-1] + sum((rings[i][j] - rings[i - 1][j]).length for j in range(N)) / N)
    for i in range(len(rings) - 1):
        fl = 1 if i in inner_rows else 0
        for j in range(N if closed else N - 1):
            j2 = (j + 1) % N
            mb.af((idx[i][j], idx[i][j2], idx[i + 1][j2], idx[i + 1][j]), mat,
                  [(u_off + arcs[i][j], vco[i]), (u_off + arcs[i][j + 1], vco[i]),
                   (u_off + arcs[i + 1][j + 1], vco[i + 1]), (u_off + arcs[i + 1][j], vco[i + 1])], fl)
    if cap0 is not None:
        mb.af(tuple(reversed(idx[0])), cap0)
    if cap1 is not None:
        mb.af(tuple(idx[-1]), cap1)
    return idx


def add_box_path(mb, path, w_dirs, h_dirs, w, h, mat, col=1.0, caps=True):
    """Sweep a w x h rectangle along a path. w_dirs/h_dirs: per-point unit vectors."""
    rings = []
    for p, wd, hd in zip(path, w_dirs, h_dirs):
        rings.append([p - wd * w / 2, p + wd * w / 2, p + wd * w / 2 + hd * h, p - wd * w / 2 + hd * h])
    idx = [[mb.av(q) for q in r] for r in rings]
    vco = [0.0]
    for i in range(1, len(path)):
        vco.append(vco[-1] + (path[i] - path[i - 1]).length)
    for i in range(len(rings) - 1):
        for j in range(4):
            j2 = (j + 1) % 4
            uu = [0, w, w + h, 2 * w + h, 2 * w + 2 * h]
            mb.af((idx[i][j], idx[i + 1][j], idx[i + 1][j2], idx[i][j2]), mat,
                  [(uu[j], vco[i]), (uu[j], vco[i + 1]), (uu[j + 1], vco[i + 1]), (uu[j + 1], vco[i])], 0, col)
    if caps:
        mb.af(tuple(idx[0]), mat, None, 0, col)
        mb.af(tuple(reversed(idx[-1])), mat, None, 0, col)
    return idx


def fix_normals_outward(ob, center_fn=None):
    """Recalculate normals of each connected island (closed or open) to point away from its centre."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(ob.data)
    bm.free()


# --------------------------------------------------------------------------------------------
# Skin sampling (angular envelope of body vertices around an axis)
# --------------------------------------------------------------------------------------------
NB = 72


def envelope(pts2, window_deg=14.0):
    R = [None] * NB
    w = math.radians(window_deg)
    span = int(w / TAU * NB) + 1
    for (x, y) in pts2:
        r = math.hypot(x, y)
        if r < 1e-6:
            continue
        a = math.atan2(y, x)
        kc = int(round(a / TAU * NB))
        for dk in range(-span, span + 1):
            k = (kc + dk) % NB
            da = wrap_pi(a - TAU * k / NB)
            if abs(da) <= w:
                val = r * math.cos(da)
                if R[k] is None or val > R[k]:
                    R[k] = val
    return R


def env_finish(R, fallback, min_cov=0.8):
    n = sum(1 for r in R if r is not None)
    if n == 0:
        out = [fallback] * NB
    elif n < min_cov * NB:
        out = [max(r, fallback) if r is not None else fallback for r in R]
    else:
        out = list(R)
        for k in range(NB):
            if out[k] is None:
                a = k
                while R[a % NB] is None:
                    a -= 1
                b = k
                while R[b % NB] is None:
                    b += 1
                t = (k - a) / (b - a)
                out[k] = lerp(R[a % NB], R[b % NB], t)
    for _ in range(2):
        out = [(out[k - 1] + 2 * out[k] + out[(k + 1) % NB]) * 0.25 for k in range(NB)]
    return out


def sampleR(R, phi):
    t = (phi % TAU) / TAU * NB
    k = int(t)
    f = t - k
    return R[k % NB] * (1 - f) + R[(k + 1) % NB] * f


def push_clear(points, bvh, clear, idxs=None, iters=3):
    """Move points outward along the nearest surface normal until they are >= clear from it."""
    moved = 0
    rng = range(len(points)) if idxs is None else idxs
    for _ in range(iters):
        for i in rng:
            p = points[i]
            loc, nrm, fi, d = bvh.find_nearest(p, 0.25)
            if loc is None:
                continue
            s = (p - loc).dot(nrm)
            if s < clear:
                points[i] = p + nrm * (clear - s)
                moved += 1
    return moved


# --------------------------------------------------------------------------------------------
# Virtual torso (culled on this body): elliptical sections estimated from corrective joints
#   z, centre_y, half_width, front_depth, back_depth
# --------------------------------------------------------------------------------------------
TORSO = [(0.80, 0.000, 0.176, 0.100, 0.120),
         (0.82, 0.000, 0.178, 0.105, 0.125),
         (0.86, 0.000, 0.183, 0.110, 0.130),
         (0.90, 0.000, 0.185, 0.118, 0.130),
         (0.94, 0.000, 0.183, 0.125, 0.125),
         (0.98, -0.005, 0.178, 0.135, 0.118),
         (1.02, -0.010, 0.172, 0.148, 0.112),
         (1.06, -0.010, 0.170, 0.155, 0.108),
         (1.12, -0.010, 0.170, 0.155, 0.108),
         (1.18, -0.005, 0.172, 0.148, 0.115),
         (1.24, 0.000, 0.180, 0.140, 0.125),
         (1.30, 0.010, 0.192, 0.135, 0.138),
         (1.36, 0.015, 0.198, 0.132, 0.145)]


def ell_pt(cy, a, f, b, th, n=2.3):
    s, c = math.sin(th), math.cos(th)
    sx = math.copysign(abs(s) ** (2.0 / n), s)
    cx = math.copysign(abs(c) ** (2.0 / n), c)
    return a * sx, cy - (f if c > 0 else b) * cx


def torso_ring(z, ease, Hn, n=2.3, pinch_f=0.0, pinch_b=0.0, pert=None):
    cy, a, f, b = interp_table(TORSO, z)
    pts = []
    for k in range(Hn):
        th = TAU * k / Hn
        e = ease + (pert(th) if pert else 0.0)
        x, y = ell_pt(cy, a + e, f + e, b + e, th, n)
        y += pinch_f * math.exp(-(wrap_pi(th) / 0.45) ** 2)
        y -= pinch_b * math.exp(-(wrap_pi(th - math.pi) / 0.45) ** 2)
        pts.append(Vector((x, y, z)))
    return pts


# ---------------- shirt torso ----------------
HS = 40
SHIRT_ROWS = [(0.962, 0.006), (0.99, 0.006), (1.025, 0.006), (1.040, 0.008), (1.052, 0.021),
              (1.075, 0.024), (1.105, 0.023), (1.14, 0.022), (1.18, 0.022), (1.22, 0.022),
              (1.26, 0.022), (1.30, 0.022), (1.34, 0.022)]
# shoulder rows above z=1.34: (r_side, z_side), (r_front, z_front), (r_back, z_back), centre_y
SHOULDER = [((0.222, 1.390), (0.150, 1.390), (0.170, 1.390), 0.016),
            ((0.222, 1.430), (0.135, 1.425), (0.163, 1.430), 0.020),
            ((0.205, 1.465), (0.114, 1.450), (0.148, 1.465), 0.023),
            ((0.170, 1.495), (0.094, 1.465), (0.125, 1.495), 0.026),
            ((0.125, 1.515), (0.080, 1.472), (0.100, 1.518), 0.028),
            ((0.086, 1.528), (0.075, 1.476), (0.080, 1.534), 0.028)]


def shoulder_pt(row, th):
    (rs, zs), (rf, zf), (rb, zb), cy = SHOULDER[row]
    c, s = math.cos(th), math.sin(th)
    wf, wb, ws = max(c, 0) ** 2, max(-c, 0) ** 2, s * s
    x, y = ell_pt(cy, rs, rf, rb, th, 2.15)
    z = wf * zf + wb * zb + ws * zs
    return Vector((x, y, z))


def neck_hole(th):
    return shoulder_pt(len(SHOULDER) - 1, th)


def blouse(z):
    def f(th):
        amp = 0.0045 * ss(1.045, 1.06, z) * (1 - ss(1.08, 1.15, z))
        return amp * math.sin(7 * th + 0.6) + 0.002 * math.sin(3 * th + 1.3) * ss(1.045, 1.06, z)
    return f


def build_shirt_torso():
    rings = []
    for z, e in SHIRT_ROWS:
        r = torso_ring(z, e, HS, 2.3, pert=blouse(z))
        if 1.04 < z < 1.32:  # side seams: tiny inward groove
            for k in (HS // 4, 3 * HS // 4):
                r[k] = r[k] + (Vector((0, r[k].y, 0)) - Vector((r[k].x, r[k].y, 0))).normalized() * 0.0015
        rings.append(r)
    for row in range(len(SHOULDER)):
        r = [shoulder_pt(row, TAU * k / HS) for k in range(HS)]
        if row == 1:  # back yoke seam groove
            for k in range(HS):
                th = TAU * k / HS
                if math.cos(th) < -0.25:
                    c = Vector((0, SHOULDER[row][3], r[k].z))
                    r[k] = r[k] + (c - r[k]).normalized() * 0.0015
        rings.append(r)
    mb = MB()
    add_tube(mb, rings, M_SHIRT, cap0=M_CAP, cap1=M_CAP, vco=[r[0].z for r in rings])
    return mb.obj("tmp_shirt_torso"), rings


# ---------------- sleeves ----------------
NSL = 20
ARM_PTS = {1: [v for v in BW if v.x > 0.15 and v.z > 0.98], -1: [v for v in BW if v.x < -0.15 and v.z > 0.98]}


def arm_axes(s):
    return H(sfx('upperarm', s)), H(sfx('lowerarm', s)), H(sfx('hand', s))


def arm_frame(axis, s):
    under = Vector((-s, 0.0, -0.35))
    under = (under - axis * under.dot(axis)).normalized()
    e1 = axis.cross(under).normalized()
    return under, e1


def arm_skin_env(s, c, axis, e0, e1, fallback, band=0.02):
    pts = []
    for v in ARM_PTS[s]:
        d = v - c
        a = d.dot(axis)
        if abs(a) < band:
            q = d - axis * a
            if q.length < 0.13:
                pts.append((q.dot(e0), q.dot(e1)))
    return env_finish(envelope(pts), fallback)


def sleeve_stations(s):
    S, E, Hd = arm_axes(s)
    du, df = (E - S).normalized(), (Hd - E).normalized()
    Lu, Lf = (E - S).length, (Hd - E).length
    st = []  # (centre, axis, ease, T)
    for t, ease in [(-0.16, 0.0), (-0.06, 0.012), (0.04, 0.02), (0.16, 0.02), (0.30, 0.02), (0.45, 0.02),
                    (0.60, 0.021), (0.74, 0.022), (0.86, 0.024), (0.95, 0.026)]:
        st.append((S + du * (t * Lu), du, ease, t))
    st.append((E, (du + df).normalized(), 0.026, 1.0))
    for sfr, ease in [(0.06, 0.024), (0.12, 0.017), (0.20, 0.013)]:
        st.append((E + df * (sfr * Lf), df, ease, 1.0 + sfr * Lf / Lu))
    return st


def build_sleeve(s):
    rings = []
    for i, (c, axis, ease, T) in enumerate(sleeve_stations(s)):
        e0, e1 = arm_frame(axis, s)
        fb = 0.064 if T < 0.35 else 0.05
        R = arm_skin_env(s, c, axis, e0, e1, fb)
        ring = []
        for j in range(NSL):
            psi = TAU * j / NSL
            d = math.cos(psi) * e0 + math.sin(psi) * e1
            r = sampleR(R, psi) + ease
            if T < 0:  # inside the torso: taper so the start cap stays hidden
                r = lerp(0.045, r, ss(-0.16, 0.0, T))
            front = max(0.0, d.dot(Vector((0, -1, 0)))) ** 2
            if 0.8 < T < 1.15:  # elbow folds on the inner side
                r += front * (0.004 if i % 2 == 0 else -0.002)
            if 0.25 < T < 0.8:  # underarm slack so the arm can swing forward
                r += 0.006 * max(0.0, math.cos(psi)) ** 2 * ss(0.25, 0.4, T) * (1 - ss(0.6, 0.8, T))
            ring.append(c + d * r)
        rings.append(ring)
    mb = MB()
    vco = [0.0]
    for i in range(1, len(rings)):
        vco.append(vco[-1] + (sum(rings[i], Vector()) / NSL - sum(rings[i - 1], Vector()) / NSL).length)
    add_tube(mb, rings, M_SHIRT, cap0=M_CAP, cap1=M_CAP, vco=vco, u_off=(2.0 if s > 0 else 3.0))
    return mb.obj("tmp_sleeve_" + ("l" if s > 0 else "r")), rings


def join(obs, name):
    for o in list(bpy.context.selected_objects):
        o.select_set(False)
    for o in obs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = obs[0]
    with bpy.context.temp_override(active_object=obs[0], object=obs[0], selected_objects=obs,
                                   selected_editable_objects=obs):
        bpy.ops.object.join()
    obs[0].name = name
    obs[0].data.name = name
    return obs[0]


def boolean_union_self(ob):
    for o in list(bpy.context.selected_objects):
        o.select_set(False)
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.intersect_boolean(operation='UNION', use_swap=False, use_self=True, solver='EXACT')
    bpy.ops.object.mode_set(mode='OBJECT')


def delete_mat_faces(ob, mat_index):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    kill = [f for f in bm.faces if f.material_index == mat_index]
    bmesh.ops.delete(bm, geom=kill, context='FACES')
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context='VERTS')
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()


def mesh_bvh(ob, skip_inner=True, mats=None):
    me = ob.data
    vs = [ob.matrix_world @ v.co for v in me.vertices]
    inner = me.attributes.get('inner')
    polys = []
    for p in me.polygons:
        if skip_inner and inner and inner.data[p.index].value:
            continue
        if mats is not None and p.material_index not in mats:
            continue
        polys.append(tuple(p.vertices))
    return BVHTree.FromPolygons(vs, polys)


# --------------------------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------------------------
def setup_render():
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_WORKBENCH'
    sh = sc.display.shading
    sh.light = 'STUDIO'
    sh.color_type = 'MATERIAL'
    sh.show_cavity = True
    sh.cavity_type = 'BOTH'
    sh.show_object_outline = False
    if not sc.world:
        sc.world = bpy.data.worlds.new("W")
    sc.world.color = (0.78, 0.79, 0.81)
    if "PrevCam" not in bpy.data.objects:
        cd = bpy.data.cameras.new("PrevCam")
        co = bpy.data.objects.new("PrevCam", cd)
        sc.collection.objects.link(co)
    sc.camera = bpy.data.objects["PrevCam"]


def render_view(fname, eye, target, scale, res=(900, 1200), ortho=True):
    sc = bpy.context.scene
    co = sc.camera
    co.data.type = 'ORTHO' if ortho else 'PERSP'
    co.data.ortho_scale = scale
    co.data.lens = 50
    co.location = eye
    co.rotation_euler = (Vector(target) - Vector(eye)).to_track_quat('-Z', 'Y').to_euler()
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.filepath = os.path.join(PREV, fname)
    bpy.ops.render.render(write_still=True)


# --------------------------------------------------------------------------------------------
# Trousers: hip rings (H verts) -> crotch row split into two leg rings sharing a crotch chain
# --------------------------------------------------------------------------------------------
HT = 32
HALF = HT // 2
MCH = 3
LT = HALF + 1 + MCH
TROUSER_HIP = [  # z, ease, pinch_front, pinch_back
    (0.820, 0.022, 0.055, 0.045), (0.860, 0.022, 0.030, 0.025), (0.900, 0.021, 0.012, 0.010),
    (0.940, 0.019, 0.0, 0.0), (0.980, 0.017, 0.0, 0.0), (1.010, 0.0155, 0.0, 0.0), (1.033, 0.0145, 0.0, 0.0)]
LEG_Z = [0.785, 0.74, 0.69, 0.635, 0.58, 0.54, 0.515, 0.49, 0.465, 0.44, 0.40, 0.34, 0.28, 0.225,
         0.185, 0.155, 0.130]
HEM_Z = 0.066
LEG_PROFILE = [(0.08, 0.071, 0.077), (0.30, 0.074, 0.079), (0.50, 0.079, 0.084), (0.65, 0.090, 0.096),
               (0.80, 0.098, 0.104)]
LEG_PTS = {1: [v for v in BW if v.x > 0.0 and v.z < 0.80], -1: [v for v in BW if v.x < 0.0 and v.z < 0.80]}


def leg_center(s, z):
    a, b, c = H(sfx('thigh', s)), H(sfx('calf', s)), H(sfx('foot', s))
    if z >= b.z:
        t = (z - b.z) / (a.z - b.z)
        p = b.lerp(a, t)
    else:
        t = (z - c.z) / (b.z - c.z)
        p = c.lerp(b, max(0.0, t))
    return Vector((p.x, p.y, z))


def leg_skin_R(s, z, c):
    pts = [(v.x - c.x, v.y - c.y) for v in LEG_PTS[s] if abs(v.z - z) < 0.02]
    return env_finish(envelope(pts), 0.082 if z > 0.6 else 0.05)


def leg_ease(z):
    return 0.018 if z > 0.6 else (0.02 if z > 0.38 else 0.015)


def build_trousers(shoe_bvh=None):
    mb = MB()
    hip_rows = [torso_ring(z, e, HT, 2.3, pf, pb) for (z, e, pf, pb) in TROUSER_HIP]
    # gentle gathers under the belt
    for ri in (5, 6):
        for k in range(HT):
            th = TAU * k / HT
            hip_rows[ri][k] = hip_rows[ri][k] + Vector((math.sin(th), -math.cos(th), 0)) * 0.0012 * math.sin(16 * th)
    F, B = hip_rows[0][0], hip_rows[0][HALF]
    chain = []
    for i in range(1, MCH + 1):
        t = i / (MCH + 1)
        p = B.lerp(F, t)
        p.z = 0.82 - 0.032 * math.sin(math.pi * t)
        chain.append(p)
    # verts
    hip_idx = [[mb.av(p) for p in r] for r in hip_rows]
    ch_idx = [mb.av(p) for p in chain]
    # hip faces (ascending rows => outward normals); UV u from front centre
    for i in range(len(hip_rows) - 1):
        a0, a1 = ring_arcs(hip_rows[i]), ring_arcs(hip_rows[i + 1])
        for k in range(HT):
            k2 = (k + 1) % HT
            mb.af((hip_idx[i][k], hip_idx[i][k2], hip_idx[i + 1][k2], hip_idx[i + 1][k]), M_TROUS,
                  [(a0[k], hip_rows[i][k].z), (a0[k + 1], hip_rows[i][k2].z),
                   (a1[k + 1], hip_rows[i + 1][k2].z), (a1[k], hip_rows[i + 1][k].z)])
    # waistband: rounded top edge + inner facing (inner=1)
    top = hip_rows[-1]
    wb_rings = [top]
    for dr, dz in [(-0.002, 0.003), (-0.005, 0.0), (-0.005, -0.035)]:
        ring = []
        for p in top:
            rad = Vector((p.x, p.y - interp_table(TORSO, p.z)[0], 0)).normalized()
            ring.append(p + rad * dr + Vector((0, 0, dz)))
        wb_rings.append(ring)
    wb_idx = [hip_idx[-1]] + [[mb.av(p) for p in r] for r in wb_rings[1:]]
    for i in range(3):
        a0, a1 = ring_arcs(wb_rings[i]), ring_arcs(wb_rings[i + 1])
        for k in range(HT):
            k2 = (k + 1) % HT
            mb.af((wb_idx[i][k], wb_idx[i][k2], wb_idx[i + 1][k2], wb_idx[i + 1][k]), M_TROUS,
                  [(a0[k], 1.033 + 0.01 * i), (a0[k + 1], 1.033 + 0.01 * i), (a1[k + 1], 1.043 + 0.01 * i),
                   (a1[k], 1.043 + 0.01 * i)], 1 if i == 2 else 0)
    legs = {}
    for s in (1, -1):
        if s > 0:
            crotch_idx = [hip_idx[0][k] for k in range(HALF + 1)] + ch_idx
        else:
            crotch_idx = [hip_idx[0][0]] + list(reversed(ch_idx)) + [hip_idx[0][k] for k in range(HALF, HT)]
        crotch_pts = [mb.v[i] for i in crotch_idx]
        c0 = leg_center(s, 0.80)
        phis = []
        for p in crotch_pts:
            a = math.atan2(p.y - c0.y, p.x - c0.x)
            if phis:
                while a <= phis[-1]:
                    a += TAU
            phis.append(a)
        uni = [phis[0] + TAU * j / LT for j in range(LT)]
        rings = []
        zs = LEG_Z + ["hem"]
        for zi, z in enumerate(zs):
            zz = HEM_Z if z == "hem" else z
            c = leg_center(s, zz)
            R = leg_skin_R(s, zz, c)
            rx, ry = interp_table(LEG_PROFILE, zz)
            w = ss(0.80, 0.60, zz)
            ring = []
            for j in range(LT):
                phi = lerp(phis[j], uni[j], w)
                d = Vector((math.cos(phi), math.sin(phi), 0))
                prof = 1.0 / math.sqrt((d.x / rx) ** 2 + (d.y / ry) ** 2)
                r = max(sampleR(R, phi) + leg_ease(zz), prof)
                back, front = max(0.0, d.y) ** 2, max(0.0, -d.y) ** 2
                if 0.42 < zz < 0.60:  # folds behind the knee
                    r += back * (0.010 if zi % 2 == 0 else 0.004)  # knee bagging: slack for sitting
                if 0.12 < zz < 0.20:  # break above the shoe
                    r += front * (0.005 if zi % 2 == 0 else -0.001) + 0.002
                if 0.70 < zz < 0.80:  # seat/groin ease
                    r += 0.002
                p = c + d * r
                if z == "hem":
                    p.z = HEM_Z + 0.012 * math.sqrt(front)
                    if shoe_bvh is not None:  # hem rests on the shoe (break over the instep)
                        hit = shoe_bvh.ray_cast(Vector((p.x, p.y, 0.30)), Vector((0, 0, -1)), 0.4)
                        if hit[0] is not None and hit[0].z > 0.03:
                            p.z = min(0.118, max(p.z, hit[0].z + 0.008))
                if p.x * s < 0.001:
                    p.x = 0.001 * s
                ring.append(p)
            rings.append(ring)
        # z-smooth radial offsets between neighbouring rings (not the hem)
        legs[s] = (crotch_idx, rings)
    # clearance vs body and shoes on the leg rings
    for s in (1, -1):
        crotch_idx, rings = legs[s]
        flat = [p for r in rings for p in r]
        push_clear(flat, BVH_BODY, 0.009)
        if shoe_bvh is not None:
            low = [i for i, p in enumerate(flat) if p.z < 0.2]
            push_clear(flat, shoe_bvh, 0.005, low)
        for i, p in enumerate(flat):
            if p.x * s < 0.001:
                p.x = 0.001 * s
        n = LT
        rings = [flat[i * n:(i + 1) * n] for i in range(len(rings))]
        # hem facing (inner)
        hem, above = rings[-1], rings[-2]
        cH = leg_center(s, HEM_Z)
        fac1, fac2 = [], []
        for p, q in zip(hem, above):
            rad = Vector((p.x - cH.x, p.y - cH.y, 0)).normalized()
            fac1.append(p - rad * 0.004)
            # facing stays inside both the hem ring and the ring above (fold offsets alternate)
            m = p.lerp(q, 0.7)
            cm = leg_center(s, m.z)
            r_in = min(Vector((p.x - cH.x, p.y - cH.y)).length, Vector((q.x - cm.x, q.y - cm.y)).length) - 0.006
            fac2.append(Vector((cm.x, cm.y, m.z)) + rad * r_in)
        legs[s] = (crotch_idx, rings, fac1, fac2)
    for s in (1, -1):
        crotch_idx, rings, fac1, fac2 = legs[s]
        idx = [crotch_idx] + [[mb.av(p) for p in r] for r in rings] + [[mb.av(p) for p in fac1],
                                                                        [mb.av(p) for p in fac2]]
        pts = [[mb.v[i] for i in row] for row in idx]
        uoff = 1.5 if s > 0 else 2.5
        for i in range(len(idx) - 1):
            a0, a1 = ring_arcs(pts[i]), ring_arcs(pts[i + 1])
            fl = 1 if i >= len(idx) - 3 else 0
            for j in range(LT):
                j2 = (j + 1) % LT
                # leg rings descend: reverse winding to keep normals outward
                mb.af((idx[i][j], idx[i + 1][j], idx[i + 1][j2], idx[i][j2]), M_TROUS,
                      [(uoff + a0[j], pts[i][j].z), (uoff + a1[j], pts[i + 1][j].z),
                       (uoff + a1[j + 1], pts[i + 1][j2].z), (uoff + a0[j + 1], pts[i][j2].z)], fl)
    return mb.obj("tmp_trousers")


# --------------------------------------------------------------------------------------------
# Generic helpers: 2D hull, raised surface patches
# --------------------------------------------------------------------------------------------
def hull2d(pts):
    pts = sorted(set((round(x, 5), round(y, 5)) for x, y in pts))
    if len(pts) < 3:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, up = [], []
    for p in pts:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(up) >= 2 and cross(up[-2], up[-1], p) <= 0:
            up.pop()
        up.append(p)
    return lo[:-1] + up[:-1]  # CCW


def resample_closed(poly, n, start):
    m = len(poly)
    poly = poly[start:] + poly[:start]
    seg = [math.dist(poly[i], poly[(i + 1) % m]) for i in range(m)]
    tot = sum(seg)
    out, acc, i = [], 0.0, 0
    for k in range(n):
        target = tot * k / n
        while acc + seg[i] < target - 1e-12:
            acc += seg[i]
            i += 1
        t = (target - acc) / seg[i] if seg[i] > 0 else 0
        a, b = poly[i], poly[(i + 1) % m]
        out.append((lerp(a[0], b[0], t), lerp(a[1], b[1], t)))
    return out


def poly_normals(poly):
    n = len(poly)
    out = []
    for i in range(n):
        a, b = poly[i - 1], poly[(i + 1) % n]
        tx, ty = b[0] - a[0], b[1] - a[1]
        l = math.hypot(tx, ty) or 1
        out.append((ty / l, -tx / l))  # CCW polygon -> outward
    return out


def newell(pts):
    n = Vector()
    for i in range(len(pts)):
        a, b = pts[i], pts[(i + 1) % len(pts)]
        n += Vector(((a.y - b.y) * (a.z + b.z), (a.z - b.z) * (a.x + b.x), (a.x - b.x) * (a.y + b.y)))
    return n


def af_oriented(mb, idx, mat, uvs, want, inner=0, col=1.0):
    if newell([mb.v[i] for i in idx]).dot(want) < 0:
        idx = list(reversed(idx))
        uvs = list(reversed(uvs)) if uvs else None
    mb.af(idx, mat, uvs, inner, col)


def densify(rays, sub):
    """Bilinearly subdivide a rows x cols grid of (origin, direction) rays."""
    if sub <= 1:
        return rays
    R, C = len(rays), len(rays[0])
    out = []
    for r in range((R - 1) * sub + 1):
        r0 = min(r // sub, R - 2)
        fr = r / sub - r0
        row = []
        for c in range((C - 1) * sub + 1):
            c0 = min(c // sub, C - 2)
            fc = c / sub - c0
            o = (rays[r0][c0][0] * (1 - fc) + rays[r0][c0 + 1][0] * fc) * (1 - fr) + \
                (rays[r0 + 1][c0][0] * (1 - fc) + rays[r0 + 1][c0 + 1][0] * fc) * fr
            d = (rays[r0][c0][1] * (1 - fc) + rays[r0][c0 + 1][1] * fc) * (1 - fr) + \
                (rays[r0 + 1][c0][1] * (1 - fc) + rays[r0 + 1][c0 + 1][1] * fc) * fr
            row.append((o, d.normalized()))
        out.append(row)
    return out


def add_patch(mb, bvh, rays, off, mat, embed=0.0015, col=1.0, uvmode='xz', sub=1):
    """rays: rows x cols of (origin, direction). Builds a raised slab following the hit surface."""
    rays = densify(rays, sub)
    top, bot, nrm = [], [], []
    for row in rays:
        tr, br, nr = [], [], []
        for o, d in row:
            loc, n, fi, dist = bvh.ray_cast(o, d, 2.0)
            if loc is None:
                log("patch ray miss", o, d)
                return False
            if n.dot(d) > 0:
                n = -n
            tr.append(loc + n * off)
            br.append(loc - n * embed)
            nr.append(n)
        top.append(tr)
        bot.append(br)
        nrm.append(nr)
    R, C = len(top), len(top[0])
    ti = [[mb.av(p) for p in r] for r in top]
    bi = [[mb.av(p) for p in r] for r in bot]

    def uv(p):
        if uvmode == 'xz':
            return (p.x, p.z)
        if uvmode == '-xz':
            return (-p.x, p.z)
        if uvmode == 'xy':
            return (p.x, p.y)
        return (p.y, p.z)
    cen = sum((p for r in top for p in r), Vector()) / (R * C)
    for r in range(R - 1):
        for c in range(C - 1):
            ids = [ti[r][c], ti[r][c + 1], ti[r + 1][c + 1], ti[r + 1][c]]
            want = nrm[r][c] + nrm[r + 1][c + 1]
            af_oriented(mb, ids, mat, [uv(mb.v[i]) for i in ids], want, 0, col)
    per = [(0, c) for c in range(C)] + [(r, C - 1) for r in range(1, R)] + \
          [(R - 1, c) for c in range(C - 2, -1, -1)] + [(r, 0) for r in range(R - 2, 0, -1)]
    for k in range(len(per)):
        (r0, c0), (r1, c1) = per[k], per[(k + 1) % len(per)]
        ids = [ti[r0][c0], ti[r1][c1], bi[r1][c1], bi[r0][c0]]
        mid = (mb.v[ti[r0][c0]] + mb.v[ti[r1][c1]]) / 2
        want = mid - cen
        want = want - nrm[r0][c0] * want.dot(nrm[r0][c0])
        af_oriented(mb, ids, mat, [uv(mb.v[i]) for i in ids], want, 0, col)
    return True


# --------------------------------------------------------------------------------------------
# Shoes: stacked horizontal outlines (3D-dilated foot hull), welt + sole + heel, lace panel, toe cap
# --------------------------------------------------------------------------------------------
NSH = 20
FOOT_PTS = {s: [v for v in BW if v.x * s > 0.03 and v.z < 0.18] for s in (1, -1)}
SHOE_Z = [0.016, 0.028, 0.040, 0.051, 0.062, 0.074, 0.088, 0.104, 0.120, 0.135]


def shoe_outline(s, z, clr):
    pts = [(v.x, v.y) for v in FOOT_PTS[s] if abs(v.z - z) < 0.014]
    h = hull2d(pts)
    nr = poly_normals(h)
    h = hull2d([(p[0] + n[0] * clr, p[1] + n[1] * clr) for p, n in zip(h, nr)])
    start = max(range(len(h)), key=lambda i: h[i][1])  # heel (max y)
    return resample_closed(h, NSH, start)


def build_shoe(s):
    mb = MB()
    ups = []
    for z in SHOE_Z:
        clr = 0.0125 if z < 0.035 else (0.0115 if z < 0.10 else 0.0135)
        ups.append([Vector((x, y, z)) for x, y in shoe_outline(s, z, clr)])
    for i in range(1, len(ups) - 1):  # light vertical smoothing of the outlines
        for j in range(NSH):
            a, b, c = ups[i - 1][j], ups[i][j], ups[i + 1][j]
            m = (a + c) / 2
            b.x = lerp(b.x, m.x, 0.25)
            b.y = lerp(b.y, m.y, 0.25)
    base2 = [(p.x, p.y) for p in ups[0]]
    nr = poly_normals(base2)
    heel = [ss(-0.03, 0.045, p.y) for p in ups[0]]
    for j, p in enumerate(ups[0]):
        p.z = 0.016 + 0.007 * heel[j]

    def off(j, d, z):
        p = ups[0][j]
        return Vector((p.x + nr[j][0] * d, p.y + nr[j][1] * d, z))
    # welt ledge + chunky sole (heel block raised at the back)
    sole_top = [off(j, 0.0085, 0.0135 + 0.007 * heel[j]) for j in range(NSH)]
    sole_mid = [off(j, 0.0085, -0.003) for j in range(NSH)]
    sole_bot = [off(j, 0.0055, -0.009) for j in range(NSH)]
    topr = ups[-1]
    ct = sum(topr, Vector()) / NSH
    f1 = [p + (Vector((ct.x, ct.y, p.z)) - p).normalized() * 0.005 + Vector((0, 0, -0.002)) for p in topr]
    f2 = [p + (Vector((ct.x, ct.y, p.z)) - p).normalized() * 0.006 + Vector((0, 0, -0.018)) for p in topr]
    rings = [sole_bot, sole_mid, sole_top] + ups + [f1, f2]
    nrow = len(rings)
    idx = add_tube(mb, rings, M_SHOES, inner_rows=(nrow - 3, nrow - 2), vco=[r[0].z for r in rings],
                   u_off=(0.0 if s > 0 else 0.5))
    cb = sum(sole_bot, Vector()) / NSH
    ci = mb.av(cb)
    for j in range(NSH):
        j2 = (j + 1) % NSH
        mb.af((ci, idx[0][j2], idx[0][j]), M_SHOES,
              [(cb.x, cb.y), (sole_bot[j2].x, sole_bot[j2].y), (sole_bot[j].x, sole_bot[j].y)])
    ob = mb.obj("tmp_shoe")
    bvh = mesh_bvh(ob)
    fa, ba = H(sfx('foot', s)), H(sfx('ball', s))

    def cx(y):
        t = (y - fa.y) / (ba.y - fa.y)
        return lerp(fa.x, ba.x, t) + 0.004 * s
    mb2 = MB()
    # lace panel (vamp) from the top opening forward; first find where the rays stop entering the opening
    ys = []
    for k in range(40):
        y = -0.02 - 0.0025 * k
        loc, n, fi, d = bvh.ray_cast(Vector((cx(y), y, 0.5)), Vector((0, 0, -1)), 2.0)
        if loc is not None and loc.z > 0.06:
            ys.append(y)
    y0 = max(ys) - 0.006
    STATS.setdefault('lace_y0', []).append(round(y0, 4))
    prow = [y0 - 0.0155 * k for k in range(5)]
    rows = [[(Vector((cx(y) + dx * (1 - 0.25 * k / 4), y, 0.5)), Vector((0, 0, -1))) for dx in (-0.017, 0.0, 0.017)]
            for k, y in enumerate(prow)]
    add_patch(mb2, bvh, rows, 0.0022, M_SHOES, uvmode='xy', sub=2)
    for y in [y0 - 0.008 - 0.0145 * k for k in range(4)]:  # laces
        path, nn = [], []
        for dx in (-0.014, -0.007, 0.0, 0.007, 0.014):
            loc, n, fi, d = bvh.ray_cast(Vector((cx(y) + dx, y, 0.5)), Vector((0, 0, -1)), 2.0)
            if loc is None:
                break
            if n.z < 0:
                n = -n
            path.append(loc + n * 0.0026)
            nn.append(n)
        if len(path) == 5:
            add_box_path(mb2, path, [Vector((0, -1, 0))] * 5, nn, 0.0035, 0.0016, M_SHOES, col=0.0)
    ob2 = mb2.obj("tmp_shoe_detail")
    tag_solid(ob2)
    return join([ob, ob2], "shoe_" + ("l" if s > 0 else "r"))


def recalc_normals(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(ob.data)
    bm.free()


def tag_solid(ob, val=1):
    a = ob.data.attributes.get('solid') or ob.data.attributes.new('solid', 'INT', 'FACE')
    a.data.foreach_set('value', [val] * len(ob.data.polygons))


def add_closed_sweep(mb, sections, mat, closed_path=False, caps=True, col=1.0, uv_sc=1.0):
    """sections: list of closed loops (same vertex count). Faces between consecutive loops."""
    n = len(sections[0])
    idx = [[mb.av(p) for p in sec] for sec in sections]
    vco = [0.0]
    for i in range(1, len(sections)):
        vco.append(vco[-1] + (sum(sections[i], Vector()) / n - sum(sections[i - 1], Vector()) / n).length)
    if closed_path:
        vco.append(vco[-1] + (sum(sections[0], Vector()) / n - sum(sections[-1], Vector()) / n).length)
    m = len(sections) if closed_path else len(sections) - 1
    for i in range(m):
        i2 = (i + 1) % len(sections)
        arc = ring_arcs(sections[i])
        for j in range(n):
            j2 = (j + 1) % n
            mb.af((idx[i][j], idx[i][j2], idx[i2][j2], idx[i2][j]), mat,
                  [(arc[j] * uv_sc, vco[i]), (arc[j + 1] * uv_sc, vco[i]), (arc[j + 1] * uv_sc, vco[i + 1]),
                   (arc[j] * uv_sc, vco[i + 1])], 0, col)
    if caps and not closed_path:
        mb.af(tuple(idx[0]), mat, [(p.x, p.z) for p in sections[0]], 0, col)
        mb.af(tuple(reversed(idx[-1])), mat, [(p.x, p.z) for p in sections[-1]], 0, col)
    return idx


def add_button(mb, c, n, r=0.0055, h=0.002, seg=8):
    n = n.normalized()
    t1 = n.cross(Vector((0, 0, 1)))
    if t1.length < 1e-3:
        t1 = n.cross(Vector((1, 0, 0)))
    t1.normalize()
    t2 = n.cross(t1)
    bot = [mb.av(c + (t1 * math.cos(TAU * k / seg) + t2 * math.sin(TAU * k / seg)) * r) for k in range(seg)]
    top = [mb.av(c + n * h + (t1 * math.cos(TAU * k / seg) + t2 * math.sin(TAU * k / seg)) * r * 0.85)
           for k in range(seg)]
    for k in range(seg):
        k2 = (k + 1) % seg
        ids = [bot[k], bot[k2], top[k2], top[k]]
        af_oriented(mb, ids, M_SHIRT, [(0.001, 0.001)] * 4, (mb.v[bot[k]] + mb.v[bot[k2]]) / 2 - c, 0, 0.0)
    af_oriented(mb, top, M_SHIRT, [(0.001, 0.001)] * seg, n, 0, 0.0)


# --------------------------------------------------------------------------------------------
# Shirt details: collar, placket, buttons, chest pocket with flap, rolled cuffs
# --------------------------------------------------------------------------------------------
def front_rays(pts_xz, y0=-0.6):
    return [[(Vector((x, y0, z)), Vector((0, 1, 0))) for (x, z) in row] for row in pts_xz]


def build_collar(shirt_bvh):
    mb = MB()
    secs = []
    n_sec = 22
    th0 = math.radians(3)
    for i in range(n_sec):
        th = th0 + (TAU - 2 * th0) * i / (n_sec - 1)
        dfront = min(th, TAU - th)  # angular distance from centre front
        sgn = 1 if th < math.pi else -1
        base = neck_hole(th)
        cy = SHOULDER[-1][3]
        nh = Vector((base.x, base.y - cy, 0)).normalized()
        up = Vector((0, 0, 1))
        extra = ss(math.radians(45), math.radians(6), dfront)
        p0 = base - nh * 0.004 + up * -0.007
        p1 = base - nh * 0.006 + up * 0.031
        p2 = base - nh * 0.001 + up * (0.037 - 0.004 * extra)
        p3 = base + nh * 0.006 + up * (0.034 - 0.004 * extra)
        p7 = base + nh * 0.0025 + up * 0.029
        p8 = base + nh * 0.0025 + up * -0.007
        # fall edge lands on the shirt (yoke / chest) and lengthens into collar points at the front
        thT = th + sgn * math.radians(22) * extra
        bT = neck_hole(thT)
        nT = Vector((bT.x, bT.y - cy, 0)).normalized()
        dist = 0.030 + 0.042 * extra
        T = bT + (nT * 0.62 - up * 0.78) * dist
        loc, nrm, fi, d = shirt_bvh.find_nearest(T, 0.2)
        if loc is None:
            loc, nrm = T, nT
        p5 = loc + nrm * 0.0035
        p6 = loc + nrm * 0.0012 + (p8 - loc).normalized() * 0.003
        p4 = (p3 + p5) / 2 + nh * 0.004 + up * 0.002
        p45 = (p7 + p6) / 2 + nh * 0.0015
        secs.append([p0, p1, p2, p3, p4, p5, p6, p45, p7, p8])
    add_closed_sweep(mb, secs, M_SHIRT, closed_path=False, caps=True)
    ob = mb.obj("collar")
    recalc_normals(ob)
    tag_solid(ob)
    return ob


def build_shirt_overlays(shirt_bvh):
    mb = MB()
    # placket (box pleat strip, centre front)
    zs = [1.43, 1.40, 1.37, 1.34, 1.30, 1.26, 1.22, 1.18, 1.14, 1.10, 1.07, 1.05]
    add_patch(mb, shirt_bvh, front_rays([[(x, z) for x in (-0.016, 0.0, 0.016)] for z in zs]), 0.0025, M_SHIRT)
    # chest pocket on the wearer's left (+x)
    rows = [[(0.030, 1.352), (0.063, 1.352), (0.096, 1.352), (0.128, 1.352)],
            [(0.030, 1.318), (0.063, 1.318), (0.096, 1.318), (0.128, 1.318)],
            [(0.030, 1.282), (0.063, 1.282), (0.096, 1.282), (0.128, 1.282)],
            [(0.031, 1.252), (0.063, 1.249), (0.096, 1.249), (0.127, 1.252)],
            [(0.040, 1.236), (0.063, 1.232), (0.096, 1.232), (0.118, 1.236)]]
    add_patch(mb, shirt_bvh, front_rays(rows), 0.0022, M_SHIRT)
    rows = [[(0.026, 1.364), (0.079, 1.364), (0.132, 1.364)],
            [(0.026, 1.338), (0.079, 1.336), (0.132, 1.338)],
            [(0.040, 1.325), (0.079, 1.316), (0.118, 1.325)]]
    add_patch(mb, shirt_bvh, front_rays(rows), 0.0042, M_SHIRT)
    # buttons
    btn = [(0.0, z, 0.0025) for z in (1.415, 1.340, 1.265, 1.190, 1.115)] + [(0.079, 1.327, 0.0042)]
    for x, z, off in btn:
        loc, n, fi, d = shirt_bvh.ray_cast(Vector((x, -0.6, z)), Vector((0, 1, 0)), 2.0)
        if loc is not None:
            if n.y > 0:
                n = -n
            add_button(mb, loc + n * (off - 0.0005), n)
    ob = mb.obj("shirt_overlays")
    tag_solid(ob)
    return ob


def build_cuff(s):
    S, E, Hd = arm_axes(s)
    df = (Hd - E).normalized()
    Lf = (Hd - E).length
    s_bot, s_top = 0.36, 0.12
    h = (s_bot - s_top) * Lf
    e0, e1 = arm_frame(df, s)
    NC = 16
    prof = [(0.0090, 0.0), (0.0190, 0.002), (0.0230, 0.020), (0.0190, 0.031), (0.0230, 0.041),
            (0.0195, h), (0.0100, h - 0.003)]
    Rs = {}
    secs = []
    for d, a in prof:
        c = E + df * (s_bot * Lf - a)
        key = round(a, 4)
        if key not in Rs:
            Rs[key] = arm_skin_env(s, c, df, e0, e1, 0.045, band=0.025)
        R = Rs[key]
        secs.append([c + (math.cos(TAU * j / NC) * e0 + math.sin(TAU * j / NC) * e1) * (sampleR(R, TAU * j / NC) + d)
                     for j in range(NC)])
    mb = MB()
    add_closed_sweep(mb, secs, M_SHIRT, closed_path=True, caps=False)
    ob = mb.obj("cuff_" + ("l" if s > 0 else "r"))
    recalc_normals(ob)
    tag_solid(ob)
    return ob


# --------------------------------------------------------------------------------------------
# Trouser details: belt + buckle + tail, belt loops, back pockets, front pocket edges, fly
# --------------------------------------------------------------------------------------------
def out_dir(th):
    return Vector((math.sin(th), -math.cos(th), 0))


def radial_hit(bvh, th, z, cy=-0.008):
    o = Vector((0, cy, z)) + out_dir(th) * 0.6
    loc, n, fi, d = bvh.ray_cast(o, -out_dir(th), 1.0)
    return loc, n


def wob(i, k=1.0):
    return math.sin(i * 12.9898 * k + 78.233) * 0.5


def build_belt(trous_bvh):
    mb = MB()
    NBT = 40
    z0, z1 = 0.999, 1.030
    secs = []
    for i in range(NBT):
        th = TAU * i / NBT
        lo, _ = radial_hit(trous_bvh, th, z0)
        hi, _ = radial_hit(trous_bvh, th, z1)
        o = out_dir(th)
        t = 0.0042 + 0.0006 * wob(i)
        dz = 0.0008 * wob(i, 3.1)
        a = lo + o * 0.0015
        b = hi + o * 0.0015
        secs.append([a + Vector((0, 0, dz)), a + o * t + Vector((0, 0, dz)), b + o * t + Vector((0, 0, dz)),
                     b + Vector((0, 0, dz))])
    add_closed_sweep(mb, secs, M_BELT, closed_path=True, caps=False, uv_sc=1.0)
    belt = mb.obj("belt")
    recalc_normals(belt)
    bb = mesh_bvh(belt)
    # buckle (flat frame on the belt front, slightly left of centre) + prong + tail
    mb2 = MB()
    loc, n = radial_hit(bb, 0.0, 0.5 * (z0 + z1))
    n = Vector((0, -1, 0))
    c = loc + n * 0.0008 + Vector((-0.006, 0, 0))
    W, Hh, bar, th = 0.054, 0.046, 0.0065, 0.0045
    X, Z = Vector((1, 0, 0)), Vector((0, 0, 1))
    corners = [c + X * (-W / 2) + Z * (-Hh / 2), c + X * (W / 2) + Z * (-Hh / 2),
               c + X * (W / 2) + Z * (Hh / 2), c + X * (-W / 2) + Z * (Hh / 2)]
    for k in range(4):
        a, b = corners[k], corners[(k + 1) % 4]
        d = (b - a).normalized()
        inward = (c - (a + b) / 2)
        inward = (inward - d * inward.dot(d)).normalized()
        path = [a - d * 0.0, b]
        add_box_path(mb2, [a + inward * bar / 2, b + inward * bar / 2], [inward] * 2, [n] * 2, bar, th, M_BELT, col=0.0)
    # prong across the frame
    add_box_path(mb2, [c + X * (-W / 2 + bar / 2) + n * th, c + X * (W / 2 - bar * 0.4) + n * th * 1.2],
                 [Z] * 2, [n] * 2, 0.0035, 0.0028, M_BELT, col=0.0)
    # tail of the strap running to the wearer's left over the belt, through the first loop
    path, wd, hd = [], [], []
    for k in range(7):
        thk = math.radians(4 + 6.5 * k)
        p, _ = radial_hit(bb, thk, 0.5 * (z0 + z1))
        o = out_dir(thk)
        path.append(p + o * 0.0004)
        wd.append(Vector((0, 0, 1)))
        hd.append(o)
    add_box_path(mb2, path, wd, hd, 0.028, 0.0042, M_BELT)
    buck = mb2.obj("buckle")
    recalc_normals(buck)
    for o in (belt, buck):
        tag_solid(o)
    return join([belt, buck], "belt"), bb


def build_trouser_overlays(trous_bvh, belt_bvh):
    mb = MB()
    # belt loops
    for deg in (52, -52, 103, -103, 155, -155):
        th = math.radians(deg)
        o = out_dir(th)
        top, _ = radial_hit(trous_bvh, th, 1.034)
        b1, _ = radial_hit(belt_bvh, th, 1.0275)
        b2, _ = radial_hit(belt_bvh, th, 1.0015)
        low, _ = radial_hit(trous_bvh, th, 0.990)
        if None in (top, b1, b2, low):
            continue
        path = [top + o * 0.0005, b1 + o * 0.0015, b2 + o * 0.0015, low + o * 0.0005]
        tang = Vector((math.cos(th), math.sin(th), 0))
        add_box_path(mb, path, [tang] * 4, [o] * 4, 0.011, 0.0025, M_TROUS)
    # back pockets (patch)
    for s in (1, -1):
        rows = [[(s * x, z) for x in (0.035, 0.085, 0.135)] for z in (0.975, 0.93, 0.89)]
        rows.append([(s * 0.042, 0.856), (s * 0.085, 0.846), (s * 0.128, 0.856)])
        rays = [[(Vector((x, 0.6, z)), Vector((0, -1, 0))) for (x, z) in row] for row in rows]
        add_patch(mb, trous_bvh, rays, 0.003, M_TROUS, uvmode='-xz', sub=2)
    # slanted front pocket edges
    for s in (1, -1):
        rows = []
        for k in range(5):
            t = k / 4
            th = math.radians(lerp(30, 64, t)) * s
            z = lerp(0.992, 0.885, t)
            rows.append([(th, z), (th + math.radians(4.5) * s, z)])
        rays = [[(Vector((0, -0.008, z)) + out_dir(th) * 0.6, -out_dir(th)) for (th, z) in row] for row in rows]
        add_patch(mb, trous_bvh, rays, 0.0018, M_TROUS)
    # fly (left over right)
    rows = [[(0.003, 0.996), (0.019, 0.996), (0.035, 0.996)],
            [(0.003, 0.95), (0.019, 0.95), (0.035, 0.95)],
            [(0.003, 0.912), (0.019, 0.912), (0.033, 0.915)],
            [(0.003, 0.882), (0.014, 0.885), (0.024, 0.895)]]
    add_patch(mb, trous_bvh, front_rays(rows), 0.0016, M_TROUS)
    ob = mb.obj("trouser_overlays")
    tag_solid(ob)
    return ob


# ============================================================================================
# MAIN: assemble -> skin -> pose tests -> previews -> export -> round-trip verify
# (set ENZO_LIB=1 in the environment to load the builders only)
# ============================================================================================
T_SHIRT, T_COLLAR, T_SHIRT_OV, T_CUFF, T_TROUS, T_TROUS_OV, T_BELT, T_SHOE = 1, 2, 3, 4, 5, 6, 7, 8
MAX_INFL = 4
UV_PER_M = 2.0  # one texture tile = 50 cm of cloth


def set_tag(ob, t):
    a = ob.data.attributes.get('tag') or ob.data.attributes.new('tag', 'INT', 'POINT')
    a.data.foreach_set('value', [t] * len(ob.data.vertices))


def evaluated_world(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    oe = ob.evaluated_get(dg)
    me = oe.to_mesh()
    M = ob.matrix_world.copy()
    V = [M @ v.co for v in me.vertices]
    P = [tuple(p.vertices) for p in me.polygons]
    oe.to_mesh_clear()
    return V, P


def build_all():
    shl = build_shoe(1)
    shr = build_shoe(-1)
    shoe_bvh = BVHTree.FromPolygons([v.co for v in shl.data.vertices] + [v.co for v in shr.data.vertices],
                                    [tuple(p.vertices) for p in shl.data.polygons] +
                                    [tuple(i + len(shl.data.vertices) for i in p.vertices) for p in shr.data.polygons])
    tr = build_trousers(shoe_bvh)
    tb = mesh_bvh(tr)
    torso, _ = build_shirt_torso()
    sl, _ = build_sleeve(1)
    sr, _ = build_sleeve(-1)
    shirt = join([torso, sl, sr], "shirt")
    boolean_union_self(shirt)
    delete_mat_faces(shirt, M_CAP)
    sb = mesh_bvh(shirt)
    col = build_collar(sb)
    ov = build_shirt_overlays(sb)
    cl, cr = build_cuff(1), build_cuff(-1)
    belt, bb = build_belt(tb)
    tov = build_trouser_overlays(tb, bb)
    parts = [(shirt, T_SHIRT), (col, T_COLLAR), (ov, T_SHIRT_OV), (cl, T_CUFF), (cr, T_CUFF), (tr, T_TROUS),
             (tov, T_TROUS_OV), (belt, T_BELT), (shl, T_SHOE), (shr, T_SHOE)]
    for o, t in parts:
        set_tag(o, t)
        if o.data.attributes.get('inner') is None:
            o.data.attributes.new('inner', 'INT', 'FACE')
        log("part", o.name, "tris", sum(len(p.vertices) - 2 for p in o.data.polygons))
    return join([p[0] for p in parts], GNAME)


if os.environ.get('ENZO_LIB') != '1':
    ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    DO_RENDER = 'norender' not in ARGS
    DO_EXPORT = 'noexport' not in ARGS
    T0 = time.time()
    OUT = build_all()
    me = OUT.data
    # ---------------------------------------------------------------- clean-up, triangulate, UVs, slots
    assert all(p.material_index != M_CAP for p in me.polygons), "cap faces left"
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    bmesh.ops.triangulate(bm, faces=bm.faces[:], quad_method='BEAUTY', ngon_method='BEAUTY')
    bmesh.ops.dissolve_degenerate(bm, dist=1e-6, edges=bm.edges[:])
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 3])
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.calc_area() < 1e-10], context='FACES')
    seen, dup = set(), []
    for f in bm.faces:
        key = tuple(sorted(v.index for v in f.verts))
        if key in seen:
            dup.append(f)
        seen.add(key)
    bmesh.ops.delete(bm, geom=dup, context='FACES')
    log("removed duplicate faces", len(dup))
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    uvl = bm.loops.layers.uv.active
    for f in bm.faces:
        f.smooth = True
        for l in f.loops:
            l[uvl].uv = l[uvl].uv * UV_PER_M
    for e in bm.edges:
        e.smooth = not (len(e.link_faces) == 2 and e.calc_face_angle(0) > math.radians(60))
    bm.to_mesh(me)
    bm.free()
    me.materials.pop(index=M_CAP)
    me.update()
    TRIS = len(me.polygons)
    log("outfit verts", len(me.vertices), "tris", TRIS)
    TAGS = [d.value for d in me.attributes['tag'].data]
    INNER_F = [d.value for d in me.attributes['inner'].data]
    SOLID_F = [d.value for d in me.attributes['solid'].data]

    # ---------------------------------------------------------------- armature: drop the 0.01 import empty
    emp = ARM.parent
    mw = ARM.matrix_world.copy()
    ARM.parent = None
    ARM.matrix_world = mw
    if emp is not None:
        bpy.data.objects.remove(emp, do_unlink=True)
    bpy.context.view_layer.update()
    REST_W = [OUT.matrix_world @ v.co for v in me.vertices]  # outfit object is identity: world metres

    # ---------------------------------------------------------------- 1) Data Transfer from the body
    dt = OUT.modifiers.new("BodyWeights", 'DATA_TRANSFER')
    dt.object = BODY
    dt.use_vert_data = True
    dt.data_types_verts = {'VGROUP_WEIGHTS'}
    dt.vert_mapping = 'POLYINTERP_NEAREST'
    dt.layers_vgroup_select_src = 'ALL'
    dt.layers_vgroup_select_dst = 'NAME'
    with override(OUT):
        bpy.ops.object.datalayout_transfer(modifier=dt.name)
        bpy.ops.object.modifier_apply(modifier=dt.name)
    gname = {g.index: g.name for g in OUT.vertex_groups}
    DTW = [{gname[g.group]: g.weight for g in v.groups if g.weight > 1e-5} for v in me.vertices]
    log("data transfer: groups", len(OUT.vertex_groups))

    # ---------------------------------------------------------------- 2) procedural field where the body is culled
    BH = {b.name: ARM.matrix_world @ b.head_local for b in ARM.data.bones}
    CHAIN = [('pelvis', 0.93), ('spine_01', 0.5 * (BH['spine_01'].z + BH['spine_02'].z)),
             ('spine_02', 0.5 * (BH['spine_02'].z + BH['spine_03'].z)),
             ('spine_03', 0.5 * (BH['spine_03'].z + BH['spine_04'].z)),
             ('spine_04', 0.5 * (BH['spine_04'].z + BH['spine_05'].z)), ('spine_05', 1.40)]

    def chain_weights(z):
        if z <= CHAIN[0][1]:
            return {CHAIN[0][0]: 1.0}
        if z >= CHAIN[-1][1]:
            return {CHAIN[-1][0]: 1.0}
        for (b0, z0), (b1, z1) in zip(CHAIN, CHAIN[1:]):
            if z0 <= z <= z1:
                t = ss(z0, z1, z)
                return {b0: 1 - t, b1: t}

    ARMS = {}
    for s in (1, -1):
        S, E = BH[sfx('upperarm', s)], BH[sfx('lowerarm', s)]
        ARMS[s] = (S, (E - S).normalized(), (E - S).length)

    def arm_param(s, p):
        S, ax, L = ARMS[s]
        d = p - S
        a = d.dot(ax)
        return a / L, (d - ax * a).length

    def seg_closest(p, a, b):
        ab = b - a
        t = max(0.0, min(1.0, (p - a).dot(ab) / ab.length_squared))
        return a + ab * t

    def dist_to_chain(p, pts):
        return min((p - seg_closest(p, a, b)).length for a, b in zip(pts, pts[1:]))

    ARM_CHAIN = {s: [BH[sfx('upperarm', s)], BH[sfx('lowerarm', s)], BH[sfx('hand', s)]] for s in (1, -1)}

    def proc_weights(p, tag):
        W = {}

        def add(b, w):
            if w > 1e-6:
                W[b] = W.get(b, 0.0) + w
        x, y, z = p
        back = ss(-0.03, 0.07, y)
        side = ss(0.10, 0.19, abs(x))
        z_hi = lerp(lerp(0.92, 0.89, back), 0.90, side)
        z_lo = lerp(lerp(0.80, 0.76, back), 0.79, side)
        s_leg = ss(z_hi, z_lo, z)
        wl = ss(-0.025, 0.025, x)
        tw = 0.5 * ss(0.86, 0.72, z)
        for s, f in ((1, wl), (-1, 1 - wl)):
            add(sfx('thigh', s), s_leg * f * (1 - tw))
            add(sfx('thigh_twist_01', s), s_leg * f * tw)
        rest = 1 - s_leg
        Aw, Cw = {}, {}
        for s in (1, -1):
            xs = x * s
            t, rad = arm_param(s, p)
            a = ss(-0.15, 0.15, t) * ss(0.13, 0.07, rad) * ss(0.10, 0.16, xs)
            if xs > 0.12 and tag in (T_SHIRT, T_CUFF, T_SHIRT_OV):
                a = max(a, ss(0.10, 0.30, t) * ss(0.13, 0.08, rad))
            c = ss(0.04, 0.13, xs) * ss(1.28, 1.40, z) * (1 - a) * 0.6
            Aw[s] = (a, t)
            Cw[s] = c
        neck = 0.5 * ss(1.44, 1.52, z) * ss(0.11, 0.075, math.hypot(x, y - 0.02))
        used = sum(v[0] for v in Aw.values()) + sum(Cw.values()) + neck
        sc = 1.0 / used if used > 1 else 1.0
        for b, w in chain_weights(z).items():
            add(b, rest * max(0.0, 1 - used * sc) * w)
        add('neck_01', rest * neck * sc)
        for s in (1, -1):
            a, t = Aw[s]
            a *= sc
            w_ua = 1 - ss(0.25, 0.40, t)
            w_t2 = ss(0.50, 0.62, t)
            w_t1 = max(0.0, 1 - w_ua - w_t2)
            add(sfx('upperarm', s), rest * a * w_ua)
            add(sfx('upperarm_twist_01', s), rest * a * w_t1)
            add(sfx('upperarm_twist_02', s), rest * a * w_t2)
            add(sfx('clavicle', s), rest * Cw[s] * sc)
        return W

    FINAL = []
    for i, p in enumerate(REST_W):
        tag = TAGS[i]
        s = 1 if p.x >= 0 else -1
        other = '_r' if s > 0 else '_l'
        t_arm, rad_arm = arm_param(s, p)
        if tag == T_SHOE:
            s_body = 1.0
        elif tag in (T_SHIRT, T_CUFF, T_SHIRT_OV) and abs(p.x) > 0.15 and dist_to_chain(p, ARM_CHAIN[s]) < 0.11:
            s_body = ss(0.40, 0.50, t_arm)
        elif tag in (T_TROUS, T_TROUS_OV) and p.z < 0.80:
            s_body = ss(0.765, 0.66, p.z)
        else:
            s_body = 0.0
        W = {}
        if s_body > 0:
            clean, tot = {}, 0.0
            for b, w in DTW[i].items():
                if abs(p.x) > 0.02 and b.endswith(other):
                    continue
                if tag == T_SHOE and 'toe_' in b:
                    b = sfx('ball', s)
                clean[b] = clean.get(b, 0.0) + w
                tot += w
            if tot > 0:
                for b, w in clean.items():
                    W[b] = W.get(b, 0.0) + s_body * w / tot
            else:
                s_body = 0.0
        if s_body < 1:
            for b, w in proc_weights(p, tag).items():
                W[b] = W.get(b, 0.0) + (1 - s_body) * w
        items = sorted(W.items(), key=lambda kv: -kv[1])[:MAX_INFL]
        tot = sum(w for _, w in items)
        FINAL.append([(b, w / tot) for b, w in items if w / tot > 1e-4])
    for g in list(OUT.vertex_groups):
        OUT.vertex_groups.remove(g)
    needed = sorted({b for fw in FINAL for b, _ in fw})
    missing = [b for b in needed if b not in ARM.data.bones]
    assert not missing, missing
    VG = {b: OUT.vertex_groups.new(name=b) for b in needed}
    for i, fw in enumerate(FINAL):
        tot = sum(w for _, w in fw)
        for b, w in fw:
            VG[b].add([i], w / tot, 'REPLACE')
    with override(OUT):
        bpy.ops.object.vertex_group_normalize_all(group_select_mode='ALL', lock_active=False)
        bpy.ops.object.vertex_group_limit_total(group_select_mode='ALL', limit=MAX_INFL)
    MAXI = max(len([g for g in v.groups if g.weight > 0]) for v in me.vertices)
    WSUM = max(abs(sum(g.weight for g in v.groups) - 1.0) for v in me.vertices)
    log("weights: groups", len(needed), "max influences", MAXI, "max |sum-1|", WSUM)
    STATS['max_infl'] = MAXI
    STATS['bones_used'] = needed

    # ---------------------------------------------------------------- parent to the armature (cm data like the body)
    me.transform(ARM.matrix_world.inverted())
    OUT.parent = ARM
    OUT.matrix_parent_inverse = Matrix.Identity(4)
    OUT.matrix_basis = Matrix.Identity(4)
    am = OUT.modifiers.new("Armature", 'ARMATURE')
    am.object = ARM
    am.use_vertex_groups = True
    bpy.context.view_layer.update()
    REST_CHK = [OUT.matrix_world @ v.co for v in me.vertices]
    log("parent check (m)", max((a - b).length for a, b in zip(REST_CHK, REST_W)))

    # ---------------------------------------------------------------- pose tools
    def reset_pose(arm=None):
        arm = arm or ARM
        for pb in arm.pose.bones:
            pb.matrix_basis = Matrix.Identity(4)
        bpy.context.view_layer.update()

    def rot_world(arm, bn, axis, deg):
        pb = arm.pose.bones[bn]
        bpy.context.view_layer.update()
        M = pb.matrix.copy()
        h = M.to_translation()
        R = Matrix.Rotation(math.radians(deg), 4, axis)
        pb.matrix = Matrix.Translation(h) @ R @ Matrix.Translation(-h) @ M
        bpy.context.view_layer.update()

    def aim(arm, bn, child, target):
        pb = arm.pose.bones[bn]
        bpy.context.view_layer.update()
        h = pb.head.copy()
        c = arm.pose.bones[child].head.copy()
        q = (c - h).normalized().rotation_difference(Vector(target).normalized())
        pb.matrix = Matrix.Translation(h) @ q.to_matrix().to_4x4() @ Matrix.Translation(-h) @ pb.matrix
        bpy.context.view_layer.update()

    def seated_pose(arm=None):
        """Seated on a chair, forearms resting forward on a table."""
        arm = arm or ARM
        reset_pose(arm)
        rot_world(arm, 'spine_01', 'X', 6)
        rot_world(arm, 'spine_03', 'X', 4)
        for s in (1, -1):
            rot_world(arm, sfx('thigh', s), 'X', -86)
            rot_world(arm, sfx('calf', s), 'X', 86)
            aim(arm, sfx('upperarm', s), sfx('lowerarm', s), (0.16 * s, -0.46, -0.87))
            aim(arm, sfx('lowerarm', s), sfx('hand', s), (-0.22 * s, -0.97, -0.06))

    # ---------------------------------------------------------------- checks
    OUT_P = [tuple(p.vertices) for p in me.polygons]

    def polys_where(fn):
        return [OUT_P[k] for k in range(len(OUT_P)) if fn(k)]

    def vtag(k):
        return TAGS[OUT_P[k][0]]

    BODY_REST = [BODY.matrix_world @ v.co for v in BODY.data.vertices]
    FOREARM = {}
    for s in (1, -1):
        S_, E_, Hd_ = arm_axes(s)
        FOREARM[s] = (E_, (Hd_ - E_).normalized(), (Hd_ - E_).length)
    COVER = {'legs': [], 'arms_sleeve': [], 'arms_cuff': [], 'feet': []}
    for i, p in enumerate(BODY_REST):
        s = 1 if p.x >= 0 else -1
        t, rad = arm_param(s, p)
        E_, df, Lf = FOREARM[s]
        f = (p - E_).dot(df) / Lf
        if abs(p.x) > 0.15 and p.z > 0.95:
            if 0.47 <= t and f <= 0.17:
                COVER['arms_sleeve'].append(i)
            elif 0.15 <= f <= 0.34:
                COVER['arms_cuff'].append(i)
        elif 0.12 <= p.z <= 0.765 and abs(p.x) < 0.3:
            COVER['legs'].append(i)
        elif p.z < 0.10 and abs(p.x) < 0.3:
            COVER['feet'].append(i)
    # garment surface each body region must stay under (overlay slabs and hem/opening facings excluded)
    SLEEVE_V = []
    for i, p in enumerate(REST_W):
        s = 1 if p.x >= 0 else -1
        t, rad = arm_param(s, p)
        SLEEVE_V.append(TAGS[i] == T_SHIRT and abs(p.x) > 0.15 and t > 0.2 and dist_to_chain(p, ARM_CHAIN[s]) < 0.12)

    def is_sleeve(k):
        return all(SLEEVE_V[j] for j in OUT_P[k])
    COVER_POLYS = {
        'legs': lambda k: vtag(k) == T_TROUS and not INNER_F[k],
        'arms_sleeve': lambda k: is_sleeve(k) and not INNER_F[k],
        'arms_cuff': lambda k: (vtag(k) == T_CUFF or is_sleeve(k)) and not INNER_F[k],
        'feet': lambda k: vtag(k) == T_SHOE and not INNER_F[k] and not SOLID_F[k]}
    COVER_CHAIN = {'legs': ('thigh', 'calf', 'foot'), 'arms_sleeve': ('upperarm', 'lowerarm', 'hand'),
                   'arms_cuff': ('upperarm', 'lowerarm', 'hand'), 'feet': ('foot', 'ball')}
    WORST = {}
    PARITY_POLYS = {'legs': lambda k: vtag(k) == T_TROUS, 'arms_sleeve': lambda k: vtag(k) == T_SHIRT,
                    'arms_cuff': lambda k: vtag(k) in (T_SHIRT, T_CUFF), 'feet': lambda k: vtag(k) == T_SHOE}
    PDIRS = [Vector(d).normalized() for d in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (1, 1, 0.2),
                                               (-1, 1, 0.2), (1, -1, 0.2), (-1, -1, 0.2), (0.3, 0.2, 1))]

    def enclosed(bvh, p):
        """Generalised winding number along several rays (outward normals): > 0 means the point is inside
        the garment volume, also where folds make the deformed garment overlap itself."""
        votes = 0
        for d in PDIRS:
            o, w = p.copy(), 0
            for _ in range(60):
                loc, n, fi, hd = bvh.ray_cast(o, d, 3.0)
                if loc is None:
                    break
                w += 1 if n.dot(d) > 0 else -1
                o = loc + d * 1e-5
            votes += 1 if w > 0 else 0
        return votes * 2 > len(PDIRS)

    def check(state):
        """Radial test: ray from the (posed) bone axis through each covered skin vertex; the first garment
        hit must lie beyond the vertex. clearance = hit distance - skin distance (negative = poke-through)."""
        bpy.context.view_layer.update()
        BV, _ = evaluated_world(BODY)
        OV, _ = evaluated_world(OUT)
        PH = {pb.name: ARM.matrix_world @ pb.head for pb in ARM.pose.bones}
        res = {}
        for key, idxs in COVER.items():
            bvh = BVHTree.FromPolygons(OV, polys_where(COVER_POLYS[key]))
            pbvh = BVHTree.FromPolygons(OV, polys_where(PARITY_POLYS[key]))
            pokes = close = miss = hidden = 0
            mind = 1e9
            worst = []
            low = []
            for i in idxs:
                b = BV[i]
                s = 1 if BODY_REST[i].x >= 0 else -1
                ch = [PH[sfx(n, s)] for n in COVER_CHAIN[key]]
                best = None
                for a0, a1 in zip(ch, ch[1:]):
                    c = seg_closest(b, a0, a1)
                    if best is None or (b - c).length < (b - best).length:
                        best = c
                dvec = b - best
                L = dvec.length
                if L < 1e-4:
                    continue
                loc, n, fi, hd = bvh.ray_cast(best, dvec / L, L + 0.25)
                if loc is None:
                    miss += 1
                    continue
                clr = hd - L
                low.append((round(clr * 100, 2), tuple(round(c, 3) for c in BODY_REST[i])))
                mind = min(mind, clr)
                if clr <= 0:
                    if enclosed(pbvh, b):
                        hidden += 1  # crosses a fold of the same garment but stays inside its volume
                        continue
                    pokes += 1
                    worst.append((round(clr * 100, 2), tuple(round(c, 3) for c in BODY_REST[i]),
                                  'posed', tuple(round(c, 3) for c in b)))
                elif clr < 0.006:
                    close += 1
            WORST[(state, key)] = sorted(worst)[:4] if worst else sorted(low)[:3]
            if state == "rest" and key != 'arms_cuff':  # cuff zone: skin sits in the ring's hole by design
                ne = sum(1 for i in idxs[::7] if not enclosed(pbvh, BV[i]))
                log("  sanity: rest skin verts not enclosed by winding test (1/7 sample)", key, ne, "/", len(idxs[::7]))
            res['body_' + key] = dict(n=len(idxs), visible_pokes=pokes, enclosed_fold_crossings=hidden,
                                      under_6mm=close, uncovered=miss, min_clear_cm=round(mind * 100, 3))

        TROUS_ALL = BVHTree.FromPolygons(OV, polys_where(lambda k: vtag(k) == T_TROUS))

        def gg(src, dst_fn, chain, want_inside):
            """want_inside: src vertex must be inside dst (first dst hit beyond it along the axis ray);
            otherwise src must be outside dst (dst hit before reaching the vertex)."""
            bvh = BVHTree.FromPolygons(OV, polys_where(dst_fn))
            bad = n_ = nohit = 0
            mind = 1e9
            for i in range(len(OV)):
                if not src(i):
                    continue
                s = 1 if REST_W[i].x >= 0 else -1
                ch = [PH[sfx(n, s) if n in ('calf', 'foot', 'ball', 'thigh') else n] for n in chain]
                b = OV[i]
                best = None
                for a0, a1 in zip(ch, ch[1:]):
                    c = seg_closest(b, a0, a1)
                    if best is None or (b - c).length < (b - best).length:
                        best = c
                dvec = b - best
                L = dvec.length
                loc, nn, fi, hd = bvh.ray_cast(best, dvec / L, L + 0.15)
                n_ += 1
                if loc is None:
                    if want_inside and enclosed(TROUS_ALL, b):
                        continue
                    nohit += 1
                    NOHIT.append(tuple(round(c, 3) for c in REST_W[i]))
                    if want_inside:
                        bad += 1
                    continue
                m = hd - L if want_inside else L - hd
                if m <= 0 and want_inside and enclosed(TROUS_ALL, b):
                    continue  # ray crossed a trouser fold, but the vertex is still inside the trousers
                mind = min(mind, m)
                if m <= 0:
                    bad += 1
                    NOHIT.append(('bad', round(m * 100, 2), tuple(round(c, 3) for c in REST_W[i]), 'posed',
                                  tuple(round(c, 3) for c in b)))
            return dict(n=n_, bad=bad, nohit=nohit, min_cm=round(mind * 100, 3))
        TORSO_CH = ('pelvis', 'spine_01', 'spine_02', 'spine_03')
        NOHIT = []
        res['shirt_tucked_in_trousers'] = gg(lambda i: TAGS[i] == T_SHIRT and REST_W[i].z < 0.99,
                                             lambda k: vtag(k) == T_TROUS and not INNER_F[k] and
                                             REST_W[OUT_P[k][0]].z > 0.80, TORSO_CH, True)
        res['belt_over_trousers'] = gg(lambda i: TAGS[i] == T_BELT and abs(REST_W[i].z - 1.015) < 0.02,
                                       lambda k: vtag(k) == T_TROUS and not INNER_F[k], TORSO_CH, False)
        res['trouser_hem_over_shoes'] = gg(lambda i: TAGS[i] == T_TROUS and REST_W[i].z < 0.11,
                                           lambda k: vtag(k) == T_SHOE and not INNER_F[k] and not SOLID_F[k],
                                           ('calf', 'foot', 'ball'), False)
        for k, v in res.items():
            log("CHECK %-7s %-26s" % (state, k), v)
        if NOHIT:
            log("  nohit", state, NOHIT[:8])
        for k, v in WORST.items():
            if k[0] == state and v:
                log("  worst", k, v)
        return res

    STATS['check_rest'] = check("rest")
    seated_pose()
    STATS['check_seated'] = check("seated")
    OVs, _ = evaluated_world(OUT)
    ratios = []
    for p in OUT_P:
        for k in range(3):
            a, b = p[k], p[(k + 1) % 3]
            l0 = (REST_W[a] - REST_W[b]).length
            if l0 > 0.005:
                ratios.append(((OVs[a] - OVs[b]).length / l0, TAGS[a], tuple(round(c, 3) for c in REST_W[a])))
    ratios.sort(key=lambda r: r[0])
    n = len(ratios)
    STATS['stretch'] = {"min": round(ratios[0][0], 3), "p01": round(ratios[n // 100][0], 3),
                        "p99": round(ratios[-n // 100][0], 3), "max": round(ratios[-1][0], 3),
                        "worst": ratios[-3:], "most_compressed": ratios[:3]}
    log("seated edge ratio", STATS['stretch'])
    reset_pose()

    # ---------------------------------------------------------------- previews
    PREVIEWS = []

    def make_plaid():
        img = bpy.data.images.new("plaid_check", 128, 128)
        px = []
        for yy in range(128):
            for xx in range(128):
                a = 1.0 if (xx // 16) % 4 == 0 else (0.55 if (xx // 16) % 4 == 2 else 0.0)
                b = 1.0 if (yy // 16) % 4 == 0 else (0.55 if (yy // 16) % 4 == 2 else 0.0)
                d = max(a, b) * 0.6 + min(a, b) * 0.4
                px += [lerp(0.55, 0.06, d), lerp(0.08, 0.05, d), lerp(0.06, 0.04, d), 1.0]
        img.pixels = px
        return img

    def setup_preview():
        sc = bpy.context.scene
        sc.render.engine = 'BLENDER_WORKBENCH'
        sh = sc.display.shading
        sh.light = 'STUDIO'
        sh.color_type = 'MATERIAL'
        sh.show_cavity = True
        sh.cavity_type = 'BOTH'
        sh.show_backface_culling = False
        sh.show_specular_highlight = True
        sc.view_settings.view_transform = 'Standard'
        w = bpy.data.worlds.new("Preview")
        w.color = (0.60, 0.62, 0.65)
        sc.world = w
        for m in BODY.data.materials:
            if m:
                m.diffuse_color = (0.62, 0.45, 0.36, 1)

    def shoot(name, target, dist, az, el, lens=55, res=(900, 1200)):
        sc = bpy.context.scene
        sc.render.resolution_x, sc.render.resolution_y = res
        cd = bpy.data.cameras.new(name)
        cd.lens = lens
        cd.clip_start = 0.05
        cam = bpy.data.objects.new(name, cd)
        sc.collection.objects.link(cam)
        t = Vector(target)
        a, e = math.radians(az), math.radians(el)
        loc = t + Vector((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e))) * dist
        cam.location = loc
        cam.rotation_euler = (t - loc).to_track_quat('-Z', 'Y').to_euler()
        sc.camera = cam
        path = os.path.join(PREV, name + ".png")
        sc.render.filepath = path
        bpy.ops.render.render(write_still=True)
        bpy.data.objects.remove(cam, do_unlink=True)
        PREVIEWS.append(path)

    if DO_RENDER:
        for f in os.listdir(PREV):
            if f.endswith('.png'):
                os.remove(os.path.join(PREV, f))
        setup_preview()
        reset_pose()
        shoot("01_front", (0, 0, 0.86), 3.2, 0, 4)
        shoot("02_three_quarter", (0, 0, 0.86), 3.2, 38, 8)
        shoot("03_back", (0, 0, 0.86), 3.2, 180, 6)
        shoot("04_side", (0, 0, 0.86), 3.2, 90, 4)
        shoot("05_closeup_collar_pocket", (0.03, -0.05, 1.33), 0.9, 22, 8, res=(1000, 900))
        shoot("06_closeup_belt_waist", (0.0, -0.05, 0.97), 0.95, 28, 8, res=(1000, 800))
        shoot("07_closeup_shoes", (0.0, -0.06, 0.08), 1.0, 35, 18, res=(1000, 700))
        shoot("07b_closeup_hem_side", (0.12, -0.04, 0.11), 0.55, 75, 4, res=(1000, 800))
        shoot("08_closeup_rolled_sleeve", (0.36, -0.02, 1.15), 0.8, 60, 8, res=(900, 900))
        shoot("09_closeup_back_pockets", (0.0, 0.05, 0.93), 0.95, 180, 8, res=(1000, 800))
        seated_pose()
        shoot("10_seated_three_quarter", (0, -0.25, 0.85), 3.0, 40, 10)
        shoot("11_seated_side", (0, -0.25, 0.85), 3.0, 90, 4)
        shoot("12_seated_front", (0, -0.25, 0.85), 3.0, 0, 12)
        shoot("13_seated_back_low", (0, -0.2, 0.80), 3.0, 205, -5)
        shoot("14_seated_closeup_hips_knees", (0.1, -0.3, 0.85), 1.35, 60, 25, res=(1000, 900))
        shoot("15_seated_closeup_shoulders_arms", (0.0, -0.25, 1.25), 1.4, 30, 20, res=(1000, 900))
        shoot("17_seated_closeup_front_crease", (0.0, -0.12, 0.95), 0.9, 12, -12, res=(1000, 900))
        shoot("18_seated_underside_thigh_knee", (0.11, -0.33, 0.86), 1.0, 90, -50, res=(1000, 900))
        shoot("19_seated_closeup_back_shoulder", (0.12, 0.05, 1.25), 0.85, 155, 15, res=(1000, 900))
        # UV check: tiling plaid on the shirt
        reset_pose()
        img = make_plaid()
        mshirt = me.materials[M_SHIRT]
        mshirt.use_nodes = True
        nt = mshirt.node_tree
        tex = nt.nodes.new('ShaderNodeTexImage')
        tex.image = img
        nt.nodes.active = tex
        bpy.context.scene.display.shading.color_type = 'TEXTURE'
        shoot("16_uv_check_plaid", (0, 0, 1.15), 2.0, 25, 6, res=(900, 900))
        bpy.context.scene.display.shading.color_type = 'MATERIAL'
        nt.nodes.remove(tex)
        bpy.data.images.remove(img)
        reset_pose()

    # ---------------------------------------------------------------- export
    reset_pose()
    ARM.data.pose_position = 'REST'
    bpy.context.view_layer.update()
    for an in ('tag', 'inner', 'solid', 'Col'):
        if me.attributes.get(an):
            me.attributes.remove(me.attributes[an])
    REF = [OUT.matrix_world @ v.co for v in me.vertices]
    ARM.data.pose_position = 'POSE'
    seated_pose()
    REF_POSED, _ = evaluated_world(OUT)
    reset_pose()
    ARM.data.pose_position = 'REST'
    bpy.context.view_layer.update()
    STATS['slots_build'] = [m.name for m in me.materials]
    if DO_EXPORT:
        for o in bpy.context.selected_objects:
            o.select_set(False)
        ARM.select_set(True)
        OUT.select_set(True)
        bpy.context.view_layer.objects.active = ARM
        bpy.ops.export_scene.fbx(
            filepath=OUT_FBX, use_selection=True, object_types={'ARMATURE', 'MESH'},
            add_leaf_bones=False, primary_bone_axis='Y', secondary_bone_axis='X',
            armature_nodetype='NULL', bake_anim=False, use_armature_deform_only=False,
            apply_scale_options='FBX_SCALE_NONE', global_scale=1.0, apply_unit_scale=True,
            axis_forward='Y', axis_up='Z', mesh_smooth_type='FACE', use_mesh_modifiers=False,
            use_tspace=False, embed_textures=False, path_mode='STRIP')
        log("exported", OUT_FBX)

        # ------------------------------------------------------------ round-trip verification
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.fbx(filepath=BODY_FBX)
        body_objs = set(bpy.data.objects)
        bpy.ops.import_scene.fbx(filepath=OUT_FBX)
        new = [o for o in bpy.data.objects if o not in body_objs]
        b_arm = next(o for o in body_objs if o.type == 'ARMATURE')
        b_mesh = next(o for o in body_objs if o.type == 'MESH')
        g_arm = next(o for o in new if o.type == 'ARMATURE')
        g_mesh = [o for o in new if o.type == 'MESH']
        log("reimported:", [(o.name, o.type) for o in new])
        assert len(g_mesh) == 1, g_mesh
        g_mesh = g_mesh[0]
        bpy.context.view_layer.update()
        nb, ng = [b.name for b in b_arm.data.bones], [b.name for b in g_arm.data.bones]

        def pname(arm, n):
            b = arm.data.bones[n]
            return b.parent.name if b.parent else None
        hier_ok = sorted(nb) == sorted(ng) and all(pname(b_arm, n) == pname(g_arm, n) for n in nb)
        bone_off = max(((b_arm.matrix_world @ b_arm.data.bones[n].head_local) -
                        (g_arm.matrix_world @ g_arm.data.bones[n].head_local)).length for n in nb)
        GV = [g_mesh.matrix_world @ v.co for v in g_mesh.data.vertices]
        if len(GV) == len(REF):
            v_off = max((a - b).length for a, b in zip(GV, REF))
        else:
            kd = KDTree(len(GV))
            for i, p in enumerate(GV):
                kd.insert(p, i)
            kd.balance()
            v_off = max(kd.find(p)[2] for p in REF)
        BV2 = [b_mesh.matrix_world @ v.co for v in b_mesh.data.vertices]
        body_off = max((a - b).length for a, b in zip(BV2, BODY_REST))
        infl = max(len([g for g in v.groups if g.weight > 1e-6]) for v in g_mesh.data.vertices)
        tris = sum(len(p.vertices) - 2 for p in g_mesh.data.polygons)
        slots = [m.name if m else None for m in g_mesh.data.materials]
        seated_pose(g_arm)
        GVp, _ = evaluated_world(g_mesh)
        posed_off = max((a - b).length for a, b in zip(GVp, REF_POSED)) if len(GVp) == len(REF_POSED) else -1
        reset_pose(g_arm)
        STATS.update(dict(tris=tris, max_infl_reimport=infl, roundtrip_cm=v_off * 100, bone_cm=bone_off * 100,
                          body_ref_cm=body_off * 100, posed_cm=posed_off * 100, slots=slots, mesh=g_mesh.name,
                          armature=g_arm.name, bones=len(ng), hierarchy_identical=hier_ok,
                          uv_layers=[u.name for u in g_mesh.data.uv_layers]))
    STATS['previews'] = PREVIEWS
    STATS['tris_build'] = TRIS
    print("RESULT_JSON " + json.dumps(STATS, default=str), flush=True)
    log("done in %.1fs" % (time.time() - T0))
