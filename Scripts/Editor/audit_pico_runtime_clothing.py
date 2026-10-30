"""Read-only audit of the skeletal meshes actually worn by the story characters.

This is intended to be run with UnrealEditor-Cmd.  It loads the resident-room map,
reports the body/wardrobe component relationship, and records the LOD/build settings
that determine Android GPU skinning.  It deliberately does not save any package.
"""
import unreal


MAP = "/Game/Wattleview/Maps/L_ResidentRoom"
LABELS = ("Maria_StandIn", "David_StandIn", "Enzo_Overlay")


def log(message):
    unreal.log("[PicoClothingAudit] " + str(message))


def safe_property(obj, name):
    try:
        return obj.get_editor_property(name)
    except Exception as exc:
        return f"<unavailable: {exc}>"


def component(actor, name):
    return next(
        (c for c in actor.get_components_by_class(unreal.ActorComponent)
         if c.get_name() == name),
        None,
    )


def mesh_report(mesh):
    subsystem = unreal.get_editor_subsystem(unreal.SkeletalMeshEditorSubsystem)
    count = subsystem.get_lod_count(mesh)
    log(f"  asset={mesh.get_path_name()} class={mesh.get_class().get_name()}")
    log(f"  skeleton={safe_property(mesh, 'skeleton')} lods={count} "
        f"support_ray_tracing={safe_property(mesh, 'support_ray_tracing')} "
        f"allow_cpu_access={safe_property(mesh, 'allow_cpu_access')}")
    log(f"  lod_settings={safe_property(mesh, 'lod_settings')}")
    log(f"  skin_weight_profiles={safe_property(mesh, 'skin_weight_profiles')}")
    lod_info = safe_property(mesh, "lod_info")
    if isinstance(lod_info, (list, tuple)):
        log(f"  lod_info_count={len(lod_info)}")
        for index, info in enumerate(lod_info):
            log(f"  LOD{index}: verts={subsystem.get_num_verts(mesh, index)} "
                f"sections={subsystem.get_num_sections(mesh, index)} "
                f"screen={safe_property(info, 'screen_size')} "
                f"bones_to_remove={safe_property(info, 'bones_to_remove')} "
                f"bones_to_prioritize={safe_property(info, 'bones_to_prioritize')} "
                f"reduction={safe_property(info, 'reduction_settings')} "
                f"build={safe_property(info, 'build_settings')}")
    else:
        for index in range(count):
            log(f"  LOD{index}: verts={subsystem.get_num_verts(mesh, index)} "
                f"sections={subsystem.get_num_sections(mesh, index)}")


def main():
    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if not levels.load_level(MAP):
        raise RuntimeError("Could not load " + MAP)
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    by_label = {a.get_actor_label(): a for a in actors}
    for label in LABELS:
        actor = by_label.get(label)
        if actor is None:
            log(label + ": absent")
            continue
        log(label + f": class={actor.get_class().get_path_name()}")
        body = component(actor, "Body")
        wardrobe = component(actor, "SkeletalMesh")
        lod_sync = component(actor, "LODSync")
        for role, comp in (("body", body), ("wardrobe", wardrobe)):
            if comp is None:
                log(f"  {role}: missing")
                continue
            mesh = comp.get_skinned_asset()
            leader = safe_property(comp, "leader_pose_component")
            log(f"  {role}_component={comp.get_path_name()} leader={leader} "
                f"forced_lod_model={safe_property(comp, 'forced_lod_model')} "
                f"cloth_disabled={safe_property(comp, 'disable_cloth_simulation')}")
            if isinstance(mesh, unreal.SkeletalMesh):
                mesh_report(mesh)
            else:
                log(f"  {role}_asset={mesh} class={mesh.get_class().get_name() if mesh else 'None'}")
        if lod_sync:
            log(f"  LODSync forced_lod={safe_property(lod_sync, 'forced_lod')} "
                f"min_lod={safe_property(lod_sync, 'min_lod')} "
                f"num_lods={safe_property(lod_sync, 'num_lods')} "
                f"components={safe_property(lod_sync, 'components_to_sync')} "
                f"custom_mapping={safe_property(lod_sync, 'custom_lod_mapping')}")
    for name in (
        "r.GPUSkin.UnlimitedBoneInfluences",
        "r.GPUSkin.Support16BitBoneIndex",
        "Compat.MAX_GPUSKIN_BONES",
        "r.SkinCache.CompileShaders",
    ):
        try:
            value = unreal.SystemLibrary.get_console_variable_int_value(name)
        except Exception as exc:
            value = f"<unavailable: {exc}>"
        log(f"cvar {name}={value}")
    log("done (read-only; no packages saved)")


main()
