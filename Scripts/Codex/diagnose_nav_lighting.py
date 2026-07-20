import json

import unreal


MAP_PATH = "/Game/Maps/HospitalRoom"


def vector_to_list(value):
    return [
        round(float(value.x), 3),
        round(float(value.y), 3),
        round(float(value.z), 3),
    ]


def main():
    world = unreal.EditorLoadingAndSavingUtils.load_map(MAP_PATH)
    if world is None:
        raise RuntimeError("Unable to load {}".format(MAP_PATH))

    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    report = {
        "map": world.get_path_name(),
        "world_settings": {},
        "nav_bounds": [],
        "lights": [],
        "generated_meshes": [],
        "ceiling_like_meshes": [],
    }

    world_settings = world.get_world_settings()
    if world_settings is not None:
        for property_name in (
            "force_no_precomputed_lighting",
            "lightmass_settings",
        ):
            try:
                value = world_settings.get_editor_property(property_name)
                report["world_settings"][property_name] = str(value)
            except Exception:
                pass

    for actor in actor_subsystem.get_all_level_actors():
        label = actor.get_actor_label()
        actor_class = actor.get_class().get_name()
        location = actor.get_actor_location()

        if isinstance(actor, unreal.NavMeshBoundsVolume):
            origin, extent = actor.get_actor_bounds(False)
            report["nav_bounds"].append(
                {
                    "label": label,
                    "location": vector_to_list(location),
                    "scale": vector_to_list(actor.get_actor_scale3d()),
                    "bounds_origin": vector_to_list(origin),
                    "bounds_extent": vector_to_list(extent),
                }
            )

        light_component = None
        for property_name in (
            "directional_light_component",
            "point_light_component",
            "spot_light_component",
            "sky_light_component",
            "rect_light_component",
        ):
            try:
                light_component = actor.get_editor_property(property_name)
            except Exception:
                light_component = None
            if light_component is not None:
                break

        if light_component is not None:
            light_info = {
                "label": label,
                "class": actor_class,
                "location": vector_to_list(location),
            }
            for property_name in (
                "mobility",
                "cast_shadows",
                "cast_static_shadows",
                "cast_dynamic_shadows",
                "intensity",
            ):
                try:
                    light_info[property_name] = str(
                        light_component.get_editor_property(property_name)
                    )
                except Exception:
                    pass
            report["lights"].append(light_info)

        if isinstance(actor, unreal.StaticMeshActor):
            component = actor.static_mesh_component
            mesh = component.static_mesh
            mesh_path = mesh.get_path_name() if mesh is not None else None
            can_affect_navigation = None
            for property_name in (
                "can_ever_affect_navigation",
                "b_can_ever_affect_navigation",
            ):
                try:
                    can_affect_navigation = bool(
                        component.get_editor_property(property_name)
                    )
                    break
                except Exception:
                    pass
            info = {
                "label": label,
                "mesh": mesh_path,
                "location": vector_to_list(location),
                "mobility": str(component.get_editor_property("mobility")),
                "collision_enabled": str(component.get_collision_enabled()),
                "can_ever_affect_navigation": can_affect_navigation,
                "cast_shadow": bool(component.get_editor_property("cast_shadow")),
            }
            if label.startswith(("WG_Corridor_", "WG_LargeRoom_", "WG_Sky_")):
                report["generated_meshes"].append(info)
            if (
                "ceiling" in label.lower()
                or (mesh_path is not None and "ceiling" in mesh_path.lower())
            ):
                report["ceiling_like_meshes"].append(info)

    print("CODEX_DIAGNOSTIC=" + json.dumps(report, sort_keys=True))


try:
    main()
except Exception as exc:
    print(
        "CODEX_DIAGNOSTIC="
        + json.dumps({"success": False, "error": str(exc)}, sort_keys=True)
    )
    raise
