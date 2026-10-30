"""Read-only diagnostics for Maria's body/outfit integration."""

import json
import unreal


MAP = "/Game/Wattleview/Maps/L_ResidentRoom"


def safe(obj, prop):
    try:
        value = obj.get_editor_property(prop)
        if isinstance(value, unreal.Object):
            return value.get_path_name()
        if isinstance(value, (list, tuple)):
            return [safe_item(v) for v in value]
        return str(value)
    except Exception as exc:
        return "<unavailable: %s>" % exc


def safe_item(value):
    if isinstance(value, unreal.Object):
        return value.get_path_name()
    try:
        return str(value)
    except Exception:
        return "<?>"


unreal.EditorLoadingAndSavingUtils.load_map(MAP)
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
maria = next(a for a in actors if a.get_actor_label() == "Maria_StandIn")

out = {"actor": maria.get_path_name(), "components": []}
for comp in maria.get_components_by_class(unreal.SkeletalMeshComponent):
    mesh = comp.get_skinned_asset()
    materials = []
    if mesh:
        try:
            for i, entry in enumerate(mesh.get_editor_property("materials")):
                materials.append({
                    "index": i,
                    "slot": str(entry.get_editor_property("material_slot_name")),
                    "material": safe_item(entry.get_editor_property("material_interface")),
                })
        except Exception as exc:
            materials = ["<materials error: %s>" % exc]
    overrides = []
    try:
        overrides = [safe_item(x) for x in comp.get_editor_property("override_materials")]
    except Exception:
        pass
    info = {
        "name": comp.get_name(),
        "mesh": mesh.get_path_name() if mesh else None,
        "skeleton": safe(mesh, "skeleton") if mesh else None,
        "materials": materials,
        "overrides": overrides,
        "leader_pose_component": safe(comp, "leader_pose_component"),
        "master_pose_component": safe(comp, "master_pose_component"),
        "visibility_based_anim_tick_option": safe(comp, "visibility_based_anim_tick_option"),
        "forced_lod_model": safe(comp, "forced_lod_model"),
        "min_lod_model": safe(comp, "min_lod_model"),
    }
    try:
        info["lod_count"] = unreal.EditorSkeletalMeshLibrary.get_lod_count(mesh)
    except Exception as exc:
        info["lod_count"] = "<unavailable: %s>" % exc
    out["components"].append(info)

unreal.log_warning("[MariaGarmentInspect] " + json.dumps(out, indent=2))
