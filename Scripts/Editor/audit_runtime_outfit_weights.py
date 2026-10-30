"""Read-only skin-weight audit using Geometry Script source LOD data."""
import unreal


ASSETS = (
    "/Game/MetaHumans/MariaReference/Clothing/MariaReference_Outfits",
    "/Game/MetaHumans/DavidReference/Clothing/DavidReference_Outfits",
    "/Game/Wattleview/Characters/MobileSafe/MariaReference_Outfits_Pico",
    "/Game/Wattleview/Characters/MobileSafe/DavidReference_Outfits_Pico",
)


def log(message):
    unreal.log("[PicoWeightAudit] " + str(message))


def unpack_weights(result):
    """Handle Python's tuple form for a function with return + output parameters."""
    if not isinstance(result, tuple):
        return [], False
    arrays = [
        value for value in result
        if not isinstance(value, (str, bytes, bool, unreal.DynamicMesh))
        and hasattr(value, "__len__")
    ]
    flags = [value for value in result if isinstance(value, bool)]
    return (arrays[-1] if arrays else []), (flags[-1] if flags else False)


def main():
    asset_lib = unreal.GeometryScript_AssetUtils
    query_lib = unreal.GeometryScript_MeshQueries
    weight_lib = unreal.GeometryScript_BoneWeights
    options = unreal.GeometryScriptCopyMeshFromAssetOptions()
    options.set_editor_property("apply_build_settings", True)
    for path in ASSETS:
        mesh = unreal.load_asset(path)
        log(path)
        for lod_index in range(4):
            dynamic_mesh = unreal.DynamicMesh()
            requested = unreal.GeometryScriptMeshReadLOD()
            requested.set_editor_property("lod_type", unreal.GeometryScriptLODType.SOURCE_MODEL)
            requested.set_editor_property("lod_index", lod_index)
            result = asset_lib.copy_mesh_from_skeletal_mesh(mesh, dynamic_mesh, options, requested)
            outcome = next((value for value in result if isinstance(value, unreal.GeometryScriptOutcomePins)), None) \
                if isinstance(result, tuple) else None
            vertex_count = query_lib.get_vertex_count(dynamic_mesh)
            # Skeletal source LODs copied by Geometry Script are dense.  Unreal's
            # Python name mangling for the C++ acronym-based GetNumVertexIDs varies
            # by engine build, so the dense vertex count is also the ID upper bound.
            num_ids = vertex_count
            maximum = 0
            zero = 0
            invalid = 0
            non_normalized = 0
            histogram = {}
            for vertex_id in range(num_ids):
                weights, valid = unpack_weights(
                    weight_lib.get_vertex_bone_weights(dynamic_mesh, vertex_id)
                )
                if not valid:
                    invalid += 1
                    continue
                positive = []
                for entry in weights:
                    try:
                        value = float(entry.get_editor_property("weight"))
                    except Exception:
                        value = float(getattr(entry, "weight", 0.0))
                    if value > 1.0e-6:
                        positive.append(value)
                count = len(positive)
                histogram[count] = histogram.get(count, 0) + 1
                maximum = max(maximum, count)
                if count == 0:
                    zero += 1
                elif abs(sum(positive) - 1.0) > 1.0e-3:
                    non_normalized += 1
            log(f"  LOD{lod_index}: outcome={outcome} vertices={vertex_count} "
                f"max_influences={maximum} zero={zero} invalid={invalid} "
                f"non_normalized={non_normalized} histogram={histogram}")
    log("done (read-only)")


main()
