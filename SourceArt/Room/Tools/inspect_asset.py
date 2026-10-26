"""Inspect one exported SM_*.fbx: measurements, mesh checks and a six-view contact sheet.

Run headless (Blender 5.0):
  blender -b --factory-startup --python inspect_asset.py -- <path/to/SM_Name.fbx> [out_dir]

Writes <out_dir>/<SM_Name>.json and <out_dir>/<SM_Name>_sheet.png (default out_dir is
SourceArt/Room/Previews/Inspect). All measurements are reported in Unreal centimetres and
Unreal axes (X forward, Y right, Z up), converted from Blender with ue = (x, -y, z) * 100.

Checks:
  triangles, bounds/size, pivot position relative to the bounds, UV layer names, material
  slots, non-manifold/boundary edges, loose geometry, degenerate faces, intersecting PARTS
  (separate mesh islands whose triangles pass through each other), and how much of the
  'Lightmap' UV layer overlaps itself or leaves 0..1.
"""
import bpy
import bmesh
import json
import math
import os
import sys

import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from palette import colour_for  # noqa: E402
ROOM = os.path.dirname(HERE)


def ue(v):
    return [round(v.x * 100, 2), round(-v.y * 100, 2), round(v.z * 100, 2)]


def args():
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if not a:
        raise SystemExit("usage: -- <fbx> [out_dir]")
    out = a[1] if len(a) > 1 else os.path.join(ROOM, "Previews", "Inspect")
    os.makedirs(out, exist_ok=True)
    return a[0], out


def clear():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for m in list(bpy.data.meshes):
        bpy.data.meshes.remove(m)


def import_fbx(path):
    bpy.ops.import_scene.fbx(filepath=path)
    objs = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    if not objs:
        raise SystemExit("no mesh in " + path)
    return objs


def world_bmesh(objs):
    """One bmesh in world space holding every mesh object, plus per-face material names."""
    bm = bmesh.new()
    mats = []
    deps = bpy.context.evaluated_depsgraph_get()
    for o in objs:
        ev = o.evaluated_get(deps)
        me = ev.to_mesh()
        me.transform(o.matrix_world)
        names = [s.material.name if s.material else "<none>" for s in o.material_slots]
        offset = len(mats)
        mats.extend(names)
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
    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    return bm, mats


def islands(bm):
    """Connected components by shared vertices. Returns face index -> island id."""
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
    roots = {}
    face_island = []
    for f in bm.faces:
        r = find(f.verts[0].index)
        face_island.append(roots.setdefault(r, len(roots)))
    return face_island, len(roots)


def part_intersections(bm, face_island):
    """Triangle pairs from DIFFERENT islands that intersect, grouped by island pair."""
    tris = bm.calc_loop_triangles()
    verts = [v.co.copy() for v in bm.verts]
    polys = [[l.vert.index for l in t] for t in tris]
    tri_face = [t[0].face.index for t in tris]
    if not polys:
        return []
    tree = BVHTree.FromPolygons(verts, polys, epsilon=0.0)
    pairs = tree.overlap(tree)
    groups = {}
    for i, j in pairs:
        if i >= j:
            continue
        ia, ib = face_island[tri_face[i]], face_island[tri_face[j]]
        if ia == ib:
            continue
        key = (min(ia, ib), max(ia, ib))
        g = groups.setdefault(key, {"count": 0, "min": Vector((1e9,) * 3), "max": Vector((-1e9,) * 3)})
        g["count"] += 1
        for idx in polys[i] + polys[j]:
            c = verts[idx]
            g["min"] = Vector(map(min, g["min"], c))
            g["max"] = Vector(map(max, g["max"], c))
    # island bounding boxes for context
    ib_min, ib_max = {}, {}
    for f in bm.faces:
        k = face_island[f.index]
        for v in f.verts:
            ib_min[k] = Vector(map(min, ib_min.get(k, Vector((1e9,) * 3)), v.co))
            ib_max[k] = Vector(map(max, ib_max.get(k, Vector((-1e9,) * 3)), v.co))
    out = []
    for (a, b), g in sorted(groups.items(), key=lambda kv: -kv[1]["count"]):
        sa = [round(x * 100, 1) for x in (ib_max[a] - ib_min[a])]
        sb = [round(x * 100, 1) for x in (ib_max[b] - ib_min[b])]
        out.append({"islands": [a, b], "island_sizes_cm": [sa, sb], "tri_pairs": g["count"],
                    "region_min": ue(g["min"]), "region_max": ue(g["max"])})
    return out[:25]


def uv_overlap(bm, layer_name, res=512):
    """Fraction of covered lightmap texels hit by more than one face island, and out-of-range UVs."""
    uv = bm.loops.layers.uv.get(layer_name)
    if uv is None:
        return None
    face_island, _ = islands(bm)
    owner = np.full((res, res), -1, dtype=np.int64)
    multi = np.zeros((res, res), dtype=bool)
    out_of_range = 0
    total_loops = 0
    for t in bm.calc_loop_triangles():
        pts = []
        for l in t:
            u, v = l[uv].uv
            total_loops += 1
            if u < -1e-4 or u > 1.0001 or v < -1e-4 or v > 1.0001:
                out_of_range += 1
            pts.append((u * res, v * res))
        (x0, y0), (x1, y1), (x2, y2) = pts
        minx, maxx = int(max(0, math.floor(min(x0, x1, x2)))), int(min(res - 1, math.ceil(max(x0, x1, x2))))
        miny, maxy = int(max(0, math.floor(min(y0, y1, y2)))), int(min(res - 1, math.ceil(max(y0, y1, y2))))
        if maxx < minx or maxy < miny:
            continue
        xs, ys = np.meshgrid(np.arange(minx, maxx + 1) + 0.5, np.arange(miny, maxy + 1) + 0.5)
        d = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
        if abs(d) < 1e-12:
            continue
        a = ((y1 - y2) * (xs - x2) + (x2 - x1) * (ys - y2)) / d
        b = ((y2 - y0) * (xs - x2) + (x0 - x2) * (ys - y2)) / d
        c = 1 - a - b
        inside = (a > 0.02) & (b > 0.02) & (c > 0.02)   # shrink slightly: shared edges are fine
        if not inside.any():
            continue
        isl = face_island[t[0].face.index]
        sub = owner[miny:maxy + 1, minx:maxx + 1]
        clash = inside & (sub >= 0) & (sub != isl)
        multi[miny:maxy + 1, minx:maxx + 1] |= clash
        sub[inside & (sub < 0)] = isl
    covered = int((owner >= 0).sum())
    return {"coverage": round(covered / float(res * res), 3),
            "overlap_fraction": round(float(multi.sum()) / max(1, covered), 4),
            "out_of_range_loops": out_of_range, "loops": total_loops}


def mesh_checks(bm):
    non_manifold = sum(1 for e in bm.edges if not e.is_manifold and not e.is_boundary)
    boundary = sum(1 for e in bm.edges if e.is_boundary)
    loose_v = sum(1 for v in bm.verts if not v.link_edges)
    loose_e = sum(1 for e in bm.edges if not e.link_faces)
    degenerate = sum(1 for f in bm.faces if f.calc_area() < 1e-10)
    return {"non_manifold_edges": non_manifold, "boundary_edges": boundary,
            "loose_verts": loose_v, "loose_edges": loose_e, "degenerate_faces": degenerate}


# --------------------------------------------------------------------------- rendering
def setup_render(objs, out_png_dir, name):
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    sh = scene.display.shading
    sh.light = "STUDIO"
    sh.color_type = "MATERIAL"
    sh.show_cavity = True
    sh.cavity_type = "BOTH"
    sh.show_object_outline = True
    sh.show_shadows = True
    sh.shadow_intensity = 0.35
    scene.render.film_transparent = False
    world = scene.world or bpy.data.worlds.new("W")
    scene.world = world
    world.color = (1, 1, 1)
    sh.background_type = "WORLD" if hasattr(sh, "background_type") else sh.background_type
    scene.render.resolution_x = 700
    scene.render.resolution_y = 700
    scene.render.image_settings.file_format = "PNG"
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    # FBX import puts the colour on the Principled node; Workbench MATERIAL mode reads the
    # material's viewport colour, so copy it across.
    for o in objs:
        for slot in o.material_slots:
            m = slot.material
            if not m:
                continue
            pal = colour_for(m.name)
            # Unknown slot names render magenta so they stand out in review.
            col = (pal + (1.0,)) if pal else (1.0, 0.0, 1.0, 1.0)
            if col:
                m.diffuse_color = col

    mn = Vector((1e9,) * 3)
    mx = Vector((-1e9,) * 3)
    for o in objs:
        for c in o.bound_box:
            w = o.matrix_world @ Vector(c)
            mn = Vector(map(min, mn, w))
            mx = Vector(map(max, mx, w))
    centre = (mn + mx) / 2
    radius = max((mx - mn).length / 2, 0.02)

    cam_data = bpy.data.cameras.new("InspectCam")
    cam_data.lens = 50
    cam = bpy.data.objects.new("InspectCam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    cam_data.clip_start = radius * 0.01
    cam_data.clip_end = radius * 100

    # Blender directions for Unreal views: UE +X == Blender +X (front), UE +Y == Blender -Y.
    views = [
        ("front", Vector((1, 0, 0.08))),
        ("three_quarter", Vector((1, 0.9, 0.55))),
        ("side", Vector((0, -1, 0.08))),
        ("back_three_quarter", Vector((-1, -0.9, 0.45))),
        ("top", Vector((0.001, 0.0, 1))),
        ("front_left_low", Vector((0.85, -0.75, 0.12))),
    ]
    paths = []
    for tag, d in views:
        d = d.normalized()
        dist = radius / math.tan(cam_data.angle / 2) * 1.12
        cam.location = centre + d * dist
        look = (centre - cam.location).normalized()
        cam.rotation_euler = look.to_track_quat("-Z", "Y").to_euler()
        p = os.path.join(out_png_dir, f"{name}_{tag}.png")
        scene.render.filepath = p
        bpy.ops.render.render(write_still=True)
        paths.append(p)
    return paths


def contact_sheet(paths, out_path, cols=3):
    imgs = [bpy.data.images.load(p) for p in paths]
    w, h = imgs[0].size
    rows = math.ceil(len(imgs) / cols)
    sheet = np.ones((rows * h, cols * w, 4), dtype=np.float32)
    for k, im in enumerate(imgs):
        px = np.array(im.pixels[:], dtype=np.float32).reshape(h, w, 4)
        r, c = divmod(k, cols)
        # Blender pixel rows start at the bottom; place row 0 at the top of the sheet.
        y0 = (rows - 1 - r) * h
        sheet[y0:y0 + h, c * w:(c + 1) * w] = px
    out = bpy.data.images.new("sheet", cols * w, rows * h, alpha=True)
    out.pixels = sheet.ravel()
    out.filepath_raw = out_path
    out.file_format = "PNG"
    out.save()
    for p in paths:
        try:
            os.remove(p)
        except OSError:
            pass


def main():
    fbx, out_dir = args()
    name = os.path.splitext(os.path.basename(fbx))[0]
    clear()
    objs = import_fbx(fbx)
    bm, mat_names = world_bmesh(objs)
    tris = sum(len(f.verts) - 2 for f in bm.faces)
    mn = Vector((1e9,) * 3)
    mx = Vector((-1e9,) * 3)
    for v in bm.verts:
        mn = Vector(map(min, mn, v.co))
        mx = Vector(map(max, mx, v.co))
    a, b = ue(mn), ue(mx)
    lo = [min(a[i], b[i]) for i in range(3)]
    hi = [max(a[i], b[i]) for i in range(3)]
    size = [round(hi[i] - lo[i], 2) for i in range(3)]
    centre = [round((hi[i] + lo[i]) / 2, 2) for i in range(3)]
    face_island, n_islands = islands(bm)
    uv_layers = sorted({l.name for o in objs for l in o.data.uv_layers})
    used_mats = sorted({mat_names[f.material_index] for f in bm.faces if f.material_index < len(mat_names)})
    report = {
        "name": name,
        "objects": [o.name for o in objs],
        "triangles": tris,
        "vertices": len(bm.verts),
        "islands": n_islands,
        "bounds_min_ue": lo, "bounds_max_ue": hi, "size_ue": size,
        "pivot_offset_from_bottom_centre": [centre[0], centre[1], lo[2]],
        "pivot_offset_from_centre": centre,
        "uv_layers": uv_layers,
        "material_slots": sorted(set(mat_names)),
        "materials_used": used_mats,
        "mesh": mesh_checks(bm),
        "intersecting_parts": part_intersections(bm, face_island),
        "lightmap_uv": uv_overlap(bm, "Lightmap"),
    }
    paths = setup_render(objs, out_dir, name)
    sheet = os.path.join(out_dir, f"{name}_sheet.png")
    contact_sheet(paths, sheet)
    report["sheet"] = sheet
    report["sheet_views"] = "row1: front(+X), three-quarter, side(from -Y in Unreal); row2: back three-quarter, top, front-left low"
    with open(os.path.join(out_dir, f"{name}.json"), "w") as fh:
        json.dump(report, fh, indent=1)
    print("INSPECT " + json.dumps({k: report[k] for k in ("name", "triangles", "size_ue", "uv_layers", "materials_used")}))
    print("INSPECT_PARTS %d intersecting island pairs" % len(report["intersecting_parts"]))
    bm.free()


main()
