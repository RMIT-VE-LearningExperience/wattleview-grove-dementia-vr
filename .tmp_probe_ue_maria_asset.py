import json
import traceback
import unreal

PATH = "/Game/Wattleview/Characters/Garments/Maria/SKM_Maria_Outfit"


def safe(label, fn, result):
    try:
        value = fn()
        result[label] = str(value)
    except Exception as exc:
        result[label] = "ERROR: %s" % exc


try:
    mesh = unreal.load_asset(PATH)
    result = {
        "asset": mesh.get_path_name() if mesh else None,
        "class": str(mesh.get_class()) if mesh else None,
        "methods": [n for n in dir(mesh) if any(t in n.lower() for t in (
            "bound", "lod", "render", "vertex", "triangle", "section", "material", "skeleton", "import"
        ))] if mesh else [],
    }
    if mesh:
        for name in (
            "get_bounds", "get_bounding_box", "get_num_lods", "get_lod_num_vertices",
            "get_imported_bounds", "get_render_data", "get_resource_for_rendering",
            "get_materials", "get_skeleton", "get_asset_import_data",
        ):
            if hasattr(mesh, name):
                safe(name, lambda n=name: getattr(mesh, n)(), result)
        for prop in (
            "materials", "skeleton", "imported_bounds", "positive_bounds_extension",
            "negative_bounds_extension", "lod_info", "asset_import_data",
        ):
            safe("prop_" + prop, lambda p=prop: mesh.get_editor_property(p), result)

        try:
            subsystem = unreal.get_editor_subsystem(unreal.SkeletalMeshEditorSubsystem)
            result["subsystem_methods"] = [n for n in dir(subsystem) if any(t in n.lower() for t in (
                "lod", "vertex", "triangle", "section", "bound"
            ))]
            for name in result["subsystem_methods"]:
                if name.startswith("get_"):
                    try:
                        result["subsystem_" + name] = str(getattr(subsystem, name)(mesh))
                    except Exception:
                        pass
            safe("subsystem_get_lod_build_settings_0", lambda: subsystem.get_lod_build_settings(mesh, 0), result)
            section_count = subsystem.get_num_sections(mesh, 0)
            result["section_count"] = section_count
            result["sections"] = []
            for section_index in range(section_count):
                section = {"index": section_index}
                for label, function in (
                    ("material_slot", lambda si=section_index: subsystem.get_lod_material_slot(mesh, 0, si)),
                    ("cast_shadow", lambda si=section_index: subsystem.get_section_cast_shadow(mesh, 0, si)),
                    ("ray_visible", lambda si=section_index: subsystem.get_section_visible_in_ray_tracing(mesh, 0, si)),
                    ("recompute_tangent", lambda si=section_index: subsystem.get_section_recompute_tangent(mesh, 0, si)),
                ):
                    try:
                        section[label] = str(function())
                    except Exception as exc:
                        section[label] = "ERROR: %s" % exc
                result["sections"].append(section)
        except Exception as exc:
            result["subsystem_error"] = str(exc)
        try:
            library = unreal.EditorSkeletalMeshLibrary
            result["library_methods"] = [n for n in dir(library) if any(t in n.lower() for t in (
                "lod", "vertex", "triangle", "section", "mesh"
            ))]
        except Exception as exc:
            result["library_error"] = str(exc)
    unreal.log_warning("[CodexMariaAssetProbe] " + json.dumps(result, indent=2))
except Exception:
    unreal.log_error("[CodexMariaAssetProbe] " + traceback.format_exc())
