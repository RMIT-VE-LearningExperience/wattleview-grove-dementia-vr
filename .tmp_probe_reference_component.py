import json
import traceback
import unreal


def vec(v):
    return [float(v.x), float(v.y), float(v.z)]


def component_info(component):
    mesh = component.get_skinned_asset()
    origin, extent, radius = unreal.SystemLibrary.get_component_bounds(component)
    result = {
        "name": component.get_name(),
        "mesh": mesh.get_path_name() if mesh else None,
        "visible": bool(component.is_visible()),
        "component_location": vec(component.get_world_location()),
        "bounds_origin": vec(origin),
        "bounds_extent": vec(extent),
        "bounds_radius": float(radius),
        "leader": component.get_editor_property("leader_pose_component").get_path_name()
            if component.get_editor_property("leader_pose_component") else None,
        "enable_animation": str(component.get_editor_property("enable_animation")),
    }
    for bone in ("root", "pelvis", "spine_01", "head"):
        try:
            result[bone] = vec(component.get_bone_location(bone, unreal.BoneSpaces.WORLD_SPACE))
        except Exception as exc:
            result[bone] = "ERROR: %s" % exc
    return result


try:
    unreal.EditorLoadingAndSavingUtils.load_map("/Game/Wattleview/Maps/L_ResidentRoom")
    try:
        unreal.AutomationLibrary.finish_loading_before_screenshot()
    except Exception:
        pass
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    maria = next(a for a in actors if a.get_actor_label() == "Maria_StandIn")
    components = list(maria.get_components_by_class(unreal.SkeletalMeshComponent))
    body = next(c for c in components if c.get_name() == "Body")
    outfit = next(c for c in components if c.get_name() == "SkeletalMesh")
    result = {"before": component_info(outfit), "body": component_info(body)}
    outfit.set_leader_pose_component(None)
    outfit.set_enable_animation(False)
    for component in components:
        if component != outfit:
            component.set_visibility(False, True)
    outfit.set_visibility(True, True)
    result["after_detach"] = component_info(outfit)
    try:
        outfit.refresh_bone_transforms()
        outfit.update_bounds()
        outfit.mark_render_transform_dirty()
        outfit.mark_render_dynamic_data_dirty()
        result["after_refresh"] = component_info(outfit)
    except Exception as exc:
        result["refresh_error"] = str(exc)
    unreal.log_warning("[CodexMariaReferenceProbe] " + json.dumps(result, indent=2))
except Exception:
    unreal.log_error("[CodexMariaReferenceProbe] " + traceback.format_exc())
