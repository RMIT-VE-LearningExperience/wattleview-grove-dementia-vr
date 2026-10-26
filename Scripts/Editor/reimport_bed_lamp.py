"""Reimport selected corrected resident-room FBXs.

Run from UnrealEditor-Cmd while the interactive editor is closed.  Importing an FBX
directly inside an UnrealMCPython request can re-enter Interchange's task queue, so this
small startup script keeps the operation on Unreal's normal command-line import path.

Set WG_REIMPORT_ASSETS to a comma-separated list to override the default bed/lamp pair,
for example ``WG_REIMPORT_ASSETS=SM_Armchair``.
"""
import json
import os

import unreal


PROJECT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
SOURCE = os.path.join(PROJECT, "SourceArt", "Room", "Export")
DESTINATION = "/Game/Wattleview/Environment/Meshes/Room"
MATERIALS = "/Game/Wattleview/Environment/Materials"

ASSET_RESOLUTIONS = {
    "SM_BedLinen": 256,
    "SM_FloorLamp": 64,
    "SM_Armchair": 128,
    "SM_Recliner": 256,
}

requested = os.environ.get("WG_REIMPORT_ASSETS", "SM_BedLinen,SM_FloorLamp")
ASSETS = {}
for requested_name in (item.strip() for item in requested.split(",")):
    if not requested_name:
        continue
    if requested_name not in ASSET_RESOLUTIONS:
        raise RuntimeError(f"Unsupported targeted room mesh: {requested_name}")
    ASSETS[requested_name] = ASSET_RESOLUTIONS[requested_name]


def material_for_slot(slot):
    stem = slot[2:] if slot.startswith("M_") else slot
    return unreal.load_asset(f"{MATERIALS}/MI_{stem}")


def reimport(name, lightmap_resolution):
    filename = os.path.join(SOURCE, name + ".fbx")
    if not os.path.isfile(filename):
        raise RuntimeError(f"Missing source FBX: {filename}")

    task = unreal.AssetImportTask()
    task.filename = filename
    task.destination_path = DESTINATION
    task.destination_name = name
    task.automated = True
    task.replace_existing = True
    task.save = False

    options = unreal.FbxImportUI()
    options.import_mesh = True
    options.import_as_skeletal = False
    options.import_materials = False
    options.import_textures = False
    options.import_animations = False
    try:
        options.set_editor_property("automated_import_should_detect_type", False)
        options.set_editor_property("mesh_type_to_import", unreal.FBXImportType.FBXIT_STATIC_MESH)
    except Exception:
        pass

    mesh_options = options.static_mesh_import_data
    mesh_options.combine_meshes = True
    mesh_options.generate_lightmap_u_vs = False
    mesh_options.auto_generate_collision = False
    mesh_options.remove_degenerates = True
    mesh_options.normal_import_method = unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS
    try:
        mesh_options.set_editor_property("build_nanite", False)
    except Exception:
        pass

    task.options = options
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])

    mesh = unreal.load_asset(f"{DESTINATION}/{name}")
    if not isinstance(mesh, unreal.StaticMesh):
        raise RuntimeError(f"Import did not produce a StaticMesh for {name}")

    static_meshes = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    uv_channels = static_meshes.get_num_uv_channels(mesh, 0)
    mesh.set_editor_property("light_map_coordinate_index", 1 if uv_channels > 1 else 0)
    mesh.set_editor_property("light_map_resolution", lightmap_resolution)
    try:
        nanite = mesh.get_editor_property("nanite_settings")
        nanite.set_editor_property("enabled", False)
        mesh.set_editor_property("nanite_settings", nanite)
    except Exception:
        pass

    slots = []
    for index, static_material in enumerate(mesh.get_editor_property("static_materials")):
        slot = str(static_material.get_editor_property("material_slot_name")).split(".")[0]
        slots.append(slot)
        material = material_for_slot(slot)
        if material is None:
            raise RuntimeError(f"Missing material instance for slot {slot} on {name}")
        mesh.set_material(index, material)

    unreal.EditorAssetLibrary.save_loaded_asset(mesh, False)
    bounds = mesh.get_bounding_box()
    return {
        "name": name,
        "uv_channels": uv_channels,
        "slots": slots,
        "bounds_min": [bounds.min.x, bounds.min.y, bounds.min.z],
        "bounds_max": [bounds.max.x, bounds.max.y, bounds.max.z],
    }


def main():
    report = []
    for asset_name, resolution in ASSETS.items():
        report.append(reimport(asset_name, resolution))
        unreal.SystemLibrary.collect_garbage()
    unreal.log_warning("[BedLampReimport] " + json.dumps(report))


main()
