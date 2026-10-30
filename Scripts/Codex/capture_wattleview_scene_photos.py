"""Capture a compact Wattleview Grove review-photo set from the current saved map.

Run with UnrealEditor-Cmd against the UE 5.8 project.  The cameras are transient and the
map is never saved, so this script cannot alter placed actors or story state.
"""
import json
import os
import time

import unreal


MAP_PATH = "/Game/Wattleview/Maps/L_ResidentRoom"
OUT_DIR = os.path.join(unreal.Paths.project_saved_dir(), "Captures", "ScenePhotos")
WIDTH, HEIGHT = 1600, 900
WAIT_SECONDS = float(os.environ.get("WG_CAPTURE_WAIT", "25"))


SHOTS = [
    ("01_ResidentRoom_Overview.png", (105, 40, 165), (300, 150, 125), 82.0),
    ("02_ResidentRoom_Corner.png", (80, 330, 225), (300, 140, 100), 82.0),
    ("03_Table_And_Chairs.png", (275, 95, 155), (405, 205, 58), 68.0),
    ("04_Bed_And_Wardrobe.png", (430, 110, 180), (175, 345, 82), 72.0),
    ("05_Corridor.png", (300, 130, 160), (300, -360, 135), 76.0),
    ("06_Large_Room.png", (-60, -720, 175), (340, -1050, 110), 78.0),
    ("07_Large_Room_Window.png", (300, -1100, 160), (930, -1100, 140), 72.0),
]


def vector(values):
    return unreal.Vector(float(values[0]), float(values[1]), float(values[2]))


def capture(world, actor_subsystem, name, location, target, fov):
    render_target = unreal.RenderingLibrary.create_render_target2d(
        world,
        WIDTH,
        HEIGHT,
        unreal.TextureRenderTargetFormat.RTF_RGBA8_SRGB,
    )
    camera_location = vector(location)
    camera_rotation = unreal.MathLibrary.find_look_at_rotation(camera_location, vector(target))
    capture_actor = actor_subsystem.spawn_actor_from_class(
        unreal.SceneCapture2D,
        camera_location,
        camera_rotation,
    )
    try:
        component = capture_actor.capture_component2d
        component.set_editor_property("texture_target", render_target)
        component.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_COLOR_LDR)
        component.set_editor_property("fov_angle", float(fov))
        component.capture_scene()
        unreal.RenderingLibrary.export_render_target(
            world,
            render_target,
            OUT_DIR,
            name,
        )
        unreal.log(f"[ScenePhotos] wrote {name}")
        return os.path.join(OUT_DIR, name)
    finally:
        actor_subsystem.destroy_actor(capture_actor)


state = {"ticks": 0, "loaded_at": None, "done": False, "handle": None}


def finish():
    unreal.unregister_slate_post_tick_callback(state["handle"])
    unreal.EditorPythonScripting.set_keep_python_script_alive(False)


def tick(_delta_seconds):
    if state["done"]:
        return
    state["ticks"] += 1
    try:
        if state["loaded_at"] is None:
            if state["ticks"] < 10:
                return
            level_editor = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
            if not level_editor.load_level(MAP_PATH):
                raise RuntimeError(f"Could not load {MAP_PATH}")
            state["loaded_at"] = time.time()
            unreal.log("[ScenePhotos] level loaded; waiting for shaders and textures")
            return

        if time.time() - state["loaded_at"] < WAIT_SECONDS:
            return

        state["done"] = True
        try:
            unreal.AutomationLibrary.finish_loading_before_screenshot()
        except Exception:
            pass

        world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
        actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        os.makedirs(OUT_DIR, exist_ok=True)
        paths = [
            capture(world, actor_subsystem, name, location, target, fov)
            for name, location, target, fov in SHOTS
        ]
        unreal.log("[ScenePhotos] " + json.dumps({"captures": paths}))
        finish()
    except Exception as exc:
        unreal.log_error(f"[ScenePhotos] failed: {exc}")
        state["done"] = True
        finish()


unreal.EditorPythonScripting.set_keep_python_script_alive(True)
state["handle"] = unreal.register_slate_post_tick_callback(tick)
