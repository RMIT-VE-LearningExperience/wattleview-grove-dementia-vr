"""Render a PNG from every camera in the resident room for layout review.

Run headless:
  UnrealEditor-Cmd.exe <project>.uproject -ExecutePythonScript="<this file>" -nosplash

Output: <project>/Saved/Captures/<camera label>.png. Desktop renderer, so judge layout and
framing only; brightness must be judged on the headset (no exposure on mobile LDR).
"""
import os
import time

import unreal

MAP_PATH = "/Game/Wattleview/Maps/L_ResidentRoom"
OUT_DIR = os.path.join(unreal.Paths.project_saved_dir(), "Captures")
W, H = 1600, 900


def log(msg):
    unreal.log("[Capture] " + msg)


def load():
    les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if not les.load_level(MAP_PATH):
        raise RuntimeError("could not load " + MAP_PATH)


def capture():
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    os.makedirs(OUT_DIR, exist_ok=True)

    rt = unreal.RenderingLibrary.create_render_target2d(world, W, H, unreal.TextureRenderTargetFormat.RTF_RGBA8_SRGB)
    cams = [a for a in actors.get_all_level_actors() if isinstance(a, unreal.CineCameraActor)]
    log(f"{len(cams)} cameras in {world.get_name()}")
    for cam in cams:
        label = cam.get_actor_label()
        cap = actors.spawn_actor_from_class(unreal.SceneCapture2D, cam.get_actor_location(), cam.get_actor_rotation())
        comp = cap.capture_component2d
        comp.set_editor_property("texture_target", rt)
        comp.set_editor_property("fov_angle", 100.0)
        comp.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_COLOR_LDR)
        try:   # wait for shader compilation and texture streaming (FunctionalTesting helper)
            unreal.AutomationLibrary.finish_loading_before_screenshot()
        except Exception:
            pass
        comp.capture_scene()
        unreal.RenderingLibrary.export_render_target(world, rt, OUT_DIR, label + ".png")
        actors.destroy_actor(cap)
        log(f"wrote {label}.png")


# Shaders for freshly loaded materials compile/load asynchronously, so capturing straight
# after loading renders the default checker material. Load on an early tick, then let the
# editor run for WAIT_SECONDS of wall-clock time before capturing.
# Override with the WG_CAPTURE_WAIT environment variable (seconds); new master materials can
# take several minutes to compile on the first run.
WAIT_SECONDS = float(os.environ.get("WG_CAPTURE_WAIT", "30"))
_state = {"ticks": 0, "loaded_at": None, "done": False, "handle": None}


def _finish():
    unreal.unregister_slate_post_tick_callback(_state["handle"])
    # Releasing keep-alive lets -ExecutePythonScript close the editor.
    unreal.EditorPythonScripting.set_keep_python_script_alive(False)


def _tick(dt):
    if _state["done"]:
        return
    _state["ticks"] += 1
    try:
        if _state["loaded_at"] is None:
            if _state["ticks"] >= 10:
                load()
                _state["loaded_at"] = time.time()
                log("level loaded; waiting for shaders")
            return
        if time.time() - _state["loaded_at"] < WAIT_SECONDS:
            return
        _state["done"] = True
        capture()
        _finish()
    except Exception as exc:  # surface errors, then still quit
        unreal.log_error(f"[Capture] failed: {exc}")
        _state["done"] = True
        _finish()


# -ExecutePythonScript closes the editor once the script returns unless asked to stay alive.
unreal.EditorPythonScripting.set_keep_python_script_alive(True)
_state["handle"] = unreal.register_slate_post_tick_callback(_tick)
