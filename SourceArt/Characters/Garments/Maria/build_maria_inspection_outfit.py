"""Build Maria's temporary inspection outfit: plain bra, skirt and shoes.

The bra is extracted from Maria's full-body surface so it follows her exact body
shape and preserves the MetaHuman skin weights.  Cardigan and blouse faces are
removed from a copy of the current outfit; the production outfit is not touched.
"""

import bmesh
import bpy
import os


ROOT = r"D:\Unreal-Projects\WattleviewGrove-ue58\SourceArt\Characters"
FULL_BODY = os.path.join(ROOT, "Bodies", "SKM_Maria_BodyMesh_Full.fbx")
CURRENT_OUTFIT = os.path.join(ROOT, "Garments", "Maria", "SKM_Maria_Outfit.fbx")
OUTPUT = os.path.join(ROOT, "Garments", "Maria", "SKM_Maria_InspectionOutfit_Blender.fbx")


def imported_objects(filepath):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=filepath)
    return [obj for obj in bpy.data.objects if obj not in before]


def world_center(obj, face):
    return obj.matrix_world @ face.calc_center_median()


def keep_bra_face(point):
    """A simple supportive crop-bra silhouette with broad shoulder straps."""
    x = abs(point.x)
    z = point.z
    band = 0.965 <= z <= 1.165 and x <= 0.215
    straps = 1.135 <= z <= 1.255 and 0.052 <= x <= 0.116
    return band or straps


bpy.ops.wm.read_factory_settings(use_empty=True)

full_objects = imported_objects(FULL_BODY)
body = next(obj for obj in full_objects if obj.type == "MESH")
body_armature = next(obj for obj in full_objects if obj.type == "ARMATURE")

# Duplicate the body surface, keeping its UVs and exact MetaHuman vertex weights.
bra = body.copy()
bra.data = body.data.copy()
bpy.context.scene.collection.objects.link(bra)
bra.name = "Maria_Inspection_Bra"
bra.data.name = "Maria_Inspection_Bra"

bm = bmesh.new()
bm.from_mesh(bra.data)
bm.faces.ensure_lookup_table()
remove_faces = [face for face in bm.faces if not keep_bra_face(world_center(bra, face))]
bmesh.ops.delete(bm, geom=remove_faces, context="FACES")
loose_vertices = [vertex for vertex in bm.verts if not vertex.link_faces]
if loose_vertices:
    bmesh.ops.delete(bm, geom=loose_vertices, context="VERTS")
bm.to_mesh(bra.data)
bm.free()
bra.data.update()

# The imported mesh is in centimetres beneath a 0.01 parent scale.  A local 0.32
# unit normal offset is therefore 3.2 mm in Unreal/world space.
for vertex in bra.data.vertices:
    vertex.co += vertex.normal * 0.32
bra.data.update()

bra.data.materials.clear()
bra_material = bpy.data.materials.new("M_Bra")
bra.data.materials.append(bra_material)
for polygon in bra.data.polygons:
    polygon.material_index = 0

outfit_objects = imported_objects(CURRENT_OUTFIT)
outfit = next(obj for obj in outfit_objects if obj.type == "MESH")
outfit_armature = next(obj for obj in outfit_objects if obj.type == "ARMATURE")

# Remove cardigan (slot 0) and blouse/collar (slot 1).  Retain skirt and shoes.
bm = bmesh.new()
bm.from_mesh(outfit.data)
bm.faces.ensure_lookup_table()
remove_faces = [face for face in bm.faces if face.material_index in {0, 1}]
bmesh.ops.delete(bm, geom=remove_faces, context="FACES")
loose_vertices = [vertex for vertex in bm.verts if not vertex.link_faces]
if loose_vertices:
    bmesh.ops.delete(bm, geom=loose_vertices, context="VERTS")
bm.to_mesh(outfit.data)
bm.free()
outfit.data.update()

bpy.context.view_layer.objects.active = outfit
outfit.select_set(True)
bpy.ops.object.material_slot_remove_unused()
outfit.select_set(False)

# Remap the bra to the canonical outfit armature.  The bone names and bind pose are
# shared; preserving matrix_world keeps the two imported FBXs exactly aligned.
bra_world = bra.matrix_world.copy()
bra.parent = outfit_armature
bra.matrix_world = bra_world
for modifier in bra.modifiers:
    if modifier.type == "ARMATURE":
        modifier.object = outfit_armature

# Join bra, skirt and shoes into a single skinned mesh.  The active outfit's armature
# modifier drives the merged vertex groups, including the copied bra weights.
bpy.ops.object.select_all(action="DESELECT")
bra.select_set(True)
outfit.select_set(True)
bpy.context.view_layer.objects.active = outfit
bpy.ops.object.join()
outfit = bpy.context.object
outfit.name = "SKM_Maria_InspectionOutfit"
outfit.data.name = "SKM_Maria_InspectionOutfit"

# Remove the now-unused full-body source hierarchy without touching the merged mesh.
for obj in full_objects:
    if obj != bra and obj.name in bpy.data.objects:
        bpy.data.objects.remove(obj, do_unlink=True)

assert [material.name for material in outfit.data.materials] == ["M_Skirt", "M_Shoes", "M_Bra"], [
    material.name for material in outfit.data.materials
]
assert len(outfit.data.polygons) > 1000

bpy.ops.object.select_all(action="DESELECT")
outfit_armature.select_set(True)
outfit.select_set(True)
bpy.context.view_layer.objects.active = outfit_armature
bpy.ops.export_scene.fbx(
    filepath=OUTPUT,
    use_selection=True,
    object_types={"ARMATURE", "MESH"},
    add_leaf_bones=False,
    primary_bone_axis="Y",
    secondary_bone_axis="X",
    armature_nodetype="NULL",
    bake_anim=False,
    use_armature_deform_only=True,
    apply_scale_options="FBX_SCALE_NONE",
    global_scale=1.0,
    apply_unit_scale=True,
    axis_forward="Y",
    axis_up="Z",
    mesh_smooth_type="FACE",
    use_mesh_modifiers=False,
    use_tspace=False,
    embed_textures=False,
    path_mode="AUTO",
)

print(
    "INSPECTION_OUTFIT",
    OUTPUT,
    "verts",
    len(outfit.data.vertices),
    "polys",
    len(outfit.data.polygons),
    "slots",
    [material.name for material in outfit.data.materials],
)
