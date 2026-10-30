"""Render isolated Maria reference views from the saved UE 5.8 resident-room map.

All actor moves and capture helpers are transient.  The map is never saved.
"""
import json
import math
import os
import time
import traceback

import unreal


MAP_PATH = "/Game/Wattleview/Maps/L_ResidentRoom"
OUT_DIR = os.path.join(unreal.Paths.project_saved_dir(), "Captures", "CharacterSheet", "Maria")
WIDTH, HEIGHT = 1000, 1400
WAIT_SECONDS = float(os.environ.get("WG_CAPTURE_WAIT", "35"))


def log(message):
    unreal.log("[MariaSheet] " + str(message))


def v(x, y, z):
    return unreal.Vector(float(x), float(y), float(z))


def add_light(actor_subsystem, cls, location, rotation=None):
    return actor_subsystem.spawn_actor_from_class(
        cls,
        location,
        rotation or unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0),
    )


def offset(base, forward, right, forward_amount, right_amount, z_amount):
    return v(
        base.x + forward.x * forward_amount + right.x * right_amount,
        base.y + forward.y * forward_amount + right.y * right_amount,
        base.z + z_amount,
    )


def configure_lighting(actor_subsystem, base, forward, right):
    helpers = []

    sun = add_light(
        actor_subsystem,
        unreal.DirectionalLight,
        offset(base, forward, right, 250, 160, 350),
        unreal.Rotator(roll=0.0, pitch=-28.0, yaw=-145.0),
    )
    sun.light_component.set_mobility(unreal.ComponentMobility.MOVABLE)
    sun.light_component.set_intensity(1.45)
    sun.light_component.set_editor_property("light_source_angle", 7.0)
    helpers.append(sun)

    key = add_light(actor_subsystem, unreal.PointLight, offset(base, forward, right, 230, 170, 205))
    key.light_component.set_mobility(unreal.ComponentMobility.MOVABLE)
    key.light_component.set_intensity(75.0)
    key.light_component.set_editor_property("attenuation_radius", 750.0)
    key.light_component.set_editor_property("source_radius", 55.0)
    helpers.append(key)

    fill = add_light(actor_subsystem, unreal.PointLight, offset(base, forward, right, 120, -240, 145))
    fill.light_component.set_mobility(unreal.ComponentMobility.MOVABLE)
    fill.light_component.set_intensity(30.0)
    fill.light_component.set_editor_property("attenuation_radius", 700.0)
    fill.light_component.set_editor_property("source_radius", 70.0)
    helpers.append(fill)

    rim = add_light(actor_subsystem, unreal.PointLight, offset(base, forward, right, -210, -80, 195))
    rim.light_component.set_mobility(unreal.ComponentMobility.MOVABLE)
    rim.light_component.set_intensity(45.0)
    rim.light_component.set_editor_property("attenuation_radius", 650.0)
    rim.light_component.set_editor_property("source_radius", 45.0)
    helpers.append(rim)

    sky = add_light(actor_subsystem, unreal.SkyLight, offset(base, forward, right, 0, 0, 300))
    sky.light_component.set_mobility(unreal.ComponentMobility.MOVABLE)
    sky.light_component.set_editor_property("source_type", unreal.SkyLightSourceType.SLS_SPECIFIED_CUBEMAP)
    sky.light_component.set_editor_property(
        "cubemap",
        unreal.load_asset("/Engine/MapTemplates/Sky/DaylightAmbientCubemap.DaylightAmbientCubemap"),
    )
    sky.light_component.set_intensity(0.55)
    sky.light_component.recapture_sky()
    helpers.append(sky)
    return helpers


def body_and_head(maria):
    components = list(maria.get_components_by_class(unreal.SkeletalMeshComponent))
    if not components:
        raise RuntimeError("Maria has no SkeletalMeshComponent")
    body = next((c for c in components if "body" in c.get_name().lower()), components[0])
    face = next((c for c in components if "face" in c.get_name().lower()), body)
    origin, extent, _radius = unreal.SystemLibrary.get_component_bounds(body)
    center = v(origin.x, origin.y, origin.z)
    if face.does_socket_exist("head"):
        head = face.get_socket_location("head")
        head = v(head.x, head.y, head.z + 7.0)
    elif body.does_socket_exist("head"):
        head = body.get_socket_location("head")
        head = v(head.x, head.y, head.z + 7.0)
    else:
        head = v(center.x, center.y, center.z + extent.z * 0.60)
    return body, center, v(extent.x, extent.y, extent.z), head, components


def capture_view(world, actor_subsystem, maria, hidden_actors, name, location, target, fov):
    render_target = unreal.RenderingLibrary.create_render_target2d(
        world,
        WIDTH,
        HEIGHT,
        unreal.TextureRenderTargetFormat.RTF_RGBA8_SRGB,
    )
    capture_actor = actor_subsystem.spawn_actor_from_class(
        unreal.SceneCapture2D,
        location,
        unreal.MathLibrary.find_look_at_rotation(location, target),
    )
    try:
        component = capture_actor.capture_component2d
        component.set_editor_property("texture_target", render_target)
        component.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_COLOR_LDR)
        component.set_editor_property("fov_angle", float(fov))
        for actor in hidden_actors:
            component.hide_actor_components(actor, True)

        post = component.get_editor_property("post_process_settings")
        post.set_editor_property("override_auto_exposure_method", True)
        post.set_editor_property("auto_exposure_method", unreal.AutoExposureMethod.AEM_MANUAL)
        post.set_editor_property("override_auto_exposure_apply_physical_camera_exposure", True)
        post.set_editor_property("auto_exposure_apply_physical_camera_exposure", False)
        post.set_editor_property("override_auto_exposure_bias", True)
        post.set_editor_property("auto_exposure_bias", -1.10)
        component.set_editor_property("post_process_settings", post)

        try:
            unreal.AutomationLibrary.finish_loading_before_screenshot()
        except Exception:
            pass
        component.capture_scene()
        unreal.RenderingLibrary.export_render_target(world, render_target, OUT_DIR, name)
        log("wrote " + name)
        return os.path.join(OUT_DIR, name)
    finally:
        actor_subsystem.destroy_actor(capture_actor)


def run():
    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    all_actors = list(actor_subsystem.get_all_level_actors())
    maria = next((a for a in all_actors if a.get_actor_label() == "Maria_StandIn"), None)
    if maria is None:
        raise RuntimeError("Maria_StandIn was not found")

    old_location = maria.get_actor_location()
    old_rotation = maria.get_actor_rotation()
    # Do not move or rotate the placed MetaHuman for capture. Groom simulation follows the
    # component transform asynchronously, so an instantaneous editor move can leave the hair
    # at its former world-space position. The camera rig is built around the saved transform.
    visual_yaw = math.radians(float(old_rotation.yaw) + 90.0)
    forward = v(math.cos(visual_yaw), math.sin(visual_yaw), 0.0)
    right = v(-math.sin(visual_yaw), math.cos(visual_yaw), 0.0)
    maria.set_actor_hidden_in_game(False)

    helpers = configure_lighting(actor_subsystem, old_location, forward, right)

    # Hair and some MetaHuman parts may be attached child actors rather than components owned
    # directly by BP_Maria.  Keep the entire Maria attachment tree visible.
    def belongs_to_maria(actor):
        current = actor
        seen = set()
        while current is not None and current not in seen:
            if current == maria:
                return True
            seen.add(current)
            current = current.get_attach_parent_actor()
        return False

    visible_group = [a for a in all_actors if belongs_to_maria(a)]
    hidden = [a for a in all_actors if a not in visible_group]
    os.makedirs(OUT_DIR, exist_ok=True)

    body, center, extent, head, components = body_and_head(maria)
    log(json.dumps({
        "actor": maria.get_path_name(),
        "center": [center.x, center.y, center.z],
        "extent": [extent.x, extent.y, extent.z],
        "head": [head.x, head.y, head.z],
        "saved_location": [old_location.x, old_location.y, old_location.z],
        "saved_rotation": [old_rotation.pitch, old_rotation.yaw, old_rotation.roll],
        "visual_forward": [forward.x, forward.y, forward.z],
        "components": [f"{c.get_name()}:{c.get_class().get_name()}" for c in components],
        "visible_group": [f"{a.get_actor_label()}:{a.get_class().get_name()}" for a in visible_group],
    }))

    body_target = v(center.x, center.y, center.z - extent.z * 0.03)
    full_distance = max(330.0, extent.z * 4.15)
    front = offset(body_target, forward, right, full_distance, 0, 0)
    three_quarter = offset(body_target, forward, right, full_distance * 0.78, full_distance * 0.62, 0)
    profile = offset(body_target, forward, right, 0, full_distance, 0)
    back = offset(body_target, forward, right, -full_distance, 0, 0)
    face_location = offset(head, forward, right, 92.0, 6.0, 1.0)
    torso_target = v(center.x, center.y, center.z + extent.z * 0.08)
    torso_location = offset(torso_target, forward, right, 150.0, 80.0, 4.0)

    shots = [
        ("01_front.png", front, body_target, 29.0),
        ("02_three_quarter.png", three_quarter, body_target, 29.0),
        ("03_profile.png", profile, body_target, 29.0),
        ("04_back.png", back, body_target, 29.0),
        ("05_face.png", face_location, head, 27.0),
        ("06_outfit_detail.png", torso_location, torso_target, 26.0),
    ]
    paths = [
        capture_view(world, actor_subsystem, maria, hidden, name, location, target, fov)
        for name, location, target, fov in shots
    ]

    maria.set_actor_location(old_location, False, True)
    maria.set_actor_rotation(old_rotation, False)
    maria.set_actor_hidden_in_game(False)
    for helper in helpers:
        actor_subsystem.destroy_actor(helper)
    log(json.dumps({"captures": paths}))


STATE = {"ticks": 0, "loaded_at": None, "done": False, "handle": None}


def finish():
    unreal.unregister_slate_post_tick_callback(STATE["handle"])
    unreal.EditorPythonScripting.set_keep_python_script_alive(False)


def tick(_delta_seconds):
    if STATE["done"]:
        return
    STATE["ticks"] += 1
    try:
        if STATE["loaded_at"] is None:
            if STATE["ticks"] < 10:
                return
            level_editor = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
            if not level_editor.load_level(MAP_PATH):
                raise RuntimeError("Could not load " + MAP_PATH)
            STATE["loaded_at"] = time.time()
            log("level loaded; waiting for MetaHuman shaders and grooms")
            return
        if time.time() - STATE["loaded_at"] < WAIT_SECONDS:
            return
        STATE["done"] = True
        run()
        finish()
    except Exception:
        unreal.log_error("[MariaSheet] failed\n" + traceback.format_exc())
        STATE["done"] = True
        finish()


unreal.EditorPythonScripting.set_keep_python_script_alive(True)
STATE["handle"] = unreal.register_slate_post_tick_callback(tick)
