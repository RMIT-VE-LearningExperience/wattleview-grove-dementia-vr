import json
import os
import traceback

import unreal


def vec(x, y, z):
    return unreal.Vector(float(x), float(y), float(z))


def rot(pitch=0.0, yaw=0.0, roll=0.0):
    value = unreal.Rotator()
    value.pitch = float(pitch)
    value.yaw = float(yaw)
    value.roll = float(roll)
    return value


def capture_once(world, actor_subsystem, output_dir, name, location, rotation):
    capture_actor = None
    render_target = None
    try:
        render_target = unreal.RenderingLibrary.create_render_target2d(
            world,
            1024,
            576,
            unreal.TextureRenderTargetFormat.RTF_RGBA8,
        )
        capture_actor = actor_subsystem.spawn_actor_from_class(
            unreal.SceneCapture2D,
            location,
            rotation,
        )
        if capture_actor is None:
            raise RuntimeError("Unable to create one-shot capture actor")

        component = capture_actor.capture_component2d
        component.set_editor_property("capture_every_frame", False)
        component.set_editor_property("capture_on_movement", False)
        component.set_editor_property("always_persist_rendering_state", False)
        component.set_editor_property("texture_target", render_target)
        component.set_editor_property(
            "capture_source",
            unreal.SceneCaptureSource.SCS_FINAL_COLOR_LDR,
        )
        component.set_editor_property("fov_angle", 82.0)
        component.capture_scene()

        unreal.RenderingLibrary.export_render_target(
            world,
            render_target,
            output_dir,
            name,
        )
        return os.path.join(output_dir, name)
    finally:
        if capture_actor is not None:
            actor_subsystem.destroy_actor(capture_actor)
        render_target = None


def run():
    editor_subsystem = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    world = editor_subsystem.get_editor_world()
    if world is None or world.get_name() != "HospitalRoom":
        raise RuntimeError("HospitalRoom is not the active editor world")

    output_dir = os.path.join(
        unreal.Paths.project_saved_dir(),
        "CodexCaptures",
        "BuildingExpansion",
        "ExposureRebalance",
    )
    os.makedirs(output_dir, exist_ok=True)

    room_corner = vec(-60, -720, 175)
    room_target = vec(340, -1050, 110)
    room_rotation = unreal.MathLibrary.find_look_at_rotation(room_corner, room_target)

    captures = [
        capture_once(
            world,
            actor_subsystem,
            output_dir,
            "CorridorFromHospital.png",
            vec(300, 130, 160),
            rot(0, -90, 0),
        ),
        capture_once(
            world,
            actor_subsystem,
            output_dir,
            "LargeRoomEntrance.png",
            vec(300, -470, 160),
            rot(0, -90, 0),
        ),
        capture_once(
            world,
            actor_subsystem,
            output_dir,
            "LargeRoomOverview.png",
            room_corner,
            room_rotation,
        ),
        capture_once(
            world,
            actor_subsystem,
            output_dir,
            "LargeRoomWindowSky.png",
            vec(300, -1100, 160),
            rot(0, 0, 0),
        ),
        capture_once(
            world,
            actor_subsystem,
            output_dir,
            "ExteriorSkyDirect.png",
            vec(1000, -1100, 180),
            rot(0, 0, 0),
        ),
    ]
    return {"success": True, "captures": captures}


try:
    print(json.dumps(run()))
except Exception as exc:
    print(
        json.dumps(
            {
                "success": False,
                "message": str(exc),
                "traceback": traceback.format_exc(),
            }
        )
    )
