"""Sky group: T_SkyDome.jpg (tonemapped Poly Haven HDRI) + SM_SkyDome (inverted UV sphere).

Run headless:
  "C:\\Program Files\\Blender Foundation\\Blender 5.0\\blender.exe" -b --factory-startup --python sky.py

Conventions: SourceArt/Room/CONVENTIONS.md. Unreal cm -> Blender m via ue(x, y, z) = (x/100, -y/100, z/100).
Source HDRI: Poly Haven 'noon_grass' (CC0), 2k .hdr in Items/sky_src (md5 checked below).
"""
import bpy, bmesh, math, os, hashlib
from mathutils import Vector

ROOM = r"D:\Unreal-Projects\WattleviewGrove-ue58\SourceArt\Room"
HDR = os.path.join(ROOM, "Items", "sky_src", "noon_grass_2k.hdr")
HDR_MD5 = "1e0908b14d868fccc9b024f87587cee4"
EXPORT = os.path.join(ROOM, "Export")
PREVIEWS = os.path.join(ROOM, "Previews")
JPG = os.path.join(EXPORT, "T_SkyDome.jpg")
SOURCE_TXT = os.path.join(EXPORT, "T_SkyDome_SOURCE.txt")

# Tonemap: Standard view, exposure 0 -> sky median ~(0.46, 0.58, 0.86) sRGB, horizon not clipped.
VIEW_TRANSFORM = "Standard"
EXPOSURE = 0.0
GAMMA = 1.0

# Dome
RADIUS_CM = 2500.0
SEGMENTS = 48      # around
RINGS = 24         # pole to pole
# Image u that faces Unreal +X (north / the window): the right flank of the large shade-tree
# cluster (u 0.10..0.29) at the window's left, open blue sky over distant trees and lawn.
U_FACING_X = 0.32

os.makedirs(EXPORT, exist_ok=True)
os.makedirs(PREVIEWS, exist_ok=True)


def ue(x, y, z):
    return Vector((x / 100.0, -y / 100.0, z / 100.0))


# ---------------------------------------------------------------- scene reset
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

# ---------------------------------------------------------------- 1. tonemap HDRI -> LDR JPG
with open(HDR, "rb") as f:
    md5 = hashlib.md5(f.read()).hexdigest()
assert md5 == HDR_MD5, "HDR md5 mismatch: %s" % md5

hdr = bpy.data.images.load(HDR)
if tuple(hdr.size) != (2048, 1024):
    hdr.scale(2048, 1024)
scene.view_settings.view_transform = VIEW_TRANSFORM
scene.view_settings.look = "None"
scene.view_settings.exposure = EXPOSURE
scene.view_settings.gamma = GAMMA
scene.display_settings.display_device = "sRGB"
scene.render.image_settings.file_format = "JPEG"
scene.render.image_settings.color_mode = "RGB"
scene.render.image_settings.quality = 92
hdr.save_render(JPG, scene=scene)
print("Saved", JPG)

# ---------------------------------------------------------------- 2. SM_SkyDome mesh
# Unreal is left-handed (X fwd, Y right, Z up). Looking toward +X, turning right goes to +Y,
# and an equirect panorama's u increases to the right, so u = U_FACING_X + psi / 2pi with
# psi = atan2(Y_ue, X_ue). v = 0.5 + elevation / pi (image top = zenith, horizon at v 0.5).
R = RADIUS_CM
verts = []
idx = {}
south = len(verts); verts.append(ue(0, 0, -R))
for j in range(1, RINGS):
    el = -math.pi / 2 + math.pi * j / RINGS
    for i in range(SEGMENTS):
        psi = 2 * math.pi * (i / SEGMENTS - U_FACING_X)
        idx[(i, j)] = len(verts)
        verts.append(ue(R * math.cos(el) * math.cos(psi), R * math.cos(el) * math.sin(psi), R * math.sin(el)))
north = len(verts); verts.append(ue(0, 0, R))

faces, uvs = [], []   # uvs: per face list of (u, v) per corner


def vi(i, j):
    return idx[(i % SEGMENTS, j)]


def uv(i, j):
    return (i / SEGMENTS, j / RINGS)


for i in range(SEGMENTS):
    # south cap
    faces.append([south, vi(i + 1, 1), vi(i, 1)])
    uvs.append([((i + 0.5) / SEGMENTS, 0.0), uv(i + 1, 1), uv(i, 1)])
    for j in range(1, RINGS - 1):
        faces.append([vi(i, j), vi(i, j + 1), vi(i + 1, j + 1), vi(i + 1, j)])
        uvs.append([uv(i, j), uv(i, j + 1), uv(i + 1, j + 1), uv(i + 1, j)])
    # north cap
    faces.append([north, vi(i, RINGS - 1), vi(i + 1, RINGS - 1)])
    uvs.append([((i + 0.5) / SEGMENTS, 1.0), uv(i, RINGS - 1), uv(i + 1, RINGS - 1)])

me = bpy.data.meshes.new("SM_SkyDome")
me.from_pydata([tuple(v) for v in verts], [], faces)
me.update()

uv0 = me.uv_layers.new(name="UVMap")
uv1 = me.uv_layers.new(name="Lightmap")
for poly, fuv in zip(me.polygons, uvs):
    for k, li in enumerate(poly.loop_indices):
        u, v = fuv[k]
        uv0.data[li].uv = (u, v)
        # Lightmap: same non-overlapping equirect layout, inset to 2%..98%
        uv1.data[li].uv = (0.02 + 0.96 * u, 0.02 + 0.96 * v)
me.uv_layers.active_index = 0
for p in me.polygons:
    p.use_smooth = True

obj = bpy.data.objects.new("SM_SkyDome", me)
scene.collection.objects.link(obj)

# Make sure every face normal points inward (toward the pivot at the centre)
inward = sum(1 for p in me.polygons if p.normal.dot(p.center) < 0)
if inward < len(me.polygons):
    bm = bmesh.new(); bm.from_mesh(me)
    for f in bm.faces:
        if f.normal.dot(f.calc_center_median()) > 0:
            f.normal_flip()
    bm.to_mesh(me); bm.free(); me.update()
inward = sum(1 for p in me.polygons if p.normal.dot(p.center) < 0)
assert inward == len(me.polygons), "normals not all inward"

# Material slot M_Sky (image hooked up for previews; Unreal replaces it with an unlit material)
mat = bpy.data.materials.new("M_Sky")
mat.diffuse_color = (0.35, 0.55, 0.95, 1.0)
mat.use_nodes = True
nt = mat.node_tree
bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
tex = nt.nodes.new("ShaderNodeTexImage")
tex.image = bpy.data.images.load(JPG)
tex.extension = "REPEAT"
nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
nt.nodes.active = tex
obj.data.materials.append(mat)

tris = sum(len(p.vertices) - 2 for p in me.polygons)
print("SM_SkyDome: verts %d faces %d tris %d inward-normals %d/%d" %
      (len(me.vertices), len(me.polygons), tris, inward, len(me.polygons)))

# ---------------------------------------------------------------- 3. export FBX
bpy.ops.object.select_all(action="DESELECT")
obj.select_set(True)
bpy.context.view_layer.objects.active = obj
bpy.ops.export_scene.fbx(
    filepath=os.path.join(EXPORT, "SM_SkyDome.fbx"),
    use_selection=True, object_types={"MESH"},
    apply_unit_scale=True, apply_scale_options="FBX_SCALE_UNITS",
    axis_forward="-Y", axis_up="Z",
    mesh_smooth_type="FACE", add_leaf_bones=False,
    use_mesh_modifiers=True, bake_space_transform=False,
    path_mode="STRIP")
print("Exported SM_SkyDome.fbx")

# ---------------------------------------------------------------- 4. previews
scene.render.engine = "BLENDER_WORKBENCH"
scene.render.resolution_x, scene.render.resolution_y = 900, 700
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGB"
scene.render.film_transparent = False
scene.view_settings.view_transform = "Standard"
scene.view_settings.exposure = 0.0
world = bpy.data.worlds.new("W"); world.color = (1, 1, 1); scene.world = world
sh = scene.display.shading
sh.color_type = "TEXTURE"

cam_data = bpy.data.cameras.new("Cam")
cam_data.clip_start = 0.05; cam_data.clip_end = 200.0
cam = bpy.data.objects.new("Cam", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam


def look_at(cam_obj, eye, target):
    cam_obj.location = eye
    d = (target - eye).normalized()
    cam_obj.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


# a) inside, from window-viewer height, looking toward Unreal +X, flat lighting = image as-is
sh.light = "FLAT"
sh.show_backface_culling = False
cam_data.lens_unit = "FOV"; cam_data.angle = math.radians(100)
eye = ue(0, 0, 150)
look_at(cam, eye, eye + ue(100, 0, 18))
scene.render.filepath = os.path.join(PREVIEWS, "SM_SkyDome.png")
bpy.ops.render.render(write_still=True)

# b) inside, narrow window-sized view toward +X (what a resident sees through the window)
cam_data.angle = math.radians(56)  # ~ window width seen from mid-room
look_at(cam, eye, eye + ue(100, 0, 12))
scene.render.filepath = os.path.join(PREVIEWS, "SM_SkyDome_WindowView.png")
bpy.ops.render.render(write_still=True)

# c) outside 3/4, studio light, backface culling on: proves the normals face inward
sh.light = "STUDIO"
sh.show_backface_culling = True
cam_data.angle = math.radians(40)
look_at(cam, ue(-6500, -5200, 4200), ue(0, 0, 0))
scene.render.filepath = os.path.join(PREVIEWS, "SM_SkyDome_Exterior.png")
bpy.ops.render.render(write_still=True)

# ---------------------------------------------------------------- 5. source note
with open(SOURCE_TXT, "w", encoding="utf-8") as f:
    f.write("""T_SkyDome.jpg - source
HDRI id:      noon_grass  ("Noon Grass")
Author:       Greg Zaal (Poly Haven)
License:      CC0 1.0 Universal (public domain) - https://polyhaven.com/license
Page:         https://polyhaven.com/a/noon_grass
File:         https://dl.polyhaven.org/file/ph-assets/HDRIs/hdr/2k/noon_grass_2k.hdr
              (2048x1024 Radiance .hdr, md5 %s; local copy Items/sky_src/noon_grass_2k.hdr)
Location:     -26.153, 27.991 (Johannesburg, southern hemisphere; clear midday, sun near zenith)
Tonemap:      Blender 5.0 Image.save_render, view transform '%s', look None, exposure %.2f,
              gamma %.2f, display sRGB -> JPEG q92, 2048x1024 equirectangular.
Dome mapping: SM_SkyDome UV0 is equirectangular; image horizon (v=0.5) on the dome equator,
              image u=%.2f faces Unreal +X (north/window), u increases toward Unreal +Y.
Built by:     SourceArt/Room/Items/sky.py
""" % (HDR_MD5, VIEW_TRANSFORM, EXPOSURE, GAMMA, U_FACING_X))
print("DONE")
