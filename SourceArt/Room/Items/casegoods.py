"""Casegoods for Maria's room: bedside, wardrobe, TV cabinet, TV + screen, wall shelf, memory box.

Run headless:
  "C:\\Program Files\\Blender Foundation\\Blender 5.0\\blender.exe" -b --factory-startup --python casegoods.py
  (set CASEGOODS_ONLY=SM_Wardrobe,SM_TVCabinet to export / preview only those pieces)

Follows SourceArt/Room/CONVENTIONS.md and placement.json:
  * Geometry is authored in Unreal centimetres (X front, Y right, Z up) and converted once per
    piece to Blender metres with ue(x, y, z) = (x/100, -y/100, z/100); faces are flipped with the
    mirror so normals stay outward.
  * Pivot bottom centre on the floor, front +X. SM_Shelf: pivot at the back centre of the board
    underside (back on the wall plane at local x = 0). SM_TV / SM_TVScreen: pivot at the bottom of
    the pedestal, no baked height (placement drops the TV onto the cabinet); both share it.
    SM_MemoryBox: pivot bottom centre, lowest point at z = 0.
  * UV0 'UVMap' = 1 m box projection (SM_TVScreen: 0..1 over the screen); UV1 'Lightmap' = smart
    project + pack, 2% margin.
  * Real shapes, not boxes: shaker frame-and-panel doors (one slab per door, chamfered recessed
    panels), bevelled drawer fronts with shadow gaps, swept round bar pulls, mitred swept crown
    moulding (cove + bead + fascia), bullnose shelf board with ogee corbels, lathed tapered legs,
    a TV cabinet carcass built from separate bevelled boards, a slim rounded-bezel TV on a
    pedestal, a keepsake box with a moulded plinth band, an overhanging lid with a recessed field,
    brass corner straps, name plaque, keyhole escutcheon and barrel hinges.
  * The wardrobe has BYPASS SLIDING doors: the bed is only ~56 cm in front of it, so hinged
    76 cm doors would hit the bed (room audit, fix round 1).
  * Shading: finalize() marks edges sharp above sharp_deg and applies a Weighted Normal (face
    area, keep sharp) so large flat panels keep flat corner normals; the NORMALS lines printed by
    build() report any large face whose normals lean. NB the inspector's Workbench studio light
    shows a soft view-dependent gradient even on a perfectly flat six-face cube.
  * No intersections: parts inside a piece are separated by >= 0.05 cm air gaps (pull posts stop
    0.05 off the face, doors 0.1 off the carcass, etc.), so the inspector finds no intersecting
    parts. Footprints are checked against the placement fit rectangles in the RESULT lines.
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
CHECK = os.environ.get("CASEGOODS_CHECK_DIR")      # optional: extra check renders

# placement.json puts the memory box at yaw 90 on the 28 cm deep shelf, so local X runs along the
# wall. The box's 32 cm length therefore lies on local X and the hasp side (the face the room sees)
# is local -Y. Set False if the placement yaw ever becomes 0 / 180 (then length on local Y, hasp +X).
MEMORYBOX_LENGTH_ON_X = True

MATS = {
    "M_Timber": (0.66, 0.50, 0.33),
    "M_TimberDark": (0.36, 0.23, 0.13),
    "M_Metal": (0.62, 0.62, 0.64),
    "M_Brass": (0.80, 0.62, 0.28),
    "M_PlasticBlack": (0.045, 0.045, 0.05),
    "M_Screen": (0.10, 0.13, 0.18),
}
GAP = 0.05          # air gap between parts of one piece (cm)


def mat(name):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.diffuse_color = (*MATS[name], 1.0)
    m.roughness = 0.45
    return m


# ------------------------------------------------------------------ low-level helpers
def obj_from_bm(bm, name="tmp"):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def eval_to_bm(ob, recalc=True):
    """Apply all modifiers of ob (mesh or curve), return a bmesh, delete ob."""
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
    elif isinstance(data, bpy.types.Curve):
        bpy.data.curves.remove(data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-5)
    if recalc:
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return bm


def bevelled(bm, width=0.0, seg=1, angle=30):
    """Angle-limited bevel modifier, applied."""
    if width <= 0:
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        return bm
    ob = obj_from_bm(bm)
    m = ob.modifiers.new("bevel", "BEVEL")
    m.width = width
    m.segments = seg
    m.limit_method = "ANGLE"
    m.angle_limit = math.radians(angle)
    m.profile = 0.5
    m.harden_normals = False
    return eval_to_bm(ob)


def bevel_edges(bm, edges, offset, seg):
    bmesh.ops.bevel(bm, geom=list(edges), offset=offset, offset_type="OFFSET", segments=seg,
                    profile=0.5, affect="EDGES", clamp_overlap=True)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])


def translate(bm, v):
    bmesh.ops.translate(bm, verts=bm.verts[:], vec=Vector(v))
    return bm


def rotate(bm, m3):
    bmesh.ops.rotate(bm, verts=bm.verts[:], cent=Vector((0, 0, 0)), matrix=m3)
    return bm


def box(x0, x1, y0, y1, z0, z1, m, bev=0.3, seg=2, angle=30):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector((x1 if v.co.x > 0 else x0, y1 if v.co.y > 0 else y0, z1 if v.co.z > 0 else z0))
    return bevelled(bm, bev, seg, angle), m


def panel(x0, x1, y0, y1, z0, z1, m, bev=0.3, seg=2, skip_back=True, skip_top=False):
    """Board / panel: a box whose edges are bevelled with 'seg' segments, except the edges lying
    entirely in the back plane x = x0 (against the wall, never seen) when skip_back is set, and
    those in the top plane z = z1 (hidden under a top board) when skip_top is set."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector((x1 if v.co.x > 0 else x0, y1 if v.co.y > 0 else y0, z1 if v.co.z > 0 else z0))
    if bev > 0:
        edges = [e for e in bm.edges
                 if not (skip_back and all(abs(v.co.x - x0) < 1e-6 for v in e.verts))
                 and not (skip_top and all(abs(v.co.z - z1) < 1e-6 for v in e.verts))]
        bevel_edges(bm, edges, bev, seg)
    return bm, m


def rrect(w, h, r, segs=4):
    """CCW rounded rectangle outline centred at 0 (w along a, h along b)."""
    pts = []
    for cx, cy, a0 in ((w / 2 - r, h / 2 - r, 0), (-w / 2 + r, h / 2 - r, 90),
                       (-w / 2 + r, -h / 2 + r, 180), (w / 2 - r, -h / 2 + r, 270)):
        for i in range(segs + 1):
            a = math.radians(a0 + 90.0 * i / segs)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def prism(pts, to3d, d0, d1):
    """Extrude a closed 2D outline (may be concave) between depths d0..d1; returns bm, cap0, cap1."""
    bm = bmesh.new()
    r0 = [bm.verts.new(to3d(a, b, d0)) for a, b in pts]
    r1 = [bm.verts.new(to3d(a, b, d1)) for a, b in pts]
    n = len(pts)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((r0[i], r0[j], r1[j], r1[i]))
    c0 = bm.faces.new(list(reversed(r0)))
    c1 = bm.faces.new(r1)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return bm, c0, c1


def rounded_slab(pts, to3d, d0, d1, bev0, seg0, bev1, seg1):
    """Prism with its two cap outlines bevelled independently (soft-edged plates, lids, bezels)."""
    bm, c0, c1 = prism(pts, to3d, d0, d1)
    e0 = list(c0.edges)
    e1 = list(c1.edges)
    if bev1 > 0:
        bevel_edges(bm, e1, bev1, seg1)
    if bev0 > 0:
        e0 = [e for e in e0 if e.is_valid]
        bevel_edges(bm, e0, bev0, seg0)
    return bm


def rr_loft(L, W, R, rings, segs=3):
    """Soft rounded-rectangle solid lofted through rings [(inset, z), ...] (bottom to top): each
    ring is the L x W, radius R outline shrunk by 'inset'. Capped top and bottom. Used for turned-
    looking lids, cushioned tops and boxes with rounded edges in one clean quad mesh."""
    bm = bmesh.new()
    loops = []
    for ring in rings:
        o, z = ring[0], ring[1]
        r = ring[2] if len(ring) > 2 else max(R - o, 0.05)
        loops.append([bm.verts.new((a, b, z)) for a, b in rrect(L - 2 * o, W - 2 * o, r, segs)])
    n = len(loops[0])
    for k in range(len(loops) - 1):
        a, b = loops[k], loops[k + 1]
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((a[i], a[j], b[j], b[i]))
    bm.faces.new(list(reversed(loops[0])))
    bm.faces.new(loops[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return bm


def quarter(o0, z0, o1, z1, n, convex=True):
    """Ring list for a quarter-round from (inset o0, z0) to (o1, z1), excluding the start."""
    out = []
    for k in range(1, n + 1):
        a = math.radians(90.0 * k / n)
        if convex:      # bulges outward: inset grows slowly first while z climbs quickly
            out.append((o0 + (o1 - o0) * (1 - math.cos(a)), z0 + (z1 - z0) * math.sin(a)))
        else:
            out.append((o0 + (o1 - o0) * math.sin(a), z0 + (z1 - z0) * (1 - math.cos(a))))
    return out


def sweep(profile, path, hint=(0, 0, 1), mitre=True, closed=False):
    """Sweep a closed 2D profile (u = side, v = up) along a polyline with mitred joints."""
    hint = Vector(hint)
    P = [Vector(p) for p in path]
    n = len(P)
    bm = bmesh.new()
    rings = []
    for i in range(n):
        if closed:
            t0 = (P[i] - P[i - 1]).normalized()
            t1 = (P[(i + 1) % n] - P[i]).normalized()
            t = (t0 + t1).normalized()
        elif i == 0:
            t = t0 = (P[1] - P[0]).normalized()
        elif i == n - 1:
            t = t0 = (P[i] - P[i - 1]).normalized()
        else:
            t0 = (P[i] - P[i - 1]).normalized()
            t1 = (P[i + 1] - P[i]).normalized()
            t = (t0 + t1).normalized()
        side = t.cross(hint).normalized()
        up = side.cross(t).normalized()
        k = 1.0
        if mitre and (closed or 0 < i < n - 1):
            k = 1.0 / max(0.25, side.dot(t0.cross(hint).normalized()))
        rings.append([bm.verts.new(P[i] + side * (u * k) + up * v) for u, v in profile])
    m = len(profile)
    for i in range(n if closed else n - 1):
        a, b = rings[i], rings[(i + 1) % n]
        for j in range(m):
            jj = (j + 1) % m
            bm.faces.new((a[j], a[jj], b[jj], b[j]))
    if not closed:
        bm.faces.new(list(reversed(rings[0])))
        bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return bm


def fillet(points, r, segs=3):
    """Round the interior corners of a polyline with quadratic-Bezier arcs of radius ~r."""
    P = [Vector(p) for p in points]
    out = [P[0]]
    for i in range(1, len(P) - 1):
        a, b, c = P[i - 1], P[i], P[i + 1]
        d = min(r, (a - b).length * 0.49, (c - b).length * 0.49)
        p1 = b + (a - b).normalized() * d
        p2 = b + (c - b).normalized() * d
        for k in range(segs + 1):
            t = k / segs
            out.append(p1 * (1 - t) ** 2 + b * 2 * (1 - t) * t + p2 * t * t)
    out.append(P[-1])
    return out


def tube(points, radius, m, res=1):
    """Round tube swept along a polyline (curve bevel_depth), capped, converted to mesh."""
    cu = bpy.data.curves.new("tube", "CURVE")
    cu.dimensions = "3D"
    cu.bevel_mode = "ROUND"
    cu.bevel_depth = radius
    cu.bevel_resolution = res
    cu.use_fill_caps = True
    cu.twist_mode = "MINIMUM"
    sp = cu.splines.new("POLY")
    sp.points.add(len(points) - 1)
    for i, p in enumerate(points):
        sp.points[i].co = (p[0], p[1], p[2], 1.0)
    ob = bpy.data.objects.new("tube", cu)
    bpy.context.scene.collection.objects.link(ob)
    return eval_to_bm(ob), m


def bar_pull(x_face, yc, zc, length, proj, radius, m, vertical=False, res=1):
    """D bar handle: two posts out of the face (+X) and a bar, corners filleted, swept round section.
    The posts stop GAP short of the face so the handle never passes into the door."""
    x0 = x_face + GAP
    xb = x_face + proj - radius
    if vertical:
        pts = [(x0, yc, zc - length / 2), (xb, yc, zc - length / 2),
               (xb, yc, zc + length / 2), (x0, yc, zc + length / 2)]
    else:
        pts = [(x0, yc - length / 2, zc), (xb, yc - length / 2, zc),
               (xb, yc + length / 2, zc), (x0, yc + length / 2, zc)]
    return tube(fillet(pts, min(radius * 2.2, proj * 0.6), 3), radius, m, res)


def lathe(profile, steps, m, axis="Z", loc=(0, 0, 0)):
    """Turned part: (r, z) profile from axis to axis, revolved with a Screw modifier."""
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
    if axis == "X":
        rotate(bm, Matrix.Rotation(math.radians(90), 3, "Y"))
    elif axis == "Y":
        rotate(bm, Matrix.Rotation(math.radians(-90), 3, "X"))
    translate(bm, loc)
    return bm, m


def shaker(y0, y1, z0, z1, xb, t, stile, panels, m, rail=None, cham=0.5, drop=0.4, bev=0.3):
    """One-piece shaker door / panel, front face at xb + t facing +X.

    panels = [(za, zb), ...] z-ranges of the recessed panels (between them are rails); stiles are
    'stile' wide. Each panel is sunk with a 45 degree chamfer (cham) then a square drop, and all
    the slab's outside edges get a rounded bevel. One closed mesh, so no internal seams."""
    xf = xb + t
    ys = [y0, y0 + stile, y1 - stile, y1]
    zs = [z0]
    for a, b in panels:
        zs += [a, b]
    zs.append(z1)
    bm = bmesh.new()
    V = [[bm.verts.new((xf, y, z)) for z in zs] for y in ys]
    nz = len(zs)
    panel_faces = []
    for i in range(3):
        for j in range(nz - 1):
            f = bm.faces.new((V[i][j], V[i + 1][j], V[i + 1][j + 1], V[i][j + 1]))
            if i == 1 and j % 2 == 1:
                panel_faces.append(f)
    per = [V[i][0] for i in range(4)] + [V[3][j] for j in range(1, nz)] + \
          [V[i][nz - 1] for i in range(2, -1, -1)] + [V[0][j] for j in range(nz - 2, 0, -1)]
    back = [bm.verts.new((xb, v.co.y, v.co.z)) for v in per]
    n = len(per)
    for k in range(n):
        bm.faces.new((per[k], back[k], back[(k + 1) % n], per[(k + 1) % n]))
    bm.faces.new(list(reversed(back)))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    for f in panel_faces:
        bmesh.ops.inset_region(bm, faces=[f], thickness=cham, depth=-cham, use_even_offset=True)
        bmesh.ops.inset_region(bm, faces=[f], thickness=0.0, depth=-drop, use_even_offset=True)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return bevelled(bm, bev, 2, angle=60), m


def arc_strap(cx, cy, r, a0, a1, arm, z0, z1, th, m, segs=4):
    """Brass corner strap: thin band swept horizontally around a vertical rounded corner of radius r
    centred at (cx, cy), from angle a0 to a1 (deg), with straight arms 'arm' long on both sides.
    The band's inner face sits GAP off the wood."""
    rc = r + GAP + th / 2
    pts = []
    a0r, a1r = math.radians(a0), math.radians(a1)
    t0 = Vector((math.sin(a0r), -math.cos(a0r), 0))          # tangent pointing back along a0 side
    p0 = Vector((cx + rc * math.cos(a0r), cy + rc * math.sin(a0r), 0))
    pts.append(p0 + t0 * arm)
    for k in range(segs + 1):
        a = a0r + (a1r - a0r) * k / segs
        pts.append(Vector((cx + rc * math.cos(a), cy + rc * math.sin(a), 0)))
    t1 = Vector((-math.sin(a1r), math.cos(a1r), 0))
    pts.append(pts[-1] + t1 * arm)
    h = (z1 - z0) / 2
    prof = [(-th / 2, -h), (th / 2, -h), (th / 2, h), (-th / 2, h)]
    bm = sweep(prof, [(p.x, p.y, (z0 + z1) / 2) for p in pts], hint=(0, 0, 1), mitre=True)
    return bm, m


# ------------------------------------------------------------------ piece assembly
def finalize(name, parts, sharp_deg=40.0, wn_weight=50):
    """Join (bmesh, material) parts, convert UE cm -> Blender m (mirror Y), triangulate, normals."""
    mats = []
    allbm = bmesh.new()
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
    bmesh.ops.reverse_faces(allbm, faces=allbm.faces[:])          # mirror flips winding back
    bmesh.ops.triangulate(allbm, faces=allbm.faces[:], quad_method="BEAUTY", ngon_method="BEAUTY")
    bmesh.ops.dissolve_degenerate(allbm, dist=1e-7, edges=allbm.edges[:])
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
    wn.weight = wn_weight         # 100 = large flat faces fully own their corner normals
    dg = bpy.context.evaluated_depsgraph_get()
    me2 = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    ob.modifiers.clear()
    ob.data = me2
    bpy.data.meshes.remove(me)
    me2.name = name
    return ob


def tris(ob):
    return sum(len(p.vertices) - 2 for p in ob.data.polygons)


def bounds_ue(ob):
    xs = [v.co.x * 100 for v in ob.data.vertices]
    ys = [-v.co.y * 100 for v in ob.data.vertices]
    zs = [v.co.z * 100 for v in ob.data.vertices]
    return (min(xs), max(xs)), (min(ys), max(ys)), (min(zs), max(zs))


# ------------------------------------------------------------------ pieces
def bedside():
    """3-drawer bedside, 46 d x 52 w x 62 h: rounded top, overlay drawer fronts with 0.3 shadow gaps,
    D bar pulls, recessed dark plinth."""
    p = [
        box(-23.0, 23.0, -26.0, 26.0, 59.45, 62.0, "M_Timber", 0.8, 3),      # top, soft rounded edges
        box(-22.9, 20.5, -25.0, 25.0, 6.05, 59.4, "M_Timber", 0.3, 1),       # carcass
        box(-21.0, 17.5, -23.0, 23.0, 0.0, 6.0, "M_TimberDark", 0.25, 1),    # recessed plinth
    ]
    for z0, z1 in ((6.4, 25.4), (25.7, 42.4), (42.7, 59.1)):
        p.append(box(20.6, 22.4, -24.85, 24.85, z0, z1, "M_Timber", 0.4, 2))
        p.append(bar_pull(22.4, 0.0, (z0 + z1) / 2, 12.8, 2.6, 0.5, "M_Metal", res=1))
    return finalize("SM_Bedside", p)


def wardrobe():
    """Double wardrobe 62 d x 160 w x 205 h with two BYPASS SLIDING shaker doors (the bed side is
    only ~56 cm from the wardrobe front, so hinged 76 cm doors would hit the bed). Real build:
    1.8 cm side panels running forward to frame the doors, carcass body, top pelmet hiding the
    track, aluminium bottom guide rail, recessed dark plinth, swept crown moulding.
    Rear door (left, -Y) on the inner track has a slim strip pull (1.2 cm proud) so the front door
    (right, +Y, outer track, 1.8 cm in front) can slide over it; the front door has a long bar."""
    Wc, XB = 76.0, -31.0             # outer half width (sides), back plane
    XC, XS = 20.5, 26.7              # carcass body front, side panel / pelmet front
    Wi = Wc - 1.8                    # inner face of the side panels
    p = [
        box(XB, XC, -Wi + GAP, Wi - GAP, 8.05, 205.0, "M_Timber", 0.0),               # body
        box(-29.0, XC - 2.5, -Wc + 2.0, Wc - 2.0, 0.0, 8.0, "M_TimberDark", 0.25, 1),   # plinth
        panel(XC + GAP, XS, -Wi + GAP, Wi - GAP, 192.0, 205.0, "M_Timber", 0.3, 2),     # pelmet
        box(XC + GAP, XS - 0.4, -Wi + GAP, Wi - GAP, 8.1, 9.0, "M_Metal", 0.15, 1),     # bottom rail
    ]
    for y0, y1 in ((-Wc, -Wi), (Wi, Wc)):                                               # side panels
        p.append(panel(XB, XS, y0, y1, 8.05, 205.0, "M_Timber", 0.3, 2))
    panels = [(19.1, 70.0), (78.0, 183.9)]
    p.append(shaker(-Wi + 0.1, 2.0, 9.1, 191.9, XC + 0.3, 1.9, 7.5, panels, "M_Timber"))   # rear door
    p.append(shaker(-2.0, Wi - 0.1, 9.1, 191.9, 24.5, 1.9, 7.5, panels, "M_Timber"))       # front door
    p.append(bar_pull(XC + 0.3 + 1.9, -Wi + 5.6, 110.0, 60.0, 1.2, 0.35, "M_Metal", vertical=True))
    p.append(bar_pull(24.5 + 1.9, Wi - 5.6, 110.0, 50.0, 3.0, 0.6, "M_Metal", vertical=True))
    # Crown moulding: cove, step, bead, fascia, rounded top -- swept round front + sides, mitred.
    prof = [(GAP, 196.5), (0.6, 196.5), (0.6, 197.2)]
    for k in range(1, 6):                                     # concave cove r 2.4, centre (3.0, 197.2)
        a = math.radians(180 - 90 * k / 5)
        prof.append((3.0 + 2.4 * math.cos(a), 197.2 + 2.4 * math.sin(a)))
    prof.append((3.3, 199.6))
    for k in range(1, 5):                                     # convex bead r 0.5, centre (3.3, 200.1)
        a = math.radians(-90 + 180 * k / 4)
        prof.append((3.3 + 0.5 * math.cos(a), 200.1 + 0.5 * math.sin(a)))
    prof += [(3.5, 200.6), (4.0, 200.9), (4.0, 204.3)]
    for k in range(1, 4):                                     # rounded top edge r 0.7
        a = math.radians(90 * k / 3)
        prof.append((3.3 + 0.7 * math.cos(a), 204.3 + 0.7 * math.sin(a)))
    prof.append((GAP, 205.0))
    prof = list(reversed(prof))
    path = [(XB, -Wc, 0.0), (XS, -Wc, 0.0), (XS, Wc, 0.0), (XB, Wc, 0.0)]
    p.append((sweep(prof, path), "M_Timber"))
    return finalize("SM_Wardrobe", p, sharp_deg=50.0, wn_weight=100)


def tv_cabinet():
    """Low TV cabinet 44 d x 110 w x 60 h on four lathed tapered legs, two shaker doors, bar pulls.
    Carcass built from real boards: 1.8 cm side panels (front and long edges bevelled 0.3 / 2 seg),
    a bottom panel raised 1 cm and set 1 cm back from the side edges (visible underside reveal above
    the legs) and a thin back panel, all separated by 0.05 cm air gaps."""
    SX0, SX1, SW, SZ0, SZ1 = -21.8, 18.6, 54.0, 12.0, 57.5
    Wi = SW - 1.8
    p = [
        box(-22.0, 21.0, -55.0, 55.0, 57.55, 60.0, "M_Timber", 0.8, 2),      # top, rounded edges
        box(SX0, SX0 + 0.8, -Wi + GAP, Wi - GAP, SZ0, SZ1 - GAP, "M_Timber", 0.0),             # back
        box(SX0 + 0.8 + GAP, SX1 - 1.0, -Wi + GAP, Wi - GAP, SZ0 + 1.0, SZ0 + 2.8, "M_Timber", 0.0),  # bottom
    ]
    for y0, y1 in ((-SW, -Wi), (Wi, SW)):
        p.append(panel(SX0, SX1, y0, y1, SZ0, SZ1, "M_Timber", 0.3, 2, skip_top=True))
    for y0, y1 in ((-53.9, -0.15), (0.15, 53.9)):
        p.append(shaker(y0, y1, 12.4, 57.1, 18.7, 1.8, 6.5, [(18.9, 50.6)], "M_Timber"))
    for y in (-3.4, 3.4):
        p.append(bar_pull(20.5, y, 40.0, 12.8, 2.2, 0.45, "M_Metal", vertical=True, res=1))
    top = SZ0 + 1.0 - GAP            # legs carry the raised bottom panel
    leg = [(0.0, 0.0), (1.05, 0.0), (1.25, 0.3), (1.75, top - 2.35), (2.2, top - 1.75), (2.2, top),
           (0.0, top)]
    for x in (-18.0, 14.5):
        for y in (-49.0, 49.0):
            p.append(lathe(leg, 10, "M_Timber", loc=(x, y, 0.0)))
    return finalize("SM_TVCabinet", p, sharp_deg=50.0, wn_weight=100)


# TV geometry (UE cm, local to the pedestal pivot; shared by SM_TV and SM_TVScreen).
SCR_W, SCR_H = 88.4, 49.7                  # 40" 16:9 active area
BEZ_EDGE, BEZ_IN, SCR_MARGIN, CHIN = 0.3, 0.7, 0.2, 0.8
TV_W = SCR_W + 2 * (BEZ_EDGE + BEZ_IN + SCR_MARGIN)
TV_H = SCR_H + 2 * (BEZ_EDGE + BEZ_IN + SCR_MARGIN) + CHIN
TV_XB, TV_XF = 1.8, 3.0                    # panel back / front face (X)
TV_ZB = 8.0                                # panel bottom above the pedestal base
TV_ZC = TV_ZB + TV_H / 2
RECESS = 0.12
SCR_X = TV_XF - RECESS + 0.03              # screen surface sits just in front of the recessed face
SCR_Z0 = TV_ZB + BEZ_EDGE + BEZ_IN + SCR_MARGIN + CHIN
SCR_Z1 = SCR_Z0 + SCR_H


def tv():
    """Slim 40" TV: rounded-bezel panel with a recessed screen field, rounded rear electronics
    housing, short pedestal neck on a soft rounded base plate."""
    bm = rounded_slab(rrect(TV_W, TV_H, 1.6, 4), lambda a, b, d: (d, a, TV_ZC + b), TV_XB, TV_XF,
                      0.3, 1, BEZ_EDGE, 2)
    front = max((f for f in bm.faces if f.normal.x > 0.999), key=lambda f: f.calc_area())
    bmesh.ops.inset_region(bm, faces=[front], thickness=BEZ_IN, depth=-RECESS, use_even_offset=True)
    zmin = min(v.co.z for v in front.verts)
    for v in front.verts:                                     # thicker chin under the screen
        if v.co.z < zmin + 0.9:
            v.co.z += CHIN
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    p = [(bm, "M_PlasticBlack")]
    hz0, hz1 = TV_ZB + 6.0, TV_ZB + 36.0
    housing = rounded_slab(rrect(60.0, hz1 - hz0, 3.0, 4), lambda a, b, d: (d, a, (hz0 + hz1) / 2 + b),
                           -3.2, TV_XB - GAP, 1.6, 3, 0.2, 1)
    p.append((housing, "M_PlasticBlack"))
    base = rounded_slab(rrect(19.0, 26.0, 4.5, 4), lambda a, b, d: (a, b, d), 0.0, 1.0, 0.15, 1, 0.45, 2)
    p.append((base, "M_PlasticBlack"))
    neck = rounded_slab(rrect(2.6, 7.0, 1.0, 3), lambda a, b, d: (a - 0.6, b, d), 1.0 + GAP, hz0 - GAP,
                        0.0, 0, 0.0, 0)
    p.append((neck, "M_PlasticBlack"))
    return finalize("SM_TV", p)


def tv_screen():
    bm = bmesh.new()
    w = SCR_W / 2
    vs = [bm.verts.new(c) for c in ((SCR_X, -w, SCR_Z0), (SCR_X, w, SCR_Z0), (SCR_X, w, SCR_Z1),
                                    (SCR_X, -w, SCR_Z1))]
    f = bm.faces.new(vs)
    f.normal_update()
    if f.normal.x < 0:
        f.normal_flip()
    return finalize("SM_TVScreen", [(bm, "M_Screen")])


def shelf():
    """Wall shelf 28 d x 90 l x 2.5: bullnose-fronted board on two ogee corbels.
    Pivot: back centre of the board underside; back face on the wall plane at local x = 0."""
    T, D, L = 2.5, 28.0, 90.0
    prof = [(0.0, 0.0), (D - 0.6, 0.0)]                       # (x, z) section of the board
    for k in range(1, 4):                                     # small round under the front
        a = math.radians(-90 + 90 * k / 3)
        prof.append((D - 0.6 + 0.6 * math.cos(a), 0.6 + 0.6 * math.sin(a)))
    for k in range(1, 6):                                     # big bullnose on the top front edge
        a = math.radians(90 * k / 5)
        prof.append((D - 1.4 + 1.4 * math.cos(a), T - 1.9 + 1.9 * math.sin(a)))
    prof += [(0.15, T), (0.0, T - 0.15)]
    # profile is ordered (front-bottom -> front-top), first points first
    bm, _, _ = prism(prof, lambda a, b, d: (a, d, b), -L / 2, L / 2)
    p = [(bevelled(bm, 0.35, 2, angle=60), "M_Timber")]
    # Ogee corbel: back post, top arm, S-curve from the arm tip down to the post foot.
    H, A = 16.0, 20.0
    cprof = [(0.0, -GAP), (A, -GAP), (A, -1.6)]
    for k in range(1, 13):
        t = k / 12.0
        x = A - (A - 2.2) * t
        s = 0.5 - 0.5 * math.cos(math.pi * t)                 # ogee: ease in/out
        z = -1.6 - (H - 1.6 - 1.2) * (0.35 * t + 0.65 * s)
        prof_x = x - 2.0 * math.sin(math.pi * t)              # belly
        cprof.append((prof_x, z))
    cprof += [(2.2, -H + 0.6), (0.0, -H)]
    cprof = list(reversed(cprof))
    for y in (-32.0, 32.0):
        cb, _, _ = prism(cprof, lambda a, b, d: (a, d, b), y - 1.1, y + 1.1)
        p.append((bevelled(cb, 0.3, 2, angle=35), "M_Timber"))
    return finalize("SM_Shelf", p)


def memory_box():
    """Keepsake box 32 x 22 x 16 (pivot bottom centre, nothing baked): moulded timber plinth band,
    body, and a fitted lid that overhangs the body 0.35 cm all round with a quarter-round edge and a
    recessed, bevelled panel field on top. Brass: corner straps on the lid skirt, a small name
    plaque in the field, keyhole escutcheon on the front, two barrel hinges with leaves at the back.
    The flat field is one face bounded by a >40 degree (sharp) bevel, so its normals stay flat."""
    L, W = 32.0, 22.0                  # plinth band footprint (outermost timber)
    R = 1.6
    BI = 0.5                           # body inset from the plinth band
    ZB1, ZL0, ZL1 = 11.4, 11.5, 16.0   # body top, lid bottom (0.1 seam), lid top
    LI = 0.15                          # lid inset from the band: overhangs the body by 0.35
    p = []
    # plinth band (bottom round, quarter-round top, ledge) and body (rounded rim) in one loft
    rings = [(0.15, 0.0, R - 0.15), (0.0, 0.15, R), (0.0, 0.55, R)]
    rings += [(o, z, R - o) for o, z in quarter(0.0, 0.55, 0.42, 1.2, 3)]
    rb = R - BI
    rings += [(BI, 1.2, rb), (BI, ZB1 - 0.2, rb)]
    rings += [(o, z, R - o) for o, z in quarter(BI, ZB1 - 0.2, BI + 0.2, ZB1, 2)]
    p.append((rr_loft(L, W, R, rings), "M_TimberDark"))
    # lid: rounded seam edge, skirt, quarter-round top edge, flat frame, bevel down into the field
    Ll, Wl, Rl = L - 2 * LI, W - 2 * LI, R - LI
    rings = [(0.15, ZL0, Rl - 0.15), (0.0, ZL0 + 0.15, Rl), (0.0, ZL1 - 1.0, Rl)]
    rings += [(o, z, Rl - o * 0.6) for o, z in quarter(0.0, ZL1 - 1.0, 0.9, ZL1, 3)]
    FI = 2.4                                                   # field inset
    rings += [(FI, ZL1, 0.75), (FI + 0.06, ZL1 - 0.07, 0.72), (FI + 0.13, ZL1 - 0.2, 0.68),
              (FI + 0.16, ZL1 - 0.25, 0.66)]
    p.append((rr_loft(Ll, Wl, Rl, rings), "M_TimberDark"))
    # brass corner straps around the lid skirt
    th = 0.15
    cx, cy = Ll / 2 - Rl, Wl / 2 - Rl
    for sx, sy, a0 in ((1, 1, 0), (-1, 1, 90), (-1, -1, 180), (1, -1, 270)):
        p.append(arc_strap(sx * cx, sy * cy, Rl, a0, a0 + 90, 2.0, ZL0 + 0.45, ZL1 - 1.15, th, "M_Brass",
                           segs=4))
    # name plaque in the recessed field
    zf = ZL1 - 0.25 + GAP
    plaque = rounded_slab(rrect(6.0, 2.5, 0.35, 2), lambda a, b, d: (a, b, d), zf, zf + 0.1, 0.0, 0, 0.05, 1)
    p.append((plaque, "M_Brass"))
    # keyhole escutcheon on the body front (room side, local -Y) just below the seam
    yfront = W / 2 - BI + GAP          # distance of the escutcheon back from the centre plane
    zk = ZB1 - 1.7
    esc = rounded_slab(rrect(1.7, 2.3, 0.8, 3), lambda a, b, d: (a, -d, zk + b), yfront, yfront + 0.12,
                       0.0, 0, 0.04, 1)
    p.append((esc, "M_Brass"))
    kh = []
    for k in range(9):                                         # keyhole: round head ...
        a = math.radians(-70 + 320 * k / 8.0)
        kh.append((0.24 * math.cos(a), 0.3 + 0.24 * math.sin(a)))
    kh += [(-0.16, -0.45), (0.16, -0.45)]                      # ... and flared slot
    keyb, _, _ = prism(kh, lambda a, b, d: (a, -d, zk + b), yfront + 0.14, yfront + 0.17)
    p.append((keyb, "M_TimberDark"))
    # barrel hinges tucked under the lid's back overhang (behind the body face, below the lid),
    # with a leaf on the body back
    yh = W / 2 - BI + GAP + 0.18
    yl = W / 2 - BI + GAP
    for x in (-9.0, 9.0):
        hb = [(0.0, -1.6), (0.18, -1.6), (0.18, 1.6), (0.0, 1.6)]
        p.append(lathe(hb, 8, "M_Brass", axis="X", loc=(x, yh, ZL0 - GAP - 0.18)))
        p.append(box(x - 1.5, x + 1.5, yl, yl + 0.08, ZB1 - 1.6, ZB1 - 0.45, "M_Brass", 0.0))
    if not MEMORYBOX_LENGTH_ON_X:
        for bmx, _ in p:
            rotate(bmx, Matrix.Rotation(math.radians(90), 3, "Z"))   # length on Y, hasp on +X
    return finalize("SM_MemoryBox", p, wn_weight=100)


# ------------------------------------------------------------------ UVs, export, preview
def uv_world_and_lightmap(ob, margin=0.02):
    me = ob.data
    while len(me.uv_layers):
        me.uv_layers.remove(me.uv_layers[0])
    uv0 = me.uv_layers.new(name="UVMap")
    bm = bmesh.new()
    bm.from_mesh(me)
    layer = bm.loops.layers.uv[uv0.name]
    if ob.name == "SM_TVScreen":
        w, h = SCR_W / 100.0, SCR_H / 100.0
        z0 = SCR_Z0 / 100.0
        for f in bm.faces:
            for loop in f.loops:
                co = loop.vert.co
                loop[layer].uv = ((co.y + w / 2) / w, (co.z - z0) / h)   # u = viewer's left -> right
    else:
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
    sc.render.film_transparent = False
    sh = sc.display.shading
    sh.light = "STUDIO"
    sh.color_type = "MATERIAL"
    sh.show_cavity = True
    sh.cavity_type = "BOTH"
    sh.show_specular_highlight = True
    sc.display.render_aa = "16"
    sc.view_settings.view_transform = "Standard"
    w = bpy.data.worlds.new("White")
    w.color = (1.0, 1.0, 1.0)
    sc.world = w
    cd = bpy.data.cameras.new("Cam")
    cd.lens = 50
    cd.sensor_fit = "HORIZONTAL"
    cd.sensor_width = 36
    cd.clip_start = 0.01
    cd.clip_end = 100
    cam = bpy.data.objects.new("Cam", cd)
    sc.collection.objects.link(cam)
    sc.camera = cam
    return cam


def render(cam, objs, path, d=(1.0, -0.8, 0.55)):
    sc = bpy.context.scene
    for o in sc.objects:
        o.hide_render = (o.type == "MESH" and o not in objs)
    bpy.context.view_layer.update()
    pts = [o.matrix_world @ Vector(c) for o in objs for c in o.bound_box]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    c = (lo + hi) / 2
    d = Vector(d).normalized()
    cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    bpy.context.view_layer.update()
    r = cam.matrix_world.to_3x3().col[0]
    u = cam.matrix_world.to_3x3().col[1]
    f = -d
    tx = math.tan(math.atan(18.0 / 50.0)) * 0.86
    ty = tx * 700.0 / 900.0
    D = max(max(abs((p - c).dot(r)) / tx, abs((p - c).dot(u)) / ty) - (p - c).dot(f) for p in pts)
    cam.location = c + d * D
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)


def flat_normal_report(ob, min_area_cm2=40.0, tol_deg=2.0):
    """Shading self-check: on every large face (> min_area), how far do the exported corner normals
    lean off the face normal? Large flat panels should be ~0 (no smeared gradients when baked)."""
    me = ob.data
    n_big, n_bad, worst = 0, 0, 0.0
    for poly in me.polygons:
        if poly.area * 1e4 < min_area_cm2:
            continue
        n_big += 1
        dev = max(math.degrees(me.corner_normals[li].vector.angle(poly.normal)) for li in poly.loop_indices)
        worst = max(worst, dev)
        n_bad += dev > tol_deg
    return f"{n_big} faces > {min_area_cm2:.0f} cm2, {n_bad} lean > {tol_deg} deg, worst {worst:.2f} deg"


def world_aabb(ob, pivot, yaw):
    """Footprint in room (Unreal cm) for a piece placed at pivot with yaw (degrees)."""
    cy, sy = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    xs, ys, zs = [], [], []
    for v in ob.data.vertices:
        x, y, z = v.co.x * 100, -v.co.y * 100, v.co.z * 100
        xs.append(pivot[0] + x * cy - y * sy)
        ys.append(pivot[1] + x * sy + y * cy)
        zs.append(pivot[2] + z)
    return f"X {min(xs):.1f}..{max(xs):.1f}  Y {min(ys):.1f}..{max(ys):.1f}  Z {min(zs):.1f}..{max(zs):.1f}"


def build():
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(PREV, exist_ok=True)
    pieces = [bedside(), wardrobe(), tv_cabinet(), tv(), tv_screen(), shelf(), memory_box()]
    by = {o.name: o for o in pieces}
    # CASEGOODS_ONLY=SM_A,SM_B limits export + previews to those pieces (default: all of them).
    only = [n.strip() for n in os.environ.get("CASEGOODS_ONLY", "").split(",") if n.strip()]
    for ob in pieces:
        uv_world_and_lightmap(ob)
        if not only or ob.name in only:
            export(ob)
    cam = setup_render()
    views = {"SM_Shelf": (1.0, -0.9, 0.25), "SM_TVScreen": (1.0, -0.5, 0.2), "SM_TV": (1.0, -0.6, 0.3),
             "SM_MemoryBox": (0.55, -1.0, 0.6)}
    for ob in pieces:
        if only and ob.name not in only:
            continue
        objs = [ob, by["SM_TVScreen"]] if ob.name == "SM_TV" else [ob]
        render(cam, objs, os.path.join(PREV, f"{ob.name}.png"), views.get(ob.name, (1.0, -0.8, 0.55)))
    if CHECK:
        os.makedirs(CHECK, exist_ok=True)
        tvs = [by["SM_TV"], by["SM_TVScreen"]]
        for o in tvs:
            o.location = (0.0, -0.02, 0.602)       # TV loc is 2 cm nearer the wall than the cabinet
        render(cam, [by["SM_TVCabinet"]] + tvs, os.path.join(CHECK, "check_tv_assembly.png"), (1.0, -0.7, 0.35))
        for o in tvs:
            o.location = (0, 0, 0)
    placements = {"SM_Bedside": ((266, 421.5, 0), -90), "SM_Wardrobe": ((34, 220, 0), 0),
                  "SM_TVCabinet": ((426, 426, 0), -90), "SM_TV": ((426, 428, 60.2), -90),
                  "SM_TVScreen": ((426, 428, 60.2), -90), "SM_Shelf": ((0.2, 365, 125), 0),
                  "SM_MemoryBox": ((14, 371, 127.7), 90)}
    for ob in pieces:
        extra = world_aabb(ob, *placements[ob.name]) if ob.name in placements else ""
        (x0, x1), (y0, y1), (z0, z1) = bounds_ue(ob)
        print(f"NORMALS {ob.name}: {flat_normal_report(ob)}")
        print(f"RESULT {ob.name}: tris={tris(ob)} mats={[m.name for m in ob.data.materials]} "
              f"size=({x1 - x0:.1f}, {y1 - y0:.1f}, {z1 - z0:.1f}) local X {x0:.2f}..{x1:.2f} "
              f"Y {y0:.2f}..{y1:.2f} Z {z0:.2f}..{z1:.2f} | placed {extra}")
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ITEMS, "casegoods.blend"))


if __name__ == "__main__":
    build()
