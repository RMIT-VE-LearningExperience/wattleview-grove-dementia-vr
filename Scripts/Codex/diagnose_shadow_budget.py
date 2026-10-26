import json
import traceback

import unreal


LIGHT_PROPERTIES = (
    "mobility",
    "intensity",
    "indirect_lighting_intensity",
    "cast_shadows",
    "cast_static_shadows",
    "cast_dynamic_shadows",
    "cast_modulated_shadows",
    "shadow_bias",
    "shadow_slope_bias",
    "shadow_resolution_scale",
    "contact_shadow_length",
    "contact_shadow_length_in_world_space_units",
    "dynamic_shadow_distance_stationary_light",
    "dynamic_shadow_distance_movable_light",
    "dynamic_shadow_cascades",
    "num_dynamic_shadow_cascades",
    "cascade_distribution_exponent",
    "cascade_transition_fraction",
    "shadow_distance_fadeout_fraction",
    "use_inset_shadows_for_movable_objects",
)

MESH_PROPERTIES = (
    "mobility",
    "cast_shadow",
    "cast_dynamic_shadow",
    "cast_static_shadow",
    "cast_contact_shadow",
    "cast_capsule_direct_shadow",
    "cast_capsule_indirect_shadow",
    "visible_in_ray_tracing",
)


def serialise(value):
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    try:
        return value.get_path_name()
    except Exception:
        return str(value)


def available_properties(obj, candidates):
    result = {}
    for property_name in candidates:
        try:
            result[property_name] = serialise(
                obj.get_editor_property(property_name)
            )
        except Exception:
            pass
    return result


def main():
    world = unreal.get_editor_subsystem(
        unreal.UnrealEditorSubsystem
    ).get_editor_world()
    if world is None:
        raise RuntimeError("No live editor world is available")

    actor_subsystem = unreal.get_editor_subsystem(
        unreal.EditorActorSubsystem
    )
    report = {
        "success": True,
        "world": world.get_path_name(),
        "lights": [],
        "maria_components": [],
        "lightmass": {},
    }

    settings = world.get_world_settings()
    lightmass = settings.get_editor_property("lightmass_settings")
    for property_name in (
        "use_ambient_occlusion",
        "direct_illumination_occlusion_fraction",
        "indirect_illumination_occlusion_fraction",
        "occlusion_exponent",
        "fully_occluded_samples_fraction",
        "max_occlusion_distance",
        "indirect_lighting_smoothness",
        "indirect_lighting_quality",
    ):
        try:
            report["lightmass"][property_name] = serialise(
                lightmass.get_editor_property(property_name)
            )
        except Exception:
            pass

    for actor in actor_subsystem.get_all_level_actors():
        label = actor.get_actor_label()

        light_component = None
        for property_name in (
            "directional_light_component",
            "sky_light_component",
            "rect_light_component",
            "point_light_component",
            "spot_light_component",
        ):
            try:
                light_component = actor.get_editor_property(property_name)
            except Exception:
                light_component = None
            if light_component is not None:
                break

        if light_component is not None:
            report["lights"].append(
                {
                    "label": label,
                    "class": actor.get_class().get_name(),
                    "properties": available_properties(
                        light_component,
                        LIGHT_PROPERTIES,
                    ),
                }
            )

        if "maria" not in label.lower():
            continue

        for component in actor.get_components_by_class(
            unreal.SkinnedMeshComponent
        ):
            report["maria_components"].append(
                {
                    "actor": label,
                    "component": component.get_name(),
                    "class": component.get_class().get_name(),
                    "properties": available_properties(
                        component,
                        MESH_PROPERTIES,
                    ),
                }
            )

    print("CODEX_SHADOW_DIAG=" + json.dumps(report, sort_keys=True))


try:
    main()
except Exception as exc:
    print(
        "CODEX_SHADOW_DIAG="
        + json.dumps(
            {
                "success": False,
                "error": str(exc),
                "traceback": traceback.format_exc(),
            },
            sort_keys=True,
        )
    )
    raise
