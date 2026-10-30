"""Build and apply four-influence copies of the MetaHuman runtime outfits.

Pico's limited mobile GPU-skinning path cannot render the assembled outfits'
7-12 influences per vertex reliably.  The desktop originals remain untouched;
this script duplicates them, keeps the four strongest normalized weights on every
vertex of every source LOD, and assigns the copies to the placed story characters.

Run with ``-EnablePlugins=GeometryScripting`` in UnrealEditor-Cmd.
"""
import unreal


MAP = "/Game/Wattleview/Maps/L_ResidentRoom"
ASSETS = {
    "Maria_StandIn": (
        "/Game/MetaHumans/MariaReference/Clothing/MariaReference_Outfits",
        "/Game/Wattleview/Characters/MobileSafe/MariaReference_Outfits_Pico",
    ),
    "David_StandIn": (
        "/Game/MetaHumans/DavidReference/Clothing/DavidReference_Outfits",
        "/Game/Wattleview/Characters/MobileSafe/DavidReference_Outfits_Pico",
    ),
}
MAX_INFLUENCES = 4


def log(message):
    unreal.log("[PicoSafeOutfits] " + str(message))


def unpack_weights(result):
    if not isinstance(result, tuple):
        return [], False
    arrays = [
        value for value in result
        if not isinstance(value, (str, bytes, bool, unreal.DynamicMesh))
        and hasattr(value, "__len__")
    ]
    flags = [value for value in result if isinstance(value, bool)]
    return (arrays[-1] if arrays else []), (flags[-1] if flags else False)


def weight_value(entry):
    return float(entry.get_editor_property("weight"))


def bone_index(entry):
    return int(entry.get_editor_property("bone_index"))


def copy_lod_with_pruned_weights(source, target, lod_index):
    asset_lib = unreal.GeometryScript_AssetUtils
    query_lib = unreal.GeometryScript_MeshQueries
    weight_lib = unreal.GeometryScript_BoneWeights

    dynamic_mesh = unreal.DynamicMesh()
    read_options = unreal.GeometryScriptCopyMeshFromAssetOptions()
    read_options.set_editor_property("apply_build_settings", True)
    read_options.set_editor_property("request_tangents", True)
    requested = unreal.GeometryScriptMeshReadLOD()
    requested.set_editor_property("lod_type", unreal.GeometryScriptLODType.SOURCE_MODEL)
    requested.set_editor_property("lod_index", lod_index)
    result = asset_lib.copy_mesh_from_skeletal_mesh(
        source, dynamic_mesh, read_options, requested
    )
    if isinstance(result, tuple) and unreal.GeometryScriptOutcomePins.FAILURE in result:
        raise RuntimeError(f"Could not read {source.get_name()} LOD{lod_index}")

    vertex_count = query_lib.get_vertex_count(dynamic_mesh)
    changed = 0
    observed_max = 0
    for vertex_id in range(vertex_count):
        entries, valid = unpack_weights(
            weight_lib.get_vertex_bone_weights(dynamic_mesh, vertex_id)
        )
        if not valid or not entries:
            raise RuntimeError(
                f"{source.get_name()} LOD{lod_index} vertex {vertex_id} has no skin weights"
            )
        weighted = sorted(
            ((bone_index(entry), weight_value(entry)) for entry in entries if weight_value(entry) > 1.0e-8),
            key=lambda item: item[1],
            reverse=True,
        )
        observed_max = max(observed_max, len(weighted))
        selected = weighted[:MAX_INFLUENCES]
        total = sum(value for _, value in selected)
        if total <= 1.0e-8:
            raise RuntimeError(
                f"{source.get_name()} LOD{lod_index} vertex {vertex_id} has zero total weight"
            )
        normalized = [
            unreal.GeometryScriptBoneWeight(bone_index=index, weight=value / total)
            for index, value in selected
        ]
        weight_lib.set_vertex_bone_weights(dynamic_mesh, vertex_id, normalized)
        if len(weighted) > MAX_INFLUENCES:
            changed += 1

    write_options = unreal.GeometryScriptCopyMeshToAssetOptions()
    write_options.set_editor_property("enable_recompute_normals", False)
    write_options.set_editor_property("enable_recompute_tangents", False)
    write_options.set_editor_property("enable_remove_degenerates", False)
    write_options.set_editor_property("use_original_vertex_order", True)
    write_options.set_editor_property("replace_materials", False)
    write_options.set_editor_property("emit_transaction", False)
    write_lod = unreal.GeometryScriptMeshWriteLOD()
    write_lod.set_editor_property("lod_index", lod_index)
    result = asset_lib.copy_mesh_to_skeletal_mesh(
        dynamic_mesh, target, write_options, write_lod
    )
    if isinstance(result, tuple) and unreal.GeometryScriptOutcomePins.FAILURE in result:
        raise RuntimeError(f"Could not write {target.get_name()} LOD{lod_index}")
    log(
        f"{target.get_name()} LOD{lod_index}: {vertex_count} vertices, "
        f"source max {observed_max}, pruned {changed} vertices to <= {MAX_INFLUENCES}"
    )


def build_assets():
    editor_assets = unreal.EditorAssetLibrary
    built = {}
    for label, (source_path, target_path) in ASSETS.items():
        source = unreal.load_asset(source_path)
        if not isinstance(source, unreal.SkeletalMesh):
            raise RuntimeError("Missing skeletal mesh " + source_path)
        if not editor_assets.does_asset_exist(target_path):
            if not editor_assets.duplicate_asset(source_path, target_path):
                raise RuntimeError("Could not duplicate " + source_path)
        target = unreal.load_asset(target_path)
        if not isinstance(target, unreal.SkeletalMesh):
            raise RuntimeError("Invalid target " + target_path)
        lod_count = unreal.get_editor_subsystem(
            unreal.SkeletalMeshEditorSubsystem
        ).get_lod_count(source)
        for lod_index in range(lod_count):
            copy_lod_with_pruned_weights(source, target, lod_index)
        editor_assets.save_loaded_asset(target, False)
        built[label] = target
    return built


def apply_to_level(built):
    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if not levels.load_level(MAP):
        raise RuntimeError("Could not load " + MAP)
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    by_label = {actor.get_actor_label(): actor for actor in actors}
    for label, mesh in built.items():
        actor = by_label.get(label)
        if actor is None:
            raise RuntimeError(label + " is not present")
        wardrobe = next(
            (component for component in actor.get_components_by_class(unreal.SkeletalMeshComponent)
             if component.get_name() == "SkeletalMesh"),
            None,
        )
        body = next(
            (component for component in actor.get_components_by_class(unreal.SkeletalMeshComponent)
             if component.get_name() == "Body"),
            None,
        )
        if wardrobe is None or body is None:
            raise RuntimeError(label + " is missing Body or SkeletalMesh")
        wardrobe.modify()
        wardrobe.set_skinned_asset_and_update(mesh)
        wardrobe.set_leader_pose_component(body, True, False)
        wardrobe.set_editor_property("disable_cloth_simulation", True)
        wardrobe.set_editor_property("allow_cloth_actors", False)
        log(f"{label}: assigned {mesh.get_path_name()} and leader-posed to Body")
    levels.save_current_level()
    log("saved " + MAP)


def main():
    built = build_assets()
    apply_to_level(built)
    log("done")


main()
