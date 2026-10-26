import json
import traceback

import unreal


EXPECTED_WORLD = "HospitalRoom"
LIGHT_SETTINGS = {
    "WG_Corridor_Fill": {
        "class": "RectLight",
        "intensity": 350.0,
        "indirect_lighting_intensity": 0.6,
    },
    "WG_LargeRoom_Fill_West": {
        "class": "RectLight",
        "intensity": 450.0,
        "indirect_lighting_intensity": 0.6,
    },
    "WG_LargeRoom_Fill_East": {
        "class": "RectLight",
        "intensity": 450.0,
        "indirect_lighting_intensity": 0.6,
    },
    "WG_LargeRoom_WindowFill": {
        "class": "SpotLight",
        "intensity": 400.0,
        "indirect_lighting_intensity": 0.7,
    },
}


def component_for(actor):
    if isinstance(actor, unreal.RectLight):
        return actor.rect_light_component
    if isinstance(actor, unreal.SpotLight):
        return actor.spot_light_component
    raise RuntimeError(
        "{} has unexpected class {}".format(
            actor.get_actor_label(),
            actor.get_class().get_name(),
        )
    )


def run():
    world = unreal.get_editor_subsystem(
        unreal.UnrealEditorSubsystem
    ).get_editor_world()
    if world is None or world.get_name() != EXPECTED_WORLD:
        raise RuntimeError(
            "Expected current world {}, found {}".format(
                EXPECTED_WORLD,
                world.get_name() if world else "<none>",
            )
        )

    actor_subsystem = unreal.get_editor_subsystem(
        unreal.EditorActorSubsystem
    )
    by_label = {}
    for actor in actor_subsystem.get_all_level_actors():
        label = actor.get_actor_label()
        if label in LIGHT_SETTINGS:
            by_label.setdefault(label, []).append(actor)

    bad_counts = {
        label: len(by_label.get(label, []))
        for label in LIGHT_SETTINGS
        if len(by_label.get(label, [])) != 1
    }
    if bad_counts:
        raise RuntimeError(
            "Expansion light counts are not exactly one each: {}".format(
                bad_counts
            )
        )

    changes = []
    for label, settings in LIGHT_SETTINGS.items():
        actor = by_label[label][0]
        actual_class = actor.get_class().get_name()
        if actual_class != settings["class"]:
            raise RuntimeError(
                "{} expected class {}, found {}".format(
                    label,
                    settings["class"],
                    actual_class,
                )
            )

        component = component_for(actor)
        before = {
            "intensity": float(component.get_editor_property("intensity")),
            "indirect_lighting_intensity": float(
                component.get_editor_property(
                    "indirect_lighting_intensity"
                )
            ),
        }
        component.modify()
        component.set_editor_property(
            "intensity",
            settings["intensity"],
        )
        component.set_editor_property(
            "indirect_lighting_intensity",
            settings["indirect_lighting_intensity"],
        )
        after = {
            "intensity": float(component.get_editor_property("intensity")),
            "indirect_lighting_intensity": float(
                component.get_editor_property(
                    "indirect_lighting_intensity"
                )
            ),
        }
        changes.append(
            {
                "label": label,
                "class": actual_class,
                "before": before,
                "after": after,
            }
        )

    if not unreal.EditorLevelLibrary.save_current_level():
        raise RuntimeError("Unable to save the current HospitalRoom level.")

    result = {
        "success": True,
        "world": world.get_path_name(),
        "changes": changes,
        "requires_lighting_rebuild": True,
    }
    unreal.MCPythonHelper.submit_result(
        json.dumps(result, sort_keys=True)
    )


try:
    run()
except Exception as exc:
    unreal.MCPythonHelper.submit_result(
        json.dumps(
            {
                "success": False,
                "error": str(exc),
                "traceback": traceback.format_exc(),
            },
            sort_keys=True,
        )
    )
    raise
