"""Room shell for Maria's room: floor, ceiling, walls, and real moulded trims.

Run headless:
  "C:\\Program Files\\Blender Foundation\\Blender 5.0\\blender.exe" -b --factory-startup --python shell.py

Follows SourceArt/Room/CONVENTIONS.md:
  * Geometry is authored in Unreal centimetres (X north/window, Y east, Z up) and converted once per
    piece to Blender metres with ue(x, y, z) = (x/100, -y/100, z/100); faces are re-wound after the
    mirror so normals stay outward. Every shell piece keeps the WORLD ORIGIN as its pivot.
  * UV0 'UVMap' = 1 m world box projection; UV1 'Lightmap' = smart project + pack, 2% margin.
  * Slots: M_Carpet, M_Ceiling, M_WallPaint, M_PaintedTimber, M_DoorTimber, M_Metal.

Pieces
  SM_Floor, SM_Ceiling, SM_Wall_*   unchanged slabs from build_room_shell.py, except the north wall
                                    gets a 2 cm rebate (X 500..502, Z 77.5..80) so the sill board's
                                    back edge seats into the wall instead of passing through it.
  SM_Skirting     colonial skirting (plain face, quirk, ogee, pencil-round top), 10 cm x 1.8 cm,
                  one continuous mitred sweep round the room, stopping 0.2 cm short of the door
                  architraves.
  SM_Cornice      6 x 6 cm plaster cove with flat returns, one closed mitred loop at the ceiling.
  SM_WindowFrame  reveal linings, frame with rebated stops, centre mullion (boolean-unioned to the
                  frame), two sashes with integral ovolo glazing beads and an empty glass slot, sill
                  board with bullnose (X 486..502, Z 77.5..80, Y 94..356), apron, 5 cm moulded
                  architrave. Glass is left out.
  SM_Door         four-panel door: stiles, rails, muntin; chamfer-stuck recesses with raised fielded
                  panels on both faces. X 61..149, Y -9..-4.5, Z 1..209.
  SM_DoorFrame    jamb linings with planted stops (one sweep) + 7 cm colonial architrave on the room
                  side.
  SM_DoorHandle   lathe-turned rose with neck, swept bevelled return-to-door lever (rounded end), and a
                  matching privacy escutcheon with a thumbturn. Rose centre X 137, Z 102, on the door
                  face at Y -4.5 (0.1 cm off it).
"""
import math
import os

import bmesh
import bpy
from mathutils import Matrix, Vector

ROOT = r"D:\Unreal-Projects\WattleviewGrove-ue58\SourceArt\Room"
OUT = os.path.join(ROOT, "Export")
PREV = os.path.join(ROOT, "Previews")
ITEMS = os.path.join(ROOT, "Items")

X, Y, H, T = 500.0, 450.0, 270.0, 15.0
WIN = dict(y0=100.0, y1=350.0, z0=80.0, z1=220.0)
DOOR = dict(x0=60.0, x1=150.0, z1=210.0)
GAP = 0.2

MATS = {
    "M_WallPaint": (0.80, 0.77, 0.71),
    "M_Ceiling": (0.85, 0.84, 0.81),
    "M_Carpet": (0.45, 0.42, 0.38),
    "M_PaintedTimber": (0.90, 0.89, 0.86),
    "M_DoorTimber": (0.62, 0.47, 0.32),
    "M_Metal": (0.60, 0.61, 0.63),
}


def mat(name):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.diffuse_color = (*MATS[name], 1.0)
    m.roughness = 0.45
    return m


# ------------------------------------------------------------------ low-level helpers (UE cm)
def obj_from_bm(bm, name="tmp"):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def eval_to_bm(ob, recalc=True):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    bm = bmesh.new()
    bm.from_mesh(me)
    ev.to_mesh_clear()
    data = ob.data
    bpy.data.objects.remove(ob, do_unlink=True)
    if isinstance(data, bpy.types.Mesh):
        bpy.data.meshes.remove(data)
    if recalc:
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return bm


def boolean(bm, others, op="UNION"):
    """EXACT boolean of bm with each bmesh in others (all consumed)."""
    ob = obj_from_bm(bm, "bool_base")
    cutters = []
    for i, o in enumerate(others):
        c = obj_from_bm(o, "bool_%d" % i)
        c.hide_render = True
        cutters.append(c)
        m = ob.modifiers.new("b%d" % i, "BOOLEAN")
        m.operation = op
        m.solver = "EXACT"
        m.object = c
    out = eval_to_bm(ob)
    for c in cutters:
        me = c.data
        bpy.data.objects.remove(c, do_unlink=True)
        bpy.data.meshes.remove(me)
    return out


def merge_bms(bms):
    out = bmesh.new()
    for b in bms:
        tmp = bpy.data.meshes.new("tmp")
        b.to_mesh(tmp)
        b.free()
        out.from_mesh(tmp)
        bpy.data.meshes.remove(tmp)
    return out


def bevelled(bm, width, seg=2, angle=30):
    ob = obj_from_bm(bm)
    m = ob.modifiers.new("bevel", "BEVEL")
    m.width = width
    m.segments = seg
    m.limit_method = "ANGLE"
    m.angle_limit = math.radians(angle)
    m.use_clamp_overlap = True
    return eval_to_bm(ob)


def box_bm(x0, x1, y0, y1, z0, z1):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector((x1 if v.co.x > 0 else x0, y1 if v.co.y > 0 else y0, z1 if v.co.z > 0 else z0))
    return bm


def prism(pts, to3d, d0, d1):
    """Extrude a closed 2D outline (may be concave) between depths d0..d1, capped."""
    bm = bmesh.new()
    r0 = [bm.verts.new(to3d(a, b, d0)) for a, b in pts]
    r1 = [bm.verts.new(to3d(a, b, d1)) for a, b in pts]
    n = len(pts)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((r0[i], r0[j], r1[j], r1[i]))
    bm.faces.new(list(reversed(r0)))
    bm.faces.new(r1)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return bm


def loft(rings):
    """Closed solid through a list of rings (same vertex count), capped at both ends."""
    bm = bmesh.new()
    R = [[bm.verts.new(Vector(p)) for p in ring] for ring in rings]
    m = len(rings[0])
    for a, b in zip(R[:-1], R[1:]):
        for j in range(m):
            jj = (j + 1) % m
            bm.faces.new((a[j], a[jj], b[jj], b[j]))
    bm.faces.new(list(reversed(R[0])))
    bm.faces.new(R[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return bm


def subdivide(path, seg, closed=False):
    """Insert points so no straight path segment is longer than seg (lightmap chunking)."""
    P = [Vector(p) for p in path]
    out = []
    n = len(P)
    for i in range(n if closed else n - 1):
        a, b = P[i], P[(i + 1) % n]
        k = max(1, int(math.ceil((b - a).length / seg)))
        out += [a.lerp(b, j / k) for j in range(k)]
    if not closed:
        out.append(P[-1])
    return out


def sweep(profile, path, hint, closed=False, scales=None, round_end=0, seg=None, lm=True):
    """Sweep a closed 2D profile (u along 'side', v along 'up') along a polyline with mitred joints.

    side = tangent x hint, up = side x tangent. For a path lying in the plane normal to hint the
    mitre is exact (u is stretched by 1/cos(half angle) at each joint). Open paths are capped;
    round_end adds that many shrinking rings past the last point for a domed end.
    lm: write an unwrapped 'Lightmap' UV layer (cm): u = distance round the profile, v = distance
    along the path; every path segment is its own island, caps are planar islands.
    """
    hint = Vector(hint).normalized()
    P = subdivide(path, seg, closed) if seg else [Vector(p) for p in path]
    n = len(P)
    scales = scales or [1.0] * n
    rings = []
    for i in range(n):
        if closed:
            t0 = (P[i] - P[i - 1]).normalized()
            t1 = (P[(i + 1) % n] - P[i]).normalized()
        else:
            t0 = (P[i] - P[i - 1]).normalized() if i > 0 else (P[1] - P[0]).normalized()
            t1 = (P[i + 1] - P[i]).normalized() if i < n - 1 else t0
        t = (t0 + t1).normalized()
        side = t.cross(hint).normalized()
        up = side.cross(t).normalized()
        side0 = t0.cross(hint).normalized()
        k = 1.0 / max(0.3, side.dot(side0))
        s = scales[i]
        rings.append([P[i] + side * (u * k * s) + up * (v * s) for u, v in profile])
    if round_end and not closed:
        t = (P[-1] - P[-2]).normalized()
        side = t.cross(hint).normalized()
        up = side.cross(t).normalized()
        half = max(max(abs(u) for u, v in profile), max(abs(v) for u, v in profile)) * scales[-1]
        for j in range(1, round_end + 1):
            a = (math.pi / 2) * j / (round_end + 0.6)
            s = scales[-1] * math.cos(a)
            c = P[-1] + t * (half * math.sin(a))
            rings.append([c + side * (u * s) + up * (v * s) for u, v in profile])
    bm = bmesh.new()
    R = [[bm.verts.new(p) for p in ring] for ring in rings]
    m = len(profile)
    pairs = list(zip(R[:-1], R[1:]))
    if closed:
        pairs.append((R[-1], R[0]))
    uvl = bm.loops.layers.uv.new("Lightmap") if lm else None
    sj = [0.0]
    for j in range(m):
        a, b = Vector(profile[j]), Vector(profile[(j + 1) % m])
        sj.append(sj[-1] + (b - a).length)
    for i, (a, b) in enumerate(pairs):
        seglen = (b[0].co - a[0].co).length
        for j in range(m):
            jj = (j + 1) % m
            f = bm.faces.new((a[j], a[jj], b[jj], b[j]))
            if uvl:
                for loop, uv in zip(f.loops, ((sj[j], 0.0), (sj[j + 1], 0.0), (sj[j + 1], seglen), (sj[j], seglen))):
                    loop[uvl].uv = uv
    if not closed:
        for ring in (list(reversed(R[0])), R[-1]):
            f = bm.faces.new(ring)
            if uvl:
                for loop in f.loops:
                    u, v = profile[R[0].index(loop.vert)] if loop.vert in R[0] else profile[R[-1].index(loop.vert)]
                    loop[uvl].uv = (u, v)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return bm


def box_lm(bm, prefer=None, thresh=0.25, chunk=None, chunk_axis=0):
    """'Lightmap' UVs (cm) by projecting each face along its dominant axis (sign-separated groups,
    so connected groups become islands). prefer=(axis) pulls faces with |n[axis]| >= thresh into
    that axis' heightfield projection (keeps a panelled face in one island). chunk (cm) splits
    islands every chunk along chunk_axis (faces must already be cut there)."""
    uvl = bm.loops.layers.uv.get("Lightmap") or bm.loops.layers.uv.new("Lightmap")
    bm.normal_update()
    for f in bm.faces:
        n = f.normal
        ax = max(range(3), key=lambda i: abs(n[i]))
        if prefer is not None and abs(n[prefer]) >= thresh:
            ax = prefer
        sgn = 1.0 if n[ax] >= 0 else -1.0
        off = 0.0
        if chunk:
            off = 1000.0 * math.floor(f.calc_center_median()[chunk_axis] / chunk)
        for loop in f.loops:
            c = loop.vert.co
            if ax == 0:
                uv = (c.y * sgn, c.z)
            elif ax == 1:
                uv = (c.x * -sgn, c.z)
            else:
                uv = (c.x, c.y * sgn)
            loop[uvl].uv = (uv[0] + off, uv[1])
    return bm


def fillet(points, r, segs=4):
    """Round interior corners of a polyline with quadratic-Bezier arcs (r = tangent distance)."""
    P = [Vector(p) for p in points]
    rr = r if isinstance(r, (list, tuple)) else [r] * len(P)
    out = [P[0]]
    for i in range(1, len(P) - 1):
        a, b, c = P[i - 1], P[i], P[i + 1]
        d = min(rr[i], (a - b).length * 0.49, (c - b).length * 0.49)
        p1 = b + (a - b).normalized() * d
        p2 = b + (c - b).normalized() * d
        for k in range(segs + 1):
            t = k / segs
            out.append(p1 * (1 - t) ** 2 + b * 2 * (1 - t) * t + p2 * t * t)
    out.append(P[-1])
    return out


def lathe(profile, steps, axis="Z", loc=(0, 0, 0)):
    """Turned part from an (r, h) profile running axis -> axis, revolved with a Screw modifier.
    axis 'Y': h maps to UE Y."""
    me = bpy.data.meshes.new("profile")
    me.from_pydata([(r, 0.0, z) for r, z in profile], [(i, i + 1) for i in range(len(profile) - 1)], [])
    ob = bpy.data.objects.new("profile", me)
    bpy.context.scene.collection.objects.link(ob)
    s = ob.modifiers.new("screw", "SCREW")
    s.axis = "Z"
    s.angle = 2 * math.pi
    s.steps = steps
    s.render_steps = steps
    s.use_merge_vertices = True
    s.merge_threshold = 1e-4
    s.use_normal_calculate = True
    bm = eval_to_bm(ob)
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-4)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    if axis == "Y":
        bmesh.ops.rotate(bm, verts=bm.verts[:], cent=Vector(), matrix=Matrix.Rotation(math.radians(-90), 3, "X"))
    bmesh.ops.translate(bm, verts=bm.verts[:], vec=Vector(loc))
    return bm


def arc(cx, cy, r, a0, a1, n):
    return [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * i / n)),
             cy + r * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]


def smoothstep(t):
    return t * t * (3 - 2 * t)


# ------------------------------------------------------------------ profiles
def skirting_profile():
    """(proud, z) points of a 10 x 1.8 cm colonial skirting, front face only, bottom to top."""
    pts = [(1.8, 0.0), (1.8, 6.3), (1.52, 6.48)]                    # plain face, quirk bevel
    for i in range(1, 9):                                            # ogee 1.52 -> 1.02
        t = i / 8.0
        pts.append((1.52 - 0.50 * smoothstep(t), 6.48 + 1.5 * t))
    pts.append((1.02, 8.2))
    for i in range(1, 9):                                            # pencil-round top
        a = math.radians(90.0 * i / 8)
        pts.append((0.25 + 0.77 * math.cos(a), 8.2 + 1.8 * math.sin(a)))
    pts.append((0.0, 10.0))
    return [(0.0, 0.0)] + pts


def architrave_profile(W=7.0):
    """(s, h): s from the sight edge (0) outward to W, h = thickness off the wall. Colonial style:
    small bead at the sight edge, quirk, gently splayed field, ogee up to a rounded back band."""
    f = W / 7.0
    pts = [(0.0, 0.0), (0.0, 1.0)]
    for i in range(1, 6):                                            # sight-edge bead
        a = math.radians(90.0 * i / 5)
        pts.append((0.55 * f * (1 - math.cos(a)), 1.0 + 0.5 * math.sin(a)))
    pts += [(0.8 * f, 1.32), (4.0 * f, 1.55)]                        # quirk, field
    for i in range(1, 9):                                            # ogee
        t = i / 8.0
        pts.append(((4.0 + 1.5 * t) * f, 1.55 + 0.65 * smoothstep(t)))
    pts.append((W - 0.35, 2.3))
    for i in range(1, 6):                                            # back band round
        a = math.radians(90.0 * i / 5)
        pts.append((W - 0.35 + 0.35 * math.sin(a), 1.95 + 0.35 * math.cos(a)))
    pts.append((W, 0.0))
    return pts


def cornice_profile():
    """(off_wall, down_from_ceiling): 6 x 6 cm cove with 0.6 cm flat returns and eased edges."""
    pts = [(0.0, 0.0), (0.0, 6.0), (0.45, 6.0), (0.6, 5.85)]
    pts += arc(6.0, 6.0, 5.4, 180, 270, 16)[1:-1]
    pts += [(5.85, 0.6), (6.0, 0.45), (6.0, 0.0)]
    return pts


# ------------------------------------------------------------------ pieces
def floor_piece():
    return [(box_bm(-T, X + T, -T, Y + T, -10, 0), "M_Carpet")]


def ceiling_piece():
    return [(box_bm(-T, X + T, -T, Y + T, H, H + 10), "M_Ceiling")]


def wall_north():
    w = box_bm(X, X + T, -T, Y + T, 0, H)
    w = boolean(w, [box_bm(X - 1, X + T + 1, WIN["y0"], WIN["y1"], WIN["z0"], WIN["z1"]),
                    box_bm(X - 1, X + 2.0, 94.0, 356.0, 77.5, 80.0)], "DIFFERENCE")
    return [(w, "M_WallPaint")]


def wall_west():
    w = box_bm(-T, X + T, -T, 0, 0, H)
    w = boolean(w, [box_bm(DOOR["x0"], DOOR["x1"], -T - 1, 1, -1, DOOR["z1"])], "DIFFERENCE")
    return [(w, "M_WallPaint")]


def wall_south():
    return [(box_bm(-T, 0, 0, Y, 0, H), "M_WallPaint")]


def wall_east():
    return [(box_bm(-T, X + T, Y, Y + T, 0, H), "M_WallPaint")]


ARCH_W = 7.0
ARCH_SIGHT = 0.4          # architrave sight edge overlaps the jamb lining edge by this much


def skirting():
    prof = [(-p, z) for p, z in skirting_profile()]                  # side points outward (wall)
    x_left = DOOR["x0"] + ARCH_SIGHT - ARCH_W - GAP                   # 53.2
    x_right = DOOR["x1"] - ARCH_SIGHT + ARCH_W + GAP                  # 156.8
    path = [(x_right, 0, 0), (X, 0, 0), (X, Y, 0), (0, Y, 0), (0, 0, 0), (x_left, 0, 0)]
    return [(sweep(prof, path, (0, 0, 1), seg=110.0), "M_PaintedTimber")]


def cornice():
    prof = [(-s, -t) for s, t in cornice_profile()]
    path = [(0, 0, H), (X, 0, H), (X, Y, H), (0, Y, H)]
    return [(sweep(prof, path, (0, 0, 1), closed=True, seg=110.0), "M_Ceiling")]


# window --------------------------------------------------------------
WF_X0, WF_X1 = 508.0, 514.5            # frame depth inside the reveal (room face at 508)
WF = dict(y0=102.0, y1=348.0, z0=80.2, z1=218.0)
WF_FACE = 5.0
MULL_Y, MULL_HW = 225.0, 3.0


def yz_loop(y0, y1, z0, z1):
    return [(X, y0, z0), (X, y0, z1), (X, y1, z1), (X, y1, z0)]


def window_frame():
    parts = []
    hint = (-1, 0, 0)                 # side = outward from the opening, up = into the room (-X)

    # sill board with a bullnose front, horns 6 cm past the opening
    outline = [(502.0, 77.5), (502.0, 80.0)] + arc(487.25, 78.75, 1.25, 90, 270, 16)
    ys = [94.0 + (356.0 - 94.0) * i / 4 for i in range(5)]           # cut every 65.5 cm for lightmap chunks
    sill = loft([[(a, y, b) for a, b in outline] for y in ys])
    parts.append((box_lm(bevelled(sill, 0.3, 2, 30), chunk=65.5, chunk_axis=1), "M_PaintedTimber"))

    # apron under the sill (window architrave profile, sight edge up)
    prof5 = architrave_profile(5.0)
    apron_prof = [(-s, h) for s, h in prof5]
    parts.append((sweep(apron_prof, [(X, 96.0, 77.5 - GAP), (X, 354.0, 77.5 - GAP)], hint, seg=140.0), "M_PaintedTimber"))

    # architrave: legs stand on the sill (0.2 gap), head across
    sy0, sy1, sz1 = WIN["y0"] + ARCH_SIGHT, WIN["y1"] - ARCH_SIGHT, WIN["z1"] - ARCH_SIGHT
    zb = WIN["z0"] + GAP
    arch = sweep(prof5, [(X, sy0, zb), (X, sy0, sz1), (X, sy1, sz1), (X, sy1, zb)], hint, seg=140.0)
    parts.append((arch, "M_PaintedTimber"))

    # reveal linings (jambs + head), 1.8 thick, front edge 0.2 behind the wall face
    lin = [(0.0, 500.2), (1.6, 500.2), (1.8, 500.4), (1.8, WF_X0 - GAP), (0.0, WF_X0 - GAP)]
    lin_prof = [(-s, X - x) for s, x in lin]
    parts.append((sweep(lin_prof, [(X, WIN["y0"], zb), (X, WIN["y0"], WIN["z1"]),
                                   (X, WIN["y1"], WIN["z1"]), (X, WIN["y1"], zb)], hint, seg=140.0),
                  "M_PaintedTimber"))

    # frame ring with room-side chamfer and outside stop lip + mullion, unioned
    fr = [(0, 508.3), (0.3, 508.0), (4.4, 508.0), (5.0, 508.6), (5.0, 513.2), (6.0, 513.2), (6.0, WF_X1),
          (0, WF_X1)]
    ring = sweep([(-s, X - x) for s, x in fr], yz_loop(WF["y0"], WF["y1"], WF["z0"], WF["z1"]), hint, closed=True,
                 seg=140.0)
    m0, m1 = MULL_Y - MULL_HW, MULL_Y + MULL_HW
    mo = [(m0, 508.6), (m0 + 0.6, 508.0), (m1 - 0.6, 508.0), (m1, 508.6), (m1, 513.2), (m1 + 1.0, 513.2),
          (m1 + 1.0, WF_X1), (m0 - 1.0, WF_X1), (m0 - 1.0, 513.2), (m0, 513.2)]
    mull = prism(mo, lambda a, b, d: Vector((b, a, d)), WF["z0"] + WF_FACE - 0.4, WF["z1"] - WF_FACE + 0.4)
    parts.append((boolean(ring, [box_lm(mull)], "UNION"), "M_PaintedTimber"))

    # sashes with integral glazing bead (ovolo) and an empty glass slot
    sp = [(0, 509.4), (0.4, 509.0), (4.2, 509.0), (4.45, 509.35), (4.7, 509.2), (5.15, 509.2)]
    sp += [(5.15 + 0.65 * math.sin(math.radians(a)), 509.85 - 0.65 * math.cos(math.radians(a)))
           for a in (18, 36, 54, 72)]
    sp += [(5.8, 509.85), (5.8, 511.2), (5.0, 511.2), (5.0, 511.6), (5.4, 511.6), (5.4, 513.0), (0, 513.0)]
    sash_prof = [(-s, X - x) for s, x in sp]
    g = 0.25
    zi0, zi1 = WF["z0"] + WF_FACE + g, WF["z1"] - WF_FACE - g
    for y0, y1 in ((WF["y0"] + WF_FACE + g, m0 - g), (m1 + g, WF["y1"] - WF_FACE - g)):
        parts.append((sweep(sash_prof, yz_loop(y0, y1, zi0, zi1), hint, closed=True, seg=140.0), "M_PaintedTimber"))
    return parts


# door ----------------------------------------------------------------
D_X0, D_X1, D_Y0, D_Y1, D_Z0, D_Z1 = 61.0, 149.0, -9.0, -4.5, 1.0, 209.0
D_MID = (D_Y0 + D_Y1) / 2


def rect_ring(x0, x1, z0, z1, y, e=0.0):
    return [(x0 - e, y, z0 - e), (x1 + e, y, z0 - e), (x1 + e, y, z1 + e), (x0 - e, y, z1 + e)]


def door():
    body = bevelled(box_bm(D_X0, D_X1, D_Y0, D_Y1, D_Z0, D_Z1), 0.3, 2, 30)
    stile, muntin = 11.5, 10.0
    xm = (D_X0 + D_X1) / 2
    cols = [(D_X0 + stile, xm - muntin / 2), (xm + muntin / 2, D_X1 - stile)]
    rows = [(D_Z0 + 22.0, 88.0), (112.0, D_Z1 - 12.0)]          # bottom rail 22, lock rail 88..112, top 12
    cutters, fields = [], []
    for side in (1, -1):
        def yy(y):                                              # room side as authored, mirrored for corridor
            return y if side == 1 else 2 * D_MID - y
        for x0, x1 in cols:
            for z0, z1 in rows:
                # chamfer-stuck recess 1.4 deep (0.9 wide chamfer at the face)
                cutters.append(loft([rect_ring(x0, x1, z0, z1, yy(-5.9)),
                                     rect_ring(x0, x1, z0, z1, yy(-4.2), 1.09)]))
                # raised field: 0.5 groove, 0.3 lip, 3 cm bevelled field rising to 0.3 below the face
                fields.append(loft([rect_ring(x0, x1, z0, z1, yy(-5.95), -0.5),
                                    rect_ring(x0, x1, z0, z1, yy(-5.6), -0.62),
                                    rect_ring(x0, x1, z0, z1, yy(-4.8), -3.5)]))
    body = boolean(body, [merge_bms(cutters)], "DIFFERENCE")
    body = boolean(body, [merge_bms(fields)], "UNION")
    return [(box_lm(body, prefer=1), "M_DoorTimber"), (box_lm(hinge_knuckles()), "M_Metal")]


def hinge_knuckles():
    """Three butt-hinge knuckles with domed finials on the hinge edge, room side (the door swings in).
    The 0.2 door/lining gap is too narrow to hold a knuckle, so each barrel stands just proud of the
    door face beside the edge: 0.2 clear of the lining face (X 60.8) and of the door face (Y -4.5)."""
    r = 0.65
    kx, ky = DOOR["x0"] + 0.8 + GAP + r, D_Y1 + GAP + r
    prof = [(0, -5.5), (0.22, -5.47), (0.38, -5.38), (0.46, -5.24), (0.48, -5.1), (r - 0.04, -5.04),
            (r, -4.96), (r, 4.96), (r - 0.04, 5.04), (0.48, 5.1), (0.46, 5.24), (0.38, 5.38), (0.22, 5.47),
            (0, 5.5)]
    return merge_bms([lathe(prof, 14, "Z", (kx, ky, z)) for z in (25.0, 105.0, 185.0)])


def door_frame():
    hint = (0, 1, 0)                  # side = outward from the opening, up = +Y (room)
    lp = [(0, -15.0), (0, -GAP), (0.8, -GAP), (0.8, -9.2), (2.0, -9.2), (2.2, -9.4), (2.2, -11.0),
          (2.0, -11.2), (0.8, -11.2), (0.8, -15.0)]
    lining = sweep([(-s, y) for s, y in lp],
                   [(DOOR["x0"], 0, 0), (DOOR["x0"], 0, DOOR["z1"]), (DOOR["x1"], 0, DOOR["z1"]), (DOOR["x1"], 0, 0)],
                   hint, seg=80.0)
    sx0, sx1, sz = DOOR["x0"] + ARCH_SIGHT, DOOR["x1"] - ARCH_SIGHT, DOOR["z1"] - ARCH_SIGHT
    arch = sweep(architrave_profile(ARCH_W), [(sx0, 0, 0), (sx0, 0, sz), (sx1, 0, sz), (sx1, 0, 0)], hint, seg=80.0)
    return [(lining, "M_PaintedTimber"), (arch, "M_PaintedTimber")]


HX, HZ, HY = 137.0, 102.0, D_Y1      # rose centre on the room face of the door


def rounded_rect(hu, hv, r, segs=3):
    pts = []
    for cx, cy, a0 in ((hu - r, hv - r, 0), (-hu + r, hv - r, 90), (-hu + r, -hv + r, 180), (hu - r, -hv + r, 270)):
        for i in range(segs + 1):
            a = math.radians(a0 + 90.0 * i / segs)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def door_handle():
    y0 = HY + 0.1
    rose = [(0, y0), (2.6, y0), (2.6, y0 + 0.3), (2.54, y0 + 0.48), (2.3, y0 + 0.65),
            (1.55, y0 + 0.9), (1.33, y0 + 1.08), (1.25, y0 + 1.35), (1.25, y0 + 3.0),
            (1.17, y0 + 3.27), (0.88, y0 + 3.4), (0, y0 + 3.4)]
    rose_bm = lathe(rose, 24, "Y", (HX, 0, HZ))

    # lever: out of the neck, 90 degree bend toward the hinge side, grip, curved return to the door
    pts = [(HX, y0 + 1.6, HZ), (HX, 1.3, HZ), (123.6, 1.3, HZ), (122.0, -1.3, HZ)]
    path = fillet(pts, [0, 2.3, 2.0, 0], 4)
    L = [0.0]
    for a, b in zip(path[:-1], path[1:]):
        L.append(L[-1] + (b - a).length)
    scales = [1.0 + 0.10 * smoothstep(min(1.0, l / (L[-1] * 0.55))) for l in L]
    lever = sweep(rounded_rect(0.62, 0.92, 0.42, 2), path, (0, 0, 1), scales=scales, round_end=2, lm=False)
    handle = boolean(rose_bm, [lever], "UNION")

    ez = HZ - 8.5
    esc = [(0, y0), (1.7, y0), (1.7, y0 + 0.25), (1.48, y0 + 0.5), (1.1, y0 + 0.6),
           (0.55, y0 + 0.75), (0.5, y0 + 0.9), (0.5, y0 + 1.2), (0.42, y0 + 1.3), (0, y0 + 1.3)]
    esc_bm = lathe(esc, 20, "Y", (HX, 0, ez))
    turn = bmesh.new()
    bmesh.ops.create_uvsphere(turn, u_segments=10, v_segments=6, radius=1.0)
    for v in turn.verts:
        v.co = Vector((HX + v.co.x * 0.32, y0 + 1.75 + v.co.y * 0.55, ez + v.co.z * 1.15))
    esc_bm = boolean(esc_bm, [turn], "UNION")
    return [(handle, "M_Metal"), (esc_bm, "M_Metal")]


# ------------------------------------------------------------------ finalize / UV / export / preview
def finalize(name, parts, sharp_deg=35.0):
    mats = []
    allbm = bmesh.new()
    if any(bm.loops.layers.uv.get("Lightmap") for bm, m in parts):
        allbm.loops.layers.uv.new("Lightmap")
    for bm, m in parts:
        if m not in mats:
            mats.append(m)
        for f in bm.faces:
            f.material_index = mats.index(m)
        tmp = bpy.data.meshes.new("tmp")
        bm.to_mesh(tmp)
        bm.free()
        allbm.from_mesh(tmp)
        bpy.data.meshes.remove(tmp)
    for v in allbm.verts:
        v.co = Vector((v.co.x / 100.0, -v.co.y / 100.0, v.co.z / 100.0))
    bmesh.ops.reverse_faces(allbm, faces=allbm.faces[:])
    bmesh.ops.remove_doubles(allbm, verts=allbm.verts[:], dist=1e-6)
    bmesh.ops.triangulate(allbm, faces=allbm.faces[:], quad_method="BEAUTY", ngon_method="BEAUTY")
    me = bpy.data.meshes.new(name)
    allbm.to_mesh(me)
    allbm.free()
    for m in mats:
        me.materials.append(mat(m))
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    me.shade_smooth()
    me.set_sharp_from_angle(angle=math.radians(sharp_deg))
    wn = ob.modifiers.new("wn", "WEIGHTED_NORMAL")
    wn.mode = "FACE_AREA"
    wn.keep_sharp = True
    dg = bpy.context.evaluated_depsgraph_get()
    me2 = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    ob.modifiers.clear()
    ob.data = me2
    bpy.data.meshes.remove(me)
    me2.name = name
    return ob


def uv_world_and_lightmap(ob, margin=0.02):
    """UV0 'UVMap': 1 m world box projection. UV1 'Lightmap': the procedural unwrap written by the
    builders (sweeps / box_lm, in cm) when present, otherwise smart project; then averaged and packed
    into 0..1 with a 2% margin."""
    me = ob.data
    pre = None
    if "Lightmap" in me.uv_layers:
        pre = [d.uv.copy() for d in me.uv_layers["Lightmap"].data]
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
    if pre is not None:
        for d, uv in zip(uv1.data, pre):
            d.uv = uv / 100.0
    me.uv_layers.active = uv1
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.context.scene.tool_settings.use_uv_select_sync = True      # UV ops act on the mesh selection
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    if pre is None:
        bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=margin, scale_to_bounds=False)
    bpy.ops.uv.average_islands_scale()
    bpy.ops.uv.pack_islands(margin_method="FRACTION", margin=margin, rotate=True)
    bpy.ops.object.mode_set(mode="OBJECT")
    me.uv_layers.active = uv0
    uv0.active_render = True


def export(ob):
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
    sh = sc.display.shading
    sh.light = "STUDIO"
    sh.color_type = "MATERIAL"
    sh.show_cavity = True
    sh.cavity_type = "BOTH"
    sh.show_shadows = True
    sh.shadow_intensity = 0.35
    sc.display.render_aa = "16"
    sc.view_settings.view_transform = "Standard"
    w = bpy.data.worlds.new("White")
    w.color = (1.0, 1.0, 1.0)
    sc.world = w
    cd = bpy.data.cameras.new("Cam")
    cd.lens = 50
    cd.sensor_fit = "HORIZONTAL"
    cd.sensor_width = 36
    cd.clip_start = 0.005
    cd.clip_end = 100
    cam = bpy.data.objects.new("Cam", cd)
    sc.collection.objects.link(cam)
    sc.camera = cam
    return cam


def render(cam, objs, path, d_ue, focus=None):
    """Frame objs (or a UE-cm focus box (lo, hi)) from UE direction d_ue."""
    sc = bpy.context.scene
    for o in sc.objects:
        o.hide_render = (o.type == "MESH" and o not in objs)
    bpy.context.view_layer.update()
    if focus:
        lo, hi = focus
        pts = [Vector((x / 100, -y / 100, z / 100)) for x in (lo[0], hi[0]) for y in (lo[1], hi[1])
               for z in (lo[2], hi[2])]
    else:
        pts = [o.matrix_world @ Vector(c) for o in objs for c in o.bound_box]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    c = (lo + hi) / 2
    d = Vector((d_ue[0], -d_ue[1], d_ue[2])).normalized()
    cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    bpy.context.view_layer.update()
    r = cam.matrix_world.to_3x3().col[0]
    u = cam.matrix_world.to_3x3().col[1]
    f = -d
    tx = 18.0 / 50.0 * 0.9
    ty = tx * 700.0 / 900.0
    D = max(max(abs((p - c).dot(r)) / tx, abs((p - c).dot(u)) / ty) - (p - c).dot(f) for p in pts)
    cam.location = c + d * D
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)


def tris(ob):
    return sum(len(p.vertices) - 2 for p in ob.data.polygons)


VIEWS = {
    "SM_Floor": (-0.6, -0.8, 0.9), "SM_Ceiling": (-0.6, -0.8, -0.9),
    "SM_Wall_North": (-1.0, -0.4, 0.3), "SM_Wall_South": (1.0, 0.4, 0.3),
    "SM_Wall_West": (0.35, 1.0, 0.3), "SM_Wall_East": (0.35, -1.0, 0.3),
    "SM_Skirting": (-0.7, -0.9, 1.1), "SM_Cornice": (-0.7, -0.9, -0.8),
    "SM_WindowFrame": (-1.0, -0.55, 0.3), "SM_Door": (0.45, 1.0, 0.2),
    "SM_DoorFrame": (0.45, 1.0, 0.2), "SM_DoorHandle": (0.55, 1.0, 0.35),
}
DETAILS = {   # extra close-ups (UE-cm focus boxes) written next to the main preview
    "SM_Skirting": [("corner", ((470, -5, 0), (500, 30, 12)), (-1.0, 0.8, 0.5)),
                    ("door_end", ((150, -2, 0), (168, 4, 12)), (0.3, 1.0, 0.4))],
    "SM_Cornice": [("corner", ((480, 430, 258), (500, 450, 270)), (-1.0, -0.8, -0.5))],
    "SM_WindowFrame": [("sill_corner", ((484, 86, 70), (515, 116, 100)), (-1.0, 0.6, 0.45)),
                       ("mullion", ((495, 205, 195), (515, 245, 222)), (-1.0, 0.35, -0.2))],
    "SM_Door": [("panel", ((100, -10, 80), (150, -3, 125)), (0.6, 1.0, 0.4))],
    "SM_DoorFrame": [("head_corner", ((45, -12, 195), (75, 3, 220)), (0.6, 1.0, 0.3))],
    "SM_DoorHandle": [("side", ((118, -5, 88), (142, 3, 106)), (0.0, 1.0, 0.05)),
                      ("top", ((118, -5, 88), (142, 3, 106)), (0.05, 0.3, 1.0))],
}


def build():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(PREV, exist_ok=True)
    builders = [
        ("SM_Floor", floor_piece, 35), ("SM_Ceiling", ceiling_piece, 35),
        ("SM_Wall_North", wall_north, 35), ("SM_Wall_South", wall_south, 35),
        ("SM_Wall_East", wall_east, 35), ("SM_Wall_West", wall_west, 35),
        ("SM_Skirting", skirting, 35), ("SM_Cornice", cornice, 35),
        ("SM_WindowFrame", window_frame, 35), ("SM_Door", door, 35),
        ("SM_DoorFrame", door_frame, 35), ("SM_DoorHandle", door_handle, 40),
    ]
    obs = []
    for name, fn, sharp in builders:
        ob = finalize(name, fn(), sharp)
        uv_world_and_lightmap(ob, 0.01 if name == "SM_WindowFrame" else 0.02)
        export(ob)
        obs.append(ob)
        print("SHELL %-16s %6d tris" % (name, tris(ob)))
    cam = setup_render()
    for ob in obs:
        render(cam, [ob], os.path.join(PREV, ob.name + ".png"), VIEWS[ob.name])
        for tag, box, d in DETAILS.get(ob.name, []):
            render(cam, [ob], os.path.join(PREV, "Assembly_shell", "%s_%s.png" % (ob.name, tag)), d, box)
    # whole shell interior trims together, from the door
    trims = [o for o in obs if o.name not in ("SM_Ceiling", "SM_Wall_West")]
    render(cam, trims, os.path.join(PREV, "Assembly_shell", "shell_from_door.png"), (0.5, 1.0, 0.45),
           ((300, 0, 0), (515, 450, 270)))
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ITEMS, "shell.blend"))


build()
