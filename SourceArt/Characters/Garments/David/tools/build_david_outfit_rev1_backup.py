# build_david_outfit.py
# Headless Blender 5.0 build of David's placeholder uniform (support worker, aged care):
#   navy polo (2-button placket, ribbed collar + cuffs, name badge), charcoal straight-leg
#   trousers with belt loops, black belt, black non-slip work shoes.
# Skinned to the MetaHuman body skeleton (metahuman_base_skel) from the exported body FBX.
#
# Run:
#   "C:\Program Files\Blender Foundation\Blender 5.0\blender.exe" -b --factory-startup --python build_david_outfit.py
# Optional args after "--":  norender  noexport
#
# NOTE: the input body is a UE-Optimized MetaHuman body: faces hidden by the default
# T-shirt/shorts were removed (no torso, upper arms or upper thighs; only forearms, legs
# from mid-thigh, hands, feet). The torso shape is therefore a parametric proxy built from
# the skeleton + the remaining stumps, and the skin weights for the missing region are a
# procedural (position-based) field; everywhere the body exists, weights are copied from the
# body with a Data Transfer modifier (nearest face interpolated).

import bpy, bmesh, math, os, sys, time
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
DO_RENDER = 'norender' not in ARGS
DO_EXPORT = 'noexport' not in ARGS
ONLY = [x for a in ARGS if a.startswith('only=') for x in a[5:].split(',')]

NAME = "David"
ROOT = r"D:\Unreal-Projects\WattleviewGrove-ue58\SourceArt\Characters"
BODY_FBX = os.path.join(ROOT, "Bodies", "SKM_%s_BodyMesh.fbx" % NAME)
OUT = os.path.join(ROOT, "Garments", NAME)
PREV = os.path.join(OUT, "Previews")
FBX_OUT = os.path.join(OUT, "SKM_%s_Outfit.fbx" % NAME)
OUTFIT = "SKM_%s_Outfit" % NAME
SLOTS = ["M_PoloShirt", "M_Trousers", "M_Belt", "M_Shoes", "M_Badge"]
M_SHIRT, M_TROUSERS, M_BELT, M_SHOES, M_BADGE = range(5)
PREVIEW_COLORS = {  # linear RGB for Workbench previews (lifted slightly so detail reads)
    "M_PoloShirt": (0.045, 0.075, 0.20), "M_Trousers": (0.12, 0.12, 0.13),
    "M_Belt": (0.018, 0.018, 0.018), "M_Shoes": (0.03, 0.03, 0.032), "M_Badge": (0.85, 0.85, 0.80)}
UVS = 2.0           # UV units per metre -> one texture tile = 50 cm
MAX_INFL = 4

# vertex tags (stored in an int attribute while building)
T_SHIRT, T_SLV_L, T_SLV_R, T_COLLAR, T_PLACKET, T_BADGE, T_SHIRT_IN = 1, 2, 3, 4, 5, 6, 7
T_TR_PEL, T_TR_LEG_L, T_TR_LEG_R, T_TR_DET, T_TR_IN = 10, 11, 12, 13, 14
T_BELT, T_BUCKLE = 20, 21
T_SHOE_L, T_SHOE_R, T_SHOE_IN, T_LACE = 30, 31, 32, 34

os.makedirs(PREV, exist_ok=True)
T0 = time.time()


def log(*a):
    print("[DAVID %6.1fs]" % (time.time() - T0), *a, flush=True)


def lerp(a, b, t): return a + (b - a) * t
def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))


def smoothstep(e0, e1, x):
    if e0 == e1:
        return 1.0 if x >= e1 else 0.0
    t = clamp((x - e0) / (e1 - e0))
    return t * t * (3 - 2 * t)


def wrap_pi(a):
    while a > math.pi: a -= 2 * math.pi
    while a < -math.pi: a += 2 * math.pi
    return a


# ----------------------------------------------------------------------------- scene
def setup_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=BODY_FBX)
    arm = [o for o in bpy.data.objects if o.type == 'ARMATURE'][0]
    body = [o for o in bpy.data.objects if o.type == 'MESH'][0]
    emp = arm.parent
    mw = arm.matrix_world.copy()
    arm.parent = None
    arm.matrix_world = mw          # armature keeps the 0.01 (cm->m) scale; bone data stays cm
    if emp is not None:
        bpy.data.objects.remove(emp, do_unlink=True)
    body.name = "SKM_%s_BodyMesh" % NAME
    bpy.context.view_layer.update()
    return arm, body


def mesh_world(obj, evaluated=True):
    dg = bpy.context.evaluated_depsgraph_get()
    ob = obj.evaluated_get(dg) if evaluated else obj
    me = ob.to_mesh()
    M = obj.matrix_world.copy()
    V = [M @ v.co for v in me.vertices]
    P = [tuple(p.vertices) for p in me.polygons]
    ob.to_mesh_clear()
    return V, P


def bone_head(arm, n): return arm.matrix_world @ arm.data.bones[n].head_local


# ----------------------------------------------------------------------------- part builder
class Part:
    def __init__(self, name, mat):
        self.name = name
        self.mat = mat
        self.bm = bmesh.new()
        self.uv = self.bm.loops.layers.uv.new("UVMap")
        self.tag = self.bm.verts.layers.int.new("tag")

    def vert(self, co, tag):
        if isinstance(co, bmesh.types.BMVert):
            return co
        v = self.bm.verts.new(co)
        v[self.tag] = tag
        return v

    def face(self, verts, uvs=None, mat=None):
        try:
            f = self.bm.faces.new(verts)
        except ValueError:
            return None
        f.material_index = self.mat if mat is None else mat
        f.smooth = True
        if uvs:
            for l, uv in zip(f.loops, uvs):
                l[self.uv].uv = uv
        return f

    def grid(self, rows, tag, cyclic=True, flip=False, mat=None, uv_offset=(0.0, 0.0)):
        V = [[self.vert(p, tag) for p in row] for row in rows]
        P = [[v.co.copy() for v in row] for row in V]
        R, C = len(V), len(V[0])
        # arc-length UVs
        U = []
        for i in range(R):
            acc = [0.0]
            for j in range(1, C + (1 if cyclic else 0)):
                acc.append(acc[-1] + (P[i][j % C] - P[i][j - 1]).length)
            U.append(acc)
        Vv = [[0.0] * (C + 1) for _ in range(R)]
        for j in range(C + 1):
            jj = j % C
            for i in range(1, R):
                Vv[i][j] = Vv[i - 1][j] + (P[i][jj] - P[i - 1][jj]).length
        if not cyclic:
            for i in range(R):
                U[i].append(U[i][-1])

        def uv(i, j):
            return (U[i][j] * UVS + uv_offset[0], Vv[i][j] * UVS + uv_offset[1])
        ncol = C if cyclic else C - 1
        faces = []
        for i in range(R - 1):
            for j in range(ncol):
                j2 = (j + 1) % C
                q = [V[i][j], V[i][j2], V[i + 1][j2], V[i + 1][j]]
                u = [uv(i, j), uv(i, j + 1), uv(i + 1, j + 1), uv(i + 1, j)]
                if flip:
                    q.reverse(); u.reverse()
                if len(set(q)) < 4:
                    q2 = []; u2 = []
                    for vv, uu in zip(q, u):
                        if vv not in q2:
                            q2.append(vv); u2.append(uu)
                    if len(q2) < 3:
                        continue
                    q, u = q2, u2
                f = self.face(q, u, mat)
                if f: faces.append(f)
        return V, faces

    def to_object(self):
        me = bpy.data.meshes.new(self.name)
        self.bm.to_mesh(me)
        ob = bpy.data.objects.new(self.name, me)
        bpy.context.scene.collection.objects.link(ob)
        return ob


def orient_faces(faces, outward_fn):
    """flip faces whose normal points against outward_fn(face_center)."""
    for f in faces:
        if not f.is_valid: continue
        f.normal_update()
        if f.normal.dot(outward_fn(f.calc_center_median())) < 0:
            f.normal_flip()


def bvh_from_rows(rows, cyclic=True):
    V = []; idx = []
    for row in rows:
        idx.append([])
        for p in row:
            idx[-1].append(len(V)); V.append(p.co.copy() if isinstance(p, bmesh.types.BMVert) else p.copy())
    P = []
    C = len(rows[0])
    for i in range(len(rows) - 1):
        for j in range(C if cyclic else C - 1):
            j2 = (j + 1) % C
            P.append((idx[i][j], idx[i][j2], idx[i + 1][j2], idx[i + 1][j]))
    return BVHTree.FromPolygons(V, P)


def bvh_from_faces(faces):
    vmap = {}; V = []; P = []
    for f in faces:
        if not f.is_valid: continue
        t = []
        for v in f.verts:
            if v not in vmap:
                vmap[v] = len(V); V.append(v.co.copy())
            t.append(vmap[v])
        P.append(tuple(t))
    return BVHTree.FromPolygons(V, P)


def push_out(p, bvh, min_d, max_search=0.08):
    """move p so that it is at least min_d outside the surface (signed by face normal)."""
    loc, n, i, d = bvh.find_nearest(p, max_search)
    if loc is None:
        return p, None
    sd = (p - loc).dot(n)
    if sd < min_d:
        return p + n * (min_d - sd), sd
    return p, sd


# ============================================================================= main build
arm, body = setup_scene()
B = {n: bone_head(arm, n) for n in [b.name for b in arm.data.bones]}
BV, BP = mesh_world(body)
BODY_BVH = BVHTree.FromPolygons(BV, BP)
side_polys = {'l': [], 'r': []}
for p in BP:
    cx = sum(BV[i].x for i in p) / len(p)
    side_polys['l' if cx > 0 else 'r'].append(p)
BODY_SIDE = {s: BVHTree.FromPolygons(BV, side_polys[s]) for s in 'lr'}
BEDGES = set()
for p in BP:
    for k in range(len(p)):
        a, b = p[k], p[(k + 1) % len(p)]
        BEDGES.add((min(a, b), max(a, b)))
BEDGES = list(BEDGES)
log("body verts", len(BV), "tris", len(BP))


def slice_pts(co, no, filt):
    out = []
    for a, b in BEDGES:
        pa, pb = BV[a], BV[b]
        da = (pa - co).dot(no); db = (pb - co).dot(no)
        if da * db < 0:
            p = pa + (pb - pa) * (da / (da - db))
            if filt(p): out.append(p)
    return out


# ----------------------------------------------------------------------------- arm frames
ARM = {}
for sd, sg in (('l', 1), ('r', -1)):
    S = B['upperarm_' + sd]; E = B['lowerarm_' + sd]
    ax = (E - S).normalized(); L = (E - S).length
    up = Vector((0, 0, 1))
    u = (up - ax * up.dot(ax)).normalized()          # top of arm
    v = ax.cross(u).normalized()
    if v.y > 0: v = -v                                # v -> front (-Y)
    offs = []
    for f in (0.52, 0.58, 0.64):
        co = S + ax * L * f
        pts = slice_pts(co, ax, lambda p: p.x * sg > 0 and (p - co).length < 0.12)
        if pts:
            c = sum(pts, Vector()) / len(pts)
            offs.append(c - co)
    off = sum(offs, Vector()) / len(offs)
    off -= ax * off.dot(ax)
    ARM[sd] = dict(S=S, E=E, ax=ax, L=L, u=u, v=v, off=off, sg=sg)
    log("arm", sd, "L %.3f" % L, "centroid offset", [round(x, 4) for x in off])

# ----------------------------------------------------------------------------- proxy torso
Z_S = 1.405                         # top of the "vertical" torso; above it the shoulder dome
TORSO_KEYS = [  # z, half-width, front y, back y, superellipse exponent
    (0.78, 0.178, -0.100, 0.100, 2.4),
    (0.83, 0.183, -0.106, 0.112, 2.5),
    (0.87, 0.187, -0.110, 0.122, 2.5),
    (0.93, 0.182, -0.114, 0.115, 2.5),
    (1.00, 0.166, -0.117, 0.093, 2.4),
    (1.07, 0.156, -0.119, 0.079, 2.4),
    (1.15, 0.160, -0.121, 0.086, 2.4),
    (1.23, 0.170, -0.126, 0.099, 2.5),
    (1.30, 0.176, -0.123, 0.108, 2.6),
    (1.36, 0.180, -0.104, 0.110, 2.6),
    (1.405, 0.178, -0.080, 0.102, 2.5),
]
NECK_C = (0.0, 0.006)
NECK_R = (0.069, 0.068)


def interp_keys(keys, z):
    zs = [k[0] for k in keys]
    if z <= zs[0]:
        return list(keys[0][1:])
    if z >= zs[-1]:
        return list(keys[-1][1:])
    i = max(j for j in range(len(zs) - 1) if zs[j] <= z)
    z0, z1 = zs[i], zs[i + 1]
    t = (z - z0) / (z1 - z0)
    im, ip = max(i - 1, 0), min(i + 2, len(keys) - 1)
    out = []
    for c in range(1, len(keys[0])):
        p0, p1, p2, p3 = keys[im][c], keys[i][c], keys[i + 1][c], keys[ip][c]
        m1 = (p2 - p0) / (zs[i + 1] - zs[im]) * (z1 - z0)
        m2 = (p3 - p1) / (zs[ip] - zs[i]) * (z1 - z0)
        h00 = 2 * t ** 3 - 3 * t ** 2 + 1; h10 = t ** 3 - 2 * t ** 2 + t
        h01 = -2 * t ** 3 + 3 * t ** 2; h11 = t ** 3 - t ** 2
        out.append(h00 * p1 + h10 * m1 + h01 * p2 + h11 * m2)
    return out


def superellipse(th, a, yf, yb, n):
    c, s = math.cos(th), math.sin(th)
    x = a * math.copysign(abs(c) ** (2.0 / n), c)
    ys = math.copysign(abs(s) ** (2.0 / n), s)
    y = ys * (yb if s > 0 else -yf)
    return x, y


def neckline(th):
    s = math.sin(th)
    x = NECK_C[0] + NECK_R[0] * math.cos(th)
    y = NECK_C[1] + NECK_R[1] * s
    z = 1.479 + 0.007 * max(0.0, s) - 0.031 * max(0.0, -s) ** 2
    return Vector((x, y, z))


def bezier(p0, p1, p2, p3, t):
    a = 1 - t
    return p0 * a ** 3 + p1 * (3 * a * a * t) + p2 * (3 * a * t * t) + p3 * t ** 3


def torso_point(u, th):
    if u <= Z_S:
        a, yf, yb, n = interp_keys(TORSO_KEYS, u)
        x, y = superellipse(th, a, yf, yb, n)
        return Vector((x, y, u))
    t = u - Z_S
    P0 = torso_point(Z_S, th)
    d = (P0 - torso_point(Z_S - 0.01, th)).normalized()
    side = abs(math.cos(th)) ** 1.5
    P1 = P0 + d * (0.018 + 0.030 * side)
    N = neckline(th)
    radial = Vector((N.x - NECK_C[0], N.y - NECK_C[1], 0)).normalized()
    P2 = N + radial * (0.006 + 0.075 * side) + Vector((0, 0, -(0.022 - 0.012 * side)))
    return bezier(P0, P1, P2, N, t) + shoulder_bump(t, th)


SH_BUMP_X, SH_BUMP_Z = 0.037, 0.016


def shoulder_bump(t, th):
    # deltoid / shoulder-point fill: the proxy dome alone sits ~4 cm under the sleeve cap
    c = math.cos(th)
    side = abs(c) ** 2.2
    g = smoothstep(0.02, 0.36, t) * (1 - smoothstep(0.50, 0.86, t))
    return Vector((math.copysign(SH_BUMP_X, c) * side * g, 0.0, SH_BUMP_Z * side * g))


def surf_normal(fn, u, th, du=0.002, dth=0.01):
    pu = fn(u + du, th) - fn(u - du, th)
    pt = fn(u, th + dth) - fn(u, th - dth)
    n = pt.cross(pu)
    if n.length < 1e-12:
        return Vector((0, 0, 1))
    return n.normalized()


def z_top(th):          # trouser waistband top line (front lower)
    return 1.003 + 0.010 * math.sin(th)


# --- garment offsets from the proxy (metres)
def shirt_off(u, th):
    s = math.sin(th)
    dzw = u - z_top(th)
    base = 0.012
    if u > Z_S:
        base = lerp(0.010, 0.005, smoothstep(0.0, 0.7, u - Z_S))
    front, back = max(0.0, -s), max(0.0, s)
    base += 0.004 * front * smoothstep(1.03, 1.10, u) * (1 - smoothstep(1.22, 1.32, u))
    base += 0.003 * back * smoothstep(1.02, 1.08, u) * (1 - smoothstep(1.20, 1.30, u))
    tuck = 1 - smoothstep(0.0, 0.012, dzw)
    blouse = smoothstep(0.0, 0.03, dzw) * (1 - smoothstep(0.05, 0.13, dzw))
    off = lerp(base, 0.0045, tuck) + 0.010 * blouse
    off += 0.0035 * blouse * math.sin(9 * th + 0.6) * smoothstep(0.012, 0.03, dzw)
    # side seam / shoulder seam groove
    for ths in (0.0, math.pi):
        dd = abs(wrap_pi(th - ths))
        off -= 0.0012 * max(0.0, 1 - dd / 0.12)
    return off


def trouser_off(u, th):
    s = math.sin(th)
    dzw = u - z_top(th)
    base = 0.016 + 0.005 * max(0.0, -s) * smoothstep(0.88, 0.83, u)
    off = lerp(base, 0.0145, smoothstep(-0.10, -0.045, dzw))
    off += 0.0012 * smoothstep(-0.0395, -0.0375, dzw)     # waistband step
    for ths in (0.0, math.pi):                              # outseam groove
        dd = abs(wrap_pi(th - ths))
        off -= 0.0008 * max(0.0, 1 - dd / 0.12) * (1 - smoothstep(-0.040, -0.037, dzw))
    return off


def shirt_point(u, th):
    return torso_point(u, th) + surf_normal(torso_point, u, th) * shirt_off(u, th)


def trouser_point(u, th, extra=0.0):
    return torso_point(u, th) + surf_normal(torso_point, u, th) * (trouser_off(u, th) + extra)


def row_u(spec, th):
    k, val = spec
    if k == 'w': return z_top(th) + val
    if k == 'z': return val
    if k == 'd': return Z_S + val
    raise ValueError(k)


parts = {}

# ============================================================================= SHIRT
log("building shirt")
shirt = Part("Shirt", M_SHIRT)
parts['shirt'] = shirt
N_T = 36
TH_SHIRT = [math.pi / 2 + 2 * math.pi * j / N_T for j in range(N_T)]   # col 0 = centre back
SHIRT_ROWS = [('w', -0.058), ('w', -0.036), ('w', -0.015), ('w', 0.004), ('w', 0.018),
              ('w', 0.040), ('w', 0.068), ('z', 1.11), ('z', 1.15), ('z', 1.19), ('z', 1.23),
              ('z', 1.27), ('z', 1.305), ('z', 1.34), ('z', 1.375), ('z', Z_S),
              ('d', 0.17), ('d', 0.34), ('d', 0.50), ('d', 0.65), ('d', 0.79), ('d', 0.91), ('d', 1.0)]
rows = [[shirt_point(row_u(sp, th), th) for th in TH_SHIRT] for sp in SHIRT_ROWS]
# armpit drag folds on the torso just below the sleeve (front & back of the armpit)
for i, sp in enumerate(SHIRT_ROWS):
    u0 = row_u(sp, 0)
    if 1.20 < u0 < 1.36:
        for j, th in enumerate(TH_SHIRT):
            for ths in (0.0, math.pi):
                dd = wrap_pi(th - ths)
                for c0, amp in ((0.42, 0.0025), (-0.42, 0.0022)):
                    w = max(0.0, 1 - abs(dd - c0) / 0.13) * smoothstep(1.20, 1.27, u0) * (1 - smoothstep(1.31, 1.36, u0))
                    if w > 0:
                        n = surf_normal(torso_point, u0, th)
                        rows[i][j] = rows[i][j] + n * amp * w
SHIRT_GRID, shirt_faces = shirt.grid(rows, T_SHIRT)
SHIRT_BVH = bvh_from_faces(shirt_faces)
TORSO_FACES = list(shirt_faces)

# ----------------------------------------------------------------------------- sleeves
SLV_F = [-0.10, 0.0, 0.10, 0.20, 0.30, 0.40, 0.49, 0.565]
F_CUFF0, F_HEM, F_SEAL = 0.572, 0.640, 0.552
N_SL = 20


def sleeve_frame(sd, f):
    A = ARM[sd]
    c = A['S'] + A['ax'] * A['L'] * f + A['off'] * smoothstep(-0.05, 0.35, f)
    return c


def arm_radius(sd, f, phi):
    A = ARM[sd]
    c = sleeve_frame(sd, f)
    d = A['u'] * math.cos(phi) + A['v'] * math.sin(phi)
    hit = BODY_SIDE[sd].ray_cast(c, d, 0.11)
    if hit[0] is None:
        return None
    return (hit[0] - c).length


def sleeve_style(f, phi):
    base = lerp(0.071, 0.063, clamp(f / 0.62))
    asym = -0.018 * (1 - smoothstep(0.04, 0.38, f))          # flatter cap: blends into the shoulder
    drape = 0.005 * max(0.0, -math.cos(phi)) ** 2 * smoothstep(0.1, 0.4, f)
    return base + asym * math.cos(phi) + drape


SLEEVE_INFO = {}
for sd in 'lr':
    A = ARM[sd]
    tag = T_SLV_L if sd == 'l' else T_SLV_R
    phis = [2 * math.pi * j / N_SL for j in range(N_SL)]

    def ring(f, dr=0.0, clr=0.010, rb_rel=False):
        pts = []
        R = []
        for phi in phis:
            rs = sleeve_style(f, phi)
            rb = arm_radius(sd, f, phi)
            r = rs if rb is None else max(rs, rb + clr)
            R.append(r)
        # circular smoothing
        for _ in range(2):
            R = [0.25 * R[j - 1] + 0.5 * R[j] + 0.25 * R[(j + 1) % N_SL] for j in range(N_SL)]
        c = sleeve_frame(sd, f)
        for j, phi in enumerate(phis):
            d = A['u'] * math.cos(phi) + A['v'] * math.sin(phi)
            pts.append(c + d * (R[j] + dr))
        return pts, R
    rows = []
    for f in SLV_F:
        pts, R = ring(f, clr=0.0105)
        rows.append(pts)
    # underside wrinkles + underarm seam groove
    for i, f in enumerate(SLV_F):
        amp = {0.20: 0.003, 0.30: -0.001, 0.40: 0.0025}.get(f, 0.0)
        c = sleeve_frame(sd, f)
        for j, phi in enumerate(phis):
            d = (rows[i][j] - c).normalized()
            w = max(0.0, -math.cos(phi)) ** 2
            g = -0.001 * max(0.0, 1 - abs(wrap_pi(phi - math.pi)) / 0.35) if f > 0.15 else 0.0
            rows[i][j] = rows[i][j] + d * (amp * w + g)
    # conform the buried root ring under the torso shell
    for j in range(N_SL):
        p = rows[0][j]
        loc, n, _, _ = SHIRT_BVH.find_nearest(p, 0.2)
        if loc is not None and (p - loc).dot(n) > -0.004:
            rows[0][j] = loc - n * 0.006
    # cuff (ribbed band, rolled hem edge, inner facing, seal to the arm)
    cuff_R = []
    c0, Rc0 = ring(F_CUFF0, clr=0.0118)
    c1, Rc1 = ring(F_HEM - 0.004, clr=0.0118)
    cc0 = sleeve_frame(sd, F_CUFF0); cc1 = sleeve_frame(sd, F_HEM - 0.004)
    ch = sleeve_frame(sd, F_HEM); ci0 = sleeve_frame(sd, F_HEM - 0.004); ci1 = sleeve_frame(sd, 0.600)
    cs = sleeve_frame(sd, F_SEAL)
    r_c0, r_c1, r_edge, r_in0, r_in1, r_seal = [], [], [], [], [], []
    for j, phi in enumerate(phis):
        d = A['u'] * math.cos(phi) + A['v'] * math.sin(phi)
        Rm = max(Rc0[j], Rc1[j])
        r_c0.append(cc0 + d * (Rm - 0.0012))
        r_c1.append(cc1 + d * (Rm - 0.0012))
        r_edge.append(ch + d * (Rm - 0.0030))
        r_in0.append(ci0 + d * (Rm - 0.0050))
        r_in1.append(ci1 + d * (Rm - 0.0050))
        rb = arm_radius(sd, F_SEAL, phi)
        rs = (rb + 0.0025) if rb is not None else (Rm - 0.02)
        r_seal.append(cs + d * rs)
    # guarantee skin clearance where the sleeve overlaps the arm (body exists from f ~0.44)
    for i, f in enumerate(SLV_F):
        if f >= 0.3:
            rows[i] = [push_out(q, BODY_SIDE[sd], 0.0095, 0.05)[0] for q in rows[i]]
    r_c0 = [push_out(q, BODY_SIDE[sd], 0.0110, 0.05)[0] for q in r_c0]
    r_c1 = [push_out(q, BODY_SIDE[sd], 0.0110, 0.05)[0] for q in r_c1]
    r_edge = [push_out(q, BODY_SIDE[sd], 0.0090, 0.05)[0] for q in r_edge]
    r_in0 = [push_out(q, BODY_SIDE[sd], 0.0075, 0.05)[0] for q in r_in0]
    r_in1 = [push_out(q, BODY_SIDE[sd], 0.0075, 0.05)[0] for q in r_in1]
    rows_outer = rows + [r_c0, r_c1, r_edge]
    Vg, f_out = shirt.grid(rows_outer, tag)
    Vin, f_in = shirt.grid([Vg[-1], r_in0, r_in1], T_SHIRT_IN)
    Vs, f_seal = shirt.grid([Vin[-1], r_seal], T_SHIRT_IN)
    axd = A['ax']
    cs_f = sleeve_frame

    def out_fn(p, sd=sd):
        Aq = ARM[sd]
        t = (p - Aq['S']).dot(Aq['ax'])
        c = Aq['S'] + Aq['ax'] * t
        return p - c
    orient_faces(f_out, out_fn)
    orient_faces(f_in, lambda p, f=out_fn: -f(p))
    orient_faces(f_seal, lambda p, a=axd: a)
    SLEEVE_INFO[sd] = dict(rows=Vg, faces=f_out)

# ----------------------------------------------------------------------------- collar
log("collar / placket / badge")
U_TOP = Z_S + 1.0
d0 = math.radians(12)
N_COL = 31
TH_COL = [-math.pi / 2 + d0 + (2 * math.pi - 2 * d0) * k / (N_COL - 1) for k in range(N_COL)]
PROFILE = [(-0.0012, -0.004), (-0.0015, 0.028), (0.003, 0.0325), (0.012, 0.0225),
           (0.024, 0.003), (0.034, -0.013), (0.0322, -0.0158), (0.0215, 0.0005),
           (0.0065, 0.0105), (0.0045, -0.002)]
col_cols = []
for th in TH_COL:
    base = shirt_point(U_TOP, th)
    C = Vector((NECK_C[0], NECK_C[1], base.z))
    rh = Vector((base.x - C.x, base.y - C.y, 0))
    R0 = rh.length; rh.normalize()
    ang = abs(wrap_pi(th + math.pi / 2))
    fe = 1 - smoothstep(d0, d0 + 0.9, ang)
    e, dr = 0.011 * fe, 0.022 * fe
    pts = []
    for k, (rr, zz) in enumerate(PROFILE):
        if 4 <= k <= 7:
            rr += e * (1.0 if k in (5, 6) else 0.6)
            zz -= dr * (1.0 if k in (5, 6) else 0.55)
        pts.append(Vector((C.x, C.y, base.z)) + rh * (R0 + rr) + Vector((0, 0, zz)))
    # the fall must lie on top of the shirt
    for k in (3, 4, 5, 6, 7, 8):
        p = pts[k]
        for _ in range(2):
            p, _sd = push_out(p, SHIRT_BVH, 0.0035 if k in (5, 6) else 0.0045, 0.06)
        pts[k] = p
    col_cols.append(pts)
# grid: rows = profile index, cols = theta (open)
crows = [[col_cols[c][k] for c in range(N_COL)] for k in range(len(PROFILE))] + \
        [[col_cols[c][0] for c in range(N_COL)]]
# share first/last row verts to close the profile loop
Vc = [[shirt.vert(p, T_COLLAR) for p in row] for row in crows[:-1]]
Vc.append(Vc[0])
_, collar_faces = shirt.grid(Vc, T_COLLAR, cyclic=False)
for cidx in (0, N_COL - 1):          # end caps
    vs = [Vc[k][cidx] for k in range(len(PROFILE))]
    f = shirt.face(vs)
    if f: collar_faces.append(f)
nc = Vector((NECK_C[0], NECK_C[1], 0))


def collar_out(p):
    # outward = away from the profile's centroid line
    th = math.atan2(p.y - NECK_C[1], p.x - NECK_C[0])
    base = shirt_point(U_TOP, th)
    C = Vector((NECK_C[0], NECK_C[1], base.z))
    rh = Vector((base.x - C.x, base.y - C.y, 0)).normalized()
    cen = C + rh * ((base - C).length + 0.014) + Vector((0, 0, 0.006))
    return p - cen
orient_faces(collar_faces, collar_out)
# neck seal (hidden annulus closing the gap between collar and the head's neck)
top_ring = SHIRT_GRID[-1]
inner = []
for v in top_ring:
    p = v.co
    C = Vector((NECK_C[0], NECK_C[1], p.z - 0.004))
    rh = Vector((p.x - C.x, p.y - C.y, 0)).normalized()
    inner.append(C + rh * 0.052)
_, seal_faces = shirt.grid([top_ring, inner], T_SHIRT_IN)
orient_faces(seal_faces, lambda p: Vector((0, 0, 1)))


# ----------------------------------------------------------------------------- placket + buttons
def ray_front(bvh, x, z, y0=-0.6):
    hit = bvh.ray_cast(Vector((x, y0, z)), Vector((0, 1, 0)), 1.0)
    return hit[0], hit[1]


PLK_X = [-0.0145, 0.0, 0.0145]
PLK_Z = [1.446, 1.428, 1.405, 1.382, 1.358, 1.334, 1.310]
top_v, base_v = [], []
for z in PLK_Z:
    trow, brow = [], []
    for x in PLK_X:
        h, n = ray_front(SHIRT_BVH, x, z)
        trow.append(h + n * (0.0024 + (0.0004 if x == 0 else 0.0)))
        brow.append(h + n * 0.0002)
    top_v.append(trow); base_v.append(brow)
Vp, plk_faces = shirt.grid(top_v, T_PLACKET, cyclic=False)
# side walls & bottom
L_wall = [[base_v[i][0] for i in range(len(PLK_Z))], [Vp[i][0] for i in range(len(PLK_Z))]]
R_wall = [[Vp[i][2] for i in range(len(PLK_Z))], [base_v[i][2] for i in range(len(PLK_Z))]]
_, fw1 = shirt.grid(L_wall, T_PLACKET, cyclic=False)
_, fw2 = shirt.grid(R_wall, T_PLACKET, cyclic=False)
_, fw3 = shirt.grid([[base_v[-1][k] for k in range(3)], Vp[-1]], T_PLACKET, cyclic=False)
plk_all = plk_faces + fw1 + fw2 + fw3
orient_faces(plk_all, lambda p: Vector((0, -1, 0)) + Vector((p.x * 8, 0, 0)))
PLK_BVH = bvh_from_faces(plk_faces)


def disc(part, center, n, radius, thick, tag, sides=8, mat=None):
    n = n.normalized()
    t1 = n.cross(Vector((0, 0, 1)))
    if t1.length < 1e-6: t1 = n.cross(Vector((1, 0, 0)))
    t1.normalize(); t2 = n.cross(t1)
    bot = [center + (t1 * math.cos(2 * math.pi * k / sides) + t2 * math.sin(2 * math.pi * k / sides)) * radius for k in range(sides)]
    top = [p + n * thick for p in bot]
    Vb = [part.vert(p, tag) for p in bot]; Vt = [part.vert(p, tag) for p in top]
    fs = []
    for k in range(sides):
        k2 = (k + 1) % sides
        fs.append(part.face([Vb[k], Vb[k2], Vt[k2], Vt[k]], [(0.9, 0.9)] * 4, mat))
    fs.append(part.face(Vt, [(0.9 + 0.01 * math.cos(2 * math.pi * k / sides), 0.9 + 0.01 * math.sin(2 * math.pi * k / sides)) for k in range(sides)], mat))
    fs = [f for f in fs if f]
    orient_faces(fs, lambda p, c=center: p - (c - n * 0.01))
    return fs


for zb in (1.418, 1.366):
    h, nn = ray_front(PLK_BVH, 0.0, zb)
    disc(shirt, h + nn * 0.0002, nn, 0.0056, 0.0019, T_PLACKET)

# ----------------------------------------------------------------------------- badge (own slot)
badge = Part("Badge", M_BADGE)
parts['badge'] = badge
BX, BZ, BW, BH = 0.088, 1.335, 0.070, 0.022
xs = [BX - BW / 2 + BW * k / 3 for k in range(4)]
zs = [BZ - BH / 2, BZ + BH / 2]
ftop, fbase = [], []
for z in zs:
    tr, br = [], []
    for x in xs:
        h, n = ray_front(SHIRT_BVH, x, z)
        tr.append(h + n * 0.0032); br.append(h + n * 0.0003)
    ftop.append(tr); fbase.append(br)
Vt = [[badge.vert(p, T_BADGE) for p in row] for row in ftop]
Vb = [[badge.vert(p, T_BADGE) for p in row] for row in fbase]
bfaces = []
for i in range(3):   # front face, UV 0..1 across the badge (name texture)
    q = [Vt[0][i], Vt[0][i + 1], Vt[1][i + 1], Vt[1][i]]
    uvq = [(i / 3, 0.0), ((i + 1) / 3, 0.0), ((i + 1) / 3, 1.0), (i / 3, 1.0)]
    bfaces.append(badge.face(q, uvq))
ring_t = [Vt[0][0], Vt[0][1], Vt[0][2], Vt[0][3], Vt[1][3], Vt[1][2], Vt[1][1], Vt[1][0]]
ring_b = [Vb[0][0], Vb[0][1], Vb[0][2], Vb[0][3], Vb[1][3], Vb[1][2], Vb[1][1], Vb[1][0]]
for k in range(8):
    k2 = (k + 1) % 8
    bfaces.append(badge.face([ring_b[k], ring_b[k2], ring_t[k2], ring_t[k]], [(0, 0), (0.05, 0), (0.05, 0.02), (0, 0.02)]))
bfaces = [f for f in bfaces if f]
orient_faces(bfaces, lambda p: Vector(((p.x - BX) * 6, -1, (p.z - BZ) * 6)))

# ============================================================================= SHOES
# Closed derby-style work shoe. Built per foot from the foot's own geometry:
#   footprint outline (polar max of the foot verts) -> welt line; ankle ring -> collar line;
#   upper rows run from the welt over a height envelope of the foot (so the toes are covered)
#   to the collar; then clearance push + smoothing. Sole = welt ledge + wall + flat tread.
log("building shoes")
from mathutils.kdtree import KDTree
shoes = Part("Shoes", M_SHOES)
parts['shoes'] = shoes
N_SH = 22
SHOE_INFO = {}
Z_WELT, Z_SOLE_BOT = 0.017, -0.0085
S_ROWS = [0.07, 0.17, 0.29, 0.41, 0.53, 0.65, 0.76, 0.86, 0.94, 1.0]


def polar_outline(pts, c, nbins=144, smooth=3):
    R = [0.0] * nbins
    for p in pts:
        d = p.to_2d() - c
        a = math.atan2(d.y, d.x) % (2 * math.pi)
        k = int(a / (2 * math.pi) * nbins) % nbins
        R[k] = max(R[k], d.length)
    for _ in range(3):                        # dilate (conservative: never cuts inside the foot)
        R = [max(R[k - 1], R[k], R[(k + 1) % nbins]) for k in range(nbins)]
    for _ in range(smooth):                   # then plain smoothing
        R = [0.25 * R[k - 1] + 0.5 * R[k] + 0.25 * R[(k + 1) % nbins] for k in range(nbins)]

    def r_at(phi):
        a = (phi % (2 * math.pi)) / (2 * math.pi) * nbins
        k0 = int(a) % nbins
        t = a - int(a)
        return R[k0] * (1 - t) + R[(k0 + 1) % nbins] * t
    return r_at


for sd, sg in (('l', 1), ('r', -1)):
    tag = T_SHOE_L if sd == 'l' else T_SHOE_R
    bvh = BODY_SIDE[sd]
    FV = [p for p in BV if p.x * sg > 0.02 and p.z < 0.17]
    FV += [BV[a].lerp(BV[b], t) for a, b in BEDGES if BV[a].x * sg > 0.02 and BV[a].z < 0.17 and BV[b].z < 0.17
           for t in (0.25, 0.5, 0.75)]          # densify along edges so the outline has no gaps
    low = [p for p in FV if p.z < 0.095]
    xs_ = [p.x for p in low]
    ys_ = [p.y for p in low]
    C = Vector(((min(xs_) + max(xs_)) / 2, (min(ys_) + max(ys_)) / 2))
    log("foot", sd, "x %.3f..%.3f y %.3f..%.3f zmin %.4f" % (min(xs_), max(xs_), min(ys_), max(ys_), min(p.z for p in low)))
    foot_r = polar_outline(low, C)
    # ankle ring (collar) around the ankle slice
    ank = [p for p in FV if 0.075 < p.z < 0.115]
    Ca = Vector((sum(p.x for p in ank) / len(ank), sum(p.y for p in ank) / len(ank)))
    ank_r = polar_outline(ank, Ca, nbins=72)
    kd = KDTree(len(FV))
    for i, p in enumerate(FV):
        kd.insert(Vector((p.x, p.y, 0.0)), i)
    kd.balance()

    def env(xy, rad=0.013, kd=kd, FV=FV):
        zz = [FV[i].z for (_, i, _) in kd.find_range(Vector((xy.x, xy.y, 0.0)), rad)]
        return max(zz) if zz else 0.0

    # columns: equal arc length along the clearance-expanded footprint, col 0 = heel
    def outline_pt(phi, C=C, foot_r=foot_r):
        fwd = max(0.0, -math.sin(phi)) ** 3          # extra room at the toe
        r = foot_r(phi) + 0.0105 + 0.010 * fwd
        return C + Vector((math.cos(phi), math.sin(phi))) * r
    samp = []
    for k in range(720):
        phi = math.pi / 2 + 2 * math.pi * k / 720 * sg
        samp.append((phi, outline_pt(phi)))
    acc = [0.0]
    for k in range(1, 721):
        acc.append(acc[-1] + (samp[k % 720][1] - samp[k - 1][1]).length)
    phis = []
    for j in range(N_SH):
        target = acc[-1] * j / N_SH
        k = max(i for i in range(720) if acc[i] <= target)
        phis.append(samp[k][0])

    def z_col(phi):                                  # collar line height
        s = math.sin(phi)
        return 0.074 + 0.012 * max(0.0, s) ** 2 + 0.030 * max(0.0, -s) ** 3

    def z_wall(phi):
        s = math.sin(phi)
        return 0.032 + 0.018 * max(0.0, s) ** 2      # heel counter higher

    rows = []
    O = [outline_pt(phi) for phi in phis]
    Q = []
    for phi in phis:
        d = Vector((math.cos(phi), math.sin(phi)))
        Q.append((Ca + d * (ank_r(phi) + 0.0075), z_col(phi)))
    rows.append([Vector((o.x, o.y, Z_WELT)) for o in O])
    for s in S_ROWS:
        row = []
        for j, phi in enumerate(phis):
            q, zc = Q[j]
            xy = O[j].lerp(q, s ** 0.85)
            zw = z_wall(phi)
            ramp = lerp(zw, zc, smoothstep(0.0, 1.0, s) if math.sin(phi) > -0.3 else s ** 2.2)
            ramp = max(ramp, zw * min(1.0, s / 0.07))
            ze = min(env(xy) + 0.0085, zc)
            row.append(Vector((xy.x, xy.y, max(ramp, ze, Z_WELT + 0.004))))
        rows.append(row)
    # clearance push + light Laplacian smoothing (welt and collar rows held)
    for it in range(4):
        for k in range(1, len(rows)):
            for j in range(N_SH):
                rows[k][j], _ = push_out(rows[k][j], bvh, 0.0080, 0.05)
        if it < 3:
            new = [r[:] for r in rows]
            for k in range(1, len(rows) - 1):
                for j in range(N_SH):
                    nb = rows[k - 1][j] + rows[k + 1][j] + rows[k][j - 1] + rows[k][(j + 1) % N_SH]
                    new[k][j] = rows[k][j].lerp(nb / 4, 0.35)
            rows = new
    for k in range(1, len(rows)):
        for j in range(N_SH):
            rows[k][j], _ = push_out(rows[k][j], bvh, 0.0080, 0.05)
    # toe-cap seam + heel seam grooves
    for k in range(len(rows)):
        for j, phi in enumerate(phis):
            p = rows[k][j]
            d = (p.to_2d() - C).normalized()
            g = 0.0
            if j == 0 and k > 1: g -= 0.0009
            if k == 3 and -math.sin(phi) > 0.55: g -= 0.0008
            rows[k][j] = p + Vector((d.x, d.y, 0)) * g
    Vu, f_up = shoes.grid(rows, tag)
    # collar lining (turns into the shoe)
    lin0, lin1 = [], []
    for j, v in enumerate(Vu[-1]):
        p = v.co
        d = Vector((p.x - Ca.x, p.y - Ca.y, 0)).normalized()
        lin0.append(p - d * 0.0035 + Vector((0, 0, 0.0015)))
        lin1.append(p - d * 0.0045 + Vector((0, 0, -0.018)))
    Vl, f_lin = shoes.grid([Vu[-1], lin0, lin1], T_SHOE_IN)
    # sole: welt ledge (flat, facing up), wall with a groove, bevelled tread edge, flat bottom
    welt_o, w_mid, groove, w_low, bot = [], [], [], [], []
    for j, v in enumerate(Vu[0]):
        p = v.co
        d = Vector((p.x - C.x, p.y - C.y, 0)).normalized()
        welt_o.append(p + d * 0.0042)
        w_mid.append(Vector((p.x, p.y, 0.0065)) + d * 0.0046)
        groove.append(Vector((p.x, p.y, 0.0045)) + d * 0.0032)
        w_low.append(Vector((p.x, p.y, Z_SOLE_BOT + 0.003)) + d * 0.0046)
        bot.append(Vector((p.x, p.y, Z_SOLE_BOT)) + d * 0.0030)
    Vw_, f_welt = shoes.grid([Vu[0], welt_o], tag)
    Vso, f_sole = shoes.grid([Vw_[-1], w_mid, groove, w_low, bot], tag)
    cb = Vector((C.x, C.y, Z_SOLE_BOT))
    # tread: two rings inward + centre fan
    inner1 = [Vector((v.co.x, v.co.y, Z_SOLE_BOT)).lerp(cb, 0.35) for v in Vso[-1]]
    inner2 = [Vector((v.co.x, v.co.y, Z_SOLE_BOT)).lerp(cb, 0.70) for v in Vso[-1]]
    Vt_, f_tread = shoes.grid([Vso[-1], inner1, inner2], tag)
    vc = shoes.vert(cb, tag)
    f_bot = []
    for j in range(N_SH):
        j2 = (j + 1) % N_SH
        a, b_ = Vt_[-1][j], Vt_[-1][j2]
        f = shoes.face([a, vc, b_], [(a.co.x * UVS, a.co.y * UVS), (cb.x * UVS, cb.y * UVS), (b_.co.x * UVS, b_.co.y * UVS)])
        if f: f_bot.append(f)
    for f in f_tread:   # planar UVs on the tread
        for l in f.loops:
            l[shoes.uv].uv = (l.vert.co.x * UVS, l.vert.co.y * UVS)

    def out_fn(p, C=C):
        return Vector((p.x - C.x, p.y - C.y, 0.0)) + Vector((0, 0, 0.6 * (p.z - 0.03)))
    orient_faces(f_up + f_sole, out_fn)
    orient_faces(f_welt, lambda p: Vector((0, 0, 1)))
    orient_faces(f_bot + f_tread, lambda p: Vector((0, 0, -1)))
    orient_faces(f_lin, lambda p, Ca=Ca: -Vector((p.x - Ca.x, p.y - Ca.y, 0.0)))
    UPPER_BVH = bvh_from_faces(f_up)
    # laces + eyestays over the instep (front column, between toe cap and collar)
    lace_faces = []
    jf = min(range(N_SH), key=lambda j: math.sin(phis[j]))         # front-most column

    def on_upper(xy, lift, U=UPPER_BVH):
        hit = U.ray_cast(Vector((xy.x, xy.y, 0.3)), Vector((0, 0, -1)), 0.4)
        if hit[0] is None: return None
        return hit[0] + hit[1] * lift
    pA = rows[4][jf].to_2d()
    pB = Q[jf][0]
    axis = (pB - pA)
    L_ax = axis.length
    axis.normalize()
    perp = Vector((-axis.y, axis.x))
    for t in (0.30, 0.47, 0.64, 0.80):
        c2 = pA + axis * (L_ax * t)
        hw_ = 0.012 + 0.004 * t
        bar_t, bar_b, base_t, base_b = [], [], [], []
        ok = True
        for k in range(3):
            o = (k - 1) * hw_
            lift = 0.0034 + (0.0010 if k == 1 else 0.0)
            pt_ = on_upper(c2 + perp * o + axis * 0.0028, lift)
            pb_ = on_upper(c2 + perp * o - axis * 0.0028, lift)
            bt_ = on_upper(c2 + perp * o + axis * 0.0028, 0.0003)
            bb_ = on_upper(c2 + perp * o - axis * 0.0028, 0.0003)
            if None in (pt_, pb_, bt_, bb_):
                ok = False
                break
            bar_t.append(pt_); bar_b.append(pb_); base_t.append(bt_); base_b.append(bb_)
        if ok:
            Vl_, f1 = shoes.grid([bar_b, bar_t], T_LACE, cyclic=False)
            _, f2 = shoes.grid([Vl_[1], base_t], T_LACE, cyclic=False)
            _, f3 = shoes.grid([base_b, Vl_[0]], T_LACE, cyclic=False)
            lace_faces += f1 + f2 + f3
    for side_ in (-1, 1):          # eyestay quarters: thin raised strips either side of the laces
        top_, base_ = [], []
        for t in (0.20, 0.42, 0.64, 0.86, 0.97):
            c2 = pA + axis * (L_ax * t) + perp * side_ * (0.0185 + 0.004 * t)
            a_ = on_upper(c2, 0.0016)
            b0_ = on_upper(c2 + perp * side_ * 0.009, 0.0016)
            a0 = on_upper(c2, 0.0002)
            b00 = on_upper(c2 + perp * side_ * 0.009, 0.0002)
            if None in (a_, b0_, a0, b00): continue
            top_.append([a_, b0_]); base_.append([a0, b00])
        if len(top_) >= 2:
            Ve, f1 = shoes.grid([[r[0] for r in top_], [r[1] for r in top_]], T_LACE, cyclic=False)
            _, f2 = shoes.grid([[r[0] for r in base_], Ve[0]], T_LACE, cyclic=False)
            lace_faces += f1 + f2
    orient_faces(lace_faces, lambda p: Vector((0, 0, 1)))
    SHOE_INFO[sd] = dict(center=C, phis=phis, bvh=bvh, up_faces=f_up + f_sole + f_welt + f_bot + f_tread)

SHOE_BVH = {sd: bvh_from_faces(SHOE_INFO[sd]['up_faces']) for sd in 'lr'}

# ============================================================================= TROUSERS
log("building trousers")
tr = Part("Trousers", M_TROUSERS)
parts['trousers'] = tr
TH_TR = [-math.pi / 2 + 2 * math.pi * j / N_T for j in range(N_T)]   # col 0 = centre front
Z_C = 0.83


def pel_u(spec, th):
    k, v = spec
    if k == 'c':
        return Z_C + (z_top(th) - 0.040 - Z_C) * v
    return z_top(th) + v


PEL_ROWS = [('c', 0.0), ('c', 0.22), ('c', 0.45), ('c', 0.68), ('c', 0.86), ('c', 1.0),
            ('w', -0.0375), ('w', 0.0)]
prow = [[trouser_point(pel_u(sp, th), th) for th in TH_TR] for sp in PEL_ROWS]
Vpel = [[tr.vert(p, T_TR_PEL) for p in row] for row in prow]
# crotch chain (shared by both legs)
Pf, Pb = Vpel[0][0].co, Vpel[0][N_T // 2].co
chain = []
for k in range(1, 6):
    t = k / 6
    chain.append(tr.vert(Vector((0.0, lerp(Pf.y, Pb.y, t), Z_C - 0.048 * math.sin(math.pi * t))), T_TR_PEL))
ringL = Vpel[0][0:N_T // 2 + 1] + chain[::-1]
ringR = Vpel[0][N_T // 2:] + [Vpel[0][0]] + chain
ringL = ringL[21:] + ringL[:21]          # UV seam on the inseam
ringR = ringR[21:] + ringR[:21]
N_L = len(ringL)
assert N_L == len(ringR) == 24, (N_L, len(ringR))

LEG_C_KEYS = [(0.83, 0.098, -0.008), (0.70, 0.0975, -0.024), (0.60, 0.101, -0.017),
              (0.50, 0.109, -0.010), (0.05, 0.127, 0.004)]
LEG_S_KEYS = [(0.83, 0.103, 0.110), (0.765, 0.101, 0.104), (0.70, 0.097, 0.099), (0.62, 0.090, 0.092),
              (0.54, 0.083, 0.086), (0.47, 0.080, 0.084), (0.38, 0.079, 0.084), (0.25, 0.078, 0.084),
              (0.12, 0.077, 0.085), (0.04, 0.077, 0.087)]


def lin_keys(keys, z):
    ks = sorted(keys)
    if z <= ks[0][0]: return ks[0][1:]
    if z >= ks[-1][0]: return ks[-1][1:]
    for a, b in zip(ks, ks[1:]):
        if a[0] <= z <= b[0]:
            t = (z - a[0]) / (b[0] - a[0])
            return tuple(lerp(a[i], b[i], t) for i in range(1, len(a)))


def leg_center(sg, z):
    x, y = lin_keys(LEG_C_KEYS, z)
    return Vector((x * sg, y))


def z_hem(phi): return 0.065 - 0.020 * math.sin(phi)


Z_LEG = [0.765, 0.73, 0.695, 0.65, 0.60, 0.56, 0.535, 0.51, 0.485, 0.46, 0.41, 0.35, 0.29, 0.23,
         0.18, 0.15, 0.12, None]
W_BLEND = {0.765: 0.55, 0.73: 0.85}
KNEE_SLACK = float(([a[6:] for a in ARGS if a.startswith('slack=')] or ['-0.022'])[0])
LEG_MIN_CLR = float(([a[4:] for a in ARGS if a.startswith('clr=')] or ['0.0105'])[0])
KNEE_FOLD = {0.56: 0.0030, 0.535: -0.0008, 0.51: 0.0035, 0.485: -0.0008, 0.46: 0.0028}
BREAK_FOLD = {0.18: 0.0030, 0.15: -0.0006, 0.12: 0.0038}
LEG_INFO = {}
for sd, sg, ring0, tag in (('l', 1, ringL, T_TR_LEG_L), ('r', -1, ringR, T_TR_LEG_R)):
    c0 = leg_center(sg, Z_C)
    phis = [math.atan2(v.co.y - c0.y, v.co.x - c0.x) for v in ring0]
    rows = []
    for z_row in Z_LEG:
        R = []; Zs = []
        for j, phi in enumerate(phis):
            z = z_row if z_row is not None else z_hem(phi)
            c = leg_center(sg, z)
            rx, ry = lin_keys(LEG_S_KEYS, z)
            cphi, sphi = math.cos(phi), math.sin(phi)
            rs = 1.0 / math.sqrt((cphi / rx) ** 2 + (sphi / ry) ** 2)
            o = Vector((c.x, c.y, z)); d = Vector((cphi, sphi, 0))
            hit = BODY_SIDE[sd].ray_cast(o, d, 0.14)
            clr = 0.010 + 0.004 * max(0.0, -sphi) ** 2 * smoothstep(0.62, 0.52, z) * smoothstep(0.38, 0.46, z)
            r = rs
            if hit[0] is not None:
                r = max(rs, (hit[0] - o).length + clr)
            R.append(r); Zs.append(z)
        for _ in range(2):
            R = [0.25 * R[j - 1] + 0.5 * R[j] + 0.25 * R[(j + 1) % N_L] for j in range(N_L)]
        row = []
        for j, phi in enumerate(phis):
            z = Zs[j]; c = leg_center(sg, z)
            cphi, sphi = math.cos(phi), math.sin(phi)
            r = R[j]
            back, front = max(0.0, sphi), max(0.0, -sphi)
            if z_row in KNEE_FOLD: r += KNEE_FOLD[z_row] * back ** 1.5
            # slack behind / beside the knee so the bent knee's crease stays covered when seated
            r += KNEE_SLACK * smoothstep(-0.35, 0.55, sphi) * max(0.0, 1 - abs(z - 0.505) / 0.105)
            if z_row in BREAK_FOLD: r += BREAK_FOLD[z_row] * (0.4 + 0.6 * front)
            # pressed front crease / inseam & outseam grooves
            r += 0.0022 * max(0.0, 1 - abs(wrap_pi(phi + math.pi / 2)) / 0.28)
            r -= 0.0008 * max(0.0, 1 - abs(wrap_pi(phi)) / 0.2)
            r -= 0.0008 * max(0.0, 1 - abs(wrap_pi(phi - math.pi)) / 0.2)
            p = Vector((c.x + r * cphi, c.y + r * sphi, z))
            if z_row in W_BLEND:
                p0 = ring0[j].co
                p = Vector((p0.x, p0.y, z)).lerp(p, W_BLEND[z_row])
            row.append(p)
        rows.append(row)
    # clearance to the leg (normal based) and to the shoe
    for it in range(2):
        for i in range(len(rows)):
            for j in range(N_L):
                rows[i][j], _ = push_out(rows[i][j], BODY_SIDE[sd], LEG_MIN_CLR, 0.06)
                if rows[i][j].z < 0.20:
                    rows[i][j], _ = push_out(rows[i][j], SHOE_BVH[sd], 0.0045, 0.04)
    Vleg, f_leg = tr.grid([ring0] + rows, tag)
    # hem: rolled edge + inner facing
    hem = Vleg[-1]
    e_, i0, i1 = [], [], []
    for v in hem:
        p = v.co; c = leg_center(sg, p.z)
        d = Vector((p.x - c.x, p.y - c.y, 0)).normalized()
        q_, _ = push_out(p + Vector((0, 0, -0.0025)) - d * 0.0016, SHOE_BVH[sd], 0.0035, 0.04)
        e_.append(q_)
        i0.append(p - d * 0.0042)
        i1.append(p - d * 0.0042 + Vector((0, 0, 0.032)))
    Vh, f_hem_edge = tr.grid([hem, e_], tag)
    Vhi, f_hem_in = tr.grid([Vh[-1], i0, i1], T_TR_IN)

    def out_fn(p, sg=sg):
        c = leg_center(sg, p.z)
        return Vector((p.x - c.x, p.y - c.y, 0))
    orient_faces(f_leg + f_hem_edge, out_fn)
    orient_faces(f_hem_in, lambda p, f=out_fn: -f(p))
    LEG_INFO[sd] = dict(faces=f_leg)
# pelvis faces (grid over shared verts)
_, f_pel = tr.grid(Vpel, T_TR_PEL)
# waistband top roll + inner facing
top = Vpel[-1]
r_e, r_i0, r_i1 = [], [], []
for j, th in enumerate(TH_TR):
    u = z_top(th)
    n = surf_normal(torso_point, u, th)
    p = top[j].co
    r_e.append(p + Vector((0, 0, 0.002)) - n * 0.0022)
    r_i0.append(p - n * 0.0042)
    r_i1.append(trouser_point(u - 0.034, th) - surf_normal(torso_point, u - 0.034, th) * 0.0042)
Vw, f_wb = tr.grid([top, r_e], T_TR_PEL)
Vwi, f_wbi = tr.grid([Vw[-1], r_i0, r_i1], T_TR_IN)


def pel_out(p):
    return Vector((p.x, p.y - 0.005, 0.0))
orient_faces(f_pel + f_wb, pel_out)
orient_faces(f_wbi, lambda p: -pel_out(p))
TR_PEL_FACES = f_pel


# ----------------------------------------------------------------------------- trouser details
def strip(part, pts_center, width_dir_fn, half_w, lift, base_lift, tag, walls=(True, True, True, True)):
    """raised strip along a polyline of (point, normal); returns faces."""
    top_l, top_r, bot_l, bot_r = [], [], [], []
    for (p, n), wd in zip(pts_center, width_dir_fn):
        top_l.append(p + n * lift - wd * half_w); top_r.append(p + n * lift + wd * half_w)
        bot_l.append(p + n * base_lift - wd * half_w); bot_r.append(p + n * base_lift + wd * half_w)
    Vt_, f1 = part.grid([top_l, top_r], tag, cyclic=False)
    fs = list(f1)
    if walls[0]:
        _, f = part.grid([bot_l, Vt_[0]], tag, cyclic=False); fs += f
    if walls[1]:
        _, f = part.grid([Vt_[1], bot_r], tag, cyclic=False); fs += f
    if walls[2]:
        f = part.face([part.vert(bot_l[0], tag), part.vert(bot_r[0], tag), Vt_[1][0], Vt_[0][0]]); fs.append(f)
    if walls[3]:
        f = part.face([Vt_[0][-1], Vt_[1][-1], part.vert(bot_r[-1], tag), part.vert(bot_l[-1], tag)]); fs.append(f)
    fs = [f for f in fs if f]
    orient_faces(fs, lambda p: Vector((p.x, p.y - 0.005, 0)))
    return fs


def tsurf(u, th, extra=0.0):
    return trouser_point(u, th, extra), surf_normal(torso_point, u, th)


det_faces = []
# fly (wearer's left of centre front, J-curve at the bottom)
fly_pts, fly_w = [], []
for k, u in enumerate([z_top(-math.pi / 2) - 0.041, 0.935, 0.915, 0.895, 0.878]):
    wcen = 0.017 if k < 4 else 0.009
    rr = math.hypot(*trouser_point(u, -math.pi / 2).to_2d())
    th = -math.pi / 2 + wcen / max(rr, 0.05)
    p, n = tsurf(u, th)
    fly_pts.append((p, n))
    fly_w.append(Vector((1, 0, 0)))
det_faces += strip(tr, fly_pts, fly_w, 0.016 if True else 0, 0.0016, 0.0001, T_TR_DET)
# slanted front pocket lips
for sg in (1, -1):
    pts, wds = [], []
    for k in range(5):
        t = k / 4
        th = -math.pi / 2 + sg * lerp(math.radians(30), math.radians(76), t)
        u = lerp(z_top(th) - 0.041, 0.875, t)
        p, n = tsurf(u, th)
        pts.append((p, n))
    for k in range(5):
        a = pts[max(k - 1, 0)][0]; b = pts[min(k + 1, 4)][0]
        tdir = (b - a).normalized(); n = pts[k][1]
        wds.append(n.cross(tdir).normalized() * (1 if sg > 0 else -1))
    det_faces += strip(tr, pts, wds, 0.005, 0.0014, 0.0001, T_TR_DET)
# back welt pockets
for sg in (1, -1):
    pts, wds = [], []
    for k in range(4):
        th = math.pi / 2 - sg * lerp(math.radians(18), math.radians(48), k / 3)
        p, n = tsurf(0.935, th)
        pts.append((p, n)); wds.append(Vector((0, 0, 1)))
    det_faces += strip(tr, pts, wds, 0.005, 0.0013, 0.0001, T_TR_DET)
# belt loops (over the belt)
BELT_IN = 0.0145 + 0.0012 + 0.0008
BELT_OUT = BELT_IN + 0.0038
for thd in (-55, -125, 5, 175, 52, 128, 90):
    th = math.radians(thd)
    rr = math.hypot(*trouser_point(1.0, th).to_2d())
    dth = 0.006 / rr
    cols_ = []
    for th2 in (th - dth, th + dth):
        prof = []
        for dzw, extra in ((-0.048, 0.0003), (-0.041, BELT_OUT - trouser_off(z_top(th2) - 0.041, th2) + 0.0015),
                           (-0.0015, BELT_OUT - trouser_off(z_top(th2) - 0.0015, th2) + 0.0015), (0.0006, 0.0006)):
            u = z_top(th2) + dzw
            prof.append(trouser_point(u, th2, extra))
        cols_.append(prof)
    # front face
    _, f1 = tr.grid([cols_[0], cols_[1]], T_TR_DET, cyclic=False)
    side0 = [trouser_point(z_top(th - dth) + dz, th - dth, 0.0) for dz in (-0.048, -0.041, -0.0015, 0.0006)]
    side1 = [trouser_point(z_top(th + dth) + dz, th + dth, 0.0) for dz in (-0.048, -0.041, -0.0015, 0.0006)]
    _, f2 = tr.grid([side0, cols_[0]], T_TR_DET, cyclic=False)
    _, f3 = tr.grid([cols_[1], side1], T_TR_DET, cyclic=False)
    fs = f1 + f2 + f3
    orient_faces(fs, lambda p: Vector((p.x, p.y - 0.005, 0)))
    det_faces += fs

# ============================================================================= BELT
log("building belt")
belt = Part("Belt", M_BELT)
parts['belt'] = belt
N_B = 32
TH_B = [-math.pi / 2 + 2 * math.pi * j / N_B for j in range(N_B)]
bl = []
for th in TH_B:
    zt = z_top(th)
    bl.append([trouser_point(zt - 0.0375, th, BELT_IN - trouser_off(zt - 0.0375, th)),
               trouser_point(zt - 0.0375, th, BELT_OUT - trouser_off(zt - 0.0375, th)),
               trouser_point(zt - 0.0025, th, BELT_OUT - trouser_off(zt - 0.0025, th)),
               trouser_point(zt - 0.0025, th, BELT_IN - trouser_off(zt - 0.0025, th))])
brows = [[bl[j][k] for j in range(N_B)] for k in range(4)]
Vb_ = [[belt.vert(p, T_BELT) for p in row] for row in brows]
Vb_.append(Vb_[0])
_, belt_faces = belt.grid(Vb_, T_BELT)


def belt_out(p):
    th = math.atan2(p.y, p.x)
    zt = z_top(th)
    c = trouser_point(zt - 0.02, th, BELT_IN + 0.0019 - trouser_off(zt - 0.02, th))
    return p - c
orient_faces(belt_faces, belt_out)
# buckle (rectangular frame) at centre front
thf = -math.pi / 2
uc = z_top(thf) - 0.020
pc = trouser_point(uc, thf, BELT_OUT - trouser_off(uc, thf))
nf = surf_normal(torso_point, uc, thf)
ex = Vector((1, 0, 0)); ez = nf.cross(ex).normalized()
if ez.z < 0: ez = -ez
bk = []
for depth in (0.0007, 0.0048):
    lay = []
    for (hw, hh) in ((0.025, 0.021), (0.0175, 0.0135)):
        lay.append([pc + nf * depth + ex * sx_ * hw + ez * sz_ * hh for sx_, sz_ in ((-1, -1), (1, -1), (1, 1), (-1, 1))])
    bk.append(lay)
# layers: bk[depth][outer/inner][4]
Vk = [[[belt.vert(p, T_BUCKLE) for p in ring] for ring in lay] for lay in bk]
bfs = []
for k in range(4):
    k2 = (k + 1) % 4
    bfs.append(belt.face([Vk[1][1][k], Vk[1][1][k2], Vk[1][0][k2], Vk[1][0][k]], [(0, 0)] * 4))   # front frame
    bfs.append(belt.face([Vk[0][0][k], Vk[0][0][k2], Vk[1][0][k2], Vk[1][0][k]], [(0, 0)] * 4))   # outer wall
    bfs.append(belt.face([Vk[1][1][k], Vk[1][1][k2], Vk[0][1][k2], Vk[0][1][k]], [(0, 0)] * 4))   # inner wall
bfs = [f for f in bfs if f]


def buckle_out(p):
    q = p - pc
    lx, lz, ln = q.dot(ex), q.dot(ez), q.dot(nf)
    # front faces -> +n ; walls -> away from the frame mid-line
    mx = 0.02125 * (1 if lx >= 0 else -1); mz = 0.01725 * (1 if lz >= 0 else -1)
    if ln > 0.0045:
        return nf
    ax_, az_ = abs(lx), abs(lz)
    if ax_ / 0.02125 > az_ / 0.01725:
        return ex * (1 if (ax_ > 0.02125) == (lx > 0) else -1) * (1 if ax_ > 0.02125 else 1)
    return ez * (1 if lz > 0 else -1) * (1 if az_ > 0.01725 else -1)
for f in bfs:
    f.normal_update()
    c = f.calc_center_median() - pc
    lx, lz, ln = c.dot(ex), c.dot(ez), c.dot(nf)
    if abs(ln - 0.0048) < 1e-4:
        want = nf
    elif abs(abs(lx) - 0.025) < 1e-4 or abs(abs(lz) - 0.021) < 1e-4:
        want = ex * math.copysign(1, lx) if abs(abs(lx) - 0.025) < 1e-4 else ez * math.copysign(1, lz)
    else:
        want = -ex * math.copysign(1, lx) if abs(abs(lx) - 0.0175) < 1e-4 else -ez * math.copysign(1, lz)
    if f.normal.dot(want) < 0: f.normal_flip()
# belt tip lying over the strap towards the wearer's left
tip = []
nt = 6
for k in range(nt):
    t = k / (nt - 1)
    th = -math.pi / 2 + lerp(math.radians(7.5), math.radians(30), t)
    zt = z_top(th)
    hh = 0.0145 * (1.0 if k < nt - 1 else 0.55)
    um = zt - 0.020
    o_in = BELT_OUT + 0.0004; o_out = BELT_OUT + 0.0040
    tip.append([trouser_point(um - hh, th, o_in - trouser_off(um - hh, th)),
                trouser_point(um - hh, th, o_out - trouser_off(um - hh, th)),
                trouser_point(um + hh, th, o_out - trouser_off(um + hh, th)),
                trouser_point(um + hh, th, o_in - trouser_off(um + hh, th))])
trows = [[tip[j][k] for j in range(nt)] for k in range(4)]
Vtp = [[belt.vert(p, T_BELT) for p in row] for row in trows]
_, tip_faces = belt.grid(Vtp[1:3], T_BELT, cyclic=False)              # outer face
_, tf2 = belt.grid([Vtp[0], Vtp[1]], T_BELT, cyclic=False)            # bottom edge
_, tf3 = belt.grid([Vtp[2], Vtp[3]], T_BELT, cyclic=False)            # top edge
endc = belt.face([Vtp[0][-1], Vtp[1][-1], Vtp[2][-1], Vtp[3][-1]])
tip_all = tip_faces + tf2 + tf3 + ([endc] if endc else [])
orient_faces(tip_all, belt_out)

# ============================================================================= join
log("joining parts")
mats = []
for s in SLOTS:
    m = bpy.data.materials.new(s)
    c = PREVIEW_COLORS[s]
    m.diffuse_color = (c[0], c[1], c[2], 1.0)
    mats.append(m)
objs = []
for key in ('shirt', 'trousers', 'belt', 'shoes', 'badge'):
    p = parts[key]
    bmesh.ops.remove_doubles(p.bm, verts=[v for v in p.bm.verts], dist=1e-7)
    ob = p.to_object()
    for m in mats:
        ob.data.materials.append(m)
    objs.append(ob)
bpy.ops.object.select_all(action='DESELECT')
for ob in objs:
    ob.select_set(True)
bpy.context.view_layer.objects.active = objs[0]
bpy.ops.object.join()
outfit = bpy.context.view_layer.objects.active
outfit.name = OUTFIT
outfit.data.name = OUTFIT
# triangulate, sharp edges, clean
bm = bmesh.new(); bm.from_mesh(outfit.data)
bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
bmesh.ops.triangulate(bm, faces=bm.faces[:], quad_method='BEAUTY', ngon_method='BEAUTY')
for e in bm.edges:
    e.smooth = True
    if len(e.link_faces) == 2 and e.calc_face_angle(0) > math.radians(55):
        e.smooth = False
bm.to_mesh(outfit.data); bm.free()
outfit.data.update()
TRIS = len(outfit.data.polygons)
log("outfit verts", len(outfit.data.vertices), "tris", TRIS)
tags = [d.value for d in outfit.data.attributes['tag'].data]

# ============================================================================= skinning
log("skinning")
# move into armature space and parent (mesh data in cm like the body)
inv = arm.matrix_world.inverted()
outfit.data.transform(inv)
outfit.parent = arm
outfit.matrix_parent_inverse = Matrix.Identity(4)
outfit.matrix_basis = Matrix.Identity(4)
bpy.context.view_layer.update()
REST_W = [outfit.matrix_world @ v.co for v in outfit.data.vertices]

# 1) Data Transfer from the body (vertex groups, nearest face interpolated)
dt = outfit.modifiers.new("BodyWeights", 'DATA_TRANSFER')
dt.object = body
dt.use_vert_data = True
dt.data_types_verts = {'VGROUP_WEIGHTS'}
dt.vert_mapping = 'POLYINTERP_NEAREST'
dt.layers_vgroup_select_src = 'ALL'
dt.layers_vgroup_select_dst = 'NAME'
bpy.ops.object.select_all(action='DESELECT')
outfit.select_set(True)
bpy.context.view_layer.objects.active = outfit
bpy.ops.object.datalayout_transfer(modifier=dt.name)
bpy.ops.object.modifier_apply(modifier=dt.name)
gname = {g.index: g.name for g in outfit.vertex_groups}
DTW = [{gname[g.group]: g.weight for g in v.groups if g.weight > 1e-5} for v in outfit.data.vertices]
log("data transfer done; groups", len(outfit.vertex_groups))

# 2) procedural field for the region the optimized body no longer has
CHAIN_B = ['pelvis', 'spine_01', 'spine_02', 'spine_03', 'spine_04', 'spine_05', 'neck_01']
heads_z = [B[b].z for b in CHAIN_B]
CHAIN = [('pelvis', 0.92)] + [(CHAIN_B[i], 0.5 * (heads_z[i] + heads_z[i + 1])) for i in range(1, 6)]


def chain_weights(z):
    if z <= CHAIN[0][1]: return {CHAIN[0][0]: 1.0}
    if z >= CHAIN[-1][1]: return {CHAIN[-1][0]: 1.0}
    for (b0, z0), (b1, z1) in zip(CHAIN, CHAIN[1:]):
        if z0 <= z <= z1:
            t = (z - z0) / (z1 - z0)
            return {b0: 1 - t, b1: t}


def arm_param(sd, p):
    A = ARM[sd]
    d = p - A['S']
    t = d.dot(A['ax']) / A['L']
    rad = (d - A['ax'] * d.dot(A['ax'])).length
    return t, rad


def proc_weights(p, tag):
    W = {}

    def add(b, w):
        if w > 1e-5: W[b] = W.get(b, 0.0) + w
    x, y, z = p
    back = smoothstep(-0.03, 0.07, y)
    z_hi = lerp(0.955, 0.89, back); z_lo = lerp(0.83, 0.76, back)
    s_leg = smoothstep(z_hi, z_lo, z)
    wl = smoothstep(-0.025, 0.025, x)
    tw = 0.5 * smoothstep(0.86, 0.72, z)
    for sd, f in (('l', wl), ('r', 1 - wl)):
        add('thigh_' + sd, s_leg * f * (1 - tw)); add('thigh_twist_01_' + sd, s_leg * f * tw)
    rest = 1 - s_leg
    Aw, Cw = {}, {}
    for sd in 'lr':
        sg = ARM[sd]['sg']; xs = x * sg
        t, rad = arm_param(sd, p)
        a = smoothstep(-0.12, 0.12, t) * smoothstep(0.095, 0.075, rad) * smoothstep(0.10, 0.15, xs)
        if tag in (T_SLV_L, T_SLV_R, T_SHIRT_IN) and xs > 0.1:
            a = max(a, smoothstep(0.15, 0.35, t))
        c = smoothstep(0.04, 0.13, xs) * smoothstep(1.28, 1.40, z) * (1 - a) * 0.6
        Aw[sd] = (a, t); Cw[sd] = c
    neck = 0.6 * smoothstep(1.44, 1.52, z) * smoothstep(0.10, 0.072, math.hypot(x, y - NECK_C[1]))
    used = sum(v[0] for v in Aw.values()) + sum(Cw.values()) + neck
    sc = 1.0 / used if used > 1 else 1.0
    for b, w in chain_weights(z).items():
        add(b, rest * max(0.0, 1 - used * sc) * w)
    add('neck_01', rest * neck * sc)
    for sd in 'lr':
        a, t = Aw[sd]
        a *= sc
        w_ua = 1 - smoothstep(0.25, 0.40, t); w_t2 = smoothstep(0.50, 0.62, t); w_t1 = max(0.0, 1 - w_ua - w_t2)
        add('upperarm_' + sd, rest * a * w_ua)
        add('upperarm_twist_01_' + sd, rest * a * w_t1)
        add('upperarm_twist_02_' + sd, rest * a * w_t2)
        add('clavicle_' + sd, rest * Cw[sd] * sc)
    return W


TOE_TO_BALL = ('toe_0',)
full_w = []
for i, v in enumerate(outfit.data.vertices):
    p = REST_W[i]; tag = tags[i]
    dtw = DTW[i]
    sgn = 'l' if p.x >= 0 else 'r'
    other = '_r' if sgn == 'l' else '_l'
    if tag in (T_SHOE_L, T_SHOE_R, T_SHOE_IN, T_LACE):
        s_body = 1.0
    elif tag in (T_SLV_L, T_SLV_R, T_SHIRT_IN) and abs(p.x) > 0.15:
        t, rad = arm_param(sgn, p)
        s_body = smoothstep(0.47, 0.58, t)
    elif tag in (T_TR_LEG_L, T_TR_LEG_R, T_TR_IN, T_TR_PEL, T_TR_DET) and p.z < 0.80:
        s_body = smoothstep(0.765, 0.66, p.z)
    else:
        s_body = 0.0
    W = {}
    if s_body > 0:
        tot = 0.0
        clean = {}
        for b, w in dtw.items():
            if abs(p.x) > 0.02 and b.endswith(other):
                continue
            if tag in (T_SHOE_L, T_SHOE_R, T_SHOE_IN, T_LACE) and 'toe_0' in b:
                b = 'ball' + b[-2:]
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
    tot = sum(W.values())
    full_w.append({b: w / tot for b, w in W.items()} if tot > 0 else {'pelvis': 1.0})

# ----------------------------------------------------------------------------- weight post-process
import numpy as np
BONES_ALL = sorted({b for W in full_w for b in W})
BIDX = {b: k for k, b in enumerate(BONES_ALL)}
NV = len(full_w)
WM = np.zeros((NV, len(BONES_ALL)))
for i, W in enumerate(full_w):
    for b, w in W.items():
        WM[i, BIDX[b]] = w
ADJ = [set() for _ in range(NV)]
for poly in outfit.data.polygons:
    vs = list(poly.vertices)
    for k in range(len(vs)):
        a_, b_ = vs[k], vs[(k + 1) % len(vs)]
        ADJ[a_].add(b_); ADJ[b_].add(a_)
TR_MAIN = {T_TR_PEL, T_TR_LEG_L, T_TR_LEG_R, T_TR_IN}
KNEE_IT = int(([a[5:] for a in ARGS if a.startswith('knee=')] or ['10'])[0])


def harmonic(mask_free, allowed, iters, alpha=1.0):
    """Jacobi smoothing of WM rows in mask_free, neighbours restricted to 'allowed' verts."""
    free = [i for i in range(NV) if mask_free[i]]
    if not free:
        return
    sub = sorted({j for i in free for j in ADJ[i] if allowed[j]} | set(free))
    loc = {v: k for k, v in enumerate(sub)}
    A = np.zeros((len(sub), len(sub)))
    for i in free:
        nb = [j for j in ADJ[i] if allowed[j]]
        if not nb:
            continue
        for j in nb:
            A[loc[i], loc[j]] = 1.0 / len(nb)
    fr = np.array([loc[i] for i in free])
    X = WM[sub].copy()
    for _ in range(iters):
        Y = A @ X
        X[fr] = (1 - alpha) * X[fr] + alpha * Y[fr]
    WM[sub] = X


allowed_tr = [tags[i] in TR_MAIN for i in range(NV)]


def seat_free(i):
    p = REST_W[i]
    if tags[i] not in TR_MAIN:
        return False
    th_ = math.atan2(p.y, p.x)
    return 0.775 < p.z < z_top(th_) - 0.046 - 0.030 * max(0.0, -math.sin(th_)) ** 2


# 1) seat / hip band (no body surface there): harmonic pelvis -> thigh blend, spreads the stretch
SEAT_FREE = [seat_free(i) for i in range(NV)]
harmonic(SEAT_FREE, allowed_tr, 400)
for i in range(NV):
    if SEAT_FREE[i] or (tags[i] in TR_MAIN and 0.70 < REST_W[i].z < 0.80):
        for sd in 'lr':
            for tw in ('thigh_twist_01_' + sd, 'thigh_twist_02_' + sd):
                if tw in BIDX and ('thigh_' + sd) in BIDX:
                    WM[i, BIDX['thigh_' + sd]] += WM[i, BIDX[tw]]
                    WM[i, BIDX[tw]] = 0.0


# 2) back of the knee: soften so the cloth bridges the fold instead of following the crease
def knee_back_free(i):
    p = REST_W[i]
    if tags[i] not in (T_TR_LEG_L, T_TR_LEG_R):
        return False
    c = leg_center(1 if p.x > 0 else -1, p.z)
    return 0.40 < p.z < 0.63 and (p.y - c.y) > 0.012


KNEE_W = float(([a[6:] for a in ARGS if a.startswith('kneew=')] or ['0'])[0])
if KNEE_W > 0:
    # clean thigh->calf blend along the leg behind the knee (keeps each family's corrective mix)
    CALF_C = [BIDX[b] for b in BONES_ALL if b.startswith('calf')]
    THIGH_C = [BIDX[b] for b in BONES_ALL if b.startswith('thigh')]
    for i in range(NV):
        if not knee_back_free(i):
            continue
        p = REST_W[i]
        sd_ = 'l' if p.x > 0 else 'r'
        zk = B['calf_' + sd_].z
        f = smoothstep(zk + KNEE_W, zk - KNEE_W, p.z)
        wc = WM[i, CALF_C].copy(); wt = WM[i, THIGH_C].copy()
        wc = wc / wc.sum() if wc.sum() > 1e-6 else None
        wt = wt / wt.sum() if wt.sum() > 1e-6 else None
        if wc is None:
            wc = np.zeros(len(CALF_C)); wc[CALF_C.index(BIDX['calf_' + sd_])] = 1.0
        if wt is None:
            wt = np.zeros(len(THIGH_C)); wt[THIGH_C.index(BIDX['thigh_twist_02_' + sd_] if ('thigh_twist_02_' + sd_) in BIDX else BIDX['thigh_' + sd_])] = 1.0
        WM[i] = 0.0
        WM[i, CALF_C] = f * wc
        WM[i, THIGH_C] = (1 - f) * wt
harmonic([knee_back_free(i) for i in range(NV)], allowed_tr, KNEE_IT, 1.0)

# 3) trouser details, belt and the tucked shirt copy the (smoothed) trouser shell weights
TRI_TR = [tuple(poly.vertices) for poly in outfit.data.polygons if all(allowed_tr[v] for v in poly.vertices)]
TR_BVH = BVHTree.FromPolygons(REST_W, TRI_TR)
from mathutils.interpolate import poly_3d_calc


def shell_weights(p):
    loc, n, fi, d = TR_BVH.find_nearest(p, 0.2)
    if loc is None:
        return None
    tri = TRI_TR[fi]
    bw = poly_3d_calc([REST_W[v] for v in tri], loc)
    return sum(WM[v] * w for v, w in zip(tri, bw))


for i in range(NV):
    t = tags[i]
    p = REST_W[i]
    if t in (T_TR_DET, T_BELT, T_BUCKLE):
        sw = shell_weights(p)
        if sw is not None:
            WM[i] = sw
    elif t == T_SHIRT:
        zt = z_top(math.atan2(p.y, p.x))
        b = 1 - smoothstep(zt - 0.004, zt + 0.035, p.z)
        if b > 0:
            sw = shell_weights(p)
            if sw is not None:
                WM[i] = WM[i] * (1 - b) + sw * b

# 4) limit to MAX_INFL influences, normalise
final_w = []
for i in range(NV):
    row = WM[i]
    idx = np.argsort(-row)[:MAX_INFL]
    items = [(BONES_ALL[k], float(row[k])) for k in idx if row[k] > 1e-4]
    tot = sum(w for _, w in items)
    final_w.append([(b, w / tot) for b, w in items if w / tot > 1e-4])
# rewrite vertex groups
for g in list(outfit.vertex_groups):
    outfit.vertex_groups.remove(g)
needed = sorted({b for fw in final_w for b, _ in fw})
missing = [b for b in needed if b not in arm.data.bones]
assert not missing, missing
VG = {b: outfit.vertex_groups.new(name=b) for b in needed}
for i, fw in enumerate(final_w):
    for b, w in fw:
        VG[b].add([i], w, 'REPLACE')
MAXI = max(len(v.groups) for v in outfit.data.vertices)
log("weights written: groups", len(needed), "max influences", MAXI)
am = outfit.modifiers.new("Armature", 'ARMATURE')
am.object = arm
am.use_vertex_groups = True

# ============================================================================= pose tests
VERT_TAGS = tags
OUT_POLYS = [tuple(p.vertices) for p in outfit.data.polygons]
POLY_TAG = [VERT_TAGS[p[0]] for p in OUT_POLYS]


def reset_pose():
    for pb in arm.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()


def rot_world(bn, axis, deg):
    pb = arm.pose.bones[bn]
    bpy.context.view_layer.update()
    M = pb.matrix.copy(); h = M.to_translation()
    R = Matrix.Rotation(math.radians(deg), 4, axis)
    pb.matrix = Matrix.Translation(h) @ R @ Matrix.Translation(-h) @ M
    bpy.context.view_layer.update()


def aim(bn, child, target):
    pb = arm.pose.bones[bn]; bpy.context.view_layer.update()
    h = pb.head.copy(); c = arm.pose.bones[child].head.copy()
    q = (c - h).normalized().rotation_difference(Vector(target).normalized())
    pb.matrix = Matrix.Translation(h) @ q.to_matrix().to_4x4() @ Matrix.Translation(-h) @ pb.matrix
    bpy.context.view_layer.update()


def seated_pose():
    reset_pose()
    rot_world('spine_01', 'X', 7)
    rot_world('spine_03', 'X', 4)
    for sd, sg in (('l', 1), ('r', -1)):
        rot_world('thigh_' + sd, 'X', -86)
        rot_world('calf_' + sd, 'X', 87)
        rot_world('foot_' + sd, 'X', -1)
        aim('upperarm_' + sd, 'lowerarm_' + sd, (0.16 * sg, -0.46, -0.87))
        aim('lowerarm_' + sd, 'hand_' + sd, (-0.22 * sg, -0.97, -0.06))


def evaluated_world(obj):
    V, P = mesh_world(obj, evaluated=True)
    return V, P


def coverage_sets():
    """body vertices that must stay inside a garment (rest pose definition)."""
    sets = {'arm_l': [], 'arm_r': [], 'leg_l': [], 'leg_r': [], 'foot_l': [], 'foot_r': []}
    for i, p in enumerate(BV):
        sd = 'l' if p.x > 0 else 'r'
        t, rad = arm_param(sd, p)
        if 0.44 <= t <= F_HEM - 0.035 and rad < 0.1:
            sets['arm_' + sd].append(i)
        elif 0.12 <= p.z <= 0.765 and t > 1.2 or (0.12 <= p.z <= 0.765 and abs(p.x) < 0.25 and p.z < 0.8):
            if p.z <= 0.765: sets['leg_' + sd].append(i)
        elif p.z < 0.04:
            sets['foot_' + sd].append(i)
    return sets


COVER = coverage_sets()
COVER_TAGS = {'arm_l': {T_SLV_L}, 'arm_r': {T_SLV_R}, 'leg_l': {T_TR_LEG_L, T_TR_PEL}, 'leg_r': {T_TR_LEG_R, T_TR_PEL},
              'foot_l': {T_SHOE_L}, 'foot_r': {T_SHOE_R}}


def check(state):
    bpy.context.view_layer.update()
    BVp, BPp = evaluated_world(body)
    OV, OP = evaluated_world(outfit)
    dg = bpy.context.evaluated_depsgraph_get()
    be = body.evaluated_get(dg); bme = be.to_mesh()
    R3 = body.matrix_world.to_3x3()
    BN = [(R3 @ v.normal).normalized() for v in bme.vertices]
    be.to_mesh_clear()
    res = {}
    worst = []
    for key, idxs in COVER.items():
        polys = [p for p, t in zip(OP, POLY_TAG) if t in COVER_TAGS[key]]
        bvh = BVHTree.FromPolygons(OV, polys)
        pokes = 0; close = 0; mind = 1e9
        for i in idxs:
            b = BVp[i]
            loc, n, _, d = bvh.find_nearest(b, 0.3)
            if loc is None: continue
            sd = (b - loc).dot(n)
            clr = d if sd < 0 else -d          # true distance, signed by the face side
            if clr <= 0.0:
                # nearest-face sign is ambiguous at creases/corners: confirm with a ray along the skin normal
                h = bvh.ray_cast(b + BN[i] * 1e-4, BN[i], 0.12)
                if h[0] is not None and h[1].dot(BN[i]) > 0:
                    clr = h[3]
            if clr < mind: mind = clr; mloc = BV[i]
            if clr <= 0.0: pokes += 1; worst.append((clr, key, i))
            elif clr < 0.006: close += 1; worst.append((clr, key, i))
        res[key] = (len(idxs), pokes, close, mind * 100)
        log("      min clearance %-7s %.2f cm at" % (key, mind * 100), [round(x, 3) for x in mloc])
    # garment vs garment: tucked shirt inside trousers, trousers outside shoes, belt outside trousers
    def gg(src_tags, src_filter, dst_tags, want_inside):
        polys = [p for p in OP if all(VERT_TAGS[v] in dst_tags for v in p)]   # outer shell only (no linings)
        bvh = BVHTree.FromPolygons(OV, polys)
        bad = 0; n_ = 0; mind = 1e9
        for i, t in enumerate(VERT_TAGS):
            if t in src_tags and src_filter(REST_W[i]):
                loc, nn, _, d = bvh.find_nearest(OV[i], 0.1)
                if loc is None: continue
                n_ += 1
                sd = (OV[i] - loc).dot(nn)
                m = -sd if want_inside else sd
                mind = min(mind, m)
                if m <= 0:
                    bad += 1
                    if bad <= 3: log("      gg bad", sorted(src_tags), [round(x, 3) for x in REST_W[i]], round(m * 100, 2))
        return (n_, bad, mind * 100)
    res['shirt_in_trousers'] = gg({T_SHIRT}, lambda p: p.z < z_top(math.atan2(p.y, p.x)) - 0.006, {T_TR_PEL}, True)
    res['belt_over_trousers'] = gg({T_BELT}, lambda p: True, {T_TR_PEL}, False)
    res['trousers_over_shoes_l'] = gg({T_TR_LEG_L}, lambda p: p.z < 0.11, {T_SHOE_L}, False)
    res['trousers_over_shoes_r'] = gg({T_TR_LEG_R}, lambda p: p.z < 0.11, {T_SHOE_R}, False)
    for k, v in res.items():
        log("CHECK %-8s %-22s" % (state, k), v)
    return res, sorted(worst)[:10]


reset_pose()
REST_CHECK = check("rest")
for w in REST_CHECK[1]: log("  worst rest", w[1], round(w[0]*100,2), [round(x,3) for x in BV[w[2]]])
seated_pose()
SEAT_CHECK = check("seated")
for w in SEAT_CHECK[1]: log("  worst seated", w[1], round(w[0]*100,2), [round(x,3) for x in BV[w[2]]])
# stretch: max relative edge length change in seated pose
OVs, _ = evaluated_world(outfit)
mx_st = 0.0; mx_e = None
for p in OUT_POLYS:
    for k in range(3):
        a, b_ = p[k], p[(k + 1) % 3]
        l0 = (REST_W[a] - REST_W[b_]).length
        if l0 > 1e-5:
            r = (OVs[a] - OVs[b_]).length / l0
            if abs(r - 1) > mx_st: mx_st = abs(r - 1); mx_e = (VERT_TAGS[a], r, REST_W[a])
log("seated max edge stretch", round(mx_st, 3), mx_e)
ST = []
for p in OUT_POLYS:
    for k in range(3):
        a, b_ = p[k], p[(k + 1) % 3]
        l0 = (REST_W[a] - REST_W[b_]).length
        if l0 > 1e-5:
            ST.append(((OVs[a] - OVs[b_]).length / l0, VERT_TAGS[a], tuple(round(x, 3) for x in REST_W[a]), tuple(round(x, 3) for x in REST_W[b_])))
ST.sort(reverse=True)
for e in ST[:12]: log("  stretch", round(e[0], 2), e[1:])
log("  edges >1.6x:", sum(1 for e in ST if e[0] > 1.6), " <0.5x:", sum(1 for e in ST if e[0] < 0.5))

# ============================================================================= previews
def setup_render():
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_WORKBENCH'
    sh = sc.display.shading
    sh.light = 'STUDIO'
    sh.color_type = 'MATERIAL'
    sh.show_cavity = True
    sh.cavity_type = 'BOTH'
    sh.curvature_ridge_factor = 1.0
    sh.curvature_valley_factor = 1.0
    sh.show_backface_culling = True
    sh.show_specular_highlight = True
    sc.view_settings.view_transform = 'Standard'
    w = bpy.data.worlds.new("Preview"); w.color = (0.62, 0.64, 0.67); sc.world = w
    skin = bpy.data.materials.new("Skin"); skin.diffuse_color = (0.55, 0.38, 0.30, 1)
    body.data.materials.clear(); body.data.materials.append(skin)


def render(name, target, dist, az, el, lens=55, res=(900, 1200)):
    if ONLY and not any(name.startswith(o) for o in ONLY):
        return None
    sc = bpy.context.scene
    sc.render.resolution_x, sc.render.resolution_y = res
    cam_d = bpy.data.cameras.new(name); cam_d.lens = lens; cam_d.clip_start = 0.05
    cam = bpy.data.objects.new(name, cam_d); sc.collection.objects.link(cam)
    t = Vector(target)
    a, e = math.radians(az), math.radians(el)
    # az 0 = in front of the character (character faces -Y)
    loc = t + Vector((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e))) * dist
    cam.location = loc
    cam.rotation_euler = (t - loc).to_track_quat('-Z', 'Y').to_euler()
    sc.camera = cam
    path = os.path.join(PREV, name + ".png")
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    bpy.data.objects.remove(cam, do_unlink=True)
    return path


PREVIEWS = []  # None entries filtered at the end
if DO_RENDER:
    log("rendering previews")
    setup_render()
    reset_pose()
    PREVIEWS.append(render("01_front", (0, 0, 0.82), 3.1, 0, 4))
    PREVIEWS.append(render("02_three_quarter", (0, 0, 0.82), 3.1, 38, 8))
    PREVIEWS.append(render("03_back", (0, 0, 0.82), 3.1, 180, 6))
    PREVIEWS.append(render("04_side", (0, 0, 0.82), 3.1, 90, 4))
    PREVIEWS.append(render("05_closeup_collar_badge", (0.03, -0.05, 1.33), 0.85, 22, 8, res=(1000, 900)))
    PREVIEWS.append(render("06_closeup_belt_waist", (0.0, -0.05, 0.98), 0.9, 30, 10, res=(1000, 800)))
    PREVIEWS.append(render("07_closeup_shoes", (0.0, -0.06, 0.08), 0.95, 35, 18, res=(1000, 700)))
    PREVIEWS.append(render("07b_closeup_shoes_inner", (-0.07, -0.03, 0.07), 0.45, 25, 12, res=(1000, 800)))
    PREVIEWS.append(render("08_closeup_shoulder_sleeve", (0.22, 0.0, 1.30), 0.75, 70, 10, res=(900, 900)))
    PREVIEWS.append(render("09_closeup_shoulders_front", (0.0, 0.0, 1.36), 1.0, 0, 6, res=(1100, 800)))
    seated_pose()
    PREVIEWS.append(render("10_seated_three_quarter", (0, -0.2, 0.85), 3.0, 40, 10))
    PREVIEWS.append(render("11_seated_side", (0, -0.2, 0.85), 3.0, 90, 5))
    PREVIEWS.append(render("12_seated_front", (0, -0.2, 0.85), 3.0, 0, 12))
    PREVIEWS.append(render("13_seated_back_low", (0, -0.2, 0.85), 3.0, 200, -5))
    PREVIEWS.append(render("14_seated_closeup_hips_knees", (0.1, -0.3, 0.88), 1.3, 60, 25, res=(1000, 900)))
    PREVIEWS.append(render("15_seated_closeup_shoulders_back", (0.0, 0.0, 1.30), 1.1, 160, 15, res=(1100, 900)))
    PREVIEWS.append(render("16_seated_closeup_seat", (0.0, 0.0, 0.75), 1.2, 135, -10, res=(1000, 900)))
    PREVIEWS.append(render("19_seated_closeup_crotch", (0.0, -0.20, 0.86), 0.9, 0, 15, res=(1000, 900)))
    PREVIEWS.append(render("17_seated_closeup_knee_under", (0.0, -0.40, 0.84), 1.1, 150, -35, res=(1000, 900)))
    PREVIEWS.append(render("18_seated_closeup_knee_side", (0.12, -0.42, 0.86), 0.9, 95, -5, res=(1000, 900)))
    reset_pose()

# ============================================================================= export
reset_pose()
arm.data.pose_position = 'REST'
bpy.context.view_layer.update()
if 'tag' in outfit.data.attributes:
    outfit.data.attributes.remove(outfit.data.attributes['tag'])
REF = [outfit.matrix_world @ v.co for v in outfit.data.vertices]
REF_BONES = {b.name: (arm.matrix_world @ b.head_local, arm.matrix_world @ b.tail_local) for b in arm.data.bones}
# posed reference for the skinning round-trip
arm.data.pose_position = 'POSE'
seated_pose()
REF_POSED, _ = evaluated_world(outfit)
reset_pose()
arm.data.pose_position = 'REST'
bpy.context.view_layer.update()

if DO_EXPORT:
    log("exporting", FBX_OUT)
    bpy.ops.object.select_all(action='DESELECT')
    arm.select_set(True); outfit.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.export_scene.fbx(
        filepath=FBX_OUT, use_selection=True, object_types={'ARMATURE', 'MESH'},
        add_leaf_bones=False, primary_bone_axis='Y', secondary_bone_axis='X',
        armature_nodetype='NULL', bake_anim=False, use_armature_deform_only=False,
        apply_scale_options='FBX_SCALE_NONE', global_scale=1.0, apply_unit_scale=True,
        axis_forward='Y', axis_up='Z', mesh_smooth_type='FACE', use_mesh_modifiers=False,
        use_tspace=False, embed_textures=False, path_mode='AUTO')

    # ------------------------------------------------------------------ round-trip verify
    log("verifying round-trip in a fresh scene")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=BODY_FBX)
    body_objs = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=FBX_OUT)
    new_objs = [o for o in bpy.data.objects if o not in body_objs]
    b_arm = [o for o in body_objs if o.type == 'ARMATURE'][0]
    b_mesh = [o for o in body_objs if o.type == 'MESH'][0]
    g_arm = [o for o in new_objs if o.type == 'ARMATURE'][0]
    g_mesh = [o for o in new_objs if o.type == 'MESH']
    log("reimported objects:", [(o.name, o.type) for o in new_objs])
    assert len(g_mesh) == 1, g_mesh
    g_mesh = g_mesh[0]
    bpy.context.view_layer.update()
    names_b = {b.name for b in b_arm.data.bones}; names_g = {b.name for b in g_arm.data.bones}
    log("bones body %d garment %d  missing %s  extra %s" % (len(names_b), len(names_g), sorted(names_b - names_g)[:5], sorted(names_g - names_b)[:5]))
    bone_off = 0.0
    for b in g_arm.data.bones:
        if b.name in b_arm.data.bones:
            hb = b_arm.matrix_world @ b_arm.data.bones[b.name].head_local
            hg = g_arm.matrix_world @ b.head_local
            bone_off = max(bone_off, (hb - hg).length)
    GV = [g_mesh.matrix_world @ v.co for v in g_mesh.data.vertices]
    if len(GV) == len(REF):
        v_off = max((a - b).length for a, b in zip(GV, REF))
    else:
        from mathutils.kdtree import KDTree
        kd = KDTree(len(GV))
        for i, p in enumerate(GV): kd.insert(p, i)
        kd.balance()
        v_off = max(kd.find(p)[2] for p in REF)
    infl = max(len([g for g in v.groups if g.weight > 1e-6]) for v in g_mesh.data.vertices)
    tris = sum(len(p.vertices) - 2 for p in g_mesh.data.polygons)
    slots = [m.name if m else None for m in g_mesh.data.materials]
    # rest-pose clearance against the original body after round trip
    BVr, BPr = mesh_world(b_mesh)
    # posed round-trip: pose the re-imported garment armature like the build
    arm = g_arm
    seated_pose()
    GVp, _ = mesh_world(g_mesh)
    posed_off = max((a - b).length for a, b in zip(GVp, REF_POSED)) if len(GVp) == len(REF_POSED) else -1
    reset_pose()
    log("ROUNDTRIP vertex max offset %.5f cm | bone max offset %.5f cm | posed (seated) max offset %.5f cm"
        % (v_off * 100, bone_off * 100, posed_off * 100))
    log("ROUNDTRIP tris %d  max influences %d  slots %s  mesh name %s  body objects untouched %s"
        % (tris, infl, slots, g_mesh.name, b_mesh.name))
    print("RESULT_JSON", {"tris": tris, "max_infl": infl, "roundtrip_cm": v_off * 100, "bone_cm": bone_off * 100,
                          "posed_cm": posed_off * 100, "slots": slots, "previews": [p for p in PREVIEWS if p],
                          "rest": REST_CHECK[0], "seated": SEAT_CHECK[0]})
log("done")
