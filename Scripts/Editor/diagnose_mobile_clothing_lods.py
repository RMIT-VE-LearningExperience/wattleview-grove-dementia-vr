"""Render the assembled MetaHuman clothes at every runtime LOD and stress pose.

This is a non-saving diagnostic.  It temporarily drives each body with the same
retargeted idle/walk/sit clips used by LS_Story, forces the actor's LODSync level,
and captures only that actor.  All component state is restored before exit.
"""
import math
import os
import time
import traceback

import unreal


OUT = os.path.join(unreal.Paths.project_saved_dir(), "MobileClothingLODReview")
W, H = 1000, 1200
ACTORS = [
    ("Maria", "Maria_StandIn", "/Game/Wattleview/Animations/MH/Maria"),
    ("Carer", "David_StandIn", "/Game/Wattleview/Animations/MH/David"),
]
POSES = [
    ("idle", "MM_Idle", 0.32),
    ("walk", "AS_Placeholder_Walk", 0.52),
    ("sit", "AS_Placeholder_Sit", 0.82),
]
LODS = (0, 1, 2)

actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
world_sub = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)


def log(message):
    unreal.log("[MobileClothingLOD] " + str(message))


def find_actor(label):
    return next(
        (actor for actor in actor_sub.get_all_level_actors() if actor.get_actor_label() == label),
        None,
    )


def component(actor, name):
    return next(
        (comp for comp in actor.get_components_by_class(unreal.ActorComponent)
         if comp.get_name() == name),
        None,
    )


def load_pose(folder, stem, person):
    path = f"{folder}/{stem}_{'Maria' if person == 'Maria' else 'David'}"
    asset = unreal.load_asset(path)
    if asset is None:
        raise RuntimeError("Missing animation " + path)
    return asset


def camera_transform(actor):
    # MetaHuman body faces local +Y.  Use a stable front three-quarter view.
    origin = actor.get_actor_location()
    yaw = actor.get_actor_rotation().yaw + 118.0
    radians = math.radians(yaw)
    outward = unreal.Vector(math.cos(radians), math.sin(radians), 0.0)
    camera = origin + outward * 250.0 + unreal.Vector(0.0, 0.0, 105.0)
    target = origin + unreal.Vector(0.0, 0.0, 91.0)
    return camera, unreal.MathLibrary.find_look_at_rotation(camera, target)


def setup():
    os.makedirs(OUT, exist_ok=True)
    world = world_sub.get_editor_world()
    if world is None:
        raise RuntimeError("No editor world")
    targets = []
    for person, label, folder in ACTORS:
        actor = find_actor(label)
        if actor is None:
            raise RuntimeError("Missing actor " + label)
        body = component(actor, "Body")
        lod_sync = component(actor, "LODSync")
        if body is None or lod_sync is None:
            raise RuntimeError(label + " is missing Body or LODSync")
        original_anim = None
        try:
            original_anim = body.get_editor_property("animation_data")
        except Exception:
            pass
        targets.append({
            "person": person,
            "actor": actor,
            "body": body,
            "lod_sync": lod_sync,
            "folder": folder,
            "original_lod": lod_sync.get_editor_property("forced_lod"),
            "original_mode": body.get_editor_property("animation_mode"),
            "original_anim": original_anim,
        })

    render_target = unreal.RenderingLibrary.create_render_target2d(
        world, W, H, unreal.TextureRenderTargetFormat.RTF_RGBA8_SRGB
    )
    render_target.set_editor_property("clear_color", unreal.LinearColor(0.18, 0.18, 0.18, 1.0))
    capture = actor_sub.spawn_actor_from_class(
        unreal.SceneCapture2D, unreal.Vector(), unreal.Rotator()
    )
    capture.set_actor_label("__MobileClothingLODDiagnostic")
    capture.tags = [unreal.Name("TransientDiagnostic")]
    capture_component = capture.capture_component2d
    capture_component.set_editor_property("texture_target", render_target)
    capture_component.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_COLOR_LDR)
    capture_component.set_editor_property("fov_angle", 48.0)
    capture_component.set_editor_property(
        "primitive_render_mode", unreal.SceneCapturePrimitiveRenderMode.PRM_USE_SHOW_ONLY_LIST
    )
    capture_component.set_editor_property("capture_every_frame", False)
    capture_component.set_editor_property("capture_on_movement", False)
    return world, targets, render_target, capture, capture_component


STATE = {
    "world": None,
    "targets": [],
    "rt": None,
    "capture": None,
    "capture_component": None,
    "target": 0,
    "pose": 0,
    "lod": 0,
    "phase": "setup",
    "settle_until": 0.0,
    "callback": None,
    "busy": False,
}


def restore():
    for target in STATE["targets"]:
        try:
            target["lod_sync"].set_editor_property("forced_lod", target["original_lod"])
            target["body"].set_animation_mode(target["original_mode"])
            if target["original_anim"] is not None:
                target["body"].set_editor_property("animation_data", target["original_anim"])
        except Exception:
            unreal.log_warning("[MobileClothingLOD] restore failed:\n" + traceback.format_exc())
    if STATE["capture"] is not None:
        actor_sub.destroy_actor(STATE["capture"])
    # The diagnostic is intentionally non-saving.  All modified level-instance state
    # has been restored, so do not leave the map marked dirty merely from previewing it.
    try:
        STATE["world"].get_outermost().set_dirty_flag(False)
    except Exception:
        pass


def finish():
    restore()
    if STATE["callback"] is not None:
        unreal.unregister_slate_post_tick_callback(STATE["callback"])
        STATE["callback"] = None
    log("done: " + OUT)


def advance():
    STATE["lod"] += 1
    if STATE["lod"] >= len(LODS):
        STATE["lod"] = 0
        STATE["pose"] += 1
        if STATE["pose"] >= len(POSES):
            STATE["pose"] = 0
            STATE["target"] += 1
            if STATE["target"] >= len(STATE["targets"]):
                finish()
                return False
    return True


def tick(_delta):
    if STATE["busy"]:
        return
    STATE["busy"] = True
    try:
        now = time.time()
        if STATE["phase"] == "setup":
            (STATE["world"], STATE["targets"], STATE["rt"], STATE["capture"],
             STATE["capture_component"]) = setup()
            unreal.AutomationLibrary.finish_loading_before_screenshot()
            STATE["phase"] = "pose"
        elif STATE["phase"] == "pose":
            target = STATE["targets"][STATE["target"]]
            pose_name, anim_stem, fraction = POSES[STATE["pose"]]
            lod = LODS[STATE["lod"]]
            anim = load_pose(target["folder"], anim_stem, target["person"])
            target["lod_sync"].set_editor_property("forced_lod", lod)
            body = target["body"]
            body.set_animation_mode(unreal.AnimationMode.ANIMATION_SINGLE_NODE)
            body.set_animation(anim)
            body.play(False)
            body.set_position(max(0.0, anim.get_play_length() * fraction), False)
            body.set_play_rate(0.0)
            STATE["settle_until"] = now + 0.55
            STATE["phase"] = "settle"
            log(f"{target['person']} {pose_name} LODSync {lod}")
        elif STATE["phase"] == "settle" and now >= STATE["settle_until"]:
            STATE["phase"] = "capture"
        elif STATE["phase"] == "capture":
            target = STATE["targets"][STATE["target"]]
            pose_name = POSES[STATE["pose"]][0]
            lod = LODS[STATE["lod"]]
            location, rotation = camera_transform(target["actor"])
            STATE["capture"].set_actor_location_and_rotation(location, rotation, False, True)
            comp = STATE["capture_component"]
            comp.clear_show_only_components()
            comp.show_only_actor_components(target["actor"], True)
            comp.capture_scene()
            filename = f"{target['person']}_{pose_name}_LODSync{lod}.png"
            unreal.RenderingLibrary.export_render_target(
                STATE["world"], STATE["rt"], OUT, filename
            )
            log("wrote " + filename)
            if advance():
                STATE["phase"] = "pose"
    except Exception:
        unreal.log_error("[MobileClothingLOD] FAILED\n" + traceback.format_exc())
        finish()
    finally:
        STATE["busy"] = False


STATE["callback"] = unreal.register_slate_post_tick_callback(tick)
log("started")
