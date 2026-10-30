"""Put David and Enzo in neutral full-body inspection configurations.

The production MetaHuman body and garment assets are preserved.  Complete body
exports are imported into character-specific Inspection folders and the placed
garment components are hidden, leaving the baked neutral modesty layer visible.
"""

import json
import os

import unreal


PROJECT = r"D:\Unreal-Projects\WattleviewGrove-ue58"
MAP_PATH = "/Game/Wattleview/Maps/L_ResidentRoom"
SKELETON = "/Game/MetaHumans/Common/Female/Medium/NormalWeight/Body/metahuman_base_skel"

CHARACTERS = (
    {
        "name": "David",
        "actor": "David_StandIn",
        "fbx": os.path.join(
            PROJECT, "SourceArt", "Characters", "Bodies", "SKM_David_BodyMesh_Full.fbx"
        ),
        "material": "/Game/MetaHumans/David/Body/Materials/MI_Body_Baked",
    },
    {
        "name": "Enzo",
        "actor": "Enzo_Overlay",
        "fbx": os.path.join(
            PROJECT, "SourceArt", "Characters", "Bodies", "SKM_Enzo_BodyMesh_Full.fbx"
        ),
        "material": "/Game/MetaHumans/Enzo/Body/Materials/MI_Body_Baked",
    },
)


def log(message):
    unreal.log_warning("[NeutralCharacterInspection] " + str(message))


def import_full_body(character):
    destination = f"/Game/Wattleview/Characters/Garments/{character['name']}/Inspection"
    asset_name = f"SKM_{character['name']}_BodyFull_Inspection"
    asset_path = destination + "/" + asset_name
    unreal.EditorAssetLibrary.make_directory(destination)

    existing = unreal.load_asset(asset_path)
    if isinstance(existing, unreal.SkeletalMesh):
        return existing

    try:
        settings = unreal.get_default_object(unreal.InterchangeFbxTranslatorSettings)
        settings.set_editor_property("consider_cluster_before_pose_for_mesh_bind_pose", True)
    except Exception as exc:
        log("Could not set cluster-first bind policy: " + str(exc))

    task = unreal.AssetImportTask()
    task.filename = character["fbx"]
    task.destination_path = destination
    task.destination_name = asset_name
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
    mesh = unreal.load_asset(asset_path)
    if not isinstance(mesh, unreal.SkeletalMesh):
        for imported_path in task.imported_object_paths:
            candidate = unreal.load_asset(imported_path)
            if isinstance(candidate, unreal.SkeletalMesh):
                mesh = candidate
                break
    if not isinstance(mesh, unreal.SkeletalMesh):
        raise RuntimeError("Full-body import failed for " + character["name"])
    return mesh


def assign_body_material(mesh, material_path):
    material = unreal.load_asset(material_path)
    entries = list(mesh.get_editor_property("materials"))
    if not entries:
        raise RuntimeError("Imported body has no material slots: " + mesh.get_path_name())
    for index, entry in enumerate(entries):
        entry.set_editor_property("material_interface", material)
        entries[index] = entry
    mesh.set_editor_property("materials", entries)
    unreal.EditorAssetLibrary.save_loaded_asset(mesh, False)


meshes = {}
for character in CHARACTERS:
    mesh = import_full_body(character)
    assign_body_material(mesh, character["material"])
    meshes[character["name"]] = mesh

level_editor = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
if not level_editor.load_level(MAP_PATH):
    raise RuntimeError("Could not load " + MAP_PATH)

actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
results = []
for character in CHARACTERS:
    actor = next(a for a in actors if a.get_actor_label() == character["actor"])
    components = {
        component.get_name(): component
        for component in actor.get_components_by_class(unreal.SkeletalMeshComponent)
    }
    body = components["Body"]
    face = components["Face"]
    outfit = components["SkeletalMesh"]

    body.set_skinned_asset_and_update(meshes[character["name"]])
    body.set_editor_property("override_materials", [])
    body.set_visibility(True, False)
    body.set_hidden_in_game(False)

    # Keep the garment asset attached for easy restoration, but do not render it.
    outfit.set_visibility(False, False)
    outfit.set_hidden_in_game(True)

    face.set_visibility(True, False)
    face.set_hidden_in_game(False)

    results.append(
        {
            "actor": actor.get_path_name(),
            "body": body.get_skinned_asset().get_path_name(),
            "outfit": outfit.get_skinned_asset().get_path_name(),
            "outfit_visible": outfit.is_visible(),
        }
    )

if not level_editor.save_current_level():
    raise RuntimeError("Could not save the current level")

print(json.dumps(results, indent=2))
