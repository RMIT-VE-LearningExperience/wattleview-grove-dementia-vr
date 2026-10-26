"""Assemble the whole room from Export/SM_*.fbx using placement.json, then audit it.

Run headless (Blender 5.0):
  blender -b --factory-startup --python assemble_room.py -- [--render] [--save] [--out <dir>]

What it does
  1. Imports every mesh named in placement.json (missing FBX files are reported, not fatal).
  2. Places each piece at its Unreal location/yaw. rest_on pieces are dropped by raycasting
     down onto the named support under the piece's footprint, then lifted gap_cm.
  3. Checks: fit rectangles, max_x (curtains in front of the sill), min_z (ceiling fan head
     clearance), and pairwise mesh intersections between all pieces except shell-vs-shell,
     overlay (memory scene) and sky. Each intersecting triangle pair is classified as a
     PENETRATION (each triangle crosses the other's plane: a real clash) or TOUCHING (faces or
     edges resting on each other, e.g. feet on the floor: harmless, though a 0.2 cm gap is better).
  4. --render writes review images to Previews/Assembly/ (plan view plus close-ups from the
     story viewpoints); --save keeps RoomAssembly.blend for inspection.
  5. Writes Previews/Assembly/report.json.

Coordinates in the report are Unreal cm (X forward/north, Y east, Z up).
"""
import bpy
import bmesh
import json
import math
import os
import sys

from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
ROOM = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from palette import colour_for  # noqa: E402

EXPORT = os.path.join(ROOM, "Export")
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = ARGS[ARGS.index("--out") + 1] if "--out" in ARGS else os.path.join(ROOM, "Previews", "Assembly")
RENDER = "--render" in ARGS
SAVE = "--save" in ARGS
SKIP_KINDS = {"overlay", "sky"}
INFO_LABELS = {"Garden_Lawn"}      # pieces planted in the lawn are expected to touch it


def b2u(v):
    return Vector((v.x * 100.0, -v.y * 100.0, v.z * 100.0))


def u2b(x, y, z):
    return Vector((x / 100.0, -y / 100.0, z / 100.0))


def clear():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for m in list(bpy.data.meshes):
        bpy.data.meshes.remove(m)


def load_master(mesh_name):
    """Import SM_<name>.fbx and bake it into one mesh datablock in its own local space."""
    path = os.path.join(EXPORT, mesh_name + ".fbx")
    if not os.path.exists(path):
        return None
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]
    meshes = [o for o in new if o.type == "MESH"]
    bm = bmesh.new()
    mats = []
    deps = bpy.context.evaluated_depsgraph_get()
    for o in meshes:
        ev = o.evaluated_get(deps)
        me = ev.to_mesh()
        me.transform(o.matrix_world)
        offset = len(mats)
        mats.extend(s.material for s in o.material_slots)
        tmp = bmesh.new()
        tmp.from_mesh(me)
        for f in tmp.faces:
            f.material_index += offset
        me2 = bpy.data.meshes.new("tmp")
        tmp.to_mesh(me2)
        tmp.free()
        bm.from_mesh(me2)
        bpy.data.meshes.remove(me2)
        ev.to_mesh_clear()
    master = bpy.data.meshes.new(mesh_name)
    bm.to_mesh(master)
    bm.free()
    for m in mats:
        master.materials.append(m)
    for o in new:
        bpy.data.objects.remove(o, do_unlink=True)
    for m in master.materials:
        if m is not None:
            c = colour_for(m.name)
            m.diffuse_color = (c + (1.0,)) if c else (1.0, 0.0, 1.0, 1.0)
    return master


def place(obj, loc, yaw, z_override=None):
    x, y, z = loc
    if z_override is not None:
        z = z_override
    obj.matrix_world = Matrix.Translation(u2b(x, y, z)) @ Matrix.Rotation(math.radians(-yaw), 4, "Z")


def world_data(obj):
    """World-space verts (Blender metres), triangles and a BVH for an object."""
    me = obj.data
    me.calc_loop_triangles()
    mw = obj.matrix_world
    verts = [mw @ v.co for v in me.vertices]
    tris = [tuple(t.vertices) for t in me.loop_triangles]
    tree = BVHTree.FromPolygons(verts, tris, epsilon=0.0) if tris else None
    if verts:
        mn = Vector((min(v.x for v in verts), min(v.y for v in verts), min(v.z for v in verts)))
        mx = Vector((max(v.x for v in verts), max(v.y for v in verts), max(v.z for v in verts)))
    else:
        mn = mx = Vector()
    return {"verts": verts, "tris": tris, "tree": tree, "min": mn, "max": mx}


def ue_bounds(wd):
    a, b = b2u(wd["min"]), b2u(wd["max"])
    lo = [round(min(a[i], b[i]), 2) for i in range(3)]
    hi = [round(max(a[i], b[i]), 2) for i in range(3)]
    return lo, hi


def drop_onto(obj, support_wd, probe_z_cm, gap_cm):
    """Raycast down at the piece's footprint onto the support; return the new z (Unreal cm)."""
    wd = world_data(obj)
    mn, mx = wd["min"], wd["max"]
    cx, cy = (mn.x + mx.x) / 2, (mn.y + mx.y) / 2
    hx, hy = (mx.x - mn.x) * 0.35, (mx.y - mn.y) * 0.35
    pts = [(cx, cy)] + [(cx + sx * hx, cy + sy * hy) for sx in (-1, 1) for sy in (-1, 1)]
    top = None
    for px, py in pts:
        hit = support_wd["tree"].ray_cast(Vector((px, py, probe_z_cm / 100.0)), Vector((0, 0, -1)), 10.0)
        if hit[0] is not None:
            z = hit[0].z
            top = z if top is None else max(top, z)
    if top is None:
        return None, "no support surface under the footprint"
    # current lowest point relative to the object's origin
    origin_z = obj.matrix_world.translation.z
    lowest_rel = mn.z - origin_z
    new_origin_z = top + gap_cm / 100.0 - lowest_rel
    return new_origin_z * 100.0, None


def tri_normal(a, b, c):
    n = (b - a).cross(c - a)
    return n.normalized() if n.length > 1e-12 else None


def classify_pairs(wa, wb):
    pairs = wa["tree"].overlap(wb["tree"])
    pen, cop = 0, 0
    rmin = Vector((1e9,) * 3)
    rmax = Vector((-1e9,) * 3)
    eps = 0.0002   # 0.02 cm
    for i, j in pairs:
        ta = [wa["verts"][k] for k in wa["tris"][i]]
        tb = [wb["verts"][k] for k in wb["tris"][j]]
        na, nb = tri_normal(*ta), tri_normal(*tb)
        if na is None or nb is None:
            continue
        # A clash needs each triangle to strictly cross the other's plane. Faces lying on
        # each other, or an edge resting on a face (feet on the floor), only touch.
        da = [na.dot(v - ta[0]) for v in tb]
        db = [nb.dot(v - tb[0]) for v in ta]
        crosses_a = max(da) > eps and min(da) < -eps
        crosses_b = max(db) > eps and min(db) < -eps
        if not (crosses_a and crosses_b):
            cop += 1
            continue
        pen += 1
        # localise with the smaller of the two triangles
        small = ta if (ta[1] - ta[0]).cross(ta[2] - ta[0]).length < (tb[1] - tb[0]).cross(tb[2] - tb[0]).length else tb
        for v in small:
            rmin = Vector(map(min, rmin, v))
            rmax = Vector(map(max, rmax, v))
    region = None
    if pen:
        a, b = b2u(rmin), b2u(rmax)
        region = {"min": [round(min(a[i], b[i]), 1) for i in range(3)],
                  "max": [round(max(a[i], b[i]), 1) for i in range(3)]}
    return pen, cop, region


def aabb_overlap(a, b, margin=0.0001):
    return all(a["min"][i] - margin <= b["max"][i] and b["min"][i] - margin <= a["max"][i] for i in range(3))


# --------------------------------------------------------------------------- rendering
VIEWS = [
    # name, camera (Unreal cm), target (Unreal cm), lens mm
    ("david_door", (105, 40, 165), (420, 260, 90), 14),
    ("maria_seated", (333, 200, 117), (500, 200, 110), 16),
    ("corner", (80, 330, 225), (300, 140, 100), 14),
    ("bed_from_table", (430, 180, 150), (180, 400, 60), 16),
    ("window_to_door", (470, 330, 160), (100, 0, 100), 14),
    ("table_props", (330, 140, 125), (410, 200, 76), 24),
    ("curtain_sill_left", (420, 150, 150), (496, 80, 110), 20),
    ("curtain_sill_right", (420, 300, 150), (496, 370, 110), 20),
    ("bedside", (300, 360, 115), (266, 425, 70), 24),
    ("shelf_wardrobe", (150, 330, 150), (20, 330, 120), 18),
    ("door_handle", (140, 60, 120), (137, -4, 102), 30),
    ("recliner", (330, 140, 130), (285, 50, 60), 22),
    ("tv", (330, 330, 130), (426, 440, 90), 22),
    ("window_view_out", (380, 225, 140), (900, 225, 120), 18),
]


def setup_render():
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    sh = scene.display.shading
    sh.light = "STUDIO"
    sh.color_type = "MATERIAL"
    sh.show_cavity = True
    sh.cavity_type = "BOTH"
    sh.show_shadows = True
    sh.shadow_intensity = 0.4
    sh.show_object_outline = False
    scene.view_settings.view_transform = "Standard"
    world = scene.world or bpy.data.worlds.new("W")
    scene.world = world
    world.color = (1, 1, 1)
    scene.render.resolution_x = 1400
    scene.render.resolution_y = 900
    scene.render.image_settings.file_format = "PNG"
    cam_data = bpy.data.cameras.new("AsmCam")
    cam_data.clip_start = 0.02
    cam_data.clip_end = 200
    cam = bpy.data.objects.new("AsmCam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    return scene, cam


def render_views(objs_by_label):
    os.makedirs(OUT, exist_ok=True)
    scene, cam = setup_render()
    written = []
    # plan view: hide the ceiling
    hide = [objs_by_label.get(k) for k in ("Ceiling", "Cornice", "SkyDome")]
    for o in hide:
        if o:
            o.hide_render = True
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = 5.9
    cam.location = u2b(250, 225, 900)
    cam.rotation_euler = (0, 0, math.radians(-90))   # Unreal +X (north, window) at the top
    scene.render.resolution_x, scene.render.resolution_y = 1300, 1200
    scene.render.filepath = os.path.join(OUT, "plan.png")
    bpy.ops.render.render(write_still=True)
    written.append(scene.render.filepath)
    for o in hide:
        if o:
            o.hide_render = False
    sky = objs_by_label.get("SkyDome")
    cam.data.type = "PERSP"
    scene.render.resolution_x, scene.render.resolution_y = 1400, 900
    for name, c, t, lens in VIEWS:
        cam.data.lens = lens
        cam.location = u2b(*c)
        look = (u2b(*t) - cam.location).normalized()
        cam.rotation_euler = look.to_track_quat("-Z", "Y").to_euler()
        scene.render.filepath = os.path.join(OUT, name + ".png")
        bpy.ops.render.render(write_still=True)
        written.append(scene.render.filepath)
    return written


def main():
    cfg = json.load(open(os.path.join(ROOM, "placement.json")))
    gap = cfg.get("gap_cm", 0.2)
    pieces = cfg["pieces"]
    clear()
    masters, missing = {}, []
    for p in pieces:
        m = p["mesh"]
        if m in masters or m in missing:
            continue
        mm = load_master(m)
        if mm is None:
            missing.append(m)
        else:
            masters[m] = mm

    objs, data, notes = {}, {}, []
    by_label = {p["label"]: p for p in pieces}
    pending = [p for p in pieces if p["mesh"] in masters]
    placed = set()
    # place pieces whose support is placed (supports first)
    for _ in range(6):
        progress = False
        for p in list(pending):
            sup = p.get("rest_on")
            same = p.get("same_as")
            if sup and sup not in placed and sup in by_label and by_label[sup]["mesh"] in masters:
                continue
            if same and same not in placed:
                continue
            o = bpy.data.objects.new(p["label"], masters[p["mesh"]])
            bpy.context.scene.collection.objects.link(o)
            if same:
                o.matrix_world = objs[same].matrix_world.copy()
            else:
                place(o, p["loc"], p.get("yaw", 0))
                if sup:
                    if sup not in placed:
                        notes.append({"label": p["label"], "issue": f"support {sup} missing; left at loc z"})
                    else:
                        z, err = drop_onto(o, data[sup], p.get("probe_z", 200 if sup != "WindowFrame" else 150), gap)
                        if err:
                            notes.append({"label": p["label"], "issue": f"rest_on {sup}: {err}"})
                        else:
                            place(o, p["loc"], p.get("yaw", 0), z_override=z)
                            p["_z"] = round(z, 2)
            objs[p["label"]] = o
            data[p["label"]] = world_data(o)
            placed.add(p["label"])
            pending.remove(p)
            progress = True
        if not progress:
            break
    for p in pending:
        notes.append({"label": p["label"], "issue": "could not be placed (support missing)"})

    # rule checks
    checks = []
    for label, wd in data.items():
        p = by_label[label]
        lo, hi = ue_bounds(wd)
        if "fit" in p:
            x0, x1, y0, y1 = p["fit"]
            over = []
            if lo[0] < x0 - 0.05: over.append(f"x min {lo[0]} < {x0}")
            if hi[0] > x1 + 0.05: over.append(f"x max {hi[0]} > {x1}")
            if lo[1] < y0 - 0.05: over.append(f"y min {lo[1]} < {y0}")
            if hi[1] > y1 + 0.05: over.append(f"y max {hi[1]} > {y1}")
            if over:
                checks.append({"label": label, "check": "fit", "detail": "; ".join(over), "bounds": [lo, hi]})
        if "max_x" in p and hi[0] > p["max_x"] + 0.05:
            checks.append({"label": label, "check": "max_x", "detail": f"x max {hi[0]} > {p['max_x']}", "bounds": [lo, hi]})
        if "min_z" in p and lo[2] < p["min_z"] - 0.05:
            checks.append({"label": label, "check": "min_z", "detail": f"lowest point {lo[2]} < {p['min_z']}", "bounds": [lo, hi]})

    # pairwise intersections
    labels = sorted(data)
    clashes, contacts = [], []
    for i, a in enumerate(labels):
        pa = by_label[a]
        if pa["kind"] in SKIP_KINDS:
            continue
        for b in labels[i + 1:]:
            pb = by_label[b]
            if pb["kind"] in SKIP_KINDS:
                continue
            if pa["kind"] == "shell" and pb["kind"] == "shell":
                continue
            if pb.get("same_as") == a or pa.get("same_as") == b:
                continue
            wa, wb = data[a], data[b]
            if wa["tree"] is None or wb["tree"] is None or not aabb_overlap(wa, wb):
                continue
            pen, cop, region = classify_pairs(wa, wb)
            if not pen and not cop:
                continue
            rec = {"a": a, "b": b, "mesh_a": pa["mesh"], "mesh_b": pb["mesh"],
                   "penetrating_tri_pairs": pen, "touching_tri_pairs": cop, "region": region}
            if pen and not (a in INFO_LABELS or b in INFO_LABELS):
                clashes.append(rec)
            else:
                contacts.append(rec)
    clashes.sort(key=lambda r: -r["penetrating_tri_pairs"])

    report = {
        "missing_meshes": missing,
        "placement_notes": notes,
        "rule_violations": checks,
        "clashes": clashes,
        "contacts_info": contacts,
        "rest_on_z": {p["label"]: p["_z"] for p in pieces if "_z" in p},
        "bounds": {k: dict(zip(("min", "max"), ue_bounds(v))) for k, v in data.items()},
    }
    os.makedirs(OUT, exist_ok=True)
    if RENDER:
        report["renders"] = render_views(objs)
    with open(os.path.join(OUT, "report.json"), "w") as fh:
        json.dump(report, fh, indent=1)
    if SAVE:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ROOM, "RoomAssembly.blend"))
    print("ASSEMBLY " + json.dumps({"missing": missing, "clashes": len(clashes), "rule_violations": len(checks),
                                    "contacts": len(contacts), "notes": len(notes)}))
    for c in clashes[:40]:
        print("CLASH %s <-> %s: %d tri pairs, region %s" % (c["a"], c["b"], c["penetrating_tri_pairs"], c["region"]))
    for c in checks:
        print("RULE %s %s: %s" % (c["label"], c["check"], c["detail"]))
    for n in notes:
        print("NOTE %s: %s" % (n["label"], n["issue"]))


main()
