"""Capture Maria's imported garment on real UE animation assets without saving the map."""

import json
import math
import os
import time
import traceback

import unreal


MAP_PATH = "/Game/Wattleview/Maps/L_ResidentRoom"
OUT_DIR = os.path.join(unreal.Paths.project_saved_dir(), "Captures", "GarmentValidation", "Maria")
WIDTH, HEIGHT = 1000, 1200
LOAD_WAIT = float(os.environ.get("WG_CAPTURE_WAIT", "20"))
POSE_WAIT = 1.25
DEBUG_MATERIAL = os.environ.get("WG_GARMENT_DEBUG_MATERIAL", "").strip()
REFERENCE_ONLY = os.environ.get("WG_GARMENT_REFERENCE_ONLY", "0") == "1"
LIVE_ONLY = os.environ.get("WG_GARMENT_LIVE_ONLY", "0") == "1"
POSES = [
    ("idle", "/Game/Wattleview/Animations/MH/Maria/MM_Idle_Maria", 0.45),
    ("walk", "/Game/Wattleview/Animations/MH/Maria/AS_Placeholder_Walk_Maria", 0.42),
    ("sit", "/Game/Wattleview/Animations/MH/Maria/AS_Placeholder_Sit_Maria", 0.96),
]
if REFERENCE_ONLY:
    POSES = [("reference", None, 0.0)]
elif LIVE_ONLY:
    POSES = [("live", None, 0.0)]
elif os.environ.get("WG_GARMENT_SIT_SWEEP", "0") == "1":
    sit = "/Game/Wattleview/Animations/MH/Maria/AS_Placeholder_Sit_Maria"
    POSES = [("sit25", sit, 0.25), ("sit45", sit, 0.45), ("sit65", sit, 0.65), ("sit85", sit, 0.85)]


def log(message):
    unreal.log("[MariaGarmentValidation] " + str(message))


def vec(x, y, z):
    return unreal.Vector(float(x), float(y), float(z))


def offset(base, forward, right, forward_amount, right_amount, z_amount):
    return vec(
        base.x + forward.x * forward_amount + right.x * right_amount,
        base.y + forward.y * forward_amount + right.y * right_amount,
        base.z + z_amount,
    )


def spawn_light(actor_subsystem, cls, location, rotation=None):
    return actor_subsystem.spawn_actor_from_class(
        cls, location, rotation or unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0)
    )


def make_lights(actor_subsystem, base, forward, right):
    helpers = []
    sun = spawn_light(
        actor_subsystem,
        unreal.DirectionalLight,
        offset(base, forward, right, 250, 160, 350),
        unreal.Rotator(roll=0.0, pitch=-28.0, yaw=-145.0),
    )
    sun.light_component.set_mobility(unreal.ComponentMobility.MOVABLE)
    sun.light_component.set_intensity(1.35)
    sun.light_component.set_editor_property("light_source_angle", 7.0)
    helpers.append(sun)
    for fa, ra, za, intensity, radius in (
        (230, 170, 205, 75.0, 55.0),
        (120, -240, 145, 30.0, 70.0),
        (-210, -80, 195, 45.0, 45.0),
    ):
        light = spawn_light(actor_subsystem, unreal.PointLight, offset(base, forward, right, fa, ra, za))
        light.light_component.set_mobility(unreal.ComponentMobility.MOVABLE)
        light.light_component.set_intensity(intensity)
        light.light_component.set_editor_property("attenuation_radius", 750.0)
        light.light_component.set_editor_property("source_radius", radius)
        helpers.append(light)
    sky = spawn_light(actor_subsystem, unreal.SkyLight, offset(base, forward, right, 0, 0, 300))
    sky.light_component.set_mobility(unreal.ComponentMobility.MOVABLE)
    sky.light_component.set_editor_property("source_type", unreal.SkyLightSourceType.SLS_SPECIFIED_CUBEMAP)
    sky.light_component.set_editor_property(
        "cubemap", unreal.load_asset("/Engine/MapTemplates/Sky/DaylightAmbientCubemap.DaylightAmbientCubemap")
    )
    sky.light_component.set_intensity(0.55)
    sky.light_component.recapture_sky()
    helpers.append(sky)
    return helpers


def capture(world, actor_subsystem, hidden, name, location, target, fov):
    target_tex = unreal.RenderingLibrary.create_render_target2d(
        world, WIDTH, HEIGHT, unreal.TextureRenderTargetFormat.RTF_RGBA8_SRGB
    )
    actor = actor_subsystem.spawn_actor_from_class(
        unreal.SceneCapture2D, location, unreal.MathLibrary.find_look_at_rotation(location, target)
    )
    try:
        comp = actor.capture_component2d
        comp.set_editor_property("texture_target", target_tex)
        comp.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_COLOR_LDR)
        comp.set_editor_property("fov_angle", float(fov))
        for item in hidden:
            comp.hide_actor_components(item, True)
        post = comp.get_editor_property("post_process_settings")
        post.set_editor_property("override_auto_exposure_method", True)
        post.set_editor_property("auto_exposure_method", unreal.AutoExposureMethod.AEM_MANUAL)
        post.set_editor_property("override_auto_exposure_apply_physical_camera_exposure", True)
        post.set_editor_property("auto_exposure_apply_physical_camera_exposure", False)
        post.set_editor_property("override_auto_exposure_bias", True)
        post.set_editor_property("auto_exposure_bias", -1.05)
        comp.set_editor_property("post_process_settings", post)
        try:
            unreal.AutomationLibrary.finish_loading_before_screenshot()
        except Exception:
            pass
        comp.capture_scene()
        unreal.RenderingLibrary.export_render_target(world, target_tex, OUT_DIR, name)
        log("wrote " + name)
    finally:
        actor_subsystem.destroy_actor(actor)


def setup():
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    all_actors = list(actors.get_all_level_actors())
    maria = next((a for a in all_actors if a.get_actor_label() == "Maria_StandIn"), None)
    if maria is None:
        raise RuntimeError("Maria_StandIn was not found")
    components = list(maria.get_components_by_class(unreal.SkeletalMeshComponent))
    body = next((c for c in components if c.get_name() == "Body"), None)
    outfit = next((c for c in components if c.get_name() == "SkeletalMesh"), None)
    if body is None or outfit is None:
        raise RuntimeError("Maria Body/SkeletalMesh components were not found")
    mesh = outfit.get_skinned_asset()
    expected = "/Game/Wattleview/Characters/Garments/Maria/SKM_Maria_Outfit.SKM_Maria_Outfit"
    if mesh is None or mesh.get_path_name() != expected:
        raise RuntimeError("unexpected outfit mesh: %s" % (mesh.get_path_name() if mesh else None))
    leader = outfit.get_editor_property("leader_pose_component")
    if leader != body:
        raise RuntimeError("outfit is not following Body: %s" % leader)
    if DEBUG_MATERIAL:
        material = unreal.load_asset(DEBUG_MATERIAL)
        if material is None:
            raise RuntimeError("missing debug material " + DEBUG_MATERIAL)
        for index in range(len(mesh.get_editor_property("materials"))):
            outfit.set_material(index, material)
        log("debug material override: " + DEBUG_MATERIAL)
    if REFERENCE_ONLY:
        outfit.set_leader_pose_component(None)
        outfit.set_enable_animation(False)
        for component in components:
            if component != outfit:
                component.set_visibility(False, True)
        outfit.set_visibility(True, True)
        log("reference-only capture: leader detached and other skeletal meshes hidden")
    for c in (body, outfit):
        try:
            c.set_editor_property("update_animation_in_editor", True)
        except Exception:
            pass
        c.set_editor_property("visibility_based_anim_tick_option", unreal.VisibilityBasedAnimTickOption.ALWAYS_TICK_POSE_AND_REFRESH_BONES)

    base = maria.get_actor_location()
    yaw = math.radians(float(maria.get_actor_rotation().yaw) + 90.0)
    forward = vec(math.cos(yaw), math.sin(yaw), 0.0)
    right = vec(-math.sin(yaw), math.cos(yaw), 0.0)

    def belongs(actor):
        current, seen = actor, set()
        while current is not None and current not in seen:
            if current == maria:
                return True
            seen.add(current)
            current = current.get_attach_parent_actor()
        return False

    visible = [a for a in all_actors if belongs(a)]
    hidden = [a for a in all_actors if a not in visible]
    helpers = make_lights(actors, base, forward, right)
    os.makedirs(OUT_DIR, exist_ok=True)
    log(json.dumps({
        "mesh": mesh.get_path_name(),
        "leader": leader.get_path_name(),
        "body": body.get_path_name(),
        "outfit": outfit.get_path_name(),
    }))
    return actors, world, maria, body, outfit, hidden, helpers, forward, right


def set_pose(body, pose):
    label, path, fraction = pose
    if path is None:
        log("pose reference")
        return
    anim = unreal.load_asset(path)
    if anim is None:
        raise RuntimeError("missing animation " + path)
    length = float(anim.get_play_length())
    body.set_animation_mode(unreal.AnimationMode.ANIMATION_SINGLE_NODE)
    body.set_editor_property("global_anim_rate_scale", 1.0)
    body.play_animation(anim, False)
    body.set_position(max(0.0, min(length - 0.001, length * fraction)), False)
    # Force the single-node instance to evaluate immediately in the editor commandlet;
    # otherwise successive captures can all retain the first cached pose.
    try:
        body.tick_animation(0.001, False)
        body.refresh_bone_transforms()
        body.update_bounds()
        body.mark_render_dynamic_data_dirty()
    except Exception as exc:
        log("pose refresh fallback: %s" % exc)
    try:
        body.set_editor_property("global_anim_rate_scale", 0.0)
    except Exception:
        pass
    log("pose %s at %.3f / %.3f" % (label, length * fraction, length))


def capture_pose(ctx, pose):
    actors, world, maria, body, outfit, hidden, helpers, forward, right = ctx
    label = pose[0]
    bounds_component = outfit if REFERENCE_ONLY else body
    origin, extent, _radius = unreal.SystemLibrary.get_component_bounds(bounds_component)
    center = vec(origin.x, origin.y, origin.z)
    extent = vec(extent.x, extent.y, extent.z)
    target = vec(center.x, center.y, center.z - extent.z * 0.02)
    dist = max(330.0, extent.z * 4.2)
    front = offset(target, forward, right, dist, 0, 0)
    three = offset(target, forward, right, dist * 0.80, dist * 0.62, 0)
    profile = offset(target, forward, right, 0, dist, 0)
    rear = offset(target, forward, right, -dist, 0, 0)
    shoulder_target = vec(center.x, center.y, center.z + extent.z * 0.34)
    shoulder = offset(shoulder_target, forward, right, 145.0, 70.0, 4.0)
    rear_shoulder = offset(shoulder_target, forward, right, -145.0, 55.0, 4.0)
    capture(world, actors, hidden, "%s_01_front.png" % label, front, target, 30.0)
    capture(world, actors, hidden, "%s_02_three_quarter.png" % label, three, target, 30.0)
    capture(world, actors, hidden, "%s_03_profile.png" % label, profile, target, 30.0)
    capture(world, actors, hidden, "%s_04_shoulders.png" % label, shoulder, shoulder_target, 25.0)
    capture(world, actors, hidden, "%s_05_rear.png" % label, rear, target, 30.0)
    capture(world, actors, hidden, "%s_06_rear_shoulders.png" % label, rear_shoulder, shoulder_target, 25.0)


STATE = {"phase": "boot", "since": time.time(), "pose_index": 0, "ctx": None, "handle": None}


def finish():
    unreal.unregister_slate_post_tick_callback(STATE["handle"])
    unreal.EditorPythonScripting.set_keep_python_script_alive(False)
    if STATE["ctx"]:
        for helper in STATE["ctx"][6]:
            STATE["ctx"][0].destroy_actor(helper)


def tick(_delta):
    try:
        now = time.time()
        if STATE["phase"] == "boot":
            if now - STATE["since"] < 0.5:
                return
            if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level(MAP_PATH):
                raise RuntimeError("could not load " + MAP_PATH)
            STATE.update(phase="loading", since=now)
            log("level loaded; waiting for MetaHuman assets")
            return
        if STATE["phase"] == "loading":
            if now - STATE["since"] < LOAD_WAIT:
                return
            STATE["ctx"] = setup()
            set_pose(STATE["ctx"][3], POSES[0])
            STATE.update(phase="pose_wait", since=now)
            return
        if STATE["phase"] == "pose_wait":
            if now - STATE["since"] < POSE_WAIT:
                return
            # Scene capture pumps Slate messages and can re-enter this callback.
            # Mark it busy before capture so one pose is emitted exactly once.
            STATE["phase"] = "capturing"
            capture_pose(STATE["ctx"], POSES[STATE["pose_index"]])
            STATE["pose_index"] += 1
            if STATE["pose_index"] >= len(POSES):
                log(json.dumps({"captures": OUT_DIR, "poses": [p[0] for p in POSES]}))
                STATE["phase"] = "done"
                finish()
                return
            set_pose(STATE["ctx"][3], POSES[STATE["pose_index"]])
            STATE.update(phase="pose_wait", since=now)
    except Exception:
        unreal.log_error("[MariaGarmentValidation] failed\n" + traceback.format_exc())
        STATE["phase"] = "failed"
        finish()


unreal.EditorPythonScripting.set_keep_python_script_alive(True)
STATE["handle"] = unreal.register_slate_post_tick_callback(tick)
