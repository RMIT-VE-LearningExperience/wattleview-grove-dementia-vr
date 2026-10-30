"""Build Maria's temporary inspection outfit containing only skirt and shoes."""

import bmesh
import bpy
import os


ROOT = r"D:\Unreal-Projects\WattleviewGrove-ue58\SourceArt\Characters\Garments\Maria"
SOURCE = os.path.join(ROOT, "SKM_Maria_Outfit.fbx")
OUTPUT = os.path.join(ROOT, "SKM_Maria_ToplessInspectionOutfit_Blender.fbx")

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=SOURCE)
outfit = next(obj for obj in bpy.data.objects if obj.type == "MESH")
armature = next(obj for obj in bpy.data.objects if obj.type == "ARMATURE")

# Slot 0 is the cardigan and slot 1 is the blouse/collar.  Remove both while
# retaining the current skirt and shoes exactly as they are.
bm = bmesh.new()
bm.from_mesh(outfit.data)
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
outfit.name = "SKM_Maria_ToplessInspectionOutfit"
outfit.data.name = "SKM_Maria_ToplessInspectionOutfit"

slots = [material.name for material in outfit.data.materials]
assert slots == ["M_Skirt", "M_Shoes"], slots

bpy.ops.object.select_all(action="DESELECT")
armature.select_set(True)
outfit.select_set(True)
bpy.context.view_layer.objects.active = armature
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

print("TOPLESS_INSPECTION_OUTFIT", OUTPUT, "slots", slots, "polys", len(outfit.data.polygons))
