"""Shoot the wall photograph: young Maria and Enzo in a backyard thick with green.

Runs inside the open editor (tick-driven, uses Play-In-Editor so the MetaHuman faces follow the
bodies). It builds a temporary set far outside the room (lawn, fig tree, tomato plants, flower
bed, photographic sky), places BP_MariaYoung and BP_EnzoYoung (Optimized builds in
/Game/MetaHumans/PhotoM) in Maria's and Enzo's clothes, plays the retargeted idle and takes a
HighResShot from a set camera.

The shot used for the current print was an editor-viewport capture of the same set through
PhotoSet_Camera (hair strands don't render in a SceneCapture). Both routes give the young faces
glowing white eyes; grade_wall_photo.py repaints them.

Leave the set in place when done and CLOSE THE EDITOR WITHOUT SAVING: destroying the photo-set
MetaHuman actors after they animated in the editor crashed it ("pure virtual not implemented").

Save the raw image as SourceArt/Photos/raw_MariaEnzo_young.png, then
  python Scripts/Tools/grade_wall_photo.py     -> SourceArt/Photos/T_Photo_MariaEnzo.jpg
  import_room_assets.py (PHOTOS)               -> on SM_PhotoFrame_MariaEnzo

Run: exec(open(r"<this file>").read()) in the editor (or via MCP), with nothing else running.
"""
import os
import time

import unreal

O = unreal.Vector(0.0, 20000.0, 0.0)
ENV = "/Game/Wattleview/Environment/Meshes"
SET = [  # label, mesh, offset from O, yaw, scale
    ("PhotoSet_Lawn", f"{ENV}/Garden/SM_Lawn", (0, 0, 0), 0, 0.4),
    ("PhotoSet_Sky", f"{ENV}/Sky/SM_SkyDome", (0, 0, -30), 200, 0.35),
    ("PhotoSet_Fig", f"{ENV}/Memory/SM_FigTree", (-170, 70, 0), 30, 1.0),
    ("PhotoSet_Tomato1", f"{ENV}/Memory/SM_TomatoPlant", (-110, -90, 0), 0, 1.0),
    ("PhotoSet_Tomato2", f"{ENV}/Memory/SM_TomatoPlant", (-120, -135, 0), 140, 1.0),
    ("PhotoSet_Bed", f"{ENV}/Garden/SM_FlowerBed", (-210, -10, 0), 0, 1.0),
    ("PhotoSet_Tree", f"{ENV}/Garden/SM_GardenTree_A", (-650, 260, 0), 80, 1.0),
    ("PhotoSet_Shrub", f"{ENV}/Garden/SM_Shrub", (-260, 190, 0), 0, 1.0),
]
PEOPLE = [  # label, blueprint, offset, yaw (meshes face +Y at yaw 0), garment, idle clip
    ("PhotoSet_Enzo", "/Game/MetaHumans/PhotoM/EnzoYoung/BP_EnzoYoung", (0, -34, 0), -78,
     "/Game/Wattleview/Characters/Garments/Enzo/SKM_Enzo_Outfit", "/Game/Wattleview/Animations/MH/David/MM_Idle_David"),
    ("PhotoSet_Maria", "/Game/MetaHumans/PhotoM/MariaYoung/BP_MariaYoung", (0, 34, 0), -102,
     "/Game/Wattleview/Characters/Garments/Maria/SKM_Maria_Outfit", "/Game/Wattleview/Animations/MH/Maria/MM_Idle_Maria"),
]
CAM = ("PhotoSet_Camera", (430, 0, 150), (0, 0, 120), 35.0)   # label, offset, look-at offset, focal mm
EXPOSURE_BIAS = -0.6   # stops; the desktop preview has no auto exposure and the sunlit set clips

acts = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
SHOTS = os.path.join(unreal.Paths.project_saved_dir(), "Screenshots", "WindowsEditor")
ST = {"h": None, "step": "build", "t": 0.0, "shot_before": set(), "busy": False}


def log(m):
    unreal.log("[WallPhoto] " + str(m))


def V(off):
    return unreal.Vector(O.x + off[0], O.y + off[1], O.z + off[2])


def clear_set():
    for a in acts.get_all_level_actors():
        if a.get_actor_label().startswith("PhotoSet_"):
            acts.destroy_actor(a)


def build_set():
    clear_set()
    for label, path, off, yaw, scale in SET:
        mesh = unreal.load_asset(path)
        if mesh is None:
            log(f"missing {path}")
            continue
        a = acts.spawn_actor_from_object(mesh, V(off), unreal.Rotator(roll=0, pitch=0, yaw=yaw))
        a.set_actor_label(label)
        a.set_actor_scale3d(unreal.Vector(scale, scale, scale))
        a.static_mesh_component.set_mobility(unreal.ComponentMobility.MOVABLE)
        if label == "PhotoSet_Sky":
            a.static_mesh_component.set_cast_shadow(False)
    for label, bp, off, yaw, garment, idle in PEOPLE:
        cls = unreal.EditorAssetLibrary.load_blueprint_class(bp)
        a = acts.spawn_actor_from_class(cls, V(off), unreal.Rotator(roll=0, pitch=0, yaw=yaw))
        a.set_actor_label(label)
        g = unreal.load_asset(garment)
        for c in a.get_components_by_class(unreal.SkeletalMeshComponent):
            m = c.get_skinned_asset()
            if m and "Outfit" in m.get_name() and g:
                c.set_skinned_asset_and_update(g)
                c.set_editor_property("override_materials", [])
                for i, sm in enumerate(g.get_editor_property("materials")):
                    c.set_material(i, sm.get_editor_property("material_interface"))
    label, off, look, focal = CAM
    cam = acts.spawn_actor_from_class(unreal.CineCameraActor, V(off),
                                      unreal.MathLibrary.find_look_at_rotation(V(off), V(look)))
    cam.set_actor_label(label)
    cc = cam.get_cine_camera_component()
    try:
        cc.set_editor_property("current_focal_length", focal)
        fs = cc.get_editor_property("focus_settings")
        fs.set_editor_property("manual_focus_distance", 330.0)
        cc.set_editor_property("focus_settings", fs)
    except Exception as exc:
        log(f"camera settings partly skipped: {exc}")
    pp = cc.get_editor_property("post_process_settings")
    for prop, val in (("override_auto_exposure_method", True),
                      ("auto_exposure_method", unreal.AutoExposureMethod.AEM_MANUAL),
                      ("override_auto_exposure_apply_physical_camera_exposure", True),
                      ("auto_exposure_apply_physical_camera_exposure", False),
                      ("override_auto_exposure_bias", True), ("auto_exposure_bias", EXPOSURE_BIAS)):
        pp.set_editor_property(prop, val)
    cc.set_editor_property("post_process_settings", pp)
    cc.set_editor_property("post_process_blend_weight", 1.0)
    log("set built")


def pie_world():
    ws = unreal.EditorLevelLibrary.get_pie_worlds(False)
    return ws[0] if ws else None


def pie_actor(w, label):
    for a in unreal.GameplayStatics.get_all_actors_of_class(w, unreal.Actor):
        try:
            if a.get_actor_label() == label:
                return a
        except Exception:
            pass
    return None


def pose_and_frame(w):
    for label, bp, off, yaw, garment, idle in PEOPLE:
        a = pie_actor(w, label)
        anim = unreal.load_asset(idle)
        if a is None or anim is None:
            log(f"PIE: {label} or idle missing")
            continue
        body = next((c for c in a.get_components_by_class(unreal.SkeletalMeshComponent)
                     if c.get_name().startswith("Body")), None)
        if body:
            body.set_animation_mode(unreal.AnimationMode.ANIMATION_SINGLE_NODE)
            body.play_animation(anim, True)
    cam = pie_actor(w, CAM[0])
    unreal.GameplayStatics.get_player_controller(w, 0).set_view_target_with_blend(cam, 0.0)


def tick(dt):
    if ST["busy"]:
        return
    ST["busy"] = True
    try:
        now = time.time()
        if ST["step"] == "build":
            build_set()
            ST["step"], ST["t"] = "pie", now
        elif ST["step"] == "pie" and now - ST["t"] > 3:
            les.editor_request_begin_play()
            ST["step"], ST["t"] = "wait_pie", now
        elif ST["step"] == "wait_pie" and pie_world() is not None and now - ST["t"] > 8:
            pose_and_frame(pie_world())
            ST["step"], ST["t"] = "settle", now
        elif ST["step"] == "settle" and now - ST["t"] > 6:
            pose_and_frame(pie_world())          # re-assert the view target after the director's BeginPlay
            ST["shot_before"] = set(os.listdir(SHOTS)) if os.path.isdir(SHOTS) else set()
            unreal.SystemLibrary.execute_console_command(pie_world(), "HighResShot 2")
            ST["step"], ST["t"] = "wait_shot", now
        elif ST["step"] == "wait_shot":
            new = (set(os.listdir(SHOTS)) if os.path.isdir(SHOTS) else set()) - ST["shot_before"]
            if new or now - ST["t"] > 40:
                log(f"screenshot: {sorted(new)}")
                les.editor_request_end_play()
                ST["step"], ST["t"] = "cleanup", now
        elif ST["step"] == "cleanup" and pie_world() is None and now - ST["t"] > 3:
            unreal.unregister_slate_post_tick_callback(ST["h"])
            log("done: close the editor WITHOUT saving (the set stays unsaved in the level)")
    except Exception:
        import traceback
        log("FAILED " + traceback.format_exc())
        try:
            les.editor_request_end_play()
        except Exception:
            pass
        unreal.unregister_slate_post_tick_callback(ST["h"])
    finally:
        ST["busy"] = False


ST["h"] = unreal.register_slate_post_tick_callback(tick)
