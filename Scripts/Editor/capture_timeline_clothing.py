"""Capture Maria and David's runtime clothes at representative LS_Story frames.

This is a read-only visual validation pass. It opens and evaluates the existing sequence,
spawns transient SceneCapture2D actors, writes PNGs under Saved/TimelineClothingReview, and
does not save the map or sequence.

Run in an interactive editor (MCP/Execute Python); the tick callback allows animation poses,
cloth/skinning and rendering to settle before each capture.
"""
import os
import time
import math

import unreal


MAP = "/Game/Wattleview/Maps/L_ResidentRoom"
SEQUENCE = "/Game/Wattleview/Cinematics/LS_Story"
OUT = os.path.join(unreal.Paths.project_saved_dir(), "TimelineClothingReview", "Isolated")
W, H = 1200, 1000
FPS = 30

# Times exercise the actual story states that stress the outfit most: neutral standing,
# David walking, Maria walking/turning, Maria's sit transition, both seated, David leaving.
MOMENTS = [
    (2.0, "00_idle"),
    (7.5, "01_david_walk"),
    (25.5, "02_maria_walk"),
    (30.0, "03_maria_sit"),
    (241.0, "04_both_seated"),
    (285.5, "05_david_exit"),
]
PEOPLE = [("Maria", "Maria_StandIn"), ("Carer", "David_StandIn")]

actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
seq_lib = unreal.LevelSequenceEditorBlueprintLibrary


def log(msg):
    unreal.log("[TimelineClothes] " + str(msg))


def find(label):
    return next((a for a in actors.get_all_level_actors() if a.get_actor_label() == label), None)


def frame_camera(person):
    loc = person.get_actor_location()
    # MetaHuman bodies face local +Y, so actor yaw + 90 degrees is the visual forward.
    # Add a 25-degree orbit for a readable front three-quarter view. The isolated render
    # ignores room occluders, so this stays consistent even when Maria faces the wall.
    yaw = person.get_actor_rotation().yaw + 115.0
    r = math.radians(yaw)
    forward = unreal.Vector(math.cos(r), math.sin(r), 0.0)
    cam_loc = loc + forward * 245.0 + unreal.Vector(0.0, 0.0, 112.0)
    target = loc + unreal.Vector(0.0, 0.0, 92.0)
    return cam_loc, unreal.MathLibrary.find_look_at_rotation(cam_loc, target)


def setup():
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    if world is None or world.get_path_name().split(".")[0] != MAP:
        if not les.load_level(MAP):
            raise RuntimeError("Could not load " + MAP)
        world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    seq = unreal.load_asset(SEQUENCE)
    if seq is None or not seq_lib.open_level_sequence(seq):
        raise RuntimeError("Could not open " + SEQUENCE)
    os.makedirs(OUT, exist_ok=True)
    rt = unreal.RenderingLibrary.create_render_target2d(
        world, W, H, unreal.TextureRenderTargetFormat.RTF_RGBA8_SRGB
    )
    rt.set_editor_property("clear_color", unreal.LinearColor(0.18, 0.18, 0.18, 1.0))
    cap = actors.spawn_actor_from_class(unreal.SceneCapture2D, unreal.Vector(), unreal.Rotator())
    comp = cap.capture_component2d
    comp.set_editor_property("texture_target", rt)
    comp.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_COLOR_LDR)
    comp.set_editor_property("fov_angle", 52.0)
    comp.set_editor_property(
        "primitive_render_mode", unreal.SceneCapturePrimitiveRenderMode.PRM_USE_SHOW_ONLY_LIST
    )
    comp.set_editor_property("capture_every_frame", False)
    comp.set_editor_property("capture_on_movement", False)
    return world, rt, cap, comp


STATE = {
    "world": None,
    "rt": None,
    "cap": None,
    "comp": None,
    "moment": 0,
    "person": 0,
    "phase": "setup",
    "started": time.time(),
    "settle_until": 0.0,
    "handle": None,
    "busy": False,
}


def finish():
    try:
        if STATE["cap"] is not None:
            actors.destroy_actor(STATE["cap"])
    finally:
        if STATE["handle"] is not None:
            unreal.unregister_slate_post_tick_callback(STATE["handle"])
        log("done: " + OUT)


def tick(_dt):
    if STATE["busy"]:
        return
    STATE["busy"] = True
    try:
        now = time.time()
        if STATE["phase"] == "setup":
            STATE["world"], STATE["rt"], STATE["cap"], STATE["comp"] = setup()
            unreal.AutomationLibrary.finish_loading_before_screenshot()
            STATE["phase"] = "pose"
        elif STATE["phase"] == "pose":
            seconds, _name = MOMENTS[STATE["moment"]]
            seq_lib.set_current_time(int(round(seconds * FPS)))
            seq_lib.refresh_current_level_sequence()
            STATE["settle_until"] = now + 0.75
            STATE["phase"] = "settle"
        elif STATE["phase"] == "settle" and now >= STATE["settle_until"]:
            STATE["phase"] = "capture"
        elif STATE["phase"] == "capture":
            seconds, moment_name = MOMENTS[STATE["moment"]]
            display_name, actor_label = PEOPLE[STATE["person"]]
            person = find(actor_label)
            if person is None:
                raise RuntimeError("Missing actor " + actor_label)
            cam_loc, cam_rot = frame_camera(person)
            STATE["cap"].set_actor_location_and_rotation(cam_loc, cam_rot, False, True)
            STATE["comp"].clear_show_only_components()
            STATE["comp"].show_only_actor_components(person, True)
            STATE["comp"].capture_scene()
            filename = f"{moment_name}_{seconds:06.1f}s_{display_name}.png"
            unreal.RenderingLibrary.export_render_target(
                STATE["world"], STATE["rt"], OUT, filename
            )
            log("wrote " + filename)
            STATE["person"] += 1
            if STATE["person"] >= len(PEOPLE):
                STATE["person"] = 0
                STATE["moment"] += 1
                STATE["phase"] = "pose"
                if STATE["moment"] >= len(MOMENTS):
                    finish()
            else:
                STATE["phase"] = "capture"
    except Exception:
        import traceback
        unreal.log_error("[TimelineClothes] FAILED\n" + traceback.format_exc())
        finish()
    finally:
        STATE["busy"] = False


STATE["handle"] = unreal.register_slate_post_tick_callback(tick)
log("started")
