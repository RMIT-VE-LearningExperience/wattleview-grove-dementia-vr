"""Blender (headless): room fixtures for Maria's room.

Run:
  "C:\\Program Files\\Blender Foundation\\Blender 5.0\\blender.exe" -b --factory-startup --python fixtures.py

Pieces: SM_FloorLamp, SM_CeilingFan, SM_Curtains, SM_CurtainRod, SM_Rug, SM_PlantPot,
SM_PhotoFrame_MariaEnzo, SM_PhotoFrame_Small, SM_PhotoFrame_Wide, SM_Calendar.

Follows SourceArt/Room/CONVENTIONS.md and placement.json:
  * Modelled in centimetres, scaled 0.01 -> Blender metres on join. U(x, y, z) converts Unreal cm to
    Blender-axis cm (Y mirrored), so anything placed in room coordinates goes through U().
  * Pivots: floor pieces bottom centre; wall pieces back centre (front +X); SM_CeilingFan at the
    ceiling mount (canopy top at z 0, geometry hangs into -Z); SM_Curtains / SM_CurtainRod at the
    world origin (built in room coordinates).
  * Real shapes: lathed turned parts (Screw modifier), swept rods / brackets / wires, cloth-simulated
    curtains (pinned heading, collision with floor / wall line / TV cabinet), moulded frames with a
    profile run around the rectangle with mitred corners, closed thin leaves and petals.
  * No interpenetration: resting parts keep 0.2 cm air gaps; plant leaves are placed with a clearance
    test against everything already built.
  * UV0 'UVMap': 1 m box projection; M_Photo faces get their own 0..1 map; curtains use the unfolded
    cloth (metres). UV1 'Lightmap': unfolded cloth for curtains, smart project for the rest, packed
    with a 2 % margin.
Exports SourceArt/Room/Export/SM_<Name>.fbx and Previews/SM_<Name>.png (Workbench, studio light).
"""
import math
import os
import random
import time

import bmesh
import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

ROOM = r"D:\Unreal-Projects\WattleviewGrove-ue58\SourceArt\Room"
EXPORT = os.path.join(ROOM, "Export")
PREVIEW = os.path.join(ROOM, "Previews")
GAP = 0.2

MATS = {
    "M_Timber": (0.66, 0.50, 0.33), "M_TimberDark": (0.30, 0.18, 0.10),
    "M_Metal": (0.62, 0.63, 0.65), "M_Brass": (0.72, 0.54, 0.24),
    "M_PlasticWhite": (0.90, 0.90, 0.88), "M_PlasticBlack": (0.05, 0.05, 0.055),
    "M_Glass": (0.86, 0.88, 0.88), "M_LampShade": (0.90, 0.84, 0.70),
    "M_Curtain": (0.88, 0.86, 0.80), "M_Rug": (0.62, 0.50, 0.33),
    "M_Ceramic": (0.70, 0.36, 0.22), "M_Soil": (0.20, 0.13, 0.08),
    "M_Plant": (0.20, 0.42, 0.14), "M_FlowerRed": (0.82, 0.10, 0.10),
    "M_Paper": (0.95, 0.94, 0.90), "M_Photo": (0.40, 0.52, 0.36),
    "M_Flower": (0.98, 0.86, 0.25), "M_Gold": (0.83, 0.66, 0.28),
}


def U(x, y, z):
    """Unreal cm -> Blender-axis cm (Y mirrored)."""
    return Vector((x, -y, z))


def smoothstep(a, b, x):
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def mat(name):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.diffuse_color = (*MATS[name], 1.0)
    m.roughness = 0.5
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
    return new


def set_mat(ob, m):
    ob.data.materials.clear()
    ob.data.materials.append(mat(m))
    for p in ob.data.polygons:
        p.material_index = 0
    return ob


def assign_mats(ob, fn):
    """Per-face material by a function of the face centre (cm, object space)."""
    me = ob.data
    picks = [fn(p.center) for p in me.polygons]
    names = []
    for n in picks:
        if n not in names:
            names.append(n)
    me.materials.clear()
    for n in names:
        me.materials.append(mat(n))
    for p, n in zip(me.polygons, picks):
        p.material_index = names.index(n)
    return ob


def smooth(ob, angle=40.0, recalc=True, dedupe=True):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    if dedupe:
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


def bm_object(bm, names, name, angle=40.0, recalc=True):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for n in names:
        me.materials.append(mat(n))
    ob = link(name, me)
    return smooth(ob, angle, recalc)


# ------------------------------------------------------------------ primitives
def lathe(profile, seg, m, name="lathe", angle_smooth=40.0, closed=False):
    """Revolve a 2D (r, z) profile around Z with the Screw modifier, then apply it."""
    pts = list(profile) + ([profile[0]] if closed else [])
    verts = [(r, 0.0, z) for r, z in pts]
    edges = [(i, i + 1) for i in range(len(verts) - 1)]
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, edges, [])
    ob = link(name, me)
    mod = ob.modifiers.new("screw", "SCREW")
    mod.axis = "Z"
    mod.angle = 2 * math.pi
    mod.steps = seg
    mod.render_steps = seg
    mod.use_merge_vertices = True
    mod.merge_threshold = 1e-3
    mod.use_normal_calculate = True
    ob = bake(ob)
    set_mat(ob, m)
    return smooth(ob, angle_smooth)


def sweep(points, radius, m, res=4, bevel_res=1, radii=None, cyclic=False, bevel_obj=None,
          caps=True, kind="BEZIER", name="sweep", angle_smooth=60.0):
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


def slab(outline, z0, z1, m, bevel=0.0, seg=1, name="slab", angle_smooth=40.0):
    """Extrude a 2D outline (cm, XY) from z0 to z1 and bevel its cap rims."""
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
    return bm_object(bm, [m], name, angle_smooth)


def ball(c, r, m, u=8, v=5, name="ball", angle_smooth=80.0):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=u, v_segments=v, radius=r)
    for vt in bm.verts:
        vt.co = vt.co + Vector(c)
    return bm_object(bm, [m], name, angle_smooth)


def torus(c, R, r, axis, m, nu=10, nv=4, name="torus"):
    """Torus centred at c whose hole runs along `axis` ('X'|'Y'|'Z')."""
    a = {"X": Vector((1, 0, 0)), "Y": Vector((0, 1, 0)), "Z": Vector((0, 0, 1))}[axis]
    e1 = {"X": Vector((0, 1, 0)), "Y": Vector((1, 0, 0)), "Z": Vector((1, 0, 0))}[axis]
    e2 = a.cross(e1)
    bm = bmesh.new()
    V = []
    for i in range(nu):
        t = 2 * math.pi * i / nu
        d = e1 * math.cos(t) + e2 * math.sin(t)
        row = []
        for j in range(nv):
            s = 2 * math.pi * (j + 0.5) / nv
            row.append(bm.verts.new(Vector(c) + d * (R + r * math.cos(s)) + a * (r * math.sin(s))))
        V.append(row)
    for i in range(nu):
        for j in range(nv):
            bm.faces.new((V[i][j], V[(i + 1) % nu][j], V[(i + 1) % nu][(j + 1) % nv], V[i][(j + 1) % nv]))
    return bm_object(bm, [m], name, 70)


def frame_sweep(frames, section, m, name="fsweep", angle_smooth=50.0):
    """Sweep a 2D (b, c) section along explicit frames [(P, S, N)] -> closed tube with end caps."""
    bm = bmesh.new()
    rings = []
    for P, S, N in frames:
        rings.append([bm.verts.new(P + S * b + N * c) for b, c in section])
    n = len(section)
    for k in range(len(rings) - 1):
        for i in range(n):
            bm.faces.new((rings[k][i], rings[k][(i + 1) % n], rings[k + 1][(i + 1) % n], rings[k + 1][i]))
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])
    return bm_object(bm, [m], name, angle_smooth)


def tube(points, radius, m, sides=3, cyclic=False, up=None, name="tube", angle_smooth=180.0, phase=0.0,
         caps=True):
    """Polygon-section tube through explicit points (cm): closed (end caps, or a cyclic loop).
    radius: a number or one radius per point (tapered tube).
    up: fixed plane normal for planar paths, otherwise parallel-transported frames."""
    P = [Vector(p) for p in points]
    n = len(P)
    rads = list(radius) if isinstance(radius, (list, tuple)) else [radius] * n
    T = []
    for i in range(n):
        if cyclic:
            a, b = P[(i - 1) % n], P[(i + 1) % n]
        else:
            a, b = P[max(i - 1, 0)], P[min(i + 1, n - 1)]
        T.append((b - a).normalized())
    frames = []
    if up is not None:
        upv = Vector(up).normalized()
        for t in T:
            s = t.cross(upv).normalized()
            frames.append((s, upv))
    else:
        ref = Vector((0, 0, 1)) if abs(T[0].z) < 0.9 else Vector((1, 0, 0))
        s = T[0].cross(ref).normalized()
        for t in T:
            s = (s - t * s.dot(t)).normalized()
            frames.append((s, t.cross(s).normalized()))
    bm = bmesh.new()
    rings = []
    for i in range(n):
        s, nn = frames[i]
        ring = []
        for k in range(sides):
            a = 2 * math.pi * k / sides + phase
            ring.append(bm.verts.new(P[i] + (s * math.cos(a) + nn * math.sin(a)) * rads[i]))
        rings.append(ring)
    for i in range(n if cyclic else n - 1):
        a, b = rings[i], rings[(i + 1) % n]
        for k in range(sides):
            bm.faces.new((a[k], a[(k + 1) % sides], b[(k + 1) % sides], b[k]))
    if not cyclic and caps:
        bm.faces.new(list(reversed(rings[0])))
        bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm_object(bm, [m], name, angle_smooth, recalc=False)


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


# ------------------------------------------------------------------ clearance tests (cm space)
def tri_bvh(objs):
    verts, polys = [], []
    for o in objs:
        mw = o.matrix_world
        off = len(verts)
        verts.extend(mw @ v.co for v in o.data.vertices)
        polys.extend([off + i for i in p.vertices] for p in o.data.polygons)
    return BVHTree.FromPolygons(verts, polys, epsilon=0.0) if polys else None


def is_clear(ob, others, margin):
    tree = tri_bvh(others)
    if tree is None:
        return True
    mine = tri_bvh([ob])
    if tree.overlap(mine):
        return False
    for v in ob.data.vertices:
        if tree.find_nearest(v.co, margin)[0] is not None:
            return False
    # also test the other way (their verts near my faces)
    for o in others:
        for v in o.data.vertices:
            if mine.find_nearest(v.co, margin)[0] is not None:
                return False
    return True


def kill(ob):
    me = ob.data
    bpy.data.objects.remove(ob, do_unlink=True)
    if me.users == 0:
        bpy.data.meshes.remove(me)


# ====================================================================== SM_FloorLamp
def floor_lamp():
    # Turned brass base and slim pole, black socket cup (one lathe; materials by height).
    prof = [(0.0, 0.5), (13.0, 0.5), (13.4, 0.0), (14.4, 0.0), (14.6, 0.9), (13.6, 2.2), (9.0, 3.6),
            (4.8, 5.3), (3.2, 6.8), (3.3, 8.0), (1.15, 9.0), (1.1, 145.8), (2.05, 146.6),
            (2.05, 151.3), (1.6, 151.5), (1.6, 148.6), (0.0, 148.6)]
    body = lathe(prof, 22, "M_Brass", name="lamp_body", angle_smooth=35)
    # Keep the lower socket collar brass so the pole visibly meets the shade in the room.
    # Making the entire socket black caused the narrow connection to disappear against the
    # shaded wall on mobile, which made the lampshade look as though it was floating.
    assign_mats(body, lambda c: "M_PlasticBlack" if c.z > 148.8 else "M_Brass")
    # Frosted A60 bulb screwed into the cup (0.25 cm clear of the cup wall and floor).
    bulb_p = [(0.0, 148.85), (1.32, 148.85), (1.32, 151.9), (1.75, 152.7), (2.5, 154.5), (3.0, 156.6),
              (3.0, 158.4), (2.5, 160.6), (1.4, 161.8), (0.0, 162.1)]
    bulb = lathe(bulb_p, 12, "M_PlasticWhite", name="bulb", angle_smooth=50)
    assign_mats(bulb, lambda c: "M_Brass" if c.z < 152.3 else "M_PlasticWhite")
    # Fabric drum shade, open top and bottom, 0.3 cm wall, top hem rolled over the wire ring.
    shade_p = [(18.65, 147.6), (18.95, 147.6), (17.75, 178.0), (17.05, 178.0), (17.05, 177.0),
               (17.45, 176.8)]
    shade = lathe(shade_p, 32, "M_LampShade", name="shade", angle_smooth=50, closed=True)
    # Uno fitter: hub ring round the socket and three arms up to the shade's top hem.
    hub = lathe([(2.3, 147.0), (3.0, 147.0), (3.0, 147.6), (2.3, 147.6)], 12, "M_Brass",
                name="hub", angle_smooth=30, closed=True)
    parts = [body, bulb, shade, hub]
    for k in range(3):
        a = math.radians(90 + 120 * k)
        d = Vector((math.cos(a), math.sin(a), 0))
        p0 = d * 3.25 + Vector((0, 0, 147.3))
        p1 = d * 10.5 + Vector((0, 0, 163.5))
        p2 = d * 16.65 + Vector((0, 0, 177.5))
        parts.append(sweep([p0, p1, p2], 0.15, "M_Brass", res=2, bevel_res=0, name="arm"))
    return join("SM_FloorLamp", parts)


# ====================================================================== SM_CeilingFan
def ceiling_fan():
    # Canopy, downrod, motor housing, switch cup and light bowl: one coaxial lathe.
    prof = [(0.0, 0.0), (6.4, 0.0), (7.4, -1.0), (7.3, -3.6), (5.2, -6.0), (2.0, -7.1), (1.1, -7.6),
            (1.1, -20.6), (2.3, -21.2), (2.3, -22.3), (6.2, -22.8), (9.8, -24.4), (11.0, -27.0),
            (10.6, -29.8), (9.0, -31.6), (6.5, -32.2), (6.5, -34.4), (7.6, -35.0), (7.3, -38.8),
            (5.2, -42.8), (2.6, -44.6), (0.0, -45.0)]
    body = lathe(prof, 20, "M_PlasticWhite", name="fan_body", angle_smooth=40)
    assign_mats(body, lambda c: "M_Glass" if c.z < -34.7 else "M_PlasticWhite")
    parts = [body]

    pitch = math.radians(12.0)
    z_axis = -35.4          # blade mid-plane on its long axis
    th_b, th_br = 0.9, 0.5  # blade and bracket thickness
    c0 = th_b / 2 + GAP + th_br / 2

    # Blade outline (a radial, b tangential): tapered paddle, rounded tip, eased root corners.
    a0, a_tip_c, w0, w1 = 20.0, 61.4, 4.75, 6.6
    right = []
    for t in (0.06, 0.3, 0.55, 0.8, 1.0):
        a = a0 + 1.2 + (a_tip_c - a0 - 1.2) * t
        right.append((a, -(w0 + (w1 - w0) * t ** 0.8)))
    tip = [(a_tip_c + w1 * math.cos(math.radians(t)), w1 * math.sin(math.radians(t)))
           for t in (-60, -30, 0, 30, 60)]
    left = [(a, -b) for a, b in reversed(right)]
    root = [(a0 + 0.35, w0 - 0.25), (a0, w0 - 1.2), (a0, -(w0 - 1.2)), (a0 + 0.35, -(w0 - 0.25))]
    outline = right + tip + left + root
    # bracket path (blade frame): under the motor floor, then down and out onto the blade
    path = [(7.4, -32.65, 0.0), (10.5, -32.65, 0.0), (13.5, -33.0, 0.3), (16.5, -33.85, 0.75),
            (19.0, None, 1.0), (24.0, None, 1.0), (31.0, None, 1.0)]
    section = [(1.5, 0.25), (-1.5, 0.25), (-1.5, -0.25), (1.5, -0.25)]
    for k in range(3):
        rot = Matrix.Rotation(math.radians(120 * k + 30), 4, "Z")
        blade = slab(outline, -th_b / 2, th_b / 2, "M_Timber", bevel=0.2, seg=1, name="blade",
                     angle_smooth=45)
        xform(blade, rot @ Matrix.Translation((0, 0, z_axis)) @ Matrix.Rotation(pitch, 4, "X"))
        parts.append(blade)
        frames = []
        pts = []
        for a, z, w in path:
            phi = pitch * w
            if z is None:
                P = Vector((a, -c0 * math.sin(pitch), z_axis + c0 * math.cos(pitch)))
            else:
                P = Vector((a, -c0 * math.sin(phi) * w, z))
            pts.append((P, phi))
        for i, (P, phi) in enumerate(pts):
            Pn = pts[min(i + 1, len(pts) - 1)][0]
            Pp = pts[max(i - 1, 0)][0]
            T = (Pn - Pp).normalized()
            Y = Vector((0, 1, 0))
            N0 = T.cross(Y).normalized()
            S0 = N0.cross(T).normalized()
            S = S0 * math.cos(phi) + N0 * math.sin(phi)
            N = -S0 * math.sin(phi) + N0 * math.cos(phi)
            frames.append((P, S, N))
        br = frame_sweep(frames, section, "M_Metal", name="bracket", angle_smooth=40)
        xform(br, rot)
        parts.append(br)
    return join("SM_CeilingFan", parts)


# ====================================================================== SM_CurtainRod
ROD_X, ROD_Z, ROD_R = 479.0, 243.0, 1.1
# Three brackets: one near each end and a centre support at Y 225 in the gap between the panels
# (112..338), so the 3.9 m run has no long unsupported span.
BRACKET_Y = (38.0, 225.0, 412.0)


def curtain_rod():
    # Rod: a plain open tube (12 sides) between the finial collars; three intermediate rings only
    # give the lightmap chunker faces to cut. Its open ends hide inside the finial collars.
    S0, S1 = 35.6, 414.4                           # tube ends, 0.1 cm off each collar's back face
    prof = [(ROD_R, S0 + (S1 - S0) * k / 4) for k in range(5)]
    rod = lathe(prof, 12, "M_Metal", name="rod", angle_smooth=40)
    # Ball finials: own lathes at 20 sides (a round silhouette at 0.3 m): a 44 mm ball (profile
    # points on the sphere every 45 deg, smooth shaded), a neck and a flared collar (r 1.45 at
    # s 35.5) that covers the 12-sided tube end. The collar back stays open (it faces the tube end
    # 0.1 cm away and is never seen).
    BR, BC = 2.2, 32.2
    fin = [(BR * math.sin(math.radians(a)), BC - BR * math.cos(math.radians(a))) for a in (0, 45, 90, 135)]
    fin += [(0.9, 34.35), (1.45, 35.5)]
    fin_a = lathe(fin, 20, "M_Metal", name="finial", angle_smooth=50)
    fin_b = lathe([(r, 450.0 - z) for r, z in fin], 20, "M_Metal", name="finial", angle_smooth=50)
    # lathe axis Z (= Unreal Y) -> Blender: X = x + 479, Y = -z, Z = y + 243
    M = Matrix(((1, 0, 0, ROD_X), (0, 0, -1, 0), (0, 1, 0, ROD_Z), (0, 0, 0, 1)))
    for o in (rod, fin_a, fin_b):
        xform(o, M)
    for o in (rod, fin_a, fin_b):  # open lathes (and the mirrored profile): point normals outward
        bm = bmesh.new()
        bm.from_mesh(o.data)
        cen = sum((v.co for v in bm.verts), Vector()) / len(bm.verts)
        bm.faces.ensure_lookup_table()
        out = sum((f.calc_center_median() - cen).dot(f.normal) * f.calc_area() for f in bm.faces)
        if out < 0:
            bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
        bm.to_mesh(o.data)
        bm.free()
        smooth(o, 50, recalc=False)
    parts = [rod, fin_a, fin_b]
    # Bracket: turned wall rose (r 3.2), a tapered round arm (r 0.85 at the wall -> 0.65 at the bend),
    # a short vertical neck and a closed holder ring round the rod with 0.2 cm air all round.
    RING_MR = 0.4                                   # holder ring section radius
    RING_R0 = ROD_R + GAP + RING_MR                 # 1.7 centreline radius
    z_ring_bot = ROD_Z - RING_R0 - RING_MR          # 240.9 outer bottom of the ring
    Rb = 1.3                                        # bend radius arm -> neck
    zarm = z_ring_bot - Rb - 0.5                    # 239.1 arm centreline
    # (back face against the wall left open: never seen)
    ROSE = [(3.2, 0.0), (3.2, 0.3), (1.15, 1.6), (0.0, 1.6)]
    X_BACK = 499.8
    x_arm0 = X_BACK - ROSE[-1][1] - 0.03            # arm seats on the rose socket face
    cx, cz = ROD_X + Rb, zarm + Rb                  # bend centre (Unreal x, z)
    path = [(x_arm0, zarm), (cx, zarm)]
    path += [(cx + Rb * math.cos(math.radians(t)), cz + Rb * math.sin(math.radians(t))) for t in (-120, -150)]
    path += [(ROD_X, cz), (ROD_X, z_ring_bot + 0.25)]     # neck ends inside the ring section
    radii = [0.85, 0.65, 0.58, 0.5, 0.44, 0.36]
    for yb in BRACKET_Y:
        rose = lathe(ROSE, 16, "M_Metal", name="rose", angle_smooth=40)
        # lathe (r_x, r_y, h) -> Blender X = 499.8 - h, Y = -yb + r_y, Z = zarm + r_x
        xform(rose, Matrix(((0, 0, -1, X_BACK), (0, 1, 0, -yb), (1, 0, 0, zarm), (0, 0, 0, 1))))
        parts.append(rose)
        ring = torus(U(ROD_X, yb, ROD_Z), RING_R0, RING_MR, "Y", "M_Metal", nu=16, nv=5, name="holder")
        arm = tube([U(x, yb, z) for x, z in path], radii, "M_Metal", sides=8, up=(0, 1, 0), name="bracket",
                   angle_smooth=50, phase=math.pi / 8)
        # weld the neck into the holder ring (one cast piece): exact boolean union, then drop the ring
        mod = arm.modifiers.new("weld", "BOOLEAN")
        mod.operation = "UNION"
        mod.solver = "EXACT"
        mod.object = ring
        arm = bake(arm)
        kill(ring)
        # drop the arm's wall-end cap: it sits 0.03 cm off the rose's socket face and is never seen
        bm = bmesh.new()
        bm.from_mesh(arm.data)
        cap = [f for f in bm.faces if all(abs(v.co.x - x_arm0) < 1e-3 for v in f.verts)]
        bmesh.ops.delete(bm, geom=cap, context="FACES_ONLY")
        bm.to_mesh(arm.data)
        bm.free()
        parts.append(smooth(arm, 60, recalc=False))
    return join("SM_CurtainRod", parts)


# ====================================================================== SM_Curtains
CUR_TOP = 241.0
CUR_BOTTOM = 2.0                   # pre-sim hem height; the sheer stretches a little under gravity
RING_R, RING_r = 1.55, 0.2
CUR_NRING, CUR_C = 7, 6
HEM_OFF = 0.3                      # hem layers sit 0.3 cm behind the face fabric


def curtain_panel(y0, y1, inner_y, seed):
    """Pre-folded sheer panel between Unreal y0..y1 hanging from rings, as a grid (rows top->bottom).
    Fold depth and pitch vary per pleat; ring spacing is jittered."""
    rnd = random.Random(seed)
    NRING, C = CUR_NRING, CUR_C
    span = (y1 - y0 - 1.0) / (NRING - 1)
    ring_y = [y0 + 0.5 + k * span + (rnd.uniform(-1.5, 1.5) if 0 < k < NRING - 1 else 0.0)
              for k in range(NRING)]
    U_ = (NRING - 1) * C
    # ~32 rows, none taller than ~8.3 cm, so a fold crest drifting sideways never jumps a column
    # between two rows (no stair-step kinks in oblique silhouettes)
    steps = [2, 3, 4, 5, 6, 7] + [8] * 24 + [7, 6]
    sc = (CUR_TOP - CUR_BOTTOM) / sum(steps)
    zs = [CUR_TOP]
    for s in steps:
        zs.append(zs[-1] - s * sc)
    zs[-1] = CUR_BOTTOM
    A0 = [rnd.uniform(4.0, 9.0) for _ in range(NRING - 1)]
    ph = [rnd.uniform(0, 6.28) for _ in range(3 * (NRING - 1))]
    outer_is_low = inner_y > (y0 + y1) / 2          # left panel: outer edge is the low-Y edge
    outer_y = y0 + 0.5 if outer_is_low else y1 - 0.5
    inner = y1 - 0.5 if outer_is_low else y0 + 0.5
    grid = []
    for z in zs:
        h = CUR_TOP - z
        Hh = max(0.0, 1.0 - h / 9.0)
        grow = 1.0 + 0.22 * smoothstep(0, 140, h)
        # draw the panel slightly narrower near the floor (clears the TV cabinet end on the right)
        taper = 1.0 - (1.0 - 62.5 / 67.0) * (1.0 - smoothstep(75, 150, z))
        row = []
        for i in range(U_ + 1):
            s = i / C
            k = min(int(s), NRING - 2)
            f = s - k
            A = A0[k] * grow * (1 + 0.16 * math.sin(h / 29.0 + ph[k]) + 0.08 * math.sin(h / 11.0 + ph[k + 6]))
            skew = 0.08 * math.sin(h / 47.0 + ph[k + 6]) * (1 - Hh)
            fs = f + skew * math.sin(math.pi * f)
            low = 0.5 - 0.5 * math.cos(2 * math.pi * fs)
            low += 0.06 * smoothstep(20, 160, h) * math.sin(4 * math.pi * fs + ph[k + 12] + h / 37.0) * math.sin(math.pi * f)
            top = math.sin(math.pi * f) ** 0.75 if 0 < f < 1 else 0.0
            prof = Hh * top + (1 - Hh) * low
            x = 479.3 - A * prof + (1 - Hh) * 0.45 * (1 - prof) * math.sin(h / 41.0 + ph[k + 12])
            y = ring_y[k] + f * (ring_y[k + 1] - ring_y[k])
            y += (1 - Hh) * 0.6 * math.sin(h / 67.0 + k) * math.sin(math.pi * i / U_)
            y = inner + (y - inner) * taper
            row.append((x, y, z))
        grid.append(row)
    return grid, ring_y, outer_y


def curtains():
    panels = [curtain_panel(44.0, 112.0, 112.0, 11), curtain_panel(338.0, 406.0, 338.0, 23)]
    NR = len(panels[0][0])
    NC = len(panels[0][0][0])
    bm = bmesh.new()
    rest = bm.verts.layers.float_vector.new("rest")
    gid = bm.verts.layers.int.new("gid")              # panel * 100000 + row * 1000 + column
    pin = []
    for p, (grid, _, _) in enumerate(panels):
        V = []
        # rest (unfolded) coordinates: arc length along the row, height
        for j, row in enumerate(grid):
            acc = [0.0]
            for a, b in zip(row, row[1:]):
                acc.append(acc[-1] + math.dist(a, b))
            vr = []
            for i, (x, y, z) in enumerate(row):
                v = bm.verts.new(Vector((x / 100, -y / 100, z / 100)))
                v[rest] = Vector((acc[i] / 100, z / 100, 0))
                v[gid] = p * 100000 + j * 1000 + i
                vr.append(v)
                if j == 0:     # hooks hold the ring columns; the heading between them may dip
                    pin.append((v, 1.0 if i % CUR_C == 0 else 0.3))
            V.append(vr)
        for j in range(len(V) - 1):
            for i in range(len(V[0]) - 1):
                bm.faces.new((V[j][i], V[j][i + 1], V[j + 1][i + 1], V[j + 1][i]))
    bm.verts.index_update()
    pin_idx = [(v.index, w) for v, w in pin]
    me = bpy.data.meshes.new("cloth")
    bm.to_mesh(me)
    bm.free()
    cloth = link("cloth", me)
    vg = cloth.vertex_groups.new(name="pin")
    for idx, w in pin_idx:
        vg.add([idx], w, "REPLACE")

    # collision: floor, the wall line in front of the sill (x 481.8) and the TV cabinet end
    def box(x0, x1, y0, y1, z0, z1):
        b = bmesh.new()
        bmesh.ops.create_cube(b, size=1.0)
        for v in b.verts:
            v.co = Vector(((x0 + x1) / 2 + v.co.x * (x1 - x0), -((y0 + y1) / 2 + v.co.y * (y1 - y0)),
                           (z0 + z1) / 2 + v.co.z * (z1 - z0))) / 100
        m = bpy.data.meshes.new("col")
        b.to_mesh(m)
        b.free()
        o = link("col", m)
        o.modifiers.new("Collision", "COLLISION")
        o.collision.thickness_outer = 0.002
        o.collision.cloth_friction = 5
        return o
    # floor only: wall / cabinet boxes close behind or beside the pre-folded sheet destabilised the
    # solver (the sheet blew through them). It hangs clear of x 482 without a wall, and the panel is
    # drawn in near the floor and clamped afterwards to clear the TV cabinet end.
    cols = [box(-100, 600, -100, 550, -50, 0)]

    mod = cloth.modifiers.new("Cloth", "CLOTH")
    s = mod.settings
    s.quality = 10
    s.mass = 0.15                     # Blender cloth mass is per vertex
    s.air_damping = 1.0
    s.tension_stiffness = 15
    s.compression_stiffness = 15
    s.shear_stiffness = 8
    s.bending_stiffness = 0.08        # soft sheer: crests stay rounded instead of pinching
    s.vertex_group_mass = "pin"
    s.pin_stiffness = 1.0
    c = mod.collision_settings
    c.use_collision = True
    c.distance_min = 0.003
    c.use_self_collision = True
    c.self_distance_min = 0.003
    frames = 180
    # The rod line (x 479.3) is only 2.5 cm in front of the x 481.8 limit, so a sheet hanging
    # straight would centre its folds on the rod line and press the back folds flat against the
    # limit. A 2.5 % lean of gravity toward the room (about 1.4 deg, invisible on a hanging sheer)
    # lets the folds settle in front of the rod line instead.
    bpy.context.scene.gravity = (-0.25, 0.0, -9.81)
    mod.point_cache.frame_start = 1
    mod.point_cache.frame_end = frames
    sc = bpy.context.scene
    sc.frame_start, sc.frame_end = 1, frames
    t0 = time.time()
    for f in range(1, frames + 1):
        sc.frame_set(f)
        if os.environ.get("CLOTH_DEBUG") and f in (1, 2, 5, 10, 20, 40, 80, 120, 180):
            ev = cloth.evaluated_get(bpy.context.evaluated_depsgraph_get()).data
            P = [v.co * 100 for v in ev.vertices if v.co.y > -2.25]
            print("   f%3d x %.1f..%.1f  ue y %.1f..%.1f  z %.1f..%.1f" % (
                f, min(q.x for q in P), max(q.x for q in P), min(-q.y for q in P), max(-q.y for q in P),
                min(q.z for q in P), max(q.z for q in P)))
    print(f"  cloth: {frames} frames in {time.time() - t0:.1f}s")
    cloth = bake(cloth)
    bpy.context.scene.gravity = (0.0, 0.0, -9.81)
    sc.frame_set(1)
    for o in cols:
        kill(o)
    for g in list(cloth.vertex_groups):
        cloth.vertex_groups.remove(g)

    # back to cm; rescale the drop so the hem sits 1 cm above the floor; keep x <= 481.4 (hem
    # layers go 0.3 behind that, still in front of x 482)
    me = cloth.data
    me.transform(Matrix.Scale(100, 4))
    zmin = min(v.co.z for v in me.vertices)
    ztop = max(v.co.z for v in me.vertices)
    k = (ztop - 1.0) / (ztop - zmin)
    print(f"  cloth: top {ztop:.2f}, lowest before rescale {zmin:.2f} cm, hem rescale {100 * (k - 1):+.2f} %")
    for v in me.vertices:
        v.co.z = ztop - (ztop - v.co.z) * k
        v.co.x = min(v.co.x, 481.4)
    # fit each panel back inside its span (the hanging sheet spreads ~1 cm past its edge columns)
    for (lo, hi) in ((44.2, 111.8), (338.2, 405.8)):
        pv = [v for v in me.vertices if lo - 15 < -v.co.y < hi + 15]
        y0 = min(-v.co.y for v in pv)
        y1 = max(-v.co.y for v in pv if v.co.z > 80)        # upper drop sets the span
        sq = (hi - lo) / (y1 - y0)
        print(f"  cloth panel {lo:.0f}..{hi:.0f}: sim span {y0:.2f}..{y1:.2f}, squeeze {100 * (1 - sq):.1f} %")
        for v in pv:
            v.co.y = -(lo + (-v.co.y - y0) * sq)
    for v in me.vertices:
        if v.co.z < 63.0 and -v.co.y > 402.8:      # TV cabinet end (Y >= 403.06, top 60)
            v.co.y = -402.8
    set_mat(cloth, "M_Curtain")
    smooth(cloth, 60)                                # consistent winding within each panel

    # Face each panel into the room on its own (the two panels must not be summed together),
    # then add turned side hems and a folded-back double hem at the bottom.
    bm = bmesh.new()
    bm.from_mesh(me)
    rest_l = bm.verts.layers.float_vector.get("rest")
    gid_l = bm.verts.layers.int.get("gid")
    G = {}
    for v in bm.verts:
        g = v[gid_l]
        G[(g // 100000, (g % 100000) // 1000, g % 1000)] = v
    bm.faces.ensure_lookup_table()
    for p in range(2):
        pf = [f for f in bm.faces if f.verts[0][gid_l] // 100000 == p]
        nx = sum(f.normal.x * f.calc_area() for f in pf)
        print(f"  cloth panel {p}: normal.x*area {nx / 1e4:+.2f} m2 -> {'flip' if nx > 0 else 'ok'}")
        if nx > 0:
            bmesh.ops.reverse_faces(bm, faces=pf)
    bm.normal_update()
    hem_faces = []

    def back_of(v):
        """Vertex position pushed HEM_OFF behind the face fabric (opposite the room-facing normal)."""
        return v.co - v.normal * HEM_OFF

    def new_v(co, r):
        nv = bm.verts.new(co)
        nv[rest_l] = r
        nv[gid_l] = -1
        return nv

    def mirror_rest(edge_v, nb_v, axis):
        re, rn = Vector(edge_v[rest_l]), Vector(nb_v[rest_l])
        d = re[axis] - rn[axis]
        sgn = 1.0 if d >= 0 else -1.0
        r1, r2 = re.copy(), re.copy()
        r1[axis] = re[axis] + sgn * HEM_OFF / 100
        r2[axis] = re[axis] + sgn * (HEM_OFF / 100 + abs(d))
        return r1, r2
    def bridge3(top, bot2):
        """Faces between a row of n verts and a row of 2n-1 (every other one shared in position):
        three triangles per span so the finer row keeps its extra silhouette points."""
        for i in range(len(top) - 1):
            a, b = top[i], top[i + 1]
            l, m, r = bot2[2 * i], bot2[2 * i + 1], bot2[2 * i + 2]
            hem_faces.append(bm.faces.new((a, l, m)))
            hem_faces.append(bm.faces.new((a, m, b)))
            hem_faces.append(bm.faces.new((b, m, r)))
    for p in range(2):
        B = [G[(p, NR - 1, i)] for i in range(NC)]           # bottom edge
        T = [G[(p, NR - 2, i)] for i in range(NC)]           # hem height (~7 cm up)
        # Double the bottom edge's resolution with four-point subdivision midpoints so the hem's
        # silhouette is rounded instead of straight facets; the bottom fabric row becomes 3 tris/span.
        Bm = []
        for i in range(NC - 1):
            P0, P1, P2, P3 = (B[max(i - 1, 0)].co, B[i].co, B[i + 1].co, B[min(i + 2, NC - 1)].co)
            co = (-P0 + 9 * P1 + 9 * P2 - P3) / 16
            r = (Vector(B[i][rest_l]) + Vector(B[i + 1][rest_l])) / 2
            v = new_v(co, r)
            v.normal = (B[i].normal + B[i + 1].normal).normalized()
            Bm.append(v)
        for i in range(NC - 1):
            e = bm.edges.get((B[i], B[i + 1]))
            for f in list(e.link_faces):
                bm.faces.remove(f)
        Bseq = [B[0]]
        for i in range(NC - 1):
            Bseq += [Bm[i], B[i + 1]]
        bridge3(T, Bseq)
        # folded-back double hem: fold strip at the bottom, back layer up to the hem height
        Bbseq, Tb = [], []
        for k, b in enumerate(Bseq):
            r = Vector(b[rest_l])
            Bbseq.append(new_v(b.co - b.normal * HEM_OFF, Vector((r.x, r.y - HEM_OFF / 100, 0))))
        for b, t in zip(B, T):
            r1, r2 = mirror_rest(b, t, 1)
            Tb.append(new_v(back_of(t), r2))
        for k in range(len(Bseq) - 1):
            hem_faces.append(bm.faces.new((Bseq[k], Bseq[k + 1], Bbseq[k + 1], Bbseq[k])))
        bridge3(Tb, Bbseq)
        Bb = [Bbseq[0], Bbseq[-1]]
        for col, nb in ((0, 1), (NC - 1, NC - 2)):          # turned side hems above the bottom hem
            S = [G[(p, j, col)] for j in range(NR - 1)]
            N = [G[(p, j, nb)] for j in range(NR - 1)]
            Sb, Nb = [], []
            for sv, nv_ in zip(S, N):
                r1, r2 = mirror_rest(sv, nv_, 0)
                Sb.append(new_v(back_of(sv), r1))
                Nb.append(new_v(back_of(nv_), r2))
            for j in range(NR - 2):
                hem_faces.append(bm.faces.new((S[j], S[j + 1], Sb[j + 1], Sb[j])))
                hem_faces.append(bm.faces.new((Sb[j], Sb[j + 1], Nb[j + 1], Nb[j])))
            # close the side of the bottom hem fold
            bc = Bb[0] if col == 0 else Bb[-1]     # ends of the folded-back hem
            hem_faces.append(bm.faces.new((S[-1], B[col], bc, Sb[-1])))
    # wind the hem faces consistently with the face fabric they continue from
    for f in hem_faces:
        for e in f.edges:
            others = [o for o in e.link_faces if o is not f and o not in hem_faces]
            if others:
                o = others[0]
                a, b = e.verts
                def fwd(face):
                    vs = list(face.verts)
                    ia = vs.index(a)
                    return vs[(ia + 1) % len(vs)] is b
                if fwd(f) == fwd(o):
                    f.normal_flip()
                break
    # propagate to hem faces not touching the fabric (back layers)
    changed = True
    fixed = {f for f in hem_faces if any(o not in hem_faces for e in f.edges for o in e.link_faces if o is not f)}
    while changed:
        changed = False
        for f in hem_faces:
            if f in fixed:
                continue
            for e in f.edges:
                nbs = [o for o in e.link_faces if o is not f and o in fixed]
                if nbs:
                    o = nbs[0]
                    a, b = e.verts
                    vs, vo = list(f.verts), list(o.verts)
                    if (vs[(vs.index(a) + 1) % len(vs)] is b) == (vo[(vo.index(a) + 1) % len(vo)] is b):
                        f.normal_flip()
                    fixed.add(f)
                    changed = True
                    break
    bm.to_mesh(me)
    bm.free()
    if "gid" in me.attributes:
        me.attributes.remove(me.attributes["gid"])
    smooth(cloth, 60, recalc=False, dedupe=False)   # keep the coincident hem-corner verts apart (UV seam)
    xmax = max(v.co.x for v in me.vertices)
    zlo = min(v.co.z for v in me.vertices)
    print(f"  cloth: x max {xmax:.2f}, z min {zlo:.2f}, faces {len(me.polygons)}")
    parts = [cloth]
    # rings round the rod (part of the curtain), resting on the rod's top with 0.2 cm air
    zc = CUR_TOP + GAP + RING_R + RING_r
    for _, ring_y, _ in panels:
        for y in ring_y:
            parts.append(torus(U(ROD_X, y, zc), RING_R, RING_r, "Y", "M_Metal", nu=8, nv=3, name="ring"))
    return join("SM_Curtains", parts)


# ====================================================================== SM_Rug
def rug():
    """Jute rug 195 wide, 196 cm body + ~4.5 cm knotted cord fringe on each short (X) end (~205 overall;
    the +X fringe must stop short of the north skirting at x 498.2 with the rug placed at x 395),
    0.6 thick: whipped bound edge, flat quad-grid field. The underside lies on the floor and is left
    open (never seen)."""
    L, W, rc = 196.0, 195.0, 4.0
    hx, hy = L / 2 - rc, W / 2 - rc
    NX, NY = 6, 6                                    # field grid (about 32 cm cells)
    gx = [-hx + 2 * hx * i / NX for i in range(NX + 1)]
    gy = [-hy + 2 * hy * j / NY for j in range(NY + 1)]
    FZ = 0.53
    # border profile (d inward from the edge, z); bound edge with a slightly raised whipped border
    prof = [(0.3, 0.0), (0.0, 0.3), (0.15, 0.55), (0.7, 0.6), (2.1, FZ)]
    CORNERS = ((hx, hy, 0), (-hx, hy, 90), (-hx, -hy, 180), (hx, -hy, 270))

    def outline(d, sides=False, n=4):
        """Rounded-rectangle loop (CCW from +X). With sides=True the straight runs also get points at
        the field grid lines. Returns [(x, y, tag)]: tag ('c', corner, i) or ('s', corner, k, frac)."""
        r = rc - d
        pts = []
        for c, (cx, cy, a0) in enumerate(CORNERS):
            for i in range(n + 1):
                a = math.radians(a0 + 90 * i / n)
                pts.append((cx + r * math.cos(a), cy + r * math.sin(a), ("c", c, i)))
            if sides:   # run from the end of corner c to the start of corner c+1
                if c == 0:
                    run = [(gx[i], hy + r) for i in range(NX - 1, 0, -1)]
                elif c == 1:
                    run = [(-hx - r, gy[j]) for j in range(NY - 1, 0, -1)]
                elif c == 2:
                    run = [(gx[i], -hy - r) for i in range(1, NX)]
                else:
                    run = [(hx + r, gy[j]) for j in range(1, NY)]
                for k, (x, y) in enumerate(run):
                    pts.append((x, y, ("s", c, k, (k + 1) / (len(run) + 1))))
        return pts
    bm = bmesh.new()
    lm = bm.verts.layers.float_vector.new("lm")    # lightmap unfold: border flattened outward
    s_out = [0.0]
    for (d0, z0), (d1, z1) in zip(reversed(prof[1:]), reversed(prof[:-1])):
        s_out.append(s_out[-1] + math.hypot(d1 - d0, z1 - z0))
    s_out = list(reversed(s_out))                    # profile arc length out from the 2.1 cm loop
    rings = []
    for (d, z), so in zip(prof, s_out):
        ring = []
        for (x, y, _), (ux, uy, _) in zip(outline(d), outline(prof[-1][0] - so)):
            v = bm.verts.new((x, y, z))
            v[lm] = Vector((ux, uy, 0.0))
            ring.append(v)
        rings.append(ring)
    n = len(rings[0])
    for k in range(len(rings) - 1):
        for i in range(n):
            bm.faces.new((rings[k][i], rings[k][(i + 1) % n], rings[k + 1][(i + 1) % n], rings[k + 1][i]))
    sharp_ring = set(rings[-1])
    # inner flat loop at d 3.0 with points on the grid lines, and the field grid
    o3 = outline(3.0, sides=True)
    r3 = [bm.verts.new((x, y, FZ)) for x, y, _ in o3]
    G = [[bm.verts.new((gx[i], gy[j], FZ)) for j in range(NY + 1)] for i in range(NX + 1)]
    for v in r3 + [g for col in G for g in col]:
        v[lm] = Vector((v.co.x, v.co.y, 0.0))
    r2 = rings[-1]
    per = 5   # arc points per corner on the plain rings

    def anchor2(tag):     # ring 3.0 point -> ring 2.1 point it is bridged to
        if tag[0] == "c":
            return r2[tag[1] * per + tag[2]]
        c = tag[1]
        return r2[c * per + per - 1] if tag[3] <= 0.5 else r2[((c + 1) % 4) * per]

    corner_g = [G[NX][NY], G[0][NY], G[0][0], G[NX][0]]

    def anchorG(x, y, tag):   # ring 3.0 point -> field grid vertex it is bridged to
        if tag[0] == "c":
            return corner_g[tag[1]]
        i = min(range(NX + 1), key=lambda q: abs(gx[q] - x))
        j = min(range(NY + 1), key=lambda q: abs(gy[q] - y))
        c = tag[1]
        if c in (0, 2):
            return G[i][NY if c == 0 else 0]
        return G[0 if c == 1 else NX][j]

    def bridge(outer, anchors):
        m = len(outer)
        for i in range(m):
            p, q = outer[i], outer[(i + 1) % m]
            ap, aq = anchors[i], anchors[(i + 1) % m]
            if ap is aq:
                bm.faces.new((ap, p, q))
            else:
                bm.faces.new((ap, aq, q, p))
    bridge(r3, [anchor2(t) for _, _, t in o3])
    bridge(r3, [anchorG(x, y, t) for x, y, t in o3])
    for i in range(NX):
        for j in range(NY):
            bm.faces.new((G[i][j], G[i + 1][j], G[i + 1][j + 1], G[i][j + 1]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    up = sum(f.normal.z * f.calc_area() for f in bm.faces)
    if up < 0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces)
    sharp_co = [v.co.copy() for v in sharp_ring]
    body = bm_object(bm, ["M_Rug"], "rug_body", 35, recalc=False)
    # flat field: the 2.1 cm loop is a hard edge so the field and inner border shade dead flat
    bm = bmesh.new()
    bm.from_mesh(body.data)
    tree_pts = {(round(c.x, 3), round(c.y, 3), round(c.z, 3)) for c in sharp_co}
    for e in bm.edges:
        if all((round(v.co.x, 3), round(v.co.y, 3), round(v.co.z, 3)) in tree_pts for v in e.verts):
            e.smooth = False
    bm.to_mesh(body.data)
    bm.free()
    parts = [body]

    # Knotted cord fringe: one continuous strip per end so no floor shows between tassels. Each
    # tassel = a knot mound at the binding (root row: a low boundary + a raised centre) fanning out to
    # five cord columns (ridge / valley / ridge / valley / ridge) whose ends are cut at individual,
    # ragged lengths; the boundary column between tassels is short so each tassel reads on its own.
    rnd = random.Random(5)
    NT = 28
    y_lo, y_hi = -hy + 0.4, hy - 0.4
    pitch = (y_hi - y_lo) / NT
    x_root, x_knot = L / 2 + 0.2, L / 2 + 1.2
    for sgn in (1, -1):
        cen = [y_lo + pitch * (k + 0.5) + rnd.uniform(-0.6, 0.6) for k in range(NT)]
        bnd = [y_lo] + [(a + b) / 2 for a, b in zip(cen, cen[1:])] + [y_hi]
        bm = bmesh.new()
        lmf = bm.verts.layers.float_vector.new("lm")

        def vert(x, y, z):
            v = bm.verts.new((sgn * x, y, z))
            v[lmf] = Vector((v.co.x, v.co.y, 0.0))
            return v

        def boundary(y):
            ln = rnd.uniform(1.6, 2.3)
            return (vert(x_root, y, 0.06), vert(x_knot, y, 0.05), vert(x_knot + ln, y, 0.02))
        prev = boundary(bnd[0])
        for k in range(NT):
            w = bnd[k + 1] - bnd[k]
            nxt = boundary(bnd[k + 1])
            c = cen[k]
            yaw = math.radians(rnd.uniform(-6, 6))
            base_len = rnd.uniform(2.8, 3.5)
            root_c = vert(x_root, c, 0.3)
            knot, tip = [], []
            for q, f in enumerate((-0.36, -0.18, 0.0, 0.18, 0.36)):
                ridge = q % 2 == 0
                yk = c + f * w
                ln = base_len * (rnd.uniform(0.88, 1.12) if ridge else rnd.uniform(0.8, 0.92))
                spl = f * rnd.uniform(0.25, 0.45) * w * 0.5           # cords fan out slightly
                ln = min(ln, (L / 2 + 4.6 - x_knot) / max(math.cos(yaw), 1e-3))   # skirting clearance
                knot.append(vert(x_knot, yk, 0.34 if ridge else 0.2))
                tip.append(vert(x_knot + ln * math.cos(yaw), yk + spl + ln * math.sin(yaw),
                                0.06 if ridge else 0.025))
            # knot fan: root (boundary, centre, boundary) -> knot row
            krow = [prev[1]] + knot + [nxt[1]]
            bm.faces.new((prev[0], root_c, krow[1], krow[0]))
            for a, b in zip(krow[1:-2], krow[2:-1]):
                bm.faces.new((root_c, b, a))
            bm.faces.new((root_c, nxt[0], krow[-1], krow[-2]))
            # cords: knot row -> ragged tips
            trow = [prev[2]] + tip + [nxt[2]]
            for i in range(len(krow) - 1):
                bm.faces.new((krow[i], krow[i + 1], trow[i + 1], trow[i]))
            prev = nxt
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        if sum(f.normal.z for f in bm.faces) < 0:
            bmesh.ops.reverse_faces(bm, faces=bm.faces)
        parts.append(bm_object(bm, ["M_Rug"], "fringe", 70, recalc=False))
    return join("SM_Rug", parts)


# ====================================================================== SM_PlantPot
POT_Z = 0.65                                       # pot foot: saucer floor (0.45) + 0.2 cm air
SOIL_Z0, SOIL_R, SOIL_DROP = POT_Z + 9.1, 5.4, 0.35    # soil mound: 9.75 at the centre, 9.4 at the wall


def soil_z(r):
    return SOIL_Z0 - SOIL_DROP * min(r, SOIL_R) / SOIL_R


def qcurve(S, mid, E, n):
    """n points on the quadratic curve S -> E passing through `mid` at t = 0.5."""
    C = 2 * mid - (S + E) / 2
    return [S * (1 - t) ** 2 + C * (2 * (1 - t) * t) + E * (t * t) for t in (i / (n - 1) for i in range(n))]


LEAF_LOBES, LEAF_M = 7, 3   # seven crenate lobes; 3 mid-ring vertices


def leaf_mesh(A, az, tilt, R, cup, seed, per=3):
    """Closed zonal-pelargonium leaf: round blade with seven crenate lobes (a notch vertex pulled in
    to 0.86 R between lobes, `per` rim vertices per lobe), a basal sinus at the petiole end A,
    dished up (cup) and ruffled along the margin. Top = centre fan to a mid ring + fans to the rim,
    underside = shallower fan from a point below the centre (kept below the top surface).
    Returns (object, ft, nrm, E): E = petiole end tucked 0.26 under the underside near the sinus."""
    rnd = random.Random(seed)
    fh = Vector((math.cos(az), math.sin(az), 0))
    s = Vector((0, 0, 1)).cross(fh)
    ft = fh * math.cos(tilt) - Vector((0, 0, 1)) * math.sin(tilt)
    nrm = ft.cross(s).normalized()
    C = A + ft * (0.9 * R)
    ph = rnd.uniform(0, 6.28)
    asym = rnd.uniform(-0.05, 0.05)
    NR = LEAF_LOBES * per
    rf = 0.18 * R / 3.5                            # margin ruffle (0.18 cm on a 3.5 cm leaf)

    def rim_r(i, t):
        d = abs((t % (2 * math.pi)) - math.pi)      # angle from the basal sinus
        lobe = 0.86 if i % per == 0 else (1.0 if per == 2 else 0.985)
        return R * lobe * (1 + asym * math.sin(t)) * (1 - 0.28 * math.exp(-(d / 0.3) ** 2))

    def pt(rho, t, lift, ruffle=1.0):
        w = cup * R * (rho / R) ** 2 + ruffle * rf * math.sin(LEAF_LOBES * t + ph) * (rho / R)
        return C + ft * (rho * math.cos(t)) + s * (rho * math.sin(t)) + nrm * (w + lift)
    # rim vertex 0 sits exactly on the sinus (t = pi) and is a notch vertex
    ts = [math.pi + 2 * math.pi * i / NR for i in range(NR)]
    step = NR // LEAF_M
    bm = bmesh.new()
    rim = [bm.verts.new(pt(rim_r(i, t), t, 0.0)) for i, t in enumerate(ts)]
    lift_mid = 0.25 * cup * R + 0.07 + 0.5 * rf
    tm = [ts[step * k] + math.pi / LEAF_M for k in range(LEAF_M)]
    mid = [bm.verts.new(pt(0.5 * R, t, lift_mid, 0.5)) for t in tm]
    ct = bm.verts.new(pt(0.0, 0.0, 0.07 + 0.25 * rf))
    cbp = pt(0.0, 0.0, -0.08)
    cb = bm.verts.new(cbp)
    for k in range(LEAF_M):
        m0, m1 = mid[k], mid[(k + 1) % LEAF_M]
        r = [rim[(step * k + j) % NR] for j in range(step + 1)]
        bm.faces.new((ct, m0, m1))
        for j in range(step):
            bm.faces.new((m0, r[j], r[j + 1]))
        bm.faces.new((m0, r[step], m1))
    for i in range(NR):
        bm.faces.new((cb, rim[(i + 1) % NR], rim[i]))
    E = cbp.lerp(rim[0].co, 0.72) - nrm * 0.26
    ob = bm_object(bm, ["M_Plant"], "leaf", 70, recalc=False)
    return ob, ft, nrm, E


def floret(c, d, rad, rot, name="floret"):
    """Geranium floret: five rounded petals (tip + notch rim points) cupped into a shallow bowl
    (0.45 f^2 rad) round a raised centre, facing direction d. An open cup (10-triangle top fan): its
    back faces the head centre where neighbours and the pedicels hide it."""
    q = d.to_track_quat("Z", "Y").to_matrix()
    bm = bmesh.new()
    rim = []
    for k in range(5):
        th = rot + 2 * math.pi * k / 5
        for da, f in ((0.0, 1.0), (math.pi / 5, 0.74)):     # shallow notches: rounded petals
            r = rad * f
            a = th + da
            rim.append(bm.verts.new(c + q @ Vector((r * math.cos(a), r * math.sin(a), 0.45 * f * f * rad))))
    ct = bm.verts.new(c + q @ Vector((0, 0, 0.08)))
    n = len(rim)
    for i in range(n):
        bm.faces.new((ct, rim[i], rim[(i + 1) % n]))
    return bm_object(bm, ["M_FlowerRed"], name, 70)


def bud(base, d, length, width, rot, name="bud"):
    """Closed geranium bud: a 4-sided teardrop (round shoulder at 35 % of the length, pointed tip)."""
    q = d.to_track_quat("Z", "Y").to_matrix()
    bm = bmesh.new()
    b0 = bm.verts.new(base)
    ring = [bm.verts.new(base + q @ Vector((width / 2 * math.cos(rot + k * math.pi / 2),
                                             width / 2 * math.sin(rot + k * math.pi / 2), 0.35 * length)))
            for k in range(4)]
    tip = bm.verts.new(base + d * length)
    for k in range(4):
        bm.faces.new((b0, ring[(k + 1) % 4], ring[k]))
        bm.faces.new((tip, ring[k], ring[(k + 1) % 4]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm_object(bm, ["M_Plant"], name, 80, recalc=False)


def bez2(S, C, E, n):
    """n points on the quadratic Bezier S -> E with control point C."""
    return [S * (1 - t) ** 2 + C * (2 * (1 - t) * t) + E * (t * t) for t in (i / (n - 1) for i in range(n))]


def plant_pot():
    rnd = random.Random(7)
    SEG = 18
    # Saucer (pivot underneath): splayed wall, rolled lip, 0.45 cm floor. Its underside rests on the
    # sill and is left open.
    sau = lathe([(5.0, 0.0), (6.3, 1.1), (6.1, 1.3), (5.25, 0.45), (0.0, 0.45)], SEG, "M_Ceramic",
                name="saucer", angle_smooth=35)
    # Glazed pot standing in it with 0.2 cm air: tapered belly, rolled bead at the rim, inner lip down
    # to the soil (soil faces take M_Soil). The base sits inside the saucer lip, unseen.
    Z = POT_Z
    prof = [(4.5, Z), (5.65, Z + 7.6), (5.95, Z + 8.95), (6.2, Z + 9.6), (5.9, Z + 10.3),
            (SOIL_R, soil_z(SOIL_R)), (0.0, SOIL_Z0)]
    pot = lathe(prof, SEG, "M_Ceramic", name="pot", angle_smooth=35)
    assign_mats(pot, lambda c: "M_Soil" if (math.hypot(c.x, c.y) < SOIL_R - 0.05 and c.z > Z + 8.5
                                            and c.z < SOIL_Z0 + 0.05) else "M_Ceramic")
    parts = [sau, pot]
    # Short woody crown stem rising from the soil; petioles and flower stalks spring from it.
    cr_pts = [Vector((0.25, 0.1, SOIL_Z0 + 0.05)), Vector((0.55, 0.35, SOIL_Z0 + 2.6)),
              Vector((0.3, 0.6, SOIL_Z0 + 5.0))]
    CR_R = 0.5
    crown = tube(cr_pts, [0.5, 0.45, 0.38], "M_Plant", sides=4, name="crown", angle_smooth=80)
    parts.append(crown)
    cr_line = qcurve(cr_pts[0], cr_pts[1], cr_pts[2], 11)

    def crown_at(t):
        return cr_line[min(10, max(0, round(t * 10)))]

    def sprout(t, direction, rad):
        """Start point on the crown surface for a tube of radius `rad` leaving along `direction`."""
        c = crown_at(t)
        hor = Vector((direction.x, direction.y, 0))
        hor = hor.normalized() if hor.length > 1e-6 else Vector((1, 0, 0))
        side = math.sqrt(max(0.0, 1 - (direction.normalized().dot(hor)) ** 2))
        return c + hor * (CR_R + 0.05 + rad * side)

    NODE_R = 0.28
    flowers = []
    # Flower stalk 1: leans ~10 deg toward az 30 and carries a full open umbel: a small node at the
    # stalk tip, 14 florets on 3-sided pedicels radiating from it over a dome (polar 0..82 deg),
    # alternately set at two depths so the cupped florets nest without touching.
    az1 = math.radians(UMBEL_AZ[0])
    h1 = Vector((math.cos(az1), math.sin(az1), 0))
    S1 = sprout(0.92, h1 * 0.18 + Vector((0, 0, 1)), 0.2)
    N1 = S1 + h1 * 1.2 + Vector((0, 0, UMBEL_RISE))                # node centre
    d01 = (h1 * 0.12 + Vector((0, 0, 1))).normalized()              # stalk end direction
    E1 = N1 - d01 * 0.29          # 3-sided stalk: its flat sides stay outside the node
    st1 = tube(bez2(S1, E1 - d01 * 3.0, E1, 5), 0.2, "M_Plant", sides=3, name="stalk", caps=False)
    node1 = ball(N1, NODE_R, "M_Plant", u=5, v=3, name="node")
    flowers += [st1, node1]
    q1 = d01.to_track_quat("Z", "Y").to_matrix()
    ga = math.pi * (3 - math.sqrt(5))
    rot0 = rnd.uniform(0, 6.28)
    florets = []
    NFL = 14
    for k in range(NFL):
        ok = False
        for attempt in range(10):
            pol = math.radians(82) * math.sqrt((k + 0.5) / NFL) + math.radians(
                4 * ((attempt + 1) // 2) * (1 if attempt % 2 else -1))
            a = rot0 + k * ga + math.radians(9 * attempt)
            d = (q1 @ Vector((math.sin(pol) * math.cos(a), math.sin(pol) * math.sin(a), math.cos(pol)))).normalized()
            dist = (FL_DIST[0] if k % 2 == 0 else FL_DIST[1]) + rnd.uniform(-0.1, 0.1)
            rad = rnd.uniform(0.86, 0.98) - 0.025 * attempt
            fc = N1 + d * dist
            fl = floret(fc, d, rad, rnd.uniform(0, 1.2))
            # straight pedicel (as on a real umbel) from just outside the node into the floret's cup
            ped = tube([N1 + d * 0.33, fc - d * 0.12], 0.07, "M_Plant", sides=3, caps=False, name="pedicel")
            if is_clear(fl, florets + [st1, node1], 0.0) and is_clear(ped, florets + [fl, st1], 0.01):
                florets += [fl, ped]
                ok = True
                break
            kill(fl)
            kill(ped)
        if not ok:
            print(f"  plant: floret {k} not placed")
    print(f"  plant: umbel {len(florets) // 2}/{NFL} florets")
    flowers += florets
    # Flower stalk 2: leans toward az 150, then arches over (control point outward, end tangent
    # pointing down) into a nodding cluster of 7 closed buds on drooping pedicels.
    az2 = math.radians(UMBEL_AZ[1])
    h2 = Vector((math.cos(az2), math.sin(az2), 0))
    S2 = sprout(0.85, h2 * 0.21 + Vector((0, 0, 1)), 0.2)
    C2 = S2 + h2 * 2.6 + Vector((0, 0, BUD_RISE + 1.2))             # arch control point
    N2 = S2 + h2 * 4.2 + Vector((0, 0, BUD_RISE))                   # node: nodding, below the arch
    d02 = (N2 - C2).normalized()
    E2 = N2 - d02 * 0.29
    st2 = tube(bez2(S2, C2, E2, 6), 0.19, "M_Plant", sides=3, name="stalk", caps=False)
    node2 = ball(N2, NODE_R * 0.9, "M_Plant", u=4, v=3, name="node")
    flowers += [st2, node2]
    buds = []
    NB = 7
    for k in range(NB):
        ok = False
        for attempt in range(12):
            a = 2 * math.pi * k / NB + rnd.uniform(-0.25, 0.25) + 0.45 * attempt
            droop = math.radians(rnd.uniform(30, 60))               # angle from straight down
            dd = Vector((math.sin(droop) * math.cos(a), math.sin(droop) * math.sin(a), -math.cos(droop)))
            dd = (dd + d02 * 0.35).normalized()
            p0 = N2 + dd * 0.3
            plen = rnd.uniform(0.8, 1.3)
            p1 = p0 + dd * plen
            ped = tube([p0, p1], 0.06, "M_Plant", sides=3, caps=False, name="pedicel")
            bd = bud(p1 + dd * 0.06, dd, rnd.uniform(0.82, 0.95), rnd.uniform(0.45, 0.52), rnd.uniform(0, 1.5))
            if is_clear(bd, buds + [st2, node2], 0.02) and is_clear(ped, buds + [bd, st2], 0.01):
                buds += [bd, ped]
                ok = True
                break
            kill(bd)
            kill(ped)
        if not ok:
            print(f"  plant: bud {k} not placed")
    print(f"  plant: {len(buds) // 2}/{NB} buds")
    flowers += buds
    parts += flowers
    # Leaves on arched petioles from the crown: large leaves low and outward (tilt 25-40 deg)
    # overhanging the rim, three small leaves low over the soil (radius 2-4 cm) and two small leaves
    # high in the centre, so no soil shows inside r 4 from above.
    placed = [p for p in parts if p is not crown]
    plan = ["big"] * 6 + ["low"] * 3 + ["high"] * 4
    leaves = 0
    # top-view soil samples (r <= 4.6): centre leaves pick, among a few clear candidates, the one that
    # covers the most still-visible soil
    samples = [Vector((x * 0.4, y * 0.4, 0)) for x in range(-12, 13) for y in range(-12, 13)
               if math.hypot(x * 0.4, y * 0.4) <= 4.6]

    def covers(objs):
        tree = tri_bvh(objs)
        return {k for k, q in enumerate(samples)
                if tree.ray_cast(Vector((q.x, q.y, 60.0)), Vector((0, 0, -1)))[0] is not None}
    covered = covers(flowers + [crown])      # (not the pot: its soil is what must be hidden)
    for i, kind in enumerate(plan):
        az0 = math.radians(i * 137.5 + 10)
        done = False
        cands = []
        for attempt in range(60):
            if kind != "big" and len(cands) >= 8:
                break
            az = az0 + math.radians(12 * ((attempt + 1) // 2) * (1 if attempt % 2 else -1))
            if kind == "big":
                t = rnd.uniform(0.15, 0.5)
                R = rnd.uniform(3.4, 4.1)
                tilt = math.radians(rnd.uniform(25, 40))
                plen = rnd.uniform(4.0, 5.3)
                elev = math.radians(rnd.uniform(5, 25))
                per = 3
            elif kind == "low":          # young leaves on short, steep petioles: blades over r 0..5
                t = rnd.uniform(0.15, 0.45)
                R = rnd.uniform(3.0, 3.4)
                tilt = math.radians(rnd.uniform(0, 10))
                plen = rnd.uniform(1.0, 2.0)
                elev = math.radians(rnd.uniform(40, 70))
                per = 2
            else:
                t = rnd.uniform(0.7, 1.0)
                R = rnd.uniform(2.8, 3.3)
                tilt = math.radians(rnd.uniform(0, 12))
                plen = rnd.uniform(1.2, 2.2)
                elev = math.radians(rnd.uniform(55, 80))
                per = 2
            fh = Vector((math.cos(az), math.sin(az), 0))
            pdir = fh * math.cos(elev) + Vector((0, 0, math.sin(elev)))
            S = sprout(t, pdir, 0.2)
            A = S + pdir * plen
            lf, ft, nrm, E = leaf_mesh(A, az, tilt, R, rnd.uniform(0.2, 0.3), seed=i * 31 + attempt, per=per)
            spread = max(math.hypot(v.co.x, v.co.y) for v in lf.data.vertices)
            if spread > 11.6:
                kill(lf)
                continue
            arch = 1.0 if attempt < 35 else 0.6
            mid = S.lerp(E, 0.5) + Vector((0, 0, arch))
            n_pts = 5 if kind == "big" else 3
            pet = tube(qcurve(S, mid, E, n_pts), 0.2 if kind == "big" else 0.17, "M_Plant", sides=3,
                       name="petiole", caps=False)
            if is_clear(lf, placed + [crown], 0.1) and is_clear(pet, placed + [lf], 0.06) \
                    and is_clear(pet, [crown], 0.01):
                if kind == "big":
                    cands = [(0, lf, pet)]
                    break
                cands.append((len(covers([lf]) - covered), lf, pet))
                continue
            kill(lf)
            kill(pet)
        if cands:
            cands.sort(key=lambda c: -c[0])
            _, lf, pet = cands[0]
            for _, l2, p2 in cands[1:]:
                kill(l2)
                kill(p2)
            placed += [lf, pet]
            parts += [lf, pet]
            covered |= covers([lf])
            leaves += 1
            done = True
        if not done:
            print(f"  plant: {kind} leaf {i} not placed")
    print(f"  plant: {leaves}/{len(plan)} leaves placed, soil samples covered {len(covered)}/{len(samples)}")
    return join("SM_PlantPot", parts)


UMBEL_AZ = (30.0, 150.0)       # flower stalk lean directions (deg)
UMBEL_RISE = 7.2               # crown top -> umbel node (cm); node z ~ 22
BUD_RISE = 6.2                 # crown top -> nodding bud node
FL_DIST = (2.25, 2.7)          # node -> floret centre, alternating depths


# ====================================================================== photo frames
BASE_PROFILE = [  # (d inward from the outer edge, x depth from the wall) for a 4.5 x 2.8 moulding
    (0.0, 0.0), (0.0, 1.9), (0.15, 2.35), (0.5, 2.65), (1.0, 2.8), (1.6, 2.75), (2.1, 2.45),
    (2.6, 2.2), (3.1, 2.3), (3.5, 2.45), (3.9, 2.35), (4.2, 2.0), (4.5, 1.6), (4.5, 1.25),
    (3.6, 1.25), (3.6, 0.0)]


def rect_loop(bm, W, H, d, x):
    hy, hz = W / 2 - d, H / 2 - d
    return [bm.verts.new((x, sy * hy, sz * hz)) for sy, sz in ((1, 1), (-1, 1), (-1, -1), (1, -1))]


def photo_frame(name, W, H, mw, depth, frame_mat, mat_border=0.0, slip_gold=False):
    sd, sx = mw / 4.5, depth / 2.8
    prof = [(d * sd, x * sx) for d, x in BASE_PROFILE]
    names = [frame_mat] + (["M_Gold"] if slip_gold else [])
    bm = bmesh.new()
    loops = [rect_loop(bm, W, H, d, x) for d, x in prof]
    n = len(loops)
    for k in range(n):
        a, b = loops[k], loops[(k + 1) % n]
        dmid = (prof[k][0] + prof[(k + 1) % n][0]) / 2 / sd
        xmid = (prof[k][1] + prof[(k + 1) % n][1]) / 2 / sx
        gold = slip_gold and 3.5 <= dmid <= 4.5 and xmid > 1.5
        for c in range(4):
            f = bm.faces.new((a[c], a[(c + 1) % 4], b[(c + 1) % 4], b[c]))
            f.material_index = 1 if gold else 0
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    parts = [bm_object(bm, names, "moulding", 32)]

    d_r = 3.6 * sd + GAP          # picture / mat / backing reach into the rebate
    x_lip = 1.25 * sx              # underside of the sight lip
    x = x_lip - GAP
    if mat_border > 0:
        # bevel-cut card mat
        bm = bmesh.new()
        t = 0.15
        d_in = mw + mat_border
        of, ob_ = rect_loop(bm, W, H, d_r, x), rect_loop(bm, W, H, d_r, x - t)
        inf, inb = rect_loop(bm, W, H, d_in - t, x), rect_loop(bm, W, H, d_in, x - t)
        for c in range(4):
            c1 = (c + 1) % 4
            bm.faces.new((of[c], of[c1], inf[c1], inf[c]))
            bm.faces.new((ob_[c1], ob_[c], inb[c], inb[c1]))
            bm.faces.new((ob_[c], ob_[c1], of[c1], of[c]))
            bm.faces.new((inf[c], inf[c1], inb[c1], inb[c]))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        parts.append(bm_object(bm, ["M_Paper"], "mat", 30))
        x = x - t - GAP
    # picture plane (own 0..1 UVs in the UV pass), facing +X
    bm = bmesh.new()
    hy, hz = W / 2 - d_r, H / 2 - d_r
    v = [bm.verts.new((x, y, z)) for y, z in ((-hy, -hz), (hy, -hz), (hy, hz), (-hy, hz))]
    bm.faces.new(v)
    parts.append(bm_object(bm, ["M_Photo"], "photo", 30, recalc=False))
    # hardboard backing
    xb1 = x - GAP
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for vt in bm.verts:
        vt.co = Vector(((xb1 + 0.1) / 2 + vt.co.x * (xb1 - 0.1), vt.co.y * 2 * hy, vt.co.z * 2 * hz))
    parts.append(bm_object(bm, ["M_TimberDark"], "backing", 30))
    return join(name, parts)


# ====================================================================== SM_Calendar
def sheet(ys, zs, x0, thick, dfn, mfn, names, name):
    """Thin closed paper sheet on a (y, z) grid; dfn(y, z) -> (dx, dz); mfn(y, z, front) -> slot index."""
    bm = bmesh.new()
    F, B = [], []
    for z in zs:
        fr, br = [], []
        for y in ys:
            dx, dz = dfn(y, z)
            fr.append(bm.verts.new((x0 + thick + dx, y, z + dz)))
            br.append(bm.verts.new((x0 + dx, y, z + dz)))
        F.append(fr)
        B.append(br)
    ny, nz = len(ys), len(zs)
    for j in range(nz - 1):
        for i in range(ny - 1):
            yc, zc = (ys[i] + ys[i + 1]) / 2, (zs[j] + zs[j + 1]) / 2
            # triangulate ourselves: back = exact reverse of the front triangles (shared diagonals,
            # so the two skins stay parallel on non-planar curl cells)
            f00, f01, f11, f10 = F[j][i], F[j][i + 1], F[j + 1][i + 1], F[j + 1][i]
            b00, b01, b11, b10 = B[j][i], B[j][i + 1], B[j + 1][i + 1], B[j + 1][i]
            for tri in ((f00, f01, f11), (f00, f11, f10)):
                bm.faces.new(tri).material_index = mfn(yc, zc, True)
            for tri in ((b11, b01, b00), (b10, b11, b00)):
                bm.faces.new(tri).material_index = mfn(yc, zc, False)
    for i in range(ny - 1):
        bm.faces.new((B[0][i], B[0][i + 1], F[0][i + 1], F[0][i]))
        bm.faces.new((F[-1][i], F[-1][i + 1], B[-1][i + 1], B[-1][i]))
    for j in range(nz - 1):
        bm.faces.new((B[j][0], F[j][0], F[j + 1][0], B[j + 1][0]))
        bm.faces.new((F[j][-1], B[j][-1], B[j + 1][-1], F[j + 1][-1]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm_object(bm, names, name, 40, recalc=False)


def slotted_sheet(ys, zs, holes, h1, top, x0, thick, dfn, mfn, names, name, coarse_above=None):
    """Thin closed paper sheet: a (ys x zs) grid up to h0 = zs[-1], a band h0..h1 with punched
    holes, and a strip h1..top. holes = [(a, b, kind)] along y; kind 'slot' (closed hole) or
    'notch' (open to the top edge). Long-edged polygons are fanned from a corner so no triangle
    is degenerate. dfn(y, z) -> (dx, dz); mfn(y, z, front) -> slot index."""
    h0 = zs[-1]
    y0, y1 = ys[0], ys[-1]
    edges_y = sorted(set(ys + [a for a, _, _ in holes] + [b for _, b, _ in holes]))

    def in_hole(y, kinds):
        return any(a < y < b and k in kinds for a, b, k in holes)
    def lv(z):     # y breakpoints used on the level z (only the outer edges above coarse_above)
        return ys if coarse_above is None or z <= coarse_above else [y0, y1]
    polys = []     # outlines CCW seen from +X (y right, z up); first key is the fan apex
    for j in range(len(zs) - 2):
        yb, yt = lv(zs[j]), lv(zs[j + 1])
        if yb == yt:
            for i in range(len(yb) - 1):
                polys.append([(yb[i], zs[j]), (yb[i + 1], zs[j]), (yb[i + 1], zs[j + 1]), (yb[i], zs[j + 1])])
        else:      # fine level below a coarse one (flat there): one fan from the top-left corner
            polys.append([(y0, zs[j + 1])] + [(y, zs[j]) for y in yb] + [(y1, zs[j + 1])])
    j = len(zs) - 2
    yb = lv(zs[j])
    for i in range(len(yb) - 1):
        topv = [(y, h0) for y in edges_y if yb[i] <= y <= yb[i + 1]]
        polys.append([(yb[i], zs[j]), (yb[i + 1], zs[j])] + list(reversed(topv)))
    for u, v in zip(edges_y, edges_y[1:]):
        if not in_hole((u + v) / 2, ("slot", "notch")):
            polys.append([(u, h0), (v, h0), (v, h1), (u, h1)])
    segs, cur = [], y0
    for a, b, k in sorted(holes):
        if k == "notch":
            segs.append((cur, a))
            cur = b
    segs.append((cur, y1))
    for sa, sb in segs:
        polys.append([(sa, top)] + [(y, h1) for y in edges_y if sa <= y <= sb] + [(sb, top)])
    bm = bmesh.new()
    F, B = {}, {}
    for poly in polys:
        for key in poly:
            if key not in F:
                dx, dz = dfn(*key)
                F[key] = bm.verts.new((x0 + thick + dx, key[0], key[1] + dz))
                B[key] = bm.verts.new((x0 + dx, key[0], key[1] + dz))
    use = {}
    for poly in polys:
        yc = sum(k[0] for k in poly) / len(poly)
        zc = sum(k[1] for k in poly) / len(poly)
        mf, mb = mfn(yc, zc, True), mfn(yc, zc, False)
        if len(poly) > 4:
            tris = [(poly[0], poly[t], poly[t + 1]) for t in range(1, len(poly) - 1)]
        else:
            tris = [(poly[0], poly[1], poly[2]), (poly[0], poly[2], poly[3])]
        for tri in tris:
            bm.faces.new([F[k] for k in tri]).material_index = mf
            bm.faces.new([B[k] for k in reversed(tri)]).material_index = mb
        for k1, k2 in zip(poly, poly[1:] + poly[:1]):
            e = (min(k1, k2), max(k1, k2))
            use.setdefault(e, []).append((k1, k2))
    for e, lst in use.items():
        if len(lst) == 1:
            k1, k2 = lst[0]
            yc, zc = (k1[0] + k2[0]) / 2, (k1[1] + k2[1]) / 2
            f = bm.faces.new((F[k2], F[k1], B[k1], B[k2]))
            f.material_index = mfn(yc, zc, False)
    return bm_object(bm, names, name, 40, recalc=False)


def calendar():
    """Wall calendar 60 x 80 overall: card-backed month stack and the current month sheet (picture
    on top, printed month grid below, bottom-right corner curling), wire-o loops through punched
    slots wrapping the top edge, a wire hanger in a centre notch. Pivot at the back centre (wall
    contact), faces +X."""
    top = 37.8                                # paper top; the hanger peaks at z 40
    R, rw = 0.65, 0.07                        # loop radius (8-gon, flat bottom) and wire radius
    cflat = R * math.cos(math.pi / 8)
    xc = cflat + rw                           # paper mid-plane / loop centre (back flat at ~x 0)
    zh = top - 0.7                            # hole centre: loops enclose the top 0.7 cm
    zc = zh + cflat
    h0, h1 = zh - 0.27, zh + 0.27             # slot band: 0.2 cm air round the wire
    loop_y = [sg * (6.0 + 5.5 * k) for k in range(5) for sg in (1, -1)]
    holes = [(y - 0.3, y + 0.3, "slot") for y in loop_y] + [(-3.0, 3.0, "notch")]
    paper = []
    # month stack on its card back (0.2 thick), then the current month sheet 0.2 cm in front
    xs0 = xc - 0.225
    # (the stack stops just under the punched band: it is hidden behind the current month except at
    # the curled corner, so it needs no slots of its own and stays clear of the wire loops)
    paper.append(sheet([-30.0, 30.0], [-40.0, h0 - 0.25], xs0, 0.2,
                       lambda y, z: (0, 0), lambda y, z, f: 0, ["M_Paper"], "stack"))

    def curl(y, z):    # bottom-right corner of the current month lifts off the stack
        t = smoothstep(12, 30, y) * smoothstep(-26, -40, z)
        return 2.2 * t * t, 0.35 * t * t
    xm0 = xs0 + 0.2 + GAP
    # Orientation-calendar page: top 40 % a picture (M_Photo, own 0..1 map), bottom 60 % a printed
    # month grid on white paper (M_Paper) with ink lines (M_PlasticBlack): a month title bar, a
    # weekday header row and 7 x 5 day cells, the days up to today crossed off in marker.
    # Breakpoints: a fine 2 cm lattice only where the bottom-right corner curls (y 12..30,
    # z -40..-26) and at the picture's lower edge (z 6); grid-line positions inside the curl sit on
    # lattice nodes so the ink strips follow the bent paper exactly.
    PH0 = 6.0                                  # picture: z 6 .. 34.6, full width
    MT = 0.1                                   # month sheet thickness (1 mm)
    month_ys = [-30.0, 12.0, 14.0, 16.0, 18.0, 20.0, 22.0, 24.0, 26.0, 28.0, 30.0]
    month_zs = [-40.0, -38.0, -36.0, -34.0, -31.0, -29.0, -26.0, PH0, 34.6, h0]
    paper.append(slotted_sheet(month_ys, month_zs, holes, h1, top, xm0, MT, curl,
                               lambda y, z, f: 1 if (f and PH0 < z < 34.6) else 0,
                               ["M_Paper", "M_Photo"], "month", coarse_above=-26.0))
    # ink: flat strips 0.06 cm proud of the month face, sampled on the lattice inside the curl
    xf = xm0 + MT
    ink_bm = bmesh.new()

    def ink_pt(y, z, lift):
        dx, dz = curl(y, z)
        return Vector((xf + dx + lift, y, z + dz))

    def ink_strip(p0, p1, w, lift=0.06):
        """Strip of width w from (y0, z0) to (y1, z1); split at every lattice node it crosses."""
        (ya, za), (yb, zb) = p0, p1
        L = math.hypot(yb - ya, zb - za)
        uy, uz = (yb - ya) / L, (zb - za) / L
        ny, nz = -uz * w / 2, uy * w / 2
        ts = {0.0, 1.0}
        in_curl = min(za, zb) < -26.0 and max(ya, yb) > 12.0
        for yy in (month_ys if in_curl else []):
            if abs(yb - ya) > 1e-6 and min(ya, yb) < yy < max(ya, yb):
                ts.add((yy - ya) / (yb - ya))
        for zz in (month_zs if in_curl else []):
            if abs(zb - za) > 1e-6 and min(za, zb) < zz < max(za, zb):
                ts.add((zz - za) / (zb - za))
        ts = sorted(ts)
        left = [ink_bm.verts.new(ink_pt(ya + (yb - ya) * t + ny, za + (zb - za) * t + nz, lift)) for t in ts]
        right = [ink_bm.verts.new(ink_pt(ya + (yb - ya) * t - ny, za + (zb - za) * t - nz, lift)) for t in ts]
        for k in range(len(ts) - 1):
            ink_bm.faces.new((right[k], right[k + 1], left[k + 1], left[k]))
    GY = [-28.0 + 8.0 * k for k in range(8)]              # 7 columns, 8 cm wide
    GZ = [0.0, -3.0, -10.0, -17.0, -24.0, -31.0, -38.0]   # weekday header + 5 week rows, 7 cm tall
    LW = 0.28
    # verticals and horizontals on separate layers (0.015 cm apart) so crossing strips never share
    # a plane; the horizontals stop short of the outer verticals' ends (no welded corners)
    for gy in GY:
        ink_strip((gy, GZ[0] + LW / 2), (gy, GZ[-1] - LW / 2), LW, 0.06)
    for k, gz in enumerate(GZ):
        ink_strip((GY[0] - LW / 2 + 0.02, gz), (GY[-1] + LW / 2 - 0.02, gz), LW * (1.6 if k == 0 else 1.0),
                  0.075)
    # month title bar and weekday header tint
    ink_strip((-11.0, 3.3), (11.0, 3.3), 2.2)
    # days up to today crossed off (two strokes per cell, the second a hair higher)
    crossed = [(r, c) for r in range(3) for c in range(7)][2:19]
    for r, c in crossed:
        y0c, y1c = GY[c] + 1.6, GY[c + 1] - 1.6
        z0c, z1c = GZ[r + 2] + 1.3, GZ[r + 1] - 1.3
        ink_strip((y0c, z0c), (y1c, z1c), 0.3, 0.06)
        ink_strip((y0c, z1c), (y1c, z0c), 0.3, 0.075)
    paper.append(bm_object(ink_bm, ["M_PlasticBlack"], "ink", 20, recalc=False))
    # wire-o loops (8-gon with a flat bottom run through the slots) and the hanger in the notch
    wire = []
    for y in loop_y:
        pts = [Vector((xc + R * math.cos(a), y, zc + R * math.sin(a)))
               for a in (math.pi / 8 + 2 * math.pi * i / 8 for i in range(8))]
        wire.append(tube(pts, rw, "M_Metal", sides=3, cyclic=True, up=(0, 1, 0), name="loop"))
    hp = [(-2.2, zh), (2.2, zh), (2.5, zh + 0.4), (0.9, 38.9), (0.32, 39.7), (0.0, 40.0 - rw),
          (-0.32, 39.7), (-0.9, 38.9), (-2.5, zh + 0.4)]
    wire.append(tube([Vector((xc, y, z)) for y, z in hp], rw, "M_Metal", sides=3, cyclic=True,
                     up=(1, 0, 0), name="hanger"))
    # the paper leans back so its bottom edge rests at the wall plane under the wire's stand-off
    xmin_w = min(v.co.x for o in wire for v in o.data.vertices)
    s = (xs0 - xmin_w) / (top + 40.0)
    for o in paper:
        xform(o, Matrix(((1, 0, s, -s * top), (0, 1, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1))))
    parts = paper + wire
    for o in parts:
        xform(o, Matrix.Translation((-xmin_w, 0, 0)))
    return join("SM_Calendar", parts)


# ------------------------------------------------------------------ UVs, export, preview
def uvs(ob, margin=0.02, chunk_m=None, angle=60.0):
    me = ob.data
    rest = me.attributes.get("rest")
    rest_v = [Vector(d.vector) for d in rest.data] if rest is not None else None
    lma = me.attributes.get("lm")
    lm_v = [Vector(d.vector) for d in lma.data] if lma is not None else None
    while len(me.uv_layers):
        me.uv_layers.remove(me.uv_layers[0])
    uv0 = me.uv_layers.new(name="UVMap")
    uv1 = me.uv_layers.new(name="Lightmap")
    names = [m.name if m else "" for m in me.materials]
    photo = {i for i, n in enumerate(names) if n == "M_Photo"}
    cloth = {i for i, n in enumerate(names) if n == "M_Curtain"}
    bm = bmesh.new()
    bm.from_mesh(me)
    l0 = bm.loops.layers.uv["UVMap"]
    l1 = bm.loops.layers.uv["Lightmap"]
    for f in bm.faces:
        n = f.normal
        ax = max(range(3), key=lambda i: abs(n[i]))
        for loop in f.loops:
            co = loop.vert.co
            loop[l0].uv = (co.y, co.z) if ax == 0 else (co.x, co.z) if ax == 1 else (co.x, co.y)
    pf = [f for f in bm.faces if f.material_index in photo]
    if pf:   # 0..1 picture map: u to the viewer's right (+Y in Blender for a +X facing picture), v up
        nrm = pf[0].normal
        udir = Vector((0, 0, 1)).cross(nrm).normalized()
        vdir = nrm.cross(udir).normalized()
        cos = [l.vert.co for f in pf for l in f.loops]
        us, vs = [c.dot(udir) for c in cos], [c.dot(vdir) for c in cos]
        for f in pf:
            for loop in f.loops:
                c = loop.vert.co
                loop[l0].uv = ((c.dot(udir) - min(us)) / (max(us) - min(us)),
                               (c.dot(vdir) - min(vs)) / (max(vs) - min(vs)))
    if rest_v is not None and cloth:
        # second panel shifted in u so both unfolded panels sit side by side
        cf = [f for f in bm.faces if f.material_index in cloth]
        for f in cf:
            for loop in f.loops:
                r = rest_v[loop.vert.index]
                loop[l0].uv = (r.x, r.y)
                loop[l1].uv = (r.x + (2.0 if loop.vert.co.y < -2.25 else 0.0), r.y)
    if lm_v is not None:   # builder-supplied unfold (e.g. the rug: field + flattened border in one island)
        for f in bm.faces:
            for loop in f.loops:
                r = lm_v[loop.vert.index]
                loop[l1].uv = (r.x, r.y)
    bm.to_mesh(me)
    bm.free()
    if rest is not None:
        me.attributes.remove(me.attributes["rest"])
    if lma is not None:
        me.attributes.remove(me.attributes["lm"])
    me.uv_layers.active = me.uv_layers["Lightmap"]
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.context.scene.tool_settings.use_uv_select_sync = True
    bpy.ops.mesh.select_mode(type="FACE")
    bpy.ops.mesh.select_all(action="DESELECT")
    ebm = bmesh.from_edit_mesh(me)
    for f in ebm.faces:
        if f.material_index not in cloth and lm_v is None:
            f.select_set(True)
    ebm.select_flush_mode()
    bmesh.update_edit_mesh(me)
    if any(f.select for f in ebm.faces):
        bpy.ops.uv.smart_project(angle_limit=math.radians(angle), island_margin=margin, scale_to_bounds=False)
    if chunk_m:
        # long thin parts (the rod): cut their lightmap strips into chunks along Y so packing
        # can stack them instead of shrinking everything to fit one 4 m strip
        ebm = bmesh.from_edit_mesh(me)
        lm = ebm.loops.layers.uv["Lightmap"]
        for f in ebm.faces:
            k = math.floor(f.calc_center_median().y / chunk_m)
            for loop in f.loops:
                loop[lm].uv.x += 5.0 * k
        bmesh.update_edit_mesh(me)
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.average_islands_scale()
    bpy.ops.uv.pack_islands(margin=margin, rotate=True)
    bpy.ops.object.mode_set(mode="OBJECT")
    me.uv_layers.active = me.uv_layers["UVMap"]
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
    sh.show_shadows = True
    sh.shadow_intensity = 0.3
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


def tri_count(ob):
    return sum(len(p.vertices) - 2 for p in ob.data.polygons)


VIEW_DIR = {"SM_CeilingFan": (1.0, -0.8, -0.45), "SM_Curtains": (-1.0, -0.35, 0.25),
            "SM_CurtainRod": (-1.0, -0.5, 0.3), "SM_Rug": (1.0, -0.8, 0.9)}


def build():
    import sys
    only = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    os.makedirs(PREVIEW, exist_ok=True)
    builders = [("SM_FloorLamp", floor_lamp), ("SM_CeilingFan", ceiling_fan), ("SM_CurtainRod", curtain_rod),
                ("SM_Curtains", curtains), ("SM_Rug", rug), ("SM_PlantPot", plant_pot),
                ("SM_PhotoFrame_MariaEnzo", lambda: photo_frame("SM_PhotoFrame_MariaEnzo", 50, 45, 4.5, 3.0,
                                                                "M_TimberDark", 4.0, slip_gold=True)),
                ("SM_PhotoFrame_Small", lambda: photo_frame("SM_PhotoFrame_Small", 30, 40, 2.6, 2.2, "M_Timber")),
                ("SM_PhotoFrame_Wide", lambda: photo_frame("SM_PhotoFrame_Wide", 45, 32, 3.2, 2.6,
                                                           "M_TimberDark", 3.0)),
                ("SM_Calendar", calendar)]
    pieces = []
    for name, fn in builders:
        if only and name not in only:
            continue
        print("building", name)
        pieces.append(fn())
    cam = setup_render()
    report = []
    for ob in pieces:
        uvs(ob, chunk_m=0.4 if ob.name == "SM_CurtainRod" else None,
            angle=66.0 if ob.name == "SM_Rug" else 60.0)
        export(ob)
        preview(ob, cam, VIEW_DIR.get(ob.name, (1.0, -0.8, 0.65)))
        pts = [v.co for v in ob.data.vertices]
        lo = Vector((min(p.x for p in pts), -max(p.y for p in pts), min(p.z for p in pts))) * 100
        hi = Vector((max(p.x for p in pts), -min(p.y for p in pts), max(p.z for p in pts))) * 100
        report.append(f"{ob.name}: tris={tri_count(ob)} mats={[m.name for m in ob.data.materials]} "
                      f"uv={[u.name for u in ob.data.uv_layers]} "
                      f"ue_bbox=({lo.x:.1f},{lo.y:.1f},{lo.z:.2f})..({hi.x:.1f},{hi.y:.1f},{hi.z:.2f})")
    if not only:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ROOM, "Items", "fixtures.blend"))
    print("\n".join(["FIXTURES REPORT"] + report))


build()
