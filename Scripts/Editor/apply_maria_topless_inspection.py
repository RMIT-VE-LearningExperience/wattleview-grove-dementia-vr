"""Put Maria in the temporary topless diagnostic configuration.

Uses the existing full-body MetaHuman export and a skirt/shoes-only copy of the
current outfit.  Production body, face and outfit assets are not overwritten.
"""

import json
import os

import unreal


PROJECT = r"D:\Unreal-Projects\WattleviewGrove-ue58"
DEST = "/Game/Wattleview/Characters/Garments/Maria/Inspection"
SKELETON = "/Game/MetaHumans/Common/Female/Medium/NormalWeight/Body/metahuman_base_skel"
FULL_BODY_FBX = os.path.join(
    PROJECT, "SourceArt", "Characters", "Bodies", "SKM_Maria_BodyMesh_Full.fbx"
)
OUTFIT_FBX = os.path.join(
    PROJECT,
    "SourceArt",
    "Characters",
    "Garments",
    "Maria",
    "SKM_Maria_ToplessInspectionOutfit.fbx",
)

BODY_ASSET = DEST + "/SKM_Maria_BodyFull_Inspection"
OUTFIT_ASSET = DEST + "/SKM_Maria_ToplessInspectionOutfit"
FACE_MATERIAL = DEST + "/MI_Maria_FaceSkin_Inspection"


def log(message):
    unreal.log_warning("[MariaToplessInspection] " + str(message))


def import_skeletal_mesh(filename, destination_name):
    try:
        settings = unreal.get_default_object(unreal.InterchangeFbxTranslatorSettings)
        settings.set_editor_property("consider_cluster_before_pose_for_mesh_bind_pose", True)
    except Exception as exc:
        log("Could not set cluster-first bind policy: " + str(exc))

    task = unreal.AssetImportTask()
    task.filename = filename
    task.destination_path = DEST
    task.destination_name = destination_name
    task.automated = True
    task.replace_existing = True
    task.save = False

    options = unreal.FbxImportUI()
    options.import_mesh = True
    options.import_as_skeletal = True
    options.mesh_type_to_import = unreal.FBXImportType.FBXIT_SKELETAL_MESH
    options.import_materials = False
    options.import_textures = False
    options.import_animations = False
    options.create_physics_asset = False
    options.skeleton = unreal.load_asset(SKELETON)

    data = options.skeletal_mesh_import_data
    for prop, value in (
        ("import_morph_targets", False),
        ("update_skeleton_reference_pose", False),
        ("use_t0_as_ref_pose", False),
        ("convert_scene_unit", False),
        ("import_meshes_in_bone_hierarchy", True),
    ):
        try:
            data.set_editor_property(prop, value)
        except Exception:
            pass

    task.options = options
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    expected = DEST + "/" + destination_name
    mesh = unreal.load_asset(expected)
    if not isinstance(mesh, unreal.SkeletalMesh):
        for path in task.imported_object_paths:
            candidate = unreal.load_asset(path)
            if isinstance(candidate, unreal.SkeletalMesh):
                mesh = candidate
                break
    if not isinstance(mesh, unreal.SkeletalMesh):
        raise RuntimeError("Skeletal mesh import failed for " + filename)
    return mesh


def set_mesh_materials(mesh, mapping):
    entries = list(mesh.get_editor_property("materials"))
    assigned = {}
    for index, entry in enumerate(entries):
        slot = str(entry.get_editor_property("material_slot_name")).split(".")[0]
        material_path = mapping.get(slot)
        if material_path is None and len(entries) == 1:
            material_path = next(iter(mapping.values()))
        if material_path:
            material = unreal.load_asset(material_path)
            entry.set_editor_property("material_interface", material)
            entries[index] = entry
            assigned[slot] = material_path
    mesh.set_editor_property("materials", entries)
    unreal.EditorAssetLibrary.save_loaded_asset(mesh, False)
    return assigned


def inspection_face_material():
    if not unreal.EditorAssetLibrary.does_asset_exist(FACE_MATERIAL):
        unreal.EditorAssetLibrary.duplicate_asset(
            "/Game/MetaHumans/Maria/Face/Materials/MI_Face_Skin_Baked_LOD3",
            FACE_MATERIAL,
        )
    material = unreal.load_asset(FACE_MATERIAL)
    material.set_editor_property(
        "parent",
        unreal.load_asset(
            "/Game/MetaHumans/Common/Lookdev_UHM/Skin/Materials/Baked/MI_Head_Baked_LOD2"
        ),
    )
    unreal.MaterialEditingLibrary.update_material_instance(material)
    unreal.EditorAssetLibrary.save_loaded_asset(material, False)
    return material


unreal.EditorAssetLibrary.make_directory(DEST)
body_mesh = unreal.load_asset(BODY_ASSET)
if not isinstance(body_mesh, unreal.SkeletalMesh):
    body_mesh = import_skeletal_mesh(FULL_BODY_FBX, "SKM_Maria_BodyFull_Inspection")
outfit_mesh = unreal.load_asset(OUTFIT_ASSET)
if not isinstance(outfit_mesh, unreal.SkeletalMesh):
    outfit_mesh = import_skeletal_mesh(
        OUTFIT_FBX, "SKM_Maria_ToplessInspectionOutfit"
    )

body_materials = set_mesh_materials(
    body_mesh,
    {"MI_Body_Baked": "/Game/MetaHumans/Maria/Body/Materials/MI_Body_Baked"},
)
outfit_materials = set_mesh_materials(
    outfit_mesh,
    {
        "M_Skirt": "/Game/Wattleview/Characters/Garments/Materials/MI_Garment_Skirt",
        "M_Shoes": "/Game/Wattleview/Characters/Garments/Materials/MI_Garment_Shoes",
    },
)

level_editor = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
if not level_editor.load_level("/Game/Wattleview/Maps/L_ResidentRoom"):
    raise RuntimeError("Could not load L_ResidentRoom")

actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
maria = next(actor for actor in actors if actor.get_actor_label() == "Maria_StandIn")
components = maria.get_components_by_class(unreal.SkeletalMeshComponent)
body_component = next(component for component in components if component.get_name() == "Body")
face_component = next(component for component in components if component.get_name() == "Face")
outfit_component = next(
    component for component in components if component.get_name() == "SkeletalMesh"
)

body_component.set_skinned_asset_and_update(body_mesh)
outfit_component.set_skinned_asset_and_update(outfit_mesh)
body_component.set_editor_property("override_materials", [])
outfit_component.set_editor_property("override_materials", [])

# The production face material deliberately sinks its shoulder skirt beneath the
# cardigan.  Reparent a duplicate to the original MetaHuman head material so the
# neck/shoulder surface remains visible in this diagnostic configuration.
face_skin = inspection_face_material()
face_component.set_material(6, face_skin)
face_component.set_material(7, face_skin)

if not level_editor.save_current_level():
    raise RuntimeError("Could not save the current level")

print(
    json.dumps(
        {
            "actor": maria.get_path_name(),
            "body": body_mesh.get_path_name(),
            "outfit": outfit_mesh.get_path_name(),
            "face_material": face_skin.get_path_name(),
            "body_materials": body_materials,
            "outfit_materials": outfit_materials,
        },
        indent=2,
    )
)
