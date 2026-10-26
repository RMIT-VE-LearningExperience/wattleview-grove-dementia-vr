# build_maria_outfit.py
# Headless Blender 5.0 build of Maria's placeholder day clothes (82, aged care):
#   oatmeal knitted cardigan (buttoned, V-neck, 3/4 sleeves with ribbed cuffs, ribbed hem, patch
#   pockets), floral blouse visible at the neckline (yoke + Peter Pan collar + placket), navy mid-calf
#   A-line skirt (+ hidden lining shorts that close the skirt interior), brown slip-on comfort shoes.
# Skinned to the MetaHuman body skeleton (metahuman_base_skel) from the exported body FBX.
#
# Run:
#   "C:\Program Files\Blender Foundation\Blender 5.0\blender.exe" -b --factory-startup --python build_maria_outfit.py
# Optional args after "--":  norender  noexport
#
# NOTE: the input body is a UE-Optimized MetaHuman body: faces hidden by the default
# T-shirt/shorts were removed (no torso, no upper arms above z~1.15, no thighs above z~0.64).
# The torso is therefore a parametric proxy built from the skeleton; weights for the missing
# region are a procedural field. Where the body exists, weights come from the body via a Data
# Transfer modifier (nearest face interpolated); the skirt blends both legs' body weights.

import bpy, bmesh, math, os, sys, time
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree
from mathutils.interpolate import poly_3d_calc

ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
DO_RENDER = 'norender' not in ARGS
DO_EXPORT = 'noexport' not in ARGS

NAME = "Maria"
ROOT = r"D:\Unreal-Projects\WattleviewGrove-ue58\SourceArt\Characters"
BODY_FBX = os.path.join(ROOT, "Bodies", "SKM_%s_BodyMesh.fbx" % NAME)
OUT = os.path.join(ROOT, "Garments", NAME)
PREV = os.path.join(OUT, "Previews")
FBX_OUT = os.path.join(OUT, "SKM_%s_Outfit.fbx" % NAME)
OUTFIT = "SKM_%s_Outfit" % NAME
SLOTS = ["M_Cardigan", "M_Blouse", "M_Skirt", "M_Shoes"]
M_CARD, M_BLOUSE, M_SKIRT, M_SHOES = range(4)
PREVIEW_COLORS = {"M_Cardigan": (0.66, 0.56, 0.40), "M_Blouse": (0.72, 0.34, 0.40),
                  "M_Skirt": (0.028, 0.045, 0.12), "M_Shoes": (0.075, 0.042, 0.025)}
UVS = 2.0           # UV units per metre -> one texture tile = 50 cm
MAX_INFL = 4

T_CARD, T_SLV_L, T_SLV_R, T_CARD_DET, T_CARD_IN, T_SLV_IN = 1, 2, 3, 4, 5, 17
T_BLOUSE, T_COLLAR, T_BL_IN, T_BL_DET = 6, 7, 8, 9
T_SKIRT, T_SK_IN, T_SK_WB = 10, 11, 12
T_SLIP, T_SLIP_L, T_SLIP_R, T_SLIP_IN = 13, 14, 15, 16
T_SHOE_L, T_SHOE_R, T_SHOE_IN = 30, 31, 32
SKIRT_TAGS = {T_SKIRT, T_SK_IN, T_SK_WB}
SLIP_TAGS = {T_SLIP, T_SLIP_L, T_SLIP_R, T_SLIP_IN}
SHOE_TAGS = {T_SHOE_L, T_SHOE_R, T_SHOE_IN}

os.makedirs(PREV, exist_ok=True)
T0 = time.time()


def log(*a):
    print("[MARIA %6.1fs]" % (time.time() - T0), *a, flush=True)


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
    for f in faces:
        if not f.is_valid: continue
        f.normal_update()
        if f.normal.dot(outward_fn(f.calc_center_median())) < 0:
            f.normal_flip()


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
    loc, n, i, d = bvh.find_nearest(p, max_search)
    if loc is None:
        return p, None
    sd = (p - loc).dot(n)
    if sd < min_d:
        return p + n * (min_d - sd), sd
    return p, sd


def disc(part, center, n, radius, thick, tag, sides=8, mat=None):
    n = n.normalized()
    t1 = n.cross(Vector((0, 0, 1)))
    if t1.length < 1e-6: t1 = n.cross(Vector((1, 0, 0)))
    t1.normalize(); t2 = n.cross(t1)
    ring = [(t1 * math.cos(2 * math.pi * k / sides) + t2 * math.sin(2 * math.pi * k / sides)) for k in range(sides)]
    bot = [center + d * radius for d in ring]
    top = [center + n * thick + d * radius for d in ring]
    rim = [center + n * (thick * 1.35) + d * radius * 0.55 for d in ring]
    Vb = [part.vert(p, tag) for p in bot]; Vt = [part.vert(p, tag) for p in top]; Vr = [part.vert(p, tag) for p in rim]
    fs = []
    for k in range(sides):
        k2 = (k + 1) % sides
        fs.append(part.face([Vb[k], Vb[k2], Vt[k2], Vt[k]], [(0.9, 0.9)] * 4, mat))
        fs.append(part.face([Vt[k], Vt[k2], Vr[k2], Vr[k]], [(0.9, 0.9)] * 4, mat))
    fs.append(part.face(Vr, [(0.9 + 0.01 * d.x, 0.9 + 0.01 * d.y) for d in ring], mat))
    fs = [f for f in fs if f]
    orient_faces(fs, lambda p, c=center: p - (c - n * 0.01))
    return fs


def ray_front(bvh, x, z, y0=-0.6):
    hit = bvh.ray_cast(Vector((x, y0, z)), Vector((0, 1, 0)), 1.0)
    return hit[0], hit[1]


def lin_keys(keys, z):
    ks = sorted(keys)
    if z <= ks[0][0]: return ks[0][1:]
    if z >= ks[-1][0]: return ks[-1][1:]
    for a, b in zip(ks, ks[1:]):
        if a[0] <= z <= b[0]:
            t = (z - a[0]) / (b[0] - a[0])
            return tuple(lerp(a[i], b[i], t) for i in range(1, len(a)))


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


def bezier(p0, p1, p2, p3, t):
    a = 1 - t
    return p0 * a ** 3 + p1 * (3 * a * a * t) + p2 * (3 * a * t * t) + p3 * t ** 3


def surf_normal(fn, u, th, du=0.002, dth=0.01):
    pu = fn(u + du, th) - fn(u - du, th)
    pt = fn(u, th + dth) - fn(u, th - dth)
    n = pt.cross(pu)
    if n.length < 1e-12:
        return Vector((0, 0, 1))
    return n.normalized()


# ============================================================================= body data
arm, body = setup_scene()
B = {b.name: bone_head(arm, b.name) for b in arm.data.bones}
BV, BP = mesh_world(body)
BTRI = []
for p in BP:
    for k in range(1, len(p) - 1):
        BTRI.append((p[0], p[k], p[k + 1]))
side_polys = {'l': [], 'r': []}
leg_tris = {'l': [], 'r': []}
for t in BTRI:
    c = (BV[t[0]] + BV[t[1]] + BV[t[2]]) / 3
    s = 'l' if c.x > 0 else 'r'
    side_polys[s].append(t)
    if c.z < 0.70:
        leg_tris[s].append(t)
BODY_SIDE = {s: BVHTree.FromPolygons(BV, side_polys[s]) for s in 'lr'}
LEG_BVH = {s: BVHTree.FromPolygons(BV, leg_tris[s]) for s in 'lr'}
BEDGES = set()
for p in BP:
    for k in range(len(p)):
        a, b = p[k], p[(k + 1) % len(p)]
        BEDGES.add((min(a, b), max(a, b)))
BEDGES = list(BEDGES)
bgn = {g.index: g.name for g in body.vertex_groups}
BW = [{bgn[g.group]: g.weight for g in v.groups if g.weight > 1e-5} for v in body.data.vertices]
log("body verts", len(BV), "tris", len(BTRI))


def slice_pts(co, no, filt):
    out = []
    for a, b in BEDGES:
        pa, pb = BV[a], BV[b]
        da = (pa - co).dot(no); db = (pb - co).dot(no)
        if da * db < 0:
            p = pa + (pb - pa) * (da / (da - db))
            if filt(p): out.append(p)
    return out


# ============================================================================= proxy torso
Z_S = 1.205          # top of the "vertical" torso; above it the shoulder dome
DL = 0.075           # parameter length of the dome (u = Z_S .. Z_S + DL)
U_NECK = Z_S + DL
TORSO_KEYS = [  # z, half-width, front y, back y, superellipse exponent   (elderly female)
    (0.66, 0.183, -0.090, 0.112, 2.3),
    (0.72, 0.189, -0.096, 0.122, 2.3),
    (0.78, 0.187, -0.102, 0.124, 2.4),
    (0.84, 0.178, -0.110, 0.114, 2.4),
    (0.90, 0.168, -0.116, 0.098, 2.4),
    (0.95, 0.158, -0.117, 0.088, 2.3),
    (1.00, 0.152, -0.122, 0.084, 2.3),
    (1.05, 0.153, -0.134, 0.090, 2.3),
    (1.09, 0.150, -0.132, 0.096, 2.4),
    (1.13, 0.146, -0.118, 0.100, 2.5),
    (1.17, 0.142, -0.100, 0.100, 2.5),
    (1.205, 0.137, -0.080, 0.094, 2.5),
]
NECK_C = (0.0, 0.008)
NECK_R = (0.060, 0.058)


def neckline(th):
    s = math.sin(th)
    x = NECK_C[0] + NECK_R[0] * math.cos(th)
    y = NECK_C[1] + NECK_R[1] * s
    z = 1.258 + 0.010 * max(0.0, s) - 0.024 * max(0.0, -s) ** 2
    return Vector((x, y, z))


def torso_point(u, th):
    if u <= Z_S:
        a, yf, yb, n = interp_keys(TORSO_KEYS, u)
        x, y = superellipse(th, a, yf, yb, n)
        return Vector((x, y, u))
    t = (u - Z_S) / DL
    P0 = torso_point(Z_S, th)
    d = (P0 - torso_point(Z_S - 0.01, th)).normalized()
    side = abs(math.cos(th)) ** 1.5
    P1 = P0 + d * (0.016 + 0.034 * side)
    N = neckline(th)
    radial = Vector((N.x - NECK_C[0], N.y - NECK_C[1], 0)).normalized()
    P2 = N + radial * (0.005 + 0.060 * side) + Vector((0, 0, -(0.016 - 0.012 * side)))
    return bezier(P0, P1, P2, N, t)


def torso_n(u, th): return surf_normal(torso_point, u, th)


parts = {}

# ============================================================================= arms (frames)
ARM = {}
for sd, sg in (('l', 1), ('r', -1)):
    S = B['upperarm_' + sd]; E = B['lowerarm_' + sd]; H = B['hand_' + sd]
    axU = (E - S).normalized(); LU = (E - S).length
    axF = (H - E).normalized(); LF = (H - E).length

    def cen_off(P0, ax, L, fr, sg=sg):
        offs = []
        for f in fr:
            co = P0 + ax * L * f
            pts = slice_pts(co, ax, lambda p, co=co: p.x * sg > 0.05 and (p - co).length < 0.085)
            if len(pts) >= 6:
                offs.append(sum(pts, Vector()) / len(pts) - co)
        o = sum(offs, Vector()) / max(1, len(offs))
        return o - ax * o.dot(ax)
    offU = cen_off(S, axU, LU, (0.62, 0.72, 0.82))
    offF = cen_off(E, axF, LF, (0.30, 0.45, 0.60, 0.75))
    RB = 0.05
    pts = []
    q = -0.04
    while q < LU - RB - 1e-9:
        pts.append(S + axU * q + offU * smoothstep(-0.05 * LU, 0.35 * LU, q)); q += 0.005
    n_up = len(pts)
    A_ = S + axU * (LU - RB) + offU
    C_ = E + axF * RB + offF
    M_ = E + (offU + offF) * 0.5
    for k in range(1, 20):
        t = k / 20
        pts.append(A_ * (1 - t) ** 2 + M_ * (2 * (1 - t) * t) + C_ * (t * t))
    q = RB
    while q <= 0.85 * LF:
        pts.append(E + axF * q + offF); q += 0.005
    acc = [0.0]
    for i in range(1, len(pts)):
        acc.append(acc[-1] + (pts[i] - pts[i - 1]).length)
    s0 = acc[8]
    acc = [a - s0 for a in acc]
    TT = [(pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized() for i in range(len(pts))]
    u0 = Vector((0, 0, 1)); u0 = (u0 - TT[0] * u0.dot(TT[0])).normalized()
    UU = [u0]
    for i in range(1, len(pts)):
        u = UU[-1] - TT[i] * UU[-1].dot(TT[i]); UU.append(u.normalized())
    kd = KDTree(len(pts))
    for i, p in enumerate(pts): kd.insert(p, i)
    kd.balance()
    S_E = acc[n_up + 9]
    inner = axF - axU
    ARM[sd] = dict(S=S, E=E, H=H, axU=axU, axF=axF, LU=LU, LF=LF, sg=sg, pts=pts, acc=acc, TT=TT, UU=UU,
                   kd=kd, S_E=S_E, inner=inner, offU=offU, offF=offF)
    log("arm", sd, "LU %.3f LF %.3f S_E %.3f" % (LU, LF, S_E), "offU", [round(x, 4) for x in offU], "offF", [round(x, 4) for x in offF])


def arm_frame(sd, s):
    A = ARM[sd]; acc = A['acc']
    if s <= acc[0]:
        c = A['pts'][0] + A['TT'][0] * (s - acc[0])
        T = A['TT'][0]; U = A['UU'][0]
    else:
        i = 0
        while i < len(acc) - 2 and acc[i + 1] < s: i += 1
        t = clamp((s - acc[i]) / max(1e-9, acc[i + 1] - acc[i]))
        c = A['pts'][i].lerp(A['pts'][i + 1], t)
        T = A['TT'][i].lerp(A['TT'][i + 1], t).normalized()
        U = A['UU'][i].lerp(A['UU'][i + 1], t)
    U = (U - T * U.dot(T)).normalized()
    V = T.cross(U).normalized()
    return c, T, U, V


def arm_s(sd, p):
    A = ARM[sd]
    co, i, d = A['kd'].find(p)
    return A['acc'][i], d


def arm_param(sd, p):
    A = ARM[sd]
    d = p - A['S']
    t = d.dot(A['axU']) / A['LU']
    rad = (d - A['axU'] * d.dot(A['axU'])).length
    return t, rad


# ============================================================================= slip (hidden lining shorts)
log("building lining shorts")
slip = Part("Slip", M_SKIRT)
parts['slip'] = slip
N_TS = 24
TH_S = [-math.pi / 2 + 2 * math.pi * j / N_TS for j in range(N_TS)]   # col 0 = centre front
Z_C = 0.705
SLIP_OFF = 0.0035
SLIP_TOP = 0.925


def slip_point(u, th): return torso_point(u, th) + torso_n(u, th) * SLIP_OFF


def leg_slice_center(z, sg):
    pts = slice_pts(Vector((0, 0, z)), Vector((0, 0, 1)), lambda p: p.x * sg > 0.0 and abs(p.x) < 0.3 and p.z < 0.7)
    xs = [p.x for p in pts]; ys = [p.y for p in pts]
    return Vector(((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2))


LEGC = {}
for sd, sg in (('l', 1), ('r', -1)):
    LEGC[sd] = [(z, leg_slice_center(z, sg)) for z in (0.53, 0.56, 0.59, 0.61)]
    log("leg centre", sd, [(z, tuple(round(v, 3) for v in c)) for z, c in LEGC[sd]])


def leg_center(sd, z):
    cs = LEGC[sd]
    if z >= cs[-1][0]: return cs[-1][1]
    if z <= cs[0][0]: return cs[0][1]
    for (z0, c0), (z1, c1) in zip(cs, cs[1:]):
        if z0 <= z <= z1:
            return c0.lerp(c1, (z - z0) / (z1 - z0))


def leg_r(sd, z, phi):
    zz = min(z, 0.61)
    c = leg_center(sd, zz)
    o = Vector((c.x, c.y, zz)); d = Vector((math.cos(phi), math.sin(phi), 0))
    hit = BODY_SIDE[sd].ray_cast(o, d, 0.16)
    if hit[0] is None:
        return None
    return (hit[0] - o).length


pel_us = [Z_C, 0.745, 0.79, 0.835, 0.88, SLIP_TOP]
Vpel = [[slip.vert(slip_point(u, th), T_SLIP) for th in TH_S] for u in pel_us]
Pf, Pb = Vpel[0][0].co, Vpel[0][N_TS // 2].co
chain = [slip.vert(Vector((0.0, lerp(Pf.y, Pb.y, k / 4), Z_C - 0.030 * math.sin(math.pi * k / 4))), T_SLIP) for k in range(1, 4)]
ringL = Vpel[0][0:N_TS // 2 + 1] + chain[::-1]
ringR = Vpel[0][N_TS // 2:] + [Vpel[0][0]] + chain
assert len(ringL) == len(ringR)
NLS = len(ringL)
Z_LEG_S = [0.675, 0.648, 0.618, 0.590, 0.566]
for sd, sg, ring0, tag in (('l', 1, ringL, T_SLIP_L), ('r', -1, ringR, T_SLIP_R)):
    c0 = leg_center(sd, 0.61)
    phis = [math.atan2(v.co.y - c0.y, v.co.x - c0.x) for v in ring0]
    rows = []
    for z in Z_LEG_S:
        R = []
        for phi in phis:
            rb = leg_r(sd, z, phi)
            if rb is None: rb = 0.07
            R.append(rb + 0.0065 + max(0.0, z - 0.61) * 0.30)
        for _ in range(2):
            R = [0.25 * R[j - 1] + 0.5 * R[j] + 0.25 * R[(j + 1) % NLS] for j in range(NLS)]
        c = leg_center(sd, z)
        row = [Vector((c.x + R[j] * math.cos(phi), c.y + R[j] * math.sin(phi), z)) for j, phi in enumerate(phis)]
        if z > 0.66:
            row = [Vector((ring0[j].co.x, ring0[j].co.y, z)).lerp(p, 0.55) for j, p in enumerate(row)]
        rows.append(row)
    for it in range(2):
        for i in range(len(rows)):
            for j in range(NLS):
                rows[i][j], _ = push_out(rows[i][j], BODY_SIDE[sd], 0.0060, 0.05)
    Vleg, f_leg = slip.grid([ring0] + rows, tag)
    seal = []
    zs_ = 0.560
    c = leg_center(sd, zs_)
    for j, phi in enumerate(phis):
        rb = leg_r(sd, zs_, phi) or 0.065
        seal.append(Vector((c.x + (rb + 0.0025) * math.cos(phi), c.y + (rb + 0.0025) * math.sin(phi), zs_)))
    _, f_seal = slip.grid([Vleg[-1], seal], T_SLIP_IN)

    def out_fn(p, sd=sd):
        c = leg_center(sd, p.z)
        return Vector((p.x - c.x, p.y - c.y, 0))
    orient_faces(f_leg, out_fn)
    orient_faces(f_seal, lambda p: Vector((0, 0, -1)))
_, f_pel = slip.grid(Vpel, T_SLIP)
orient_faces(f_pel, lambda p: Vector((p.x, p.y, 0.0)))
SLIP_BVH = bvh_from_faces([f for f in slip.bm.faces])

# ============================================================================= skirt
log("building skirt")
sk = Part("Skirt", M_SKIRT)
parts['skirt'] = sk
N_SK = 36
TH_SK = [-math.pi / 2 + 2 * math.pi * j / N_SK for j in range(N_SK)]
SK_TOP = 0.965
SK_WB = 0.935
SK_HEM = 0.255
SK_KEYS = [  # z, half-width, front y, back y, exponent  (A-line, front kept close for sitting)
    (0.78, 0.203, -0.118, 0.137, 2.3),
    (0.60, 0.208, -0.125, 0.135, 2.2),
    (0.414, 0.230, -0.136, 0.142, 2.1),
    (0.255, 0.262, -0.160, 0.163, 2.05),
]
SK_OFF = 0.0065


def skirt_point(z, th, folds=True):
    pt = torso_point(z, th) + torso_n(z, th) * SK_OFF
    a, yf, yb, n = lin_keys(SK_KEYS, z)
    x, y = superellipse(th, a, yf, yb, n)
    pa = Vector((x, y, z))
    if pa.to_2d().length < pt.to_2d().length:
        pa = Vector((pt.x, pt.y, z))
    b = smoothstep(0.85, 0.74, z)
    p = pt.lerp(pa, b)
    radial = Vector((p.x, p.y, 0)).normalized()
    if folds:
        A = 0.019 * smoothstep(0.76, 0.30, z)
        A *= 0.72 + 0.28 * math.sin(3 * th + 1.0)
        f = math.cos(10 * th + 0.5)
        p = p + radial * (A * math.copysign(abs(f) ** 0.7, f))
    for ths, g in ((0.0, 0.0010), (math.pi, 0.0010), (math.pi / 2, 0.0008)):
        dd = abs(wrap_pi(th - ths))
        p = p - radial * g * max(0.0, 1 - dd / 0.12)
    return p


SK_Z = [SK_TOP, 0.951, 0.937, SK_WB, 0.90, 0.865, 0.83, 0.795, 0.755, 0.71, 0.66, 0.605, 0.545, 0.485,
        0.43, 0.375, 0.325, 0.285, SK_HEM]
SK_EXTRA = {SK_TOP: 0.0014, 0.951: 0.0016, 0.937: 0.0014, SK_WB: -0.0004}
rows = []
for z in SK_Z:
    row = []
    for th in TH_SK:
        p = skirt_point(z, th)
        if z in SK_EXTRA:
            p = p + torso_n(z, th) * SK_EXTRA[z]
        row.append(p)
    rows.append(row)
for it in range(2):
    for i, z in enumerate(SK_Z):
        if z > 0.80: continue
        for j in range(N_SK):
            p = rows[i][j]
            for sd in 'lr':
                p, _ = push_out(p, LEG_BVH[sd], 0.013, 0.06)
            p, _ = push_out(p, SLIP_BVH, 0.006, 0.05)
            rows[i][j] = p
Vsk, f_sk = sk.grid(rows, T_SKIRT)
hem = Vsk[-1]
e_, i0, i1 = [], [], []
for v in hem:
    p = v.co
    d = Vector((p.x, p.y, 0)).normalized()
    e_.append(p + Vector((0, 0, -0.0028)) - d * 0.0018)
    i0.append(p - d * 0.0045)
    i1.append(p - d * 0.0045 + Vector((0, 0, 0.028)))
Vh, f_hem_e = sk.grid([hem, e_], T_SKIRT)
Vhi, f_hem_i = sk.grid([Vh[-1], i0, i1], T_SK_IN)
top = Vsk[0]
r_e, r_i = [], []
for j, th in enumerate(TH_SK):
    n = torso_n(SK_TOP, th)
    p = top[j].co
    r_e.append(p + Vector((0, 0, 0.0018)) - n * 0.0022)
    r_i.append(p - n * 0.0040 - Vector((0, 0, 0.022)))
Vw, f_wb = sk.grid([top, r_e], T_SK_WB)
Vwi, f_wbi = sk.grid([Vw[-1], r_i], T_SK_IN)
orient_faces(f_sk + f_hem_e + f_wb, lambda p: Vector((p.x, p.y, 0)))
orient_faces(f_hem_i + f_wbi, lambda p: -Vector((p.x, p.y, 0)))
SKIRT_BVH = bvh_from_faces(f_sk + f_wb)

# ============================================================================= cardigan torso
log("building cardigan")
card = Part("Cardigan", M_CARD)
parts['card'] = card
N_C = 36
TH_C = [-math.pi / 2 + 2 * math.pi * j / N_C for j in range(N_C)]   # col 0 = centre front
Z_V = 1.10
ALPHA_V = 0.85
U_CTOP = Z_S + 0.88 * DL
Z_HEM = 0.797


def yf_abs(z): return abs(interp_keys(TORSO_KEYS, z)[1])


def card_drape(u, th):
    front = max(0.0, -math.sin(th)) ** 1.5
    if front <= 0 or u >= 1.06: return 0.0
    y0 = yf_abs(u)
    best = 0.0
    for k in range(1, 9):
        z2 = lerp(u, 1.06, k / 8)
        best = max(best, yf_abs(z2) - y0 - 0.30 * (z2 - u))
    return best * front


def card_off(u, th):
    if u > Z_S:
        t = (u - Z_S) / DL
        base = lerp(0.013, 0.0085, smoothstep(0.0, 1.0, t))
    else:
        base = 0.0145 + 0.003 * smoothstep(0.95, 0.83, u) + card_drape(u, th)
        front = max(0.0, -math.sin(th))
        base += 0.0022 * front * smoothstep(1.03, 0.93, u) * math.cos(12 * th + 0.4)
    for ths in (0.0, math.pi):
        dd = abs(wrap_pi(th - ths))
        base -= 0.0012 * max(0.0, 1 - dd / 0.12)
    return base


def card_point(u, th, extra=0.0):
    return torso_point(u, th) + torso_n(u, th) * (card_off(u, th) + extra)


_PT = card_point(U_CTOP, -math.pi / 2 + ALPHA_V)
X_TOP, Z_TOP = abs(_PT.x), _PT.z


def xv(z): return X_TOP * (z - Z_V) / (Z_TOP - Z_V)


def u_top(th):
    a = abs(wrap_pi(th + math.pi / 2))
    if a >= ALPHA_V - 1e-6: return U_CTOP
    if a < 1e-6: return Z_V
    lo, hi = Z_V, U_CTOP
    for _ in range(40):
        mid = 0.5 * (lo + hi); p = card_point(mid, th)
        if abs(p.x) - xv(p.z) > 0: lo = mid
        else: hi = mid
    return 0.5 * (lo + hi)


UTOP = [u_top(th) for th in TH_C]
BAND_Z = [Z_HEM, 0.82, 0.843, 0.847]
BAND_EXTRA = [0.0028, 0.0034, 0.0028, -0.0006]
N_BODY_ROWS = 16
U0 = 0.852
rows = []
for zb, ex in zip(BAND_Z, BAND_EXTRA):
    rows.append([card_point(zb, th, ex + (0.0005 if j % 2 else -0.0003)) for j, th in enumerate(TH_C)])
for i in range(N_BODY_ROWS):
    t = i / (N_BODY_ROWS - 1)
    rows.append([card_point(lerp(U0, UTOP[j], t), th) for j, th in enumerate(TH_C)])
for it in range(2):
    for i in range(len(rows)):
        for j in range(N_C):
            if rows[i][j].z < 0.98:
                rows[i][j], _ = push_out(rows[i][j], SKIRT_BVH, 0.0090, 0.06)
Vc, f_card = card.grid(rows, T_CARD)
hem = Vc[0]
e_, i0, i1 = [], [], []
for j, v in enumerate(hem):
    n = torso_n(Z_HEM, TH_C[j])
    p = v.co
    e_.append(p + Vector((0, 0, -0.003)) - n * 0.0022)
    i0.append(p - n * 0.0045)
    i1.append(p - n * 0.0045 + Vector((0, 0, 0.032)))
Vh, f_che = card.grid([hem, e_], T_CARD)
Vhi, f_chi = card.grid([Vh[-1], i0, i1], T_CARD_IN)
orient_faces(f_card + f_che, lambda p: Vector((p.x, p.y, 0.0)) + Vector((0, 0, max(0.0, p.z - 1.2) * 2)))
orient_faces(f_chi, lambda p: -Vector((p.x, p.y, 0.0)))
CARD_BVH = bvh_from_faces(f_card)

# ----------------------------------------------------------------------------- neckband (V edge)
# built on the analytic cardigan surface: offset perpendicular to the edge in (u, theta) space
NB_W = 0.022


def edge_inward(u, th, tng, dist):
    """param point at 3D distance `dist` from card_point(u, th), perpendicular to tng, inside the cardigan."""
    uu, tt = u, th
    P0 = card_point(u, th)
    for _ in range(3):
        Pu = (card_point(uu + 0.002, tt) - card_point(uu - 0.002, tt)) / 0.004
        Pt = (card_point(uu, tt + 0.004) - card_point(uu, tt - 0.004)) / 0.008
        du, dt = Pt.dot(tng), -Pu.dot(tng)
        d3 = Pu * du + Pt * dt
        if d3.length < 1e-9: break
        k = dist / d3.length
        cand = [(u + du * k, th + dt * k), (u - du * k, th - dt * k)]
        cand.sort(key=lambda c: -(u_top(c[1]) - c[0]))
        uu, tt = cand[0]
        # correct for curvature: rescale so the true 3D distance matches
        L = (card_point(uu, tt) - P0).length
        if L > 1e-6:
            uu = u + (uu - u) * dist / L; tt = th + (tt - th) * dist / L
    return uu, tt


top = Vc[-1]
ob, ot, mt, it_, ib, cen = [], [], [], [], [], []
for j in range(N_C):
    th = TH_C[j]; u = UTOP[j]
    P = top[j].co.copy()
    tng = (top[(j + 1) % N_C].co - top[j - 1].co).normalized()
    n = torso_n(u, th)
    um, tm = edge_inward(u, th, tng, NB_W * 0.5)
    ui, ti = edge_inward(u, th, tng, NB_W)
    a_ = wrap_pi(th + math.pi / 2)
    Pm = card_point(um, tm); Pi = card_point(ui, ti)
    if 0 < abs(a_) < ALPHA_V:          # V edges: keep the band on its own side of the centre line
        sgn = 1 if a_ > 0 else -1
        Pm.x = sgn * max(sgn * Pm.x, 0.004); Pi.x = sgn * max(sgn * Pi.x, 0.007)
    nm = torso_n(um, tm); ni = torso_n(ui, ti)
    w = (Pi - P).normalized()
    ob.append(P - n * 0.0035 - w * 0.0006)
    ot.append(P + n * 0.0030 - w * 0.0010)
    mt.append(Pm + nm * 0.0040)
    it_.append(Pi + ni * 0.0030)
    ib.append(Pi + ni * 0.0002)
    cen.append(Pm - nm * 0.002)
for row, md in ((mt, 0.0034), (it_, 0.0026)):
    for j in range(N_C):
        row[j], _ = push_out(row[j], CARD_BVH, md, 0.03)
Vnb, f_nb = card.grid([ob, ot, mt, it_, ib], T_CARD_DET)
kd_nb = KDTree(N_C)
for j, p in enumerate(cen): kd_nb.insert(p, j)
kd_nb.balance()
orient_faces(f_nb, lambda p: p - kd_nb.find(p)[0])
NB_BVH = bvh_from_faces(f_nb)

# ----------------------------------------------------------------------------- front button band
FB_X = [-0.014, 0.0, 0.014]
FB_Z = [0.800, 0.84, 0.88, 0.92, 0.96, 1.00, 1.035, 1.062, 1.080]
top_v, base_v = [], []
for z in FB_Z:
    trow, brow = [], []
    for x in FB_X:
        h, nn = ray_front(CARD_BVH, x, z)
        if h is None:
            h, nn = ray_front(CARD_BVH, x * 0.5, z - 0.003)
        trow.append(h + nn * (0.0034 + (0.0005 if x == 0 else 0.0)))
        brow.append(h - nn * 0.0006)
    top_v.append(trow); base_v.append(brow)
Vfb, fb_faces = card.grid(top_v, T_CARD_DET, cyclic=False)
L_wall = [[base_v[i][0] for i in range(len(FB_Z))], [Vfb[i][0] for i in range(len(FB_Z))]]
R_wall = [[Vfb[i][2] for i in range(len(FB_Z))], [base_v[i][2] for i in range(len(FB_Z))]]
_, fw1 = card.grid(L_wall, T_CARD_DET, cyclic=False)
_, fw2 = card.grid(R_wall, T_CARD_DET, cyclic=False)
_, fw3 = card.grid([[base_v[0][k] for k in range(3)], Vfb[0]], T_CARD_DET, cyclic=False)
_, fw4 = card.grid([Vfb[-1], [base_v[-1][k] for k in range(3)]], T_CARD_DET, cyclic=False)
fb_all = fb_faces + fw1 + fw2 + fw3 + fw4
orient_faces(fb_all, lambda p: Vector((p.x * 8, -1, -1 if p.z < 0.801 else (1 if p.z > 1.079 else 0))))
FB_BVH = bvh_from_faces(fb_faces)
for zb in (0.835, 0.888, 0.941, 0.994, 1.047):
    h, nn = ray_front(FB_BVH, 0.0, zb)
    disc(card, h + nn * 0.0002, nn, 0.0075, 0.0026, T_CARD_DET, sides=8)

# ----------------------------------------------------------------------------- patch pockets
for sg in (1, -1):
    xs = [sg * x for x in (0.052, 0.085, 0.118, 0.148)]
    zs = [0.856, 0.89, 0.922, 0.926, 0.946]
    lifts = [0.0030, 0.0030, 0.0030, 0.0040, 0.0040]
    ftop, fbase = [], []
    for z, lf in zip(zs, lifts):
        tr_, br_ = [], []
        for x in xs:
            h, nn = ray_front(CARD_BVH, x, z)
            tr_.append(h + nn * lf); br_.append(h - nn * 0.0004)
        ftop.append(tr_); fbase.append(br_)
    Vt, fp = card.grid(ftop, T_CARD_DET, cyclic=False)
    nz, nx = len(zs), len(xs)
    perim_t = [Vt[0][k] for k in range(nx)] + [Vt[i][nx - 1] for i in range(1, nz)] + \
              [Vt[nz - 1][k] for k in range(nx - 2, -1, -1)] + [Vt[i][0] for i in range(nz - 2, 0, -1)]
    perim_b = [fbase[0][k] for k in range(nx)] + [fbase[i][nx - 1] for i in range(1, nz)] + \
              [fbase[nz - 1][k] for k in range(nx - 2, -1, -1)] + [fbase[i][0] for i in range(nz - 2, 0, -1)]
    Vw_, fwall = card.grid([perim_b, perim_t], T_CARD_DET)
    cx = sum(xs) / 4; cz = sum(zs) / 5
    orient_faces(fp + fwall, lambda p, cx=cx, cz=cz: Vector(((p.x - cx) * 6, -1, (p.z - cz) * 6)))

# ============================================================================= blouse
log("building blouse")
bl = Part("Blouse", M_BLOUSE)
parts['blouse'] = bl
N_B = 32
TH_B = [-math.pi / 2 + 2 * math.pi * j / N_B for j in range(N_B)]


def bl_off(u): return 0.005 if u <= Z_S else lerp(0.005, 0.0032, (u - Z_S) / DL)
def bl_point(u, th): return torso_point(u, th) + torso_n(u, th) * bl_off(u)


BL_U = [1.02, 1.06, 1.10, 1.14, 1.175, Z_S, Z_S + 0.3 * DL, Z_S + 0.6 * DL, Z_S + 0.85 * DL, U_NECK]
rows = [[bl_point(u, th) for th in TH_B] for u in BL_U]
Vb, f_bl = bl.grid(rows, T_BLOUSE)
orient_faces(f_bl, lambda p: Vector((p.x, p.y - NECK_C[1], 0.0)) + Vector((0, 0, max(0.0, p.z - 1.2) * 2)))
BL_BVH = bvh_from_faces(f_bl)
top_ring = Vb[-1]
inner = []
for v in top_ring:
    p = v.co
    C = Vector((NECK_C[0], NECK_C[1], p.z - 0.004))
    rh = Vector((p.x - C.x, p.y - C.y, 0)).normalized()
    inner.append(C + rh * 0.046)
_, seal_faces = bl.grid([top_ring, inner], T_BL_IN)
orient_faces(seal_faces, lambda p: Vector((0, 0, 1)))

PLK_X = [-0.008, 0.0, 0.008]
PLK_Z = [1.226, 1.20, 1.17, 1.14, 1.11, 1.08, 1.05]
top_v, base_v = [], []
for z in PLK_Z:
    trow, brow = [], []
    for x in PLK_X:
        h, nn = ray_front(BL_BVH, x, z)
        trow.append(h + nn * (0.0018 + (0.0003 if x == 0 else 0.0)))
        brow.append(h - nn * 0.0002)
    top_v.append(trow); base_v.append(brow)
Vp, plk_faces = bl.grid(top_v, T_BL_DET, cyclic=False)
L_wall = [[base_v[i][0] for i in range(len(PLK_Z))], [Vp[i][0] for i in range(len(PLK_Z))]]
R_wall = [[Vp[i][2] for i in range(len(PLK_Z))], [base_v[i][2] for i in range(len(PLK_Z))]]
_, fw1 = bl.grid(L_wall, T_BL_DET, cyclic=False)
_, fw2 = bl.grid(R_wall, T_BL_DET, cyclic=False)
orient_faces(plk_faces + fw1 + fw2, lambda p: Vector((p.x * 8, -1, 0)))
PLK_BVH = bvh_from_faces(plk_faces)
for zb in (1.208, 1.163, 1.118):
    h, nn = ray_front(PLK_BVH, 0.0, zb)
    disc(bl, h + nn * 0.0001, nn, 0.0042, 0.0015, T_BL_DET, sides=6)

# ============================================================================= sleeves
log("building sleeves")
N_SL = 18


def sleeve_style(sd, s, phi):
    S_E = ARM[sd]['S_E']
    if s <= 0.0: base = 0.060
    elif s <= 0.16: base = lerp(0.060, 0.054, s / 0.16)
    elif s <= S_E: base = lerp(0.054, 0.051, (s - 0.16) / (S_E - 0.16))
    else: base = lerp(0.051, 0.047, clamp((s - S_E) / 0.066))
    asym = -0.006 * (1 - smoothstep(0.02, 0.09, s))
    drape = 0.004 * max(0.0, -math.cos(phi)) ** 2 * smoothstep(0.04, 0.12, s) * (1 - smoothstep(S_E - 0.05, S_E, s))
    return base + asym * math.cos(phi) + drape


SLEEVE_INFO = {}
for sd in 'lr':
    A = ARM[sd]
    S_E = A['S_E']
    tag = T_SLV_L if sd == 'l' else T_SLV_R
    phis = [2 * math.pi * j / N_SL for j in range(N_SL)]
    cE, TE, UE, VE = arm_frame(sd, S_E)
    inn = A['inner'] - TE * A['inner'].dot(TE)
    phi_in = math.atan2(inn.dot(VE), inn.dot(UE))
    S_C0 = S_E + 0.066
    S_C1 = S_E + 0.112
    A['S_C0'] = S_C0; A['S_C1'] = S_C1

    def body_r(s, phi, sd=sd):
        c, T, U, V = arm_frame(sd, s)
        d = U * math.cos(phi) + V * math.sin(phi)
        hit = BODY_SIDE[sd].ray_cast(c, d, 0.12)
        if hit[0] is None: return None
        return (hit[0] - c).length

    def ring(s, style_fn, clr, smooth=2, sd=sd, body_r=body_r, phi_in=phi_in, S_E=S_E, phis=phis):
        c, T, U, V = arm_frame(sd, s)
        R = []
        for phi in phis:
            rs = style_fn(s, phi)
            rb = body_r(s, phi)
            cl = clr + 0.003 * max(0.0, math.cos(phi - phi_in - math.pi)) ** 2 * (1 - smoothstep(0.0, 0.04, abs(s - S_E)))
            R.append(rs if rb is None else max(rs, rb + cl))
        for _ in range(smooth):
            R = [0.25 * R[j - 1] + 0.5 * R[j] + 0.25 * R[(j + 1) % N_SL] for j in range(N_SL)]
        return c, U, V, R
    SLV_S = [-0.03, 0.0, 0.032, 0.064, 0.096, 0.128, 0.16, S_E - 0.05, S_E - 0.028, S_E - 0.010,
             S_E + 0.008, S_E + 0.026, S_E + 0.046, S_C0 - 0.004]
    FOLD_IN = {S_E - 0.028: 0.0045, S_E - 0.010: -0.0008, S_E + 0.008: 0.0050, S_E + 0.026: 0.0012}
    rows = []
    for s in SLV_S:
        c, U, V, R = ring(s, lambda s_, ph, sd=sd: sleeve_style(sd, s_, ph), 0.0115)
        row = []
        for j, phi in enumerate(phis):
            r = R[j]
            w_in = max(0.0, math.cos(phi - phi_in)) ** 2
            r += FOLD_IN.get(s, 0.0) * w_in
            if abs(s - 0.096) < 1e-6: r += 0.0022 * max(0.0, -math.cos(phi)) ** 2
            if abs(s - (S_E + 0.046)) < 1e-6: r += 0.0028 * (0.6 + 0.4 * math.cos(2 * phi + 0.7))
            if abs(s - (S_C0 - 0.004)) < 1e-6: r += 0.0016
            row.append(c + (U * math.cos(phi) + V * math.sin(phi)) * r)
        rows.append(row)
    for j in range(N_SL):
        p = rows[0][j]
        loc, n, _, _ = CARD_BVH.find_nearest(p, 0.2)
        if loc is not None and (p - loc).dot(n) > -0.004:
            rows[0][j] = loc - n * 0.006
    cuff_s = [S_C0, S_C0 + 0.022, S_C1 - 0.003]
    Rc_all = [ring(s, lambda s_, ph: 0.041, 0.0085) for s in cuff_s]
    Rmax = [max(r[3][j] for r in Rc_all) for j in range(N_SL)]
    cuff_rows = []
    for (c, U, V, R) in Rc_all:
        cuff_rows.append([c + (U * math.cos(phi) + V * math.sin(phi)) * (Rmax[j] + (0.0006 if j % 2 else -0.0004))
                          for j, phi in enumerate(phis)])
    c1, _, U1, V1 = arm_frame(sd, S_C1)
    edge = [c1 + (U1 * math.cos(phi) + V1 * math.sin(phi)) * (Rmax[j] - 0.0028) for j, phi in enumerate(phis)]
    ci0, _, Ui0, Vi0 = arm_frame(sd, S_C1 - 0.004)
    ci1, _, Ui1, Vi1 = arm_frame(sd, S_C0 + 0.012)
    in0 = [ci0 + (Ui0 * math.cos(phi) + Vi0 * math.sin(phi)) * (Rmax[j] - 0.0048) for j, phi in enumerate(phis)]
    in1 = [ci1 + (Ui1 * math.cos(phi) + Vi1 * math.sin(phi)) * (Rmax[j] - 0.0048) for j, phi in enumerate(phis)]
    cs_, _, Us, Vs = arm_frame(sd, S_C0 + 0.010)
    seal = []
    for j, phi in enumerate(phis):
        rb = body_r(S_C0 + 0.010, phi)
        rr = (rb + 0.0025) if rb is not None else (Rmax[j] - 0.012)
        seal.append(cs_ + (Us * math.cos(phi) + Vs * math.sin(phi)) * rr)
    Vg, f_out = card.grid(rows + cuff_rows + [edge], tag)
    Vin, f_in = card.grid([Vg[-1], in0, in1], T_SLV_IN)
    Vs_, f_seal = card.grid([Vin[-1], seal], T_SLV_IN)

    def out_fn(p, sd=sd):
        s, _ = arm_s(sd, p)
        c, T, U, V = arm_frame(sd, s)
        d = p - c
        return d - T * d.dot(T)
    orient_faces(f_out, out_fn)
    orient_faces(f_in, lambda p, f=out_fn: -f(p))
    orient_faces(f_seal, lambda p, sd=sd, s1=S_C1: arm_frame(sd, s1)[1])
    SLEEVE_INFO[sd] = dict(faces=f_out, phi_in=phi_in)
    log("sleeve", sd, "S_E %.3f cuff %.3f..%.3f  phi_in %.2f" % (S_E, S_C0, S_C1, phi_in))

# ============================================================================= collar (Peter Pan)
log("collar")
N_COL = 25
d0 = 0.10
TH_COL = [-math.pi / 2 + d0 + (2 * math.pi - 2 * d0) * k / (N_COL - 1) for k in range(N_COL)]
PROFILE = [(-0.0015, -0.003), (-0.0015, 0.010), (0.002, 0.0155), (0.010, 0.0125), (0.026, 0.002),
           (0.043, -0.010), (0.0445, -0.0135), (0.041, -0.0128), (0.024, -0.0016), (0.007, 0.0058),
           (0.0025, -0.0022)]
col_cols = []
for th in TH_COL:
    base = bl_point(U_NECK, th)
    C = Vector((NECK_C[0], NECK_C[1], base.z))
    rh = Vector((base.x - C.x, base.y - C.y, 0)); R0 = rh.length; rh.normalize()
    ce = min(abs(wrap_pi(th - TH_COL[0])), abs(wrap_pi(th - TH_COL[-1])))
    fw = 0.32 + 0.68 * math.sqrt(clamp(ce / 0.55))
    pts = []
    for k, (rr, zz) in enumerate(PROFILE):
        if k in (4, 5, 6, 7, 8):
            rr = 0.010 + (rr - 0.010) * fw
            zz = 0.0125 + (zz - 0.0125) * fw
        pts.append(C + rh * (R0 + rr) + Vector((0, 0, zz)))
    for k in (3, 4, 5, 6, 7, 8, 9):
        p = pts[k]
        md = 0.0032 if k in (6, 7) else 0.0042
        for _ in range(3):
            p, _ = push_out(p, BL_BVH, md, 0.06)
            p, _ = push_out(p, NB_BVH, md + 0.0012, 0.03)
            p, _ = push_out(p, CARD_BVH, md + 0.0008, 0.02)
        pts[k] = p
    col_cols.append(pts)
crows = [[col_cols[c][k] for c in range(N_COL)] for k in range(len(PROFILE))]
Vcl = [[bl.vert(p, T_COLLAR) for p in row] for row in crows]
Vcl.append(Vcl[0])
_, collar_faces = bl.grid(Vcl, T_COLLAR, cyclic=False)
for cidx in (0, N_COL - 1):
    vs = [Vcl[k][cidx] for k in range(len(PROFILE))]
    f = bl.face(vs)
    if f: collar_faces.append(f)


def collar_out(p):
    th = math.atan2(p.y - NECK_C[1], p.x - NECK_C[0])
    base = bl_point(U_NECK, th)
    C = Vector((NECK_C[0], NECK_C[1], base.z))
    rh = Vector((base.x - C.x, base.y - C.y, 0)).normalized()
    cen = C + rh * ((base - C).length + 0.012) + Vector((0, 0, 0.004))
    return p - cen
orient_faces(collar_faces, collar_out)

# ============================================================================= shoes (slip-on comfort shoes)
log("building shoes")
shoes = Part("Shoes", M_SHOES)
parts['shoes'] = shoes
N_SH = 20
SH_T = [0.0, 0.15, 0.32, 0.50, 0.68, 0.84, 1.0]
SHOE_INFO = {}


def slice_center(z, sg):
    pts = slice_pts(Vector((0, 0, z)), Vector((0, 0, 1)), lambda p: p.x * sg > 0.02 and p.z < 0.3)
    xs_ = [p.x for p in pts]; ys_ = [p.y for p in pts]
    return Vector(((min(xs_) + max(xs_)) / 2, (min(ys_) + max(ys_)) / 2, z))


for sd, sg in (('l', 1), ('r', -1)):
    tag = T_SHOE_L if sd == 'l' else T_SHOE_R
    bvh = BODY_SIDE[sd]
    C0 = slice_center(0.012, sg); C1 = slice_center(0.09, sg)

    def center(z, C0=C0, C1=C1):
        t = clamp(z / 0.09)
        return C0.lerp(C1, t).to_2d()

    def foot_r(z, phi, bvh=bvh, center=center):
        c = center(z)
        d = Vector((math.cos(phi), math.sin(phi), 0))
        best = None
        for dz in (-0.004, 0.0, 0.004, 0.008):
            zz = max(0.002, z + dz)
            o = Vector((c.x, c.y, zz))
            for dp in (-0.04, 0.0, 0.04):
                dd = Vector((math.cos(phi + dp), math.sin(phi + dp), 0))
                hit = bvh.ray_cast(o + dd * 0.18, -dd, 0.18)
                if hit[0] is None: continue
                r = (hit[0] - o).dot(d)
                if r > 0 and (best is None or r > best): best = r
        return best
    samp = []
    for k in range(720):
        phi = math.pi / 2 + 2 * math.pi * k / 720 * sg
        r = foot_r(0.012, phi) or 0.05
        c = center(0.012)
        samp.append((phi, Vector((c.x + r * math.cos(phi), c.y + r * math.sin(phi)))))
    acc = [0.0]
    for k in range(1, 721):
        acc.append(acc[-1] + (samp[k % 720][1] - samp[k - 1][1]).length)
    total = acc[-1]
    phis = []
    for j in range(N_SH):
        target = total * j / N_SH
        k = max(i for i in range(720) if acc[i] <= target)
        phis.append(samp[k][0])

    def z_w(phi): return 0.011 + 0.005 * max(0.0, math.sin(phi))
    def z_tp(phi): return 0.046 + 0.020 * max(0.0, math.sin(phi)) ** 2 + 0.024 * max(0.0, -math.sin(phi)) ** 2
    rows = []
    prevR = None
    for k, t in enumerate(SH_T):
        R = []
        for j, phi in enumerate(phis):
            z = lerp(z_w(phi), z_tp(phi), t)
            fr = foot_r(z, phi)
            if fr is None:
                fr = (prevR[j] - 0.0105) * 0.97 if prevR else None
            front = max(0.0, -math.sin(phi)) ** 4
            if fr is None:
                R.append(None); continue
            clr = 0.0085 + 0.011 * front * (1 - smoothstep(0.0, 0.45, t))
            clr += 0.003 * (1 - smoothstep(0.1, 0.3, t))
            if t >= 0.9: clr = 0.0105
            R.append(fr + clr)
        for j in range(N_SH):
            if R[j] is None:
                R[j] = max(R[j - 1] or 0.0, R[(j + 1) % N_SH] or 0.0) or 0.05
        R0 = list(R)
        for _ in range(2):
            R = [0.25 * R[j - 1] + 0.5 * R[j] + 0.25 * R[(j + 1) % N_SH] for j in range(N_SH)]
        R = [max(a, b) for a, b in zip(R, R0)]
        prevR = R
        row = []
        for j, phi in enumerate(phis):
            z = lerp(z_w(phi), z_tp(phi), t)
            c = center(z)
            row.append(Vector((c.x + R[j] * math.cos(phi), c.y + R[j] * math.sin(phi), z)))
        rows.append(row)
    for k in range(len(rows)):
        for j, phi in enumerate(phis):
            c = center(rows[k][j].z)
            d = (rows[k][j].to_2d() - c).normalized()
            g = 0.0
            front = max(0.0, -math.sin(phi))
            if j == 0 and SH_T[k] > 0.1: g -= 0.0010
            if k == 3 and front > 0.55: g -= 0.0011
            if k >= 4 and abs(abs(wrap_pi(phi + math.pi / 2)) - 0.85) < 0.18: g -= 0.0009
            rows[k][j] = rows[k][j] + Vector((d.x, d.y, 0)) * g
    for it in range(3):
        for k in range(len(rows)):
            md = 0.0100 if SH_T[k] >= 0.9 else 0.0072
            for j in range(N_SH):
                rows[k][j], _ = push_out(rows[k][j], bvh, md, 0.05)
    Vu, f_up = shoes.grid(rows, tag)
    lin0, lin1, lin2 = [], [], []
    for j, v in enumerate(Vu[-1]):
        p = v.co; c = center(p.z)
        d = Vector((p.x - c.x, p.y - c.y, 0)).normalized()
        lin0.append(p - d * 0.0035 + Vector((0, 0, 0.0025)))
        lin1.append(p - d * 0.0050 + Vector((0, 0, -0.014)))
        q = Vu[0][j].co; cq = center(q.z)          # lining continues down to the insole
        dq = Vector((q.x - cq.x, q.y - cq.y, 0)).normalized()
        lin2.append(q - dq * 0.0045 + Vector((0, 0, 0.002)))
    Vl, f_lin = shoes.grid([Vu[-1], lin0, lin1, lin2], T_SHOE_IN)
    welt, mid, bot = [], [], []
    cb = Vector((C0.x, C0.y, -0.012))
    for j, v in enumerate(Vu[0]):
        p = v.co
        d = Vector((p.x - C0.x, p.y - C0.y, 0)).normalized()
        heel = max(0.0, math.sin(phis[j]))
        welt.append(p + d * 0.0045)
        mid.append(Vector((p.x, p.y, 0.0005)) + d * 0.0046)
        bot.append(Vector((p.x, p.y, -0.012 - 0.002 * heel)) + d * 0.0040)
    Vso, f_sole = shoes.grid([Vu[0], welt, mid, bot], tag)
    vc = shoes.vert(cb, tag)
    f_bot = []
    for j in range(N_SH):
        j2 = (j + 1) % N_SH
        a, b_ = Vso[-1][j], Vso[-1][j2]
        f = shoes.face([a, vc, b_], [(a.co.x * UVS, a.co.y * UVS), (cb.x * UVS, cb.y * UVS), (b_.co.x * UVS, b_.co.y * UVS)])
        if f: f_bot.append(f)

    def out_fn(p, center=center):
        c = center(clamp(p.z, 0, 0.09))
        return Vector((p.x - c.x, p.y - c.y, 0.0)) + Vector((0, 0, 0.3 * (p.z - 0.04)))
    orient_faces(f_up + f_sole, out_fn)
    for f in f_sole:
        f.normal_update()
        if abs(f.normal.z) > 0.7 and f.calc_center_median().z > 0.006 and f.normal.z < 0:
            f.normal_flip()
    orient_faces(f_bot, lambda p: Vector((0, 0, -1)))
    orient_faces(f_lin, lambda p, f=out_fn: -f(p))
    SHOE_INFO[sd] = dict(up_faces=f_up + f_sole + f_bot)

# ============================================================================= join
log("joining parts")
mats = []
for s in SLOTS:
    m = bpy.data.materials.new(s)
    c = PREVIEW_COLORS[s]
    m.diffuse_color = (c[0], c[1], c[2], 1.0)
    mats.append(m)
objs = []
for key in ('card', 'blouse', 'skirt', 'slip', 'shoes'):
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
tags = [d.value for d in outfit.data.attributes['tag'].data]
cnt = {}
for p in outfit.data.polygons:
    t = tags[p.vertices[0]]
    cnt[t] = cnt.get(t, 0) + 1
log("outfit verts", len(outfit.data.vertices), "tris", TRIS, "per tag", sorted(cnt.items()))

# ============================================================================= skinning
log("skinning")
inv = arm.matrix_world.inverted()
outfit.data.transform(inv)
outfit.parent = arm
outfit.matrix_parent_inverse = Matrix.Identity(4)
outfit.matrix_basis = Matrix.Identity(4)
bpy.context.view_layer.update()
REST_W = [outfit.matrix_world @ v.co for v in outfit.data.vertices]

# 1) Data Transfer from the body (vertex groups, nearest face interpolated) -- applied
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
CHAIN = [('pelvis', 0.80)] + [(CHAIN_B[i], 0.5 * (heads_z[i] + heads_z[i + 1])) for i in range(1, 6)]
log("spine chain", [(b, round(z, 3)) for b, z in CHAIN])


def chain_weights(z):
    if z <= CHAIN[0][1]: return {CHAIN[0][0]: 1.0}
    if z >= CHAIN[-1][1]: return {CHAIN[-1][0]: 1.0}
    for (b0, z0), (b1, z1) in zip(CHAIN, CHAIN[1:]):
        if z0 <= z <= z1:
            t = (z - z0) / (z1 - z0)
            return {b0: 1 - t, b1: t}


def hip_leg_share(p):
    """share of the thigh bones in the hip region (same for every concentric layer)."""
    x, y, z = p
    r = math.hypot(x, y) or 1e-6
    back = smoothstep(-0.35, 0.35, y / r)
    side = smoothstep(0.55, 0.95, abs(x) / r)
    z_hi = lerp(0.855, 0.79, back) + 0.025 * side; z_lo = lerp(0.73, 0.66, back) - 0.05 * side
    return smoothstep(z_hi, z_lo, z)


TV = []; TP = []
_us = [0.60 + 0.01 * k for k in range(int((Z_S - 0.60) / 0.01) + 1)] + [Z_S + DL * k / 8 for k in range(1, 9)]
_ths = [2 * math.pi * j / 72 for j in range(72)]
for i, u in enumerate(_us):
    for th in _ths:
        TV.append(torso_point(u, th))
for i in range(len(_us) - 1):
    for j in range(72):
        j2 = (j + 1) % 72
        TP.append((i * 72 + j, i * 72 + j2, (i + 1) * 72 + j2, (i + 1) * 72 + j))
TORSO_REF = BVHTree.FromPolygons(TV, TP)
TORSO_LAYER = {T_CARD, T_CARD_IN, T_CARD_DET, T_BLOUSE, T_COLLAR, T_BL_IN, T_BL_DET} | SKIRT_TAGS | SLIP_TAGS


def ref_point(p):
    loc, n, _, d = TORSO_REF.find_nearest(p, 0.5)
    if loc is None: return p
    return loc.lerp(p, smoothstep(0.035, 0.065, d))


def proc_weights(p, tag):
    W = {}

    def add(b, w):
        if w > 1e-6: W[b] = W.get(b, 0.0) + w
    x, y, z = p
    s_leg = hip_leg_share(p)
    wl = smoothstep(-0.03, 0.03, x)
    tw = 0.5 * smoothstep(0.73, 0.59, z)
    for sd, f in (('l', wl), ('r', 1 - wl)):
        add('thigh_' + sd, s_leg * f * (1 - tw)); add('thigh_twist_01_' + sd, s_leg * f * tw)
    rest = 1 - s_leg
    Aw, Cw = {}, {}
    for sd in 'lr':
        sg = ARM[sd]['sg']; xs = x * sg
        t, rad = arm_param(sd, p)
        if tag in (T_SLV_L, T_SLV_R, T_SLV_IN):
            a = smoothstep(-0.10, 0.30, t) if xs > 0.04 else 0.0
        else:
            a = 0.6 * smoothstep(-0.12, 0.12, t) * smoothstep(0.075, 0.055, rad) * smoothstep(0.075, 0.11, xs)
        c = smoothstep(0.03, 0.10, xs) * smoothstep(1.10, 1.20, z) * (1 - a) * 0.6
        Aw[sd] = (a, t); Cw[sd] = c
    neck = 0.6 * smoothstep(1.24, 1.29, z) * smoothstep(0.085, 0.062, math.hypot(x, y - NECK_C[1]))
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


def leg_weights(p, sd):
    loc, n, idx, d = LEG_BVH[sd].find_nearest(p, 2.0)
    tri = leg_tris[sd][idx]
    ws = poly_3d_calc([BV[i] for i in tri], loc)
    other = '_r' if sd == 'l' else '_l'
    W = {}
    for i, wi in zip(tri, ws):
        for b, w in BW[i].items():
            if b.endswith(other): continue
            W[b] = W.get(b, 0.0) + wi * w
    tot = sum(W.values()) or 1.0
    return {b: w / tot for b, w in W.items()}


def clean_dt(dtw, p, shoe=False):
    sgn = 'l' if p.x >= 0 else 'r'
    other = '_r' if sgn == 'l' else '_l'
    clean = {}
    for b, w in dtw.items():
        if abs(p.x) > 0.02 and b.endswith(other):
            continue
        if shoe and 'toe_0' in b:          # toes are rigid inside a shoe
            b = 'ball' + b[-2:]
        clean[b] = clean.get(b, 0.0) + w
    tot = sum(clean.values())
    return {b: w / tot for b, w in clean.items()} if tot > 0 else {}


def mix(dst, src, f):
    for b, w in src.items():
        dst[b] = dst.get(b, 0.0) + w * f


WFULL = []
for i, v in enumerate(outfit.data.vertices):
    p = REST_W[i]; tag = tags[i]
    W = {}
    if tag in SHOE_TAGS:
        W = clean_dt(DTW[i], p, shoe=True)
    elif tag in SKIRT_TAGS or tag in SLIP_TAGS:
        s_body = smoothstep(0.70, 0.615, p.z)
        if s_body > 0:
            if tag == T_SLIP_L or (tag == T_SLIP_IN and p.x > 0):
                mix(W, leg_weights(p, 'l'), s_body)
            elif tag == T_SLIP_R or (tag == T_SLIP_IN and p.x <= 0):
                mix(W, leg_weights(p, 'r'), s_body)
            else:
                wl = smoothstep(-0.05, 0.05, p.x)
                mix(W, leg_weights(p, 'l'), s_body * wl)
                mix(W, leg_weights(p, 'r'), s_body * (1 - wl))
        if s_body < 1:
            mix(W, proc_weights(ref_point(p), tag), 1 - s_body)
    elif tag in (T_SLV_L, T_SLV_R, T_SLV_IN):
        sd = 'l' if p.x >= 0 else 'r'
        t, rad = arm_param(sd, p)
        s_body = smoothstep(0.42, 0.56, t)
        dtc = clean_dt(DTW[i], p)
        if not dtc: s_body = 0.0
        if s_body > 0: mix(W, dtc, s_body)
        if s_body < 1: mix(W, proc_weights(p, tag), 1 - s_body)
    else:
        W = proc_weights(ref_point(p) if tag in TORSO_LAYER else p, tag)
    WFULL.append(W)

# 3) smooth the skirt / lining weights along the surface (no hard left/right or hip/leg seams)
adj = [[] for _ in outfit.data.vertices]
for e in outfit.data.edges:
    a, b_ = e.vertices
    adj[a].append(b_); adj[b_].append(a)
GROUP = {}
for t in SKIRT_TAGS: GROUP[t] = 1
for t in SLIP_TAGS: GROUP[t] = 2
SMOOTH_ITERS = 0
smooth_idx = [i for i, t in enumerate(tags) if t in GROUP and REST_W[i].z < 0.72]
for it in range(SMOOTH_ITERS):
    NW = {}
    for i in smooth_idx:
        nb = [j for j in adj[i] if GROUP.get(tags[j]) == GROUP[tags[i]]]
        if not nb: continue
        k = 0.5 * smoothstep(0.72, 0.64, REST_W[i].z)
        acc = {}
        mix(acc, WFULL[i], 1 - k)
        for j in nb: mix(acc, WFULL[j], k / len(nb))
        NW[i] = acc
    for i, w in NW.items(): WFULL[i] = w

final_w = []
for W in WFULL:
    items = sorted(W.items(), key=lambda kv: -kv[1])[:MAX_INFL]
    tot = sum(w for _, w in items)
    final_w.append([(b, w / tot) for b, w in items if w / tot > 1e-4])
for g in list(outfit.vertex_groups):
    outfit.vertex_groups.remove(g)
needed = sorted({b for fw in final_w for b, _ in fw})
missing = [b for b in needed if b not in arm.data.bones]
assert not missing, missing
VG = {b: outfit.vertex_groups.new(name=b) for b in needed}
for i, fw in enumerate(final_w):
    for b, w in fw:
        VG[b].add([i], w, 'REPLACE')
bpy.ops.object.select_all(action='DESELECT')
outfit.select_set(True)
bpy.context.view_layer.objects.active = outfit
bpy.ops.object.vertex_group_normalize_all(lock_active=False)
MAXI = max(len(v.groups) for v in outfit.data.vertices)
log("weights written: groups", len(needed), "max influences", MAXI)
am = outfit.modifiers.new("Armature", 'ARMATURE')
am.object = arm
am.use_vertex_groups = True

# ============================================================================= pose tests
OUT_POLYS = [tuple(p.vertices) for p in outfit.data.polygons]
POLY_TAG = [tags[p[0]] if len({tags[k] for k in p}) == 1 else max(tags[k] for k in p) for p in OUT_POLYS]


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


def coverage_sets():
    sets = {'arm_l': [], 'arm_r': [], 'legs_skirt': [], 'thigh_top_l': [], 'thigh_top_r': [], 'foot_l': [], 'foot_r': []}
    for i, p in enumerate(BV):
        sd = 'l' if p.x > 0 else 'r'
        if p.z > 0.75 and abs(p.x) > 0.12:
            s, d = arm_s(sd, p)
            if d < 0.08 and s <= ARM[sd]['S_C1'] - 0.025:
                sets['arm_' + sd].append(i)
        elif 0.30 <= p.z <= 0.70:
            sets['legs_skirt'].append(i)
            if p.z >= 0.585:
                sets['thigh_top_' + sd].append(i)
        elif p.z < 0.03:
            sets['foot_' + sd].append(i)
    return sets


COVER = coverage_sets()
COVER_TAGS = {'arm_l': {T_SLV_L}, 'arm_r': {T_SLV_R}, 'legs_skirt': {T_SKIRT},
              'thigh_top_l': {T_SLIP_L}, 'thigh_top_r': {T_SLIP_R},
              'foot_l': {T_SHOE_L}, 'foot_r': {T_SHOE_R}}
log("coverage set sizes", {k: len(v) for k, v in COVER.items()})


EXPO_TAGS = {'arm_l': {T_SLV_L, T_SLV_IN}, 'arm_r': {T_SLV_R, T_SLV_IN}, 'legs_skirt': SKIRT_TAGS | SLIP_TAGS,
             'thigh_top_l': SKIRT_TAGS | SLIP_TAGS, 'thigh_top_r': SKIRT_TAGS | SLIP_TAGS,
             'foot_l': SHOE_TAGS, 'foot_r': SHOE_TAGS}


def body_world_normals():
    dg = bpy.context.evaluated_depsgraph_get(); ob = body.evaluated_get(dg); me = ob.to_mesh()
    M = body.matrix_world; N3 = M.to_3x3().inverted().transposed()
    V = [M @ v.co for v in me.vertices]; Nn = [(N3 @ v.normal).normalized() for v in me.vertices]
    ob.to_mesh_clear()
    return V, Nn


def exposure(state):
    BVn, BNn = body_world_normals()
    OV, OP = mesh_world(outfit)
    res = {}
    for key, idxs in COVER.items():
        polys = [p for p, t in zip(OP, POLY_TAG) if t in EXPO_TAGS[key]]
        bvh = BVHTree.FromPolygons(OV, polys)
        exp_ = [i for i in idxs if bvh.ray_cast(BVn[i] + BNn[i] * 0.001, BNn[i], 0.6)[0] is None]
        res[key] = (len(idxs), len(exp_))
        if exp_:
            log("   exposed", state, key, [tuple(round(c, 3) for c in BV[i]) for i in exp_[:4]])
    log("EXPOSURE %-7s (verts, exposed)" % state, res)
    return res


def check(state):
    bpy.context.view_layer.update()
    BVp, BPp = mesh_world(body)
    OV, OP = mesh_world(outfit)
    res = {}
    worst = []
    for key, idxs in COVER.items():
        polys = [p for p, t in zip(OP, POLY_TAG) if t in COVER_TAGS[key]]
        bvh = BVHTree.FromPolygons(OV, polys)
        pokes = 0; close = 0; mind = 1e9
        for i in idxs:
            b = BVp[i]
            loc, n, _, d = bvh.find_nearest(b, 0.4)
            if loc is None: continue
            clr = -(b - loc).dot(n)
            mind = min(mind, clr)
            if clr <= 0.0: pokes += 1; worst.append((round(clr * 100, 2), key, tuple(round(c, 3) for c in BV[i]), tuple(round(c, 3) for c in b), tuple(round(c, 3) for c in loc), tuple(round(c, 2) for c in n)))
            elif clr < 0.006: close += 1
        res[key] = (len(idxs), pokes, close, round(mind * 100, 2))

    dg = bpy.context.evaluated_depsgraph_get(); oe = outfit.evaluated_get(dg); me_ = oe.to_mesh()
    N3 = outfit.matrix_world.to_3x3().inverted().transposed()
    ONRM = [(N3 @ v.normal).normalized() for v in me_.vertices]
    oe.to_mesh_clear()

    def gg(src_tags, src_filter, dst_tags, want_inside, md=0.0):
        polys = [p for p, t in zip(OP, POLY_TAG) if t in dst_tags]
        bvh = BVHTree.FromPolygons(OV, polys)
        bad = 0; n_ = 0; mind = 1e9; badl = []
        for i, t in enumerate(tags):
            if t in src_tags and src_filter(REST_W[i]):
                loc, nn, _, d = bvh.find_nearest(OV[i], 0.1)
                if loc is None: continue
                n_ += 1
                sd = (OV[i] - loc).dot(nn)
                m = -sd if want_inside else sd
                mind = min(mind, m)
                if m <= md:
                    bad += 1
                    badl.append((round(m * 100, 2), tuple(round(c, 3) for c in REST_W[i]), tuple(round(c, 3) for c in OV[i]), tags[i]))
        exposed = 0
        if badl:
            log("   gg-bad", state, sorted(badl)[:3])
            # is any flagged vertex actually visible? ray along its normal must hit another garment layer
            other = [p for p, t in zip(OP, POLY_TAG) if t not in src_tags]
            obvh = BVHTree.FromPolygons(OV, other)
            for i, t in enumerate(tags):
                if t in src_tags and src_filter(REST_W[i]):
                    loc, nn, _, d = bvh.find_nearest(OV[i], 0.1)
                    if loc is None: continue
                    sd_ = (OV[i] - loc).dot(nn)
                    if (-sd_ if want_inside else sd_) <= md:
                        if obvh.ray_cast(OV[i] + ONRM[i] * 0.0005, ONRM[i], 0.5)[0] is None:
                            exposed += 1
        return (n_, bad, round(mind * 100, 2), exposed)
    res['blouse_in_cardigan'] = gg({T_BLOUSE}, lambda p: p.z < 1.19 and not (p.z > Z_V - 0.03 and abs(p.x) < xv(p.z) + 0.035),
                                   {T_CARD}, True)
    res['skirt_in_cardigan'] = gg({T_SKIRT, T_SK_WB}, lambda p: p.z > 0.815, {T_CARD}, True)
    res['slip_in_skirt'] = gg({T_SLIP}, lambda p: p.z > 0.715, {T_SKIRT, T_SK_WB}, True)
    for k, v in res.items():
        log("CHECK %-7s %-20s" % (state, k), v)
    return res, sorted(worst)[:12]


def stretch_report(state):
    OVs, _ = mesh_world(outfit)
    per = {}
    for p in OUT_POLYS:
        for k in range(3):
            a, b_ = p[k], p[(k + 1) % 3]
            l0 = (REST_W[a] - REST_W[b_]).length
            if l0 > 2e-3:
                r = (OVs[a] - OVs[b_]).length / l0
                t = tags[a]
                cur = per.get(t, (1.0, 1.0, None, None))
                lo = (r, tuple(round(c, 3) for c in REST_W[a])) if r < cur[0] else (cur[0], cur[2])
                hi = (r, tuple(round(c, 3) for c in REST_W[a])) if r > cur[1] else (cur[1], cur[3])
                per[t] = (lo[0], hi[0], lo[1], hi[1])
    log("STRETCH %s (min,max edge ratio per tag, rest positions)" % state, {k: (round(v[0], 2), round(v[1], 2), v[2], v[3]) for k, v in sorted(per.items())})
    return per


reset_pose()
REST_EXPO = exposure("rest")
REST_CHECK = check("rest")
log("rest worst", REST_CHECK[1][:6])
seated_pose()
SEAT_EXPO = exposure("seated")
SEAT_CHECK = check("seated")
log("seated worst", SEAT_CHECK[1])
STRETCH = stretch_report("seated")
reset_pose()


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
    sh.show_specular_highlight = False
    sc.view_settings.view_transform = 'Standard'
    w = bpy.data.worlds.new("Preview"); w.color = (0.62, 0.64, 0.67); sc.world = w
    skin = bpy.data.materials.new("Skin"); skin.diffuse_color = (0.62, 0.45, 0.38, 1)
    body.data.materials.clear(); body.data.materials.append(skin)


def render(name, target, dist, az, el, lens=55, res=(900, 1200)):
    sc = bpy.context.scene
    sc.render.resolution_x, sc.render.resolution_y = res
    cam_d = bpy.data.cameras.new(name); cam_d.lens = lens; cam_d.clip_start = 0.05
    cam = bpy.data.objects.new(name, cam_d); sc.collection.objects.link(cam)
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
    return path


PREVIEWS = []
if DO_RENDER:
    log("rendering previews")
    for f in os.listdir(PREV):
        if f.endswith('.png'): os.remove(os.path.join(PREV, f))
    setup_render()
    reset_pose()
    PREVIEWS.append(render("01_front", (0, 0, 0.68), 2.7, 0, 4))
    PREVIEWS.append(render("02_three_quarter", (0, 0, 0.68), 2.7, 38, 8))
    PREVIEWS.append(render("03_back", (0, 0, 0.68), 2.7, 180, 6))
    PREVIEWS.append(render("04_side", (0, 0, 0.68), 2.7, 90, 4))
    PREVIEWS.append(render("05_closeup_neckline", (0.0, -0.05, 1.16), 0.75, 18, 10, res=(1000, 900)))
    PREVIEWS.append(render("06_closeup_right_cuff_wrist", (-0.33, -0.06, 0.95), 0.75, -45, 8, res=(1000, 900)))
    PREVIEWS.append(render("07_closeup_shoes", (0.0, -0.06, 0.07), 0.9, 35, 18, res=(1000, 700)))
    PREVIEWS.append(render("08_closeup_hem_pockets", (0.03, -0.08, 0.86), 0.85, 25, 6, res=(1000, 800)))
    seated_pose()
    PREVIEWS.append(render("10_seated_three_quarter", (0, -0.2, 0.72), 2.7, 40, 10))
    PREVIEWS.append(render("11_seated_side", (0, -0.2, 0.72), 2.7, 90, 5))
    PREVIEWS.append(render("12_seated_front", (0, -0.2, 0.72), 2.7, 0, 12))
    PREVIEWS.append(render("13_seated_back", (0, -0.2, 0.72), 2.7, 200, 8))
    PREVIEWS.append(render("14_seated_low_front_knees", (0.0, -0.32, 0.55), 1.6, 15, -2, res=(1000, 900)))
    PREVIEWS.append(render("15_seated_closeup_lap_arms", (0.05, -0.30, 0.86), 1.3, 55, 28, res=(1000, 900)))
    reset_pose()

# ============================================================================= export
reset_pose()
arm.data.pose_position = 'REST'
bpy.context.view_layer.update()
if 'tag' in outfit.data.attributes:
    outfit.data.attributes.remove(outfit.data.attributes['tag'])
REF = [outfit.matrix_world @ v.co for v in outfit.data.vertices]
arm.data.pose_position = 'POSE'
seated_pose()
REF_POSED, _ = mesh_world(outfit)
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
    hier_ok = all((b.parent.name if b.parent else None) == (b_arm.data.bones[b.name].parent.name if b_arm.data.bones[b.name].parent else None)
                  for b in g_arm.data.bones if b.name in names_b)
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
        kd2 = KDTree(len(GV))
        for i, p in enumerate(GV): kd2.insert(p, i)
        kd2.balance()
        v_off = max(kd2.find(p)[2] for p in REF)
    # body vs garment alignment: garment clearance to the re-imported body (rest)
    BVr, BPr = mesh_world(b_mesh)
    body_bvh_r = BVHTree.FromPolygons(BVr, BPr)
    BVo = BV
    body_shift = max((a - b).length for a, b in zip(BVr, BVo)) if len(BVr) == len(BVo) else -1
    infl = max(len([g for g in v.groups if g.weight > 1e-6]) for v in g_mesh.data.vertices)
    tris = sum(len(p.vertices) - 2 for p in g_mesh.data.polygons)
    slots = [m.name if m else None for m in g_mesh.data.materials]
    uvs = [u.name for u in g_mesh.data.uv_layers]
    arm = g_arm
    seated_pose()
    GVp, _ = mesh_world(g_mesh)
    posed_off = max((a - b).length for a, b in zip(GVp, REF_POSED)) if len(GVp) == len(REF_POSED) else -1
    reset_pose()
    log("ROUNDTRIP vertex max offset %.5f cm | bone max offset %.5f cm | body re-import shift %.5f cm | posed (seated) max offset %.5f cm"
        % (v_off * 100, bone_off * 100, body_shift * 100, posed_off * 100))
    log("ROUNDTRIP tris %d  max influences %d  slots %s  uv %s  mesh name %s  hierarchy match %s"
        % (tris, infl, slots, uvs, g_mesh.name, hier_ok))
    print("RESULT_JSON", {"tris": tris, "max_infl": infl, "roundtrip_cm": v_off * 100, "bone_cm": bone_off * 100,
                          "posed_cm": posed_off * 100, "slots": slots, "previews": PREVIEWS,
                          "rest": REST_CHECK[0], "seated": SEAT_CHECK[0], "expo_rest": REST_EXPO, "expo_seated": SEAT_EXPO})
log("done")

